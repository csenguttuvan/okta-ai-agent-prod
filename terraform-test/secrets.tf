# Store Okta private key in Secrets Manager
resource "aws_secretsmanager_secret" "okta_private_key" {
  name_prefix             = "okta-mcp-private-key-"
  description             = "Okta OAuth private key for MCP server"
  recovery_window_in_days = 0 # Immediate deletion for dev/test
}

resource "aws_secretsmanager_secret_version" "okta_private_key" {
  secret_id     = aws_secretsmanager_secret.okta_private_key.id
  secret_string = file("${path.module}/keys/private_key.pem")
}

# Grant EC2 instance permission to read BOTH secrets
resource "aws_iam_role_policy" "secrets_manager" {
  name = "okta-mcp-secrets-access"
  role = aws_iam_role.okta_mcp.id

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
          "${aws_secretsmanager_secret.okta_private_key.arn}*",
          "arn:aws:secretsmanager:${var.aws_region}:275581418957:secret:okta-mcp-admin-private-key-*"
        ]
      }
    ]
  })
}