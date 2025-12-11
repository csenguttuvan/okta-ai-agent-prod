output "vpc_id" {
  value       = aws_vpc.okta_mcp.id
  description = "VPC ID"
}

output "instance_public_ip" {
  value       = aws_instance.okta_mcp.public_ip
  description = "Public IP address of EC2 instance"
}

output "ssh_command" {
  value       = "ssh -i ~/.ssh/${var.key_name}.pem ec2-user@${aws_instance.okta_mcp.public_ip}"
  description = "SSH command to connect"
}

output "docker_logs_command" {
  value       = "ssh -i ~/.ssh/${var.key_name}.pem ec2-user@${aws_instance.okta_mcp.public_ip} 'sudo docker logs -f okta-mcp'"
  description = "Command to view logs"
}

output "roo_code_config" {
  value       = <<-EOT
    
    Add to ~/.roo/mcp_settings.json:
    
    {
      "mcpServers": {
        "okta-remote-readonly": {
          "command": "ssh",
          "args": [
            "-i", "~/.ssh/${var.key_name}.pem",
            "ec2-user@${aws_instance.okta_mcp.public_ip}",
            "sudo", "docker", "exec", "-i", "okta-mcp", ".venv/bin/okta-mcp-server"
          ],
          "description": "Okta MCP - Remote EC2 (OAuth JWT)"
        }
      }
    }
  EOT
  description = "Roo Code MCP configuration"
}
