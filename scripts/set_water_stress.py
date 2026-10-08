"""Fill in the WRI Aqueduct baseline water stress score (0-5) for regions in data/regions.yaml.

    python scripts/set_water_stress.py --list                      # coordinates to look up
    python scripts/set_water_stress.py ap-south-1=4.1 eu-north-1=0.4 ...

Look each value up in the Aqueduct Water Risk Atlas (https://www.wri.org/applications/aqueduct/water-risk-atlas):
search the region's coordinates, layer "Baseline Water Stress", read the score (0-5) for the basin.
A score changes the cost model: stress multiplier = 1 + score / 5 (docs/cost-model.md section 6).
The edit keeps the file's comments and layout; only that one line per region changes.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATH = ROOT / "data" / "regions.yaml"


def apply(text: str, scores: dict[str, float]) -> str:
    for rid, score in scores.items():
        if not 0 <= score <= 5:
            raise ValueError(f"{rid}: score must be between 0 and 5, got {score}")
        block = re.search(rf"(^  - id: {re.escape(rid)}\n)(.*?)(?=^  - id: |\Z)", text, flags=re.M | re.S)
        if not block:
            raise ValueError(f"no region {rid} in regions.yaml")
        body, n = re.subn(r"^(    water_stress_score:).*$", rf"\g<1> {score:g}", block.group(2), flags=re.M)
        if n != 1:
            raise ValueError(f"{rid}: no water_stress_score line to update")
        text = text[:block.start(2)] + body + text[block.end(2):]
    return text


def main(argv: list[str]) -> int:
    if not argv or argv == ["--list"]:
        sys.path.insert(0, str(ROOT))
        from model import regions

        for r in regions.load().values():
            print(f"{r.id:16} {r.name:34} lat {r.lat:7.2f}  lon {r.lon:8.2f}  current: {r.water_stress_score}")
        return 0
    try:
        scores = {k: float(v) for k, v in (a.split("=", 1) for a in argv)}
        PATH.write_text(apply(PATH.read_text(encoding="utf-8"), scores), encoding="utf-8")
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print("updated:", ", ".join(f"{k}={v:g}" for k, v in scores.items()), "-> now run: make validate && make test")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
