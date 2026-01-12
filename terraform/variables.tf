# =============================================================================
# ROOT VARIABLES
# =============================================================================

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "fraud-scoring"
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
}

# =============================================================================
# SNOWFLAKE CONFIGURATION
# =============================================================================

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
  default     = "VISIT_ID"  # UPDATE THIS based on actual schema
}

variable "training_days_limit" {
  description = "Number of days of historical data for training"
  type        = number
  default     = 15
}

# =============================================================================
# GLUE CONFIGURATION
# =============================================================================

variable "glue_worker_type" {
  description = "Glue worker type"
  type        = string
  default     = "G.1X"
}

variable "glue_num_workers" {
  description = "Number of Glue workers"
  type        = number
  default     = 2
}

# =============================================================================
# SAGEMAKER CONFIGURATION
# =============================================================================

variable "xgboost_version" {
  description = "XGBoost container version"
  type        = string
  default     = "1.7-1"
}

variable "training_instance_type" {
  description = "EC2 instance type for training"
  type        = string
  default     = "ml.m5.xlarge"
}

variable "training_instance_count" {
  description = "Number of training instances"
  type        = number
  default     = 1
}

variable "training_volume_size_gb" {
  description = "EBS volume size for training (GB)"
  type        = number
  default     = 30
}

variable "training_max_runtime_seconds" {
  description = "Maximum training time in seconds"
  type        = number
  default     = 3600
}

variable "transform_instance_type" {
  description = "EC2 instance type for batch transform"
  type        = string
  default     = "ml.m5.large"
}

variable "transform_instance_count" {
  description = "Number of batch transform instances"
  type        = number
  default     = 1
}

# =============================================================================
# SCHEDULE CONFIGURATION
# =============================================================================

variable "enable_schedules" {
  description = "Whether to enable the scheduled triggers"
  type        = bool
  default     = false
}
