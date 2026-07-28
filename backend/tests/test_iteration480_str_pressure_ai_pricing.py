"""Iteration 480 — STR pressure signal in AI pricing + cron STR scan verification."""
import os
import time
import pytest
import requests
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio

def _load_base():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass
    return ""

BASE = _load_base()
MONGO = os.environ.get("MONGO_URL")
DB = os.environ.get("DB_NAME")
ADMIN = {"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"}


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json=ADMIN, timeout=15)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def db():
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
    global MONGO, DB
    MONGO = os.environ.get("MONGO_URL")
    DB = os.environ.get("DB_NAME")
    client = AsyncIOMotorClient(MONGO)
    return client[DB]


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------- STR-market overview (Zurich dest_id fix) ----------
def test_str_overview_default_property_has_live(sess):
    r = sess.get(f"{BASE}/api/str-market/default/overview?days=30", timeout=20)
    assert r.status_code == 200, r.text
    js = r.json()
    summary = js.get("summary") or {}
    assert summary.get("live_dates", 0) >= 1, f"expected live_dates>=1, got {summary}"
    assert js.get("source") in ("hybrid", "booking-live"), js.get("source")


# ---------- Snapshots present for 'default' ----------
def test_str_snapshots_default_property(db):
    async def _q():
        cnt = await db.str_market_snapshots.count_documents(
            {"property_id": "default", "source": "booking-live", "method": "browser"}
        )
        return cnt
    cnt = _run(_q())
    assert cnt >= 1, f"expected at least 1 live snapshot for default, got {cnt}"


# ---------- Cron scan status ----------
def test_str_scan_status_cron_evidence(db):
    async def _q():
        docs = await db.str_scan_status.find({"started_by": "cron", "status": "done"}).to_list(100)
        return docs
    docs = _run(_q())
    props = {d.get("property_id") for d in docs}
    # spec says at least these should have cron-run entries
    expected_any = {"camden-suites", "city-rooms", "london-suites", "whitechapel-hotel"}
    hit = props & expected_any
    assert len(hit) >= 1, f"expected cron entries for one of {expected_any}, got {props}"
    # any cron done doc with live_ok>0
    any_live = any((d.get("live_ok") or 0) > 0 for d in docs)
    assert any_live, "no cron scan produced live_ok>0"


# ---------- AI Pricing suggestions include STR fields ----------
def test_ai_pricing_suggestions_have_str_fields(sess):
    r = sess.get(
        f"{BASE}/api/revenue/ai-pricing/default/suggestions?days=14&use_llm=false",
        timeout=45,
    )
    assert r.status_code == 200, r.text
    js = r.json()
    items = js.get("items") or js.get("suggestions") or []
    assert isinstance(items, list) and len(items) > 0, f"no items: {js}"
    for it in items[:3]:
        for k in ("str_mult", "str_median", "str_unavailable_pct"):
            assert k in it, f"missing key {k} in {it}"
    # at least one item should have str_median populated (fresh snapshots exist)
    has_median = any((it.get("str_median") or 0) > 0 for it in items)
    assert has_median, "no item populated with live str_median"


# ---------- STR pressure injection: verify str_mult=1.1 when unavailable_pct=92 ----------
def test_str_pressure_multiplier_injection(sess, db):
    async def _find_target():
        # pick any future snapshot for default
        docs = await db.str_market_snapshots.find(
            {"property_id": "default", "source": "booking-live"}
        ).to_list(50)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        future = [d for d in docs if d.get("date") and d["date"] >= today]
        return future[0] if future else (docs[0] if docs else None)

    target = _run(_find_target())
    assert target, "no snapshot to inject"
    orig_unavail = target.get("unavailable_pct", 0)
    target_date = target["date"]

    async def _set(val):
        await db.str_market_snapshots.update_one(
            {"_id": target["_id"]}, {"$set": {"unavailable_pct": val,
                                              "fetched_at": datetime.now(timezone.utc)}}
        )
    try:
        _run(_set(92))
        # allow any caches to settle
        time.sleep(1)
        r = sess.get(
            f"{BASE}/api/revenue/ai-pricing/default/suggestions?days=30&use_llm=false",
            timeout=45,
        )
        assert r.status_code == 200, r.text
        items = r.json().get("items") or r.json().get("suggestions") or []
        row = next((it for it in items if it.get("date") == target_date), None)
        assert row is not None, f"date {target_date} not in items"
        assert row.get("str_mult") == 1.1, f"expected str_mult=1.1, got {row.get('str_mult')} row={row}"
        assert (row.get("str_unavailable_pct") or 0) >= 90
    finally:
        # RESTORE
        _run(_set(orig_unavail))


# ---------- Regression: AI-pricing cadence ----------
def test_ai_pricing_cadence(sess):
    r = sess.get(f"{BASE}/api/revenue/ai-pricing/aldgate-flats/cadence", timeout=20)
    assert r.status_code == 200, r.text
    js = r.json()
    for k in ("runs_today", "applied_today", "target_updates_per_day", "horizon_days"):
        assert k in js, f"missing {k}: {js}"


# ---------- Regression: run-auto-apply logs even if skipped ----------
def test_ai_pricing_run_auto_apply_returns(sess):
    r = sess.post(f"{BASE}/api/revenue/ai-pricing/aldgate-flats/run-auto-apply", timeout=45)
    assert r.status_code == 200, r.text
    js = r.json()
    # ok status returned. Either applied count or skipped_reason present
    assert "ok" in js or "applied" in js or "skipped_reason" in js, js


# ---------- Regression: Base-curve config + preview ----------
def test_base_curve_config_and_preview(sess):
    r1 = sess.get(f"{BASE}/api/base-curve/aldgate-flats/config", timeout=15)
    assert r1.status_code == 200, r1.text
    r2 = sess.get(f"{BASE}/api/base-curve/aldgate-flats/preview?days=540", timeout=30)
    assert r2.status_code == 200, r2.text
    js = r2.json()
    rows = js.get("rows") or js.get("preview") or []
    assert isinstance(rows, list) and len(rows) > 0, f"no preview rows: {js}"
