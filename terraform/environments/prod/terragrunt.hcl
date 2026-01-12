# =============================================================================
# PROD ENVIRONMENT CONFIGURATION
# =============================================================================

# Include root configuration
include "root" {
  path = find_in_parent_folders()
}

# Point to the terraform code
terraform {
  source = "../.."
}

# Environment-specific inputs
inputs = {
  environment = "prod"
  
  # Snowflake - UPDATE THESE VALUES
  snowflake_account      = "YOUR_ACCOUNT.us-east-1"  # e.g., "xy12345.us-east-1"
  snowflake_source_table = "ZPUB_PROD.LOOKER_PDT_ZXM.H2_ZPUB_ANALYTICS_ANALYTICS_QUALITY_BY_VISIT_TRAINING"
  snowflake_scores_table = "ZPUB_PROD.ZXM_ANALYTICS.FRAUD_SCORES"
  id_column              = "VISIT_ID"  # UPDATE with actual ID column
  training_days_limit    = 15
  
  # Glue - larger for prod
  glue_worker_type = "G.2X"
  glue_num_workers = 5
  
  # SageMaker - production sizing (matches your notebook hyperparameters)
  training_instance_type       = "ml.m5.xlarge"
  training_instance_count      = 1
  training_volume_size_gb      = 50
  training_max_runtime_seconds = 7200  # 2 hours for prod
  
  transform_instance_type  = "ml.m5.xlarge"
  transform_instance_count = 2  # More instances for faster inference
  
  # Schedules - ENABLED for prod
  enable_schedules = true
}
