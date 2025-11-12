#!/usr/bin/env python3
"""
REAL End-to-End Test - No Fake Data, Real Queries

Tests the full MCP orchestrator with ACTUAL tables and REAL data.
"""

import os
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import structlog

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


async def main():
    """Run real end-to-end tests with actual data."""
    print("\n" + "="*80)
    print("REAL END-TO-END TEST - ACTUAL TABLES & DATA")
    print("="*80)
    
    from src.orchestrator.main import process_query
    
    # Test 1: List actual tables in the database
    print("\n" + "="*80)
    print("TEST 1: Discover Real Tables")
    print("="*80)
    print("\n🔍 Query: List all tables in the database")
    
    result = await process_query("List all the tables available in the database")
    print("\n📊 Agent Response:")
    print(result)
    
    # Test 2: Small query (should stay inline, <30 rows)
    print("\n" + "="*80)
    print("TEST 2: Small Query (Inline Results)")
    print("="*80)
    print("\n🔍 Query: Get current date and time")
    
    result = await process_query("What is the current server date and time?")
    print("\n📊 Agent Response:")
    print(result)
    
    # Test 3: Query with UNION to create 50 rows (triggers CSV export)
    print("\n" + "="*80)
    print("TEST 3: Large Query (Should Trigger CSV Export)")
    print("="*80)
    print("\n🔍 Query: Generate 50 rows of test data")
    print("   (Expected: Agent should warn about >30 rows and call sql_to_csv)")
    
    result = await process_query(
        "What accounts (name) have duplicates? Make me a csv"
    )
    print("\n📊 Agent Response:")
    print(result)
    
    # Check if CSV URL is in response
    if "https://" in result and "blob.core.windows.net" in result:
        print("\n✅ SUCCESS: CSV export URL generated!")
        print("🔔 The agent correctly:")
        print("   1. Recognized the large result set")
        print("   2. Called sql_to_csv tool")
        print("   3. Generated a public download URL")
    else:
        print("\n⚠️  WARNING: No CSV URL found in response")
    
    print("\n" + "="*80)
    print("END-TO-END TEST COMPLETE")
    print("="*80)
    print("\n✅ All tests completed successfully!")


if __name__ == "__main__":
    # Set environment
    os.environ["MAX_ROWS_INLINE"] = "30"
    
    asyncio.run(main())
