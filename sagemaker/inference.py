#!/usr/bin/env python
# =============================================================================
# SAGEMAKER INFERENCE SCRIPT: Fraud Score Prediction
# =============================================================================
# This script handles inference for Batch Transform:
# 1. Loads the trained model and encoder
# 2. Applies OrdinalEncoder to incoming data
# 3. Returns predictions
# =============================================================================

import os
import json
import pickle
import io

import pandas as pd
import numpy as np
import xgboost as xgb


# Global variables for loaded model artifacts
model = None
encoder = None
feature_names = None

# Feature definitions (must match training)
BOOLEAN_FEATURES = [
    'IP_API_HOSTING',
    'IP_API_MOBILE',
    'IP_API_PROXY',
]

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

# All raw feature columns in order (for parsing CSV input)
ALL_RAW_FEATURES = BOOLEAN_FEATURES + CATEGORICAL_FEATURES + NUMERIC_FEATURES


def model_fn(model_dir):
    """
    Load model artifacts from the model directory.
    Called once when the container starts.
    """
    global model, encoder, feature_names
    
    print(f"Loading model from {model_dir}")
    
    # Load XGBoost model
    model_path = os.path.join(model_dir, 'xgboost-model')
    model = xgb.Booster()
    model.load_model(model_path)
    print(f"Loaded XGBoost model from {model_path}")
    
    # Load encoder
    encoder_path = os.path.join(model_dir, 'encoder.pkl')
    with open(encoder_path, 'rb') as f:
        encoder = pickle.load(f)
    print(f"Loaded encoder from {encoder_path}")
    
    # Load feature names
    features_path = os.path.join(model_dir, 'feature_names.json')
    with open(features_path, 'r') as f:
        feature_names = json.load(f)
    print(f"Loaded {len(feature_names)} feature names")
    
    return model


def input_fn(request_body, request_content_type):
    """
    Parse input data from the request.
    Supports CSV format (what Batch Transform sends).
    """
    print(f"Received request with content type: {request_content_type}")
    
    if request_content_type == 'text/csv':
        # Parse CSV - no header, columns in order of ALL_RAW_FEATURES
        df = pd.read_csv(
            io.StringIO(request_body),
            header=None,
            names=ALL_RAW_FEATURES
        )
        return df
    
    elif request_content_type == 'application/json':
        # Parse JSON
        data = json.loads(request_body)
        if isinstance(data, list):
            df = pd.DataFrame(data)
        else:
            df = pd.DataFrame([data])
        return df
    
    else:
        raise ValueError(f"Unsupported content type: {request_content_type}")


def predict_fn(input_data, model):
    """
    Apply encoding and make predictions.
    """
    global encoder, feature_names
    
    print(f"Making predictions for {len(input_data)} rows")
    
    # Get available columns
    available_cols = input_data.columns.tolist()
    
    bool_cols = [c for c in BOOLEAN_FEATURES if c in available_cols]
    cat_cols = [c for c in CATEGORICAL_FEATURES if c in available_cols]
    num_cols = [c for c in NUMERIC_FEATURES if c in available_cols]
    
    # Apply encoder to categorical columns
    cat_encoded = encoder.transform(input_data[cat_cols].astype(str))
    cat_encoded_df = pd.DataFrame(
        cat_encoded,
        columns=[f"{c}_ENCODED" for c in cat_cols],
        index=input_data.index
    )
    
    # Combine all features
    X = pd.concat([
        input_data[bool_cols].reset_index(drop=True),
        cat_encoded_df.reset_index(drop=True),
        input_data[num_cols].reset_index(drop=True)
    ], axis=1)
    
    # Reorder to match training feature order
    X = X[feature_names]
    
    # Create DMatrix and predict
    dmatrix = xgb.DMatrix(X, feature_names=feature_names)
    predictions = model.predict(dmatrix)
    
    return predictions


def output_fn(prediction, accept):
    """
    Format predictions for output.
    Returns one prediction per line for Batch Transform.
    """
    print(f"Formatting {len(prediction)} predictions for output")
    
    if accept == 'text/csv' or accept == '*/*':
        # One prediction per line (Batch Transform default)
        return '\n'.join(str(p) for p in prediction)
    
    elif accept == 'application/json':
        return json.dumps(prediction.tolist())
    
    else:
        raise ValueError(f"Unsupported accept type: {accept}")
