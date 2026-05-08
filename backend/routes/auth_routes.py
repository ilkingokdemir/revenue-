"""
Auth, User Management, and Property Management Routes
Extracted from server.py for maintainability
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from datetime import datetime, timezone, timedelta
from bson import ObjectId
import jwt
from auth import require_perm


def create_auth_router(db, require_roles, get_current_user, hash_password, verify_password,
                        create_access_token, create_refresh_token, get_jwt_secret, JWT_ALGORITHM):
    """Factory function that creates auth routes with injected dependencies"""
    from models import (
        UserRegister, UserLogin, UserUpdate, Property, PropertyCreate, PropertyUpdate,
        VALID_ROLES, VALID_DEPARTMENTS, VALID_PROPERTY_TYPES,
    )
    router = APIRouter()

    # ==================== AUTH ROUTES ====================

    @router.post("/auth/register")
    async def register(user: UserRegister, request: Request, response: Response, current_user: dict = Depends(require_perm("create_users"))):
        """Register new user (admin only)"""
        email = user.email.lower().strip()
        existing = await db.users.find_one({"email": email})
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")
        if user.role not in VALID_ROLES:
            raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {', '.join(VALID_ROLES)}")
        if user.department not in VALID_DEPARTMENTS:
            raise HTTPException(status_code=400, detail=f"Invalid department. Must be one of: {', '.join(VALID_DEPARTMENTS)}")

        hashed = hash_password(user.password)
        # Admins + managers are activated instantly. Other staff roles must complete onboarding.
        needs_onboarding = user.role not in ("admin", "manager")
        new_user = {
            "id": str(__import__('uuid').uuid4()),
            "email": email,
            "password_hash": hashed,
            "name": user.name,
            "role": user.role,
            "department": user.department,
            "is_active": True,
            "is_activated": not needs_onboarding,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        result = await db.users.insert_one(new_user)
        return {
            "id": new_user["id"],
            "email": email,
            "name": user.name,
            "role": user.role,
            "department": user.department,
            "is_active": True,
            "is_activated": not needs_onboarding,
            "needs_onboarding": needs_onboarding,
        }

    @router.post("/auth/login")
    async def login(user: UserLogin, request: Request, response: Response):
        """Login"""
        email = user.email.lower().strip()
        client_ip = request.client.host if request.client else "unknown"
        identifier = f"{client_ip}:{email}"
        attempts = await db.login_attempts.find_one({"identifier": identifier})
        if attempts and attempts.get("count", 0) >= 5:
            last_attempt = attempts.get("last_attempt")
            if last_attempt:
                if isinstance(last_attempt, str):
                    last_attempt = datetime.fromisoformat(last_attempt)
                if datetime.now(timezone.utc) - last_attempt < timedelta(minutes=15):
                    raise HTTPException(status_code=429, detail="Too many login attempts. Try again in 15 minutes.")

        db_user = await db.users.find_one({"email": email})
        if not db_user or not verify_password(user.password, db_user["password_hash"]):
            await db.login_attempts.update_one(
                {"identifier": identifier},
                {"$inc": {"count": 1}, "$set": {"last_attempt": datetime.now(timezone.utc).isoformat()}},
                upsert=True
            )
            raise HTTPException(status_code=401, detail="Invalid email or password")

        if not db_user.get("is_active", True):
            raise HTTPException(status_code=403, detail="Account is deactivated")

        await db.login_attempts.delete_one({"identifier": identifier})

        user_id = str(db_user["_id"])
        access_token = create_access_token(user_id, email)
        refresh_token = create_refresh_token(user_id)

        response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite="lax", max_age=86400, path="/")
        response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, secure=False, samesite="lax", max_age=604800, path="/")

        return {
            "id": user_id,
            "email": db_user["email"],
            "name": db_user["name"],
            "role": db_user["role"],
            "department": db_user.get("department", "front_desk"),
            "is_activated": db_user.get("is_activated", True),
            "token": access_token
        }

    @router.get("/auth/me")
    async def get_me(current_user: dict = Depends(get_current_user)):
        return {
            "id": current_user["_id"],
            "email": current_user["email"],
            "name": current_user["name"],
            "role": current_user["role"],
            "department": current_user.get("department", "front_desk"),
            "is_active": current_user.get("is_active", True),
            "is_activated": current_user.get("is_activated", True)
        }

    @router.post("/auth/logout")
    async def logout(response: Response):
        response.delete_cookie("access_token", path="/")
        response.delete_cookie("refresh_token", path="/")
        return {"message": "Logged out"}

    @router.post("/auth/refresh")
    async def refresh_token_endpoint(request: Request, response: Response):
        token = request.cookies.get("refresh_token")
        if not token:
            raise HTTPException(status_code=401, detail="No refresh token")
        try:
            payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
            if payload.get("type") != "refresh":
                raise HTTPException(status_code=401, detail="Invalid token type")
            user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
            if not user:
                raise HTTPException(status_code=401, detail="User not found")
            new_access = create_access_token(str(user["_id"]), user["email"])
            response.set_cookie(key="access_token", value=new_access, httponly=True, secure=False, samesite="lax", max_age=86400, path="/")
            return {"message": "Token refreshed"}
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Refresh token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid refresh token")

    # ==================== USER MANAGEMENT ROUTES ====================

    @router.get("/users")
    async def list_users(current_user: dict = Depends(require_roles("admin", "manager"))):
        users = await db.users.find({}, {"password_hash": 0}).to_list(100)
        for u in users:
            u["_id"] = str(u["_id"])
            u["id"] = u.pop("_id")
        return users

    @router.put("/users/{user_id}")
    async def update_user(user_id: str, update: UserUpdate, current_user: dict = Depends(require_perm("edit_users"))):
        update_data = {k: v for k, v in update.model_dump().items() if v is not None}
        if "role" in update_data and update_data["role"] not in VALID_ROLES:
            raise HTTPException(status_code=400, detail="Invalid role")
        if "department" in update_data and update_data["department"] not in VALID_DEPARTMENTS:
            raise HTTPException(status_code=400, detail="Invalid department")
        result = await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": update_data})
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="User not found")
        return {"message": "User updated"}

    @router.delete("/users/{user_id}")
    async def delete_user(user_id: str, current_user: dict = Depends(require_perm("delete_users"))):
        if current_user["_id"] == user_id:
            raise HTTPException(status_code=400, detail="Cannot delete yourself")
        result = await db.users.delete_one({"_id": ObjectId(user_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="User not found")
        return {"message": "User deleted"}

    # ==================== PROPERTY MANAGEMENT ROUTES ====================

    @router.get("/properties")
    async def list_properties(request: Request):
        """List all properties"""
        current_user = await get_current_user(request)
        properties = await db.properties.find({}, {"_id": 0}).to_list(100)
        if not properties:
            # Seed a default property if none exist
            default_prop = {
                "id": "default",
                "name": "My Hotel",
                "address": "",
                "city": "",
                "country": "",
                "property_type": "hotel",
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.properties.insert_one(default_prop)
            properties = [default_prop]
        return [{k: v for k, v in p.items() if k != "_id"} for p in properties]

    @router.post("/properties")
    async def create_property(prop: PropertyCreate, current_user: dict = Depends(require_perm("create_branches"))):
        """Create a new property (admin only)"""
        if prop.property_type not in VALID_PROPERTY_TYPES:
            raise HTTPException(status_code=400, detail=f"Invalid property type. Must be one of: {', '.join(VALID_PROPERTY_TYPES)}")
        new_prop = Property(**prop.model_dump())
        doc = new_prop.model_dump()
        await db.properties.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.put("/properties/{property_id}")
    async def update_property(property_id: str, update: PropertyUpdate, current_user: dict = Depends(require_perm("edit_branches"))):
        """Update a property (admin only)"""
        update_data = {k: v for k, v in update.model_dump().items() if v is not None}
        if "property_type" in update_data and update_data["property_type"] not in VALID_PROPERTY_TYPES:
            raise HTTPException(status_code=400, detail="Invalid property type")
        result = await db.properties.update_one({"id": property_id}, {"$set": update_data})
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Property not found")
        updated = await db.properties.find_one({"id": property_id}, {"_id": 0})
        return updated

    @router.delete("/properties/{property_id}")
    async def delete_property(property_id: str, current_user: dict = Depends(require_perm("delete_branches"))):
        """Delete a property (admin only)"""
        if property_id == "default":
            raise HTTPException(status_code=400, detail="Cannot delete default property")
        result = await db.properties.delete_one({"id": property_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Property not found")
        return {"message": "Property deleted"}

    @router.get("/roles")
    async def get_roles():
        return {
            "roles": [
                {"id": "admin", "name": "Admin", "description": "Full access, manage users and settings"},
                {"id": "manager", "name": "Manager", "description": "Approve/reject responses, view analytics"},
                {"id": "receptionist", "name": "Receptionist", "description": "Draft responses, submit for approval"}
            ],
            "departments": [
                {"id": "front_desk", "name": "Front Desk"},
                {"id": "management", "name": "Management"},
                {"id": "housekeeping", "name": "Housekeeping"},
                {"id": "food_beverage", "name": "Food & Beverage"},
                {"id": "maintenance", "name": "Maintenance"},
                {"id": "spa_wellness", "name": "Spa & Wellness"},
                {"id": "concierge", "name": "Concierge"}
            ]
        }


    return router
