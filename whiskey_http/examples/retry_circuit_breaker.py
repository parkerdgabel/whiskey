"""Example demonstrating retry and circuit breaker patterns."""

import asyncio
import random

from whiskey import Whiskey, inject
from whiskey_http import http_extension

app = Whiskey()
app.use(http_extension)


# Simulated flaky API client with retry
@app.http_client(
    "flaky_api",
    base_url="https://httpbin.org",
    retry={
        "attempts": 3,
        "backoff": "exponential",
        "initial_delay": 1.0,
        "on_status": [500, 502, 503, 504],
    },
)
class FlakyAPIClient:
    """Client that demonstrates retry logic."""

    pass


# Client with circuit breaker
@app.http_client(
    "protected_api",
    base_url="https://httpbin.org",
    circuit_breaker={"failure_threshold": 3, "recovery_timeout": 10.0},
)
class ProtectedAPIClient:
    """Client with circuit breaker protection."""

    pass


@app.component
class ResilientService:
    def __init__(self, flaky: FlakyAPIClient, protected: ProtectedAPIClient):
        self.flaky = flaky
        self.protected = protected

    async def test_retry(self):
        """Test retry logic with a flaky endpoint."""
        print("🔄 Testing retry logic...")

        try:
            # This endpoint randomly returns 500 errors
            response = await self.flaky.get("/status/500")
            print(f"✅ Request succeeded: {response.status_code}")
        except Exception as e:
            print(f"❌ Request failed after retries: {e}")

        # Try with an endpoint that sometimes succeeds
        print("\n🎲 Testing with random failures...")
        for i in range(5):
            # Randomly choose between success and failure
            status = random.choice([200, 200, 500, 503])
            try:
                response = await self.flaky.get(f"/status/{status}")
                print(f"  Attempt {i + 1}: ✅ {response.status_code}")
            except Exception as e:
                print(f"  Attempt {i + 1}: ❌ Failed - {type(e).__name__}")

    async def test_circuit_breaker(self):
        """Test circuit breaker pattern."""
        print("\n🔌 Testing circuit breaker...")

        # Make requests that will fail
        for i in range(5):
            try:
                # This will always fail
                response = await self.protected.get("/status/500")
                print(f"  Request {i + 1}: ✅ {response.status_code}")
            except Exception as e:
                print(f"  Request {i + 1}: ❌ {type(e).__name__}: {e!s}")

            await asyncio.sleep(0.5)

        print("\n⏳ Waiting for circuit breaker recovery...")
        await asyncio.sleep(11)  # Wait for recovery timeout

        # Try again after recovery
        print("\n🔄 Attempting after recovery...")
        try:
            response = await self.protected.get("/status/200")
            print(f"✅ Circuit recovered! Status: {response.status_code}")
        except Exception as e:
            print(f"❌ Still failing: {e}")


@inject
async def main(service: ResilientService):
    """Demonstrate resilience patterns."""
    print("🛡️ Demonstrating HTTP Client Resilience Patterns\n")

    await service.test_retry()
    await service.test_circuit_breaker()


if __name__ == "__main__":
    app.run(main)
