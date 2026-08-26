"""
Canlı Duman Testi (Live Smoke Test) — canlı URL'de uçtan uca akış doğrulaması:
sağlık → giriş → test rezervasyonu → Stripe checkout oturumu → temizlik (iptal).
Sonuçlar adım adım raporlanır ve live_smoke_runs koleksiyonunda arşivlenir.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict
import uuid
import httpx


def _now():
    return datetime.now(timezone.utc)


async def run_smoke(base_url: str, email: str, password: str, property_id: str) -> Dict:
    base = base_url.rstrip("/")
    steps = []
    booking_id = None
    token = None

    async def step(name, fn):
        t0 = _now()
        try:
            detail = await fn()
            steps.append({"name": name, "status": "pass", "detail": detail,
                          "ms": int((_now() - t0).total_seconds() * 1000)})
            return True
        except Exception as ex:
            steps.append({"name": name, "status": "fail", "detail": str(ex)[:200],
                          "ms": int((_now() - t0).total_seconds() * 1000)})
            return False

    async with httpx.AsyncClient(timeout=30) as client:
        async def s_health():
            r = await client.get(f"{base}/api/system-health/status")
            if r.status_code >= 500:
                raise Exception(f"HTTP {r.status_code}")
            return f"HTTP {r.status_code}"
        ok = await step("1. Sağlık kontrolü (/api/system-health/status)", s_health)

        async def s_login():
            nonlocal token
            r = await client.post(f"{base}/api/auth/login",
                                  json={"email": email, "password": password})
            if r.status_code != 200:
                raise Exception(f"HTTP {r.status_code}: {r.text[:120]}")
            d = r.json()
            token = d.get("access_token") or d.get("token")
            if not token:
                raise Exception("Token dönmedi")
            return "Giriş başarılı, token alındı"
        if ok:
            ok = await step("2. Giriş (auth/login)", s_login)

        H = {"Authorization": f"Bearer {token}"} if token else {}

        async def s_booking():
            nonlocal booking_id
            ci = (_now().date() + timedelta(days=30)).isoformat()
            co = (_now().date() + timedelta(days=31)).isoformat()
            r = await client.post(f"{base}/api/bookings", headers=H, json={
                "property_id": property_id, "guest_name": "SMOKE TEST — SİLİNECEK",
                "guest_email": "smoke@test.local", "check_in": ci, "check_out": co,
                "rate": 1, "notes": "Canlı duman testi — otomatik iptal edilir"})
            if r.status_code != 200:
                raise Exception(f"HTTP {r.status_code}: {r.text[:120]}")
            booking_id = r.json().get("id")
            return f"Rezervasyon oluşturuldu: {r.json().get('booking_ref')}"
        if ok:
            ok = await step("3. Test rezervasyonu oluştur (POST /api/bookings)", s_booking)

        async def s_stripe():
            r = await client.post(f"{base}/api/payments/booking-checkout", headers=H,
                                  json={"booking_id": booking_id, "origin_url": base})
            if r.status_code != 200:
                raise Exception(f"HTTP {r.status_code}: {r.text[:150]}")
            url = r.json().get("url") or r.json().get("checkout_url", "")
            if "stripe" not in url and "checkout" not in url:
                raise Exception(f"Checkout URL beklenmedik: {url[:80]}")
            return f"Stripe checkout oturumu açıldı: {url[:60]}…"
        if ok and booking_id:
            await step("4. Stripe checkout oturumu (booking-checkout)", s_stripe)

        async def s_cleanup():
            r = await client.put(f"{base}/api/bookings/{booking_id}/status",
                                 headers=H, params={"status": "cancelled"})
            if r.status_code != 200:
                raise Exception(f"HTTP {r.status_code}: {r.text[:120]}")
            return "Test rezervasyonu iptal edildi (temizlik tamam)"
        if booking_id:
            await step("5. Temizlik: test rezervasyonunu iptal et", s_cleanup)

    passed = sum(1 for s in steps if s["status"] == "pass")
    return {"id": str(uuid.uuid4()), "base_url": base, "property_id": property_id,
            "ran_at": _now().isoformat(), "steps": steps,
            "passed": passed, "total": len(steps),
            "verdict": "PASS" if passed == len(steps) and len(steps) >= 4 else "FAIL"}


def create_live_smoke_router(db, require_roles):
    router = APIRouter(prefix="/live-smoke", tags=["live-smoke"])

    @router.post("/run")
    async def run(data: Dict, u: dict = Depends(require_roles("admin"))):
        base_url = (data.get("base_url") or "").strip()
        if not base_url.startswith("http"):
            raise HTTPException(422, "Geçerli bir canlı URL girin (https://…)")
        result = await run_smoke(base_url, data.get("email", ""), data.get("password", ""),
                                 data.get("property_id", "default"))
        result["ran_by"] = u.get("name") or u.get("email", "")
        await db.live_smoke_runs.insert_one(dict(result))
        result.pop("_id", None)
        return result

    @router.get("/history")
    async def history(_u: dict = Depends(require_roles("admin"))):
        runs = await db.live_smoke_runs.find({}, {"_id": 0}).sort("ran_at", -1).to_list(20)
        return {"runs": runs}

    return router
