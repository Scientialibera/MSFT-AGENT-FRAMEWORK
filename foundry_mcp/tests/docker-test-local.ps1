#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Docker MCP Server Local Testing Script
    
.DESCRIPTION
    Runs the MCP server in Docker container locally for testing before Azure deployment.
    
.EXAMPLE
    .\docker-test-local.ps1
#>

Write-Host "`n" + "="*80 -ForegroundColor Cyan
Write-Host "Docker MCP Server - Local Test Setup" -ForegroundColor Cyan
Write-Host "="*80 -ForegroundColor Cyan

# Check if .env exists
if (-not (Test-Path ".env")) {
    Write-Host "`n[ERROR] .env file not found!" -ForegroundColor Red
    Write-Host "Copy .env.example to .env and configure your settings first" -ForegroundColor Yellow
    exit 1
}

Write-Host "`n[Step 1] Loading environment variables..." -ForegroundColor Cyan
$envVars = @{}
Get-Content ".env" | ForEach-Object {
    if ($_ -match "^\s*([^=#]+)=(.*)$") {
        $key = $matches[1].Trim()
        $value = $matches[2].Trim()
        if ($key -and $value) {
            $envVars[$key] = $value
        }
    }
}
Write-Host "[OK] Loaded $(($envVars.Keys).Count) environment variables" -ForegroundColor Green

# Check Docker
Write-Host "`n[Step 2] Checking Docker..." -ForegroundColor Cyan
$dockerCheck = docker ps 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Docker daemon is not running!" -ForegroundColor Red
    Write-Host "Please start Docker Desktop and try again" -ForegroundColor Yellow
    exit 1
}
Write-Host "[OK] Docker is running" -ForegroundColor Green

# Build image
Write-Host "`n[Step 3] Building Docker image..." -ForegroundColor Cyan
Write-Host "Image: fabric-mcp-server:latest" -ForegroundColor Blue
Write-Host "Dockerfile: deployment/Dockerfile" -ForegroundColor Blue
Write-Host "(This may take 2-3 minutes on first build...)" -ForegroundColor Yellow

$buildOutput = docker build -f deployment/Dockerfile -t fabric-mcp-server:latest . 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Docker build failed!" -ForegroundColor Red
    Write-Host $buildOutput -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Docker image built successfully" -ForegroundColor Green

# Run container
Write-Host "`n[Step 4] Starting MCP server container..." -ForegroundColor Cyan

$containerName = "fabric-mcp-docker"
$containerCheck = docker ps --filter "name=$containerName" --format "{{.ID}}" 2>&1
if ($containerCheck) {
    Write-Host "[INFO] Stopping existing container..." -ForegroundColor Yellow
    docker stop $containerName | Out-Null
}

Write-Host "Container name: $containerName" -ForegroundColor Blue
Write-Host "Running: python tests/mcp_server.py" -ForegroundColor Blue

$dockerRun = docker run -it --rm `
    --name $containerName `
    -e ENABLE_MCP_SERVER=true `
    -e AZURE_OPENAI_ENDPOINT=$($envVars["AZURE_OPENAI_ENDPOINT"]) `
    -e AZURE_OPENAI_CHAT_DEPLOYMENT=$($envVars["AZURE_OPENAI_CHAT_DEPLOYMENT"]) `
    -e TENANT_ID=$($envVars["TENANT_ID"]) `
    -e DATA_AGENT_URL=$($envVars["DATA_AGENT_URL"]) `
    -p 8000:8000 `
    fabric-mcp-server:latest

Write-Host "[CONTAINER STOPPED]" -ForegroundColor Yellow
Write-Host "`nTo view container logs in another terminal:" -ForegroundColor Cyan
Write-Host "  docker logs -f $containerName" -ForegroundColor Blue
