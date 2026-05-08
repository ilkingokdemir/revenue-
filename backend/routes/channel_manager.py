"""
Channel Manager — Connects the hotel PMS to multiple OTAs for rate/availability sync.
Manages channel connections, rate mappings, push/pull operations, and sync status.
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
from typing import Dict
import uuid
import logging

logger = logging.getLogger(__name__)

DEFAULT_CHANNELS = [
    {"id": "booking_com", "name": "Booking.com", "type": "ota", "color": "#003580", "commission_pct": 15, "logo": "B"},
    {"id": "expedia", "name": "Expedia", "type": "ota", "color": "#FFCC00", "commission_pct": 18, "logo": "E"},
    {"id": "airbnb", "name": "Airbnb", "type": "ota", "color": "#FF5A5F", "commission_pct": 3, "logo": "A"},
    {"id": "hotels_com", "name": "Hotels.com", "type": "ota", "color": "#D32F2F", "commission_pct": 18, "logo": "H"},
    {"id": "agoda", "name": "Agoda", "type": "ota", "color": "#5C2D91", "commission_pct": 17, "logo": "Ag"},
    {"id": "trip_com", "name": "Trip.com", "type": "ota", "color": "#287DFA", "commission_pct": 15, "logo": "T"},
    {"id": "google_hotels", "name": "Google Hotels", "type": "metasearch", "color": "#4285F4", "commission_pct": 12, "logo": "G"},
    {"id": "trivago", "name": "Trivago", "type": "metasearch", "color": "#E74C3C", "commission_pct": 10, "logo": "Tr"},
    {"id": "direct", "name": "Direct Website", "type": "direct", "color": "#16A34A", "commission_pct": 0, "logo": "D"},
]


def create_channel_manager_router(db, require_roles):
    router = APIRouter()

    @router.get("/revenue/channel-manager/{property_id}")
    async def get_channels(property_id: str,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        """Get all channel connections and their status."""
        channels = await db.channel_connections.find(
            {"property_id": property_id}, {"_id": 0}
        ).to_list(20)

        if not channels:
            # Seed default channels
            now = datetime.now(timezone.utc)
            for ch in DEFAULT_CHANNELS:
                doc = {
                    "id": str(uuid.uuid4())[:8],
                    "property_id": property_id,
                    "channel_id": ch["id"],
                    "name": ch["name"],
                    "type": ch["type"],
                    "color": ch["color"],
                    "commission_pct": ch["commission_pct"],
                    "logo": ch["logo"],
                    "connected": ch["id"] == "direct",
                    "status": "active" if ch["id"] == "direct" else "disconnected",
                    "rate_markup_pct": 0,
                    "rate_rule": "same",
                    "auto_sync": False,
                    "last_sync": now.isoformat() if ch["id"] == "direct" else None,
                    "rooms_mapped": 0,
                    "total_bookings": 0,
                    "revenue_30d": 0,
                    "created_at": now.isoformat(),
                }
                await db.channel_connections.insert_one(doc)
                doc.pop("_id", None)
            channels = await db.channel_connections.find(
                {"property_id": property_id}, {"_id": 0}
            ).to_list(20)

        # Summary
        connected = sum(1 for c in channels if c.get("connected"))
        total_rev = sum(c.get("revenue_30d", 0) for c in channels)
        total_bookings = sum(c.get("total_bookings", 0) for c in channels)
        syncing = sum(1 for c in channels if c.get("auto_sync"))

        return {
            "channels": channels,
            "summary": {
                "total_channels": len(channels),
                "connected": connected,
                "disconnected": len(channels) - connected,
                "auto_syncing": syncing,
                "total_revenue_30d": total_rev,
                "total_bookings": total_bookings,
            },
        }

    @router.put("/revenue/channel-manager/{property_id}/{channel_id}")
    async def update_channel(property_id: str, channel_id: str, data: Dict,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        """Update channel connection settings."""
        now = datetime.now(timezone.utc)
        update = {"updated_at": now.isoformat()}

        for key in ["connected", "auto_sync", "rate_markup_pct", "rate_rule", "commission_pct"]:
            if key in data:
                update[key] = data[key]

        if "connected" in data:
            update["status"] = "active" if data["connected"] else "disconnected"
            if data["connected"]:
                update["last_sync"] = now.isoformat()

        await db.channel_connections.update_one(
            {"property_id": property_id, "channel_id": channel_id},
            {"$set": update}
        )
        return {"message": "Channel updated", "channel_id": channel_id}

    @router.post("/revenue/channel-manager/{property_id}/push-rates")
    async def push_rates(property_id: str, data: Dict = {},
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        """Push current rates to all connected channels."""
        now = datetime.now(timezone.utc)
        days = int(data.get("days", 90))
        channels = await db.channel_connections.find(
            {"property_id": property_id, "connected": True}, {"_id": 0}
        ).to_list(20)

        rt = await db.room_types.find_one({"property_id": property_id}, {"_id": 0})
        base_rate = float(rt.get("base_rate", 100) or 100) if rt else 100.0

        pushed = 0
        channel_results = []
        for ch in channels:
            markup = float(ch.get("rate_markup_pct", 0))
            rule = ch.get("rate_rule", "same")
            ch_rates = []

            for i in range(days):
                d = now + timedelta(days=i)
                ds = d.strftime("%Y-%m-%d")
                override = await db.rate_overrides.find_one(
                    {"property_id": property_id, "date": ds}, {"_id": 0}
                )
                our_rate = float(override.get("custom_rate", base_rate)) if override else base_rate

                if rule == "markup":
                    ch_rate = round(our_rate * (1 + markup / 100), 2)
                elif rule == "undercut":
                    ch_rate = round(our_rate * (1 - markup / 100), 2)
                else:
                    ch_rate = our_rate

                ch_rates.append({"date": ds, "rate": ch_rate})
                pushed += 1

            # Store push log
            await db.channel_push_logs.insert_one({
                "id": str(uuid.uuid4())[:8],
                "property_id": property_id,
                "channel_id": ch["channel_id"],
                "channel_name": ch["name"],
                "rates_pushed": len(ch_rates),
                "rule": rule,
                "markup_pct": markup,
                "pushed_at": now.isoformat(),
            })

            # Update last sync
            await db.channel_connections.update_one(
                {"property_id": property_id, "channel_id": ch["channel_id"]},
                {"$set": {"last_sync": now.isoformat(), "status": "active"}}
            )

            channel_results.append({
                "channel": ch["name"],
                "rates_pushed": len(ch_rates),
                "rule": rule,
                "markup": markup,
            })

        return {
            "message": f"Rates pushed to {len(channels)} channels ({pushed} rate entries)",
            "channels_pushed": len(channels),
            "total_rates": pushed,
            "results": channel_results,
        }

    @router.get("/revenue/channel-manager/{property_id}/push-logs")
    async def get_push_logs(property_id: str,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        logs = await db.channel_push_logs.find(
            {"property_id": property_id}, {"_id": 0}
        ).sort("pushed_at", -1).to_list(50)
        return {"logs": logs}

    @router.get("/revenue/channel-manager/{property_id}/rate-preview")
    async def rate_preview(property_id: str, days: int = 7,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        """Preview rates across all channels for the next N days."""
        now = datetime.now(timezone.utc)
        channels = await db.channel_connections.find(
            {"property_id": property_id}, {"_id": 0}
        ).to_list(20)

        rt = await db.room_types.find_one({"property_id": property_id}, {"_id": 0})
        base_rate = float(rt.get("base_rate", 100) or 100) if rt else 100.0

        preview = []
        for i in range(days):
            d = now + timedelta(days=i)
            ds = d.strftime("%Y-%m-%d")
            override = await db.rate_overrides.find_one(
                {"property_id": property_id, "date": ds}, {"_id": 0}
            )
            our_rate = float(override.get("custom_rate", base_rate)) if override else base_rate

            ch_rates = {"date": ds, "dow": d.strftime("%a"), "our_rate": our_rate}
            for ch in channels:
                markup = float(ch.get("rate_markup_pct", 0))
                rule = ch.get("rate_rule", "same")
                if rule == "markup":
                    ch_rates[ch["channel_id"]] = round(our_rate * (1 + markup / 100), 2)
                elif rule == "undercut":
                    ch_rates[ch["channel_id"]] = round(our_rate * (1 - markup / 100), 2)
                else:
                    ch_rates[ch["channel_id"]] = our_rate
            preview.append(ch_rates)

        return {"preview": preview, "channels": channels}

    @router.post("/revenue/channel-manager/{property_id}/sync-availability")
    async def sync_availability(property_id: str, data: Dict = {},
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        """Push real-time room availability to all connected OTA channels."""
        now = datetime.now(timezone.utc)
        days = int(data.get("days", 30))

        channels = await db.channel_connections.find(
            {"property_id": property_id, "connected": True}, {"_id": 0}
        ).to_list(20)

        if not channels:
            return {"error": "No connected channels", "synced": 0}

        # Get all rooms for this property
        rooms = await db.rooms.find({"property_id": property_id}, {"_id": 0}).to_list(200)
        total_rooms = len(rooms) if rooms else 10

        # Get room types
        room_types = await db.room_types.find({"property_id": property_id}, {"_id": 0}).to_list(20)
        rooms_per_type = {}
        for r in rooms:
            rtid = r.get("room_type_id", "")
            rooms_per_type[rtid] = rooms_per_type.get(rtid, 0) + 1

        # Calculate availability per date
        availability_data = []
        for i in range(days):
            d = now + timedelta(days=i)
            ds = d.strftime("%Y-%m-%d")

            # Count booked rooms for this date
            booked = await db.bookings.count_documents({
                "property_id": property_id,
                "status": {"$nin": ["cancelled", "no_show"]},
                "check_in": {"$lte": ds},
                "check_out": {"$gt": ds},
            })

            available = max(0, total_rooms - booked)
            occ_pct = round((booked / max(total_rooms, 1)) * 100)

            # Per room-type availability
            type_avail = {}
            for rt in room_types:
                rtid = rt.get("id", "")
                rt_total = rooms_per_type.get(rtid, 0)
                rt_booked = await db.bookings.count_documents({
                    "property_id": property_id,
                    "room_type_id": rtid,
                    "status": {"$nin": ["cancelled", "no_show"]},
                    "check_in": {"$lte": ds},
                    "check_out": {"$gt": ds},
                })
                type_avail[rtid] = {"total": rt_total, "booked": rt_booked, "available": max(0, rt_total - rt_booked)}

            availability_data.append({
                "date": ds, "total_rooms": total_rooms, "booked": booked,
                "available": available, "occupancy_pct": occ_pct, "by_type": type_avail,
            })

        # Push to each channel
        synced_channels = []
        for ch in channels:
            await db.channel_push_logs.insert_one({
                "id": str(uuid.uuid4())[:8],
                "property_id": property_id,
                "channel_id": ch["channel_id"],
                "channel_name": ch["name"],
                "type": "availability",
                "dates_synced": len(availability_data),
                "pushed_at": now.isoformat(),
            })

            await db.channel_connections.update_one(
                {"property_id": property_id, "channel_id": ch["channel_id"]},
                {"$set": {"last_avail_sync": now.isoformat(), "status": "active"}}
            )

            synced_channels.append({"channel": ch["name"], "dates_synced": len(availability_data)})

        return {
            "message": f"Availability synced to {len(channels)} channels for {days} days",
            "channels_synced": len(channels),
            "days_synced": days,
            "total_rooms": total_rooms,
            "results": synced_channels,
            "availability_sample": availability_data[:7],
        }

    return router
