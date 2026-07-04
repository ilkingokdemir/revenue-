"""
Test Mews University endpoints + ROAS Auto Budget Suggestion (iter 364).
"""
import os
import io
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://review-hub-108.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def hdr(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ─── Mews University ──────────────────────────────────────────────
class TestUniversity:
    def test_seed_first_time(self, hdr):
        r = requests.post(f"{BASE_URL}/api/university/courses/seed", headers=hdr, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("ok") is True
        assert "courses_created" in d and "lessons_created" in d
        # May be 0 if already seeded from earlier

    def test_seed_idempotent(self, hdr):
        r = requests.post(f"{BASE_URL}/api/university/courses/seed", headers=hdr, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["courses_created"] == 0
        assert d["lessons_created"] == 0

    def test_list_courses(self, hdr):
        r = requests.get(f"{BASE_URL}/api/university/courses", headers=hdr, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "items" in d and len(d["items"]) >= 6
        c0 = d["items"][0]
        for key in ("id", "title", "lesson_count", "completed_lessons", "progress_pct", "is_mandatory"):
            assert key in c0, f"missing {key}"
        assert isinstance(c0["is_mandatory"], bool)

    def test_get_course_hides_correct_index(self, hdr):
        courses = requests.get(f"{BASE_URL}/api/university/courses", headers=hdr).json()["items"]
        cid = courses[0]["id"]
        r = requests.get(f"{BASE_URL}/api/university/courses/{cid}", headers=hdr, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "lessons" in d and len(d["lessons"]) > 0
        for l in d["lessons"]:
            assert "completed" in l
            if l.get("quiz"):
                assert "question" in l["quiz"] and "options" in l["quiz"]
                assert "correct_index" not in l["quiz"], "correct_index leaked!"

    def test_enroll_idempotent(self, hdr):
        courses = requests.get(f"{BASE_URL}/api/university/courses", headers=hdr).json()["items"]
        cid = courses[0]["id"]
        r1 = requests.post(f"{BASE_URL}/api/university/courses/{cid}/enroll", headers=hdr, timeout=15)
        assert r1.status_code == 200
        assert r1.json().get("enrolled") is True
        r2 = requests.post(f"{BASE_URL}/api/university/courses/{cid}/enroll", headers=hdr, timeout=15)
        assert r2.status_code == 200

    def test_complete_lesson_and_me(self, hdr):
        courses = requests.get(f"{BASE_URL}/api/university/courses", headers=hdr).json()["items"]
        cid = courses[0]["id"]
        course = requests.get(f"{BASE_URL}/api/university/courses/{cid}", headers=hdr).json()
        # first non-quiz lesson
        lesson = next((l for l in course["lessons"] if not l.get("quiz")), None)
        assert lesson
        r = requests.put(f"{BASE_URL}/api/university/lessons/{lesson['id']}/complete",
                          headers=hdr, timeout=15)
        assert r.status_code == 200
        assert r.json().get("ok") is True

        # verify via /me
        me = requests.get(f"{BASE_URL}/api/university/me", headers=hdr).json()
        assert me["total_lessons_done"] >= 1
        assert me["total_enrolled"] >= 1
        assert any(it["course_id"] == cid for it in me["items"])

    def test_quiz_wrong_and_right(self, hdr):
        courses = requests.get(f"{BASE_URL}/api/university/courses", headers=hdr).json()["items"]
        cid = courses[0]["id"]
        course = requests.get(f"{BASE_URL}/api/university/courses/{cid}", headers=hdr).json()
        quiz_lesson = next((l for l in course["lessons"] if l.get("quiz")), None)
        assert quiz_lesson
        n_opts = len(quiz_lesson["quiz"]["options"])
        # try answer 0
        r1 = requests.post(f"{BASE_URL}/api/university/lessons/{quiz_lesson['id']}/quiz",
                            headers=hdr, json={"answer_index": 0}, timeout=15)
        assert r1.status_code == 200
        d1 = r1.json()
        assert "passed" in d1 and "score" in d1 and "correct_index" in d1
        correct = d1["correct_index"]
        assert 0 <= correct < n_opts

        # submit correct answer
        r2 = requests.post(f"{BASE_URL}/api/university/lessons/{quiz_lesson['id']}/quiz",
                            headers=hdr, json={"answer_index": correct}, timeout=15)
        assert r2.status_code == 200
        assert r2.json()["passed"] is True
        assert r2.json()["score"] == 100

    def test_leaderboard_admin(self, hdr):
        r = requests.get(f"{BASE_URL}/api/university/leaderboard?days=30", headers=hdr, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "items" in d
        if d["items"]:
            assert "avg_quiz_score" in d["items"][0]
            assert "lessons_done" in d["items"][0]

    def test_leaderboard_forbidden_for_recep(self):
        # try with test receptionist
        rr = requests.post(f"{BASE_URL}/api/auth/login",
                            json={"email": "testrecep@hotelbox.com", "password": "Test2026!"})
        if rr.status_code != 200:
            pytest.skip("recep not available")
        tok = rr.json().get("access_token")
        r = requests.get(f"{BASE_URL}/api/university/leaderboard",
                          headers={"Authorization": f"Bearer {tok}"}, timeout=15)
        assert r.status_code in (401, 403)


# ─── ROAS Auto Budget Suggestion ──────────────────────────────────
class TestRoasSuggestion:
    PROP = f"TEST_roas_{uuid.uuid4().hex[:6]}"

    def _seed(self, hdr):
        # Upload cost CSV with 3 campaigns
        csv_text = ("Campaign,Cost,Currency,Clicks,Impressions\n"
                    "TEST_red_camp,500,GBP,100,5000\n"
                    "TEST_yellow_camp,200,GBP,80,3000\n"
                    "TEST_green_camp,50,GBP,40,1500\n")
        files = {"file": ("costs.csv", csv_text.encode(), "text/csv")}
        r = requests.post(f"{BASE_URL}/api/attribution/{self.PROP}/roas/cost",
                          headers=hdr, files=files, timeout=15)
        assert r.status_code == 200, r.text

        # Seed booking attribution rows
        # red: revenue 100 (roas 0.2 <break_even)
        # yellow: revenue 400 (roas 2.0 → between 1.5 & 2.5 be, hold territory)
        # green: revenue 800 (roas 16.0 → >8*be → double)
        seeds = [
            ("TEST_red_camp", 100),
            ("TEST_yellow_camp", 400),
            ("TEST_green_camp", 800),
        ]
        for camp, val in seeds:
            for i in range(2):
                bid = f"TEST_{camp}_{i}_{uuid.uuid4().hex[:6]}"
                requests.post(f"{BASE_URL}/api/attribution/track", headers=hdr, json={
                    "booking_id": bid,
                    "property_id": self.PROP,
                    "utm_source": "google",
                    "utm_campaign": camp,
                    "value": val / 2,
                    "currency": "GBP",
                }, timeout=10)

    def test_roas_shape_and_suggestions(self, hdr):
        self._seed(hdr)
        r = requests.get(f"{BASE_URL}/api/attribution/{self.PROP}/roas?days=30&margin_pct=60",
                          headers=hdr, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "campaigns" in d
        assert "action_summary" in d
        for key in ("cut", "hold", "increase", "double", "info", "skip",
                    "potential_savings", "potential_increase"):
            assert key in d["action_summary"], f"missing key {key} in action_summary"

        by_camp = {c["campaign"]: c for c in d["campaigns"]}
        for expected in ("TEST_red_camp", "TEST_yellow_camp", "TEST_green_camp"):
            assert expected in by_camp, f"{expected} not in response"
            sug = by_camp[expected].get("suggestion")
            assert sug is not None
            for k in ("action", "delta_pct", "delta_amount", "headline", "reason"):
                assert k in sug, f"suggestion missing {k}"

        # red camp (roas 0.2 < break_even=1.67) → cut, -50
        red = by_camp["TEST_red_camp"]
        assert red["status"] == "red"
        assert red["suggestion"]["action"] == "cut"
        assert red["suggestion"]["delta_pct"] == -50

        # green camp (revenue 800 cost 50 → roas 16 → > break_even*8=13.33) → double, +100
        green = by_camp["TEST_green_camp"]
        assert green["status"] == "green"
        assert green["suggestion"]["action"] == "double"
        assert green["suggestion"]["delta_pct"] == 100

        # yellow (rev 400 cost 200 → roas 2 → be 1.67; be*1.5=2.5. roas<2.5 → cut -30)
        yel = by_camp["TEST_yellow_camp"]
        # roas 2.0 → status = yellow (>=1)
        assert yel["status"] == "yellow"
        # Per code: <break_even*1.5 (2.5) → cut -30
        assert yel["suggestion"]["action"] in ("cut", "hold")

    def test_action_summary_counts(self, hdr):
        r = requests.get(f"{BASE_URL}/api/attribution/{self.PROP}/roas?days=30&margin_pct=60",
                          headers=hdr, timeout=15).json()
        s = r["action_summary"]
        # at least 1 cut (red camp), 1 double (green camp)
        assert s["cut"] >= 1
        assert s["double"] >= 1
        assert s["potential_savings"] > 0
        assert s["potential_increase"] > 0
