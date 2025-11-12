"""
FastMCP Server - Fabric Data Agent Account Query Tool

This module exposes Azure AI Foundry Fabric Data Agent as an MCP server using FastMCP.
The server communicates via stdio, making it compatible with any MCP client including
Claude Desktop and other AI applications.

FastMCP is a modern, lightweight MCP framework that handles all protocol details
while allowing you to focus on defining tools and resources.

## Architecture

The MCP server provides a single tool: `fabricdataagentaccount` which:
1. Accepts natural language queries about business intelligence and financial data
2. Routes requests to the Azure AI Foundry Fabric Data Agent
3. Returns structured results back to the MCP client

## Deployment

For local testing:
    Set ENABLE_MCP_SERVER=True in .env
    Run: python app/mcp_server.py

For Azure App Service deployment:
    - Build Docker image: docker build -f deployment/Dockerfile -t fabric-mcp:latest .
    - Push to ACR: docker tag fabric-mcp:latest <registry>.azurecr.io/fabric-mcp:latest
    - Deploy to App Service via Azure CLI or Portal

## Environment Variables

Required:
    - ENABLE_MCP_SERVER: Set to "True" to enable the server
    - AZURE_OPENAI_ENDPOINT: Azure OpenAI endpoint URL
    - AZURE_OPENAI_CHAT_DEPLOYMENT: Deployment name for the chat model
    - FABRIC_AGENT_ENDPOINT: (Optional) Custom endpoint for Fabric Data Agent

Optional:
    - AZURE_OPENAI_API_VERSION: OpenAI API version (default: 2024-10-01-preview)
    - LOG_LEVEL: Logging level (default: INFO)
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Annotated, Optional

import structlog
from dotenv import load_dotenv
from fastmcp import FastMCP
from pydantic import Field

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from foundry_mcp.agent_creation.fabric_agent import SmartSCMFoundryAgent
from src.fabric_data.service import FabricDataService

# ============================================================================
# CONFIGURATION
# ============================================================================

# Load environment variables from .env (optional - falls back to system env vars)
load_dotenv()

# Server configuration
ENABLE_MCP_SERVER = os.getenv("ENABLE_MCP_SERVER", "False").lower() == "true"
DIRECT_FDA = os.getenv("DIRECT_FDA", "False").lower() == "true"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Debug: Print configuration on startup
print(f"[STARTUP DEBUG] ENABLE_MCP_SERVER={os.getenv('ENABLE_MCP_SERVER')}", file=sys.stderr)
print(f"[STARTUP DEBUG] ENABLE_MCP_HTTP_SERVER={os.getenv('ENABLE_MCP_HTTP_SERVER')}", file=sys.stderr)
print(f"[STARTUP DEBUG] MCP_HTTP_PORT={os.getenv('MCP_HTTP_PORT')}", file=sys.stderr)
print(f"[STARTUP DEBUG] DIRECT_FDA={os.getenv('DIRECT_FDA')}", file=sys.stderr)

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================
# Configure logging to stderr to preserve stdout for MCP JSON-RPC protocol
# This is critical for MCP communication via stdio

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
    force=True,
)

# Silence noisy Azure SDK HTTP loggers
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
logging.getLogger("azure.identity").setLevel(logging.WARNING)
logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
    cache_logger_on_first_use=True,
)

logger = logging.getLogger(__name__)

# ============================================================================
# FASTMCP SERVER SETUP
# ============================================================================

# Create FastMCP server instance with system instructions
mcp = FastMCP(
    name="FabricDataAgentMCP",
    instructions="""
You are a data analyst assistant with access to the Fabric Data Agent.

You can help users with:
- Business intelligence queries and reporting
- Financial data analysis and insights
- Enterprise data exploration and discovery
- Data-driven decision support

When a user asks a data-related question:
1. Use the fabricdataagentaccount tool to query the Fabric Data Agent
2. Provide clear, actionable insights from the results
3. Ask clarifying questions if the query is ambiguous
4. Suggest additional relevant queries to explore the data deeper

Always be precise and cite the source data when providing information.
    """,
)

# Global agent instance (initialized once at startup)
_agent: Optional[SmartSCMFoundryAgent] = None
_fda_service: Optional[FabricDataService] = None


def _initialize_agent() -> SmartSCMFoundryAgent:
    """
    Initialize the Fabric Data Agent.

    Returns:
        SmartSCMFoundryAgent: The initialized agent connected to Fabric.

    Raises:
        EnvironmentError: If required environment variables are missing.
        Exception: If initialization fails.
    """
    global _agent

    if _agent is not None:
        logger.info("[AGENT] Using cached agent instance")
        return _agent

    try:
        logger.info("[AGENT] Initializing new Fabric Data Agent instance...")
        
        # Get configuration from environment
        agent_name = os.getenv("FOUNDRY_AGENT_NAME", "SmartSCMFabricAgenttemplate")
        system_prompt_file = os.getenv("FOUNDRY_SYSTEM_PROMPT_FILE", "config/orchestrator/system_prompt.txt")
        
        logger.info(f"[AGENT] Agent name: {agent_name}")
        logger.info(f"[AGENT] System prompt file: {system_prompt_file}")
        
        _agent = SmartSCMFoundryAgent(
            agent_name=agent_name,
            system_prompt_file=system_prompt_file
        )
        logger.info("[AGENT] ✓ Fabric Data Agent initialized successfully")
        return _agent

    except EnvironmentError as e:
        logger.error(f"[AGENT ERROR] Configuration error: {e}")
        raise
    except Exception as e:
        logger.error(f"[AGENT ERROR] Failed to initialize agent: {e}", exc_info=True)
        raise


def _initialize_direct_fda() -> FabricDataService:
    """
    Initialize the Direct Fabric Data Agent service.

    Returns:
        FabricDataService: The initialized direct FDA service.

    Raises:
        EnvironmentError: If required environment variables are missing.
        Exception: If initialization fails.
    """
    global _fda_service

    if _fda_service is not None:
        logger.info("[DIRECT FDA] Using cached FDA service instance")
        return _fda_service

    try:
        logger.info("[DIRECT FDA] Initializing Direct Fabric Data Agent service...")
        
        # Get configuration from environment
        tenant_id = os.getenv("TENANT_ID")
        data_agent_url = os.getenv("DATA_AGENT_URL")
        
        if not tenant_id or not data_agent_url:
            raise EnvironmentError("TENANT_ID and DATA_AGENT_URL are required for DIRECT_FDA mode")
        
        logger.info(f"[DIRECT FDA] Tenant ID: {tenant_id}")
        logger.info(f"[DIRECT FDA] Data Agent URL: {data_agent_url}")
        
        _fda_service = FabricDataService(
            tenant_id=tenant_id,
            data_agent_url=data_agent_url
        )
        logger.info("[DIRECT FDA] ✓ Direct Fabric Data Agent service initialized successfully")
        return _fda_service

    except EnvironmentError as e:
        logger.error(f"[DIRECT FDA ERROR] Configuration error: {e}")
        raise
    except Exception as e:
        logger.error(f"[DIRECT FDA ERROR] Failed to initialize direct FDA service: {e}", exc_info=True)
        raise


# ============================================================================
# MCP TOOL DEFINITIONS
# ============================================================================


@mcp.tool
async def fabricdataagentaccount(
    query: Annotated[
        str,
        Field(
            description="Natural language query for the Fabric Data Agent. "
            "Examples: 'What is the total revenue by region?', "
            "'Show me the top 10 customers by spending', "
            "'What trends do you see in Q3 sales?'"
        ),
    ],
) -> str:
    """
    Query the Fabric Data Agent for business intelligence and financial data.

    This tool connects to your enterprise data platform via Azure AI Foundry
    and Fabric, retrieving insights, analytics, and reporting data based on
    natural language queries.

    Args:
        query: The natural language question or data request

    Returns:
        str: The agent's response with data and insights

    Raises:
        str: Error message if the query fails
    """
    try:
        logger.info("=" * 80)
        logger.info(f"[TOOL CALL] fabricdataagentaccount")
        logger.info(f"[MODE] {'DIRECT FDA' if DIRECT_FDA else 'AI Foundry Agent'}")
        logger.info(f"[QUERY] {query[:200]}")
        logger.info("=" * 80)

        if DIRECT_FDA:
            # Direct FDA mode: Call Fabric Data Agent directly
            logger.info("[DIRECT FDA] Using direct Fabric Data Agent client")
            
            # Get the direct FDA service instance
            logger.info("[DIRECT FDA] Retrieving FDA service instance...")
            fda_service = _initialize_direct_fda()
            logger.info("[DIRECT FDA] FDA service instance ready")

            # Query the FDA directly
            logger.info("[PROCESSING] Sending query to Fabric Data Agent (direct)...")
            result = await asyncio.to_thread(fda_service.run, {"query": query})
            
        else:
            # AI Foundry Agent mode: Use existing AI Foundry wrapper
            logger.info("[AI FOUNDRY] Using AI Foundry agent wrapper")
            
            # Get the agent instance
            logger.info("[AGENT] Retrieving agent instance...")
            agent = _initialize_agent()
            logger.info("[AGENT] Agent instance ready")

            # Query the agent
            logger.info("[PROCESSING] Sending query to Fabric Data Agent (via AI Foundry)...")
            result = await asyncio.to_thread(agent.ask, query)
        
        logger.info("=" * 80)
        logger.info(f"[SUCCESS] Query completed")
        logger.info(f"[RESPONSE LENGTH] {len(result)} characters")
        logger.info(f"[RESPONSE PREVIEW] {result[:200]}...")
        logger.info("=" * 80)
        
        return result

    except Exception as e:
        error_msg = f"Query processing failed: {str(e)}"
        logger.error("=" * 80)
        logger.error(f"[ERROR] Tool execution failed")
        logger.error(f"[QUERY] {query[:200]}")
        logger.error(f"[ERROR MESSAGE] {error_msg}")
        logger.error("=" * 80)
        logger.error("Full traceback:", exc_info=True)
        return error_msg


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================


async def main() -> None:
    """
    Run the FastMCP server.

    This function:
    1. Checks if the MCP server is enabled
    2. Initializes the Fabric Data Agent
    3. Starts the FastMCP server via HTTP transport
    4. Handles graceful shutdown
    
    The server supports both:
    - STDIO transport: For local CLI and desktop applications
    - HTTP transport: For remote access and cloud deployment
    
    Transport is determined by ENABLE_MCP_HTTP_SERVER environment variable.
    """

    if not ENABLE_MCP_SERVER:
        logger.error("MCP Server is disabled")
        logger.error("To enable, set ENABLE_MCP_SERVER=True in .env")
        sys.exit(1)

    logger.info("=" * 80)
    logger.info("Starting Fabric Data Agent MCP Server")
    logger.info(f"[MODE] {'DIRECT FDA (bypassing AI Foundry)' if DIRECT_FDA else 'AI Foundry Agent'}")
    logger.info("=" * 80)

    try:
        # Don't initialize agent at startup - do it lazily on first tool call
        # This prevents startup delays and timeouts in Azure
        if DIRECT_FDA:
            logger.info("[STARTUP] Direct Fabric Data Agent client will be initialized on first use (lazy loading)")
        else:
            logger.info("[STARTUP] Fabric Data Agent will be initialized on first use (lazy loading)")

        # Check if HTTP transport is requested
        enable_http = os.getenv("ENABLE_MCP_HTTP_SERVER", "False").lower() == "true"
        
        if enable_http:
            # Start FastMCP server via HTTP transport
            http_port = int(os.getenv("MCP_HTTP_PORT", "8000"))
            logger.info("=" * 80)
            logger.info(f"[HTTP SERVER] Starting MCP HTTP server")
            logger.info(f"[PORT] {http_port}")
            logger.info(f"[ENDPOINT] http://0.0.0.0:{http_port}/mcp")
            logger.info(f"[TRANSPORT] Streamable-HTTP (FastMCP native)")
            logger.info("=" * 80)
            await mcp.run_async(transport="http", host="0.0.0.0", port=http_port)
        else:
            # Start FastMCP server via stdio (default transport)
            logger.info("=" * 80)
            logger.info("[STDIO SERVER] Starting MCP stdio server")
            logger.info("[TRANSPORT] STDIO")
            logger.info("=" * 80)
            await mcp.run_async()

    except EnvironmentError as e:
        logger.error("=" * 80)
        logger.error("[FATAL] Configuration error")
        logger.error(f"[ERROR] {e}")
        logger.error("=" * 80)
        sys.exit(1)
    except Exception as e:
        logger.error("=" * 80)
        logger.error("[FATAL] MCP server error")
        logger.error(f"[ERROR] {e}")
        logger.error("=" * 80)
        logger.error("Full traceback:", exc_info=True)
        sys.exit(1)


# ============================================================================
# SCRIPT ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("MCP Server stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"MCP Server fatal error: {e}", exc_info=True)
        sys.exit(1)
