#!/bin/bash
set -e

yum update -y
yum install -y docker aws-cli jq

systemctl start docker
systemctl enable docker
usermod -aG docker ec2-user

# Pull MCP image
docker pull blackstaa/okta-mcp-server:prod

# Fetch secrets from Secrets Manager
aws secretsmanager get-secret-value \
  --secret-id ${secrets_arn} \
  --region ${aws_region} \
  --query SecretString \
  --output text | jq -r 'to_entries[] | "\(.key)=\(.value)"' > /etc/okta-mcp.env

chmod 600 /etc/okta-mcp.env

# Note: MCP server runs on-demand when Claude connects via SSH
# No systemd service needed - Docker container starts per connection
echo "MCP server setup complete. Connect via SSH to use."
