output "training_pipeline_arn" {
  description = "ARN of the training pipeline state machine"
  value       = aws_sfn_state_machine.training_pipeline.arn
}

output "training_pipeline_name" {
  description = "Name of the training pipeline state machine"
  value       = aws_sfn_state_machine.training_pipeline.name
}

output "inference_pipeline_arn" {
  description = "ARN of the inference pipeline state machine"
  value       = aws_sfn_state_machine.inference_pipeline.arn
}

output "inference_pipeline_name" {
  description = "Name of the inference pipeline state machine"
  value       = aws_sfn_state_machine.inference_pipeline.name
}

output "training_schedule_arn" {
  description = "ARN of the training schedule EventBridge rule"
  value       = aws_cloudwatch_event_rule.training_schedule.arn
}

output "inference_schedule_arn" {
  description = "ARN of the inference schedule EventBridge rule"
  value       = aws_cloudwatch_event_rule.inference_schedule.arn
}
