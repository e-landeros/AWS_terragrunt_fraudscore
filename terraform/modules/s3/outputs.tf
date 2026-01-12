output "bucket_name" {
  description = "Name of the main S3 bucket"
  value       = aws_s3_bucket.fraud_scoring.id
}

output "bucket_arn" {
  description = "ARN of the main S3 bucket"
  value       = aws_s3_bucket.fraud_scoring.arn
}

output "training_data_prefix" {
  description = "S3 prefix for training data"
  value       = "training/data"
}

output "inference_input_prefix" {
  description = "S3 prefix for inference input"
  value       = "inference/input"
}

output "inference_output_prefix" {
  description = "S3 prefix for inference output"
  value       = "inference/output"
}

output "models_prefix" {
  description = "S3 prefix for model artifacts"
  value       = "models"
}

output "scripts_prefix" {
  description = "S3 prefix for Glue scripts"
  value       = "scripts/glue"
}
