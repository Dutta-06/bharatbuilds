"""Turn an hourly risk strip into plain-language safe windows.

All user-facing words live in ``strings/windows.json`` so a translator can
edit them without touching code. Adding a language means adding a key there.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

from .thresholds import GREEN, LEVELS, RED

STRINGS_PATH = Path(__file__).parent / "strings" / "windows.json"
HAZARDS = ("heat", "waterlogging")


@lru_cache(maxsize=1)
def load_strings() -> dict:
    with STRINGS_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def languages() -> list[str]:
    return list(load_strings())


@dataclass(frozen=True)
class Segment:
    level: str
    start: datetime
    end: datetime  # exclusive: the hour the next level begins


def segments(levels: Sequence[str], times: Sequence[datetime]) -> list[Segment]:
    """Group consecutive hours with the same level."""
    if len(levels) != len(times):
        raise ValueError("levels and times must be the same length")
    out: list[Segment] = []
    for level, t in zip(levels, times):
        if level not in LEVELS:
            raise ValueError(f"unknown level {level!r}")
        if out and out[-1].level == level:
            out[-1] = Segment(level, out[-1].start, t + timedelta(hours=1))
        else:
            out.append(Segment(level, t, t + timedelta(hours=1)))
    return out


def format_time(t: datetime, now: datetime, lang: str) -> str:
    """'2 PM', '6 AM tomorrow', 'दोपहर 2 बजे', 'कल सुबह 6 बजे'."""
    s = load_strings()[lang]["time"]
    hour12 = t.hour % 12 or 12
    if "dayparts" in s:
        meridiem = next(p["word"] for p in s["dayparts"] if p["from"] <= t.hour <= p["to"])
    else:
        meridiem = s["am"] if t.hour < 12 else s["pm"]
    days = (t.date() - now.date()).days
    if days == 0:
        return s["format"].format(hour=hour12, meridiem=meridiem)
    day = s["day"].get(str(days), t.strftime("%d %b"))
    return s["format_other_day"].format(hour=hour12, meridiem=meridiem, day=day)


def summarize(
    levels: Sequence[str],
    times: Sequence[datetime],
    work: str = "heavy",
    hazard: str = "heat",
    lang: str = "en",
) -> dict:
    """Sentences and windows for a strip. ``times[0]`` is treated as now.

    Returns ``{"now": level, "sentences": [...], "windows": [...]}``.
    """
    if hazard not in HAZARDS:
        raise ValueError(f"hazard must be one of {HAZARDS}")
    strings = load_strings()
    if lang not in strings:
        raise ValueError(f"no strings for language {lang!r}")
    if not levels:
        raise ValueError("empty strip")

    t = strings[lang][hazard]
    work_word = strings[lang]["work"][work]
    # Hindi adjectives inflect before a postposition: "हल्का काम" but "हल्के काम के लिए"
    words = {"work": work_word, "work_obl": strings[lang]["work_oblique"][work]}
    now = times[0]
    segs = segments(levels, times)
    fmt = lambda dt: format_time(dt, now, lang)  # noqa: E731

    def fmt_range(seg: Segment) -> dict:
        # "7 PM tomorrow to 11 PM", not "7 PM tomorrow to 11 PM tomorrow"
        end_ref = seg.start if seg.end.date() == seg.start.date() else now
        return {"start": fmt(seg.start), "end": format_time(seg.end, end_ref, lang)}

    first = segs[0]
    sentences = []
    if len(segs) == 1:
        sentences.append(t[f"now_{first.level}_all"].format(**words))
    else:
        sentences.append(t[f"now_{first.level}_until"].format(**words, time=fmt(first.end)))

        if first.level != RED:
            red = next((s for s in segs[1:] if s.level == RED), None)
            if red:
                sentences.append(
                    t["next_red"].format(**words, **fmt_range(red))
                )

    if first.level != GREEN:
        safe = next((s for s in segs[1:] if s.level == GREEN), None)
        if safe:
            sentences.append(
                t["next_safe"].format(**words, **fmt_range(safe))
            )
        else:
            sentences.append(t["no_safe"].format(**words))

    return {
        "now": first.level,
        "now_word": strings[lang]["level"][first.level],
        "sentences": sentences,
        "windows": [
            {
                "level": s.level,
                "start": s.start.isoformat(timespec="minutes"),
                "end": s.end.isoformat(timespec="minutes"),
                "start_label": fmt(s.start),
                "end_label": fmt(s.end),
            }
            for s in segs
        ],
    }
