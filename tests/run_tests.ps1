#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Setup and run service tests for Fabric Data Agent

.DESCRIPTION
    Configures environment variables and runs the standalone service test
    Uses your Fabric SQL endpoint and Azure Storage account

.EXAMPLE
    .\tests\run_tests.ps1
#>

# ============================================================================
# Configuration - MODIFY THESE VALUES
# ============================================================================

# Your Fabric SQL endpoint and database
$FabricSqlServer = "tcp:dwqurwscuuxern3c5uxx3n3hgq-apvmkjmaa6xe3knachpdztfq3e.datawarehouse.fabric.microsoft.com,1433"
$FabricSqlDatabase = "lh_aura_001"

# Your Azure Storage account (for CSV exports)
$StorageAccount = "aurabotstorage6572"
$StorageContainer = "fabric-exports"  # Will be created if it doesn't exist

# ============================================================================
# Setup
# ============================================================================

Write-Host "╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║    FABRIC DATA AGENT - SERVICE TEST SETUP                      ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan

Write-Host "`n📋 Configuration:" -ForegroundColor Yellow
Write-Host "   Fabric SQL Server:     $FabricSqlServer"
Write-Host "   Fabric SQL Database:   $FabricSqlDatabase"
Write-Host "   Storage Account:       $StorageAccount"
Write-Host "   Storage Container:     $StorageContainer"

# Check Azure CLI authentication
Write-Host "`n🔐 Checking Azure CLI authentication..." -ForegroundColor Yellow
try {
    $null = az account show --query name -o tsv 2>$null
    Write-Host "✅ Authenticated to Azure CLI" -ForegroundColor Green
} catch {
    Write-Host "❌ Not authenticated to Azure CLI" -ForegroundColor Red
    Write-Host "   Run: az login" -ForegroundColor Yellow
    exit 1
}

# Set environment variables for the test
Write-Host "`n📝 Setting environment variables..." -ForegroundColor Yellow
$env:FABRIC_SQL_SERVER = $FabricSqlServer
$env:FABRIC_SQL_DATABASE = $FabricSqlDatabase
$env:AZURE_STORAGE_ACCOUNT = $StorageAccount
$env:AZURE_STORAGE_CONTAINER = $StorageContainer

Write-Host "   ✓ FABRIC_SQL_SERVER"
Write-Host "   ✓ FABRIC_SQL_DATABASE"
Write-Host "   ✓ AZURE_STORAGE_ACCOUNT"
Write-Host "   ✓ AZURE_STORAGE_CONTAINER"

# ============================================================================
# Run Tests
# ============================================================================

Write-Host "`n🚀 Running tests..." -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray

# Get the project root
$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Write-Host "Project Root: $projectRoot" -ForegroundColor Gray

# Run the test script
python "$projectRoot\tests\test_services_standalone.py"

$exitCode = $LASTEXITCODE

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray

if ($exitCode -eq 0) {
    Write-Host "`n✅ All tests passed!" -ForegroundColor Green
} else {
    Write-Host "`n❌ Tests failed with exit code: $exitCode" -ForegroundColor Red
}

exit $exitCode
