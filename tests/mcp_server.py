"""
FastMCP Server - Expose AI Assistant as Model Context Protocol Server (via stdio)

This module exposes the AI Assistant as an MCP server using FastMCP.
The server communicates via stdio, making it compatible with any MCP client.

FastMCP is a modern, lightweight MCP framework that handles all protocol details
while allowing you to focus on defining tools and resources.

To use:
1. Set ENABLE_MCP_SERVER=True in config/settings.py or .env
2. Run: python tests/mcp_server.py
3. Connect with an MCP client (e.g., Claude Desktop, FastMCP clients)

The agent's tools will be available as MCP tools to any MCP-compatible client.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Annotated

import structlog
from fastmcp import FastMCP
from pydantic import Field
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.orchestrator.main import AIAssistant

# Load environment variables
load_dotenv()

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================
# Configure logging to stderr to preserve stdout for MCP JSON-RPC protocol
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr,
    force=True,
)

structlog.configure(
    processors=[structlog.processors.JSONRenderer()],
    wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
    cache_logger_on_first_use=True,
)

logger = logging.getLogger(__name__)

# ============================================================================
# FASTMCP SERVER SETUP
# ============================================================================

# Create FastMCP server instance
mcp = FastMCP(
    name="DataAgentMCP",
    instructions="""
        You are a data assistant with access to business intelligence tools.
        You can query the Fabric Data Agent for financial and business data.
        Use the available tools to answer questions about data and provide insights.
    """,
)


def _initialize_assistant() -> AIAssistant:
    """
    Initialize the AI Assistant.
    
    Returns:
        AIAssistant: The initialized assistant with all tools loaded.
    """
    try:
        assistant = AIAssistant()
        logger.info("AI Assistant initialized")
        return assistant
    except Exception as e:
        logger.error(f"Failed to initialize assistant: {e}", exc_info=True)
        raise


async def main():
    """Run the FastMCP server."""
    
    # Check if MCP is enabled via environment
    enable_mcp = os.getenv("ENABLE_MCP_SERVER", "False").lower() == "true"
    if not enable_mcp:
        logger.error("MCP Server is disabled.")
        logger.error("To enable, set ENABLE_MCP_SERVER=True in .env")
        return
    
    logger.info("Starting FastMCP server...")
    
    try:
        # Initialize assistant once at startup
        assistant = _initialize_assistant()
        logger.info("AI Assistant ready")
        
        # Extract tools from the agent and register them with FastMCP
        # The agent's tools are Python functions we need to wrap as MCP tools
        
        @mcp.tool
        async def process_query(
            query: Annotated[
                str,
                Field(description="The data query or question to process"),
            ]
        ) -> str:
            """
            Process a query using the AI Assistant.
            
            The assistant will analyze your question, determine which tools are needed,
            and provide a comprehensive answer by potentially calling multiple tools
            and synthesizing the results.
            """
            try:
                logger.info(f"Processing query via MCP: {query}")
                
                # Use the agent's process_question method which handles
                # tool selection, execution, and synthesis
                result = await assistant.process_question(query)
                
                if result.get("success"):
                    logger.info(f"Query processed successfully: {query}")
                    return result.get("response", "No response returned")
                else:
                    logger.warning(f"Query processing returned error: {query}")
                    return result.get("response", "Error processing query")
                
            except Exception as e:
                logger.error(f"Query processing failed: {e}", exc_info=True)
                return f"Error processing query: {str(e)}"
        
        # Run the FastMCP server via stdio (default transport)
        logger.info("FastMCP server ready, accepting connections via stdio")
        await mcp.run_async()
        
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return
    except Exception as e:
        logger.error(f"MCP server error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    import asyncio
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("MCP Server stopped by user")
    except Exception as e:
        logger.error(f"MCP Server fatal error: {e}", exc_info=True)
        raise
