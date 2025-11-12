#!/usr/bin/env pwsh
#
# deploy.ps1 - Rebuild, Push, and Restart Fabric MCP Server in Azure
#
# Usage: .\deploy.ps1
#

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Fabric MCP Server - Azure Deployment Script" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

$IMAGE_NAME = "auraboreg.azurecr.io/fabric-mcp:latest"
$WEB_APP_NAME = "mcp-aura"
$RESOURCE_GROUP = "AURA-Bot"

# Step 1: Build Docker image
Write-Host "🔨 [1/4] Building Docker image..." -ForegroundColor Yellow
docker build -f foundry_mcp/deployment/Dockerfile -t $IMAGE_NAME .
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Docker build failed!" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Build complete" -ForegroundColor Green
Write-Host ""

# Step 2: Push to Azure Container Registry
Write-Host "📤 [2/4] Pushing to Azure Container Registry..." -ForegroundColor Yellow
docker push $IMAGE_NAME
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Docker push failed!" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Push complete" -ForegroundColor Green
Write-Host ""

# Step 3: Restart Azure Web App
Write-Host "🔄 [3/4] Restarting Azure Web App..." -ForegroundColor Yellow
az webapp restart --name $WEB_APP_NAME --resource-group $RESOURCE_GROUP
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Web App restart failed!" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Web App restarted" -ForegroundColor Green
Write-Host ""

# Step 4: Wait for startup
Write-Host "⏳ [4/4] Waiting for Web App to warm up (30 seconds)..." -ForegroundColor Yellow
Start-Sleep -Seconds 30
Write-Host "✅ Ready for testing" -ForegroundColor Green
Write-Host ""

# Summary
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Deployment Complete!" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "Test locally:  python test_tool_works.py" -ForegroundColor White
Write-Host "Test Azure:    python test_tool_works.py azure" -ForegroundColor White
Write-Host ""
Write-Host "Azure endpoint: https://mcp-aura.azurewebsites.net/mcp" -ForegroundColor White
Write-Host ""
