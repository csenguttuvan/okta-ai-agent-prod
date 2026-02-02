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
      - ACCESS_LEVEL=admin
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
      - ACCESS_LEVEL=readonly
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
      - ./custom_callbacks.py:/app/custom_callbacks.py:ro

    env_file:
      - .env
    environment:
      - PORT=4000
      - LITELLM_LOG=DEBUG
      - PYTHONPATH=/app

    command: ["--config", "/app/config.yaml", "--port", "4000", "--num_workers", "1"]
    restart: unless-stopped
    depends_on:
      - redis
  
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

  redis:
    image: redis:7-alpine
    container_name: litellm-redis
    ports:
      - "6379:6379"
    volumes:
      - ./redis-data:/data
    command: redis-server --appendonly yes
    restart: unless-stopped
    networks:
      - logging

COMPOSE

# Create LiteLLM config
cat > litellm-config.yaml << EOF
model_list:
  # Claude 4.5 Sonnet
  - model_name: bedrock-sonnet
    litellm_params:
      model: bedrock/eu.anthropic.claude-sonnet-4-5-20250929-v1:0
      aws_region_name: ${aws_region}
      max_tokens: 1200
      
  # Claude 4.5 Haiku (fast, cheap)
  - model_name: bedrock-haiku
    litellm_params:
      model: bedrock/eu.anthropic.claude-haiku-4-5-20251001-v1:0
      aws_region_name: ${aws_region}
      max_tokens: 4000
      
  # Llama 3.1 70B (open source)
  - model_name: bedrock-llamater
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
  modify_params: true
  success_callback: ["stdout"]
  failure_callback: ["stdout"]
  set_verbose: false
  callbacks: custom_callbacks.proxy_handler_instance
  
  # Redis caching
  cache: true
  cache_params:
    type: "redis"
    host: "localhost"
    port: 6379
    ttl: 3600
  
  # Token optimization
  default_max_tokens: 1500
  num_retries: 2
  request_timeout: 30

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
  max_input_tokens: 50000
  stream: true
  enable_compression: true
EOF


cat > /opt/okta-litellm/custom_callbacks.py << 'CALLBACK_EOF'
# custom_callbacks.py - Token-optimized MCP tool filtering
from __future__ import annotations
from typing import Any, Dict, List, Literal, Optional, Set
from litellm.integrations.custom_logger import CustomLogger
from litellm.proxy.proxy_server import DualCache, UserAPIKeyAuth
import re
import copy

SLIM_SYSTEM_PROMPT = """Okta admin with full access via okta-admin MCP. Delete requires deactivate first. Tables for groups/apps, bullets for users.

Available tools:
- Users: find, create, update, deactivate, delete, reactivate
- Groups: list, find, create, update, delete, members  
- Apps: list, get, assign
- Policies: list, get, create, update, delete

Call ONE tool per turn. No assumptions."""

def _extract_tool_name(tool: Any) -> str:
    if not isinstance(tool, dict):
        return ""
    fn = tool.get("function") or {}
    if isinstance(fn, dict):
        n = fn.get("name")
        return n if isinstance(n, str) else ""
    return ""


def _is_okta_mcp(name: str) -> bool:
    return name.startswith("mcp--okta") or name.startswith("mcp__okta")


def _prune_conversation(messages: list, max_history: int = 6) -> list:
    if len(messages) <= max_history + 1:
        return messages
    pruned = []
    if messages and messages[0].get("role") == "system":
        pruned.append(messages[0])
        start_idx = 1
    else:
        start_idx = 0
    recent_messages = messages[-max_history:]
    pruned.extend(recent_messages)
    tokens_saved = len(messages) - len(pruned)
    if tokens_saved > 0:
        print(f"[MCP] 🔪 Pruned {tokens_saved} old messages (kept {len(pruned)})")
    return pruned


def _normalize_plural(text: str) -> str:
    """Normalize plural forms to singular for consistent matching"""
    replacements = {
        "groups": "group",
        "users": "user",
        "apps": "app",
        "applications": "application",
        "policies": "policy",
        "rules": "rule",
        "members": "member",
        "factors": "factor",
        "roles": "role"
    }
    for plural, singular in replacements.items():
        text = text.replace(plural, singular)
    return text


def _extract_latest_user_query(messages: list) -> str:
    """Extract ONLY the most recent user query (multi-turn safe)"""

    # 🔍 DEBUG: Print last 2 user messages to see format
    user_messages = [m for m in messages if m.get("role") == "user"]
    if user_messages:
        last_msg = user_messages[-1]
        print(f"[MCP DEBUG] Last user message content: {str(last_msg.get('content', ''))[:200]}")
    
    last_user_msg = None
    last_tool_msg = None
    
    for msg in reversed(messages):
        if msg.get("role") == "tool" and last_tool_msg is None:
            last_tool_msg = msg
        if msg.get("role") == "user" and last_user_msg is None:
            last_user_msg = msg
        if (last_tool_msg or last_user_msg):
            break
    
    # Priority 1: Check tool message for <feedback>
    if last_tool_msg:
        content = last_tool_msg.get("content", "")
        if isinstance(content, str) and "<feedback>" in content:
            feedback_match = re.search(r'<feedback>(.*?)</feedback>', content, flags=re.DOTALL | re.IGNORECASE)
            if feedback_match:
                query = feedback_match.group(1).strip()
                query = re.sub(r'<[^>]+>', '', query)
                if len(query) > 3:
                    print(f"[MCP] 📋 Extracted from <feedback>: {query[:60]}")
                    return query.lower()
    
    # Priority 2: Extract from last user message
    if last_user_msg:
        content = last_user_msg.get("content", "")
    
        # Handle list format (Roo's standard format)
        if isinstance(content, list):
            # Process blocks in order and return FIRST non-environment match
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text = block.get("text", "")
                
                    # Skip environment_details blocks
                    if "<environment_details>" in text and "</environment_details>" in text:
                        # But check if query is BEFORE environment_details
                        parts = text.split("<environment_details>")
                        if parts[0].strip() and len(parts[0].strip()) > 5:
                            query = parts[0].strip()
                            query = re.sub(r'<[^>]+>', '', query)
                            print(f"[MCP] 📋 Extracted before environment: {query[:60]}")
                            return query.lower()
                        continue
                
                    # Try ALL possible tag formats
                    for tag in ["user_message", "task", "user_query", "query", "instruction"]:
                        pattern = f'<{tag}>(.*?)</{tag}>'
                        match = re.search(pattern, text, flags=re.DOTALL | re.IGNORECASE)
                        if match:
                            query = match.group(1).strip()
                            query = re.sub(r'<[^>]+>', '', query)
                            if len(query) > 3:
                                print(f"[MCP] 📋 Extracted from <{tag}>: {query[:60]}")
                                return query.lower()
                
                    # If no tags found but text is short and meaningful, use it
                    cleaned = re.sub(r'<[^>]+>', '', text).strip()
                    if cleaned and len(cleaned) < 200 and len(cleaned) > 5:
                        # But skip if it's just environment noise
                        if not any(noise in cleaned.lower() for noise in ["vscode", "current time", "iso 8601", "time zone"]):
                            print(f"[MCP] 📋 Extracted from plain text: {cleaned[:60]}")
                            return cleaned.lower()
        
        # Handle string format
        elif isinstance(content, str):
            # Check if query is BEFORE environment_details
            if "<environment_details>" in content:
                parts = content.split("<environment_details>")
                if parts[0].strip() and len(parts[0].strip()) > 5:
                    query = parts[0].strip()
                    query = re.sub(r'<[^>]+>', '', query)
                    print(f"[MCP] 📋 Extracted before environment: {query[:60]}")
                    return query.lower()
            
            # Try ALL possible tag formats
            for tag in ["user_message", "task", "user_query", "query", "instruction"]:
                pattern = f'<{tag}>(.*?)</{tag}>'
                match = re.search(pattern, content, flags=re.DOTALL | re.IGNORECASE)
                if match:
                    query = match.group(1).strip()
                    query = re.sub(r'<[^>]+>', '', query)
                    if len(query) > 3:
                        print(f"[MCP] 📋 Extracted from <{tag}>: {query[:60]}")
                        return query.lower()
            
            # Fallback: strip environment details and extract first meaningful line
            cleaned = re.sub(r'<environment_details>.*?</environment_details>', '', content, flags=re.DOTALL | re.IGNORECASE)
            lines = cleaned.split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if line.startswith('<') and '>' in line:
                    tag_text = re.sub(r'<[^>]+>', '', line)
                    if len(tag_text.strip()) > 3:
                        print(f"[MCP] 📋 Extracted from inline tag: {tag_text[:60]}")
                        return tag_text.strip().lower()
                if line.startswith('#'):
                    continue
                if len(line) > 10:
                    print(f"[MCP] 📋 Extracted from plain text: {line[:60]}")
                    return line.lower()
    
    # Priority 3: Check previous user message (sometimes Roo's query is earlier)
    if len(user_messages) >= 2:
        prev_msg = user_messages[-2]
        content = prev_msg.get("content", "")
        
        if isinstance(content, str) and len(content) > 5 and len(content) < 200:
            # Simple string queries like "remove all users from group"
            cleaned = re.sub(r'<[^>]+>', '', content).strip()
            if cleaned and not any(noise in cleaned.lower() for noise in ["vscode", "current time"]):
                print(f"[MCP] 📋 Extracted from previous message: {cleaned[:60]}")
                return cleaned.lower()
    
    print("[MCP] ⚠️ No query extracted, using defaults")
    return ""

def _compress_tool_response(content: str) -> str:
    """Strip verbose fields from Okta API tool responses"""
    try:
        import json
        data = json.loads(content)
        
        # If it's a list, limit to first 20 items
        if isinstance(data, list) and len(data) > 20:
            truncated_count = len(data) - 20
            data = data[:20]
            data.append({"_truncated": f"... and {truncated_count} more items"})
        
        # Remove verbose Okta fields
        def strip_verbose(obj):
            if isinstance(obj, dict):
                essential = ['id', 'name', 'email', 'status', 'label', 'type', 
                            'description', 'firstName', 'lastName', 'login', 
                            'profile', 'success', 'error', 'message']
                return {k: strip_verbose(v) for k, v in obj.items() if k in essential}
            elif isinstance(obj, list):
                return [strip_verbose(item) for item in obj[:20]]
            return obj
        
        data = strip_verbose(data)
        return json.dumps(data, separators=(',', ':'))
    except:
        if len(content) > 1000:
            return content[:1000] + f"... [truncated {len(content) - 1000} chars]"
        return content

def _get_relevant_tools(messages: list) -> Set[str]:
    msg = _extract_latest_user_query(messages)
    msg = _normalize_plural(msg)  # Normalize plurals to singular

    print(f"[MCP DEBUG] 🔍 Query after normalization: '{msg}'")
    print(f"[MCP DEBUG] 🔍 'delete' in msg: {'delete' in msg}")
    print(f"[MCP DEBUG] 🔍 'user' in msg: {'user' in msg}")
    print(f"[MCP DEBUG] 🔍 'group' not in msg: {'group' not in msg}")
    
    tools = set()
    
    def add_tool(base_name):
        # Try all possible MCP server naming conventions
        tools.add(f"mcp--okta-admin--{base_name}")      # Standard: okta-admin
        tools.add(f"mcp--okta___admin--{base_name}")    # Triple underscore variant
        tools.add(f"mcp--oktaadmin--{base_name}")       # No dash: oktaadmin
        tools.add(f"mcp__okta_admin__{base_name}")      # All underscores
    
    add_tool("check_permissions")
    add_tool("checkpermissions")  # No underscore variant
    
    if not msg or len(msg) < 3:
        add_tool("list_users")
        add_tool("listusers")
        add_tool("list_groups")
        add_tool("listgroups")
        add_tool("list_group_users")
        add_tool("listgroupusers")
        add_tool("find_user")
        add_tool("finduser")
        return tools
    
    attribute_keywords = ["division", "department", "title", "location", "manager", "costcenter", "cost center", "office", "city", "country", "org", "organization", "team", "role", "level", "grade", "profile", "attribute", "property", "field"]
    has_attribute_query = any(kw in msg for kw in attribute_keywords)
    
    # LOGS - Process FIRST to prioritize log queries
    is_log_query = any(w in msg for w in ["log", "logs", "audit", "event", "activity", "history"])
    
    if is_log_query:
        # Try all possible tool name variations
        add_tool("get_logs")           # Standard naming: get_logs
        add_tool("getlogs")            # No underscore variant: getlogs
        add_tool("list_system_logs")   # Alternative naming
        add_tool("listsystemlogs")
        add_tool("system_logs")
        add_tool("systemlogs")
        
        # If asking about logs for a specific user, also include user lookup
        if "user" in msg or any(w in msg for w in ["for", "by", "from", "about"]):
            add_tool("find_user")
            add_tool("finduser")
            add_tool("get_user")
            add_tool("getuser")
        
        return tools  # Return early to prioritize log queries
    
    # USERS
    if "list" in msg and "user" in msg and "group" not in msg and "app" not in msg:
        add_tool("list_users")
        add_tool("listusers")
    if any(w in msg for w in ["search", "find", "lookup", "get", "show", "who has", "user with"]):
        if "user" in msg or has_attribute_query:
            add_tool("find_user")
            add_tool("finduser")
            add_tool("search_users_fuzzy")
            add_tool("searchusersfuzzy")
            add_tool("get_user")
            add_tool("getuser")
            add_tool("search_users")
            add_tool("searchusers")
            if has_attribute_query:
                add_tool("search_users_by_attribute")
                add_tool("searchusersbyattribute")
    if "create" in msg and "user" in msg and "group" not in msg:
        add_tool("create_user")
        add_tool("createuser")
    if ("update" in msg or "modify" in msg or "change" in msg) and "user" in msg:
        add_tool("update_user")
        add_tool("updateuser")
        add_tool("get_user")
        add_tool("getuser")
        add_tool("find_user")
        add_tool("finduser")
    if "deactivate" in msg and "user" in msg:
        add_tool("deactivate_user")
        add_tool("deactivateuser")
        add_tool("find_user")
        add_tool("finduser")
        add_tool("get_user")
        add_tool("getuser")
    if "activate" in msg and "user" in msg:
        add_tool("activate_user")
        add_tool("activateuser")
        add_tool("reactivate_user")
        add_tool("reactivateuser")
        add_tool("find_user")
        add_tool("finduser")
        add_tool("get_user")
        add_tool("getuser")
    if "reactivate" in msg and "user" in msg:
        add_tool("reactivate_user")
        add_tool("reactivateuser")
        add_tool("find_user")
        add_tool("finduser")
        add_tool("get_user")
        add_tool("getuser")
    if "delete" in msg and "user" in msg and "group" not in msg:
        add_tool("delete_user")
        add_tool("deleteuser")
        add_tool("deactivateuser")
        add_tool("deactivate_user")
        add_tool("find_user")
        add_tool("finduser")
        add_tool("get_user")
        add_tool("getuser")
    if any(w in msg for w in ["what group", "which group", "user group", "user's group"]) and "user" in msg:
        add_tool("get_user_groups")
        add_tool("getusergroups")
        add_tool("find_user")
        add_tool("finduser")
        add_tool("get_user")
        add_tool("getuser")    
    if any(w in msg for w in ["reset", "unlock", "mfa", "password", "2fa", "factor"]):
        if "user" in msg or "mfa" in msg or "password" in msg:
            add_tool("reset_user_mfa_and_password")
            add_tool("resetusermfaandpassword")
            add_tool("find_user")
            add_tool("finduser")
    # Batch operations with attribute filtering
    if has_attribute_query and "user" in msg:
        if any(w in msg for w in ["add", "assign"]) and "group" in msg:
            add_tool("add_users_to_group_by_attribute")
            add_tool("adduserstogroupbyattribute")
            add_tool("search_users_by_attribute")
            add_tool("searchusersbyattribute")
            add_tool("search_groups_fuzzy")
            add_tool("searchgroupsfuzzy")
        if any(w in msg for w in ["remove", "unassign"]) and "group" in msg:
            add_tool("remove_users_from_group_by_attribute")
            add_tool("removeusersfromgroupbyattribute")
            add_tool("search_users_by_attribute")
            add_tool("searchusersbyattribute")
            add_tool("search_groups_fuzzy")
            add_tool("searchgroupsfuzzy")
        if any(w in msg for w in ["remove", "unassign"]) and ("app" in msg or "application" in msg):
            add_tool("unassign_users_from_application_by_attribute")
            add_tool("unassignusersfromapplicationbyattribute")
            add_tool("search_users_by_attribute")
            add_tool("searchusersbyattribute")
    
    # GROUPS
    if "list" in msg and "group" in msg and any(w in msg for w in ["user", "member", "in the group", "in group"]):
        add_tool("list_groups")
        add_tool("listgroups")
        add_tool("list_group_users")
        add_tool("listgroupusers")
        add_tool("search_groups_fuzzy")
        add_tool("searchgroupsfuzzy")
        add_tool("get_group")
        add_tool("getgroup")
    elif "list" in msg and "group" in msg:
        add_tool("list_groups")
        add_tool("listgroups")
    if any(w in msg for w in ["search", "find", "lookup", "get", "show"]) and "group" in msg:
        add_tool("search_groups_fuzzy")
        add_tool("searchgroupsfuzzy")
        add_tool("get_group")
        add_tool("getgroup")
        add_tool("list_groups")
        add_tool("listgroups")
    if "create" in msg and "group" in msg:
        add_tool("create_group")
        add_tool("creategroup")
        add_tool("list_groups")
        add_tool("listgroups")
        add_tool("search_groups_fuzzy")
        add_tool("searchgroupsfuzzy")
        if has_attribute_query or any(w in msg for w in ["add all", "add user", "with", "who have"]):
            add_tool("search_users_by_attribute")
            add_tool("searchusersbyattribute")
            add_tool("add_users_to_group_by_attribute")
            add_tool("adduserstogroupbyattribute")
            add_tool("list_group_users")
            add_tool("listgroupusers")
            add_tool("add_user_to_group")
            add_tool("addusertogroup")
            add_tool("list_group_users")
            add_tool("listgroupusers")
            add_tool("find_user")
            add_tool("finduser")
    if ("update" in msg or "modify" in msg or "change" in msg) and "group" in msg:
        add_tool("update_group")
        add_tool("updategroup")
        add_tool("get_group")
        add_tool("getgroup")
        add_tool("search_groups_fuzzy")
        add_tool("searchgroupsfuzzy")
        add_tool("list_groups")
        add_tool("listgroups")
    if "delete" in msg and "group" in msg:
        add_tool("delete_group")
        add_tool("deletegroup")
        add_tool("search_groups_fuzzy")
        add_tool("searchgroupsfuzzy")
        add_tool("get_group")
        add_tool("getgroup")
        add_tool("list_groups")
        add_tool("listgroups")
        # Add preview tool for safety
        if any(w in msg for w in ["preview", "impact", "check", "what", "show"]):
            add_tool("preview_group_deletion_impact")
            add_tool("previewgroupdeletionimpact")
        if any(w in msg for w in ["empty", "member", "clear"]):
            add_tool("list_group_users")
            add_tool("listgroupusers")
            add_tool("remove_users_from_group")
            add_tool("removeusersfromgroup")
    if any(w in msg for w in ["add", "assign", "join"]) and "group" in msg:
        add_tool("add_user_to_group")
        add_tool("addusertogroup")
        add_tool("add_users_to_group")
        add_tool("adduserstogroup")
        add_tool("find_user")  
        add_tool("finduser")
        add_tool("searchgroupsfuzzy")
        add_tool("search_groups_fuzzy")
        add_tool("get_group")
        add_tool("getgroup")
        add_tool("list_groups")
        add_tool("listgroups")
        if has_attribute_query or any(w in msg for w in ["who have", "with", "all user"]):
            add_tool("add_users_to_group_by_attribute")
            add_tool("adduserstogroupbyattribute")
            add_tool("search_users_by_attribute")
            add_tool("searchusersbyattribute")
            add_tool("list_group_users")
            add_tool("listgroupusers")
    if ("remove" in msg or "unassign" in msg) and "group" in msg and "user" in msg:
        add_tool("remove_user_from_group")
        add_tool("removeuserfromgroup")
        add_tool("remove_users_from_group")
        add_tool("removeusersfromgroup")
        add_tool("list_group_users")
        add_tool("listgroupusers")
        add_tool("search_groups_fuzzy")
        add_tool("searchgroupsfuzzy")
        add_tool("get_group")
        add_tool("getgroup")
        add_tool("find_user") 
        add_tool("finduser")   
        if has_attribute_query:
            add_tool("remove_users_from_group_by_attribute")
            add_tool("removeusersfromgroupbyattribute")
            add_tool("search_users_by_attribute")
            add_tool("searchusersbyattribute")

    # Preview group deletion impact (separate condition for clarity)
    if any(w in msg for w in ["preview", "impact", "check", "what happen"]) and "delet" in msg and "group" in msg:
        add_tool("preview_group_deletion_impact")
        add_tool("previewgroupdeletionimpact")
        add_tool("search_groups_fuzzy")
        add_tool("searchgroupsfuzzy")
        add_tool("get_group")
        add_tool("getgroup")
        add_tool("list_groups")
        add_tool("listgroups")
    
    # APPLICATIONS
    if "list" in msg and ("app" in msg or "application" in msg):
        if "user" in msg:
            add_tool("list_application_users")
            add_tool("listapplicationusers")
            add_tool("get_application")
            add_tool("getapplication")
        elif "group" in msg:
            add_tool("list_application_groups")
            add_tool("listapplicationgroups")
            add_tool("get_application")
            add_tool("getapplication")
        else:
            add_tool("list_applications")
            add_tool("listapplications")
    
    if any(w in msg for w in ["get", "show", "find"]) and ("app" in msg or "application" in msg):
        add_tool("get_application")
        add_tool("getapplication")
        add_tool("list_applications")
        add_tool("listapplications")
    if "create" in msg and ("app" in msg or "application" in msg):
        add_tool("create_application")
        add_tool("createapplication")
        add_tool("list_applications")
        add_tool("listapplications")
    if "delete" in msg and ("app" in msg or "application" in msg):
        add_tool("delete_application")
        add_tool("deleteapplication")
        add_tool("get_application")
        add_tool("getapplication")
        add_tool("list_applications")
        add_tool("listapplications")
        
    
    if any(w in msg for w in ["assign", "add", "grant"]) and ("app" in msg or "application" in msg):
        if "group" in msg:
            add_tool("assign_group_to_application")
            add_tool("assigngrouptoapplication")
            add_tool("get_application")
            add_tool("getapplication")
            add_tool("search_groups_fuzzy")
            add_tool("searchgroupsfuzzy")
            add_tool("list_groups")
            add_tool("listgroups")
        if "user" in msg:
            add_tool("assign_user_to_application")
            add_tool("assignusertoapplication")
            add_tool("batch_assign_users_to_application")
            add_tool("batchassignuserstoapplication")
            add_tool("get_application")
            add_tool("getapplication")
            add_tool("find_user")
            add_tool("finduser")
            add_tool("list_applications")
            add_tool("listapplications")
            if any(w in msg for w in ["role", "arn", "aws", "saml"]):
                add_tool("assign_user_to_application_with_role")
                add_tool("assignusertoapplicationwithrole")
                add_tool("list_application_available_roles")
                add_tool("listapplicationavailableroles")
                add_tool("check_role_exists_on_application")
                add_tool("checkroleexistsonapplication")
            if has_attribute_query:
                add_tool("search_users_by_attribute")
                add_tool("searchusersbyattribute")
    if any(w in msg for w in ["unassign", "remove"]) and ("app" in msg or "application" in msg):
        if "user" in msg:
            add_tool("list_application_users")
            add_tool("listapplicationusers")
            add_tool("get_application")
            add_tool("getapplication")
            add_tool("find_user")
            add_tool("finduser")
            if has_attribute_query:
                add_tool("unassign_users_from_application_by_attribute")
                add_tool("unassignusersfromapplicationbyattribute")
                add_tool("search_users_by_attribute")
                add_tool("searchusersbyattribute")
    if ("update" in msg or "change" in msg) and ("role" in msg or "arn" in msg) and ("app" in msg or "application" in msg):
        add_tool("update_user_application_role")
        add_tool("updateuserapplicationrole")
        add_tool("list_application_available_roles")
        add_tool("listapplicationavailableroles")
        add_tool("get_application")
        add_tool("getapplication")
        add_tool("find_user")
        add_tool("finduser")
    if any(w in msg for w in ["list", "show", "available"]) and "role" in msg and ("app" in msg or "application" in msg):
        add_tool("list_application_available_roles")
        add_tool("listapplicationavailableroles")
        add_tool("get_application")
        add_tool("getapplication")
    if "check" in msg and "role" in msg:
        add_tool("check_role_exists_on_application")
        add_tool("checkroleexistsonapplication")
        add_tool("get_application")
        add_tool("getapplication")
    
    # POLICIES
    if "list" in msg and "policy" in msg:
        add_tool("list_policies")
        add_tool("listpolicies")
        if "rule" in msg:
            add_tool("list_policy_rules")
            add_tool("listpolicyrules")
            add_tool("get_policy")
            add_tool("getpolicy")

    if any(w in msg for w in ["get", "show", "find"]) and "policy" in msg:
        add_tool("get_policy")
        add_tool("getpolicy")
        add_tool("list_policies")
        add_tool("listpolicies")

    if "create" in msg and "policy" in msg:
        if "rule" in msg:
            add_tool("create_policy_rule")
            add_tool("createpolicyrule")
            add_tool("get_policy")
            add_tool("getpolicy")
            add_tool("list_policy_rules")
            add_tool("listpolicyrules")
        else:
            add_tool("create_policy")
            add_tool("createpolicy")
            add_tool("list_policies")
            add_tool("listpolicies")

    if "update" in msg and "policy" in msg:
        if "rule" in msg:
            add_tool("update_policy_rule")
            add_tool("updatepolicyrule")
            add_tool("get_policy_rule")
            add_tool("getpolicyrule")
            add_tool("list_policy_rules")
            add_tool("listpolicyrules")
            add_tool("get_policy")
            add_tool("getpolicy")
        else:
            add_tool("update_policy")
            add_tool("updatepolicy")
            add_tool("get_policy")
            add_tool("getpolicy")
            add_tool("list_policies")
            add_tool("listpolicies")

    if "delete" in msg and "policy" in msg:
        if "rule" in msg:
            add_tool("delete_policy_rule")
            add_tool("deletepolicyrule")
            add_tool("get_policy_rule")
            add_tool("getpolicyrule")
            add_tool("list_policy_rules")
            add_tool("listpolicyrules")
            add_tool("get_policy")
            add_tool("getpolicy")
        else:
            add_tool("delete_policy")
            add_tool("deletepolicy")
            add_tool("get_policy")
            add_tool("getpolicy")
            add_tool("list_policies")
            add_tool("listpolicies")

    if "activate" in msg and "policy" in msg:
        if "rule" in msg:
            add_tool("activate_policy_rule")
            add_tool("activatepolicyrule")
            add_tool("get_policy_rule")
            add_tool("getpolicyrule")
            add_tool("get_policy")
            add_tool("getpolicy")
        else:
            add_tool("activate_policy")
            add_tool("activatepolicy")
            add_tool("get_policy")
            add_tool("getpolicy")

    if "deactivate" in msg and "policy" in msg:
        if "rule" in msg:
            add_tool("deactivate_policy_rule")
            add_tool("deactivatepolicyrule")
            add_tool("get_policy_rule")
            add_tool("getpolicyrule")
            add_tool("get_policy")
            add_tool("getpolicy")
        else:
            add_tool("deactivate_policy")
            add_tool("deactivatepolicy")
            add_tool("get_policy")
            add_tool("getpolicy")

    if any(w in msg for w in ["get", "show"]) and "rule" in msg and "policy" in msg:
        add_tool("get_policy_rule")
        add_tool("getpolicyrule")
        add_tool("list_policy_rules")
        add_tool("listpolicyrules")
        add_tool("get_policy")
        add_tool("getpolicy")
    
    # FALLBACK
    if len(tools) == 1:
        add_tool("list_users")
        add_tool("listusers")
        add_tool("list_groups")
        add_tool("listgroups")
        add_tool("list_group_users")
        add_tool("listgroupusers")
        add_tool("find_user")
        add_tool("finduser")
    
    return tools


def _ultra_slim_tool(t: Dict[str, Any]) -> Dict[str, Any]:
    fn = t.get("function", {})
    params = fn.get("parameters", {})
    props = params.get("properties", {})
    required = params.get("required", [])
    minimal_props = {}
    for key, prop in props.items():
        desc = prop.get("description", "").split('.')[0].split('\n')[0][:60].strip()
        minimal_props[key] = {"type": prop.get("type", "string"), "description": desc}
        if prop.get("enum"):
            minimal_props[key]["enum"] = prop["enum"][:]
    func_desc = '.'.join(fn.get("description", "").split('.')[:2]).strip()
    if func_desc and not func_desc.endswith('.'):
        func_desc += '.'
    return {"type": "function", "function": {"name": fn.get("name", ""), "description": func_desc, "parameters": {"type": "object", "properties": minimal_props, "required": required[:] if required else []}}}


class McpOnlyToolsHandler(CustomLogger):
    async def async_pre_call_hook(
        self,
        user_api_key_dict: UserAPIKeyAuth,
        cache: DualCache,
        data: dict,
        call_type: Literal["completion", "embeddings", "image_generation", ...],
    ) -> dict:
        try:
            messages = data.get("messages", [])
            if not messages:
                return data
            
            # 🔧 OPTIMIZATION 1: More aggressive pruning (6 → 4 messages)
            messages = _prune_conversation(messages, max_history=4)
            data["messages"] = messages
            
            # 🔧 OPTIMIZATION 2: Replace verbose system prompt with slim version
            if messages and messages[0].get("role") == "system":
                original_length = len(messages[0].get("content", ""))
                messages[0]["content"] = SLIM_SYSTEM_PROMPT
                new_length = len(SLIM_SYSTEM_PROMPT)
                print(f"[MCP] 📝 Compressed system prompt: {original_length} → {new_length} chars ({original_length - new_length} saved)")
            
            # 🔧 OPTIMIZATION 3: Compress tool responses from previous turns
            # 🔧 OPTIMIZATION 3: DISABLED - Was breaking tool responses
            # for msg in messages:
            #     if msg.get("role") == "tool":
            #         original_content = msg.get("content", "")
            #         if isinstance(original_content, str) and len(original_content) > 500:
            #             compressed = _compress_tool_response(original_content)
            #             if len(compressed) < len(original_content):
            #                 msg["content"] = compressed
            #                 print(f"[MCP] 🗜️  Compressed tool response: {len(original_content)} → {len(compressed)} chars")
            
            # Extract query for tool filtering
            query = _extract_latest_user_query(messages)
            
            # Extract query for tool filtering
            query = _extract_latest_user_query(messages)
            relevant_tools = _get_relevant_tools(messages)
            
            # Deep copy to avoid mutation
            data = copy.deepcopy(data)
            
            # Find where tools are stored
            direct_tools = data.get("tools")
            optional_params = data.get("optional_params")
            optional_tools = optional_params.get("tools") if isinstance(optional_params, dict) else None
            
            container = None
            tools = None
            if isinstance(direct_tools, list):
                container = "data.tools"
                tools = direct_tools
            elif isinstance(optional_tools, list):
                container = "data.optional_params.tools"
                tools = optional_tools
            
            if not tools:
                return data
            
            # Filter tools
            kept = []
            okta_count = 0
            all_okta_tools = []
            matched_okta_tools = []
            
            for t in tools:
                name = _extract_tool_name(t)
                if not _is_okta_mcp(name):
                    kept.append(t)
                    continue
                
                all_okta_tools.append(name)
                
                if name in relevant_tools:
                    kept.append(_ultra_slim_tool(t))
                    matched_okta_tools.append(name)
                    okta_count += 1
            
            # Update the tools in the correct container
            if container == "data.tools":
                data["tools"] = kept
            elif container == "data.optional_params.tools":
                data["optional_params"]["tools"] = kept
            
            # Log the filtering results
            total_before = len(tools)
            total_after = len(kept)
            
            query_preview = query[:50] + "..." if len(query) > 50 else query
            if not query_preview:
                query_preview = "unknown query"
            
            print(f"[MCP] '{query_preview}' | {total_before} → {total_after} ({okta_count} Okta)")
            
            if okta_count < len(all_okta_tools):
                print(f"[MCP DEBUG] Filtered out {len(all_okta_tools) - okta_count} Okta tools")
            
            return data
        
        except Exception as e:
            print(f"[MCP ERROR] {e}")
            import traceback
            traceback.print_exc()
            return data


proxy_handler_instance = McpOnlyToolsHandler()


CALLBACK_EOF



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



