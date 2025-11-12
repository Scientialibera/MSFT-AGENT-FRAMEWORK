# Fabric Data Agent MCP Server - Deployment Guide

## Overview

This directory contains deployment configuration for the FastMCP server that exposes the Azure AI Foundry Fabric Data Agent as a Model Context Protocol (MCP) server.

The server can be deployed to:
- **Azure App Service** (recommended for production)
- **Local development** via Docker
- **Direct execution** for testing

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  MCP Client (Claude Desktop, etc.)                         │
└────────────────────────┬────────────────────────────────────┘
                         │ JSON-RPC (via stdio)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  FastMCP Server (../app/mcp_server.py)                     │
│  └─ fabricdataagentaccount tool                            │
└────────────────────────┬────────────────────────────────────┘
                         │ Azure AI Foundry SDK
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Azure AI Foundry Agent + Fabric Data Connection           │
│  └─ Queries enterprise data via Fabric                     │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Local Development

```bash
# From project root
python foundry_mcp/app/mcp_server.py
```

Requires:
- `.env` configured in `foundry_mcp/` with `ENABLE_MCP_SERVER=True`
- Azure CLI login (`az login`)
- Python 3.11+

### 2. Docker Build

```bash
# From project root
docker build -f foundry_mcp/deployment/Dockerfile -t fabric-mcp-server:latest .
```

### 3. Push to Azure Container Registry

```bash
# Login
az acr login --name auraboreg

# Tag
docker tag fabric-mcp-server:latest auraboreg.azurecr.io/fabric-mcp-server:latest

# Push
docker push auraboreg.azurecr.io/fabric-mcp-server:latest
```

## Azure App Service Deployment

### Step 1: Create App Service (One-time setup)

```bash
# Create resource group
az group create --name fabric-mcp-rg --location eastus

# Create App Service plan
az appservice plan create `
  --name fabric-mcp-plan `
  --resource-group fabric-mcp-rg `
  --sku B1 `
  --is-linux

# Create web app
az webapp create `
  --resource-group fabric-mcp-rg `
  --plan fabric-mcp-plan `
  --name fabric-mcp-app `
  --deployment-container-image-name auraboreg.azurecr.io/fabric-mcp-server:latest
```

### Step 2: Enable Managed Identity

```bash
# Assign system-managed identity
az webapp identity assign `
  --name fabric-mcp-app `
  --resource-group fabric-mcp-rg
```

### Step 3: Configure Environment Variables

```bash
az webapp config appsettings set `
  --resource-group fabric-mcp-rg `
  --name fabric-mcp-app `
  --settings `
    ENABLE_MCP_SERVER=True `
    FOUNDRY_AGENT_NAME=SmartSCMFabricAgenttemplate `
    FOUNDRY_SYSTEM_PROMPT_FILE=config/orchestrator/system_prompt.txt `
    AZURE_OPENAI_URL=https://your-resource.openai.azure.com/ `
    AZURE_AI_MODEL_DEPLOYMENT_NAME=gpt-4o `
    MODEL_VERSION=2024-10-01-preview `
    AZURE_AI_FOUNDRY_URL=https://aura-ai-foundry-2025.services.ai.azure.com/api/projects/fabric-data-agent-proj `
    FOUNDRY_FABRIC_RESOURCE_ID=<YOUR_CONNECTION_ID> `
    LOG_LEVEL=INFO
```

### Step 4: Configure Container Registry Access

```bash
az webapp config container set `
  --name fabric-mcp-app `
  --resource-group fabric-mcp-rg `
  --docker-custom-image-name auraboreg.azurecr.io/fabric-mcp-server:latest `
  --docker-registry-server-url https://auraboreg.azurecr.io `
  --docker-registry-server-user {username} `
  --docker-registry-server-password {password}
```

### Step 5: View Logs

```bash
az webapp log tail `
  --resource-group fabric-mcp-rg `
  --name fabric-mcp-app
```

## Configuration

All configuration is managed via environment variables in the `.env` file (see `../.env`):

**Required:**
- `ENABLE_MCP_SERVER` - Must be `True`
- `AZURE_OPENAI_URL` - Azure OpenAI endpoint
- `AZURE_AI_MODEL_DEPLOYMENT_NAME` - Model deployment name
- `AZURE_AI_FOUNDRY_URL` - Foundry project endpoint
- `FOUNDRY_FABRIC_RESOURCE_ID` - Fabric connection ID

**Optional:**
- `FOUNDRY_AGENT_NAME` - Agent name (default: `SmartSCMFabricAgenttemplate`)
- `FOUNDRY_SYSTEM_PROMPT_FILE` - System prompt path
- `LOG_LEVEL` - Logging level (default: `INFO`)

## Testing

### Unit Test

```bash
# From project root
python foundry_mcp/tests/test_mcp_server.py
```

This validates:
- Agent initialization
- Azure AI Foundry connectivity
- Fabric data query execution
- Response handling

### Manual Testing (Local)

```bash
# Start server
python foundry_mcp/app/mcp_server.py

# In another terminal, send a test query
# The server accepts MCP protocol messages on stdin
```

### Integration with Claude Desktop

1. Edit `%APPDATA%\Claude\claude_desktop_config.json`
2. Add server configuration
3. Restart Claude Desktop
4. The `fabricdataagentaccount` tool will appear

## Troubleshooting

### Container Won't Start

```bash
# Check logs
az webapp log tail --resource-group fabric-mcp-rg --name fabric-mcp-app

# Verify image
docker run --rm auraboreg.azurecr.io/fabric-mcp-server:latest
```

### Authentication Failed

```bash
# Verify Managed Identity
az webapp identity show --name fabric-mcp-app --resource-group fabric-mcp-rg

# Test locally with Azure CLI
az login
python foundry_mcp/app/mcp_server.py
```

### Query Returns No Results

- Check system prompt file exists and is readable
- Verify Fabric connection ID is correct
- Review Azure AI Foundry project settings

## Monitoring

### Azure Monitor

```bash
# Create Application Insights
az monitor app-insights component create `
  --app fabric-mcp-insights `
  --location eastus `
  --resource-group fabric-mcp-rg
```

### Metrics to Track

- Container startup time
- Query response time
- Error rates
- Token usage

## Updates

```bash
# Build and push new version
docker build -f foundry_mcp/deployment/Dockerfile -t fabric-mcp-server:v1.1.0 .
docker tag fabric-mcp-server:v1.1.0 auraboreg.azurecr.io/fabric-mcp-server:v1.1.0
docker push auraboreg.azurecr.io/fabric-mcp-server:v1.1.0

# Update App Service
az webapp config container set `
  --name fabric-mcp-app `
  --resource-group fabric-mcp-rg `
  --docker-custom-image-name auraboreg.azurecr.io/fabric-mcp-server:v1.1.0
```

## See Also

- `../app/mcp_server.py` - MCP server implementation
- `../.env` - Configuration file
- `../README.md` - Architecture overview
- `Dockerfile` - Container image definition
