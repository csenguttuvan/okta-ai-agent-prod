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
  ami                         = data.aws_ami.okta_mcp_packer.id
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
    delete_on_termination = true
    encrypted             = true
  }

  # ✅ Prevent AMI updates from destroying the instance
  lifecycle {
    ignore_changes = [ami, user_data]
  }

  tags = {
    Name        = "okta-mcp-litellm-ansible-prod-server"
    Environment = "Prod"
    Purpose     = "MCP Server Prod"
  }
}


# Get latest Amazon Linux 2023 AMI
data "aws_ami" "okta_mcp_packer" {
  most_recent = true
  owners      = ["self"] # my own AWS account

  filter {
    name   = "name"
    values = ["okta-mcp-litellm-prod-*"] # Should match my packer's ami_name
  }

  filter {
    name   = "tag:ManagedBy"
    values = ["packer"]
  }
}


# Persistent data volume — survives EC2 recreation
resource "aws_ebs_volume" "persistent_data" {
  availability_zone = aws_instance.okta_mcp_prod.availability_zone
  size              = 50  # GB — covers Grafana, Loki, Redis, LiteLLM data
  type              = "gp3"
  encrypted         = true

  lifecycle {
    prevent_destroy = true  # ← never deleted, even on terraform destroy
  }

  tags = {
    Name = "okta-mcp-persistent-data"
  }
}

# Attach to EC2 — reattaches automatically on recreation
resource "aws_volume_attachment" "persistent_data" {
  device_name  = "/dev/xvdf"
  volume_id    = aws_ebs_volume.persistent_data.id
  instance_id  = aws_instance.okta_mcp_prod.id
  force_detach = true  # ← allows clean detach when EC2 is terminated
}