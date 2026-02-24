# outputs.tf - Updated for new Ansible instance with different ports

output "instance_private_ip" {
  description = "Private IP of the Okta MCP Ansible instance"
  value       = aws_instance.okta_mcp_prod.private_ip # ✅ Updated name
}

output "instance_id" {
  description = "Instance ID"
  value       = aws_instance.okta_mcp_prod.id # ✅ Updated name
}

# StrongDM SSH Resource Config (same port - SSH doesn't conflict)
output "strongdm_ssh_resource_config" {
  description = "Configuration for StrongDM SSH resource"
  value = {
    hostname = aws_instance.okta_mcp_prod.private_ip # ✅ Updated name
    port     = 22
    username = "ec2-user"
  }
}

# StrongDM LiteLLM Resource Config (DIFFERENT PORT to avoid conflict)
output "strongdm_litellm_resource_config" {
  description = "Configuration for StrongDM LiteLLM Proxy resource"
  value = {
    name             = "okta-mcp-litellm-prod-proxy"                          # ✅ Different name
    url              = "http://${aws_instance.okta_mcp_prod.private_ip}:4002" # ✅ Port 4002 (was 4001)
    healthcheck_path = "/health"
  }
}

# StrongDM Grafana Resource Config (DIFFERENT PORT to avoid conflict)
output "strongdm_grafana_resource_config" {
  description = "Configuration for StrongDM Grafana resource"
  value = {
    name             = "okta-mcp-grafana-prod"                                # ✅ Different name
    url              = "http://${aws_instance.okta_mcp_prod.private_ip}:3002" # ✅ Port 3002 (was 3001)
    healthcheck_path = "/api/health"
  }
}

output "ansible_next_steps" {
  description = "Next steps for Ansible configuration"
  value       = <<-EOT
  
  ✅ EC2 Instance Created: ${aws_instance.okta_mcp_prod.tags.Name}
  
  📍 Private IP: ${aws_instance.okta_mcp_prod.private_ip}
  
  🔌 Service Ports (UPDATED to avoid conflicts):
     - SSH: 22
     - LiteLLM: 4002 (changed from 4001)
     - Grafana: 3002 (changed from 3001)
     - Loki: 3100
     - Redis: 6379
     - MCP Admin: 8080
     - MCP Readonly: 8081
  
  📝 Next Steps:
     1. SSH into instance: ssh -i ~/.ssh/${var.key_name}.pem ec2-user@${aws_instance.okta_mcp_prod.private_ip}
     2. Check bootstrap log: sudo cat /var/log/user-data.log
     3. Run Ansible: cd ../ansible && ansible-playbook playbook.yml -i inventory/hosts.ini
  
  EOT
}
