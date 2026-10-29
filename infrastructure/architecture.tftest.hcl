mock_provider "aws" {
  mock_data "aws_availability_zones" {
    defaults = { names = ["eu-west-3a", "eu-west-3b"] }
  }
  mock_data "aws_caller_identity" {
    defaults = { account_id = "123456789012" }
  }
  mock_data "aws_ec2_managed_prefix_list" {
    defaults = { id = "pl-12345678" }
  }
  mock_data "aws_ssm_parameter" {
    defaults = { value = "ami-0123456789abcdef0" }
  }
}
mock_provider "aws" { alias = "global" }
mock_provider "random" {}

variables {
  sender_email = "shop@example.com"
  alarm_emails = ["member1@example.com", "member2@example.com", "member3@example.com"]
}

run "demo_plan" {
  command = plan
  variables { high_availability = false }
  assert {
    condition = (
      aws_db_instance.main.instance_class == "db.t4g.micro" &&
      aws_db_instance.main.allocated_storage == 20 &&
      aws_db_instance.main.max_allocated_storage == 0 &&
      aws_db_instance.main.storage_type == "gp2" &&
      aws_db_instance.main.backup_retention_period == 1 &&
      length(aws_db_instance.main.enabled_cloudwatch_logs_exports) == 0
    )
    error_message = "Reduced RDS must stay micro, 20 GiB gp2, no storage autoscaling, one-day backups and no exported SQL logs."
  }
  assert {
    condition     = aws_lb.api.internal
    error_message = "The domain-free API must use an internal ALB."
  }
  assert {
    condition     = aws_cloudfront_vpc_origin.api.vpc_origin_endpoint_config[0].origin_protocol_policy == "http-only" && aws_lb_listener.http.port == 80
    error_message = "The VPC origin must reach the private HTTP listener without a custom certificate."
  }
  assert {
    condition     = one(aws_cloudfront_distribution.site.viewer_certificate).cloudfront_default_certificate
    error_message = "The site must use CloudFront's default HTTPS certificate."
  }
  assert {
    condition = length(aws_sns_topic_subscription.alerts) == 3 && alltrue([
      for subscription in aws_sns_topic_subscription.alerts : contains(var.alarm_emails, subscription.endpoint)
    ])
    error_message = "Each team member needs an alert subscription."
  }
  assert {
    condition     = toset(one(aws_budgets_budget.monthly.notification).subscriber_email_addresses) == var.alarm_emails
    error_message = "Budget alerts must reach all team members."
  }
  assert {
    condition     = aws_autoscaling_group.api.min_size == 1 && !aws_db_instance.main.multi_az
    error_message = "Demo must use one API instance and single-AZ RDS."
  }
  assert {
    condition     = !aws_db_instance.main.publicly_accessible && aws_db_instance.main.storage_encrypted
    error_message = "Database must stay private and encrypted."
  }
  assert {
    condition     = alltrue([for queue in aws_sqs_queue.consumer : queue.visibility_timeout_seconds >= 180])
    error_message = "SQS visibility must be at least six times the 30-second Lambda timeout."
  }
  assert {
    condition     = length(aws_sqs_queue.dead_letter) == 3
    error_message = "Each business consumer needs its own DLQ."
  }
}

run "high_availability_plan" {
  command = plan
  variables { high_availability = true }
  assert {
    condition = (
      aws_db_instance.main.instance_class == "db.t4g.small" &&
      aws_db_instance.main.storage_type == "gp3" &&
      aws_db_instance.main.max_allocated_storage == 50 &&
      aws_db_instance.main.backup_retention_period == 7
    )
    error_message = "The optional paid HA profile must retain its database capacity and seven-day backups."
  }
  assert {
    condition     = aws_autoscaling_group.api.min_size == 2 && aws_db_instance.main.multi_az && length(aws_nat_gateway.main) == 2
    error_message = "HA requires two API instances, Multi-AZ RDS and one NAT per AZ."
  }
}
