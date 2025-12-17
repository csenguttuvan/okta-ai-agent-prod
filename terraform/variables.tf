variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.small" # Upgraded from t3.micro for LiteLLM
}

variable "key_name" {
  description = "SSH key pair name (must exist in AWS)"
  type        = string
}

variable "okta_api_base_url" {
  description = "Okta organization URL"
  type        = string
  default     = "https://integrator-7772662.okta.com"
}

variable "okta_client_id" {
  description = "Okta OAuth client ID (read-only app)"
  type        = string
  default     = "0oay0b661jlQnwFJG697"
}

variable "okta_scopes" {
  description = "Okta API scopes (read-only)"
  type        = string
  default     = "okta.users.read okta.groups.read okta.apps.read okta.logs.read"
}

variable "okta_admin_client_id" {
  description = "Okta OAuth client ID (admin app)"
  type        = string
  default     = "0oay0p5kq9WhsKa9c697"
}

variable "okta_admin_scopes" {
  description = "Okta API scopes (admin with write)"
  type        = string
  default     = "okta.users.read okta.users.manage okta.groups.read okta.groups.manage okta.apps.read okta.logs.read"
}

variable "docker_image" {
  description = "Docker image for Okta MCP server"
  type        = string
  default     = "blackstaa/okta-mcp-server:latest"
}

variable "litellm_master_key" {
  description = "LiteLLM master API key"
  type        = string
  sensitive   = true
  default     = "sk-litellm-master-key-change-me"
}

variable "litellm_admin_key" {
  description = "LiteLLM admin team API key"
  type        = string
  sensitive   = true
  default     = "sk-okta-admin-team-key"
}

variable "litellm_reader_key" {
  description = "LiteLLM reader team API key"
  type        = string
  sensitive   = true
  default     = "sk-okta-reader-team-key"
}

variable "bedrock_model_id" {
  type    = string
  default = "anthropic.claude-3-5-sonnet-20240620-v1:0"
}