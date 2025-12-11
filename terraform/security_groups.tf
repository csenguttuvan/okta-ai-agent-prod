# Get existing strongDM worker security group
data "aws_security_group" "strongdm_worker" {
  vpc_id = data.aws_vpc.corp_it_eu.id

  filter {
    name   = "tag:Name"
    values = ["sdm-proxy-worker-20251117135336592700000006"] # Adjust to match actual SG name
  }
}

# MCP Server Security Group (SSH from strongDM worker only)
resource "aws_security_group" "mcp" {
  name_prefix = "okta-mcp-server-"
  vpc_id      = data.aws_vpc.corp_it_eu.id
  description = "Security group for Okta MCP Server"

  # SSH from strongDM worker nodes only
  ingress {
    description     = "SSH from strongDM worker"
    from_port       = 22
    to_port         = 22
    protocol        = "tcp"
    security_groups = [data.aws_security_group.strongdm_worker.id]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "okta-mcp-server-sg"
  }
}
