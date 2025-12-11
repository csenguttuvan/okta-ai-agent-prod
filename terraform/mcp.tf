resource "aws_instance" "mcp_server" {
  ami                    = data.aws_ami.amazon_linux.id
  instance_type          = "t3.small"
  key_name               = var.ec2_key_name
  vpc_security_group_ids = [aws_security_group.mcp.id]
  subnet_id              = data.aws_subnet.private_target.id  # Use existing subnet from 
  iam_instance_profile   = aws_iam_instance_profile.mcp.name

  user_data = templatefile("${path.module}/userdata/mcp-init.sh", {
    secrets_arn = aws_secretsmanager_secret.okta_mcp.arn
    aws_region  = var.aws_region
  })

  tags = {
    Name        = "okta-mcp-server"
    Environment = "production"
    ManagedBy   = "terraform"
  }
}
