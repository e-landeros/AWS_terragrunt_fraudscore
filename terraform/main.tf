# =============================================================================
# MAIN TERRAFORM CONFIGURATION - FRAUD SCORING INFRASTRUCTURE
# =============================================================================
# This configuration combines all modules to create the complete infrastructure
# =============================================================================

# =============================================================================
# S3 BUCKETS
# =============================================================================

module "s3" {
  source = "./modules/s3"

  project_name = var.project_name
  environment  = var.environment
}

# =============================================================================
# IAM ROLES
# =============================================================================

module "iam" {
  source = "./modules/iam"

  project_name  = var.project_name
  environment   = var.environment
  s3_bucket_arn = module.s3.bucket_arn
}

# =============================================================================
# GLUE JOBS
# =============================================================================

module "glue" {
  source = "./modules/glue"

  project_name           = var.project_name
  environment            = var.environment
  s3_bucket_name         = module.s3.bucket_name
  glue_role_arn          = module.iam.glue_role_arn
  snowflake_account      = var.snowflake_account
  snowflake_source_table = var.snowflake_source_table
  snowflake_scores_table = var.snowflake_scores_table
  id_column              = var.id_column
  training_days_limit    = var.training_days_limit
  glue_worker_type       = var.glue_worker_type
  glue_num_workers       = var.glue_num_workers
}

# =============================================================================
# SAGEMAKER
# =============================================================================

module "sagemaker" {
  source = "./modules/sagemaker"

  project_name                 = var.project_name
  environment                  = var.environment
  sagemaker_role_arn           = module.iam.sagemaker_role_arn
  s3_bucket_name               = module.s3.bucket_name
  xgboost_version              = var.xgboost_version
  training_instance_type       = var.training_instance_type
  training_instance_count      = var.training_instance_count
  training_volume_size_gb      = var.training_volume_size_gb
  training_max_runtime_seconds = var.training_max_runtime_seconds
  transform_instance_type      = var.transform_instance_type
  transform_instance_count     = var.transform_instance_count
}

# =============================================================================
# STEP FUNCTIONS
# =============================================================================

module "stepfunctions" {
  source = "./modules/stepfunctions"

  project_name                 = var.project_name
  environment                  = var.environment
  stepfunctions_role_arn       = module.iam.stepfunctions_role_arn
  eventbridge_role_arn         = module.iam.eventbridge_role_arn
  sagemaker_role_arn           = module.iam.sagemaker_role_arn
  s3_bucket_name               = module.s3.bucket_name
  
  # Glue job names
  extract_training_job_name  = module.glue.extract_training_job_name
  extract_inference_job_name = module.glue.extract_inference_job_name
  load_scores_job_name       = module.glue.load_scores_job_name
  
  # SageMaker configuration
  xgboost_container_uri        = module.sagemaker.xgboost_container_uri
  xgboost_hyperparameters      = module.sagemaker.xgboost_hyperparameters
  training_instance_type       = module.sagemaker.training_instance_type
  training_instance_count      = module.sagemaker.training_instance_count
  training_volume_size_gb      = module.sagemaker.training_volume_size_gb
  training_max_runtime_seconds = module.sagemaker.training_max_runtime_seconds
  transform_instance_type      = module.sagemaker.transform_instance_type
  transform_instance_count     = module.sagemaker.transform_instance_count
  
  # Schedule configuration
  enable_schedules = var.enable_schedules
}
