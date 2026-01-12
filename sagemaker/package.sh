#!/bin/bash
# =============================================================================
# Package SageMaker Scripts for Script Mode
# =============================================================================
# This script creates a sourcedir.tar.gz containing the training and inference
# scripts for SageMaker Script Mode.
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_FILE="${SCRIPT_DIR}/sourcedir.tar.gz"

echo "Packaging SageMaker scripts..."

# Create tar.gz from the sagemaker directory
cd "${SCRIPT_DIR}"
tar -czvf sourcedir.tar.gz \
    training_script.py \
    inference.py

echo "Created: ${OUTPUT_FILE}"
echo ""
echo "Next steps:"
echo "  1. Get your S3 bucket name from Terraform output"
echo "  2. Upload to S3:"
echo "     aws s3 cp sourcedir.tar.gz s3://YOUR-BUCKET/scripts/sagemaker/"
