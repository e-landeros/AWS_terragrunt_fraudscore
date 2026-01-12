variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "fraud-scoring"
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
}

variable "s3_bucket_arn" {
  description = "ARN of the S3 bucket for data storage"
  type        = string
}
