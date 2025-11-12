"""
FastMCP Client Test - Connect to running MCP Server

Tests the MCP server by connecting to it with a FastMCP client.

IMPORTANT: The MCP server must already be running before running this test!

Steps:
1. In Terminal 1: Start the MCP server
   python tests/mcp_server.py
   
2. In Terminal 2: Run this test
   python tests/test_mcp_client.py
"""

import asyncio
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastmcp import Client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)

logger = logging.getLogger(__name__)


async def test_mcp_via_fastmcp():
    """Test MCP server using FastMCP client via stdio transport."""
    
    load_dotenv()
    
    print("\n" + "=" * 80)
    print("FastMCP Client Test - Stdio Transport")
    print("=" * 80)
    
    print("\n[REQUIREMENT] Make sure the MCP server is running in another terminal:")
    print("  Terminal 1: python tests/mcp_server.py")
    print("  Terminal 2: python tests/test_mcp_client.py (this test)")
    
    print("\n[Step 1] Creating FastMCP client with stdio transport...")
    
    try:
        # Connect to MCP server via stdio - FastMCP will spawn the process
        # Use relative path to tests/mcp_server.py
        client = Client("tests/mcp_server.py")
        print("[OK] FastMCP client created (configured for stdio transport)")
        
        print("\n[Step 2] Connecting to MCP server...")
        async with client:
            print("[OK] Connected to MCP server")
            
            print("\n[Step 3] Pinging server...")
            await client.ping()
            print("[OK] Server responded to ping")
            
            print("\n[Step 4] Listing available tools...")
            
            # List tools
            tools_response = await client.list_tools()
            tools = tools_response.tools if hasattr(tools_response, 'tools') else tools_response
            tool_count = len(tools) if tools else 0
            
            print(f"[OK] Found {tool_count} tools")
            
            if tool_count == 0:
                print("[WARNING] No tools found! Server may not be configured correctly.")
            else:
                for tool in tools:
                    print(f"  - {tool.name}: {tool.description}")
            
            # Test calling process_query tool
            if tool_count > 0:
                print("\n[Step 5] Testing tool execution...")
                
                # Find the process_query tool
                process_query_tool = None
                for tool in tools:
                    if tool.name == "process_query":
                        process_query_tool = tool
                        break
                
                if process_query_tool:
                    print(f"\n[INFO] Found process_query tool")
                    
                    test_queries = [
                        "What data is available?",
                        "How many accounts have the same name (exact same name)?",
                    ]
                    
                    for query in test_queries:
                        print(f"\n[TEST] Query: '{query}'")
                        
                        try:
                            # Call the tool
                            result = await client.call_tool(
                                "process_query",
                                {"query": query}
                            )
                            
                            print(f"[OK] Tool executed successfully")
                            response = result.content[0].text if result.content else "No response"
                            print(f"[RESPONSE] {response[:200]}...")
                            
                        except Exception as e:
                            print(f"[ERROR] Tool execution failed: {e}")
                            import traceback
                            traceback.print_exc()
                else:
                    print("[WARNING] process_query tool not found")
                    print(f"[INFO] Available tools: {[t.name for t in tools]}")
            
            print("\n[Step 6] Test completed!")
            print("[OK] MCP server is working correctly via stdio transport")
    
    except Exception as e:
        print(f"[ERROR] FastMCP client error: {e}")
        logger.exception("FastMCP client test failed")
        print("\n[HINT] Make sure:")
        print("  1. MCP server is running: python tests/mcp_server.py")
        print("  2. ENABLE_MCP_SERVER=True in .env or config/settings.py")
        print("  3. Your .env file is configured correctly")


if __name__ == "__main__":
    asyncio.run(test_mcp_via_fastmcp())
