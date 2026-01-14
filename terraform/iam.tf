resource "aws_iam_role" "mcp" {
  name = "mcp-role"

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

  tags = {
    Name = "mcp-role"
  }
}

resource "aws_iam_instance_profile" "mcp" {
  name = "mcp-instance-profile"
  role = aws_iam_role.mcp.name
}

# attach secrets access policy defined in secrets.tf
resource "aws_iam_role_policy" "secrets_access" {
  name = "mcp-secrets-access"
  role = aws_iam_role.mcp.id

  # policy is jsonencode(...) in secrets.tf or inline here
  policy = file("${path.module}/secretsmanager-policy-v2.json")
}


resource "aws_iam_role_policy" "okta_mcp_bedrock" {
  name = "okta-mcp-bedrock-policy"
  role = aws_iam_role.mcp.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
          "bedrock:ListFoundationModels"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "aws-marketplace:ViewSubscriptions",
          "aws-marketplace:Subscribe"
        ]
        Resource = "*"
      }
    ]
  })
}


# Allow EC2 to access S3 bucket for LiteLLM cache
resource "aws_iam_role_policy" "s3_cache_access" {
  name = "litellm-s3-cache-access"
  role = aws_iam_role.mcp.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = [
          "arn:aws:s3:::corpit-terraform-tfstate-paris/litellm-cache/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::corpit-terraform-tfstate-paris"
        ]
        Condition = {
          StringLike = {
            "s3:prefix" = ["litellm-cache/*"]
          }
        }
      }
    ]
  })
}