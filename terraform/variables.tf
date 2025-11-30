variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "fortinet_vpn_cidr" {
  description = "Fortinet VPN CIDR range"
  type        = string
  default     = "172.16.0.0/16" # Update with your VPN CIDR
}

variable "ec2_key_name" {
  description = "EC2 Key Pair name (optional)"
  type        = string
  default     = ""
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

variable "AWS_ACCESS_KEY_ID" {
  description = "AWS Access key id"
  type        = string
}
variable "AWS_SECRET_ACCESS_KEY" {
  description = "AWS Secret key"
  type        = string
}


