<#
.SYNOPSIS
    Deploys the Fabric Data Agent MCP Server to Azure App Service.
    
.DESCRIPTION
    This script performs the following steps:
    1. Builds a Docker image from the Dockerfile
    2. Pushes the image to Azure Container Registry (ACR)
    3. Configures the webapp to use the container image
    4. Sets required environment variables in the webapp
    5. Restarts the webapp
    
    The script is idempotent - running it multiple times is safe.
    
.PARAMETER ResourceGroupName
    The name of the Azure Resource Group. Default: "AURA-Bot"
    
.PARAMETER WebAppName
    The name of the web app. Default: "aura-bot"
    
.PARAMETER RegistryName
    The name of the Azure Container Registry. Default: "auraboreg"
    
.PARAMETER ImageName
    The name of the Docker image. Default: "mcp-server"
    
.PARAMETER ImageTag
    The Docker image tag (version). Default: "latest"
    
.PARAMETER AzureOpenAIEndpoint
    The Azure OpenAI endpoint URL (from .env or manually set)
    
.PARAMETER AzureOpenAIChatDeployment
    The Azure OpenAI chat deployment name (from .env or manually set)
    
.PARAMETER TenantId
    The Tenant ID for authentication (from .env or manually set)
    
.PARAMETER DataAgentUrl
    The Fabric Data Agent URL (from .env or manually set)
    
.EXAMPLE
    .\Deploy-ToWebApp.ps1 -ResourceGroupName "AURA-Bot" -RegistryName "auraboreg"
    
.EXAMPLE
    .\Deploy-ToWebApp.ps1 `
        -ResourceGroupName "AURA-Bot" `
        -RegistryName "auraboreg" `
        -AzureOpenAIEndpoint "https://your-resource.openai.azure.com/" `
        -AzureOpenAIChatDeployment "gpt-4o" `
        -TenantId "74c77be6-1ad3-4957-a4f2-94028372d7d6" `
        -DataAgentUrl "https://api.fabric.microsoft.com/v1/workspaces/..."
#>

param(
    [string]$ResourceGroupName = "AURA-Bot",
    [string]$WebAppName = "aura-bot",
    [string]$RegistryName = "auraboreg",
    [string]$ImageName = "mcp-server",
    [string]$ImageTag = "latest",
    [string]$AzureOpenAIEndpoint,
    [string]$AzureOpenAIChatDeployment,
    [string]$TenantId,
    [string]$DataAgentUrl
)

$ErrorActionPreference = "Stop"

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

function Write-Header {
    param([string]$Message)
    Write-Host "`n" -ForegroundColor Cyan
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
    Write-Host "  $Message" -ForegroundColor Cyan
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Write-Info {
    param([string]$Message)
    Write-Host "ℹ $Message" -ForegroundColor Blue
}

function Write-Warning {
    param([string]$Message)
    Write-Host "⚠ $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "✗ $Message" -ForegroundColor Red
}

# ============================================================================
# VERIFY PREREQUISITES
# ============================================================================

Write-Header "Verifying Prerequisites"

# Check Docker
try {
    $dockerVersion = docker --version 2>$null
    Write-Success "Docker installed: $dockerVersion"
} catch {
    Write-Error "Docker not found. Please install it from https://www.docker.com/products/docker-desktop"
    exit 1
}

# Check Azure CLI
try {
    $azVersion = az --version 2>$null | Select-Object -First 1
    Write-Success "Azure CLI installed"
} catch {
    Write-Error "Azure CLI not found. Please install it."
    exit 1
}

# ============================================================================
# VERIFY ENVIRONMENT VARIABLES
# ============================================================================

Write-Header "Verifying Environment Variables"

if (-not $AzureOpenAIEndpoint -or -not $AzureOpenAIChatDeployment -or -not $TenantId -or -not $DataAgentUrl) {
    Write-Warning "Some environment variables are missing. Attempting to load from .env file..."
    
    $envFile = ".env"
    if (Test-Path $envFile) {
        Write-Info "Loading from .env file..."
        Get-Content $envFile | ForEach-Object {
            if ($_ -match "^\s*([^=]+)=(.*)$") {
                $key = $matches[1].Trim()
                $value = $matches[2].Trim()
                
                if ($key -eq "AZURE_OPENAI_ENDPOINT") { $AzureOpenAIEndpoint = $value }
                elseif ($key -eq "AZURE_OPENAI_CHAT_DEPLOYMENT") { $AzureOpenAIChatDeployment = $value }
                elseif ($key -eq "TENANT_ID") { $TenantId = $value }
                elseif ($key -eq "DATA_AGENT_URL") { $DataAgentUrl = $value }
            }
        }
    }
}

if (-not $AzureOpenAIEndpoint) {
    Write-Error "AZURE_OPENAI_ENDPOINT not set. Please provide via parameter or .env file"
    exit 1
}
if (-not $AzureOpenAIChatDeployment) {
    Write-Error "AZURE_OPENAI_CHAT_DEPLOYMENT not set. Please provide via parameter or .env file"
    exit 1
}
if (-not $TenantId) {
    Write-Error "TENANT_ID not set. Please provide via parameter or .env file"
    exit 1
}
if (-not $DataAgentUrl) {
    Write-Error "DATA_AGENT_URL not set. Please provide via parameter or .env file"
    exit 1
}

Write-Success "All required environment variables are set"

# ============================================================================
# GET REGISTRY CREDENTIALS
# ============================================================================

Write-Header "Getting Registry Credentials"

try {
    $registryInfo = az acr show --name $RegistryName --resource-group $ResourceGroupName --query "{loginServer:loginServer, id:id}" -o json | ConvertFrom-Json
    $loginServer = $registryInfo.loginServer
    Write-Success "Registry found: $loginServer"
} catch {
    Write-Error "Failed to find registry: $RegistryName"
    exit 1
}

# ============================================================================
# BUILD DOCKER IMAGE
# ============================================================================

Write-Header "Building Docker Image"

$imageFullName = "$loginServer/$ImageName`:$ImageTag"
Write-Info "Building image: $imageFullName"

try {
    docker build -t $imageFullName -t "$loginServer/$ImageName`:latest" .
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Docker image built successfully"
    } else {
        throw "Docker build failed with exit code $LASTEXITCODE"
    }
} catch {
    Write-Error "Docker build failed: $_"
    exit 1
}

# ============================================================================
# LOGIN TO ACR AND PUSH IMAGE
# ============================================================================

Write-Header "Pushing Image to ACR"

try {
    Write-Info "Authenticating with ACR..."
    az acr login --name $RegistryName
    Write-Success "Authenticated with ACR"
    
    Write-Info "Pushing image to ACR: $imageFullName"
    docker push $imageFullName
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Image pushed successfully"
    } else {
        throw "Push failed with exit code $LASTEXITCODE"
    }
} catch {
    Write-Error "Failed to push image: $_"
    exit 1
}

# ============================================================================
# CONFIGURE WEBAPP FOR CONTAINER DEPLOYMENT
# ============================================================================

Write-Header "Configuring Web App"

try {
    # Get ACR admin credentials
    Write-Info "Getting ACR credentials..."
    $acrCredentials = az acr credential show --name $RegistryName --resource-group $ResourceGroupName --query "{username:username, password:passwords[0].value}" -o json | ConvertFrom-Json
    $username = $acrCredentials.username
    $password = $acrCredentials.password
    
    Write-Success "Retrieved ACR credentials"
} catch {
    Write-Error "Failed to get ACR credentials: $_"
    exit 1
}

try {
    # Configure webapp to use container
    Write-Info "Configuring webapp to use container image..."
    az webapp config container set `
        --name $WebAppName `
        --resource-group $ResourceGroupName `
        --docker-custom-image-name $imageFullName `
        --docker-registry-server-url "https://$loginServer" `
        --docker-registry-server-user $username `
        --docker-registry-server-password $password
    
    Write-Success "Web app configured for container deployment"
} catch {
    Write-Error "Failed to configure web app: $_"
    exit 1
}

# ============================================================================
# SET ENVIRONMENT VARIABLES (APP SETTINGS)
# ============================================================================

Write-Header "Setting Environment Variables"

try {
    Write-Info "Setting app settings..."
    az webapp config appsettings set `
        --name $WebAppName `
        --resource-group $ResourceGroupName `
        --settings `
            "AZURE_OPENAI_ENDPOINT=$AzureOpenAIEndpoint" `
            "AZURE_OPENAI_CHAT_DEPLOYMENT=$AzureOpenAIChatDeployment" `
            "TENANT_ID=$TenantId" `
            "DATA_AGENT_URL=$DataAgentUrl" `
            "ENABLE_MCP_SERVER=true" `
            "WEBSITES_PORT=8000"
    
    Write-Success "Environment variables set"
} catch {
    Write-Error "Failed to set environment variables: $_"
    exit 1
}

# ============================================================================
# RESTART WEBAPP
# ============================================================================

Write-Header "Restarting Web App"

try {
    Write-Info "Restarting web app..."
    az webapp restart --name $WebAppName --resource-group $ResourceGroupName
    Write-Success "Web app restarted"
} catch {
    Write-Error "Failed to restart web app: $_"
    exit 1
}

# ============================================================================
# FINAL SUMMARY
# ============================================================================

Write-Header "Deployment Complete"

Write-Success "Your MCP Server is deployed!"
Write-Host ""
Write-Host "Summary:" -ForegroundColor Cyan
Write-Host "  Resource Group:   $ResourceGroupName" -ForegroundColor Cyan
Write-Host "  Web App:          $WebAppName" -ForegroundColor Cyan
Write-Host "  Registry:         $RegistryName" -ForegroundColor Cyan
Write-Host "  Image:            $ImageName`:$ImageTag" -ForegroundColor Cyan
Write-Host "  Full URL:         https://$(az webapp show --name $WebAppName --resource-group $ResourceGroupName --query defaultHostName -o tsv)" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Monitor deployment: az webapp log tail --name $WebAppName --resource-group $ResourceGroupName" -ForegroundColor Yellow
Write-Host "  2. Check container logs for startup messages" -ForegroundColor Yellow
Write-Host "  3. The MCP server is available to MCP clients (VS Code, Claude, etc.)" -ForegroundColor Yellow
Write-Host ""
Write-Host "To view logs:" -ForegroundColor Cyan
Write-Host "  az webapp log tail --name $WebAppName --resource-group $ResourceGroupName --provider docker" -ForegroundColor Cyan
