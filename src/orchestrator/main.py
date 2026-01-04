"""
AI Assistant using Microsoft Agent Framework + Dynamic Tool Loader.

A general-purpose, extensible AI agent that dynamically loads tools from
config/tools/*.json files and automatically discovers services using a
strict naming convention.

NAMING CONVENTION (Required for auto-discovery)
===============================================

config/tools/<NAME>.json         → Tool config file
src/<NAME>/service.py            → Service implementation class: <NAME>Service

Example:
  config/tools/weather.json → src/weather/service.py (WeatherService)

SERVICE INTERFACE
=================

All services must implement:

    def run(self, tool_call: Dict[str, Any]) -> str:
        # Extract parameters from tool_call (provided by LLM)
        query = tool_call.get('query', '')
        
        # Execute your logic
        result = self._do_something(query)
        
        # Return as string
        return str(result)

CONFIGURATION
=============

All configuration is in TOML format:
- config/agent.toml (recommended)
- or pyproject.toml [tool.agent] section

Environment variables can override TOML settings:
- AZURE_OPENAI_ENDPOINT
- AZURE_OPENAI_DEPLOYMENT
- AZURE_OPENAI_API_VERSION

ADDING NEW TOOLS (3 Steps)
==========================

1. Create config file: config/tools/<NAME>.json
   - Define function name, description, and parameters
   
2. Create service: src/<NAME>/service.py with <NAME>Service class
   - Implement run(tool_call) -> str method
   
3. (Optional) Add tool-specific config in agent.toml:
   [agent.tools.<NAME>]
   setting = "value"
"""

from pathlib import Path
from typing import Any, Dict

import structlog
from agent_framework import ChatAgent
from agent_framework.azure import AzureOpenAIChatClient
from azure.identity import DefaultAzureCredential

from src.orchestrator.config import get_config, AgentConfig
from src.orchestrator.loader import load_and_register_tools
from src.orchestrator.middleware import function_call_middleware

logger = structlog.get_logger(__name__)


def _load_system_prompt(config: AgentConfig) -> str:
    """Load system prompt from configuration file."""
    prompt_path = Path(config.system_prompt_file)
    
    if not prompt_path.exists():
        raise FileNotFoundError(
            f"System prompt file not found: {config.system_prompt_file}"
        )
    
    prompt = prompt_path.read_text(encoding="utf-8").strip()
    logger.info("Loaded system prompt", prompt_file=config.system_prompt_file)
    return prompt


class AIAssistant:
    """
    AI Assistant with dynamic tool loading and service discovery.
    
    Uses Microsoft Agent Framework to reason across multiple data sources.
    Tools are discovered from config/tools/*.json files and matched to services
    using naming convention: config/tools/<NAME>.json → src/<NAME>/service.py
    
    Services implement the run(tool_call) -> str method.
    """

    def __init__(self, config: AgentConfig = None) -> None:
        """
        Initialize assistant with Azure OpenAI and load tools dynamically.
        
        Args:
            config: Optional AgentConfig instance. If not provided, loads from
                   config/agent.toml or pyproject.toml
        """
        # Load configuration
        self.config = config or get_config()
        self.config.validate()
        
        # Load system prompt
        self.system_prompt = _load_system_prompt(self.config)
        self.tools: list = []
        
        # Initialize Azure OpenAI client
        self.chat_client = AzureOpenAIChatClient(
            endpoint=self.config.azure_openai_endpoint,
            deployment_name=self.config.azure_openai_deployment,
            credential=DefaultAzureCredential(),
        )
        
        # Load all tools dynamically
        self._load_tools()
        
        # Create agent with tools and middleware
        self.agent = ChatAgent(
            chat_client=self.chat_client,
            instructions=self.system_prompt,
            tools=self.tools,
            middleware=[function_call_middleware],
        )
        
        logger.info(
            "Initialized AI Assistant",
            tools_count=len(self.tools),
            deployment=self.config.azure_openai_deployment
        )

    def _load_tools(self) -> None:
        """
        Load and register all tools from config/tools/*.json files.
        
        Tool loader scans the tools directory, discovers tool configurations,
        finds or creates corresponding services, and registers tool functions.
        """
        tools_loaded = load_and_register_tools(
            self,
            config_dir=self.config.tools_config_dir
        )
        logger.info("Tools loaded via dynamic loader", count=tools_loaded)

    async def process_question(self, question: str) -> Dict[str, Any]:
        """
        Process a question using the Agent Framework.

        The Agent Framework automatically handles:
        - Agentic reasoning loop
        - Tool selection and calling
        - Context management
        - Multi-step reasoning
        - Loop termination

        Args:
            question: User's question to process

        Returns:
            Dictionary containing:
                - question: Original question
                - response: Agent's response text
                - success: Whether processing succeeded
        """
        logger.info("Processing question", question=question[:100])

        try:
            result = await self.agent.run(question)
            
            logger.info("Processing completed successfully")
            return {
                "question": question,
                "response": result.text,
                "success": True,
            }
        except Exception as e:
            logger.error("Processing failed", error=str(e))
            return {
                "question": question,
                "response": f"Error: {str(e)}",
                "success": False,
            }

    async def close(self) -> None:
        """Close resources and cleanup."""
        for attr_name in dir(self):
            if attr_name.endswith('_service'):
                service = getattr(self, attr_name, None)
                if service and hasattr(service, 'close'):
                    try:
                        service.close()
                        logger.debug("Closed service", service_name=attr_name)
                    except Exception as e:
                        logger.warning(
                            "Failed to close service", 
                            service_name=attr_name, 
                            error=str(e)
                        )
        logger.info("AI Assistant closed")


# Singleton instance for convenience
_assistant_instance = None


async def process_query(question: str) -> str:
    """
    Simple helper function to process a query using the AI Assistant.
    Creates a singleton instance for efficiency.
    
    Args:
        question: User's question to process
        
    Returns:
        str: Agent's response text
    """
    global _assistant_instance
    
    if _assistant_instance is None:
        _assistant_instance = AIAssistant()
        logger.info("Created new AI Assistant instance")
    
    result = await _assistant_instance.process_question(question)
    return result["response"]


async def main():
    """Example usage of the AI Assistant."""
    assistant = AIAssistant()
    
    try:
        result = await assistant.process_question("Hello! What can you help me with?")
        print(f"Response: {result['response']}")
    finally:
        await assistant.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
