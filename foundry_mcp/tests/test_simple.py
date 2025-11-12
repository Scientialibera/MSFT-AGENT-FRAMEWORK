"""
Simple test: Does the agent work?
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

print("=" * 80)
print("TEST 1: Direct Agent Call (agent.ask)")
print("=" * 80)

# Initialize agent
agent = SmartSCMFoundryAgent(
    agent_name=os.getenv("FOUNDRY_AGENT_NAME"),
    system_prompt_file="config/orchestrator/system_prompt.txt"
)

# Query
query = "How many accounts have duplicate names?"
print(f"\nQuery: {query}")
print("\nCalling agent.ask()...\n")

response = agent.ask(query)

print("=" * 80)
print("RESPONSE:")
print("=" * 80)
print(response)
print("=" * 80)
print(f"\n✅ SUCCESS - Got {len(response)} characters")
