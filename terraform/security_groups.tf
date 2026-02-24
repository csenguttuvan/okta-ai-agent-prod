
# Security Group - Enhanced for HTTP/SSE and LiteLLM
resource "aws_security_group" "okta_mcp" {
  name        = "okta-mcp-prod-sg"
  description = "Security group for Okta MCP server with LiteLLM"
  vpc_id      = data.aws_vpc.corp_it.id

  # SSH access
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["10.2.0.0/16"]
    description = "SSH access"
  }

  # LiteLLM proxy port
  ingress {
    from_port   = 4002
    to_port     = 4002
    protocol    = "tcp"
    cidr_blocks = ["10.2.0.0/16"] # Restrict to VPN or specific IPs in production
    description = "LiteLLM proxy"
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
    from_port   = 3002
    to_port     = 3002
    protocol    = "tcp"
    cidr_blocks = ["10.2.0.0/16"]
    description = "Grafana dashboard via StrongDM"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }

  tags = {
    Name        = "okta-mcp-prod-sg"
    Environment = "prod"
  }
}