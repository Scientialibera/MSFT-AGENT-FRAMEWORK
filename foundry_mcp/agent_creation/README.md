# Agent Creation Guide

This directory contains tools to create and test Azure AI Foundry agents connected to Microsoft Fabric.

## Overview

`fabric_agent.py` provides a reusable `SmartSCMFoundryAgent` class that:
- Creates agents in Azure AI Foundry
- Connects to Fabric Data Agents for data access
- Supports additional tools (Bing Search, SharePoint, etc.)
- Reuses existing agents to minimize costs
- Handles thread isolation for query independence

## Quick Start

### 1. Setup Environment

```bash
# Copy environment template
Copy-Item .env.example .env

# Edit .env with your Azure configuration
# See .env.example for detailed descriptions
```

**Minimum required variables:**
```bash
AZURE_OPENAI_URL=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-key
AZURE_AI_MODEL_DEPLOYMENT_NAME=gpt-4
MODEL_VERSION=2024-10-01-preview
AZURE_AI_FOUNDRY_URL=https://your-foundry.api.azureml.ms/
FOUNDRY_FABRIC_RESOURCE_ID=your-fabric-connection-id
```

### 2. Install Dependencies

The main project requirements already include what you need. If running standalone:

```bash
pip install openai azure-ai-projects azure-identity python-dotenv
```

### 3. Create and Query an Agent

```python
from fabric_agent import SmartSCMFoundryAgent
import os

# Create agent
agent = SmartSCMFoundryAgent(
    agent_name="MyDataQueryAgent",
    fabric_connection_id=os.getenv("FOUNDRY_FABRIC_RESOURCE_ID"),
    system_prompt_file="path/to/system_prompt.txt"
)

# Query the agent
response = agent.ask("What is the total revenue by region?")
print(response)
```

### 4. Run Interactive Mode

```bash
python fabric_agent.py
```

Then type your queries. Type `end` to exit.

## Architecture

### Agent Creation Flow

```
SmartSCMFoundryAgent.__init__()
    ↓
Load Azure OpenAI credentials
    ↓
Load Azure AI Foundry credentials
    ↓
Check if agent already exists (by name)
    ↓
    YES → Reuse existing agent (cost optimization)
    NO  → Create new agent with Fabric tool + optional tools
```

### Query Flow

```
agent.ask("Your question")
    ↓
Create isolated thread in Azure AI Foundry
    ↓
Send message to agent
    ↓
Run agent (leverages Fabric + other tools)
    ↓
Extract response from thread
    ↓
Return to user
```

## Usage Patterns

### Single Agent for General Queries

```python
agent = SmartSCMFoundryAgent(
    agent_name="GeneralDataAgent",
    system_prompt_file="config/prompts/general_system_prompt.txt"
)

result = agent.ask("Tell me about our data")
```

### Specialized Agents

Create different agents for different purposes:

```python
# Tariff & Disruption Agent (with market intelligence)
tariff_agent = SmartSCMFoundryAgent(
    agent_name="TariffDisruptionAgent",
    fabric_connection_id=os.getenv("FOUNDRY_FABRIC_RESOURCE_ID_TARIFF"),
    system_prompt_file="config/prompts/tariff_prompt.txt",
    additional_tools=["bing_search"]
)

# Demand Forecasting Agent (Fabric only)
demand_agent = SmartSCMFoundryAgent(
    agent_name="DemandForecastAgent",
    fabric_connection_id=os.getenv("FOUNDRY_FABRIC_RESOURCE_ID_DEMAND"),
    system_prompt_file="config/prompts/demand_prompt.txt"
)

# PO Status Agent (with internal documents)
po_agent = SmartSCMFoundryAgent(
    agent_name="POStatusAgent",
    fabric_connection_id=os.getenv("FOUNDRY_FABRIC_RESOURCE_ID_PO"),
    system_prompt_file="config/prompts/po_prompt.txt",
    additional_tools=["sharepoint"]
)
```

### Batch Processing

```python
agent = SmartSCMFoundryAgent(agent_name="BatchAgent")

queries = [
    "What was revenue in Q1?",
    "Show me top 10 customers",
    "What's the cost breakdown by region?"
]

for query in queries:
    try:
        response = agent.ask(query)
        print(f"Q: {query}\nA: {response}\n")
    except Exception as e:
        print(f"Error on '{query}': {e}")
```

## Configuration

### System Prompts

Create system prompt files to control agent behavior:

```txt
# config/prompts/general_system_prompt.txt

You are a helpful data analyst assistant.
You have access to enterprise data through Fabric Data Agents.

When answering questions:
1. Be specific and cite data sources
2. Provide context when relevant
3. Ask clarifying questions if ambiguous
4. Suggest follow-up queries

Always prioritize accuracy over speed.
```

### Tool Configuration

**Fabric Data Agent** (always enabled):
- Connects to your Fabric workspace
- Provides access to tables, views, reports
- Set via `fabric_connection_id` parameter

**Bing Search** (optional):
```python
additional_tools=["bing_search"]
# Requires: BING_SEARCH_API_KEY
```

**SharePoint** (optional):
```python
additional_tools=["sharepoint"]
# Requires: SHAREPOINT_SITE_URL, SHAREPOINT_CONNECTION_ID
```

## Troubleshooting

### "Missing required environment variables"

Check that all these are set:
```bash
echo $env:AZURE_OPENAI_URL
echo $env:AZURE_OPENAI_API_KEY
echo $env:AZURE_AI_MODEL_DEPLOYMENT_NAME
echo $env:MODEL_VERSION
echo $env:AZURE_AI_FOUNDRY_URL
echo $env:FOUNDRY_FABRIC_RESOURCE_ID
```

### Authentication Errors

Try Azure CLI authentication first:
```bash
az login
```

The agent will use your cached credentials automatically.

### Fabric Connection Errors

Verify your Fabric connection ID:
1. Go to Azure AI Foundry
2. Select your project
3. Go to Data connections
4. Find your Fabric data agent
5. Copy the connection ID

### Agent Creation Failures

Check logs for detailed errors. Common issues:
- Invalid system prompt file path
- Insufficient permissions in Foundry/Fabric
- API quota exceeded
- Network connectivity issues

## Cost Optimization

### Reusing Existing Agents

The agent automatically finds and reuses agents by name:

```python
# First call: Creates agent (costs RUs)
agent1 = SmartSCMFoundryAgent(agent_name="MyAgent")

# Second call: Reuses agent1 (no creation cost)
agent2 = SmartSCMFoundryAgent(agent_name="MyAgent")
```

Each query in a thread consumes RUs based on your model and data complexity.

### Best Practices

1. ✅ Create agents once, reuse them
2. ✅ Use specific system prompts to reduce token usage
3. ✅ Batch queries in a single thread when possible
4. ✅ Monitor usage in Azure AI Foundry console

## API Reference

### SmartSCMFoundryAgent

**Constructor Parameters:**

| Parameter | Required | Description |
|-----------|----------|-------------|
| `agent_name` | Yes | Unique identifier for the agent |
| `fabric_connection_id` | No | Fabric connection ID (uses env var if not provided) |
| `system_prompt_file` | No | Path to system instructions file (default: `system_prompt.txt`) |
| `additional_tools` | No | List of additional tools: `["bing_search", "sharepoint"]` |

**Methods:**

```python
def ask(user_question: str) -> str:
    """
    Query the agent.
    
    Args:
        user_question: Natural language question
        
    Returns:
        Agent response string
        
    Raises:
        RuntimeError: If agent run failed
        EnvironmentError: If config missing
    """
```

## Examples

### Weather & Supply Chain Impact

```python
tariff_agent = SmartSCMFoundryAgent(
    agent_name="SupplyChainIntel",
    additional_tools=["bing_search"]
)

response = tariff_agent.ask(
    "What external factors (weather, tariffs, geopolitics) might impact "
    "our Q4 supply chain? Check current news and our historical data."
)
```

### Demand Planning

```python
demand_agent = SmartSCMFoundryAgent(
    agent_name="DemandPlanner",
    system_prompt_file="config/prompts/demand_analysis_prompt.txt"
)

response = demand_agent.ask(
    "Based on our historical sales and market trends, "
    "forecast demand for product X in Q1 2025"
)
```

### PO Tracking

```python
po_agent = SmartSCMFoundryAgent(
    agent_name="POTracker",
    additional_tools=["sharepoint"]
)

response = po_agent.ask(
    "Show me all delayed purchase orders and their business impact. "
    "Include vendor communication logs from SharePoint."
)
```

## Environment Variables Reference

See `.env.example` for complete list with descriptions.

**Quick reference for creation:**

```bash
# Required
AZURE_OPENAI_URL                    # Azure OpenAI endpoint
AZURE_OPENAI_API_KEY                # Azure OpenAI API key
AZURE_AI_MODEL_DEPLOYMENT_NAME      # Model deployment name
MODEL_VERSION                        # OpenAI API version
AZURE_AI_FOUNDRY_URL               # Foundry project endpoint
FOUNDRY_FABRIC_RESOURCE_ID          # Fabric connection ID

# Optional - For additional tools
BING_SEARCH_API_KEY                 # For Bing Search tool
SHAREPOINT_SITE_URL                 # For SharePoint tool
SHAREPOINT_CONNECTION_ID            # For SharePoint tool
```

## Resources

- [Azure AI Foundry Documentation](https://learn.microsoft.com/azure/ai-foundry/)
- [Fabric Data Agents](https://learn.microsoft.com/fabric/ai/)
- [Azure OpenAI API](https://learn.microsoft.com/azure/ai-services/openai/)

## Next Steps

1. ✅ Setup environment variables
2. ✅ Test agent creation and querying
3. ✅ Integrate into MCP server
4. ✅ Deploy to Azure
