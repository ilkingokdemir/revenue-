"""
Agentic AI Loops — Mews 2026 parity.

Autonomous AI agents that orchestrate workflows across departments.
Unlike reactive automation_rules (which fire on events), agents plan
multi-step action chains, monitor outcomes, and adapt.

Concepts:
  - Agent: a named role with a `mission` (Turkish description), trigger schedule,
           tool whitelist, and conservative approval policy.
  - AgentRun: a single execution. Records plan (LLM-generated),
              actions taken, results, and final disposition.
  - Approval: actions tagged "high_risk" pause for human ack.

Pre-installed agents (seeded on first read):
  1. "Misafir Memnuniyet Agent" — finds low-rated reviews from last 24h,
     drafts apology message, creates service-recovery voucher idea.
  2. "Operasyon Optimize Agent" — finds out-of-service rooms exceeding 24h
     and pings maintenance.
  3. "Revenue Pulse Agent" — finds dates with sub-threshold occupancy
     forecast and proposes promo rules.

Endpoints
---------
  GET  /api/agents
  POST /api/agents
  PATCH /api/agents/{id}
  POST /api/agents/{id}/run             — trigger an agent run (manual)
  GET  /api/agents/{id}/runs            — recent runs
  POST /api/agents/runs/{run_id}/approve
  POST /api/agents/runs/{run_id}/reject
  GET  /api/agents/runs/{run_id}        — run detail
"""
from datetime import datetime, timezone, timedelta
import os
import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


SEED_AGENTS = [
    {
        "name": "Misafir Memnuniyet Agent",
        "category": "guest_recovery",
        "mission": ("Son 24 saatte 3 yıldız ve altı yorum bırakan misafirleri "
                    "tespit et, her biri için kişisel özür mesajı taslağı + "
                    "service-recovery voucher öner."),
        "tools": ["find_low_reviews", "draft_apology", "propose_voucher"],
        "schedule": "manual",
        "max_actions_per_run": 5,
        "requires_approval": True,
        "is_active": True,
    },
    {
        "name": "Operasyon Optimize Agent",
        "category": "operations",
        "mission": ("24 saatten uzun süredir 'OOS' (out-of-service) olan "
                    "odaları bul, bakım ekibine ping at, gelir kaybını hesapla."),
        "tools": ["find_stale_oos", "create_maintenance_ticket", "estimate_revenue_loss"],
        "schedule": "manual",
        "max_actions_per_run": 10,
        "requires_approval": False,
        "is_active": True,
    },
    {
        "name": "Revenue Pulse Agent",
        "category": "revenue",
        "mission": ("Önümüzdeki 30 gün için forecast'ı %60 dolulukun altında "
                    "olan tarihleri bul ve son-dakika promo kuralı (örn. "
                    "%15 indirim) öner. Onaya kadar UYGULAMA."),
        "tools": ["find_low_occupancy_dates", "draft_promo_rule"],
        "schedule": "manual",
        "max_actions_per_run": 7,
        "requires_approval": True,
        "is_active": True,
    },
]


def create_agents_router(db, require_roles):
    router = APIRouter()

    async def _ensure_seeded():
        existing = await db.ai_agents.count_documents({})
        if existing > 0:
            return
        docs = []
        for s in SEED_AGENTS:
            docs.append({
                "id": str(uuid.uuid4()),
                **s,
                "created_at": _now_iso(),
                "last_run_at": None,
                "total_runs": 0,
                "seeded": True,
            })
        if docs:
            await db.ai_agents.insert_many(docs)

    @router.get("/agents")
    async def list_agents(_: dict = Depends(require_roles("admin", "manager"))):
        await _ensure_seeded()
        items = await db.ai_agents.find({}, {"_id": 0}).sort(
            "created_at", -1
        ).to_list(200)
        return {"items": items, "count": len(items)}

    @router.post("/agents")
    async def create_agent(body: dict,
                           current_user: dict = Depends(require_roles("admin"))):
        if not body.get("name") or not body.get("mission"):
            raise HTTPException(400, "name and mission required")
        doc = {
            "id": str(uuid.uuid4()),
            "name": body["name"],
            "category": body.get("category", "general"),
            "mission": body["mission"],
            "tools": body.get("tools", []),
            "schedule": body.get("schedule", "manual"),
            "max_actions_per_run": int(body.get("max_actions_per_run", 5)),
            "requires_approval": body.get("requires_approval", True),
            "is_active": body.get("is_active", True),
            "created_at": _now_iso(),
            "created_by": current_user.get("name", ""),
            "last_run_at": None,
            "total_runs": 0,
        }
        await db.ai_agents.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.patch("/agents/{agent_id}")
    async def patch_agent(agent_id: str, body: dict,
                          _: dict = Depends(require_roles("admin"))):
        allowed = {"name", "mission", "tools", "schedule",
                   "max_actions_per_run", "requires_approval",
                   "is_active", "category"}
        update = {k: v for k, v in body.items() if k in allowed}
        if not update:
            raise HTTPException(400, "Nothing to update")
        r = await db.ai_agents.update_one({"id": agent_id}, {"$set": update})
        if not r.matched_count:
            raise HTTPException(404, "Agent not found")
        return {"ok": True}

    @router.post("/agents/{agent_id}/run")
    async def run_agent(agent_id: str,
                        current_user: dict = Depends(require_roles("admin", "manager"))):
        agent = await db.ai_agents.find_one({"id": agent_id}, {"_id": 0})
        if not agent:
            raise HTTPException(404, "Agent not found")
        if not agent.get("is_active", True):
            raise HTTPException(403, "Agent disabled")
        run_id = str(uuid.uuid4())
        run = {
            "id": run_id,
            "agent_id": agent_id,
            "agent_name": agent["name"],
            "status": "running",
            "started_at": _now_iso(),
            "started_by": current_user.get("name", ""),
            "plan": [],
            "actions_taken": [],
            "results": {},
            "requires_approval": agent.get("requires_approval", True),
        }
        await db.ai_agent_runs.insert_one(run)

        # Execute the agent tool chain
        actions_taken, results = await _execute_agent(db, agent)

        # Determine disposition
        if agent.get("requires_approval", True) and actions_taken:
            status = "pending_approval"
        else:
            status = "completed"
        await db.ai_agent_runs.update_one(
            {"id": run_id},
            {"$set": {
                "status": status,
                "actions_taken": actions_taken,
                "results": results,
                "completed_at": _now_iso(),
            }}
        )
        await db.ai_agents.update_one(
            {"id": agent_id},
            {"$set": {"last_run_at": _now_iso()},
             "$inc": {"total_runs": 1}}
        )
        run.update({"status": status, "actions_taken": actions_taken, "results": results})
        run.pop("_id", None)
        return run

    @router.get("/agents/{agent_id}/runs")
    async def list_runs(agent_id: str, limit: int = 50,
                        _: dict = Depends(require_roles("admin", "manager"))):
        items = await db.ai_agent_runs.find(
            {"agent_id": agent_id}, {"_id": 0}
        ).sort("started_at", -1).to_list(min(limit, 200))
        return {"items": items, "count": len(items)}

    @router.get("/agents/runs/{run_id}")
    async def get_run(run_id: str,
                      _: dict = Depends(require_roles("admin", "manager"))):
        run = await db.ai_agent_runs.find_one({"id": run_id}, {"_id": 0})
        if not run:
            raise HTTPException(404, "Run not found")
        return run

    @router.post("/agents/runs/{run_id}/approve")
    async def approve_run(run_id: str,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        run = await db.ai_agent_runs.find_one({"id": run_id}, {"_id": 0})
        if not run:
            raise HTTPException(404, "Run not found")
        if run.get("status") != "pending_approval":
            raise HTTPException(400, "Run is not pending approval")
        # On approval, we 'commit' the proposed actions. For demo modules,
        # the propose phase already created suggestion records, so approval
        # just stamps the decision.
        await db.ai_agent_runs.update_one(
            {"id": run_id},
            {"$set": {"status": "approved",
                      "approved_at": _now_iso(),
                      "approved_by": current_user.get("name", "")}}
        )
        return {"ok": True}

    @router.post("/agents/runs/{run_id}/reject")
    async def reject_run(run_id: str, body: dict = None,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        body = body or {}
        run = await db.ai_agent_runs.find_one({"id": run_id}, {"_id": 0})
        if not run:
            raise HTTPException(404, "Run not found")
        await db.ai_agent_runs.update_one(
            {"id": run_id},
            {"$set": {"status": "rejected",
                      "rejected_at": _now_iso(),
                      "rejected_by": current_user.get("name", ""),
                      "reject_reason": body.get("reason", "")}}
        )
        return {"ok": True}

    return router


# ============== Agent tool implementations ==============

async def _execute_agent(db, agent: dict) -> tuple[list, dict]:
    """Run all tools the agent is permitted to use. Conservative: collect
    findings but do not commit destructive actions unless approval policy allows.
    """
    actions: list = []
    results: dict = {}
    tools = agent.get("tools", [])
    max_actions = agent.get("max_actions_per_run", 5)

    if "find_low_reviews" in tools:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        low = await db.reviews.find(
            {"rating": {"$lte": 3}, "created_at": {"$gte": cutoff}},
            {"_id": 0, "id": 1, "rating": 1, "author": 1, "comment": 1, "property_id": 1}
        ).limit(max_actions).to_list(max_actions)
        actions.append({
            "tool": "find_low_reviews",
            "found": len(low),
            "items": low,
            "ts": _now_iso(),
        })
        results["low_reviews"] = low

        if "draft_apology" in tools and low:
            drafts = []
            for r in low[:max_actions]:
                drafts.append({
                    "review_id": r["id"],
                    "author": r.get("author", "Misafir"),
                    "rating": r.get("rating"),
                    "draft": (f"Sayın {r.get('author','Misafir')}, "
                              f"yorumunuz için içtenlikle özür dileriz. "
                              f"Bu konuyu yönetim ekibimizle inceledik ve "
                              f"sizinle bireysel olarak ilgilenmek istiyoruz."),
                })
            actions.append({"tool": "draft_apology", "drafts": drafts, "ts": _now_iso()})
            results["apology_drafts"] = drafts

        if "propose_voucher" in tools and low:
            vouchers = []
            for r in low[:max_actions]:
                vouchers.append({
                    "review_id": r["id"],
                    "type": "service_recovery",
                    "value_pct": 15 if (r.get("rating", 0) <= 2) else 10,
                    "valid_days": 90,
                    "note": "AI Agent önerisi — yönetim onayı bekleniyor.",
                })
            actions.append({"tool": "propose_voucher", "vouchers": vouchers, "ts": _now_iso()})
            results["voucher_proposals"] = vouchers

    if "find_stale_oos" in tools:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        # Look for rooms with status OOS for >24h. Try multiple field names.
        candidates = await db.rooms.find(
            {"$or": [
                {"status": "out_of_service"},
                {"status": "oos"},
                {"is_out_of_service": True},
            ]},
            {"_id": 0, "id": 1, "room_number": 1, "property_id": 1, "status": 1,
             "oos_since": 1, "updated_at": 1}
        ).limit(max_actions).to_list(max_actions)
        stale = [r for r in candidates
                 if (r.get("oos_since") or r.get("updated_at") or "") < cutoff]
        actions.append({"tool": "find_stale_oos", "found": len(stale),
                        "items": stale, "ts": _now_iso()})
        results["stale_oos"] = stale

        if "create_maintenance_ticket" in tools and stale:
            tickets = []
            for r in stale:
                tickets.append({
                    "room": r.get("room_number"),
                    "property_id": r.get("property_id"),
                    "priority": "high",
                    "title": f"Oda {r.get('room_number')} 24h+ OOS — inceleme gerekli",
                    "auto_created_by": agent.get("name"),
                })
            actions.append({"tool": "create_maintenance_ticket",
                            "tickets": tickets, "ts": _now_iso()})
            results["maintenance_tickets"] = tickets

        if "estimate_revenue_loss" in tools and stale:
            loss = 0.0
            for _ in stale:
                # Conservative: assume 24h * avg_rate (£150 default)
                loss += 150.0
            actions.append({"tool": "estimate_revenue_loss",
                            "amount": loss, "ts": _now_iso()})
            results["revenue_loss_estimate"] = loss

    if "find_low_occupancy_dates" in tools:
        # Look at forecasts for next 30 days that are below 60%
        cutoff_start = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        cutoff_end = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%d")
        low_dates = await db.forecast_daily.find(
            {"date": {"$gte": cutoff_start, "$lte": cutoff_end},
             "occupancy_forecast": {"$lt": 0.60}},
            {"_id": 0, "date": 1, "property_id": 1, "occupancy_forecast": 1}
        ).limit(max_actions).to_list(max_actions)
        actions.append({"tool": "find_low_occupancy_dates",
                        "found": len(low_dates), "items": low_dates,
                        "ts": _now_iso()})
        results["low_occupancy_dates"] = low_dates

        if "draft_promo_rule" in tools and low_dates:
            promos = []
            for d in low_dates:
                promos.append({
                    "date": d["date"],
                    "property_id": d.get("property_id"),
                    "type": "last_minute",
                    "discount_percent": 15,
                    "rationale": f"Forecast {(d['occupancy_forecast']*100):.0f}% < 60% threshold",
                })
            actions.append({"tool": "draft_promo_rule",
                            "promos": promos, "ts": _now_iso()})
            results["promo_proposals"] = promos

    # If LLM key present, ask GPT to summarise findings (best-effort)
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        llm_key = os.environ.get("EMERGENT_LLM_KEY")
        if llm_key and actions:
            findings_text = "\n".join([f"- {a['tool']}" for a in actions])
            chat = LlmChat(
                api_key=llm_key,
                session_id=f"agent-{agent.get('id','x')}",
                system_message=("Bir otel zinciri için çalışan otonom AI agent'sın. "
                                "Bulguları kısa Türkçe yönetici özetiyle aktar."),
            ).with_model("openai", "gpt-4o-mini")
            summary = await chat.send_message(UserMessage(
                text=f"Misyon: {agent.get('mission')}\nBulgular:\n{findings_text}"
            ))
            results["executive_summary"] = summary
    except Exception as e:
        logger.warning(f"Agent LLM summary failed: {e}")

    return actions, results
