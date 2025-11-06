# Multi-Source AI Assistant

Enterprise-grade Python application using Microsoft's Agent Framework. The LLM autonomously decides which tools to call, chains them, and synthesizes answers. That's the entire pattern.

## Documentation

## Quick Start

```bash
# Setup
git clone <repo>
cd fabric-data-agent
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your settings

# Run tests
python tests/test_agentic_queries.py
```

---

# The Pattern

```
Query comes in
       ↓
LLM sees question + available tools
       ↓
LLM decides: "Do I need a tool?"
       ├─ NO  → Return answer (DONE)
       └─ YES → Call tool(s)
              ↓
           Tool executes → returns result
              ↓
           Result added to conversation context
              (LLM will see it)
              ↓
           LLM decides: "Answer or call another tool?"
              ├─ ANSWER → Return answer (DONE)
              └─ TOOL   → Loop (go back)
```

This pattern applies to any LLM-based agent: the LLM makes tool decisions automatically because it sees all results in context.

---

# Adding Tools - Dynamic Discovery Pattern

This system uses **automatic tool discovery** based on a strict naming convention. Add a new tool by simply creating 2 files and 1 factory function - no code changes needed!

## The Naming Convention

Tools are auto-discovered using this 1:1:1 mapping:

```
config/tools/<NAME>.json         ← Tool config (metadata)
         ↓
src/<NAME>/service.py            ← Service implementation + factory function
         ↓ (auto-created)
Agent can use the tool
```

## Step 1: Create Tool Configuration

**File: `config/tools/<NAME>.json`**

```json
{
  "function": {
    "name": "query_sql_database",
    "description": "Query SQL database for operational data",
    "parameters": {
      "properties": {
        "reasoning": {
          "type": "string",
          "description": "Why are you calling this tool?"
        },
        "query": {
          "type": "string",
          "description": "Natural language question (NOT SQL)"
        }
      }
    }
  }
}
```

## Step 2: Create Service Class + Factory Function

**File: `src/sql_database/service.py`**

```python
import os
from typing import Dict, Any, Optional

class SqlDatabaseService:
    """Query operational data from SQL database."""
    
    def __init__(self, connection_string: str):
        """Initialize with connection parameters."""
        self.connection_string = connection_string
    
    def run(self, tool_call: Dict[str, Any] = None) -> str:
        """
        Execute query.
        
        Args:
            tool_call: Dict with parameters (query, reasoning, etc) from LLM
        
        Returns:
            String result
        """
        query = tool_call.get('query', '')
        reasoning = tool_call.get('reasoning', '')
        
        # Your query logic here
        results = self._execute_query(query)
        return str(results)
    
    def _execute_query(self, query: str) -> str:
        """Execute the actual query."""
        # Implementation
        pass
    
    def close(self):
        """Cleanup resources."""
        pass


# Singleton instance
_service: Optional[SqlDatabaseService] = None


def get_sql_database_service() -> SqlDatabaseService:
    """Get or create service instance following naming convention."""
    global _service
    
    if _service is None:
        connection_string = os.getenv("SQL_DATABASE_CONNECTION_STRING")
        if not connection_string:
            raise ValueError("SQL_DATABASE_CONNECTION_STRING environment variable required")
        
        _service = SqlDatabaseService(connection_string=connection_string)
    
    return _service
```

## That's It!

Tool loader automatically:
1. Discovers `config/tools/sql_database.json`
2. Calls `get_sql_database_service()` factory function
3. Creates typed tool function with proper parameters
4. Registers with Agent Framework
5. Agent can now use the tool

**No code changes needed anywhere!** The loader:
- Scans `config/tools/` directory
- For each `<name>.json`, looks for `src/<name>/service.py`
- Calls `get_<name>_service()` factory function
- Dynamically creates tool function with exact parameters from config
- Registers with agent

---

## System Prompt Configuration

After adding tools, update `config/orchestrator/system_prompt.txt` to help the LLM understand the available tools and when to use them.

**Why update the system prompt?**
- Tells the LLM which tools exist and what they're for
- Provides context about data sources (Fabric, SQL, API, etc.)
- Helps the LLM decide which tool to use for different questions
- Enables better tool chaining (combining results from multiple tools)

**Example system prompt snippet:**

```
You are an AI assistant with access to multiple data sources:

1. Fabric Data Agent - Query business/financial data
   - Use for: revenue, sales, customer data, KPIs
   - Available in: Power BI semantic models, warehouses, lakehouses

2. SQL Database - Query operational data
   - Use for: customer records, orders, transactions
   - Available in: Corporate SQL Server

3. External API - Search market data
   - Use for: industry benchmarks, competitor data, market trends

When a user asks a question:
- Determine which tool(s) have the data they need
- Call the appropriate tool(s)
- Combine results if needed
- Provide a synthesized answer

Example: "Show Q4 revenue vs industry average"
  → Call: query_fabric_data_agent("Q4 revenue")
  → Call: search_api("Q4 industry average")
  → Synthesize and compare both results
```

**Key tips:**
- Be specific about what data each tool accesses
- Give examples of questions for each tool
- Explain when to use multiple tools together
- Update this whenever you add or remove tools

---

## Done!

Agent Framework automatically:
- Adds tool to LLM's available tools
- LLM calls it when needed
- Feeds result back to LLM context
- LLM chains with other tools (because it sees all results)

No routing. No orchestration. Just services + tools.

---

## Example: SQL Database Tool

To add SQL database querying capability, follow the 2-step pattern above:

1. Create `config/tools/sql_database.json`
2. Create `src/sql_database/service.py` with `get_sql_database_service()` factory

**That's it!** The loader automatically discovers and registers the tool.

# Multi-Tool Scenario

**User**: "Show Q4 revenue and compare to monthly sales trend"

```
LLM sees available tools:
  - query_fabric_data_agent()
  - query_sql_database()

LLM reasoning:
  "Need financial metrics AND operational trends"

1. Calls query_fabric_data_agent("Q4 revenue")
   → Returns: "Q4 revenue: $50M (up 15% QoQ)"
   → Added to context

2. Calls query_sql_database("monthly sales trend 2024")
   → Returns: "Jan: $10M, Feb: $11M, ... Dec: $15M"
   → Added to context

3. LLM sees both results
   → Synthesizes: "Q4 (Oct-Dec avg: $13.3M) shows strong 
                   growth trend throughout year"
   → Returns answer
```

The LLM combines results automatically because it sees all tool outputs in context.

---

# Multi-Tool Scenario

**User**: "Show Q4 revenue and compare to industry average"

```
LLM sees available tools:
  - query_fabric_data_agent()
  - search_external_api()

LLM reasoning:
  "Need both internal and external data"

1. Calls query_fabric_data_agent("Q4 revenue")
   → Returns: "$50M"
   → Added to context

2. Calls search_external_api("industry average")
   → Returns: "$45M"
   → Added to context

3. LLM sees both results in context
   → Synthesizes: "Our $50M is 11% above industry $45M"
   → Returns answer
```

**The LLM did all the combining automatically** because it saw both tool results.

---

# Project Structure

```
src/
├── orchestrator/
│   ├── main.py                   # AIAssistant + tool loader
│   ├── loader.py                 # Dynamic tool discovery
│   └── __init__.py
├── fabric_data/
│   ├── client.py
│   └── service.py                # Service + factory function
└── __init__.py

config/
├── orchestrator/
│   └── system_prompt.txt
├── src/
│   └── settings.py
├── tools/
│   └── fabric_data.json          # Tool config
└── .env

tests/
└── test_agentic_queries.py
```

---

# Naming

**Services**: `{Source}Service`
- `FabricAgentService`
- `DatabaseService`
---

# Configuration

## `.env` (Your Settings)

```bash
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4o
TENANT_ID=your-tenant-id
DATA_AGENT_URL=https://api.fabric.microsoft.com/v1/workspaces/xxx/...

# Optional (uses defaults if not set)
# AZURE_OPENAI_TEMPERATURE=0.7
# AZURE_OPENAI_MAX_TOKENS=2000
```

## `config/src/settings.py`

Contains defaults and validation. Load with:

```python
from config.src.settings import AzureOpenAISettings
settings = AzureOpenAISettings()
```

## `config/orchestrator/system_prompt.txt`

Tells LLM what tools exist and when to use them. Update whenever you add/remove tools.

---

# Using as MCP Server

Expose the AI Assistant as a Model Context Protocol (MCP) server to use it as a tool in MCP-compatible clients (VS Code Copilot Agents, Claude, etc.).

## Enable MCP

**Option 1: Environment Variable (`recommended for production`)**

```bash
# In .env file
ENABLE_MCP_SERVER=true
```

**Option 2: Configuration File**

**File: `src/config/settings.py`**

```python
# Set to True to expose the agent as an MCP server
ENABLE_MCP_SERVER = True
```

## Run MCP Server

```bash
python tests/mcp_server.py
```

The agent is now available as a tool to any MCP-compatible client.

---

# Testing

```python
import asyncio
from src.orchestrator.main import AIAssistant
from config.src.settings import AzureOpenAISettings


async def test():
    settings = AzureOpenAISettings.from_env()
    assistant = AIAssistant(aoai_settings=settings)
    
    result = await assistant.process_question(
        "Show top 5 orders"
    )
    
    print(f"Success: {result['success']}")
    print(f"Response: {result['response']}")


asyncio.run(test())
```

---

# How Agent Framework Works Behind The Scenes

When you call `process_question(question)`:

1. All functions in `self.tools` are registered with the LLM
2. LLM receives: question + list of available tools
3. LLM decides: "Which tool(s) do I need?"
4. If tool chosen: Execute it, get result
5. Add result to conversation context
6. Go to step 2 (LLM sees everything: original question + all tool results)
7. Repeat until LLM answers without tools

**You provide**: Services (data access) + Tools (function signatures)
**Agent Framework provides**: Looping, context management, routing

---