# Add Managed Identity to Fabric Workspace
# This script adds the Azure Web App's managed identity to the Fabric workspace

$WORKSPACE_ID = "25c5ea03-0780-4dae-a9a0-11de3cccb0d9"
$MSI_OBJECT_ID = "869185a6-0192-47dc-85db-2fec26a3d0c4"
$MSI_NAME = "mcp-aura"

Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Add Managed Identity to Fabric Workspace" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "Workspace ID: $WORKSPACE_ID" -ForegroundColor Yellow
Write-Host "MSI Object ID: $MSI_OBJECT_ID" -ForegroundColor Yellow
Write-Host "MSI Name: $MSI_NAME" -ForegroundColor Yellow
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "⚠️  MANUAL STEPS REQUIRED:" -ForegroundColor Red
Write-Host ""
Write-Host "Unfortunately, Azure CLI doesn't directly support adding members to Fabric workspaces." -ForegroundColor Yellow
Write-Host "You need to add the managed identity through the Fabric Portal:" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. Go to: https://app.fabric.microsoft.com/" -ForegroundColor White
Write-Host ""
Write-Host "2. Navigate to the workspace (ID: $WORKSPACE_ID)" -ForegroundColor White
Write-Host ""
Write-Host "3. Click 'Manage access' or 'Workspace settings'" -ForegroundColor White
Write-Host ""
Write-Host "4. Click 'Add people or groups'" -ForegroundColor White
Write-Host ""
Write-Host "5. Search for: '$MSI_NAME' (the managed identity)" -ForegroundColor White
Write-Host "   - It should appear as an Enterprise Application" -ForegroundColor Gray
Write-Host "   - Object ID: $MSI_OBJECT_ID" -ForegroundColor Gray
Write-Host ""
Write-Host "6. Assign role: 'Contributor' or 'Member'" -ForegroundColor White
Write-Host "   - Contributor: Can read and execute data agents" -ForegroundColor Gray
Write-Host "   - Member: Full access to workspace items" -ForegroundColor Gray
Write-Host ""
Write-Host "7. Click 'Add' to save" -ForegroundColor White
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "Alternative: Use PowerBI/Fabric REST API" -ForegroundColor Yellow
Write-Host ""
Write-Host "If you want to automate this, you can use the Fabric REST API:" -ForegroundColor Gray
Write-Host ""
Write-Host "POST https://api.fabric.microsoft.com/v1/workspaces/$WORKSPACE_ID/users" -ForegroundColor Gray
Write-Host "Body:" -ForegroundColor Gray
Write-Host @"
{
  "identifier": "$MSI_OBJECT_ID",
  "groupUserAccessRight": "Member",
  "principalType": "App"
}
"@ -ForegroundColor Gray
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "After adding the MSI to the workspace, test again with:" -ForegroundColor Green
Write-Host "  python test_tool_works.py azure" -ForegroundColor White
Write-Host ""
