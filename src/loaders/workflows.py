"""
Workflow loader for the AI Assistant.

Loads and manages Microsoft Agent Framework workflows from configuration.
Supports multiple workflow patterns:
- sequential: Agents execute in order
- custom: User-defined workflow graphs via config
"""

from typing import Any, Dict, List, Optional
from pathlib import Path

import structlog

# Import Workflow types from Agent Framework
try:
    from agent_framework import ChatAgent, WorkflowBuilder
    from agent_framework._workflows import SequentialBuilder
    WORKFLOW_AVAILABLE = True
except ImportError:
    try:
        from agent_framework import ChatAgent
        from agent_framework.workflows import WorkflowBuilder, SequentialBuilder
        WORKFLOW_AVAILABLE = True
    except ImportError:
        WORKFLOW_AVAILABLE = False
        WorkflowBuilder = None
        SequentialBuilder = None

logger = structlog.get_logger(__name__)


class WorkflowManager:
    """
    Manages workflow creation and execution for the AI Assistant.
    
    Creates multi-agent workflows from configuration, allowing complex
    orchestration patterns like sequential pipelines, parallel execution,
    and conditional routing.
    """
    
    def __init__(self, chat_client: Any):
        """
        Initialize the workflow manager.
        
        Args:
            chat_client: The Azure OpenAI chat client to use for agents
        """
        self._chat_client = chat_client
        self._workflows: Dict[str, Any] = {}
        self._workflow_agents: Dict[str, Any] = {}
        self._initialized = False
        
    def load_workflows(self, workflow_configs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Load and initialize workflows from configuration.
        
        Args:
            workflow_configs: List of workflow configurations, each containing:
                - name: Friendly name for the workflow
                - type: "sequential" or "custom"
                - enabled: Whether this workflow is enabled (default: true)
                
                For sequential type:
                - agents: List of agent definitions with name and instructions
                
                For custom type:
                - agents: List of agent definitions
                - edges: List of edge definitions (from, to, optional condition)
                - start: Name of the starting agent
                
        Returns:
            Dict mapping workflow names to workflow agent instances
        """
        if not WORKFLOW_AVAILABLE:
            logger.warning(
                "Workflow support not available. Install agent-framework with workflow support."
            )
            return {}
        
        if not workflow_configs:
            logger.debug("No workflows configured")
            return {}
        
        for config in workflow_configs:
            # Skip disabled workflows
            if not config.get("enabled", True):
                logger.debug("Skipping disabled workflow", name=config.get("name"))
                continue
                
            try:
                workflow_agent = self._create_workflow(config)
                if workflow_agent:
                    name = config.get("name", "unnamed-workflow")
                    self._workflow_agents[name] = workflow_agent
                    logger.info(
                        "Loaded workflow",
                        name=name,
                        type=config.get("type")
                    )
            except Exception as e:
                logger.error(
                    "Failed to load workflow",
                    name=config.get("name"),
                    error=str(e)
                )
        
        self._initialized = True
        logger.info("Workflows loaded", count=len(self._workflow_agents))
        return self._workflow_agents
    
    def _create_workflow(self, config: Dict[str, Any]) -> Optional[Any]:
        """Create a workflow based on configuration."""
        workflow_type = config.get("type", "").lower()
        name = config.get("name", "unnamed-workflow")
        
        if workflow_type == "sequential":
            return self._create_sequential_workflow(config)
        elif workflow_type == "custom":
            return self._create_custom_workflow(config)
        else:
            logger.error("Unknown workflow type", name=name, type=workflow_type)
            return None
    
    def _create_sequential_workflow(self, config: Dict[str, Any]) -> Any:
        """
        Create a sequential workflow where agents execute in order.
        
        Args:
            config: Workflow configuration containing:
                - name: Workflow name
                - agents: List of agent definitions
                    - name: Agent name
                    - instructions: Agent system prompt
                    
        Returns:
            Workflow agent instance
        """
        agents_config = config.get("agents", [])
        if not agents_config:
            raise ValueError(f"Workflow '{config.get('name')}' requires 'agents' list")
        
        # Create agents
        agents = []
        for agent_config in agents_config:
            agent = ChatAgent(
                name=agent_config.get("name", f"Agent-{len(agents)}"),
                instructions=agent_config.get("instructions", "You are a helpful assistant."),
                chat_client=self._chat_client,
            )
            agents.append(agent)
            logger.debug("Created agent for workflow", agent_name=agent.name)
        
        # Build sequential workflow
        workflow = (
            SequentialBuilder()
            .participants(agents)
            .build()
        )
        
        # Convert to workflow agent
        workflow_agent = workflow.as_agent(name=config.get("name", "Sequential Workflow"))
        
        logger.info(
            "Created sequential workflow",
            name=config.get("name"),
            agent_count=len(agents)
        )
        
        return workflow_agent
    
    def _create_custom_workflow(self, config: Dict[str, Any]) -> Any:
        """
        Create a custom workflow with user-defined edges.
        
        Args:
            config: Workflow configuration containing:
                - name: Workflow name
                - agents: List of agent definitions
                - edges: List of edge definitions (from_agent, to_agent)
                - start: Name of starting agent
                    
        Returns:
            Workflow agent instance
        """
        agents_config = config.get("agents", [])
        edges_config = config.get("edges", [])
        start_agent = config.get("start")
        
        if not agents_config:
            raise ValueError(f"Workflow '{config.get('name')}' requires 'agents' list")
        if not start_agent:
            raise ValueError(f"Workflow '{config.get('name')}' requires 'start' agent name")
        
        # Create agents and store by name
        agents_by_name: Dict[str, Any] = {}
        for agent_config in agents_config:
            agent_name = agent_config.get("name")
            if not agent_name:
                raise ValueError("Each agent in workflow must have a 'name'")
                
            agent = ChatAgent(
                name=agent_name,
                instructions=agent_config.get("instructions", "You are a helpful assistant."),
                chat_client=self._chat_client,
            )
            agents_by_name[agent_name] = agent
            logger.debug("Created agent for workflow", agent_name=agent_name)
        
        # Validate start agent exists
        if start_agent not in agents_by_name:
            raise ValueError(f"Start agent '{start_agent}' not found in agents list")
        
        # Build workflow
        builder = WorkflowBuilder()
        builder.set_start_executor(agents_by_name[start_agent])
        
        # Add edges
        for edge in edges_config:
            from_agent = edge.get("from")
            to_agent = edge.get("to")
            
            if from_agent not in agents_by_name:
                raise ValueError(f"Edge 'from' agent '{from_agent}' not found")
            if to_agent not in agents_by_name:
                raise ValueError(f"Edge 'to' agent '{to_agent}' not found")
            
            builder.add_edge(agents_by_name[from_agent], agents_by_name[to_agent])
            logger.debug("Added edge", from_agent=from_agent, to_agent=to_agent)
        
        workflow = builder.build()
        
        # Convert to workflow agent
        workflow_agent = workflow.as_agent(name=config.get("name", "Custom Workflow"))
        
        logger.info(
            "Created custom workflow",
            name=config.get("name"),
            agent_count=len(agents_by_name),
            edge_count=len(edges_config)
        )
        
        return workflow_agent
    
    def get_workflow(self, name: str) -> Optional[Any]:
        """Get a workflow agent by name."""
        return self._workflow_agents.get(name)
    
    @property
    def workflows(self) -> Dict[str, Any]:
        """Get all loaded workflow agents."""
        return self._workflow_agents
    
    @property
    def workflow_names(self) -> List[str]:
        """Get names of all loaded workflows."""
        return list(self._workflow_agents.keys())


def parse_workflow_configs(config_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Parse workflow configurations from agent config.
    
    Supports two formats in TOML:
    
    1. Array format (recommended for multiple workflows):
        [[agent.workflows]]
        name = "content-pipeline"
        type = "sequential"
        
        [[agent.workflows.agents]]
        name = "Researcher"
        instructions = "Research the topic..."
        
        [[agent.workflows.agents]]
        name = "Writer"
        instructions = "Write content based on research..."
    
    2. Table format (for named workflows):
        [agent.workflows.content-pipeline]
        type = "sequential"
        agents = [
            { name = "Researcher", instructions = "..." },
            { name = "Writer", instructions = "..." }
        ]
    
    Args:
        config_dict: The agent configuration dictionary
        
    Returns:
        List of workflow configuration dictionaries
    """
    workflow_config = config_dict.get("workflows", {})
    
    # If it's a list, return as-is
    if isinstance(workflow_config, list):
        return workflow_config
    
    # If it's a dict, convert to list format
    if isinstance(workflow_config, dict):
        workflow_list = []
        for name, settings in workflow_config.items():
            if isinstance(settings, dict):
                # Add name from key if not specified
                if "name" not in settings:
                    settings["name"] = name
                workflow_list.append(settings)
        return workflow_list
    
    return []
