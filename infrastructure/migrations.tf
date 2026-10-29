# Administrative migrations are isolated from API and business-consumer credentials.
resource "aws_iam_role" "migration" {
  name = "${local.name}-migration"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "lambda.amazonaws.com" } }]
  })
}
resource "aws_iam_role_policy" "migration" {
  role = aws_iam_role.migration.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["ec2:CreateNetworkInterface", "ec2:DescribeNetworkInterfaces", "ec2:DescribeSubnets", "ec2:DeleteNetworkInterface", "ec2:AssignPrivateIpAddresses", "ec2:UnassignPrivateIpAddresses"], Resource = "*" },
      { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = ["${aws_cloudwatch_log_group.migration.arn}:*"] },
      { Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = [aws_db_instance.main.master_user_secret[0].secret_arn, aws_secretsmanager_secret.application.arn] }
    ]
  })
}
resource "aws_cloudwatch_log_group" "migration" {
  name              = "/aws/lambda/${local.name}-migration"
  retention_in_days = 14
}
resource "aws_lambda_function" "migration" {
  function_name                  = "${local.name}-migration"
  role                           = aws_iam_role.migration.arn
  runtime                        = "python3.12"
  handler                        = "shop.migration_handler.handler"
  architectures                  = ["x86_64"]
  s3_bucket                      = aws_s3_bucket.private["artifacts"].id
  s3_key                         = aws_s3_object.lambda.key
  source_code_hash               = filebase64sha256(var.lambda_path)
  timeout                        = 120
  memory_size                    = 256
  reserved_concurrent_executions = var.enable_lambda_reserved_concurrency ? 1 : -1
  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda.id]
  }
  environment {
    variables = merge(local.database_environment, {
      DB_SECRET_ARN     = aws_db_instance.main.master_user_secret[0].secret_arn
      APP_DB_SECRET_ARN = aws_secretsmanager_secret.application.arn
    })
  }
  depends_on = [aws_cloudwatch_log_group.migration, time_sleep.lambda_iam_propagation, aws_secretsmanager_secret_version.application, aws_route_table_association.private]
}
