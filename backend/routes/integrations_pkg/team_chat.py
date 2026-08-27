"""
Internal Team Chat — Flexkeeping-style multi-channel team communication.

Channels: per-department, per-property, or direct (1:1). MVP uses polling
(short-poll every few seconds from the client) — no websocket dependency.

Endpoints:
  GET    /api/team-chat/channels                          — list channels visible to me
  POST   /api/team-chat/channels                          — create channel
  GET    /api/team-chat/channels/{channel_id}/messages    — fetch messages (paginated)
  POST   /api/team-chat/channels/{channel_id}/messages    — post message
  POST   /api/team-chat/channels/{channel_id}/read        — mark up-to-now as read
  GET    /api/team-chat/unread                            — unread counts per channel
  POST   /api/team-chat/dm/{user_id}                      — open / find DM channel
"""
from datetime import datetime, timezone
import uuid
import os
from typing import Optional, List, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)


CHANNEL_KINDS = {"property", "department", "direct", "general"}


class ChannelIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    kind: str = "department"
    department: str = ""        # e.g. "housekeeping"
    property_id: str = "all"
    members: List[str] = []     # user ids (for direct channels)
    description: str = ""


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    mentions: List[str] = []    # user ids mentioned with @


def _can_user_see(channel: dict, user: dict) -> bool:
    """Visibility rules for a channel."""
    kind = channel.get("kind")
    if kind == "general":
        return True
    if kind == "direct":
        return (user.get("id") or user.get("email")) in (channel.get("members") or [])
    if kind == "department":
        u_role = (user.get("role") or "").lower()
        dept = (channel.get("department") or "").lower()
        # Map role → department
        mapping = {
            "receptionist": "front-office",
            "housekeeping": "housekeeping",
            "maintenance": "maintenance",
            "manager": dept,  # managers can see all
            "admin": dept,
        }
        if u_role in {"admin", "manager"}:
            return True
        return mapping.get(u_role) == dept
    if kind == "property":
        # Anyone with access to that property — keep simple: all authed users
        return True
    return False


def create_team_chat_router(db, require_roles):
    router = APIRouter(prefix="/team-chat")

    async def _ensure_seed_channels():
        """Seed default channels if none exist (idempotent)."""
        n = await db.chat_channels.count_documents({})
        if n > 0:
            return
        now = datetime.now(timezone.utc).isoformat()
        defaults = [
            {"name": "general", "kind": "general", "description": "Everyone — announcements"},
            {"name": "front-office", "kind": "department", "department": "front-office"},
            {"name": "housekeeping", "kind": "department", "department": "housekeeping"},
            {"name": "maintenance", "kind": "department", "department": "maintenance"},
            {"name": "fnb", "kind": "department", "department": "fnb", "description": "Food & Beverage"},
            {"name": "management", "kind": "department", "department": "management"},
        ]
        for ch in defaults:
            ch.update({"id": str(uuid.uuid4()), "property_id": "all", "members": [],
                       "created_at": now, "updated_at": now, "created_by": "system"})
            await db.chat_channels.insert_one(ch)

    @router.get("/channels")
    async def list_channels(
        current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeping", "maintenance")),
    ):
        await _ensure_seed_channels()
        all_ch = await db.chat_channels.find({}, {"_id": 0}).sort([("kind", 1), ("name", 1)]).to_list(500)
        visible = [c for c in all_ch if _can_user_see(c, current_user)]
        uid = current_user.get("id") or current_user.get("email") or "anon"

        # Unread counts (efficient single query)
        unread_map: dict = {}
        last_reads = await db.chat_reads.find({"user_id": uid}, {"_id": 0}).to_list(500)
        last_map = {r["channel_id"]: r.get("last_read_at", "") for r in last_reads}
        for c in visible:
            last = last_map.get(c["id"], "")
            q = {"channel_id": c["id"]}
            if last:
                q["created_at"] = {"$gt": last}
            # Don't count own messages as unread
            q["author_id"] = {"$ne": uid}
            unread_map[c["id"]] = await db.chat_messages.count_documents(q)
            # Last message preview
            lm = await db.chat_messages.find_one({"channel_id": c["id"]},
                                                 {"_id": 0, "body": 1, "author_name": 1, "created_at": 1},
                                                 sort=[("created_at", -1)])
            c["last_message"] = lm
            c["unread_count"] = unread_map[c["id"]]
        return {"channels": visible}

    @router.post("/channels")
    async def create_channel(body: ChannelIn,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        if body.kind not in CHANNEL_KINDS:
            raise HTTPException(400, f"kind must be one of {CHANNEL_KINDS}")
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "id": str(uuid.uuid4()),
            **body.dict(),
            "created_by": current_user.get("name") or current_user.get("email") or "",
            "created_at": now,
            "updated_at": now,
        }
        await db.chat_channels.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.get("/channels/{channel_id}/messages")
    async def list_messages(
        channel_id: str, limit: int = 100, before: str = "",
        current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeping", "maintenance")),
    ):
        channel = await db.chat_channels.find_one({"id": channel_id}, {"_id": 0})
        if not channel:
            raise HTTPException(404, "Channel not found")
        if not _can_user_see(channel, current_user):
            raise HTTPException(403, "No access to this channel")
        q: dict = {"channel_id": channel_id}
        if before:
            q["created_at"] = {"$lt": before}
        msgs = await db.chat_messages.find(q, {"_id": 0}).sort("created_at", -1).to_list(min(limit, 200))
        msgs.reverse()  # chronological
        return {"channel_id": channel_id, "messages": msgs, "channel": channel}

    @router.post("/channels/{channel_id}/messages")
    async def post_message(
        channel_id: str, body: MessageIn,
        current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeping", "maintenance")),
    ):
        channel = await db.chat_channels.find_one({"id": channel_id}, {"_id": 0})
        if not channel:
            raise HTTPException(404, "Channel not found")
        if not _can_user_see(channel, current_user):
            raise HTTPException(403, "No access to this channel")
        now = datetime.now(timezone.utc).isoformat()
        uid = current_user.get("id") or current_user.get("email") or "anon"
        doc = {
            "id": str(uuid.uuid4()),
            "channel_id": channel_id,
            "author_id": uid,
            "author_name": current_user.get("name") or current_user.get("email") or "anon",
            "author_role": current_user.get("role", ""),
            "body": body.body,
            "mentions": body.mentions,
            "created_at": now,
            "edited": False,
        }
        await db.chat_messages.insert_one(doc)
        # Bump channel updated_at for sort ordering
        await db.chat_channels.update_one({"id": channel_id}, {"$set": {"updated_at": now}})
        # Auto-mark own message as read for sender
        await db.chat_reads.update_one(
            {"channel_id": channel_id, "user_id": uid},
            {"$set": {"last_read_at": now}},
            upsert=True,
        )
        doc.pop("_id", None)
        return doc

    @router.post("/channels/{channel_id}/read")
    async def mark_read(
        channel_id: str,
        current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeping", "maintenance")),
    ):
        channel = await db.chat_channels.find_one({"id": channel_id}, {"_id": 0})
        if not channel:
            raise HTTPException(404, "Channel not found")
        if not _can_user_see(channel, current_user):
            raise HTTPException(403, "No access to this channel")
        uid = current_user.get("id") or current_user.get("email") or "anon"
        now = datetime.now(timezone.utc).isoformat()
        await db.chat_reads.update_one(
            {"channel_id": channel_id, "user_id": uid},
            {"$set": {"last_read_at": now}},
            upsert=True,
        )
        return {"read": True, "at": now}

    @router.get("/unread")
    async def unread_counts(
        current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeping", "maintenance")),
    ):
        await _ensure_seed_channels()
        uid = current_user.get("id") or current_user.get("email") or "anon"
        channels = await db.chat_channels.find({}, {"_id": 0}).to_list(500)
        last_reads = await db.chat_reads.find({"user_id": uid}, {"_id": 0}).to_list(500)
        last_map = {r["channel_id"]: r.get("last_read_at", "") for r in last_reads}
        total = 0
        per_channel: dict = {}
        for c in channels:
            if not _can_user_see(c, current_user):
                continue
            q: dict = {"channel_id": c["id"], "author_id": {"$ne": uid}}
            if last_map.get(c["id"]):
                q["created_at"] = {"$gt": last_map[c["id"]]}
            cnt = await db.chat_messages.count_documents(q)
            if cnt > 0:
                per_channel[c["id"]] = cnt
                total += cnt
        return {"total": total, "by_channel": per_channel}

    @router.post("/dm/{user_id}")
    async def open_dm(
        user_id: str,
        current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeping", "maintenance")),
    ):
        """Find or create a direct-message channel between current user and target."""
        target = await db.users.find_one({"$or": [{"id": user_id}, {"email": user_id}]},
                                          {"_id": 0, "id": 1, "name": 1, "email": 1})
        if not target:
            raise HTTPException(404, "User not found")
        me = current_user.get("id") or current_user.get("email")
        other = target.get("id") or target.get("email")
        if me == other:
            raise HTTPException(400, "Cannot DM yourself")
        members = sorted([me, other])
        existing = await db.chat_channels.find_one({"kind": "direct", "members": members}, {"_id": 0})
        if existing:
            return existing
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "id": str(uuid.uuid4()),
            "name": target.get("name") or target.get("email") or "DM",
            "kind": "direct",
            "department": "",
            "property_id": "all",
            "members": members,
            "description": "",
            "created_by": current_user.get("name", ""),
            "created_at": now,
            "updated_at": now,
        }
        await db.chat_channels.insert_one(doc)
        doc.pop("_id", None)
        return doc

    SUPPORTED_LANGS = {"tr": "Türkçe", "en": "English", "de": "Deutsch",
                       "ru": "Русский", "ar": "العربية", "es": "Español"}

    @router.post("/channels/{channel_id}/translate")
    async def translate_channel(
        channel_id: str, data: Dict,
        current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeping", "maintenance")),
    ):
        """Kanalın son mesajlarını hedef dile çevirir (Flexkeeping dil bariyeri paritesi).
        Çeviriler mesaj dokümanında cache'lenir — her mesaj/dil için 1 LLM çağrısı."""
        lang = data.get("lang", "tr")
        if lang not in SUPPORTED_LANGS:
            raise HTTPException(400, f"Desteklenen diller: {list(SUPPORTED_LANGS)}")
        channel = await db.chat_channels.find_one({"id": channel_id}, {"_id": 0})
        if not channel or not _can_user_see(channel, current_user):
            raise HTTPException(403, "No access to this channel")
        msgs = await db.chat_messages.find(
            {"channel_id": channel_id}, {"_id": 0, "id": 1, "body": 1, "translations": 1}
        ).sort("created_at", -1).to_list(30)
        result = {m["id"]: (m.get("translations") or {}).get(lang) for m in msgs}
        pending = [m for m in msgs if not result[m["id"]] and (m.get("body") or "").strip()]
        if pending:
            api_key = os.environ.get("EMERGENT_LLM_KEY")
            if not api_key:
                raise HTTPException(503, "Çeviri servisi kullanılamıyor")
            try:
                from emergentintegrations.llm.chat import LlmChat, UserMessage
                import json as _json
                import re as _re
                payload = [{"id": m["id"], "text": m["body"][:500]} for m in pending[:30]]
                chat = LlmChat(
                    api_key=api_key, session_id=f"chat-tr-{uuid.uuid4().hex[:8]}",
                    system_message=(
                        f"Otel personeli sohbet mesajlarını {SUPPORTED_LANGS[lang]} diline çevir. "
                        "Mesaj zaten o dildeyse aynen döndür. Kısaltmaları ve otel jargonunu koru. "
                        'SADECE strict JSON array döndür: [{"id":"...","text":"çeviri"}]'
                    ),
                ).with_model("openai", "gpt-4o-mini")
                resp = await chat.send_message(UserMessage(text=_json.dumps(payload, ensure_ascii=False)))
                mjson = _re.search(r"\[.*\]", (resp or ""), _re.DOTALL)
                for item in (_json.loads(mjson.group(0)) if mjson else []):
                    mid, text = item.get("id"), (item.get("text") or "").strip()
                    if mid and text and mid in result:
                        result[mid] = text
                        await db.chat_messages.update_one(
                            {"id": mid}, {"$set": {f"translations.{lang}": text}})
            except Exception as e:
                logger.warning("Chat translate failed: %s", e)
        return {"lang": lang, "translations": {k: v for k, v in result.items() if v}}

    return router
