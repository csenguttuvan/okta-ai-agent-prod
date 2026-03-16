#!/bin/bash
set -e

echo "🚀 Starting minimal bootstrap..."

# Update system
yum update -y

# Install Python and dependencies
yum install -y python3 python3-pip git jq
sudo dnf install -y nodejs #For github Runner


# Install Ansible
pip3 install ansible boto3 botocore

# Create ansible user for running playbooks
useradd -m -s /bin/bash ansible || true
mkdir -p /home/ansible/.ssh
cp /home/ec2-user/.ssh/authorized_keys /home/ansible/.ssh/ || true
chown -R ansible:ansible /home/ansible/.ssh
chmod 700 /home/ansible/.ssh
chmod 600 /home/ansible/.ssh/authorized_keys

# Signal completion
echo "✅ Bootstrap complete - ready for Ansible" > /var/log/bootstrap-complete
