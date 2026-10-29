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
mock_provider "time" {}

variables {
  sender_email = "shop@example.com"
  alarm_emails = ["member1@example.com", "member2@example.com", "member3@example.com"]
}

run "small_account_shared_concurrency" {
  command = plan
  assert {
    condition = alltrue([
      for consumer in aws_lambda_function.consumer : consumer.reserved_concurrent_executions == -1
    ]) && aws_lambda_function.migration.reserved_concurrent_executions == -1
    error_message = "Small accounts must not reserve Lambda concurrency by default."
  }
  assert {
    condition = alltrue([
      for mapping in aws_lambda_event_source_mapping.consumer : one(mapping.scaling_config).maximum_concurrency == 2
    ])
    error_message = "SQS must keep the per-consumer concurrency cap without reservations."
  }
}

run "optional_reserved_concurrency" {
  command = plan
  variables { enable_lambda_reserved_concurrency = true }
  assert {
    condition = alltrue([
      for consumer in aws_lambda_function.consumer : consumer.reserved_concurrent_executions == 2
    ]) && aws_lambda_function.migration.reserved_concurrent_executions == 1
    error_message = "Opting in must reserve two executions per consumer and one for migrations."
  }
}
