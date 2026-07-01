# Serverless — Email Verification Lambda

AWS Lambda function for sending email verification messages when a new user registers on the CSYE6225 cloud-native web application.

## Overview

When a user creates an account, the web application publishes a message to an SNS topic. This Lambda function is triggered by that SNS notification and:

1. Checks DynamoDB to prevent duplicate emails
2. Sends a verification email via AWS SES containing a unique token link
3. Records the sent email in DynamoDB

## Architecture

```
POST /v1/user (webapp)
        ↓
    SNS Topic
        ↓
  Lambda Function
    ↓         ↓
 DynamoDB    SES
(dedup)   (send email)
        ↓
User receives:
http://demo.techwithhk.me/v1/user/verify-email?email=...&token=<UUID>
```

## Prerequisites

- Python 3.12+
- AWS CLI configured with appropriate credentials
- AWS account with the following services enabled:
  - AWS Lambda
  - AWS SNS
  - AWS SES (domain or email verified)
  - AWS DynamoDB
- Terraform (for infrastructure provisioning — see `tf-infra` repo)

## Repository Structure

```
serverless/
├── lambda_function.py   # Lambda handler
├── requirements.txt     # Python dependencies
├── README.md
└── .gitignore
```

## Local Development Setup

```bash
# Clone the repo
git clone git@github.com:hrishiNEU/serverless.git
cd serverless

# Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Environment Variables

The Lambda function reads these environment variables (set via Terraform):

| Variable | Description | Example |
|---|---|---|
| `DYNAMODB_TABLE` | DynamoDB table name for email tracking | `csye6225-vpc-email-tracking` |
| `SES_FROM_EMAIL` | Verified SES sender address | `no-reply@techwithhk.me` |
| `AWS_REGION_NAME` | AWS region | `us-east-1` |

## Building & Deploying

### Package the Lambda zip

```bash
# boto3 is included in the Lambda runtime — no need to bundle dependencies
zip lambda_function.zip lambda_function.py

# Copy to tf-infra for Terraform to use
cp lambda_function.zip ../tf-infra/aws/
```

### Deploy via Terraform

Infrastructure is managed in the `tf-infra` repository. The Lambda function is deployed as part of `terraform apply`:

```bash
cd ../tf-infra/aws
export AWS_PROFILE=dev
terraform apply -target=aws_lambda_function.email_verification
```

### Update Lambda code only (without full terraform apply)

```bash
zip lambda_function.zip lambda_function.py
aws lambda update-function-code \
  --function-name csye6225-vpc-email-verification \
  --zip-file fileb://lambda_function.zip \
  --profile dev
```

## Testing

### Invoke Lambda manually via AWS CLI

```bash
aws lambda invoke \
  --function-name csye6225-vpc-email-verification \
  --payload '{"Records":[{"Sns":{"Message":"{\"email\":\"test@example.com\",\"first_name\":\"Test\",\"token\":\"some-uuid\",\"domain\":\"demo.techwithhk.me\"}"}}]}' \
  --cli-binary-format raw-in-base64-out \
  response.json \
  --profile dev

cat response.json
```

### Check Lambda logs in CloudWatch

```bash
aws logs tail /aws/lambda/csye6225-vpc-email-verification \
  --follow \
  --profile dev
```

### Verify DynamoDB tracking record was created

```bash
aws dynamodb scan \
  --table-name csye6225-vpc-email-tracking \
  --profile dev
```

## How Duplicate Prevention Works

Before sending any email, the Lambda checks DynamoDB for an existing record with the same `email` as the hash key. If a record exists, the email is skipped. This prevents duplicate emails even if SNS delivers the same message more than once (at-least-once delivery guarantee).
