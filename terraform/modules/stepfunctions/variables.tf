variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "fraud-scoring"
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
}

# IAM Roles
variable "stepfunctions_role_arn" {
  description = "ARN of the Step Functions IAM role"
  type        = string
}

variable "eventbridge_role_arn" {
  description = "ARN of the EventBridge IAM role"
  type        = string
}

variable "sagemaker_role_arn" {
  description = "ARN of the SageMaker IAM role"
  type        = string
}

# S3 Configuration
variable "s3_bucket_name" {
  description = "Name of the S3 bucket for data storage"
  type        = string
}

# Glue Job Names
variable "extract_training_job_name" {
  description = "Name of the Glue job for extracting training data"
  type        = string
}

variable "extract_inference_job_name" {
  description = "Name of the Glue job for extracting inference data"
  type        = string
}

variable "load_scores_job_name" {
  description = "Name of the Glue job for loading scores to Snowflake"
  type        = string
}

# SageMaker Configuration
variable "xgboost_container_uri" {
  description = "URI of the XGBoost container image"
  type        = string
}

variable "xgboost_hyperparameters" {
  description = "XGBoost hyperparameters for training"
  type        = map(string)
}

variable "training_instance_type" {
  description = "Instance type for training jobs"
  type        = string
  default     = "ml.m5.xlarge"
}

variable "training_instance_count" {
  description = "Number of training instances"
  type        = number
  default     = 1
}

variable "training_volume_size_gb" {
  description = "EBS volume size for training"
  type        = number
  default     = 30
}

variable "training_max_runtime_seconds" {
  description = "Maximum training runtime"
  type        = number
  default     = 3600
}

variable "transform_instance_type" {
  description = "Instance type for batch transform"
  type        = string
  default     = "ml.m5.large"
}

variable "transform_instance_count" {
  description = "Number of batch transform instances"
  type        = number
  default     = 1
}

# Schedule Configuration
variable "enable_schedules" {
  description = "Whether to enable the scheduled triggers"
  type        = bool
  default     = false  # Disabled by default for safety
}
