"""
AI Summary Copilot — Cross-dashboard "Bunu açıkla" feature.

User selects any JSON payload (KPI block, chart data, anomaly, leaderboard etc.)
and clicks "AI Özet" → GPT-5.2 returns a 2-4 sentence Turkish insight + 3 actions.

Key design:
  - Universal endpoint: POST /copilot/summarize  body: {context_type, data, query?}
  - Caches responses by hash to avoid duplicate LLM spend
  - Returns both insight + suggested_actions[]

Why beat competitors:
  Mews/Cloudbeds don't have a unified AI copilot.
  Opera has Oracle AI but it's an expensive add-on.
  Us: cross-module, free with Emergent LLM key.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import hashlib
import json as _json
import os
import uuid as _uuid
import logging

logger = logging.getLogger(__name__)


class SummarizeReq(BaseModel):
    context_type: str                # "kpis" | "anomaly" | "timeseries" | "leaderboard" | "inquiry" | "forecast" | "custom"
    data: Any                        # structured JSON payload
    query: Optional[str] = None      # optional user question
    property_id: Optional[str] = None


CONTEXT_PROMPTS = {
    "kpis": "These are hotel KPI metrics. Summarize the health of the business in 2-3 Turkish sentences.",
    "anomaly": "This is an anomaly detection result. Explain in 2-3 Turkish sentences what happened and why it matters.",
    "timeseries": "This is a time series of a hotel metric. Describe the trend in 2-3 Turkish sentences.",
    "leaderboard": "This is a leaderboard of staff or items. Describe the top and bottom performers in Turkish.",
    "inquiry": "This is a MICE inquiry with a proposal. Summarize the opportunity + risks in 2-3 Turkish sentences.",
    "forecast": "This is a demand forecast. Highlight the best/worst months and suggest actions in Turkish.",
    "custom": "Summarize this hotel data payload in 2-3 Turkish sentences.",
}


def _hash_payload(context_type: str, data: Any, query: Optional[str]) -> str:
    raw = _json.dumps({"t": context_type, "d": data, "q": query or ""}, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _heuristic_summary(req: SummarizeReq) -> dict:
    """Fallback when LLM unavailable."""
    ctx = req.context_type
    if ctx == "anomaly":
        text = "İstatistiksel sapma tespit edildi. Ciddiyete göre hemen incelenmeli ve kök neden araştırılmalı."
        actions = ["Karşılaştırma grafiği aç", "İlgili günün segmentini incele", "Operasyonla paylaş"]
    elif ctx == "kpis":
        text = "KPI değerleri gösterildiği gibi. Benchmark ile karşılaştırarak güçlü ve zayıf yönleri tespit edin."
        actions = ["Geçen yıl ile karşılaştır", "Hedeflere karşı ölç", "Ekiple haftalık görüşme"]
    elif ctx == "leaderboard":
        text = "Liderlik tablosu en başarılı ve geride kalan kalemleri gösterir. En iyi uygulamaları paylaşın."
        actions = ["En iyi 3'ü ödüllendir", "Alttakilerle 1-1 görüşme", "Eğitim programı başlat"]
    elif ctx == "forecast":
        text = "Tahmin verisine göre en yüksek ve en düşük dönemleri belirleyin. Fiyat ve kapasite stratejinizi hazırlayın."
        actions = ["Peak dönem fiyat +%20", "Trough dönem kampanya", "Staff planlama"]
    else:
        text = "Veriniz analiz edildi. Detaylara inmek için anomali veya benchmark raporlarına bakın."
        actions = ["Veriyi segmente et", "Benchmark karşılaştır", "Detaylı rapor çek"]
    return {"insight": text, "suggested_actions": actions}


def create_copilot_router(db, require_roles, LlmChat=None, UserMessage=None):
    router = APIRouter()

    @router.post("/copilot/summarize")
    async def summarize(req: SummarizeReq,
                        current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        if req.context_type not in CONTEXT_PROMPTS:
            raise HTTPException(400, f"context_type must be one of {list(CONTEXT_PROMPTS.keys())}")

        # Cache lookup
        key = _hash_payload(req.context_type, req.data, req.query)
        cached = await db.copilot_cache.find_one({"key": key}, {"_id": 0})
        if cached and cached.get("insight"):
            return {**cached, "cached": True}

        # LLM call
        llm_key = os.environ.get("EMERGENT_LLM_KEY", "")
        result = None
        if llm_key and LlmChat and UserMessage:
            try:
                # Serialize data compactly (truncate large arrays)
                try:
                    data_str = _json.dumps(req.data, default=str)[:3500]
                except Exception:
                    data_str = str(req.data)[:3500]

                system = (
                    "You are a seasoned hotel revenue and operations analyst. "
                    "Respond in Turkish. Be concise (2-3 sentences) and specific. "
                    "After the insight, provide exactly 3 short action items. "
                    "Return JSON: {\"insight\": \"...\", \"suggested_actions\": [\"a1\",\"a2\",\"a3\"]}"
                )
                prompt = (
                    f"{CONTEXT_PROMPTS[req.context_type]}\n"
                    f"Data: {data_str}\n"
                    + (f"\nUser question: {req.query}\n" if req.query else "")
                    + "\nRespond with valid JSON only."
                )
                chat = LlmChat(
                    api_key=llm_key,
                    session_id=f"copilot-{_uuid.uuid4()}",
                    system_message=system,
                ).with_model("openai", "gpt-5.2")
                resp = await chat.send_message(UserMessage(text=prompt))
                text = str(resp).strip() if resp else ""
                # Strip ```json fences if present
                if text.startswith("```"):
                    text = text.strip("`").split("\n", 1)[-1]
                    if text.endswith("```"):
                        text = text[:-3]
                try:
                    parsed = _json.loads(text)
                    if isinstance(parsed, dict) and "insight" in parsed:
                        actions = parsed.get("suggested_actions") or []
                        if not isinstance(actions, list):
                            actions = [str(actions)]
                        result = {
                            "insight": str(parsed["insight"])[:1000],
                            "suggested_actions": [str(a)[:120] for a in actions[:5]],
                            "source": "llm",
                        }
                except _json.JSONDecodeError:
                    # Use the raw text as insight, generate heuristic actions
                    result = {
                        "insight": text[:1000] or _heuristic_summary(req)["insight"],
                        "suggested_actions": _heuristic_summary(req)["suggested_actions"],
                        "source": "llm_raw",
                    }
            except Exception as e:
                logger.warning(f"Copilot LLM failed: {e}")
                result = None

        if result is None:
            h = _heuristic_summary(req)
            result = {**h, "source": "heuristic"}

        # Store in cache
        now = datetime.now(timezone.utc).isoformat()
        cache_doc = {
            "key": key,
            "context_type": req.context_type,
            "insight": result["insight"],
            "suggested_actions": result["suggested_actions"],
            "source": result["source"],
            "created_at": now,
            "created_by": current_user.get("email"),
        }
        await db.copilot_cache.update_one({"key": key}, {"$set": cache_doc}, upsert=True)

        return {**result, "cached": False, "key": key}

    @router.get("/copilot/recent")
    async def recent(limit: int = 20,
                     current_user: dict = Depends(require_roles("admin", "manager"))):
        """Show recently-cached copilot responses across the property (learnings)."""
        if limit < 1 or limit > 100:
            raise HTTPException(400, "limit must be 1..100")
        rows = await db.copilot_cache.find({}, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
        return {"rows": rows, "count": len(rows)}

    return router
