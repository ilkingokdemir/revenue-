"""
Currency & FX Consolidation
---------------------------
Multi-currency infrastructure for multi-property portfolios. Each property can
trade in its own currency; operators consolidate revenue, AR and deposits in a
shared base currency (typically GBP) using an admin-maintained FX table.

Collections:
- fx_rates:          {id, code, rate_to_base, as_of, source, notes, created_at, updated_at}
                     One doc per currency code → latest rate is picked by as_of DESC.
- currency_settings: singleton {id: "singleton", base_currency, rounding_mode, auto_refresh}

Conversions:
- Stored rates are expressed as "1 unit of <code> in base_currency units".
  e.g. code="EUR", rate_to_base=0.86 means 1 EUR = 0.86 GBP when base is GBP.
- The base currency itself is always rate_to_base = 1.

Endpoints (/api/currency-fx/*):
- GET    /settings                      → base currency + available codes
- PUT    /settings
- GET    /rates                         → latest rate per code
- POST   /rates                         → add/overwrite rate for a code
- DELETE /rates/{code}
- POST   /convert                       → { amount, from, to } → base-normalised
- GET    /ar-aging                      → city-ledger aging converted to base currency
- GET    /portfolio-summary             → per-property revenue & AR in base currency
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Optional, List, Dict
import uuid

from auth import require_perm


# ---------- Constants ----------
DEFAULT_BASE = "GBP"
# Seed rates — stable defaults so portfolio math still works before admin sets any.
# 1 unit of KEY = VALUE GBP. Covers 40 major ISO 4217 currencies (April 2026 reference).
SEED_RATES_TO_GBP = {
    "GBP": 1.0,
    # Americas
    "USD": 0.79, "CAD": 0.58, "MXN": 0.046, "BRL": 0.155, "ARS": 0.00088, "CLP": 0.00083,
    # Europe
    "EUR": 0.86, "CHF": 0.89, "SEK": 0.074, "NOK": 0.073, "DKK": 0.115,
    "PLN": 0.20, "CZK": 0.035, "HUF": 0.0022, "RON": 0.173, "ISK": 0.0057, "BGN": 0.44,
    # Middle East & Africa
    "TRY": 0.024, "AED": 0.215, "SAR": 0.21, "QAR": 0.217, "KWD": 2.58, "BHD": 2.10, "ILS": 0.22, "ZAR": 0.042, "EGP": 0.016, "MAD": 0.079,
    # Asia-Pacific
    "JPY": 0.0053, "CNY": 0.11, "HKD": 0.10, "SGD": 0.59, "KRW": 0.00058, "INR": 0.0095,
    "THB": 0.023, "IDR": 0.000049, "MYR": 0.18, "PHP": 0.014, "VND": 0.000031,
    "AUD": 0.52, "NZD": 0.47,
}

CURRENCY_SYMBOLS = {
    "GBP": "£", "USD": "$", "EUR": "€", "TRY": "₺", "AED": "د.إ",
    "JPY": "¥", "CAD": "C$", "AUD": "A$", "CHF": "CHF", "INR": "₹",
    "MXN": "Mex$", "BRL": "R$", "ARS": "AR$", "CLP": "CLP$",
    "SEK": "kr", "NOK": "kr", "DKK": "kr", "PLN": "zł", "CZK": "Kč", "HUF": "Ft",
    "RON": "lei", "ISK": "kr", "BGN": "лв",
    "SAR": "﷼", "QAR": "﷼", "KWD": "د.ك", "BHD": ".د.ب", "ILS": "₪", "ZAR": "R", "EGP": "£E", "MAD": "د.م.",
    "CNY": "¥", "HKD": "HK$", "SGD": "S$", "KRW": "₩",
    "THB": "฿", "IDR": "Rp", "MYR": "RM", "PHP": "₱", "VND": "₫",
    "NZD": "NZ$",
}


# ---------- Schemas ----------
class FxRateIn(BaseModel):
    code: str                  # 3-letter ISO, e.g. "EUR"
    rate_to_base: float        # 1 code = X base
    as_of: Optional[str] = None
    source: Optional[str] = "manual"
    notes: Optional[str] = ""


class SettingsIn(BaseModel):
    base_currency: str = DEFAULT_BASE
    rounding_mode: str = "banker"     # banker | half_up | down
    auto_refresh: bool = False         # future: daily ECB pull


class ConvertIn(BaseModel):
    amount: float
    source: str                        # "from" is reserved in py; keep neutral
    target: str


# ---------- Helpers ----------
async def _get_settings(db) -> dict:
    s = await db.currency_settings.find_one({"id": "singleton"}, {"_id": 0})
    if not s:
        s = {"id": "singleton", "base_currency": DEFAULT_BASE,
             "rounding_mode": "banker", "auto_refresh": False}
        await db.currency_settings.insert_one(dict(s))
        s.pop("_id", None)
    return s


async def _get_rate_map(db) -> Dict[str, float]:
    """Return { code: rate_to_base }. Seed baseline rows for any missing codes so
    new ISO additions show up automatically after deploys."""
    existing_codes = set(await db.fx_rates.distinct("code"))
    missing = [c for c in SEED_RATES_TO_GBP.keys() if c not in existing_codes]
    if missing:
        now = datetime.now(timezone.utc).isoformat()
        docs = [{
            "id": str(uuid.uuid4()),
            "code": code, "rate_to_base": SEED_RATES_TO_GBP[code],
            "as_of": now[:10], "source": "seed", "notes": "Seeded default",
            "created_at": now, "updated_at": now,
        } for code in missing]
        await db.fx_rates.insert_many([dict(d) for d in docs])

    rows = await db.fx_rates.find({"code": {"$exists": True}}, {"_id": 0}).to_list(500)
    # Keep the most recent per code (as_of DESC)
    by_code: Dict[str, dict] = {}
    for r in rows:
        code = r.get("code")
        if not code:
            continue  # Skip docs without code field
        existing_r = by_code.get(code)
        if not existing_r or (r.get("as_of", "") >= existing_r.get("as_of", "")):
            by_code[code] = r
    return {code: float(row.get("rate_to_base", 1)) for code, row in by_code.items()}


def _convert(amount: float, src: str, dst: str, rates: Dict[str, float], base: str) -> float:
    if not amount:
        return 0.0
    src = (src or base).upper()
    dst = (dst or base).upper()
    if src == dst:
        return round(amount, 2)
    # Everything is normalised via base.
    src_to_base = rates.get(src, 1.0) if src != base else 1.0
    dst_to_base = rates.get(dst, 1.0) if dst != base else 1.0
    if dst_to_base == 0:
        return round(amount * src_to_base, 2)
    base_amount = amount * src_to_base
    return round(base_amount / dst_to_base, 2)


# ---------- Router ----------
def create_currency_fx_router(db):
    router = APIRouter(prefix="/currency-fx")

    # ----- settings -----
    @router.get("/settings")
    async def get_settings(
        current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any")),
    ):
        s = await _get_settings(db)
        # Populate available codes so the frontend can drive selects
        rates = await _get_rate_map(db)
        s["available_codes"] = sorted(rates.keys())
        s["symbols"] = CURRENCY_SYMBOLS
        return s

    @router.put("/settings")
    async def update_settings(
        data: SettingsIn,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        doc = data.model_dump()
        doc["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.currency_settings.update_one(
            {"id": "singleton"}, {"$set": {**doc, "id": "singleton"}}, upsert=True,
        )
        return {"ok": True, **doc}

    # ----- per-property native currency -----
    @router.get("/properties")
    async def list_property_currencies(
        current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any")),
    ):
        props = await db.properties.find(
            {"id": {"$ne": "default"}},
            {"_id": 0, "id": 1, "name": 1, "currency": 1, "country": 1},
        ).sort("name", 1).to_list(500)
        for p in props:
            if not p.get("currency"):
                p["currency"] = "GBP"
        return props

    @router.put("/properties/{property_id}")
    async def set_property_currency(
        property_id: str,
        body: dict,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        new_cur = (body.get("currency") or "").upper()
        if not new_cur or len(new_cur) != 3:
            raise HTTPException(400, "3-letter currency code required")
        r = await db.properties.update_one(
            {"id": property_id}, {"$set": {"currency": new_cur}}
        )
        if r.matched_count == 0:
            raise HTTPException(404, "Property not found")
        # Cascade to rooms so future bookings widget quotes match
        await db.room_types.update_many(
            {"property_id": property_id}, {"$set": {"currency": new_cur}}
        )
        # Cascade to already-created future bookings so consolidation math is correct
        today = datetime.now(timezone.utc).date().isoformat()
        await db.bookings.update_many(
            {"property_id": property_id, "check_in": {"$gte": today}},
            {"$set": {"currency": new_cur}},
        )
        return {"ok": True, "property_id": property_id, "currency": new_cur}

    # ----- rates -----
    @router.get("/rates")
    async def list_rates(
        current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any")),
    ):
        # Ensure seed rows exist
        await _get_rate_map(db)
        rows = await db.fx_rates.find({"code": {"$exists": True}}, {"_id": 0}).sort("code", 1).to_list(500)
        # Collapse to latest per code for the UI
        latest: Dict[str, dict] = {}
        for r in rows:
            code = r.get("code")
            if not code:
                continue
            existing_r = latest.get(code)
            if not existing_r or (r.get("as_of", "") >= existing_r.get("as_of", "")):
                latest[code] = r
        return sorted(latest.values(), key=lambda r: r.get("code", ""))

    @router.post("/rates")
    async def upsert_rate(
        data: FxRateIn,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "id": str(uuid.uuid4()),
            "code": data.code.upper(),
            "rate_to_base": float(data.rate_to_base),
            "as_of": data.as_of or now[:10],
            "source": data.source or "manual",
            "notes": data.notes or "",
            "created_at": now,
            "updated_at": now,
            "created_by": current_user.get("email", ""),
        }
        # Upsert by (code, as_of) so same-day edits don't duplicate
        await db.fx_rates.update_one(
            {"code": doc["code"], "as_of": doc["as_of"]},
            {"$set": doc}, upsert=True,
        )
        return {"ok": True, **doc}

    @router.delete("/rates/{code}")
    async def delete_rate(
        code: str,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        code = code.upper()
        if code == DEFAULT_BASE:
            raise HTTPException(400, "Cannot delete the base currency rate")
        r = await db.fx_rates.delete_many({"code": code})
        return {"deleted": r.deleted_count}

    # ----- conversion -----
    @router.post("/convert")
    async def convert(
        data: ConvertIn,
        current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any")),
    ):
        settings = await _get_settings(db)
        rates = await _get_rate_map(db)
        out = _convert(data.amount, data.source, data.target, rates, settings["base_currency"])
        return {
            "amount": data.amount, "from": data.source.upper(), "to": data.target.upper(),
            "converted": out,
            "base_currency": settings["base_currency"],
        }

    # ----- consolidated AR aging (city ledger) -----
    @router.get("/ar-aging")
    async def ar_aging(
        current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any")),
    ):
        settings = await _get_settings(db)
        base = settings["base_currency"]
        rates = await _get_rate_map(db)
        today = datetime.now(timezone.utc).date()

        invs = await db.city_ledger_invoices.find(
            {"status": {"$ne": "paid"}}, {"_id": 0}
        ).to_list(5000)

        buckets = {"current": 0.0, "d30": 0.0, "d60": 0.0, "d90": 0.0, "over90": 0.0}
        by_currency: Dict[str, dict] = {}
        total_base = 0.0

        for inv in invs:
            cur = (inv.get("currency") or base).upper()
            balance_native = round(float(inv.get("amount", 0)) - float(inv.get("paid_amount", 0)), 2)
            if balance_native <= 0:
                continue
            balance_base = _convert(balance_native, cur, base, rates, base)
            try:
                due = datetime.fromisoformat(inv.get("due_date", today.isoformat())).date()
            except Exception:
                due = today
            days_late = (today - due).days
            if days_late <= 0:
                bucket = "current"
            elif days_late <= 30:
                bucket = "d30"
            elif days_late <= 60:
                bucket = "d60"
            elif days_late <= 90:
                bucket = "d90"
            else:
                bucket = "over90"

            buckets[bucket] = round(buckets[bucket] + balance_base, 2)
            total_base = round(total_base + balance_base, 2)

            row = by_currency.setdefault(cur, {
                "currency": cur, "native_total": 0.0, "base_total": 0.0,
                "rate": rates.get(cur, 1.0), "invoices": 0,
            })
            row["native_total"] = round(row["native_total"] + balance_native, 2)
            row["base_total"] = round(row["base_total"] + balance_base, 2)
            row["invoices"] += 1

        return {
            "base_currency": base,
            "as_of": today.isoformat(),
            "buckets": buckets,
            "total": total_base,
            "by_currency": sorted(by_currency.values(), key=lambda r: r["base_total"], reverse=True),
            "invoice_count": sum(v["invoices"] for v in by_currency.values()),
        }

    # ----- portfolio summary (revenue + AR per property in base) -----
    @router.get("/portfolio-summary")
    async def portfolio_summary(
        current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any")),
    ):
        settings = await _get_settings(db)
        base = settings["base_currency"]
        rates = await _get_rate_map(db)

        properties = await db.properties.find(
            {"id": {"$ne": "default"}}, {"_id": 0, "id": 1, "name": 1, "currency": 1, "country": 1}
        ).to_list(500)
        if not properties:
            properties = [{"id": "default", "name": "Default Property", "currency": base}]

        # Pre-build booking → property index for AR attribution
        booking_to_prop: Dict[str, str] = {}
        async for b in db.bookings.find({}, {"_id": 0, "id": 1, "property_id": 1}):
            if b.get("id"):
                booking_to_prop[b["id"]] = b.get("property_id", "default")

        open_invs = await db.city_ledger_invoices.find(
            {"status": {"$ne": "paid"}}, {"_id": 0}
        ).to_list(5000)

        totals = {
            "revenue_native": 0.0, "revenue_base": 0.0,
            "ar_native": 0.0, "ar_base": 0.0,
        }
        rows = []
        for p in properties:
            pcur = (p.get("currency") or base).upper()

            # Revenue = sum of bookings with status in {confirmed, checked_in, checked_out}
            cursor = db.bookings.find(
                {"property_id": p["id"], "status": {"$in": ["confirmed", "checked_in", "checked_out"]}},
                {"_id": 0, "total_price": 1, "currency": 1},
            )
            rev_native_by_cur: Dict[str, float] = {}
            async for b in cursor:
                cur = (b.get("currency") or pcur).upper()
                rev_native_by_cur[cur] = round(rev_native_by_cur.get(cur, 0) + float(b.get("total_price", 0)), 2)
            rev_base = round(sum(_convert(v, c, base, rates, base) for c, v in rev_native_by_cur.items()), 2)
            rev_native_total = round(sum(rev_native_by_cur.values()), 2)

            # AR attribution by matching booking_ids → property
            ar_base_val = 0.0
            ar_native_total = 0.0
            for inv in open_invs:
                if not any(booking_to_prop.get(bid) == p["id"] for bid in inv.get("booking_ids", [])):
                    continue
                bal = round(float(inv.get("amount", 0)) - float(inv.get("paid_amount", 0)), 2)
                if bal <= 0:
                    continue
                cur = (inv.get("currency") or pcur).upper()
                ar_base_val += _convert(bal, cur, base, rates, base)
                ar_native_total += bal
            ar_base_val = round(ar_base_val, 2)
            ar_native_total = round(ar_native_total, 2)

            rows.append({
                "property_id": p["id"],
                "property_name": p.get("name", p["id"]),
                "currency": pcur,
                "revenue_native": rev_native_total,
                "revenue_base": rev_base,
                "ar_native": ar_native_total,
                "ar_base": ar_base_val,
            })
            totals["revenue_native"] += rev_native_total
            totals["revenue_base"] += rev_base
            totals["ar_native"] += ar_native_total
            totals["ar_base"] += ar_base_val

        totals = {k: round(v, 2) for k, v in totals.items()}
        return {
            "base_currency": base,
            "properties": sorted(rows, key=lambda r: r["revenue_base"], reverse=True),
            "totals": totals,
            "rate_as_of": datetime.now(timezone.utc).date().isoformat(),
        }

    return router
