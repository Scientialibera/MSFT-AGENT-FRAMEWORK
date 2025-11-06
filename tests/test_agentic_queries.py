"""
Test script demonstrating agentic reasoning with Microsoft Agent Framework.

Tests: 1) Simple direct answer, 2) General knowledge, 3) Complex multi-step analysis
"""

import asyncio
import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.src.settings import AzureOpenAISettings
from src.orchestrator.main import AIAssistant

# Configure logging
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


async def run_agentic_tests():
    """Run three test queries demonstrating agentic capabilities."""

    load_dotenv()

    settings = AzureOpenAISettings(
        endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-01-preview"),
        chat_deployment=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
    )
    assistant = AIAssistant(aoai_settings=settings)

    # Test queries
    test_queries = [
        {
            "name": "Test 1: Simple Direct Answer",
            "query": "How are you?",
        },
        {
            "name": "Test 2: General Knowledge",
            "query": "What is the current date and time?",
        },
        {
            "name": "Test 3: Complex Multi-Step Analysis",
            "query": "What are all category types and after that tell me the top 5 closing balance for the first one in alphabetical order",
        },
    ]

    for test in test_queries:
        print("\n" + "=" * 80)
        print(f"{test['name']}")
        print("=" * 80)
        print(f"Question: {test['query']}\n")

        try:
            result = await assistant.process_question(test["query"])

            print(f"Success: {result['success']}")
            print(f"\nAgent Response:")
            print("-" * 80)
            print(result['response'])
            print("-" * 80)

        except Exception as e:
            print(f"Error: {type(e).__name__}: {str(e)}")

    await assistant.close()


if __name__ == "__main__":
    asyncio.run(run_agentic_tests())
