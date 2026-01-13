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

echo "📦 Setting up persistent Grafana storage..."
DEVICE="/dev/xvdf"
MOUNT_POINT="/opt/okta-litellm/grafana-data"

# Wait for device to be available (up to 30 seconds)
COUNTER=0
while [ ! -b "$DEVICE" ] && [ $COUNTER -lt 30 ]; do
  echo "Waiting for EBS volume $DEVICE to attach..."
  sleep 1
  COUNTER=$((COUNTER+1))
done

if [ -b "$DEVICE" ]; then
  echo "✅ EBS volume $DEVICE found"
  
  # Check if filesystem exists
  if ! blkid "$DEVICE" | grep -q 'TYPE="ext4"'; then
    echo "📝 Creating ext4 filesystem on $DEVICE"
    mkfs -t ext4 "$DEVICE"
  else
    echo "✅ Filesystem already exists on $DEVICE"
  fi
  
  # Create mount point
  mkdir -p "$MOUNT_POINT"
  
  # Mount the volume
  mount "$DEVICE" "$MOUNT_POINT"
  
  # Set correct permissions for Grafana (UID 472)
  chown -R 472:472 "$MOUNT_POINT"
  chmod 755 "$MOUNT_POINT"
  
  # Add to fstab for automatic mounting on reboot
  if ! grep -q "$DEVICE" /etc/fstab; then
    echo "$DEVICE $MOUNT_POINT ext4 defaults,nofail 0 2" >> /etc/fstab
  fi
  
  echo "✅ Grafana data volume mounted at $MOUNT_POINT"
else
  echo "⚠️  EBS volume not found, using host directory"
  mkdir -p "$MOUNT_POINT"
  chown -R 472:472 "$MOUNT_POINT"
fi


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


GATEWAY_SESSION_SECRET=$(aws secretsmanager get-secret-value \
  --secret-id ${gateway_session_secret_id} \
  --region ${aws_region} \
  --query SecretString \
  --output text)
echo "✅ Gateway session secret retrieved"

GATEWAY_INTERNAL_AUTH_TOKEN=$(aws secretsmanager get-secret-value \
  --secret-id ${gateway_internal_auth_secret_id} \
  --region ${aws_region} \
  --query SecretString \
  --output text)
echo "✅ Gateway internal auth token retrieved"

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
GATEWAY_SESSION_SECRET=$GATEWAY_SESSION_SECRET
GATEWAY_INTERNAL_AUTH_TOKEN=$GATEWAY_INTERNAL_AUTH_TOKEN
EOF

chmod 600 .env

# Create .env.gateway.readonly file
cat > .env.gateway.readonly << EOF
OKTA_CLIENT_ID=${okta_gateway_client_id}
OKTA_ISSUER=${okta_issuer}
GATEWAY_PORT=9000
SESSION_SECRET=$GATEWAY_SESSION_SECRET
REDIRECT_URI=${gateway_redirect_uri}
INTERNAL_AUTH_TOKEN=$GATEWAY_INTERNAL_AUTH_TOKEN
ACCESS_LEVEL=readonly
MCP_READONLY_URL=http://127.0.0.1:8081
EOF

chmod 600 .env.gateway.readonly

# Create .env.gateway.admin file
cat > .env.gateway.admin << EOF
OKTA_CLIENT_ID=${okta_gateway_client_id}
OKTA_ISSUER=${okta_issuer}
GATEWAY_PORT=9001
SESSION_SECRET=$GATEWAY_SESSION_SECRET
REDIRECT_URI=${gateway_redirect_uri}
INTERNAL_AUTH_TOKEN=$GATEWAY_INTERNAL_AUTH_TOKEN
ACCESS_LEVEL=admin
MCP_ADMIN_URL=http://127.0.0.1:8080
EOF

chmod 600 .env.gateway.admin


# Create Loki data directories with correct permissions
mkdir -p /opt/okta-litellm/{loki-data,loki-wal}
chown -R 10001:10001 /opt/okta-litellm/{loki-data,loki-wal}
chmod -R 755 /opt/okta-litellm/{loki-data,loki-wal}


# Create docker-compose.yml
cat > docker-compose.yml << 'COMPOSE'
version: '3.8'

networks:
  logging:
    driver: bridge

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
      test: ["CMD-SHELL", "curl -f --silent --max-time 2 http://localhost:8080/sse | head -c 1 > /dev/null"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    labels:
      - "com.centurylinklabs.watchtower.enable=true"

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
      test: ["CMD-SHELL", "curl -f --silent --max-time 2 http://localhost:8081/sse | head -c 1 > /dev/null"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    labels:
     - "com.centurylinklabs.watchtower.enable=true"
  
  watchtower:
    image: containrrr/watchtower
    container_name: watchtower
    restart: unless-stopped
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - WATCHTOWER_CLEANUP=true              # Remove old images
      - WATCHTOWER_INCLUDE_STOPPED=true      # Update stopped containers
      - WATCHTOWER_POLL_INTERVAL=300         # Check every 5 minutes
      - WATCHTOWER_LABEL_ENABLE=true         # Only update labeled containers

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
      - LITELLM_LOG=DEBUG
    command: ["--config", "/app/config.yaml", "--port", "4000", "--num_workers", "1"]
    restart: unless-stopped
  
  loki:
    image: grafana/loki:2.9.0
    container_name: loki
    user: "10001:10001"
    command: -config.file=/etc/loki/config/loki-config.yaml
    volumes:
      - ./loki-config.yaml:/etc/loki/config/loki-config.yaml:ro
      - ./loki-data:/loki
      - ./loki-wal:/wal
    ports:
      - "3100:3100"
    networks:
      - logging
    restart: unless-stopped

  promtail:
    image: grafana/promtail:2.9.0
    container_name: promtail
    command: -config.file=/etc/promtail/config/promtail-config.yaml
    volumes:
      - ./promtail-config.yaml:/etc/promtail/config/promtail-config.yaml:ro
      - /var/log:/var/log:ro
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
    networks:
      - logging
    restart: unless-stopped

  grafana:
    image: grafana/grafana:10.4.0
    container_name: grafana
    user: "472:472"
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - ./grafana-data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
    networks:
      - logging
    restart: unless-stopped

  okta-mcp-gateway-readonly:
    image: blackstaa/okta-mcp-gateway:latest
    container_name: okta-mcp-gateway-readonly
    network_mode: "host"
    env_file: .env.gateway.readonly
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "curl -f --silent --max-time 2 http://localhost:9000/health | head -c 1 > /dev/null"]
      interval: 30s
      timeout: 5s
      retries: 3
    labels:
      - "com.centurylinklabs.watchtower.enable=true"

  okta-mcp-gateway-admin:
    image: blackstaa/okta-mcp-gateway:latest
    container_name: okta-mcp-gateway-admin
    network_mode: "host"
    env_file: .env.gateway.admin
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "curl -f --silent --max-time 2 http://localhost:9001/health | head -c 1 > /dev/null"]
      interval: 30s
      timeout: 5s
      retries: 3
    labels:
      - "com.centurylinklabs.watchtower.enable=true"

COMPOSE

# Create LiteLLM config
cat > litellm-config.yaml << EOF
model_list:
  # Claude 4.5 Sonnet
  - model_name: bedrock-sonnet
    litellm_params:
      model: bedrock/eu.anthropic.claude-sonnet-4-5-20250929-v1:0
      aws_region_name: ${aws_region}

  # Claude 4.5 Haiku (fast, cheap)
  - model_name: bedrock-haiku
    litellm_params:
      model: bedrock/eu.anthropic.claude-haiku-4-5-20251001-v1:0
      aws_region_name: ${aws_region}

  # Llama 3.1 70B (open source)
  - model_name: bedrock-llama
    litellm_params:
      model: bedrock/eu.meta.llama3-1-3b-instruct-v1:0
      aws_region_name: ${aws_region}
      max_tokens: 4000
  
  # Mistral Large
  - model_name: bedrock-mistral
    litellm_params:
      model: bedrock/eu.mistral.mistral-large-2402-v1:0
      aws_region_name: ${aws_region}
      max_tokens: 8000

litellm_settings:
  master_key: \$LITELLM_MASTER_KEY
  drop_params: true
  success_callback: ["stdout"]
  failure_callback: ["stdout"]
  set_verbose: true

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
  disable_spend_logs: false
  store_prompts_in_spend_logs: true
EOF


# Create Loki config
cat > loki-config.yaml << 'EOF_LOKI'
auth_enabled: false

server:
  http_listen_port: 3100
  grpc_listen_port: 9095

ingester:
  lifecycler:
    address: 127.0.0.1
    ring:
      kvstore:
        store: inmemory
      replication_factor: 1
    final_sleep: 0s
  chunk_idle_period: 5m
  chunk_block_size: 262144
  chunk_retain_period: 30s
  max_transfer_retries: 0

schema_config:
  configs:
    - from: 2020-10-24
      store: boltdb-shipper
      object_store: filesystem
      schema: v11
      index:
        prefix: index_
        period: 24h

storage_config:
  boltdb_shipper:
    active_index_directory: /loki/index
    cache_location: /loki/index_cache
    shared_store: filesystem
  filesystem:
    directory: /loki/chunks

compactor:
  working_directory: /loki/compactor
  shared_store: filesystem

limits_config:
  ingestion_rate_mb: 32
  ingestion_burst_size_mb: 64
  max_query_series: 100000
  max_query_length: 48h
  max_entries_limit_per_query: 10000

chunk_store_config:
  max_look_back_period: 0s

table_manager:
  retention_deletes_enabled: true
  retention_period: 168h  # 7 days
EOF_LOKI

# Create Promtail config
cat > promtail-config.yaml << 'EOF_PROMTAIL'
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: docker
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
        refresh_interval: 5s
    relabel_configs:
      # UNCONDITIONAL STATIC LABELS - ALWAYS EXIST
      - target_label: job
        replacement: docker
      - target_label: cluster  
        replacement: okta-litellm
      - target_label: host
        replacement: ec2-instance
      # Container metadata (safe fallbacks)
      - source_labels: ['__meta_docker_container_name']
        regex: '/(.*)'
        target_label: container_name
        action: replace
      - source_labels: ['__meta_docker_container_id']
        target_label: container_id
        action: replace
EOF_PROMTAIL




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



