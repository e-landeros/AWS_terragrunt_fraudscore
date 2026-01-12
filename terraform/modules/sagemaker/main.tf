# =============================================================================
# SAGEMAKER CONFIGURATION FOR FRAUD SCORING
# =============================================================================
# This module sets up:
# - XGBoost container reference
# - Training job configuration (used by Step Functions)
# - Batch Transform configuration
# =============================================================================

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

# =============================================================================
# XGBoost Container Image
# =============================================================================
# AWS provides pre-built XGBoost containers for SageMaker
# See: https://docs.aws.amazon.com/sagemaker/latest/dg/xgboost.html

locals {
  # XGBoost container URI pattern
  # Format: {account}.dkr.ecr.{region}.amazonaws.com/sagemaker-xgboost:{version}
  xgboost_container_uri = "${var.xgboost_ecr_account}.dkr.ecr.${data.aws_region.current.name}.amazonaws.com/sagemaker-xgboost:${var.xgboost_version}"
  
  # XGBoost hyperparameters (from Fabian's Snowflake ML notebook)
  xgboost_hyperparameters = {
    objective           = "reg:squarederror"  # Regression for fraud score 0-100
    num_round           = "1400"              # n_estimators
    max_depth           = "6"
    eta                 = "0.0769"            # learning_rate
    subsample           = "0.958"
    colsample_bytree    = "0.707"
    seed                = "42"
    tree_method         = "hist"              # Fast histogram-based algorithm
    eval_metric         = "rmse"
  }
}

# ECR account IDs for SageMaker XGBoost containers per region
# https://docs.aws.amazon.com/sagemaker/latest/dg/sagemaker-algo-docker-registry-paths.html
variable "xgboost_ecr_account" {
  description = "ECR account for XGBoost container (varies by region)"
  type        = string
  default     = "683313688378"  # us-east-1, update for other regions
}

# =============================================================================
# OUTPUT VALUES FOR STEP FUNCTIONS
# =============================================================================
# Step Functions will use these to construct SageMaker API calls
