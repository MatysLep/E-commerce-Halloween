variable "aws_profile" {
  type        = string
  default     = null
  description = "Optional named AWS CLI profile used by Terraform and frontend publication."
  validation {
    condition     = var.aws_profile == null ? true : length(trimspace(var.aws_profile)) > 0
    error_message = "Use a non-empty profile name, or null for the default credential chain."
  }
}

variable "expected_account_id" {
  type        = string
  default     = null
  description = "Optional 12-digit account ID; AWS providers refuse credentials from another account."
  validation {
    condition     = var.expected_account_id == null ? true : can(regex("^[0-9]{12}$", var.expected_account_id))
    error_message = "expected_account_id must contain exactly 12 digits, or be null."
  }
}

variable "project_name" {
  type    = string
  default = "halloween-shop"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,23}$", var.project_name))
    error_message = "Use 3–24 lowercase letters, digits or hyphens, starting with a letter."
  }
}

variable "high_availability" {
  type        = bool
  default     = false
  description = "Two EC2 instances, RDS Multi-AZ and one NAT per AZ. False is a paid demo without HA."
}

variable "sender_email" {
  type        = string
  description = "SES sender address; its owner must complete email verification."
  validation {
    condition     = can(regex("^[^@]+@[^@]+\\.[^@]+$", var.sender_email))
    error_message = "Provide an email address."
  }
}

variable "alarm_emails" {
  type        = set(string)
  description = "Addresses receiving monitoring and budget alerts; confirm each SNS subscription."
  validation {
    condition = length(var.alarm_emails) >= 1 && length(var.alarm_emails) <= 10 && alltrue([
      for email in var.alarm_emails : can(regex("^[^@]+@[^@]+\\.[^@]+$", email))
    ])
    error_message = "Provide between 1 and 10 distinct email addresses."
  }
}

variable "monthly_budget_usd" {
  type    = number
  default = 20
  validation {
    condition     = var.monthly_budget_usd > 0
    error_message = "Budget must be positive. It is an alert, not a spending cap."
  }
}

variable "deletion_protection" {
  type        = bool
  default     = false
  nullable    = false
  description = "False allows complete demo teardown (S3 versions, RDS backups and application secret included). True protects RDS/ALB/Cognito, refuses non-empty S3 deletion and retains a final snapshot and a seven-day secret recovery window. Apply changes before destroy."
}

variable "enable_waf" {
  type    = bool
  default = true
}

variable "release_path" {
  type    = string
  default = "../build/release.tar.gz"
}

variable "lambda_path" {
  type    = string
  default = "../build/lambda.zip"
}

variable "enable_lambda_reserved_concurrency" {
  type        = bool
  default     = false
  description = "Reserve 2 executions per consumer and 1 for migrations only when the account quota permits it. SQS mappings remain limited to 2 without reservations."
}
