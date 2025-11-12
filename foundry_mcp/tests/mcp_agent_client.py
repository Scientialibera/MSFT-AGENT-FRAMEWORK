"""
MCP Agent Client - Uses Azure AI Foundry Agent with deployed MCP server.

This script creates an agent that connects to the Fabric Data Agent MCP server
deployed on Azure Web App and uses it to answer queries about Fabric data.

The MCP server is hosted at: https://aura-bot.azurewebsites.net/
"""

import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.agents.models import (
    ListSortOrder,
    McpTool,
    RequiredMcpToolCall,
    RunStepActivityDetails,
    SubmitToolApprovalAction,
    ToolApproval,
)

# Load environment variables from foundry_mcp/.env
env_path = Path(__file__).parent / "foundry_mcp" / ".env"
load_dotenv(dotenv_path=env_path)

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))


def create_mcp_agent():
    """Create and run an agent with MCP tools"""
    
    print("=" * 80)
    print("MCP Agent Client - Fabric Data Agent")
    print("=" * 80)
    
    # Get configuration from environment
    project_endpoint = os.getenv("AZURE_AI_FOUNDRY_URL")
    model_deployment = os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-4o")
    
    # MCP server configuration
    # For deployed MCP server on Azure Web App
    mcp_server_url = "https://aura-bot.azurewebsites.net"
    mcp_server_label = "fabric_data_agent"
    
    print(f"\n[INFO] Foundry Project: {project_endpoint}")
    print(f"[INFO] Model: {model_deployment}")
    print(f"[INFO] MCP Server: {mcp_server_label}")
    
    try:
        # Initialize Azure AI Foundry client
        project_client = AIProjectClient(
            endpoint=project_endpoint,
            credential=DefaultAzureCredential(),
        )
        
        # Initialize MCP tool
        # Note: For stdio-based MCP servers (like our FastMCP), 
        # you would typically provide a startup command instead of URL
        mcp_tool = McpTool(
            server_label=mcp_server_label,
            server_url=mcp_server_url,  # Use the Azure Web App endpoint
            allowed_tools=[],  # Will allow all tools
        )
        
        print(f"\n[INIT] MCP Tool configured: {mcp_server_label}")
        
        with project_client:
            agents_client = project_client.agents
            
            # Create agent with MCP tool
            print("\n[AGENT] Creating agent with MCP tool...")
            agent = agents_client.create_agent(
                model=model_deployment,
                name="FabricDataMcpAgent",
                instructions="""You are a helpful data analysis agent with access to Fabric Data Agent through MCP.

Your capabilities:
- Query business intelligence and financial data
- Analyze account information and duplicates
- Provide insights from the Fabric data warehouse
- Answer questions about enterprise data

Use the available MCP tools to help users with their data queries. 
Always provide clear, actionable insights based on the data returned.
""",
                tools=mcp_tool.definitions,
            )
            
            print(f"✅ Agent created: {agent.id}")
            print(f"   Name: {agent.name}")
            
            # Create thread
            print("\n[THREAD] Creating conversation thread...")
            thread = agents_client.threads.create()
            print(f"✅ Thread created: {thread.id}")
            
            # Define test queries
            queries = [
                "How many accounts have duplicate names?",
                "What is the total count of active accounts?",
            ]
            
            for query_idx, user_query in enumerate(queries, 1):
                print(f"\n{'=' * 80}")
                print(f"[QUERY {query_idx}] {user_query}")
                print(f"{'=' * 80}")
                
                # Create message
                message = agents_client.messages.create(
                    thread_id=thread.id,
                    role="user",
                    content=user_query,
                )
                print(f"\n[MESSAGE] Created: {message.id}")
                
                # Create and process run
                print("[RUN] Starting agent run...")
                run = agents_client.runs.create(
                    thread_id=thread.id, 
                    agent_id=agent.id,
                    tool_resources=mcp_tool.resources if hasattr(mcp_tool, 'resources') else None
                )
                print(f"[RUN] Run ID: {run.id}")
                
                # Poll for completion
                max_iterations = 30
                iteration = 0
                while run.status in ["queued", "in_progress", "requires_action"] and iteration < max_iterations:
                    time.sleep(2)
                    run = agents_client.runs.get(thread_id=thread.id, run_id=run.id)
                    iteration += 1
                    
                    print(f"[STATUS] {run.status} (iteration {iteration}/{max_iterations})")
                    
                    # Handle tool approvals if needed
                    if run.status == "requires_action" and isinstance(run.required_action, SubmitToolApprovalAction):
                        tool_calls = run.required_action.submit_tool_approval.tool_calls
                        print(f"[APPROVAL] {len(tool_calls)} tool calls require approval")
                        
                        tool_approvals = []
                        for tool_call in tool_calls:
                            if isinstance(tool_call, RequiredMcpToolCall):
                                print(f"  - Approving: {tool_call.id}")
                                tool_approvals.append(
                                    ToolApproval(
                                        tool_call_id=tool_call.id,
                                        approve=True,
                                    )
                                )
                        
                        if tool_approvals:
                            agents_client.runs.submit_tool_outputs(
                                thread_id=thread.id,
                                run_id=run.id,
                                tool_approvals=tool_approvals
                            )
                
                # Check final status
                print(f"\n[COMPLETE] Run status: {run.status}")
                
                if run.status == "failed":
                    print(f"❌ Run failed: {run.last_error}")
                    continue
                
                if run.status == "completed":
                    print("✅ Run completed successfully")
                
                # Display run steps
                print("\n[STEPS]")
                run_steps = agents_client.run_steps.list(thread_id=thread.id, run_id=run.id)
                for step in run_steps:
                    print(f"  Step: {step['id']}")
                    print(f"  Status: {step['status']}")
                    
                    step_details = step.get("step_details", {})
                    tool_calls = step_details.get("tool_calls", [])
                    if tool_calls:
                        print(f"  Tool calls: {len(tool_calls)}")
                
                # Fetch messages
                print("\n[MESSAGES]")
                messages = agents_client.messages.list(thread_id=thread.id, order=ListSortOrder.ASCENDING)
                for msg in messages:
                    if msg.text_messages:
                        last_text = msg.text_messages[-1]
                        role = msg.role.upper()
                        content = last_text.text.value
                        print(f"\n{role}:")
                        print(f"  {content}")
            
            # Cleanup
            print(f"\n[CLEANUP] Deleting agent {agent.id}...")
            agents_client.delete_agent(agent.id)
            print("✅ Agent deleted")
            
            print("\n" + "=" * 80)
            print("✅ MCP Agent Client completed successfully!")
            print("=" * 80)
            
            return True
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = create_mcp_agent()
    sys.exit(0 if success else 1)
