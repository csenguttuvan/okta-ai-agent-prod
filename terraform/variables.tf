variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-west-3"
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.medium"
}

variable "key_name" {
  description = "SSH key pair name (must exist in AWS)"
  type        = string
  default     = "okta-mcp-prod"
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

variable "use_existing_vpc" {
  description = "Whether to use existing VPC or create new one"
  type        = bool
  default     = true
}

variable "database" {
  description = "Database configuration"
  type = object({
    rds_host                  = string
    rds_master_user           = string
    rds_db_password_secret_id = string
  })
  default = {
    rds_host                  = "okta-orchestrator-db.cxvxlfb3g9aw.eu-west-3.rds.amazonaws.com"
    rds_master_user           = "orchestrator"
    rds_db_password_secret_id = "arn:aws:secretsmanager:eu-west-3:306965385748:secret:okta-orchestrator-db-password-Q9XPIF"
  }
}
