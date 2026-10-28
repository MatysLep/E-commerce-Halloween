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
  type    = bool
  default = true
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
