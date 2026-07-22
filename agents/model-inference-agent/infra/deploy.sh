#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# Healthcare ML Inference Agent V2 — Deployment Script
#
# Provisions all AWS resources for the AgentCore-powered agent.
# Run from the project root:
#   chmod +x infra/deploy.sh && ./infra/deploy.sh
#
# Prerequisites:
#   - AWS CLI configured with appropriate credentials
#   - AgentCore CLI installed (pip install bedrock-agentcore)
#   - Docker installed (for Lambda packaging)
# ──────────────────────────────────────────────────────────────

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────

REGION="${AWS_REGION:-us-west-2}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
PROJECT="healthcare-agent-v2"
BUCKET="${PROJECT}-${ACCOUNT_ID}"
STACK_NAME="${PROJECT}-stack"

echo "═══════════════════════════════════════════════════════"
echo "  Healthcare ML Inference Agent V2 — Deployment"
echo "  Account: ${ACCOUNT_ID}"
echo "  Region:  ${REGION}"
echo "  Bucket:  ${BUCKET}"
echo "═══════════════════════════════════════════════════════"

# ── Step 1: Create S3 Bucket ─────────────────────────────────

echo ""
echo "[1/7] Creating S3 bucket..."
if aws s3api head-bucket --bucket "${BUCKET}" 2>/dev/null; then
    echo "  Bucket ${BUCKET} already exists"
else
    aws s3api create-bucket \
        --bucket "${BUCKET}" \
        --region "${REGION}" \
        --create-bucket-configuration LocationConstraint="${REGION}"
    aws s3api put-bucket-versioning \
        --bucket "${BUCKET}" \
        --versioning-configuration Status=Enabled
    echo "  Created bucket ${BUCKET} with versioning"
fi

# ── Step 2: Upload Data to S3 ────────────────────────────────

echo ""
echo "[2/7] Uploading patient data to S3..."
aws s3 sync data/raw/preprocessing/ "s3://${BUCKET}/data/" \
    --exclude ".*"
echo "  Uploaded 3 CSV files to s3://${BUCKET}/data/"

# ── Step 3: Upload Model Artifacts to S3 ─────────────────────

echo ""
echo "[3/7] Uploading model artifacts to S3..."
if [ -d "models/exported" ]; then
    aws s3 sync models/exported/ "s3://${BUCKET}/models/" \
        --exclude ".*" --exclude "__pycache__/*"
    echo "  Uploaded model artifacts to s3://${BUCKET}/models/"
else
    echo "  WARNING: models/exported/ not found. Upload manually."
fi

# ── Step 4: Create IAM Roles ─────────────────────────────────

echo ""
echo "[4/7] Creating IAM roles..."

# Lambda execution role (shared by all 5 tool Lambdas)
LAMBDA_ROLE_NAME="${PROJECT}-lambda-role"
LAMBDA_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${LAMBDA_ROLE_NAME}"

cat > /tmp/lambda-trust.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "lambda.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
EOF

aws iam create-role \
    --role-name "${LAMBDA_ROLE_NAME}" \
    --assume-role-policy-document file:///tmp/lambda-trust.json \
    --description "Lambda role for Healthcare Agent V2 tools" \
    2>/dev/null || echo "  Role ${LAMBDA_ROLE_NAME} already exists"

# Attach policies
aws iam attach-role-policy \
    --role-name "${LAMBDA_ROLE_NAME}" \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole \
    2>/dev/null || true

# Inline policy for S3 + SageMaker access
cat > /tmp/lambda-inline.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::${BUCKET}",
        "arn:aws:s3:::${BUCKET}/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": ["sagemaker:InvokeEndpoint"],
      "Resource": "arn:aws:sagemaker:${REGION}:${ACCOUNT_ID}:endpoint/healthcare-*"
    },
    {
      "Effect": "Allow",
      "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": "*"
    }
  ]
}
EOF

aws iam put-role-policy \
    --role-name "${LAMBDA_ROLE_NAME}" \
    --policy-name "${PROJECT}-inline" \
    --policy-document file:///tmp/lambda-inline.json

echo "  IAM roles configured"

# ── Step 5: Deploy Lambda Functions ──────────────────────────

echo ""
echo "[5/7] Deploying Lambda functions..."

TOOLS=("parse_query" "load_patient_data" "select_model" "run_inference" "format_response")

# Package the source code
echo "  Packaging source code..."
rm -rf /tmp/${PROJECT}-lambda-pkg
mkdir -p /tmp/${PROJECT}-lambda-pkg
cp -r src/ /tmp/${PROJECT}-lambda-pkg/src/
pip install -q -t /tmp/${PROJECT}-lambda-pkg/ pandas numpy boto3 2>/dev/null

for TOOL in "${TOOLS[@]}"; do
    FUNC_NAME="${PROJECT}-${TOOL}"
    HANDLER="src.tools.${TOOL}.lambda_handler"

    echo "  Deploying ${FUNC_NAME}..."

    # Create zip
    pushd /tmp/${PROJECT}-lambda-pkg > /dev/null
    zip -qr /tmp/${FUNC_NAME}.zip . -x "*.pyc" "__pycache__/*"
    popd > /dev/null

    # Create or update Lambda
    aws lambda create-function \
        --function-name "${FUNC_NAME}" \
        --runtime python3.12 \
        --handler "${HANDLER}" \
        --role "${LAMBDA_ROLE_ARN}" \
        --zip-file "fileb:///tmp/${FUNC_NAME}.zip" \
        --timeout 300 \
        --memory-size 1024 \
        --environment "Variables={MOSAIC_S3_BUCKET=${BUCKET},AWS_DEFAULT_REGION=${REGION},SAGEMAKER_AUTOGLUON_ENDPOINT=healthcare-autogluon,SAGEMAKER_TABPFN_ENDPOINT=healthcare-tabpfn}" \
        --region "${REGION}" \
        2>/dev/null || \
    aws lambda update-function-code \
        --function-name "${FUNC_NAME}" \
        --zip-file "fileb:///tmp/${FUNC_NAME}.zip" \
        --region "${REGION}" \
        2>/dev/null

    echo "    ✓ ${FUNC_NAME}"
done

echo "  All 5 Lambda functions deployed"

# ── Step 6: AgentCore Gateway Setup ──────────────────────────

echo ""
echo "[6/7] Setting up AgentCore Gateway..."
echo "  NOTE: AgentCore Gateway setup requires the AgentCore CLI."
echo "  Run the following commands manually:"
echo ""
echo "  # Create Gateway"
echo "  agentcore gateway create-mcp-gateway \\"
echo "      --name HealthcareAgentGateway \\"
echo "      --region ${REGION}"
echo ""
echo "  # Register each tool target"
for TOOL in "${TOOLS[@]}"; do
    FUNC_ARN="arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:${PROJECT}-${TOOL}"
    echo "  agentcore gateway create-mcp-gateway-target \\"
    echo "      --gateway-arn \$GATEWAY_ARN \\"
    echo "      --name ${TOOL} \\"
    echo "      --target-type lambda \\"
    echo "      --target-payload '{\"lambda_arn\": \"${FUNC_ARN}\"}'"
    echo ""
done

# ── Step 7: Deploy Agent to AgentCore Runtime ────────────────

echo ""
echo "[7/7] Deploying agent to AgentCore Runtime..."
echo "  Run from the project root:"
echo ""
echo "  export AGENTCORE_MEMORY_ID=<your-memory-id>"
echo "  export AGENTCORE_GATEWAY_URL=<your-gateway-url>"
echo "  export AGENTCORE_TOKEN_ENDPOINT=<your-token-endpoint>"
echo "  export AGENTCORE_CLIENT_ID=<your-client-id>"
echo "  export AGENTCORE_CLIENT_SECRET=<your-client-secret>"
echo ""
echo "  agentcore launch"
echo ""

# ── Summary ──────────────────────────────────────────────────

echo "═══════════════════════════════════════════════════════"
echo "  Deployment Summary"
echo "═══════════════════════════════════════════════════════"
echo "  S3 Bucket:    s3://${BUCKET}/"
echo "  Lambda Funcs: ${TOOLS[*]}"
echo "  Region:       ${REGION}"
echo ""
echo "  Remaining manual steps:"
echo "    1. Create SageMaker endpoints (healthcare-autogluon, healthcare-tabpfn)"
echo "    2. Set up AgentCore Gateway (commands printed above)"
echo "    3. Deploy agent with 'agentcore launch'"
echo "    4. Run UI: streamlit run app_v2.py"
echo "═══════════════════════════════════════════════════════"
