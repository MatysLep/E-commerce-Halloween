resource "random_id" "suffix" { byte_length = 4 }
resource "aws_s3_bucket" "private" {
  for_each = toset(["frontend", "artifacts", "audit"])
  bucket   = "${local.name}-${each.key}-${local.account_id}-${random_id.suffix.hex}"
  # Also remove versions and delete markers left by uploads and CloudTrail.
  force_destroy = !var.deletion_protection
}
resource "aws_s3_bucket_public_access_block" "private" {
  for_each                = aws_s3_bucket.private
  bucket                  = each.value.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_server_side_encryption_configuration" "private" {
  for_each = aws_s3_bucket.private
  bucket   = each.value.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}
resource "aws_s3_bucket_versioning" "private" {
  for_each = aws_s3_bucket.private
  bucket   = each.value.id
  versioning_configuration { status = "Enabled" }
}
resource "aws_s3_bucket_lifecycle_configuration" "private" {
  for_each = aws_s3_bucket.private
  bucket   = each.value.id
  rule {
    id     = "old-versions"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration { noncurrent_days = each.key == "audit" ? 365 : 30 }
    abort_incomplete_multipart_upload { days_after_initiation = 7 }
  }
}
resource "aws_s3_object" "release" {
  bucket      = aws_s3_bucket.private["artifacts"].id
  key         = "releases/${filesha256(var.release_path)}.tar.gz"
  source      = var.release_path
  source_hash = filesha256(var.release_path)
}
resource "aws_s3_object" "lambda" {
  bucket      = aws_s3_bucket.private["artifacts"].id
  key         = "releases/${filesha256(var.lambda_path)}.zip"
  source      = var.lambda_path
  source_hash = filesha256(var.lambda_path)
}

resource "aws_s3_bucket_policy" "frontend" {
  bucket = aws_s3_bucket.private["frontend"].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow", Principal = { Service = "cloudfront.amazonaws.com" }, Action = "s3:GetObject"
        Resource  = "${aws_s3_bucket.private["frontend"].arn}/*"
        Condition = { StringEquals = { "AWS:SourceArn" = aws_cloudfront_distribution.site.arn } }
      },
      {
        Effect    = "Deny", Principal = "*", Action = "s3:*"
        Resource  = [aws_s3_bucket.private["frontend"].arn, "${aws_s3_bucket.private["frontend"].arn}/*"]
        Condition = { Bool = { "aws:SecureTransport" = "false" } }
      }
    ]
  })
}

resource "aws_s3_bucket_policy" "audit" {
  bucket = aws_s3_bucket.private["audit"].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow", Principal = { Service = "cloudtrail.amazonaws.com" }, Action = "s3:GetBucketAcl"
        Resource  = aws_s3_bucket.private["audit"].arn
        Condition = { StringEquals = { "aws:SourceArn" = "arn:aws:cloudtrail:eu-west-3:${local.account_id}:trail/${local.name}" } }
      },
      {
        Effect   = "Allow", Principal = { Service = "cloudtrail.amazonaws.com" }, Action = "s3:PutObject"
        Resource = "${aws_s3_bucket.private["audit"].arn}/AWSLogs/${local.account_id}/*"
        Condition = { StringEquals = {
          "s3:x-amz-acl"  = "bucket-owner-full-control",
          "aws:SourceArn" = "arn:aws:cloudtrail:eu-west-3:${local.account_id}:trail/${local.name}"
        } }
      },
      {
        Effect    = "Deny", Principal = "*", Action = "s3:*"
        Resource  = [aws_s3_bucket.private["audit"].arn, "${aws_s3_bucket.private["audit"].arn}/*"]
        Condition = { Bool = { "aws:SecureTransport" = "false" } }
      }
    ]
  })
}

resource "aws_cloudtrail" "main" {
  name                          = local.name
  s3_bucket_name                = aws_s3_bucket.private["audit"].id
  include_global_service_events = true
  is_multi_region_trail         = false
  enable_log_file_validation    = true
  depends_on                    = [aws_s3_bucket_policy.audit]
}
