import os
import time
import jwt
import requests
from typing import Optional, Dict, Any
from loguru import logger


class OktaOAuthJWTClient:
    """OAuth 2.0 client for Okta API using private_key_jwt authentication."""

    def __init__(self):
        # Load from environment
        self.base_url = os.getenv("OKTA_API_BASE_URL")
        self.client_id = os.getenv("OKTA_CLIENT_ID")
        self.private_key_path = os.getenv("OKTA_PRIVATE_KEY_PATH")
        self.scopes = os.getenv("OKTA_SCOPES", "").split()

        # Validate required env vars
        if not all([self.base_url, self.client_id, self.private_key_path]):
            raise ValueError(
                "Missing required environment variables. "
                "Check OKTA_API_BASE_URL, OKTA_CLIENT_ID, OKTA_PRIVATE_KEY_PATH"
            )

        # Load private key
        with open(self.private_key_path, 'r') as f:
            self.private_key = f.read()

        # Org authorization server endpoint
        self.token_url = f"{self.base_url}/oauth2/v1/token"

        logger.info("Okta OAuth JWT Client initialized")
        logger.info(f"Base URL: {self.base_url}")
        logger.info(f"Token URL: {self.token_url}")
        logger.info(f"Private key: {self.private_key_path}")

        self.access_token: Optional[str] = None
        self.token_info: Dict[str, Any] = {}

        # Get initial token
        self._fetch_token()

    def _create_client_assertion(self) -> str:
        """Create JWT for client assertion."""
        now = int(time.time())
        
        payload = {
            "iss": self.client_id,
            "sub": self.client_id,
            "aud": self.token_url,
            "iat": now,
            "exp": now + 300,
            "jti": f"{self.client_id}-{now}"
        }

        token = jwt.encode(
            payload,
            self.private_key,
            algorithm="RS256"
        )

        return token

    def _fetch_token(self):
        """Fetch access token using private_key_jwt."""
        logger.info("Requesting OAuth token with private_key_jwt...")
        logger.debug(f"Client ID: {self.client_id}")
        logger.debug(f"Requested scopes: {' '.join(self.scopes)}")

        try:
            client_assertion = self._create_client_assertion()

            response = requests.post(
                self.token_url,
                data={
                    "grant_type": "client_credentials",
                    "scope": " ".join(self.scopes),
                    "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                    "client_assertion": client_assertion
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
        url = f"{self.base_url}{endpoint}"
        response = requests.get(url, headers=self._get_headers(), params=params)

        if response.status_code == 401:
            self._fetch_token()
        response = requests.get(url, headers=self._get_headers(), params=params)

        if response.status_code == 403:
            raise PermissionError(f"❌ Insufficient scope for {endpoint}")

        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            raise ValueError(
                f"Expected JSON from Okta, got {content_type}: {response.text[:200]}"
        )

        return response.json()

    async def post(self, endpoint: str, data: Dict) -> Any:
        """Make authenticated POST request."""
        url = f"{self.base_url}{endpoint}"
        response = requests.post(url, headers=self._get_headers(), json=data)

        if response.status_code == 403:
            raise PermissionError(f"❌ Write operation blocked: {endpoint}")

        response.raise_for_status()
        return response.json()

    async def put(self, endpoint: str, data: Optional[Dict] = None) -> Any:
        """Make authenticated PUT request."""
        url = f"{self.base_url}{endpoint}"
        if data:
            response = requests.put(url, headers=self._get_headers(), json=data)
        else:
            response = requests.put(url, headers=self._get_headers())

        if response.status_code == 403:
            raise PermissionError(f"❌ Write operation blocked: {endpoint}")

        response.raise_for_status()
        return response.json() if response.text else {}

    async def delete(self, endpoint: str) -> Any:
        """Make authenticated DELETE request."""
        url = f"{self.base_url}{endpoint}"
        response = requests.delete(url, headers=self._get_headers())

        if response.status_code == 403:
            raise PermissionError(f"❌ Delete operation blocked: {endpoint}")

        response.raise_for_status()
        return response.json() if response.text else {}

    def get_granted_scopes(self) -> list[str]:
        """Return list of granted scopes."""
        return self.token_info.get("scope", "").split()

    def get_token_info(self) -> Dict[str, Any]:
        """Return full token information."""
        return self.token_info


okta_client = None

def init_okta_client():
    """Initialize the global Okta OAuth JWT client."""
    global okta_client
    if okta_client is None:
        okta_client = OktaOAuthJWTClient()
    return okta_client


def get_client():
    """Get the global okta_client instance."""
    global okta_client
    if okta_client is None:
        raise RuntimeError("Okta client not initialized. Call init_okta_client() first.")
    return okta_client
