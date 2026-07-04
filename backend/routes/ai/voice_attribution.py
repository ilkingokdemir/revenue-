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
