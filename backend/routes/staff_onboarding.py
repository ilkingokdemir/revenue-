"""
Staff Onboarding — Right-to-Work verification.
New users must complete: passport upload + address proof + HMRC starter checklist
+ contract signing before their account is activated and they can use the dashboard.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from datetime import datetime, timezone
from typing import Dict, Optional
import os
import io
import uuid
import zipfile
import base64
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


def create_staff_onboarding_router(db, require_roles, get_current_user, resend_lib=None):
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
        # Required fields per HMRC 09/22 Starter Checklist
        required = ["last_name", "first_names", "sex", "dob",
                    "home_address", "postcode", "start_date",
                    "statement",
                    "declaration_full_name", "declaration_signature", "declaration_date"]
        missing = [k for k in required if not (data.get(k) or "").strip()]
        if missing:
            raise HTTPException(400, f"Missing fields: {', '.join(missing)}")

        if data["sex"] not in ("male", "female"):
            raise HTTPException(400, "Sex must be male or female (as shown on birth certificate)")
        if data["statement"] not in HMRC_STATEMENTS:
            raise HTTPException(400, "Statement must be A, B or C")
        if not data.get("declaration_confirmed"):
            raise HTTPException(400, "You must confirm the declaration")

        # NI soft validation (optional, if provided)
        ni = (data.get("ni_number") or "").replace(" ", "").upper()
        if ni and len(ni) != 9:
            raise HTTPException(400, "NI number should be 9 characters (e.g. AB123456C)")

        # Student loan plans: list of plan_1 / plan_2 / plan_4 / postgraduate
        loan_plans = data.get("student_loan_plans") or []
        valid_plans = {"plan_1", "plan_2", "plan_4", "postgraduate"}
        loan_plans = [p for p in loan_plans if p in valid_plans]
        has_loan = bool(data.get("has_loan"))

        hmrc_payload = {
            # Personal details
            "last_name": data["last_name"].strip(),
            "first_names": data["first_names"].strip(),
            "sex": data["sex"],
            "dob": data["dob"],
            "home_address": data["home_address"].strip(),
            "postcode": data["postcode"].strip().upper(),
            "country": (data.get("country") or "United Kingdom").strip(),
            "ni_number": ni,
            "start_date": data["start_date"],
            # Employee statement decision-tree answers
            "q8_another_job":        bool(data.get("q8_another_job", False)),
            "q9_receives_pension":   bool(data.get("q9_receives_pension", False)),
            "q10_recent_payments":   bool(data.get("q10_recent_payments", False)),
            "statement":             data["statement"],
            # Student loan
            "has_loan":              has_loan,
            "still_studying":        bool(data.get("still_studying", False)),
            "student_loan_plans":    loan_plans,
            # Declaration
            "declaration_full_name": data["declaration_full_name"].strip(),
            "declaration_signature": data["declaration_signature"].strip(),
            "declaration_date":      data["declaration_date"],
            "submitted_at":          datetime.now(timezone.utc).isoformat(),
            # Back-compat aliases for admin panel
            "first_name":            data["first_names"].split()[0] if data["first_names"].split() else data["first_names"].strip(),
            "gender":                data["sex"],
            "address":               data["home_address"].strip(),
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

    # -------- HMRC PDF GENERATOR (shared) --------
    def _build_hmrc_pdf(doc: Dict) -> bytes:
        """Generate an authentic-looking HMRC Starter Checklist PDF from onboarding data."""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import mm
            from reportlab.lib import colors
            from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                            Table, TableStyle, PageBreak)
        except Exception as e:
            logger.error(f"reportlab not available: {e}")
            raise HTTPException(500, "PDF library unavailable")

        h = doc.get("hmrc_data") or {}
        buf = io.BytesIO()
        pdf = SimpleDocTemplate(buf, pagesize=A4,
                                leftMargin=18 * mm, rightMargin=18 * mm,
                                topMargin=15 * mm, bottomMargin=15 * mm,
                                title="HMRC Starter Checklist")
        styles = getSampleStyleSheet()
        h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=16, spaceAfter=2 * mm, textColor=colors.HexColor("#0B5394"))
        h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=11, spaceBefore=4 * mm, spaceAfter=1 * mm,
                            textColor=colors.HexColor("#0B5394"))
        body = ParagraphStyle("body", parent=styles["Normal"], fontSize=9, leading=12)
        small = ParagraphStyle("small", parent=styles["Normal"], fontSize=7, leading=9, textColor=colors.grey)

        story = []
        story.append(Paragraph("HM Revenue & Customs", h1))
        story.append(Paragraph("Starter checklist · HMRC 09/22", small))
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph(
            "Tell your employer of your circumstances so that you do not pay too much or too little tax.", body))
        story.append(Spacer(1, 3 * mm))

        def row(label, value):
            return [Paragraph(f"<b>{label}</b>", body), Paragraph(str(value or "—"), body)]

        # Personal details
        story.append(Paragraph("Employee's personal details", h2))
        plans = ", ".join(h.get("student_loan_plans") or []) or "—"
        pers = [
            row("1. Last name", h.get("last_name", doc.get("user_name", ""))),
            row("2. First names", h.get("first_names", "")),
            row("3. Sex", (h.get("sex") or h.get("gender", "")).title()),
            row("4. Date of birth", h.get("dob", "")),
            row("5. Home address", h.get("home_address") or h.get("address", "")),
            row("   Postcode", h.get("postcode", "")),
            row("   Country", h.get("country", "United Kingdom")),
            row("6. National Insurance", h.get("ni_number", "not provided")),
            row("7. Employment start date", h.get("start_date", "")),
        ]
        t = Table(pers, colWidths=[55 * mm, 115 * mm])
        t.setStyle(TableStyle([
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.whitesmoke, colors.white]),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t)

        # Statement
        story.append(Paragraph("Employee statement", h2))
        def yn(b): return "Yes" if b else "No"
        stmt_tbl = [
            row("8. Do you have another job?",       yn(h.get("q8_another_job"))),
            row("9. Receive State/workplace/private pension?", yn(h.get("q9_receives_pension"))),
            row("10. Since 6 April: another job, JSA, ESA or Incapacity Benefit?", yn(h.get("q10_recent_payments"))),
            row("Statement applied",                 f"Statement {h.get('statement','—')}"),
        ]
        t2 = Table(stmt_tbl, colWidths=[90 * mm, 80 * mm])
        t2.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ("BACKGROUND", (0, 3), (-1, 3), colors.HexColor("#E0ECFF")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t2)

        # Student loans
        story.append(Paragraph("Student loans", h2))
        loan_tbl = [
            row("11. Have a student or postgraduate loan?", yn(h.get("has_loan"))),
            row("12. Any qualifying study statements?",     yn(h.get("still_studying"))),
            row("13. Loan plans",                            plans),
        ]
        t3 = Table(loan_tbl, colWidths=[90 * mm, 80 * mm])
        t3.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t3)

        # Declaration
        story.append(Paragraph("Declaration", h2))
        decl_tbl = [
            row("Full name", h.get("declaration_full_name", "")),
            row("Date",      h.get("declaration_date", "")),
            row("Signature", h.get("declaration_signature", "")),
            row("Submitted", h.get("submitted_at", "")),
        ]
        t4 = Table(decl_tbl, colWidths=[55 * mm, 115 * mm])
        t4.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t4)
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(
            "I confirm that the information I've given on this form is correct. This document was digitally "
            "signed and submitted via the hotel onboarding platform.", small))

        pdf.build(story)
        return buf.getvalue()

    # -------- ADMIN: DOWNLOAD INDIVIDUAL DOC --------
    @router.get("/staff-onboarding/{user_id}/download/{kind}")
    async def admin_download(user_id: str, kind: str,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        doc = await db.staff_onboarding.find_one({"user_id": user_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Onboarding not found")
        if kind == "passport":
            path = doc.get("passport_path")
            if not path or not os.path.exists(path):
                raise HTTPException(404, "Passport file missing")
            return FileResponse(path, filename=doc.get("passport_filename", "passport"))
        if kind == "address":
            path = doc.get("address_proof_path")
            if not path or not os.path.exists(path):
                raise HTTPException(404, "Address proof file missing")
            return FileResponse(path, filename=doc.get("address_proof_filename", "address"))
        if kind == "hmrc":
            if not doc.get("hmrc_submitted"):
                raise HTTPException(404, "HMRC checklist not submitted")
            pdf = _build_hmrc_pdf(doc)
            name = (doc.get("user_name") or "staff").replace(" ", "_")
            return StreamingResponse(
                io.BytesIO(pdf),
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="HMRC_Starter_{name}.pdf"'},
            )
        raise HTTPException(400, "Unknown document kind")

    # -------- ADMIN: DOWNLOAD BUNDLE ZIP --------
    @router.get("/staff-onboarding/{user_id}/download-bundle")
    async def admin_download_bundle(user_id: str,
                                    current_user: dict = Depends(require_roles("admin", "manager"))):
        doc = await db.staff_onboarding.find_one({"user_id": user_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Onboarding not found")
        name = (doc.get("user_name") or "staff").replace(" ", "_")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            # Passport
            if doc.get("passport_path") and os.path.exists(doc["passport_path"]):
                ext = doc["passport_filename"].rsplit(".", 1)[-1] if "." in (doc.get("passport_filename") or "") else "jpg"
                zf.write(doc["passport_path"], arcname=f"{name}/1_ID_Passport.{ext}")
            # Address
            if doc.get("address_proof_path") and os.path.exists(doc["address_proof_path"]):
                ext = doc["address_proof_filename"].rsplit(".", 1)[-1] if "." in (doc.get("address_proof_filename") or "") else "jpg"
                zf.write(doc["address_proof_path"], arcname=f"{name}/2_Address_Proof.{ext}")
            # HMRC PDF
            if doc.get("hmrc_submitted"):
                zf.writestr(f"{name}/3_HMRC_Starter_Checklist.pdf", _build_hmrc_pdf(doc))
            # Contract ref as a small txt if signed
            if doc.get("contract_id"):
                zf.writestr(f"{name}/4_Contract_Reference.txt",
                            f"Signed contract ID: {doc['contract_id']}\nStaff: {doc.get('user_name','')}\nEmail: {doc.get('user_email','')}\n")
        buf.seek(0)
        return StreamingResponse(
            buf, media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="Onboarding_{name}.zip"'},
        )

    # -------- ADMIN: EMAIL DOCUMENTS --------
    @router.post("/staff-onboarding/{user_id}/email")
    async def admin_email(user_id: str, data: Dict,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        if not resend_lib or not os.environ.get("RESEND_API_KEY"):
            raise HTTPException(503, "Email service not configured")

        to_list = data.get("to") or []
        if isinstance(to_list, str):
            to_list = [x.strip() for x in to_list.split(",") if x.strip()]
        if not to_list:
            raise HTTPException(400, "At least one recipient required")

        includes = set(data.get("include") or ["passport", "address", "hmrc"])
        subject = (data.get("subject") or "Staff onboarding documents").strip()
        message = (data.get("message") or "").strip()

        doc = await db.staff_onboarding.find_one({"user_id": user_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Onboarding not found")
        name = (doc.get("user_name") or "staff").replace(" ", "_")

        # Build Resend attachments list (base64)
        attachments = []
        if "passport" in includes and doc.get("passport_path") and os.path.exists(doc["passport_path"]):
            with open(doc["passport_path"], "rb") as f:
                content = base64.b64encode(f.read()).decode()
            fn = doc.get("passport_filename") or "passport"
            attachments.append({"filename": f"{name}_ID_{fn}", "content": content})
        if "address" in includes and doc.get("address_proof_path") and os.path.exists(doc["address_proof_path"]):
            with open(doc["address_proof_path"], "rb") as f:
                content = base64.b64encode(f.read()).decode()
            fn = doc.get("address_proof_filename") or "address"
            attachments.append({"filename": f"{name}_Address_{fn}", "content": content})
        if "hmrc" in includes and doc.get("hmrc_submitted"):
            attachments.append({
                "filename": f"{name}_HMRC_Starter_Checklist.pdf",
                "content": base64.b64encode(_build_hmrc_pdf(doc)).decode(),
            })

        if not attachments:
            raise HTTPException(400, "No documents available to send")

        sender = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
        body_html = f"""<div style='font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;max-width:600px;margin:auto;padding:24px;color:#1f2937;'>
<h2 style='color:#065f46;margin:0 0 8px 0;'>Onboarding documents for {doc.get('user_name','staff')}</h2>
<p style='color:#6b7280;font-size:13px;'>Sent by {current_user.get('name','HR')} · {len(attachments)} attachment(s)</p>
<p>{message or 'Attached are the onboarding documents for this employee. This email is confidential and intended for the recipient only.'}</p>
<ul style='font-size:13px;color:#374151;'>
{"".join([f"<li>{a['filename']}</li>" for a in attachments])}
</ul>
<p style='color:#9ca3af;font-size:11px;margin-top:24px;'>Sent via hotel onboarding platform · please do not forward.</p>
</div>"""

        try:
            resend_lib.Emails.send({
                "from": sender,
                "to": to_list,
                "subject": subject,
                "html": body_html,
                "attachments": attachments,
            })
        except Exception as e:
            logger.error(f"Resend email failed: {e}")
            raise HTTPException(502, f"Email send failed: {str(e)[:160]}")

        # Audit log
        await db.staff_onboarding.update_one(
            {"user_id": user_id},
            {"$push": {"email_log": {
                "sent_at": datetime.now(timezone.utc).isoformat(),
                "sent_by": current_user.get("name", ""),
                "to": to_list,
                "attachments": [a["filename"] for a in attachments],
                "subject": subject,
            }}}
        )
        return {"ok": True, "sent_to": to_list, "attachments": len(attachments)}

    return router
