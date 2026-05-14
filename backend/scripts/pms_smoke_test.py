"""
PMS smoke test — same approach as rm_smoke_test.py for all PMS-related routers.
"""
import os
import asyncio
import httpx
from datetime import datetime, timezone, timedelta

API = "http://localhost:8001"
PROP = "aldgate-flats"
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
TOMORROW = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")

PMS_ROUTE_FILES = [
    "bookings.py", "arrivals.py", "housekeeping.py", "maintenance.py",
    "inventory_allocations.py", "channel_manager.py", "walkin.py",
    "group_bookings.py", "group_rooming.py", "group_rooming_wiz.py",
    "booking_engine_v2.py", "booking_timeline.py", "booking_widget.py",
    "channel_hub.py", "channel_inbound.py", "channel_mappings.py",
    "channel_parity.py", "channel_restrictions.py", "channels_v2.py",
    "folio_live.py", "folio_split.py", "guest_app.py", "guest_journey.py",
    "guest_payment.py", "guest_portal_v2.py", "guest_prefs.py",
    "guest_profiles.py", "guest_rfm.py", "guest_services.py",
    "late_checkout.py", "late_checkout_offer.py", "night_audit.py",
    "night_audit_close.py", "pre_arrival.py", "preventive_maintenance.py",
    "room_move.py", "room_qr.py", "self_checkin_auto.py", "self_checkin_v2.py",
    "crm_360.py",
]

PARAM_DEFAULTS = {
    "{property_id}": PROP,
    "{date}": TODAY,
    "{check_in}": TODAY,
    "{check_out}": TOMORROW,
    "{booking_id}": "skip", "{room_id}": "skip", "{guest_id}": "skip",
    "{task_id}": "skip", "{order_id}": "skip", "{folio_id}": "skip",
    "{group_id}": "skip", "{job_id}": "skip", "{move_id}": "skip",
    "{request_id}": "skip", "{qr_id}": "skip", "{token}": "skip",
    "{session_id}": "skip", "{user_id}": "skip", "{org_id}": "skip",
    "{branch_id}": PROP, "{audit_id}": "skip", "{allocation_id}": "skip",
    "{template_id}": "skip", "{prefs_id}": "skip", "{channel_id}": "skip",
    "{webhook_id}": "skip", "{rate_plan_id}": "skip", "{event_id}": "skip",
    "{pre_id}": "skip", "{mapping_id}": "skip", "{policy_id}": "skip",
    "{slot_id}": "skip", "{key_id}": "skip", "{lock_id}": "skip",
    "{room_no}": "skip", "{schedule_id}": "skip", "{checklist_id}": "skip",
}


def expand(p: str) -> str | None:
    p = p.strip().rstrip(')').strip('"').strip("'")
    for k, v in PARAM_DEFAULTS.items():
        if k in p:
            if v == "skip":
                return None
            p = p.replace(k, v)
    if "{" in p:
        return None
    return p


async def main():
    # Collect endpoints
    import re
    all_gets = []
    for fname in PMS_ROUTE_FILES:
        path = f"/app/backend/routes/{fname}"
        if not os.path.exists(path):
            continue
        with open(path) as f:
            content = f.read()
        for m in re.finditer(r'@\w+\.get\("([^"]+)"', content):
            ep = expand(m.group(1))
            if ep:
                all_gets.append((fname, ep))

    uniq = list({(f, p) for f, p in all_gets})
    print(f"Found {len(uniq)} unique GET endpoints across {len(PMS_ROUTE_FILES)} PMS files")

    async with httpx.AsyncClient(base_url=API, timeout=20) as client:
        r = await client.post("/api/auth/login", json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"})
        r.raise_for_status()
        token = r.json().get("access_token") or r.json().get("token")
        headers = {"Authorization": f"Bearer {token}"}

        ok = []
        client_err = []
        broken = []
        for fname, p in sorted(uniq, key=lambda x: x[1]):
            full = f"/api{p}"
            try:
                resp = await client.get(full, headers=headers)
                if resp.status_code in (200, 401, 403):
                    ok.append((fname, full))
                elif resp.status_code >= 500:
                    detail = ""
                    try:
                        detail = resp.json().get("detail", "")
                        if isinstance(detail, list):
                            detail = str(detail)[:160]
                        else:
                            detail = str(detail)[:160]
                    except Exception:
                        detail = resp.text[:160]
                    broken.append((fname, full, resp.status_code, detail))
                else:
                    client_err.append((fname, full, resp.status_code))
            except Exception as e:
                broken.append((fname, full, "EXC", str(e)[:160]))

        print(f"\n✅ OK (200/auth): {len(ok)}")
        print(f"⚠️  4xx: {len(client_err)}")
        print(f"❌ 500/EXC: {len(broken)}")

        if broken:
            print("\n=== BROKEN ===")
            for fname, full, code, detail in broken:
                print(f"  [{code}] {fname:35s} {full}")
                if detail:
                    print(f"        → {detail}")

        if client_err:
            print("\n=== 4xx (first 15) ===")
            for fname, full, code in client_err[:15]:
                print(f"  [{code}] {fname:35s} {full}")


if __name__ == "__main__":
    asyncio.run(main())
