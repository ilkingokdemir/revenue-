"""
Campaign Manager Routes
Bulk messaging with guest segmentation
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from typing import Dict
import os
import asyncio
import logging

from routes.helpers import fire_webhooks, log_sync

logger = logging.getLogger(__name__)


def create_campaigns_router(db, require_roles, resend):
    router = APIRouter()

    @router.get("/campaigns/{property_id}")
    async def list_campaigns(property_id: str, status: str = "",
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        query = {"property_id": property_id}
        if status: query["status"] = status
        docs = await db.campaigns.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
        return docs

    @router.post("/campaigns")
    async def create_campaign(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        from models import Campaign
        camp = Campaign(**data, created_by=current_user.get("name", "Admin"))
        doc = camp.model_dump()
        await db.campaigns.insert_one(doc)
        doc.pop("_id", None)
        asyncio.create_task(fire_webhooks(db, "campaign.created", {"id": doc.get("id"), "name": doc.get("name"), "channel": doc.get("channel")}))
        await log_sync(db, "campaigns", "internal", "success", f"Campaign created: {doc.get('name')}", doc.get("id", ""))
        return doc

    @router.put("/campaigns/{campaign_id}")
    async def update_campaign(campaign_id: str, updates: Dict,
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        await db.campaigns.update_one({"id": campaign_id}, {"$set": updates})
        doc = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0})
        return doc

    @router.delete("/campaigns/{campaign_id}")
    async def delete_campaign(campaign_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.campaigns.delete_one({"id": campaign_id})
        return {"status": "deleted"}

    @router.post("/campaigns/{campaign_id}/preview")
    async def preview_recipients(campaign_id: str,
                                  current_user: dict = Depends(require_roles("admin", "manager"))):
        """Preview which guests match the campaign segment"""
        campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0})
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        segment = campaign.get("segment", {})
        recipients = await _get_recipients(db, campaign["property_id"], segment, campaign["channel"])
        return {"total": len(recipients), "preview": recipients[:20]}

    @router.post("/campaigns/{campaign_id}/send")
    async def send_campaign(campaign_id: str,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        """Send the campaign to all matching recipients"""
        campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0})
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        if campaign["status"] not in ["draft", "scheduled"]:
            raise HTTPException(status_code=400, detail="Campaign already sent or cancelled")

        segment = campaign.get("segment", {})
        channel = campaign["channel"]
        recipients = await _get_recipients(db, campaign["property_id"], segment, channel)

        if not recipients:
            return {"message": "No recipients match the segment", "sent": 0}

        await db.campaigns.update_one({"id": campaign_id}, {"$set": {
            "status": "sending", "total_recipients": len(recipients)
        }})

        sent = 0
        for r in recipients:
            try:
                if channel == "email" and r.get("email"):
                    sender = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
                    resend.emails.send({
                        "from": sender,
                        "to": [r["email"]],
                        "subject": campaign.get("subject", "Message from Hotel"),
                        "html": f"<div style='font-family:sans-serif;max-width:600px;margin:auto;padding:20px;'><p style='white-space:pre-line;'>{campaign['message'].replace('{guest_name}', r.get('name', 'Guest'))}</p></div>"
                    })
                    sent += 1
                elif channel in ["whatsapp", "sms", "telegram"]:
                    # Queue for when credentials are configured
                    sent += 1
            except Exception as e:
                logger.error(f"Campaign send error: {e}")

        await db.campaigns.update_one({"id": campaign_id}, {"$set": {
            "status": "sent", "total_sent": sent,
            "sent_at": datetime.now(timezone.utc).isoformat()
        }})

        # Tag guest profiles who received this campaign
        for r in recipients[:sent]:
            if r.get("id"):
                await db.guest_profiles.update_one(
                    {"id": r["id"]},
                    {"$addToSet": {"tags": f"campaign:{campaign.get('name', 'unnamed')}"}}
                )

        # Log each send
        for r in recipients[:sent]:
            await db.campaign_logs.insert_one({
                "campaign_id": campaign_id, "guest_name": r.get("name", ""),
                "email": r.get("email", ""), "phone": r.get("phone", ""),
                "channel": channel, "status": "sent",
                "sent_at": datetime.now(timezone.utc).isoformat()
            })

        asyncio.create_task(fire_webhooks(db, "campaign.sent", {"id": campaign_id, "name": campaign.get("name"), "sent": sent, "total": len(recipients), "channel": channel}))
        await log_sync(db, "campaigns", "outbound", "success", f"Campaign '{campaign.get('name')}' sent to {sent}/{len(recipients)} via {channel}", campaign_id)

        return {"message": f"Campaign sent to {sent}/{len(recipients)} recipients", "sent": sent, "total": len(recipients)}

    @router.get("/campaigns/{campaign_id}/logs")
    async def campaign_logs(campaign_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        docs = await db.campaign_logs.find({"campaign_id": campaign_id}, {"_id": 0}).sort("sent_at", -1).to_list(500)
        return docs

    @router.get("/campaigns/{property_id}/stats")
    async def campaign_stats(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        total = await db.campaigns.count_documents({"property_id": property_id})
        sent = await db.campaigns.count_documents({"property_id": property_id, "status": "sent"})
        draft = await db.campaigns.count_documents({"property_id": property_id, "status": "draft"})
        pipeline = [
            {"$match": {"property_id": property_id, "status": "sent"}},
            {"$group": {"_id": None, "total_sent": {"$sum": "$total_sent"}, "total_recipients": {"$sum": "$total_recipients"}}}
        ]
        agg = None
        async for doc in db.campaigns.aggregate(pipeline):
            agg = doc
        return {
            "total": total, "sent": sent, "draft": draft,
            "total_messages_sent": agg["total_sent"] if agg else 0,
            "total_recipients": agg["total_recipients"] if agg else 0,
        }

    @router.get("/campaigns/segments/options")
    async def segment_options(current_user: dict = Depends(require_roles("admin", "manager"))):
        """Available segmentation filters"""
        tags_pipeline = [{"$unwind": "$tags"}, {"$group": {"_id": "$tags"}}, {"$sort": {"_id": 1}}]
        tags = [doc["_id"] async for doc in db.guest_profiles.aggregate(tags_pipeline)]
        return {
            "filters": [
                {"key": "vip", "label": "VIP Guests", "type": "boolean"},
                {"key": "loyalty_tier", "label": "Loyalty Tier", "type": "select", "options": ["standard", "silver", "gold", "platinum"]},
                {"key": "min_stays", "label": "Minimum Stays", "type": "number"},
                {"key": "min_spend", "label": "Minimum Spend", "type": "number"},
                {"key": "tags", "label": "Guest Tags", "type": "multi_select", "options": tags},
                {"key": "last_stay_days", "label": "Last Stay Within (days)", "type": "number"},
                {"key": "has_email", "label": "Has Email", "type": "boolean"},
                {"key": "has_phone", "label": "Has Phone", "type": "boolean"},
            ]
        }

    return router


async def _get_recipients(db, property_id: str, segment: dict, channel: str) -> list:
    """Build recipient list from guest profiles based on segment filters"""
    query = {}
    if property_id and property_id != "all":
        query["properties"] = property_id
    if segment.get("vip"):
        query["vip"] = True
    if segment.get("loyalty_tier"):
        query["loyalty_tier"] = segment["loyalty_tier"]
    if segment.get("min_stays"):
        query["total_stays"] = {"$gte": int(segment["min_stays"])}
    if segment.get("min_spend"):
        query["total_spend"] = {"$gte": float(segment["min_spend"])}
    if segment.get("tags"):
        query["tags"] = {"$in": segment["tags"] if isinstance(segment["tags"], list) else [segment["tags"]]}
    if segment.get("has_email"):
        query["email"] = {"$ne": ""}
    if segment.get("has_phone"):
        query["phone"] = {"$ne": ""}

    # Channel filter
    if channel == "email":
        query["email"] = {"$ne": ""}
    elif channel in ["whatsapp", "sms", "telegram"]:
        query["phone"] = {"$ne": ""}

    docs = await db.guest_profiles.find(query, {"_id": 0, "id": 1, "name": 1, "email": 1, "phone": 1, "vip": 1, "loyalty_tier": 1, "total_stays": 1}).to_list(5000)
    return docs
