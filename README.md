# Okta MCP Server with AWS Infrastructure

A complete Model Context Protocol (MCP) server implementation for Okta management, deployed on AWS with LiteLLM proxy for Claude Sonnet 4.5 integration via AWS Bedrock.

## 🏗️ Architecture

Roo/Claude Desktop (Local Machine)
↓ StrongDM Tunnel or SSH (ports 9000/9001)
EC2 Instance (AWS eu-west-3)
├─ Auth Gateway Layer
│ ├─ Admin Gateway (port 9001) - Okta OAuth + StrongDM auth
│ └─ Readonly Gateway (port 9000) - Read-only access
├─ MCP Server Layer
│ ├─ MCP Admin Server (port 8080) - Full read/write access
│ ├─ MCP Readonly Server (port 8081) - Read-only access
│ └─ LiteLLM Proxy (port 4000) - AWS Bedrock Claude Sonnet 4.5
├─ Observability Stack
│ ├─ Grafana (port 3000) - Dashboards & visualization
│ ├─ Loki (port 3100) - Log aggregation
│ └─ Promtail - Log collection
└─ Auto-Update Layer
└─ Watchtower - Auto-updates Docker images every 5 minutes


**Data Privacy:** All AI inference happens within AWS Bedrock in eu-west-3. Your prompts never leave AWS and are not used for model training.

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
- `list_application_users` - View app assignments
- `assign_user_to_application` - Assign users to apps (admin only)

#### Policy & Audit
- `list_policies` - View authentication policies
- `get_policy` - Get policy details
- `get_logs` - Query system audit logs with filters
- `check_permissions` - View granted OAuth scopes

### Infrastructure
- **Terraform-managed AWS deployment** (VPC, EC2, Secrets Manager, IAM)
- **Docker-based services** with Watchtower auto-updates
- **Dual MCP servers:** Admin (full access) and Readonly (safe queries)
- **Auth gateway layer:** Okta OAuth + StrongDM integration
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
bash
# Get instance IP
terraform output instance_public_ip

# SSH into instance
ssh -i ~/.ssh/your-key.pem ec2-user@<INSTANCE_IP>

# Check all services
docker ps

# Should see all containers as (healthy):
# - okta-mcp-admin
# - okta-mcp-readonly
# - okta-mcp-gateway-admin
# - okta-mcp-gateway-readonly
# - litellm-proxy
# - grafana
# - loki
# - promtail
# - watchtower

Test Gateway Endpoints
bash
# Test admin gateway health
curl http://localhost:9001/health

# Test readonly gateway health
curl http://localhost:9000/health

# Test LiteLLM
export LITELLM_KEY=$(terraform output -raw litellm_master_key)
curl http://localhost:4000/v1/models \
  -H "Authorization: Bearer $LITELLM_KEY"
5. Connect Roo/Claude Desktop
Option A: Via StrongDM (Recommended)

Configure StrongDM to proxy the gateway endpoints, then use the StrongDM URLs in your client config.

Option B: Via SSH Tunnel

bash
ssh -L 9001:localhost:9001 -L 9000:localhost:9000 \
  -i ~/.ssh/your-key.pem ec2-user@<INSTANCE_IP> -N
Configure Roo (VS Code settings.json):

json
{
  "roo-code.mcpServers": {
    "okta-admin": {
      "transport": {
        "type": "sse",
        "url": "http://localhost:9001/sse"
      }
    },
    "okta-readonly": {
      "transport": {
        "type": "sse",
        "url": "http://localhost:9000/sse"
      }
    }
  }
}

🔧 Configuration
Okta OAuth 2.0 Setup
Create three OAuth 2.0 API Services applications in Okta:

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

3. Gateway OAuth App
Grant Type: Authorization Code
Scopes:

openid

profile

email

groups

Redirect URI: https://okta-gateway.your-domain.com/oauth/callback

Generate private keys for apps 1 & 2 and add to terraform.tfvars.

AWS Bedrock Setup
Enable AWS Bedrock in eu-west-3

Subscribe to Claude Sonnet 4.5 in AWS Marketplace

Request model access in Bedrock console

Ensure IAM role has bedrock:InvokeModel permission

LiteLLM Configuration
The deployment includes these Bedrock models (configured in litellm-config.yaml):

text
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

Gateway authentication layer - Okta OAuth + StrongDM integration

IAM role-based access - EC2 instance uses IAM for AWS services

VPC isolation - EC2 in private subnet with NAT gateway

Security groups - Restricted inbound access (SSH + gateway ports only)

Data residency - All AI processing stays in AWS eu-west-3

Auto-updates - Watchtower keeps containers current with security patches

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
docker inspect okta-mcp-admin | jq '..State.Health'

# Test gateway endpoints
curl http://localhost:9001/health
curl http://localhost:9000/health
🐛 Troubleshooting
MCP Server Connection Failed
Verify gateway is running: docker ps | grep gateway

Check gateway health: curl http://localhost:9001/health

View gateway logs: docker logs okta-mcp-gateway-admin

Test MCP server directly: curl http://localhost:8080/sse

Verify authentication headers are being passed

Container Shows "unhealthy"
Check healthcheck logs:

bash
docker inspect okta-mcp-admin | jq '..State.Health.Log[-1]'
Verify curl is installed in container:

bash
docker exec okta-mcp-admin which curl
Test healthcheck command manually:

bash
docker exec okta-mcp-admin curl -f http://localhost:8080/sse
Watchtower Not Updating Images
Check Watchtower logs: docker logs watchtower

Verify containers have label: docker inspect okta-mcp-admin | grep watchtower.enable

Manually trigger update: docker restart watchtower

Check Docker Hub for new images: docker pull blackstaa/okta-mcp-server:latest

LiteLLM Bedrock Errors
Error: "Not subscribed to Bedrock model"

Subscribe to Claude Sonnet 4.5 in AWS Marketplace

Wait 2-3 minutes for subscription to propagate

Error: "AccessDeniedException"

Check IAM role has bedrock:InvokeModel permission

Verify model access enabled in Bedrock console

Confirm correct AWS region (eu-west-3)

Okta Authentication Failed
Verify credentials in Secrets Manager:

bash
aws secretsmanager get-secret-value --secret-id okta-mcp-admin-key
Check private key format (must include \n for newlines)

Verify OAuth scopes in Okta application

Test OAuth token generation:

bash
docker logs okta-mcp-admin | grep "OAuth"
🔄 Updates and Maintenance
Auto-Updates via Watchtower
Watchtower automatically checks for new Docker images every 5 minutes and updates containers with the label com.centurylinklabs.watchtower.enable=true.

Monitored images:

blackstaa/okta-mcp-server:latest (admin + readonly servers)

blackstaa/okta-mcp-gateway:latest (admin + readonly gateways)

To deploy updates:

Build and push new Docker image to Docker Hub

Wait up to 5 minutes for Watchtower to detect and apply update

Verify update: docker ps (check container "Created" time)

Manual Updates
bash
ssh -i ~/.ssh/your-key.pem ec2-user@<INSTANCE_IP>

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
# Make changes to Terraform files
terraform plan
terraform apply

# For user-data.sh changes, recreate instance:
terraform taint aws_instance.okta_mcp
terraform apply
📁 Project Structure
text
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
│   ├── okta_mcp_server/
│   │   ├── server.py              # MCP server entrypoint
│   │   ├── oauth_jwt_client.py    # Okta OAuth client
│   │   └── tools/                 # MCP tool implementations
│   │       ├── users/
│   │       │   ├── users.py       # User read operations
│   │       │   └── users_admin.py # User write + attribute search
│   │       ├── groups/            # Group operations
│   │       ├── applications/      # App operations
│   │       └── policies/          # Policy operations
│   └── gateway/
│       ├── gateway.py             # FastAPI auth gateway
│       └── Dockerfile             # Gateway container image
├── Dockerfile                     # MCP server container image
├── docker-compose.yml             # Service orchestration (in user-data.sh)
├── user-data.sh                   # EC2 initialization script
├── litellm-config.yaml            # LiteLLM model configuration
├── loki-config.yaml               # Loki log aggregation config
├── promtail-config.yaml           # Promtail log collection config
└── README.md                      # This file
💰 Cost Estimate
AWS Resources (eu-west-3):

EC2 t3.medium: ~$30/month

NAT Gateway: ~$32/month

EBS storage (30GB): ~$3/month

Secrets Manager (5 secrets): ~$2/month

Data transfer: Variable (~$5-10/month)

AWS Bedrock Claude Sonnet 4.5: Pay-per-use

Input: $3 per million tokens

Output: $15 per million tokens

Total: ~$72-77/month + Bedrock usage

Typical usage costs:

Light use (100k tokens/month): ~$75/month

Moderate use (1M tokens/month): ~$90/month

Heavy use (10M tokens/month): ~$200/month

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