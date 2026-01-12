# Deployment Guide: Fraud Scoring Pipeline

This guide walks you through deploying the fraud scoring infrastructure from scratch.

## Prerequisites

Before starting, make sure you have:

1. **AWS CLI** configured with appropriate credentials
2. **Terraform** >= 1.0.0 installed
3. **Terragrunt** installed
4. **Snowflake** access with permissions to create tables

## Step 1: Prepare AWS Account

### Create S3 Bucket for Terraform State

```bash
# Replace with your AWS account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

aws s3 mb s3://fraud-scoring-terraform-state-${AWS_ACCOUNT_ID} --region us-east-1

aws s3api put-bucket-versioning \
  --bucket fraud-scoring-terraform-state-${AWS_ACCOUNT_ID} \
  --versioning-configuration Status=Enabled
```

### Create DynamoDB Table for State Locking

```bash
aws dynamodb create-table \
  --table-name fraud-scoring-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

## Step 2: Configure Snowflake

### Find Your Snowflake Account Identifier

In Snowflake, run:
```sql
SELECT CURRENT_ACCOUNT();
-- Returns something like: xy12345
```

Your full account identifier is: `xy12345.us-east-1` (replace with your region)

### Identify Your Primary Key Column

Look at your source table to find the unique identifier:
```sql
SELECT * FROM ZPUB_PROD.LOOKER_PDT_ZXM.H2_ZPUB_ANALYTICS_ANALYTICS_QUALITY_BY_VISIT_TRAINING
LIMIT 10;
```

Common candidates: `VISIT_ID`, `TRANSACTION_ID`, `SESSION_ID`, etc.

### Create Target Tables

Run the setup script in `snowflake/setup.sql` to create the fraud scores tables.

## Step 3: Update Configuration

### Edit Environment Configuration

Open `terraform/environments/dev/terragrunt.hcl` and update:

```hcl
inputs = {
  # UPDATE THESE:
  snowflake_account = "YOUR_ACCOUNT.us-east-1"  # Your actual account
  id_column         = "VISIT_ID"                # Your actual ID column
  
  # Rest of configuration...
}
```

Do the same for `terraform/environments/prod/terragrunt.hcl`.

## Step 4: Deploy Infrastructure (Dev First)

```bash
cd terraform/environments/dev

# Initialize and plan
terragrunt init
terragrunt plan

# Review the plan, then apply
terragrunt apply
```

This creates:
- S3 bucket for data
- IAM roles
- Glue jobs (not yet runnable - need scripts)
- Step Functions state machines (not yet runnable - need secrets)
- EventBridge schedules (disabled)

## Step 5: Set Up Snowflake Credentials

After deployment, you'll see the secret name in outputs. Set the credentials:

```bash
# Get the secret name from terraform output
SECRET_NAME=$(terragrunt output -raw snowflake_secret_name)

# Set the secret value
aws secretsmanager put-secret-value \
  --secret-id ${SECRET_NAME} \
  --secret-string '{
    "account": "YOUR_ACCOUNT",
    "user": "YOUR_USERNAME",
    "password": "YOUR_PASSWORD",
    "warehouse": "ZAN_SANDBOX_DATA",
    "database": "ZPUB_PROD",
    "schema": "ZXM_ANALYTICS",
    "role": "YOUR_ROLE"
  }'
```

## Step 6: Upload Glue Scripts and JDBC Driver

```bash
# Get the S3 bucket name
BUCKET=$(terragrunt output -raw s3_bucket_name)

# Upload Glue scripts
aws s3 cp ../../../glue_scripts/extract_training_data.py s3://${BUCKET}/scripts/glue/
aws s3 cp ../../../glue_scripts/extract_inference_data.py s3://${BUCKET}/scripts/glue/
aws s3 cp ../../../glue_scripts/load_scores_to_snowflake.py s3://${BUCKET}/scripts/glue/

# Download and upload Snowflake JDBC driver
# Get latest from: https://repo1.maven.org/maven2/net/snowflake/snowflake-jdbc/
curl -L -o snowflake-jdbc.jar https://repo1.maven.org/maven2/net/snowflake/snowflake-jdbc/3.14.4/snowflake-jdbc-3.14.4.jar
aws s3 cp snowflake-jdbc.jar s3://${BUCKET}/scripts/glue/
```

## Step 7: Test the Pipeline Manually

### Test Training Pipeline

```bash
# Start training pipeline
TRAINING_ARN=$(terragrunt output -raw training_pipeline_arn)

aws stepfunctions start-execution \
  --state-machine-arn ${TRAINING_ARN} \
  --name "manual-test-$(date +%Y%m%d-%H%M%S)"
```

Monitor in AWS Console → Step Functions → Executions

### Test Inference Pipeline (after training succeeds)

```bash
# Start inference pipeline
INFERENCE_ARN=$(terragrunt output -raw inference_pipeline_arn)

aws stepfunctions start-execution \
  --state-machine-arn ${INFERENCE_ARN} \
  --name "manual-test-$(date +%Y%m%d-%H%M%S)"
```

## Step 8: Enable Scheduled Runs

Once testing passes, enable the schedules:

1. Edit `terragrunt.hcl`:
   ```hcl
   inputs = {
     enable_schedules = true
     # ...
   }
   ```

2. Apply the change:
   ```bash
   terragrunt apply
   ```

## Step 9: Deploy to Production

Once dev is working:

```bash
cd ../prod
terragrunt init
terragrunt plan
terragrunt apply
```

Repeat steps 5-7 for production.

---

## Troubleshooting

### Glue Job Fails with Connection Error

Check:
1. Snowflake credentials in Secrets Manager are correct
2. JDBC driver is uploaded to S3
3. Snowflake account identifier format is correct

### SageMaker Training Fails

Check:
1. Training data exists in S3 (`s3://{bucket}/training/data/{date}/train/`)
2. IAM role has correct permissions
3. CloudWatch Logs for detailed error messages

### Batch Transform Fails

Check:
1. Model exists (run training first)
2. Inference input data format matches training data
3. Instance type has enough memory for your data

### Step Functions Timeout

Increase timeout values in:
- `modules/glue/main.tf` → `timeout` parameter
- `modules/sagemaker/variables.tf` → `training_max_runtime_seconds`

---

## Monitoring

### CloudWatch Dashboards

Consider creating dashboards for:
- Glue job duration and success rate
- SageMaker training metrics (RMSE over time)
- Inference latency
- Cost tracking

### Alerts

Set up CloudWatch alarms for:
- Step Functions execution failures
- Glue job failures
- Long-running jobs

---

## Cost Optimization

### Dev Environment
- Use smaller instances
- Disable schedules
- Delete old training data

### Prod Environment
- Right-size instances based on actual data volume
- Consider Spot instances for training
- Set appropriate lifecycle rules on S3

---

## Architecture Decisions

### Why Batch Transform instead of Real-time Endpoint?

You're scoring yesterday's data once per day. Batch Transform:
- Spins up, processes, shuts down
- No 24/7 costs
- Perfect for scheduled batch scoring

### Why Glue instead of Lambda for Snowflake?

- Glue has native Spark integration
- Better for large data volumes
- Built-in Snowflake JDBC support
- Handles schema evolution

### Why Step Functions instead of Airflow?

- Fully serverless (no cluster to manage)
- Native AWS service integration
- Pay per execution
- Visual debugging in console
