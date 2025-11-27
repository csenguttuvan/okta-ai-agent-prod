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
