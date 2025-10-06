"""Chaos testing actions for Chiron."""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import requests


def generate_http_load(
    url: str, total_requests: int = 100, concurrency: int = 10
) -> dict[str, Any]:
    """
    Generate HTTP load against a URL.

    Args:
        url: Target URL
        requests: Total number of requests to send
        concurrency: Number of concurrent requests

    Returns:
        dict with results
    """
    print(
        f"🔥 Generating load: {total_requests} requests with concurrency {concurrency}"
    )

    results = {"success": 0, "failed": 0, "total_time": 0}
    start_time = time.time()

    def make_request():
        try:
            resp = requests.get(url, timeout=10)
            return resp.status_code == 200
        except Exception:
            return False

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(make_request) for _ in range(total_requests)]

        for future in as_completed(futures):
            if future.result():
                results["success"] += 1
            else:
                results["failed"] += 1

    results["total_time"] = time.time() - start_time
    results["requests_per_second"] = total_requests / results["total_time"]

    print(f"✅ Load test completed: {results}")
    return results
