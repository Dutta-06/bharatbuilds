"""Write data files in a diff-friendly layout: one list item per line."""

import json
from pathlib import Path

LIST_KEYS = ("cells", "hotspots", "points", "sources")


def dump(data: dict, path: Path) -> None:
    lines = ["{"]
    items = list(data.items())
    for i, (key, value) in enumerate(items):
        comma = "," if i < len(items) - 1 else ""
        if key in LIST_KEYS and isinstance(value, list):
            lines.append(f"  {json.dumps(key)}: [")
            for j, item in enumerate(value):
                sep = "," if j < len(value) - 1 else ""
                lines.append(f"    {json.dumps(item, ensure_ascii=False)}{sep}")
            lines.append(f"  ]{comma}")
        else:
            lines.append(f"  {json.dumps(key)}: {json.dumps(value, ensure_ascii=False)}{comma}")
    lines.append("}")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def load(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))
