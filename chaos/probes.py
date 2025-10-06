"""Chaos testing probes for Chiron."""

import time
from typing import Any

import requests


def check_response_time(url: str, max_ms: int = 1000) -> dict[str, Any]:
    """
    Check if a URL responds within the specified time.

    Args:
        url: Target URL
        max_ms: Maximum response time in milliseconds

    Returns:
        dict with response time info
    """
    start = time.time()
    try:
        response = requests.get(url, timeout=10)
        elapsed_ms = (time.time() - start) * 1000

        result = {
            "url": url,
            "status_code": response.status_code,
            "response_time_ms": elapsed_ms,
            "within_threshold": elapsed_ms <= max_ms,
        }

        if elapsed_ms > max_ms:
            print(f"⚠️  Response time {elapsed_ms:.0f}ms exceeds threshold {max_ms}ms")
        else:
            print(f"✅ Response time {elapsed_ms:.0f}ms is acceptable")

        return result
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return {
            "url": url,
            "error": str(e),
            "response_time_ms": (time.time() - start) * 1000,
            "within_threshold": False,
        }


def check_service_health(url: str = "http://localhost:8000/health") -> bool:
    """
    Check if the service is healthy.

    Args:
        url: Health check endpoint URL

    Returns:
        bool indicating if service is healthy
    """
    try:
        response = requests.get(url, timeout=5)
        healthy = response.status_code == 200

        if healthy:
            print("✅ Service is healthy")
        else:
            print(f"❌ Service returned status {response.status_code}")

        return healthy
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False
