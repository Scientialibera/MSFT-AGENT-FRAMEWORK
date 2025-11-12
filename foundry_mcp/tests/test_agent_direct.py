"""
Direct test of Fabric Data Agent to debug query issues
"""
import os
import sys
from dotenv import load_dotenv

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Load environment variables
load_dotenv("foundry_mcp/.env")

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "foundry_mcp"))

from agent_creation.fabric_agent import SmartSCMFoundryAgent

def test_agent():
    print("=" * 80)
    print("DIRECT FABRIC DATA AGENT TEST")
    print("=" * 80)
    
    # Get configuration from environment
    agent_name = os.getenv("FOUNDRY_AGENT_NAME")
    system_prompt_file = os.getenv("SYSTEM_PROMPT_FILE", "config/orchestrator/system_prompt.txt")
    
    print(f"\n[CONFIG]")
    print(f"  Agent name: {agent_name}")
    print(f"  System prompt: {system_prompt_file}")
    print(f"  Azure AI Foundry: {os.getenv('AZURE_AI_FOUNDRY_URL')}")
    print(f"  Fabric Resource: {os.getenv('FOUNDRY_FABRIC_RESOURCE_ID')}")
    
    # Initialize agent
    print(f"\n[1] Initializing agent...")
    try:
        agent = SmartSCMFoundryAgent(
            agent_name=agent_name,
            system_prompt_file=system_prompt_file
        )
        print(f"✓ Agent initialized")
        print(f"  Agent ID: {agent.agent.id if hasattr(agent, 'agent') else 'N/A'}")
    except Exception as e:
        print(f"❌ Agent initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test query
    query = "How many accounts have duplicate names?"
    print(f"\n[2] Testing query...")
    print(f"  Query: {query}")
    
    try:
        print(f"\n[3] Sending to agent...")
        
        # Create thread and message
        thread = agent.project_client.agents.threads.create()
        print(f"  Thread created: {thread.id}")
        
        agent.project_client.agents.messages.create(
            thread_id=thread.id,
            role="user",
            content=query,
        )
        print(f"  Message added to thread")
        
        # Run agent with detailed tracking
        print(f"\n[4] Running agent...")
        run = agent.project_client.agents.runs.create_and_process(
            thread_id=thread.id,
            agent_id=agent.agent.id,
        )
        
        print(f"\n[5] Run completed:")
        print(f"  Status: {run.status}")
        print(f"  ID: {run.id}")
        if run.status == "failed":
            print(f"  Error: {run.last_error}")
        
        # Get messages
        messages = agent.project_client.agents.messages.list(
            thread_id=thread.id,
            order="asc"
        )
        
        print(f"\n[6] Messages in thread:")
        for i, msg in enumerate(messages):
            print(f"\n  Message {i+1}:")
            print(f"    Role: {msg.role} (type: {type(msg.role)})")
            print(f"    Role value: {msg.role.value if hasattr(msg.role, 'value') else 'N/A'}")
            print(f"    Role == 'user': {msg.role == 'user'}")
            print(f"    Role != 'user': {msg.role != 'user'}")
            print(f"    Has text_messages: {bool(msg.text_messages)}")
            if msg.text_messages:
                print(f"    Content: {msg.text_messages[0].text.value[:100]}...")
        
        # Extract response
        responses = [
            msg.text_messages[-1].text.value
            for msg in messages
            if msg.role != "user" and msg.text_messages
        ]
        
        response = "\n".join(responses) if responses else "No response generated."
        
        print(f"\n[7] Final Response:")
        print("=" * 80)
        print(response)
        print("=" * 80)
        print(f"\n✅ Query successful ({len(response)} chars)")
        
    except Exception as e:
        print(f"\n❌ Query failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_agent()
