resource "aws_iam_role" "ec2" {
  name = "${local.name}-ec2"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "ec2.amazonaws.com" } }]
  })
}
resource "aws_iam_instance_profile" "ec2" {
  name = local.name
  role = aws_iam_role.ec2.name
}
resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}
resource "aws_iam_role_policy" "ec2" {
  role = aws_iam_role.ec2.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["s3:GetObject"], Resource = [aws_s3_object.release.arn] },
      { Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = [local.database_environment.DB_SECRET_ARN] },
      { Effect = "Allow", Action = ["sns:Publish"], Resource = [aws_sns_topic.events.arn] },
      { Effect = "Allow", Action = ["lambda:InvokeFunction"], Resource = [aws_lambda_function.migration.arn] },
      {
        Effect    = "Allow", Action = ["cloudwatch:PutMetricData"], Resource = "*"
        Condition = { StringEquals = { "cloudwatch:namespace" = "HalloweenShop" } }
      },
      {
        Effect    = "Allow", Action = ["kms:GenerateDataKey*", "kms:Decrypt"], Resource = "*"
        Condition = { StringEquals = { "kms:ViaService" = "sns.eu-west-3.amazonaws.com", "kms:CallerAccount" = local.account_id } }
      },
      { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogStreams"], Resource = ["${aws_cloudwatch_log_group.application.arn}:*"] }
    ]
  })
}

resource "aws_iam_role" "lambda" {
  for_each = local.consumers
  name     = "${local.name}-${each.key}"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "lambda.amazonaws.com" } }]
  })
}
resource "aws_iam_role_policy" "lambda" {
  for_each = local.consumers
  role     = aws_iam_role.lambda[each.key].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat([
      {
        Effect = "Allow", Action = ["ec2:CreateNetworkInterface", "ec2:DescribeNetworkInterfaces", "ec2:DescribeSubnets", "ec2:DeleteNetworkInterface", "ec2:AssignPrivateIpAddresses", "ec2:UnassignPrivateIpAddresses"], Resource = "*"
      },
      { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = ["${aws_cloudwatch_log_group.lambda[each.key].arn}:*"] },
      { Effect = "Allow", Action = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"], Resource = [aws_sqs_queue.consumer[each.key].arn] },
      { Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = [local.database_environment.DB_SECRET_ARN] }
      ], each.key == "notification" ? [{
        # SES can authorize recipient identities too in sandbox. Keep sending
        # limited to this account/region and the exact configured From address.
        Effect    = "Allow", Action = ["ses:SendEmail"], Resource = ["arn:aws:ses:eu-west-3:${local.account_id}:identity/*"]
        Condition = { StringEquals = { "ses:FromAddress" = var.sender_email } }
    }] : [])
  })
}

# IAM writes are eventually consistent. Lambda can fail asynchronously even after
# PutRolePolicy succeeds; wait before configuring its private network interfaces.
resource "time_sleep" "lambda_iam_propagation" {
  create_duration = "30s"
  triggers = {
    policy_revision = sha256(jsonencode({
      consumers = {
        for name, policy in aws_iam_role_policy.lambda : name => {
          id     = policy.id
          policy = policy.policy
        }
      }
      migration = {
        id     = aws_iam_role_policy.migration.id
        policy = aws_iam_role_policy.migration.policy
      }
    }))
  }
}
