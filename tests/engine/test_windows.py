from datetime import datetime, timedelta

import pytest

from engine.windows import format_time, languages, load_strings, segments, summarize

NOW = datetime(2026, 5, 26, 6)


def strip(pattern):
    """'GGAARR' -> (levels, times) starting at NOW."""
    names = {"G": "green", "A": "amber", "R": "red"}
    levels = [names[c] for c in pattern]
    return levels, [NOW + timedelta(hours=i) for i in range(len(levels))]


def test_segments_group_runs():
    segs = segments(*strip("GGRRRG"))
    assert [(s.level, s.start.hour, s.end.hour) for s in segs] == [
        ("green", 6, 8), ("red", 8, 11), ("green", 11, 12)
    ]


def test_green_then_red_morning():
    levels, times = strip("G" * 5 + "R" * 8 + "G" * 35)
    out = summarize(levels, times, work="heavy", lang="en")
    assert out["now"] == "green"
    assert out["sentences"] == [
        "Safe for heavy work now, until 11 AM.",
        "Avoid heavy work from 11 AM to 7 PM.",
    ]


def test_red_now_points_to_next_safe_window():
    levels, times = strip("R" * 12 + "A" * 4 + "G" * 6 + "R" * 26)
    out = summarize(levels, times, work="heavy", lang="en")
    assert out["sentences"][0] == "Danger now: stop heavy work and rest in shade until 6 PM."
    assert out["sentences"][-1] == "Next safe time for heavy work: 10 PM to 4 AM tomorrow."


def test_all_green_and_no_safe():
    assert summarize(*strip("G" * 48))["sentences"] == [
        "Safe for heavy work for the next 48 hours."
    ]
    assert summarize(*strip("R" * 48))["sentences"][-1] == (
        "No safe time for heavy work in the next 48 hours."
    )


def test_hindi_sentences():
    levels, times = strip("G" * 5 + "R" * 8 + "G" * 35)
    out = summarize(levels, times, work="heavy", lang="hi")
    assert out["now_word"] == "सुरक्षित"
    assert out["sentences"] == [
        "अभी भारी काम के लिए सुरक्षित है, सुबह 11 बजे तक।",
        "सुबह 11 बजे से शाम 7 बजे तक भारी काम न करें।",
    ]


@pytest.mark.parametrize(
    "hour,day,en,hi",
    [
        (6, 0, "6 AM", "सुबह 6 बजे"),
        (14, 0, "2 PM", "दोपहर 2 बजे"),
        (0, 1, "12 AM tomorrow", "कल रात 12 बजे"),
        (17, 1, "5 PM tomorrow", "कल शाम 5 बजे"),
        (21, 2, "9 PM day after tomorrow", "परसों रात 9 बजे"),
    ],
)
def test_time_labels(hour, day, en, hi):
    t = datetime(2026, 5, 26 + day, hour)
    assert format_time(t, NOW, "en") == en
    assert format_time(t, NOW, "hi") == hi


def test_waterlogging_wording():
    out = summarize(*strip("G" * 10 + "R" * 3 + "G" * 35), hazard="waterlogging")
    assert out["sentences"][1] == "Waterlogging likely from 4 PM to 7 PM. Avoid underpasses."


def test_every_language_has_every_key():
    s = load_strings()
    reference = s["en"]
    for lang in languages():
        for hazard in ("heat", "waterlogging"):
            assert set(s[lang][hazard]) == set(reference[hazard]), lang
        assert set(s[lang]["work"]) == set(reference["work"])
        assert set(s[lang]["work_oblique"]) == set(reference["work"])
        assert set(s[lang]["level"]) == set(reference["level"])


def test_hindi_oblique_adjective():
    levels, times = strip("G" * 5 + "R" * 43)
    out = summarize(levels, times, work="light", lang="hi")
    assert out["sentences"][0] == "अभी हल्के काम के लिए सुरक्षित है, सुबह 11 बजे तक।"
    assert out["sentences"][1] == "सुबह 11 बजे से परसों सुबह 6 बजे तक हल्का काम न करें।"
