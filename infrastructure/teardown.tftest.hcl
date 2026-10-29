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

run "demo_can_be_destroyed" {
  command = plan
  assert {
    condition = (
      !aws_db_instance.main.deletion_protection &&
      !aws_lb.api.enable_deletion_protection &&
      aws_cognito_user_pool.customers.deletion_protection == "INACTIVE"
    )
    error_message = "The default demo must allow RDS, ALB and Cognito deletion."
  }
  assert {
    condition     = alltrue([for bucket in aws_s3_bucket.private : bucket.force_destroy])
    error_message = "Demo teardown must empty all buckets, including object versions."
  }
  assert {
    condition = (
      aws_db_instance.main.skip_final_snapshot &&
      aws_db_instance.main.final_snapshot_identifier == null &&
      aws_db_instance.main.delete_automated_backups &&
      aws_secretsmanager_secret.application.recovery_window_in_days == 0
    )
    error_message = "Demo teardown must not retain a final snapshot, automated backups or a recoverable application secret."
  }
  assert {
    condition     = !aws_cloudfront_distribution.site.retain_on_delete && aws_cloudfront_distribution.site.wait_for_deployment
    error_message = "CloudFront must be deleted and its deployment completed before teardown continues."
  }
}

run "protected_retention" {
  command = plan
  variables { deletion_protection = true }
  assert {
    condition = (
      aws_db_instance.main.deletion_protection &&
      aws_lb.api.enable_deletion_protection &&
      aws_cognito_user_pool.customers.deletion_protection == "ACTIVE" &&
      alltrue([for bucket in aws_s3_bucket.private : !bucket.force_destroy])
    )
    error_message = "Protected deployments must block service deletion and refuse non-empty bucket deletion."
  }
  assert {
    condition = (
      !aws_db_instance.main.skip_final_snapshot &&
      aws_secretsmanager_secret.application.recovery_window_in_days == 7
    )
    error_message = "Protected deployments must retain a final snapshot and seven-day secret recovery."
  }
}
