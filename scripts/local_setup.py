"""Create the DynamoDB table and S3 bucket in LocalStack and upload the config.

    make local-setup      (sets AWS_ENDPOINT_URL to LocalStack)

Safe to run twice.
"""

import os
import sys
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend.db import TABLE_KEYS, table_name  # noqa: E402


def create_table(dynamodb) -> None:
    name = table_name()
    if name in dynamodb.list_tables()["TableNames"]:
        print(f"table {name} exists")
        return
    kwargs = {
        "TableName": name,
        "BillingMode": "PAY_PER_REQUEST",
        **TABLE_KEYS,
    }
    dynamodb.create_table(**kwargs)
    dynamodb.get_waiter("table_exists").wait(TableName=name)
    dynamodb.update_time_to_live(
        TableName=name, TimeToLiveSpecification={"AttributeName": "expires_at", "Enabled": True}
    )
    print(f"created table {name}")


def create_bucket(s3) -> str:
    name = os.environ.get("BUCKET_NAME", "pravaah-data-local")
    region = s3.meta.region_name
    existing = [b["Name"] for b in s3.list_buckets().get("Buckets", [])]
    if name not in existing:
        kwargs = {"Bucket": name}
        if region != "us-east-1":
            kwargs["CreateBucketConfiguration"] = {"LocationConstraint": region}
        s3.create_bucket(**kwargs)
        print(f"created bucket {name}")
    for path in [ROOT / "data" / "regions.yaml", ROOT / "model" / "coefficients.yaml"]:
        key = f"config/{path.name}"
        s3.upload_file(str(path), name, key, ExtraArgs={"ContentType": "application/yaml"})
        print(f"uploaded s3://{name}/{key}")
    return name


def main() -> None:
    if not os.environ.get("AWS_ENDPOINT_URL"):
        sys.exit("AWS_ENDPOINT_URL is not set; refusing to touch a real AWS account. Use `make local-setup`.")
    create_table(boto3.client("dynamodb"))
    create_bucket(boto3.client("s3"))


if __name__ == "__main__":
    main()
