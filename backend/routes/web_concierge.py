"""
AI 24/7 Web Concierge — Eviivo parity.

Public widget endpoint for hotel websites: drop-in chat widget that
answers guest inquiries from a per-property knowledge base + GPT.

No auth required for `/chat` (it's a public widget). Admin endpoints
require manager/admin to manage the knowledge base.

Endpoints
---------
Public:
  POST /api/web-concierge/chat
       Body: { property_id, session_id, message }
       Returns: { reply, suggested_actions, session_id }

  GET  /api/web-concierge/widget-config/{property_id}
       Public widget bootstrap (name, primary color, welcome message).

Admin:
  GET  /api/web-concierge/knowledge/{property_id}
  POST /api/web-concierge/knowledge/{property_id}
  PATCH /api/web-concierge/knowledge/{kb_id}
  DELETE /api/web-concierge/knowledge/{kb_id}
  GET  /api/web-concierge/sessions/{property_id}?limit=50
  GET  /api/web-concierge/session/{session_id}
  POST /api/web-concierge/config/{property_id}  — set widget appearance + welcome
"""
from datetime import datetime, timezone
import os
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_web_concierge_router(db, require_roles):
    router = APIRouter()

    DEFAULT_WELCOME = ("Merhaba! Otelimiz hakkında ne sormak istersiniz? "
                       "Oda fiyatları, doluluk, lokasyon, evcil hayvan politikası "
                       "veya rezervasyon koşulları — istediğiniz konuda yardımcı olayım.")

    DEFAULT_KB = [
        {"category": "check_in", "question": "Giriş ve çıkış saatleri",
         "answer": "Giriş saati 15:00, çıkış saati 11:00'dir. Erken giriş ve geç çıkış müsaitlik durumuna göre ücretsiz veya ek ücretli olarak ayarlanabilir."},
        {"category": "pets", "question": "Evcil hayvan kabul ediyor musunuz?",
         "answer": "Küçük evcil hayvanlar (10kg altı) ek 200 TL/gece ücret karşılığında kabul edilmektedir. Rezervasyon sırasında lütfen belirtin."},
        {"category": "breakfast", "question": "Kahvaltı dahil mi?",
         "answer": "Açık büfe kahvaltımız 07:00-10:30 saatleri arasında servis edilir. Çoğu oda tipinde dahildir, rezervasyon koşullarına bakınız."},
        {"category": "parking", "question": "Otopark var mı?",
         "answer": "Ücretsiz kapalı otoparkımız mevcuttur. Vale hizmeti ek ücretlidir."},
        {"category": "amenities", "question": "Otelinizde neler var?",
         "answer": "Fitness merkezi, spa, açık ve kapalı yüzme havuzu, restoran, bar, toplantı salonları ve 24 saat resepsiyon hizmeti sunmaktayız."},
    ]

    async def _get_or_create_config(property_id: str) -> dict:
        cfg = await db.web_concierge_config.find_one({"property_id": property_id}, {"_id": 0})
        if cfg:
            return cfg
        # Look up property name
        prop = await db.properties.find_one({"id": property_id}, {"_id": 0, "name": 1})
        cfg = {
            "property_id": property_id,
            "property_name": (prop or {}).get("name", "Otelimiz"),
            "primary_color": "#0c0a09",
            "welcome_message": DEFAULT_WELCOME,
            "agent_name": "Concierge AI",
            "auto_seed_done": False,
            "is_active": True,
            "created_at": _now_iso(),
        }
        await db.web_concierge_config.insert_one(cfg)
        cfg.pop("_id", None)
        return cfg

    async def _seed_default_kb(property_id: str):
        existing = await db.web_concierge_kb.count_documents({"property_id": property_id})
        if existing > 0:
            return
        docs = []
        for item in DEFAULT_KB:
            docs.append({
                "id": str(uuid.uuid4()),
                "property_id": property_id,
                "category": item["category"],
                "question": item["question"],
                "answer": item["answer"],
                "is_active": True,
                "created_at": _now_iso(),
                "seeded": True,
            })
        if docs:
            await db.web_concierge_kb.insert_many(docs)

    # =========== Public widget config ===========
    @router.get("/web-concierge/widget-config/{property_id}")
    async def widget_config(property_id: str):
        cfg = await _get_or_create_config(property_id)
        return {
            "property_id": property_id,
            "property_name": cfg.get("property_name", "Otelimiz"),
            "primary_color": cfg.get("primary_color", "#0c0a09"),
            "welcome_message": cfg.get("welcome_message", DEFAULT_WELCOME),
            "agent_name": cfg.get("agent_name", "Concierge AI"),
            "is_active": cfg.get("is_active", True),
        }

    # =========== Public chat ===========
    @router.post("/web-concierge/chat")
    async def chat(body: dict):
        property_id = body.get("property_id") or ""
        session_id = body.get("session_id") or str(uuid.uuid4())
        message = (body.get("message") or "").strip()
        if not property_id or not message:
            raise HTTPException(400, "property_id and message required")
        cfg = await _get_or_create_config(property_id)
        if not cfg.get("is_active", True):
            raise HTTPException(403, "Concierge disabled for this property")
        # Auto-seed KB on first chat
        if not cfg.get("auto_seed_done"):
            await _seed_default_kb(property_id)
            await db.web_concierge_config.update_one(
                {"property_id": property_id},
                {"$set": {"auto_seed_done": True}}
            )
        # Get / create session
        sess = await db.web_concierge_sessions.find_one(
            {"session_id": session_id}, {"_id": 0}
        )
        if not sess:
            sess = {
                "session_id": session_id,
                "property_id": property_id,
                "messages": [],
                "started_at": _now_iso(),
                "lead_captured": False,
            }
            await db.web_concierge_sessions.insert_one(sess)
        # Pull KB
        kb_items = await db.web_concierge_kb.find(
            {"property_id": property_id, "is_active": True}, {"_id": 0}
        ).to_list(200)
        kb_context = "\n".join([
            f"- ({k['category']}) Q: {k['question']} | A: {k['answer']}"
            for k in kb_items
        ])
        # Build conversation history (last 8 turns)
        history = sess.get("messages", [])[-16:]
        # Try LLM with emergentintegrations; fall back to keyword KB match.
        reply = None
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            llm_key = os.environ.get("EMERGENT_LLM_KEY")
            if llm_key:
                system_prompt = (
                    f"Sen {cfg.get('property_name', 'Otelimiz')}'in 7/24 dijital "
                    f"concierge asistanısın. Misafirlere kısa, sıcak ve net "
                    f"Türkçe yanıtlar ver. Emin olmadığın bilgileri uydurma — "
                    f"böyle durumlarda rezervasyon ekibine yönlendir. "
                    f"\n\nMülk Bilgi Tabanı:\n{kb_context}\n\n"
                    f"Yanıtların 2-3 cümleyi geçmesin."
                )
                chat_client = LlmChat(
                    api_key=llm_key,
                    session_id=session_id,
                    system_message=system_prompt,
                ).with_model("openai", "gpt-4o-mini")
                # Replay history briefly as context
                msg_text = message
                if history:
                    last = history[-4:]
                    ctx = "\n".join([
                        f"{('Misafir' if m['role']=='user' else 'AI')}: {m['content']}"
                        for m in last
                    ])
                    msg_text = f"Önceki konuşma:\n{ctx}\n\nYeni soru: {message}"
                user_msg = UserMessage(text=msg_text)
                reply = await chat_client.send_message(user_msg)
        except Exception as e:
            logger.warning(f"web-concierge LLM failed, falling back: {e}")
            reply = None

        # Fallback: simple keyword search across KB
        if not reply:
            lowered = message.lower()
            best = None
            for k in kb_items:
                qw = k["question"].lower()
                if any(tok in lowered for tok in qw.split() if len(tok) > 3):
                    best = k
                    break
            if best:
                reply = best["answer"]
            else:
                reply = ("Şu an için detay bulamadım — rezervasyon ekibimiz size "
                         "yardımcı olacaktır. Telefon veya e-posta bırakırsanız "
                         "kısa süre içinde döneriz.")

        # Append messages
        now = _now_iso()
        new_messages = history + [
            {"role": "user", "content": message, "ts": now},
            {"role": "assistant", "content": reply, "ts": now},
        ]
        await db.web_concierge_sessions.update_one(
            {"session_id": session_id},
            {"$set": {"messages": new_messages, "last_message_at": now}}
        )
        # Detect simple lead intent
        actions = []
        low = message.lower()
        if any(w in low for w in ["rezerv", "fiyat", "müsait", "musait", "uygunluk", "boş", "bos"]):
            actions.append({"label": "Şimdi Rezervasyon Yap", "type": "book"})
        if any(w in low for w in ["ara", "telefon", "iletisim", "iletişim"]):
            actions.append({"label": "Bizi Arayın", "type": "call"})
        return {
            "session_id": session_id,
            "reply": reply,
            "suggested_actions": actions,
        }

    # =========== Admin: KB management ===========
    @router.get("/web-concierge/knowledge/{property_id}")
    async def list_kb(property_id: str,
                      _: dict = Depends(require_roles("admin", "manager"))):
        items = await db.web_concierge_kb.find(
            {"property_id": property_id}, {"_id": 0}
        ).sort("category", 1).to_list(500)
        return {"items": items, "count": len(items)}

    @router.post("/web-concierge/knowledge/{property_id}")
    async def add_kb(property_id: str, body: dict,
                     current_user: dict = Depends(require_roles("admin", "manager"))):
        q = (body.get("question") or "").strip()
        a = (body.get("answer") or "").strip()
        if not q or not a:
            raise HTTPException(400, "question and answer required")
        doc = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "category": body.get("category", "general"),
            "question": q,
            "answer": a,
            "is_active": True,
            "created_at": _now_iso(),
            "created_by": current_user.get("name", ""),
        }
        await db.web_concierge_kb.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.patch("/web-concierge/knowledge/{kb_id}")
    async def patch_kb(kb_id: str, body: dict,
                       _: dict = Depends(require_roles("admin", "manager"))):
        allowed = {"category", "question", "answer", "is_active"}
        update = {k: v for k, v in body.items() if k in allowed}
        if not update:
            raise HTTPException(400, "Nothing to update")
        update["updated_at"] = _now_iso()
        r = await db.web_concierge_kb.update_one({"id": kb_id}, {"$set": update})
        if not r.matched_count:
            raise HTTPException(404, "KB item not found")
        return {"ok": True}

    @router.delete("/web-concierge/knowledge/{kb_id}")
    async def delete_kb(kb_id: str,
                        _: dict = Depends(require_roles("admin"))):
        r = await db.web_concierge_kb.delete_one({"id": kb_id})
        if not r.deleted_count:
            raise HTTPException(404, "KB item not found")
        return {"ok": True}

    # =========== Admin: session monitoring ===========
    @router.get("/web-concierge/sessions/{property_id}")
    async def list_sessions(property_id: str, limit: int = 50,
                            _: dict = Depends(require_roles("admin", "manager"))):
        items = await db.web_concierge_sessions.find(
            {"property_id": property_id}, {"_id": 0}
        ).sort("started_at", -1).to_list(min(limit, 200))
        # Trim messages preview
        for s in items:
            msgs = s.get("messages", [])
            s["message_count"] = len(msgs)
            s["first_user_message"] = next(
                (m["content"] for m in msgs if m["role"] == "user"), ""
            )
            s["last_message_at"] = s.get("last_message_at") or s.get("started_at")
            s.pop("messages", None)
        return {"items": items, "count": len(items)}

    @router.get("/web-concierge/session/{session_id}")
    async def get_session(session_id: str,
                          _: dict = Depends(require_roles("admin", "manager"))):
        s = await db.web_concierge_sessions.find_one(
            {"session_id": session_id}, {"_id": 0}
        )
        if not s:
            raise HTTPException(404, "Session not found")
        return s

    @router.post("/web-concierge/config/{property_id}")
    async def update_config(property_id: str, body: dict,
                            _: dict = Depends(require_roles("admin", "manager"))):
        allowed = {"property_name", "primary_color", "welcome_message",
                   "agent_name", "is_active"}
        update = {k: v for k, v in body.items() if k in allowed}
        if not update:
            raise HTTPException(400, "Nothing to update")
        update["updated_at"] = _now_iso()
        await db.web_concierge_config.update_one(
            {"property_id": property_id},
            {"$set": update},
            upsert=True
        )
        return {"ok": True}

    return router
