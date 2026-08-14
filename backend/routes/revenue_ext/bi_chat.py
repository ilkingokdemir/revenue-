"""Doğal Dil BI Chat — FLYR 'Insights: ask your data anything' paritesi.
Tüm otel verisi (doluluk, gelir, kanal, pickup, yorum) üzerinde Türkçe soru-cevap."""
import os
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from typing import Dict

SYSTEM = """Sen bir otel iş zekası (BI) analistisin. Sana verilen GERÇEK otel verisi bağlamını kullanarak
kullanıcının sorusunu Türkçe, kısa ve sayı odaklı yanıtla. Veriyi uydurma; bağlamda yoksa 'bu veri elimde yok' de.
Mümkünse karşılaştırma ve yüzde değişim ver. Yanıt en fazla 6 cümle olsun."""


async def _data_pack(db, pid: str) -> str:
    from routes.revenue_ext.ml_pickup import _stay_counts
    cap = await db.rooms.count_documents({"property_id": pid}) or 20
    today = datetime.now(timezone.utc).date()
    lines = [f"Kapasite: {cap} oda. Bugün: {today.isoformat()}"]
    for label, s, e in [("Son 7 gün", -7, 0), ("Önceki 7 gün", -14, -7), ("Gelecek 7 gün", 1, 8)]:
        rev, rooms_sold, n = 0.0, 0, 0
        for i in range(s, e):
            ds = (today + timedelta(days=i)).isoformat()
            otb = (await _stay_counts(db, pid, ds))["otb"]
            rooms_sold += otb
            n += 1
        occ = round(rooms_sold / (cap * max(n, 1)) * 100, 1)
        lines.append(f"{label}: satılan oda-gece {rooms_sold}, doluluk %{occ}")
    m_start = today.replace(day=1).isoformat()
    agg = await db.bookings.aggregate([
        {"$match": {"property_id": pid, "status": {"$nin": ["cancelled", "no_show"]},
                    "check_in": {"$gte": m_start}}},
        {"$group": {"_id": "$source", "rev": {"$sum": "$total_price"}, "n": {"$sum": 1}}},
        {"$sort": {"rev": -1}}]).to_list(10)
    tot = sum(a["rev"] or 0 for a in agg) or 1
    lines.append("Bu ay kanal kırılımı (check-in bazlı): " + "; ".join(
        f"{a['_id'] or 'direct'}: £{(a['rev'] or 0):,.0f} (%{(a['rev'] or 0) / tot * 100:.0f}, {a['n']} rez)" for a in agg))
    adr_agg = await db.bookings.aggregate([
        {"$match": {"property_id": pid, "status": {"$nin": ["cancelled", "no_show"]},
                    "check_in": {"$gte": (today - timedelta(days=30)).isoformat()}}},
        {"$group": {"_id": None, "rev": {"$sum": "$total_price"}, "n": {"$sum": 1}}}]).to_list(1)
    if adr_agg:
        lines.append(f"Son 30 gün: toplam gelir £{(adr_agg[0]['rev'] or 0):,.0f}, {adr_agg[0]['n']} rezervasyon")
    comp = await db.complaints.count_documents({"property_id": pid}) if "complaints" in await db.list_collection_names() else 0
    lines.append(f"Toplam şikayet kaydı: {comp}")
    imp = await db.exec_reports.find_one({"property_id": pid}, {"_id": 0, "impact": 1}, sort=[("week", -1)])
    if imp:
        lines.append(f"Robot katkısı (son arşiv): £{imp['impact'].get('est_total_contribution', 0):,.0f}, başarı %{imp['impact'].get('success_rate')}")
    return "\n".join(lines)


def create_bi_chat_router(db, require_roles):
    router = APIRouter(prefix="/bi-chat", tags=["bi-chat"])
    ROLES = ("admin", "manager", "receptionist")

    @router.get("/{pid}/history")
    async def history(pid: str, session_id: str = "", _u: dict = Depends(require_roles(*ROLES))):
        q = {"property_id": pid}
        if session_id:
            q["session_id"] = session_id
        items = await db.bi_chat_messages.find(q, {"_id": 0}).sort("created_at", 1).to_list(100)
        return {"items": items}

    @router.post("/{pid}")
    async def ask(pid: str, body: Dict, current_user: dict = Depends(require_roles(*ROLES))):
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        question = (body.get("question") or "").strip()[:500]
        session_id = body.get("session_id") or str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).isoformat()
        await db.bi_chat_messages.insert_one({
            "id": str(uuid.uuid4())[:8], "property_id": pid, "session_id": session_id,
            "role": "user", "content": question, "created_at": now})
        pack = await _data_pack(db, pid)
        prev = await db.bi_chat_messages.find(
            {"property_id": pid, "session_id": session_id}, {"_id": 0}).sort("created_at", -1).to_list(8)
        hist = "\n".join(f"{m['role']}: {m['content']}" for m in reversed(prev[1:]))
        try:
            chat = LlmChat(api_key=os.environ.get("EMERGENT_LLM_KEY", ""),
                           session_id=f"bi-{pid}-{session_id}",
                           system_message=f"{SYSTEM}\n\nOTEL VERİSİ:\n{pack}\n\nÖnceki konuşma:\n{hist}"
                           ).with_model("openai", "gpt-5.2")
            answer = await chat.send_message(UserMessage(text=question))
        except Exception as e:
            answer = f"Şu an yanıt üretemedim ({str(e)[:80]}). Lütfen tekrar deneyin."
        await db.bi_chat_messages.insert_one({
            "id": str(uuid.uuid4())[:8], "property_id": pid, "session_id": session_id,
            "role": "assistant", "content": answer, "created_at": datetime.now(timezone.utc).isoformat()})
        return {"session_id": session_id, "answer": answer}

    return router
