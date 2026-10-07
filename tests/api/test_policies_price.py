import pytest

from .conftest import NOW, body, http, load_handler


def authed(method, team, payload=None, groups="platform-leads", email="lead@example.com"):
    e = http(body=payload, path=f"/policies/{team}", path_params={"team": team})
    e["requestContext"] = {"http": {"method": method}, "authorizer": {"jwt": {"claims": {
        "sub": "u1", "email": email, "cognito:groups": groups}}}}
    return e


def test_policy_requires_sign_in_and_lead_group(aws):
    h = load_handler("policies")
    anon = http(path="/policies/ml", path_params={"team": "ml"})
    anon["requestContext"] = {"http": {"method": "GET"}}
    assert h(anon, None)["statusCode"] == 401
    assert h(authed("PUT", "ml", {"weights": {"water": 1, "carbon": 0}}, groups="engineers"), None)["statusCode"] == 403
    assert h(authed("GET", "ml"), None)["statusCode"] == 404


def test_lead_sets_policy_and_next_job_reflects_it(seeded):
    """Plan's done-when: a platform lead changes a team's weights and the next job reflects them."""
    h = load_handler("policies")
    put = h(authed("PUT", "ml", {"weights": {"water": 1, "carbon": 0},
                                 "allowed_regions": ["ap-south-1", "ap-southeast-1", "eu-north-1"]}), None)
    assert put["statusCode"] == 200 and body(put)["updated_by"] == "lead@example.com"
    assert body(h(authed("GET", "ml", groups="engineers"), None))["weights"] == {"water": 1.0, "carbon": 0.0}

    job = body(load_handler("submit_job")(http(body={"gpu_hours": 4, "deadline_h": 24, "team": "ml",
                                                     "weights": {"water": 0, "carbon": 1}}), None))
    assert job["request"]["weights"] == {"water": 1.0, "carbon": 0.0}       # policy wins
    assert job["placement"]["chosen"]["region"] in {"ap-south-1", "ap-southeast-1", "eu-north-1"}
    assert job["policy_applied"]["team"] == "ml"

    # the job may narrow regions further, but not escape the policy
    narrowed = body(load_handler("submit_job")(http(body={"gpu_hours": 1, "deadline_h": 6, "team": "ml",
                                                          "allowed_regions": ["eu-north-1", "us-east-1"]}), None))
    assert narrowed["request"]["allowed_regions"] == ["eu-north-1"]
    bad = load_handler("submit_job")(http(body={"gpu_hours": 1, "deadline_h": 6, "team": "ml",
                                                "allowed_regions": ["us-east-1"]}), None)
    assert bad["statusCode"] == 400


def test_unknown_team_and_bad_policy(seeded):
    assert load_handler("submit_job")(http(body={"gpu_hours": 1, "deadline_h": 6, "team": "ghost"}), None)["statusCode"] == 404
    h = load_handler("policies")
    assert h(authed("PUT", "ml", {"weights": {"water": 0, "carbon": 0}}), None)["statusCode"] == 400
    assert h(authed("PUT", "ml", {"allowed_regions": ["mars-1"]}), None)["statusCode"] == 400


def test_groups_claim_formats():
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("p", Path(__file__).resolve().parents[2] / "functions/policies/app.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    assert m.groups({"cognito:groups": "[platform-leads engineers]"}) == {"platform-leads", "engineers"}
    assert m.groups({"cognito:groups": ["platform-leads"]}) == {"platform-leads"}


def test_public_price(seeded):
    h = load_handler("get_price")
    r = h(http({"region": "ap-south-1", "hour": "2026-10-10T08:00"}), None)
    assert r["statusCode"] == 200 and r["headers"]["Cache-Control"] == "public, max-age=300"
    b = body(r)
    assert b["per_gpu_hour"]["litres"] == pytest.approx(b["per_kwh_it"]["litres"] * 0.4 * 0.7 * 1.3, rel=1e-2)
    assert b["inputs"]["weather_source"] == "synthetic"
    assert h(http({"region": "ap-south-1"}), None)["statusCode"] == 200            # defaults to now
    assert h(http({"region": "mars-1"}), None)["statusCode"] == 400
    assert h(http({"region": "ap-south-1", "hour": "nope"}), None)["statusCode"] == 400
    assert h(http({"region": "ap-south-1", "hour": "2030-01-01T00:00"}), None)["statusCode"] == 404
