# MCP Server Security Group
resource "aws_security_group" "mcp" {
  name_prefix = "okta-mcp-server-"
  vpc_id      = aws_vpc.main.id

  # SSH from Fortinet VPN (or your IP for testing)
  ingress {
    description = "SSH from VPN"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.fortinet_vpn_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "okta-mcp-server-sg"
  }
}
