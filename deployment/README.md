# Deployment - Fabric Data Agent MCP Server

This folder contains all files and scripts needed to deploy the Fabric Data Agent MCP Server to Azure.

## Files

| File | Purpose |
|------|---------|
| **Setup-AzureInfra.ps1** | Idempotent PowerShell script to create Azure infrastructure (App Service Plan, Web App, Container Registry, Managed Identity, RBAC) |
| **Deploy-ToWebApp.ps1** | Idempotent PowerShell script to build, push Docker image to ACR, and deploy to the web app |
| **Dockerfile** | Multi-stage Docker build for the MCP server container |
| **.dockerignore** | Files to exclude from Docker image |
| **connection.yml** | AI Foundry OpenAI connection configuration |
| **README.md** | This file |

## Quick Start

### Prerequisites

- **Azure CLI** - [Install](https://docs.microsoft.com/cli/azure/install-azure-cli)
- **Docker Desktop** - [Install](https://www.docker.com/products/docker-desktop)
- **PowerShell 7+** - [Install](https://github.com/PowerShell/PowerShell/releases)
- **Azure Subscription** with AURA-Bot resource group

### Step 1: Setup Infrastructure (One-time)

Run from the **parent directory** (where your `.env` file is):

```powershell
.\deployment\Setup-AzureInfra.ps1 -ResourceGroupName "AURA-Bot"
```

This creates:
-  App Service Plan (Linux, B1 SKU)
-  Web App (Python 3.11)
-  Container Registry (Basic SKU)
-  Managed Identity
-  RBAC role assignments

**Idempotent**: Safe to run multiple times

### Step 2: Deploy Application

Run from the **parent directory** (where your `.env` file is):

```powershell
.\deployment\Deploy-ToWebApp.ps1 -ResourceGroupName "AURA-Bot"
```

This:
1.  Builds Docker image from `Dockerfile`
2.  Pushes image to Azure Container Registry
3.  Configures web app with container settings
4.  Sets environment variables from `.env`
5.  Restarts web app

**Auto-loads environment variables from `.env`:**
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_CHAT_DEPLOYMENT`
- `TENANT_ID`
- `DATA_AGENT_URL`

## Usage Examples

### Basic deployment
```powershell
# From parent directory
.\deployment\Setup-AzureInfra.ps1
.\deployment\Deploy-ToWebApp.ps1
```

### Custom resource group
```powershell
.\deployment\Setup-AzureInfra.ps1 -ResourceGroupName "MyRG"
.\deployment\Deploy-ToWebApp.ps1 -ResourceGroupName "MyRG"
```

### Different Azure region
```powershell
.\deployment\Setup-AzureInfra.ps1 -Location "westus2" -ResourceGroupName "AURA-Bot"
```

### Larger App Service Plan
```powershell
.\deployment\Setup-AzureInfra.ps1 -Sku "B2" -ResourceGroupName "AURA-Bot"
```

### Manual environment variables (optional)
```powershell
.\deployment\Deploy-ToWebApp.ps1 `
    -ResourceGroupName "AURA-Bot" `
    -AzureOpenAIEndpoint "https://your-resource.openai.azure.com/" `
    -AzureOpenAIChatDeployment "gpt-4o" `
    -TenantId "74c77be6-1ad3-4957-a4f2-94028372d7d6" `
    -DataAgentUrl "https://api.fabric.microsoft.com/v1/workspaces/..."
```

## Monitoring

### View real-time logs
```bash
az webapp log tail --name aura-bot --resource-group AURA-Bot
```

### View app status
```bash
az webapp show --name aura-bot --resource-group AURA-Bot --query "{name:name, state:state, url:defaultHostName}"
```

### View environment variables
```bash
az webapp config appsettings list --name aura-bot --resource-group AURA-Bot -o table
```

## Architecture

```
Local Machine
    ↓
    → Setup-AzureInfra.ps1 (creates Azure resources)
    
    → Deploy-ToWebApp.ps1
        → docker build (builds image)
        → az acr login (authenticates to ACR)
        → docker push (pushes to auraboreg.azurecr.io)
        → az webapp deploy (configures app service)
                    ↓
            Azure App Service
                    ↓
            Container Instance
            (tests/mcp_server.py)
                    ↓
            Azure OpenAI (your-resource)
            (via Managed Identity, no keys!)
```

## Key Features

 **Fully Idempotent** - Can run scripts multiple times safely
 **No API Keys** - Uses Managed Identity for Azure OpenAI
 **Policy Compliant** - Applies required tags (purpose, owner)
 **Role-Based Access** - Webapp has only necessary permissions
 **Environment Variables** - Auto-loaded from `.env`
 **Multi-Stage Build** - Optimized Docker image

## Troubleshooting

### Docker image won't build
```bash
# Check Dockerfile exists
ls deployment/Dockerfile

# Check requirements.txt exists in parent
ls requirements.txt

# Try building manually to see errors
docker build -f deployment/Dockerfile -t test:latest .
```

### Can't push to ACR
```bash
# Verify ACR exists
az acr show --name auraboreg --resource-group AURA-Bot

# Try manual login
az acr login --name auraboreg

# Check credentials
az acr credential show --name auraboreg --resource-group AURA-Bot
```

### Container won't start
```bash
# Check logs
az webapp log tail --name aura-bot --resource-group AURA-Bot

# Common issues:
# 1. Missing environment variables
# 2. Port mismatch (should be 8000)
# 3. Module import errors (check requirements.txt)
```

## Files Structure

```
FABRIC-DATA-AGENT/
 deployment/              ← You are here
    Setup-AzureInfra.ps1
    Deploy-ToWebApp.ps1
    Dockerfile
    .dockerignore
    connection.yml
    README.md
 .env                     ← Required (not in this folder)
 requirements.txt
 tests/
    mcp_server.py
 src/
     orchestrator/
     fabric_data/
```

## Related Documentation

- See `DEPLOYMENT.md` in parent directory for full deployment guide
- See `QUICK_REFERENCE.md` in parent directory for common Azure CLI commands
- See `DEPLOYMENT_SUMMARY.md` in parent directory for infrastructure overview

## Support

For issues:
1. Check logs: `az webapp log tail --name aura-bot --resource-group AURA-Bot`
2. Verify resources exist: `az resource list --resource-group AURA-Bot -o table`
3. Check managed identity: `az webapp identity show --name aura-bot --resource-group AURA-Bot`

---

**Ready to deploy? Start with:**
```powershell
.\Setup-AzureInfra.ps1
.\Deploy-ToWebApp.ps1
```
