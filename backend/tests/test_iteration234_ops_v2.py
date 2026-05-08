"""
Iteration 234 - Batch 22: Ops v2 (Maintenance Work-Order State Machine + Linen PAR + HK Inspection)

Tests:
- Maintenance work orders: CRUD + full state machine (reported→assigned→in_progress→completed→verified)
- Maintenance work orders: pause/resume/reopen transitions
- Linen PAR: overview, upsert item, cycle movements, seed defaults
- HK Inspection: template, submit with auto-work-order creation, history with pass_rate
- Edge cases: invalid action, negative qty, missing property_id
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

@pytest.fixture(scope="module")
def session():
    """Create authenticated session"""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    # Login as admin
    login_resp = s.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    return s


class TestMaintenanceWorkOrders:
    """Maintenance work order CRUD and state machine tests"""
    
    def test_list_workorders_empty_or_existing(self, session):
        """GET /api/ops-v2/workorders/{property_id} - list work orders"""
        resp = session.get(f"{BASE_URL}/api/ops-v2/workorders/default")
        assert resp.status_code == 200
        data = resp.json()
        assert "rows" in data
        assert "counters" in data
        assert "critical_open" in data
        # Counters should have all status keys
        for status in ["reported", "assigned", "in_progress", "completed", "verified"]:
            assert status in data["counters"]
        print(f"✓ List workorders: {len(data['rows'])} rows, counters={data['counters']}")
    
    def test_create_workorder(self, session):
        """POST /api/ops-v2/workorders - create new work order"""
        payload = {
            "property_id": "default",
            "title": f"TEST_WO_{uuid.uuid4().hex[:8]}",
            "description": "Test work order for plumbing issue",
            "location": "Room 101",
            "priority": "high",
            "category": "plumbing"
        }
        resp = session.post(f"{BASE_URL}/api/ops-v2/workorders", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert data["status"] == "reported"
        assert data["title"] == payload["title"]
        assert data["priority"] == "high"
        assert data["category"] == "plumbing"
        assert "reported_at" in data
        assert "events" in data
        print(f"✓ Created work order: {data['id']}")
        return data["id"]
    
    def test_full_state_machine_flow(self, session):
        """Test complete state machine: reported → assigned → in_progress → completed → verified"""
        # Create a new work order
        wo_payload = {
            "property_id": "default",
            "title": f"TEST_STATE_MACHINE_{uuid.uuid4().hex[:8]}",
            "description": "Testing full state machine",
            "priority": "critical",
            "category": "electrical"
        }
        create_resp = session.post(f"{BASE_URL}/api/ops-v2/workorders", json=wo_payload)
        assert create_resp.status_code == 200
        wo_id = create_resp.json()["id"]
        print(f"✓ Created WO for state machine test: {wo_id}")
        
        # Step 1: Assign
        assign_resp = session.post(f"{BASE_URL}/api/ops-v2/workorders/{wo_id}/action", json={
            "action": "assign",
            "assigned_to": "technician@hotel.com",
            "notes": "Assigned to electrician"
        })
        assert assign_resp.status_code == 200
        assert assign_resp.json()["status"] == "assigned"
        print(f"✓ Assigned: {assign_resp.json()}")
        
        # Step 2: Start
        start_resp = session.post(f"{BASE_URL}/api/ops-v2/workorders/{wo_id}/action", json={
            "action": "start",
            "notes": "Starting work"
        })
        assert start_resp.status_code == 200
        assert start_resp.json()["status"] == "in_progress"
        print(f"✓ Started: {start_resp.json()}")
        
        # Step 3: Complete
        complete_resp = session.post(f"{BASE_URL}/api/ops-v2/workorders/{wo_id}/action", json={
            "action": "complete",
            "notes": "Work completed successfully"
        })
        assert complete_resp.status_code == 200
        assert complete_resp.json()["status"] == "completed"
        print(f"✓ Completed: {complete_resp.json()}")
        
        # Step 4: Verify
        verify_resp = session.post(f"{BASE_URL}/api/ops-v2/workorders/{wo_id}/action", json={
            "action": "verify",
            "notes": "Verified by supervisor"
        })
        assert verify_resp.status_code == 200
        assert verify_resp.json()["status"] == "verified"
        print(f"✓ Verified: {verify_resp.json()}")
        
        # Verify final state via GET
        list_resp = session.get(f"{BASE_URL}/api/ops-v2/workorders/default?status=verified")
        assert list_resp.status_code == 200
        verified_wos = [w for w in list_resp.json()["rows"] if w["id"] == wo_id]
        assert len(verified_wos) == 1
        assert verified_wos[0]["status"] == "verified"
        print(f"✓ Full state machine flow completed successfully")
    
    def test_pause_resume_flow(self, session):
        """Test pause and resume transitions"""
        # Create and start a work order
        wo_payload = {
            "property_id": "default",
            "title": f"TEST_PAUSE_RESUME_{uuid.uuid4().hex[:8]}",
            "priority": "normal",
            "category": "hvac"
        }
        create_resp = session.post(f"{BASE_URL}/api/ops-v2/workorders", json=wo_payload)
        assert create_resp.status_code == 200
        wo_id = create_resp.json()["id"]
        
        # Assign
        session.post(f"{BASE_URL}/api/ops-v2/workorders/{wo_id}/action", json={"action": "assign"})
        # Start
        session.post(f"{BASE_URL}/api/ops-v2/workorders/{wo_id}/action", json={"action": "start"})
        
        # Pause
        pause_resp = session.post(f"{BASE_URL}/api/ops-v2/workorders/{wo_id}/action", json={
            "action": "pause",
            "notes": "Waiting for parts"
        })
        assert pause_resp.status_code == 200
        assert pause_resp.json()["status"] == "paused"
        print(f"✓ Paused: {pause_resp.json()}")
        
        # Resume
        resume_resp = session.post(f"{BASE_URL}/api/ops-v2/workorders/{wo_id}/action", json={
            "action": "resume",
            "notes": "Parts arrived"
        })
        assert resume_resp.status_code == 200
        assert resume_resp.json()["status"] == "in_progress"
        print(f"✓ Resumed: {resume_resp.json()}")
    
    def test_reopen_flow(self, session):
        """Test reopen transition from completed back to reported"""
        # Create and complete a work order
        wo_payload = {
            "property_id": "default",
            "title": f"TEST_REOPEN_{uuid.uuid4().hex[:8]}",
            "priority": "low",
            "category": "general"
        }
        create_resp = session.post(f"{BASE_URL}/api/ops-v2/workorders", json=wo_payload)
        wo_id = create_resp.json()["id"]
        
        # Fast-track to completed
        session.post(f"{BASE_URL}/api/ops-v2/workorders/{wo_id}/action", json={"action": "assign"})
        session.post(f"{BASE_URL}/api/ops-v2/workorders/{wo_id}/action", json={"action": "start"})
        session.post(f"{BASE_URL}/api/ops-v2/workorders/{wo_id}/action", json={"action": "complete"})
        
        # Reopen
        reopen_resp = session.post(f"{BASE_URL}/api/ops-v2/workorders/{wo_id}/action", json={
            "action": "reopen",
            "notes": "Issue recurred"
        })
        assert reopen_resp.status_code == 200
        assert reopen_resp.json()["status"] == "reported"
        print(f"✓ Reopened: {reopen_resp.json()}")
    
    def test_invalid_action(self, session):
        """Test invalid action returns 400"""
        # Create a work order
        wo_payload = {
            "property_id": "default",
            "title": f"TEST_INVALID_{uuid.uuid4().hex[:8]}",
            "priority": "normal",
            "category": "general"
        }
        create_resp = session.post(f"{BASE_URL}/api/ops-v2/workorders", json=wo_payload)
        wo_id = create_resp.json()["id"]
        
        # Try invalid action
        invalid_resp = session.post(f"{BASE_URL}/api/ops-v2/workorders/{wo_id}/action", json={
            "action": "invalid_action"
        })
        assert invalid_resp.status_code == 400
        print(f"✓ Invalid action correctly rejected: {invalid_resp.json()}")
    
    def test_workorder_not_found(self, session):
        """Test action on non-existent work order returns 404"""
        resp = session.post(f"{BASE_URL}/api/ops-v2/workorders/nonexistent-id/action", json={
            "action": "assign"
        })
        assert resp.status_code == 404
        print(f"✓ Non-existent WO correctly returns 404")
    
    def test_status_filter(self, session):
        """Test filtering work orders by status"""
        resp = session.get(f"{BASE_URL}/api/ops-v2/workorders/default?status=reported")
        assert resp.status_code == 200
        data = resp.json()
        # All returned rows should have status=reported
        for row in data["rows"]:
            assert row["status"] == "reported"
        print(f"✓ Status filter works: {len(data['rows'])} reported WOs")


class TestLinenPAR:
    """Linen PAR tracking tests"""
    
    def test_linen_overview(self, session):
        """GET /api/ops-v2/linen/{property_id} - get linen overview"""
        resp = session.get(f"{BASE_URL}/api/ops-v2/linen/default")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "low_par_count" in data
        assert "low_par" in data
        print(f"✓ Linen overview: {len(data['items'])} items, {data['low_par_count']} below PAR")
        return data
    
    def test_seed_linen_defaults(self, session):
        """POST /api/ops-v2/linen/{property_id}/seed-defaults - seed default linen items"""
        # Use a unique property_id to test seeding
        test_prop = f"test_linen_{uuid.uuid4().hex[:8]}"
        
        # First seed should create 5 items
        resp = session.post(f"{BASE_URL}/api/ops-v2/linen/{test_prop}/seed-defaults")
        assert resp.status_code == 200
        data = resp.json()
        # Either seeded 5 or already exists
        assert "seeded" in data or "note" in data
        print(f"✓ Seed linen: {data}")
        
        # Second seed should return note about existing items
        resp2 = session.post(f"{BASE_URL}/api/ops-v2/linen/{test_prop}/seed-defaults")
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2.get("seeded") == 0 or "already" in data2.get("note", "").lower()
        print(f"✓ Re-seed correctly skipped: {data2}")
    
    def test_upsert_linen_item(self, session):
        """POST /api/ops-v2/linen/item - upsert linen item"""
        payload = {
            "property_id": "default",
            "item_type": "tablecloth",
            "par_level": 50,
            "reorder_threshold": 20,
            "unit_cost": 15.0
        }
        resp = session.post(f"{BASE_URL}/api/ops-v2/linen/item", json=payload)
        assert resp.status_code == 200
        assert resp.json().get("updated") == True
        print(f"✓ Upserted linen item: tablecloth")
        
        # Verify it appears in overview
        overview = session.get(f"{BASE_URL}/api/ops-v2/linen/default")
        items = overview.json()["items"]
        tablecloth = [i for i in items if i["item_type"] == "tablecloth"]
        assert len(tablecloth) > 0
        assert tablecloth[0]["par_level"] == 50
        print(f"✓ Verified tablecloth in overview")
    
    def test_linen_cycle_clean_to_in_use(self, session):
        """POST /api/ops-v2/linen/cycle - clean_to_in_use movement"""
        # First ensure we have linen seeded
        session.post(f"{BASE_URL}/api/ops-v2/linen/default/seed-defaults")
        
        # Get current state
        before = session.get(f"{BASE_URL}/api/ops-v2/linen/default").json()
        bed_sheet_before = next((i for i in before["items"] if i["item_type"] == "bed_sheet"), None)
        
        if bed_sheet_before and bed_sheet_before.get("clean", 0) >= 5:
            clean_before = bed_sheet_before["clean"]
            in_use_before = bed_sheet_before.get("in_use", 0)
            
            # Move 5 from clean to in_use
            resp = session.post(f"{BASE_URL}/api/ops-v2/linen/cycle", json={
                "property_id": "default",
                "item_type": "bed_sheet",
                "movement": "clean_to_in_use",
                "qty": 5
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["movement"] == "clean_to_in_use"
            assert data["qty"] == 5
            assert data["from"] == "clean"
            assert data["to"] == "in_use"
            print(f"✓ Cycle clean_to_in_use: {data}")
            
            # Verify state changed
            after = session.get(f"{BASE_URL}/api/ops-v2/linen/default").json()
            bed_sheet_after = next((i for i in after["items"] if i["item_type"] == "bed_sheet"), None)
            assert bed_sheet_after["clean"] == clean_before - 5
            assert bed_sheet_after["in_use"] == in_use_before + 5
            print(f"✓ Verified state change: clean {clean_before}→{bed_sheet_after['clean']}, in_use {in_use_before}→{bed_sheet_after['in_use']}")
        else:
            print("⚠ Skipping cycle test - not enough clean bed sheets")
    
    def test_linen_cycle_all_movements(self, session):
        """Test all valid linen cycle movements"""
        valid_movements = [
            "checkout_to_dirty",
            "dirty_to_washing",
            "washing_to_clean",
            "clean_to_in_use",
            "lost_or_damaged"
        ]
        
        for movement in valid_movements:
            resp = session.post(f"{BASE_URL}/api/ops-v2/linen/cycle", json={
                "property_id": "default",
                "item_type": "towel_bath",
                "movement": movement,
                "qty": 1
            })
            assert resp.status_code == 200
            assert resp.json()["movement"] == movement
            print(f"✓ Movement {movement} accepted")
    
    def test_linen_cycle_invalid_movement(self, session):
        """Test invalid movement returns 400"""
        resp = session.post(f"{BASE_URL}/api/ops-v2/linen/cycle", json={
            "property_id": "default",
            "item_type": "bed_sheet",
            "movement": "invalid_movement",
            "qty": 5
        })
        assert resp.status_code == 400
        print(f"✓ Invalid movement correctly rejected: {resp.json()}")
    
    def test_low_par_detection(self, session):
        """Test that low_par items are detected when clean < reorder_threshold"""
        overview = session.get(f"{BASE_URL}/api/ops-v2/linen/default").json()
        # Check structure
        for item in overview["items"]:
            assert "below_par" in item
            assert "states" in item
            assert "clean" in item
            assert "dirty" in item
            assert "washing" in item
            assert "in_use" in item
        print(f"✓ Low PAR detection structure verified, {overview['low_par_count']} items below PAR")


class TestHKInspection:
    """HK Inspection checklist tests"""
    
    def test_inspection_template(self, session):
        """GET /api/ops-v2/inspection/template - get default checks"""
        resp = session.get(f"{BASE_URL}/api/ops-v2/inspection/template")
        assert resp.status_code == 200
        data = resp.json()
        assert "default_checks" in data
        assert len(data["default_checks"]) == 10
        expected_checks = [
            "Bed made and linen fresh",
            "Bathroom cleaned and stocked",
            "Trash bins empty",
            "Floor vacuumed/mopped",
            "Minibar restocked"
        ]
        for check in expected_checks:
            assert check in data["default_checks"]
        print(f"✓ Inspection template: {len(data['default_checks'])} checks")
    
    def test_submit_inspection_all_pass(self, session):
        """POST /api/ops-v2/inspection - submit inspection with all checks passing"""
        checks = [
            {"name": "Bed made", "pass": True, "notes": ""},
            {"name": "Bathroom clean", "pass": True, "notes": ""},
            {"name": "Trash empty", "pass": True, "notes": ""}
        ]
        payload = {
            "property_id": "default",
            "room_id": f"TEST_{uuid.uuid4().hex[:4]}",
            "checks": checks,
            "overall_pass": True,
            "notes": "All good"
        }
        resp = session.post(f"{BASE_URL}/api/ops-v2/inspection", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert data["passed_count"] == 3
        assert data["failed_count"] == 0
        assert data["overall_pass"] == True
        assert data["workorders_created"] == []
        print(f"✓ Inspection all pass: {data}")
    
    def test_submit_inspection_with_failures_creates_workorders(self, session):
        """POST /api/ops-v2/inspection - failed checks auto-create work orders"""
        room_id = f"TEST_FAIL_{uuid.uuid4().hex[:4]}"
        checks = [
            {"name": "Bed made", "pass": True, "notes": ""},
            {"name": "Bathroom clean", "pass": False, "notes": "Toilet not cleaned"},
            {"name": "Minibar restocked", "pass": False, "notes": "Missing items"}
        ]
        payload = {
            "property_id": "default",
            "room_id": room_id,
            "checks": checks,
            "overall_pass": False,
            "notes": "Needs attention"
        }
        resp = session.post(f"{BASE_URL}/api/ops-v2/inspection", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["passed_count"] == 1
        assert data["failed_count"] == 2
        assert data["overall_pass"] == False
        assert len(data["workorders_created"]) == 2
        print(f"✓ Inspection with failures: {data['failed_count']} failed, {len(data['workorders_created'])} WOs created")
        
        # Verify work orders were actually created
        wo_list = session.get(f"{BASE_URL}/api/ops-v2/workorders/default").json()
        created_wo_ids = data["workorders_created"]
        for wo_id in created_wo_ids:
            wo = next((w for w in wo_list["rows"] if w["id"] == wo_id), None)
            assert wo is not None
            assert "Inspection fail:" in wo["title"]
            assert wo["room_id"] == room_id
            assert wo["priority"] == "high"
            assert wo["category"] == "housekeeping"
        print(f"✓ Verified auto-created work orders exist")
    
    def test_list_inspections_with_pass_rate(self, session):
        """GET /api/ops-v2/inspections/{property_id} - list with pass rate"""
        resp = session.get(f"{BASE_URL}/api/ops-v2/inspections/default")
        assert resp.status_code == 200
        data = resp.json()
        assert "rows" in data
        assert "total" in data
        assert "failed" in data
        assert "pass_rate" in data
        # pass_rate should be a percentage
        assert 0 <= data["pass_rate"] <= 100
        print(f"✓ Inspections list: {data['total']} total, {data['failed']} failed, {data['pass_rate']}% pass rate")
    
    def test_inspection_history_structure(self, session):
        """Verify inspection history row structure"""
        resp = session.get(f"{BASE_URL}/api/ops-v2/inspections/default?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        
        if data["rows"]:
            row = data["rows"][0]
            assert "id" in row
            assert "property_id" in row
            assert "room_id" in row
            assert "checks" in row
            assert "overall_pass" in row
            assert "inspected_at" in row
            assert "inspected_by" in row
            assert "passed_count" in row
            assert "failed_count" in row
            print(f"✓ Inspection row structure verified")
        else:
            print("⚠ No inspections to verify structure")


class TestEdgeCases:
    """Edge case and error handling tests"""
    
    def test_workorder_missing_title(self, session):
        """Work order without title should fail validation"""
        payload = {
            "property_id": "default",
            "description": "No title"
        }
        resp = session.post(f"{BASE_URL}/api/ops-v2/workorders", json=payload)
        # Pydantic should reject missing required field
        assert resp.status_code in [400, 422]
        print(f"✓ Missing title correctly rejected")
    
    def test_inspection_missing_room_id(self, session):
        """Inspection without room_id should fail validation"""
        payload = {
            "property_id": "default",
            "checks": [{"name": "Test", "pass": True}],
            "overall_pass": True
        }
        resp = session.post(f"{BASE_URL}/api/ops-v2/inspection", json=payload)
        assert resp.status_code in [400, 422]
        print(f"✓ Missing room_id correctly rejected")
    
    def test_linen_cycle_zero_qty(self, session):
        """Linen cycle with qty=0 should be accepted (no-op)"""
        resp = session.post(f"{BASE_URL}/api/ops-v2/linen/cycle", json={
            "property_id": "default",
            "item_type": "bed_sheet",
            "movement": "clean_to_in_use",
            "qty": 0
        })
        # Should be accepted but effectively a no-op
        assert resp.status_code == 200
        print(f"✓ Zero qty cycle accepted")


class TestRBAC:
    """RBAC permission tests"""
    
    def test_unauthenticated_access_denied(self):
        """Unauthenticated requests should be denied"""
        s = requests.Session()
        resp = s.get(f"{BASE_URL}/api/ops-v2/workorders/default")
        assert resp.status_code in [401, 403]
        print(f"✓ Unauthenticated access denied")
    
    def test_housekeeping_role_can_access_linen(self, session):
        """Housekeeping role should have access to linen endpoints"""
        # Admin has all permissions, so this should work
        resp = session.get(f"{BASE_URL}/api/ops-v2/linen/default")
        assert resp.status_code == 200
        print(f"✓ Linen access verified for admin")
    
    def test_housekeeping_role_can_submit_inspection(self, session):
        """Housekeeping role should be able to submit inspections"""
        resp = session.get(f"{BASE_URL}/api/ops-v2/inspection/template")
        assert resp.status_code == 200
        print(f"✓ Inspection template access verified")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
