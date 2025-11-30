output "alb_dns_name" {
  description = "Internal ALB DNS name (use via VPN)"
  value       = aws_lb.mcp.dns_name
}

output "mcp_private_ip" {
  description = "MCP server private IP"
  value       = aws_instance.mcp_server.private_ip
}

output "secrets_arn" {
  description = "Secrets Manager ARN"
  value       = aws_secretsmanager_secret.okta_mcp.arn
}

output "claude_config" {
  description = "Copy this into claude_desktop_config.json"
  value = jsonencode({
    mcpServers = {
      "okta-prod" = {
        url       = "http://${aws_lb.mcp.dns_name}:8080"
        transport = "http-streaming"
      }
    }
  })
}
