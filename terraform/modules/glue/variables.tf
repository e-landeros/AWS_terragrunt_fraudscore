variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "fraud-scoring"
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
}

variable "s3_bucket_name" {
  description = "Name of the S3 bucket for data storage"
  type        = string
}

variable "glue_role_arn" {
  description = "ARN of the IAM role for Glue jobs"
  type        = string
}

# Snowflake configuration
variable "snowflake_account" {
  description = "Snowflake account identifier (e.g., xy12345.us-east-1)"
  type        = string
}

variable "snowflake_source_table" {
  description = "Fully qualified source table name"
  type        = string
  default     = "ZPUB_PROD.LOOKER_PDT_ZXM.H2_ZPUB_ANALYTICS_ANALYTICS_QUALITY_BY_VISIT_TRAINING"
}

variable "snowflake_scores_table" {
  description = "Target table for fraud scores"
  type        = string
  default     = "ZPUB_PROD.ZXM_ANALYTICS.FRAUD_SCORES"
}

variable "id_column" {
  description = "Primary key column name for joining scores back"
  type        = string
  default     = "VISIT_ID"  # UPDATE THIS based on your actual ID column
}

variable "training_days_limit" {
  description = "Number of days of historical data for training"
  type        = number
  default     = 15
}

# Glue job sizing
variable "glue_worker_type" {
  description = "Glue worker type (G.1X, G.2X, etc.)"
  type        = string
  default     = "G.1X"
}

variable "glue_num_workers" {
  description = "Number of Glue workers"
  type        = number
  default     = 2
}
