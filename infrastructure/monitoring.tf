resource "aws_sns_topic" "alerts" { name = "${local.name}-alerts" }
resource "aws_cloudwatch_metric_alarm" "outbox_age" {
  alarm_name          = "${local.name}-outbox-age-or-publisher-down"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "OutboxAgeSeconds"
  namespace           = "HalloweenShop"
  period              = 60
  statistic           = "Maximum"
  threshold           = 300
  treat_missing_data  = "breaching"
  dimensions          = { Topic = aws_sns_topic.events.arn }
  alarm_actions       = [aws_sns_topic.alerts.arn]
}
resource "aws_sns_topic_subscription" "alerts" {
  for_each  = var.alarm_emails
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = each.value
}
resource "aws_cloudwatch_metric_alarm" "dlq" {
  for_each            = local.consumers
  alarm_name          = "${local.name}-${each.key}-dlq"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Maximum"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  dimensions          = { QueueName = aws_sqs_queue.dead_letter[each.key].name }
  alarm_actions       = [aws_sns_topic.alerts.arn]
}
resource "aws_cloudwatch_metric_alarm" "queue_age" {
  for_each            = local.consumers
  alarm_name          = "${local.name}-${each.key}-delay"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "ApproximateAgeOfOldestMessage"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Maximum"
  threshold           = 300
  treat_missing_data  = "notBreaching"
  dimensions          = { QueueName = aws_sqs_queue.consumer[each.key].name }
  alarm_actions       = [aws_sns_topic.alerts.arn]
}
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  for_each            = local.consumers
  alarm_name          = "${local.name}-${each.key}-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 60
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  dimensions          = { FunctionName = aws_lambda_function.consumer[each.key].function_name }
  alarm_actions       = [aws_sns_topic.alerts.arn]
}
resource "aws_cloudwatch_metric_alarm" "unhealthy" {
  alarm_name          = "${local.name}-unhealthy"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "UnHealthyHostCount"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Maximum"
  threshold           = 0
  treat_missing_data  = "breaching"
  dimensions          = { LoadBalancer = aws_lb.api.arn_suffix, TargetGroup = aws_lb_target_group.api.arn_suffix }
  alarm_actions       = [aws_sns_topic.alerts.arn]
}
resource "aws_cloudwatch_metric_alarm" "database_connections" {
  alarm_name          = "${local.name}-database-connections"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "DatabaseConnections"
  namespace           = "AWS/RDS"
  period              = 60
  statistic           = "Maximum"
  threshold           = 40
  treat_missing_data  = "notBreaching"
  dimensions          = { DBInstanceIdentifier = aws_db_instance.main.identifier }
  alarm_actions       = [aws_sns_topic.alerts.arn]
}
resource "aws_cloudwatch_log_metric_filter" "publisher_failure" {
  name           = "${local.name}-publisher-failure"
  log_group_name = aws_cloudwatch_log_group.application.name
  pattern        = "?outbox_retry ?publisher_unavailable"
  metric_transformation {
    name      = "PublisherErrors"
    namespace = local.name
    value     = "1"
  }
}
resource "aws_cloudwatch_metric_alarm" "publisher" {
  alarm_name          = "${local.name}-publisher-failure"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = aws_cloudwatch_log_metric_filter.publisher_failure.metric_transformation[0].name
  namespace           = local.name
  period              = 60
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}
resource "aws_budgets_budget" "monthly" {
  name         = local.name
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = sort(tolist(var.alarm_emails))
  }
}
