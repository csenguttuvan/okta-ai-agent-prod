locals {
  bedrock_models = [
    "anthropic.claude-3-haiku-20240307-v1:0",
    "meta.llama3-1-8b-instruct-v1:0", 
    "mistral.mistral-large-2402-v1:0"
  ]
}


resource "aws_cloudwatch_metric_alarm" "bedrock_high_latency" {
  for_each = toset(local.bedrock_models)
  alarm_name = "bedrock-${each.value}-high-latency" 
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  threshold           = 3000
  metric_name         = "InvocationLatency"
  namespace           = "AWS/Bedrock"
  period              = 300
  extended_statistic  = "p95"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ModelId = each.value
    Region  = var.aws_region
  }
}

resource "aws_cloudwatch_metric_alarm" "bedrock_errors" {
  for_each = toset(local.bedrock_models)  
  alarm_name          = "bedrock-${replace(each.value, ".", "-")}-errors"  
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  threshold           = 1
  metric_name         = "ServerErrors"
  namespace           = "AWS/Bedrock"
  period              = 300
  statistic           = "Sum"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ModelId = each.value
    Region  = var.aws_region
  }
}

resource "aws_cloudwatch_metric_alarm" "bedrock_high_tokens" {
  for_each = toset(local.bedrock_models)  
  
  alarm_name          = "bedrock-${replace(each.value, ".", "-")}-high-tokens"  
  comparison_operator = "GreaterThanThreshold" 
  evaluation_periods  = 1  
  metric_name         = "InputTokenCount"
  namespace           = "AWS/Bedrock"
  statistic           = "Sum"
  period              = 3600
  threshold           = 1000000
  treat_missing_data  = "notBreaching"  

  dimensions = {  
    ModelId = each.value
    Region  = var.aws_region
  }
}