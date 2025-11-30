# ALB Security Group (VPN access only)
resource "aws_security_group" "alb" {
  name_prefix = "okta-mcp-alb-"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "Fortinet VPN access"
    from_port   = 8080
    to_port     = 8080
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
    Name = "okta-mcp-alb-sg"
  }
}

# MCP Server Security Group
resource "aws_security_group" "mcp" {
  name_prefix = "okta-mcp-server-"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "ALB traffic"
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  ingress {
    description     = "Health check from ALB"
    from_port       = 80
    to_port         = 80
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
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
