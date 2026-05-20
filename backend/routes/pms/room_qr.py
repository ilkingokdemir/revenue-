"""
Housekeeping / Maintenance Room QR Code Generator
-------------------------------------------------
Generates a printable QR-code sheet (one square per room) that staff can stick
on inside-of-doors. Scanning the QR opens the mobile companion view pre-loaded
to that exact room — instantly showing status board, "mark clean" button,
and a 1-tap "Report maintenance" link. No app install required.

Endpoints:
  GET  /api/room-qr/{property_id}/png/{room_number}     — PNG of single QR
  GET  /api/room-qr/{property_id}/sheet                  — HTML printable sheet
  GET  /api/room-qr/{property_id}/list                   — JSON list (for preview)
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from datetime import datetime, timezone
from typing import Optional
import io
import os
import logging
import qrcode

logger = logging.getLogger(__name__)


def _frontend_base() -> str:
    # Public-facing URL that the staff phone will load on scan.
    base = os.environ.get("PUBLIC_FRONTEND_URL") or os.environ.get("REACT_APP_BACKEND_URL", "")
    return base.rstrip("/")


def create_room_qr_router(db, require_roles):
    router = APIRouter()

    def _qr_png_bytes(url: str) -> bytes:
        qr = qrcode.QRCode(
            version=None, error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10, border=2,
        )
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#0f172a", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def _room_url(property_id: str, room_number: str, kind: str = "hk") -> str:
        base = _frontend_base()
        return f"{base}/room/{property_id}/{room_number}?via={kind}"

    @router.get("/room-qr/{property_id}/list")
    async def list_qrs(property_id: str,
                        current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        rooms = await db.room_statuses.find(
            {"property_id": property_id}, {"_id": 0, "id": 1, "room_number": 1, "floor": 1}
        ).sort("room_number", 1).to_list(500)
        items = []
        for r in rooms:
            rn = str(r.get("room_number", ""))
            items.append({
                "room_number": rn,
                "floor": r.get("floor", ""),
                "qr_url": _room_url(property_id, rn, "hk"),
                "image_url": f"/api/room-qr/{property_id}/png/{rn}",
            })
        return {"property_id": property_id, "count": len(items), "items": items}

    @router.get("/room-qr/{property_id}/png/{room_number}")
    async def png(property_id: str, room_number: str, kind: str = "hk"):
        url = _room_url(property_id, room_number, kind)
        png_bytes = _qr_png_bytes(url)
        return StreamingResponse(
            io.BytesIO(png_bytes),
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=3600"},
        )

    @router.get("/room-qr/{property_id}/sheet", response_class=HTMLResponse)
    async def sheet(property_id: str, kind: str = "hk",
                    current_user: dict = Depends(require_roles("admin", "manager"))):
        rooms = await db.room_statuses.find(
            {"property_id": property_id}, {"_id": 0, "room_number": 1, "floor": 1}
        ).sort("room_number", 1).to_list(500)
        prop = await db.properties.find_one({"id": property_id}, {"_id": 0, "name": 1}) or {}
        prop_name = prop.get("name", property_id)
        if not rooms:
            return HTMLResponse(
                f"<html><body><h2>No rooms seeded for {prop_name}</h2></body></html>",
                status_code=200,
            )

        cards_html = []
        for r in rooms:
            rn = str(r.get("room_number", ""))
            cards_html.append(f"""
              <div class="card">
                <div class="head">
                  <div class="room">Room {rn}</div>
                  <div class="floor">Floor {r.get("floor","")}</div>
                </div>
                <img src="/api/room-qr/{property_id}/png/{rn}?kind={kind}" alt="Room {rn} QR" />
                <div class="hint">Scan for housekeeping & maintenance</div>
                <div class="brand">{prop_name}</div>
              </div>
            """)

        html = f"""<!doctype html>
<html><head>
<meta charset="utf-8" />
<title>Room QR sheet — {prop_name}</title>
<style>
  @page {{ size: A4; margin: 12mm; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         margin: 0; padding: 18px; color: #0f172a; background:#f8fafc; }}
  h1   {{ font-size: 22px; margin: 0 0 4px; }}
  .sub {{ font-size: 12px; color:#64748b; margin: 0 0 18px; }}
  .grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10mm; }}
  .card {{ border: 1.5px dashed #cbd5e1; border-radius: 12px;
          padding: 12px; background:#fff; text-align:center; page-break-inside: avoid; }}
  .head {{ display:flex; justify-content:space-between; font-size:11px; color:#475569; }}
  .room {{ font-weight: 700; font-size: 14px; color:#0f172a; }}
  .floor {{ background:#f1f5f9; padding:2px 6px; border-radius:6px; }}
  img  {{ width: 100%; max-width: 220px; margin: 6px 0; }}
  .hint {{ font-size: 10px; color:#64748b; }}
  .brand {{ font-size: 9px; color:#94a3b8; margin-top: 4px; }}
  .toolbar {{ position: fixed; top: 8px; right: 8px; }}
  @media print {{ .toolbar {{ display:none; }} body {{ background:#fff; }} }}
</style></head>
<body>
  <div class="toolbar"><button onclick="window.print()">Print</button></div>
  <h1>{prop_name} — Room QR codes</h1>
  <p class="sub">{len(rooms)} rooms · scan to open the mobile housekeeping/maintenance view for that room.</p>
  <div class="grid">{''.join(cards_html)}</div>
</body></html>"""
        return HTMLResponse(content=html)

    return router
