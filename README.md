## Okta MCP Server with AWS Infrastructure

A complete Model Context Protocol (MCP) server implementation for Okta management, deployed on AWS with LiteLLM proxy for Claude Sonnet 4.5 integration via AWS Bedrock.

## 🏗️ Architecture

```mermaid
flowchart LR

%% Client side
subgraph LOCAL["Local machine"]
  Roo["Roo / Claude Desktop"]
  SDM["StrongDM Client\n(local tunnel)"]
  Roo --> SDM
end

%% AWS side
subgraph AWS["AWS (eu-west-3) - EC2 Instance"]
  direction TB

  subgraph MCP["Okta MCP Servers"]
    MCPAdmin["MCP Admin Server\n:8080 (read/write)"]
    MCPRO["MCP Readonly Server\n:8081 (read-only)"]
  end

  subgraph LLM["LLM Gateway"]
    LiteLLM["LiteLLM Proxy\n:4000"]
    Bedrock["AWS Bedrock\n(Claude Sonnet 4.5)"]
    LiteLLM --> Bedrock
  end

  subgraph OBS["Observability"]
    Promtail["Promtail\n(log shipper)"]
    Loki["Loki\n:3100 (logs)"]
    Grafana["Grafana\n:3000 (dashboards)"]
    Promtail --> Loki --> Grafana
  end

  subgraph AUTO["Auto-update"]
    Watchtower["Watchtower\n(auto-updates every 5 min)"]
  end

  %% Traffic flows
  SDM --> LiteLLM
  SDM --> MCPAdmin
  SDM --> MCPRO

  %% Logs
  MCPAdmin --> Promtail
  MCPRO --> Promtail
  LiteLLM --> Promtail

  %% Notes (keep inside diagram)
  Bedrock -. "Inference stays in AWS (eu-west-3)\nPrompts not used for training" .- Bedrock
end


## ✨ Features

### 🔐 Authentication & Security
- **Dual authentication layer**: StrongDM + Okta OAuth 2.0
- **Gateway isolation**: MCP servers never exposed directly
- **Per-user session management**: Track and audit all sessions
- **JWT-based Okta auth**: Private key authentication (more secure than API tokens)
- **Health check endpoints**: Monitor service availability

### 🛠️ Okta Management Tools

#### User Management
- `list_users` - List all users with pagination
- `find_user` - Universal user lookup (exact + fuzzy fallback)
- `get_user` - Get detailed user information
- `search_users` - Search users using Okta search syntax
- `search_users_fuzzy` - Fuzzy search by name/email
- `create_user` - Create new users (admin only)
- `deactivate_user` - Deactivate existing users (admin only)
- `delete_user` - Delete users (admin only)

#### 🆕 Profile Attribute Search & Bulk Operations
- `search_users_by_attribute` - Find users by any profile field (division, department, title, location, etc.)
- `add_users_to_group_by_attribute` - Bulk add users to groups based on profile criteria
- `remove_users_from_group_by_attribute` - Bulk remove users from groups based on profile criteria
- **Dry-run support**: Preview changes before applying

**Example workflows:**

"List all users in the Corp IT division"
"Add all users with division='Engineering' to the eng-team group"
"Do a dry run of adding Sales division to sales-team group"
"Remove all contractors from the full-time-benefits group"


#### Group Management
- `list_groups` - View all groups
- `search_groups_fuzzy` - Fuzzy search groups by name
- `get_group` - Get group details
- `list_group_users` - View group membership
- `create_group` - Create new groups (admin only)
- `delete_group` - Delete groups (admin only)
- `add_user_to_group` - Add single user to group (admin only)
- `remove_user_from_group` - Remove user from group (admin only)
- `add_users_to_group` - Batch add users to a group (admin only)

#### Application Management
- `list_applications` - View all applications
- `get_application` - Get app details
- `list_application_users` - View users assigned to an app
- `list_application_groups` - View groups assigned to an app
- `get_application_schema` - Get app user profile schema (shows available role fields)
- `list_application_available_roles` - List all roles configured/available on an app
- `list_application_roles_in_use` - List unique roles currently assigned to users
- `get_user_application_roles` - Get specific user's role(s) for an app
- `check_role_exists_on_application` - Validate if a specific role exists on an app
- `assign_user_to_application` - Assign user to app (admin only)
- `assign_user_to_application_with_role` - Assign user to app with specific role (admin only)
- `update_user_application_role` - Update role for already-assigned user (admin only)
- `assign_group_to_application` - Assign group to app (admin only)
- `create_application` - Create new application (admin only)
- `unassign_users_from_application_by_attribute` - Bulk unassign users by attribute filter (admin only)


#### Policy & Audit
- `list_policies` - View authentication policies
- `get_policy` - Get policy details
- `get_logs` - Query system audit logs with filters
- `check_permissions` - View granted OAuth scopes

### Infrastructure
- **Terraform-managed AWS deployment** (VPC, EC2, Secrets Manager, IAM)
- **Docker-based services** with Watchtower auto-updates
- **Dual MCP servers:** Admin (full access) and Readonly (safe queries)
- **StrongDM:** StrongDM integration
- **LiteLLM API Gateway:** OpenAI-compatible API for AWS Bedrock
- **Complete observability:** Grafana + Loki + Promtail logging stack
- **Automated deployment** via user-data script

## 🚀 Quick Start

### Prerequisites

- AWS CLI configured with credentials
- Terraform >= 1.0
- Okta account with OAuth 2.0 applications
- SSH key pair for EC2 access
- Docker images pushed to Docker Hub (optional for custom builds)

### 1. Clone and Configure

```bash
git clone <your-repo-url>
cd okta-mcp-aws

# Copy and configure variables
cp terraform.tfvars.example terraform.tfvars

Edit terraform.tfvars:

text
aws_region          = "eu-west-3"
project_name        = "okta-mcp"
key_name            = "your-key-name"

# Okta OAuth Apps (3 separate apps)
okta_domain              = "your-domain.okta.com"
okta_admin_client_id     = "admin-app-client-id"
okta_readonly_client_id  = "readonly-app-client-id"
okta_gateway_client_id   = "gateway-app-client-id"
okta_issuer              = "https://your-domain.okta.com/oauth2/default"

# Private keys (stored in AWS Secrets Manager)
admin_private_key_pem     = "-----BEGIN RSA PRIVATE KEY-----\n..."
readonly_private_key_pem  = "-----BEGIN RSA PRIVATE KEY-----\n..."

# LiteLLM keys
litellm_master_key  = "sk-YOUR-SECURE-MASTER-KEY"
litellm_admin_key   = "sk-ADMIN-TEAM-KEY"
litellm_reader_key  = "sk-READER-TEAM-KEY"

# Gateway settings
gateway_redirect_uri      = "https://okta-gateway.your-domain.com/oauth/callback"
gateway_session_secret    = "your-secure-session-secret"
gateway_internal_auth     = "your-internal-auth-token"

# Docker images (optional - uses public images by default)
docker_image              = "blackstaa/okta-mcp-server:latest"
gateway_image             = "blackstaa/okta-mcp-gateway:latest"

Deploy Infrastructure
bash
terraform init
terraform plan
terraform apply

Verify Deployment
# Get instance IP
terraform output instance_public_ip

# SSH into instance
ssh -i ~/.ssh/your-key.pem ec2-user@<INSTANCE_IP>

# Check all services
docker ps

# Should see all containers as (healthy):
# - okta-mcp-admin
# - okta-mcp-readonly
# - litellm-proxy
# - grafana
# - loki
# - promtail
# - watchtower


Test Endpoints
# Test admin MCP health
curl http://localhost:8080/health

# Test readonly MCP health
curl http://localhost:8081/health

# Test LiteLLM
export LITELLM_KEY=$(terraform output -raw litellm_master_key)
curl http://localhost:4000/v1/models \
  -H "Authorization: Bearer $LITELLM_KEY"

Configure StrongDM

Create two HTTP resources in StrongDM:

Admin MCP Server:

Hostname: 10.2.0.37 (or your EC2 private IP)

Port: 8080

Healthcheck Path: /health

Subdomain: okta-mcp-admin

Readonly MCP Server:

Hostname: 10.2.0.37

Port: 8081

Healthcheck Path: /health

Subdomain: okta-mcp-readonly

6. Connect Roo/Claude Desktop
Configure Roo (VS Code settings.json):

{
  "roo-cline.mcpServers": {
    "okta-admin": {
      "transport": {
        "type": "sse",
        "url": "http://okta-mcp-admin.your-sdm-domain.network/sse"
      }
    },
    "okta-readonly": {
      "transport": {
        "type": "sse",
        "url": "http://okta-mcp-readonly.your-sdm-domain.network/sse"
      }
    }
  }
}


🔧 Configuration
Okta OAuth 2.0 Setup
Create two OAuth 2.0 API Services applications in Okta:

1. Admin MCP Server App
Grant Type: Client Credentials

Scopes:

okta.users.read

okta.users.manage

okta.groups.read

okta.groups.manage

okta.apps.read

okta.apps.manage

okta.policies.read

okta.logs.read

2. Readonly MCP Server App
Grant Type: Client Credentials

Scopes:

okta.users.read

okta.groups.read

okta.apps.read

okta.policies.read

okta.logs.read

Generate private keys for both apps and add to terraform.tfvars

AWS Bedrock Setup
Enable AWS Bedrock in eu-west-3

Subscribe to Claude Sonnet 4.5 in AWS Marketplace

Request model access in Bedrock console

Ensure IAM role has bedrock:InvokeModel permission

LiteLLM Configuration
The deployment includes these Bedrock models (configured in litellm-config.yaml):

model_list:
  # Claude Sonnet 4.5 (primary)
  - model_name: bedrock-sonnet
    litellm_params:
      model: bedrock/eu.anthropic.claude-sonnet-4-5-20250929-v1:0
      aws_region_name: eu-west-3

  # Claude Haiku 4.5 (fast, cheap)
  - model_name: bedrock-haiku
    litellm_params:
      model: bedrock/eu.anthropic.claude-haiku-4-5-20251001-v1:0
      aws_region_name: eu-west-3

  # Llama 3.3 70B (open source)
  - model_name: bedrock-llama
    litellm_params:
      model: bedrock/eu.meta.llama3-3-70b-instruct-v1:0
      aws_region_name: eu-west-3

  # Mistral Large
  - model_name: bedrock-mistral
    litellm_params:
      model: bedrock/eu.mistral.mistral-large-2402-v1:0
      aws_region_name: eu-west-3


🔐 Security
Secrets in AWS Secrets Manager - No hardcoded credentials

Private key JWT authentication - More secure than API tokens

StrongDM tunnel - Secure access with audit logging

IAM role-based access - EC2 instance uses IAM for AWS services

VPC isolation - EC2 in private subnet with NAT gateway

Security groups - Restricted inbound access (VPC range only)

Data residency - All AI processing stays in AWS eu-west-3

Auto-updates - Watchtower keeps containers current with security patches

Health monitoring - /health endpoints for uptime monitoring

📊 Monitoring
Access Grafana Dashboards
bash
# Create SSH tunnel to Grafana
ssh -L 3000:localhost:3000 -i ~/.ssh/your-key.pem ec2-user@<INSTANCE_IP> -N

# Open browser to http://localhost:3000
# Default credentials: admin/admin
Check Service Logs
bash
# View all container logs
docker logs -f okta-mcp-admin
docker logs -f okta-mcp-gateway-admin
docker logs -f litellm-proxy

# Check Watchtower auto-update logs
docker logs watchtower

# View aggregated logs in Loki (via Grafana)
# Query: {container="okta-mcp-admin"}
Check Service Health
bash
# Check all container health status
docker ps

# View detailed healthcheck logs
docker inspect okta-mcp-admin | jq '.[].State.Health'

# Test health endpoints
curl http://localhost:8080/health
curl http://localhost:8081/health

# Via StrongDM
curl http://okta-mcp-admin.your-sdm-domain.network/health

🐛 Troubleshooting
MCP Server Connection Failed
Verify MCP server is running: docker ps | grep okta-mcp

Check server health: curl http://localhost:8080/health

View server logs: docker logs okta-mcp-admin

Verify StrongDM tunnel is active

Test SSE endpoint: curl http://localhost:8080/sse

Container Shows "unhealthy"
bash
# Check healthcheck logs
docker inspect okta-mcp-admin | jq '.[].State.Health.Log[-1]'

# Verify health endpoint responds
docker exec okta-mcp-admin curl -f http://localhost:8080/health

# Restart container if needed
docker restart okta-mcp-admin

Watchtower Not Updating Images
bash
# Check Watchtower logs
docker logs watchtower

# Verify containers have label
docker inspect okta-mcp-admin | grep watchtower.enable

# Manually trigger update
docker restart watchtower

# Check Docker Hub for new images
docker pull blackstaa/okta-mcp-server:latest

LiteLLM Bedrock Errors
Error: "Not subscribed to Bedrock model"

Subscribe to Claude Sonnet 4.5 in AWS Marketplace

Wait 2-3 minutes for subscription to propagate

Error: "AccessDeniedException"

Check IAM role has bedrock:InvokeModel permission

Verify model access enabled in Bedrock console

Confirm correct AWS region (eu-west-3)

Okta Authentication Failed
bash
# Verify credentials in Secrets Manager
aws secretsmanager get-secret-value --secret-id okta-mcp-admin-key

# Check private key format (must include \n for newlines)
# Verify OAuth scopes in Okta application

# Test OAuth token generation
docker logs okta-mcp-admin | grep "OAuth"

StrongDM Healthcheck Failing
bash
# Verify health endpoint works locally
curl http://localhost:8080/health

# Check StrongDM configuration
# - Healthcheck Path should be: /health
# - Port should match: 8080 or 8081
# - Security group allows traffic from VPC range (10.2.0.0/16)

# View MCP server logs
docker logs okta-mcp-admin --tail 50

# Pull latest images
docker pull blackstaa/okta-mcp-server:latest
docker pull blackstaa/okta-mcp-gateway:latest

# Restart services
cd /opt/okta-litellm
docker compose down
docker compose up -d

# Verify all containers healthy
docker ps
Update Infrastructure
bash

🔄 Updates and Maintenance
Auto-Updates via Watchtower
Watchtower automatically checks for new Docker images every 5 minutes and updates containers with the label com.centurylinklabs.watchtower.enable=true.

Monitored images:

blackstaa/okta-mcp-server:latest (admin + readonly servers)

To deploy updates:

Build and push new Docker image to Docker Hub

Wait up to 5 minutes for Watchtower to detect and apply update

Verify update: docker ps (check container "Created" time)

Manual Updates
bash
ssh -i ~/.ssh/your-key.pem ec2-user@<INSTANCE_IP>

# Pull latest images
docker pull blackstaa/okta-mcp-server:latest

# Restart services
cd /opt/okta-litellm
docker-compose down
docker-compose up -d


# Make changes to Terraform files
terraform plan
terraform apply

# For user-data.sh changes, recreate instance:
terraform taint aws_instance.okta_mcp
terraform apply
📁 Project Structure
.
├── terraform/
│   ├── main.tf                    # Main infrastructure
│   ├── vpc.tf                     # VPC and networking
│   ├── iam.tf                     # IAM roles and policies
│   ├── secrets.tf                 # Secrets Manager resources
│   ├── security_groups.tf         # Security group rules
│   ├── outputs.tf                 # Terraform outputs
│   ├── variables.tf               # Input variables
│   └── terraform.tfvars           # Your configuration (gitignored)
├── src/
│   └── okta_mcp_server/
│       ├── server.py              # MCP server entrypoint
│       ├── oauth_jwt_client.py    # Okta OAuth client
│       └── tools/                 # MCP tool implementations
│           ├── users/
│           │   ├── users.py       # User read operations
│           │   └── users_admin.py # User write + attribute search
│           ├── groups/            # Group operations
│           ├── applications/      # App operations
│           └── policies/          # Policy operations
├── Dockerfile                     # MCP server container image
├── docker-compose.yml             # Service orchestration (in user-data.sh)
├── user-data.sh                   # EC2 initialization script
├── litellm-config.yaml            # LiteLLM model configuration
├── loki-config.yaml               # Loki log aggregation config
├── promtail-config.yaml           # Promtail log collection config
└── README.md                      # This file


## 💰 Cost Estimate

**AWS Resources (eu-west-3):**
- EC2 t3.medium: ~$30/month
- NAT Gateway: ~$32/month
- EBS storage (30GB): ~$3/month
- Secrets Manager (2 secrets): ~$1/month
- Data transfer: Variable (~$5-10/month)

**AWS Bedrock Claude Sonnet 4.5:** Pay-per-use
- Input: $3 per million tokens
- Cached input: $0.30 per million tokens (90% discount)
- Output: $15 per million tokens

**Infrastructure Base:** ~$71-76/month

**With Prompt Caching + MCP Filtering:**
- Light use (5 queries/day): ~**$72-77/month** (minimal Bedrock cost)
- Moderate use (20 queries/day): ~**$76-81/month** (+$5 Bedrock)
- Heavy use (100 queries/day): ~**$95-100/month** (+$24 Bedrock)

**Note:** Prompt caching reduces token costs by ~90% for system prompts and tool definitions. MCP tool filtering further reduces context size. Most costs come from infrastructure, not AI usage.


🤝 Contributing
Fork the repository

Create a feature branch (git checkout -b feature/amazing-feature)

Make your changes

Test thoroughly with both admin and readonly servers

Commit your changes (git commit -m 'feat: add amazing feature')

Push to the branch (git push origin feature/amazing-feature)

Open a Pull Request

📝 License
MIT License - See LICENSE file for details

🙏 Acknowledgments
Model Context Protocol by Anthropic

LiteLLM by BerriAI

Okta Management API

AWS Bedrock

Grafana Stack for observability

Watchtower for auto-updates

📞 Support
For issues and questions:

Open a GitHub issue with detailed logs

Check MCP documentation

Review AWS Bedrock docs

Check container logs: docker logs <container-name>

View Grafana dashboards for system metrics

Built with ❤️ for secure, privacy-focused Okta automation with enterprise-grade observability