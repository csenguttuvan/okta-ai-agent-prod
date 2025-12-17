#!/bin/bash
set -e

exec > >(tee /var/log/user-data.log)
exec 2>&1

echo "🚀 Starting Okta MCP Server + LiteLLM deployment..."

# Update system
yum update -y

# Install dependencies
yum install -y docker aws-cli jq || echo "docker/aws-cli/jq already installed, continuing"

# Install Docker Compose v2
DOCKER_COMPOSE_VERSION="v2.24.0"
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL "https://github.com/docker/compose/releases/download/$${DOCKER_COMPOSE_VERSION}/docker-compose-linux-x86_64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# Start Docker
systemctl start docker
systemctl enable docker
usermod -a -G docker ec2-user

# Create application directory
mkdir -p /opt/okta-litellm/{keys,litellm-data}
cd /opt/okta-litellm

echo "🔐 Fetching secrets from AWS Secrets Manager..."

# Fetch readonly private key
aws secretsmanager get-secret-value \
  --secret-id ${readonly_secret_id} \
  --region ${aws_region} \
  --query SecretString \
  --output text > keys/readonly_private_key.pem
chmod 444 keys/readonly_private_key.pem
echo "✅ Readonly private key retrieved"

# Fetch admin private key
aws secretsmanager get-secret-value \
  --secret-id ${admin_secret_id} \
  --region ${aws_region} \
  --query SecretString \
  --output text > keys/admin_private_key.pem
chmod 444 keys/admin_private_key.pem
echo "✅ Admin private key retrieved"

# Fetch LiteLLM keys
LITELLM_MASTER_KEY=$(aws secretsmanager get-secret-value \
  --secret-id ${litellm_master_secret_id} \
  --region ${aws_region} \
  --query SecretString \
  --output text)
echo "✅ LiteLLM master key retrieved"

LITELLM_ADMIN_KEY=$(aws secretsmanager get-secret-value \
  --secret-id ${litellm_admin_secret_id} \
  --region ${aws_region} \
  --query SecretString \
  --output text)
echo "✅ LiteLLM admin team key retrieved"

LITELLM_READER_KEY=$(aws secretsmanager get-secret-value \
  --secret-id ${litellm_reader_secret_id} \
  --region ${aws_region} \
  --query SecretString \
  --output text)
echo "✅ LiteLLM reader team key retrieved"

# Create .env file
cat > .env << EOF
LITELLM_MASTER_KEY=$LITELLM_MASTER_KEY
LITELLM_ADMIN_KEY=$LITELLM_ADMIN_KEY
LITELLM_READER_KEY=$LITELLM_READER_KEY
OKTA_API_BASE_URL=${okta_api_base_url}
OKTA_ADMIN_CLIENT_ID=${okta_admin_client_id}      # ✅ CORRECT
OKTA_ADMIN_SCOPES=${okta_admin_scopes}            # ✅ CORRECT  
OKTA_READONLY_CLIENT_ID=${okta_readonly_client_id}  # ✅ CORRECT
OKTA_READONLY_SCOPES=${okta_readonly_scopes}       
OKTA_LOG_LEVEL=INFO
DOCKER_IMAGE=${docker_image}
EOF

chmod 600 .env

# Create docker-compose.yml
cat > docker-compose.yml << 'COMPOSE'
version: '3.8'

services:
  okta-mcp-admin:
    image: blackstaa/okta-mcp-server:latest
    container_name: okta-mcp-admin
    network_mode: "host"
    volumes:
      - ./keys:/app/keys:ro
    env_file:
      - .env
    environment:
      - OKTA_PRIVATE_KEY_PATH=/app/keys/admin_private_key.pem
      - OKTA_CLIENT_ID=${okta_admin_client_id}
      - OKTA_SCOPES=${okta_admin_scopes}
      - MCP_TRANSPORT=sse
      - MCP_PORT=8080
      - MCP_HOST=0.0.0.0
      - MCP_SERVER_NAME=okta-admin
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/sse"]
      interval: 5s
      timeout: 3s
      retries: 3

  okta-mcp-readonly:
    image: blackstaa/okta-mcp-server:latest
    container_name: okta-mcp-readonly
    network_mode: "host"
    volumes:
      - ./keys:/app/keys:ro
    env_file:
      - .env
    environment:
      - OKTA_PRIVATE_KEY_PATH=/app/keys/readonly_private_key.pem
      - OKTA_CLIENT_ID=${okta_readonly_client_id}
      - OKTA_SCOPES=${okta_readonly_scopes}
      - MCP_TRANSPORT=sse
      - MCP_PORT=8081
      - MCP_HOST=0.0.0.0
      - MCP_SERVER_NAME=okta-readonly
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8081/sse"]
      interval: 5s
      timeout: 3s
      retries: 3

  litellm:
    image: ghcr.io/berriai/litellm:main-latest
    container_name: litellm-proxy
    network_mode: "host"
    volumes:
      - ./litellm-config.yaml:/app/config.yaml:ro
      - ./litellm-data:/app/data
    env_file:
      - .env
    environment:
      - PORT=4000
    command: ["--config", "/app/config.yaml", "--port", "4000", "--num_workers", "1"]
    restart: unless-stopped

COMPOSE

# Create LiteLLM config
cat > litellm-config.yaml << EOF
model_list:
  - model_name: bedrock-claude
    litellm_params:
      model: bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0
      aws_region_name: ${aws_region}


litellm_settings:
  master_key: \$LITELLM_MASTER_KEY
  drop_params: true

teams:
  - team_id: okta_admins
    team_alias: "Okta Administrators"
    members_with_roles:
      - role: admin
        key: \$LITELLM_ADMIN_KEY
    metadata:
      allowed_mcp_servers: ["okta_admin", "okta_readonly"]
      
  - team_id: okta_readers
    team_alias: "Okta Read-Only Users"
    members_with_roles:
      - role: user
        key: \$LITELLM_READER_KEY
    metadata:
      allowed_mcp_servers: ["okta_readonly"]

general_settings:
  store_model_in_db: true
  json_logs: true
EOF

# Create systemd service
cat > /etc/systemd/system/okta-litellm.service << 'SYSTEMD'
[Unit]
Description=Okta MCP + LiteLLM Stack
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/okta-litellm
ExecStart=/usr/local/lib/docker/cli-plugins/docker-compose up -d
ExecStop=/usr/local/lib/docker/cli-plugins/docker-compose down
ExecReload=/usr/local/lib/docker/cli-plugins/docker-compose restart

[Install]
WantedBy=multi-user.target
SYSTEMD

# Start services
systemctl daemon-reload
systemctl enable okta-litellm
systemctl start okta-litellm

echo "⏳ Waiting for services to start..."
sleep 30

INSTANCE_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)

# Create README
cat > /home/ec2-user/README.txt << EOF
# Okta MCP + LiteLLM Server

Instance IP: $INSTANCE_IP

## Access LiteLLM
URL: http://$INSTANCE_IP:4000

Master Key: $LITELLM_MASTER_KEY
Admin Team Key: $LITELLM_ADMIN_KEY
Reader Team Key: $LITELLM_READER_KEY

## SSH Tunnel (Recommended)
ssh -L 4000:localhost:4000 -i ~/.ssh/${key_name}.pem ec2-user@$INSTANCE_IP

Then access: http://localhost:4000

## Check Services
cd /opt/okta-litellm
docker ps
docker compose logs -f

## Health Checks
curl http://localhost:4000/health
curl http://localhost:8080/  # Admin
curl http://localhost:8081/  # Readonly
EOF

chown ec2-user:ec2-user /home/ec2-user/README.txt

echo "✅ Deployment complete!"
echo "🔗 LiteLLM: http://$INSTANCE_IP:4000"
