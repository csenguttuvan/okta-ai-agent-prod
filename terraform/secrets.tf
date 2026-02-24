# secrets.tf - Reference existing Secrets Manager secrets

# Okta readonly private key
data "aws_secretsmanager_secret" "okta_readonly_private_key" {
  name = "okta-mcp-readonly-private-key-prod"
}

# Okta admin private key
data "aws_secretsmanager_secret" "okta_admin_private_key" {
  name = "okta-mcp-admin-private-key-prod"
}

# LiteLLM master key
data "aws_secretsmanager_secret" "litellm_master_key" {
  name = "litellm-master-key-20260128123932657700000001"
}

# LiteLLM admin team key
data "aws_secretsmanager_secret" "litellm_admin_key" {
  name = "litellm-admin-team-key-20260128123932658100000005"
}

# LiteLLM reader team key
data "aws_secretsmanager_secret" "litellm_reader_key" {
  name = "litellm-reader-team-key-20260128123932933300000009"
}

# Gateway session secret (optional, if needed)
data "aws_secretsmanager_secret" "gateway_session_secret" {
  name = "okta-mcp-gateway-session-secret"
}

# Gateway internal auth token (optional, if needed)
data "aws_secretsmanager_secret" "gateway_internal_auth_token" {
  name = "okta-mcp-gateway-internal-auth-token"
}

# No IAM policy needed - the existing mcp-role already has secrets access