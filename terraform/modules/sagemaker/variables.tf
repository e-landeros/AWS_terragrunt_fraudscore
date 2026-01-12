variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "fraud-scoring"
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
}

variable "sagemaker_role_arn" {
  description = "ARN of the IAM role for SageMaker"
  type        = string
}

variable "s3_bucket_name" {
  description = "Name of the S3 bucket for data storage"
  type        = string
}

# XGBoost configuration
variable "xgboost_version" {
  description = "XGBoost container version"
  type        = string
  default     = "1.7-1"  # Latest stable version
}

# Training instance configuration
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
  default     = 3600  # 1 hour
}

# Batch Transform configuration
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

variable "transform_max_payload_mb" {
  description = "Maximum payload size for batch transform (MB)"
  type        = number
  default     = 6
}
