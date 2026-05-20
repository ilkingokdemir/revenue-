"""
Brand Portal / Chain HQ — multi-property rollup + per-property white-label.

Two concerns:
  A) White-label branding per property (logo, colors, custom domain, from-email)
  B) Brand / Chain HQ console: consolidated view across all properties owned
     by the current org — KPI rollup, comparative table, top-alert aggregation.

This unlocks franchise + chain-HQ scenarios (Opera Cloud Central equivalent).
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, date, timedelta
from typing import Optional
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)


class PropertyBranding(BaseModel):
    property_id: str
    logo_url: Optional[str] = None
    primary_color: Optional[str] = "#0f172a"
    secondary_color: Optional[str] = "#f59e0b"
    custom_domain: Optional[str] = None
    from_email: Optional[str] = None
    legal_footer: Optional[str] = None
    booking_engine_url: Optional[str] = None
    social_instagram: Optional[str] = None
    social_facebook: Optional[str] = None
    email_signature: Optional[str] = None


def create_brand_portal_router(db, require_roles):
    router = APIRouter()

    # ---- Per-property branding ----

    @router.get("/brand-portal/branding/{property_id}")
    async def get_branding(property_id: str,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        doc = await db.property_branding.find_one(
            {"property_id": property_id}, {"_id": 0}
        )
        if not doc:
            # Auto-create defaults
            doc = {
                "property_id": property_id,
                "primary_color": "#0f172a",
                "secondary_color": "#f59e0b",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.property_branding.insert_one(doc)
            doc = {k: v for k, v in doc.items() if k != "_id"}
        return doc

    @router.put("/brand-portal/branding/{property_id}")
    async def update_branding(property_id: str, b: PropertyBranding,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        upd = b.dict(exclude_unset=True, exclude={"property_id"})
        upd["updated_at"] = datetime.now(timezone.utc).isoformat()
        upd["updated_by"] = current_user.get("email")
        await db.property_branding.update_one(
            {"property_id": property_id},
            {"$set": upd, "$setOnInsert": {"created_at": upd["updated_at"]}},
            upsert=True,
        )
        return {"updated": True}

    # ---- Public single-property branding (for guest pages to pick up theme) ----

    @router.get("/brand-portal/public-branding/{property_id}")
    async def public_branding(property_id: str):
        doc = await db.property_branding.find_one(
            {"property_id": property_id},
            {"_id": 0, "from_email": 0}
        )
        if not doc:
            return {"property_id": property_id, "primary_color": "#0f172a"}
        return doc

    # ---- Chain HQ overview ----

    async def _property_kpis(property_id: str, since_iso: str, until_iso: str):
        bookings = await db.bookings.find({
            "property_id": property_id,
            "check_in": {"$gte": since_iso, "$lte": until_iso},
            "status": {"$in": ["confirmed", "checked_in", "checked_out"]},
        }, {"_id": 0}).limit(5000).to_list(5000)
        total_rooms = await db.rooms.count_documents({"property_id": property_id})

        total_rev = 0.0
        total_nights = 0
        room_nights = 0
        for b in bookings:
            total_rev += float(b.get("total_price") or 0)
            try:
                ci = datetime.strptime(b.get("check_in"), "%Y-%m-%d").date()
                co = datetime.strptime(b.get("check_out"), "%Y-%m-%d").date()
                nights = max(1, (co - ci).days)
                total_nights += nights
                room_nights += nights
            except Exception:
                pass

        # Denominator for occupancy
        try:
            days_window = (datetime.strptime(until_iso, "%Y-%m-%d").date()
                           - datetime.strptime(since_iso, "%Y-%m-%d").date()).days or 1
        except Exception:
            days_window = 30
        available_room_nights = total_rooms * days_window
        occupancy = (room_nights / available_room_nights * 100) if available_room_nights else 0

        adr = (total_rev / total_nights) if total_nights else 0
        revpar = (total_rev / available_room_nights) if available_room_nights else 0

        # Reviews avg (last 30d)
        reviews = await db.reviews.find(
            {"property_id": property_id},
            {"_id": 0, "rating": 1, "overall_rating": 1}
        ).limit(500).to_list(500)
        ratings = [float(r.get("rating") or r.get("overall_rating") or 0) for r in reviews if (r.get("rating") or r.get("overall_rating"))]
        avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else 0

        return {
            "property_id": property_id,
            "rooms": total_rooms,
            "bookings": len(bookings),
            "revenue": round(total_rev, 2),
            "occupancy_pct": round(occupancy, 1),
            "adr": round(adr, 2),
            "revpar": round(revpar, 2),
            "avg_rating": avg_rating,
            "review_count": len(reviews),
        }

    @router.get("/brand-portal/overview")
    async def overview(days: int = 30,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        """Chain-HQ rollup across ALL properties visible to current user."""
        properties = await db.properties.find({}, {"_id": 0}).to_list(500)
        if not properties:
            return {"properties": [], "total": {}, "window_days": days}

        since = (date.today() - timedelta(days=days)).isoformat()
        until = date.today().isoformat()

        rows = []
        for p in properties:
            try:
                kpis = await _property_kpis(p["id"], since, until)
                kpis["name"] = p.get("name")
                kpis["city"] = p.get("city")
                kpis["country"] = p.get("country")
                rows.append(kpis)
            except Exception as ex:
                logger.warning(f"KPI fail {p.get('id')}: {ex}")

        total = {
            "properties": len(rows),
            "rooms": sum(r["rooms"] for r in rows),
            "bookings": sum(r["bookings"] for r in rows),
            "revenue": round(sum(r["revenue"] for r in rows), 2),
            "avg_occupancy": round(sum(r["occupancy_pct"] for r in rows) / len(rows), 1) if rows else 0,
            "avg_adr": round(sum(r["adr"] for r in rows) / len(rows), 2) if rows else 0,
            "avg_revpar": round(sum(r["revpar"] for r in rows) / len(rows), 2) if rows else 0,
            "avg_rating": round(sum(r["avg_rating"] for r in rows if r["avg_rating"]) / max(1, len([r for r in rows if r["avg_rating"]])), 2) if rows else 0,
        }

        # Rank tables
        by_revenue = sorted(rows, key=lambda r: r["revenue"], reverse=True)[:10]
        by_occupancy = sorted(rows, key=lambda r: r["occupancy_pct"], reverse=True)[:10]
        lowest_rating = sorted([r for r in rows if r["review_count"] > 0], key=lambda r: r["avg_rating"])[:5]

        return {
            "window_days": days,
            "total": total,
            "properties": rows,
            "by_revenue": by_revenue,
            "by_occupancy": by_occupancy,
            "lowest_rating": lowest_rating,
        }

    @router.get("/brand-portal/alerts")
    async def cross_property_alerts(days: int = 7,
                                    current_user: dict = Depends(require_roles("admin", "manager"))):
        """Aggregate alert-like conditions across all properties."""
        properties = await db.properties.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(500)
        alerts = []
        for p in properties:
            pid = p["id"]
            # Unread inbox
            for coll in ("unified_inbox", "inbox_messages"):
                try:
                    cnt = await db[coll].count_documents({"property_id": pid, "read": False})
                    if cnt > 10:
                        alerts.append({
                            "property_id": pid, "property_name": p["name"],
                            "type": "unread_inbox", "severity": "warn",
                            "count": cnt, "message": f"{cnt} unread messages",
                        })
                        break
                except Exception:
                    pass
            # Unanswered reviews
            try:
                unans = await db.reviews.count_documents({"property_id": pid, "response": {"$in": [None, ""]}})
                if unans > 5:
                    alerts.append({
                        "property_id": pid, "property_name": p["name"],
                        "type": "unanswered_reviews", "severity": "warn",
                        "count": unans, "message": f"{unans} unanswered reviews",
                    })
            except Exception:
                pass
            # Low occupancy tomorrow
            try:
                tmrw = (date.today() + timedelta(days=1)).isoformat()
                rooms = await db.rooms.count_documents({"property_id": pid})
                occ = await db.bookings.count_documents({
                    "property_id": pid,
                    "check_in": {"$lte": tmrw},
                    "check_out": {"$gt": tmrw},
                    "status": {"$in": ["confirmed", "checked_in"]},
                })
                if rooms and (occ / rooms * 100) < 40:
                    alerts.append({
                        "property_id": pid, "property_name": p["name"],
                        "type": "low_occupancy", "severity": "info",
                        "count": occ, "message": f"Tomorrow {occ}/{rooms} ({round(occ/rooms*100,1)}%)",
                    })
            except Exception:
                pass
        return {"alerts": alerts, "count": len(alerts)}

    return router
