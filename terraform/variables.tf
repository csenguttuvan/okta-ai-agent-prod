variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-west-3"
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
  default     = "https://kaltura.okta.com"
}

variable "okta_client_id" {
  description = "Okta OAuth client ID (read-only app)"
  type        = string
  default     = "0oa25ucjxsjaMTjO40h8"
}

variable "okta_scopes" {
  description = "Okta API scopes (read-only)"
  type        = string
  default     = "okta.users.read okta.groups.read okta.apps.read okta.logs.read"
}

variable "okta_admin_client_id" {
  description = "Okta OAuth client ID (admin app)"
  type        = string
  default     = "0oa25ucksrp2GU6rs0h8"
}

variable "okta_admin_scopes" {
  description = "Okta API scopes (admin with write)"
  type        = string
  default     = "okta.users.manage okta.groups.manage okta.apps.manage okta.logs.read"
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
  default = "bedrock/eu.anthropic.claude-sonnet-4-5-20250929-v1:0"
}

variable "existing_vpc_id" {
  description = "corp-it-eu-vpc"
  type        = string
  default     = "vpc-069c70c3cf14974cd"
}

variable "existing_private_subnet_id" {
  description = "ID of existing private subnet for EC2/ECS tasks"
  type        = string
  default     = "subnet-017db9446e376909c"
}

//variable "existing_public_subnet_id" {
//description = "ID of existing public subnet for load balancers"
//type        = string
//default     = ""
//}

variable "use_existing_vpc" {
  description = "Whether to use existing VPC or create new one"
  type        = bool
  default     = true
}

variable "okta_issuer" {
  description = "Okta OAuth issuer URL"
  type        = string
  default     = "https://kaltura.okta.com"
}
