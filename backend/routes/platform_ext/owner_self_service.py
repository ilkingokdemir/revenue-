"""
Owner Portal — Self-Service Login.

Provides owners (REIT investors / unit owners) direct access to their
performance dashboard and monthly statements without going through an
admin user.

Auth model:
  - Owner record stores `password_hash` (bcrypt of a numeric PIN or password)
  - `POST /owner-auth/login`  → returns JWT with `type='owner_access'`, `sub=<owner_id>`
  - All other owner-self-service endpoints `Depend(get_current_owner)` which
    verifies the token, fetches the owner, and refuses if disabled.

The owner JWT cannot access staff endpoints (different `type` claim).

Endpoints
---------
  POST /api/owner-auth/login                      — email + PIN
  GET  /api/owner-auth/me                         — current owner profile
  GET  /api/owner-auth/dashboard?year=YYYY        — YTD performance
  GET  /api/owner-auth/statements?year=YYYY       — list of months
  GET  /api/owner-auth/statement.pdf?month=YYYY-MM — PDF (same template as admin path)

Admin endpoints
---------------
  POST /api/owners/{owner_id}/set-credentials     — admin sets/resets PIN
"""
from datetime import datetime, timezone, timedelta
import io
import os
import secrets
import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request

JWT_ALGORITHM = "HS256"


def _jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


def _hash(p: str) -> str:
    return bcrypt.hashpw(p.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode("utf-8"), h.encode("utf-8"))
    except Exception:
        return False


def _create_owner_token(owner_id: str) -> str:
    payload = {
        "sub": owner_id,
        "type": "owner_access",
        "exp": datetime.now(timezone.utc) + timedelta(hours=12),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def create_owner_auth_router(db, require_roles):
    router = APIRouter()

    async def get_current_owner(request: Request) -> dict:
        token = request.cookies.get("owner_access_token")
        if not token:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
        if not token:
            raise HTTPException(401, "Not authenticated")
        try:
            payload = jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])
            if payload.get("type") != "owner_access":
                raise HTTPException(401, "Invalid token type")
            owner = await db.unit_owners.find_one({"id": payload["sub"]}, {"_id": 0})
            if not owner:
                raise HTTPException(401, "Owner not found")
            if not owner.get("login_enabled", True):
                raise HTTPException(403, "Owner login disabled")
            return owner
        except jwt.ExpiredSignatureError:
            raise HTTPException(401, "Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(401, "Invalid token")

    # =========== Public login ===========
    @router.post("/owner-auth/login")
    async def login(body: dict):
        email = (body.get("email") or "").strip().lower()
        pin = body.get("pin") or body.get("password") or ""
        if not email or not pin:
            raise HTTPException(400, "email and pin required")
        owner = await db.unit_owners.find_one({"email": email}, {"_id": 0})
        if not owner or not owner.get("password_hash"):
            raise HTTPException(401, "Invalid credentials")
        if not _verify(pin, owner["password_hash"]):
            raise HTTPException(401, "Invalid credentials")
        if not owner.get("login_enabled", True):
            raise HTTPException(403, "Login disabled — contact management")
        token = _create_owner_token(owner["id"])
        # Stamp last login
        await db.unit_owners.update_one(
            {"id": owner["id"]},
            {"$set": {"last_login_at": datetime.now(timezone.utc).isoformat()}},
        )
        return {
            "access_token": token,
            "token_type": "bearer",
            "owner": {"id": owner["id"], "name": owner.get("name"),
                      "email": owner.get("email"),
                      "management_fee_percent": owner.get("management_fee_percent", 25)},
        }

    @router.get("/owner-auth/me")
    async def me(owner: dict = Depends(get_current_owner)):
        return {
            "id": owner["id"], "name": owner.get("name"),
            "email": owner.get("email"),
            "company": owner.get("company"),
            "phone": owner.get("phone"),
            "management_fee_percent": owner.get("management_fee_percent", 25),
            "unit_count": owner.get("unit_count", 0),
            "last_login_at": owner.get("last_login_at"),
        }

    @router.get("/owner-auth/dashboard")
    async def dashboard(year: str = "", owner: dict = Depends(get_current_owner)):
        """YTD performance + monthly breakdown for the logged-in owner."""
        from routes.platform_ext.owner_portal import create_owner_portal_router  # noqa: F401 (ensures models share collections)
        if not year:
            year = datetime.now(timezone.utc).strftime("%Y")
        # Re-implement the slim summary inline (avoid private import noise)
        units = await db.unit_owner_units.find({"owner_id": owner["id"]}, {"_id": 0}).to_list(200)
        unit_ids = [u["room_id"] for u in units if u.get("room_id")]
        # Pull bookings for the owner's rooms in the year
        q = {"room_id": {"$in": unit_ids}, "status": {"$nin": ["cancelled"]}} if unit_ids else {"__none__": True}
        bookings = await db.bookings.find(q, {"_id": 0}).to_list(2000) if unit_ids else []
        # Aggregate per month
        months = [{"month": f"{year}-{m:02d}", "revenue": 0.0, "nights": 0, "bookings": 0}
                  for m in range(1, 13)]
        for b in bookings:
            ci = (b.get("check_in") or "")[:7]
            if not ci.startswith(year):
                continue
            try:
                idx = int(ci[5:7]) - 1
            except (ValueError, TypeError):
                continue
            if 0 <= idx < 12:
                months[idx]["revenue"] += float(b.get("total_price") or 0)
                months[idx]["nights"] += int(b.get("nights") or 1)
                months[idx]["bookings"] += 1
        # Apply mgmt fee to compute net distribution per month
        mgmt = float(owner.get("management_fee_percent", 25)) / 100.0
        opex_rate = 0.12
        for mo in months:
            gross = mo["revenue"]
            mgmt_fee = gross * mgmt
            opex = gross * opex_rate
            mo["mgmt_fee"] = round(mgmt_fee, 2)
            mo["opex_est"] = round(opex, 2)
            mo["net_distribution"] = round(gross - mgmt_fee - opex, 2)
            mo["revenue"] = round(mo["revenue"], 2)
        total = {
            "revenue": round(sum(m["revenue"] for m in months), 2),
            "net_distribution": round(sum(m["net_distribution"] for m in months), 2),
            "nights": sum(m["nights"] for m in months),
            "bookings_count": sum(m["bookings"] for m in months),
        }
        return {
            "owner_id": owner["id"], "year": year,
            "unit_count": len(unit_ids), "months": months, "total": total,
            "management_fee_percent": float(owner.get("management_fee_percent", 25)),
        }

    @router.get("/owner-auth/statements")
    async def list_statements(year: str = "", owner: dict = Depends(get_current_owner)):
        if not year:
            year = datetime.now(timezone.utc).strftime("%Y")
        months = [f"{year}-{m:02d}" for m in range(1, 13)]
        return {"owner_id": owner["id"], "year": year, "available_months": months}

    @router.get("/owner-auth/statement.pdf")
    async def get_statement_pdf(month: str = "", owner: dict = Depends(get_current_owner)):
        """Owner-scoped PDF endpoint — re-uses the same generator as the admin path."""
        from routes.platform_ext.owner_portal import create_owner_portal_router  # noqa: F401
        # Call the admin endpoint's PDF builder by re-creating the same data flow.
        # Cheapest: just import and call get_statement_pdf logic.
        # We replicate the body inline rather than introduce a circular dep.
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from fastapi.responses import StreamingResponse

        if not month:
            month = datetime.now(timezone.utc).strftime("%Y-%m")
        # Find this owner's units & bookings
        units = await db.unit_owner_units.find({"owner_id": owner["id"]}, {"_id": 0}).to_list(200)
        unit_ids = [u["room_id"] for u in units if u.get("room_id")]
        bookings = []
        if unit_ids:
            bookings = await db.bookings.find(
                {"room_id": {"$in": unit_ids},
                 "status": {"$nin": ["cancelled"]},
                 "check_in": {"$regex": f"^{month}"}},
                {"_id": 0},
            ).to_list(500)
        gross = round(sum(float(b.get("total_price") or 0) for b in bookings), 2)
        mgmt_pct = float(owner.get("management_fee_percent", 25))
        mgmt_fee = round(gross * mgmt_pct / 100, 2)
        opex = round(gross * 0.12, 2)
        net = round(gross - mgmt_fee - opex, 2)
        nights = sum(int(b.get("nights") or 1) for b in bookings)

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4,
                                leftMargin=18 * mm, rightMargin=18 * mm,
                                topMargin=18 * mm, bottomMargin=18 * mm,
                                title=f"Owner Statement {month} — {owner.get('name')}")
        styles = getSampleStyleSheet()
        h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=16,
                            textColor=colors.HexColor("#0c0a09"))
        small = ParagraphStyle("small", parent=styles["Normal"], fontSize=9,
                               textColor=colors.HexColor("#525252"))
        muted = ParagraphStyle("muted", parent=styles["Normal"], fontSize=8,
                               textColor=colors.HexColor("#737373"))
        story = [
            Paragraph("OWNER DISTRIBUTION STATEMENT (SELF-SERVICE)", h1),
            Paragraph(f"<b>{owner.get('name')}</b> · {owner.get('email')}", small),
            Paragraph(f"Period: <b>{month}</b> · Units: <b>{len(unit_ids)}</b>", small),
            Spacer(1, 6 * mm),
        ]
        summary = [
            ["Description", "Amount (£)"],
            ["Gross Revenue", f"{gross:.2f}"],
            [f"Less: Management Fee ({mgmt_pct:.0f}%)", f"-{mgmt_fee:.2f}"],
            ["Less: Operating Costs (est. 12%)", f"-{opex:.2f}"],
            ["NET DISTRIBUTION", f"{net:.2f}"],
        ]
        tbl = Table(summary, colWidths=[110 * mm, 50 * mm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0c0a09")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#dcfce7")),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, -1), (-1, -1), 11),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#a8a29e")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 6 * mm))
        story.append(Paragraph(
            f"<b>Performance:</b> {len(bookings)} reservations · {nights} room-nights",
            small))
        story.append(Spacer(1, 10 * mm))
        story.append(Paragraph(
            "This statement is self-issued via the owner portal. "
            "Final reconciliation is provided with the year-end audited accounts. "
            f"Generated {datetime.now(timezone.utc).strftime('%d %b %Y %H:%M')} UTC.",
            muted))
        doc.build(story)
        buf.seek(0)
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="application/pdf",
            headers={"Content-Disposition":
                     f"attachment; filename=statement_{owner['id'][:8]}_{month}.pdf"},
        )

    @router.post("/owner-auth/logout")
    async def logout(_: dict = Depends(get_current_owner)):
        # Stateless JWT; client just discards the token. We return OK for symmetry.
        return {"ok": True}

    # =========== Admin: set/reset owner credentials ===========
    @router.post("/owners/{owner_id}/set-credentials")
    async def set_credentials(owner_id: str, body: dict,
                              current_user: dict = Depends(require_roles("admin"))):
        """Set or reset an owner's PIN.

        Body: { pin?: string, generate?: bool, login_enabled?: bool }.
        If generate=true (or no pin given), generates a 6-digit PIN and returns it once.
        """
        owner = await db.unit_owners.find_one({"id": owner_id}, {"_id": 0, "id": 1})
        if not owner:
            raise HTTPException(404, "Owner not found")
        pin = body.get("pin") or ""
        generate = body.get("generate", not pin)
        if generate:
            pin = "".join(secrets.choice("0123456789") for _ in range(6))
        if not pin or len(pin) < 4:
            raise HTTPException(400, "PIN must be at least 4 chars")
        update: dict = {
            "password_hash": _hash(pin),
            "login_enabled": body.get("login_enabled", True),
            "credentials_set_at": datetime.now(timezone.utc).isoformat(),
            "credentials_set_by": current_user.get("name", ""),
        }
        await db.unit_owners.update_one({"id": owner_id}, {"$set": update})
        return {
            "ok": True,
            "pin_generated": generate,
            "pin": pin if generate else None,
            "note": "Share this PIN with the owner over a secure channel. It will not be shown again.",
        }

    return router
