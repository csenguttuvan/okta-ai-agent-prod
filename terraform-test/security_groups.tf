# Security Group - Enhanced for HTTP/SSE and LiteLLM
resource "aws_security_group" "okta_mcp" {
  name        = "okta-mcp-sg"
  description = "Security group for Okta MCP server with LiteLLM"
  vpc_id      = aws_vpc.mcp.id

  # SSH access
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"] # Restrict to your IP in production
    description = "SSH access"
  }

  # LiteLLM proxy port
  ingress {
    from_port   = 4000
    to_port     = 4000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"] # Restrict to VPN or specific IPs in production
    description = "LiteLLM proxy"
  }

  # MCP servers (for debugging only - should be internal)
  ingress {
    from_port   = 8080
    to_port     = 8081
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"] # Internal VPC only
    description = "MCP servers internal"
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
    Environment = "test"
  }
}