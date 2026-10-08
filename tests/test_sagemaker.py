import io
import json
import sys
import tarfile

from tests.api.conftest import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
import sagemaker_train as st  # noqa: E402


def test_source_package_has_what_training_imports_and_no_models():
    with tarfile.open(fileobj=io.BytesIO(st.source_tarball()), mode="r:gz") as tar:
        names = set(tar.getnames())
    assert {"train_entry.py", "requirements.txt", "scripts/train_forecasts.py", "data/regions.yaml",
            "model/regions.py", "forecasting/evaluate.py", "sources/openmeteo.py"} <= names
    assert not any(n.startswith("forecasting/models") or "__pycache__" in n for n in names)


def test_request_shape():
    r = st.request("job1", "bkt", "arn:aws:iam::1:role/r", "ap-south-1", "ml.m5.xlarge", 45, "eu-north-1")
    assert r["ResourceConfig"]["InstanceType"] == "ml.m5.xlarge"
    assert r["AlgorithmSpecification"]["TrainingImage"].endswith("sagemaker-scikit-learn:1.4-2-py312-cpu-py3")
    hp = r["HyperParameters"]
    assert json.loads(hp["days"]) == 45 and json.loads(hp["regions"]) == "eu-north-1"
    assert json.loads(hp["sagemaker_submit_directory"]) == "s3://bkt/training/job1/source/sourcedir.tar.gz"
    assert r["OutputDataConfig"]["S3OutputPath"] == "s3://bkt/training/job1/output"
