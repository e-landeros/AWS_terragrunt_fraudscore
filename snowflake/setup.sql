-- =============================================================================
-- SNOWFLAKE SETUP SCRIPT
-- =============================================================================
-- Run this in Snowflake to create the target table for fraud scores
-- =============================================================================

USE DATABASE ZPUB_PROD;
USE SCHEMA ZXM_ANALYTICS;
USE WAREHOUSE ZAN_SANDBOX_DATA;

-- =============================================================================
-- DEV TARGET TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS FRAUD_SCORES_DEV (
    VISIT_ID        VARCHAR(255),      -- Primary key (UPDATE if different)
    PREDICTED_FRAUD_SCORE FLOAT,       -- Model prediction (0-100)
    MODEL_VERSION   VARCHAR(255),      -- Model version/name for tracking
    SCORE_DATE      DATE,              -- Date of the scored data
    SCORED_AT       TIMESTAMP_NTZ,     -- When the scoring ran
    CREATED_AT      TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- Index for faster lookups
CREATE OR REPLACE INDEX IDX_FRAUD_SCORES_DEV_VISIT_ID 
ON FRAUD_SCORES_DEV (VISIT_ID);

CREATE OR REPLACE INDEX IDX_FRAUD_SCORES_DEV_SCORE_DATE 
ON FRAUD_SCORES_DEV (SCORE_DATE);

-- =============================================================================
-- PROD TARGET TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS FRAUD_SCORES (
    VISIT_ID        VARCHAR(255),      -- Primary key (UPDATE if different)
    PREDICTED_FRAUD_SCORE FLOAT,       -- Model prediction (0-100)
    MODEL_VERSION   VARCHAR(255),      -- Model version/name for tracking
    SCORE_DATE      DATE,              -- Date of the scored data
    SCORED_AT       TIMESTAMP_NTZ,     -- When the scoring ran
    CREATED_AT      TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- Index for faster lookups
CREATE OR REPLACE INDEX IDX_FRAUD_SCORES_VISIT_ID 
ON FRAUD_SCORES (VISIT_ID);

CREATE OR REPLACE INDEX IDX_FRAUD_SCORES_SCORE_DATE 
ON FRAUD_SCORES (SCORE_DATE);

-- =============================================================================
-- SAMPLE QUERIES
-- =============================================================================

-- Get latest scores for a specific date
-- SELECT * FROM FRAUD_SCORES WHERE SCORE_DATE = '2024-01-15';

-- Get all scores for a specific visit
-- SELECT * FROM FRAUD_SCORES WHERE VISIT_ID = 'xxx' ORDER BY SCORED_AT DESC;

-- Get average fraud score by day
-- SELECT SCORE_DATE, AVG(PREDICTED_FRAUD_SCORE) as avg_score, COUNT(*) as num_scored
-- FROM FRAUD_SCORES
-- GROUP BY SCORE_DATE
-- ORDER BY SCORE_DATE DESC;

-- Join scores back to original data
-- SELECT 
--     t.*,
--     f.PREDICTED_FRAUD_SCORE,
--     f.MODEL_VERSION
-- FROM ZPUB_PROD.LOOKER_PDT_ZXM.H2_ZPUB_ANALYTICS_ANALYTICS_QUALITY_BY_VISIT_TRAINING t
-- LEFT JOIN FRAUD_SCORES f ON t.VISIT_ID = f.VISIT_ID AND DATE(t.CREATED_AT) = f.SCORE_DATE;
