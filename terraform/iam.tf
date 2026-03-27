resource "aws_iam_role" "mcp_prod" {
  name = "mcp-prod-role"

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

resource "aws_iam_instance_profile" "mcp_prod" {
  name = "mcp-instance-profile"
  role = aws_iam_role.mcp_prod.name
}

# ── Secrets Manager ───────────────────────────────────────────────────────────
resource "aws_iam_role_policy" "secrets_access" {
  name   = "mcp-prod-secrets-access"
  role   = aws_iam_role.mcp_prod.id
  policy = file("${path.module}/secretsmanager-policy-v2.json")
}

resource "aws_iam_role_policy" "secrets_metadata" {
  name = "mcp-prod-secrets-metadata"
  role = aws_iam_role.mcp_prod.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "SecretsManagerMetadata"
        Effect = "Allow"
        Action = [
          "secretsmanager:DescribeSecret",
          "secretsmanager:ListSecrets",
          "secretsmanager:GetResourcePolicy"
        ]
        Resource = "*"
      }
    ]
  })
}

# ── Bedrock ───────────────────────────────────────────────────────────────────
resource "aws_iam_role_policy" "bedrock" {
  name = "mcp-prod-bedrock"
  role = aws_iam_role.mcp_prod.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "BedrockInvoke"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
          "bedrock:ListFoundationModels"
        ]
        Resource = "*"
      },
      {
        Sid    = "MarketplaceSubscriptions"
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

# ── S3 ────────────────────────────────────────────────────────────────────────
resource "aws_iam_role_policy" "s3" {
  name = "mcp-prod-s3"
  role = aws_iam_role.mcp_prod.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "LiteLLMCacheObjects"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = [
          "arn:aws:s3:::corpit-terraform-tfstate-paris/litellm-cache/*",
          "arn:aws:s3:::corpit-terraform-tfstate-paris/okta-mcp-litellm-prod/*"
        ]
      },
      {
        Sid      = "BucketList"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = "arn:aws:s3:::corpit-terraform-tfstate-paris"
        Condition = {
          StringLike = {
            "s3:prefix" = [
              "litellm-cache/*",
              "okta-mcp-litellm-prod/*"
            ]
          }
        }
      }
    ]
  })
}

# ── DynamoDB — Terraform state lock ──────────────────────────────────────────
resource "aws_iam_role_policy" "terraform_state_lock" {
  name = "mcp-prod-terraform-state-lock"
  role = aws_iam_role.mcp_prod.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "TerraformStateLock"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:DeleteItem"
        ]
        Resource = "arn:aws:dynamodb:eu-west-3:306965385748:table/terraform-state-lock"
      }
    ]
  })
}

# ── Terraform operator — EC2, IAM, CloudWatch ─────────────────────────────────
resource "aws_iam_role_policy" "terraform_operator" {
  name = "mcp-prod-terraform-operator"
  role = aws_iam_role.mcp_prod.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "IAMSelfManage"
        Effect = "Allow"
        Action = [
          "iam:GetRole",
          "iam:GetRolePolicy",
          "iam:PutRolePolicy",
          "iam:DeleteRolePolicy",
          "iam:ListRolePolicies",
          "iam:ListAttachedRolePolicies",
          "iam:GetInstanceProfile",
          "iam:CreateInstanceProfile",
          "iam:DeleteInstanceProfile",
          "iam:AddRoleToInstanceProfile",
          "iam:RemoveRoleFromInstanceProfile",
          "iam:PassRole",
          "iam:TagRole",
          "iam:UntagRole",
          "iam:CreateRole",
          "iam:DeleteRole",
          "iam:UpdateRole",
          "iam:TagInstanceProfile",
          "iam:UntagInstanceProfile"
        ]
        Resource = [
          "arn:aws:iam::306965385748:role/mcp-prod-role",
          "arn:aws:iam::306965385748:instance-profile/mcp-instance-profile",
          "arn:aws:iam::306965385748:role/github-actions-packer-role"
        ]
      },
      {
        Sid    = "EC2Describe"
        Effect = "Allow"
        Action = [
          "ec2:DescribeImages",
          "ec2:DescribeInstances",
          "ec2:DescribeInstanceAttribute",
          "ec2:DescribeInstanceTypes",
          "ec2:DescribeInstanceCreditSpecifications",
          "ec2:DescribeVpcs",
          "ec2:DescribeSubnets",
          "ec2:DescribeSecurityGroups",
          "ec2:DescribeSecurityGroupRules",
          "ec2:DescribeVolumes",
          "ec2:DescribeTags",
          "ec2:DescribeKeyPairs",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DescribeAvailabilityZones",
          "ec2:DescribeVpcAttribute"
        ]
        Resource = "*"
      },
      {
        Sid    = "EC2Manage"
        Effect = "Allow"
        Action = [
          "ec2:CreateSecurityGroup",
          "ec2:DeleteSecurityGroup",
          "ec2:AuthorizeSecurityGroupIngress",
          "ec2:AuthorizeSecurityGroupEgress",
          "ec2:RevokeSecurityGroupIngress",
          "ec2:RevokeSecurityGroupEgress",
          "ec2:RunInstances",
          "ec2:TerminateInstances",
          "ec2:StopInstances",
          "ec2:StartInstances",
          "ec2:ModifyInstanceAttribute",
          "ec2:CreateTags",
          "ec2:DeleteTags",
          "ec2:ModifySecurityGroupRules"
        ]
        Resource = "*"
      },
      {
        Sid    = "CloudWatchAlarms"
        Effect = "Allow"
        Action = [
          "cloudwatch:DescribeAlarms",
          "cloudwatch:PutMetricAlarm",
          "cloudwatch:DeleteAlarms",
          "cloudwatch:ListTagsForResource",
          "cloudwatch:TagResource",
          "cloudwatch:UntagResource"
        ]
        Resource = "*"
      }
    ]
  })
}

# ── SSM connection for packer ──────────────────────────────────────────

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.mcp_prod.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}


# ── OIDC Token creation for Packer to assume an IAM role ──────────────────────────────────────────

resource "aws_iam_role" "github_actions_packer" {
  name = "github-actions-packer-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = {
        Federated = "arn:aws:iam::306965385748:oidc-provider/token.actions.githubusercontent.com"
      }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringLike = {
          # ✅ Lock to your specific repo
          "token.actions.githubusercontent.com:sub" = "repo:kaltura/corp-it-okta-ai-agent-llm-bedrock-prod:*"
        }
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "github_actions_packer" {
  name = "github-actions-packer-policy"
  role = aws_iam_role.github_actions_packer.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # Packer needs EC2 permissions to build AMIs
        Effect = "Allow"
        Action = [
          "ec2:DescribeImages",
          "ec2:DescribeInstances",
          "ec2:DescribeInstanceStatus",
          "ec2:RunInstances",
          "ec2:StopInstances",
          "ec2:TerminateInstances",
          "ec2:CreateImage",
          "ec2:DeregisterImage",
          "ec2:DescribeSnapshots",
          "ec2:DeleteSnapshot",
          "ec2:CreateTags",
          "ec2:DescribeTags",
          "ec2:DescribeSubnets",
          "ec2:DescribeSecurityGroups",
          "ec2:DescribeVpcs",
          "ec2:DescribeKeyPairs",
          "ec2:CreateKeypair",
          "ec2:DeleteKeyPair",
          "ec2:DescribeRegions",
          "ec2:DescribeVolumes",
          "ec2:ModifyInstanceAttribute",
          "ec2:AssociateIamInstanceProfile",
          "iam:PassRole",
          "ssm:StartSession",
          "ssm:TerminateSession",
          "ssm:DescribeSessions",
          "ssm:DescribeInstanceInformation"
        ]
        Resource = "*"
      }
    ]
  })
}