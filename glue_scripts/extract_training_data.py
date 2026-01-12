# =============================================================================
# GLUE JOB: Extract Training Data from Snowflake
# =============================================================================
# This script:
# 1. Connects to Snowflake using credentials from Secrets Manager
# 2. Executes the preprocessing SQL (matching Fabian's notebook logic)
# 3. Writes the data to S3 in Parquet format for SageMaker
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
from pyspark.sql.functions import col, when, coalesce, lit, rand

# =============================================================================
# CONFIGURATION - Feature Definitions (from Snowflake ML notebook)
# =============================================================================

# Target column
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


def build_preprocessing_sql(source_table, days_limit, test_size=0.20, random_seed=42):
    """
    Build SQL that handles all preprocessing in Snowflake.
    Matches the logic from the Snowflake ML notebook.
    """
    select_parts = []
    
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
    
    # Target column
    select_parts.append(TARGET)
    
    columns_sql = ',\n        '.join(select_parts)
    
    query = f"""
    WITH cleaned_data AS (
        SELECT 
            {columns_sql},
            RANDOM({random_seed}) AS split_key
        FROM {source_table}
        WHERE {TARGET} IS NOT NULL
          AND CREATED_AT >= DATEADD(day, -{days_limit}, CURRENT_DATE())
    )
    SELECT *,
        CASE 
            WHEN split_key < {test_size} THEN 'TEST'
            ELSE 'TRAIN'
        END AS DATA_SPLIT
    FROM cleaned_data
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
        'DAYS_LIMIT'
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
    
    # Build preprocessing query
    query = build_preprocessing_sql(
        source_table=args['SNOWFLAKE_SOURCE_TABLE'],
        days_limit=int(args['DAYS_LIMIT'])
    )
    
    print("Executing Snowflake query...")
    print(f"Source table: {args['SNOWFLAKE_SOURCE_TABLE']}")
    print(f"Days limit: {args['DAYS_LIMIT']}")
    
    # Read from Snowflake
    df = spark.read \
        .format("net.snowflake.spark.snowflake") \
        .options(**sfOptions) \
        .option("query", query) \
        .load()
    
    # Get counts
    total_count = df.count()
    train_count = df.filter(col("DATA_SPLIT") == "TRAIN").count()
    test_count = df.filter(col("DATA_SPLIT") == "TEST").count()
    
    print(f"Total records: {total_count:,}")
    print(f"Train records: {train_count:,}")
    print(f"Test records: {test_count:,}")
    
    # Write to S3 partitioned by DATA_SPLIT
    today = datetime.now().strftime("%Y-%m-%d")
    output_path = f"s3://{args['S3_BUCKET']}/{args['S3_PREFIX']}/{today}"
    
    print(f"Writing to: {output_path}")
    
    # Drop the split_key column before saving
    df = df.drop("split_key")
    
    # Write train and test separately for SageMaker
    df.filter(col("DATA_SPLIT") == "TRAIN") \
        .drop("DATA_SPLIT") \
        .write \
        .mode("overwrite") \
        .parquet(f"{output_path}/train")
    
    df.filter(col("DATA_SPLIT") == "TEST") \
        .drop("DATA_SPLIT") \
        .write \
        .mode("overwrite") \
        .parquet(f"{output_path}/test")
    
    print("Training data extraction complete!")
    
    job.commit()


if __name__ == "__main__":
    main()
