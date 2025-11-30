output "mcp_private_ip" {
  description = "MCP server private IP (for VPN access)"
  value       = aws_instance.mcp_server.private_ip
}

output "mcp_public_ip" {
  description = "MCP server public IP (temporary for testing)"
  value       = aws_instance.mcp_server.public_ip
}

output "ssh_command" {
  description = "SSH command to connect"
  value       = "ssh -i ${var.ec2_key_name}.pem ec2-user@${aws_instance.mcp_server.private_ip}"
}

output "claude_config" {
  description = "Copy this into claude_desktop_config.json"
  value = jsonencode({
    mcpServers = {
      "okta-prod" = {
        command = "ssh"
        args = [
          "-i",
          "~/.ssh/${var.ec2_key_name}.pem",
          "ec2-user@${aws_instance.mcp_server.private_ip}",
          "docker",
          "run",
          "--rm",
          "-i",
          "--env-file",
          "/etc/okta-mcp.env",
          "blackstaa/okta-mcp-server:prod"
        ]
      }
    }
  })
}
