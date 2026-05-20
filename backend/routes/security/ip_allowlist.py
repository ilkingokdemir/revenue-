"""
IP Allowlist (Iter 157) — enterprise security. Restrict admin panel access to
known office IPs. When allowlist is empty, all IPs allowed (default). When
populated, admin users must connect from a whitelisted IP/CIDR.
Front-end reception/guest flows are never blocked — only admin-panel routes.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import datetime, timezone
from typing import Dict
import ipaddress
import uuid
import logging

logger = logging.getLogger(__name__)


def _ip_matches(ip_str: str, rule: str) -> bool:
    """True if ip_str matches the rule (single IP or CIDR)."""
    try:
        ip = ipaddress.ip_address(ip_str)
        if "/" in rule:
            return ip in ipaddress.ip_network(rule, strict=False)
        return str(ip) == rule
    except ValueError:
        return False


def create_ip_allowlist_router(db, require_roles):
    router = APIRouter()

    @router.get("/ip-allowlist")
    async def list_rules(current_user: dict = Depends(require_roles("admin"))):
        rows = await db.ip_allowlist.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
        return {"enabled": len(rows) > 0, "rules": rows, "count": len(rows)}

    @router.post("/ip-allowlist")
    async def add_rule(data: Dict, request: Request,
                       current_user: dict = Depends(require_roles("admin"))):
        """Body: {cidr_or_ip, label, note}. Validates CIDR/IP syntax before saving."""
        value = (data.get("cidr_or_ip") or "").strip()
        if not value:
            raise HTTPException(status_code=400, detail="cidr_or_ip required")
        try:
            if "/" in value:
                ipaddress.ip_network(value, strict=False)
            else:
                ipaddress.ip_address(value)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid IP or CIDR: {value}")

        existing = await db.ip_allowlist.find_one({"cidr_or_ip": value}, {"_id": 0})
        if existing:
            raise HTTPException(status_code=409, detail="Already in allowlist")

        rule = {
            "id": str(uuid.uuid4()),
            "cidr_or_ip": value,
            "label": (data.get("label") or "").strip(),
            "note": (data.get("note") or "").strip(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": current_user.get("name", ""),
        }
        await db.ip_allowlist.insert_one(rule)
        rule.pop("_id", None)
        return rule

    @router.delete("/ip-allowlist/{rule_id}")
    async def delete_rule(rule_id: str,
                          current_user: dict = Depends(require_roles("admin"))):
        res = await db.ip_allowlist.delete_one({"id": rule_id})
        return {"status": "deleted" if res.deleted_count else "not_found"}

    @router.get("/ip-allowlist/my-ip")
    async def my_ip(request: Request, current_user: dict = Depends(require_roles("admin"))):
        """Returns the client IP so the admin can self-add."""
        fwd = request.headers.get("x-forwarded-for", "")
        ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "")
        return {"ip": ip, "via_proxy": bool(fwd)}

    @router.post("/ip-allowlist/check")
    async def check_ip(data: Dict, current_user: dict = Depends(require_roles("admin"))):
        """Body: {ip}. Returns whether that IP would pass the allowlist."""
        ip = (data.get("ip") or "").strip()
        rules = await db.ip_allowlist.find({}, {"_id": 0}).to_list(200)
        if not rules:
            return {"ip": ip, "allowed": True, "reason": "allowlist is empty (all IPs allowed)"}
        matched = [r for r in rules if _ip_matches(ip, r["cidr_or_ip"])]
        return {
            "ip": ip,
            "allowed": bool(matched),
            "matched_rule": matched[0] if matched else None,
            "reason": f"matches rule '{matched[0]['label'] or matched[0]['cidr_or_ip']}'" if matched else "no matching rule",
        }

    return router
