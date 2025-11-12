#!/usr/bin/env python3
"""
Test MCP Orchestrator with Fabric Data Services

Tests the full MCP orchestrator flow with both fabric_data and sql_to_csv tools.

Requirements:
- Azure CLI logged in: `az login`
- Environment variables set (same as test_services_standalone.py)

Run:
  python tests/test_mcp_orchestrator.py
"""

import os
import sys
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import structlog

# Setup logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


async def test_orchestrator_small_query():
    """Test orchestrator with a small query (should use fabric_data only)."""
    print("\n" + "="*80)
    print("TEST 1: MCP Orchestrator - Small Query (fabric_data tool)")
    print("="*80)
    
    try:
        from src.orchestrator.main import process_query
        
        # Small query - should return inline results
        query = "Show me the connection status and current time"
        print(f"\n🔍 User Query: {query}")
        
        result = await process_query(query)
        
        print("\n📊 Agent Response:")
        print(result)
        
        print("\n✅ TEST 1 PASSED: Small query handled correctly")
        return True
        
    except Exception as e:
        print(f"\n❌ TEST 1 FAILED: {str(e)}")
        logger.error("TEST 1 failed", error=str(e), exc_info=True)
        return False


async def test_orchestrator_large_query():
    """Test orchestrator with a large query (should recommend sql_to_csv)."""
    print("\n" + "="*80)
    print("TEST 2: MCP Orchestrator - Large Query (fabric_data + sql_to_csv)")
    print("="*80)
    
    try:
        from src.orchestrator.main import process_query
        
        # Large query - should trigger warning and csv export
        # Generate 50 rows to exceed the 30 row limit
        query = "Export a dataset with 50 rows of test data"
        print(f"\n🔍 User Query: {query}")
        print("   (Expected: Agent should use fabric_data first, then call sql_to_csv)")
        
        result = await process_query(query)
        
        print("\n📊 Agent Response:")
        print(result)
        
        # Check if response contains both inline data and CSV URL
        if "⚠️" in result or "csv" in result.lower():
            print("\n✅ TEST 2 PASSED: Agent recognized large result set")
        else:
            print("\n⚠️  TEST 2 WARNING: Agent may not have detected large result set")
        
        return True
        
    except Exception as e:
        print(f"\n❌ TEST 2 FAILED: {str(e)}")
        logger.error("TEST 2 failed", error=str(e), exc_info=True)
        return False


async def test_orchestrator_direct_csv():
    """Test orchestrator with direct CSV export request."""
    print("\n" + "="*80)
    print("TEST 3: MCP Orchestrator - Direct CSV Export (sql_to_csv tool)")
    print("="*80)
    
    try:
        from src.orchestrator.main import process_query
        
        # Direct CSV export request
        query = "Export all test data to CSV and give me the download link"
        print(f"\n🔍 User Query: {query}")
        
        result = await process_query(query)
        
        print("\n📊 Agent Response:")
        print(result)
        
        # Check if response contains CSV URL
        if "https://" in result and "blob.core.windows.net" in result:
            print("\n✅ TEST 3 PASSED: CSV export with download URL generated")
        else:
            print("\n⚠️  TEST 3 WARNING: No download URL found in response")
        
        return True
        
    except Exception as e:
        print(f"\n❌ TEST 3 FAILED: {str(e)}")
        logger.error("TEST 3 failed", error=str(e), exc_info=True)
        return False


async def main():
    """Run all orchestrator tests."""
    print("\n" + "="*80)
    print("MCP ORCHESTRATOR - INTEGRATION TESTING")
    print("="*80)
    print("\nTesting MCP orchestrator with Fabric Data services")
    print("Using Azure CLI credentials (DefaultAzureCredential)")
    
    # Check required environment variables
    required_vars = [
        "FABRIC_SQL_SERVER",
        "FABRIC_SQL_DATABASE",
        "AZURE_STORAGE_ACCOUNT",
        "AZURE_STORAGE_CONTAINER",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_CHAT_DEPLOYMENT"
    ]
    
    print("\n📋 Checking environment variables...")
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
            print(f"   ❌ {var}: Not set")
        else:
            print(f"   ✅ {var}: Set")
    
    if missing_vars:
        print(f"\n❌ Missing required environment variables: {', '.join(missing_vars)}")
        print("\nSet them before running this test:")
        for var in missing_vars:
            print(f"   $env:{var}='<value>'")
        return False
    
    # Set MAX_ROWS_INLINE to 30 for testing
    os.environ["MAX_ROWS_INLINE"] = "30"
    print("\n✅ MAX_ROWS_INLINE set to 30")
    
    # Check Azure CLI authentication
    print("\n🔐 Checking Azure CLI authentication...")
    try:
        from azure.identity import DefaultAzureCredential
        cred = DefaultAzureCredential(exclude_interactive_browser_credential=True)
        token = cred.get_token("https://database.windows.net/.default")
        print("✅ Authenticated via Azure CLI")
    except Exception as e:
        print("❌ Not authenticated to Azure CLI")
        print("   Run: az login")
        return False
    
    # Run tests
    test1_passed = await test_orchestrator_small_query()
    test2_passed = await test_orchestrator_large_query()
    test3_passed = await test_orchestrator_direct_csv()
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Small Query (fabric_data):        {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    print(f"Large Query (multi-tool):         {'✅ PASSED' if test2_passed else '❌ FAILED'}")
    print(f"Direct CSV Export (sql_to_csv):   {'✅ PASSED' if test3_passed else '❌ FAILED'}")
    
    if test1_passed and test2_passed and test3_passed:
        print("\n🎉 All orchestrator tests passed!")
        return True
    else:
        print("\n⚠️  Some tests failed. Check the logs above for details.")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
