"""
Orchestrator module - DEPRECATED, use src.agent, src.config, src.loaders instead.

This module is kept for backwards compatibility and re-exports from new locations.
"""

import warnings

warnings.warn(
    "src.orchestrator is deprecated. Use src.agent, src.config, or src.loaders instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new locations for backwards compatibility
from src.agent import AIAssistant, process_query
from src.config import get_config, load_config, AgentConfig
from src.loaders import load_and_register_tools, MCPManager

__all__ = [
    "AIAssistant",
    "process_query", 
    "get_config",
    "load_config",
    "AgentConfig",
    "load_and_register_tools",
    "MCPManager",
]
