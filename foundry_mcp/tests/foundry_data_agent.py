"""
Azure AI Foundry Agent with Microsoft Fabric Integration

This module provides a reusable template for deploying specialized AI agents
that query enterprise data via Fabric Data Agents. Supports multi-agent deployments
with extensible tool configurations.

Supported Agents:
- Tariff/Disruption (MVP) - Fabric + Bing Search
- PO Delayed - Fabric + Bing Search
- Demand Forecasting - Fabric only
- Sales Order Status - Fabric only
- Purchase Order Status - Fabric only

Usage:
    agent = SmartSCMFoundryAgent(
        agent_name="SmartSCMFabricAgent_Tariff",
        fabric_connection_id=os.getenv("FOUNDRY_FABRIC_RESOURCE_ID_TARIFF"),
        system_prompt_file="config/prompts/tariff_system_prompt.txt",
        additional_tools=["bing_search"]  # Optional
    )
    answer = agent.ask("Query here")
"""

import os
from dotenv import load_dotenv
from openai import AzureOpenAI
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
load_dotenv()
 
class SmartSCMFoundryAgent:
    """
    Reusable Azure AI Foundry Agent with Fabric integration.
    
    Instantiate per agent type (e.g., Tariff, Demand, PO_Status).
    Automatically reuses existing agents to minimize creation overhead.
    
    Architecture:
    - Each Fabric Data Agent is a curated data source (specific tables/views)
    - Each Foundry Agent is an LLM with access to Fabric + optional external tools
    - Thread-per-query pattern ensures isolation while reusing agent instances
    """
    
    def __init__(
        self,
        agent_name: str = "SmartSCMFabricAgenttemplate",
        fabric_connection_id: str = None,
        system_prompt_file: str = "system_prompt.txt",
        additional_tools: list = None
    ):
        """
        Initialize agent with configurable name and tools.
        
        Args:
            agent_name: Unique agent identifier (e.g., "SmartSCMFabricAgent_Tariff")
            fabric_connection_id: Fabric data agent connection ID (overrides env var)
            system_prompt_file: Path to system instructions
            additional_tools: List of tool names ["bing_search", "sharepoint"] if needed
        """
        self.agent_name = agent_name
        self.additional_tools = additional_tools or []
        
        # Azure OpenAI configuration (LLM backbone)
        self.endpoint = os.getenv("AZURE_OPENAI_URL")
        self.deployment_name = os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME")
        self.api_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.api_version = os.getenv("MODEL_VERSION")
 
        # Azure AI Foundry configuration (agent orchestration)
        self.project_endpoint = os.getenv("AZURE_AI_FOUNDRY_URL")
        
        # Fabric integration: Use parameter or env var
        self.fabric_connection_id = (
            fabric_connection_id or 
            os.getenv("FOUNDRY_FABRIC_RESOURCE_ID")
        )
 
        if not all([
            self.endpoint,
            self.api_key,
            self.deployment_name,
            self.api_version,
            self.project_endpoint,
            self.fabric_connection_id
        ]):
            raise EnvironmentError("Missing required environment variables")
 
        # Initialize Azure OpenAI client
        self.client = AzureOpenAI(
            api_version=self.api_version,
            azure_endpoint=self.endpoint,
            api_key=self.api_key,
        )
 
        # Initialize Azure AI Foundry project client
        self.project_client = AIProjectClient(
            endpoint=self.project_endpoint,
            credential=DefaultAzureCredential(),
        )
        
        self.agent = None
        self.system_prompt_file = system_prompt_file
        self._initialize_agent()
 
    def _initialize_agent(self):
        """Initialize or retrieve the existing agent."""
        agents_client = self.project_client.agents
        
        # Try to find existing agent by name (cost optimization)
        try:
            agents_list = agents_client.list_agents()
            for agent in agents_list:
                if agent.name == self.agent_name:
                    self.agent = agent
                    print(f"[AGENT] Reusing existing agent: {self.agent_name} (ID: {self.agent.id})")
                    return
        except Exception as e:
            print(f"[AGENT] Could not list agents: {e}")
        
        # If not found, create new agent with configured tools
        print(f"[AGENT] Creating new agent: {self.agent_name}")
        
        # PRIMARY TOOL: Fabric Data Agent (always required)
        tools = [self._build_fabric_tool()]
        
        # OPTIONAL TOOLS: Add external integrations based on agent needs
        # TODO: Add Tariff agent - uncomment bing_search in additional_tools
        # TODO: Add PO_Delayed agent - uncomment bing_search in additional_tools
        # TODO: Add Demand agent - fabric_only, no additional tools
        for tool_name in self.additional_tools:
            if tool_name == "bing_search":
                tools.append(self._build_bing_search_tool())
            elif tool_name == "sharepoint":
                tools.append(self._build_sharepoint_tool())
            # elif tool_name == "custom_tool": tools.append(self._build_custom_tool())
 
        with open(self.system_prompt_file, "r", encoding="utf-8") as f:
            system_prompt = f.read()
 
        self.agent = agents_client.create_agent(
            model=self.deployment_name,
            name=self.agent_name,
            instructions=system_prompt,
            tools=tools,
            headers={"x-ms-enable-preview": "true"}
        )
        print(f"[AGENT] Created: {self.agent_name} (ID: {self.agent.id})")
    
    def _build_fabric_tool(self) -> dict:
        """Build Fabric Data Agent tool definition (always required)."""
        return {
            "type": "fabric_dataagent",
            "fabric_dataagent": {
                "connections": [
                    {"connection_id": self.fabric_connection_id}
                ]
            }
        }
    
    def _build_bing_search_tool(self) -> dict:
        """Build Bing Search tool definition (for market/web data)."""
        return {
            "type": "bing_search",
            "bing_search": {
                "api_key": os.getenv("BING_SEARCH_API_KEY")
            }
        }
    
    def _build_sharepoint_tool(self) -> dict:
        """Build SharePoint tool definition (for internal documents)."""
        return {
            "type": "sharepoint",
            "sharepoint": {
                "site_url": os.getenv("SHAREPOINT_SITE_URL"),
                "connection_id": os.getenv("SHAREPOINT_CONNECTION_ID")
            }
        }
        # To add custom tools: implement _build_custom_tool() above
 
    def ask(self, user_question: str) -> str:
        """
        Query the agent with a new isolated thread (no chat history bleed).
        Reuses agent instance for cost efficiency.
        
        Args:
            user_question: Query string
            
        Returns:
            Agent response
        """
        # Thread isolation: fresh context per query, but reused agent
        thread = self.project_client.agents.threads.create()
 
        self.project_client.agents.messages.create(
            thread_id=thread.id,
            role="user",
            content=user_question,
        )
 
        # Run agent on thread (leverages all configured tools)
        run = self.project_client.agents.runs.create_and_process(
            thread_id=thread.id,
            agent_id=self.agent.id,
        )
 
        if run.status == "failed":
            raise RuntimeError(f"Agent run failed: {run.last_error}")
 
        # Extract response from thread
        messages = self.project_client.agents.messages.list(
            thread_id=thread.id,
            order="asc"
        )
 
        responses = [
            msg.text_messages[-1].text.value
            for msg in messages
            if msg.role != "user" and msg.text_messages
        ]
 
        return "\n".join(responses) if responses else "No response generated."
 
 
def main():
    """
    Example: Deploy single agent or multiple specialized agents.
    
    TODO: Create separate agent instances for each use case:
    - tariff_agent = SmartSCMFoundryAgent(
        agent_name="SmartSCMFabricAgent_Tariff",
        fabric_connection_id=os.getenv("FOUNDRY_FABRIC_RESOURCE_ID_TARIFF"),
        system_prompt_file="config/prompts/tariff_disruption_system_prompt.txt",
        additional_tools=["bing_search"]  # For market intelligence
      )
    
    - demand_agent = SmartSCMFoundryAgent(
        agent_name="SmartSCMFabricAgent_Demand",
        fabric_connection_id=os.getenv("FOUNDRY_FABRIC_RESOURCE_ID_DEMAND"),
        system_prompt_file="config/prompts/demand_forecast_system_prompt.txt"
        # Fabric-only, no additional tools
      )
    """
    # Default: template agent (customize for your use case)
    client = SmartSCMFoundryAgent()
    print("[MAIN] Agent ready. Type 'end' to exit.")
    while True:
        question = input("Question: ").strip()
        if question.lower() == "end":
            print("Exiting...")
            break
        if not question:
            print("Please enter a valid question.")
            continue
        try:
            answer = client.ask(question)
            print("Answer:\n", answer)
        except Exception as e:
            print(f"Error: {e}")
 
 
if __name__ == "__main__":
    main()
