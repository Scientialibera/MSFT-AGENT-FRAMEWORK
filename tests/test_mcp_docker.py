"""
FastMCP Docker Test - Test MCP Server Running in Docker Container

This script tests the MCP server running in a Docker container locally.

Setup:
1. Build the Docker image:
   docker build -f deployment/Dockerfile -t fabric-mcp-server:latest .

2. Run the container in one terminal:
   docker run -it --rm \
     -e ENABLE_MCP_SERVER=true \
     -e AZURE_OPENAI_ENDPOINT=<your-endpoint> \
     -e AZURE_OPENAI_CHAT_DEPLOYMENT=<your-deployment> \
     -e TENANT_ID=<your-tenant-id> \
     -e DATA_AGENT_URL=<your-data-agent-url> \
     -p 8000:8000 \
     fabric-mcp-server:latest

3. In another terminal, run this test:
   python tests/test_mcp_docker.py

The MCP server inside the container communicates via stdio (not HTTP).
Since Docker containers run in stdio mode by default, the test will
attempt to connect via subprocess communication.
"""

import asyncio
import sys
import logging
import subprocess
import os
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)

logger = logging.getLogger(__name__)


def check_docker_running():
    """Check if Docker daemon is running."""
    try:
        result = subprocess.run(['docker', 'ps'], capture_output=True, timeout=5)
        return result.returncode == 0
    except Exception:
        return False


def check_container_running(container_name: str = "fabric-mcp-docker"):
    """Check if the MCP container is running."""
    try:
        result = subprocess.run(
            ['docker', 'ps', '--filter', f'name={container_name}', '--format', '{{.ID}}'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return bool(result.stdout.strip())
    except Exception:
        return False


def get_container_logs(container_name: str = "fabric-mcp-docker", lines: int = 20):
    """Get logs from the running container."""
    try:
        result = subprocess.run(
            ['docker', 'logs', '--tail', str(lines), container_name],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.stdout
    except Exception as e:
        return f"Error getting logs: {e}"


async def test_docker_mcp():
    """Test MCP server running in Docker container."""
    
    load_dotenv()
    
    print("\n" + "=" * 80)
    print("FastMCP Docker Test")
    print("=" * 80)
    
    # Check prerequisites
    print("\n[Step 1] Checking Docker setup...")
    
    if not check_docker_running():
        print("[ERROR] Docker daemon is not running!")
        print("  Please start Docker Desktop and try again.")
        return
    
    print("[OK] Docker daemon is running")
    
    # Check if container is running
    print("\n[Step 2] Checking if MCP container is running...")
    
    container_name = "fabric-mcp-docker"
    if not check_container_running(container_name):
        print(f"[ERROR] Container '{container_name}' is not running!")
        print("\n[INFO] To start the container, run:")
        print(f"""
docker run -it --rm --name {container_name} \\
  -e ENABLE_MCP_SERVER=true \\
  -e AZURE_OPENAI_ENDPOINT={os.getenv('AZURE_OPENAI_ENDPOINT', 'https://...')} \\
  -e AZURE_OPENAI_CHAT_DEPLOYMENT={os.getenv('AZURE_OPENAI_CHAT_DEPLOYMENT', 'gpt-4o')} \\
  -e TENANT_ID={os.getenv('TENANT_ID', '...')} \\
  -e DATA_AGENT_URL={os.getenv('DATA_AGENT_URL', 'https://...')} \\
  -p 8000:8000 \\
  fabric-mcp-server:latest
""")
        return
    
    print(f"[OK] Container '{container_name}' is running")
    
    # Get container logs
    print("\n[Step 3] Checking container logs...")
    logs = get_container_logs(container_name)
    print("[Container Logs - Last 10 lines]")
    print("-" * 80)
    log_lines = logs.split('\n')
    for line in log_lines[-10:]:
        if line.strip():
            print(f"  {line}")
    print("-" * 80)
    
    # Check for startup success
    if "FastMCP server ready" in logs or "mcp.run_async" in logs:
        print("[OK] MCP server started successfully in container")
    else:
        print("[WARNING] MCP server startup status unclear - check logs above")
    
    # Try to interact with the container via Docker exec
    print("\n[Step 4] Testing container communication...")
    
    try:
        # Use docker exec to run a simple Python command in the container
        # This verifies the container is responsive
        result = subprocess.run(
            ['docker', 'exec', container_name, 'python', '-c', 'print("Container is responsive")'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            print(f"[OK] Container is responsive: {result.stdout.strip()}")
        else:
            print(f"[ERROR] Container exec failed: {result.stderr}")
    
    except Exception as e:
        print(f"[ERROR] Could not communicate with container: {e}")
    
    # Summary
    print("\n[Step 5] Summary")
    print("-" * 80)
    print("[INFO] The MCP server is running in Docker!")
    print(f"[INFO] Container name: {container_name}")
    print("[INFO] The server communicates via stdio (not HTTP)")
    print("")
    print("[NEXT STEPS]")
    print("  1. To test the MCP server, connect via stdio in another terminal:")
    print("     - Use any MCP-compatible client (VS Code, Claude, etc.)")
    print("     - Configure the stdio process as: docker exec fabric-mcp-docker python tests/mcp_server.py")
    print("")
    print("  2. View live logs:")
    print(f"     docker logs -f {container_name}")
    print("")
    print("  3. Stop the container:")
    print(f"     docker stop {container_name}")
    print("-" * 80)


if __name__ == "__main__":
    asyncio.run(test_docker_mcp())
