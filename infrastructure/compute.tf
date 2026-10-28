data "aws_ssm_parameter" "ami" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

resource "random_password" "origin" {
  length  = 48
  special = false
}

resource "aws_lb" "api" {
  name                       = local.name
  internal                   = true
  load_balancer_type         = "application"
  subnets                    = aws_subnet.private[*].id
  security_groups            = [aws_security_group.alb.id]
  drop_invalid_header_fields = true
  enable_deletion_protection = var.deletion_protection
}
resource "aws_lb_target_group" "api" {
  name                 = local.name
  port                 = 8000
  protocol             = "HTTP"
  vpc_id               = aws_vpc.main.id
  deregistration_delay = 30
  health_check {
    path                = "/api/health"
    interval            = 30
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.api.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type = "fixed-response"
    fixed_response {
      content_type = "text/plain"
      message_body = "Forbidden"
      status_code  = "403"
    }
  }
}
resource "aws_lb_listener_rule" "cloudfront" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 1
  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
  condition {
    http_header {
      http_header_name = "X-Origin-Verify"
      values           = [random_password.origin.result]
    }
  }
}

resource "aws_cloudwatch_log_group" "application" {
  name              = "/${local.name}/application"
  retention_in_days = 14
}

resource "aws_launch_template" "api" {
  name_prefix            = "${local.name}-"
  image_id               = data.aws_ssm_parameter.ami.value
  instance_type          = "t3.micro"
  vpc_security_group_ids = [aws_security_group.application.id]
  update_default_version = true
  iam_instance_profile { name = aws_iam_instance_profile.ec2.name }
  metadata_options {
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }
  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size           = 12
      volume_type           = "gp3"
      encrypted             = true
      delete_on_termination = true
    }
  }
  user_data = base64encode(templatefile("${path.module}/bootstrap.sh.tftpl", {
    artifact_uri       = "s3://${aws_s3_object.release.bucket}/${aws_s3_object.release.key}"
    artifact_sha       = filesha256(var.release_path)
    migration_function = aws_lambda_function.migration.function_name
    log_group          = aws_cloudwatch_log_group.application.name
    environment = merge(local.database_environment, {
      DB_CA_BUNDLE         = "/opt/halloween/global-bundle.pem"
      AWS_REGION           = "eu-west-3"
      COGNITO_USER_POOL_ID = aws_cognito_user_pool.customers.id
      COGNITO_CLIENT_ID    = aws_cognito_user_pool_client.web.id
      EVENT_TOPIC_ARN      = aws_sns_topic.events.arn
      PYTHONPATH           = "/opt/halloween/dependencies:/opt/halloween/backend"
      PYTHONUNBUFFERED     = "1"
    })
  }))
  tag_specifications {
    resource_type = "instance"
    tags          = { Name = local.name }
  }
}

resource "aws_autoscaling_group" "api" {
  name                      = local.name
  min_size                  = var.high_availability ? 2 : 1
  max_size                  = var.high_availability ? 4 : 2
  desired_capacity          = var.high_availability ? 2 : 1
  vpc_zone_identifier       = aws_subnet.private[*].id
  target_group_arns         = [aws_lb_target_group.api.arn]
  health_check_type         = "ELB"
  health_check_grace_period = 600
  wait_for_capacity_timeout = "20m"
  launch_template {
    id      = aws_launch_template.api.id
    version = aws_launch_template.api.latest_version
  }
  instance_refresh {
    strategy = "Rolling"
    preferences {
      min_healthy_percentage = 100
      max_healthy_percentage = 200
      instance_warmup        = 120
    }
  }
  lifecycle { ignore_changes = [desired_capacity] }
  depends_on = [aws_iam_role_policy.ec2, aws_iam_role_policy_attachment.ssm, aws_route_table_association.private, aws_lb_listener_rule.cloudfront]
}
resource "aws_autoscaling_policy" "requests" {
  name                   = "${local.name}-requests"
  autoscaling_group_name = aws_autoscaling_group.api.name
  policy_type            = "TargetTrackingScaling"
  target_tracking_configuration {
    target_value = 300
    predefined_metric_specification {
      predefined_metric_type = "ALBRequestCountPerTarget"
      resource_label         = "${aws_lb.api.arn_suffix}/${aws_lb_target_group.api.arn_suffix}"
    }
  }
}
