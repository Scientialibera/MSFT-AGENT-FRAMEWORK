"""
Agent Framework Middleware

Provides function-level middleware to intercept and monitor tool calls.
Follows Agent Framework middleware patterns for logging, security, and transformation.
"""

from typing import Callable, Awaitable
import structlog

# Import Agent Framework middleware types
# Note: Adjust imports based on actual agent_framework package structure
try:
    from agent_framework import FunctionInvocationContext
except ImportError:
    # Fallback if agent_framework not available or different structure
    # Define minimal type for development
    class FunctionInvocationContext:
        """Minimal FunctionInvocationContext for type hints."""
        function: any
        args: dict
        result: any

logger = structlog.get_logger(__name__)


async def function_call_middleware(
    context: FunctionInvocationContext,
    next: Callable[[FunctionInvocationContext], Awaitable[None]],
) -> None:
    """
    Middleware that intercepts function (tool) calls.
    
    This middleware:
    1. Logs when a function is called
    2. Passes control to the actual function execution
    3. Logs the result
    
    Future enhancements can add:
    - Input validation and sanitization
    - Rate limiting and quotas
    - Security checks and authorization
    - Result transformation
    - Error handling and retry logic
    - Performance monitoring
    
    Args:
        context: Function invocation context with function metadata and arguments
        next: Continuation function to invoke the actual tool
    """
    # Log function call start
    function_name = getattr(context.function, 'name', 'unknown')
    args_preview = str(context.args)[:200] if hasattr(context, 'args') else 'N/A'
    
    logger.info(
        "[MIDDLEWARE] Function call starting",
        function_name=function_name,
        args_preview=args_preview
    )
    
    try:
        # Continue to actual function execution
        await next(context)
        
        # Log successful completion
        result_preview = str(context.result)[:200] if hasattr(context, 'result') and context.result else 'N/A'
        
        logger.info(
            "[MIDDLEWARE] Function call completed",
            function_name=function_name,
            result_preview=result_preview
        )
        
    except Exception as e:
        # Log errors
        logger.error(
            "[MIDDLEWARE] Function call failed",
            function_name=function_name,
            error=str(e),
            exc_info=True
        )
        # Re-raise to let agent framework handle it
        raise


# Additional middleware examples (not currently used, but available for future)

async def security_middleware(
    context: FunctionInvocationContext,
    next: Callable[[FunctionInvocationContext], Awaitable[None]],
) -> None:
    """
    Example: Security middleware for authorization checks.
    
    Could validate:
    - User permissions for specific tools
    - Rate limits and quotas
    - Input sanitization (SQL injection prevention)
    """
    function_name = getattr(context.function, 'name', 'unknown')
    
    logger.debug(
        "[SECURITY MIDDLEWARE] Checking authorization",
        function_name=function_name
    )
    
    # TODO: Add actual security checks here
    # For now, just pass through
    
    await next(context)


async def performance_middleware(
    context: FunctionInvocationContext,
    next: Callable[[FunctionInvocationContext], Awaitable[None]],
) -> None:
    """
    Example: Performance monitoring middleware.
    
    Tracks execution time and logs slow operations.
    """
    import time
    
    function_name = getattr(context.function, 'name', 'unknown')
    start_time = time.time()
    
    logger.debug(
        "[PERFORMANCE MIDDLEWARE] Starting timer",
        function_name=function_name
    )
    
    try:
        await next(context)
    finally:
        elapsed_time = time.time() - start_time
        
        logger.info(
            "[PERFORMANCE MIDDLEWARE] Execution complete",
            function_name=function_name,
            elapsed_seconds=round(elapsed_time, 3)
        )
        
        # Warn about slow operations
        if elapsed_time > 10.0:
            logger.warning(
                "[PERFORMANCE MIDDLEWARE] Slow operation detected",
                function_name=function_name,
                elapsed_seconds=round(elapsed_time, 3)
            )


# Middleware stack - combine multiple middleware
async def combined_middleware(
    context: FunctionInvocationContext,
    next: Callable[[FunctionInvocationContext], Awaitable[None]],
) -> None:
    """
    Example: Combined middleware stack.
    
    Applies multiple middleware in sequence:
    1. Logging
    2. Security
    3. Performance monitoring
    """
    # Create nested middleware chain
    async def with_performance(ctx):
        await performance_middleware(ctx, next)
    
    async def with_security(ctx):
        await security_middleware(ctx, with_performance)
    
    await function_call_middleware(context, with_security)
