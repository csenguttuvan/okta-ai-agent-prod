# AWS Secrets Manager
resource "aws_secretsmanager_secret" "okta_mcp" {
  name                    = "okta-mcp-prod"
  description             = "Okta MCP Server credentials"
  recovery_window_in_days = 7

  tags = {
    Environment = "prod"
    Service     = "okta-mcp"
  }
}

resource "aws_secretsmanager_secret_version" "okta_mcp" {
  secret_id = aws_secretsmanager_secret.okta_mcp.id
  secret_string = jsonencode({
    OKTA_API_BASE_URL = var.okta_api_base_url
    OKTA_API_TOKEN    = var.okta_api_token
    OKTA_LOG_LEVEL    = "INFO"
  })
}
