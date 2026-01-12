# =============================================================================
# GLUE JOB: Load Fraud Scores back to Snowflake
# =============================================================================
# This script:
# 1. Reads SageMaker Batch Transform output from S3
# 2. Joins scores with IDs
# 3. Loads the results to Snowflake target table
# =============================================================================

import sys
import json
import boto3
from datetime import datetime, timedelta
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col,
    lit,
    current_timestamp,
    monotonically_increasing_id,
)
from pyspark.sql.types import FloatType

# =============================================================================
# MAIN JOB
# =============================================================================


def get_snowflake_credentials(secret_name, region):
    """Retrieve Snowflake credentials from Secrets Manager"""
    client = boto3.client("secretsmanager", region_name=region)
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response["SecretString"])


def main():
    # Get job arguments
    args = getResolvedOptions(
        sys.argv,
        [
            "JOB_NAME",
            "SECRET_NAME",
            "S3_BUCKET",
            "S3_PREFIX",
            "TARGET_TABLE",
            "ID_COLUMN",
            "MODEL_VERSION",  # Passed from Step Functions
        ],
    )

    # Initialize Spark/Glue context
    sc = SparkContext()
    glueContext = GlueContext(sc)
    spark = glueContext.spark_session
    job = Job(glueContext)
    job.init(args["JOB_NAME"], args)

    # Get region from environment
    region = boto3.session.Session().region_name

    # Get Snowflake credentials
    print(f"Retrieving Snowflake credentials from: {args['SECRET_NAME']}")
    creds = get_snowflake_credentials(args["SECRET_NAME"], region)

    # Configure Snowflake connection
    sfOptions = {
        "sfURL": f"{creds['account']}.snowflakecomputing.com",
        "sfUser": creds["user"],
        "sfPassword": creds["password"],
        "sfDatabase": creds["database"],
        "sfSchema": creds["schema"],
        "sfWarehouse": creds["warehouse"],
        "sfRole": creds.get("role", ""),
    }

    # Determine paths based on yesterday's date
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    # Read IDs
    ids_path = f"s3://{args['S3_BUCKET']}/inference/input/{yesterday}/ids"
    print(f"Reading IDs from: {ids_path}")

    ids_df = spark.read.option("header", "true").csv(ids_path)

    # Add row index for joining
    ids_df = ids_df.withColumn("_row_idx", monotonically_increasing_id())

    # Read predictions from SageMaker Batch Transform output
    predictions_path = f"s3://{args['S3_BUCKET']}/{args['S3_PREFIX']}/{yesterday}"
    print(f"Reading predictions from: {predictions_path}")

    # SageMaker Batch Transform outputs one prediction per line (no header)
    predictions_df = (
        spark.read.option("header", "false")
        .csv(predictions_path)
        .withColumnRenamed("_c0", "PREDICTED_FRAUD_SCORE")
    )

    # Add row index for joining
    predictions_df = predictions_df.withColumn(
        "_row_idx", monotonically_increasing_id()
    )

    # Join IDs with predictions
    result_df = ids_df.join(predictions_df, on="_row_idx", how="inner").drop("_row_idx")

    # Add metadata columns
    result_df = (
        result_df.withColumn(
            "PREDICTED_FRAUD_SCORE", col("PREDICTED_FRAUD_SCORE").cast(FloatType())
        )
        .withColumn("MODEL_VERSION", lit(args.get("MODEL_VERSION", "unknown")))
        .withColumn("SCORED_AT", current_timestamp())
        .withColumn("SCORE_DATE", lit(yesterday))
    )

    # Rename ID column to match target table
    id_column = args["ID_COLUMN"]
    result_df = result_df.withColumnRenamed(id_column, id_column.upper())

    record_count = result_df.count()
    print(f"Records to load: {record_count:,}")

    # Preview the data
    print("Sample output:")
    result_df.show(5, truncate=False)

    # Write to Snowflake
    # Using 'append' mode to add new scores without overwriting historical data
    print(f"Writing to Snowflake table: {args['TARGET_TABLE']}")

    result_df.write.format("net.snowflake.spark.snowflake").options(**sfOptions).option(
        "dbtable", args["TARGET_TABLE"]
    ).mode("append").save()

    print(f"Successfully loaded {record_count:,} scores to Snowflake!")

    job.commit()


if __name__ == "__main__":
    main()
