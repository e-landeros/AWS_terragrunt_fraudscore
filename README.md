# Fraud Scoring Infrastructure

> **Note**: This is a **simplified, production-ready reference implementation** of a batch ML training and inference pipeline on AWS using Terragrunt. It demonstrates core patterns and architectural decisions for building scalable ML pipelines, but intentionally omits advanced features like model versioning, A/B testing, feature stores, and complex monitoring to maintain clarity and focus on fundamental patterns.

This project manages the infrastructure and pipelines for training and deploying an XGBoost fraud scoring model using AWS managed services. It showcases a serverless, event-driven architecture optimized for batch processing workflows.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Training Pipeline (Every 15 Days)            │
├─────────────────────────────────────────────────────────────────┤
│ 1. EventBridge Schedule → Step Functions                        │
│ 2. Glue Job: Extract historical data from Snowflake → S3        │
│ 3. SageMaker Training Job: Train XGBoost model                  │
│ 4. SageMaker Model: Register trained model                      │
│ 5. Model artifacts saved to S3                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    Inference Pipeline (Daily)                   │
├─────────────────────────────────────────────────────────────────┤
│ 1. EventBridge Schedule → Step Functions                        │
│ 2. Glue Job: Extract yesterday's data from Snowflake → S3       │
│ 3. SageMaker Batch Transform: Score data                        │
│ 4. Glue Job: Load scores back to Snowflake                      │
└─────────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
fraud-scoring-infra/
├── terraform/
│   ├── modules/
│   │   ├── s3/                 # Data lake buckets with lifecycle policies
│   │   ├── iam/                # Service roles with least-privilege policies
│   │   ├── glue/               # Snowflake connection + ETL job definitions
│   │   ├── sagemaker/          # XGBoost container + hyperparameter config
│   │   └── stepfunctions/      # Pipeline orchestration state machines
│   │
│   └── environments/
│       ├── dev/                # Development environment config
│       │   └── terragrunt.hcl
│       └── prod/               # Production environment config
│           └── terragrunt.hcl
│
├── glue_scripts/
│   ├── extract_training_data.py    # Historical data extraction
│   ├── extract_inference_data.py  # Daily inference data extraction
│   └── load_scores_to_snowflake.py # Score loading back to warehouse
│
└── sagemaker/
    └── training_script.py          # XGBoost training script - if you need anythign not in aws XGB by default such as oridinal encoder,
```

## Configuration

### Snowflake Connection
- Database: `ZPUB_PROD`
- Schema: `ZXM_ANALYTICS`
- Warehouse: `ZAN_SANDBOX_DATA`
- Source Table: `ZPUB_PROD.LOOKER_PDT_ZXM.H2_ZPUB_ANALYTICS_ANALYTICS_QUALITY_BY_VISIT_TR*`

### Model Configuration
- Algorithm: XGBoost Regressor
- Target: `IPQS_DEVICE_FP_FRAUD_SCORE` (0-100)
- Features: 85 (3 boolean + 22 categorical + 60 numeric)

### XGBoost Hyperparameters
- `n_estimators`: 1400
- `max_depth`: 6
- `learning_rate`: 0.0769
- `subsample`: 0.958
- `colsample_bytree`: 0.707

## Deployment

```bash
# Deploy to dev
cd terraform/environments/dev
terragrunt apply

# Deploy to prod
cd terraform/environments/prod
terragrunt apply
```

## Schedules

| Pipeline   | Schedule                          | Cron Expression           |
|------------|-----------------------------------|---------------------------|
| Training   | Every 15 days (1st and 15th)      | `cron(0 2 1,15 * ? *)`    |
| Inference  | Daily at 3am UTC                  | `cron(0 3 * * ? *)`       |

---

## Architecture Patterns & Engineering Decisions

This section provides a deep dive into the architectural patterns, design decisions, and engineering alternatives considered for this pipeline.

### 1. Infrastructure as Code: Terragrunt over Terraform Workspaces

**Pattern**: Using Terragrunt for multi-environment infrastructure management with DRY (Don't Repeat Yourself) principles.

**Decision**: Terragrunt with environment-specific `terragrunt.hcl` files.

**Rationale**:
- **Explicit environment separation**: Each environment (`dev`, `prod`) has its own directory and state file, preventing accidental cross-environment changes
- **DRY configuration**: Shared root configuration in `terraform/terragrunt.hcl` reduces duplication
- **State isolation**: Separate state files per environment prevent state corruption and enable independent deployments
- **Clear variable overrides**: Environment-specific values (instance sizes, schedules) are explicit and easy to audit

**Alternatives Considered**:

| Alternative | Pros | Cons | Why Not Chosen |
|------------|------|------|----------------|
| **Terraform Workspaces** | Native Terraform feature, no extra tooling | State file sharing risks, less explicit, harder to audit | Risk of accidentally applying to wrong environment |
| **Terraform Cloud/Enterprise** | Built-in collaboration, policy as code | Cost, vendor lock-in, overkill for small teams | Unnecessary complexity and cost for this use case |
| **AWS CDK** | Type-safe, familiar to developers | Less mature ecosystem, Python/TypeScript dependency | Terraform has better AWS ML service support |
| **CloudFormation** | Native AWS, no state management | Verbose YAML/JSON, limited modularity | Terragrunt provides better module reusability |

**Trade-offs**:
- **Pros**: Clear separation, easy to understand, industry-standard pattern
- **Cons**: Requires Terragrunt installation, slight learning curve

---

### 2. Orchestration: Step Functions over Airflow/MWAA

**Pattern**: Serverless workflow orchestration using AWS Step Functions with native service integrations.

**Decision**: Step Functions state machines with EventBridge scheduling.

**Rationale**:
- **Zero infrastructure**: No clusters, databases, or workers to manage
- **Native AWS integration**: Built-in connectors for Glue, SageMaker, Lambda (no custom operators)
- **Visual debugging**: AWS Console provides execution graphs and state transitions
- **Cost-effective**: Pay per state transition (~$0.000025 per transition), no idle costs
- **Built-in retries and error handling**: Catch blocks and retry policies configured declaratively
- **Execution history**: 90 days of execution history without additional setup

**Alternatives Considered**:

| Alternative | Pros | Cons | Why Not Chosen |
|------------|------|------|----------------|
| **Apache Airflow (self-hosted)** | Rich ecosystem, Python-based, flexible | Requires EC2/ECS cluster, database, maintenance overhead | Operational burden too high for this use case |
| **MWAA (Managed Airflow)** | Managed service, no cluster management | ~$0.49/hour base cost, still requires understanding Airflow | Cost and complexity unnecessary for simple linear pipelines |
| **AWS Data Pipeline** | Native AWS service | Deprecated, limited features, poor UX | Being phased out by AWS |
| **Lambda-based orchestration** | Full control, serverless | Manual retry logic, state management complexity | Step Functions handles this better |
| **EventBridge + Lambda chains** | Simple, event-driven | No visual workflow, manual error handling | Lacks orchestration features |

**Trade-offs**:
- **Pros**: Serverless, native integrations, visual debugging, cost-effective
- **Cons**: Less flexible than Airflow for complex DAGs, JSON-based definition can be verbose
- **Note**: For complex ML pipelines with feature engineering, data quality checks, and conditional branching, Airflow might be more appropriate

---

### 3. ETL: AWS Glue over Lambda/EMR

**Pattern**: Serverless ETL using AWS Glue for Snowflake-to-S3 data extraction and loading.

**Decision**: Glue jobs with JDBC connections to Snowflake.

**Rationale**:
- **Handles large datasets**: Glue Spark engine can process terabytes without memory constraints
- **Built-in Snowflake connector**: JDBC support with connection pooling
- **Automatic scaling**: Glue workers scale based on data volume
- **Schema evolution**: Glue Data Catalog can track schema changes
- **Cost-effective for batch**: Pay per DPU-hour, only when running
- **Secrets Manager integration**: Secure credential management without hardcoding

**Alternatives Considered**:

| Alternative | Pros | Cons | Why Not Chosen |
|------------|------|------|----------------|
| **Lambda + boto3** | Simple, serverless, fast for small data | 15-minute timeout, 10GB memory limit, no Spark | Cannot handle large historical extracts |
| **EMR (Elastic MapReduce)** | Full Spark control, cost-effective at scale | Cluster management, longer startup time | Overkill for scheduled batch jobs |
| **AWS Data Pipeline** | Native AWS | Deprecated, limited features | Being phased out |
| **dbt + Airflow** | SQL-based, version-controlled transformations | Requires compute (Snowflake warehouse or dbt Cloud), different paradigm | Better for transformation, not extraction |
| **Fivetran/Stitch** | Managed, no-code | Cost per row, vendor lock-in, less control | Overkill for simple batch extracts |

**Trade-offs**:
- **Pros**: Handles large volumes, automatic scaling, Snowflake-native
- **Cons**: Cold start time (~2-3 minutes), less flexible than custom Spark code
- **Note**: For real-time streaming, consider Kinesis Data Firehose or Kafka Connect

---

### 4. Inference: Batch Transform over Real-time Endpoints

**Pattern**: Batch inference using SageMaker Batch Transform for scheduled scoring.

**Decision**: Batch Transform jobs that spin up, process, and shut down.

**Rationale**:
- **Cost optimization**: No 24/7 endpoint costs (~$0.10-0.50/hour per instance)
- **Perfect for scheduled workloads**: Daily batch scoring doesn't need real-time availability
- **Automatic scaling**: Handles variable data volumes without manual intervention
- **Simpler infrastructure**: No endpoint management, auto-scaling policies, or load balancers
- **Data locality**: Processes data directly from S3, no network transfer overhead

**Alternatives Considered**:

| Alternative | Pros | Cons | Why Not Chosen |
|------------|------|------|----------------|
| **SageMaker Real-time Endpoints** | Low latency (<100ms), always available | 24/7 costs, requires load balancing, auto-scaling config | Unnecessary for daily batch scoring |
| **SageMaker Serverless Inference** | Pay per request, no endpoint management | Still has cold starts, per-request cost higher | Batch Transform is more cost-effective for bulk processing |
| **Lambda + model artifact** | Serverless, simple | 15-minute timeout, 10GB memory limit, model loading overhead | Cannot handle large inference batches |
| **ECS/Fargate containers** | Full control, flexible | Container management, scaling logic, more complex | Batch Transform handles this automatically |
| **SageMaker Multi-Model Endpoints** | Multiple models, cost-sharing | Still requires 24/7 endpoint, complexity | Overkill for single model |

**Trade-offs**:
- **Pros**: Cost-effective, automatic scaling, simple
- **Cons**: Not suitable for real-time use cases, ~5-10 minute startup time
- **Note**: If requirements change to real-time scoring (e.g., API-based), migrate to Real-time Endpoints or Serverless Inference

---

### 5. Model Management: Simple S3 Storage over Model Registry

**Pattern**: Model artifacts stored in S3 with fixed naming convention.

**Decision**: Models saved to `s3://bucket/models/` with execution-based naming.

**Rationale**:
- **Simplicity**: No additional service to manage or learn
- **Cost-effective**: S3 storage is cheap (~$0.023/GB/month)
- **Versioning**: S3 versioning enabled for model artifact history
- **Sufficient for this use case**: Single model, retrained every 15 days, no A/B testing needed

**Alternatives Considered**:

| Alternative | Pros | Cons | Why Not Chosen |
|------------|------|------|----------------|
| **SageMaker Model Registry** | Model versioning, approval workflows, lineage tracking | Additional complexity, cost, learning curve | Overkill for simple retraining pipeline |
| **MLflow Model Registry** | Open-source, model tracking, experiment management | Requires infrastructure (tracking server), additional setup | Adds complexity without clear benefit for this use case |
| **DVC (Data Version Control)** | Git-like versioning, experiment tracking | Requires storage backend, more suited for research | Better for experimentation, not production deployment |
| **Custom metadata store (DynamoDB)** | Full control, custom workflows | Requires building and maintaining custom system | Unnecessary complexity |

**Trade-offs**:
- **Pros**: Simple, cost-effective, sufficient for basic needs
- **Cons**: No built-in model comparison, approval workflows, or metadata tracking
- **Note**: For production systems with multiple models, A/B testing, or compliance requirements, Model Registry is recommended

---

### 6. Scheduling: EventBridge over Cron/Lambda

**Pattern**: Managed event scheduling using EventBridge (formerly CloudWatch Events).

**Decision**: EventBridge rules with cron expressions triggering Step Functions.

**Rationale**:
- **Fully managed**: No EC2 instances or Lambda functions to maintain
- **Reliable**: AWS-managed service with 99.99% SLA
- **Flexible**: Supports cron, rate-based, and event-based triggers
- **Integration**: Native Step Functions integration
- **Cost-effective**: First 1 million requests/month free, then $1.00 per million

**Alternatives Considered**:

| Alternative | Pros | Cons | Why Not Chosen |
|------------|------|------|----------------|
| **EC2 with cron** | Simple, familiar | Requires EC2 instance (24/7 cost), maintenance, single point of failure | Operational overhead and cost |
| **Lambda scheduled events** | Serverless | Requires Lambda function as intermediary, less direct | EventBridge is more direct and feature-rich |
| **Airflow scheduling** | Rich scheduling features, dependencies | Requires Airflow infrastructure | Overkill for simple cron-based scheduling |
| **Step Functions Express with rate** | Built into Step Functions | Less flexible than cron expressions | EventBridge provides better scheduling control |

**Trade-offs**:
- **Pros**: Managed, reliable, cost-effective, native integration
- **Cons**: Less flexible than Airflow for complex dependencies
- **Note**: For workflows with complex dependencies (e.g., "run after training completes"), consider Step Functions callbacks or EventBridge event patterns

---

### 7. Secrets Management: Secrets Manager over Parameter Store/Environment Variables

**Pattern**: Centralized secrets management using AWS Secrets Manager.

**Decision**: Secrets Manager for Snowflake credentials with IAM-based access control.

**Rationale**:
- **Automatic rotation**: Supports automatic credential rotation (not used here, but available)
- **Audit trail**: CloudTrail integration for access logging
- **Encryption**: KMS encryption at rest and in transit
- **Glue integration**: Native Secrets Manager connector in Glue
- **Versioning**: Automatic versioning of secret values

**Alternatives Considered**:

| Alternative | Pros | Cons | Why Not Chosen |
|------------|------|------|----------------|
| **Systems Manager Parameter Store** | Lower cost ($0.05/10K parameters vs $0.40/secret/month), hierarchical | No automatic rotation, less feature-rich | Secrets Manager provides better security features |
| **Environment variables in Glue** | Simple, no additional service | Visible in Glue console, no rotation, less secure | Security best practice to use Secrets Manager |
| **Hardcoded in Terraform** | Simple | Security risk, version control exposure | Never acceptable for production |
| **HashiCorp Vault** | Advanced features, open-source | Requires infrastructure, operational overhead | Overkill for simple credential storage |

**Trade-offs**:
- **Pros**: Secure, auditable, rotation support, native Glue integration
- **Cons**: Higher cost than Parameter Store ($0.40/secret/month)
- **Note**: For non-sensitive configuration (e.g., table names), Parameter Store is more cost-effective

---

### 8. Data Lake: Single S3 Bucket with Prefixes over Multiple Buckets

**Pattern**: Logical separation using S3 prefixes within a single bucket.

**Decision**: One bucket with prefixes: `training/data/`, `inference/input/`, `inference/output/`, `models/`.

**Rationale**:
- **Simpler IAM policies**: Single bucket ARN in policies
- **Lifecycle policies**: Easier to manage with prefix-based rules
- **Cost optimization**: Single bucket reduces management overhead
- **Logical separation**: Prefixes provide clear data organization
- **Versioning**: Single versioning configuration

**Alternatives Considered**:

| Alternative | Pros | Cons | Why Not Chosen |
|------------|------|------|----------------|
| **Separate buckets per environment** | Strong isolation, easier to delete entire environment | More IAM policies, more lifecycle rules, more management | Single bucket with prefixes is simpler |
| **Separate buckets per data type** | Clear separation, different retention policies | More complex IAM, cross-bucket operations | Prefix-based separation is sufficient |
| **S3 Access Points** | Fine-grained access control | Additional complexity, newer feature | Prefix-based access is simpler for this use case |

**Trade-offs**:
- **Pros**: Simple, cost-effective, clear organization
- **Cons**: Less isolation than separate buckets (mitigated by IAM policies)
- **Note**: For multi-tenant scenarios or strict compliance requirements, separate buckets may be necessary

---

### 9. Error Handling: Step Functions Catch Blocks over External Monitoring

**Pattern**: Declarative error handling within Step Functions state machine.

**Decision**: Catch blocks in each state that route to failure states with error details.

**Rationale**:
- **Declarative**: Error handling defined in state machine, not in application code
- **Automatic retries**: Built-in retry policies with exponential backoff
- **Error visibility**: Errors captured in Step Functions execution history
- **No additional services**: No need for external error tracking (initially)

**Alternatives Considered**:

| Alternative | Pros | Cons | Why Not Chosen |
|------------|------|------|----------------|
| **CloudWatch Alarms + SNS** | Real-time alerts, integration with PagerDuty/Slack | Requires additional setup, external dependencies | Can be added later for production |
| **X-Ray tracing** | Distributed tracing, performance insights | Additional cost, setup complexity | Overkill for simple linear pipelines |
| **Custom Lambda error handlers** | Full control, custom logic | More code to maintain, additional Lambda invocations | Step Functions catch blocks are sufficient |

**Trade-offs**:
- **Pros**: Built-in, declarative, no additional services
- **Cons**: Limited to Step Functions execution history (90 days)
- **Note**: For production, add CloudWatch Alarms and SNS notifications for failures

---

### 10. Infrastructure Modules: Terraform Modules over Monolithic Configuration

**Pattern**: Modular Terraform code with reusable, composable modules.

**Decision**: Separate modules for S3, IAM, Glue, SageMaker, and Step Functions.

**Rationale**:
- **Reusability**: Modules can be reused across projects
- **Maintainability**: Changes isolated to specific modules
- **Testability**: Modules can be tested independently
- **Clarity**: Clear separation of concerns
- **DRY principle**: Shared configuration reduces duplication

**Alternatives Considered**:

| Alternative | Pros | Cons | Why Not Chosen |
|------------|------|------|----------------|
| **Monolithic Terraform** | Simple, single file | Hard to maintain, no reusability, difficult to test | Doesn't scale with complexity |
| **Terraform Cloud Modules** | Versioned, shareable | Requires Terraform Cloud account, less control | Local modules provide more flexibility |
| **Terragrunt dependencies** | Explicit dependencies between modules | More complex, requires Terragrunt | Current approach is simpler and sufficient |

**Trade-offs**:
- **Pros**: Maintainable, reusable, testable
- **Cons**: Slight learning curve, more files to manage
- **Note**: For larger teams, consider publishing modules to Terraform Registry

---

## Simplifications & Future Enhancements

This implementation intentionally omits several advanced features to maintain clarity and focus on core patterns. Here are areas for future enhancement:

### Model Management
- **SageMaker Model Registry**: For model versioning, approval workflows, and A/B testing
- **Model performance monitoring**: Track model drift, data quality metrics
- **Automatic model rollback**: Revert to previous model version on performance degradation

### Data Quality
- **Great Expectations or Deequ**: Data quality checks before training/inference
- **Feature store**: Centralized feature management (SageMaker Feature Store, Feast)
- **Data validation**: Schema validation, outlier detection

### Monitoring & Observability
- **CloudWatch Dashboards**: Custom dashboards for pipeline metrics
- **SNS alerts**: Real-time notifications for failures
- **X-Ray tracing**: Distributed tracing for performance analysis
- **Cost tracking**: Per-pipeline cost attribution

### Advanced Orchestration
- **Conditional branching**: Skip training if data quality fails
- **Parallel processing**: Process multiple data partitions in parallel
- **Manual approval gates**: Human-in-the-loop for model promotion

### Security
- **VPC endpoints**: Private connectivity to AWS services
- **KMS encryption**: Customer-managed keys for S3 and Secrets Manager
- **IAM policy boundaries**: Additional guardrails for production

---

## Cost Optimization

### Current Architecture Costs (Estimated)

**Monthly costs (assuming daily inference, bi-monthly training)**:

- **S3 Storage**: ~$5-20/month (depending on data volume)
- **Glue**: ~$10-30/month (2-4 DPU-hours per day)
- **SageMaker Training**: ~$5-15/month (1-2 training jobs per month)
- **SageMaker Batch Transform**: ~$10-25/month (daily inference)
- **Step Functions**: <$1/month (minimal state transitions)
- **EventBridge**: Free (under 1M requests/month)
- **Secrets Manager**: $0.40/month per secret

**Total**: ~$30-90/month (highly dependent on data volume and instance sizes)

### Cost Optimization Strategies

1. **Use Spot Instances for Training**: 70-90% cost savings (addressed in production config)
2. **S3 Lifecycle Policies**: Move old data to Glacier/Deep Archive (already implemented)
3. **Right-size Instances**: Monitor actual usage and adjust instance types
4. **Reserved Capacity**: For predictable workloads (not applicable for this variable schedule)

---

## Best Practices Demonstrated

1. ✅ **Least-privilege IAM**: Service roles with minimal required permissions
2. ✅ **Infrastructure as Code**: All resources defined in Terraform/Terragrunt
3. ✅ **Environment separation**: Clear dev/prod boundaries
4. ✅ **Secrets management**: No hardcoded credentials
5. ✅ **Cost optimization**: Lifecycle policies, appropriate instance sizing
6. ✅ **Error handling**: Declarative error handling in Step Functions
7. ✅ **Tagging**: Consistent resource tagging for cost allocation
8. ✅ **Encryption**: S3 encryption at rest, Secrets Manager encryption

---

## References & Further Reading

- [AWS Step Functions Best Practices](https://docs.aws.amazon.com/step-functions/latest/dg/best-practices.html)
- [SageMaker Batch Transform](https://docs.aws.amazon.com/sagemaker/latest/dg/batch-transform.html)
- [AWS Glue Best Practices](https://docs.aws.amazon.com/glue/latest/dg/best-practices.html)
- [Terragrunt Documentation](https://terragrunt.gruntwork.io/docs/)
- [MLOps Best Practices](https://ml-ops.org/content/mlops-principles)

---

## License

This project is provided as a reference implementation. 
