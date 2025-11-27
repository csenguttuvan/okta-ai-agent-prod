# Okta MCP Server

An MCP (Model Context Protocol) server for Okta identity management operations.

## Features

- List, create, and retrieve users
- Manage groups and applications
- Query system logs
- Read-only policy access

## Setup

1. Clone the repository
2. Copy `.env.example` to `.env` and fill in your Okta credentials
3. Install dependencies: `pip install -r requirements.txt`
4. Run the server: `uv run okta-mcp-server`

## Configuration

Required environment variables:
- `OKTA_API_BASE_URL`: Your Okta organization URL
- `OKTA_API_TOKEN`: Your Okta API token

## Security

- Never commit `.env` files or secrets
- Use environment variables or secrets managers for credentials
- Rotate API tokens regularly

## Troubleshooting & Issues Fixed

This section documents common issues encountered during development and their solutions.

### 1. **"Could not attach to MCP server" Error**

**Issue:** Claude Desktop shows "Could not attach to MCP server okta-mcp-server"

**Causes & Solutions:**
- **Missing `uv` command:** Install uv globally: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Wrong directory path:** Verify the `--directory` path in `claude_desktop_config.json` is correct
- **Environment variables not loaded:** Ensure all required env vars are in Claude config

---

### 2. **JSON-RPC Protocol Errors: "Unexpected token 'X' is not valid JSON"**

**Issue:** Errors like:
- `Unexpected token 'C', "CLIENT_ID:"... is not valid JSON`
- `Unexpected token 'R', "RESPONSE CODE:"... is not valid JSON`

**Cause:** `print()` statements in code writing to stdout, breaking JSON-RPC protocol

**Solution:** 
- Remove ALL `print()` statements from your codebase
- Use `logger.info()` or `logger.debug()` instead (writes to stderr)
- MCP protocol requires stdout to contain ONLY JSON-RPC messages

Find any remaining print statements
grep -r "print(" src/

text

---

### 3. **HTTP 404 "Page Not Found" Errors**

**Issue:** Getting 404 errors when calling Okta APIs (e.g., listing users)

**Cause:** Using OAuth authorization server URL for resource API calls

**Problem:**
WRONG - Using OAuth issuer for API calls
orgUrl = "https://your-org.okta.com/oauth2/ausxxx..."

text

**Solution:**
CORRECT - Separate URLs for different purposes
OKTA_ORG_URL = "https://your-org.okta.com/oauth2/ausxxx..." # For OAuth/device flow
OKTA_API_BASE_URL = "https://your-org.okta.com" # For resource APIs

text

**Key Insight:**
- OAuth endpoints: `/oauth2/{authServerId}/v1/token`
- Resource APIs: `/api/v1/users`, `/api/v1/groups`
- These must use different base URLs

---

### 4. **HTTP 401 "Invalid token provided" Errors**

**Issue:** `Okta HTTP 401 E0000011 Invalid token provided`

**Cause:** Using wrong authorization mode or wrong token type

**Solutions:**

#### A. Authorization Mode Mismatch
WRONG - Bearer is for OAuth access tokens
config = {
"authorizationMode": "Bearer"
}

CORRECT - SSWS is for Okta API tokens
config = {
"authorizationMode": "SSWS"
}

text

#### B. Using OAuth Token Instead of API Token
WRONG - Using OAuth access token from keyring
api_token = keyring.get_password(SERVICE_NAME, "api_token")

CORRECT - Using API token from environment
api_token = os.environ.get("OKTA_API_TOKEN")

text

---

### 5. **Environment Variables Not Loading in Claude Desktop**

**Issue:** `'NoneType' object has no attribute 'strip'` or variables showing as `None`

**Cause:** Claude Desktop doesn't use your shell's `.env` file or `direnv`

**Solution:** Add ALL required variables to `claude_desktop_config.json`:

{
"mcpServers": {
"okta-mcp-server": {
"env": {
"OKTA_API_BASE_URL": "https://your-org.okta.com",
"OKTA_API_TOKEN": "your_token_here",
"OKTA_ORG_URL": "https://your-org.okta.com/oauth2/ausxxx..."
}
}
}
}

text

**Remember:** Completely quit and restart Claude Desktop after config changes (Cmd+Q on Mac)

---

### 6. **Cached Code Running After Changes**

**Issue:** Code changes not taking effect, still seeing old errors

**Solution:** Clear Python cache:
find . -type d -name "pycache" -exec rm -r {} + 2>/dev/null
find . -name "*.pyc" -delete

text

Then completely restart Claude Desktop.

---

### 7. **OAuth Device Flow Not Working for Production**

**Issue:** Server requires manual browser interaction for authentication

**Solution:** For production, use API token authentication only:
1. Remove all device flow/OAuth code from `auth_manager.py`
2. Configure `client.py` to use `OKTA_API_TOKEN` from environment
3. Set `authorizationMode: "SSWS"`
4. Never store API tokens in keyring

---

## Key Architecture Decisions

### Authentication Strategy
- **Development (with Claude Desktop):** Device flow with manual login
- **Production (Docker/EC2):** API token only (no interactive auth)

### URL Configuration
| Purpose | Environment Variable | Example |
|---------|---------------------|---------|
| OAuth/Device Flow | `OKTA_ORG_URL` | `https://org.okta.com/oauth2/ausxxx...` |
| Resource APIs | `OKTA_API_BASE_URL` | `https://org.okta.com` |
| API Authentication | `OKTA_API_TOKEN` | Your API token |

### Client Configuration
For Okta SDK client (resource APIs)
config = {
"orgUrl": os.environ.get("OKTA_API_BASE_URL"), # Base URL, no /oauth2
"token": os.environ.get("OKTA_API_TOKEN"), # API token
"authorizationMode": "SSWS", # NOT "Bearer"
"userAgent": "okta-mcp-server/0.0.1"
}

text

---

## Debugging Tips

### Check What Claude Desktop Sees
View Claude Desktop logs (macOS)
tail -f ~/Library/Logs/Claude/mcp-server-okta-mcp-server.log

Or open Developer Tools in Claude Desktop
Cmd+Option+I → Console tab
text

### Test API Token Directly
curl -H "Authorization: SSWS your_api_token"
"https://your-org.okta.com/api/v1/users?limit=1"

text

Should return user data (not 401 or 404).

### Verify Environment Variables
Add temporary logging to verify vars are loaded
import os
logger.info(f"OKTA_API_BASE_URL: {os.environ.get('OKTA_API_BASE_URL')}")
logger.info(f"OKTA_API_TOKEN is set: {'OKTA_API_TOKEN' in os.environ}")

text

---

## Common Mistakes to Avoid

❌ Using `print()` instead of `logger`  
❌ Mixing OAuth URLs with resource API calls  
❌ Using Bearer auth with API tokens  
❌ Hardcoding secrets in code  
❌ Not restarting Claude Desktop after config changes  
❌ Committing `.env` files to Git  

✅ Use `logger` for all output  
✅ Separate URLs for OAuth vs API  
✅ Use SSWS auth for API tokens  
✅ Load secrets from environment  
✅ Fully quit and restart Claude Desktop  
✅ Keep `.env` in `.gitignore`  
