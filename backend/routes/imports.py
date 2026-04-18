"""
Import Module — bulk import bookings, guests, rooms, rate plans from CSV/XLSX.
Competitor tagged this "Missing" — we're delivering it.

Flow:
  1. POST /imports/parse  — upload file, return {headers, sample_rows, rows_count, file_token}
  2. POST /imports/create — create job with {entity, property_id, file_token, mapping}
  3. POST /imports/{id}/dry-run — validate without committing; return warnings/errors
  4. POST /imports/{id}/run — execute the import; returns per-row outcome
  5. GET /imports — list history, paginated
  6. GET /imports/{id} — status + error detail
  7. DELETE /imports/{id} — remove job record (files auto-expire)

Supported entities:
  - bookings: guest_name, email, phone, check_in, check_out, room_type, rate, status
  - guests:   name, email, phone, nationality, notes
  - rooms:    room_number, room_type, floor, status
  - rate_plans: name, room_type, base_rate, currency, policy

Files cached in /tmp/imports/ keyed by uuid; older than 1h get pruned.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import uuid
import os
import io
import csv
import json
import logging

logger = logging.getLogger(__name__)

UPLOAD_DIR = "/tmp/imports"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# -------- Schemas per entity --------
# required: must be mapped | optional: can be mapped | transform: coerce fn
ENTITY_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "bookings": {
        "label": "Bookings",
        "icon": "calendar",
        "description": "Import reservations (guests + dates + rooms)",
        "required": ["guest_name", "check_in", "check_out"],
        "optional": ["email", "phone", "room_number", "room_type", "rate", "currency", "status", "source", "notes", "adults", "children"],
        "collection": "bookings",
    },
    "guests": {
        "label": "Guests",
        "icon": "users",
        "description": "Import guest profiles",
        "required": ["name"],
        "optional": ["email", "phone", "nationality", "date_of_birth", "address", "notes", "vip", "tags"],
        "collection": "guests",
    },
    "rooms": {
        "label": "Rooms",
        "icon": "bed",
        "description": "Import room inventory",
        "required": ["room_number"],
        "optional": ["room_type", "floor", "status", "max_occupancy", "amenities"],
        "collection": "rooms",
    },
    "rate_plans": {
        "label": "Rate Plans",
        "icon": "chart-line",
        "description": "Import rate plans",
        "required": ["name", "base_rate"],
        "optional": ["room_type", "currency", "policy", "min_stay", "max_stay", "cancellation_policy"],
        "collection": "rate_plans",
    },
}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _parse_file(content: bytes, filename: str) -> Dict:
    """Parse CSV/XLSX into headers + rows. Limit to 10k rows for safety."""
    fn = filename.lower()
    if fn.endswith(".csv") or fn.endswith(".txt"):
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = content.decode("latin-1", errors="replace")
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
    elif fn.endswith(".xlsx") or fn.endswith(".xls"):
        try:
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            ws = wb.active
            rows = []
            for r in ws.iter_rows(values_only=True):
                rows.append([("" if v is None else str(v)) for v in r])
        except Exception as e:
            raise HTTPException(400, f"Could not parse XLSX: {str(e)[:100]}")
    else:
        raise HTTPException(400, "Unsupported file type. Use .csv, .xlsx or .xls")

    if not rows:
        raise HTTPException(400, "File is empty")
    if len(rows) > 10001:
        raise HTTPException(400, f"File too large ({len(rows)-1} rows). Max 10,000 rows per import.")

    headers = [h.strip() for h in rows[0]]
    data_rows = rows[1:]
    if not headers:
        raise HTTPException(400, "No headers found")

    # Normalize: skip empty trailing rows
    while data_rows and all((c is None or str(c).strip() == "") for c in data_rows[-1]):
        data_rows.pop()

    return {
        "headers": headers,
        "rows_count": len(data_rows),
        "sample_rows": data_rows[:5],
        "all_rows": data_rows,
    }


def _auto_map(headers: List[str], entity: str) -> Dict[str, str]:
    """Best-guess mapping from CSV headers → canonical fields."""
    schema = ENTITY_SCHEMAS[entity]
    all_fields = schema["required"] + schema["optional"]
    mapping = {}
    lower_headers = [h.lower().replace(" ", "_").replace("-", "_") for h in headers]
    for field in all_fields:
        # Try exact match first
        if field in lower_headers:
            mapping[field] = headers[lower_headers.index(field)]
            continue
        # Try common aliases
        aliases = {
            "guest_name": ["name", "guest", "customer_name", "full_name"],
            "check_in": ["arrival", "arrival_date", "from", "from_date", "checkin"],
            "check_out": ["departure", "departure_date", "to", "to_date", "checkout"],
            "email": ["email_address", "mail", "e_mail"],
            "phone": ["telephone", "mobile", "phone_number", "tel"],
            "room_number": ["room", "room_no", "unit"],
            "room_type": ["category", "room_category", "type"],
            "rate": ["price", "amount", "total", "cost"],
            "nationality": ["country", "nation"],
            "date_of_birth": ["dob", "birthdate", "birth_date"],
            "base_rate": ["rate", "price", "amount"],
        }
        for alias in aliases.get(field, []):
            if alias in lower_headers:
                mapping[field] = headers[lower_headers.index(alias)]
                break
    return mapping


def _validate_row(row_dict: Dict, entity: str, row_num: int) -> Optional[str]:
    """Return error message or None if valid."""
    schema = ENTITY_SCHEMAS[entity]
    for req in schema["required"]:
        val = row_dict.get(req, "")
        if val is None or str(val).strip() == "":
            return f"Missing required field: {req}"
    # Date coercion for bookings
    if entity == "bookings":
        for d in ["check_in", "check_out"]:
            try:
                v = row_dict.get(d)
                if v:
                    datetime.fromisoformat(str(v).split("T")[0])
            except Exception:
                return f"Invalid date in {d}: '{row_dict.get(d)}'. Use YYYY-MM-DD"
    return None


def _apply_mapping(all_rows: List[List[str]], headers: List[str], mapping: Dict[str, str]) -> List[Dict]:
    """Transform rows into list of {field: value} dicts based on mapping."""
    header_idx = {h: i for i, h in enumerate(headers)}
    result = []
    for r in all_rows:
        record = {}
        for canon_field, csv_header in mapping.items():
            if not csv_header:
                continue
            idx = header_idx.get(csv_header)
            if idx is None or idx >= len(r):
                continue
            val = r[idx]
            if val is None:
                continue
            record[canon_field] = str(val).strip()
        result.append(record)
    return result


def create_imports_router(db, require_roles, get_current_user):
    router = APIRouter()

    @router.get("/imports/schemas")
    async def get_schemas(current_user: dict = Depends(get_current_user)):
        """Return all entity schemas for the UI."""
        out = {}
        for k, v in ENTITY_SCHEMAS.items():
            out[k] = {
                "label": v["label"],
                "icon": v["icon"],
                "description": v["description"],
                "required": v["required"],
                "optional": v["optional"],
                "all_fields": v["required"] + v["optional"],
            }
        return {"entities": out}

    @router.post("/imports/parse")
    async def parse_upload(file: UploadFile = File(...),
                           entity: str = Form(...),
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        if entity not in ENTITY_SCHEMAS:
            raise HTTPException(400, f"Unknown entity '{entity}'. Use: {list(ENTITY_SCHEMAS.keys())}")

        content = await file.read()
        if len(content) > 20 * 1024 * 1024:
            raise HTTPException(413, "File too large (max 20MB)")

        parsed = _parse_file(content, file.filename)
        file_token = str(uuid.uuid4())
        cache_path = os.path.join(UPLOAD_DIR, f"{file_token}.json")
        with open(cache_path, "w") as f:
            json.dump({
                "headers": parsed["headers"],
                "rows": parsed["all_rows"],
                "filename": file.filename,
                "cached_at": _now(),
            }, f)

        auto_mapping = _auto_map(parsed["headers"], entity)
        return {
            "file_token": file_token,
            "filename": file.filename,
            "entity": entity,
            "headers": parsed["headers"],
            "rows_count": parsed["rows_count"],
            "sample_rows": parsed["sample_rows"],
            "auto_mapping": auto_mapping,
            "schema": {
                "required": ENTITY_SCHEMAS[entity]["required"],
                "optional": ENTITY_SCHEMAS[entity]["optional"],
            },
        }

    # ------- CREATE JOB -------
    class CreateJobBody(BaseModel):
        entity: str
        file_token: str
        property_id: Optional[str] = None
        mapping: Dict[str, str]  # {canonical_field: csv_header}
        skip_duplicates_by: Optional[str] = None  # e.g. "email" for guests

    @router.post("/imports")
    async def create_job(body: CreateJobBody,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        if body.entity not in ENTITY_SCHEMAS:
            raise HTTPException(400, "Unknown entity")
        cache_path = os.path.join(UPLOAD_DIR, f"{body.file_token}.json")
        if not os.path.exists(cache_path):
            raise HTTPException(404, "Upload expired or not found. Re-upload the file.")

        # Validate required fields are mapped
        required = ENTITY_SCHEMAS[body.entity]["required"]
        missing = [r for r in required if not body.mapping.get(r)]
        if missing:
            raise HTTPException(400, f"Required fields not mapped: {missing}")

        job = {
            "id": str(uuid.uuid4()),
            "entity": body.entity,
            "property_id": body.property_id,
            "file_token": body.file_token,
            "mapping": body.mapping,
            "skip_duplicates_by": body.skip_duplicates_by,
            "status": "draft",  # draft | dry_run | running | done | failed
            "created_by_id": current_user.get("id"),
            "created_by_name": current_user.get("name"),
            "created_at": _now(),
            "updated_at": _now(),
            "summary": None,
            "errors": [],
        }
        await db.import_jobs.insert_one(job)
        job.pop("_id", None)
        return job

    # ------- DRY-RUN -------
    @router.post("/imports/{job_id}/dry-run")
    async def dry_run(job_id: str,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        job = await db.import_jobs.find_one({"id": job_id}, {"_id": 0})
        if not job:
            raise HTTPException(404, "Job not found")
        cache_path = os.path.join(UPLOAD_DIR, f"{job['file_token']}.json")
        if not os.path.exists(cache_path):
            raise HTTPException(404, "Upload expired")
        with open(cache_path) as f:
            cache = json.load(f)

        records = _apply_mapping(cache["rows"], cache["headers"], job["mapping"])
        errors = []
        valid_count = 0
        for i, rec in enumerate(records, start=2):  # +2 because header=1
            err = _validate_row(rec, job["entity"], i)
            if err:
                errors.append({"row": i, "error": err, "data": rec})
            else:
                valid_count += 1

        summary = {
            "total": len(records),
            "valid": valid_count,
            "errors": len(errors),
            "preview": records[:3],
        }
        await db.import_jobs.update_one(
            {"id": job_id},
            {"$set": {"status": "dry_run", "summary": summary, "errors": errors[:100], "updated_at": _now()}}
        )
        return {**summary, "errors_sample": errors[:20]}

    # ------- RUN -------
    @router.post("/imports/{job_id}/run")
    async def run_import(job_id: str,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        job = await db.import_jobs.find_one({"id": job_id}, {"_id": 0})
        if not job:
            raise HTTPException(404, "Job not found")
        if job["status"] == "running":
            raise HTTPException(400, "Import already running")
        if job["status"] == "done":
            raise HTTPException(400, "Import already completed")

        cache_path = os.path.join(UPLOAD_DIR, f"{job['file_token']}.json")
        if not os.path.exists(cache_path):
            raise HTTPException(404, "Upload expired — re-upload and re-create the job")
        with open(cache_path) as f:
            cache = json.load(f)

        await db.import_jobs.update_one({"id": job_id}, {"$set": {"status": "running", "updated_at": _now()}})

        records = _apply_mapping(cache["rows"], cache["headers"], job["mapping"])
        collection = ENTITY_SCHEMAS[job["entity"]]["collection"]
        inserted = 0
        skipped = 0
        failed = 0
        errors = []
        dedup_key = job.get("skip_duplicates_by")

        for i, rec in enumerate(records, start=2):
            err = _validate_row(rec, job["entity"], i)
            if err:
                errors.append({"row": i, "error": err, "data": rec})
                failed += 1
                continue
            # Skip duplicates if configured
            if dedup_key and rec.get(dedup_key):
                existing = await db[collection].find_one({dedup_key: rec[dedup_key]}, {"_id": 1})
                if existing:
                    skipped += 1
                    continue
            # Insert with import metadata
            rec["id"] = str(uuid.uuid4())
            rec["_imported_from"] = job_id
            rec["_imported_at"] = _now()
            if job.get("property_id"):
                rec["property_id"] = job["property_id"]
            rec["created_at"] = _now()
            try:
                await db[collection].insert_one(rec)
                inserted += 1
            except Exception as e:
                errors.append({"row": i, "error": str(e)[:100], "data": rec})
                failed += 1

        summary = {
            "total": len(records),
            "inserted": inserted,
            "skipped": skipped,
            "failed": failed,
        }
        await db.import_jobs.update_one(
            {"id": job_id},
            {"$set": {
                "status": "done" if failed == 0 else ("done" if inserted > 0 else "failed"),
                "summary": summary,
                "errors": errors[:500],
                "completed_at": _now(),
                "updated_at": _now(),
            }}
        )
        return summary

    # ------- LIST / GET / DELETE -------
    @router.get("/imports")
    async def list_jobs(entity: str = "", status: str = "",
                        current_user: dict = Depends(require_roles("admin", "manager"))):
        q = {}
        if entity:
            q["entity"] = entity
        if status:
            q["status"] = status
        jobs = await db.import_jobs.find(q, {"_id": 0, "errors": 0}).sort("created_at", -1).to_list(200)
        return {"jobs": jobs, "total": len(jobs)}

    @router.get("/imports/{job_id}")
    async def get_job(job_id: str,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        j = await db.import_jobs.find_one({"id": job_id}, {"_id": 0})
        if not j:
            raise HTTPException(404, "Job not found")
        return j

    @router.delete("/imports/{job_id}")
    async def delete_job(job_id: str,
                         current_user: dict = Depends(require_roles("admin"))):
        r = await db.import_jobs.delete_one({"id": job_id})
        if r.deleted_count == 0:
            raise HTTPException(404, "Job not found")
        return {"ok": True}

    return router
