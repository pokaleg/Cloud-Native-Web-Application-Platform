import boto3
from app.core.config import settings


def get_s3_client():
    """
    Returns a boto3 S3 client.
    On EC2 with an IAM role attached, boto3 automatically picks up credentials
    from the instance metadata — no access keys needed or allowed.
    """
    return boto3.client("s3", region_name=settings.AWS_REGION)


def upload_file_to_s3(file_bytes: bytes, s3_key: str, content_type: str) -> str:
    """
    Upload bytes to S3.
    If S3_BUCKET_NAME is empty (local dev / CI), skip real S3 call.
    """
    if not settings.S3_BUCKET_NAME:
        return f"s3://local-dev-bucket/{s3_key}"

    client = get_s3_client()
    client.put_object(
        Bucket=settings.S3_BUCKET_NAME,
        Key=s3_key,
        Body=file_bytes,
        ContentType=content_type,
    )
    return f"s3://{settings.S3_BUCKET_NAME}/{s3_key}"


def delete_file_from_s3(s3_key: str) -> None:
    """
    Delete an object from S3 by its key.
    If S3_BUCKET_NAME is empty (local dev / CI), skip silently.
    """
    if not settings.S3_BUCKET_NAME:
        return

    client = get_s3_client()
    client.delete_object(
        Bucket=settings.S3_BUCKET_NAME,
        Key=s3_key,
    )
