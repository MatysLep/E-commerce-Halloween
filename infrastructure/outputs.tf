output "site_url" { value = "https://${aws_cloudfront_distribution.site.domain_name}" }
output "frontend_bucket" { value = aws_s3_bucket.private["frontend"].id }
output "distribution_id" { value = aws_cloudfront_distribution.site.id }
output "cognito_domain" { value = "https://${aws_cognito_user_pool_domain.customers.domain}.auth.eu-west-3.amazoncognito.com" }
output "cognito_client_id" { value = aws_cognito_user_pool_client.web.id }
output "cognito_user_pool_id" { value = aws_cognito_user_pool.customers.id }
output "autoscaling_group" { value = aws_autoscaling_group.api.name }
output "dead_letter_queues" { value = { for name, queue in aws_sqs_queue.dead_letter : name => queue.arn } }
output "queues" { value = { for name, queue in aws_sqs_queue.consumer : name => queue.arn } }
output "database_identifier" { value = aws_db_instance.main.identifier }
output "artifacts_bucket" { value = aws_s3_bucket.private["artifacts"].id }
output "audit_bucket" { value = aws_s3_bucket.private["audit"].id }
