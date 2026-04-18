"""
Staff Onboarding — Right-to-Work verification.
New users must complete: passport upload + address proof + HMRC starter checklist
+ contract signing before their account is activated and they can use the dashboard.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from datetime import datetime, timezone
from typing import Dict, Optional
import os
import uuid
import logging

logger = logging.getLogger(__name__)

UPLOAD_DIR = "/app/backend/uploads/onboarding"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# HMRC Starter Checklist statements (https://www.gov.uk/new-employee)
HMRC_STATEMENTS = {
    "A": "This is my first job since 6 April and I have not been receiving taxable Jobseeker's Allowance, Employment and Support Allowance, taxable Incapacity Benefit, State or Occupational Pension.",
    "B": "This is now my only job but since 6 April I have had another job, or received taxable Jobseeker's Allowance, Employment and Support Allowance or taxable Incapacity Benefit. I do not receive a State or Occupational Pension.",
    "C": "As well as my new job, I have another job or receive a State or Occupational Pension.",
}


def _onboarding_status(doc: Dict) -> Dict:
    """Compute progress + overall status from individual task flags."""
    tasks = {
        "passport":    bool(doc.get("passport_uploaded")),
        "address":     bool(doc.get("address_proof_uploaded")),
        "hmrc":        bool(doc.get("hmrc_submitted")),
        "contract":    bool(doc.get("contract_signed")),
    }
    done = sum(1 for v in tasks.values() if v)
    total = len(tasks)
    return {
        "tasks": tasks,
        "done": done,
        "total": total,
        "pct": round(100 * done / total),
        "complete": done == total,
    }


def create_staff_onboarding_router(db, require_roles, get_current_user):
    router = APIRouter()

    # -------- GET MY STATUS --------
    @router.get("/staff-onboarding/me")
    async def my_onboarding(current_user: dict = Depends(get_current_user)):
        user_id = current_user.get("id")
        # Fetch existing doc or build a fresh one
        doc = await db.staff_onboarding.find_one({"user_id": user_id}, {"_id": 0})
        if not doc:
            doc = {
                "user_id": user_id,
                "user_name": current_user.get("name", ""),
                "user_email": current_user.get("email", ""),
                "passport_uploaded": False,
                "passport_filename": "",
                "address_proof_uploaded": False,
                "address_proof_filename": "",
                "hmrc_submitted": False,
                "hmrc_data": {},
                "contract_signed": False,
                "contract_id": "",
                "activated": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.staff_onboarding.insert_one({**doc})

        # Auto-check contract_signed status by looking up signed contracts for this user's email
        if not doc.get("contract_signed"):
            sc = await db.staff_contracts.find_one(
                {"staff_email": current_user.get("email"), "status": "signed"}, {"_id": 0, "id": 1}
            )
            if sc:
                await db.staff_onboarding.update_one(
                    {"user_id": user_id},
                    {"$set": {"contract_signed": True, "contract_id": sc["id"]}}
                )
                doc["contract_signed"] = True
                doc["contract_id"] = sc["id"]

        # Pull up-to-date user activation state
        user_doc = await db.users.find_one({"id": user_id}, {"_id": 0, "is_activated": 1})
        doc["activated"] = bool((user_doc or {}).get("is_activated", True))

        doc["progress"] = _onboarding_status(doc)
        doc["hmrc_statements"] = HMRC_STATEMENTS
        return doc

    # -------- UPLOAD PASSPORT --------
    @router.post("/staff-onboarding/upload/passport")
    async def upload_passport(file: UploadFile = File(...),
                              current_user: dict = Depends(get_current_user)):
        user_id = current_user.get("id")
        ext = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else "jpg"
        if ext not in {"jpg", "jpeg", "png", "pdf", "heic", "webp"}:
            raise HTTPException(400, "Unsupported file type")
        filename = f"passport_{user_id}_{uuid.uuid4().hex[:8]}.{ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)
        content = await file.read()
        with open(filepath, "wb") as f:
            f.write(content)

        await db.staff_onboarding.update_one(
            {"user_id": user_id},
            {"$set": {
                "passport_uploaded": True,
                "passport_filename": file.filename,
                "passport_path": filepath,
                "passport_url": f"/api/uploads/onboarding/{filename}",
                "passport_uploaded_at": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )
        return {"ok": True, "filename": file.filename}

    # -------- UPLOAD ADDRESS PROOF --------
    @router.post("/staff-onboarding/upload/address")
    async def upload_address(file: UploadFile = File(...),
                             current_user: dict = Depends(get_current_user)):
        user_id = current_user.get("id")
        ext = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else "jpg"
        if ext not in {"jpg", "jpeg", "png", "pdf", "heic", "webp"}:
            raise HTTPException(400, "Unsupported file type")
        filename = f"address_{user_id}_{uuid.uuid4().hex[:8]}.{ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)
        content = await file.read()
        with open(filepath, "wb") as f:
            f.write(content)

        await db.staff_onboarding.update_one(
            {"user_id": user_id},
            {"$set": {
                "address_proof_uploaded": True,
                "address_proof_filename": file.filename,
                "address_proof_path": filepath,
                "address_proof_url": f"/api/uploads/onboarding/{filename}",
                "address_proof_uploaded_at": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )
        return {"ok": True, "filename": file.filename}

    # -------- SUBMIT HMRC CHECKLIST --------
    @router.post("/staff-onboarding/hmrc")
    async def submit_hmrc(data: Dict,
                          current_user: dict = Depends(get_current_user)):
        user_id = current_user.get("id")
        # Validate
        required = ["first_name", "last_name", "dob", "ni_number", "address",
                    "postcode", "start_date", "statement"]
        missing = [k for k in required if not (data.get(k) or "").strip()] if isinstance(data, dict) else required
        if missing:
            raise HTTPException(400, f"Missing fields: {', '.join(missing)}")
        if data["statement"] not in HMRC_STATEMENTS:
            raise HTTPException(400, "Statement must be A, B or C")
        # NI format soft check (UK NI: 2 letters + 6 digits + 1 letter)
        ni = data["ni_number"].replace(" ", "").upper()
        if len(ni) != 9:
            raise HTTPException(400, "NI number should be 9 characters (e.g. AB123456C)")

        hmrc_payload = {
            "first_name": data["first_name"].strip(),
            "last_name": data["last_name"].strip(),
            "dob": data["dob"],
            "ni_number": ni,
            "address": data["address"].strip(),
            "postcode": data["postcode"].strip().upper(),
            "start_date": data["start_date"],
            "statement": data["statement"],
            "student_loan": bool(data.get("student_loan", False)),
            "student_loan_plan": data.get("student_loan_plan", "") if data.get("student_loan") else "",
            "postgrad_loan": bool(data.get("postgrad_loan", False)),
            "gender": data.get("gender", ""),
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.staff_onboarding.update_one(
            {"user_id": user_id},
            {"$set": {"hmrc_submitted": True, "hmrc_data": hmrc_payload}},
            upsert=True,
        )
        return {"ok": True}

    # -------- ACTIVATE MY ACCOUNT (self-service, requires all tasks done) --------
    @router.post("/staff-onboarding/complete")
    async def complete_onboarding(current_user: dict = Depends(get_current_user)):
        user_id = current_user.get("id")
        doc = await db.staff_onboarding.find_one({"user_id": user_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "No onboarding record found")
        progress = _onboarding_status(doc)
        if not progress["complete"]:
            missing = [k for k, v in progress["tasks"].items() if not v]
            raise HTTPException(400, f"Incomplete tasks: {', '.join(missing)}")

        now = datetime.now(timezone.utc).isoformat()
        await db.staff_onboarding.update_one(
            {"user_id": user_id},
            {"$set": {"completed_at": now}}
        )
        # Activate user
        await db.users.update_one(
            {"id": user_id},
            {"$set": {"is_activated": True, "activated_at": now}}
        )
        return {"ok": True, "activated": True}

    # -------- ADMIN: LIST ALL ONBOARDINGS --------
    @router.get("/staff-onboarding/list")
    async def list_onboardings(status: str = "",
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        docs = await db.staff_onboarding.find({}, {"_id": 0}) \
                                         .sort("created_at", -1).to_list(500)
        # Enrich with user.is_activated
        out = []
        for d in docs:
            u = await db.users.find_one({"id": d.get("user_id")}, {"_id": 0, "is_activated": 1, "role": 1})
            d["progress"] = _onboarding_status(d)
            d["user_role"] = (u or {}).get("role", "")
            d["activated"] = bool((u or {}).get("is_activated", True))
            if status == "pending" and d["activated"]:
                continue
            if status == "activated" and not d["activated"]:
                continue
            if status == "complete" and not d["progress"]["complete"]:
                continue
            if status == "incomplete" and d["progress"]["complete"]:
                continue
            out.append(d)
        return out

    # -------- ADMIN: ACTIVATE A USER MANUALLY --------
    @router.post("/staff-onboarding/admin-activate/{user_id}")
    async def admin_activate(user_id: str,
                             current_user: dict = Depends(require_roles("admin"))):
        u = await db.users.find_one({"id": user_id}, {"_id": 0})
        if not u:
            raise HTTPException(404, "User not found")
        now = datetime.now(timezone.utc).isoformat()
        await db.users.update_one(
            {"id": user_id},
            {"$set": {"is_activated": True, "activated_at": now, "activated_by": current_user.get("name", "")}}
        )
        return {"ok": True}

    # -------- ADMIN: DEACTIVATE --------
    @router.post("/staff-onboarding/admin-deactivate/{user_id}")
    async def admin_deactivate(user_id: str,
                               current_user: dict = Depends(require_roles("admin"))):
        await db.users.update_one(
            {"id": user_id},
            {"$set": {"is_activated": False,
                      "deactivated_at": datetime.now(timezone.utc).isoformat()}}
        )
        return {"ok": True}

    return router
