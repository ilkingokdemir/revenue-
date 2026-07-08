"""
External Loyalty Integrations (iter 373) — MyHotelBox × Chain Loyalty Programs
==============================================================================
Link in-house loyalty members to their external hotel-chain loyalty accounts:
Marriott Bonvoy, Hilton Honors, IHG One Rewards, Accor ALL, Hyatt World of Hyatt,
Wyndham Rewards, Best Western Rewards.

Why this matters
----------------
- Guests earn points in both programs simultaneously (higher engagement).
- Elite tier recognition (Marriott Platinum, Hilton Diamond, …) becomes visible
  at check-in — front-desk can prioritize upgrades, welcome amenities, etc.
- OTA Auto-Assign (iter 372) now benefits from **external** loyalty tiers too.

Architecture
------------
- `external_loyalty_links` collection stores guest_id ↔ program membership.
- Provider **adapters** (`_ADAPTERS`) implement each chain's specific API.
  Currently all providers are **MOCKED** — swap the sync/earn methods with
  real partner-API calls once credentials/partner-agreements are in place.
- No PII is stored except member number & tier (encrypted in future work).

Endpoints
---------
  GET    /api/external-loyalty/programs                — list supported programs
  POST   /api/external-loyalty/link                     — link a guest
  GET    /api/external-loyalty/guest/{guest_id}         — get guest's links
  POST   /api/external-loyalty/sync/{link_id}           — refresh tier/points
  POST   /api/external-loyalty/earn/{link_id}           — push stay accrual
  DELETE /api/external-loyalty/link/{link_id}           — unlink
  GET    /api/external-loyalty/elite-arrivals           — today's elite arrivals

Env vars (production):
  MARRIOTT_BONVOY_API_KEY, HILTON_HONORS_API_KEY, IHG_API_KEY,
  ACCOR_ALL_API_KEY, HYATT_API_KEY, WYNDHAM_API_KEY, BEST_WESTERN_API_KEY
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
import hashlib
import logging
import os
import random
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ═══════════ SUPPORTED PROGRAMS ═══════════
PROGRAMS: Dict[str, Dict[str, Any]] = {
    "marriott_bonvoy": {
        "label":          "Marriott Bonvoy",
        "brand_color":    "#1c3f94",
        "member_format":  r"^\d{9,12}$",
        "tiers":          ["Member", "Silver", "Gold", "Platinum", "Titanium", "Ambassador"],
        "elite_tiers":    ["Platinum", "Titanium", "Ambassador"],
        "api_key_env":    "MARRIOTT_BONVOY_API_KEY",
        "prod_base_url":  "https://api.marriott.com/loyalty/v1",  # illustrative
    },
    "hilton_honors": {
        "label":          "Hilton Honors",
        "brand_color":    "#00426b",
        "member_format":  r"^\d{9,11}$",
        "tiers":          ["Member", "Silver", "Gold", "Diamond"],
        "elite_tiers":    ["Diamond", "Gold"],
        "api_key_env":    "HILTON_HONORS_API_KEY",
        "prod_base_url":  "https://api.hilton.com/hhonors/v1",
    },
    "ihg_one_rewards": {
        "label":          "IHG One Rewards",
        "brand_color":    "#c8102e",
        "member_format":  r"^\d{9,12}$",
        "tiers":          ["Club", "Silver", "Gold", "Platinum", "Diamond"],
        "elite_tiers":    ["Platinum", "Diamond"],
        "api_key_env":    "IHG_API_KEY",
        "prod_base_url":  "https://api.ihg.com/rewards/v1",
    },
    "accor_all": {
        "label":          "Accor ALL",
        "brand_color":    "#000000",
        "member_format":  r"^\d{10,15}$",
        "tiers":          ["Classic", "Silver", "Gold", "Platinum", "Diamond", "Limitless"],
        "elite_tiers":    ["Platinum", "Diamond", "Limitless"],
        "api_key_env":    "ACCOR_ALL_API_KEY",
        "prod_base_url":  "https://api.accor.com/all/v1",
    },
    "hyatt_world": {
        "label":          "World of Hyatt",
        "brand_color":    "#004b8d",
        "member_format":  r"^\d{6,10}$",
        "tiers":          ["Member", "Discoverist", "Explorist", "Globalist"],
        "elite_tiers":    ["Explorist", "Globalist"],
        "api_key_env":    "HYATT_API_KEY",
        "prod_base_url":  "https://api.hyatt.com/loyalty/v1",
    },
    "wyndham_rewards": {
        "label":          "Wyndham Rewards",
        "brand_color":    "#ea1d2c",
        "member_format":  r"^\d{9,11}$",
        "tiers":          ["Blue", "Gold", "Platinum", "Diamond"],
        "elite_tiers":    ["Platinum", "Diamond"],
        "api_key_env":    "WYNDHAM_API_KEY",
        "prod_base_url":  "https://api.wyndhamrewards.com/v1",
    },
    "best_western_rewards": {
        "label":          "Best Western Rewards",
        "brand_color":    "#003479",
        "member_format":  r"^\d{7,12}$",
        "tiers":          ["Blue", "Gold", "Platinum", "Diamond", "Diamond Select"],
        "elite_tiers":    ["Platinum", "Diamond", "Diamond Select"],
        "api_key_env":    "BEST_WESTERN_API_KEY",
        "prod_base_url":  "https://api.bestwestern.com/rewards/v1",
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ═══════════ MOCK PROVIDER ADAPTER ═══════════
# NOTE — this is a **MOCKED** adapter for MVP. Once partner API credentials
# are provided, replace `_mock_lookup` with actual HTTP calls to each chain.
class _MockProviderAdapter:
    """Deterministic mock that returns stable tier/points per (program, member_id).

    Uses SHA1(member_id) to seed a rolling tier + points. Points grow by ~10/day.
    """
    def __init__(self, program_key: str):
        self.program = program_key
        cfg = PROGRAMS.get(program_key)
        if not cfg:
            raise ValueError(f"Unknown program: {program_key}")
        self.cfg = cfg
        # In prod: self.session = httpx.AsyncClient(base_url=cfg["prod_base_url"])
        self.api_key = os.environ.get(cfg["api_key_env"])
        self._live = bool(self.api_key)

    async def lookup(self, member_id: str) -> Dict[str, Any]:
        # PROD: return await self._real_lookup(member_id)
        return self._mock_lookup(member_id)

    async def earn(self, member_id: str, stay_data: Dict[str, Any]) -> Dict[str, Any]:
        # PROD: return await self._real_earn(member_id, stay_data)
        return self._mock_earn(member_id, stay_data)

    def _mock_lookup(self, member_id: str) -> Dict[str, Any]:
        seed = int(hashlib.sha1(f"{self.program}:{member_id}".encode()).hexdigest(), 16)
        rng = random.Random(seed)
        tiers = self.cfg["tiers"]
        # Bias towards mid-tier — weighted pick
        weights = [1] + [3] * (len(tiers) - 2) + [1] if len(tiers) > 2 else [1] * len(tiers)
        tier = rng.choices(tiers, weights=weights, k=1)[0]
        # Points scale with tier position
        base_points = (tiers.index(tier) + 1) * 5000
        points = base_points + rng.randint(0, 4000)
        # Nights YTD scales
        nights_ytd = (tiers.index(tier) + 1) * 8 + rng.randint(0, 5)
        return {
            "member_id":    member_id,
            "tier":         tier,
            "points":       points,
            "nights_ytd":   nights_ytd,
            "is_elite":     tier in self.cfg["elite_tiers"],
            "fetched_at":   _now(),
            "source":       "mock",   # replace with "live" when real API wired
        }

    def _mock_earn(self, member_id: str, stay_data: Dict[str, Any]) -> Dict[str, Any]:
        seed = int(hashlib.sha1(f"{self.program}:{member_id}:{stay_data.get('check_in','')}".encode()).hexdigest(), 16)
        rng = random.Random(seed)
        spend = float(stay_data.get("total_spend") or 0)
        # Default earning ratio ~10 pts per unit spend
        base_ratio = 10
        # Elite tiers earn bonuses
        cur = self._mock_lookup(member_id)
        elite_bonus = 1.5 if cur["is_elite"] else 1.0
        points_earned = int(spend * base_ratio * elite_bonus)
        confirmation = f"EARN-{self.program.upper()[:3]}-{rng.randint(10_000_000, 99_999_999)}"
        return {
            "member_id":     member_id,
            "points_earned": points_earned,
            "spend":         spend,
            "elite_bonus":   elite_bonus,
            "confirmation":  confirmation,
            "posted_at":     _now(),
            "source":        "mock",
        }


def _adapter(program_key: str) -> _MockProviderAdapter:
    return _MockProviderAdapter(program_key)


# ═══════════ MODELS ═══════════
class LinkRequest(BaseModel):
    guest_id:     str
    program:      str
    member_id:    str    = Field(..., description="Guest's external membership ID")
    verify_now:   bool   = True


class EarnRequest(BaseModel):
    booking_id:   Optional[str] = None
    total_spend:  float
    check_in:     str
    check_out:    str
    property_id:  Optional[str] = None
    room_type:    Optional[str] = None


# ═══════════ ROUTER ═══════════
def create_external_loyalty_router(db, require_roles):
    router = APIRouter(prefix="/external-loyalty", tags=["external-loyalty"])

    @router.get("/programs")
    async def list_programs():
        """Public — no auth required — for the loyalty link form UI."""
        return [
            {
                "key":            k,
                "label":          v["label"],
                "brand_color":    v["brand_color"],
                "member_format":  v["member_format"],
                "tiers":          v["tiers"],
                "elite_tiers":    v["elite_tiers"],
                "live":           bool(os.environ.get(v["api_key_env"])),
            } for k, v in PROGRAMS.items()
        ]

    @router.post("/link")
    async def link_guest(body: LinkRequest,
                          _: dict = Depends(require_roles("admin", "manager",
                                                             "front_desk"))):
        if body.program not in PROGRAMS:
            raise HTTPException(400, f"Bilinmeyen program: {body.program}")
        cfg = PROGRAMS[body.program]
        if not re.match(cfg["member_format"], body.member_id.strip()):
            raise HTTPException(400,
                f"Geçersiz üye numarası formatı ({cfg['label']} beklenen: {cfg['member_format']})")

        # Idempotent: one link per (guest, program)
        existing = await db.external_loyalty_links.find_one(
            {"guest_id": body.guest_id, "program": body.program},
            {"_id": 0, "id": 1},
        )
        link_id = existing["id"] if existing else str(uuid.uuid4())

        # Verify by calling provider now (optional)
        verified: Dict[str, Any] = {}
        if body.verify_now:
            try:
                verified = await _adapter(body.program).lookup(body.member_id.strip())
            except Exception as e:
                logger.warning(f"Verify failed: {e}")
                verified = {"error": str(e)}

        doc = {
            "id":           link_id,
            "guest_id":     body.guest_id,
            "program":      body.program,
            "member_id":    body.member_id.strip(),
            "linked_at":    existing and existing.get("linked_at") or _now(),
            "last_sync_at": _now() if verified and "error" not in verified else None,
            "tier":         verified.get("tier"),
            "points":       verified.get("points"),
            "nights_ytd":   verified.get("nights_ytd"),
            "is_elite":     verified.get("is_elite", False),
            "sync_error":   verified.get("error"),
            "updated_at":   _now(),
        }
        doc = {k: v for k, v in doc.items() if v is not None}
        await db.external_loyalty_links.update_one(
            {"guest_id": body.guest_id, "program": body.program},
            {"$set": doc}, upsert=True,
        )
        return {
            "ok":       True,
            "link_id":  link_id,
            "verified": bool(verified and "error" not in verified),
            "tier":     verified.get("tier"),
            "is_elite": verified.get("is_elite", False),
        }

    @router.get("/guest/{guest_id}")
    async def list_guest_links(guest_id: str,
                                 _: dict = Depends(require_roles("admin",
                                                                    "manager",
                                                                    "front_desk"))):
        rows = await db.external_loyalty_links.find(
            {"guest_id": guest_id}, {"_id": 0}
        ).to_list(20)
        # Enrich with program label
        for r in rows:
            cfg = PROGRAMS.get(r["program"], {})
            r["program_label"] = cfg.get("label", r["program"])
            r["program_color"] = cfg.get("brand_color")
        return {"guest_id": guest_id, "total": len(rows), "items": rows}

    @router.post("/sync/{link_id}")
    async def sync_link(link_id: str,
                          _: dict = Depends(require_roles("admin", "manager",
                                                             "front_desk"))):
        link = await db.external_loyalty_links.find_one({"id": link_id}, {"_id": 0})
        if not link:
            raise HTTPException(404, "Link bulunamadı")
        try:
            data = await _adapter(link["program"]).lookup(link["member_id"])
        except Exception as e:
            raise HTTPException(502, f"Provider sync error: {e}")
        await db.external_loyalty_links.update_one(
            {"id": link_id},
            {"$set": {
                "tier":         data.get("tier"),
                "points":       data.get("points"),
                "nights_ytd":   data.get("nights_ytd"),
                "is_elite":     data.get("is_elite", False),
                "last_sync_at": _now(),
                "sync_error":   None,
                "updated_at":   _now(),
            }},
        )
        return {"ok": True, **data}

    @router.post("/earn/{link_id}")
    async def earn_for_stay(link_id: str, body: EarnRequest,
                              _: dict = Depends(require_roles("admin", "manager",
                                                                 "front_desk"))):
        link = await db.external_loyalty_links.find_one({"id": link_id}, {"_id": 0})
        if not link:
            raise HTTPException(404, "Link bulunamadı")
        # Idempotency: don't double-post the same booking_id
        if body.booking_id:
            dupe = await db.external_loyalty_earnings.find_one(
                {"link_id": link_id, "booking_id": body.booking_id}, {"_id": 0, "id": 1},
            )
            if dupe:
                return {"ok": False, "reason": "already_earned",
                         "earning_id": dupe["id"]}

        try:
            result = await _adapter(link["program"]).earn(
                link["member_id"],
                {"total_spend": body.total_spend, "check_in": body.check_in,
                 "check_out": body.check_out, "property_id": body.property_id,
                 "room_type": body.room_type},
            )
        except Exception as e:
            raise HTTPException(502, f"Provider earn error: {e}")

        earning_id = str(uuid.uuid4())
        await db.external_loyalty_earnings.insert_one({
            "id":            earning_id,
            "link_id":       link_id,
            "guest_id":      link["guest_id"],
            "program":       link["program"],
            "booking_id":    body.booking_id,
            "check_in":      body.check_in,
            "check_out":     body.check_out,
            "spend":         body.total_spend,
            "points_earned": result.get("points_earned"),
            "confirmation":  result.get("confirmation"),
            "posted_at":     _now(),
            "source":        result.get("source"),
        })
        return {"ok": True, "earning_id": earning_id, **result}

    @router.delete("/link/{link_id}")
    async def unlink(link_id: str,
                       _: dict = Depends(require_roles("admin", "manager"))):
        r = await db.external_loyalty_links.delete_one({"id": link_id})
        return {"ok": r.deleted_count > 0}

    @router.get("/elite-arrivals")
    async def elite_arrivals(days: int = 7,
                              property_id: Optional[str] = None,
                              _: dict = Depends(require_roles("admin", "manager",
                                                                 "front_desk"))):
        """Return today+N days arrivals that have elite external-loyalty tier.
        Front-desk should proactively welcome / upgrade these guests."""
        today = datetime.now(timezone.utc).date()
        end = today + timedelta(days=max(1, min(days, 30)))
        q: dict = {
            "check_in": {"$gte": today.isoformat(), "$lte": end.isoformat()},
            "status":   {"$ne": "cancelled"},
        }
        if property_id:
            q["property_id"] = property_id
        bookings = await db.bookings.find(q, {"_id": 0}).to_list(500)

        # Batch-lookup elite links per guest_email or guest_id
        elite_hits: List[dict] = []
        seen_pairs = set()
        for b in bookings:
            candidates = []
            if b.get("guest_email"):
                candidates.append({"guest_id": b["guest_email"]})
            if b.get("guest_id"):
                candidates.append({"guest_id": b["guest_id"]})
            for c in candidates:
                async for lnk in db.external_loyalty_links.find(
                    {**c, "is_elite": True}, {"_id": 0},
                ):
                    key = (b.get("id"), lnk["id"])
                    if key in seen_pairs:
                        continue
                    seen_pairs.add(key)
                    cfg = PROGRAMS.get(lnk["program"], {})
                    elite_hits.append({
                        "booking_id":   b.get("id"),
                        "guest_name":   b.get("guest_name"),
                        "check_in":     b.get("check_in"),
                        "room_number":  b.get("room_number"),
                        "property_id":  b.get("property_id"),
                        "program":      lnk["program"],
                        "program_label": cfg.get("label"),
                        "brand_color":  cfg.get("brand_color"),
                        "tier":         lnk.get("tier"),
                        "points":       lnk.get("points"),
                    })
        elite_hits.sort(key=lambda x: x["check_in"] or "")
        return {"total": len(elite_hits), "items": elite_hits}

    return router
