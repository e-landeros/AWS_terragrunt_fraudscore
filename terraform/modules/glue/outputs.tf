output "snowflake_secret_arn" {
  description = "ARN of the Snowflake credentials secret"
  value       = aws_secretsmanager_secret.snowflake.arn
}

output "snowflake_secret_name" {
  description = "Name of the Snowflake credentials secret"
  value       = aws_secretsmanager_secret.snowflake.name
}

output "extract_training_job_name" {
  description = "Name of the Glue job for extracting training data"
  value       = aws_glue_job.extract_training_data.name
}

output "extract_inference_job_name" {
  description = "Name of the Glue job for extracting inference data"
  value       = aws_glue_job.extract_inference_data.name
}

output "load_scores_job_name" {
  description = "Name of the Glue job for loading scores to Snowflake"
  value       = aws_glue_job.load_scores.name
}

output "snowflake_connection_name" {
  description = "Name of the Glue connection to Snowflake"
  value       = aws_glue_connection.snowflake.name
}
