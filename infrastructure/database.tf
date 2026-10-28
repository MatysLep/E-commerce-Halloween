resource "aws_db_subnet_group" "main" {
  name       = local.name
  subnet_ids = aws_subnet.database[*].id
}

resource "random_password" "database_application" {
  length  = 40
  special = false
}
resource "aws_secretsmanager_secret" "application" {
  name                    = "${local.name}-database-app-${random_id.suffix.hex}"
  recovery_window_in_days = 7
}
resource "aws_secretsmanager_secret_version" "application" {
  secret_id = aws_secretsmanager_secret.application.id
  secret_string = jsonencode({
    username = "halloween_app"
    password = random_password.database_application.result
  })
}

resource "aws_db_parameter_group" "main" {
  name   = local.name
  family = "postgres16"
  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }
}

resource "aws_db_instance" "main" {
  identifier                      = local.name
  engine                          = "postgres"
  engine_version                  = "16"
  instance_class                  = "db.t4g.micro"
  db_name                         = "halloween"
  username                        = "halloween_admin"
  manage_master_user_password     = true
  allocated_storage               = 20
  max_allocated_storage           = 0
  storage_type                    = "gp2"
  storage_encrypted               = true
  multi_az                        = false
  publicly_accessible             = false
  db_subnet_group_name            = aws_db_subnet_group.main.name
  vpc_security_group_ids          = [aws_security_group.database.id]
  parameter_group_name            = aws_db_parameter_group.main.name
  backup_retention_period         = 1
  backup_window                   = "02:00-03:00"
  maintenance_window              = "sun:03:00-sun:04:00"
  auto_minor_version_upgrade      = true
  deletion_protection             = var.deletion_protection
  skip_final_snapshot             = false
  final_snapshot_identifier       = "${local.name}-final-${random_id.suffix.hex}"
  enabled_cloudwatch_logs_exports = []
}
