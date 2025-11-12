"""
Test MCP Server agent function

This test validates that the MCP server can:
1. Initialize the Fabric Data Agent
2. Successfully query Azure AI Foundry
3. Receive responses from the agent

Run: python foundry_mcp/tests/test_mcp_server.py
"""

import sys
from pathlib import Path

# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from foundry_mcp.app.mcp_server import _initialize_agent


def test_mcp_server():
    """Test the MCP server agent without starting the server"""
    
    print("=" * 80)
    print("Testing MCP Server Agent Function")
    print("=" * 80)
    
    try:
        # Initialize agent through the MCP server function
        print("\n[TEST] Initializing agent via MCP...")
        agent = _initialize_agent()
        print(f"[TEST] Agent initialized: {agent.agent_name}")
        print(f"[TEST] Agent ID: {agent.agent.id}")
        
        # Test query
        print("\n[TEST] Sending test query...")
        query = "How many accounts have duplicate names?"
        print(f"[TEST] Query: {query}")
        
        print("\n[TEST] Waiting for response...")
        answer = agent.ask(query)
        
        print("\n[TEST] Response received:")
        print("=" * 80)
        print(answer)
        print("=" * 80)
        
        print("\n✅ MCP Server agent is working correctly!")
        return 0
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(test_mcp_server())
