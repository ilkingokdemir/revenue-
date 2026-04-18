"""
Roles & Permissions — per-branch role management matching the competitor's pattern.
- Roles are stored per property_id (branch-scoped)
- role.key: immutable lowercase_underscores internal identifier
- role.display_name: editable user-facing name
- role.permissions: list of permission keys from the catalog
- role.is_global_admin: bypasses all permission checks (P1 feature)
- Clone, create, edit, delete, list
- Template bootstrapping via ROLE_TEMPLATES
- Missing test_credentials: uses existing admin token
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone
import uuid
import re

from routes.permission_catalog import (
    PERMISSION_CATALOG, ROLE_TEMPLATES,
    get_all_permission_keys, count_total_permissions,
    expand_template_permissions, enrich_catalog, get_risk,
)
import os
import json
import logging

logger = logging.getLogger(__name__)


KEY_REGEX = re.compile(r"^[a-z][a-z0-9_]{1,49}$")


class RoleCreate(BaseModel):
    key: str = Field(..., min_length=2, max_length=50)
    display_name: Optional[str] = None
    property_id: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)
    template: Optional[str] = None
    is_global_admin: bool = False


class RoleUpdate(BaseModel):
    display_name: Optional[str] = None
    permissions: Optional[List[str]] = None
    is_global_admin: Optional[bool] = None


class CloneRequest(BaseModel):
    new_key: str = Field(..., min_length=2, max_length=50)
    display_name: Optional[str] = None


class AISuggestRequest(BaseModel):
    description: str = Field(..., min_length=10, max_length=800)
    existing_permissions: List[str] = Field(default_factory=list)


def _now():
    return datetime.now(timezone.utc).isoformat()


def create_roles_router(db, require_roles, get_current_user):
    router = APIRouter()

    # ------- CATALOG -------
    @router.get("/rbac/catalog")
    async def catalog(current_user: dict = Depends(get_current_user)):
        return {
            "catalog": enrich_catalog(),
            "templates": ROLE_TEMPLATES,
            "total_permissions": count_total_permissions(),
            "all_permission_keys": get_all_permission_keys(),
        }

    # ------- AI ROLE DESIGNER (GPT-5.2) -------
    @router.post("/rbac/ai-suggest")
    async def ai_suggest(body: AISuggestRequest,
                         current_user: dict = Depends(require_roles("admin"))):
        """Given a plain-English role description, suggest permissions via GPT-5.2."""
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
        except Exception as e:
            raise HTTPException(500, f"LLM library not available: {e}")

        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            raise HTTPException(500, "EMERGENT_LLM_KEY not configured")

        # Build a compact catalog summary — key + label only, grouped by category
        catalog_summary = []
        for cat in PERMISSION_CATALOG:
            cat_perms = []
            for sg in cat["sub_groups"]:
                for p in sg["permissions"]:
                    if p.get("missing"):
                        continue
                    cat_perms.append(f"{p['key']}:{p['label']}")
            if cat_perms:
                catalog_summary.append(f"## {cat['label']}\n" + "\n".join(cat_perms))

        system_msg = (
            "You are an expert RBAC designer for hotel management software. "
            "Given a plain-English role description, select the MINIMUM set of permission keys "
            "from the catalog that this role needs. Prefer view-only over edit; avoid destructive "
            "permissions (Delete, Approve Payroll, Mark Paid, Process Refunds) unless explicitly justified. "
            "Always include corresponding 'View' / 'MENU' permissions for any module you grant access to, "
            "so users can see the sidebar entry. Return ONLY valid JSON matching this schema:\n"
            '{"permissions":["key1","key2",...], "reasoning":"2-3 sentences explaining the choices", '
            '"role_name_suggestion":"snake_case_name", "display_name_suggestion":"Title Case Name"}'
        )

        user_content = (
            f"ROLE DESCRIPTION:\n{body.description}\n\n"
            f"CURRENT PERMISSIONS (may be empty):\n{', '.join(body.existing_permissions) or '(none)'}\n\n"
            f"AVAILABLE PERMISSIONS CATALOG:\n" + "\n\n".join(catalog_summary)
        )

        try:
            chat = LlmChat(
                api_key=api_key,
                session_id=f"rbac-ai-{current_user.get('id','x')}-{uuid.uuid4().hex[:8]}",
                system_message=system_msg,
            ).with_model("openai", "gpt-5")
            resp = await chat.send_message(UserMessage(text=user_content))
            resp_text = resp if isinstance(resp, str) else str(resp)

            # Extract JSON — GPT may wrap in ```json fences
            import re as _re
            m = _re.search(r"\{[\s\S]*\}", resp_text)
            if not m:
                raise ValueError("No JSON in response")
            parsed = json.loads(m.group(0))

            valid_keys = set(get_all_permission_keys())
            suggested = [k for k in parsed.get("permissions", []) if k in valid_keys]
            return {
                "permissions": suggested,
                "reasoning": parsed.get("reasoning", ""),
                "role_name_suggestion": parsed.get("role_name_suggestion", ""),
                "display_name_suggestion": parsed.get("display_name_suggestion", ""),
                "total_suggested": len(suggested),
                "invalid_dropped": max(0, len(parsed.get("permissions", [])) - len(suggested)),
            }
        except Exception as e:
            logger.exception("AI suggestion failed")
            raise HTTPException(502, f"AI suggestion failed: {str(e)[:200]}")

    # ------- LIST -------
    @router.get("/rbac/roles")
    async def list_roles(property_id: str = "", q: str = "",
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        query: dict = {}
        if property_id:
            query["property_id"] = property_id
        roles = await db.roles.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
        if q:
            ql = q.lower()
            roles = [r for r in roles if ql in (r.get("key") or "").lower()
                     or ql in (r.get("display_name") or "").lower()]

        # Count assigned users per role
        assignments = await db.users.aggregate([
            {"$group": {"_id": "$role_key", "count": {"$sum": 1}}}
        ]).to_list(500)
        assign_map = {a["_id"]: a["count"] for a in assignments if a.get("_id")}
        for r in roles:
            r["assigned_users"] = assign_map.get(r["key"], 0)

        return {
            "roles": roles,
            "total": len(roles),
            "total_permissions_available": count_total_permissions(),
        }

    # ------- GET ONE -------
    @router.get("/rbac/roles/{role_id}")
    async def get_role(role_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        r = await db.roles.find_one({"id": role_id}, {"_id": 0})
        if not r:
            raise HTTPException(404, "Role not found")
        r["assigned_users"] = await db.users.count_documents({"role_key": r["key"]})
        return r

    # ------- CREATE -------
    @router.post("/rbac/roles")
    async def create_role(body: RoleCreate,
                          current_user: dict = Depends(require_roles("admin"))):
        key = body.key.strip().lower()
        if not KEY_REGEX.match(key):
            raise HTTPException(400, "Key must be lowercase letters, digits and underscores (2-50 chars, starts with letter)")

        # Branch scoping — key unique per property
        exists = await db.roles.find_one({"key": key, "property_id": body.property_id})
        if exists:
            raise HTTPException(400, f"Role key '{key}' already exists for this branch")

        # Resolve permissions (template overrides explicit list if provided)
        if body.template:
            perms = expand_template_permissions(body.template)
            if not perms:
                raise HTTPException(400, f"Unknown template '{body.template}'")
        else:
            perms = body.permissions or []

        # Validate all permissions against catalog
        valid_keys = set(get_all_permission_keys())
        invalid = [p for p in perms if p not in valid_keys]
        if invalid:
            raise HTTPException(400, f"Invalid permissions: {invalid[:5]}")

        role = {
            "id": str(uuid.uuid4()),
            "key": key,
            "display_name": (body.display_name or "").strip() or None,
            "property_id": body.property_id,
            "property_name": None,
            "permissions": perms,
            "is_global_admin": bool(body.is_global_admin),
            "template_used": body.template,
            "created_by_id": current_user.get("id"),
            "created_by_name": current_user.get("name"),
            "created_at": _now(),
            "updated_at": _now(),
        }
        if body.property_id:
            prop = await db.properties.find_one({"id": body.property_id}, {"_id": 0, "name": 1})
            if prop:
                role["property_name"] = prop.get("name")

        await db.roles.insert_one(role)
        role.pop("_id", None)
        return role

    # ------- UPDATE (display_name, permissions, is_global_admin only — key is immutable) -------
    @router.put("/rbac/roles/{role_id}")
    async def update_role(role_id: str, body: RoleUpdate,
                          current_user: dict = Depends(require_roles("admin"))):
        r = await db.roles.find_one({"id": role_id})
        if not r:
            raise HTTPException(404, "Role not found")
        updates: dict = {"updated_at": _now()}
        if body.display_name is not None:
            updates["display_name"] = body.display_name.strip() or None
        if body.permissions is not None:
            valid_keys = set(get_all_permission_keys())
            invalid = [p for p in body.permissions if p not in valid_keys]
            if invalid:
                raise HTTPException(400, f"Invalid permissions: {invalid[:5]}")
            updates["permissions"] = body.permissions
        if body.is_global_admin is not None:
            updates["is_global_admin"] = bool(body.is_global_admin)

        await db.roles.update_one({"id": role_id}, {"$set": updates})
        return await db.roles.find_one({"id": role_id}, {"_id": 0})

    # ------- CLONE -------
    @router.post("/rbac/roles/{role_id}/clone")
    async def clone_role(role_id: str, body: CloneRequest,
                         current_user: dict = Depends(require_roles("admin"))):
        src = await db.roles.find_one({"id": role_id}, {"_id": 0})
        if not src:
            raise HTTPException(404, "Role not found")

        new_key = body.new_key.strip().lower()
        if not KEY_REGEX.match(new_key):
            raise HTTPException(400, "Key must be lowercase letters, digits and underscores")
        exists = await db.roles.find_one({"key": new_key, "property_id": src.get("property_id")})
        if exists:
            raise HTTPException(400, f"Role key '{new_key}' already exists for this branch")

        cloned = {
            **src,
            "id": str(uuid.uuid4()),
            "key": new_key,
            "display_name": (body.display_name or f"{src.get('display_name') or src.get('key')} (copy)").strip(),
            "created_by_id": current_user.get("id"),
            "created_by_name": current_user.get("name"),
            "cloned_from_id": src["id"],
            "cloned_from_key": src["key"],
            "created_at": _now(),
            "updated_at": _now(),
        }
        cloned.pop("_id", None)
        await db.roles.insert_one(cloned)
        cloned.pop("_id", None)
        return cloned

    # ------- DELETE -------
    @router.delete("/rbac/roles/{role_id}")
    async def delete_role(role_id: str,
                          current_user: dict = Depends(require_roles("admin"))):
        r = await db.roles.find_one({"id": role_id}, {"_id": 0, "key": 1})
        if not r:
            raise HTTPException(404, "Role not found")
        # Block delete if role has assigned users
        assigned = await db.users.count_documents({"role_key": r["key"]})
        if assigned > 0:
            raise HTTPException(400, f"Cannot delete: {assigned} user(s) currently assigned this role")
        await db.roles.delete_one({"id": role_id})
        return {"ok": True}

    return router
