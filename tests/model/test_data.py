import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from calibrate_wue import write_scale  # noqa: E402
from validate_data import validate  # noqa: E402

from model import regions  # noqa: E402


def copy_repo(tmp_path):
    for sub in ("model", "data"):
        shutil.copytree(ROOT / sub, tmp_path / sub, ignore=shutil.ignore_patterns("__pycache__"))
    return tmp_path


def test_shipped_config_has_no_errors():
    errors, _ = validate(ROOT)
    assert errors == []


def test_validator_catches_missing_source(tmp_path):
    root = copy_repo(tmp_path)
    path = root / "model" / "coefficients.yaml"
    data = yaml.safe_load(path.read_text())
    del data["physics"]["air_specific_heat"]["source"]
    path.write_text(yaml.safe_dump(data, allow_unicode=True))
    errors, _ = validate(root)
    assert any("air_specific_heat is missing `source`" in e for e in errors)


def test_validator_catches_bad_region(tmp_path):
    root = copy_repo(tmp_path)
    path = root / "data" / "regions.yaml"
    data = yaml.safe_load(path.read_text())
    data["regions"][0]["grid_mix"]["shares"]["coal"] = 5.0
    data["regions"][1]["grid_mix"]["shares"]["fusion"] = 0.0
    path.write_text(yaml.safe_dump(data))
    errors, _ = validate(root)
    assert any("sum to" in e for e in errors)
    assert any("unknown sources" in e for e in errors)


def test_write_scale_keeps_file_valid(tmp_path):
    root = copy_repo(tmp_path)
    path = root / "data" / "regions.yaml"
    write_scale(path, "ap-southeast-1", 0.7563)
    write_scale(path, "ap-southeast-1", 0.75)      # replaces, does not duplicate
    write_scale(path, "us-west-2", 1.2)            # last block in the file
    text = path.read_text()
    assert text.count("\n    wue_scale: ") == 2
    loaded = regions.load.__wrapped__(path)
    assert loaded["ap-southeast-1"].wue_scale == 0.75
    assert loaded["us-west-2"].wue_scale == 1.2
    assert loaded["ap-south-1"].wue_scale == 1.0
    assert "# AWS regions Pravaah" in text            # comments survive
    errors, _ = validate(root)
    assert errors == []


def test_regions_load():
    rs = regions.load()
    assert 5 <= len(rs) <= 8
    sg = rs["ap-southeast-1"]
    assert sg.disclosed_wue == 1.68 and sg.cooling_type == "tower"
    assert rs["ap-south-1"].disclosed_wue == 0.98  # APAC aggregate fallback
