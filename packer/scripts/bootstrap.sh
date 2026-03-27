#!/bin/bash
# Runs inside packer
# pipeline test $(date)

set -e

echo "🚀 Starting minimal bootstrap..."

# Update system
dnf update -y

# Install system dependencies
dnf install -y python3 python3-pip python3.11 python3.11-pip git jq nodejs

# Install Terraform
dnf install -y dnf-plugins-core
dnf config-manager --add-repo https://rpm.releases.hashicorp.com/AmazonLinux/hashicorp.repo
dnf install -y terraform

# Install Ansible + AWS deps
pip3.11 install "ansible-core>=2.16" ansible boto3 botocore requests

# Install Docker
dnf install -y docker
systemctl enable docker

# Create ansible user for running playbooks
useradd -m -s /bin/bash ansible || true
mkdir -p /home/ansible/.ssh
cp /home/ec2-user/.ssh/authorized_keys /home/ansible/.ssh/ || true
chown -R ansible:ansible /home/ansible/.ssh
chmod 700 /home/ansible/.ssh
chmod 600 /home/ansible/.ssh/authorized_keys

# Add ec2-user and ansible to docker group
usermod -aG docker ec2-user
usermod -aG docker ansible

# Signal completion
echo "✅ Bootstrap complete - ready for Ansible" > /var/log/bootstrap-complete
