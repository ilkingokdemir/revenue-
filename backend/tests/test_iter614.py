"""Iter 614: Competitor Intel + Reward Wall + Root-Cause Tasks/Impact + Automation jobs."""
import os, uuid, pytest, requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://review-hub-108.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json().get("token") or r.json().get("access_token")


@pytest.fixture(scope="module")
def H(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ---- 1. Competitor Intel ----
def test_competitor_intel_default(H):
    r = requests.get(f"{API}/reputation/competitor-intel/default", headers=H, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("mode") in ("simulated", "live")
    comps = d.get("competitors") or []
    assert isinstance(comps, list) and len(comps) >= 1
    c0 = comps[0]
    for k in ("name", "mode", "reviews_analyzed", "strengths", "weaknesses", "amenities_praised", "they_have_we_dont"):
        assert k in c0, f"missing {k}"
    assert isinstance(d.get("they_have_we_dont"), list)
    assert isinstance(d.get("their_strength_our_weakness"), list)
    assert "our_weak_topics" in d and "our_strong_topics" in d
    assert isinstance(d.get("insight"), str)
    # sanity on they_have_we_dont items
    if d["they_have_we_dont"]:
        it = d["they_have_we_dont"][0]
        for k in ("item", "competitors", "action"):
            assert k in it


# ---- 2. Staff-praise leaderboard ----
def test_staff_praise_leaderboard(H):
    r = requests.get(f"{API}/reviews/staff-praise/leaderboard?property_id=default", headers=H, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "weekly_stars" in d and isinstance(d["weekly_stars"], list)
    badges = d.get("badges") or []
    assert isinstance(badges, list)
    sarah = next((b for b in badges if b["name"] == "Sarah"), None)
    if sarah is not None:
        # Same-week duplicates in staff_praise_log MUST NOT inflate weeks_won.
        assert sarah["weeks_won"] == 1, f"Sarah weeks_won={sarah['weeks_won']}, expected 1 (dedup by week)"
        assert "⭐ Haftanın Yıldızı" in sarah["badges"]
    board = d.get("monthly_leaderboard") or []
    assert isinstance(board, list)
    if board:
        row = board[0]
        for k in ("name", "rank", "positive", "negative", "avg_rating"):
            assert k in row


# ---- 3. My-tasks root_cause_tasks + complete ----
def test_my_tasks_root_cause_and_complete(H):
    r = requests.get(f"{API}/my-tasks", headers=H, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "root_cause_tasks" in d
    rct = d["root_cause_tasks"]
    assert isinstance(rct, list)
    if not rct:
        pytest.skip("No open root_cause tasks to complete")
    task = rct[0]
    assert task.get("source") == "root_cause"
    assert task.get("status") not in ("done", "resolved", "completed", "closed")
    tid = task["id"]

    r2 = requests.put(f"{API}/my-tasks/staff-task/{tid}/complete", headers=H, json={"notes": "test complete"}, timeout=30)
    assert r2.status_code == 200, r2.text
    assert r2.json().get("ok") is True
    assert r2.json().get("status") == "done"

    r3 = requests.get(f"{API}/my-tasks", headers=H, timeout=30)
    rct2 = r3.json().get("root_cause_tasks", [])
    assert not any(t["id"] == tid for t in rct2), "Completed task should not appear again"


def test_complete_staff_task_404(H):
    r = requests.put(f"{API}/my-tasks/staff-task/{uuid.uuid4()}/complete", headers=H, json={"notes": "x"}, timeout=30)
    assert r.status_code == 404


# ---- 4. Root-cause impact run + list ----
def test_root_cause_impact_run_and_list(H):
    r = requests.post(f"{API}/reviews/root-cause/impact/run?property_id=default", headers=H, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("ok") is True
    assert "reported" in d and isinstance(d["reported"], int)
    assert isinstance(d.get("reports"), list)

    r2 = requests.get(f"{API}/reviews/root-cause/impact?property_id=all", headers=H, timeout=30)
    assert r2.status_code == 200, r2.text
    items = r2.json().get("items") or []
    assert isinstance(items, list) and len(items) >= 1, "Expected at least 1 pre-existing impact item"
    it = items[0]
    for k in ("topic", "verdict", "before", "after"):
        assert k in it, f"missing {k}"
    assert it["verdict"] in ("improved", "worse", "unchanged", "insufficient_data")
    for w in ("before", "after"):
        assert "topic_avg_rating" in it[w]
        assert "negative_pct" in it[w]
    staff_row = next((x for x in items if x.get("topic") == "staff"), None)
    assert staff_row is not None, "Expected at least one 'staff' topic impact row"


# ---- 5. Automation jobs registry ----
def test_automation_jobs_registry(H):
    r = requests.get(f"{API}/automation/settings", headers=H, timeout=30)
    assert r.status_code == 200, r.text
    jobs = r.json().get("jobs") or r.json().get("registry") or r.json()
    # find in flattened text
    txt = str(jobs)
    assert "root_cause_impact" in txt
    assert "staff_praise_weekly" in txt
