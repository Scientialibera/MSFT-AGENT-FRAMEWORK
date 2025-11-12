"""
Test MCP-Enabled AI Foundry Agent
This script creates an AI Foundry agent that uses our deployed Fabric MCP server.
"""

import os
import time
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
from dotenv import load_dotenv

# Load environment variables
load_dotenv("foundry_mcp/.env")

# Get MCP server configuration
# Use Azure deployment for testing
MCP_SERVER_URL = "https://mcp-aura.azurewebsites.net/mcp"
MCP_SERVER_LABEL = "fabric_data_agent"  # Must match pattern ^[a-zA-Z0-9_]+$

# Azure AI Foundry configuration
PROJECT_ENDPOINT = os.environ["AZURE_AI_FOUNDRY_URL"]
MODEL_DEPLOYMENT = os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"]

print("=" * 80)
print("MCP-Enabled AI Foundry Agent Test")
print("=" * 80)
print(f"MCP Server: {MCP_SERVER_URL}")
print(f"Project: {PROJECT_ENDPOINT}")
print(f"Model: {MODEL_DEPLOYMENT}")
print("=" * 80)

# Initialize project client
project_client = AIProjectClient(
    endpoint=PROJECT_ENDPOINT,
    credential=DefaultAzureCredential(),
)

# Initialize agent MCP tool
print("\n[1] Initializing MCP tool...")
mcp_tool = McpTool(
    server_label=MCP_SERVER_LABEL,
    server_url=MCP_SERVER_URL,
    allowed_tools=[],  # Will allow all tools by default
)

# Allow the fabricdataagentaccount tool
fabric_tool_name = "fabricdataagentaccount"
mcp_tool.allow_tool(fabric_tool_name)
print(f"✅ MCP tool initialized")
print(f"   Allowed tools: {mcp_tool.allowed_tools}")

# Use existing agent
EXISTING_AGENT_ID = "asst_ruoEbD0ywIVKJU0n3bRKscgw"

with project_client:
    agents_client = project_client.agents

    print(f"\n[2] Using existing agent: {EXISTING_AGENT_ID}")
    agent = agents_client.get_agent(agent_id=EXISTING_AGENT_ID)

    print(f"✅ Retrieved agent, ID: {agent.id}")
    print(f"   Agent Name: {agent.name}")
    print(f"   MCP Server: {mcp_tool.server_label} at {mcp_tool.server_url}")

    # Create thread for communication
    print("\n[3] Creating conversation thread...")
    thread = agents_client.threads.create()
    print(f"✅ Created thread, ID: {thread.id}")

    # Create message to thread
    print("\n[4] Sending user query...")
    message = agents_client.messages.create(
        thread_id=thread.id,
        role="user",
        content="How many accounts have duplicate names?",
    )
    print(f"✅ Created message, ID: {message.id}")

    # Create and process agent run with MCP tools
    print("\n[5] Starting agent run...")
    # Set approval mode to "never" to auto-approve MCP tool calls
    mcp_tool.set_approval_mode("never")
    
    run = agents_client.runs.create(
        thread_id=thread.id, 
        agent_id=agent.id, 
        tool_resources=mcp_tool.resources
    )
    print(f"✅ Created run, ID: {run.id}")

    # Process the run
    print("\n[6] Processing run...")
    step_count = 0
    while run.status in ["queued", "in_progress", "requires_action"]:
        time.sleep(1)
        run = agents_client.runs.get(thread_id=thread.id, run_id=run.id)
        
        step_count += 1
        print(f"   Step {step_count}: {run.status}")

        if run.status == "requires_action" and isinstance(run.required_action, SubmitToolApprovalAction):
            tool_calls = run.required_action.submit_tool_approval.tool_calls
            if not tool_calls:
                print("⚠️  No tool calls provided - cancelling run")
                agents_client.runs.cancel(thread_id=thread.id, run_id=run.id)
                break

            tool_approvals = []
            for tool_call in tool_calls:
                if isinstance(tool_call, RequiredMcpToolCall):
                    try:
                        print(f"   ✓ Approving tool call: {tool_call.id}")
                        tool_approvals.append(
                            ToolApproval(
                                tool_call_id=tool_call.id,
                                approve=True,
                                headers=mcp_tool.headers,
                            )
                        )
                    except Exception as e:
                        print(f"   ❌ Error approving tool_call {tool_call.id}: {e}")

            if tool_approvals:
                agents_client.runs.submit_tool_outputs(
                    thread_id=thread.id, run_id=run.id, tool_approvals=tool_approvals
                )

    print(f"\n✅ Run completed with status: {run.status}")
    
    if run.status == "failed":
        print(f"❌ Run failed: {run.last_error}")

    # Display run steps and tool calls
    print("\n[7] Run Steps:")
    print("-" * 80)
    run_steps = agents_client.run_steps.list(thread_id=thread.id, run_id=run.id)

    for step in run_steps:
        print(f"Step {step['id']} - Status: {step['status']}")

        step_details = step.get("step_details", {})
        tool_calls = step_details.get("tool_calls", [])

        if tool_calls:
            print("  MCP Tool Calls:")
            for call in tool_calls:
                print(f"    • Tool Call ID: {call.get('id')}")
                print(f"      Type: {call.get('type')}")
                if 'mcp' in str(call.get('type', '')).lower():
                    print(f"      ✓ This is an MCP tool call!")

        if isinstance(step_details, RunStepActivityDetails):
            for activity in step_details.activities:
                for function_name, function_definition in activity.tools.items():
                    print(f'  Function: {function_name}')
                    print(f'  Description: "{function_definition.description}"')
                    if len(function_definition.parameters) > 0:
                        print("  Parameters:")
                        for argument, func_argument in function_definition.parameters.properties.items():
                            print(f"    • {argument}: {func_argument.type}")
                            print(f"      {func_argument.description}")

        print()

    # Fetch and log all messages
    print("\n[8] Conversation:")
    print("=" * 80)
    messages = agents_client.messages.list(thread_id=thread.id, order=ListSortOrder.ASCENDING)
    
    for msg in messages:
        if msg.text_messages:
            last_text = msg.text_messages[-1]
            print(f"\n{msg.role.upper()}:")
            print("-" * 80)
            print(last_text.text.value)
    
    print("=" * 80)

    # Clean-up
    print("\n[9] Agent Info:")
    print("=" * 80)
    print(f"Agent ID: {agent.id}")
    print(f"Agent Name: fabric-mcp-test-agent")
    print(f"Thread ID: {thread.id}")
    print(f"Run ID: {run.id}")
    print("=" * 80)
    print("\n✅ Agent preserved - you can view it in Azure AI Foundry UI")
    print(f"   Go to: {PROJECT_ENDPOINT.replace('/api/projects/', '/projects/')}")
    
    print("\n" + "=" * 80)
    print("Test Complete!")
    print("=" * 80)
