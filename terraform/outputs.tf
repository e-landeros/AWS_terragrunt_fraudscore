# =============================================================================
# ROOT OUTPUTS
# =============================================================================

# S3
output "s3_bucket_name" {
  description = "Name of the S3 bucket"
  value       = module.s3.bucket_name
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket"
  value       = module.s3.bucket_arn
}

# Glue
output "snowflake_secret_name" {
  description = "Name of the Snowflake credentials secret (set this manually!)"
  value       = module.glue.snowflake_secret_name
}

output "extract_training_job_name" {
  description = "Name of the training data extraction Glue job"
  value       = module.glue.extract_training_job_name
}

output "extract_inference_job_name" {
  description = "Name of the inference data extraction Glue job"
  value       = module.glue.extract_inference_job_name
}

output "load_scores_job_name" {
  description = "Name of the score loading Glue job"
  value       = module.glue.load_scores_job_name
}

# Step Functions
output "training_pipeline_arn" {
  description = "ARN of the training pipeline"
  value       = module.stepfunctions.training_pipeline_arn
}

output "inference_pipeline_arn" {
  description = "ARN of the inference pipeline"
  value       = module.stepfunctions.inference_pipeline_arn
}

# IAM
output "glue_role_arn" {
  description = "ARN of the Glue IAM role"
  value       = module.iam.glue_role_arn
}

output "sagemaker_role_arn" {
  description = "ARN of the SageMaker IAM role"
  value       = module.iam.sagemaker_role_arn
}

# Helpful commands
output "next_steps" {
  description = "Next steps after deployment"
  value       = <<-EOT
    
    ╔════════════════════════════════════════════════════════════════════════╗
    ║                           NEXT STEPS                                   ║
    ╠════════════════════════════════════════════════════════════════════════╣
    ║                                                                        ║
    ║  1. Set Snowflake credentials in Secrets Manager:                      ║
    ║     aws secretsmanager put-secret-value \                              ║
    ║       --secret-id ${module.glue.snowflake_secret_name} \
    ║       --secret-string '{"account":"xxx","user":"xxx",...}'             ║
    ║                                                                        ║
    ║  2. Upload Glue scripts to S3:                                         ║
    ║     aws s3 cp glue_scripts/ s3://${module.s3.bucket_name}/scripts/glue/ --recursive ║
    ║                                                                        ║
    ║  3. Upload Snowflake JDBC driver:                                      ║
    ║     aws s3 cp snowflake-jdbc.jar s3://${module.s3.bucket_name}/scripts/glue/ ║
    ║                                                                        ║
    ║  4. Test training pipeline manually:                                   ║
    ║     aws stepfunctions start-execution \                                ║
    ║       --state-machine-arn ${module.stepfunctions.training_pipeline_arn} ║
    ║                                                                        ║
    ║  5. Enable schedules when ready:                                       ║
    ║     Set enable_schedules = true in terragrunt.hcl                      ║
    ║                                                                        ║
    ╚════════════════════════════════════════════════════════════════════════╝
    
  EOT
}
