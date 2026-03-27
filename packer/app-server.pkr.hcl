packer {
  required_plugins {
    amazon = {
      source  = "github.com/hashicorp/amazon"
      version = ">= 1.2.8"
    }
  }
}

locals {
  timestamp = regex_replace(timestamp(), "[- TZ:]", "")
}

source "amazon-ebs" "okta_mcp" {
  ami_name      = "okta-mcp-litellm-prod-${local.timestamp}"
  instance_type = var.instance_type
  region        = var.aws_region
  security_group_id = var.security_group_id
  subnet_id                   = var.subnet_id
  associate_public_ip_address = false

   # ✅ SSM — no SSH, no SDM registration needed
  communicator          = "ssh"
  ssh_interface         = "session_manager"
  ssh_username          = "ec2-user"
  iam_instance_profile  = var.iam_instance_profile

  source_ami_filter {
    filters = {
      name                = "al2023-ami-2023.*-kernel-*-x86_64"
      root-device-type    = "ebs"
      virtualization-type = "hvm"
    }
    owners      = ["amazon"]
    most_recent = true
  }

  tags = {
    Name        = "okta-mcp-litellm-prod"
    Environment = "Prod"
    Purpose     = "MCP Server Prod"
    ManagedBy   = "packer"
  }
}

build {
  name    = "okta-mcp"
  sources = ["source.amazon-ebs.okta_mcp"]

  # Only the bootstrap script — no Ansible
  provisioner "shell" {
    script          = "scripts/bootstrap.sh"
    execute_command = "sudo -S sh -c '{{ .Vars }} {{ .Path }}'"
  }

  post-processor "manifest" {
    output     = "manifest.json"
    strip_path = true
  }
}