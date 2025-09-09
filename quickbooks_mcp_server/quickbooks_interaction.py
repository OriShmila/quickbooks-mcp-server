import requests
from requests.auth import HTTPBasicAuth
import os
from dotenv import load_dotenv

load_dotenv()


class QuickBooksSession:
    def __init__(self):
        # Get credentials from environment variables
        self.client_id = os.getenv("QUICKBOOKS_CLIENT_ID")
        self.client_secret = os.getenv("QUICKBOOKS_CLIENT_SECRET")
        self.refresh_token = os.getenv("QUICKBOOKS_REFRESH_TOKEN")
        self.company_id = os.getenv("QUICKBOOKS_COMPANY_ID")
        # Set base URL based on environment
        env = os.getenv("QUICKBOOKS_ENV", "sandbox").lower()
        base_urls = {
            "production": "https://quickbooks.api.intuit.com",
            "sandbox": "https://sandbox-quickbooks.api.intuit.com",
        }
        self.base_url = base_urls.get(env, base_urls["sandbox"])

        self.token_url = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
        self.access_token = None
        self.refresh_access_token()

    def _get_headers(self):
        if self.access_token is None:
            return None
        else:
            return {
                "Authorization": f"Bearer {self.access_token}",
                "Accept": "application/json",
            }

    def refresh_access_token(self):
        """Refresh the access token using the refresh token."""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {"grant_type": "refresh_token", "refresh_token": self.refresh_token}
        response = requests.post(
            self.token_url,
            headers=headers,
            data=data,
            auth=HTTPBasicAuth(self.client_id, self.client_secret),
        )

        if response.status_code == 200:
            tokens = response.json()
            self.access_token = tokens["access_token"]
            self.refresh_token = tokens.get("refresh_token", self.refresh_token)
        else:
            message = f"Error refreshing token: {response.status_code} {response.text}"
            raise RuntimeError(message)

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
        elif response.status_code == 401:
            # Access token expired; refresh and retry once
            self.refresh_access_token()

            if method_type == "get":
                response = method(url, params=params, headers=self._get_headers())
            else:
                response = method(
                    url, json=body, params=params, headers=self._get_headers()
                )

            if response.status_code == 200:
                return response.json()
            else:
                message = f"Error: {response.status_code} {response.text}"
                raise RuntimeError(message)
        else:
            message = f"Error: {response.status_code} {response.text}"
            raise RuntimeError(message)

    def query(self, query: str):
        """Execute a QuickBooks query."""
        return self.call_route("get", "/query", params={"query": query})

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
