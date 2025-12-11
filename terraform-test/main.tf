terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Security Group
resource "aws_security_group" "okta_mcp" {
  name        = "okta-mcp-sg"
  description = "Security group for Okta MCP server"
  vpc_id      = aws_vpc.okta_mcp.id

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"] # Restrict to your IP in production
    description = "SSH access"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }

  tags = {
    Name        = "okta-mcp-sg"
    Environment = "test"
  }
}

# IAM Role
resource "aws_iam_role" "okta_mcp" {
  name = "okta-mcp-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
    }]
  })

  tags = {
    Name = "okta-mcp-role"
  }
}

# IAM Instance Profile
resource "aws_iam_instance_profile" "okta_mcp" {
  name = "okta-mcp-profile"
  role = aws_iam_role.okta_mcp.name
}

# EC2 Instance
resource "aws_instance" "okta_mcp" {
  ami                         = data.aws_ami.amazon_linux_2023.id
  instance_type               = var.instance_type
  subnet_id                   = aws_subnet.public.id
  vpc_security_group_ids      = [aws_security_group.okta_mcp.id]
  iam_instance_profile        = aws_iam_instance_profile.okta_mcp.name
  associate_public_ip_address = true
  key_name                    = var.key_name

  root_block_device {
    volume_size           = 30
    volume_type           = "gp3"
    delete_on_termination = true
  }

  user_data = <<-USERDATA
#!/bin/bash
set -e
    
# Log output
exec > >(tee /var/log/user-data.log)
exec 2>&1
    
echo "Starting Okta MCP Server setup (Read-Only + Admin)..."
    
# Update system
yum update -y
    
# Install Docker and AWS CLI
yum install -y docker aws-cli jq
systemctl start docker
systemctl enable docker
usermod -a -G docker ec2-user
    
# Create directories for both containers
mkdir -p /opt/okta-mcp-readonly/keys
mkdir -p /opt/okta-mcp-admin/keys
    
# Fetch readonly private key from Secrets Manager
echo "Fetching readonly private key from Secrets Manager..."
aws secretsmanager get-secret-value \
    --secret-id ${aws_secretsmanager_secret.okta_private_key.id} \
    --region ${var.aws_region} \
    --query SecretString \
      --output text > /opt/okta-mcp-readonly/keys/private_key.pem
    
chmod 444 /opt/okta-mcp-readonly/keys/private_key.pem
echo "Readonly private key retrieved successfully"
    
# Fetch admin private key from Secrets Manager
echo "Fetching admin private key from Secrets Manager..."
aws secretsmanager get-secret-value \
      --secret-id okta-mcp-admin-private-key \
      --region ${var.aws_region} \
      --query SecretString \
      --output text > /opt/okta-mcp-admin/keys/private_key.pem
    
    
    
chmod 444 /opt/okta-mcp-admin/keys/private_key.pem
echo "Admin private key retrieved successfully"
    
# Pull Docker image
echo "Pulling Docker image ${var.docker_image}..."
docker pull ${var.docker_image}
    
# Create systemd service for READONLY container
cat > /etc/systemd/system/okta-mcp-readonly.service << 'SYSTEMD_READONLY'
[Unit]
Description=Okta MCP Server Read-Only (Docker with OAuth JWT)
After=docker.service
Requires=docker.service

[Service]
Type=simple
User=root
Restart=always
RestartSec=10
ExecStartPre=-/usr/bin/docker stop okta-mcp-readonly
ExecStartPre=-/usr/bin/docker rm okta-mcp-readonly
ExecStart=/usr/bin/docker run --rm --name okta-mcp-readonly \
  -e OKTA_API_BASE_URL=${var.okta_api_base_url} \
  -e OKTA_CLIENT_ID=${var.okta_client_id} \
  -e OKTA_PRIVATE_KEY_PATH=/app/keys/private_key.pem \
  -e OKTA_SCOPES="${var.okta_scopes}" \
  -e OKTA_LOG_LEVEL=INFO \
  -v /opt/okta-mcp-readonly/keys:/app/keys:ro \
  ${var.docker_image} \
  /bin/sh -c "while true; do sleep 3600; done"
ExecStop=-/usr/bin/docker stop okta-mcp-readonly

[Install]
WantedBy=multi-user.target
SYSTEMD_READONLY
    
    # Create systemd service for ADMIN container
    cat > /etc/systemd/system/okta-mcp-admin.service << 'SYSTEMD_ADMIN'
[Unit]
Description=Okta MCP Server Admin (Docker with OAuth JWT)
After=docker.service
Requires=docker.service

[Service]
Type=simple
User=root
Restart=always
RestartSec=10
ExecStartPre=-/usr/bin/docker stop okta-mcp-admin
ExecStartPre=-/usr/bin/docker rm okta-mcp-admin
ExecStart=/usr/bin/docker run --rm --name okta-mcp-admin \
  -e OKTA_API_BASE_URL=${var.okta_api_base_url} \
  -e OKTA_CLIENT_ID=${var.okta_admin_client_id} \
  -e OKTA_PRIVATE_KEY_PATH=/app/keys/private_key.pem \
  -e OKTA_SCOPES="${var.okta_admin_scopes}" \
  -e OKTA_LOG_LEVEL=INFO \
  -v /opt/okta-mcp-admin/keys:/app/keys:ro \
  ${var.docker_image} \
   /bin/sh -c "while true; do sleep 3600; done"
ExecStop=-/usr/bin/docker stop okta-mcp-admin

[Install]
WantedBy=multi-user.target
SYSTEMD_ADMIN
    
# Enable and start both services
systemctl daemon-reload
    
systemctl enable okta-mcp-readonly
systemctl start okta-mcp-readonly
echo "Okta MCP Server (Read-Only) started successfully"
    
systemctl enable okta-mcp-admin
systemctl start okta-mcp-admin
echo "Okta MCP Server (Admin) started successfully"
    
# Create connection info
INSTANCE_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)
    
cat > /home/ec2-user/README.txt << README
# Okta MCP Server - Dual Mode (Read-Only + Admin)

Instance IP: $INSTANCE_IP

## Check Status

### Read-Only Container:
sudo systemctl status okta-mcp-readonly
sudo docker ps | grep readonly
sudo docker logs okta-mcp-readonly

### Admin Container:
sudo systemctl status okta-mcp-admin
sudo docker ps | grep admin
sudo docker logs okta-mcp-admin

## View Setup Logs
sudo cat /var/log/user-data.log

## Test MCP Servers
sudo docker exec -i okta-mcp-readonly .venv/bin/okta-mcp-server
sudo docker exec -i okta-mcp-admin .venv/bin/okta-mcp-server

## Connect from Roo Code
Add to ~/.roo/mcp_settings.json:

{
  "mcpServers": {
    "okta-remote-readonly": {
      "command": "ssh",
      "args": [
        "-i", "~/.ssh/${var.key_name}.pem",
        "ec2-user@$INSTANCE_IP",
        "sudo", "docker", "exec", "-i", "okta-mcp-readonly",
        ".venv/bin/okta-mcp-server"
      ],
      "description": "Okta MCP - Read Only"
    },
    "okta-remote-admin": {
      "command": "ssh",
      "args": [
        "-i", "~/.ssh/${var.key_name}.pem",
        "ec2-user@$INSTANCE_IP",
        "sudo", "docker", "exec", "-i", "okta-mcp-admin",
        ".venv/bin/okta-mcp-server"
      ],
      "description": "Okta MCP - Admin (Read/Write)"
    }
  }
}
README
    
    chown ec2-user:ec2-user /home/ec2-user/README.txt
    
    echo "Setup complete!"
  USERDATA

  tags = {
    Name        = "okta-mcp-server"
    Environment = "test"
    Purpose     = "MCP Server with OAuth JWT (Dual Mode)"
  }
}

# Get latest Amazon Linux 2023 AMI
data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-kernel-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}
