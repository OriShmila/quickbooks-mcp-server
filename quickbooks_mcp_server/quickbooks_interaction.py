import requests
import os
from dotenv import load_dotenv

load_dotenv()


class QuickBooksSession:
    def __init__(self):
        """Initialize session using static env vars only (no refresh management).

        Required env vars:
        - QBO_ACCESS_TOKEN: OAuth access token (Bearer)
        - QBO_REALM_ID: QuickBooks realm/company id
        - QBO_ENV: 'sandbox' or 'production' (defaults to 'sandbox')
        """
        # Read required configuration
        self.access_token = os.getenv("QBO_ACCESS_TOKEN")
        self.company_id = os.getenv("QBO_REALM_ID")

        if not self.access_token:
            raise RuntimeError("QBO_ACCESS_TOKEN environment variable is required")
        if not self.company_id:
            raise RuntimeError("QBO_REALM_ID environment variable is required")

        # Set base URL based on environment
        env_raw = os.getenv("QBO_ENV", "sandbox").lower()
        # Normalize a few common aliases
        env = {
            "prod": "production",
            "production": "production",
            "live": "production",
            "sandbox": "sandbox",
            "sbx": "sandbox",
        }.get(env_raw, env_raw)

        base_urls = {
            "production": "https://quickbooks.api.intuit.com",
            "sandbox": "https://sandbox-quickbooks.api.intuit.com",
        }
        self.base_url = base_urls.get(env, base_urls["sandbox"])

    def _get_headers(self):
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }

    # No refresh token management — errors should be raised to the caller

    def call_route(self, method_type, route, params: dict = None, body: dict = None):
        method = getattr(requests, method_type)
        if not route.startswith("/"):
            route = "/" + route

        url = f"{self.base_url}/v3/company/{self.company_id}{route}"

        if method_type == "get":
            response = method(url, params=params, headers=self._get_headers())
        else:
            response = method(
                url, json=body, params=params, headers=self._get_headers()
            )

        if response.status_code == 200:
            return response.json()
        # No retries or refresh handling — surface the error immediately
        message = f"Error: {response.status_code} {response.text}"
        raise RuntimeError(message)

    def query(
        self,
        query: str,
        start_position: int | None = None,
        max_results: int | None = None,
    ):
        """Execute a QuickBooks query with optional pagination.
        start_position corresponds to QuickBooks 'startposition' param.
        max_results corresponds to QuickBooks 'maxresults' param.
        """
        params = {"query": query}
        if start_position is not None:
            params["startposition"] = start_position
        if max_results is not None:
            params["maxresults"] = max_results
        return self.call_route("get", "/query", params=params)

    def get_account(self, account_id: str):
        """Get a specific account by ID."""
        return self.call_route("get", f"/account/{account_id}")

    def get_bill(self, bill_id: str):
        """Get a specific bill by ID."""
        return self.call_route("get", f"/bill/{bill_id}")

    def get_customer(self, customer_id: str):
        """Get a specific customer by ID."""
        return self.call_route("get", f"/customer/{customer_id}")

    def get_vendor(self, vendor_id: str):
        """Get a specific vendor by ID."""
        return self.call_route("get", f"/vendor/{vendor_id}")

    def get_invoice(self, invoice_id: str):
        """Get a specific invoice by ID."""
        return self.call_route("get", f"/invoice/{invoice_id}")


if __name__ == "__main__":
    quickbooks = QuickBooksSession()
    print("Access token:", quickbooks.access_token)
