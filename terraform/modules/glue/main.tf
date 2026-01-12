# =============================================================================
# AWS GLUE RESOURCES FOR FRAUD SCORING PIPELINE
# =============================================================================
# This module creates:
# - Snowflake connection (using Secrets Manager)
# - Glue jobs for data extraction and loading
# =============================================================================

data "aws_region" "current" {}

# =============================================================================
# SECRETS MANAGER - Snowflake Credentials
# =============================================================================

resource "aws_secretsmanager_secret" "snowflake" {
  name        = "${var.project_name}/snowflake-credentials-${var.environment}"
  description = "Snowflake connection credentials for fraud scoring pipeline"

  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# NOTE: You need to manually set the secret value after deployment
# AWS Console > Secrets Manager > Set secret value with this JSON structure:
# {
#   "account": "your-snowflake-account",
#   "user": "your-username",
#   "password": "your-password",
#   "warehouse": "ZAN_SANDBOX_DATA",
#   "database": "ZPUB_PROD",
#   "schema": "ZXM_ANALYTICS",
#   "role": "your-role"
# }

# =============================================================================
# GLUE CONNECTION - Snowflake (using JDBC)
# =============================================================================

resource "aws_glue_connection" "snowflake" {
  name            = "${var.project_name}-snowflake-${var.environment}"
  connection_type = "CUSTOM"

  connection_properties = {
    CONNECTOR_CLASS_NAME = "net.snowflake.client.jdbc.SnowflakeDriver"
    CONNECTOR_TYPE       = "Jdbc"
    CONNECTOR_URL        = "s3://${var.s3_bucket_name}/scripts/glue/snowflake-jdbc.jar"
    JDBC_CONNECTION_URL  = "jdbc:snowflake://${var.snowflake_account}.snowflakecomputing.com"
    SECRET_ID            = aws_secretsmanager_secret.snowflake.name
  }

  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# =============================================================================
# GLUE JOB - Extract Training Data
# =============================================================================

resource "aws_glue_job" "extract_training_data" {
  name     = "${var.project_name}-extract-training-${var.environment}"
  role_arn = var.glue_role_arn

  command {
    name            = "glueetl"
    script_location = "s3://${var.s3_bucket_name}/scripts/glue/extract_training_data.py"
    python_version  = "3"
  }

  default_arguments = {
    "--job-language"                     = "python"
    "--job-bookmark-option"              = "job-bookmark-disable"
    "--enable-metrics"                   = "true"
    "--enable-continuous-cloudwatch-log" = "true"
    "--enable-glue-datacatalog"          = "true"
    "--TempDir"                          = "s3://${var.s3_bucket_name}/temp/"
    
    # Custom arguments
    "--SECRET_NAME"          = aws_secretsmanager_secret.snowflake.name
    "--S3_BUCKET"            = var.s3_bucket_name
    "--S3_PREFIX"            = "training/data"
    "--SNOWFLAKE_SOURCE_TABLE" = var.snowflake_source_table
    "--DAYS_LIMIT"           = tostring(var.training_days_limit)
    
    # Snowflake JDBC driver
    "--extra-jars"           = "s3://${var.s3_bucket_name}/scripts/glue/snowflake-jdbc.jar"
  }

  glue_version      = "4.0"
  worker_type       = var.glue_worker_type
  number_of_workers = var.glue_num_workers
  timeout           = 120  # 2 hours max

  execution_property {
    max_concurrent_runs = 1
  }

  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
    Pipeline    = "training"
  }
}

# =============================================================================
# GLUE JOB - Extract Inference Data (yesterday's records)
# =============================================================================

resource "aws_glue_job" "extract_inference_data" {
  name     = "${var.project_name}-extract-inference-${var.environment}"
  role_arn = var.glue_role_arn

  command {
    name            = "glueetl"
    script_location = "s3://${var.s3_bucket_name}/scripts/glue/extract_inference_data.py"
    python_version  = "3"
  }

  default_arguments = {
    "--job-language"                     = "python"
    "--job-bookmark-option"              = "job-bookmark-disable"
    "--enable-metrics"                   = "true"
    "--enable-continuous-cloudwatch-log" = "true"
    "--enable-glue-datacatalog"          = "true"
    "--TempDir"                          = "s3://${var.s3_bucket_name}/temp/"
    
    # Custom arguments
    "--SECRET_NAME"            = aws_secretsmanager_secret.snowflake.name
    "--S3_BUCKET"              = var.s3_bucket_name
    "--S3_PREFIX"              = "inference/input"
    "--SNOWFLAKE_SOURCE_TABLE" = var.snowflake_source_table
    "--ID_COLUMN"              = var.id_column
    
    # Snowflake JDBC driver
    "--extra-jars"             = "s3://${var.s3_bucket_name}/scripts/glue/snowflake-jdbc.jar"
  }

  glue_version      = "4.0"
  worker_type       = var.glue_worker_type
  number_of_workers = var.glue_num_workers
  timeout           = 60  # 1 hour max

  execution_property {
    max_concurrent_runs = 1
  }

  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
    Pipeline    = "inference"
  }
}

# =============================================================================
# GLUE JOB - Load Scores to Snowflake
# =============================================================================

resource "aws_glue_job" "load_scores" {
  name     = "${var.project_name}-load-scores-${var.environment}"
  role_arn = var.glue_role_arn

  command {
    name            = "glueetl"
    script_location = "s3://${var.s3_bucket_name}/scripts/glue/load_scores_to_snowflake.py"
    python_version  = "3"
  }

  default_arguments = {
    "--job-language"                     = "python"
    "--job-bookmark-option"              = "job-bookmark-disable"
    "--enable-metrics"                   = "true"
    "--enable-continuous-cloudwatch-log" = "true"
    "--enable-glue-datacatalog"          = "true"
    "--TempDir"                          = "s3://${var.s3_bucket_name}/temp/"
    
    # Custom arguments
    "--SECRET_NAME"           = aws_secretsmanager_secret.snowflake.name
    "--S3_BUCKET"             = var.s3_bucket_name
    "--S3_PREFIX"             = "inference/output"
    "--TARGET_TABLE"          = var.snowflake_scores_table
    "--ID_COLUMN"             = var.id_column
    
    # Snowflake JDBC driver
    "--extra-jars"            = "s3://${var.s3_bucket_name}/scripts/glue/snowflake-jdbc.jar"
  }

  glue_version      = "4.0"
  worker_type       = var.glue_worker_type
  number_of_workers = var.glue_num_workers
  timeout           = 60  # 1 hour max

  execution_property {
    max_concurrent_runs = 1
  }

  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
    Pipeline    = "inference"
  }
}
