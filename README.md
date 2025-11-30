Okta MCP Server
A Model Context Protocol (MCP) server that enables Claude Desktop and other MCP clients to interact with Okta's Identity and Access Management platform.


Table of Contents
Features

    Prerequisites

    Installation

        Using Docker (Recommended)

        From Source

    Configuration

        Claude Desktop Integration

    Available Tools

    Usage Examples

    Troubleshooting

    Security

    Contributing

    License

Features

    User Management: List, create, update, and manage Okta users

    Group Management: Create and manage groups, add/remove users

    Application Access: View applications and their assignments

    System Logs: Query Okta system logs for auditing

    Policy Access: Read-only access to Okta policies

    Pagination Support: Efficiently handle large datasets

Prerequisites
    Docker (recommended) OR Python 3.13+

    Okta organization with API access

    Okta API token with appropriate permissions:

        okta.users.read / okta.users.manage

        okta.groups.read / okta.groups.manage

        okta.apps.read

        okta.logs.read

        okta.policies.read

Installation
Using Docker (Recommended)
Pull the image from Docker Hub:

bash
docker pull blackstaa/okta-mcp-server:dev
Test the installation:

bash
docker run --rm -i \
  -e OKTA_API_BASE_URL="https://your-org.okta.com" \
  -e OKTA_API_TOKEN="your_api_token_here" \
  blackstaa/okta-mcp-server:dev
📖 Complete Docker Documentation

From Source
Clone the repository:

bash
git clone <repository-url>
cd okta-mcp-server
Install dependencies:

bash
pip install -e .
Or with uv:

bash
uv pip install -e .
Set environment variables:

bash
cp .env.example .env
# Edit .env with your Okta credentials
Run the server:

bash
uv run okta-mcp-server
Configuration
Required Environment Variables
Variable	Description	Example
OKTA_API_BASE_URL	Your Okta organization URL	https://dev-12345.okta.com
OKTA_API_TOKEN	Your Okta API token	00abc...
OKTA_LOG_LEVEL	Logging level (optional)	INFO, DEBUG
Claude Desktop Integration
Add to your Claude Desktop configuration file:

macOS: ~/Library/Application Support/Claude/claude_desktop_config.json

Windows: %APPDATA%\Claude\claude_desktop_config.json

Linux: ~/.config/Claude/claude_desktop_config.json

Using Docker:
json
{
  "mcpServers": {
    "okta": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "-e",
        "OKTA_API_BASE_URL=https://your-org.okta.com",
        "-e",
        "OKTA_API_TOKEN=your_api_token_here",
        "blackstaa/okta-mcp-server:dev"
      ]
    }
  }
}
Using local installation with uv:
json
{
  "mcpServers": {
    "okta": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/okta-mcp-server",
        "run",
        "okta-mcp-server"
      ],
      "env": {
        "OKTA_API_BASE_URL": "https://your-org.okta.com",
        "OKTA_API_TOKEN": "your_api_token_here"
      }
    }
  }
}
Important: Completely restart Claude Desktop after updating the configuration (Cmd+Q on macOS).

Available Tools
User Management
list_users - List users with filtering and pagination

get_user - Get user details by ID

create_user - Create a new user

update_user - Update user profile

delete_user - Delete a user (requires confirmation)

activate_user - Activate a user account

deactivate_user - Deactivate a user account

suspend_user / unsuspend_user - Suspend/unsuspend accounts

Group Management
list_groups - List groups with filtering and pagination

get_group - Get group details by ID

create_group - Create a new group

update_group - Update group profile

delete_group - Delete a group (requires confirmation)

list_group_users - List users in a group

list_group_apps - List applications assigned to a group

add_user_to_group / remove_user_from_group - Manage group membership

Application Management
list_applications - List applications with pagination

get_application - Get application details by ID

list_application_users - List users assigned to an application

list_application_groups - List groups assigned to an application

Policies & Logs
list_policies - List policies with filtering

get_policy - Get policy details by ID

get_system_logs - Query system logs with filtering

Usage Examples
List All Users
"Show me all users in my Okta organization"

Find Users by Email Domain
"List all users with @company.com email addresses"

Create a New Group
"Create a group called 'Engineering' with description 'Engineering team members'"

Add Users to Group
"Add user john.doe@company.com to the Engineering group"

Query System Logs
"Show me all login attempts in the last 24 hours"

Troubleshooting
Common Issues
Container exits immediately: This is normal for STDIO MCP servers. The container runs only when Claude connects to it.

Authentication errors: Verify your API token has the required scopes in Okta Admin Console → Security → API → Tokens.

Connection errors: Test your credentials:

bash
curl -H "Authorization: SSWS your_api_token" \
  "https://your-org.okta.com/api/v1/users?limit=1"
Changes not taking effect: After updating configuration, fully quit and restart Claude Desktop.

📖 Detailed Troubleshooting Guide

Security
⚠️ Never commit API tokens to version control

✅ Use environment variables for all credentials

✅ Rotate API tokens regularly

✅ Use least-privilege tokens with only required scopes

✅ Keep .env in .gitignore

✅ Monitor API usage through Okta's system logs

Architecture Notes
This server uses:

Python 3.13

MCP SDK 1.9.2

Okta SDK 2.9.13

SSWS authentication (API token-based)

STDIO transport for MCP communication

Contributing
Contributions are welcome! Please:

Fork the repository

Create a feature branch

Submit a pull request

License
Licensed under the Apache License, Version 2.0. See LICENSE file for details.

Support
Issues: [GitHub Issues]https://github.com/csenguttuvan/okta-ai-agent/issues

Docker Hub: blackstaa/okta-mcp-server

Okta Developer Docs: developer.okta.com

Built with ❤️ for the MCP community