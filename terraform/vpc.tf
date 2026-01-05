# Reference existing Corp IT VPC
data "aws_vpc" "corp_it" {
  id = var.existing_vpc_id # Pass VPC ID via variable
}

# Reference existing subnets (you'll need subnet IDs from your Corp IT team)
data "aws_subnet" "existing_private" {
  id = var.existing_private_subnet_id
}

//data "aws_subnet" "existing_public" {
//id = var.existing_public_subnet_id
//}