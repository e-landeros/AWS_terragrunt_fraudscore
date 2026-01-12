#!/usr/bin/env python
# =============================================================================
# SAGEMAKER TRAINING SCRIPT: Fraud Score XGBoost Model
# =============================================================================
# This script runs inside SageMaker and:
# 1. Loads training/validation data from S3
# 2. Applies OrdinalEncoder to categorical features (matching Snowflake ML notebook)
# 3. Trains XGBoost model
# 4. Saves model + encoder for inference
# =============================================================================

import argparse
import os
import json
import pickle
import tarfile
from pathlib import Path

import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.preprocessing import OrdinalEncoder
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score


# =============================================================================
# FEATURE DEFINITIONS (must match Glue extraction scripts)
# =============================================================================

TARGET = 'IPQS_DEVICE_FP_FRAUD_SCORE'

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


def load_data(data_dir: str) -> pd.DataFrame:
    """Load all parquet files from a directory into a single DataFrame."""
    data_path = Path(data_dir)
    
    # Handle both parquet and CSV formats
    parquet_files = list(data_path.glob("*.parquet")) + list(data_path.glob("**/*.parquet"))
    csv_files = list(data_path.glob("*.csv")) + list(data_path.glob("**/*.csv"))
    
    if parquet_files:
        print(f"Loading {len(parquet_files)} parquet files from {data_dir}")
        dfs = [pd.read_parquet(f) for f in parquet_files]
        return pd.concat(dfs, ignore_index=True)
    elif csv_files:
        print(f"Loading {len(csv_files)} CSV files from {data_dir}")
        dfs = [pd.read_csv(f) for f in csv_files]
        return pd.concat(dfs, ignore_index=True)
    else:
        raise ValueError(f"No parquet or CSV files found in {data_dir}")


def prepare_features(df: pd.DataFrame, encoder: OrdinalEncoder = None, fit: bool = False):
    """
    Prepare features for XGBoost training.
    
    - Boolean features: already 0/1 from Glue preprocessing
    - Categorical features: apply OrdinalEncoder
    - Numeric features: already cleaned from Glue preprocessing
    
    Args:
        df: Input DataFrame
        encoder: Fitted OrdinalEncoder (None if fitting)
        fit: Whether to fit the encoder (True for training data)
    
    Returns:
        X: Feature matrix
        y: Target vector (if TARGET in df)
        encoder: Fitted encoder
    """
    # Filter to available columns
    available_cols = df.columns.tolist()
    
    bool_cols = [c for c in BOOLEAN_FEATURES if c in available_cols]
    cat_cols = [c for c in CATEGORICAL_FEATURES if c in available_cols]
    num_cols = [c for c in NUMERIC_FEATURES if c in available_cols]
    
    print(f"Features found: {len(bool_cols)} boolean, {len(cat_cols)} categorical, {len(num_cols)} numeric")
    
    # Handle categorical encoding
    if fit:
        encoder = OrdinalEncoder(
            handle_unknown='use_encoded_value',
            unknown_value=-1
        )
        cat_encoded = encoder.fit_transform(df[cat_cols].astype(str))
    else:
        cat_encoded = encoder.transform(df[cat_cols].astype(str))
    
    # Create encoded column names
    cat_encoded_df = pd.DataFrame(
        cat_encoded,
        columns=[f"{c}_ENCODED" for c in cat_cols],
        index=df.index
    )
    
    # Combine all features
    X = pd.concat([
        df[bool_cols].reset_index(drop=True),
        cat_encoded_df.reset_index(drop=True),
        df[num_cols].reset_index(drop=True)
    ], axis=1)
    
    # Get target if available
    y = None
    if TARGET in df.columns:
        y = df[TARGET].values
    
    return X, y, encoder


def train_model(X_train, y_train, X_val, y_val, hyperparams: dict):
    """Train XGBoost model with given hyperparameters."""
    
    # Create DMatrix for XGBoost
    dtrain = xgb.DMatrix(X_train, label=y_train, feature_names=X_train.columns.tolist())
    dval = xgb.DMatrix(X_val, label=y_val, feature_names=X_val.columns.tolist())
    
    # XGBoost parameters (matching your Snowflake ML notebook)
    params = {
        'objective': hyperparams.get('objective', 'reg:squarederror'),
        'max_depth': int(hyperparams.get('max_depth', 6)),
        'eta': float(hyperparams.get('eta', 0.0769)),
        'subsample': float(hyperparams.get('subsample', 0.958)),
        'colsample_bytree': float(hyperparams.get('colsample_bytree', 0.707)),
        'seed': int(hyperparams.get('seed', 42)),
        'tree_method': hyperparams.get('tree_method', 'hist'),
        'eval_metric': hyperparams.get('eval_metric', 'rmse'),
    }
    
    num_round = int(hyperparams.get('num_round', 1400))
    
    print(f"Training XGBoost with {num_round} rounds...")
    print(f"Parameters: {params}")
    
    # Train with early stopping
    evals = [(dtrain, 'train'), (dval, 'validation')]
    
    model = xgb.train(
        params,
        dtrain,
        num_boost_round=num_round,
        evals=evals,
        early_stopping_rounds=50,
        verbose_eval=100
    )
    
    return model


def evaluate_model(model, X, y, dataset_name: str):
    """Evaluate model and print metrics."""
    dmatrix = xgb.DMatrix(X, feature_names=X.columns.tolist())
    predictions = model.predict(dmatrix)
    
    rmse = np.sqrt(mean_squared_error(y, predictions))
    mae = mean_absolute_error(y, predictions)
    r2 = r2_score(y, predictions)
    
    print(f"\n{'='*60}")
    print(f"{dataset_name} METRICS")
    print(f"{'='*60}")
    print(f"  RMSE: {rmse:.4f}")
    print(f"  MAE:  {mae:.4f}")
    print(f"  R²:   {r2:.4f}")
    print(f"{'='*60}\n")
    
    return {'rmse': rmse, 'mae': mae, 'r2': r2}


def save_model(model, encoder, feature_names, model_dir: str):
    """
    Save model artifacts for SageMaker inference.
    
    Creates a model.tar.gz containing:
    - xgboost-model: The trained XGBoost model
    - encoder.pkl: The fitted OrdinalEncoder
    - feature_names.json: List of feature names in order
    """
    # Save XGBoost model
    model_path = os.path.join(model_dir, 'xgboost-model')
    model.save_model(model_path)
    print(f"Saved XGBoost model to {model_path}")
    
    # Save encoder
    encoder_path = os.path.join(model_dir, 'encoder.pkl')
    with open(encoder_path, 'wb') as f:
        pickle.dump(encoder, f)
    print(f"Saved encoder to {encoder_path}")
    
    # Save feature names
    features_path = os.path.join(model_dir, 'feature_names.json')
    with open(features_path, 'w') as f:
        json.dump(feature_names, f)
    print(f"Saved feature names to {features_path}")


def parse_args():
    """Parse command line arguments (SageMaker passes hyperparameters this way)."""
    parser = argparse.ArgumentParser()
    
    # Hyperparameters
    parser.add_argument('--objective', type=str, default='reg:squarederror')
    parser.add_argument('--num_round', type=int, default=1400)
    parser.add_argument('--max_depth', type=int, default=6)
    parser.add_argument('--eta', type=float, default=0.0769)
    parser.add_argument('--subsample', type=float, default=0.958)
    parser.add_argument('--colsample_bytree', type=float, default=0.707)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--tree_method', type=str, default='hist')
    parser.add_argument('--eval_metric', type=str, default='rmse')
    
    # SageMaker specific environment variables
    parser.add_argument('--model-dir', type=str, default=os.environ.get('SM_MODEL_DIR', '/opt/ml/model'))
    parser.add_argument('--train', type=str, default=os.environ.get('SM_CHANNEL_TRAIN', '/opt/ml/input/data/train'))
    parser.add_argument('--validation', type=str, default=os.environ.get('SM_CHANNEL_VALIDATION', '/opt/ml/input/data/validation'))
    
    return parser.parse_args()


def main():
    print("="*60)
    print("FRAUD SCORE MODEL TRAINING")
    print("="*60)
    
    args = parse_args()
    
    # Convert args to hyperparameters dict
    hyperparams = {
        'objective': args.objective,
        'num_round': args.num_round,
        'max_depth': args.max_depth,
        'eta': args.eta,
        'subsample': args.subsample,
        'colsample_bytree': args.colsample_bytree,
        'seed': args.seed,
        'tree_method': args.tree_method,
        'eval_metric': args.eval_metric,
    }
    
    # Load data
    print("\nLoading training data...")
    train_df = load_data(args.train)
    print(f"Training data shape: {train_df.shape}")
    
    print("\nLoading validation data...")
    val_df = load_data(args.validation)
    print(f"Validation data shape: {val_df.shape}")
    
    # Prepare features
    print("\nPreparing features...")
    X_train, y_train, encoder = prepare_features(train_df, fit=True)
    X_val, y_val, _ = prepare_features(val_df, encoder=encoder, fit=False)
    
    print(f"Training features shape: {X_train.shape}")
    print(f"Validation features shape: {X_val.shape}")
    
    # Train model
    print("\nTraining model...")
    model = train_model(X_train, y_train, X_val, y_val, hyperparams)
    
    # Evaluate
    train_metrics = evaluate_model(model, X_train, y_train, "TRAINING")
    val_metrics = evaluate_model(model, X_val, y_val, "VALIDATION")
    
    # Save model artifacts
    print("\nSaving model artifacts...")
    save_model(model, encoder, X_train.columns.tolist(), args.model_dir)
    
    # Save metrics for SageMaker
    metrics_path = os.path.join(args.model_dir, 'metrics.json')
    with open(metrics_path, 'w') as f:
        json.dump({
            'train': train_metrics,
            'validation': val_metrics
        }, f, indent=2)
    
    print("\n" + "="*60)
    print("TRAINING COMPLETE")
    print("="*60)
    print(f"Model saved to: {args.model_dir}")
    print(f"Validation RMSE: {val_metrics['rmse']:.4f}")
    print(f"Validation R²: {val_metrics['r2']:.4f}")


if __name__ == '__main__':
    main()
