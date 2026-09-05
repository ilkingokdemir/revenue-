"""
Admin Panel — Role & Permission Management, Module Settings, Auto Purchase Orders
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Dict, List, Optional
import uuid
import logging

logger = logging.getLogger(__name__)

MODULES = [
    "dashboard", "reviews", "bookings", "pos", "payments", "accounting",
    "stock", "messaging", "surveys", "guest_profiles", "campaigns",
    "staff_performance", "automation", "settings",
]

ACTIONS = ["view", "create", "edit", "delete", "export", "manage_settings"]

DEFAULT_PERMISSIONS = {
    "admin": {m: ACTIONS[:] for m in MODULES},
    "manager": {m: ["view", "create", "edit", "export"] for m in MODULES},
    "receptionist": {
        "dashboard": ["view"], "reviews": ["view", "create"], "bookings": ["view", "create", "edit"],
        "pos": ["view", "create"], "payments": ["view"], "accounting": ["view"],
        "stock": ["view"], "messaging": ["view", "create", "edit"], "surveys": ["view"],
        "guest_profiles": ["view", "create", "edit"], "campaigns": ["view"],
        "staff_performance": ["view"], "automation": ["view"], "settings": [],
    },
    "night_auditor": {
        "dashboard": ["view"], "reviews": ["view"], "bookings": ["view", "edit"],
        "pos": ["view", "create", "edit"], "payments": ["view", "export"],
        "accounting": ["view", "create", "edit", "export"], "stock": ["view"],
        "messaging": ["view"], "surveys": ["view"], "guest_profiles": ["view"],
        "campaigns": [], "staff_performance": ["view"], "automation": [], "settings": [],
    },
    "restaurant_manager": {
        "dashboard": ["view"], "reviews": ["view"], "bookings": [],
        "pos": ACTIONS[:], "payments": ["view"], "accounting": ["view"],
        "stock": ["view", "create", "edit", "delete"], "messaging": ["view", "create"],
        "surveys": ["view"], "guest_profiles": ["view"], "campaigns": [],
        "staff_performance": ["view"], "automation": [], "settings": [],
    },
}

# Review Ops: CAN_GENERATE / CAN_APPROVE / CAN_PUBLISH ayrımı (spec §32)
REVIEW_ACTIONS = ["generate", "approve", "publish"]
DEFAULT_PERMISSIONS["admin"]["reviews"] += REVIEW_ACTIONS
DEFAULT_PERMISSIONS["manager"]["reviews"] += REVIEW_ACTIONS
DEFAULT_PERMISSIONS["receptionist"]["reviews"] += ["generate"]


def has_permission(user: dict, module: str, action: str, property_id: str = None) -> bool:
    """custom_permissions varsa onu; property_roles[property_id] varsa o rolü; yoksa genel rolü kullanır."""
    u = user or {}
    if u.get("custom_permissions") and not (property_id and property_id in (u.get("property_roles") or {})):
        perms = u["custom_permissions"]
    else:
        role = (u.get("property_roles") or {}).get(property_id) if property_id else None
        perms = DEFAULT_PERMISSIONS.get(role or u.get("role", ""), {})
    return action in (perms.get(module) or [])


def create_admin_router(db, require_roles):
    router = APIRouter()

    # ==================== CUSTOM ROLES ====================

    @router.get("/admin/roles")
    async def list_roles(current_user: dict = Depends(require_roles("admin"))):
        """List all roles (built-in + custom)"""
        custom_roles = await db.custom_roles.find({}, {"_id": 0}).to_list(50)
        built_in = [
            {"id": "admin", "name": "Admin", "description": "Full access to all modules", "is_builtin": True, "permissions": DEFAULT_PERMISSIONS["admin"]},
            {"id": "manager", "name": "Manager", "description": "View, create, edit, export across all modules", "is_builtin": True, "permissions": DEFAULT_PERMISSIONS["manager"]},
            {"id": "receptionist", "name": "Receptionist", "description": "Basic access to front desk operations", "is_builtin": True, "permissions": DEFAULT_PERMISSIONS["receptionist"]},
        ]
        return {"roles": built_in + custom_roles, "modules": MODULES, "actions": ACTIONS}

    @router.post("/admin/roles")
    async def create_role(data: Dict, current_user: dict = Depends(require_roles("admin"))):
        """Create a custom role with specific permissions"""
        role_id = data.get("id", "").lower().replace(" ", "_") or str(uuid.uuid4())[:8]
        existing = await db.custom_roles.find_one({"id": role_id}, {"_id": 0})
        if existing or role_id in ("admin", "manager", "receptionist"):
            raise HTTPException(400, "Role ID already exists")

        role = {
            "id": role_id,
            "name": data.get("name", role_id.title()),
            "description": data.get("description", ""),
            "is_builtin": False,
            "permissions": data.get("permissions", {}),
            "created_by": current_user.get("email", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.custom_roles.insert_one(role)
        role.pop("_id", None)
        return role

    @router.put("/admin/roles/{role_id}")
    async def update_role(role_id: str, data: Dict, current_user: dict = Depends(require_roles("admin"))):
        """Update a custom role's permissions"""
        if role_id in ("admin", "manager", "receptionist"):
            raise HTTPException(400, "Cannot modify built-in roles")
        data.pop("_id", None)
        data.pop("id", None)
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.custom_roles.update_one({"id": role_id}, {"$set": data})
        doc = await db.custom_roles.find_one({"id": role_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Role not found")
        return doc

    @router.delete("/admin/roles/{role_id}")
    async def delete_role(role_id: str, current_user: dict = Depends(require_roles("admin"))):
        if role_id in ("admin", "manager", "receptionist"):
            raise HTTPException(400, "Cannot delete built-in roles")
        # Check if any users have this role
        user_count = await db.users.count_documents({"role": role_id})
        if user_count > 0:
            raise HTTPException(400, f"Cannot delete: {user_count} user(s) have this role")
        await db.custom_roles.delete_one({"id": role_id})
        return {"status": "deleted"}

    # ==================== USER PERMISSIONS ====================

    @router.get("/admin/users")
    async def list_users_with_permissions(current_user: dict = Depends(require_roles("admin", "manager"))):
        """List all users with their roles and permissions"""
        users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(100)
        # Enrich with permissions
        for u in users:
            role = u.get("role", "receptionist")
            custom_perms = u.get("custom_permissions")
            if custom_perms:
                u["effective_permissions"] = custom_perms
            elif role in DEFAULT_PERMISSIONS:
                u["effective_permissions"] = DEFAULT_PERMISSIONS[role]
            else:
                custom_role = await db.custom_roles.find_one({"id": role}, {"_id": 0})
                u["effective_permissions"] = custom_role.get("permissions", {}) if custom_role else {}
        return users

    @router.put("/admin/users/{user_id}/permissions")
    async def update_user_permissions(user_id: str, data: Dict, current_user: dict = Depends(require_roles("admin"))):
        """Set custom permissions for a specific user (overrides role defaults)"""
        user = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
        if not user:
            raise HTTPException(404, "User not found")
        updates = {}
        if "role" in data:
            updates["role"] = data["role"]
        if "permissions" in data:
            updates["custom_permissions"] = data["permissions"]
        if "property_access" in data:
            updates["property_access"] = data["property_access"]
        if "branch_payments" in data:
            updates["branch_payments"] = data["branch_payments"]
        if "color" in data:
            updates["color"] = data["color"]
        if "phone" in data:
            updates["phone"] = (data["phone"] or "").strip()
        if "karne_whatsapp" in data:
            updates["karne_whatsapp"] = bool(data["karne_whatsapp"])
        if "name" in data:
            updates["name"] = data["name"]
        if "department" in data:
            updates["department"] = data["department"]
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.users.update_one({"id": user_id}, {"$set": updates})
        updated = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
        return updated

    @router.get("/admin/users/{user_id}")
    async def get_user_detail(user_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
        if not user:
            raise HTTPException(404, "User not found")
        return user

    @router.get("/admin/my-shifts")
    async def my_shifts(week_start: str = "", current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeper", "maintenance"))):
        """Get shifts for the current logged-in user"""
        user_email = current_user.get("email", "")
        user_name = current_user.get("name", "")
        query = {"$or": [{"staff_name": user_name}]}
        if week_start:
            query["week_start"] = week_start
        shifts = await db.shift_entries.find(query, {"_id": 0}).sort("date", 1).to_list(100)
        return shifts

    # ==================== MODULE SETTINGS ====================

    @router.get("/admin/module-settings/{module}/{property_id}")
    async def get_module_settings(module: str, property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Get settings for a specific module"""
        doc = await db.module_settings.find_one({"module": module, "property_id": property_id}, {"_id": 0})
        if not doc:
            defaults = _get_default_module_settings(module, property_id)
            await db.module_settings.insert_one(defaults)
            defaults.pop("_id", None)
            return defaults
        return doc

    @router.put("/admin/module-settings/{module}/{property_id}")
    async def update_module_settings(module: str, property_id: str, data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Update settings for a specific module"""
        data.pop("_id", None)
        data.pop("id", None)
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        data["updated_by"] = current_user.get("email", "")
        await db.module_settings.update_one(
            {"module": module, "property_id": property_id}, {"$set": data}, upsert=True
        )
        doc = await db.module_settings.find_one({"module": module, "property_id": property_id}, {"_id": 0})
        return doc

    @router.get("/admin/module-settings-all/{property_id}")
    async def get_all_module_settings(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Get settings for all modules at once"""
        result = {}
        for module in MODULES:
            doc = await db.module_settings.find_one({"module": module, "property_id": property_id}, {"_id": 0})
            if not doc:
                doc = _get_default_module_settings(module, property_id)
                await db.module_settings.insert_one(doc)
                doc.pop("_id", None)
            result[module] = doc
        return result

    # ==================== AUTO PURCHASE ORDERS ====================

    @router.post("/admin/auto-purchase-orders/{property_id}")
    async def generate_auto_purchase_orders(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Generate purchase orders for items below reorder level"""
        products = await db.stock_products.find({
            "property_id": property_id,
            "is_active": True,
        }, {"_id": 0}).to_list(500)

        low_stock_items = []
        for p in products:
            if p.get("current_stock", 0) <= p.get("reorder_level", 0) and p.get("par_level", 0) > 0:
                qty_needed = p["par_level"] - p.get("current_stock", 0)
                if qty_needed > 0:
                    low_stock_items.append({
                        "product_id": p["id"],
                        "product_name": p["name"],
                        "category": p.get("category", ""),
                        "current_stock": p.get("current_stock", 0),
                        "reorder_level": p.get("reorder_level", 0),
                        "par_level": p.get("par_level", 0),
                        "quantity_to_order": qty_needed,
                        "unit": p.get("unit", "pcs"),
                        "supplier": p.get("supplier", ""),
                        "estimated_cost": round(qty_needed * p.get("cost_price", 0), 2),
                    })

        if not low_stock_items:
            return {"status": "no_orders_needed", "message": "All items are above reorder level", "orders": []}

        # Group by supplier
        by_supplier = {}
        for item in low_stock_items:
            supplier = item.get("supplier") or "Unassigned"
            if supplier not in by_supplier:
                by_supplier[supplier] = []
            by_supplier[supplier].append(item)

        purchase_orders = []
        for supplier, items in by_supplier.items():
            po = {
                "id": str(uuid.uuid4()),
                "po_number": f"PO-{datetime.now(timezone.utc).strftime('%y%m%d')}-{str(uuid.uuid4())[:4].upper()}",
                "property_id": property_id,
                "supplier": supplier,
                "status": "draft",
                "items": items,
                "total_items": len(items),
                "total_cost": round(sum(i["estimated_cost"] for i in items), 2),
                "created_by": current_user.get("email", ""),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.purchase_orders.insert_one(po)
            po.pop("_id", None)
            purchase_orders.append(po)

        return {
            "status": "generated",
            "message": f"Generated {len(purchase_orders)} purchase order(s) for {len(low_stock_items)} items",
            "orders": purchase_orders,
        }

    @router.get("/admin/purchase-orders/{property_id}")
    async def list_purchase_orders(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        docs = await db.purchase_orders.find({"property_id": property_id}, {"_id": 0}).sort("created_at", -1).to_list(100)
        return docs

    @router.put("/admin/purchase-orders/{po_id}/status")
    async def update_po_status(po_id: str, data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Update PO status (draft → approved → ordered → received)"""
        status = data.get("status", "")
        if status not in ("approved", "ordered", "received", "cancelled"):
            raise HTTPException(400, "Invalid status")
        updates = {"status": status, "updated_at": datetime.now(timezone.utc).isoformat()}
        if status == "received":
            # Auto-replenish stock
            po = await db.purchase_orders.find_one({"id": po_id}, {"_id": 0})
            if po:
                for item in po.get("items", []):
                    await db.stock_products.update_one(
                        {"id": item["product_id"]},
                        {"$inc": {"current_stock": item["quantity_to_order"]}}
                    )
                    await db.stock_movements.insert_one({
                        "id": str(uuid.uuid4()),
                        "product_id": item["product_id"],
                        "property_id": po["property_id"],
                        "type": "purchase_received",
                        "quantity": item["quantity_to_order"],
                        "reference": f"PO {po.get('po_number','')}",
                        "item_name": item["product_name"],
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    })
                updates["received_at"] = datetime.now(timezone.utc).isoformat()
        await db.purchase_orders.update_one({"id": po_id}, {"$set": updates})
        doc = await db.purchase_orders.find_one({"id": po_id}, {"_id": 0})
        return doc

    return router


def _get_default_module_settings(module: str, property_id: str) -> dict:
    """Default settings for each module"""
    base = {"id": str(uuid.uuid4()), "module": module, "property_id": property_id, "created_at": datetime.now(timezone.utc).isoformat()}
    defaults = {
        "pos": {**base, "tax_rate": 20, "service_charge_pct": 0, "default_tip_options": [0, 5, 10, 15, 20],
                "receipt_header": "", "receipt_footer": "Thank you for dining with us!", "auto_print_receipt": False,
                "allow_discounts": True, "max_discount_pct": 50, "require_table_number": False,
                "kitchen_display_enabled": True, "order_numbering_prefix": "POS", "currency": "GBP"},
        "bookings": {**base, "check_in_time": "15:00", "check_out_time": "11:00", "cancellation_hours": 24,
                     "deposit_pct": 0, "overbooking_buffer": 0, "min_stay": 1, "max_stay": 30,
                     "auto_confirm": True, "require_credit_card": False, "send_confirmation_email": True,
                     "send_pre_arrival_email": True, "pre_arrival_hours": 24, "currency": "GBP"},
        "accounting": {**base, "financial_year_start": "01-01", "default_currency": "GBP", "tax_rate": 20,
                       "auto_post_pos": True, "auto_post_bookings": True, "invoice_prefix": "INV",
                       "invoice_due_days": 30, "bank_name": "", "bank_account": "", "bank_sort_code": ""},
        "messaging": {**base, "auto_reply_enabled": False, "auto_reply_message": "Thank you for your message. We'll respond shortly.",
                      "business_hours_start": "08:00", "business_hours_end": "22:00",
                      "away_message": "We're currently closed. We'll get back to you during business hours.",
                      "response_time_target_minutes": 15, "auto_translate": False},
        "reviews": {**base, "auto_respond": False, "review_request_delay_hours": 24,
                    "minimum_rating_alert": 3, "auto_response_template": "",
                    "review_platforms": ["google", "booking.com", "tripadvisor"],
                    "request_review_on_checkout": True},
        "stock": {**base, "low_stock_alert_enabled": True, "auto_reorder_enabled": False,
                  "wastage_tracking": True, "default_par_level": 30, "default_reorder_level": 5,
                  "stock_count_frequency": "weekly", "alert_email": ""},
        "surveys": {**base, "auto_send_on_checkout": False, "send_delay_hours": 2,
                    "reminder_enabled": False, "reminder_delay_hours": 48, "anonymous_allowed": True},
        "guest_profiles": {**base, "auto_merge_duplicates": True, "track_preferences": True,
                           "gdpr_data_retention_days": 365, "loyalty_program_enabled": False},
        "campaigns": {**base, "max_emails_per_day": 500, "unsubscribe_link": True,
                      "sender_name": "", "default_from_email": ""},
        "staff_performance": {**base, "track_response_time": True, "track_guest_satisfaction": True,
                              "review_cycle": "monthly", "target_response_minutes": 10},
        "automation": {**base, "max_rules": 50, "enabled": True},
        "dashboard": {**base, "default_date_range": "30d", "show_revenue": True, "show_occupancy": True},
        "payments": {**base, "stripe_enabled": True, "iyzico_enabled": False, "paytr_enabled": False,
                     "default_currency": "GBP", "tipping_enabled": True, "room_charging_enabled": True},
        "settings": {**base},
    }
    return defaults.get(module, base)
