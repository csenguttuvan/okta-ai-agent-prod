resource "aws_cloudwatch_metric_alarm" "bedrock_high_latency" {
  alarm_name          = "bedrock-${var.bedrock_model_id}-high-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  threshold           = 3000
  metric_name         = "InvocationLatency"
  namespace           = "AWS/Bedrock"
  period              = 300
  extended_statistic  = "p95"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ModelId = var.bedrock_model_id
    Region  = var.aws_region
  }

  # Remove alarm_actions line
}

resource "aws_cloudwatch_metric_alarm" "bedrock_errors" {
  alarm_name          = "bedrock-${var.bedrock_model_id}-errors"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  threshold           = 1
  metric_name         = "ServerErrors"
  namespace           = "AWS/Bedrock"
  period              = 300
  statistic           = "Sum"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ModelId = var.bedrock_model_id
    Region  = var.aws_region
  }

  # Remove alarm_actions line
}
