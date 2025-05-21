#!/bin/bash
set -e

# Get AWS account and region
echo "Deploying to AWS Account: $(aws sts get-caller-identity --query Account --output text) in Region: ${AWS_REGION:-us-west-2}"

# Set AWS_REGION if not already set
export AWS_REGION=${AWS_REGION:-us-west-2}

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "AWS CLI is not installed. Please install it first."
    exit 1
fi

# Check if AWS credentials are configured
if ! aws sts get-caller-identity &> /dev/null; then
    echo "AWS credentials are not configured. Please configure them first."
    exit 1
fi

# Check if virtual environment exists, create if not
if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
else
    source .venv/bin/activate
fi

# Ask if user wants to cleanup existing resources first
read -p "Do you want to clean up existing resources first? (y/n): " cleanup

if [[ "$cleanup" == "y" ]]; then
    echo "Cleaning up existing stacks..."
    # Delete stacks in reverse dependency order
    aws cloudformation delete-stack --stack-name EcsStack || true
    echo "Waiting for EcsStack deletion..."
    aws cloudformation wait stack-delete-complete --stack-name EcsStack || true
    
    aws cloudformation delete-stack --stack-name RdsStack || true
    echo "Waiting for RdsStack deletion..."
    aws cloudformation wait stack-delete-complete --stack-name RdsStack || true
    
    aws cloudformation delete-stack --stack-name VpcStack || true
    echo "Waiting for VpcStack deletion..."
    aws cloudformation wait stack-delete-complete --stack-name VpcStack || true
    
    # Delete orphaned log groups
    echo "Cleaning up orphaned log groups..."
    aws logs describe-log-groups --log-group-name-prefix "/ecs/ai-starter-kit" --query "logGroups[*].logGroupName" --output text | xargs -n1 aws logs delete-log-group --log-group-name || true
fi

# Bootstrap CDK
echo "Bootstrapping CDK..."
cdk bootstrap

# Deploy the stack
echo "Deploying all stacks..."
cdk deploy --all --require-approval never

# Show stack outputs
echo "Deployment completed. Stack outputs:"
aws cloudformation describe-stacks --stack-name VpcStack --query "Stacks[0].Outputs" --output table 2>/dev/null || echo "VpcStack outputs not available"
aws cloudformation describe-stacks --stack-name RdsStack --query "Stacks[0].Outputs" --output table 2>/dev/null || echo "RdsStack outputs not available"
aws cloudformation describe-stacks --stack-name EcsStack --query "Stacks[0].Outputs" --output table 2>/dev/null || echo "EcsStack outputs not available"

echo "Deployment complete!" 