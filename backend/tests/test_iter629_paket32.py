"""Iter 629 (Paket 32) backend tests:
(1) Maintenance photo normalize (data-URL → /api/uploads/maintenance/*.png, dict passthrough)
(2) Accountant archive flow (settings, send, history, public token download, email_outbox)
(3) A/B auto-close worker (_ab_auto_close) and site-builder persistence of ab_auto_n
"""
import base64
import io
import os
import re
import zipfile
import asyncio

import pytest
import requests

def _load_frontend_env():
    p = "/app/frontend/.env"
    if os.path.exists(p):
        for ln in open(p):
            ln = ln.strip()
            if ln.startswith("REACT_APP_BACKEND_URL="):
                return ln.split("=", 1)[1].strip().strip('"').strip("'")
    return None
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _load_frontend_env() or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL not set"
API = f"{BASE_URL}/api"
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
PROP = "default"

# 1x1 transparent PNG
PNG_1x1 = ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=")
DATA_URL = f"data:image/png;base64,{PNG_1x1}"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def H(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ============ (1) PHOTOS NORMALIZE ============
class TestPhotosNormalize:
    def test_mixed_data_url_and_path(self, H):
        payload = {
            "property_id": PROP,
            "title": "QA photo-normalize test",
            "description": "iter629",
            "category": "plumbing",
            "priority": "low",
            "location": "QA",
            "room_number": "999",
            "photos_before": [DATA_URL, "/api/uploads/maintenance/x.png"],
        }
        r = requests.post(f"{API}/maintenance/issues", headers=H, json=payload, timeout=30)
        assert r.status_code in (200, 201), r.text[:500]
        d = r.json()
        pb = d.get("photos_before")
        assert isinstance(pb, list) and len(pb) == 2, pb
        for p in pb:
            assert isinstance(p, dict), f"expected dict got {type(p)}: {p}"
            assert p.get("url", "").startswith("/api/uploads/maintenance/"), p
            assert p.get("uploaded_by"), p
            assert p.get("type") == "before", p
        # first from data-URL must have source hk_mobile
        assert pb[0].get("source") == "hk_mobile", pb[0]
        # fetch first url → 200 image/png
        url1 = BASE_URL + pb[0]["url"]
        g = requests.get(url1, timeout=15)
        assert g.status_code == 200, url1
        assert g.headers.get("content-type", "").startswith("image/"), g.headers

    def test_passthrough_dict_objects(self, H):
        obj = {"url": "/api/uploads/maintenance/preset.png", "uploaded_by": "QA", "type": "before"}
        payload = {
            "property_id": PROP,
            "title": "QA photo-passthrough",
            "description": "iter629",
            "category": "plumbing",
            "priority": "low",
            "photos_before": [obj],
        }
        r = requests.post(f"{API}/maintenance/issues", headers=H, json=payload, timeout=15)
        assert r.status_code in (200, 201), r.text[:400]
        pb = r.json().get("photos_before")
        assert isinstance(pb, list) and len(pb) == 1
        # should be unchanged (dict passes through). type/url preserved
        assert pb[0]["url"] == obj["url"]
        assert pb[0].get("type") == "before"


# ============ (2) ACCOUNTANT ============
class TestAccountant:
    def test_settings_put_and_echo(self, H):
        r = requests.put(f"{API}/tr-compliance/efatura/{PROP}/settings", headers=H,
                         json={"accountant_email": "muhasebe@example.com", "accountant_name": "Ayşe"}, timeout=15)
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        s = d.get("settings") or d
        assert s.get("accountant_email") == "muhasebe@example.com"
        assert s.get("accountant_name") == "Ayşe"

    def test_archive_send_ok_2026_09(self, H):
        r = requests.post(f"{API}/tr-compliance/efatura/{PROP}/archive/send", headers=H,
                         json={"month": "2026-09"}, timeout=60)
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        assert int(d.get("count") or 0) > 0
        assert "total" in d
        assert d.get("email_status") in ("mocked", "sent", "logged", "queued") or d.get("email_status")
        # per spec: email_status 'mocked'
        assert d.get("email_status") == "mocked", d
        assert d.get("auto") is False

    def test_archive_send_empty_month_404(self, H):
        r = requests.post(f"{API}/tr-compliance/efatura/{PROP}/archive/send", headers=H,
                         json={"month": "2031-01"}, timeout=15)
        assert r.status_code == 404, r.text[:200]

    def test_missing_accountant_email_422(self, H):
        # Save old accountant_email
        cur = requests.get(f"{API}/tr-compliance/efatura/{PROP}/settings", headers=H, timeout=10).json()
        old = cur.get("accountant_email") or "muhasebe@example.com"
        try:
            r = requests.put(f"{API}/tr-compliance/efatura/{PROP}/settings", headers=H,
                             json={"accountant_email": ""}, timeout=15)
            assert r.status_code == 200
            rs = requests.post(f"{API}/tr-compliance/efatura/{PROP}/archive/send", headers=H,
                              json={"month": "2026-09"}, timeout=15)
            assert rs.status_code == 422, rs.text[:200]
        finally:
            # restore
            requests.put(f"{API}/tr-compliance/efatura/{PROP}/settings", headers=H,
                         json={"accountant_email": old}, timeout=15)

    def test_history_no_token(self, H):
        r = requests.get(f"{API}/tr-compliance/efatura/{PROP}/archive/history", headers=H, timeout=15)
        assert r.status_code == 200
        body = r.json()
        rows = body.get("history") if isinstance(body, dict) else body
        assert isinstance(rows, list) and len(rows) >= 1
        for row in rows:
            assert "token" not in row, f"token leaked in history: {row}"

    def test_public_download_by_token(self, H):
        # Fetch newest token from Mongo via a backend endpoint? We access via history is redacted.
        # Use an in-process mongo query through a debug endpoint alternative: send archive and use the DB.
        # We'll query via localhost mongo directly through motor in a subprocess. Simpler: use pymongo.
        try:
            from pymongo import MongoClient
        except Exception:
            pytest.skip("pymongo not installed")
        mongo_url = os.environ.get("MONGO_URL") or "mongodb://localhost:27017"
        db_name = os.environ.get("DB_NAME") or "test_database"
        # server env may differ from pytest env — try reading backend .env
        env_path = "/app/backend/.env"
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("MONGO_URL="):
                        mongo_url = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if line.startswith("DB_NAME="):
                        db_name = line.split("=", 1)[1].strip().strip('"').strip("'")
        cli = MongoClient(mongo_url)
        rec = cli[db_name].tr_einvoice_archives.find_one(
            {"property_id": PROP}, sort=[("created_at", -1)])
        assert rec, "No archive record in DB"
        token = rec["token"]
        # bad token → 404
        bad = requests.get(f"{API}/tr-compliance/efatura/archive-download/deadbeef00000000", timeout=15)
        assert bad.status_code == 404

        # good token, no auth
        g = requests.get(f"{API}/tr-compliance/efatura/archive-download/{token}", timeout=30)
        assert g.status_code == 200, g.text[:200]
        assert g.headers.get("content-type") == "application/zip"
        zf = zipfile.ZipFile(io.BytesIO(g.content))
        names = zf.namelist()
        assert any(n.startswith("xml/") for n in names) or any(n.startswith("pdf/") for n in names), names
        assert any(n.startswith("pdf/") for n in names), names
        assert any(n.startswith("ozet_") and n.endswith(".csv") for n in names), names

        # email_outbox check
        ob = list(cli[db_name].email_outbox.find({"kind": "efatura_archive"}).sort("created_at", -1).limit(5))
        assert ob, "No efatura_archive email_outbox entry"
        # link with token should be present in html body (any of the recent 5)
        found = any(token in (row.get("html") or row.get("body") or "") for row in ob)
        assert found, f"token link not found in recent efatura_archive emails: sample={ob[0].keys() if ob else None}"


# ============ (3) A/B auto-close + site persistence ============
class TestABAutoClose:
    def test_worker_and_restore(self):
        """Run _ab_auto_close directly against motor DB; verify winner applied then restore."""
        # This calls the actual worker function in /app/backend/workers.py in a subprocess
        # to keep the pytest process light. Use exec via python -c calling asyncio.
        code = r'''
import os, sys, asyncio
sys.path.insert(0, "/app/backend")
from motor.motor_asyncio import AsyncIOMotorClient
from workers import _ab_auto_close

async def main():
    env = {}
    with open("/app/backend/.env") as f:
        for ln in f:
            ln = ln.strip()
            if "=" in ln and not ln.startswith("#"):
                k,v = ln.split("=",1); env[k]=v.strip().strip('"').strip("'")
    cli = AsyncIOMotorClient(env["MONGO_URL"])
    db = cli[env["DB_NAME"]]

    # Setup: on default property, find QANOW10 post and set ab_auto_n=5, title_b restored.
    site = await db.hotel_sites.find_one({"property_id":"default"})
    posts = (site.get("content") or {}).get("posts") or []
    # ensure QANOW10 title_b + ab_auto_n=5
    idx = None
    for i,p in enumerate(posts):
        if p.get("promo_code") == "QANOW10":
            idx = i; break
    assert idx is not None, "QANOW10 missing"
    slug = posts[idx].get("slug") or "aktif-kampanya"
    print("SLUG", slug)
    await db.hotel_sites.update_one(
        {"property_id":"default", "content.posts.promo_code":"QANOW10"},
        {"$set":{
            f"content.posts.{idx}.title_b":"Şimdi rezerve et, %10 kazan!",
            f"content.posts.{idx}.ab_auto_n":5,
            f"content.posts.{idx}.ab_winner":"",
            f"content.posts.{idx}.ab_auto_closed":False,
            f"content.posts.{idx}.title":"Aktif Kampanya",
        }})

    # Clean any qa-ab- test rows
    await db.site_visits.delete_many({"id": {"$regex": "^qa-ab-"}})

    # Insert 6 view + 3 cta_click for variant B on the actual slug
    page = f"blog/{slug}"
    for i in range(6):
        await db.site_visits.insert_one({"id": f"qa-ab-v-{i}", "property_id":"default","event":"view","page": page,"variant":"B"})
    for i in range(3):
        await db.site_visits.insert_one({"id": f"qa-ab-c-{i}", "property_id":"default","event":"cta_click","page": page,"variant":"B"})

    # Also add a untouched post scenario: ensure QAWIN20 has ab_auto_n=100000, keep title
    idx2 = None
    for i,p in enumerate(posts):
        if p.get("promo_code") == "QAWIN20":
            idx2 = i; break
    orig_qawin_title = None
    orig_qawin_title_b = None
    if idx2 is not None:
        orig_qawin_title = posts[idx2].get("title")
        orig_qawin_title_b = posts[idx2].get("title_b") or ""
        await db.hotel_sites.update_one(
            {"property_id":"default"},
            {"$set":{
                f"content.posts.{idx2}.ab_auto_n":100000,
                f"content.posts.{idx2}.title_b": orig_qawin_title_b or "Alt QA başlık",
                f"content.posts.{idx2}.ab_auto_closed": False,
            }})

    # Fire worker
    await _ab_auto_close(db)

    # Verify
    site2 = await db.hotel_sites.find_one({"property_id":"default"})
    posts2 = (site2.get("content") or {}).get("posts") or []
    for p in posts2:
        if p.get("promo_code") == "QANOW10":
            assert p["title"] == "Şimdi rezerve et, %10 kazan!", ("QANOW10 title=", p["title"])
            assert p.get("title_b","") == "", ("title_b not cleared", p.get("title_b"))
            assert p.get("ab_winner") == "B", ("winner=", p.get("ab_winner"))
            assert p.get("ab_auto_closed") is True, ("auto_closed=", p.get("ab_auto_closed"))
            assert isinstance(p.get("ab_result"), dict), ("ab_result", p.get("ab_result"))
            print("OK QANOW10 closed")
        if p.get("promo_code") == "QAWIN20":
            assert p.get("ab_auto_closed") is not True, ("QAWIN20 should be untouched", p)
            print("OK QAWIN20 untouched")

    # RESTORE QANOW10
    idx = None
    for i,p in enumerate(posts2):
        if p.get("promo_code") == "QANOW10":
            idx = i; break
    await db.hotel_sites.update_one(
        {"property_id":"default"},
        {"$set":{
            f"content.posts.{idx}.title":"Aktif Kampanya",
            f"content.posts.{idx}.title_b":"Şimdi rezerve et, %10 kazan!",
            f"content.posts.{idx}.ab_auto_n":200,
            f"content.posts.{idx}.ab_winner":"",
            f"content.posts.{idx}.ab_auto_closed":False,
        }, "$unset":{f"content.posts.{idx}.ab_result":""}})

    # Restore QAWIN20 ab_auto_n back to 200 and title_b if originally empty
    if idx2 is not None:
        set_ops = {f"content.posts.{idx2}.ab_auto_n":200}
        if not orig_qawin_title_b:
            set_ops[f"content.posts.{idx2}.title_b"] = ""
        await db.hotel_sites.update_one({"property_id":"default"}, {"$set": set_ops})

    # Cleanup site_visits inserted
    r = await db.site_visits.delete_many({"id": {"$regex": "^qa-ab-"}})
    print("DELETED", r.deleted_count)
    print("ALL OK")

asyncio.run(main())
'''
        import subprocess
        proc = subprocess.run(["python", "-c", code], capture_output=True, text=True, timeout=120)
        out = proc.stdout + "\n" + proc.stderr
        print(out)
        assert "ALL OK" in out, out

    def test_site_persistence_ab_auto_n(self, H):
        # GET config, change QANOW10 ab_auto_n to 300, POST back, GET verify, restore to 200
        cfg = requests.get(f"{API}/site-builder/{PROP}", headers=H, timeout=15).json()
        site = cfg.get("site") or cfg
        content = site.get("content") or {}
        posts = content.get("posts") or []
        found = False
        for p in posts:
            if p.get("promo_code") == "QANOW10":
                p["ab_auto_n"] = 300
                found = True
        assert found, "QANOW10 missing in site content"
        payload = {"template": site.get("template", "classic"), "content": content,
                   "mode": site.get("mode", "simple"),
                   "engine_template": site.get("engine_template", ""),
                   "published": bool(site.get("published"))}
        r = requests.post(f"{API}/site-builder/{PROP}", headers=H, json=payload, timeout=30)
        assert r.status_code in (200, 201), r.text[:300]
        cfg2 = requests.get(f"{API}/site-builder/{PROP}", headers=H, timeout=15).json()
        site2 = cfg2.get("site") or cfg2
        posts2 = (site2.get("content") or {}).get("posts") or []
        for p in posts2:
            if p.get("promo_code") == "QANOW10":
                assert int(p.get("ab_auto_n")) == 300, p
        # restore 200
        for p in posts2:
            if p.get("promo_code") == "QANOW10":
                p["ab_auto_n"] = 200
        payload2 = {"template": site2.get("template", "classic"),
                    "content": site2.get("content", {}),
                    "mode": site2.get("mode", "simple"),
                    "engine_template": site2.get("engine_template", ""),
                    "published": bool(site2.get("published"))}
        rr = requests.post(f"{API}/site-builder/{PROP}", headers=H, json=payload2, timeout=30)
        assert rr.status_code in (200, 201)
