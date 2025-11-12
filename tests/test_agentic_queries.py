"""
Test script demonstrating agentic reasoning with direct SQL execution.

Tests:
1) Simple SQL query (fabric_data tool)
2) Large result set requiring CSV export (sql_to_csv tool)
3) Multi-step SQL reasoning with middleware logging
"""

import asyncio
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.orchestrator.main import AIAssistant

# Configure logging to see middleware in action
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)

# Suppress verbose logging
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(
    logging.WARNING
)
logging.getLogger("asyncio").setLevel(logging.WARNING)
logging.getLogger("azure.identity").setLevel(logging.WARNING)


async def run_sql_execution_tests():
    """Run test queries demonstrating direct SQL execution and middleware."""

    load_dotenv()

    assistant = AIAssistant()

    # Test queries showcasing new SQL execution capabilities
    test_queries = [
        {
            "name": "Test 1: Small Result Set (fabric_data tool)",
            "query": "What are the distinct account categories? Use fabric_data to execute: SELECT DISTINCT Category FROM Accounts ORDER BY Category",
            "expected_tool": "fabric_data",
        },
        {
            "name": "Test 2: Large Result Set (sql_to_csv tool)",
            "query": "Export all accounts to CSV. Use sql_to_csv to execute: SELECT * FROM Accounts ORDER BY AccountName",
            "expected_tool": "sql_to_csv",
        },
        {
            "name": "Test 3: Multi-Step SQL Reasoning",
            "query": "How many accounts share the same name? First count duplicates, then show examples. Use: SELECT AccountName, COUNT(*) as Count FROM Accounts GROUP BY AccountName HAVING COUNT(*) > 1 ORDER BY Count DESC",
            "expected_tool": "fabric_data",
        },
        {
            "name": "Test 4: Row Limit Warning Test",
            "query": "Show me all accounts without using TOP clause. Use fabric_data: SELECT AccountName, ClosingBalance FROM Accounts ORDER BY ClosingBalance DESC",
            "expected_tool": "fabric_data",
            "expected_behavior": "Should warn about row limit and suggest sql_to_csv",
        },
    ]

    for test in test_queries:
        print("\n" + "=" * 80)
        print(f"{test['name']}")
        print("=" * 80)
        print(f"Query: {test['query']}")
        print(f"Expected Tool: {test.get('expected_tool', 'N/A')}")
        if test.get('expected_behavior'):
            print(f"Expected Behavior: {test['expected_behavior']}")
        print()

        try:
            result = await assistant.process_question(test["query"])

            print(f"Success: {result['success']}")
            print(f"\nAgent Response:")
            print("-" * 80)
            print(result['response'])
            print("-" * 80)

        except Exception as e:
            print(f"Error: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()

    await assistant.close()


if __name__ == "__main__":
    asyncio.run(run_sql_execution_tests())
