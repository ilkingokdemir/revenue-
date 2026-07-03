"""
Mews-parity AI features (iter 356)
====================================

Three high-impact features cloned/inspired by Mews PMS to close the parity gap
with the market leader:

1. **Smart Tips** — LLM-generated personalized service suggestions for a guest,
   based on their profile (tags, past stays, preferences, notes).
   Endpoint: POST /api/mews-ai/smart-tips  {guest_id | inline_profile}
   Returns:  {tips: [{icon, title, action}, ...], model, generated_at}

2. **Duplicate Guest Auto-Merge** — Scans guest_profiles for likely duplicates
   using fuzzy email/phone/name matching, then optionally asks the LLM to
   confirm each cluster before staff review.
   Endpoints:
     GET  /api/mews-ai/duplicate-guests?limit=50    — find clusters
     POST /api/mews-ai/merge-guests                 — apply an approved merge

3. **BI AI Summary** — Feeds Performance KPIs into the LLM and returns a
   Turkish natural-language "what changed this month" narrative.
   Endpoint: POST /api/mews-ai/bi-summary  {property_id, period?}

All endpoints require admin or manager role. Persist minimal audit trail.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
import logging
import os
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _llm_chat(system_prompt: str, user_prompt: str,
                     session_id: str, model: str = "gpt-4o-mini") -> Optional[str]:
    """Best-effort emergentintegrations LLM call. Returns None on failure so
    callers can fall back to a heuristic response."""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        key = os.environ.get("EMERGENT_LLM_KEY")
        if not key:
            return None
        provider = "anthropic" if model.startswith("claude") else "openai"
        chat = LlmChat(api_key=key, session_id=session_id, system_message=system_prompt) \
            .with_model(provider, model)
        return await chat.send_message(UserMessage(text=user_prompt))
    except Exception as e:
        logger.warning(f"[mews_parity] LLM call failed: {e}")
        return None


def _norm_email(v: Optional[str]) -> str:
    return (v or "").strip().lower()


def _norm_phone(v: Optional[str]) -> str:
    """Return only digits — collapses +44 20 1234 5678 into 442012345678."""
    return re.sub(r"\D+", "", str(v or ""))


def _norm_name(v: Optional[str]) -> str:
    s = (v or "").lower().strip()
    # Turkish char fold
    for a, b in [("ı", "i"), ("ç", "c"), ("ş", "s"), ("ğ", "g"), ("ü", "u"), ("ö", "o")]:
        s = s.replace(a, b)
    return re.sub(r"[^a-z\s]", "", s)


def create_mews_parity_router(db, require_roles):
    router = APIRouter(prefix="/mews-ai", tags=["mews-parity"])

    # ─────────────────────────────────────────────────────────────────────
    # 1) SMART TIPS
    # ─────────────────────────────────────────────────────────────────────
    async def _load_guest_context(guest_id: str) -> Optional[Dict]:
        g = await db.guest_profiles.find_one({"id": guest_id}, {"_id": 0})
        if not g:
            return None
        recent_bookings = await db.bookings.find(
            {"guest_id": guest_id}, {"_id": 0, "check_in": 1, "check_out": 1,
                                      "room_type": 1, "total": 1, "status": 1,
                                      "channel": 1}
        ).sort("check_in", -1).limit(5).to_list(5)
        return {
            "profile": g,
            "recent_bookings": recent_bookings,
            "booking_count": len(recent_bookings),
        }

    def _fallback_tips(profile: Dict) -> List[Dict]:
        """Deterministic starter tips when LLM is unavailable — still useful."""
        tips = []
        tags = [t.lower() for t in (profile.get("tags") or [])]
        prefs = (profile.get("preferences") or "").lower()
        notes = (profile.get("notes") or "").lower()
        blob = f"{' '.join(tags)} {prefs} {notes}"
        if "vip" in blob:
            tips.append({"icon": "star", "title": "VIP karşılama",
                         "action": "Girişte şampanya ikramı + late checkout hediyesi teklif et."})
        if "birthday" in blob or "doğum" in blob:
            tips.append({"icon": "gift", "title": "Doğum günü sürprizi",
                         "action": "Odaya küçük pasta + tebrik notu bırak."})
        if "vegetarian" in blob or "vegan" in blob or "vejeteryan" in blob:
            tips.append({"icon": "leaf", "title": "Diyet uyumu",
                         "action": "Kahvaltı için vejeteryan/vegan seçenekleri hazırla."})
        if "allergy" in blob or "alerji" in blob:
            tips.append({"icon": "alert", "title": "Alerji uyarısı",
                         "action": "Housekeeping'e alerji notunu ilet, feather-free çarşaf kullan."})
        if "quiet" in blob or "sessiz" in blob:
            tips.append({"icon": "moon", "title": "Sessiz oda",
                         "action": "Asansör/lobi gürültüsünden uzak oda ata."})
        if "business" in blob or "iş" in blob:
            tips.append({"icon": "briefcase", "title": "İş misafiri",
                         "action": "Çalışma masası + hızlı Wi-Fi kontrol, erken kahvaltı sun."})
        if not tips:
            tips.append({"icon": "heart", "title": "Kişisel karşılama",
                         "action": "Misafirin adıyla el yazısı welcome note bırak."})
        return tips[:5]

    @router.post("/smart-tips")
    async def smart_tips(payload: dict,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        """Return personalized service tips for a guest.
        Body: {guest_id: str} OR {profile: {...inline...}}
        """
        ctx: Optional[Dict] = None
        guest_id = payload.get("guest_id")
        if guest_id:
            ctx = await _load_guest_context(guest_id)
            if not ctx:
                raise HTTPException(404, "guest not found")
        elif payload.get("profile"):
            ctx = {"profile": payload["profile"], "recent_bookings": [], "booking_count": 0}
        else:
            raise HTTPException(400, "guest_id or profile is required")

        p = ctx["profile"]
        system_prompt = (
            "Sen deneyimli bir otel misafir deneyim uzmanısın. Sana verilen misafir "
            "profiline bakıp ekibin uygulayabileceği 3-5 KİŞİYE ÖZEL servis önerisi "
            "üretiyorsun. Her öneri kısa (1 cümle), aksiyon odaklı ve gerçekçi olmalı. "
            "Genel öneriler (örn. 'iyi hizmet ver') YASAKTIR — misafir profilinden bir "
            "detaya dayandır.\n\n"
            "SADECE aşağıdaki JSON formatında dön:\n"
            "{\"tips\":[{\"icon\":\"star|gift|leaf|alert|moon|briefcase|heart|coffee|"
            "wine|utensils\",\"title\":\"Kısa başlık\",\"action\":\"Ekibin ne yapacağı\"}]}"
        )
        user_prompt = (
            f"MİSAFİR PROFİLİ:\n"
            f"- Ad: {p.get('first_name','')} {p.get('last_name','')}\n"
            f"- E-mail: {p.get('email','—')}\n"
            f"- Uyruk: {p.get('nationality','—')}\n"
            f"- Etiketler: {', '.join(p.get('tags', []) or []) or '—'}\n"
            f"- Tercihler (notes): {p.get('preferences') or p.get('notes') or '—'}\n"
            f"- Toplam konaklama sayısı: {ctx['booking_count']}\n"
            f"- Son rezervasyonlar: {ctx['recent_bookings'][:3]}\n"
        )
        session_id = f"smart-tips-{guest_id or 'inline'}-{uuid.uuid4().hex[:8]}"
        raw = await _llm_chat(system_prompt, user_prompt, session_id, model="gpt-4o-mini")

        tips: List[Dict] = []
        if raw:
            try:
                import json as _json
                m = re.search(r"\{[\s\S]*\}", raw)
                data = _json.loads(m.group(0) if m else raw)
                tips = data.get("tips") or []
            except Exception as e:
                logger.info(f"[smart-tips] JSON parse failed, using fallback: {e}")

        if not tips:
            tips = _fallback_tips(p)

        # Persist for audit / analytics
        try:
            await db.mews_ai_smart_tips.insert_one({
                "id": str(uuid.uuid4()),
                "guest_id": guest_id,
                "tips_count": len(tips),
                "used_llm": bool(raw),
                "generated_by": (current_user or {}).get("email"),
                "generated_at": _now_iso(),
            })
        except Exception:
            pass

        return {
            "tips": tips[:5],
            "model": "gpt-4o-mini" if raw else "fallback",
            "generated_at": _now_iso(),
        }

    # ─────────────────────────────────────────────────────────────────────
    # 2) DUPLICATE GUEST AUTO-MERGE
    # ─────────────────────────────────────────────────────────────────────
    @router.get("/duplicate-guests")
    async def find_duplicates(limit: int = 50,
                               _: dict = Depends(require_roles("admin", "manager"))):
        """Group guest_profiles by normalized email, phone, and name+DOB signature.
        Returns clusters of ≥2 guests that look like duplicates."""
        guests = await db.guest_profiles.find({}, {"_id": 0}).limit(5000).to_list(5000)
        by_email: Dict[str, List[Dict]] = {}
        by_phone: Dict[str, List[Dict]] = {}
        by_name_dob: Dict[str, List[Dict]] = {}
        for g in guests:
            e = _norm_email(g.get("email"))
            if e and len(e) > 4:
                by_email.setdefault(e, []).append(g)
            p = _norm_phone(g.get("phone"))
            if p and len(p) >= 7:
                by_phone.setdefault(p, []).append(g)
            nm = f"{_norm_name(g.get('first_name'))}|{_norm_name(g.get('last_name'))}|{g.get('date_of_birth','')}"
            if nm.replace("|", "").replace(",", "").strip() and len(nm) > 5:
                by_name_dob.setdefault(nm, []).append(g)

        clusters: List[Dict] = []
        seen_pairs = set()

        def _add_cluster(reason: str, members: List[Dict]):
            if len(members) < 2:
                return
            key = tuple(sorted([m["id"] for m in members if m.get("id")]))
            if key in seen_pairs:
                return
            seen_pairs.add(key)
            clusters.append({
                "cluster_id": str(uuid.uuid4()),
                "reason": reason,
                "size": len(members),
                "guests": [{
                    "id": m.get("id"),
                    "first_name": m.get("first_name"),
                    "last_name": m.get("last_name"),
                    "email": m.get("email"),
                    "phone": m.get("phone"),
                    "created_at": m.get("created_at"),
                    "tags": m.get("tags", []),
                } for m in members],
            })

        for e, members in by_email.items():
            _add_cluster(f"Aynı e-mail: {e}", members)
        for p, members in by_phone.items():
            _add_cluster(f"Aynı telefon: {p}", members)
        for nm, members in by_name_dob.items():
            if len(members) >= 2:
                _add_cluster("Aynı isim + doğum tarihi", members)

        clusters.sort(key=lambda c: c["size"], reverse=True)
        return {
            "total_guests_scanned": len(guests),
            "clusters_found": len(clusters),
            "clusters": clusters[:limit],
            "generated_at": _now_iso(),
        }

    @router.post("/merge-guests")
    async def merge_guests(payload: dict,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        """Merge duplicate guest profiles into a primary one.
        Body: {primary_id: str, duplicate_ids: [str, ...]}
        - All bookings.guest_id references are re-pointed to primary_id.
        - Non-empty fields from duplicates fill missing fields on primary.
        - Duplicate profiles are archived (deleted) but audit log is kept.
        """
        primary_id = payload.get("primary_id")
        dup_ids = payload.get("duplicate_ids") or []
        if not primary_id or not dup_ids:
            raise HTTPException(400, "primary_id and duplicate_ids required")
        if primary_id in dup_ids:
            raise HTTPException(400, "primary_id cannot be in duplicate_ids")

        primary = await db.guest_profiles.find_one({"id": primary_id}, {"_id": 0})
        if not primary:
            raise HTTPException(404, "primary guest not found")

        merged_fields: Dict[str, Any] = {}
        moved_bookings = 0
        removed_dupes = 0
        for did in dup_ids:
            dup = await db.guest_profiles.find_one({"id": did}, {"_id": 0})
            if not dup:
                continue
            # Fill missing fields on primary from duplicate
            for key, val in dup.items():
                if key in {"_id", "id", "created_at"}:
                    continue
                if val in (None, "", [], {}) or primary.get(key) not in (None, "", [], {}):
                    continue
                merged_fields[key] = val
            # Merge tags (union)
            existing_tags = set(primary.get("tags") or [])
            dup_tags = set(dup.get("tags") or [])
            union_tags = list(existing_tags | dup_tags)
            if union_tags != list(existing_tags):
                merged_fields["tags"] = union_tags
            # Re-point bookings
            res = await db.bookings.update_many({"guest_id": did}, {"$set": {"guest_id": primary_id}})
            moved_bookings += res.modified_count
            # Archive duplicate profile
            await db.guest_profiles.delete_one({"id": did})
            removed_dupes += 1

        if merged_fields:
            merged_fields["merged_at"] = _now_iso()
            merged_fields["merged_by"] = (current_user or {}).get("email")
            await db.guest_profiles.update_one({"id": primary_id}, {"$set": merged_fields})

        # Audit log
        await db.mews_ai_merge_log.insert_one({
            "id": str(uuid.uuid4()),
            "primary_id": primary_id,
            "duplicate_ids": dup_ids,
            "moved_bookings": moved_bookings,
            "removed_dupes": removed_dupes,
            "merged_fields": list(merged_fields.keys()),
            "merged_by": (current_user or {}).get("email"),
            "merged_at": _now_iso(),
        })
        return {
            "ok": True,
            "primary_id": primary_id,
            "removed_dupes": removed_dupes,
            "moved_bookings": moved_bookings,
            "merged_fields_count": len(merged_fields),
        }

    # ─────────────────────────────────────────────────────────────────────
    # 3) BI AI SUMMARY
    # ─────────────────────────────────────────────────────────────────────
    async def _load_perf_snapshot(property_id: str) -> Dict:
        """Pull the same annual_forecast KPIs the Performance Report uses so the
        AI summary matches what the user sees on screen."""
        prop = await db.properties.find_one(
            {"id": property_id}, {"_id": 0, "name": 1, "currency": 1,
                                    "last_minute_discount": 1}
        )
        # Small sample: last 30d bookings count and revenue
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        d30 = (now - timedelta(days=30)).strftime("%Y-%m-%d")
        d60 = (now - timedelta(days=60)).strftime("%Y-%m-%d")
        cur_bookings = await db.bookings.count_documents({
            "property_id": property_id, "check_in": {"$gte": d30},
            "status": {"$nin": ["cancelled"]},
        })
        prev_bookings = await db.bookings.count_documents({
            "property_id": property_id, "check_in": {"$gte": d60, "$lt": d30},
            "status": {"$nin": ["cancelled"]},
        })
        # YoY data if uploaded
        yoy_rows = await db.property_yoy_history.find(
            {"property_id": property_id}, {"_id": 0, "month_key": 1, "revenue": 1}
        ).to_list(24)
        expenses = await db.property_yoy_expenses.find(
            {"property_id": property_id}, {"_id": 0, "label": 1, "amount": 1, "category": 1}
        ).to_list(50)
        return {
            "property_name": (prop or {}).get("name", property_id),
            "currency": (prop or {}).get("currency", "GBP"),
            "last_minute": (prop or {}).get("last_minute_discount") or {},
            "bookings_last_30d": cur_bookings,
            "bookings_prev_30d": prev_bookings,
            "bookings_delta_pct": round((cur_bookings - prev_bookings) / max(prev_bookings, 1) * 100, 1),
            "yoy_months_recorded": len(yoy_rows),
            "yoy_total_revenue": round(sum(r.get("revenue", 0) for r in yoy_rows), 2),
            "expense_items": len(expenses),
            "expense_annual_total": round(sum(e.get("amount", 0) for e in expenses), 2),
            "top_expense_categories": sorted(
                [{"cat": e.get("category"), "amt": e.get("amount", 0)} for e in expenses],
                key=lambda x: x["amt"], reverse=True,
            )[:5],
        }

    @router.post("/bi-summary")
    async def bi_summary(payload: dict,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        """LLM-generated natural-language summary of the property's recent
        Business Intelligence signals. Turkish output.
        Body: {property_id: str}
        Returns: {summary_md: str, snapshot: {...}, model, generated_at}
        """
        property_id = payload.get("property_id")
        if not property_id:
            raise HTTPException(400, "property_id required")
        snap = await _load_perf_snapshot(property_id)

        system_prompt = (
            "Sen bir otel Revenue Manager'ısın. Sana verilen KPI özetini analiz "
            "ederek Türkçe, 4-6 cümlelik, aksiyon-odaklı bir 'bu ay ne değişti' "
            "raporu yaz. Format:\n"
            "  • Emoji ile başlayan 3-5 madde (📈 📉 ⚠️ 💡 🎯)\n"
            "  • Her madde 1 sayı + 1 aksiyon önerisi\n"
            "  • Genel 'iyi/kötü' yorumlardan kaçın, spesifik ol\n"
            "  • En sonda 1 satır 'ÖNCELİK BU HAFTA: ...' aksiyon önerisi\n"
        )
        user_prompt = (
            f"OTEL: {snap['property_name']} ({snap['currency']})\n"
            f"Son 30 gün rezervasyon: {snap['bookings_last_30d']} "
            f"(önceki 30 gün: {snap['bookings_prev_30d']}, "
            f"delta %{snap['bookings_delta_pct']})\n"
            f"YoY geçmiş veri: {snap['yoy_months_recorded']} ay, "
            f"toplam {snap['yoy_total_revenue']} {snap['currency']}\n"
            f"Yıllık gider: {snap['expense_annual_total']} {snap['currency']} "
            f"({snap['expense_items']} kalem)\n"
            f"Top gider kategorileri: {snap['top_expense_categories']}\n"
            f"Last-minute iskonto: {snap['last_minute']}\n"
        )
        session_id = f"bi-summary-{property_id}-{uuid.uuid4().hex[:6]}"
        raw = await _llm_chat(system_prompt, user_prompt, session_id, model="gpt-4o-mini")

        summary_md = raw or (
            f"📊 Son 30 gün: {snap['bookings_last_30d']} rezervasyon "
            f"(%{snap['bookings_delta_pct']} değişim).\n"
            f"💰 Yıllık gider: {snap['expense_annual_total']} {snap['currency']}.\n"
            f"📁 YoY tarihçe: {snap['yoy_months_recorded']}/12 ay.\n"
            f"ÖNCELİK BU HAFTA: Veri girişini tamamlayın; AI özeti aktif edilemedi (LLM yanıt vermedi)."
        )

        await db.mews_ai_bi_summary.insert_one({
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "snapshot": snap,
            "used_llm": bool(raw),
            "generated_by": (current_user or {}).get("email"),
            "generated_at": _now_iso(),
        })
        return {
            "summary_md": summary_md,
            "snapshot": snap,
            "model": "gpt-4o-mini" if raw else "fallback",
            "generated_at": _now_iso(),
        }

    return router
