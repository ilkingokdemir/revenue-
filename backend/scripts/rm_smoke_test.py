"""
Revenue Management smoke test — tüm GET endpoint'lerini tarar, 500/502/exception
veren endpoint'leri raporlar. Bug bulmak için.

Run: cd /app && python3 backend/scripts/rm_smoke_test.py
"""
import os
import re
import sys
import asyncio
import httpx
from datetime import datetime, timezone

API = "http://localhost:8001"
PROP = "aldgate-flats"
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

# Path param defaults
PARAM_DEFAULTS = {
    "{property_id}": PROP,
    "{date}": TODAY,
    "{comp_id}": "skip",
    "{plan_id}": "skip",
    "{season_id}": "skip",
    "{rule_id}": "skip",
    "{guest_id}": "skip",
    "{drate_id}": "skip",
    "{webhook_id}": "skip",
    "{experiment_id}": "skip",
    "{playbook_id}": "skip",
    "{segment_id}": "skip",
    "{promo_id}": "skip",
    "{product_id}": "skip",
    "{code_id}": "skip",
}


def expand_path(raw: str) -> str | None:
    """Replace {param} placeholders. Returns None if any unresolved 'skip'."""
    path = raw.strip().rstrip(')').strip('"')
    for k, v in PARAM_DEFAULTS.items():
        if k in path:
            if v == "skip":
                return None
            path = path.replace(k, v)
    # Catch-all: any remaining {x} → skip
    if "{" in path:
        return None
    return path


async def main():
    # 1. Load endpoints from grep output
    with open("/tmp/rm_endpoints.txt") as f:
        raw_endpoints = [line.strip() for line in f if line.strip()]

    # 2. Filter GET, expand
    gets = []
    for r in raw_endpoints:
        if not r.startswith("get("):
            continue
        path = expand_path(r[4:])
        if path:
            gets.append(path)

    print(f"Testing {len(gets)} GET endpoints on {API} (prop={PROP}, date={TODAY})")
    print()

    # 3. Login
    async with httpx.AsyncClient(base_url=API, timeout=20) as client:
        r = await client.post("/api/auth/login", json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"})
        r.raise_for_status()
        token = r.json().get("access_token") or r.json().get("token")
        headers = {"Authorization": f"Bearer {token}"}

        # 4. Hit each endpoint
        ok = []
        not_found = []
        broken = []
        for p in sorted(set(gets)):
            full = f"/api{p}"
            try:
                resp = await client.get(full, headers=headers)
                if resp.status_code == 200:
                    ok.append(full)
                elif resp.status_code in (401, 403):
                    ok.append(full)  # Auth ok, not a bug
                elif resp.status_code == 404:
                    not_found.append((full, resp.status_code))
                elif resp.status_code >= 500:
                    detail = ""
                    try:
                        detail = resp.json().get("detail", "")[:120]
                    except Exception:
                        detail = resp.text[:120]
                    broken.append((full, resp.status_code, detail))
                else:
                    not_found.append((full, resp.status_code))
            except Exception as e:
                broken.append((full, "EXC", str(e)[:120]))

        print(f"✅ 200/auth: {len(ok)}")
        print(f"⚠️  404/4xx: {len(not_found)}")
        print(f"❌ 500/exc: {len(broken)}")
        print()

        if broken:
            print("=== BROKEN (500/EXC) — bunları düzelt ===")
            for full, code, detail in broken:
                print(f"  [{code}] {full}")
                if detail:
                    print(f"        → {detail}")

        if not_found:
            print()
            print("=== 404/4xx (yanlış default param olabilir) ===")
            for full, code in not_found[:20]:
                print(f"  [{code}] {full}")


if __name__ == "__main__":
    asyncio.run(main())
