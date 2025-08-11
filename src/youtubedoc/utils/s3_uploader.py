"""S3 uploader utility for publishing generated documentation.

This mirrors the behavior from Gittodoc's cloud_uploader with minor adjustments
for our app's environment variables and markdown content type.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import boto3
from botocore.exceptions import ClientError


logger = logging.getLogger(__name__)


def check_cached_documentation(object_key: str) -> Optional[str]:
    """Check if documentation already exists in S3 and return the URL if found.

    Parameters
    ----------
    object_key : str
        Key to check for in the S3 bucket.

    Returns
    -------
    Optional[str]
        Public URL of the cached object, or None if not found.
    """
    bucket_name = os.getenv("AWS_S3_BUCKET")
    if not bucket_name:
        return None

    region = (os.getenv("AWS_REGION") or "us-east-1").strip()

    try:
        s3_client = boto3.client("s3", region_name=region if region else None)
        
        # Check if object exists
        try:
            s3_client.head_object(Bucket=bucket_name, Key=object_key)
        except ClientError as exc:
            error_code = (exc.response.get("Error", {}) or {}).get("Code")
            if error_code == "404":
                return None  # Object doesn't exist
            raise  # Other error, re-raise

        # Object exists, construct URL
        try:
            loc = s3_client.get_bucket_location(Bucket=bucket_name).get("LocationConstraint")
            bucket_region = loc or "us-east-1"
        except Exception:
            bucket_region = region or "us-east-1"

        if bucket_region == "us-east-1":
            return f"https://{bucket_name}.s3.amazonaws.com/{object_key}"
        return f"https://{bucket_name}.s3.{bucket_region}.amazonaws.com/{object_key}"

    except Exception as exc:
        logger.error("Error checking cached documentation: %s", exc)
        return None


def upload_markdown_to_s3(content_md: str, object_key: str) -> Optional[str]:
    """Upload markdown to S3 and return the public URL if successful.

    Reads AWS credentials and target bucket/region from environment variables:
    - AWS_S3_BUCKET
    - AWS_REGION (default: us-east-1)
    - AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY (standard boto3 picks from env if set)

    Parameters
    ----------
    content_md: str
        Markdown content to upload.
    object_key: str
        Key to store the object under in the bucket.

    Returns
    -------
    Optional[str]
        Public URL of the uploaded object, or None on failure.
    """
    bucket_name = os.getenv("AWS_S3_BUCKET")
    if not bucket_name:
        logger.warning("AWS_S3_BUCKET env var is not set; skipping upload.")
        return None

    region = (os.getenv("AWS_REGION") or "us-east-1").strip()

    try:
        # Use a general S3 client for upload; URL construction will use the bucket's real region
        s3_client = boto3.client("s3", region_name=region if region else None)
        # First try with ACL for buckets that support it; if not supported, retry without ACL.
        try:
            s3_client.put_object(
                Bucket=bucket_name,
                Key=object_key,
                Body=content_md.encode("utf-8"),
                ContentType="text/markdown; charset=utf-8",
                ACL="public-read",
            )
        except ClientError as exc:
            error_code = (exc.response.get("Error", {}) or {}).get("Code")
            if error_code in {"AccessControlListNotSupported", "InvalidRequest"}:
                # Retry without ACL for buckets with Object Ownership: Bucket owner enforced
                s3_client.put_object(
                    Bucket=bucket_name,
                    Key=object_key,
                    Body=content_md.encode("utf-8"),
                    ContentType="text/markdown; charset=utf-8",
                )
            else:
                raise

        # Discover the actual bucket region to build a correct URL and avoid PermanentRedirect
        try:
            loc = s3_client.get_bucket_location(Bucket=bucket_name).get("LocationConstraint")
            bucket_region = loc or "us-east-1"
        except Exception:
            bucket_region = region or "us-east-1"

        if bucket_region == "us-east-1":
            return f"https://{bucket_name}.s3.amazonaws.com/{object_key}"
        return f"https://{bucket_name}.s3.{bucket_region}.amazonaws.com/{object_key}"

    except ClientError as exc:
        logger.error("Failed to upload %s to %s: %s", object_key, bucket_name, exc)
        return None
    except Exception as exc:  # pragma: no cover - safety net
        logger.error("Unexpected S3 uploader error: %s", exc)
        return None


