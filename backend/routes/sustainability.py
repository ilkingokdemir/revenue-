"""
Sustainability / ESG dashboard — modern PMS competitive wedge.

Tracks per-property monthly utility readings, computes per-room-night intensity
metrics (kWh/RN, water L/RN, waste kg/RN, CO2 kg/RN), grades performance vs the
property baseline, and surfaces an aggregate ESG score (0-100).

AI Auto-Quote for Group Requests — quick-win bolt-on that uses GPT-5.2 to draft
a price quote + reasoning given the group request payload + property base rates.

Endpoints:
- GET    /api/esg/{property_id}/config
- POST   /api/esg/{property_id}/config       (baseline + green initiatives)
- POST   /api/esg/{property_id}/reading      (monthly utility entry)
- DELETE /api/esg/{property_id}/reading/{reading_id}
- GET    /api/esg/{property_id}/dashboard    (score + trend + intensity)
- POST   /api/group-booking/{booking_id}/ai-quote   (admin)
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date
from typing import Dict, Optional, List
import os
import uuid
import logging

logger = logging.getLogger(__name__)


def create_sustainability_router(db, require_roles):
    router = APIRouter()

    DEFAULT_INITIATIVES = [
        {"key": "led_lighting",   "label": "LED lighting throughout",                "weight": 8,  "active": False},
        {"key": "linen_reuse",    "label": "Towel & linen reuse programme",          "weight": 6,  "active": False},
        {"key": "key_card_power", "label": "Key-card power cut on departure",        "weight": 6,  "active": False},
        {"key": "low_flow",       "label": "Low-flow taps & showers",                "weight": 7,  "active": False},
        {"key": "no_singles",     "label": "No single-use plastics in rooms",        "weight": 8,  "active": False},
        {"key": "local_food",     "label": "≥50% local sourcing on F&B",             "weight": 8,  "active": False},
        {"key": "renewable",      "label": "100% renewable electricity tariff",       "weight": 12, "active": False},
        {"key": "ev_charge",      "label": "On-site EV charging point",              "weight": 5,  "active": False},
        {"key": "compost",        "label": "Food waste composting",                  "weight": 6,  "active": False},
        {"key": "carbon_offset",  "label": "Carbon offset on every booking",         "weight": 8,  "active": False},
    ]

    DEFAULT_CONFIG = {
        "kwh_baseline_per_rn": 30.0,    # industry mid-range for boutique
        "water_baseline_per_rn": 250.0, # litres per room-night
        "waste_baseline_per_rn": 1.0,   # kg per room-night
        "co2_factor_grid":      0.207,  # kg CO2e / kWh — UK 2024 average
        "currency": "GBP",
    }

    # ============================================================
    # CONFIG
    # ============================================================
    @router.get("/esg/{property_id}/config")
    async def get_config(property_id: str,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        doc = await db.esg_config.find_one({"property_id": property_id}, {"_id": 0})
        if not doc:
            doc = {**DEFAULT_CONFIG, "property_id": property_id, "initiatives": DEFAULT_INITIATIVES}
        # Ensure all default initiatives are present
        existing_keys = {i.get("key") for i in (doc.get("initiatives") or [])}
        for di in DEFAULT_INITIATIVES:
            if di["key"] not in existing_keys:
                doc.setdefault("initiatives", []).append(dict(di))
        return doc

    @router.post("/esg/{property_id}/config")
    async def save_config(property_id: str, data: Dict,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        update = {
            "property_id": property_id,
            "kwh_baseline_per_rn":  float(data.get("kwh_baseline_per_rn",  DEFAULT_CONFIG["kwh_baseline_per_rn"])),
            "water_baseline_per_rn": float(data.get("water_baseline_per_rn", DEFAULT_CONFIG["water_baseline_per_rn"])),
            "waste_baseline_per_rn": float(data.get("waste_baseline_per_rn", DEFAULT_CONFIG["waste_baseline_per_rn"])),
            "co2_factor_grid":      float(data.get("co2_factor_grid",      DEFAULT_CONFIG["co2_factor_grid"])),
            "initiatives":          data.get("initiatives") or DEFAULT_INITIATIVES,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_by": current_user.get("name", current_user.get("email", "")),
        }
        await db.esg_config.update_one({"property_id": property_id}, {"$set": update}, upsert=True)
        return {"ok": True, "config": update}

    # ============================================================
    # READINGS — monthly utility entry
    # ============================================================
    @router.post("/esg/{property_id}/reading")
    async def add_reading(property_id: str, data: Dict,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        """Body: { month: 'YYYY-MM', kwh, water_litres, waste_kg, gas_kwh? }"""
        month = (data.get("month") or "").strip()
        if not month or len(month) != 7:
            raise HTTPException(400, "month must be 'YYYY-MM'")
        doc = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "month": month,
            "kwh":          float(data.get("kwh") or 0),
            "water_litres": float(data.get("water_litres") or 0),
            "waste_kg":     float(data.get("waste_kg") or 0),
            "gas_kwh":      float(data.get("gas_kwh") or 0),
            "notes":        (data.get("notes") or "")[:240],
            "created_at":   datetime.now(timezone.utc).isoformat(),
            "created_by":   current_user.get("name", ""),
        }
        # Replace existing reading for the same month (idempotent)
        await db.esg_readings.delete_many({"property_id": property_id, "month": month})
        await db.esg_readings.insert_one(dict(doc))
        return doc

    @router.delete("/esg/{property_id}/reading/{reading_id}")
    async def delete_reading(property_id: str, reading_id: str,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        r = await db.esg_readings.delete_one({"property_id": property_id, "id": reading_id})
        if r.deleted_count == 0:
            raise HTTPException(404, "Reading not found")
        return {"ok": True}

    # ============================================================
    # DASHBOARD
    # ============================================================
    @router.get("/esg/{property_id}/dashboard")
    async def dashboard(property_id: str, months: int = 12,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        months = max(3, min(int(months), 24))

        # Config (with defaults)
        cfg = await db.esg_config.find_one({"property_id": property_id}, {"_id": 0}) or {}
        kwh_b   = float(cfg.get("kwh_baseline_per_rn",   DEFAULT_CONFIG["kwh_baseline_per_rn"]))
        water_b = float(cfg.get("water_baseline_per_rn", DEFAULT_CONFIG["water_baseline_per_rn"]))
        waste_b = float(cfg.get("waste_baseline_per_rn", DEFAULT_CONFIG["waste_baseline_per_rn"]))
        co2f    = float(cfg.get("co2_factor_grid",       DEFAULT_CONFIG["co2_factor_grid"]))
        initiatives = cfg.get("initiatives") or DEFAULT_INITIATIVES

        # Readings (last N months)
        readings = await db.esg_readings.find(
            {"property_id": property_id}, {"_id": 0}
        ).sort("month", -1).to_list(months)
        readings.reverse()

        # Bookings → room-nights per month
        # Pull bookings overlapping each month
        rows = []
        for r in readings:
            ym = r["month"]
            try:
                y, m = ym.split("-")
                y, m = int(y), int(m)
                first = date(y, m, 1)
                last = date(y + (1 if m == 12 else 0), 1 if m == 12 else m + 1, 1) - timedelta(days=1)
            except Exception:
                continue
            first_iso, last_iso = first.isoformat(), (last + timedelta(days=1)).isoformat()
            room_nights = 0
            async for b in db.bookings.find({
                "property_id": property_id,
                "check_in": {"$lt": last_iso},
                "check_out": {"$gt": first_iso},
                "status": {"$nin": ["cancelled"]},
            }, {"_id": 0, "check_in": 1, "check_out": 1}):
                ci = max(date.fromisoformat(b["check_in"][:10]), first)
                co = min(date.fromisoformat(b["check_out"][:10]), last + timedelta(days=1))
                rn = max(0, (co - ci).days)
                room_nights += rn
            room_nights = max(room_nights, 1)  # avoid div0

            kwh_rn   = round(r["kwh"]   / room_nights, 2) if r["kwh"]   else 0
            water_rn = round(r["water_litres"] / room_nights, 1) if r["water_litres"] else 0
            waste_rn = round(r["waste_kg"]     / room_nights, 3) if r["waste_kg"]     else 0
            co2_total = round((r["kwh"] + r.get("gas_kwh", 0)) * co2f, 1)
            co2_rn    = round(co2_total / room_nights, 2)

            rows.append({
                **r,
                "room_nights": room_nights,
                "kwh_per_rn":   kwh_rn,
                "water_per_rn": water_rn,
                "waste_per_rn": waste_rn,
                "co2_total_kg": co2_total,
                "co2_per_rn":   co2_rn,
                "kwh_vs_baseline_pct":   round(((kwh_rn   - kwh_b)   / kwh_b)   * 100, 1) if kwh_b   and kwh_rn   else None,
                "water_vs_baseline_pct": round(((water_rn - water_b) / water_b) * 100, 1) if water_b and water_rn else None,
                "waste_vs_baseline_pct": round(((waste_rn - waste_b) / waste_b) * 100, 1) if waste_b and waste_rn else None,
            })

        # Aggregate score:
        #   intensity_score: 100 - clamp(avg vs baseline, -50..+50)*1.5
        #   initiatives_score: sum of active weights (max 74) → scaled to 0..100
        if rows:
            recent = rows[-3:] if len(rows) >= 3 else rows
            kwh_avg_dev   = sum(r["kwh_vs_baseline_pct"]   or 0 for r in recent) / max(1, len(recent))
            water_avg_dev = sum(r["water_vs_baseline_pct"] or 0 for r in recent) / max(1, len(recent))
            waste_avg_dev = sum(r["waste_vs_baseline_pct"] or 0 for r in recent) / max(1, len(recent))
            avg_dev = (kwh_avg_dev + water_avg_dev + waste_avg_dev) / 3
            intensity_score = max(0, min(100, round(100 - avg_dev * 1.5)))
        else:
            intensity_score = None

        active_weight = sum(i.get("weight", 0) for i in initiatives if i.get("active"))
        max_weight    = sum(i.get("weight", 0) for i in initiatives) or 1
        initiatives_score = round((active_weight / max_weight) * 100)

        if intensity_score is not None:
            esg_score = round(intensity_score * 0.6 + initiatives_score * 0.4)
        else:
            esg_score = initiatives_score

        grade = "A+" if esg_score >= 90 else "A" if esg_score >= 80 else "B" if esg_score >= 65 else "C" if esg_score >= 50 else "D"

        # Latest month snapshot for big tiles
        latest = rows[-1] if rows else None

        return {
            "property_id": property_id,
            "esg_score": esg_score,
            "grade": grade,
            "intensity_score": intensity_score,
            "initiatives_score": initiatives_score,
            "active_initiatives_count": sum(1 for i in initiatives if i.get("active")),
            "total_initiatives_count": len(initiatives),
            "latest": latest,
            "trend": rows,
            "config": {
                "kwh_baseline_per_rn":   kwh_b,
                "water_baseline_per_rn": water_b,
                "waste_baseline_per_rn": waste_b,
                "co2_factor_grid":       co2f,
            },
            "initiatives": initiatives,
            "as_of": datetime.now(timezone.utc).isoformat(),
        }

    # ============================================================
    # AI AUTO-QUOTE for group bookings
    # ============================================================
    @router.post("/group-booking/{booking_id}/ai-quote")
    async def ai_auto_quote(booking_id: str,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        """GPT-5.2 reads the group request + property base rates and returns a
        suggested quote price + breakdown reasoning. Saves nothing — admin
        decides whether to apply via the existing PUT endpoint."""
        gb = await db.group_bookings.find_one({"id": booking_id}, {"_id": 0})
        if not gb:
            raise HTTPException(404, "Group request not found")
        property_id = gb.get("property_id", "")

        # Property + room types for context
        prop = await db.properties.find_one({"id": property_id}, {"_id": 0}) or {}
        rooms = await db.room_types.find({"property_id": property_id}, {"_id": 0}).to_list(20)
        avg_rate = sum(float(r.get("base_rate", 100)) for r in rooms) / max(1, len(rooms)) if rooms else 100

        try:
            ci = date.fromisoformat(gb.get("check_in", "")[:10])
            co = date.fromisoformat(gb.get("check_out", "")[:10])
            nights = max(1, (co - ci).days)
        except Exception:
            nights = 1
        total_rooms = int(gb.get("total_rooms") or 1)

        # Heuristic baseline: avg_rate * rooms * nights * (1 - group_discount)
        group_disc = 0.10 if total_rooms >= 10 else 0.05
        heuristic_total = round(avg_rate * total_rooms * nights * (1 - group_disc), 2)

        api_key = os.environ.get("EMERGENT_LLM_KEY", "")
        if not api_key:
            return {
                "suggested_total": heuristic_total,
                "per_room_per_night": round(heuristic_total / max(1, total_rooms * nights), 2),
                "discount_pct": round(group_disc * 100, 1),
                "currency": "GBP",
                "reasoning": (
                    f"Heuristic: avg base rate £{round(avg_rate)} × {total_rooms} rooms × "
                    f"{nights} nights × (1 − {int(group_disc*100)}% group discount) = £{heuristic_total}."
                ),
                "fallback": True,
            }

        from emergentintegrations.llm.chat import LlmChat, UserMessage
        sys_prompt = (
            "You are a hotel sales manager preparing a quote for a group booking enquiry. "
            "Return STRICT JSON only: "
            '{"suggested_total":NUMBER,"per_room_per_night":NUMBER,"discount_pct":NUMBER,'
            '"currency":"GBP","reasoning":"2-3 short sentences"}. '
            "Rules: never go below 70% of base × rooms × nights; offer a bigger discount "
            "for >15 rooms or >5 nights; consider event_type (corporate/wedding can carry 5-12% discount); "
            "for tight budget hints, lean to the discounted end. No markdown, no extra fields."
        )
        payload = {
            "rooms_in_property": [
                {"name": r.get("name"), "base_rate": r.get("base_rate"), "max_occupancy": r.get("max_occupancy", 2)}
                for r in rooms[:8]
            ],
            "request": {k: gb.get(k) for k in [
                "contact_name", "company_name", "event_type", "check_in", "check_out",
                "total_rooms", "total_guests", "room_preferences", "special_requirements",
                "budget_range",
            ]},
            "nights": nights,
            "avg_base_rate": round(avg_rate, 2),
            "currency": "GBP",
        }
        try:
            llm = LlmChat(
                api_key=api_key, session_id=f"ai-quote-{booking_id[:8]}",
                system_message=sys_prompt,
            ).with_model("openai", "gpt-5.2")
            import json as _json, re as _re
            resp = await llm.send_message(UserMessage(text=_json.dumps(payload)))
            txt = (resp or "").strip()
            m = _re.search(r"\{.*\}", txt, _re.DOTALL)
            parsed = _json.loads(m.group(0)) if m else {}
            parsed.setdefault("currency", "GBP")
            parsed["fallback"] = False
            return parsed
        except Exception as e:
            logger.exception("AI quote failed: %s", e)
            return {
                "suggested_total": heuristic_total,
                "per_room_per_night": round(heuristic_total / max(1, total_rooms * nights), 2),
                "discount_pct": round(group_disc * 100, 1),
                "currency": "GBP",
                "reasoning": "AI engine unavailable; heuristic quote shown.",
                "fallback": True,
                "error": str(e)[:200],
            }

    # ============================================================
    # PUBLIC: ESG eco-badge (used on direct booking widget header)
    # ============================================================
    @router.get("/esg/{property_id}/public-badge")
    async def public_badge(property_id: str):
        cfg = await db.esg_config.find_one({"property_id": property_id}, {"_id": 0}) or {}
        readings = await db.esg_readings.find(
            {"property_id": property_id}, {"_id": 0}
        ).sort("month", -1).to_list(3)
        initiatives = cfg.get("initiatives") or []
        active = [i for i in initiatives if i.get("active")]
        active_weight = sum(i.get("weight", 0) for i in active)
        max_weight = sum(i.get("weight", 0) for i in initiatives) or 1
        initiatives_score = round((active_weight / max_weight) * 100)
        # If we have readings, pull intensity score from dashboard logic (lighter version)
        score = initiatives_score
        if readings:
            # very light intensity proxy: use latest deviation
            try:
                kwh_b = float(cfg.get("kwh_baseline_per_rn", 30))
                # estimate kWh/RN as kwh/30 rooms*30 days; close enough for the badge
                est_rn = 600
                kwh_rn = readings[0]["kwh"] / est_rn if readings[0].get("kwh") else 0
                dev = ((kwh_rn - kwh_b) / kwh_b) * 100 if kwh_b and kwh_rn else 0
                intensity_score = max(0, min(100, round(100 - dev * 1.5)))
                score = round(intensity_score * 0.6 + initiatives_score * 0.4)
            except Exception:
                pass
        grade = "A+" if score >= 90 else "A" if score >= 80 else "B" if score >= 65 else "C" if score >= 50 else "D"
        return {
            "score": score,
            "grade": grade,
            "show_badge": score >= 65,                # only show B or above
            "active_initiatives": len(active),
            "highlight_initiatives": [i.get("label") for i in active[:3]],
        }

    # ============================================================
    # PUBLIC: Carbon offset fee calculator
    # ============================================================
    @router.get("/esg/{property_id}/carbon-offset-quote")
    async def carbon_offset_quote(property_id: str, nights: int = 1, rooms: int = 1):
        """Public: small voluntary fee added at checkout for offsetting CO2.
        £1.50 / room / night by default (industry typical) — fully transparent."""
        try:
            n = max(1, int(nights or 1))
            r = max(1, int(rooms or 1))
        except Exception:
            n = r = 1
        cfg = await db.esg_config.find_one({"property_id": property_id}, {"_id": 0}) or {}
        per_rn = float(cfg.get("offset_fee_per_rn", 1.50))
        co2_factor = float(cfg.get("co2_factor_grid", 0.207))
        kwh_per_rn = float(cfg.get("kwh_baseline_per_rn", 30))
        # Estimated stay CO2: kwh × factor × room-nights
        co2_kg = round(kwh_per_rn * co2_factor * n * r, 1)
        return {
            "property_id": property_id,
            "nights": n, "rooms": r,
            "fee_per_room_per_night": per_rn,
            "total_fee": round(per_rn * n * r, 2),
            "estimated_co2_kg": co2_kg,
            "currency": "GBP",
            "message": (
                f"Offset the {co2_kg} kg CO₂ from your stay for £{round(per_rn * n * r, 2)}. "
                "Funds support verified UK woodland creation projects."
            ),
        }

    # ============================================================
    # CARBON REPORTING v2 — Scope 1/2/3, YoY, PDF, offset tracking
    # (Iter 283 — Green Key / Green Globe certification-ready)
    # ============================================================
    @router.get("/esg/{property_id}/scope-breakdown")
    async def scope_breakdown(property_id: str, year: str = "",
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        """GHG Protocol Scope 1/2/3 breakdown for ESG reporting.

        Scope 1: Direct emissions (gas heating, on-site fuel) — from gas_kwh
        Scope 2: Indirect electricity emissions — from kwh × grid factor
        Scope 3: Other indirect — currently estimated from waste + employee commute proxy
        """
        if not year:
            year = datetime.now(timezone.utc).strftime("%Y")
        cfg = await db.esg_config.find_one({"property_id": property_id}, {"_id": 0}) or {}
        co2f_grid = float(cfg.get("co2_factor_grid", DEFAULT_CONFIG["co2_factor_grid"]))
        co2f_gas = 0.184  # UK gas factor kg CO2e / kWh
        readings = await db.esg_readings.find(
            {"property_id": property_id, "month": {"$regex": f"^{year}"}},
            {"_id": 0}
        ).to_list(24)
        scope1 = sum(r.get("gas_kwh", 0) * co2f_gas for r in readings)
        scope2 = sum(r.get("kwh", 0) * co2f_grid for r in readings)
        # Scope 3 proxy: waste (~0.45 kg CO2e/kg general waste landfill)
        scope3 = sum(r.get("waste_kg", 0) * 0.45 for r in readings)
        total = scope1 + scope2 + scope3
        return {
            "property_id": property_id, "year": year,
            "scope1_kg": round(scope1, 1),
            "scope2_kg": round(scope2, 1),
            "scope3_kg": round(scope3, 1),
            "total_kg": round(total, 1),
            "total_tonnes": round(total / 1000, 3),
            "scope1_pct": round(scope1 / max(1, total) * 100, 1),
            "scope2_pct": round(scope2 / max(1, total) * 100, 1),
            "scope3_pct": round(scope3 / max(1, total) * 100, 1),
            "factors_used": {"grid_electricity": co2f_grid,
                              "natural_gas": co2f_gas,
                              "waste_landfill": 0.45},
            "months_with_data": len(readings),
        }

    @router.get("/esg/{property_id}/yoy")
    async def year_over_year(property_id: str, year: str = "",
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        """Year-over-year comparison: current vs previous year, % change per metric."""
        if not year:
            year = datetime.now(timezone.utc).strftime("%Y")
        try:
            prev_year = str(int(year) - 1)
        except ValueError:
            raise HTTPException(400, "Invalid year")
        async def _aggregate(yr: str) -> dict:
            rows = await db.esg_readings.find(
                {"property_id": property_id, "month": {"$regex": f"^{yr}"}},
                {"_id": 0}
            ).to_list(24)
            return {
                "kwh": sum(r.get("kwh", 0) for r in rows),
                "gas_kwh": sum(r.get("gas_kwh", 0) for r in rows),
                "water_litres": sum(r.get("water_litres", 0) for r in rows),
                "waste_kg": sum(r.get("waste_kg", 0) for r in rows),
                "months": len(rows),
            }
        cur = await _aggregate(year)
        prev = await _aggregate(prev_year)
        def _pct(a: float, b: float) -> float:
            if not b:
                return 0.0
            return round((a - b) / b * 100, 1)
        return {
            "property_id": property_id, "year": year, "prev_year": prev_year,
            "current": cur, "previous": prev,
            "change_pct": {
                "kwh":          _pct(cur["kwh"], prev["kwh"]),
                "gas_kwh":      _pct(cur["gas_kwh"], prev["gas_kwh"]),
                "water_litres": _pct(cur["water_litres"], prev["water_litres"]),
                "waste_kg":     _pct(cur["waste_kg"], prev["waste_kg"]),
            },
        }

    @router.post("/esg/{property_id}/offset-purchases")
    async def add_offset_purchase(property_id: str, body: dict,
                                   current_user: dict = Depends(require_roles("admin", "manager"))):
        """Log a carbon offset purchase (per booking or bulk)."""
        doc = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "booking_id": body.get("booking_id"),
            "tonnes_co2e": float(body.get("tonnes_co2e") or 0),
            "amount_paid": float(body.get("amount_paid") or 0),
            "currency": body.get("currency", "GBP"),
            "provider": body.get("provider", "Verified UK Woodland"),
            "certificate_url": body.get("certificate_url"),
            "purchased_at": datetime.now(timezone.utc).isoformat(),
            "purchased_by": current_user.get("name", ""),
        }
        if doc["tonnes_co2e"] <= 0:
            raise HTTPException(400, "tonnes_co2e must be > 0")
        await db.esg_offset_purchases.insert_one(dict(doc))
        return doc

    @router.get("/esg/{property_id}/offset-purchases")
    async def list_offsets(property_id: str, year: str = "",
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        q: dict = {"property_id": property_id}
        if year:
            q["purchased_at"] = {"$regex": f"^{year}"}
        items = await db.esg_offset_purchases.find(q, {"_id": 0}) \
                                              .sort("purchased_at", -1).to_list(500)
        total_tonnes = sum(i.get("tonnes_co2e", 0) for i in items)
        total_spend = sum(i.get("amount_paid", 0) for i in items)
        return {"purchases": items, "count": len(items),
                "total_tonnes_offset": round(total_tonnes, 3),
                "total_spend": round(total_spend, 2)}

    @router.get("/esg/{property_id}/report.pdf")
    async def carbon_report_pdf(property_id: str, year: str = "",
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        """Green Key / Green Globe certification-ready annual carbon report PDF."""
        import io
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from fastapi.responses import StreamingResponse

        if not year:
            year = datetime.now(timezone.utc).strftime("%Y")
        prop = await db.properties.find_one({"id": property_id}, {"_id": 0}) or {}
        scope = await scope_breakdown(property_id, year=year, current_user=current_user)
        yoy = await year_over_year(property_id, year=year, current_user=current_user)
        offsets = await list_offsets(property_id, year=year, current_user=current_user)
        # Reconstruct headline metrics
        total_kg = scope["total_kg"]
        offset_kg = offsets["total_tonnes_offset"] * 1000
        net_kg = max(0, total_kg - offset_kg)
        offset_pct = round(min(100, offset_kg / max(1, total_kg) * 100), 1)

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4,
                                leftMargin=18 * mm, rightMargin=18 * mm,
                                topMargin=18 * mm, bottomMargin=18 * mm,
                                title=f"Carbon Report {year} — {prop.get('name', property_id)}")
        styles = getSampleStyleSheet()
        h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=16,
                            textColor=colors.HexColor("#064e3b"))
        h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=12,
                            textColor=colors.HexColor("#064e3b"),
                            spaceBefore=8, spaceAfter=4)
        small = ParagraphStyle("small", parent=styles["Normal"], fontSize=9,
                               textColor=colors.HexColor("#525252"))
        muted = ParagraphStyle("muted", parent=styles["Normal"], fontSize=8,
                               textColor=colors.HexColor("#737373"))
        story = [
            Paragraph(f"ANNUAL CARBON REPORT — {year}", h1),
            Paragraph(f"<b>{prop.get('name') or property_id}</b>", small),
            Paragraph(f"Prepared by: {current_user.get('name', '-')} · "
                       f"Issued: {datetime.now(timezone.utc).strftime('%d %b %Y')} UTC · "
                       f"GHG Protocol-aligned", small),
            Spacer(1, 6 * mm),
            Paragraph("HEADLINE METRICS", h2),
        ]
        headline = [
            ["Metric", "Value"],
            ["Total Gross Emissions", f"{total_kg:,.0f} kg CO₂e ({total_kg/1000:.2f} t)"],
            ["Voluntary Carbon Offsets Purchased", f"{offset_kg:,.0f} kg ({offsets['total_tonnes_offset']:.2f} t)"],
            ["Net Emissions After Offsets", f"{net_kg:,.0f} kg ({net_kg/1000:.2f} t)"],
            ["Offset Coverage", f"{offset_pct}%"],
            ["Offset Spend", f"£{offsets['total_spend']:,.2f}"],
        ]
        tbl = Table(headline, colWidths=[100 * mm, 60 * mm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#064e3b")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#a8a29e")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#f0fdf4")]),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 6 * mm))

        # Scope breakdown
        story.append(Paragraph("GHG PROTOCOL SCOPE BREAKDOWN", h2))
        scope_table = [
            ["Scope", "Description", "kg CO₂e", "%"],
            ["1", "Direct (gas heating, on-site fuel)",
             f"{scope['scope1_kg']:,.0f}", f"{scope['scope1_pct']}%"],
            ["2", "Indirect (purchased electricity)",
             f"{scope['scope2_kg']:,.0f}", f"{scope['scope2_pct']}%"],
            ["3", "Other indirect (waste, supply chain proxy)",
             f"{scope['scope3_kg']:,.0f}", f"{scope['scope3_pct']}%"],
            ["", "TOTAL", f"{scope['total_kg']:,.0f}", "100%"],
        ]
        stb = Table(scope_table, colWidths=[15*mm, 95*mm, 30*mm, 20*mm])
        stb.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#064e3b")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#dcfce7")),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#a8a29e")),
            ("ALIGN", (2, 0), (3, -1), "RIGHT"),
        ]))
        story.append(stb)
        story.append(Spacer(1, 6 * mm))

        # YoY
        story.append(Paragraph("YEAR-OVER-YEAR CHANGE", h2))
        yoy_table = [
            ["Metric", f"{yoy['prev_year']}", f"{yoy['year']}", "Δ %"],
            ["Electricity (kWh)",
             f"{yoy['previous']['kwh']:,.0f}",
             f"{yoy['current']['kwh']:,.0f}",
             f"{yoy['change_pct']['kwh']:+.1f}%"],
            ["Gas (kWh)",
             f"{yoy['previous']['gas_kwh']:,.0f}",
             f"{yoy['current']['gas_kwh']:,.0f}",
             f"{yoy['change_pct']['gas_kwh']:+.1f}%"],
            ["Water (litres)",
             f"{yoy['previous']['water_litres']:,.0f}",
             f"{yoy['current']['water_litres']:,.0f}",
             f"{yoy['change_pct']['water_litres']:+.1f}%"],
            ["Waste (kg)",
             f"{yoy['previous']['waste_kg']:,.0f}",
             f"{yoy['current']['waste_kg']:,.0f}",
             f"{yoy['change_pct']['waste_kg']:+.1f}%"],
        ]
        ytb = Table(yoy_table, colWidths=[50*mm, 35*mm, 35*mm, 30*mm])
        ytb.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#064e3b")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#a8a29e")),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ]))
        story.append(ytb)
        story.append(Spacer(1, 6 * mm))

        # Conversion factors disclosure
        story.append(Paragraph("EMISSION FACTORS USED", h2))
        story.append(Paragraph(
            f"• Grid electricity: <b>{scope['factors_used']['grid_electricity']:.3f} kg CO₂e / kWh</b> "
            f"(UK 2024 average)<br/>"
            f"• Natural gas: <b>{scope['factors_used']['natural_gas']:.3f} kg CO₂e / kWh</b><br/>"
            f"• Landfill waste: <b>{scope['factors_used']['waste_landfill']:.3f} kg CO₂e / kg</b><br/>"
            f"• Months of data included: <b>{scope['months_with_data']}</b>",
            small))
        story.append(Spacer(1, 8 * mm))
        story.append(Paragraph(
            "This report is prepared in alignment with the GHG Protocol Corporate Standard "
            "and the Green Key / Green Globe annual reporting criteria. "
            "Self-attested figures based on monthly utility readings entered into the platform. "
            "Voluntary offsets are tracked separately and do not reduce gross emissions.",
            muted))

        doc.build(story)
        buf.seek(0)
        filename = f"carbon_report_{property_id[:8]}_{year}.pdf"
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    return router
