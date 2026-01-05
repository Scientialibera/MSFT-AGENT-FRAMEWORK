"""
MCP (Model Context Protocol) loader for the AI Assistant.

Loads and manages MCP server connections from configuration.
Supports three MCP transport types:
- stdio: Local process-based MCP servers
- http: HTTP/SSE MCP servers  
- websocket: WebSocket MCP servers
"""

from typing import Any, Dict, List, Optional
from contextlib import AsyncExitStack

import structlog

# Import MCP tool types from Agent Framework
try:
    from agent_framework import MCPStdioTool, MCPStreamableHTTPTool, MCPWebsocketTool
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    MCPStdioTool = None
    MCPStreamableHTTPTool = None
    MCPWebsocketTool = None

logger = structlog.get_logger(__name__)


class MCPManager:
    """
    Manages MCP server connections for the AI Assistant.
    
    Loads MCP configurations and creates appropriate tool instances
    based on transport type (stdio, http, websocket).
    """
    
    def __init__(self):
        """Initialize the MCP manager."""
        self._exit_stack: Optional[AsyncExitStack] = None
        self._mcp_tools: List[Any] = []
        self._initialized = False
        
    async def load_mcp_servers(self, mcp_configs: List[Dict[str, Any]]) -> List[Any]:
        """
        Load and initialize MCP servers from configuration.
        
        Args:
            mcp_configs: List of MCP server configurations, each containing:
                - name: Friendly name for the MCP server
                - type: "stdio", "http", or "websocket"
                - enabled: Whether this MCP is enabled (default: true)
                
                For stdio type:
                - command: Command to run (e.g., "uvx", "npx")
                - args: List of arguments
                - env: Optional environment variables dict
                
                For http type:
                - url: HTTP URL of the MCP server
                - headers: Optional headers dict (for auth, etc.)
                
                For websocket type:
                - url: WebSocket URL (wss://...)
                - headers: Optional headers dict (for auth, etc.)
                
        Returns:
            List of initialized MCP tool instances
        """
        if not MCP_AVAILABLE:
            logger.warning(
                "MCP tools not available. Install agent-framework with MCP support."
            )
            return []
        
        if not mcp_configs:
            logger.debug("No MCP servers configured")
            return []
        
        self._exit_stack = AsyncExitStack()
        await self._exit_stack.__aenter__()
        
        for config in mcp_configs:
            # Skip disabled MCPs
            if not config.get("enabled", True):
                logger.debug("Skipping disabled MCP", name=config.get("name"))
                continue
                
            try:
                mcp_tool = await self._create_mcp_tool(config)
                if mcp_tool:
                    self._mcp_tools.append(mcp_tool)
                    logger.info(
                        "Loaded MCP server",
                        name=config.get("name"),
                        type=config.get("type")
                    )
            except Exception as e:
                logger.error(
                    "Failed to load MCP server",
                    name=config.get("name"),
                    error=str(e)
                )
        
        self._initialized = True
        logger.info("MCP servers loaded", count=len(self._mcp_tools))
        return self._mcp_tools
    
    async def _create_mcp_tool(self, config: Dict[str, Any]) -> Optional[Any]:
        """Create an MCP tool instance based on configuration."""
        mcp_type = config.get("type", "").lower()
        name = config.get("name", "unnamed-mcp")
        
        if mcp_type == "stdio":
            return await self._create_stdio_mcp(config)
        elif mcp_type == "http":
            return await self._create_http_mcp(config)
        elif mcp_type == "websocket":
            return await self._create_websocket_mcp(config)
        else:
            logger.error("Unknown MCP type", name=name, type=mcp_type)
            return None
    
    async def _create_stdio_mcp(self, config: Dict[str, Any]) -> Any:
        """Create a stdio-based MCP tool."""
        command = config.get("command")
        if not command:
            raise ValueError(f"MCP '{config.get('name')}' requires 'command' for stdio type")
        
        mcp_tool = MCPStdioTool(
            name=config.get("name", "stdio-mcp"),
            command=command,
            args=config.get("args", []),
            env=config.get("env"),
        )
        
        # Enter the async context to initialize the MCP
        initialized_tool = await self._exit_stack.enter_async_context(mcp_tool)
        return initialized_tool
    
    async def _create_http_mcp(self, config: Dict[str, Any]) -> Any:
        """Create an HTTP-based MCP tool."""
        url = config.get("url")
        if not url:
            raise ValueError(f"MCP '{config.get('name')}' requires 'url' for http type")
        
        mcp_tool = MCPStreamableHTTPTool(
            name=config.get("name", "http-mcp"),
            url=url,
            headers=config.get("headers", {}),
        )
        
        initialized_tool = await self._exit_stack.enter_async_context(mcp_tool)
        return initialized_tool
    
    async def _create_websocket_mcp(self, config: Dict[str, Any]) -> Any:
        """Create a WebSocket-based MCP tool."""
        url = config.get("url")
        if not url:
            raise ValueError(f"MCP '{config.get('name')}' requires 'url' for websocket type")
        
        mcp_tool = MCPWebsocketTool(
            name=config.get("name", "websocket-mcp"),
            url=url,
            headers=config.get("headers", {}),
        )
        
        initialized_tool = await self._exit_stack.enter_async_context(mcp_tool)
        return initialized_tool
    
    @property
    def tools(self) -> List[Any]:
        """Get list of loaded MCP tools."""
        return self._mcp_tools
    
    async def close(self) -> None:
        """Close all MCP connections."""
        if self._exit_stack:
            try:
                await self._exit_stack.aclose()
                logger.info("Closed all MCP connections")
            except Exception as e:
                logger.error("Error closing MCP connections", error=str(e))
            finally:
                self._exit_stack = None
                self._mcp_tools = []
                self._initialized = False


def parse_mcp_configs(config_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Parse MCP configurations from agent config.
    
    Supports two formats in TOML:
    
    1. Array format (recommended for multiple MCPs):
        [[agent.mcp]]
        name = "calculator"
        type = "stdio"
        command = "uvx"
        args = ["mcp-server-calculator"]
        
        [[agent.mcp]]
        name = "docs"
        type = "http"
        url = "https://api.example.com/mcp"
    
    2. Table format (for single MCP or named MCPs):
        [agent.mcp.calculator]
        type = "stdio"
        command = "uvx"
        args = ["mcp-server-calculator"]
    
    Args:
        config_dict: The agent configuration dictionary
        
    Returns:
        List of MCP configuration dictionaries
    """
    mcp_config = config_dict.get("mcp", {})
    
    # If it's a list, return as-is
    if isinstance(mcp_config, list):
        return mcp_config
    
    # If it's a dict, convert to list format
    if isinstance(mcp_config, dict):
        mcp_list = []
        for name, settings in mcp_config.items():
            if isinstance(settings, dict):
                # Add name from key if not specified
                if "name" not in settings:
                    settings["name"] = name
                mcp_list.append(settings)
        return mcp_list
    
    return []
