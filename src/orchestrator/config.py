"""
Configuration management using TOML files.

Loads agent configuration from config/agent.toml or pyproject.toml.
Environment variables can override TOML settings with AGENT_ prefix.
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import structlog

# Python 3.11+ has tomllib built-in, otherwise use tomli
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        raise ImportError("Please install 'tomli' for Python < 3.11: pip install tomli")

logger = structlog.get_logger(__name__)


class AgentConfig:
    """Configuration container for the AI Agent."""
    
    def __init__(self, config_dict: Dict[str, Any]):
        """Initialize configuration from dictionary."""
        self._config = config_dict
        
        # Core settings
        self.system_prompt_file = self._get("system_prompt", "config/system_prompt.txt")
        self.log_level = self._get("log_level", "INFO")
        
        # Azure OpenAI settings
        azure_config = self._config.get("azure_openai", {})
        self.azure_openai_endpoint = self._get_env_or_config(
            "AZURE_OPENAI_ENDPOINT", 
            azure_config.get("endpoint", "")
        )
        self.azure_openai_deployment = self._get_env_or_config(
            "AZURE_OPENAI_DEPLOYMENT",
            azure_config.get("deployment", "")
        )
        self.azure_openai_api_version = self._get_env_or_config(
            "AZURE_OPENAI_API_VERSION",
            azure_config.get("api_version", "2024-10-01-preview")
        )
        
        # Tools settings
        tools_config = self._config.get("tools", {})
        self.tools_config_dir = tools_config.get("config_dir", "config/tools")
        self.tool_settings = {
            k: v for k, v in tools_config.items() 
            if isinstance(v, dict)
        }
        
        # MCP settings
        from src.orchestrator.mcp_loader import parse_mcp_configs
        self.mcp_configs = parse_mcp_configs(self._config)
        
        # Workflow settings
        from src.orchestrator.workflow_loader import parse_workflow_configs
        self.workflow_configs = parse_workflow_configs(self._config)
        
    def _get(self, key: str, default: Any = None) -> Any:
        """Get configuration value with default."""
        return self._config.get(key, default)
    
    def _get_env_or_config(self, env_key: str, config_value: str) -> str:
        """Get value from environment variable or config, env takes precedence."""
        return os.getenv(env_key, config_value)
    
    def get_tool_config(self, tool_name: str) -> Dict[str, Any]:
        """Get configuration for a specific tool."""
        return self.tool_settings.get(tool_name, {})
    
    def validate(self) -> None:
        """Validate required configuration values."""
        errors = []
        
        if not self.azure_openai_endpoint:
            errors.append(
                "Azure OpenAI endpoint is required. "
                "Set in config/agent.toml [agent.azure_openai] endpoint or AZURE_OPENAI_ENDPOINT env var"
            )
        
        if not self.azure_openai_deployment:
            errors.append(
                "Azure OpenAI deployment is required. "
                "Set in config/agent.toml [agent.azure_openai] deployment or AZURE_OPENAI_DEPLOYMENT env var"
            )
        
        if errors:
            for error in errors:
                logger.error("Configuration error", error=error)
            raise ValueError("Configuration validation failed:\n" + "\n".join(errors))
        
        logger.info(
            "Configuration validated",
            endpoint=self.azure_openai_endpoint[:30] + "..." if self.azure_openai_endpoint else None,
            deployment=self.azure_openai_deployment
        )


def load_config(config_path: Optional[str] = None) -> AgentConfig:
    """
    Load agent configuration from TOML file.
    
    Searches in order:
    1. Explicit config_path if provided
    2. config/agent.toml
    3. pyproject.toml [tool.agent] section
    
    Args:
        config_path: Optional explicit path to config file
        
    Returns:
        AgentConfig instance with loaded configuration
        
    Raises:
        FileNotFoundError: If no config file found
        ValueError: If configuration is invalid
    """
    config_dict: Dict[str, Any] = {}
    
    # List of paths to try
    search_paths = []
    
    if config_path:
        search_paths.append(Path(config_path))
    
    search_paths.extend([
        Path("config/agent.toml"),
        Path("pyproject.toml"),
    ])
    
    for path in search_paths:
        if path.exists():
            logger.info("Loading configuration", path=str(path))
            
            with open(path, "rb") as f:
                data = tomllib.load(f)
            
            # Check if it's pyproject.toml (need to look under [tool.agent])
            if path.name == "pyproject.toml":
                config_dict = data.get("tool", {}).get("agent", {})
                if not config_dict:
                    logger.debug("No [tool.agent] section in pyproject.toml")
                    continue
            else:
                # Direct agent.toml uses [agent] section
                config_dict = data.get("agent", {})
            
            if config_dict:
                logger.info("Configuration loaded successfully", path=str(path))
                break
    
    if not config_dict:
        raise FileNotFoundError(
            "No configuration found. Create config/agent.toml or add [tool.agent] to pyproject.toml"
        )
    
    return AgentConfig(config_dict)


# Global config instance (lazy loaded)
_config: Optional[AgentConfig] = None


def get_config() -> AgentConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = load_config()
    return _config
