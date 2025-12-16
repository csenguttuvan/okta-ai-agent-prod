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
resource "aws_instance" "okta_mcp" {
  ami                         = data.aws_ami.amazon_linux_2023.id
  instance_type               = var.instance_type
  subnet_id                   = aws_subnet.public.id
  vpc_security_group_ids      = [aws_security_group.okta_mcp.id]
  iam_instance_profile        = aws_iam_instance_profile.mcp.name
  associate_public_ip_address = true
  key_name                    = var.key_name

  root_block_device {
    volume_size           = 30
    volume_type           = "gp3"
    delete_on_termination = true
  }

  user_data = templatefile("${path.module}/user-data.sh", {
    aws_region               = var.aws_region
    readonly_secret_id       = aws_secretsmanager_secret.okta_readonly_private_key.id
    admin_secret_id          = aws_secretsmanager_secret.okta_admin_private_key.id
    litellm_master_secret_id = aws_secretsmanager_secret.litellm_master_key.id
    litellm_admin_secret_id  = aws_secretsmanager_secret.litellm_admin_key.id
    litellm_reader_secret_id = aws_secretsmanager_secret.litellm_reader_key.id
    okta_api_base_url        = var.okta_api_base_url
    okta_readonly_client_id  = var.okta_client_id         # lowercase
    okta_readonly_scopes     = var.okta_scopes             # lowercase
    okta_admin_client_id     = var.okta_admin_client_id   # lowercase
    okta_admin_scopes        = var.okta_admin_scopes       # lowercase
    docker_image             = var.docker_image
    key_name                 = var.key_name
  })

  tags = {
    Name        = "okta-mcp-litellm-server"
    Environment = "test"
    Purpose     = "MCP Server + LiteLLM Proxy"
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
