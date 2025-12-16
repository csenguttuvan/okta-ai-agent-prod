# Okta MCP Server with AWS Infrastructure

A complete Model Context Protocol (MCP) server implementation for Okta management, deployed on AWS with LiteLLM proxy for Claude 3.5 Sonnet integration via AWS Bedrock.

## 🏗️ Architecture

```
Claude Desktop (Local Machine)
    ↓ SSH Tunnel (ports 8080/8081)
EC2 Instance (AWS us-east-1)
    ├─ MCP Admin Server (port 8080) - Full read/write access
    ├─ MCP Readonly Server (port 8081) - Read-only access
    └─ LiteLLM Proxy (port 4000) - AWS Bedrock Claude 3.5 Sonnet
```

**Data Privacy:** All AI inference happens within AWS Bedrock in us-east-1. Your prompts never leave AWS and are not used for model training.

## ✨ Features

### Okta Management Tools
- **Users:** Create, list, search, deactivate, and delete users
- **Groups:** Manage groups, members, and assignments
- **Applications:** List and manage Okta applications
- **Policies:** View and manage authentication policies
- **System Logs:** Query audit logs with filters

### Infrastructure
- **Terraform-managed AWS deployment** (VPC, EC2, Secrets Manager, IAM)
- **Two MCP servers:** Admin (full access) and Readonly (safe queries)
- **LiteLLM API Gateway:** OpenAI-compatible API for AWS Bedrock
- **OAuth 2.0 JWT authentication** with Okta private key
- **Automated deployment** via user-data script

## 🚀 Quick Start

### Prerequisites

- AWS CLI configured with credentials
- Terraform >= 1.0
- Okta account with OAuth 2.0 application
- SSH key pair for EC2 access

### 1. Clone and Configure

```bash
git clone <your-repo-url>
cd okta-mcp-aws

# Copy and configure variables
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`:
```hcl
aws_region          = "us-east-1"
project_name        = "okta-mcp"
key_name            = "your-key-name"
okta_domain         = "your-domain.okta.com"
okta_client_id      = "your-client-id"
okta_private_key    = "-----BEGIN RSA PRIVATE KEY-----\n..."
litellm_master_key  = "sk-YOUR-SECURE-KEY"
```

### 2. Deploy Infrastructure

```bash
terraform init
terraform plan
terraform apply
```

### 3. Verify Deployment

```bash
# Get instance IP
terraform output instance_public_ip

# SSH into instance
ssh -i ~/.ssh/your-key.pem ec2-user@<INSTANCE_IP>

# Check services
sudo systemctl status okta-mcp-admin
sudo systemctl status okta-mcp-readonly
sudo systemctl status litellm
```

### 4. Test LiteLLM Proxy

```bash
export LITELLM_KEY=$(terraform output -raw litellm_master_key)

curl http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $LITELLM_KEY" \
  -d '{
    "model": "bedrock-claude",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### 5. Connect Claude Desktop

**Create SSH tunnel:**
```bash
ssh -L 8080:localhost:8080 -L 8081:localhost:8081 \
  -i ~/.ssh/your-key.pem ec2-user@<INSTANCE_IP> -N
```

**Configure Claude Desktop:**

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "okta-admin": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "http://localhost:8080/sse"
      ]
    },
    "okta-readonly": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "http://localhost:8081/sse"
      ]
    }
  }
}
```

**Restart Claude Desktop** and look for the MCP icon (🔨).

## 📋 Available MCP Tools

### Admin Server (Read/Write)
- `create_user` - Create new Okta users
- `deactivate_user` - Deactivate existing users
- `delete_user` - Delete users (must be deactivated first)
- `list_users` - List all users with pagination
- `search_users` - Search users by query
- `get_user` - Get detailed user information
- Plus all readonly tools

### Readonly Server (Safe Queries)
- `list_users` - View all users
- `get_user` - Get user details
- `search_users` - Search for users
- `list_groups` - View all groups
- `get_group` - Get group details
- `list_group_members` - View group membership
- `list_applications` - View applications
- `get_application` - Get app details
- `list_policies` - View authentication policies
- `get_system_logs` - Query audit logs

## 🔧 Configuration

### Okta OAuth 2.0 Setup

1. In Okta Admin Console, create a new **API Services** application
2. Grant required scopes:
   - `okta.users.read`
   - `okta.users.manage` (admin server only)
   - `okta.groups.read`
   - `okta.apps.read`
   - `okta.policies.read`
   - `okta.logs.read`
3. Generate a private key and save it
4. Add the private key to `terraform.tfvars` (escape newlines with `\n`)

### AWS Bedrock Setup

1. Enable AWS Bedrock in us-east-1
2. Subscribe to Claude 3.5 Sonnet in AWS Marketplace
3. Request model access in Bedrock console
4. Ensure IAM role has `bedrock:InvokeModel` permission

### LiteLLM Configuration

Edit `litellm-config.yaml` to add models or change settings:

```yaml
model_list:
  - model_name: bedrock-claude
    litellm_params:
      model: bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0
      aws_region_name: us-east-1

general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
```

## 🔐 Security

- **Secrets in AWS Secrets Manager** - No hardcoded credentials
- **Private key JWT authentication** - More secure than API tokens
- **IAM role-based access** - EC2 instance uses IAM for AWS services
- **VPC isolation** - EC2 in private subnet with NAT gateway
- **Security groups** - Restricted inbound access (SSH only)
- **Data residency** - All AI processing stays in AWS us-east-1

## 📊 Monitoring

### Check Service Logs

```bash
# Admin server
sudo journalctl -u okta-mcp-admin -f

# Readonly server
sudo journalctl -u okta-mcp-readonly -f

# LiteLLM
sudo journalctl -u litellm -f
```

### CloudWatch Integration

Logs are automatically sent to CloudWatch Logs (configured in user-data.sh).

## 🐛 Troubleshooting

### MCP Server Connection Failed

1. Verify SSH tunnel is running
2. Check server status: `sudo systemctl status okta-mcp-admin`
3. View logs: `sudo journalctl -u okta-mcp-admin -n 50`
4. Test endpoint: `curl http://localhost:8080/health`

### LiteLLM Bedrock Errors

**Error: "Not subscribed to Bedrock model"**
- Subscribe to Claude 3.5 Sonnet in AWS Marketplace
- Wait 2-3 minutes for subscription to propagate

**Error: "AccessDeniedException"**
- Check IAM role has `bedrock:InvokeModel` permission
- Verify model access enabled in Bedrock console

### Okta Authentication Failed

1. Verify credentials in Secrets Manager:
   ```bash
   aws secretsmanager get-secret-value --secret-id okta-mcp/credentials
   ```
2. Check private key format (must include `\n` for newlines)
3. Verify OAuth scopes in Okta application

## 🔄 Updates and Maintenance

### Update MCP Servers

```bash
ssh -i ~/.ssh/your-key.pem ec2-user@<INSTANCE_IP>

# Update admin server
cd /home/ec2-user/okta-mcp-admin
git pull
pip install -e .
sudo systemctl restart okta-mcp-admin

# Update readonly server
cd /home/ec2-user/okta-mcp-server
git pull
pip install -e .
sudo systemctl restart okta-mcp-readonly
```

### Update Infrastructure

```bash
# Make changes to .tf files
terraform plan
terraform apply
```

## 📁 Project Structure

```
.
├── main.tf                    # Main infrastructure
├── vpc.tf                     # VPC and networking
├── iam.tf                     # IAM roles and policies
├── secrets.tf                 # Secrets Manager resources
├── security_groups.tf         # Security group rules
├── outputs.tf                 # Terraform outputs
├── variables.tf               # Input variables
├── terraform.tfvars           # Your configuration (gitignored)
├── user-data.sh               # EC2 initialization script
├── litellm-config.yaml        # LiteLLM configuration
└── README.md                  # This file
```

## 💰 Cost Estimate

**AWS Resources (us-east-1):**
- EC2 t3.medium: ~$30/month
- NAT Gateway: ~$32/month
- EBS storage (20GB): ~$2/month
- Secrets Manager: ~$1/month
- Data transfer: Variable
- **AWS Bedrock Claude 3.5 Sonnet:** Pay-per-use (~$3 per million input tokens)

**Total:** ~$65-75/month + Bedrock usage

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📝 License

MIT License - See LICENSE file for details

## 🙏 Acknowledgments

- [Model Context Protocol](https://modelcontextprotocol.io/) by Anthropic
- [LiteLLM](https://github.com/BerriAI/litellm) by BerriAI
- [Okta Management API](https://developer.okta.com/docs/reference/)
- [AWS Bedrock](https://aws.amazon.com/bedrock/)

## 📞 Support

For issues and questions:
- Open a GitHub issue
- Check [MCP documentation](https://modelcontextprotocol.io/)
- Review [AWS Bedrock docs](https://docs.aws.amazon.com/bedrock/)

---

**Built with ❤️ for secure, privacy-focused Okta automation**
