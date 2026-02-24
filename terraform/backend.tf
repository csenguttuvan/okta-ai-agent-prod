terraform {
  backend "s3" {
    bucket         = "corpit-terraform-tfstate-paris"
    key            = "okta-mcp-litellm-prod/terraform.tfstate"
    region         = "eu-west-3"
    encrypt        = true
    dynamodb_table = "terraform-state-lock" # Shared lock table
  }
}
