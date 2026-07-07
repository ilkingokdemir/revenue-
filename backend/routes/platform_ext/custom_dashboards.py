"""
Custom Dashboard Builder (iter 369) — Mews parity
=================================================
Managers assemble their own dashboard from a catalog of widgets — KPIs,
mini-charts, alert boards, quick actions. Layout is persisted per user +
optionally shared property-wide.

Endpoints
---------
  GET  /api/dashboards/widget-catalog                — all available widget types
  GET  /api/dashboards/mine                          — list of my saved dashboards
  POST /api/dashboards                               — create new dashboard
  GET  /api/dashboards/{dash_id}                     — dashboard with layout
  PUT  /api/dashboards/{dash_id}                     — patch (rename, layout, widgets)
  DELETE /api/dashboards/{dash_id}
  POST /api/dashboards/{dash_id}/widgets             — add a widget
  DELETE /api/dashboards/{dash_id}/widgets/{wid_id}  — remove
  GET  /api/dashboards/widget-data/{widget_type}     — read data for a widget type

Widget types (v1)
-----------------
  kpi_occupancy     · occupancy % vs yesterday
  kpi_adr           · ADR vs yesterday
  kpi_revpar        · RevPAR vs yesterday
  kpi_pace          · pace count last 24h
  kpi_pickup        · pickup last 7d
  kpi_roas          · overall ROAS
  alerts_board      · latest 5 alerts
  quick_actions     · common shortcuts
  spark_revenue     · last 7 days revenue spark line
  hk_summary        · housekeeping status counts
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


WIDGET_CATALOG = [
    {"type": "kpi_occupancy",  "label": "Occupancy %",       "size": {"w": 3, "h": 2}, "category": "kpi"},
    {"type": "kpi_adr",        "label": "ADR",                "size": {"w": 3, "h": 2}, "category": "kpi"},
    {"type": "kpi_revpar",     "label": "RevPAR",             "size": {"w": 3, "h": 2}, "category": "kpi"},
    {"type": "kpi_pace",       "label": "Pace (24h)",         "size": {"w": 3, "h": 2}, "category": "kpi"},
    {"type": "kpi_pickup",     "label": "Pickup (7d)",        "size": {"w": 3, "h": 2}, "category": "kpi"},
    {"type": "kpi_roas",       "label": "ROAS (30d)",         "size": {"w": 3, "h": 2}, "category": "kpi"},
    {"type": "alerts_board",   "label": "Aktif Uyarılar",     "size": {"w": 6, "h": 4}, "category": "board"},
    {"type": "spark_revenue",  "label": "Son 7 Gün Gelir",    "size": {"w": 6, "h": 3}, "category": "chart"},
    {"type": "hk_summary",     "label": "Housekeeping Özeti", "size": {"w": 4, "h": 3}, "category": "board"},
    {"type": "quick_actions",  "label": "Hızlı Aksiyonlar",   "size": {"w": 4, "h": 3}, "category": "shortcuts"},
]


class DashboardCreate(BaseModel):
    name:        str
    property_id: Optional[str] = None
    shared:      bool = False


class DashboardUpdate(BaseModel):
    name:      Optional[str] = None
    shared:    Optional[bool] = None
    widgets:   Optional[list[dict]] = None   # [{id, type, x, y, w, h, settings?}]


class WidgetAdd(BaseModel):
    type:     str
    x:        int = 0
    y:        int = 0
    w:        Optional[int] = None
    h:        Optional[int] = None
    settings: Optional[dict] = None


def create_dashboards_router(db, require_roles):
    router = APIRouter(prefix="/dashboards", tags=["custom-dashboards"])

    @router.get("/widget-catalog")
    async def widget_catalog(_: dict = Depends(require_roles("admin", "manager"))):
        return {"items": WIDGET_CATALOG}

    @router.get("/mine")
    async def my_dashboards(current_user: dict = Depends(require_roles("admin", "manager"))):
        email = current_user.get("email", "")
        # own + shared with everyone
        rows = await db.custom_dashboards.find(
            {"$or": [{"owner_email": email}, {"shared": True}]},
            {"_id": 0}
        ).sort("created_at", -1).to_list(100)
        return {"items": rows}

    @router.post("")
    async def create_dashboard(body: DashboardCreate,
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        doc = {
            "id":          str(uuid.uuid4()),
            "name":        body.name.strip() or "Untitled",
            "owner_email": current_user.get("email", ""),
            "shared":      body.shared,
            "property_id": body.property_id,
            "widgets":     [],   # empty layout initially
            "created_at":  _now(),
            "updated_at":  _now(),
        }
        await db.custom_dashboards.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.get("/{dash_id}")
    async def get_dashboard(dash_id: str,
                              _: dict = Depends(require_roles("admin", "manager"))):
        d = await db.custom_dashboards.find_one({"id": dash_id}, {"_id": 0})
        if not d:
            raise HTTPException(404, "Dashboard bulunamadı")
        return d

    @router.put("/{dash_id}")
    async def update_dashboard(dash_id: str, body: DashboardUpdate,
                                 current_user: dict = Depends(require_roles("admin", "manager"))):
        d = await db.custom_dashboards.find_one({"id": dash_id}, {"_id": 0, "owner_email": 1})
        if not d:
            raise HTTPException(404, "Dashboard bulunamadı")
        # Only owner (or admin) can update
        if d["owner_email"] != current_user.get("email") and (current_user.get("role") or "").lower() != "admin":
            raise HTTPException(403, "Sadece sahibi düzenleyebilir")
        updates: dict = {"updated_at": _now()}
        if body.name is not None:
            updates["name"] = body.name.strip()
        if body.shared is not None:
            updates["shared"] = bool(body.shared)
        if body.widgets is not None:
            # Sanitize widget entries
            valid_types = {w["type"] for w in WIDGET_CATALOG}
            clean = []
            for w in body.widgets:
                if w.get("type") not in valid_types:
                    continue
                clean.append({
                    "id":       w.get("id") or str(uuid.uuid4()),
                    "type":     w["type"],
                    "x":        int(w.get("x") or 0),
                    "y":        int(w.get("y") or 0),
                    "w":        int(w.get("w") or 3),
                    "h":        int(w.get("h") or 2),
                    "settings": w.get("settings") or {},
                })
            updates["widgets"] = clean
        await db.custom_dashboards.update_one({"id": dash_id}, {"$set": updates})
        return {"ok": True}

    @router.delete("/{dash_id}")
    async def delete_dashboard(dash_id: str,
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        d = await db.custom_dashboards.find_one({"id": dash_id}, {"_id": 0, "owner_email": 1})
        if not d:
            raise HTTPException(404, "Dashboard bulunamadı")
        if d["owner_email"] != current_user.get("email") and (current_user.get("role") or "").lower() != "admin":
            raise HTTPException(403, "Sadece sahibi silebilir")
        r = await db.custom_dashboards.delete_one({"id": dash_id})
        return {"ok": True, "deleted": r.deleted_count}

    @router.post("/{dash_id}/widgets")
    async def add_widget(dash_id: str, body: WidgetAdd,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        catalog_map = {w["type"]: w for w in WIDGET_CATALOG}
        if body.type not in catalog_map:
            raise HTTPException(400, f"Bilinmeyen widget tipi: {body.type}")
        d = await db.custom_dashboards.find_one({"id": dash_id}, {"_id": 0})
        if not d:
            raise HTTPException(404, "Dashboard bulunamadı")
        if d["owner_email"] != current_user.get("email") and (current_user.get("role") or "").lower() != "admin":
            raise HTTPException(403, "Sadece sahibi düzenleyebilir")
        default_size = catalog_map[body.type]["size"]
        widget = {
            "id":       str(uuid.uuid4()),
            "type":     body.type,
            "x":        body.x,
            "y":        body.y,
            "w":        body.w or default_size["w"],
            "h":        body.h or default_size["h"],
            "settings": body.settings or {},
        }
        await db.custom_dashboards.update_one(
            {"id": dash_id},
            {"$push": {"widgets": widget}, "$set": {"updated_at": _now()}},
        )
        return widget

    @router.delete("/{dash_id}/widgets/{widget_id}")
    async def remove_widget(dash_id: str, widget_id: str,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        d = await db.custom_dashboards.find_one({"id": dash_id}, {"_id": 0, "owner_email": 1})
        if not d:
            raise HTTPException(404, "Dashboard bulunamadı")
        if d["owner_email"] != current_user.get("email") and (current_user.get("role") or "").lower() != "admin":
            raise HTTPException(403, "Sadece sahibi düzenleyebilir")
        await db.custom_dashboards.update_one(
            {"id": dash_id},
            {"$pull": {"widgets": {"id": widget_id}}, "$set": {"updated_at": _now()}},
        )
        return {"ok": True}

    # ─── Widget data endpoint (single dispatch) ────────────────────────
    @router.get("/widget-data/{widget_type}")
    async def widget_data(widget_type: str, property_id: Optional[str] = None,
                            _: dict = Depends(require_roles("admin", "manager"))):
        prop_q = {"property_id": property_id} if property_id and property_id != "all" else {}
        today = datetime.now(timezone.utc).date()
        yesterday = today - timedelta(days=1)

        async def latest_snapshot(date_iso: str):
            return await db.daily_snapshots.find_one({**prop_q, "date": date_iso}, {"_id": 0})

        if widget_type in {"kpi_occupancy", "kpi_adr", "kpi_revpar"}:
            snap_today = await latest_snapshot(today.isoformat()) or {}
            snap_yest  = await latest_snapshot(yesterday.isoformat()) or {}
            field = {"kpi_occupancy": "occupancy_pct", "kpi_adr": "adr", "kpi_revpar": "revpar"}[widget_type]
            v = snap_today.get(field)
            v_y = snap_yest.get(field)
            delta_pct = None
            if v is not None and v_y is not None and v_y != 0:
                delta_pct = round((float(v) - float(v_y)) / float(v_y) * 100, 1)
            return {
                "value": v, "yesterday": v_y, "delta_pct": delta_pct,
                "unit": "%" if widget_type == "kpi_occupancy" else "GBP",
                "label": {"kpi_occupancy": "Occupancy", "kpi_adr": "ADR", "kpi_revpar": "RevPAR"}[widget_type],
            }

        if widget_type == "kpi_pace":
            since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            n = await db.bookings.count_documents({**prop_q, "created_at": {"$gte": since}})
            return {"value": n, "unit": "res", "label": "Pace (24h)"}

        if widget_type == "kpi_pickup":
            since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
            n = await db.bookings.count_documents({**prop_q, "created_at": {"$gte": since}})
            return {"value": n, "unit": "res", "label": "Pickup (7g)"}

        if widget_type == "kpi_roas":
            days_since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
            att = await db.booking_attribution.find({**prop_q, "created_at": {"$gte": days_since}}, {"_id": 0}).to_list(5000)
            rev = sum(float(r.get("value") or 0) for r in att)
            costs = await db.campaign_costs.find(prop_q, {"_id": 0}).to_list(2000)
            cost = sum(float(c.get("cost") or 0) for c in costs)
            roas = round(rev / cost, 2) if cost > 0 else None
            return {"value": roas, "unit": "x", "label": "ROAS (30g)", "cost": cost, "revenue": rev}

        if widget_type == "spark_revenue":
            data = []
            for i in range(6, -1, -1):
                d = (today - timedelta(days=i)).isoformat()
                snap = await latest_snapshot(d) or {}
                data.append({"date": d, "revenue": snap.get("revenue") or 0})
            return {"series": data}

        if widget_type == "hk_summary":
            rooms = await db.rooms.find(prop_q, {"_id": 0}).to_list(500)
            counts: dict = {}
            for r in rooms:
                s = (r.get("housekeeping_status") or "unknown").lower()
                counts[s] = counts.get(s, 0) + 1
            return {"counts": counts, "total_rooms": len(rooms)}

        if widget_type == "alerts_board":
            # Best-effort read from an alerts collection if it exists, else empty
            alerts = await db.alerts.find(prop_q, {"_id": 0}).sort("created_at", -1).to_list(5)
            return {"items": alerts}

        if widget_type == "quick_actions":
            return {"items": [
                {"key": "new_booking", "label": "Yeni Rezervasyon", "target": "bookings"},
                {"key": "check_in",    "label": "Check-in",         "target": "arrivals"},
                {"key": "morning_brief","label": "Morning Brief",   "target": "morning-brief"},
                {"key": "roas",        "label": "ROAS",              "target": "attribution"},
            ]}

        raise HTTPException(404, f"Bilinmeyen widget tipi: {widget_type}")

    return router
