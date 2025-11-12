"""
Simple end-to-end test: Does the fabricdataagentaccount tool actually work?
"""
import requests
import json
import sys

# Toggle between local and Azure testing
USE_AZURE = len(sys.argv) > 1 and sys.argv[1] == "azure"

if USE_AZURE:
    BASE_URL = "https://mcp-aura.azurewebsites.net"
    print("🌐 Testing AZURE deployment")
else:
    BASE_URL = "http://localhost:8080"
    print("💻 Testing LOCAL deployment")

MCP_ENDPOINT = f"{BASE_URL}/mcp"

def test_tool():
    print("=" * 80)
    print("Testing fabricdataagentaccount tool end-to-end")
    print("=" * 80)
    
    # Step 1: Initialize
    print("\n[1] Initializing...")
    init_req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0"}
        }
    }
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
    }
    
    resp = requests.post(MCP_ENDPOINT, json=init_req, headers=headers)
    if resp.status_code != 200:
        print(f"❌ Init failed: {resp.status_code} - {resp.text}")
        return None
    
    session_id = resp.headers.get("mcp-session-id")
    print(f"✓ Session: {session_id}")
    
    # Step 2: Call tool
    print("\n[2] Calling fabricdataagentaccount...")
    tool_req = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "fabricdataagentaccount",
            "arguments": {"query": "How many accounts have duplicate names?"}
        }
    }
    
    headers["mcp-session-id"] = session_id
    resp = requests.post(MCP_ENDPOINT, json=tool_req, headers=headers, stream=True)
    
    if resp.status_code != 200:
        print(f"❌ Tool failed: {resp.status_code} - {resp.text}")
        return None
    
    print("✓ Tool called")
    
    # Parse response
    print("\n[3] Response:")
    result = ""
    for line in resp.iter_lines():
        if line and line.startswith(b'data: '):
            try:
                data = json.loads(line[6:])
                if 'result' in data and 'content' in data['result']:
                    for item in data['result']['content']:
                        if item.get('type') == 'text':
                            result += item['text']
            except:
                pass
    
    # Print full result with clear borders
    print("\n" + "█" * 100)
    print(result)
    print("█" * 100)
    
    if result:
        print(f"\n✅ SUCCESS ({len(result)} chars)")
        return result
    else:
        print("\n❌ FAILED: No response")
        return None

if __name__ == "__main__":
    try:
        result = test_tool()
        
        if result:
            print("\n✅ TOOL WORKS - Ready to deploy\n")
            exit(0)
        else:
            print("\n❌ TOOL FAILED - Fix before deploying\n")
            exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        import traceback
        traceback.print_exc()
        exit(1)
