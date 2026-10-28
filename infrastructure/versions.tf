terraform {
  required_version = ">= 1.10, < 2.0"
  required_providers {
    aws    = { source = "hashicorp/aws", version = "~> 6.0" }
    random = { source = "hashicorp/random", version = "~> 3.7" }
  }
}

provider "aws" {
  region = "eu-west-3"
  default_tags {
    tags = { Project = var.project_name, ManagedBy = "Terraform" }
  }
}

# CloudFront WAF is a global resource managed through us-east-1.
provider "aws" {
  alias  = "global"
  region = "us-east-1"
}

data "aws_caller_identity" "current" {}
data "aws_availability_zones" "available" { state = "available" }

locals {
  name       = var.project_name
  azs        = slice(data.aws_availability_zones.available.names, 0, 2)
  nat_count  = var.high_availability ? 2 : 1
  account_id = data.aws_caller_identity.current.account_id
  consumers = {
    packing      = "CommandeCreee"
    shipping     = "EmballageTermine"
    notification = "CommandeCreee"
  }
  database_environment = {
    APP_ENV       = "aws"
    DB_HOST       = aws_db_instance.main.address
    DB_NAME       = aws_db_instance.main.db_name
    DB_SECRET_ARN = aws_secretsmanager_secret.application.arn
    DB_CA_BUNDLE  = "/var/task/global-bundle.pem"
  }
}
