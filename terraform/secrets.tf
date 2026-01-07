# Readonly private key
resource "aws_secretsmanager_secret" "okta_readonly_private_key" {
  name_prefix             = "okta-mcp-readonly-private-key-"
  description             = "Okta OAuth private key for readonly MCP server"
  recovery_window_in_days = 7

  tags = {
    Environment = "production"
    ManagedBy   = "terraform"
  }
}

resource "aws_secretsmanager_secret_version" "okta_readonly_private_key" {
  secret_id     = aws_secretsmanager_secret.okta_readonly_private_key.id
  secret_string = file("${path.module}/keys/private_key.pem")
}

# Admin private key
resource "aws_secretsmanager_secret" "okta_admin_private_key" {
  name_prefix             = "okta-mcp-admin-private-key-"
  description             = "Okta OAuth private key for admin MCP server"
  recovery_window_in_days = 7

  tags = {
    Environment = "production"
    ManagedBy   = "terraform"
  }
}

resource "aws_secretsmanager_secret_version" "okta_admin_private_key" {
  secret_id     = aws_secretsmanager_secret.okta_admin_private_key.id
  secret_string = file("${path.module}/keys/private_key_admin.pem")
}

# LiteLLM master key
resource "aws_secretsmanager_secret" "litellm_master_key" {
  name_prefix             = "litellm-master-key-"
  description             = "LiteLLM proxy master API key"
  recovery_window_in_days = 7

  tags = {
    Environment = "production"
    ManagedBy   = "terraform"
  }
}

resource "aws_secretsmanager_secret_version" "litellm_master_key" {
  secret_id     = aws_secretsmanager_secret.litellm_master_key.id
  secret_string = var.litellm_master_key
}

# LiteLLM admin team key
resource "aws_secretsmanager_secret" "litellm_admin_key" {
  name_prefix             = "litellm-admin-team-key-"
  description             = "LiteLLM admin team API key"
  recovery_window_in_days = 7

  tags = {
    Environment = "production"
    ManagedBy   = "terraform"
  }
}

resource "aws_secretsmanager_secret_version" "litellm_admin_key" {
  secret_id     = aws_secretsmanager_secret.litellm_admin_key.id
  secret_string = var.litellm_admin_key
}

# LiteLLM reader team key
resource "aws_secretsmanager_secret" "litellm_reader_key" {
  name_prefix             = "litellm-reader-team-key-"
  description             = "LiteLLM reader team API key"
  recovery_window_in_days = 7

  tags = {
    Environment = "production"
    ManagedBy   = "terraform"
  }
}

resource "aws_secretsmanager_secret_version" "litellm_reader_key" {
  secret_id     = aws_secretsmanager_secret.litellm_reader_key.id
  secret_string = var.litellm_reader_key
}

# Gateway session secret - REFERENCE existing manually created secret
data "aws_secretsmanager_secret" "gateway_session_secret" {
  name = "okta-mcp-gateway-session-secret"
}

# Gateway internal auth token - REFERENCE existing manually created secret
data "aws_secretsmanager_secret" "gateway_internal_auth_token" {
  name = "okta-mcp-gateway-internal-auth-token"
}

# IAM policy for EC2 to access all secrets
resource "aws_iam_role_policy" "secrets_manager_access" {
  name = "okta-mcp-secrets-access"
  role = aws_iam_role.mcp.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = [
          aws_secretsmanager_secret.okta_readonly_private_key.arn,
          aws_secretsmanager_secret.okta_admin_private_key.arn,
          aws_secretsmanager_secret.litellm_master_key.arn,
          aws_secretsmanager_secret.litellm_admin_key.arn,
          aws_secretsmanager_secret.litellm_reader_key.arn,
          data.aws_secretsmanager_secret.gateway_session_secret.arn,
          data.aws_secretsmanager_secret.gateway_internal_auth_token.arn
        ]

      }
    ]
  })
}
