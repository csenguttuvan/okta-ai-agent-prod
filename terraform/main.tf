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
    encrypted = true
  }

  user_data = file("${path.module}/bootstrap.sh")

  tags = {
    Name        = "okta-mcp-litellm-ansible-prod-server"
    Environment = "Prod"
    Purpose     = "MCP Server Prod"
  }
}

# Generate Ansible inventory
resource "local_file" "ansible_inventory" {
  content = templatefile("${path.module}/inventory.tftpl", {
    instance_ip = aws_instance.okta_mcp_prod.private_ip
    aws_region  = var.aws_region
    instance_id = aws_instance.okta_mcp_prod.id
  })
  filename = "${path.module}/../ansible/inventory/hosts.ini"

  depends_on = [aws_instance.okta_mcp_prod]
}

# Generate Ansible variables
resource "local_file" "ansible_vars" {
  content = templatefile("${path.module}/group_vars.tftpl", {
    aws_region               = var.aws_region
    readonly_secret_id       = data.aws_secretsmanager_secret.okta_readonly_private_key.id
    admin_secret_id          = data.aws_secretsmanager_secret.okta_admin_private_key.id
    litellm_master_secret_id = data.aws_secretsmanager_secret.litellm_master_key.id
    litellm_admin_secret_id  = data.aws_secretsmanager_secret.litellm_admin_key.id
    litellm_reader_secret_id = data.aws_secretsmanager_secret.litellm_reader_key.id
    okta_api_base_url        = var.okta_api_base_url
    okta_readonly_client_id  = var.okta_client_id
    okta_readonly_scopes     = var.okta_scopes
    okta_admin_client_id     = var.okta_admin_client_id
    okta_admin_scopes        = var.okta_admin_scopes
    docker_image             = var.docker_image
  })
  filename = "${path.module}/../ansible/group_vars/all.yml"

  depends_on = [aws_instance.okta_mcp_prod]
}

# Automatically run Ansible after instance creation
resource "null_resource" "run_ansible" {
  triggers = {
    instance_id = aws_instance.okta_mcp_prod.id
  }

  provisioner "local-exec" {
    command = <<-EOT
      echo "⏳ Waiting for instance to be ready..."
      sleep 60
      
      until ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 \
            -p 10031 \
            -i ~/.ssh/okta-mcp-prod.pem \
            ec2-user@127.0.0.1 'command -v ansible' 2>/dev/null; do
        echo "⏳ Waiting for bootstrap..."
        sleep 10
      done
      
      echo "✅ Bootstrap complete!"
      echo "🚀 Running Ansible..."
      cd /Users/chrissenguttuvan/Desktop/okta-ai-agent/okta-mcp-server-with-litellm-prod/terraform/ansible && ansible-playbook playbook.yml -i inventory/hosts.ini
      echo "✅ Done!"
    EOT
  }

  depends_on = [
    aws_instance.okta_mcp_prod,
    local_file.ansible_inventory,
    local_file.ansible_vars
  ]
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