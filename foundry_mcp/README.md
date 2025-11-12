# Fabric Data Agent MCP Server

Production-ready Model Context Protocol (MCP) server exposing Azure AI Foundry's Fabric Data Agent as a reusable tool for any MCP client.

## Quick Overview

```
User Query → Claude Desktop → MCP Server → Azure AI Foundry → Fabric Data → Response
```

- **What**: MCP server wrapping Azure AI Foundry agent
- **Why**: Query Fabric data through any MCP-compatible client (Claude, etc.)
- **How**: FastMCP framework + DefaultAzureCredential for auth

## Key Features

✅ **Production-Ready**
- Docker containerization for Azure App Service
- Managed Identity authentication
- Structured error handling

✅ **Enterprise Data Access**
- Native Fabric Data Agent integration
- Pre-configured system prompts
- Thread-isolated queries

✅ **Easy Integration**
- Single MCP tool: `fabricdataagentaccount`
- Natural language queries
- Automatic response formatting

## Quick Start

### Option 1: Local Testing (5 minutes)

```bash
# Prerequisites: Python 3.11+, Azure CLI logged in
az login

# Start server (from project root)
python foundry_mcp/app/mcp_server.py
```

### Option 2: Docker (10 minutes)

```bash
# Build
docker build -f foundry_mcp/deployment/Dockerfile -t fabric-mcp:latest .

# Run
docker run -e ENABLE_MCP_SERVER=True fabric-mcp:latest
```

### Option 3: Azure App Service (30 minutes)

See `deployment/README.md` for full instructions.

## Configuration

All settings in **single `.env` file** → `foundry_mcp/.env`

```bash
# Required
ENABLE_MCP_SERVER=True
FOUNDRY_AGENT_NAME=SmartSCMFabricAgenttemplate
AZURE_OPENAI_URL=https://...
AZURE_AI_FOUNDRY_URL=https://...
FOUNDRY_FABRIC_RESOURCE_ID=...

# Optional
LOG_LEVEL=INFO
FOUNDRY_SYSTEM_PROMPT_FILE=config/orchestrator/system_prompt.txt
```

See `.env` for full details with descriptions.

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│  MCP Clients                                             │
│  (Claude Desktop, LLMs, APIs)                           │
└────────────────────────┬─────────────────────────────────┘
                         │ JSON-RPC stdio
                         ▼
┌──────────────────────────────────────────────────────────┐
│  FastMCP Server (mcp_server.py)                         │
│  ├─ Handles protocol messaging                          │
│  └─ Exposes: fabricdataagentaccount tool               │
└────────────────────────┬─────────────────────────────────┘
                         │ Agent SDK
                         ▼
┌──────────────────────────────────────────────────────────┐
│  Azure AI Foundry Agent                                 │
│  ├─ Orchestration                                       │
│  └─ Tools: Fabric Data Agent                           │
└────────────────────────┬─────────────────────────────────┘
                         │ Native tool
                         ▼
┌──────────────────────────────────────────────────────────┐
│  Microsoft Fabric Data Agent                            │
│  └─ Enterprise data queries                             │
└──────────────────────────────────────────────────────────┘
```

## Project Structure

```
foundry_mcp/
├── .env                       # Single config file (DO NOT COMMIT)
├── .env.example              # Config template
├── README.md                 # This file
├── app/
│   ├── mcp_server.py        # Main MCP server ⭐
│   ├── __init__.py
│   └── settings.py          # Config loader
├── agent_creation/
│   ├── fabric_agent.py      # Agent wrapper class
│   ├── .env                 # Deprecated (see ../env)
│   ├── test_agent.py        # Standalone agent test
│   └── __init__.py
├── config/
│   ├── orchestrator/
│   │   └── system_prompt.txt # Agent instructions
│   └── tools/
│       └── fabric_data_agent_account.json  # Tool schema
├── deployment/
│   ├── Dockerfile           # Production container
│   ├── README.md            # Deployment guide ⭐
│   └── Deploy-ToWebApp.ps1  # Azure deployment script
└── tests/
    └── test_mcp_server.py   # MCP server validation ⭐
```

## Testing

### Unit Test (Validates Agent)

```bash
python foundry_mcp/tests/test_mcp_server.py
```

Expected: Agent initializes → Query sent → Response received

### Manual Test (MCP Server)

```bash
# Terminal 1: Start server
python foundry_mcp/app/mcp_server.py

# Terminal 2: Send test query (Claude Desktop, custom client, etc.)
# Server listens on stdin/stdout for JSON-RPC messages
```

## Usage Example

### Query the Fabric Data Agent

```python
# Programmatically
from foundry_mcp.agent_creation.fabric_agent import SmartSCMFoundryAgent

agent = SmartSCMFoundryAgent()
response = agent.ask("How many accounts have duplicate names?")
print(response)
```

### Through Claude Desktop

Edit `~/.config/claude_desktop_config.json` (or Windows equivalent):

```json
{
  "mcpServers": {
    "fabric-data-agent": {
      "command": "python",
      "args": ["C:\\path\\to\\foundry_mcp\\app\\mcp_server.py"],
      "env": {
        "ENABLE_MCP_SERVER": "True"
      }
    }
  }
}
```

Then in Claude, use the `fabricdataagentaccount` tool.

## Deployment

### To Azure App Service

See `deployment/README.md` for step-by-step guide.

Quick summary:
1. Build Docker image
2. Push to ACR
3. Create App Service with Managed Identity
4. Set environment variables
5. Deploy container

## Troubleshooting

### Server Won't Start
```bash
# Check if MCP is enabled
echo $env:ENABLE_MCP_SERVER  # Should be: True

# Verify Azure CLI login
az account show
```

### Authentication Error
```bash
# Login with Azure CLI
az login

# Or set environment variables
# AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID
```

### Agent Query Fails
- Verify Fabric connection ID is correct
- Check system prompt file exists: `config/orchestrator/system_prompt.txt`
- Review Azure AI Foundry project for agent configuration

## Configuration Files Reference

| File | Purpose |
|------|---------|
| `.env` | Single source of truth for all config |
| `app/mcp_server.py` | MCP server entry point |
| `agent_creation/fabric_agent.py` | Agent wrapper + initialization |
| `config/orchestrator/system_prompt.txt` | LLM system instructions |
| `deployment/Dockerfile` | Production container image |
| `deployment/README.md` | Complete deployment guide |

## Dependencies

See `requirements.txt` in project root for full list. Key:

- `fastmcp>=0.1` - MCP framework
- `azure-ai-projects>=1.0` - Foundry SDK
- `azure-identity>=1.13` - Azure authentication
- `openai>=1.0` - Azure OpenAI client

## Key Variables

All in `.env`:

```
FOUNDRY_AGENT_NAME          - Agent to create/reuse
FOUNDRY_SYSTEM_PROMPT_FILE  - System instructions file
FOUNDRY_FABRIC_RESOURCE_ID  - Connection to Fabric workspace
AZURE_OPENAI_URL            - OpenAI endpoint
AZURE_AI_FOUNDRY_URL        - Foundry project endpoint
```

## Security

✅ **Authentication**: Managed Identity (App Service) or Azure CLI (local)
✅ **No Secrets in Code**: All config via `.env` and environment variables
✅ **HTTPS Only**: App Service enforces TLS
✅ **Logging**: All requests logged to stderr (outside MCP channel)

## Next Steps

1. **Quick Test**: `python foundry_mcp/tests/test_mcp_server.py`
2. **Local Dev**: `python foundry_mcp/app/mcp_server.py`
3. **Deploy**: Follow `deployment/README.md`
4. **Integrate**: Add to Claude Desktop or other MCP client

## See Also

- `deployment/README.md` - Detailed deployment guide
- `agent_creation/fabric_agent.py` - Agent implementation
- `foundry_mcp/agent_creation/FABRIC_CONNECTION_SETUP.md` - Connection setup guide

## License

See LICENSE in project root.
- 🔐 Azure authentication with Managed Identity support
- 🐳 Docker-ready with multi-stage build for minimal image size
- ☁️ Azure App Service deployment guide included
- 📊 Structured logging and error handling
- 🛡️ Non-root user execution for security

## Quick Start

### Local Development

1. **Setup environment**
   ```bash
   Copy-Item .env.example .env
   # Edit .env with your Azure credentials
   ```

2. **Install dependencies**
   ```bash
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r ../requirements.txt
   ```

3. **Run MCP server**
   ```bash
   $env:ENABLE_MCP_SERVER = "True"
   python app/mcp_server.py
   ```

### Docker Deployment

```bash
# Build
docker build -f deployment/Dockerfile -t fabric-mcp-server:latest .

# Run locally
docker run --rm -it `
  -e ENABLE_MCP_SERVER=True `
  -e AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/ `
  -e AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4 `
  fabric-mcp-server:latest

# Push to Azure Container Registry
docker tag fabric-mcp-server:latest auraboreg.azurecr.io/fabric-mcp-server:latest
docker push auraboreg.azurecr.io/fabric-mcp-server:latest
```

### Azure App Service

See [`deployment/README.md`](deployment/README.md) for comprehensive deployment instructions.

## Configuration

### Environment Setup

The MCP server delegates all Azure configuration to the Fabric Data Agent. You need environment variables from **two sources**:

#### 1. Agent Creation Variables (Required)
Copy from `agent_creation/.env.example`:
```bash
AZURE_OPENAI_URL=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-key
AZURE_AI_MODEL_DEPLOYMENT_NAME=gpt-4
MODEL_VERSION=2024-10-01-preview
AZURE_AI_FOUNDRY_URL=https://your-foundry.api.azureml.ms/
FOUNDRY_FABRIC_RESOURCE_ID=your-fabric-connection-id
```

#### 2. MCP Server Variables (Optional)
From `.env.example`:
```bash
ENABLE_MCP_SERVER=True
LOG_LEVEL=INFO
```

### Complete .env Template

```bash
# Agent Creation (REQUIRED)
AZURE_OPENAI_URL=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_AI_MODEL_DEPLOYMENT_NAME=gpt-4
MODEL_VERSION=2024-10-01-preview
AZURE_AI_FOUNDRY_URL=https://your-foundry.api.azureml.ms/
FOUNDRY_FABRIC_RESOURCE_ID=your-fabric-connection-id

# MCP Server (Optional)
ENABLE_MCP_SERVER=True
LOG_LEVEL=INFO
SYSTEM_PROMPT_FILE=config/orchestrator/system_prompt.txt

# Optional: Additional tools (if using in agent_creation)
# BING_SEARCH_API_KEY=your-key
# SHAREPOINT_SITE_URL=https://site.sharepoint.com
# SHAREPOINT_CONNECTION_ID=connection-id
```

### Authentication

The agent uses `DefaultAzureCredential`, which automatically tries:
1. Environment variables (for service principals)
2. Managed Identity (in Azure App Service)
3. Azure CLI cached credentials (`az login`)
4. Interactive browser login

### Example .env File

```bash
ENABLE_MCP_SERVER=True
AZURE_OPENAI_URL=https://my-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=sk-...
AZURE_AI_MODEL_DEPLOYMENT_NAME=gpt-4
MODEL_VERSION=2024-10-01-preview
AZURE_AI_FOUNDRY_URL=https://my-foundry.api.azureml.ms/
FOUNDRY_FABRIC_RESOURCE_ID=my-fabric-connection
LOG_LEVEL=INFO
```

## Project Structure

```
foundry_mcp/
├── app/
│   ├── __init__.py
│   ├── mcp_server.py              # Main application
│   └── settings.py                # Configuration (pydantic-based)
│
├── config/
│   └── tools/
│       └── fabric_data_agent_account.json  # Tool definition
│
├── deployment/
│   ├── Dockerfile                 # Multi-stage Docker build
│   └── README.md                  # Deployment guide
│
├── .env.example                   # Environment template
└── README.md                       # This file
```

## Tool Documentation

### fabricdataagentaccount

Query the Fabric Data Agent for business intelligence and financial data.

**Parameters:**
- `query` (required): Natural language query about data or insights
- `reasoning` (optional): Context to improve results
- `filters` (optional): Specific filters (dict of key-value pairs)

**Example:**
```json
{
  "query": "What is the total revenue by region for Q3 2024?",
  "reasoning": "Need regional breakdown for quarterly business review",
  "filters": {
    "date_range": "2024-Q3",
    "departments": ["Sales", "Finance"]
  }
}
```

**Returns:**
- Success: Data insights and analysis from Fabric Data Agent
- Error: Descriptive error message with context

## Integration with Claude Desktop

Add to `%APPDATA%\Claude\claude_desktop_config.json`:

**For Local Development:**
```json
{
  "mcpServers": {
    "fabric-data-agent": {
      "command": "python",
      "args": ["C:\\path\\to\\foundry_mcp\\app\\mcp_server.py"],
      "env": {
        "ENABLE_MCP_SERVER": "True",
        "AZURE_OPENAI_ENDPOINT": "https://your-resource.openai.azure.com/",
        "AZURE_OPENAI_CHAT_DEPLOYMENT": "gpt-4"
      }
    }
  }
}
```

**For Azure App Service:**
```json
{
  "mcpServers": {
    "fabric-data-agent": {
      "command": "curl",
      "args": ["https://your-app.azurewebsites.net/mcp"]
    }
  }
}
```

Then restart Claude Desktop to activate the tool.

## Architecture

```
MCP Client (Claude, etc.)
        ↓ (JSON-RPC via stdio)
    FastMCP Server
        ↓
    fabricdataagentaccount tool
        ↓
    AIAssistant (Agent Framework)
        ↓
    Azure AI Foundry (Fabric Data Agent)
        ↓
    Enterprise Data Sources
```

## Logging

Logs are written to stderr to preserve stdout for MCP JSON-RPC protocol compliance.

**Log Levels:**
- `DEBUG`: Detailed information for debugging
- `INFO`: General informational messages
- `WARNING`: Warning messages
- `ERROR`: Error messages with stack traces
- `CRITICAL`: Critical failures

Configure via `LOG_LEVEL` environment variable.

## Performance

- **Startup Time**: ~2-3 seconds (includes Azure credential loading)
- **Query Latency**: Depends on Fabric Data Agent response time
- **Memory**: ~200-300 MB base + query overhead

## Security Considerations

✅ **Best Practices Implemented:**
- Non-root user execution in Docker
- Managed Identity support for Azure App Service
- Credential handling via `DefaultAzureCredential`
- Structured logging for audit trails
- Error messages don't expose sensitive data

⚠️ **Additional Recommendations:**
- Use HTTPS for all communications
- Enable Azure Virtual Networks for private connectivity
- Store secrets in Azure Key Vault
- Enable Application Insights monitoring
- Implement request authentication at the client level

## Troubleshooting

### MCP Server Won't Start

```bash
# Check environment
$env:ENABLE_MCP_SERVER
$env:AZURE_OPENAI_ENDPOINT
$env:AZURE_OPENAI_CHAT_DEPLOYMENT

# Check Azure credentials
az account show
```

### Authentication Errors

```bash
# Login with Azure CLI
az login

# Check Managed Identity in App Service
az webapp identity show --name fabric-mcp-app --resource-group fabric-mcp-rg
```

### Query Errors

1. Check server logs for detailed errors
2. Verify Fabric Data Agent services are running
3. Test with simpler queries first
4. Check Azure OpenAI quota and limits

## Development

### Running Tests

```bash
# From project root
pytest tests/ -v
```

### Building Locally

```bash
# Install dev dependencies
pip install -r requirements.txt pytest

# Run the server
python foundry_mcp/app/mcp_server.py
```

## Deployment Guides

- **Local Development**: See Quick Start section above
- **Docker**: See Docker commands above
- **Azure App Service**: See [`deployment/README.md`](deployment/README.md)
- **Claude Desktop**: See Integration section above

## FastMCP Best Practices

This project implements FastMCP best practices:

✅ **Tool Design**
- Single, focused responsibility
- Clear parameter descriptions
- Structured return types
- Error handling and logging

✅ **Architecture**
- Async/await throughout
- Resource initialization at startup
- Graceful shutdown handling
- Proper logging to stderr

✅ **Deployment**
- Multi-stage Docker build
- Non-root user execution
- Health checks
- Environment-based configuration

## Resources

- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [Azure App Service Documentation](https://learn.microsoft.com/azure/app-service/)
- [Azure OpenAI Documentation](https://learn.microsoft.com/azure/cognitive-services/openai/)
- [Microsoft Agent Framework](https://github.com/microsoft/agent-framework)

## License

See LICENSE file in project root.

## Contributing

Contributions are welcome! Please:
1. Follow the existing code style
2. Add tests for new features
3. Update documentation
4. Submit a pull request

## Support

For issues, questions, or suggestions:
1. Check the troubleshooting section
2. Review logs for error details
3. Open an issue with detailed information
