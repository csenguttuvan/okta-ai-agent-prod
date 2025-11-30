# MCP EC2 IAM Role
resource "aws_iam_role" "mcp" {
  name = "okta-mcp-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
    }]
  })
}

# Secrets Manager + CloudWatch access
resource "aws_iam_role_policy" "mcp_secrets" {
  name = "okta-mcp-secrets"
  role = aws_iam_role.mcp.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = aws_secretsmanager_secret.okta_mcp.arn
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:CreateLogGroup",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:*:log-group:/aws/okta-mcp:*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "mcp_cloudwatch" {
  role       = aws_iam_role.mcp.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

resource "aws_iam_instance_profile" "mcp" {
  name = "okta-mcp-ec2-profile"
  role = aws_iam_role.mcp.name
}
