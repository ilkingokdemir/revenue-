"""
Permission Catalog — inspired by myhotelbox/Eviivo benchmark.
Deterministic source of truth for ~320 permissions organized as:
  Category → Sub-group → Permission
Each permission has:
  key: unique snake_case identifier
  label: user-facing name
  menu: True if it controls a sidebar entry (shown as MENU badge)
  missing: True if the underlying module isn't built yet (greyed out)

Structure consumed by the frontend tree renderer + backend enforcement middleware.
"""
from typing import Dict, List


def _p(key: str, label: str, menu: bool = False, missing: bool = False) -> Dict:
    return {"key": key, "label": label, "menu": menu, "missing": missing}


# ======================================================================
# Permission metadata overlay — risk levels, dependencies, categorisation
# Applied on top of the declarative catalog so we don't have to touch
# every entry. Anything not listed defaults to risk=low, implies=[].
# ======================================================================
# Risk levels: "critical" (destructive, money, access), "high" (sensitive), "medium" (everyday writes)
PERMISSION_RISK: Dict[str, str] = {
    # Destructive
    "delete_bookings": "critical", "cancel_bookings": "high",
    "delete_users": "critical", "delete_roles": "critical", "delete_branches": "critical",
    "delete_rooms": "high", "delete_rate_plans": "high", "delete_taxes": "critical",
    "delete_housekeeping_tasks": "medium", "delete_maintenance": "medium",
    "delete_shifts": "medium", "delete_group_blocks": "medium",
    "delete_webhooks": "high", "delete_secrets": "critical",
    "delete_payroll_runs": "critical", "delete_payroll_adjustments": "high",
    "delete_cash_advances": "high", "delete_exports": "medium",
    "delete_document_types": "medium", "delete_charge_types": "medium",
    "delete_booking_sources": "medium", "delete_cancellation_policies": "high",
    "delete_channel_connections": "critical", "delete_channel_mappings": "high",
    "delete_experiments": "medium", "delete_playbooks": "medium",
    "delete_normalization_rules": "medium", "delete_parity_observations": "medium",
    "delete_action_items": "medium", "delete_cost_models": "high",
    "delete_user_contracts": "high", "delete_booking_documents": "high",
    "delete_revenue_segments": "medium", "delete_adjustment_categories": "medium",
    # Money / approval
    "approve_payroll_runs": "critical", "mark_commissions_paid": "critical",
    "process_refunds": "critical", "submit_commission_payables": "high",
    "manage_expenses": "high", "run_recurring_expenses": "high",
    "generate_laundry_contract_expenses": "high",
    "create_payroll_runs": "high", "edit_payroll_runs": "high",
    # Sensitive state transitions
    "promote_experiment_winners": "high", "start_experiments": "medium",
    "run_playbooks": "high", "apply_action_items": "high",
    "trigger_rate_sync": "high", "trigger_inventory_sync": "medium",
    "rebuild_inventory": "high", "bulk_update_rate_calendar": "high",
    "manage_overbooking_policies": "high", "run_overbooking_simulations": "medium",
    # Data exfiltration
    "export_audit_logs": "high", "export_profit_data": "high",
    "download_exports": "high", "create_exports": "medium",
    # Secrets / security
    "view_secrets": "critical", "create_secrets": "critical",
    "edit_secrets": "critical", "edit_retention_policies": "high",
    # Admin-only meta
    "create_users": "high", "edit_users": "high",
    "create_roles": "critical", "edit_roles": "critical",
    "manage_property_compliance_categories": "high",
    "verify_maintenance": "medium", "audit_housekeeping_tasks": "medium",
    "finalize_laundry_audits": "medium",
}

# Dependencies — if you grant X, you almost certainly need Y too
# (UI will warn; doesn't block)
PERMISSION_IMPLIES: Dict[str, List[str]] = {
    # Create/Edit/Delete imply View
    "edit_bookings": ["view_bookings", "bookings_view"],
    "create_bookings": ["view_bookings", "bookings_view"],
    "delete_bookings": ["view_bookings", "bookings_view"],
    "confirm_bookings": ["view_bookings"],
    "checkin_bookings": ["view_bookings"],
    "checkout_bookings": ["view_bookings"],
    "cancel_bookings": ["view_bookings"],
    "assign_rooms": ["view_bookings"],
    "process_refunds": ["view_refunds", "view_bookings"],
    "edit_rate_calendar": ["view_rate_calendar", "rates_calendar_view"],
    "bulk_update_rate_calendar": ["edit_rate_calendar", "view_rate_calendar"],
    "rebuild_inventory": ["view_inventory"],
    "edit_inventory": ["view_inventory"],
    "create_rate_plans": ["view_rate_plans", "settings_rate_plans_view"],
    "edit_rate_plans": ["view_rate_plans"],
    "delete_rate_plans": ["view_rate_plans"],
    "create_group_blocks": ["view_group_blocks", "bookings_groups_view"],
    "edit_group_blocks": ["view_group_blocks"],
    "delete_group_blocks": ["view_group_blocks"],
    "assign_housekeeping_tasks": ["view_housekeeping_tasks", "housekeeping_view"],
    "approve_housekeeping_tasks": ["view_housekeeping_tasks"],
    "audit_housekeeping_tasks": ["view_housekeeping_tasks"],
    "start_maintenance": ["view_maintenance", "maintenance_view"],
    "complete_maintenance": ["view_maintenance", "start_maintenance"],
    "verify_maintenance": ["view_maintenance", "complete_maintenance"],
    "approve_payroll_runs": ["view_payroll_runs", "finance_payroll_runs_view"],
    "edit_payroll_runs": ["view_payroll_runs"],
    "mark_commissions_paid": ["view_commissions", "reports_commission_view"],
    "submit_commission_payables": ["view_commissions", "create_commission_payables"],
    "run_recurring_expenses": ["view_recurring_expenses", "finance_recurring_expenses_view"],
    "manage_expenses": ["view_expenses", "finance_expenses_view"],
    "manage_own_expenses": ["view_expenses"],
    "start_experiments": ["view_experiments", "revenue_experiments_view"],
    "pause_experiments": ["view_experiments", "start_experiments"],
    "promote_experiment_winners": ["view_experiments", "start_experiments"],
    "run_playbooks": ["view_playbooks", "revenue_playbooks_view"],
    "apply_action_items": ["view_action_items", "revenue_action_center_view"],
    "dismiss_action_items": ["view_action_items"],
    "acknowledge_benchmark_alerts": ["view_benchmark", "channel_manager_benchmark_view"],
    "acknowledge_parity_violations": ["view_parity", "revenue_parity_view"],
    "detect_parity_violations": ["view_parity"],
    "export_audit_logs": ["view_audit_logs", "channel_manager_audit_logs_view"],
    "export_profit_data": ["view_profit_reports", "revenue_profit_os_view"],
    "download_exports": ["view_exports", "settings_exports_view"],
    "create_channel_mappings": ["view_channel_mappings", "channel_manager_mapping_view"],
    "test_channel_connections": ["view_channel_connections"],
    "trigger_inventory_sync": ["view_sync_status", "channel_manager_sync_view"],
    "trigger_rate_sync": ["view_sync_status"],
    "resolve_sync_errors": ["view_sync_status"],
    "generate_laundry_contract_expenses": ["view_laundry_contracts", "laundry_contracts_view"],
    "manage_laundry_contracts": ["view_laundry_contracts"],
    "manage_laundry_stock": ["view_laundry_stock"],
    "finalize_laundry_audits": ["view_laundry_audits", "create_laundry_audits"],
    "verify_laundry_daily_usage": ["view_laundry_daily_usage"],
    "verify_laundry_orders": ["view_laundry_orders"],
    "verify_laundry_deliveries": ["view_laundry_deliveries"],
    "verify_laundry_dispatch": ["view_laundry_dispatch"],
    "manage_property_compliance": ["view_property_compliance", "operations_compliance_view"],
    "manage_property_compliance_categories": ["manage_property_compliance"],
    "manage_room_categories": ["view_room_categories"],
    "manage_laundry_items": ["view_laundry_items"],
    "manage_laundry_providers": ["view_laundry_providers"],
    "manage_expense_categories": ["view_expense_categories"],
    "manage_benchmark_alert_rules": ["view_benchmark"],
    "manage_overbooking_policies": ["view_overbooking"],
    "import_parity_observations": ["create_parity_observations", "view_parity_observations"],
    "edit_normalization_rules": ["view_normalization_rules"],
    "delete_normalization_rules": ["view_normalization_rules"],
    "edit_roles": ["view_roles", "settings_roles_view"],
    "create_roles": ["view_roles"],
    "delete_roles": ["view_roles"],
    "edit_users": ["view_users"],
    "create_users": ["view_users"],
    "delete_users": ["view_users"],
}


def get_risk(key: str) -> str:
    return PERMISSION_RISK.get(key, "low")


def get_implies(key: str) -> List[str]:
    return PERMISSION_IMPLIES.get(key, [])


def enrich_catalog() -> List[Dict]:
    """Return a deep-copy of PERMISSION_CATALOG with risk + implies fields merged in."""
    out = []
    for cat in PERMISSION_CATALOG:
        new_cat = {**cat, "sub_groups": []}
        for sg in cat["sub_groups"]:
            new_sg = {**sg, "permissions": []}
            for p in sg["permissions"]:
                new_sg["permissions"].append({
                    **p,
                    "risk": get_risk(p["key"]),
                    "implies": get_implies(p["key"]),
                })
            new_cat["sub_groups"].append(new_sg)
        out.append(new_cat)
    return out



PERMISSION_CATALOG: List[Dict] = [
    # ---------- DASHBOARD ----------
    {"key": "dashboard", "label": "Dashboard", "icon": "home", "sub_groups": [
        {"key": "dashboard.main", "label": "Main", "permissions": [
            _p("dashboard_view", "Dashboard View", menu=True),
            _p("dashboard_edit", "Dashboard Edit"),
        ]},
    ]},

    # ---------- MY TASKS ----------
    {"key": "my_tasks", "label": "My Tasks", "icon": "check-square", "sub_groups": [
        {"key": "my_tasks.main", "label": "Main", "permissions": [
            _p("tasks_my_view", "Tasks My View", menu=True),
        ]},
    ]},

    # ---------- CALENDAR ----------
    {"key": "calendar", "label": "Calendar", "icon": "calendar", "sub_groups": [
        {"key": "calendar.main", "label": "Main", "permissions": [
            _p("bookings_calendar_view", "Bookings Calendar View", menu=True),
        ]},
    ]},

    # ---------- BOOKINGS (42) ----------
    {"key": "bookings", "label": "Bookings", "icon": "calendar", "sub_groups": [
        {"key": "bookings.all", "label": "All Bookings", "permissions": [
            _p("bookings_view", "Bookings View", menu=True),
            _p("bookings_create", "Bookings Create"),
            _p("view_bookings", "View Bookings"),
            _p("create_bookings", "Create Bookings"),
            _p("edit_bookings", "Edit Bookings"),
            _p("delete_bookings", "Delete Bookings"),
            _p("confirm_bookings", "Confirm Bookings"),
            _p("checkin_bookings", "Check In Bookings"),
            _p("checkout_bookings", "Check Out Bookings"),
            _p("cancel_bookings", "Cancel Bookings"),
            _p("assign_rooms", "Assign Rooms"),
            _p("view_booking_documents", "View Booking Documents"),
            _p("upload_booking_documents", "Upload Booking Documents"),
            _p("delete_booking_documents", "Delete Booking Documents"),
            _p("view_document_types", "View Document Types"),
            _p("create_document_types", "Create Document Types"),
            _p("edit_document_types", "Edit Document Types"),
            _p("delete_document_types", "Delete Document Types"),
            _p("view_charge_types", "View Charge Types"),
            _p("create_charge_types", "Create Charge Types"),
            _p("edit_charge_types", "Edit Charge Types"),
            _p("delete_charge_types", "Delete Charge Types"),
            _p("view_refunds", "View Refunds"),
            _p("process_refunds", "Process Refunds"),
        ]},
        {"key": "bookings.rate_calendar", "label": "Rate Calendar", "permissions": [
            _p("rates_calendar_view", "Rates Calendar View", menu=True),
            _p("view_rate_calendar", "View Rate Calendar"),
            _p("edit_rate_calendar", "Edit Rate Calendar"),
            _p("bulk_update_rate_calendar", "Bulk Update Rate Calendar"),
            _p("view_inventory", "View Inventory"),
            _p("edit_inventory", "Edit Inventory"),
            _p("manage_stop_sell", "Manage Stop Sell"),
            _p("rebuild_inventory", "Rebuild Inventory"),
        ]},
        {"key": "bookings.rate_plans", "label": "Rate Plans", "permissions": [
            _p("settings_rate_plans_view", "Settings Rate Plans View", menu=True),
            _p("view_rate_plans", "View Rate Plans"),
            _p("create_rate_plans", "Create Rate Plans"),
            _p("edit_rate_plans", "Edit Rate Plans"),
            _p("delete_rate_plans", "Delete Rate Plans"),
        ]},
        {"key": "bookings.group_blocks", "label": "Group Blocks", "permissions": [
            _p("bookings_groups_view", "Bookings Groups View", menu=True),
            _p("view_group_blocks", "View Group Blocks"),
            _p("create_group_blocks", "Create Group Blocks"),
            _p("edit_group_blocks", "Edit Group Blocks"),
            _p("delete_group_blocks", "Delete Group Blocks"),
        ]},
    ]},

    # ---------- REPORTS (9) ----------
    {"key": "reports", "label": "Reports", "icon": "chart-line", "sub_groups": [
        {"key": "reports.overview", "label": "Overview", "permissions": [
            _p("reports_overview_view", "Reports Overview View", menu=True),
        ]},
        {"key": "reports.revenue", "label": "Revenue", "permissions": [
            _p("reports_revenue_view", "Reports Revenue View", menu=True),
        ]},
        {"key": "reports.occupancy", "label": "Occupancy", "permissions": [
            _p("reports_occupancy_view", "Reports Occupancy View", menu=True),
        ]},
        {"key": "reports.commission", "label": "Commission", "permissions": [
            _p("reports_commission_view", "Reports Commission View", menu=True),
            _p("view_commissions", "View Commissions"),
            _p("create_commission_payables", "Create Commission Payables"),
            _p("edit_commission_payables", "Edit Commission Payables"),
            _p("submit_commission_payables", "Submit Commission Payables"),
            _p("mark_commissions_paid", "Mark Commissions Paid"),
        ]},
    ]},

    # ---------- OPERATIONS (54) ----------
    {"key": "operations", "label": "Operations", "icon": "gear", "sub_groups": [
        {"key": "operations.housekeeping", "label": "Housekeeping", "permissions": [
            _p("housekeeping_view", "Housekeeping View", menu=True),
            _p("view_housekeeping_tasks", "View Housekeeping Tasks"),
            _p("create_housekeeping_tasks", "Create Housekeeping Tasks"),
            _p("edit_housekeeping_tasks", "Edit Housekeeping Tasks"),
            _p("delete_housekeeping_tasks", "Delete Housekeeping Tasks"),
            _p("assign_housekeeping_tasks", "Assign Housekeeping Tasks"),
            _p("approve_housekeeping_tasks", "Approve Housekeeping Tasks"),
            _p("audit_housekeeping_tasks", "Audit Housekeeping Tasks"),
            _p("view_housekeeping_inventory", "View Housekeeping Inventory"),
            _p("create_housekeeping_inventory", "Create Housekeeping Inventory"),
            _p("verify_housekeeping_inventory", "Verify Housekeeping Inventory"),
        ]},
        {"key": "operations.routine_templates", "label": "Routine Templates", "permissions": [
            _p("reception_routines_templates_view", "Reception Routines Templates View", menu=True),
        ]},
        {"key": "operations.routine_history", "label": "Routine History", "permissions": [
            _p("reception_routines_history_view", "Reception Routines History View", menu=True),
        ]},
        {"key": "operations.reception", "label": "Reception", "permissions": [
            _p("operations_reception_view", "Operations Reception View", menu=True),
            _p("view_reception_reports", "View Reception Reports"),
        ]},
        {"key": "operations.pass_over_duties", "label": "Pass Over Duties", "permissions": [
            _p("operations_notes_view", "Operations Notes View", menu=True),
        ]},
        {"key": "operations.compliance", "label": "Compliance · Register", "permissions": [
            _p("operations_compliance_view", "Operations Compliance View", menu=True),
            _p("view_property_compliance", "View Property Compliance"),
            _p("manage_property_compliance", "Manage Property Compliance"),
        ]},
        {"key": "operations.compliance_categories", "label": "Compliance · Categories", "permissions": [
            _p("manage_property_compliance_categories", "Manage Property Compliance Categories", menu=True),
        ]},
        {"key": "operations.laundry", "label": "Laundry", "permissions": [
            _p("laundry_reports_view", "Laundry Reports View", menu=True),
            _p("view_laundry_daily_usage", "View Laundry Daily Usage"),
            _p("create_laundry_daily_usage", "Create Laundry Daily Usage"),
            _p("verify_laundry_daily_usage", "Verify Laundry Daily Usage"),
            _p("view_laundry_orders", "View Laundry Orders"),
            _p("create_laundry_orders", "Create Laundry Orders"),
            _p("verify_laundry_orders", "Verify Laundry Orders"),
            _p("view_laundry_deliveries", "View Laundry Deliveries"),
            _p("create_laundry_deliveries", "Create Laundry Deliveries"),
            _p("verify_laundry_deliveries", "Verify Laundry Deliveries"),
            _p("view_laundry_dispatch", "View Laundry Dispatch"),
            _p("create_laundry_dispatch", "Create Laundry Dispatch"),
            _p("verify_laundry_dispatch", "Verify Laundry Dispatch"),
            _p("view_laundry_audits", "View Laundry Audits"),
            _p("create_laundry_audits", "Create Laundry Audits"),
            _p("finalize_laundry_audits", "Finalize Laundry Audits"),
            _p("view_laundry_stock", "View Laundry Stock"),
            _p("manage_laundry_stock", "Manage Laundry Stock"),
            _p("view_laundry_stock_transactions", "View Laundry Stock Transactions"),
            _p("create_laundry_stock_transactions", "Create Laundry Stock Transactions"),
        ]},
        {"key": "operations.shifts", "label": "Shifts", "permissions": [
            _p("operations_shifts_view", "Operations Shifts View", menu=True),
            _p("view_shifts", "View Shifts"),
            _p("create_shifts", "Create Shifts"),
            _p("edit_shifts", "Edit Shifts"),
            _p("delete_shifts", "Delete Shifts"),
        ]},
        {"key": "operations.maintenance", "label": "Maintenance", "permissions": [
            _p("maintenance_view", "Maintenance View", menu=True),
            _p("view_maintenance", "View Maintenance"),
            _p("create_maintenance", "Create Maintenance"),
            _p("edit_maintenance", "Edit Maintenance"),
            _p("delete_maintenance", "Delete Maintenance"),
            _p("start_maintenance", "Start Maintenance"),
            _p("complete_maintenance", "Complete Maintenance"),
            _p("verify_maintenance", "Verify Maintenance"),
            _p("comment_maintenance", "Comment Maintenance"),
        ]},
    ]},

    # ---------- FINANCE (30) ----------
    {"key": "finance", "label": "Finance", "icon": "dollar", "sub_groups": [
        {"key": "finance.dashboard", "label": "Dashboard", "permissions": [
            _p("finance_dashboard_view", "Finance Dashboard View", menu=True),
        ]},
        {"key": "finance.payroll_runs", "label": "Payroll Runs", "permissions": [
            _p("finance_payroll_runs_view", "Finance Payroll Runs View", menu=True),
            _p("view_payroll_runs", "View Payroll Runs"),
            _p("create_payroll_runs", "Create Payroll Runs"),
            _p("edit_payroll_runs", "Edit Payroll Runs"),
            _p("delete_payroll_runs", "Delete Payroll Runs"),
            _p("approve_payroll_runs", "Approve Payroll Runs"),
        ]},
        {"key": "finance.adjustments", "label": "Adjustments", "permissions": [
            _p("finance_payroll_adjustments_view", "Finance Payroll Adjustments View", menu=True),
            _p("view_payroll_adjustments", "View Payroll Adjustments"),
            _p("create_payroll_adjustments", "Create Payroll Adjustments"),
            _p("edit_payroll_adjustments", "Edit Payroll Adjustments"),
            _p("delete_payroll_adjustments", "Delete Payroll Adjustments"),
        ]},
        {"key": "finance.cash_advances", "label": "Cash Advances", "permissions": [
            _p("finance_payroll_cash_advances_view", "Finance Payroll Cash Advances View", menu=True),
            _p("view_cash_advances", "View Cash Advances"),
            _p("create_cash_advances", "Create Cash Advances"),
            _p("edit_cash_advances", "Edit Cash Advances"),
            _p("delete_cash_advances", "Delete Cash Advances"),
        ]},
        {"key": "finance.adjustment_categories", "label": "Adjustment Categories", "permissions": [
            _p("finance_payroll_adjustment_categories_view", "Finance Payroll Adjustment Categories View", menu=True),
            _p("view_adjustment_categories", "View Adjustment Categories"),
            _p("create_adjustment_categories", "Create Adjustment Categories"),
            _p("edit_adjustment_categories", "Edit Adjustment Categories"),
            _p("delete_adjustment_categories", "Delete Adjustment Categories"),
        ]},
        {"key": "finance.expenses", "label": "Expenses", "permissions": [
            _p("finance_expenses_view", "Finance Expenses View", menu=True),
            _p("view_expenses", "View Expenses"),
            _p("manage_expenses", "Manage Expenses"),
            _p("manage_own_expenses", "Manage Own Expenses"),
        ]},
        {"key": "finance.recurring_expenses", "label": "Recurring Expenses", "permissions": [
            _p("finance_recurring_expenses_view", "Finance Recurring Expenses View", menu=True),
            _p("view_recurring_expenses", "View Recurring Expenses"),
            _p("manage_recurring_expenses", "Manage Recurring Expenses"),
            _p("run_recurring_expenses", "Run Recurring Expenses"),
        ]},
    ]},

    # ---------- CHANNEL MANAGER (41) ----------
    {"key": "channel_manager", "label": "Channel Manager", "icon": "copy", "sub_groups": [
        {"key": "cm.publish_jobs", "label": "Publish Jobs", "permissions": [
            _p("channel_manager_publish_jobs_view", "Channel Manager Publish Jobs View", menu=True),
            _p("view_publish_jobs", "View Publish Jobs"),
            _p("create_publish_jobs", "Create Publish Jobs"),
            _p("cancel_publish_jobs", "Cancel Publish Jobs"),
        ]},
        {"key": "cm.audit_logs", "label": "Audit Logs", "permissions": [
            _p("channel_manager_audit_logs_view", "Channel Manager Audit Logs View", menu=True),
            _p("view_audit_logs", "View Audit Logs"),
            _p("export_audit_logs", "Export Audit Logs"),
            _p("view_retention_policies", "View Retention Policies"),
            _p("edit_retention_policies", "Edit Retention Policies"),
        ]},
        {"key": "cm.benchmark", "label": "Benchmark Cockpit", "permissions": [
            _p("channel_manager_benchmark_view", "Channel Manager Benchmark View", menu=True),
            _p("view_benchmark", "View Benchmark"),
            _p("create_benchmark_snapshots", "Create Benchmark Snapshots"),
            _p("manage_benchmark_alert_rules", "Manage Benchmark Alert Rules"),
            _p("acknowledge_benchmark_alerts", "Acknowledge Benchmark Alerts"),
        ]},
        {"key": "cm.profiles", "label": "Profiles", "permissions": [
            _p("channel_manager_profiles_view", "Channel Manager Profiles View", menu=True),
        ]},
        # Additional CM perms (Connections, Inventory Sync, Rate Push, Mapping)
        {"key": "cm.connections", "label": "Connections", "permissions": [
            _p("channel_manager_connections_view", "Channel Manager Connections View", menu=True),
            _p("view_channel_connections", "View Channel Connections"),
            _p("create_channel_connections", "Create Channel Connections"),
            _p("edit_channel_connections", "Edit Channel Connections"),
            _p("delete_channel_connections", "Delete Channel Connections"),
            _p("test_channel_connections", "Test Channel Connections"),
        ]},
        {"key": "cm.inventory_sync", "label": "Inventory Sync", "permissions": [
            _p("channel_manager_sync_view", "Channel Manager Sync View", menu=True),
            _p("view_sync_status", "View Sync Status"),
            _p("trigger_inventory_sync", "Trigger Inventory Sync"),
            _p("trigger_rate_sync", "Trigger Rate Sync"),
            _p("resolve_sync_errors", "Resolve Sync Errors"),
        ]},
        {"key": "cm.mapping", "label": "Room/Rate Mapping", "permissions": [
            _p("channel_manager_mapping_view", "Channel Manager Mapping View", menu=True),
            _p("view_channel_mappings", "View Channel Mappings"),
            _p("create_channel_mappings", "Create Channel Mappings"),
            _p("edit_channel_mappings", "Edit Channel Mappings"),
            _p("delete_channel_mappings", "Delete Channel Mappings"),
        ]},
    ]},

    # ---------- REVENUE (61) ----------
    {"key": "revenue", "label": "Revenue", "icon": "trending-up", "sub_groups": [
        {"key": "revenue.dashboard", "label": "Dashboard", "permissions": [
            _p("revenue_dashboard_view", "Revenue Dashboard View", menu=True),
        ]},
        {"key": "revenue.setup_wizard", "label": "Setup Wizard", "permissions": [
            _p("revenue_wizard_view", "Revenue Wizard View", menu=True),
        ]},
        {"key": "revenue.approvals", "label": "Approvals", "permissions": [
            _p("revenue_approvals_view", "Revenue Approvals View", menu=True),
        ]},
        {"key": "revenue.segments", "label": "Segments", "permissions": [
            _p("revenue_segments_view", "Revenue Segments View", menu=True),
            _p("view_revenue_segments", "View Revenue Segments"),
            _p("create_revenue_segments", "Create Revenue Segments"),
            _p("edit_revenue_segments", "Edit Revenue Segments"),
            _p("delete_revenue_segments", "Delete Revenue Segments"),
        ]},
        {"key": "revenue.rate_resolver", "label": "Rate Resolver", "permissions": [
            _p("revenue_rate_resolver_view", "Revenue Rate Resolver View", menu=True),
        ]},
        {"key": "revenue.smart_pricing", "label": "Smart Pricing", "permissions": [
            _p("revenue_smart_pricing_view", "Revenue Smart Pricing View", menu=True),
        ]},
        {"key": "revenue.forecasting", "label": "Forecasting", "permissions": [
            _p("revenue_forecasting_view", "Revenue Forecasting View", menu=True),
        ]},
        {"key": "revenue.analytics_perf", "label": "Analytics · Performance", "permissions": [
            _p("revenue_analytics_performance_view", "Revenue Analytics Performance View", menu=True),
        ]},
        {"key": "revenue.analytics_pickup", "label": "Analytics · Pickup Report", "permissions": [
            _p("revenue_analytics_pickup_view", "Revenue Analytics Pickup View", menu=True),
        ]},
        {"key": "revenue.analytics_budget", "label": "Analytics · Budget Variance", "permissions": [
            _p("revenue_analytics_budget_variance_view", "Revenue Analytics Budget Variance View", menu=True),
        ]},
        {"key": "revenue.parity", "label": "Parity", "permissions": [
            _p("revenue_parity_view", "Revenue Parity View", menu=True),
            _p("view_parity", "View Parity"),
            _p("detect_parity_violations", "Detect Parity Violations"),
            _p("create_parity_overrides", "Create Parity Overrides"),
            _p("acknowledge_parity_violations", "Acknowledge Parity Violations"),
            _p("view_parity_observations", "View Parity Observations"),
            _p("create_parity_observations", "Create Parity Observations"),
            _p("import_parity_observations", "Import Parity Observations"),
            _p("delete_parity_observations", "Delete Parity Observations"),
            _p("view_normalization_rules", "View Normalization Rules"),
            _p("create_normalization_rules", "Create Normalization Rules"),
            _p("edit_normalization_rules", "Edit Normalization Rules"),
            _p("delete_normalization_rules", "Delete Normalization Rules"),
        ]},
        {"key": "revenue.overbooking", "label": "Overbooking", "permissions": [
            _p("revenue_overbooking_view", "Revenue Overbooking View", menu=True),
            _p("view_overbooking", "View Overbooking"),
            _p("manage_overbooking_policies", "Manage Overbooking Policies"),
            _p("run_overbooking_simulations", "Run Overbooking Simulations"),
        ]},
        {"key": "revenue.experiments", "label": "Experiments", "permissions": [
            _p("revenue_experiments_view", "Revenue Experiments View", menu=True),
            _p("view_experiments", "View Experiments"),
            _p("create_experiments", "Create Experiments"),
            _p("edit_experiments", "Edit Experiments"),
            _p("delete_experiments", "Delete Experiments"),
            _p("start_experiments", "Start Experiments"),
            _p("pause_experiments", "Pause Experiments"),
            _p("promote_experiment_winners", "Promote Experiment Winners"),
        ]},
        {"key": "revenue.playbooks", "label": "Playbooks", "permissions": [
            _p("revenue_playbooks_view", "Revenue Playbooks View", menu=True),
            _p("view_playbooks", "View Playbooks"),
            _p("create_playbooks", "Create Playbooks"),
            _p("edit_playbooks", "Edit Playbooks"),
            _p("delete_playbooks", "Delete Playbooks"),
            _p("run_playbooks", "Run Playbooks"),
        ]},
        {"key": "revenue.action_center", "label": "Action Center", "permissions": [
            _p("revenue_action_center_view", "Revenue Action Center View", menu=True),
            _p("view_action_items", "View Action Items"),
            _p("create_action_items", "Create Action Items"),
            _p("edit_action_items", "Edit Action Items"),
            _p("delete_action_items", "Delete Action Items"),
            _p("apply_action_items", "Apply Action Items"),
            _p("dismiss_action_items", "Dismiss Action Items"),
        ]},
        {"key": "revenue.profit_os", "label": "Profit OS", "permissions": [
            _p("revenue_profit_os_view", "Revenue Profit OS View", menu=True),
            _p("view_cost_models", "View Cost Models"),
            _p("create_cost_models", "Create Cost Models"),
            _p("edit_cost_models", "Edit Cost Models"),
            _p("delete_cost_models", "Delete Cost Models"),
            _p("view_contribution_decisions", "View Contribution Decisions"),
            _p("view_profit_reports", "View Profit Reports"),
            _p("export_profit_data", "Export Profit Data"),
        ]},
        {"key": "revenue.distribution", "label": "Distribution", "permissions": [
            _p("revenue_distribution_view", "Revenue Distribution View", menu=True),
        ]},
    ]},

    # ---------- SETTINGS (65) ----------
    {"key": "settings", "label": "Settings", "icon": "gear", "sub_groups": [
        {"key": "settings.users", "label": "Users", "permissions": [
            _p("settings_users_view", "Settings Users View", menu=True),
            _p("view_users", "View Users"),
            _p("create_users", "Create Users"),
            _p("edit_users", "Edit Users"),
            _p("delete_users", "Delete Users"),
        ]},
        {"key": "settings.roles", "label": "Roles & Permissions", "permissions": [
            _p("settings_roles_view", "Settings Roles View", menu=True),
            _p("view_roles", "View Roles"),
            _p("create_roles", "Create Roles"),
            _p("edit_roles", "Edit Roles"),
            _p("delete_roles", "Delete Roles"),
        ]},
        {"key": "settings.user_contracts", "label": "User Contracts", "permissions": [
            _p("settings_user_contracts_view", "Settings User Contracts View", menu=True),
            _p("view_user_contracts", "View User Contracts"),
            _p("create_user_contracts", "Create User Contracts"),
            _p("edit_user_contracts", "Edit User Contracts"),
            _p("delete_user_contracts", "Delete User Contracts"),
        ]},
        {"key": "settings.branches", "label": "Branches", "permissions": [
            _p("settings_branches_view", "Settings Branches View", menu=True),
            _p("view_branches", "View Branches"),
            _p("create_branches", "Create Branches"),
            _p("edit_branches", "Edit Branches"),
            _p("delete_branches", "Delete Branches"),
        ]},
        {"key": "settings.currencies", "label": "Currencies", "permissions": [
            _p("settings_currencies_view", "Settings Currencies View", menu=True),
            _p("view_currencies", "View Currencies"),
            _p("create_currencies", "Create Currencies"),
            _p("edit_currencies", "Edit Currencies"),
            _p("delete_currencies", "Delete Currencies"),
        ]},
        {"key": "settings.room_categories", "label": "Room Categories", "permissions": [
            _p("rooms_categories_view", "Rooms Categories View", menu=True),
            _p("view_room_categories", "View Room Categories"),
            _p("manage_room_categories", "Manage Room Categories"),
        ]},
        {"key": "settings.rooms", "label": "Rooms", "permissions": [
            _p("rooms_view", "Rooms View", menu=True),
            _p("view_rooms", "View Rooms"),
            _p("create_rooms", "Create Rooms"),
            _p("edit_rooms", "Edit Rooms"),
            _p("delete_rooms", "Delete Rooms"),
        ]},
        {"key": "settings.laundry_providers", "label": "Laundry Providers", "permissions": [
            _p("laundry_providers_view", "Laundry Providers View", menu=True),
            _p("view_laundry_providers", "View Laundry Providers"),
            _p("manage_laundry_providers", "Manage Laundry Providers"),
        ]},
        {"key": "settings.laundry_contracts", "label": "Laundry Contracts", "permissions": [
            _p("laundry_contracts_view", "Laundry Contracts View", menu=True),
            _p("view_laundry_contracts", "View Laundry Contracts"),
            _p("manage_laundry_contracts", "Manage Laundry Contracts"),
            _p("generate_laundry_contract_expenses", "Generate Laundry Contract Expenses"),
        ]},
        {"key": "settings.booking_sources", "label": "Booking Sources", "permissions": [
            _p("settings_booking_sources_view", "Settings Booking Sources View", menu=True),
            _p("view_booking_sources", "View Booking Sources"),
            _p("create_booking_sources", "Create Booking Sources"),
            _p("edit_booking_sources", "Edit Booking Sources"),
            _p("delete_booking_sources", "Delete Booking Sources"),
        ]},
        {"key": "settings.expense_categories", "label": "Expense Categories", "permissions": [
            _p("settings_expense_categories_view", "Settings Expense Categories View", menu=True),
            _p("view_expense_categories", "View Expense Categories"),
            _p("manage_expense_categories", "Manage Expense Categories"),
        ]},
        {"key": "settings.laundry_items", "label": "Laundry Items", "permissions": [
            _p("settings_laundry_items_view", "Settings Laundry Items View", menu=True),
            _p("view_laundry_items", "View Laundry Items"),
            _p("manage_laundry_items", "Manage Laundry Items"),
        ]},
        {"key": "settings.cancellation_policies", "label": "Cancellation Policies", "permissions": [
            _p("settings_cancellation_policies_view", "Settings Cancellation Policies View", menu=True),
            _p("view_cancellation_policies", "View Cancellation Policies"),
            _p("create_cancellation_policies", "Create Cancellation Policies"),
            _p("edit_cancellation_policies", "Edit Cancellation Policies"),
            _p("delete_cancellation_policies", "Delete Cancellation Policies"),
        ]},
        {"key": "settings.taxes", "label": "Taxes", "permissions": [
            _p("settings_taxes_view", "Settings Taxes View", menu=True),
            _p("view_taxes", "View Taxes"),
            _p("create_taxes", "Create Taxes"),
            _p("edit_taxes", "Edit Taxes"),
            _p("delete_taxes", "Delete Taxes"),
        ]},
        {"key": "settings.data_exports", "label": "Data Exports", "permissions": [
            _p("settings_exports_view", "Settings Exports View", menu=True),
            _p("view_exports", "View Exports"),
            _p("create_exports", "Create Exports"),
            _p("download_exports", "Download Exports"),
        ]},
        {"key": "settings.import_module", "label": "Import Module", "permissions": [
            _p("settings_import_module_view", "Settings Import Module View", menu=True, missing=True),
            _p("view_import_module", "View Import Module", missing=True),
            _p("fetch_import_module_branches", "Fetch Import Module Branches", missing=True),
            _p("store_import_module_mapping", "Store Import Module Mapping", missing=True),
        ]},
    ]},

    # ---------- SYSTEM FEEDBACK & BUGS (1) ----------
    {"key": "system_feedback", "label": "System Feedback & Bugs", "icon": "bug", "sub_groups": [
        {"key": "sfb.main", "label": "Main", "permissions": [
            _p("system_feedback_view", "System Feedback View", menu=True),
        ]},
    ]},

    # ---------- HELP (1) ----------
    {"key": "help", "label": "Help", "icon": "help-circle", "sub_groups": [
        {"key": "help.main", "label": "Main", "permissions": [
            _p("help_view", "Help View", menu=True),
        ]},
    ]},

    # ---------- WEBHOOKS (5) ----------
    {"key": "webhooks", "label": "Webhooks", "icon": "code", "sub_groups": [
        {"key": "webhooks.main", "label": "Main", "permissions": [
            _p("webhooks_view", "Webhooks View", menu=True),
            _p("view_webhooks", "View Webhooks"),
            _p("create_webhooks", "Create Webhooks"),
            _p("edit_webhooks", "Edit Webhooks"),
            _p("delete_webhooks", "Delete Webhooks"),
        ]},
    ]},

    # ---------- SECRETS (4) ----------
    {"key": "secrets", "label": "Secrets", "icon": "key", "sub_groups": [
        {"key": "secrets.main", "label": "Main", "permissions": [
            _p("view_secrets", "View Secrets"),
            _p("create_secrets", "Create Secrets"),
            _p("edit_secrets", "Edit Secrets"),
            _p("delete_secrets", "Delete Secrets"),
        ]},
    ]},

    # ---------- UNCATEGORIZED ----------
    {"key": "uncategorized", "label": "Uncategorized", "icon": "help-circle", "sub_groups": [
        {"key": "uncat.main", "label": "Main", "permissions": [
            _p("system_view", "System View"),
            _p("system_admin", "System Admin"),
        ]},
    ]},
]


# Role templates (quick-start tiles)
ROLE_TEMPLATES: List[Dict] = [
    {
        "key": "receptionist",
        "label": "Receptionist",
        "description": "Front desk & bookings",
        "emoji": "🛎️",
        "color": "#fef3c7",
        "permissions": [
            "dashboard_view", "tasks_my_view", "bookings_calendar_view",
            "bookings_view", "view_bookings", "create_bookings", "edit_bookings",
            "confirm_bookings", "checkin_bookings", "checkout_bookings", "cancel_bookings",
            "assign_rooms", "view_booking_documents", "upload_booking_documents",
            "rates_calendar_view", "view_rate_calendar",
            "operations_reception_view", "view_reception_reports",
            "operations_notes_view",
        ],
    },
    {
        "key": "housekeeper",
        "label": "Housekeeper",
        "description": "Cleaning tasks",
        "emoji": "🧹",
        "color": "#d1fae5",
        "permissions": [
            "dashboard_view", "tasks_my_view",
            "housekeeping_view", "view_housekeeping_tasks", "edit_housekeeping_tasks",
            "view_housekeeping_inventory",
        ],
    },
    {
        "key": "manager",
        "label": "Manager",
        "description": "Full management access",
        "emoji": "👔",
        "color": "#ede9fe",
        "permissions": "__ALL__",
    },
    {
        "key": "accountant",
        "label": "Accountant",
        "description": "Financial operations",
        "emoji": "💰",
        "color": "#fef08a",
        "permissions": [
            "dashboard_view",
            "reports_overview_view", "reports_revenue_view", "reports_occupancy_view",
            "reports_commission_view", "view_commissions", "create_commission_payables",
            "edit_commission_payables", "submit_commission_payables", "mark_commissions_paid",
            "finance_dashboard_view",
            "finance_payroll_runs_view", "view_payroll_runs", "create_payroll_runs", "edit_payroll_runs", "approve_payroll_runs",
            "finance_payroll_adjustments_view", "view_payroll_adjustments", "create_payroll_adjustments", "edit_payroll_adjustments",
            "finance_payroll_cash_advances_view", "view_cash_advances", "create_cash_advances", "edit_cash_advances",
            "finance_expenses_view", "view_expenses", "manage_expenses",
            "finance_recurring_expenses_view", "view_recurring_expenses", "manage_recurring_expenses", "run_recurring_expenses",
            "settings_taxes_view", "view_taxes", "create_taxes", "edit_taxes",
            "settings_exports_view", "view_exports", "create_exports", "download_exports",
        ],
    },
    {
        "key": "laundry_staff",
        "label": "Laundry Staff",
        "description": "Laundry operations",
        "emoji": "🧺",
        "color": "#fecaca",
        "permissions": [
            "dashboard_view", "tasks_my_view",
            "laundry_reports_view", "view_laundry_daily_usage", "create_laundry_daily_usage",
            "view_laundry_orders", "create_laundry_orders",
            "view_laundry_deliveries", "create_laundry_deliveries",
            "view_laundry_dispatch", "create_laundry_dispatch",
            "view_laundry_stock",
        ],
    },
    {
        "key": "maintenance",
        "label": "Maintenance",
        "description": "Maintenance operations",
        "emoji": "🔧",
        "color": "#dbeafe",
        "permissions": [
            "dashboard_view", "tasks_my_view",
            "maintenance_view", "view_maintenance", "create_maintenance", "edit_maintenance",
            "start_maintenance", "complete_maintenance", "comment_maintenance",
        ],
    },
]


def get_all_permission_keys() -> List[str]:
    """Flat list of every permission key in the catalog."""
    keys = []
    for cat in PERMISSION_CATALOG:
        for sg in cat["sub_groups"]:
            for p in sg["permissions"]:
                keys.append(p["key"])
    return keys


def count_permissions_per_category(category_key: str) -> int:
    for cat in PERMISSION_CATALOG:
        if cat["key"] == category_key:
            return sum(len(sg["permissions"]) for sg in cat["sub_groups"])
    return 0


def count_total_permissions() -> int:
    return sum(
        len(sg["permissions"])
        for cat in PERMISSION_CATALOG
        for sg in cat["sub_groups"]
    )


def expand_template_permissions(template_key: str) -> List[str]:
    for t in ROLE_TEMPLATES:
        if t["key"] == template_key:
            perms = t["permissions"]
            if perms == "__ALL__":
                return get_all_permission_keys()
            return list(perms)
    return []
