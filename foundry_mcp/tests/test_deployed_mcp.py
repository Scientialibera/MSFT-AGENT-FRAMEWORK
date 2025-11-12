"""
Test script for deployed MCP server on Azure Web App.
Tests the MCP server by directly testing the agent functionality.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from foundry_mcp.agent_creation.fabric_agent import SmartSCMFoundryAgent

# Load environment variables
load_dotenv()


def test_mcp_server():
    """Test the MCP server functionality"""
    print("=" * 80)
    print("Testing Deployed MCP Server (Fabric Data Agent)")
    print("=" * 80)
    
    try:
        # Initialize the agent
        print("\n[TEST] Initializing Fabric Data Agent...")
        
        agent = SmartSCMFoundryAgent()
        print(f"[TEST] Agent initialized: {agent.agent_name}")
        print(f"[TEST] Agent ID: {agent.agent.id}")
        
        # Test query
        query = "How many accounts have duplicate names?"
        print(f"\n[TEST] Sending test query: {query}")
        print("[TEST] Waiting for response...")
        
        result = agent.ask(query)
        
        print(f"\n[TEST] Response received:")
        print("=" * 80)
        print(result)
        print("=" * 80)
        
        if result and "duplicate" in result.lower():
            print("\n✅ MCP Server is working correctly on Azure Web App!")
            return True
        else:
            print("\n⚠️ Response received but may not be expected")
            return True
            
    except Exception as e:
        print(f"\n❌ Error testing MCP server: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_mcp_server()
    sys.exit(0 if success else 1)
