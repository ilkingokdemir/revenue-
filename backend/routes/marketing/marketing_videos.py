"""
Marketing Video Generator (Sora 2 integration).

Auto-generates 4/8/12 second Instagram/TikTok-ready promotional videos for:
  - Public events (hooks into routes/public_events.py)
  - Properties (general hotel showcase)
  - Ad-hoc prompts

Videos saved to /app/backend/uploads/marketing_videos/ and served via the
existing static file route. A `video_jobs` collection tracks job state since
generation takes 2-5 minutes.

Background execution: we run the synchronous Sora 2 SDK call in a thread pool
so it doesn't block the event loop, and store the resulting job state in Mongo.

Endpoints
---------
  GET  /api/marketing-videos/sizes        — supported sizes/durations/models
  POST /api/marketing-videos/generate     — body: {prompt, size?, duration?, model?, source_type?, source_id?}
  GET  /api/marketing-videos              — list jobs (admin/manager)
  GET  /api/marketing-videos/{job_id}     — single job state
  POST /api/marketing-videos/from-event/{event_id} — auto-prompt from public event metadata
"""
from datetime import datetime, timezone
import asyncio
import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger(__name__)

VIDEOS_DIR = Path("/app/backend/uploads/marketing_videos")
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

SUPPORTED_SIZES = ["1280x720", "1792x1024", "1024x1792", "1024x1024"]
SUPPORTED_DURATIONS = [4, 8, 12]
SUPPORTED_MODELS = ["sora-2", "sora-2-pro"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _public_video_url(filename: str) -> str:
    base = os.environ.get("PUBLIC_BACKEND_URL", "")
    return f"{base}/api/uploads/marketing_videos/{filename}"


def _generate_blocking(prompt: str, output_path: str, model: str,
                       size: str, duration: int) -> str:
    """Synchronous Sora 2 SDK call. Runs in thread executor."""
    from emergentintegrations.llm.openai.video_generation import OpenAIVideoGeneration
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise RuntimeError("EMERGENT_LLM_KEY not configured")
    gen = OpenAIVideoGeneration(api_key=api_key)
    max_wait = 900 if (duration >= 12 or model == "sora-2-pro") else 600
    video_bytes = gen.text_to_video(
        prompt=prompt, model=model, size=size,
        duration=duration, max_wait_time=max_wait,
    )
    if not video_bytes:
        raise RuntimeError("Sora 2 returned empty video")
    gen.save_video(video_bytes, output_path)
    return output_path


async def _run_job(db, job_id: str, prompt: str, model: str, size: str, duration: int):
    """Background runner that updates job status as work progresses."""
    filename = f"{job_id}.mp4"
    output_path = str(VIDEOS_DIR / filename)
    try:
        await db.video_jobs.update_one(
            {"id": job_id},
            {"$set": {"status": "rendering",
                      "started_render_at": _now_iso()}}
        )
        # Run blocking SDK in thread executor
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            _generate_blocking,
            prompt, output_path, model, size, duration,
        )
        # Confirm file exists & report size
        size_bytes = os.path.getsize(output_path) if os.path.exists(output_path) else 0
        await db.video_jobs.update_one(
            {"id": job_id},
            {"$set": {"status": "completed",
                      "completed_at": _now_iso(),
                      "filename": filename,
                      "file_size_bytes": size_bytes,
                      "public_url": _public_video_url(filename),
                      "static_path": f"/api/uploads/marketing_videos/{filename}"}}
        )
        logger.info(f"Sora job {job_id} completed → {output_path} ({size_bytes} bytes)")
    except Exception as e:
        logger.exception(f"Sora job {job_id} failed")
        await db.video_jobs.update_one(
            {"id": job_id},
            {"$set": {"status": "failed",
                      "failed_at": _now_iso(),
                      "error": str(e)[:500]}}
        )


def create_marketing_videos_router(db, require_roles):
    router = APIRouter()

    @router.get("/marketing-videos/sizes")
    async def sizes(_: dict = Depends(require_roles("admin", "manager"))):
        return {
            "sizes": SUPPORTED_SIZES,
            "durations": SUPPORTED_DURATIONS,
            "models": SUPPORTED_MODELS,
            "default_size": "1024x1792",  # portrait — best for IG/TikTok
            "default_duration": 8,
            "default_model": "sora-2",
        }

    @router.post("/marketing-videos/generate")
    async def generate(body: dict,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        prompt = (body.get("prompt") or "").strip()
        if not prompt:
            raise HTTPException(400, "prompt required")
        size = body.get("size") or "1024x1792"
        duration = int(body.get("duration") or 8)
        model = body.get("model") or "sora-2"
        if size not in SUPPORTED_SIZES:
            raise HTTPException(400, f"size must be one of {SUPPORTED_SIZES}")
        if duration not in SUPPORTED_DURATIONS:
            raise HTTPException(400, f"duration must be one of {SUPPORTED_DURATIONS}")
        if model not in SUPPORTED_MODELS:
            raise HTTPException(400, f"model must be one of {SUPPORTED_MODELS}")
        job_id = str(uuid.uuid4())
        job = {
            "id": job_id,
            "prompt": prompt,
            "size": size,
            "duration": duration,
            "model": model,
            "source_type": body.get("source_type", "manual"),
            "source_id": body.get("source_id"),
            "property_id": body.get("property_id"),
            "status": "queued",
            "created_at": _now_iso(),
            "created_by": current_user.get("name", ""),
        }
        await db.video_jobs.insert_one(job)
        # Fire-and-forget background task
        asyncio.create_task(_run_job(db, job_id, prompt, model, size, duration))
        job.pop("_id", None)
        return {
            **job,
            "note": "Generation 2-5 minutes. Poll GET /api/marketing-videos/{id} for status.",
        }

    @router.get("/marketing-videos")
    async def list_jobs(source_type: str = "", status: str = "", limit: int = 50,
                         _: dict = Depends(require_roles("admin", "manager"))):
        q: dict = {}
        if source_type:
            q["source_type"] = source_type
        if status:
            q["status"] = status
        items = await db.video_jobs.find(q, {"_id": 0}).sort(
            "created_at", -1
        ).to_list(min(limit, 200))
        return {"items": items, "count": len(items)}

    @router.get("/marketing-videos/{job_id}")
    async def get_job(job_id: str,
                      _: dict = Depends(require_roles("admin", "manager"))):
        job = await db.video_jobs.find_one({"id": job_id}, {"_id": 0})
        if not job:
            raise HTTPException(404, "Job not found")
        return job

    @router.post("/marketing-videos/from-event/{event_id}")
    async def from_event(event_id: str, body: dict = None,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        body = body or {}
        ev = await db.public_events.find_one({"id": event_id}, {"_id": 0})
        if not ev:
            raise HTTPException(404, "Event not found")
        prop = await db.properties.find_one(
            {"id": ev.get("property_id")}, {"_id": 0, "name": 1, "city": 1}
        )
        prop_name = (prop or {}).get("name", "lüks bir otelde")
        prop_city = (prop or {}).get("city", "şehirde")
        # Build a richly-described prompt from event metadata
        tags_text = ", ".join(ev.get("tags", []))
        auto_prompt = (
            f"A 8-second cinematic, vertical Instagram/TikTok promotional video "
            f"for an upscale hotel event '{ev['title']}' at {prop_name} in {prop_city}. "
            f"The scene shows: {ev.get('description', '')[:300]}. "
            f"Atmosphere: {tags_text or 'elegant, warm lighting, golden hour'}. "
            f"Sweeping cinematic camera, slow motion details — glasses clinking, "
            f"smiling guests, plated dishes steaming, candles flickering. "
            f"Cinematic color grading, end on the event title overlay '{ev['title']}'. "
            f"No on-screen text other than the title."
        )
        prompt = body.get("prompt_override") or auto_prompt
        size = body.get("size") or "1024x1792"  # portrait for social
        duration = int(body.get("duration") or 8)
        model = body.get("model") or "sora-2"
        if size not in SUPPORTED_SIZES:
            raise HTTPException(400, f"size must be one of {SUPPORTED_SIZES}")
        job_id = str(uuid.uuid4())
        job = {
            "id": job_id,
            "prompt": prompt,
            "size": size,
            "duration": duration,
            "model": model,
            "source_type": "public_event",
            "source_id": event_id,
            "property_id": ev.get("property_id"),
            "event_title": ev.get("title"),
            "event_slug": ev.get("slug"),
            "status": "queued",
            "created_at": _now_iso(),
            "created_by": current_user.get("name", ""),
        }
        await db.video_jobs.insert_one(job)
        asyncio.create_task(_run_job(db, job_id, prompt, model, size, duration))
        job.pop("_id", None)
        return {**job, "note": "Auto-generated from event metadata. Poll job for status."}

    return router
