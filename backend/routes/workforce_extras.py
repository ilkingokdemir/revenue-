"""
Workforce extras — Bordro (Payroll) CSV export + Tip Pool distribution.
"""
import csv
import io
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)


def create_workforce_extras_router(db, require_roles):
    router = APIRouter()

    # ============== BORDRO CSV EXPORT ==============
    @router.get("/payroll/export/{property_id}")
    async def export_payroll(property_id: str, week_start: str = "", month: str = "",
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        """Generate CSV download for shifts within a week or month."""
        prop_filter = {} if property_id == "all" else {"property_id": property_id}
        query = {**prop_filter, "status": {"$in": ["completed", "approved"]}}
        if week_start:
            query["week_start"] = week_start
        if month:
            query["date"] = {"$regex": f"^{month}"}
        shifts = await db.shift_entries.find(query, {"_id": 0}).sort("date", 1).to_list(5000)

        # Aggregate per staff
        per_staff: dict = {}
        for s in shifts:
            sid = s.get("staff_id")
            if not sid:
                continue
            entry = per_staff.setdefault(sid, {
                "staff_name": s.get("staff_name", ""),
                "role": s.get("role", ""),
                "pay_type": s.get("pay_type", "daily"),
                "pay_rate": float(s.get("pay_rate", 0) or 0),
                "currency": s.get("currency", "GBP"),
                "shift_count": 0,
                "total_hours": 0.0,
                "total_earned": 0.0,
                "shifts": [],
            })
            entry["shift_count"] += 1
            entry["total_hours"] += float(s.get("hours_worked", 0) or 0)
            entry["total_earned"] += float(s.get("earned_amount", 0) or 0)
            entry["shifts"].append(s.get("date", ""))

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "Personel", "Rol", "Ödeme Tipi", "Birim Ücret", "Para Birimi",
            "Vardiya Sayısı", "Toplam Saat", "Toplam Kazanç",
        ])
        for entry in per_staff.values():
            writer.writerow([
                entry["staff_name"], entry["role"], entry["pay_type"],
                f"{entry['pay_rate']:.2f}", entry["currency"],
                entry["shift_count"], f"{entry['total_hours']:.2f}",
                f"{entry['total_earned']:.2f}",
            ])
        # Totals row
        writer.writerow([])
        writer.writerow([
            "TOPLAM", "", "", "", "",
            sum(e["shift_count"] for e in per_staff.values()),
            f"{sum(e['total_hours'] for e in per_staff.values()):.2f}",
            f"{sum(e['total_earned'] for e in per_staff.values()):.2f}",
        ])

        buf.seek(0)
        filename = f"bordro_{property_id}_{week_start or month or 'all'}.csv"
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    # ============== TIP POOL ==============
    @router.post("/tip-pool/distribute")
    async def distribute_tips(data: Dict,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        """Distribute total tips across staff for a date.
        Three modes:
          - equal: split evenly
          - hours: weighted by hours_worked
          - role: role-based weighting (chef=1.5x, server=1.0x, kds=0.7x, default=1.0x)
        """
        property_id = data.get("property_id", "default")
        date = data.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        total_tips = float(data.get("total_tips", 0))
        mode = data.get("mode", "hours")  # equal / hours / role
        role_weights = data.get("role_weights") or {
            "chef": 1.5, "head_chef": 1.7, "server": 1.0, "waiter": 1.0,
            "kds": 0.7, "kitchen": 1.2, "bartender": 1.3, "host": 0.8,
        }

        if total_tips <= 0:
            raise HTTPException(400, "total_tips must be > 0")

        # Get shifts working on that date
        prop_filter = {} if property_id == "all" else {"property_id": property_id}
        shifts = await db.shift_entries.find(
            {**prop_filter, "date": date,
             "status": {"$in": ["completed", "approved", "published", "planned"]}},
            {"_id": 0}
        ).to_list(200)

        if not shifts:
            return {"distributed": 0, "shares": [],
                    "note": f"No shifts on {date} for {property_id}"}

        # Compute weights
        weights = []
        for s in shifts:
            if mode == "equal":
                w = 1.0
            elif mode == "hours":
                w = max(0.5, float(s.get("hours_worked", 0) or 8))
            else:  # role
                role = (s.get("role") or "").lower()
                w = role_weights.get(role, 1.0) * max(0.5, float(s.get("hours_worked", 0) or 8))
            weights.append({"shift": s, "weight": w})
        total_w = sum(w["weight"] for w in weights) or 1
        shares = []
        now = datetime.now(timezone.utc).isoformat()
        for w in weights:
            share = round(total_tips * w["weight"] / total_w, 2)
            shares.append({
                "shift_id": w["shift"].get("id"),
                "staff_id": w["shift"].get("staff_id"),
                "staff_name": w["shift"].get("staff_name"),
                "role": w["shift"].get("role"),
                "hours": w["shift"].get("hours_worked"),
                "weight": round(w["weight"], 2),
                "share": share,
            })

        # Persist tip distribution record
        await db.tip_distributions.insert_one({
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "date": date,
            "total_tips": total_tips,
            "mode": mode,
            "shares": shares,
            "distributed_by": current_user.get("name", ""),
            "created_at": now,
        })

        return {
            "distributed": len(shares),
            "total_tips": total_tips,
            "mode": mode,
            "shares": sorted(shares, key=lambda x: -x["share"]),
        }

    @router.get("/tip-pool/history/{property_id}")
    async def tip_history(property_id: str, days: int = 30,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        cutoff = (datetime.now(timezone.utc) - timedelta(days=int(days or 30))).isoformat()
        query = {"created_at": {"$gte": cutoff}}
        if property_id != "all":
            query["property_id"] = property_id
        docs = await db.tip_distributions.find(query, {"_id": 0}).sort(
            "created_at", -1).to_list(100)
        return docs

    return router
