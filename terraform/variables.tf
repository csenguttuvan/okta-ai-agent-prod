variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-west-3"
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.medium" # Upgraded from t3.small for Prisma migration during ansible run
}

variable "key_name" {
  description = "SSH key pair name (must exist in AWS)"
  type        = string
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

variable "database" {
  description = "Database configuration"
  type = object({
    rds_host                  = string
    rds_master_user           = string
    rds_db_password_secret_id = string
    litellm_db_user           = string
    litellm_db_name           = string
  })
}

variable "okta" {
  description = "Okta configuration"
  type = object({
    okta_api_base_url = string
    # issuer          = string
    okta_readonly_client_id = string
    okta_readonly_scopes    = string
    okta_admin_client_id    = string
    okta_admin_scopes       = string
  })

  default = {
    okta_api_base_url = "https://kaltura.okta.com"
    # issuer            = "https://kaltura.okta.com"
    okta_readonly_client_id = "0oa25ucjxsjaMTjO40h8"
    okta_readonly_scopes    = "okta.users.read okta.groups.read okta.apps.read okta.logs.read"
    okta_admin_client_id    = "0oa25ucksrp2GU6rs0h8"
    okta_admin_scopes       = "okta.users.manage okta.groups.manage okta.apps.manage okta.logs.read okta.apps.read"
  }
}