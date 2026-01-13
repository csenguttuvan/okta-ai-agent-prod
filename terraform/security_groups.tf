# Security Group - Enhanced for HTTP/SSE and LiteLLM
resource "aws_security_group" "okta_mcp" {
  name        = "okta-mcp-sg"
  description = "Security group for Okta MCP server with LiteLLM"
  vpc_id      = data.aws_vpc.corp_it.id

  # SSH access
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["10.2.0.0/16"] # Restrict to your IP in production
    description = "SSH via StrongDM"
  }

  # LiteLLM proxy port
  ingress {
    from_port   = 4000
    to_port     = 4000
    protocol    = "tcp"
    cidr_blocks = ["10.2.0.0/16"] # Restrict to VPN or specific IPs in production
    description = "LiteLLM proxy via StrongDM"
  }

  # MCP servers (for debugging only - should be internal)
  ingress {
    from_port   = 8080
    to_port     = 8081
    protocol    = "tcp"
    cidr_blocks = ["10.2.0.0/16"] # Internal VPC only
    description = "MCP servers internal"
  }

  # Grafana - Internal only
  ingress {
    from_port   = 3000
    to_port     = 3000
    protocol    = "tcp"
    cidr_blocks = ["10.2.0.0/16"]
    description = "Grafana dashboard via StrongDM"
  }
  # Auth gateway readonly
  ingress {
    from_port   = 9000
    to_port     = 9000
    protocol    = "tcp"
    cidr_blocks = ["10.2.0.0/16"]
    description = "Auth Gateway for Okta Readonly"
  }

    # Auth gateway Admin
  ingress {
    from_port   = 9001
    to_port     = 9001
    protocol    = "tcp"
    cidr_blocks = ["10.2.0.0/16"]
    description = "Auth Gateway for Okta Admin"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }

  tags = {
    Name        = "okta-mcp-sg"
    Environment = "production"
  }
}