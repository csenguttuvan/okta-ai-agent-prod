# The Okta software accompanied by this notice is provided pursuant to the following terms:
# Copyright © 2025-Present, Okta, Inc.
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License.
# You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0.
# Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and limitations under the License.

import os
from loguru import logger
from okta.client import Client as OktaClient


async def get_okta_client() -> OktaClient:
    """Initialize and return an Okta client using API token authentication."""
    logger.debug("Initializing Okta client")
    
    # Get configuration from environment
    api_token = os.environ.get("OKTA_API_TOKEN")
    api_base_url = os.environ.get("OKTA_API_BASE_URL")
    
    # Validate API token
    if not api_token:
        logger.error("OKTA_API_TOKEN not found in environment variables")
        raise ValueError("OKTA_API_TOKEN must be set")
    
    logger.info(f"API token is set: True")
    logger.info(f"API token starts with: {api_token[:6]}...")
    
    # Validate base URL
    if not api_base_url:
        logger.error("OKTA_API_BASE_URL not found in environment variables")
        raise ValueError("OKTA_API_BASE_URL must be set")
    
    # Configure Okta SDK client
    config = {
        "orgUrl": api_base_url,
        "token": api_token,
        "authorizationMode": "SSWS",  # API token authentication
        "userAgent": "okta-mcp-server/0.0.1",
    }
    
    logger.info(f"Okta client configured with orgUrl: {config['orgUrl']}")
    return OktaClient(config)
