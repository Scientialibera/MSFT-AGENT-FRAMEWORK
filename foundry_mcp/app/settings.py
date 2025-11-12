"""
Configuration settings for Fabric Data Agent MCP Server.

This module loads and validates configuration from environment variables.
Uses pydantic for type validation and defaults.
"""

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All configuration is consolidated in a single .env file in the project root.
    See .env.example for the complete list of configuration variables.
    """

    # MCP Server Settings
    enable_mcp_server: bool = Field(
        default=False,
        description="Enable the MCP server",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )

    # Agent Configuration
    foundry_agent_name: str = Field(
        default="SmartSCMFabricAgenttemplate",
        description="Name of the Foundry agent to use/create",
    )

    # System Prompt Configuration
    foundry_system_prompt_file: str = Field(
        default="config/orchestrator/system_prompt.txt",
        description="Path to system prompt file for the agent",
    )

    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        case_sensitive = False


# Load settings from environment
settings = Settings()
