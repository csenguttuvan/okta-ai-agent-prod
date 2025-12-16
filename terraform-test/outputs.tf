output "instance_ip" {
  description = "Public IP of EC2 instance"
  value       = aws_instance.okta_mcp.public_ip
}

output "instance_id" {
  description = "EC2 instance ID"
  value       = aws_instance.okta_mcp.id
}

output "litellm_url" {
  description = "LiteLLM proxy URL"
  value       = "http://${aws_instance.okta_mcp.public_ip}:4000"
}

output "ssh_tunnel_command" {
  description = "SSH tunnel command for secure access"
  value       = "ssh -L 4000:localhost:4000 -i ~/.ssh/${var.key_name}.pem ec2-user@${aws_instance.okta_mcp.public_ip}"
}

output "mcp_admin_health" {
  description = "Admin MCP health check URL"
  value       = "http://${aws_instance.okta_mcp.public_ip}:8080/health"
}

output "mcp_readonly_health" {
  description = "Readonly MCP health check URL"
  value       = "http://${aws_instance.okta_mcp.public_ip}:8081/health"
}
