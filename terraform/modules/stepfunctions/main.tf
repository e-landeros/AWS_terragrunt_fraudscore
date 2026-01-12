# =============================================================================
# STEP FUNCTIONS FOR FRAUD SCORING PIPELINES
# =============================================================================
# This module creates:
# - Training pipeline state machine (runs every 15 days)
# - Inference pipeline state machine (runs daily)
# - EventBridge schedules for both
# =============================================================================

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

# =============================================================================
# TRAINING PIPELINE STATE MACHINE
# =============================================================================

resource "aws_sfn_state_machine" "training_pipeline" {
  name     = "${var.project_name}-training-pipeline-${var.environment}"
  role_arn = var.stepfunctions_role_arn

  definition = jsonencode({
    Comment = "Fraud Scoring Model Training Pipeline"
    StartAt = "ExtractTrainingData"
    States = {
      
      # Step 1: Extract training data from Snowflake to S3
      ExtractTrainingData = {
        Type     = "Task"
        Resource = "arn:aws:states:::glue:startJobRun.sync"
        Parameters = {
          JobName = var.extract_training_job_name
        }
        ResultPath = "$.glueResult"
        Next       = "TrainModel"
        Catch = [{
          ErrorEquals = ["States.ALL"]
          Next        = "TrainingFailed"
          ResultPath  = "$.error"
        }]
      }
      
      # Step 2: Train XGBoost model in SageMaker
      TrainModel = {
        Type     = "Task"
        Resource = "arn:aws:states:::sagemaker:createTrainingJob.sync"
        Parameters = {
          "TrainingJobName.$" = "States.Format('fraud-scoring-{}', $$.Execution.Name)"
          AlgorithmSpecification = {
            TrainingImage     = var.xgboost_container_uri
            TrainingInputMode = "File"
          }
          RoleArn = var.sagemaker_role_arn
          InputDataConfig = [
            {
              ChannelName = "train"
              DataSource = {
                S3DataSource = {
                  S3DataType             = "S3Prefix"
                  "S3Uri.$"              = "States.Format('s3://${var.s3_bucket_name}/training/data/{}/train', $$.Execution.StartTime)"
                  S3DataDistributionType = "FullyReplicated"
                }
              }
              ContentType = "text/csv"
            },
            {
              ChannelName = "validation"
              DataSource = {
                S3DataSource = {
                  S3DataType             = "S3Prefix"
                  "S3Uri.$"              = "States.Format('s3://${var.s3_bucket_name}/training/data/{}/test', $$.Execution.StartTime)"
                  S3DataDistributionType = "FullyReplicated"
                }
              }
              ContentType = "text/csv"
            }
          ]
          OutputDataConfig = {
            S3OutputPath = "s3://${var.s3_bucket_name}/models"
          }
          ResourceConfig = {
            InstanceCount  = var.training_instance_count
            InstanceType   = var.training_instance_type
            VolumeSizeInGB = var.training_volume_size_gb
          }
          StoppingCondition = {
            MaxRuntimeInSeconds = var.training_max_runtime_seconds
          }
          HyperParameters = var.xgboost_hyperparameters
        }
        ResultPath = "$.trainingResult"
        Next       = "CreateModel"
        Catch = [{
          ErrorEquals = ["States.ALL"]
          Next        = "TrainingFailed"
          ResultPath  = "$.error"
        }]
      }
      
      # Step 3: Register the trained model in SageMaker
      CreateModel = {
        Type     = "Task"
        Resource = "arn:aws:states:::sagemaker:createModel"
        Parameters = {
          "ModelName.$" = "States.Format('fraud-scoring-model-{}', $$.Execution.Name)"
          PrimaryContainer = {
            "Image"          = var.xgboost_container_uri
            "ModelDataUrl.$" = "$.trainingResult.ModelArtifacts.S3ModelArtifacts"
          }
          ExecutionRoleArn = var.sagemaker_role_arn
        }
        ResultPath = "$.modelResult"
        Next       = "TrainingSucceeded"
        Catch = [{
          ErrorEquals = ["States.ALL"]
          Next        = "TrainingFailed"
          ResultPath  = "$.error"
        }]
      }
      
      # Success state
      TrainingSucceeded = {
        Type = "Succeed"
      }
      
      # Failure state
      TrainingFailed = {
        Type  = "Fail"
        Error = "TrainingPipelineFailed"
        Cause = "One or more steps in the training pipeline failed"
      }
    }
  })

  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
    Pipeline    = "training"
  }
}

# =============================================================================
# INFERENCE PIPELINE STATE MACHINE
# =============================================================================

resource "aws_sfn_state_machine" "inference_pipeline" {
  name     = "${var.project_name}-inference-pipeline-${var.environment}"
  role_arn = var.stepfunctions_role_arn

  definition = jsonencode({
    Comment = "Fraud Scoring Daily Inference Pipeline"
    StartAt = "ExtractInferenceData"
    States = {
      
      # Step 1: Extract yesterday's data from Snowflake
      ExtractInferenceData = {
        Type     = "Task"
        Resource = "arn:aws:states:::glue:startJobRun.sync"
        Parameters = {
          JobName = var.extract_inference_job_name
        }
        ResultPath = "$.extractResult"
        Next       = "GetLatestModel"
        Catch = [{
          ErrorEquals = ["States.ALL"]
          Next        = "InferenceFailed"
          ResultPath  = "$.error"
        }]
      }
      
      # Step 2: Get the latest model name (most recent)
      # In production, you might use Model Registry or a Lambda for this
      GetLatestModel = {
        Type = "Pass"
        Parameters = {
          "modelName" = "${var.project_name}-model-${var.environment}"  # Use a fixed model name
        }
        ResultPath = "$.model"
        Next       = "BatchTransform"
      }
      
      # Step 3: Run Batch Transform to score the data
      BatchTransform = {
        Type     = "Task"
        Resource = "arn:aws:states:::sagemaker:createTransformJob.sync"
        Parameters = {
          "TransformJobName.$" = "States.Format('fraud-scoring-inference-{}', $$.Execution.Name)"
          "ModelName.$"        = "$.model.modelName"
          TransformInput = {
            DataSource = {
              S3DataSource = {
                S3DataType = "S3Prefix"
                "S3Uri.$"  = "States.Format('s3://${var.s3_bucket_name}/inference/input/{}/features', $$.State.EnteredTime)"
              }
            }
            ContentType = "text/csv"
            SplitType   = "Line"
          }
          TransformOutput = {
            "S3OutputPath.$" = "States.Format('s3://${var.s3_bucket_name}/inference/output/{}', $$.State.EnteredTime)"
            AssembleWith     = "Line"
          }
          TransformResources = {
            InstanceCount = var.transform_instance_count
            InstanceType  = var.transform_instance_type
          }
        }
        ResultPath = "$.transformResult"
        Next       = "LoadScoresToSnowflake"
        Catch = [{
          ErrorEquals = ["States.ALL"]
          Next        = "InferenceFailed"
          ResultPath  = "$.error"
        }]
      }
      
      # Step 4: Load scores back to Snowflake
      LoadScoresToSnowflake = {
        Type     = "Task"
        Resource = "arn:aws:states:::glue:startJobRun.sync"
        Parameters = {
          JobName   = var.load_scores_job_name
          Arguments = {
            "--MODEL_VERSION.$" = "$.model.modelName"
          }
        }
        ResultPath = "$.loadResult"
        Next       = "InferenceSucceeded"
        Catch = [{
          ErrorEquals = ["States.ALL"]
          Next        = "InferenceFailed"
          ResultPath  = "$.error"
        }]
      }
      
      # Success state
      InferenceSucceeded = {
        Type = "Succeed"
      }
      
      # Failure state
      InferenceFailed = {
        Type  = "Fail"
        Error = "InferencePipelineFailed"
        Cause = "One or more steps in the inference pipeline failed"
      }
    }
  })

  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
    Pipeline    = "inference"
  }
}

# =============================================================================
# EVENTBRIDGE SCHEDULES
# =============================================================================

# Training schedule: Every 15 days (1st and 15th of each month at 2am UTC)
resource "aws_cloudwatch_event_rule" "training_schedule" {
  name                = "${var.project_name}-training-schedule-${var.environment}"
  description         = "Trigger fraud scoring model training every 15 days"
  schedule_expression = "cron(0 2 1,15 * ? *)"
  state               = var.enable_schedules ? "ENABLED" : "DISABLED"

  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

resource "aws_cloudwatch_event_target" "training_schedule" {
  rule      = aws_cloudwatch_event_rule.training_schedule.name
  target_id = "TriggerTrainingPipeline"
  arn       = aws_sfn_state_machine.training_pipeline.arn
  role_arn  = var.eventbridge_role_arn
}

# Inference schedule: Daily at 3am UTC
resource "aws_cloudwatch_event_rule" "inference_schedule" {
  name                = "${var.project_name}-inference-schedule-${var.environment}"
  description         = "Trigger fraud scoring inference daily"
  schedule_expression = "cron(0 3 * * ? *)"
  state               = var.enable_schedules ? "ENABLED" : "DISABLED"

  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

resource "aws_cloudwatch_event_target" "inference_schedule" {
  rule      = aws_cloudwatch_event_rule.inference_schedule.name
  target_id = "TriggerInferencePipeline"
  arn       = aws_sfn_state_machine.inference_pipeline.arn
  role_arn  = var.eventbridge_role_arn
}
