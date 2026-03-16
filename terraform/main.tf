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

# EC2 Instance
resource "aws_instance" "okta_mcp_prod" {
  ami                         = data.aws_ami.amazon_linux_2023.id
  instance_type               = var.instance_type
  subnet_id                   = data.aws_subnet.existing_private.id
  vpc_security_group_ids      = [aws_security_group.okta_mcp.id]
  iam_instance_profile        = aws_iam_instance_profile.mcp_prod.name
  associate_public_ip_address = false
  key_name                    = var.key_name
  private_ip                  = "10.2.0.39"

  root_block_device {
    volume_size           = 30
    volume_type           = "gp3"
    delete_on_termination = false
    encrypted             = true
  }

  # ✅ Prevent AMI updates from destroying the instance
  lifecycle {
    ignore_changes = [ami, user_data]
  }

  user_data = file("${path.module}/bootstrap.sh")

  tags = {
    Name        = "okta-mcp-litellm-ansible-prod-server"
    Environment = "Prod"
    Purpose     = "MCP Server Prod"
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