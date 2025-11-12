<#
.SYNOPSIS
    Sets up Azure infrastructure for the Fabric Data Agent MCP Server.
    
.DESCRIPTION
    Creates or verifies the following resources in the specified resource group:
    - App Service Plan (Linux)
    - App Service (Web App)
    - System-assigned Managed Identity
    - Role assignment granting access to Azure OpenAI resource
    
    This script is idempotent - running it multiple times is safe.
    
.PARAMETER ResourceGroupName
    The name of the Azure Resource Group. Default: "AURA-Bot"
    
.PARAMETER WebAppName
    The name of the web app. Default: "aura-bot"
    
.PARAMETER AppServicePlanName
    The name of the App Service Plan. Default: "aura-bot-asp"
    
.PARAMETER Location
    Azure region. Default: "eastus2"
    
.PARAMETER Sku
    App Service Plan SKU. Default: "B1"
    
.PARAMETER PurposeTag
    Value for the 'purpose' tag. Default: "MCP Server for Fabric Data Agent"
    
.PARAMETER OwnerTag
    Value for the 'owner' tag. Default: "EmilioArzamendi"
    
.PARAMETER OpenAIResourceName
    Name of the Azure OpenAI resource. Default: "your-resource"
    
.EXAMPLE
    .\Setup-AzureInfra.ps1 -ResourceGroupName "AURA-Bot"
    
.EXAMPLE
    .\Setup-AzureInfra.ps1 -ResourceGroupName "AURA-Bot" -Location "westus2" -Sku "B2"
#>

param(
    [string]$ResourceGroupName = "AURA-Bot",
    [string]$WebAppName = "aura-bot",
    [string]$AppServicePlanName = "aura-bot-asp",
    [string]$Location = "eastus2",
    [string]$Sku = "B1",
    [string]$RegistryName = "auraboreg",
    [string]$RegistrySku = "Basic",
    [string]$PurposeTag = "MCP Server for Fabric Data Agent",
    [string]$OwnerTag = "EmilioArzamendi",
    [string]$OpenAIResourceName = "your-resource"
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

# Check Azure CLI
try {
    $azVersion = az --version 2>$null | Select-Object -First 1
    Write-Success "Azure CLI installed: $azVersion"
} catch {
    Write-Error "Azure CLI not found. Please install it from https://docs.microsoft.com/cli/azure/"
    exit 1
}

# Check authentication
try {
    $account = az account show --query "user.name" -o tsv 2>$null
    Write-Success "Authenticated as: $account"
} catch {
    Write-Error "Not authenticated with Azure CLI. Run: az login"
    exit 1
}

# ============================================================================
# VERIFY RESOURCE GROUP
# ============================================================================

Write-Header "Verifying Resource Group"

$rgExists = az group exists --name $ResourceGroupName -o tsv
if ($rgExists -eq "true") {
    $rgInfo = az group show --name $ResourceGroupName --query "{location:location, id:id}" -o json | ConvertFrom-Json
    Write-Success "Resource Group exists: $ResourceGroupName (location: $($rgInfo.location))"
    $Location = $rgInfo.location
} else {
    Write-Error "Resource Group does not exist: $ResourceGroupName"
    exit 1
}

# ============================================================================
# CHECK/CREATE APP SERVICE PLAN
# ============================================================================

Write-Header "Setting up App Service Plan"

$aspExists = az appservice plan show --name $AppServicePlanName --resource-group $ResourceGroupName -o tsv 2>$null
if ($aspExists) {
    Write-Info "App Service Plan already exists: $AppServicePlanName"
    $aspId = az appservice plan show --name $AppServicePlanName --resource-group $ResourceGroupName --query "id" -o tsv
} else {
    Write-Info "Creating App Service Plan: $AppServicePlanName"
    try {
        $aspResult = az appservice plan create `
            --name $AppServicePlanName `
            --resource-group $ResourceGroupName `
            --sku $Sku `
            --is-linux `
            --location $Location `
            --tags purpose=$PurposeTag owner=$OwnerTag `
            --query "{id:id, name:name, sku:sku.name}" -o json | ConvertFrom-Json
        Write-Success "App Service Plan created: $($aspResult.name) (SKU: $($aspResult.sku))"
        $aspId = $aspResult.id
    } catch {
        Write-Error "Failed to create App Service Plan: $_"
        exit 1
    }
}

# ============================================================================
# CHECK/CREATE WEB APP
# ============================================================================

Write-Header "Setting up Web App"

$webappExists = az webapp show --name $WebAppName --resource-group $ResourceGroupName -o tsv 2>$null
if ($webappExists) {
    Write-Info "Web App already exists: $WebAppName"
    $webappInfo = az webapp show --name $WebAppName --resource-group $ResourceGroupName --query "{id:id, name:name, defaultHostName:defaultHostName}" -o json | ConvertFrom-Json
    Write-Success "Web App: $($webappInfo.name) ($($webappInfo.defaultHostName))"
} else {
    Write-Info "Creating Web App: $WebAppName"
    try {
        $webappResult = az webapp create `
            --name $WebAppName `
            --resource-group $ResourceGroupName `
            --plan $AppServicePlanName `
            --runtime "python:3.11" `
            --tags purpose=$PurposeTag owner=$OwnerTag `
            --query "{id:id, name:name, defaultHostName:defaultHostName}" -o json | ConvertFrom-Json
        Write-Success "Web App created: $($webappResult.name)"
        Write-Info "URL: https://$($webappResult.defaultHostName)"
    } catch {
        Write-Error "Failed to create Web App: $_"
        exit 1
    }
}

# ============================================================================
# ENABLE MANAGED IDENTITY
# ============================================================================

Write-Header "Setting up Managed Identity"

try {
    $identityResult = az webapp identity show --name $WebAppName --resource-group $ResourceGroupName --query "{principalId:principalId, tenantId:tenantId}" -o json 2>$null | ConvertFrom-Json
    if ($identityResult.principalId) {
        Write-Success "Managed Identity already enabled"
        Write-Info "Principal ID: $($identityResult.principalId)"
        $principalId = $identityResult.principalId
    } else {
        throw "Managed identity exists but principal ID not found"
    }
} catch {
    Write-Info "Enabling system-assigned Managed Identity..."
    try {
        $identityResult = az webapp identity assign `
            --name $WebAppName `
            --resource-group $ResourceGroupName `
            --query "{principalId:principalId, tenantId:tenantId}" -o json | ConvertFrom-Json
        Write-Success "Managed Identity enabled"
        Write-Info "Principal ID: $($identityResult.principalId)"
        $principalId = $identityResult.principalId
    } catch {
        Write-Error "Failed to enable Managed Identity: $_"
        exit 1
    }
}

# ============================================================================
# GET OPENAI RESOURCE ID
# ============================================================================

Write-Header "Getting Azure OpenAI Resource"

try {
    $openAIResourceId = az cognitiveservices account show `
        --name $OpenAIResourceName `
        --resource-group $ResourceGroupName `
        --query "id" -o tsv
    if (-not $openAIResourceId) {
        throw "Resource not found"
    }
    Write-Success "Azure OpenAI resource found: $OpenAIResourceName"
    Write-Info "Resource ID: $openAIResourceId"
} catch {
    Write-Error "Failed to find Azure OpenAI resource: $OpenAIResourceName"
    exit 1
}

# ============================================================================
# CREATE RBAC ROLE ASSIGNMENT
# ============================================================================

Write-Header "Setting up RBAC Role Assignment"

try {
    # Check if role assignment already exists
    $existingRole = az role assignment list `
        --assignee $principalId `
        --scope $openAIResourceId `
        --query "[?roleDefinitionName=='Cognitive Services OpenAI User']" -o json | ConvertFrom-Json
    
    if ($existingRole -and $existingRole.Count -gt 0) {
        Write-Success "Role assignment already exists"
        Write-Info "Role: Cognitive Services OpenAI User"
    } else {
        Write-Info "Creating role assignment..."
        $roleResult = az role assignment create `
            --assignee-object-id $principalId `
            --assignee-principal-type ServicePrincipal `
            --role "Cognitive Services OpenAI User" `
            --scope $openAIResourceId `
            --query "{principalId:principalId, roleDefinitionName:roleDefinitionName}" -o json | ConvertFrom-Json
        Write-Success "Role assignment created"
        Write-Info "Role: Cognitive Services OpenAI User"
    }
} catch {
    Write-Error "Failed to create role assignment: $_"
    exit 1
}

# ============================================================================
# CHECK/CREATE CONTAINER REGISTRY
# ============================================================================

Write-Header "Setting up Container Registry"

$acrExists = az acr show --name $RegistryName --resource-group $ResourceGroupName -o tsv 2>$null
if ($acrExists) {
    Write-Info "Container Registry already exists: $RegistryName"
    $acrInfo = az acr show --name $RegistryName --resource-group $ResourceGroupName --query "{name:name, loginServer:loginServer, id:id}" -o json | ConvertFrom-Json
    Write-Success "Registry: $($acrInfo.name) ($($acrInfo.loginServer))"
    $acrId = $acrInfo.id
} else {
    Write-Info "Creating Container Registry: $RegistryName"
    try {
        $acrResult = az acr create `
            --resource-group $ResourceGroupName `
            --name $RegistryName `
            --sku $RegistrySku `
            --location $Location `
            --tags purpose=$PurposeTag owner=$OwnerTag `
            --admin-enabled true `
            --query "{name:name, loginServer:loginServer, id:id}" -o json | ConvertFrom-Json
        Write-Success "Container Registry created: $($acrResult.name)"
        Write-Info "Login Server: $($acrResult.loginServer)"
        $acrId = $acrResult.id
    } catch {
        Write-Error "Failed to create Container Registry: $_"
        exit 1
    }
}

# ============================================================================
# GRANT WEBAPP ACCESS TO ACR
# ============================================================================

Write-Header "Granting Web App Access to Container Registry"

try {
    # Check if role assignment already exists
    $existingAcrRole = az role assignment list `
        --assignee $principalId `
        --scope $acrId `
        --query "[?roleDefinitionName=='AcrPull']" -o json | ConvertFrom-Json
    
    if ($existingAcrRole -and $existingAcrRole.Count -gt 0) {
        Write-Success "Web App already has AcrPull role"
    } else {
        Write-Info "Creating AcrPull role assignment..."
        $acrRoleResult = az role assignment create `
            --assignee-object-id $principalId `
            --assignee-principal-type ServicePrincipal `
            --role "AcrPull" `
            --scope $acrId
        Write-Success "Web App granted AcrPull access to Container Registry"
    }
} catch {
    Write-Error "Failed to grant ACR access: $_"
    exit 1
}

# ============================================================================
# FINAL SUMMARY
# ============================================================================

Write-Header "Infrastructure Setup Complete"

Write-Success "All resources are ready!"
Write-Host ""
Write-Host "Summary:" -ForegroundColor Cyan
Write-Host "  Resource Group:     $ResourceGroupName" -ForegroundColor Cyan
Write-Host "  App Service Plan:   $AppServicePlanName (SKU: $Sku)" -ForegroundColor Cyan
Write-Host "  Web App:            $WebAppName" -ForegroundColor Cyan
Write-Host "  Container Registry: $RegistryName (SKU: $RegistrySku)" -ForegroundColor Cyan
Write-Host "  Location:           $Location" -ForegroundColor Cyan
Write-Host "  Managed Identity:   Enabled" -ForegroundColor Cyan
Write-Host "  OpenAI Access:      Configured (Cognitive Services OpenAI User)" -ForegroundColor Cyan
Write-Host "  ACR Access:         Configured (AcrPull)" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Run Deploy-ToWebApp.ps1 to deploy the application" -ForegroundColor Yellow
Write-Host "  2. The script will build, push to ACR, and deploy to the web app" -ForegroundColor Yellow
Write-Host "  3. Monitor deployment with: az webapp log tail --name $WebAppName --resource-group $ResourceGroupName" -ForegroundColor Yellow
