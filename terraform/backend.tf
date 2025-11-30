terraform {
  cloud {

    organization = "blackstaa"

    workspaces {
      name = "okta-mcp-server-prod"
    }
  }
}