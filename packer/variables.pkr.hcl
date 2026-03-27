variable "aws_region" {
  default = "eu-west-3"
}

variable "instance_type" {
  default = "t3.medium"
}

variable "subnet_id" {
  default = "subnet-017db9446e376909c"
}

variable "iam_instance_profile" {
  default = "mcp-instance-profile"  # your existing profile from iam.tf
}

variable "security_group_id" {
  default = "sg-0979f99adb6e5be3b"  # your okta_mcp security group ID from security_groups.tf
}