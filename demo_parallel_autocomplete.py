#!/usr/bin/env python3
"""
Demo script to test the parallel processing functionality of the autocomplete API.
"""

import asyncio
import time
from app.core.config import get_settings
from app.services.google_autocomplete_service import google_autocomplete_service
import httpx


async def demo_parallel_processing():
    """Demonstrate the parallel processing functionality."""
    print("Testing Parallel Processing for Google Autocomplete API")
    print("=" * 60)

    # Get settings
    settings = get_settings()
    print("Configuration:")
    print(f"Max Parallel Requests: {settings.AUTOCOMPLETE_MAX_PARALLEL_REQUESTS}")
    print(f"Request Timeout: {settings.AUTOCOMPLETE_REQUEST_TIMEOUT}s")
    print(f"Max Retries: {settings.AUTOCOMPLETE_MAX_RETRIES}")
    print(f"Retry Delay: {settings.AUTOCOMPLETE_RETRY_DELAY}s")
    print()

    # Test query
    test_query = "python"
    print(f"Testing with query: '{test_query}'")
    print()

    # Start timing
    start_time = time.time()

    # Create HTTP client
    async with httpx.AsyncClient(timeout=httpx.Timeout(settings.AUTOCOMPLETE_REQUEST_TIMEOUT)) as client:
        try:
            # Build base params
            base_params = google_autocomplete_service.build_request_params(
                query=test_query,
                output="chrome",
                gl="US",
                hl="en",
                spell=1
            )

            # Call the parallel processing function via service
            result = await google_autocomplete_service.generate_keyword_variations_parallel(
                http_client=client,
                base_query=test_query,
                params=base_params,
                max_parallel=settings.AUTOCOMPLETE_MAX_PARALLEL_REQUESTS
            )

            # Calculate execution time
            execution_time = time.time() - start_time

            print("Parallel processing completed successfully!")
            print(f"Execution time: {execution_time:.2f}s")
            print()

            # Show some results
            print("Results Summary:")
            total_suggestions = 0
            total_categories = len(result["suggestions"])

            for category, prefixes in result["suggestions"].items():
                category_suggestions = sum(len(sugs) for sugs in prefixes.values())
                total_suggestions += category_suggestions
                print(f"  {category}: {len(prefixes)} prefixes, {category_suggestions} suggestions")

            print()
            print(f"Total: {total_categories} categories, {total_suggestions} suggestions")
            print(f"Metadata entries: {len(result['metadata'])}")

        except Exception as e:
            print(f"Error during parallel processing: {str(e)}")
            execution_time = time.time() - start_time
            print(f"Execution time: {execution_time:.2f}s")

    print()
    print("Parallel Processing Demo Complete!")


if __name__ == "__main__":
    # Run the demo
    asyncio.run(demo_parallel_processing())
