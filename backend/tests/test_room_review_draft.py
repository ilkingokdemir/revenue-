"""Paket - Yorum Yanıt Taslağı: room-review AI draft + approve/reject flow."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://review-hub-108.preview.emergentagent.com").rstrip("/")
PID = "aldgate-flats"
ROOM_TYPE_ID = "king-aldgate-flats"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"},
                      timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def H(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


def _list_reviews(H):
    r = requests.get(f"{BASE_URL}/api/reviews?property_id={PID}", headers=H, timeout=30)
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    if isinstance(data, dict):
        return data.get("reviews") or data.get("items") or []
    return data


def test_room_type_exists(H):
    r = requests.get(f"{BASE_URL}/api/room-types?property_id={PID}", headers=H, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"room-types endpoint {r.status_code}")
    items = r.json() if isinstance(r.json(), list) else r.json().get("items") or r.json().get("room_types") or []
    ids = [x.get("id") for x in items]
    assert ROOM_TYPE_ID in ids, f"{ROOM_TYPE_ID} not among {ids}"


def test_auto_tag_returns_drafted_key(H):
    r = requests.post(f"{BASE_URL}/api/booking/room-reviews/{PID}/auto-tag?limit=5",
                      headers=H, timeout=120)
    assert r.status_code == 200, r.text[:300]
    j = r.json()
    for k in ("tagged", "processed", "source", "drafted"):
        assert k in j, f"missing key {k} in {j}"


def test_full_draft_approve_reject_flow(H):
    reviews = _list_reviews(H)
    # pick 2 unresponded reviews
    candidates = [r for r in reviews
                  if str(r.get("response_status", "")).lower() not in ("responded", "pending_approval")]
    assert len(candidates) >= 2, f"need 2 unresponded reviews, got {len(candidates)}"
    r1, r2 = candidates[0], candidates[1]
    rid1, rid2 = r1["id"], r2["id"]

    # PUT tag both to king-aldgate-flats
    for rid in (rid1, rid2):
        r = requests.put(f"{BASE_URL}/api/booking/room-reviews/{rid}/tag",
                         headers=H, json={"room_type_id": ROOM_TYPE_ID}, timeout=30)
        assert r.status_code == 200, f"tag {rid}: {r.status_code} {r.text[:200]}"
        assert r.json().get("room_type_id") == ROOM_TYPE_ID

    # POST draft-replies
    r = requests.post(f"{BASE_URL}/api/booking/room-reviews/{PID}/draft-replies?limit=5",
                      headers=H, timeout=180)
    assert r.status_code == 200, r.text[:300]
    dj = r.json()
    assert "drafted" in dj and "candidates" in dj
    assert dj["drafted"] >= 1, f"expected drafted>=1 got {dj}"

    # GET drafts
    r = requests.get(f"{BASE_URL}/api/booking/room-reviews/{PID}/drafts",
                     headers=H, timeout=30)
    assert r.status_code == 200, r.text[:300]
    dj = r.json()
    assert dj.get("count", 0) >= 1, dj
    drafts = dj["drafts"]
    ids_in_drafts = {d["id"] for d in drafts}
    assert rid1 in ids_in_drafts or rid2 in ids_in_drafts

    sample = next(d for d in drafts if d["id"] in (rid1, rid2))
    assert (sample.get("response_text") or "").strip(), "empty draft text"
    assert sample.get("draft_room_name") == "Deluxe King Room", f"draft_room_name={sample.get('draft_room_name')}"
    assert sample.get("guest"), "missing guest"
    assert sample.get("rating") is not None
    assert isinstance(sample.get("text"), str) and len(sample["text"]) > 0

    initial_count = dj["count"]

    # Approve rid1
    r = requests.post(f"{BASE_URL}/api/reviews/{rid1}/approve",
                      headers=H, json={"action": "approve"}, timeout=60)
    if r.status_code != 200:
        # Might be blocked by privacy/risk – try with notes
        r = requests.post(f"{BASE_URL}/api/reviews/{rid1}/approve",
                          headers=H, json={"action": "approve", "notes": "Reviewed and safe"}, timeout=60)
    assert r.status_code == 200, f"approve rid1: {r.status_code} {r.text[:300]}"
    assert r.json().get("status") == "responded"

    # Verify count decreased
    r = requests.get(f"{BASE_URL}/api/booking/room-reviews/{PID}/drafts", headers=H, timeout=30)
    new_count = r.json().get("count", 0)
    assert new_count < initial_count, f"draft count did not decrease: {initial_count} -> {new_count}"

    # Edit + approve rid2 via submit-for-approval
    edited = "Edited Merhaba, geri bildiriminiz için teşekkür ederiz. Deluxe King Room deneyiminiz için tekrar bekliyoruz."
    r = requests.post(f"{BASE_URL}/api/reviews/{rid2}/submit-for-approval",
                      headers=H, json={"response_text": edited}, timeout=30)
    assert r.status_code == 200, f"submit-for-approval: {r.status_code} {r.text[:300]}"

    r = requests.post(f"{BASE_URL}/api/reviews/{rid2}/approve",
                      headers=H, json={"action": "approve", "notes": "ok"}, timeout=60)
    assert r.status_code == 200, f"approve rid2: {r.status_code} {r.text[:300]}"

    # Verify published text is edited one
    r = requests.get(f"{BASE_URL}/api/reviews/{rid2}", headers=H, timeout=20)
    if r.status_code == 200:
        rv = r.json()
        if isinstance(rv, dict) and "review" in rv:
            rv = rv["review"]
        assert rv.get("response_text", "").startswith("Edited"), f"published text not edited: {rv.get('response_text','')[:100]}"
        assert rv.get("response_status") == "responded"

    # Reject path — pick another candidate + tag + draft
    reviews = _list_reviews(H)
    more = [r for r in reviews
            if str(r.get("response_status", "")).lower() not in ("responded", "pending_approval", "rejected")
            and r["id"] not in (rid1, rid2)]
    if more:
        rid3 = more[0]["id"]
        requests.put(f"{BASE_URL}/api/booking/room-reviews/{rid3}/tag",
                     headers=H, json={"room_type_id": ROOM_TYPE_ID}, timeout=30)
        requests.post(f"{BASE_URL}/api/booking/room-reviews/{PID}/draft-replies?limit=5",
                      headers=H, timeout=180)
        r = requests.post(f"{BASE_URL}/api/reviews/{rid3}/approve",
                          headers=H, json={"action": "reject", "notes": "not appropriate"}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert r.json().get("status") == "rejected"
