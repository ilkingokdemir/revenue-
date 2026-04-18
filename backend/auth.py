"""
Authentication utilities for the Hotel Review Hub.
Extracted from server.py for maintainability.
"""
from fastapi import HTTPException, Request
from datetime import datetime, timezone, timedelta
from bson import ObjectId
import bcrypt
import jwt
import os

from database import db

JWT_ALGORITHM = "HS256"

def get_jwt_secret():
    return os.environ["JWT_SECRET"]

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

def create_access_token(user_id: str, email: str) -> str:
    payload = {"sub": user_id, "email": email, "exp": datetime.now(timezone.utc) + timedelta(hours=24), "type": "access"}
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)

def create_refresh_token(user_id: str) -> str:
    payload = {"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(days=7), "type": "refresh"}
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)

async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        user["_id"] = str(user["_id"])
        user.pop("password_hash", None)
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def require_roles(*roles):
    async def role_checker(request: Request):
        user = await get_current_user(request)
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return role_checker


# ======================================================================
# Permission-based enforcement (RBAC v2)
# ======================================================================
# Legacy role → permission presets. Apply when a user has no `role_key`
# (hasn't been migrated to the new RBAC yet). Admin = bypass (grants all).
_LEGACY_ROLE_PERMS_CACHE = None


def _get_legacy_role_perms():
    """Lazy import to avoid circular deps with routes.permission_catalog."""
    global _LEGACY_ROLE_PERMS_CACHE
    if _LEGACY_ROLE_PERMS_CACHE is not None:
        return _LEGACY_ROLE_PERMS_CACHE
    try:
        from routes.permission_catalog import expand_template_permissions, get_all_permission_keys
        _LEGACY_ROLE_PERMS_CACHE = {
            "admin":        set(get_all_permission_keys()),   # admin = all perms
            "manager":      set(get_all_permission_keys()),   # manager = all (matches 'manager' template)
            "receptionist": set(expand_template_permissions("receptionist")),
            "housekeeper":  set(expand_template_permissions("housekeeper")),
            "accountant":   set(expand_template_permissions("accountant")),
            "laundry_staff": set(expand_template_permissions("laundry_staff")),
            "maintenance":  set(expand_template_permissions("maintenance")),
        }
    except Exception:
        _LEGACY_ROLE_PERMS_CACHE = {}
    return _LEGACY_ROLE_PERMS_CACHE


async def get_user_permissions(user: dict) -> set:
    """Resolve a user's effective permission set.
    Priority:
      1. role doc in db.roles (by role_key) — is_global_admin grants all.
      2. Legacy role presets (admin/manager/receptionist/…) — backwards compat.
    """
    role_key = user.get("role_key")
    # 1. Custom role via role_key
    if role_key:
        role_doc = await db.roles.find_one({"key": role_key}, {"_id": 0, "permissions": 1, "is_global_admin": 1})
        if role_doc:
            if role_doc.get("is_global_admin"):
                from routes.permission_catalog import get_all_permission_keys
                return set(get_all_permission_keys())
            return set(role_doc.get("permissions") or [])

    # 2. Legacy role preset
    legacy_role = user.get("role")
    return _get_legacy_role_perms().get(legacy_role, set())


def require_perm(*perm_keys, mode: str = "any"):
    """
    Require the user to have one (mode='any') or all (mode='all') of the given permission keys.
    Usage:
        current_user: dict = Depends(require_perm("approve_payroll_runs"))
        current_user: dict = Depends(require_perm("view_bookings","edit_bookings", mode="all"))
    Always allows role==admin (legacy back-compat).
    Logs every denied attempt to db.audit_trail for enterprise security visibility.
    """
    async def perm_checker(request: Request):
        user = await get_current_user(request)
        # Always allow legacy admin role (cannot lock themselves out)
        if user.get("role") == "admin":
            return user
        perms = await get_user_permissions(user)
        needed = set(perm_keys)
        ok = needed.issubset(perms) if mode == "all" else bool(needed & perms)
        if not ok:
            missing = list(needed - perms)
            # Record the denied attempt (fire-and-forget; do not crash on insert failure)
            try:
                await db.audit_trail.insert_one({
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "user_id": user.get("_id"),
                    "user_email": user.get("email"),
                    "user_name": user.get("name"),
                    "user_role": user.get("role"),
                    "user_role_key": user.get("role_key"),
                    "method": request.method,
                    "path": str(request.url.path),
                    "query": str(request.url.query),
                    "client_ip": (request.client.host if request.client else None),
                    "user_agent": request.headers.get("user-agent", "")[:300],
                    "required_perms": list(needed),
                    "mode": mode,
                    "user_perms_count": len(perms),
                    "missing_perms": missing,
                    "result": "denied",
                })
            except Exception:
                pass
            raise HTTPException(
                status_code=403,
                detail=f"Missing permission{'s' if len(missing) > 1 else ''}: {', '.join(missing[:3])}"
            )
        return user
    return perm_checker

async def verify_api_key(request: Request) -> dict:
    """Authenticate via API key (for widget/external access)"""
    api_key = request.query_params.get("api_key")
    if not api_key:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer rhk_"):
            api_key = auth_header[7:]
    if not api_key or not api_key.startswith("rhk_"):
        raise HTTPException(status_code=401, detail="Valid API key required")
    key_doc = await db.api_keys.find_one({"key": api_key, "is_active": True}, {"_id": 0})
    if not key_doc:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key")
    await db.api_keys.update_one({"key": api_key}, {
        "$set": {"last_used": datetime.now(timezone.utc).isoformat()},
        "$inc": {"request_count": 1}
    })
    return key_doc
