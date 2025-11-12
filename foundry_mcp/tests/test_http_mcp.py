"""
Test script for FastMCP HTTP server

Tests the HTTP endpoints of the FastMCP server running on port 8080.
"""

import json
import requests
import sys
from typing import Any, Dict

# Configuration
BASE_URL = "http://localhost:8080"
MCP_ENDPOINT = f"{BASE_URL}/mcp/"

def test_mcp_endpoint() -> bool:
    """Test the MCP HTTP endpoint"""
    try:
        print("\n" + "="*80)
        print("Testing FastMCP HTTP Endpoint")
        print("="*80)
        
        session_id = None
        
        # Test 1: Check if server is responding and get session ID
        print("\n[TEST 1] Getting server info and session ID...")
        try:
            response = requests.get(MCP_ENDPOINT, timeout=5)
            print(f"✓ Server is responding")
            print(f"  Status Code: {response.status_code}")
            
            # Extract session ID from response
            if 'mcp-session-id' in response.headers:
                session_id = response.headers['mcp-session-id']
                print(f"  Session ID: {session_id}")
            
            print(f"  Response: {response.text[:300]}")
        except requests.exceptions.ConnectionError as e:
            print(f"✗ Cannot connect to server: {e}")
            print(f"  Make sure the server is running on {BASE_URL}")
            return False
        
        if not session_id:
            print("✗ No session ID returned from server")
            return False
        
        # Test 2: Initialize/list resources
        print("\n[TEST 2] Initializing connection...")
        init_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0"
                }
            }
        }
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream, application/json",
            "mcp-session-id": session_id
        }
        
        try:
            response = requests.post(
                MCP_ENDPOINT,
                json=init_payload,
                headers=headers,
                timeout=10,
                stream=True
            )
            print(f"✓ Initialize request sent")
            print(f"  Status Code: {response.status_code}")
            
            if response.status_code == 200:
                full_response = ""
                for line in response.iter_lines():
                    if line:
                        decoded = line.decode('utf-8') if isinstance(line, bytes) else line
                        if decoded.startswith("data: "):
                            decoded = decoded[6:]
                        full_response += decoded
                
                print(f"  Response: {full_response[:800]}")
            else:
                print(f"  Error: {response.text[:500]}")
                
        except Exception as e:
            print(f"✗ Error: {e}")
        
        # Test 3: List tools
        print("\n[TEST 3] Listing available tools...")
        
        call_tool_payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "fabricdataagentaccount",
                "arguments": {
                    "query": "How many duplicate accounts?"
                }
            }
        }
        
        try:
            response = requests.post(
                MCP_ENDPOINT,
                json=call_tool_payload,
                headers=headers,
                timeout=60,
                stream=True
            )
            print(f"✓ Tool call request sent")
            print(f"  Status Code: {response.status_code}")
            
            if response.status_code in [200, 206]:
                full_response = ""
                for line in response.iter_lines():
                    if line:
                        decoded = line.decode('utf-8') if isinstance(line, bytes) else line
                        if decoded.startswith("data: "):
                            decoded = decoded[6:]
                        full_response += decoded + "\n"
                
                print(f"  Response:\n{full_response[:1500]}")
            else:
                print(f"  Error: {response.text[:500]}")
                
        except requests.exceptions.Timeout:
            print(f"✗ Tool call timed out (60s) - query may be processing")
        except Exception as e:
            print(f"✗ Error calling tool: {e}")
        
        print("\n" + "="*80)
        print("Testing complete!")
        print("="*80 + "\n")
        return True
        
    except Exception as e:
        print(f"✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        success = test_mcp_endpoint()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
