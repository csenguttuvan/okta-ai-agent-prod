variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-west-3"
}

variable "ec2_key_name" {
  description = "EC2 Key Pair name (optional)"
  type        = string
}

variable "okta_api_base_url" {
  description = "Okta API base URL"
  type        = string
}

variable "okta_api_token" {
  description = "Okta API token"
  type        = string
  sensitive   = true
}