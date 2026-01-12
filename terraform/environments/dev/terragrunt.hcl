# =============================================================================
# DEV ENVIRONMENT CONFIGURATION
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
  environment = "dev"
  
  # Snowflake - UPDATE THESE VALUES
  snowflake_account      = "YOUR_ACCOUNT.us-east-1"  # e.g., "xy12345.us-east-1"
  snowflake_source_table = "ZPUB_PROD.LOOKER_PDT_ZXM.H2_ZPUB_ANALYTICS_ANALYTICS_QUALITY_BY_VISIT_TRAINING"
  snowflake_scores_table = "ZPUB_PROD.ZXM_ANALYTICS.FRAUD_SCORES_DEV"
  id_column              = "VISIT_ID"  # UPDATE with actual ID column
  training_days_limit    = 15
  
  # Glue - smaller for dev
  glue_worker_type = "G.1X"
  glue_num_workers = 2
  
  # SageMaker - smaller instances for dev
  training_instance_type       = "ml.m5.large"  # Smaller than prod
  training_instance_count      = 1
  training_volume_size_gb      = 20
  training_max_runtime_seconds = 1800  # 30 minutes for dev
  
  transform_instance_type  = "ml.m5.large"
  transform_instance_count = 1
  
  # Schedules - DISABLED for dev (run manually)
  enable_schedules = false
}
