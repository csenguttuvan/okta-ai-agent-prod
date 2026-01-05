output "instance_private_ip" {
  description = "Private IP of EC2 instance (access via StrongDM)"
  value       = aws_instance.okta_mcp.private_ip
}

output "instance_id" {
  description = "EC2 instance ID"
  value       = aws_instance.okta_mcp.id
}

output "strongdm_ssh_resource_config" {
  description = "Config for StrongDM SSH resource registration"
  value = {
    hostname = aws_instance.okta_mcp.private_ip
    port     = 22
    username = "ec2-user"
  }
}

output "strongdm_litellm_resource_config" {
  description = "Config for StrongDM HTTP resource registration"
  value = {
    url              = "http://${aws_instance.okta_mcp.private_ip}:4000"
    healthcheck_path = "/health"
  }
}

output "strongdm_grafana_resource_config" {
  description = "Config for StrongDM Grafana resource registration"
  value = {
    url              = "http://${aws_instance.okta_mcp.private_ip}:3000"
    healthcheck_path = "/api/health"
  }
}
