"""
Test MCP ListTools request
"""
import requests
import json
import sys

# Toggle between local and Azure
USE_AZURE = len(sys.argv) > 1 and sys.argv[1] == "azure"

if USE_AZURE:
    MCP_ENDPOINT = "https://mcp-aura.azurewebsites.net/mcp"
    print("Testing MCP ListTools request on AZURE...")
else:
    MCP_ENDPOINT = "http://localhost:8080/mcp"
    print("Testing MCP ListTools request LOCALLY...")
print("=" * 80)

# Step 1: Initialize
print("\n[1] Initialize...")
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
print(f"Status: {resp.status_code}")
print(f"Response: {resp.text[:200]}")

session_id = resp.headers.get("mcp-session-id")
print(f"Session ID: {session_id}")

# Step 2: List Tools
print("\n[2] List Tools...")
list_tools_req = {
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list",
    "params": {}
}

headers["mcp-session-id"] = session_id
resp = requests.post(MCP_ENDPOINT, json=list_tools_req, headers=headers, stream=True)
print(f"Status: {resp.status_code}")

# Parse response
result = ""
for line in resp.iter_lines():
    if line:
        print(f"Line: {line[:200]}")
        if line.startswith(b'data: '):
            try:
                data = json.loads(line[6:])
                result = json.dumps(data, indent=2)
            except Exception as e:
                print(f"Error parsing: {e}")

print("\n[3] Tools Response:")
print("=" * 80)
print(result if result else "No response")
print("=" * 80)
