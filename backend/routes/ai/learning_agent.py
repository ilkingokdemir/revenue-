"""
Learning AI Reply Robot — self-improving response agent.

Drafts professional responses to guest REVIEWS and COMPLAINTS per property
(şube). Human-in-the-loop: manager reviews the AI draft, edits it, then
sends. Every edit teaches the agent: the diff between the AI draft and the
manager's final version is distilled by the LLM into concise style lessons
stored per property and injected into all future prompts (plus few-shot
examples of the manager's final texts).

Endpoints
---------
  GET    /api/ai-agent/inbox/{property_id}            — unified inbox (reviews + complaints)
  POST   /api/ai-agent/draft                          — {property_id, source_type, source_id}
  POST   /api/ai-agent/send/{draft_id}                — {final_text} approve/edit & send (learns from edits)
  GET    /api/ai-agent/lessons/{property_id}          — learned style rules
  POST   /api/ai-agent/lessons/{property_id}          — manually add a rule
  DELETE /api/ai-agent/lessons/{property_id}/{lesson_id}
  GET    /api/ai-agent/stats/{property_id}            — KPIs (drafts, sent, edit rate, lessons)
  GET    /api/ai-agent/history/{property_id}          — sent responses log
"""
from datetime import datetime, timezone
from difflib import SequenceMatcher
import json
import logging
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _strip_json(raw: str) -> str:
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
    return raw


def create_learning_agent_router(db, require_roles):
    router = APIRouter()

    MAX_LESSONS = 30
    FEW_SHOT_COUNT = 3

    # ---------- helpers ----------
    async def _active_lessons(property_id: str):
        return await db.ai_agent_lessons.find(
            {"property_id": property_id, "active": True}, {"_id": 0}
        ).sort("created_at", -1).to_list(MAX_LESSONS)

    async def _few_shot_examples(property_id: str, source_type: str):
        return await db.ai_agent_examples.find(
            {"property_id": property_id, "source_type": source_type}, {"_id": 0}
        ).sort("created_at", -1).to_list(FEW_SHOT_COUNT)

    async def _get_source(source_type: str, source_id: str):
        if source_type == "review":
            return await db.reviews.find_one({"id": source_id}, {"_id": 0})
        if source_type == "complaint":
            return await db.guest_complaints.find_one({"id": source_id}, {"_id": 0})
        return None

    def _source_context(source_type: str, src: dict) -> str:
        if source_type == "review":
            author = src.get("author") or src.get("guest_name") or "Misafir"
            return (f"Misafir yorumu\nMisafir: {author}\n"
                    f"Puan: {src.get('rating', '?')}/5\n"
                    f"Platform: {src.get('platform', '-')}\n"
                    f"Yorum: {(src.get('comment') or src.get('text') or '').strip()}")
        return (f"Misafir şikayeti\nMisafir: {src.get('guest_name') or 'Misafir'}\n"
                f"Kategori: {src.get('category', '-')}\n"
                f"Önem: {src.get('severity', '-')}\n"
                f"Oda: {src.get('room_number') or '-'}\n"
                f"Şikayet: {(src.get('text') or '').strip()}")

    async def _generate_draft(property_id: str, source_type: str, src: dict) -> str:
        cfg = await db.review_agent_config.find_one(
            {"property_id": property_id}, {"_id": 0}) or {}
        sign_off = cfg.get("sign_off", "Yönetim")
        lessons = await _active_lessons(property_id)
        examples = await _few_shot_examples(property_id, source_type)

        lesson_block = ""
        if lessons:
            rules = "\n".join(f"- {l['rule']}" for l in lessons)
            lesson_block = (f"\n\nYÖNETİCİNİN GEÇMİŞ DÜZENLEMELERİNDEN ÖĞRENİLEN KURALLAR "
                            f"(mutlaka uygula):\n{rules}")
        example_block = ""
        if examples:
            ex_txt = "\n\n".join(
                f"DURUM:\n{e['context'][:400]}\nYÖNETİCİNİN ONAYLADIĞI YANIT:\n{e['final_text'][:500]}"
                for e in examples)
            example_block = (f"\n\nYÖNETİCİNİN TARZINI GÖSTEREN ÖRNEKLER "
                             f"(bu üsluba sadık kal):\n{ex_txt}")

        if source_type == "review":
            task = ("Misafir yorumuna otel adına profesyonel bir yanıt yaz. "
                    "Olumlu yorumlarda içten teşekkür et ve geri davet et. "
                    "Olumsuz yorumlarda özür dile, sorumluluğu üstlen, somut adım belirt.")
        else:
            task = ("Misafir şikayetine otel şubesi adına profesyonel, empatik ve "
                    "çözüm odaklı bir yanıt yaz. Özür dile, atılacak somut adımı ve "
                    "varsa telafi önerisini belirt, iletişim kanalı sun.")

        system_prompt = (
            f"Sen otel yönetimi adına misafir iletişimi yazan uzman bir asistansın. "
            f"Türkçe yaz. {task} Yanıt 3-6 cümle olsun, klişelerden kaçın. "
            f"Sonunda '— {sign_off}' imzası kullan, başka imza ekleme."
            f"{lesson_block}{example_block}"
        )
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            llm_key = os.environ.get("EMERGENT_LLM_KEY")
            if llm_key:
                client = LlmChat(
                    api_key=llm_key,
                    session_id=f"ai-agent-{uuid.uuid4()}",
                    system_message=system_prompt,
                ).with_model("openai", "gpt-5.2")
                return await client.send_message(
                    UserMessage(text=_source_context(source_type, src)))
        except Exception as e:
            logger.warning(f"ai-agent draft LLM failed, fallback: {e}")
        # fallback template
        name = src.get("author") or src.get("guest_name") or "Misafirimiz"
        if source_type == "review":
            return (f"Sayın {name}, değerli geri bildiriminiz için teşekkür ederiz. "
                    f"Görüşleriniz ekibimizle paylaşıldı ve gelişimimiz için önemli. "
                    f"Sizi tekrar ağırlamaktan mutluluk duyarız.\n— {sign_off}")
        return (f"Sayın {name}, yaşadığınız olumsuzluk için içtenlikle özür dileriz. "
                f"Konu doğrudan şube yönetimimize iletildi ve gerekli aksiyon alınmaktadır. "
                f"Telafi için sizinle iletişime geçmekten memnuniyet duyarız.\n— {sign_off}")

    async def _learn_from_edit(property_id: str, source_type: str,
                               context: str, ai_text: str, final_text: str):
        """Distil style lessons from the manager's edit."""
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            llm_key = os.environ.get("EMERGENT_LLM_KEY")
            if not llm_key:
                return []
            client = LlmChat(
                api_key=llm_key,
                session_id=f"ai-agent-learn-{uuid.uuid4()}",
                system_message=(
                    "Bir otel yöneticisi, AI'ın yazdığı taslağı düzenleyip gönderdi. "
                    "AI taslağı ile yöneticinin final versiyonunu karşılaştır. "
                    "AI'ın gelecekte uygulaması gereken en fazla 2 kısa ve genel yazım "
                    "kuralı çıkar (Türkçe, her biri tek cümle, spesifik isim/tarih içermesin). "
                    "Eğer fark önemsizse boş liste döndür. "
                    'SADECE geçerli JSON döndür: {"lessons": ["kural 1", "kural 2"]}'
                ),
            ).with_model("openai", "gpt-5.2")
            resp = await client.send_message(UserMessage(text=(
                f"BAĞLAM:\n{context[:500]}\n\nAI TASLAĞI:\n{ai_text}\n\n"
                f"YÖNETİCİNİN FİNAL VERSİYONU:\n{final_text}")))
            obj = json.loads(_strip_json(resp))
            new_rules = [r.strip() for r in obj.get("lessons", []) if r and r.strip()][:2]
            existing = {l["rule"] for l in await _active_lessons(property_id)}
            saved = []
            for rule in new_rules:
                if rule in existing:
                    continue
                doc = {
                    "id": str(uuid.uuid4()),
                    "property_id": property_id,
                    "rule": rule,
                    "source": "edit_learning",
                    "source_type": source_type,
                    "active": True,
                    "created_at": _now_iso(),
                }
                await db.ai_agent_lessons.insert_one(doc)
                doc.pop("_id", None)
                saved.append(doc)
            return saved
        except Exception as e:
            logger.warning(f"ai-agent learning failed: {e}")
            return []

    # ---------- inbox ----------
    @router.get("/ai-agent/inbox/{property_id}")
    async def inbox(property_id: str,
                    _: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        reviews = await db.reviews.find(
            {"property_id": property_id,
             "$or": [{"response_text": {"$exists": False}}, {"response_text": ""}]},
            {"_id": 0}).sort("created_at", -1).to_list(100)
        complaints = await db.guest_complaints.find(
            {"property_id": property_id,
             "status": {"$nin": ["closed"]},
             "$or": [{"guest_response_text": {"$exists": False}},
                     {"guest_response_text": ""}]},
            {"_id": 0}).sort("created_at", -1).to_list(100)
        items = (
            [{"source_type": "review", "source_id": r["id"],
              "guest_name": r.get("author") or r.get("guest_name") or "Misafir",
              "title": f"{r.get('rating', '?')}/5 · {r.get('platform', '')}",
              "text": r.get("comment") or r.get("text") or "",
              "rating": r.get("rating"), "created_at": r.get("created_at", ""),
              "ai_draft": r.get("ai_draft", "")} for r in reviews] +
            [{"source_type": "complaint", "source_id": c["id"],
              "guest_name": c.get("guest_name") or "Misafir",
              "title": f"{c.get('category', 'diğer')} · {c.get('severity', '')}",
              "text": c.get("text", ""), "severity": c.get("severity"),
              "created_at": c.get("created_at", ""),
              "ai_draft": c.get("ai_draft", "")} for c in complaints]
        )
        items.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        return {"items": items, "count": len(items),
                "review_count": len(reviews), "complaint_count": len(complaints)}

    # ---------- draft ----------
    @router.post("/ai-agent/draft")
    async def create_draft(body: dict,
                           current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        property_id = (body.get("property_id") or "").strip()
        source_type = body.get("source_type", "")
        source_id = (body.get("source_id") or "").strip()
        if source_type not in ("review", "complaint") or not property_id or not source_id:
            raise HTTPException(400, "property_id, source_type (review|complaint) ve source_id gerekli")
        src = await _get_source(source_type, source_id)
        if not src:
            raise HTTPException(404, "Kaynak kayıt bulunamadı")
        text = await _generate_draft(property_id, source_type, src)
        draft = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "source_type": source_type,
            "source_id": source_id,
            "context": _source_context(source_type, src),
            "ai_text": text,
            "status": "draft",
            "created_by": current_user.get("email", ""),
            "created_at": _now_iso(),
        }
        await db.ai_agent_drafts.insert_one(dict(draft))
        coll = db.reviews if source_type == "review" else db.guest_complaints
        await coll.update_one({"id": source_id},
                              {"$set": {"ai_draft": text, "ai_draft_at": _now_iso(),
                                        "ai_draft_status": "pending_review"}})
        lessons_used = len(await _active_lessons(property_id))
        return {**draft, "lessons_applied": lessons_used}

    @router.get("/ai-agent/draft/latest")
    async def latest_draft(source_type: str, source_id: str,
                           _: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        doc = await db.ai_agent_drafts.find_one(
            {"source_type": source_type, "source_id": source_id, "status": "draft"},
            {"_id": 0}, sort=[("created_at", -1)])
        return doc or {}

    # ---------- bulk draft ----------
    @router.post("/ai-agent/batch-draft/{property_id}")
    async def batch_draft(property_id: str, body: dict = None,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        import asyncio
        body = body or {}
        limit = min(int(body.get("limit", 25)), 50)
        inbox_data = await inbox(property_id, _={})
        targets = [i for i in inbox_data["items"] if not i.get("ai_draft")][:limit]
        sem = asyncio.Semaphore(4)
        now = _now_iso()

        async def _one(item):
            async with sem:
                src = await _get_source(item["source_type"], item["source_id"])
                if not src:
                    return None
                text = await _generate_draft(property_id, item["source_type"], src)
                draft = {
                    "id": str(uuid.uuid4()), "property_id": property_id,
                    "source_type": item["source_type"], "source_id": item["source_id"],
                    "context": _source_context(item["source_type"], src),
                    "ai_text": text, "status": "draft",
                    "created_by": current_user.get("email", ""),
                    "created_at": now, "batch": True,
                }
                await db.ai_agent_drafts.insert_one(dict(draft))
                coll = db.reviews if item["source_type"] == "review" else db.guest_complaints
                await coll.update_one({"id": item["source_id"]},
                                      {"$set": {"ai_draft": text, "ai_draft_at": now,
                                                "ai_draft_status": "pending_review"}})
                return {"source_type": item["source_type"],
                        "source_id": item["source_id"], "draft_id": draft["id"]}

        results = [r for r in await asyncio.gather(*[_one(i) for i in targets]) if r]
        return {"property_id": property_id, "drafted_count": len(results),
                "skipped_existing": len(inbox_data["items"]) - len(targets),
                "items": results}

    # ---------- send (approve / edit) ----------
    @router.post("/ai-agent/draft/paste")
    async def paste_draft(body: dict,
                          current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        property_id = (body.get("property_id") or "").strip()
        kind = body.get("kind", "review")
        text = (body.get("text") or "").strip()
        guest_name = (body.get("guest_name") or "Misafir").strip()
        if kind not in ("review", "complaint") or not property_id or not text:
            raise HTTPException(400, "property_id, kind (review|complaint) ve text gerekli")
        src = ({"author": guest_name, "rating": body.get("rating", "?"),
                "platform": body.get("platform", "harici"), "comment": text}
               if kind == "review" else
               {"guest_name": guest_name, "category": body.get("category", "genel"),
                "severity": body.get("severity", "-"), "text": text})
        ai_text = await _generate_draft(property_id, kind, src)
        draft = {
            "id": str(uuid.uuid4()), "property_id": property_id,
            "source_type": kind, "source_id": "manual",
            "manual": True,
            "context": _source_context(kind, src),
            "ai_text": ai_text, "status": "draft",
            "created_by": current_user.get("email", ""),
            "created_at": _now_iso(),
        }
        await db.ai_agent_drafts.insert_one(dict(draft))
        lessons_used = len(await _active_lessons(property_id))
        return {**draft, "lessons_applied": lessons_used}

    @router.post("/ai-agent/send/{draft_id}")
    async def send_response(draft_id: str, body: dict,
                            current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        draft = await db.ai_agent_drafts.find_one({"id": draft_id}, {"_id": 0})
        if not draft:
            raise HTTPException(404, "Taslak bulunamadı")
        if draft.get("status") == "sent":
            raise HTTPException(400, "Bu taslak zaten gönderildi")
        final_text = (body.get("final_text") or draft["ai_text"]).strip()
        if not final_text:
            raise HTTPException(400, "final_text boş olamaz")

        similarity = SequenceMatcher(None, draft["ai_text"], final_text).ratio()
        was_edited = similarity < 0.98

        # write back to source
        now = _now_iso()
        who = current_user.get("name") or current_user.get("email", "")
        if draft.get("manual"):
            pass  # harici kaynak: yanıt yönetici tarafından kopyalanıp platformda yayınlanır
        elif draft["source_type"] == "review":
            await db.reviews.update_one(
                {"id": draft["source_id"]},
                {"$set": {"response_text": final_text, "responded_at": now,
                          "responded_by": who, "ai_assisted": True,
                          "ai_draft_status": "published"}})
        else:
            await db.guest_complaints.update_one(
                {"id": draft["source_id"]},
                {"$set": {"guest_response_text": final_text,
                          "guest_response_at": now, "responded_by": who,
                          "ai_assisted": True,
                          "status": "in_progress"}})

        new_lessons = []
        if was_edited:
            await db.ai_agent_examples.insert_one({
                "id": str(uuid.uuid4()),
                "property_id": draft["property_id"],
                "source_type": draft["source_type"],
                "context": draft.get("context", ""),
                "ai_text": draft["ai_text"],
                "final_text": final_text,
                "created_at": now,
            })
            new_lessons = await _learn_from_edit(
                draft["property_id"], draft["source_type"],
                draft.get("context", ""), draft["ai_text"], final_text)

        await db.ai_agent_drafts.update_one(
            {"id": draft_id},
            {"$set": {"status": "sent", "final_text": final_text,
                      "was_edited": was_edited,
                      "similarity": round(similarity, 3),
                      "sent_at": now, "sent_by": who}})
        return {"ok": True, "draft_id": draft_id, "was_edited": was_edited,
                "similarity": round(similarity, 3),
                "new_lessons": new_lessons,
                "learned_count": len(new_lessons)}

    # ---------- lessons ----------
    @router.get("/ai-agent/lessons/{property_id}")
    async def list_lessons(property_id: str,
                           _: dict = Depends(require_roles("admin", "manager"))):
        items = await _active_lessons(property_id)
        return {"items": items, "count": len(items)}

    @router.post("/ai-agent/lessons/{property_id}")
    async def add_lesson(property_id: str, body: dict,
                         _: dict = Depends(require_roles("admin", "manager"))):
        rule = (body.get("rule") or "").strip()
        if not rule:
            raise HTTPException(400, "rule gerekli")
        doc = {"id": str(uuid.uuid4()), "property_id": property_id,
               "rule": rule, "source": "manual", "active": True,
               "created_at": _now_iso()}
        await db.ai_agent_lessons.insert_one(dict(doc))
        return doc

    @router.delete("/ai-agent/lessons/{property_id}/{lesson_id}")
    async def delete_lesson(property_id: str, lesson_id: str,
                            _: dict = Depends(require_roles("admin", "manager"))):
        res = await db.ai_agent_lessons.update_one(
            {"id": lesson_id, "property_id": property_id},
            {"$set": {"active": False, "deactivated_at": _now_iso()}})
        if not res.matched_count:
            raise HTTPException(404, "Kural bulunamadı")
        return {"ok": True}

    # ---------- stats & history ----------
    @router.get("/ai-agent/stats/{property_id}")
    async def stats(property_id: str,
                    _: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        q = {"property_id": property_id}
        total_drafts = await db.ai_agent_drafts.count_documents(q)
        sent = await db.ai_agent_drafts.count_documents({**q, "status": "sent"})
        edited = await db.ai_agent_drafts.count_documents(
            {**q, "status": "sent", "was_edited": True})
        lessons = await db.ai_agent_lessons.count_documents({**q, "active": True})
        return {
            "total_drafts": total_drafts,
            "sent": sent,
            "edited": edited,
            "edit_rate": round(edited / sent * 100, 1) if sent else 0,
            "approval_rate": round((sent - edited) / sent * 100, 1) if sent else 0,
            "lessons": lessons,
        }

    @router.get("/ai-agent/report/{property_id}")
    async def learning_report(property_id: str, weeks: int = 6,
                              _: dict = Depends(require_roles("admin", "manager"))):
        from datetime import timedelta
        weeks = min(max(weeks, 1), 12)
        now = datetime.now(timezone.utc)
        start = now - timedelta(weeks=weeks)
        sent_drafts = await db.ai_agent_drafts.find(
            {"property_id": property_id, "status": "sent",
             "sent_at": {"$gte": start.isoformat()}}, {"_id": 0}).to_list(2000)
        lessons = await db.ai_agent_lessons.find(
            {"property_id": property_id,
             "created_at": {"$gte": start.isoformat()}}, {"_id": 0}).to_list(500)

        def week_start(iso: str):
            try:
                d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
            except Exception:
                return None
            monday = d - timedelta(days=d.weekday())
            return monday.strftime("%Y-%m-%d")

        buckets = {}
        cursor = (now - timedelta(days=now.weekday()))
        for i in range(weeks):
            wk = (cursor - timedelta(weeks=i)).strftime("%Y-%m-%d")
            buckets[wk] = {"week_start": wk, "sent": 0, "edited": 0,
                           "similarity_sum": 0.0, "lessons_learned": 0,
                           "lesson_rules": []}
        for d in sent_drafts:
            wk = week_start(d.get("sent_at", ""))
            if wk in buckets:
                b = buckets[wk]
                b["sent"] += 1
                if d.get("was_edited"):
                    b["edited"] += 1
                b["similarity_sum"] += float(d.get("similarity") or 1.0)
        for l in lessons:
            wk = week_start(l.get("created_at", ""))
            if wk in buckets:
                buckets[wk]["lessons_learned"] += 1
                buckets[wk]["lesson_rules"].append(l["rule"])

        series = []
        for wk in sorted(buckets):
            b = buckets[wk]
            sent = b["sent"]
            series.append({
                "week_start": wk, "sent": sent, "edited": b["edited"],
                "approval_rate": round((sent - b["edited"]) / sent * 100, 1) if sent else None,
                "avg_similarity": round(b["similarity_sum"] / sent, 3) if sent else None,
                "lessons_learned": b["lessons_learned"],
                "lesson_rules": b["lesson_rules"],
            })
        rates = [w["approval_rate"] for w in series if w["approval_rate"] is not None]
        return {
            "property_id": property_id, "weeks": weeks, "series": series,
            "totals": {
                "sent": sum(w["sent"] for w in series),
                "edited": sum(w["edited"] for w in series),
                "lessons_learned": sum(w["lessons_learned"] for w in series),
                "first_week_approval": rates[0] if rates else None,
                "last_week_approval": rates[-1] if rates else None,
                "trend": (round(rates[-1] - rates[0], 1)
                          if len(rates) >= 2 else None),
            },
        }

    @router.get("/ai-agent/history/{property_id}")
    async def history(property_id: str, limit: int = 50,
                      _: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        items = await db.ai_agent_drafts.find(
            {"property_id": property_id, "status": "sent"}, {"_id": 0}
        ).sort("sent_at", -1).to_list(min(limit, 200))
        return {"items": items, "count": len(items)}

    return router
