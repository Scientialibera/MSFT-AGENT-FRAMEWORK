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
from typing import Any, Dict, Optional

import structlog
from agent_framework import ChatAgent
from agent_framework.azure import AzureOpenAIChatClient
from azure.identity import DefaultAzureCredential

from src.orchestrator.config import get_config, AgentConfig
from src.orchestrator.loader import load_and_register_tools
from src.orchestrator.middleware import function_call_middleware
from src.orchestrator.mcp_loader import MCPManager
from src.orchestrator.workflow_loader import WorkflowManager

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
    AI Assistant with dynamic tool loading, MCP support, workflows, and service discovery.
    
    Uses Microsoft Agent Framework to reason across multiple data sources.
    
    Tools are loaded from:
    1. Local tools: config/tools/*.json files matched to src/<NAME>/service.py
    2. MCP servers: Configured in agent.toml [[agent.mcp]] sections
    
    Workflows are loaded from:
    - agent.toml [[agent.workflows]] sections - multi-agent orchestration pipelines
    
    Services implement the run(tool_call) -> str method.
    """

    def __init__(self, config: AgentConfig = None) -> None:
        """
        Initialize assistant with Azure OpenAI and load tools dynamically.
        
        Note: MCP servers require async initialization. Call `await assistant.initialize()`
        after creating the instance, or use the async context manager:
        
            async with await AIAssistant.create() as assistant:
                result = await assistant.process_question("Hello!")
        
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
        
        # MCP manager for external tool servers
        self._mcp_manager = MCPManager()
        self._mcp_initialized = False
        
        # Workflow manager for multi-agent pipelines
        self._workflow_manager: Optional[WorkflowManager] = None
        
        # Initialize Azure OpenAI client
        self.chat_client = AzureOpenAIChatClient(
            endpoint=self.config.azure_openai_endpoint,
            deployment_name=self.config.azure_openai_deployment,
            credential=DefaultAzureCredential(),
        )
        
        # Load local tools (sync)
        self._load_tools()
        
        # Agent will be created after MCP initialization
        self.agent = None
        
        logger.info(
            "AI Assistant created (call initialize() for MCP support)",
            local_tools_count=len(self.tools),
            deployment=self.config.azure_openai_deployment
        )
    
    async def initialize(self) -> "AIAssistant":
        """
        Initialize async components (MCP servers, workflows).
        
        Call this after creating the instance to enable MCP and workflow support:
        
            assistant = AIAssistant()
            await assistant.initialize()
        
        Returns:
            self for method chaining
        """
        if self._mcp_initialized:
            return self
        
        # Load MCP servers if configured
        if self.config.mcp_configs:
            mcp_tools = await self._mcp_manager.load_mcp_servers(self.config.mcp_configs)
            logger.info("MCP servers initialized", count=len(mcp_tools))
        
        # Load workflows if configured
        if self.config.workflow_configs:
            self._workflow_manager = WorkflowManager(self.chat_client)
            self._workflow_manager.load_workflows(self.config.workflow_configs)
            logger.info(
                "Workflows initialized", 
                count=len(self._workflow_manager.workflows),
                names=self._workflow_manager.workflow_names
            )
        
        # Combine local tools with MCP tools
        all_tools = self.tools + self._mcp_manager.tools
        
        # Create agent with all tools
        self.agent = ChatAgent(
            chat_client=self.chat_client,
            instructions=self.system_prompt,
            tools=all_tools,
            middleware=[function_call_middleware],
        )
        
        self._mcp_initialized = True
        workflow_count = len(self._workflow_manager.workflows) if self._workflow_manager else 0
        logger.info(
            "AI Assistant fully initialized",
            local_tools=len(self.tools),
            mcp_tools=len(self._mcp_manager.tools),
            total_tools=len(all_tools),
            workflows=workflow_count
        )
        
        return self
    
    @classmethod
    async def create(cls, config: AgentConfig = None) -> "AIAssistant":
        """
        Factory method to create and initialize an AI Assistant.
        
        Use this for full initialization including MCP support:
        
            assistant = await AIAssistant.create()
            result = await assistant.process_question("Hello!")
        
        Args:
            config: Optional AgentConfig instance
            
        Returns:
            Fully initialized AIAssistant instance
        """
        instance = cls(config)
        await instance.initialize()
        return instance
    
    async def __aenter__(self) -> "AIAssistant":
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()

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
        # Auto-initialize if needed (for simple usage without MCP)
        if self.agent is None:
            await self.initialize()
        
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

    async def run_workflow(
        self, 
        workflow_name: str, 
        message: str,
        stream: bool = False
    ) -> Dict[str, Any]:
        """
        Run a named workflow with the given message.
        
        Workflows are multi-agent pipelines that can include:
        - Sequential execution (agents run in order)
        - Custom routing (user-defined agent graph)
        
        Args:
            workflow_name: Name of the workflow to run (as defined in config)
            message: Input message to process through the workflow
            stream: If True, streams responses (returns async generator)
            
        Returns:
            Dictionary containing:
                - workflow: Name of the workflow
                - message: Original input message
                - response: Combined output from all workflow agents
                - success: Whether workflow completed successfully
                - author: Name of the final responding agent
        """
        # Auto-initialize if needed
        if self.agent is None:
            await self.initialize()
        
        if not self._workflow_manager:
            return {
                "workflow": workflow_name,
                "message": message,
                "response": "No workflows configured",
                "success": False,
            }
        
        workflow_agent = self._workflow_manager.get_workflow(workflow_name)
        if not workflow_agent:
            available = self._workflow_manager.workflow_names
            return {
                "workflow": workflow_name,
                "message": message,
                "response": f"Workflow '{workflow_name}' not found. Available: {available}",
                "success": False,
            }
        
        logger.info("Running workflow", workflow=workflow_name, message=message[:100])
        
        try:
            # Import message types
            from agent_framework import ChatMessage, Role
            
            # Create thread for workflow state
            thread = workflow_agent.get_new_thread()
            messages = [ChatMessage(role=Role.USER, content=message)]
            
            if stream:
                # Return streaming generator
                async def stream_workflow():
                    async for update in workflow_agent.run_stream(messages, thread=thread):
                        yield {
                            "text": update.text,
                            "author": update.author_name,
                            "done": False
                        }
                    yield {"text": "", "author": None, "done": True}
                return stream_workflow()
            else:
                # Non-streaming execution
                response = await workflow_agent.run(messages, thread=thread)
                
                # Collect response text
                response_text = ""
                final_author = None
                for msg in response.messages:
                    if msg.text:
                        response_text += f"\n\n**{msg.author_name}:**\n{msg.text}" if msg.author_name else msg.text
                        final_author = msg.author_name
                
                logger.info("Workflow completed", workflow=workflow_name, author=final_author)
                return {
                    "workflow": workflow_name,
                    "message": message,
                    "response": response_text.strip(),
                    "success": True,
                    "author": final_author
                }
                
        except Exception as e:
            logger.error("Workflow failed", workflow=workflow_name, error=str(e))
            return {
                "workflow": workflow_name,
                "message": message,
                "response": f"Error: {str(e)}",
                "success": False,
            }

    def list_workflows(self) -> list:
        """Get list of available workflow names."""
        if not self._workflow_manager:
            return []
        return self._workflow_manager.workflow_names

    async def close(self) -> None:
        """Close resources and cleanup."""
        # Close MCP connections
        if self._mcp_manager:
            await self._mcp_manager.close()
        
        # Close local services
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
        _assistant_instance = await AIAssistant.create()
        logger.info("Created new AI Assistant instance")
    
    result = await _assistant_instance.process_question(question)
    return result["response"]


async def main():
    """Example usage of the AI Assistant with MCP support."""
    # Method 1: Using async context manager (recommended)
    async with AIAssistant() as assistant:
        result = await assistant.process_question("Hello! What can you help me with?")
        print(f"Response: {result['response']}")
    
    # Method 2: Using factory method
    # assistant = await AIAssistant.create()
    # try:
    #     result = await assistant.process_question("Hello!")
    #     print(result["response"])
    # finally:
    #     await assistant.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
