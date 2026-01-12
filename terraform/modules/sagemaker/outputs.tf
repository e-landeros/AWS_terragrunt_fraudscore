output "xgboost_container_uri" {
  description = "URI of the XGBoost container image"
  value       = local.xgboost_container_uri
}

output "xgboost_hyperparameters" {
  description = "XGBoost hyperparameters for training"
  value       = local.xgboost_hyperparameters
}

output "training_instance_type" {
  description = "Instance type for training jobs"
  value       = var.training_instance_type
}

output "training_instance_count" {
  description = "Number of training instances"
  value       = var.training_instance_count
}

output "training_volume_size_gb" {
  description = "EBS volume size for training"
  value       = var.training_volume_size_gb
}

output "training_max_runtime_seconds" {
  description = "Maximum training runtime"
  value       = var.training_max_runtime_seconds
}

output "transform_instance_type" {
  description = "Instance type for batch transform"
  value       = var.transform_instance_type
}

output "transform_instance_count" {
  description = "Number of batch transform instances"
  value       = var.transform_instance_count
}

output "transform_max_payload_mb" {
  description = "Max payload for batch transform"
  value       = var.transform_max_payload_mb
}
