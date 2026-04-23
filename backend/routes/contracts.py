"""
Staff Contracts — digital employment contracts with e-signature.
Covers: contract lifecycle (draft/active/expired/terminated), signing links,
probation tracking, notice period, hours, pay, total monthly cost.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from datetime import datetime, timezone, timedelta, date
from typing import Dict, Optional, List
import secrets
import uuid
import base64
import logging

logger = logging.getLogger(__name__)

CONTRACT_TYPES = ["full_time", "part_time", "casual", "zero_hours", "freelance", "fixed_term"]
CONTRACT_STATUSES = ["draft", "sent", "signed", "active", "expired", "terminated"]


def _parse_date(s: Optional[str]):
    if not s: return None
    try:
        return date.fromisoformat(s[:10])
    except Exception:
        return None


def _compute_status(c: Dict) -> str:
    """Dynamically refine stored status based on dates."""
    stored = c.get("status", "draft")
    if stored in ("draft", "sent", "terminated"):
        return stored
    today = date.today()
    end = _parse_date(c.get("end_date"))
    if end and today > end:
        return "expired"
    return stored  # signed | active


def _monthly_cost(c: Dict) -> float:
    """Rough monthly cost: hours_per_week * hourly_rate * 4.333, or salary/12."""
    if c.get("salary_annual"):
        return round(float(c["salary_annual"]) / 12.0, 2)
    hpw = float(c.get("hours_per_week") or 0)
    rate = float(c.get("hourly_rate") or 0)
    return round(hpw * rate * 4.333, 2)


def create_contracts_router(db, require_roles):
    router = APIRouter()

    # -------- LIST --------
    @router.get("/contracts/{property_id}")
    async def list_contracts(property_id: str, status: str = "", q: str = "",
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        query: Dict = {}
        if property_id != "all":
            query["property_id"] = property_id
        docs = await db.staff_contracts.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
        for c in docs:
            c["computed_status"] = _compute_status(c)
            c["monthly_cost"] = _monthly_cost(c)
            end = _parse_date(c.get("end_date"))
            if end:
                c["days_to_end"] = (end - date.today()).days
            probation = _parse_date(c.get("probation_end"))
            c["on_probation"] = bool(probation and probation >= date.today())

        if status:
            docs = [c for c in docs if c["computed_status"] == status]
        if q:
            ql = q.lower()
            docs = [c for c in docs
                    if ql in (c.get("staff_name") or "").lower()
                    or ql in (c.get("staff_email") or "").lower()
                    or ql in (c.get("role") or "").lower()]
        return docs

    # -------- STATS --------
    @router.get("/contracts/stats/{property_id}")
    async def stats(property_id: str,
                    current_user: dict = Depends(require_roles("admin", "manager"))):
        query: Dict = {}
        if property_id != "all":
            query["property_id"] = property_id
        docs = await db.staff_contracts.find(query, {"_id": 0}).to_list(500)
        total = len(docs)
        by_status: Dict[str, int] = {}
        expiring_30 = 0
        probation = 0
        monthly_cost = 0.0
        for c in docs:
            s = _compute_status(c)
            by_status[s] = by_status.get(s, 0) + 1
            end = _parse_date(c.get("end_date"))
            if end and 0 <= (end - date.today()).days <= 30 and s in ("active", "signed"):
                expiring_30 += 1
            prob = _parse_date(c.get("probation_end"))
            if prob and prob >= date.today() and s in ("active", "signed"):
                probation += 1
            if s in ("active", "signed"):
                monthly_cost += _monthly_cost(c)
        return {
            "total": total,
            "by_status": by_status,
            "active": by_status.get("active", 0) + by_status.get("signed", 0),
            "expiring_30_days": expiring_30,
            "on_probation": probation,
            "monthly_cost": round(monthly_cost, 2),
            "annual_cost": round(monthly_cost * 12, 2),
        }

    # -------- CREATE --------
    @router.post("/contracts")
    async def create_contract(data: Dict,
                              current_user: dict = Depends(require_roles("admin"))):
        if data.get("contract_type") not in CONTRACT_TYPES:
            raise HTTPException(400, f"contract_type must be one of {CONTRACT_TYPES}")
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id") or "all",
            "user_id": data.get("user_id") or "",
            "staff_name": data.get("staff_name") or "",
            "staff_email": data.get("staff_email") or "",
            "role": data.get("role") or "",
            "department": data.get("department") or "",
            "contract_type": data["contract_type"],
            "start_date": data.get("start_date") or "",
            "end_date": data.get("end_date") or "",  # empty = permanent
            "probation_end": data.get("probation_end") or "",
            "hours_per_week": float(data.get("hours_per_week") or 0),
            "hourly_rate": float(data.get("hourly_rate") or 0),
            "salary_annual": float(data.get("salary_annual") or 0),
            "notice_period_days": int(data.get("notice_period_days") or 30),
            "holiday_entitlement_days": int(data.get("holiday_entitlement_days") or 28),
            "terms": data.get("terms") or "",
            "status": "draft",
            "sign_token": "",
            "signed_at": "",
            "signature": "",
            "signed_ip": "",
            "created_at": now,
            "created_by": current_user.get("name", ""),
            "updated_at": now,
        }
        await db.staff_contracts.insert_one(doc)
        doc.pop("_id", None)
        return doc

    # -------- UPDATE --------
    @router.put("/contracts/{contract_id}")
    async def update_contract(contract_id: str, data: Dict,
                              current_user: dict = Depends(require_roles("admin"))):
        existing = await db.staff_contracts.find_one({"id": contract_id}, {"_id": 0})
        if not existing:
            raise HTTPException(404, "Contract not found")
        if existing.get("status") == "signed":
            raise HTTPException(400, "Cannot edit a signed contract — terminate and create a new one")
        allowed = {"staff_name", "staff_email", "role", "department", "contract_type",
                   "start_date", "end_date", "probation_end", "hours_per_week",
                   "hourly_rate", "salary_annual", "notice_period_days",
                   "holiday_entitlement_days", "terms", "status"}
        patch = {k: v for k, v in data.items() if k in allowed}
        if "contract_type" in patch and patch["contract_type"] not in CONTRACT_TYPES:
            raise HTTPException(400, "Invalid contract_type")
        for k in ("hours_per_week", "hourly_rate", "salary_annual"):
            if k in patch: patch[k] = float(patch[k] or 0)
        for k in ("notice_period_days", "holiday_entitlement_days"):
            if k in patch: patch[k] = int(patch[k] or 0)
        patch["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.staff_contracts.update_one({"id": contract_id}, {"$set": patch})
        return {"ok": True}

    # -------- EXTEND END DATE (signed/active contracts only) --------
    @router.post("/contracts/{contract_id}/extend")
    async def extend_contract(contract_id: str, data: Dict,
                              current_user: dict = Depends(require_roles("admin"))):
        """Extend end_date on a signed/active contract without breaking signature integrity."""
        existing = await db.staff_contracts.find_one({"id": contract_id}, {"_id": 0})
        if not existing:
            raise HTTPException(404, "Contract not found")
        status = _compute_status(existing)
        if status not in ("signed", "active", "expired"):
            raise HTTPException(400, f"Can only extend signed/active/expired contracts (current: {status})")
        new_end = (data or {}).get("new_end_date")
        parsed = _parse_date(new_end)
        if not parsed:
            raise HTTPException(400, "new_end_date required in YYYY-MM-DD format")
        start = _parse_date(existing.get("start_date"))
        if start and parsed < start:
            raise HTTPException(400, "End date cannot be earlier than start date")
        now = datetime.now(timezone.utc).isoformat()
        history = existing.get("extensions") or []
        history.append({
            "extended_at": now,
            "extended_by": current_user.get("name", ""),
            "previous_end_date": existing.get("end_date") or "",
            "new_end_date": new_end,
            "reason": (data or {}).get("reason", ""),
        })
        # If contract was expired and new end is in the future, flip back to active
        status_update = {}
        if status == "expired" and parsed >= date.today():
            status_update["status"] = "active"
        await db.staff_contracts.update_one(
            {"id": contract_id},
            {"$set": {"end_date": new_end, "extensions": history, "updated_at": now, **status_update}}
        )
        return {"ok": True, "new_end_date": new_end, "extension_count": len(history)}

    # -------- DELETE --------
    @router.delete("/contracts/{contract_id}")
    async def delete_contract(contract_id: str,
                              current_user: dict = Depends(require_roles("admin"))):
        existing = await db.staff_contracts.find_one({"id": contract_id}, {"_id": 0})
        if not existing:
            raise HTTPException(404, "Contract not found")
        if existing.get("status") == "signed":
            raise HTTPException(400, "Cannot delete signed contract — terminate instead")
        await db.staff_contracts.delete_one({"id": contract_id})
        return {"ok": True}
    # -------- UPLOAD FILE (signed PDF, ID, visa, etc.) --------
    @router.post("/contracts/{contract_id}/upload-file")
    async def upload_contract_file(contract_id: str, file: UploadFile = File(...),
                                   current_user: dict = Depends(require_roles("admin", "manager"))):
        existing = await db.staff_contracts.find_one({"id": contract_id}, {"_id": 0})
        if not existing:
            raise HTTPException(404, "Contract not found")
        if not file.filename:
            raise HTTPException(400, "No file uploaded")
        content = await file.read()
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(400, "File too large (max 10MB)")
        attachment = {
            "id": str(uuid.uuid4()),
            "filename": file.filename,
            "content_type": file.content_type or "application/octet-stream",
            "size": len(content),
            "data_base64": base64.b64encode(content).decode(),
            "uploaded_by": current_user.get("name", ""),
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }
        files = existing.get("attachments") or []
        files.append(attachment)
        await db.staff_contracts.update_one({"id": contract_id},
            {"$set": {"attachments": files, "updated_at": attachment["uploaded_at"]}})
        return {"ok": True, "attachment": {k: v for k, v in attachment.items() if k != "data_base64"}}

    @router.get("/contracts/{contract_id}/attachments")
    async def list_attachments(contract_id: str,
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        c = await db.staff_contracts.find_one({"id": contract_id}, {"_id": 0, "attachments": 1})
        if not c:
            raise HTTPException(404, "Contract not found")
        files = c.get("attachments") or []
        return [{k: v for k, v in f.items() if k != "data_base64"} for f in files]

    @router.get("/contracts/{contract_id}/attachments/{attachment_id}")
    async def download_attachment(contract_id: str, attachment_id: str,
                                  current_user: dict = Depends(require_roles("admin", "manager"))):
        c = await db.staff_contracts.find_one({"id": contract_id}, {"_id": 0, "attachments": 1})
        if not c:
            raise HTTPException(404, "Contract not found")
        for att in (c.get("attachments") or []):
            if att.get("id") == attachment_id:
                return att
        raise HTTPException(404, "Attachment not found")

    @router.delete("/contracts/{contract_id}/attachments/{attachment_id}")
    async def delete_attachment(contract_id: str, attachment_id: str,
                                current_user: dict = Depends(require_roles("admin"))):
        c = await db.staff_contracts.find_one({"id": contract_id}, {"_id": 0})
        if not c:
            raise HTTPException(404, "Contract not found")
        files = [f for f in (c.get("attachments") or []) if f.get("id") != attachment_id]
        await db.staff_contracts.update_one({"id": contract_id}, {"$set": {"attachments": files}})
        return {"ok": True}



    # -------- SEND FOR SIGNATURE --------
    @router.post("/contracts/{contract_id}/send")
    async def send_for_signature(contract_id: str, request: Request,
                                 current_user: dict = Depends(require_roles("admin"))):
        existing = await db.staff_contracts.find_one({"id": contract_id}, {"_id": 0})
        if not existing:
            raise HTTPException(404, "Contract not found")
        if existing.get("status") == "signed":
            raise HTTPException(400, "Already signed")
        token = secrets.token_urlsafe(24)
        now = datetime.now(timezone.utc).isoformat()
        await db.staff_contracts.update_one(
            {"id": contract_id},
            {"$set": {"sign_token": token, "status": "sent", "sent_at": now, "updated_at": now}}
        )
        # Build public link
        import os as _os
        host_url = str(request.base_url).rstrip("/")
        base_url = _os.environ.get("BASE_URL", _os.environ.get("REACT_APP_BACKEND_URL", host_url))
        sign_url = f"{base_url}/contract/sign/{token}"
        return {"ok": True, "token": token, "sign_url": sign_url}

    # -------- TERMINATE --------
    @router.post("/contracts/{contract_id}/terminate")
    async def terminate_contract(contract_id: str, data: Dict = None,
                                 current_user: dict = Depends(require_roles("admin"))):
        data = data or {}
        existing = await db.staff_contracts.find_one({"id": contract_id}, {"_id": 0})
        if not existing:
            raise HTTPException(404, "Contract not found")
        now = datetime.now(timezone.utc)
        await db.staff_contracts.update_one(
            {"id": contract_id},
            {"$set": {
                "status": "terminated",
                "terminated_at": now.isoformat(),
                "terminated_by": current_user.get("name", ""),
                "termination_reason": data.get("reason", ""),
                "effective_end_date": data.get("effective_end_date") or now.date().isoformat(),
                "updated_at": now.isoformat(),
            }}
        )
        return {"ok": True}

    # -------- PUBLIC: GET CONTRACT BY SIGN TOKEN --------
    @router.get("/contracts/sign/{token}")
    async def get_sign_doc(token: str):
        c = await db.staff_contracts.find_one({"sign_token": token}, {"_id": 0})
        if not c:
            raise HTTPException(404, "Invalid or expired signing link")
        # Also return hotel name for header
        prop = None
        if c.get("property_id") and c["property_id"] != "all":
            prop = await db.properties.find_one({"id": c["property_id"]}, {"_id": 0, "name": 1})
        return {
            "contract": c,
            "hotel_name": (prop or {}).get("name", "Hotel"),
            "already_signed": c.get("status") == "signed",
        }

    # -------- PUBLIC: SIGN CONTRACT --------
    @router.post("/contracts/sign/{token}")
    async def sign_contract(token: str, data: Dict, request: Request):
        c = await db.staff_contracts.find_one({"sign_token": token}, {"_id": 0})
        if not c:
            raise HTTPException(404, "Invalid or expired signing link")
        if c.get("status") == "signed":
            raise HTTPException(400, "Already signed")
        signature = (data.get("signature") or "").strip()
        full_name = (data.get("full_name") or "").strip()
        if not signature or not full_name:
            raise HTTPException(400, "Signature and full_name required")
        if not data.get("accept_terms"):
            raise HTTPException(400, "Must accept terms")
        now = datetime.now(timezone.utc).isoformat()
        client_ip = request.client.host if request.client else ""
        await db.staff_contracts.update_one(
            {"sign_token": token},
            {"$set": {
                "status": "signed",
                "signed_at": now,
                "signature": signature,           # base64 PNG or typed name
                "signed_full_name": full_name,
                "signed_ip": client_ip,
                "updated_at": now,
            }}
        )
        return {"ok": True, "signed_at": now}

    return router
