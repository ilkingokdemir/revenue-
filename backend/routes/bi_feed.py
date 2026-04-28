"""
BI Feed — Power BI OData + Tableau WDC + Universal CSV.

External BI tools authenticate via long-lived API tokens (not session cookies).
Each property has tokens; tokens scoped to read-only feed access.

OData v4 minimal-subset compliance:
  GET /bi/odata?token=X            — service catalog
  GET /bi/odata/$metadata?token=X  — XML metadata
  GET /bi/odata/{Entity}?token=X   — entity collection (JSON)
  Supports: $top, $skip, $filter (basic eq/gt/lt on date fields)

Tableau WDC:
  GET /bi/tableau-wdc.html?token=X — self-contained HTML page

Universal CSV:
  GET /bi/csv/{entity}?token=X     — RFC 4180 CSV download

Entities:
  Bookings, Tips, FnbTabs, Inquiries, CleanlinessScores, Anomalies (last 365 days)
"""
from fastapi import APIRouter, Depends, HTTPException, Response, Request
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta, date
from typing import Optional, List, Dict, Any
import uuid
import logging
import csv as _csv
import io

logger = logging.getLogger(__name__)


class TokenCreateReq(BaseModel):
    property_id: str
    name: str
    expires_days: int = 365


ENTITIES = {
    "Bookings": {
        "collection": "bookings",
        "fields": ["id", "booking_ref", "guest_name", "guest_email", "check_in", "check_out",
                   "nights", "adults", "children", "total_price", "currency", "status",
                   "room_type", "channel", "created_at", "property_id"],
        "date_fields": ["check_in", "check_out", "created_at"],
    },
    "Tips": {
        "collection": "tips",
        "fields": ["id", "session_id", "amount", "currency", "status", "staff_role",
                   "staff_name", "guest_name", "message", "created_at", "paid_at", "property_id"],
        "date_fields": ["created_at", "paid_at"],
    },
    "FnbTabs": {
        "collection": "fnb_tabs",
        "fields": ["id", "ref", "outlet", "guest_name", "table_number", "party_size",
                   "subtotal", "tip_amount", "discount_amount", "total", "status",
                   "payment_method", "opened_at", "closed_at", "property_id"],
        "date_fields": ["opened_at", "closed_at"],
    },
    "Inquiries": {
        "collection": "conf_inquiries",
        "fields": ["id", "ref", "event_name", "event_type", "contact_name", "contact_company",
                   "start_date", "end_date", "days", "total_attendees", "proposal_total",
                   "status", "created_at", "property_id"],
        "date_fields": ["start_date", "end_date", "created_at"],
    },
    "CleanlinessScores": {
        "collection": "hk_cleanliness_scores",
        "fields": ["id", "room_id", "score", "severity", "photo_count", "scored_at",
                   "scored_by", "property_id"],
        "date_fields": ["scored_at"],
    },
    "WorkOrders": {
        "collection": "ops_workorders",
        "fields": ["id", "title", "category", "priority", "status", "room_id",
                   "reported_by", "assigned_to", "reported_at", "completed_at", "property_id"],
        "date_fields": ["reported_at", "completed_at"],
    },
}


def _odata_metadata_xml() -> str:
    """Minimal OData v4 metadata XML."""
    rows = []
    for ent, cfg in ENTITIES.items():
        props = []
        for f in cfg["fields"]:
            t = "Edm.DateTimeOffset" if f in cfg.get("date_fields", []) else "Edm.String"
            if f in ("amount", "total_price", "subtotal", "total", "tip_amount", "discount_amount", "proposal_total", "score", "nights", "adults", "children", "party_size", "days", "total_attendees", "photo_count"):
                t = "Edm.Decimal"
            props.append(f'<Property Name="{f}" Type="{t}" />')
        rows.append(f'<EntityType Name="{ent}"><Key><PropertyRef Name="id" /></Key>{"".join(props)}</EntityType>')
        rows.append(f'<EntitySet Name="{ent}" EntityType="HotelBox.{ent}" />')
    types_xml = "".join([r for r in rows if r.startswith("<EntityType")])
    sets_xml = "".join([r for r in rows if r.startswith("<EntitySet")])
    return f'''<?xml version="1.0" encoding="utf-8"?>
<edmx:Edmx xmlns:edmx="http://docs.oasis-open.org/odata/ns/edmx" Version="4.0">
  <edmx:DataServices>
    <Schema xmlns="http://docs.oasis-open.org/odata/ns/edm" Namespace="HotelBox">
      {types_xml}
      <EntityContainer Name="HotelBoxContainer">
        {sets_xml}
      </EntityContainer>
    </Schema>
  </edmx:DataServices>
</edmx:Edmx>'''


def _parse_filter(filter_str: str) -> dict:
    """Tiny OData $filter parser supporting eq/gt/lt/ge/le on date strings."""
    if not filter_str:
        return {}
    q = {}
    # Very tolerant: split by 'and'
    for clause in filter_str.split(" and "):
        clause = clause.strip()
        for op_str, mongo_op in [(" eq ", "$eq"), (" ne ", "$ne"), (" gt ", "$gt"),
                                  (" lt ", "$lt"), (" ge ", "$gte"), (" le ", "$lte")]:
            if op_str in clause:
                parts = clause.split(op_str, 1)
                if len(parts) == 2:
                    field = parts[0].strip()
                    val = parts[1].strip().strip("'\"")
                    q.setdefault(field, {})[mongo_op] = val
                break
    return q


async def _verify_token(db, token: str) -> dict:
    if not token:
        raise HTTPException(401, "Token required (?token=...)")
    tok = await db.bi_tokens.find_one({"token": token, "revoked": {"$ne": True}}, {"_id": 0})
    if not tok:
        raise HTTPException(401, "Invalid token")
    if datetime.now(timezone.utc) > datetime.fromisoformat(tok["expires_at"].replace("Z", "+00:00")):
        raise HTTPException(401, "Token expired")
    return tok


def create_bi_feed_router(db, require_roles):
    router = APIRouter()

    # ---------- TOKEN MANAGEMENT (admin only) ----------
    @router.get("/bi/tokens/{property_id}")
    async def list_tokens(property_id: str,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        rows = await db.bi_tokens.find({"property_id": property_id}, {"_id": 0}).sort("created_at", -1).to_list(100)
        # Mask token in middle for safety
        for r in rows:
            t = r.get("token", "")
            if len(t) > 12:
                r["token_masked"] = f"{t[:6]}...{t[-4:]}"
            else:
                r["token_masked"] = t
        return {"rows": rows, "count": len(rows)}

    @router.post("/bi/tokens")
    async def create_token(req: TokenCreateReq,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        if req.expires_days < 1 or req.expires_days > 3650:
            raise HTTPException(400, "expires_days must be 1..3650")
        if not req.name.strip():
            raise HTTPException(400, "name required")
        token = f"hbk_{uuid.uuid4().hex}"
        now = datetime.now(timezone.utc)
        doc = {
            "id": str(uuid.uuid4()),
            "token": token,
            "name": req.name.strip(),
            "property_id": req.property_id,
            "created_at": now.isoformat(),
            "created_by": current_user.get("email"),
            "expires_at": (now + timedelta(days=req.expires_days)).isoformat(),
            "revoked": False,
            "last_used_at": None,
            "use_count": 0,
        }
        await db.bi_tokens.insert_one(doc)
        return {k: v for k, v in doc.items() if k != "_id"}

    @router.delete("/bi/tokens/{token_id}")
    async def revoke_token(token_id: str,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        result = await db.bi_tokens.update_one(
            {"id": token_id},
            {"$set": {"revoked": True, "revoked_at": datetime.now(timezone.utc).isoformat()}}
        )
        if result.matched_count == 0:
            raise HTTPException(404, "Token not found")
        return {"revoked": True}

    # ---------- ODATA SERVICE CATALOG ----------
    @router.get("/bi/odata")
    async def odata_root(token: str = ""):
        await _verify_token(db, token)
        return {
            "@odata.context": "$metadata",
            "value": [{"name": e, "kind": "EntitySet", "url": e} for e in ENTITIES.keys()],
        }

    @router.get("/bi/odata/$metadata")
    async def odata_metadata(token: str = ""):
        await _verify_token(db, token)
        return Response(content=_odata_metadata_xml(), media_type="application/xml")

    # ---------- ODATA ENTITY COLLECTION ----------
    @router.get("/bi/odata/{entity}")
    async def odata_entity(entity: str, request: Request,
                           token: str = "", top: int = 1000, skip: int = 0,
                           filter: Optional[str] = None):
        tok = await _verify_token(db, token)
        if entity not in ENTITIES:
            raise HTTPException(404, f"Unknown entity. Valid: {sorted(ENTITIES.keys())}")
        if top < 1 or top > 5000:
            raise HTTPException(400, "$top must be 1..5000")

        cfg = ENTITIES[entity]
        q = {"property_id": tok["property_id"]}
        if filter:
            q.update(_parse_filter(filter))

        projection = {f: 1 for f in cfg["fields"]}
        projection["_id"] = 0
        rows = await db[cfg["collection"]].find(q, projection).skip(skip).limit(top).to_list(top)
        # Stamp last_used
        await db.bi_tokens.update_one(
            {"token": token},
            {"$set": {"last_used_at": datetime.now(timezone.utc).isoformat()}, "$inc": {"use_count": 1}}
        )
        return {
            "@odata.context": f"$metadata#{entity}",
            "@odata.count": len(rows),
            "value": rows,
        }

    # ---------- CSV DOWNLOAD ----------
    @router.get("/bi/csv/{entity}")
    async def csv_download(entity: str, token: str = "", top: int = 5000):
        tok = await _verify_token(db, token)
        if entity not in ENTITIES:
            raise HTTPException(404, f"Unknown entity. Valid: {sorted(ENTITIES.keys())}")
        if top < 1 or top > 50000:
            raise HTTPException(400, "top must be 1..50000")

        cfg = ENTITIES[entity]
        projection = {f: 1 for f in cfg["fields"]}
        projection["_id"] = 0
        rows = await db[cfg["collection"]].find({"property_id": tok["property_id"]}, projection).limit(top).to_list(top)

        buf = io.StringIO()
        writer = _csv.DictWriter(buf, fieldnames=cfg["fields"], extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow({f: r.get(f, "") for f in cfg["fields"]})
        await db.bi_tokens.update_one(
            {"token": token},
            {"$set": {"last_used_at": datetime.now(timezone.utc).isoformat()}, "$inc": {"use_count": 1}}
        )
        return Response(
            content=buf.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{entity}-{date.today().isoformat()}.csv"'},
        )

    # ---------- TABLEAU WDC ----------
    @router.get("/bi/tableau-wdc.html")
    async def tableau_wdc():
        # Self-contained HTML for Tableau Web Data Connector v2.x
        entities_json = ",".join(f'"{e}"' for e in ENTITIES.keys())
        return Response(content=f"""<!DOCTYPE html>
<html><head><title>HotelBox Tableau WDC</title>
<meta charset="utf-8"/>
<script src="https://connectors.tableau.com/libs/tableauwdc-2.3.latest.js"></script>
<style>body{{font-family:system-ui;padding:20px;max-width:500px;margin:auto}}
input,select,button{{display:block;width:100%;padding:8px;margin:8px 0;font-size:14px}}
button{{background:#0d9488;color:white;border:0;border-radius:4px;cursor:pointer}}</style>
</head><body>
<h2>HotelBox → Tableau</h2>
<p>Enter your BI feed token and choose an entity:</p>
<input id="tok" placeholder="hbk_xxxx..." />
<select id="ent">{"".join(f'<option value="{e}">{e}</option>' for e in ENTITIES.keys())}</select>
<button onclick="submit()">Connect</button>
<script>
const ENTITIES = [{entities_json}];
const myConnector = tableau.makeConnector();
myConnector.getSchema = function(cb) {{
  const cfg = JSON.parse(tableau.connectionData);
  const cols = cfg.fields.map(f => ({{
    id: f,
    dataType: cfg.dateFields.includes(f) ? tableau.dataTypeEnum.datetime : tableau.dataTypeEnum.string
  }}));
  cb([{{ id: cfg.entity, alias: cfg.entity, columns: cols }}]);
}};
myConnector.getData = function(table, done) {{
  const cfg = JSON.parse(tableau.connectionData);
  fetch(window.location.origin + "/api/bi/odata/" + cfg.entity + "?token=" + cfg.token + "&top=5000")
    .then(r => r.json()).then(j => {{ table.appendRows(j.value || []); done(); }})
    .catch(e => {{ tableau.abortWithError(e.toString()); }});
}};
tableau.registerConnector(myConnector);
function submit() {{
  const tok = document.getElementById('tok').value.trim();
  const ent = document.getElementById('ent').value;
  // Field map (we'll fetch from /metadata in the future, hardcode here)
  const FIELD_MAP = {{
    {",".join(f'"{e}":{{"fields":{cfg["fields"]},"dateFields":{cfg.get("date_fields",[])}}}' for e, cfg in ENTITIES.items())}
  }};
  const cfg = FIELD_MAP[ent];
  tableau.connectionData = JSON.stringify({{ token: tok, entity: ent, fields: cfg.fields, dateFields: cfg.dateFields }});
  tableau.connectionName = "HotelBox " + ent;
  tableau.submit();
}}
</script></body></html>""", media_type="text/html")

    # ---------- HELP / SAMPLES (admin) ----------
    @router.get("/bi/sample-urls/{token_id}")
    async def sample_urls(token_id: str, request: Request,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        tok = await db.bi_tokens.find_one({"id": token_id}, {"_id": 0})
        if not tok:
            raise HTTPException(404, "Token not found")
        base = str(request.base_url).rstrip("/")
        t = tok["token"]
        return {
            "odata_root": f"{base}/api/bi/odata?token={t}",
            "odata_metadata": f"{base}/api/bi/odata/$metadata?token={t}",
            "csv_examples": {e: f"{base}/api/bi/csv/{e}?token={t}" for e in ENTITIES.keys()},
            "odata_examples": {e: f"{base}/api/bi/odata/{e}?token={t}&top=100" for e in ENTITIES.keys()},
            "tableau_wdc": f"{base}/api/bi/tableau-wdc.html",
            "powerbi_instructions": [
                "Power BI Desktop → Get Data → OData feed",
                f"URL: {base}/api/bi/odata?token={t}",
                "Authentication: Anonymous",
            ],
            "excel_instructions": [
                "Excel → Data → Get Data → From Other Sources → From OData Feed",
                f"URL: {base}/api/bi/odata?token={t}",
            ],
            "entities": list(ENTITIES.keys()),
        }

    return router
