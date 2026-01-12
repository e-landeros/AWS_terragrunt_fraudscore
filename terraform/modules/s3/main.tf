# =============================================================================
# S3 BUCKETS FOR FRAUD SCORING PIPELINE
# =============================================================================
# This module creates:
# - Main data bucket (training data, inference data, model artifacts)
# - Glue scripts bucket
# =============================================================================

resource "aws_s3_bucket" "fraud_scoring" {
  bucket = "${var.project_name}-${var.environment}"

  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

resource "aws_s3_bucket_versioning" "fraud_scoring" {
  bucket = aws_s3_bucket.fraud_scoring.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "fraud_scoring" {
  bucket = aws_s3_bucket.fraud_scoring.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "fraud_scoring" {
  bucket = aws_s3_bucket.fraud_scoring.id

  # Clean up old training data after 90 days
  rule {
    id     = "training-data-cleanup"
    status = "Enabled"

    filter {
      prefix = "training/data/"
    }

    expiration {
      days = 90
    }
  }

  # Clean up old inference input/output after 30 days
  rule {
    id     = "inference-cleanup"
    status = "Enabled"

    filter {
      prefix = "inference/"
    }

    expiration {
      days = 30
    }
  }

  # Keep model artifacts longer (365 days)
  rule {
    id     = "models-archive"
    status = "Enabled"

    filter {
      prefix = "models/"
    }

    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }

    expiration {
      days = 365
    }
  }
}

resource "aws_s3_bucket_public_access_block" "fraud_scoring" {
  bucket = aws_s3_bucket.fraud_scoring.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# =============================================================================
# CREATE FOLDER STRUCTURE (using empty objects)
# =============================================================================

resource "aws_s3_object" "training_data" {
  bucket = aws_s3_bucket.fraud_scoring.id
  key    = "training/data/.gitkeep"
  source = "/dev/null"
}

resource "aws_s3_object" "inference_input" {
  bucket = aws_s3_bucket.fraud_scoring.id
  key    = "inference/input/.gitkeep"
  source = "/dev/null"
}

resource "aws_s3_object" "inference_output" {
  bucket = aws_s3_bucket.fraud_scoring.id
  key    = "inference/output/.gitkeep"
  source = "/dev/null"
}

resource "aws_s3_object" "models" {
  bucket = aws_s3_bucket.fraud_scoring.id
  key    = "models/.gitkeep"
  source = "/dev/null"
}

resource "aws_s3_object" "scripts" {
  bucket = aws_s3_bucket.fraud_scoring.id
  key    = "scripts/glue/.gitkeep"
  source = "/dev/null"
}
