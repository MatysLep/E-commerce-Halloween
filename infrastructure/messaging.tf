resource "aws_sns_topic" "events" {
  name              = "${local.name}-events"
  kms_master_key_id = "alias/aws/sns"
}

resource "aws_sqs_queue" "dead_letter" {
  for_each                  = local.consumers
  name                      = "${local.name}-${each.key}-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue" "consumer" {
  for_each                   = local.consumers
  name                       = "${local.name}-${each.key}"
  message_retention_seconds  = 345600
  visibility_timeout_seconds = 180
  receive_wait_time_seconds  = 20
  sqs_managed_sse_enabled    = true
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dead_letter[each.key].arn
    maxReceiveCount     = 5
  })
}

resource "aws_sqs_queue_redrive_allow_policy" "consumer" {
  for_each  = local.consumers
  queue_url = aws_sqs_queue.dead_letter[each.key].url
  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [aws_sqs_queue.consumer[each.key].arn]
  })
}

resource "aws_sqs_queue_policy" "sns" {
  for_each  = local.consumers
  queue_url = aws_sqs_queue.consumer[each.key].url
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow", Principal = { Service = "sns.amazonaws.com" }
      Action    = "sqs:SendMessage", Resource = aws_sqs_queue.consumer[each.key].arn
      Condition = { ArnEquals = { "aws:SourceArn" = aws_sns_topic.events.arn } }
    }]
  })
}

resource "aws_sns_topic_subscription" "consumer" {
  for_each             = local.consumers
  topic_arn            = aws_sns_topic.events.arn
  protocol             = "sqs"
  endpoint             = aws_sqs_queue.consumer[each.key].arn
  raw_message_delivery = true
  filter_policy        = jsonencode({ event_type = [each.value] })
  depends_on           = [aws_sqs_queue_policy.sns]
}

resource "aws_ses_email_identity" "sender" { email = var.sender_email }

resource "aws_cloudwatch_log_group" "lambda" {
  for_each          = local.consumers
  name              = "/aws/lambda/${local.name}-${each.key}"
  retention_in_days = 14
}

resource "aws_lambda_function" "consumer" {
  for_each                       = local.consumers
  function_name                  = "${local.name}-${each.key}"
  role                           = aws_iam_role.lambda[each.key].arn
  runtime                        = "python3.12"
  handler                        = "shop.handlers.handler"
  architectures                  = ["x86_64"]
  s3_bucket                      = aws_s3_bucket.private["artifacts"].id
  s3_key                         = aws_s3_object.lambda.key
  source_code_hash               = filebase64sha256(var.lambda_path)
  timeout                        = 30
  memory_size                    = 256
  reserved_concurrent_executions = 2
  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda.id]
  }
  environment {
    variables = merge(local.database_environment, {
      CONSUMER = each.key, SES_SENDER_EMAIL = var.sender_email
    })
  }
  depends_on = [aws_cloudwatch_log_group.lambda, aws_iam_role_policy.lambda, aws_route_table_association.private]
}

resource "aws_lambda_event_source_mapping" "consumer" {
  for_each                = local.consumers
  event_source_arn        = aws_sqs_queue.consumer[each.key].arn
  function_name           = aws_lambda_function.consumer[each.key].arn
  batch_size              = 1
  function_response_types = ["ReportBatchItemFailures"]
  scaling_config { maximum_concurrency = 2 }
}
