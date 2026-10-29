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

run "confirmation_and_shipping_notifications" {
  command = plan
  assert {
    condition     = toset(jsondecode(aws_sns_topic_subscription.consumer["notification"].filter_policy).event_type) == toset(["CommandeCreee", "ExpeditionTerminee"])
    error_message = "Notifications must receive order confirmation and shipping events."
  }
  assert {
    condition = (
      jsondecode(aws_sns_topic_subscription.consumer["packing"].filter_policy).event_type == ["CommandeCreee"] &&
      jsondecode(aws_sns_topic_subscription.consumer["shipping"].filter_policy).event_type == ["EmballageTermine"]
    )
    error_message = "Packing and shipping must retain their own event filters."
  }
}

run "ses_sender_remains_restricted" {
  command = plan
  plan_options { target = [aws_iam_role_policy.lambda] }
  override_resource {
    target          = aws_cloudwatch_log_group.lambda
    override_during = plan
    values          = { arn = "arn:aws:logs:eu-west-3:123456789012:log-group:test" }
  }
  override_resource {
    target          = aws_sqs_queue.consumer
    override_during = plan
    values          = { arn = "arn:aws:sqs:eu-west-3:123456789012:test" }
  }
  override_resource {
    target          = aws_secretsmanager_secret.application
    override_during = plan
    values          = { arn = "arn:aws:secretsmanager:eu-west-3:123456789012:secret:test" }
  }
  assert {
    condition = alltrue([
      for statement in jsondecode(aws_iam_role_policy.lambda["notification"].policy).Statement : (
        toset(statement.Resource) == toset(["arn:aws:ses:eu-west-3:123456789012:identity/*"]) &&
        statement.Condition.StringEquals["ses:FromAddress"] == var.sender_email &&
        toset(statement.Action) == toset(["ses:SendEmail"])
      ) if contains(statement.Action, "ses:SendEmail")
      ]) && length([
      for statement in jsondecode(aws_iam_role_policy.lambda["notification"].policy).Statement : statement
      if contains(statement.Action, "ses:SendEmail")
    ]) == 1
    error_message = "SES must allow account identities only with the exact configured sender and SendEmail action."
  }
}
