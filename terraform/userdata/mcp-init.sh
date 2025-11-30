#!/bin/bash
set -e

yum update -y
yum install -y docker aws-cli jq httpd

systemctl start docker
systemctl enable docker

# Pull MCP image
docker pull blackstaa/okta-mcp-server:prod

# Fetch secrets script
cat > /usr/local/bin/fetch-secrets.sh <<'SCRIPT'
#!/bin/bash
aws secretsmanager get-secret-value \
  --secret-id ${secrets_arn} \
  --region ${aws_region} \
  --query SecretString \
  --output text | jq -r 'to_entries[] | "\(.key)=\(.value)"' > /etc/okta-mcp.env
chmod 600 /etc/okta-mcp.env
SCRIPT

chmod +x /usr/local/bin/fetch-secrets.sh
/usr/local/bin/fetch-secrets.sh

# Health check
echo "OK" > /var/www/html/health
systemctl start httpd
systemctl enable httpd

# MCP systemd service
cat > /etc/systemd/system/okta-mcp.service <<EOF
[Unit]
Description=Okta MCP Server
After=docker.service

[Service]
ExecStart=/usr/bin/docker run --rm -p 8080:8080 --env-file /etc/okta-mcp.env blackstaa/okta-mcp-server:prod --tcp
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable okta-mcp
systemctl start okta-mcp
