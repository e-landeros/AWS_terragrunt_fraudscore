output "glue_role_arn" {
  description = "ARN of the Glue IAM role"
  value       = aws_iam_role.glue.arn
}

output "glue_role_name" {
  description = "Name of the Glue IAM role"
  value       = aws_iam_role.glue.name
}

output "sagemaker_role_arn" {
  description = "ARN of the SageMaker IAM role"
  value       = aws_iam_role.sagemaker.arn
}

output "sagemaker_role_name" {
  description = "Name of the SageMaker IAM role"
  value       = aws_iam_role.sagemaker.name
}

output "stepfunctions_role_arn" {
  description = "ARN of the Step Functions IAM role"
  value       = aws_iam_role.stepfunctions.arn
}

output "eventbridge_role_arn" {
  description = "ARN of the EventBridge IAM role"
  value       = aws_iam_role.eventbridge.arn
}
