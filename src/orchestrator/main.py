"""
AI Assistant using Microsoft Agent Framework + Dynamic Tool Loader.

Dynamically loads tools from config/tools/*.json files and automatically discovers
services using a strict naming convention. Services implement data query logic and
return string results. The agent autonomously reasons and chains tool calls to
answer complex questions across multiple data sources.

NAMING CONVENTION (Required for auto-discovery)
===============================================

config/tools/<NAME>.json         → Tool config file
src/<NAME>/service.py            → Service implementation class: <NAME>Service

Example:
  config/tools/fabric_data.json → src/fabric_data/service.py (FabricDataService)

SERVICE INTERFACE
=================

All services must implement:

    def run(self, tool_call: Dict[str, Any]) -> str:
        # Extract parameters from tool_call (provided by LLM)
        query = tool_call.get('query', '')
        reasoning = tool_call.get('reasoning', '')
        
        # Execute query logic
        result = self._query_data(query)
        
        # Return as string
        return str(result)

ADDING NEW TOOLS (3 Steps)
==========================

1. Create config file: config/tools/<NAME>.json
   - Define function name, description, and parameters
   
2. Create service: src/<NAME>/service.py with <NAME>Service class
   - Implement run(tool_call, tool_config) -> str method
   - Optionally provide get_<NAME>_service() factory function
"""

# Load environment variables once at module import
from dotenv import load_dotenv
load_dotenv()

import os
from pathlib import Path
from typing import Dict, Any

import structlog
from agent_framework import ChatAgent
from agent_framework.azure import AzureOpenAIChatClient
from azure.identity import DefaultAzureCredential

from src.orchestrator.loader import load_and_register_tools
from src.orchestrator.middleware import function_call_middleware

logger = structlog.get_logger(__name__)

# System prompt selection based on mode
AGENT_MODE = os.getenv("AGENT_MODE", "full").lower()  # "full" or "csv_only"
if AGENT_MODE == "csv_only":
    SYSTEM_PROMPT_FILE = "config/orchestrator/system_prompt_csv_only.txt"
else:
    SYSTEM_PROMPT_FILE = "config/orchestrator/system_prompt_full.txt"


def _load_system_prompt() -> str:
    """Load system prompt from configuration file based on AGENT_MODE."""
    try:
        prompt_path = Path(SYSTEM_PROMPT_FILE)
        if not prompt_path.exists():
            raise FileNotFoundError(
                f"System prompt file not found: {SYSTEM_PROMPT_FILE}"
            )
        logger.info(
            "Loaded system prompt",
            mode=AGENT_MODE,
            prompt_file=SYSTEM_PROMPT_FILE
        )
        return prompt_path.read_text(encoding="utf-8").strip()
    except Exception as e:
        logger.error(
            "Failed to load system prompt",
            error=str(e),
            mode=AGENT_MODE,
            prompt_file=SYSTEM_PROMPT_FILE
        )
        raise


class AIAssistant:
    """
    AI Assistant with dynamic tool loading and service discovery.
    
    Uses Microsoft Agent Framework to reason across multiple data sources.
    Tools are discovered from config/tools/*.json files and matched to services
    using strict naming convention: config/tools/<NAME>.json → src/<NAME>/service.py
    
    Services implement the run(tool_call, tool_config) -> str method.
    """

    def __init__(self) -> None:
        """
        Initialize assistant with Azure OpenAI and load tools dynamically.
        
        Reads Azure OpenAI configuration from environment variables (.env):
        - AZURE_OPENAI_ENDPOINT
        - AZURE_OPENAI_CHAT_DEPLOYMENT
        - AZURE_OPENAI_API_VERSION (optional, default: 2024-10-01-preview)
        
        Services can be pre-initialized here or created automatically based on
        naming convention. Tool loader scans config/tools/*.json and discovers
        corresponding services in src/<NAME>/service.py.
        """
        # Load Azure OpenAI config from environment
        self.endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        if not self.endpoint:
            raise ValueError("AZURE_OPENAI_ENDPOINT environment variable is required")
        
        self.chat_deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT")
        if not self.chat_deployment:
            raise ValueError("AZURE_OPENAI_CHAT_DEPLOYMENT environment variable is required")
        
        self.api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-01-preview")
        
        self.system_prompt = _load_system_prompt()
        self.tools: list = []
        
        # Initialize Azure OpenAI client
        self.chat_client = AzureOpenAIChatClient(
            endpoint=self.endpoint,
            deployment_name=self.chat_deployment,
            credential=DefaultAzureCredential(),
        )
        
        # Load all tools (tool_loader handles service discovery/creation)
        self._load_tools()
        
        # Create agent with tools and middleware
        self.agent = ChatAgent(
            chat_client=self.chat_client,
            instructions=self.system_prompt,
            tools=self.tools,
            middleware=[function_call_middleware],
        )
        
        logger.info("Initialized AI Assistant with Agent Framework")

    def _load_tools(self) -> None:
        """
        Load and register all tools from config/tools/*.json files.
        
        Tool loader scans the config/tools directory, discovers tool configurations,
        finds or creates corresponding services, and registers tool functions
        with the agent. Services are discovered using naming convention:
        config/tools/<NAME>.json → src/<NAME>/service.py (class <NAME>Service)
        """
        tools_loaded = load_and_register_tools(
            self,
            config_dir="config/tools"
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
        logger.info("Starting agent processing", question=question)

        try:
            # Run the agent - it handles all reasoning and tool calls internally
            result = await self.agent.run(question)

            logger.info("Agent processing completed", question=question)

            return {
                "question": question,
                "response": result.text,
                "success": True,
            }
        except Exception as e:
            logger.error("Agent processing failed", error=str(e), question=question)
            return {
                "question": question,
                "response": f"Error: {str(e)}",
                "success": False,
            }

    async def close(self) -> None:
        """Close resources and cleanup."""
        # Dynamically find and close all services
        for attr_name in dir(self):
            if attr_name.endswith('_service'):
                service = getattr(self, attr_name, None)
                if service and hasattr(service, 'close'):
                    try:
                        service.close()
                        logger.debug("Closed service", service_name=attr_name)
                    except Exception as e:
                        logger.warning("Failed to close service", service_name=attr_name, error=str(e))
        logger.info("AI Assistant closed")


# Singleton instance for testing
_assistant_instance = None


async def process_query(question: str) -> str:
    """
    Simple helper function to process a query using the AI Assistant.
    Creates a singleton instance for efficiency during testing.
    
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
