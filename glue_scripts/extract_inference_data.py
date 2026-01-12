# =============================================================================
# GLUE JOB: Extract Inference Data from Snowflake
# =============================================================================
# This script:
# 1. Connects to Snowflake using credentials from Secrets Manager
# 2. Extracts yesterday's records (no labels needed)
# 3. Applies same preprocessing as training
# 4. Writes to S3 in CSV format for SageMaker Batch Transform
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
from pyspark.sql.functions import col

# =============================================================================
# CONFIGURATION - Feature Definitions (must match training)
# =============================================================================

# Target column (not included in inference - we're predicting this)
TARGET = 'IPQS_DEVICE_FP_FRAUD_SCORE'

# Boolean columns - convert to 0/1 (NULL → 0)
BOOLEAN_FEATURES = [
    'IP_API_HOSTING',
    'IP_API_MOBILE',
    'IP_API_PROXY',
]

# Categorical columns - NULL → 'MISSING'
CATEGORICAL_FEATURES = [
    'IP_API_CITY',
    'IP_API_COUNTRY',
    'IP_API_COUNTRY_CODE',
    'IP_API_ORG',
    'IP_API_REGION',
    'IP_API_STATUS',
    'IP_API_TIMEZONE',
    'BROWSERNAME',
    'BROWSERVERSION',
    'DEVICECATEGORY',
    'DEVICETYPE',
    'OPERATINGSYSTEM',
    'OPERATINGSYSTEMVERSION',
    'PROPERTY_NAME',
    'PUBLISHER_NAME',
    'UTM_CONTENT',
    'UTM_TERM',
    'UTM_MEDIUM',
    'UTM_SOURCE',
    'VISITOR_TYPE',
    'DOMAIN',
    'STATE',
    'EMAIL_VERIFICATION_RESPONSE',
]

# Numeric columns - NULL → 0
NUMERIC_FEATURES = [
    'IP_API_LATITUDE',
    'IP_API_LONGITUDE',
    'VISIT_COUNT_FORM_COMPLETED_MEASURE',
    'VISIT_COUNT_FORM_STARTED_MEASURE',
    'VISIT_COUNT_VISIT_TO_PAGE_1_MEASURE',
    'VISIT_COUNT_PAGE_1_TO_PAGE_2_MEASURE',
    'VISIT_COUNT_PAGE_2_TO_PAGE_3_MEASURE',
    'SECONDS_SPENT_FORM_MEASURE',
    'SECONDS_SPENT_FORM_COMPLETE_MEASURE',
    'SECONDS_SPENT_PAGE_1_TO_2_MEASURE',
    'SECONDS_SPENT_PAGE_2_TO_3_MEASURE',
    'SECONDS_SPENT_VISIT_TO_PAGE_1_MEASURE',
    'SECONDS_SPENT_ZAN_PRIMARY_MEASURE',
    'SECONDS_SPENT_ZAN_PRIMARY_COMPLETE_MEASURE',
    'SECONDS_SPENT_ZAN_PRIMARY_INCOMPLETE_MEASURE',
    'VISIT_COUNT_ZAN_COMPLETED_LESS_THAN_7_SECONDS_MEASURE',
    'VISIT_COUNT_ZAN_PRIMARY_COMPLETE_MEASURE',
    'VISIT_COUNT_ZAN_PRIMARY_LOAD_MEASURE',
    'VISIT_COUNT_ZAN_SPENT_MORE_THAN_5_MINS_MEASURE',
    'LTV_PIXEL_CAMPAIGN_CLICKS_MEASURE',
    'LTV_PIXEL_CAMPAIGN_IMPRESSIONS_MEASURE',
    'LTV_PIXEL_PURCHASE_COUNT_MEASURE',
    'LTV_PIXEL_REVENUE_MEASURE',
    'LTV_PIXEL_ADVERTISER_COST_MEASURE',
    'FICTITIOUS_CHARACTERS_NAME_MEASURE',
    'FLAGGED_ADDRESS_MEASURE',
    'FLAGGED_NAME_MEASURE',
    'FNLN_EMAIL_STRING_MEASURE',
    'IPQS_FLAGGED_LOCATION_MEASURE',
    'MISSING_ADDRESS_NUMBER_MEASURE',
    'MISSING_STREET_TYPE_MEASURE',
    'VISITS_WITH_PII_COMPLETE_VISITS',
    'RECYCLED_IP_ADDRESS_MEASURE',
    'SINGLE_LETTER_STRING_NAME_MEASURE',
    'THREE_LETTER_STRING_NAME_MEASURE',
    'TWO_LETTER_STRING_NAME_MEASURE',
    'THREE_LETTER_STRING_LEFT_RIGHT_NAME_MEASURE',
    'VULGAR_WORDS_NAME_MEASURE',
    'VISIT_COUNT_ZAN_PRIMARY_INCOMPLETE_MEASURE',
    'POSITION_1_ANSWERS_MEASURE',
    'CAMPAIGN_CLICKS_MEASURE',
    'CAMPAIGN_CONVERSIONS_MEASURE',
    'CAMPAIGN_IMPRESSIONS_MEASURE',
    'CPA_CLICKS_MEASURE',
    'CPA_CONVERSIONS_MEASURE',
    'CPA_IMPRESSIONS_MEASURE',
    'CPA_REVENUE_MEASURE',
    'CPC_CONVERSIONS_MEASURE',
    'CPC_IMPRESSIONS_MEASURE',
    'CPC_REVENUE_MEASURE',
    'CPL_CONVERSIONS_MEASURE',
    'CPL_IMPRESSIONS_MEASURE',
    'CPL_REVENUE_MEASURE',
    'TOTAL_GROSS_REVENUE_MEASURE',
    'LAST_POSITION_ANSWERS_MEASURE',
    'TOTAL_NET_REVENUE_MEASURE',
    'PREPING_SCORE_1_PRIMARY_VISITS',
    'PREPING_SCORE_2_PRIMARY_VISITS',
    'PREPING_SCORE_3_PRIMARY_VISITS',
    'PREPING_SCORE_4_PRIMARY_VISITS',
    'PREPING_SCORE_5_PRIMARY_VISITS',
    'PRIMARY_GROSS_REVENUE_MEASURE',
    'QUESTIONS_ANSWERED_MEASURE',
    'QUESTIONS_IMPRESSED_MEASURE',
    'QUESTIONS_IMPRESSED_FOR_POSITION_RATE_MEASURE',
    'ZAN_SECONDARY_END_OF_PLACEMENT_VISITS_MEASURE',
    'QUESTIONS_ANSWERED_FOR_POSITION_RATE_MEASURE',
    'ZAN_SECONDARY_PLACEMENT_VISITS_MEASURE',
    'SECONDARY_NET_REVENUE_MEASURE',
]

# =============================================================================
# MAIN JOB
# =============================================================================

def get_snowflake_credentials(secret_name, region):
    """Retrieve Snowflake credentials from Secrets Manager"""
    client = boto3.client('secretsmanager', region_name=region)
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])


def build_inference_sql(source_table, id_column):
    """
    Build SQL for inference data extraction.
    - Includes ID column for joining scores back
    - Applies same preprocessing as training
    - Filters to yesterday's data only
    - Does NOT require target column (we're predicting it)
    """
    select_parts = []
    
    # Include ID column first
    select_parts.append(id_column)
    
    # Boolean columns → 0/1 with NULL → 0
    for col_name in BOOLEAN_FEATURES:
        select_parts.append(
            f"COALESCE(CASE WHEN {col_name} = TRUE THEN 1 ELSE 0 END, 0) AS {col_name}"
        )
    
    # Categorical columns → COALESCE with 'MISSING'
    for col_name in CATEGORICAL_FEATURES:
        select_parts.append(
            f"COALESCE(TO_VARCHAR({col_name}), 'MISSING') AS {col_name}"
        )
    
    # Numeric columns → COALESCE with 0
    for col_name in NUMERIC_FEATURES:
        select_parts.append(
            f"COALESCE({col_name}, 0) AS {col_name}"
        )
    
    columns_sql = ',\n        '.join(select_parts)
    
    # Get yesterday's data
    query = f"""
    SELECT 
        {columns_sql}
    FROM {source_table}
    WHERE DATE(CREATED_AT) = DATEADD(day, -1, CURRENT_DATE())
    """
    
    return query


def main():
    # Get job arguments
    args = getResolvedOptions(sys.argv, [
        'JOB_NAME',
        'SECRET_NAME',
        'S3_BUCKET',
        'S3_PREFIX',
        'SNOWFLAKE_SOURCE_TABLE',
        'ID_COLUMN'
    ])
    
    # Initialize Spark/Glue context
    sc = SparkContext()
    glueContext = GlueContext(sc)
    spark = glueContext.spark_session
    job = Job(glueContext)
    job.init(args['JOB_NAME'], args)
    
    # Get region from environment
    region = boto3.session.Session().region_name
    
    # Get Snowflake credentials
    print(f"Retrieving Snowflake credentials from: {args['SECRET_NAME']}")
    creds = get_snowflake_credentials(args['SECRET_NAME'], region)
    
    # Configure Snowflake connection
    sfOptions = {
        "sfURL": f"{creds['account']}.snowflakecomputing.com",
        "sfUser": creds['user'],
        "sfPassword": creds['password'],
        "sfDatabase": creds['database'],
        "sfSchema": creds['schema'],
        "sfWarehouse": creds['warehouse'],
        "sfRole": creds.get('role', ''),
    }
    
    # Build inference query
    query = build_inference_sql(
        source_table=args['SNOWFLAKE_SOURCE_TABLE'],
        id_column=args['ID_COLUMN']
    )
    
    print("Executing Snowflake query for yesterday's data...")
    print(f"Source table: {args['SNOWFLAKE_SOURCE_TABLE']}")
    print(f"ID column: {args['ID_COLUMN']}")
    
    # Read from Snowflake
    df = spark.read \
        .format("net.snowflake.spark.snowflake") \
        .options(**sfOptions) \
        .option("query", query) \
        .load()
    
    record_count = df.count()
    print(f"Records to score: {record_count:,}")
    
    if record_count == 0:
        print("WARNING: No records found for yesterday. Exiting.")
        job.commit()
        return
    
    # Write to S3
    # For SageMaker Batch Transform, we need:
    # 1. A file with IDs (to join back later)
    # 2. A file with features only (for prediction)
    
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    output_path = f"s3://{args['S3_BUCKET']}/{args['S3_PREFIX']}/{yesterday}"
    
    print(f"Writing to: {output_path}")
    
    # Save IDs separately (for joining scores back)
    df.select(args['ID_COLUMN']) \
        .write \
        .mode("overwrite") \
        .option("header", "true") \
        .csv(f"{output_path}/ids")
    
    # Save features only (for SageMaker Batch Transform)
    # XGBoost expects CSV without headers, features only
    feature_cols = BOOLEAN_FEATURES + CATEGORICAL_FEATURES + NUMERIC_FEATURES
    df.select(feature_cols) \
        .write \
        .mode("overwrite") \
        .option("header", "false") \
        .csv(f"{output_path}/features")
    
    # Also save complete data for reference/debugging
    df.write \
        .mode("overwrite") \
        .option("header", "true") \
        .parquet(f"{output_path}/complete")
    
    print("Inference data extraction complete!")
    print(f"  IDs saved to: {output_path}/ids/")
    print(f"  Features saved to: {output_path}/features/")
    
    job.commit()


if __name__ == "__main__":
    main()
