"""
Lambda function — It is triggered by SNS when a new user registers.
Sends a verification email via SES and tracks sends in DynamoDB
to prevent duplicate emails.
"""

import json
import logging
import os
import boto3
from botocore.exceptions import ClientError
from datetime import datetime, timezone

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Clients (reused across warm invocations)
ses = boto3.client("ses", region_name=os.environ.get("AWS_REGION", "us-east-1"))
dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"))

DYNAMODB_TABLE = os.environ["DYNAMODB_TABLE"]       # e.g. csye6225-email-tracking
SES_FROM_EMAIL = os.environ["SES_FROM_EMAIL"]       # e.g. no-reply@techwithhk.me


def lambda_handler(event, context):
    for record in event.get("Records", []):
        try:
            _process_record(record)
        except Exception as e:
            logger.error(f"Failed to process record: {e}", exc_info=True)
    return {"statusCode": 200}


def _process_record(record):
    # Parse SNS message
    sns_message = record["Sns"]["Message"]
    logger.info(f"Received SNS message: {sns_message}")

    try:
        payload = json.loads(sns_message)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in SNS message: {e}")
        return

    email = payload.get("email")
    first_name = payload.get("first_name", "User")
    token = payload.get("token")
    domain = payload.get("domain", "demo.techwithhk.me")

    if not email or not token:
        logger.error(f"Missing email or token in payload: {payload}")
        return

    # Duplicate check — has this email already been sent a verification?
    table = dynamodb.Table(DYNAMODB_TABLE)
    if _already_sent(table, email):
        logger.info(f"Duplicate detected — skipping email for {email}")
        return

    # Send email via SES
    verification_link = (
        f"https://{domain}/v1/user/verify-email"
        f"?email={email}&token={token}"
    )
    if not _send_email(email, first_name, verification_link):
        return  # error already logged inside _send_email

    # Record in DynamoDB to prevent future duplicates
    _record_sent(table, email, token)
    logger.info(f"Verification email sent and recorded for {email}")


def _already_sent(table, email: str) -> bool:
    """Returns True if a verification email was already sent for this email."""
    try:
        resp = table.get_item(Key={"email": email})
        return "Item" in resp
    except ClientError as e:
        logger.error(f"DynamoDB get_item failed for {email}: {e}")
        # Fail open — don't block email sending on DynamoDB errors
        return False


def _record_sent(table, email: str, token: str) -> None:
    """Write a record to DynamoDB so we don't send duplicates."""
    try:
        table.put_item(Item={
            "email": email,
            "token": token,
            "sent_at": datetime.now(timezone.utc).isoformat(),
        })
    except ClientError as e:
        logger.error(f"DynamoDB put_item failed for {email}: {e}")


def _send_email(to_email: str, first_name: str, link: str) -> bool:
    """Send the verification email via SES. Returns True on success."""
    subject = "Verify your email address"
    body_text = (
        f"Hi {first_name},\n\n"
        f"Change for A09 demo\n\n"
        f"Please verify your email address by clicking the link below.\n"
        f"This link expires in 1 minute.\n\n"
        f"{link}\n\n"
        f"If you did not create an account, please ignore this email.\n"
    )
    body_html = f"""
    <html><body>
    <p>Hi {first_name},</p>
    <p>Change for A09 demo</p>
    <p>Please verify your email address by clicking the link below.<br>
    <strong>This link expires in 1 minute.</strong></p>
    <p><a href="{link}">Verify Email Address</a></p>
    <p>Or copy this link: {link}</p>
    <p>If you did not create an account, please ignore this email.</p>
    </body></html>
    """
    try:
        ses.send_email(
            Source=SES_FROM_EMAIL,
            Destination={"ToAddresses": [to_email]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Text": {"Data": body_text, "Charset": "UTF-8"},
                    "Html": {"Data": body_html, "Charset": "UTF-8"},
                },
            },
        )
        logger.info(f"SES email sent to {to_email}")
        return True
    except ClientError as e:
        logger.error(f"SES send_email failed for {to_email}: {e}")
        return False
