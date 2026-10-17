import os
import boto3
from dotenv import load_dotenv
import io
from botocore.exceptions import ClientError

load_dotenv()

AWS_REGION = os.environ["AWS_REGION"]
S3_BUCKET = os.environ["AWS_S3_BUCKET"]

s3_client = boto3.client(
    "s3",
    region_name=AWS_REGION,
)


def upload_to_s3(file_obj, key: str, content_type: str):
    s3_client.upload_fileobj(
        file_obj,
        S3_BUCKET,
        key,
        ExtraArgs={"ContentType": content_type},
    )
    return key


def generate_download_url(key: str) -> str:
    return s3_client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": S3_BUCKET,
            "Key": key,
            "ResponseContentDisposition": "attachment",
        },
        ExpiresIn=3600,
    )


def download_s3_file(key: str):
    try:
        stream = io.BytesIO()

        s3_client.download_fileobj(Bucket=S3_BUCKET, Key=key, Fileobj=stream)

        stream.seek(0)
        return stream

    except ClientError as e:
        print(f"S3 download failed: {e}")
        return None
