"""Run scripts/train_forecasts.py as a SageMaker training job, then pull the models back.

    python scripts/sagemaker_train.py --days 60
    python scripts/sagemaker_train.py --dry-run          # package and print the request only

Needs the deployed stack (outputs BucketName and SageMakerRoleArn), AWS credentials with
sagemaker:CreateTrainingJob, iam:PassRole and S3 access to the bucket, and a service quota
for the instance type (new accounts start at 0: request "ml.m5.xlarge for training job usage").
Writes forecasting/models/*.json and metrics.json, the same files the local script writes.
The serving path is unchanged: the predict Lambda reads these JSON files, so no endpoint.
"""

import argparse
import io
import json
import sys
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "forecasting" / "models"
# AWS-owned scikit-learn framework image (Python 3.12, scikit-learn 1.4); same account id for every region listed.
IMAGE_ACCOUNTS = {"ap-south-1": "720646828776"}
IMAGE_TAG = "sagemaker-scikit-learn:1.4-2-py312-cpu-py3"
INCLUDE = ["model", "forecasting", "sources"]


def source_tarball() -> bytes:
    """Entry point, requirements and the code train_forecasts.py imports (no models, no tests)."""
    def keep(info: tarfile.TarInfo):
        parts = Path(info.name).parts
        if "__pycache__" in parts or info.name.endswith(".pyc") or "models" in parts[1:2] and parts[0] == "forecasting":
            return None
        return info

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        tar.add(ROOT / "sagemaker" / "train_entry.py", arcname="train_entry.py")
        tar.add(ROOT / "sagemaker" / "requirements.txt", arcname="requirements.txt")
        tar.add(ROOT / "scripts" / "train_forecasts.py", arcname="scripts/train_forecasts.py")
        tar.add(ROOT / "data" / "regions.yaml", arcname="data/regions.yaml")
        for d in INCLUDE:
            tar.add(ROOT / d, arcname=d, filter=keep)
    return buf.getvalue()


def request(job: str, bucket: str, role: str, region: str, instance: str, days: int, regions: str | None) -> dict:
    prefix = f"s3://{bucket}/training/{job}"
    hp = {"days": days, **({"regions": regions} if regions else {})}
    hp = {k: json.dumps(v) for k, v in hp.items()}
    hp.update({"sagemaker_program": json.dumps("train_entry.py"),
               "sagemaker_submit_directory": json.dumps(f"{prefix}/source/sourcedir.tar.gz"),
               "sagemaker_region": json.dumps(region)})
    account = IMAGE_ACCOUNTS.get(region, IMAGE_ACCOUNTS["ap-south-1"])
    return {
        "TrainingJobName": job,
        "RoleArn": role,
        "AlgorithmSpecification": {"TrainingImage": f"{account}.dkr.ecr.{region}.amazonaws.com/{IMAGE_TAG}",
                                   "TrainingInputMode": "File"},
        "HyperParameters": hp,
        "InputDataConfig": [{"ChannelName": "history", "DataSource": {"S3DataSource": {
            "S3DataType": "S3Prefix", "S3Uri": f"{prefix}/history/", "S3DataDistributionType": "FullyReplicated"}}}],
        "OutputDataConfig": {"S3OutputPath": f"{prefix}/output"},
        "ResourceConfig": {"InstanceType": instance, "InstanceCount": 1, "VolumeSizeInGB": 5},
        "StoppingCondition": {"MaxRuntimeInSeconds": 1800},
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=60)
    p.add_argument("--regions", help="comma-separated (default: all)")
    p.add_argument("--instance", default="ml.m5.xlarge")
    p.add_argument("--stack", default="pravaah")
    p.add_argument("--aws-region", default="ap-south-1")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    import boto3

    cf = boto3.client("cloudformation", region_name=args.aws_region)
    outputs = {o["OutputKey"]: o["OutputValue"]
               for o in cf.describe_stacks(StackName=args.stack)["Stacks"][0]["Outputs"]}
    bucket, role = outputs["BucketName"], outputs["SageMakerRoleArn"]
    job = "pravaah-forecast-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    req = request(job, bucket, role, args.aws_region, args.instance, args.days, args.regions)
    tarball = source_tarball()
    print(f"source package: {len(tarball) / 1024:.0f} KiB")
    if args.dry_run:
        print(json.dumps(req, indent=1))
        return 0

    s3 = boto3.client("s3", region_name=args.aws_region)
    s3.put_object(Bucket=bucket, Key=f"training/{job}/source/sourcedir.tar.gz", Body=tarball)
    s3.put_object(Bucket=bucket, Key=f"training/{job}/history/README.txt", Body=b"carbon history CSVs, if any\n")
    for f in sorted((ROOT / "data" / "history").glob("*.csv")):
        s3.upload_file(str(f), bucket, f"training/{job}/history/{f.name}")

    sm = boto3.client("sagemaker", region_name=args.aws_region)
    sm.create_training_job(**req)
    print("started", job, "on", args.instance)
    while True:
        d = sm.describe_training_job(TrainingJobName=job)
        status = d["TrainingJobStatus"]
        print(f"  {status} / {d.get('SecondaryStatus')}")
        if status in ("Completed", "Failed", "Stopped"):
            break
        time.sleep(30)
    if status != "Completed":
        print("job did not complete:", d.get("FailureReason", status), file=sys.stderr)
        return 1

    key = d["ModelArtifacts"]["S3ModelArtifacts"].split(f"s3://{bucket}/", 1)[1]
    with tarfile.open(fileobj=io.BytesIO(s3.get_object(Bucket=bucket, Key=key)["Body"].read()), mode="r:gz") as tar:
        members = [m for m in tar.getmembers() if m.isfile() and m.name.endswith(".json")]
        MODELS.mkdir(parents=True, exist_ok=True)
        fresh = {Path(m.name).name for m in members}
        for old in MODELS.glob("*-*.json"):
            if old.name not in fresh:
                old.unlink()           # a model that no longer beats its baselines must not stay
        for m in members:
            (MODELS / Path(m.name).name).write_bytes(tar.extractfile(m).read())
    print(f"wrote {len(members)} files to {MODELS}; billable {d.get('BillableTimeInSeconds')} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
