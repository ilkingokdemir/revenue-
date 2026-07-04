"""
Housekeeping voice damage report + booking attribution tracker
(iter 361 — Mews-parity Batch 3 F4 & voice improvement).

Two features share this module because both feed the operator's
BI dashboard, but they are otherwise independent.

Endpoints:
  POST /api/hk/voice-report                     — audio → transcription → maintenance ticket
  POST /api/attribution/track                   — record UTM/referral on booking creation
  GET  /api/attribution/{property_id}           — attribution dashboard payload
  GET  /api/attribution/{property_id}/export.csv — CSV for Google Ads offline conversions
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Optional
import csv
import io
import logging
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import PlainTextResponse

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _transcribe_audio(audio_bytes: bytes, filename: str,
                              language: str = "tr") -> Optional[str]:
    """Best-effort Whisper transcription. Returns None on failure so the
    caller can degrade gracefully to a stub text."""
    try:
        from emergentintegrations.llm.openai import OpenAISpeechToText
        key = os.environ.get("EMERGENT_LLM_KEY")
        if not key:
            return None
        stt = OpenAISpeechToText(api_key=key)
        bio = io.BytesIO(audio_bytes)
        bio.name = filename or "audio.webm"
        response = await stt.transcribe(
            file=bio,
            model="whisper-1",
            response_format="json",
            language=language,
            prompt="Otel hasar/temizlik raporu — oda numarası, kırık ekipman, "
                    "temizlik notu içerebilir.",
        )
        return response.text
    except Exception as e:
        logger.warning(f"[voice-report] transcription failed: {e}")
        return None


def create_voice_and_attribution_router(db, require_roles):
    router = APIRouter(tags=["voice-attribution"])

    # ─── Housekeeping Voice Damage Report ───────────────────────────────
    @router.post("/hk/voice-report")
    async def voice_damage_report(
        audio: UploadFile = File(...),
        property_id: str = Form(...),
        room_number: str = Form(""),
        language: str = Form("tr"),
        current_user: dict = Depends(require_roles("admin", "manager", "housekeeper", "receptionist", "maintenance")),
    ):
        """Accept a short audio recording from a housekeeper's phone, transcribe
        it via Whisper, and create a maintenance ticket automatically.

        Returns the ticket + the transcription so the app can echo it back.
        """
        content = await audio.read()
        if len(content) > 25 * 1024 * 1024:
            raise HTTPException(413, "Audio dosyası 25MB üzerinde olamaz")
        transcript = await _transcribe_audio(content, audio.filename or "voice.webm", language=language)
        used_llm = bool(transcript)
        transcript = transcript or "(Ses kaydı transcribe edilemedi — manuel giriş gerekiyor)"

        ticket = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "room_number": room_number or None,
            "kind": "maintenance",
            "status": "open",
            "priority": "medium",
            "source": "voice",
            "transcript": transcript,
            "created_by": (current_user or {}).get("email"),
            "created_by_name": (current_user or {}).get("name") or (current_user or {}).get("email"),
            "created_at": _now(),
            "audio_length_bytes": len(content),
        }
        await db.maintenance_tickets.insert_one(dict(ticket))
        ticket.pop("_id", None)
        return {
            "ok": True,
            "used_llm": used_llm,
            "transcript": transcript,
            "ticket": ticket,
        }

    @router.get("/hk/voice-reports/{property_id}")
    async def list_voice_reports(property_id: str, limit: int = 20,
                                   _: dict = Depends(require_roles("admin", "manager", "housekeeper"))):
        rows = await db.maintenance_tickets.find(
            {"property_id": property_id, "source": "voice"}, {"_id": 0}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        return {"total": len(rows), "items": rows}

    # ─── Booking Attribution Tracker ────────────────────────────────────
    @router.post("/attribution/track")
    async def track_attribution(body: dict,
                                  _: dict = Depends(require_roles("admin", "manager"))):
        """Persist UTM / referrer / gclid metadata against a booking so we can
        report conversion sources later (Google Ads offline conversions,
        marketing ROI dashboard etc.)."""
        booking_id = body.get("booking_id")
        property_id = body.get("property_id")
        if not booking_id or not property_id:
            raise HTTPException(400, "booking_id and property_id required")

        doc = {
            "id": str(uuid.uuid4()),
            "booking_id": booking_id,
            "property_id": property_id,
            "utm_source":   body.get("utm_source") or "",
            "utm_medium":   body.get("utm_medium") or "",
            "utm_campaign": body.get("utm_campaign") or "",
            "utm_term":     body.get("utm_term") or "",
            "utm_content":  body.get("utm_content") or "",
            "referrer":     body.get("referrer") or "",
            "gclid":        body.get("gclid") or "",
            "fbclid":       body.get("fbclid") or "",
            "landing_page": body.get("landing_page") or "",
            "value":        float(body.get("value") or 0),
            "currency":     body.get("currency", "GBP"),
            "created_at":   _now(),
        }
        # Upsert on booking_id so we don't duplicate on retries
        await db.booking_attribution.update_one(
            {"booking_id": booking_id},
            {"$set": doc},
            upsert=True,
        )
        return {"ok": True, "booking_id": booking_id}

    @router.get("/attribution/{property_id}")
    async def attribution_dashboard(property_id: str, days: int = 30,
                                     _: dict = Depends(require_roles("admin", "manager"))):
        """Aggregate the last `days` window into source/campaign leaderboards."""
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = await db.booking_attribution.find(
            {"property_id": property_id, "created_at": {"$gte": since}}, {"_id": 0}
        ).to_list(5000)

        by_source: dict[str, dict] = {}
        by_campaign: dict[str, dict] = {}
        google_ads_convs = 0
        google_ads_value = 0.0
        total_value = 0.0

        for r in rows:
            src = (r.get("utm_source") or "direct").lower()
            camp = r.get("utm_campaign") or "(no campaign)"
            v = float(r.get("value") or 0)
            total_value += v
            s = by_source.setdefault(src, {"source": src, "count": 0, "value": 0, "share_pct": 0})
            s["count"] += 1
            s["value"] += v
            c = by_campaign.setdefault(camp, {"campaign": camp, "source": src, "count": 0, "value": 0})
            c["count"] += 1
            c["value"] += v
            if r.get("gclid"):
                google_ads_convs += 1
                google_ads_value += v

        # Compute % share
        for s in by_source.values():
            s["share_pct"] = round(s["value"] / total_value * 100, 1) if total_value else 0
            s["value"] = round(s["value"], 2)
        for c in by_campaign.values():
            c["value"] = round(c["value"], 2)

        return {
            "window_days": days,
            "total_bookings_tracked": len(rows),
            "total_value": round(total_value, 2),
            "google_ads_conversions": google_ads_convs,
            "google_ads_value": round(google_ads_value, 2),
            "by_source":   sorted(by_source.values(),   key=lambda x: -x["value"]),
            "by_campaign": sorted(by_campaign.values(), key=lambda x: -x["value"])[:20],
            "generated_at": _now(),
        }

    # ─── ROAS Calculator ────────────────────────────────────────────────
    @router.get("/attribution/roas/template.csv", response_class=PlainTextResponse)
    async def roas_template_csv():
        """Downloadable CSV template so operators can paste Google Ads
        campaign cost data in the expected column order."""
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(["Campaign", "Cost", "Currency", "Clicks", "Impressions"])
        w.writerow(["london-hotels-summer", "180.55", "GBP", "412", "18450"])
        w.writerow(["brand-camden", "45.20", "GBP", "88", "3120"])
        w.writerow(["retargeting-may", "62.00", "GBP", "154", "9800"])
        return out.getvalue()

    @router.post("/attribution/{property_id}/roas/cost")
    async def upload_roas_cost(
        property_id: str,
        file: UploadFile = File(...),
        _: dict = Depends(require_roles("admin", "manager")),
    ):
        """Ingest a Google Ads CSV export (Campaign, Cost, Currency, Clicks,
        Impressions). Upserts per (property_id, campaign) so re-uploading the
        same file just refreshes totals — no duplicates."""
        raw = await file.read()
        if len(raw) > 5 * 1024 * 1024:
            raise HTTPException(413, "CSV 5MB üzerinde olamaz")
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("latin-1", errors="ignore")

        reader = csv.DictReader(io.StringIO(text))
        # Normalize header names (Google Ads uses "Campaign", "Cost", etc.)
        def _norm(h: str) -> str:
            return (h or "").strip().lower().replace(" ", "_")
        # DictReader keys already come from the header row; rebuild with normalized keys
        rows = []
        for r in reader:
            rows.append({_norm(k): (v or "").strip() for k, v in r.items()})

        if not rows:
            raise HTTPException(400, "CSV boş veya okunamıyor")

        inserted = 0
        skipped = 0
        errors = []
        for i, r in enumerate(rows, start=2):  # start=2 because row 1 is header
            camp = r.get("campaign") or r.get("campaign_name") or ""
            if not camp:
                skipped += 1
                continue
            try:
                cost = float((r.get("cost") or "0").replace(",", "").replace("£", "").replace("$", ""))
            except ValueError:
                errors.append(f"Satır {i}: geçersiz cost")
                continue
            doc = {
                "property_id":   property_id,
                "campaign":      camp,
                "cost":          cost,
                "currency":      (r.get("currency") or "GBP").upper(),
                "clicks":        int(float(r.get("clicks") or 0)) if r.get("clicks") else 0,
                "impressions":   int(float(r.get("impressions") or 0)) if r.get("impressions") else 0,
                "uploaded_at":   _now(),
            }
            await db.campaign_costs.update_one(
                {"property_id": property_id, "campaign": camp},
                {"$set": doc},
                upsert=True,
            )
            inserted += 1

        return {
            "ok": True,
            "inserted_or_updated": inserted,
            "skipped": skipped,
            "errors": errors[:10],
            "total_rows": len(rows),
        }

    @router.get("/attribution/{property_id}/roas")
    async def compute_roas(
        property_id: str,
        days: int = 30,
        margin_pct: float = 60.0,
        _: dict = Depends(require_roles("admin", "manager")),
    ):
        """Compute Return on Ad Spend per campaign.

        Revenue = sum(booking_attribution.value) grouped by utm_campaign in
        the last `days` days.
        Cost    = latest `campaign_costs` uploaded per campaign for this property.
        ROAS    = revenue / cost.
        Profit  = revenue * (margin_pct/100) - cost.
        Status  = green (>3x), yellow (1-3x), red (<1x), no_data (no cost).
        """
        if margin_pct < 0 or margin_pct > 100:
            raise HTTPException(400, "margin_pct 0-100 arasında olmalı")

        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        # Aggregate revenue + bookings per campaign
        att_rows = await db.booking_attribution.find(
            {"property_id": property_id, "created_at": {"$gte": since}}, {"_id": 0}
        ).to_list(5000)
        revenue_by_camp: dict[str, dict] = {}
        for r in att_rows:
            camp = r.get("utm_campaign") or "(no campaign)"
            v = float(r.get("value") or 0)
            b = revenue_by_camp.setdefault(camp, {"bookings": 0, "revenue": 0.0})
            b["bookings"] += 1
            b["revenue"] += v

        # Cost catalogue for this property
        costs = await db.campaign_costs.find(
            {"property_id": property_id}, {"_id": 0}
        ).to_list(2000)
        cost_by_camp = {c["campaign"]: c for c in costs}

        rows_out = []
        totals = {"cost": 0.0, "revenue": 0.0, "profit": 0.0, "bookings": 0}
        # Union of both sides — campaigns with cost OR bookings
        all_camps = set(revenue_by_camp) | set(cost_by_camp)
        for camp in all_camps:
            r = revenue_by_camp.get(camp, {"bookings": 0, "revenue": 0.0})
            c = cost_by_camp.get(camp)
            cost = float(c["cost"]) if c else 0.0
            revenue = r["revenue"]
            bookings = r["bookings"]
            profit = revenue * (margin_pct / 100.0) - cost
            if cost <= 0:
                roas = None
                status = "no_cost" if revenue > 0 else "no_data"
            else:
                roas = round(revenue / cost, 2)
                if roas >= 3:
                    status = "green"
                elif roas >= 1:
                    status = "yellow"
                else:
                    status = "red"
            rows_out.append({
                "campaign":   camp,
                "cost":       round(cost, 2),
                "revenue":    round(revenue, 2),
                "bookings":   bookings,
                "roas":       roas,
                "profit":     round(profit, 2),
                "clicks":     (c or {}).get("clicks", 0),
                "impressions":(c or {}).get("impressions", 0),
                "cpa":        round(cost / bookings, 2) if bookings and cost else None,
                "status":     status,
                "currency":   (c or {}).get("currency", "GBP"),
            })
            totals["cost"] += cost
            totals["revenue"] += revenue
            totals["profit"] += profit
            totals["bookings"] += bookings

        # Sort by revenue desc
        rows_out.sort(key=lambda x: x["revenue"], reverse=True)

        overall_roas = round(totals["revenue"] / totals["cost"], 2) if totals["cost"] > 0 else None
        return {
            "window_days": days,
            "margin_pct": margin_pct,
            "campaigns": rows_out,
            "totals": {
                "cost":     round(totals["cost"], 2),
                "revenue":  round(totals["revenue"], 2),
                "profit":   round(totals["profit"], 2),
                "bookings": totals["bookings"],
                "roas":     overall_roas,
            },
            "generated_at": _now(),
        }

    @router.delete("/attribution/{property_id}/roas/cost/{campaign}")
    async def delete_roas_cost(property_id: str, campaign: str,
                                 _: dict = Depends(require_roles("admin", "manager"))):
        """Remove a single campaign cost row (e.g. wrong upload)."""
        res = await db.campaign_costs.delete_one(
            {"property_id": property_id, "campaign": campaign}
        )
        return {"ok": True, "deleted": res.deleted_count}

    @router.get("/attribution/{property_id}/export.csv", response_class=PlainTextResponse)
    async def export_google_ads_csv(property_id: str, days: int = 90,
                                     _: dict = Depends(require_roles("admin", "manager"))):
        """CSV in Google Ads Offline Conversions format — operator uploads this
        into Google Ads to close the conversion loop (rows with gclid only)."""
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = await db.booking_attribution.find(
            {"property_id": property_id, "created_at": {"$gte": since}, "gclid": {"$ne": ""}},
            {"_id": 0},
        ).to_list(5000)
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(["Google Click ID", "Conversion Name", "Conversion Time", "Conversion Value", "Conversion Currency"])
        for r in rows:
            w.writerow([
                r["gclid"],
                "Hotel Booking",
                r["created_at"],
                round(float(r.get("value", 0)), 2),
                r.get("currency", "GBP"),
            ])
        return out.getvalue()

    return router
