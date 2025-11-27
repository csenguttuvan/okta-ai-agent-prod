# The Okta software accompanied by this notice is provided pursuant to the following terms:
# Copyright © 2025-Present, Okta, Inc.
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License.
# You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0.
# Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and limitations under the License.

import keyring
from loguru import logger
from okta.client import Client as OktaClient
import os

from okta_mcp_server.utils.auth.auth_manager import SERVICE_NAME, OktaAuthManager


async def get_okta_client(manager: OktaAuthManager) -> OktaClient:
    """Initialize and return an Okta client"""
    logger.debug("Initializing Okta client")
    
    # Get API token from environment instead of keyring
    api_token = os.environ.get("OKTA_API_TOKEN")
    
    logger.info(f"API token is set: {api_token is not None}")
    if api_token:
        logger.info(f"API token starts with: {api_token[:6]}...")
    
    if not api_token:
        logger.error("OKTA_API_TOKEN not found in environment variables")
        raise ValueError("OKTA_API_TOKEN must be set")
    
    config = {
        "orgUrl": os.environ.get("OKTA_API_BASE_URL", "https://integrator-7772662.okta.com"),
        "token": api_token,
        "authorizationMode": "SSWS",
        "userAgent": "okta-mcp-server/0.0.1",
    }
    logger.info(f"Okta client configured with orgUrl: {config['orgUrl']}")
    return OktaClient(config)

