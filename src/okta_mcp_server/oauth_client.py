import os
import requests
from typing import Optional, Dict, Any
from loguru import logger


class OktaOAuthClient:
    """OAuth 2.0 client for Okta API with scoped access."""

    def __init__(self):
        # Load from environment
        self.base_url = os.getenv("OKTA_API_BASE_URL")
        self.auth_server_id = os.getenv("OKTA_AUTH_SERVER_ID", "")
        self.client_id = os.getenv("OKTA_CLIENT_ID")
        self.client_secret = os.getenv("OKTA_CLIENT_SECRET")
        self.scopes = os.getenv("OKTA_SCOPES", "").split()

        # Validate required env vars (auth_server_id is optional for org server)
        if not all([self.base_url, self.client_id, self.client_secret]):
            raise ValueError(
                "Missing required OAuth environment variables. "
                "Check OKTA_API_BASE_URL, OKTA_CLIENT_ID, OKTA_CLIENT_SECRET"
            )

        # Build token endpoint URL - support org server (empty auth_server_id)
        if self.auth_server_id:
            self.token_url = f"{self.base_url}/oauth2/{self.auth_server_id}/v1/token"
        else:
            # Org authorization server (no auth server ID in path)
            self.token_url = f"{self.base_url}/oauth2/v1/token"

        logger.info("Okta OAuth Client initialized")
        logger.info(f"Base URL: {self.base_url}")
        logger.info(f"Auth Server ID: {self.auth_server_id or '(org server)'}")
        logger.info(f"Token URL: {self.token_url}")

        self.access_token: Optional[str] = None
        self.token_info: Dict[str, Any] = {}

        # Get initial token
        self._fetch_token()

    def _fetch_token(self):
        """Fetch access token using client credentials flow."""
        logger.info("Requesting OAuth token...")
        logger.debug(f"Client ID: {self.client_id}")
        logger.debug(f"Requested scopes: {' '.join(self.scopes)}")

        try:
            response = requests.post(
                self.token_url,
                auth=(self.client_id, self.client_secret),
                data={
                    "grant_type": "client_credentials",
                    "scope": " ".join(self.scopes),
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
            )

            if response.status_code != 200:
                logger.error(f"Token request failed: {response.status_code}")
                logger.error(f"Response: {response.text}")

            response.raise_for_status()
            self.token_info = response.json()
            self.access_token = self.token_info["access_token"]

            granted_scopes = self.token_info.get("scope", "").split()
            logger.info("✅ OAuth token obtained successfully")
            logger.info(f"Granted scopes: {' '.join(granted_scopes)}")
            logger.info(f"Token type: {self.token_info.get('token_type')}")
            logger.info(f"Expires in: {self.token_info.get('expires_in')} seconds")

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch OAuth token: {str(e)}")
            raise

    def _get_headers(self) -> Dict[str, str]:
        """Get headers with OAuth Bearer token."""
        if not self.access_token:
            logger.warning("No access token, fetching new one...")
            self._fetch_token()

        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def get(self, endpoint: str, params: Optional[Dict] = None) -> Any:
        """Make authenticated GET request to Okta API."""
        url = f"{self.base_url}{endpoint}"
        logger.debug(f"GET {url} {params or ''}")

        response = requests.get(url, headers=self._get_headers(), params=params)

        # Handle token expiration
        if response.status_code == 401:
            logger.warning("Token expired (401), refreshing...")
            self._fetch_token()
            response = requests.get(url, headers=self._get_headers(), params=params)

        # Handle insufficient scope
        if response.status_code == 403:
            error_msg = f"❌ Insufficient scope for {endpoint}\n"
            error_msg += f"Granted scopes: {self.token_info.get('scope')}\n"
            error_msg += "This operation requires additional permissions."
            logger.error(error_msg)
            raise PermissionError(error_msg)

        response.raise_for_status()
        return response.json()

    async def post(self, endpoint: str, data: Dict) -> Any:
        """Make authenticated POST request (will fail without write scopes)."""
        url = f"{self.base_url}{endpoint}"
        logger.debug(f"POST {url}")

        response = requests.post(url, headers=self._get_headers(), json=data)

        if response.status_code == 403:
            error_msg = f"❌ Write operation blocked: {endpoint}\n"
            error_msg += f"Current scopes: {self.token_info.get('scope')}\n"
            error_msg += "Write operations require additional scope (e.g., okta.users.manage)"
            logger.error(error_msg)
            raise PermissionError(error_msg)

        response.raise_for_status()
        return response.json()

    async def put(self, endpoint: str, data: Dict) -> Any:
        """Make authenticated PUT request."""
        url = f"{self.base_url}{endpoint}"
        logger.debug(f"PUT {url}")

        response = requests.put(url, headers=self._get_headers(), json=data)

        if response.status_code == 403:
            error_msg = f"❌ Write operation blocked: {endpoint}"
            logger.error(error_msg)
            raise PermissionError(error_msg)

        response.raise_for_status()
        return response.json()

    async def delete(self, endpoint: str) -> Any:
        """Make authenticated DELETE request."""
        url = f"{self.base_url}{endpoint}"
        logger.debug(f"DELETE {url}")

        response = requests.delete(url, headers=self._get_headers())

        if response.status_code == 403:
            error_msg = f"❌ Delete operation blocked: {endpoint}"
            logger.error(error_msg)
            raise PermissionError(error_msg)

        response.raise_for_status()
        return response.json() if response.text else {}

    def get_granted_scopes(self) -> list[str]:
        """Return list of granted scopes."""
        return self.token_info.get("scope", "").split()

    def get_token_info(self) -> Dict[str, Any]:
        """Return full token information."""
        return self.token_info


# Global instance
okta_client = None


def init_okta_client():
    """Initialize the global Okta OAuth client."""
    global okta_client
    if okta_client is None:
        okta_client = OktaOAuthClient()
    return okta_client
