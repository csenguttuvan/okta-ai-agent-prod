#!/bin/bash
set -e

echo "🚀 Starting minimal bootstrap..."

# Update system
yum update -y

# Install system dependencies
yum install -y python3 python3-pip git jq nodejs

# Install Terraform
yum install -y yum-utils
yum-config-manager --add-repo https://rpm.releases.hashicorp.com/AmazonLinux/hashicorp.repo
yum install -y terraform

# Install Ansible + AWS deps
pip3 install "ansible-core>=2.16" ansible boto3 botocore

# Install Docker
dnf install -y docker
systemctl enable docker
systemctl start docker

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
