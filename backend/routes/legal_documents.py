"""
Legal Documents & Consents — internal policy builder with dynamic fields,
versioning, effective/expiry dates, required-acceptance tracking.

Use cases: Privacy Policy, Terms & Conditions, GDPR consent, Code of Conduct,
Health & Safety, NDAs.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import datetime, timezone, date
from typing import Dict, List, Optional
import uuid
import re
import logging

logger = logging.getLogger(__name__)


DOC_TYPES = [
    "privacy_policy", "terms_conditions", "gdpr_consent",
    "code_of_conduct", "health_safety", "nda", "other",
]

FIELD_TYPES = ["text", "textarea", "checkbox", "signature", "date", "select", "heading"]


def _slugify(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:60] or "document"


def _parse_date(s: Optional[str]):
    if not s: return None
    try:
        return date.fromisoformat(s[:10])
    except Exception:
        return None


def _effective_status(d: Dict) -> str:
    """Computed status based on dates + active flag."""
    if not d.get("active"):
        return "draft"
    today = date.today()
    eff = _parse_date(d.get("effective_date"))
    exp = _parse_date(d.get("expiry_date"))
    if exp and today > exp:
        return "expired"
    if eff and today < eff:
        return "scheduled"
    return "active"


def create_legal_documents_router(db, require_roles, get_current_user):
    router = APIRouter()

    # -------- LIST --------
    @router.get("/legal-documents")
    async def list_documents(doc_type: str = "", status: str = "", q: str = "",
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        docs = await db.legal_documents.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
        # Enrich with acceptance counts + computed status
        # Count total users who COULD accept
        all_users = await db.users.count_documents({})
        # Group acceptance counts in one pass
        pipeline = [{"$group": {"_id": "$document_id", "count": {"$sum": 1}}}]
        cursor = db.legal_acceptances.aggregate(pipeline)
        accept_map = {r["_id"]: r["count"] async for r in cursor}
        for d in docs:
            d["computed_status"] = _effective_status(d)
            d["acceptance_count"] = accept_map.get(d["id"], 0)
            d["total_users"] = all_users
            d["acceptance_pct"] = round(100 * accept_map.get(d["id"], 0) / all_users, 1) if all_users else 0
            d["field_count"] = len(d.get("fields", []))
        if doc_type:
            docs = [d for d in docs if d.get("doc_type") == doc_type]
        if status:
            docs = [d for d in docs if d["computed_status"] == status]
        if q:
            ql = q.lower()
            docs = [d for d in docs
                    if ql in (d.get("title") or "").lower()
                    or ql in (d.get("description") or "").lower()
                    or ql in (d.get("code") or "").lower()]
        return docs

    # -------- STATS --------
    @router.get("/legal-documents/stats")
    async def stats(current_user: dict = Depends(require_roles("admin", "manager"))):
        docs = await db.legal_documents.find({}, {"_id": 0}).to_list(500)
        all_users = await db.users.count_documents({})
        active = required_active = 0
        expiring_30 = 0
        today = date.today()
        for d in docs:
            s = _effective_status(d)
            if s == "active":
                active += 1
                if d.get("required"):
                    required_active += 1
            exp = _parse_date(d.get("expiry_date"))
            if exp and 0 <= (exp - today).days <= 30 and s == "active":
                expiring_30 += 1
        total_acceptances = await db.legal_acceptances.count_documents({})
        return {
            "total_documents": len(docs),
            "active": active,
            "required_active": required_active,
            "expiring_30_days": expiring_30,
            "total_acceptances": total_acceptances,
            "total_users": all_users,
        }

    # -------- GET ONE --------
    @router.get("/legal-documents/{doc_id}")
    async def get_document(doc_id: str,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        d = await db.legal_documents.find_one({"id": doc_id}, {"_id": 0})
        if not d:
            raise HTTPException(404, "Document not found")
        d["computed_status"] = _effective_status(d)
        return d

    # -------- CREATE --------
    @router.post("/legal-documents")
    async def create_document(data: Dict,
                              current_user: dict = Depends(require_roles("admin"))):
        title = (data.get("title") or "").strip()
        if not title:
            raise HTTPException(400, "Title required")
        doc_type = data.get("doc_type") or "other"
        if doc_type not in DOC_TYPES:
            raise HTTPException(400, f"doc_type must be one of {DOC_TYPES}")
        code = (data.get("code") or "").strip().upper() or f"{doc_type.upper().replace('_','-')}-{_slugify(title)[:30]}"
        # Validate fields
        fields: List[Dict] = data.get("fields") or []
        clean_fields = []
        for f in fields:
            t = f.get("type")
            if t not in FIELD_TYPES:
                raise HTTPException(400, f"Invalid field type: {t}")
            clean_fields.append({
                "id": f.get("id") or str(uuid.uuid4()),
                "type": t,
                "label": f.get("label") or "",
                "placeholder": f.get("placeholder") or "",
                "required": bool(f.get("required")),
                "options": f.get("options") or [],  # for select
                "content": f.get("content") or "",  # for heading/static text
            })
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "id": str(uuid.uuid4()),
            "title": title,
            "code": code,
            "description": data.get("description") or "",
            "doc_type": doc_type,
            "version": (data.get("version") or "1.0").strip(),
            "effective_date": data.get("effective_date") or "",
            "expiry_date": data.get("expiry_date") or "",
            "active": bool(data.get("active", True)),
            "required": bool(data.get("required", False)),
            "fields": clean_fields,
            "parent_id": data.get("parent_id") or "",  # links to previous version
            "created_at": now,
            "created_by": current_user.get("name", ""),
            "updated_at": now,
        }
        await db.legal_documents.insert_one(doc)
        doc.pop("_id", None)
        return doc

    # -------- UPDATE --------
    @router.put("/legal-documents/{doc_id}")
    async def update_document(doc_id: str, data: Dict,
                              current_user: dict = Depends(require_roles("admin"))):
        existing = await db.legal_documents.find_one({"id": doc_id}, {"_id": 0})
        if not existing:
            raise HTTPException(404, "Document not found")
        # If there are acceptances, block substantive edits (force new version)
        accept_count = await db.legal_acceptances.count_documents({"document_id": doc_id})
        patch: Dict = {}
        safe_fields = {"active", "expiry_date"}
        full_fields = safe_fields | {
            "title", "code", "description", "doc_type", "version",
            "effective_date", "required", "fields",
        }
        for k in (full_fields if accept_count == 0 else safe_fields):
            if k in data:
                patch[k] = data[k]
        if not patch:
            raise HTTPException(400, "Document has acceptances — create a new version instead of editing")
        if "doc_type" in patch and patch["doc_type"] not in DOC_TYPES:
            raise HTTPException(400, "Invalid doc_type")
        if "fields" in patch:
            clean_fields = []
            for f in patch["fields"] or []:
                t = f.get("type")
                if t not in FIELD_TYPES:
                    raise HTTPException(400, f"Invalid field type: {t}")
                clean_fields.append({
                    "id": f.get("id") or str(uuid.uuid4()),
                    "type": t,
                    "label": f.get("label") or "",
                    "placeholder": f.get("placeholder") or "",
                    "required": bool(f.get("required")),
                    "options": f.get("options") or [],
                    "content": f.get("content") or "",
                })
            patch["fields"] = clean_fields
        patch["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.legal_documents.update_one({"id": doc_id}, {"$set": patch})
        return {"ok": True, "locked_edits": accept_count > 0}

    # -------- NEW VERSION --------
    @router.post("/legal-documents/{doc_id}/new-version")
    async def new_version(doc_id: str,
                          current_user: dict = Depends(require_roles("admin"))):
        existing = await db.legal_documents.find_one({"id": doc_id}, {"_id": 0})
        if not existing:
            raise HTTPException(404, "Document not found")
        # bump version: 1.0 -> 1.1, 1.9 -> 2.0
        cur = existing.get("version", "1.0")
        try:
            parts = cur.split(".")
            major = int(parts[0]); minor = int(parts[1]) if len(parts) > 1 else 0
            minor += 1
            if minor >= 10:
                major += 1; minor = 0
            new_ver = f"{major}.{minor}"
        except Exception:
            new_ver = "1.1"
        now = datetime.now(timezone.utc).isoformat()
        clone = {**existing,
                 "id": str(uuid.uuid4()),
                 "version": new_ver,
                 "parent_id": existing["id"],
                 "active": False,         # draft new version
                 "created_at": now,
                 "created_by": current_user.get("name", ""),
                 "updated_at": now}
        await db.legal_documents.insert_one(clone)
        clone.pop("_id", None)
        return clone

    # -------- DELETE --------
    @router.delete("/legal-documents/{doc_id}")
    async def delete_document(doc_id: str,
                              current_user: dict = Depends(require_roles("admin"))):
        accept_count = await db.legal_acceptances.count_documents({"document_id": doc_id})
        if accept_count > 0:
            raise HTTPException(400, "Document has acceptances — deactivate instead of deleting")
        r = await db.legal_documents.delete_one({"id": doc_id})
        if r.deleted_count == 0:
            raise HTTPException(404, "Not found")
        return {"ok": True}

    # -------- LIST ACCEPTANCES --------
    @router.get("/legal-documents/{doc_id}/acceptances")
    async def list_acceptances(doc_id: str,
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        rows = await db.legal_acceptances.find({"document_id": doc_id}, {"_id": 0}) \
                                          .sort("accepted_at", -1).to_list(1000)
        return rows

    # -------- PENDING DOCS FOR CURRENT USER --------
    @router.get("/legal-documents/pending/me")
    async def pending_for_me(current_user: dict = Depends(get_current_user)):
        """All active+required docs this user has not yet accepted (or where version changed)."""
        active_required = await db.legal_documents.find(
            {"active": True, "required": True}, {"_id": 0}
        ).to_list(200)
        active_required = [d for d in active_required if _effective_status(d) == "active"]
        user_id = current_user.get("id")
        accepted = await db.legal_acceptances.find(
            {"user_id": user_id}, {"_id": 0, "document_id": 1, "document_version": 1}
        ).to_list(500)
        accepted_map: Dict[str, str] = {a["document_id"]: a.get("document_version", "") for a in accepted}
        pending = []
        for d in active_required:
            prev = accepted_map.get(d["id"])
            if prev != d.get("version"):
                pending.append(d)
        return pending

    # -------- ACCEPT --------
    @router.post("/legal-documents/{doc_id}/accept")
    async def accept_document(doc_id: str, data: Dict, request: Request,
                              current_user: dict = Depends(get_current_user)):
        d = await db.legal_documents.find_one({"id": doc_id}, {"_id": 0})
        if not d:
            raise HTTPException(404, "Document not found")
        if not d.get("active"):
            raise HTTPException(400, "Document is not active")
        # Validate required fields
        responses = data.get("responses") or {}
        for f in d.get("fields", []):
            if f.get("required") and f["type"] not in ("heading",):
                val = responses.get(f["id"])
                if f["type"] == "checkbox":
                    if not val:
                        raise HTTPException(400, f"Required: {f.get('label') or f['id']}")
                elif not val or (isinstance(val, str) and not val.strip()):
                    raise HTTPException(400, f"Required: {f.get('label') or f['id']}")
        now = datetime.now(timezone.utc).isoformat()
        client_ip = request.client.host if request.client else ""
        doc = {
            "id": str(uuid.uuid4()),
            "document_id": doc_id,
            "document_code": d.get("code", ""),
            "document_title": d.get("title", ""),
            "document_version": d.get("version", ""),
            "user_id": current_user.get("id"),
            "user_name": current_user.get("name", ""),
            "user_email": current_user.get("email", ""),
            "user_role": current_user.get("role", ""),
            "responses": responses,
            "accepted_at": now,
            "ip_address": client_ip,
        }
        # Upsert so re-accepting latest version replaces prior record for that doc
        await db.legal_acceptances.update_one(
            {"document_id": doc_id, "user_id": current_user.get("id")},
            {"$set": doc}, upsert=True
        )
        return {"ok": True, "accepted_at": now}

    return router
