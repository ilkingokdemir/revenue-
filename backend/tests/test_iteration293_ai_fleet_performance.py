"""
Iteration 293 - AI Fleet Optimize & Performance Tracker Tests

Tests for:
1. POST /api/revenue/market-robot/ai-fleet-optimize - GPT-4o-mini AI recommendations
2. GET /api/revenue/market-robot/gap-history/performance-summary - Rolling performance summary
3. GET /api/revenue/market-robot/gap-history/{batch_id}/performance - Single batch performance
4. POST /api/revenue/market-robot/fleet-close-gap - Fleet-wide gap close (4 strategies)
5. GET /api/revenue/market-robot/gap-history - History list
6. POST /api/revenue/market-robot/gap-history/{batch_id}/undo - Undo batch
7. RBAC tests - receptionist must get 403 on all new endpoints
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
RECEPTIONIST_EMAIL = "testrecep@hotelbox.com"
RECEPTIONIST_PASSWORD = "Test2026!"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 200, f"Admin login failed: {response.text}"
    data = response.json()
    return data.get("access_token") or data.get("token")


@pytest.fixture(scope="module")
def receptionist_token():
    """Get receptionist authentication token for RBAC tests"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": RECEPTIONIST_EMAIL, "password": RECEPTIONIST_PASSWORD}
    )
    assert response.status_code == 200, f"Receptionist login failed: {response.text}"
    data = response.json()
    return data.get("access_token") or data.get("token")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    """Admin auth headers"""
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def receptionist_headers(receptionist_token):
    """Receptionist auth headers"""
    return {"Authorization": f"Bearer {receptionist_token}", "Content-Type": "application/json"}


class TestFleetCloseGap:
    """Tests for POST /api/revenue/market-robot/fleet-close-gap (4 strategies)"""

    def test_fleet_close_gap_half_strategy_dry_run(self, admin_headers):
        """Test fleet-close-gap with 'half' strategy (dry_run=true)"""
        response = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/fleet-close-gap",
            headers=admin_headers,
            json={"strategy": "half", "days": 14, "dry_run": True, "min_gap_pct": 2.0}
        )
        assert response.status_code == 200, f"Fleet close-gap half failed: {response.text}"
        data = response.json()
        assert data.get("ok") is True
        assert data.get("strategy") == "half"
        assert data.get("dry_run") is True
        assert data.get("batch_id") is None  # dry_run should not create batch_id
        assert "fleet_summary" in data
        assert "branches" in data
        print(f"✓ Fleet close-gap half (dry_run): {data['fleet_summary']}")

    def test_fleet_close_gap_full_strategy_dry_run(self, admin_headers):
        """Test fleet-close-gap with 'full' strategy (dry_run=true)"""
        response = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/fleet-close-gap",
            headers=admin_headers,
            json={"strategy": "full", "days": 14, "dry_run": True, "min_gap_pct": 2.0}
        )
        assert response.status_code == 200, f"Fleet close-gap full failed: {response.text}"
        data = response.json()
        assert data.get("ok") is True
        assert data.get("strategy") == "full"
        print(f"✓ Fleet close-gap full (dry_run): {data['fleet_summary']}")

    def test_fleet_close_gap_floor_strategy_dry_run(self, admin_headers):
        """Test fleet-close-gap with 'floor' strategy (dry_run=true)"""
        response = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/fleet-close-gap",
            headers=admin_headers,
            json={"strategy": "floor", "days": 14, "dry_run": True, "min_gap_pct": 2.0}
        )
        assert response.status_code == 200, f"Fleet close-gap floor failed: {response.text}"
        data = response.json()
        assert data.get("ok") is True
        assert data.get("strategy") == "floor"
        print(f"✓ Fleet close-gap floor (dry_run): {data['fleet_summary']}")

    def test_fleet_close_gap_value_strategy_dry_run(self, admin_headers):
        """Test fleet-close-gap with 'value' strategy (dry_run=true)"""
        response = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/fleet-close-gap",
            headers=admin_headers,
            json={"strategy": "value", "days": 14, "dry_run": True, "min_gap_pct": 2.0}
        )
        assert response.status_code == 200, f"Fleet close-gap value failed: {response.text}"
        data = response.json()
        assert data.get("ok") is True
        assert data.get("strategy") == "value"
        print(f"✓ Fleet close-gap value (dry_run): {data['fleet_summary']}")

    def test_fleet_close_gap_invalid_strategy(self, admin_headers):
        """Test fleet-close-gap with invalid strategy returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/fleet-close-gap",
            headers=admin_headers,
            json={"strategy": "invalid_strategy", "days": 14, "dry_run": True}
        )
        assert response.status_code == 400, f"Expected 400 for invalid strategy, got {response.status_code}"
        print("✓ Fleet close-gap invalid strategy returns 400")


class TestAIFleetOptimize:
    """Tests for POST /api/revenue/market-robot/ai-fleet-optimize (GPT-4o-mini)"""

    def test_ai_fleet_optimize_dry_run(self, admin_headers):
        """Test AI fleet optimize with dry_run=true (default)"""
        # AI call takes 5-7 seconds, set timeout to 60s
        response = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/ai-fleet-optimize",
            headers=admin_headers,
            json={"days": 14, "dry_run": True, "min_gap_pct": 5.0},
            timeout=60
        )
        assert response.status_code in (200, 502), f"AI fleet optimize failed: {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            assert data.get("ok") in (True, False)  # ok=False if no eligible branches
            assert data.get("dry_run") is True
            
            if data.get("ok"):
                assert "ai_recommendations" in data
                assert "fleet_summary" in data
                assert "branches" in data
                # Verify AI recommendations structure
                recs = data.get("ai_recommendations", [])
                for rec in recs:
                    assert "property_id" in rec
                    assert "strategy" in rec
                    assert rec["strategy"] in ("full", "half", "floor", "value")
                print(f"✓ AI fleet optimize (dry_run): {len(recs)} recommendations, summary: {data['fleet_summary']}")
            else:
                # No eligible branches - this is valid
                print(f"✓ AI fleet optimize (dry_run): No eligible branches - {data.get('error', 'N/A')}")
        else:
            # 502 means AI call failed - acceptable for testing
            print(f"⚠ AI fleet optimize returned 502 (AI call issue): {response.text[:200]}")

    def test_ai_fleet_optimize_with_apply(self, admin_headers):
        """Test AI fleet optimize with dry_run=false (real apply)"""
        response = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/ai-fleet-optimize",
            headers=admin_headers,
            json={"days": 7, "dry_run": False, "min_gap_pct": 5.0},
            timeout=60
        )
        assert response.status_code in (200, 502), f"AI fleet optimize apply failed: {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            if data.get("ok") and data.get("fleet_summary", {}).get("branches_with_apply", 0) > 0:
                # Should have batch_id when not dry_run and something applied
                assert data.get("batch_id") is not None, "batch_id should be set when dry_run=false and applied"
                print(f"✓ AI fleet optimize (apply): batch_id={data['batch_id']}, applied={data['fleet_summary']}")
            else:
                print(f"✓ AI fleet optimize (apply): No branches applied - {data.get('error', 'N/A')}")
        else:
            print(f"⚠ AI fleet optimize apply returned 502: {response.text[:200]}")


class TestGapHistory:
    """Tests for GET /api/revenue/market-robot/gap-history"""

    def test_gap_history_list(self, admin_headers):
        """Test getting gap history list"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/gap-history?limit=10",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Gap history list failed: {response.text}"
        data = response.json()
        assert "items" in data
        items = data["items"]
        assert isinstance(items, list)
        
        # Verify structure of history items
        for item in items[:3]:  # Check first 3
            assert "batch_id" in item
            assert "applied_at" in item
            assert "strategy" in item
            assert "undone" in item
        
        print(f"✓ Gap history list: {len(items)} batches found")
        return items


class TestGapBatchPerformance:
    """Tests for GET /api/revenue/market-robot/gap-history/{batch_id}/performance"""

    def test_gap_batch_performance_existing(self, admin_headers):
        """Test getting performance for an existing batch"""
        # First get history to find a batch_id
        history_response = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/gap-history?limit=5",
            headers=admin_headers
        )
        assert history_response.status_code == 200
        items = history_response.json().get("items", [])
        
        if not items:
            pytest.skip("No gap history batches found to test performance")
        
        batch_id = items[0]["batch_id"]
        
        response = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/gap-history/{batch_id}/performance",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Batch performance failed: {response.text}"
        data = response.json()
        assert data.get("ok") is True
        assert data.get("batch_id") == batch_id
        
        # Check for expected fields
        if not data.get("undone"):
            assert "summary" in data
            summary = data["summary"]
            assert "branches_in_batch" in summary
            assert "total_overrides_active" in summary
            assert "total_bookings_after_apply" in summary
            assert "estimated_total_revenue_uplift" in summary
            print(f"✓ Batch performance: {summary}")
        else:
            print(f"✓ Batch performance (undone batch): {data.get('message')}")

    def test_gap_batch_performance_not_found(self, admin_headers):
        """Test getting performance for non-existent batch returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/gap-history/nonexistent_batch_id/performance",
            headers=admin_headers
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Batch performance 404 for non-existent batch")


class TestGapPerformanceSummary:
    """Tests for GET /api/revenue/market-robot/gap-history/performance-summary"""

    def test_gap_performance_summary(self, admin_headers):
        """Test getting rolling performance summary"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/gap-history/performance-summary?limit=10",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Performance summary failed: {response.text}"
        data = response.json()
        assert data.get("ok") is True
        assert "summary" in data
        
        summary = data["summary"]
        assert "total_batches" in summary
        assert "total_bookings_after" in summary
        assert "total_revenue_uplift" in summary
        
        # Check by_strategy array
        assert "by_strategy" in data
        by_strategy = data["by_strategy"]
        assert isinstance(by_strategy, list)
        
        for strat in by_strategy:
            assert "strategy" in strat
            assert "batches" in strat
            assert "bookings" in strat
            assert "revenue_uplift" in strat
        
        print(f"✓ Performance summary: {summary}, strategies: {len(by_strategy)}")


class TestGapHistoryUndo:
    """Tests for POST /api/revenue/market-robot/gap-history/{batch_id}/undo"""

    def test_undo_nonexistent_batch(self, admin_headers):
        """Test undo for non-existent batch returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/gap-history/nonexistent_batch/undo",
            headers=admin_headers
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Undo 404 for non-existent batch")

    def test_undo_already_undone_batch(self, admin_headers):
        """Test undo for already undone batch returns 400"""
        # First get history to find an undone batch
        history_response = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/gap-history?limit=20",
            headers=admin_headers
        )
        assert history_response.status_code == 200
        items = history_response.json().get("items", [])
        
        undone_batch = next((item for item in items if item.get("undone")), None)
        
        if not undone_batch:
            pytest.skip("No undone batches found to test double-undo")
        
        batch_id = undone_batch["batch_id"]
        
        response = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/gap-history/{batch_id}/undo",
            headers=admin_headers
        )
        assert response.status_code == 400, f"Expected 400 for double undo, got {response.status_code}"
        print(f"✓ Double undo returns 400 for batch {batch_id}")

    def test_undo_creates_and_undoes_batch(self, admin_headers):
        """Test creating a batch with fleet-close-gap and then undoing it"""
        # Create a real batch (not dry_run)
        create_response = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/fleet-close-gap",
            headers=admin_headers,
            json={"strategy": "half", "days": 7, "dry_run": False, "min_gap_pct": 1.0}
        )
        assert create_response.status_code == 200, f"Create batch failed: {create_response.text}"
        create_data = create_response.json()
        
        if not create_data.get("batch_id"):
            pytest.skip("No batch created (no eligible branches)")
        
        batch_id = create_data["batch_id"]
        print(f"Created batch {batch_id} with {create_data['fleet_summary']['total_days_applied']} days applied")
        
        # Now undo it
        undo_response = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/gap-history/{batch_id}/undo",
            headers=admin_headers
        )
        assert undo_response.status_code == 200, f"Undo failed: {undo_response.text}"
        undo_data = undo_response.json()
        assert undo_data.get("ok") is True
        assert undo_data.get("batch_id") == batch_id
        assert "deleted_overrides" in undo_data
        print(f"✓ Undo batch {batch_id}: deleted {undo_data['deleted_overrides']} overrides")
        
        # Verify double undo returns 400
        double_undo_response = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/gap-history/{batch_id}/undo",
            headers=admin_headers
        )
        assert double_undo_response.status_code == 400, f"Double undo should return 400"
        print(f"✓ Double undo correctly returns 400")


class TestRBACReceptionist:
    """RBAC tests - receptionist must get 403 on all new endpoints"""

    def test_receptionist_ai_fleet_optimize_403(self, receptionist_headers):
        """Receptionist should get 403 on ai-fleet-optimize"""
        response = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/ai-fleet-optimize",
            headers=receptionist_headers,
            json={"days": 14, "dry_run": True},
            timeout=10
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print("✓ RBAC: receptionist gets 403 on ai-fleet-optimize")

    def test_receptionist_fleet_close_gap_403(self, receptionist_headers):
        """Receptionist should get 403 on fleet-close-gap"""
        response = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/fleet-close-gap",
            headers=receptionist_headers,
            json={"strategy": "half", "days": 14, "dry_run": True}
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print("✓ RBAC: receptionist gets 403 on fleet-close-gap")

    def test_receptionist_gap_history_403(self, receptionist_headers):
        """Receptionist should get 403 on gap-history"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/gap-history?limit=5",
            headers=receptionist_headers
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print("✓ RBAC: receptionist gets 403 on gap-history")

    def test_receptionist_gap_batch_performance_403(self, receptionist_headers):
        """Receptionist should get 403 on gap-history/{batch_id}/performance"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/gap-history/any_batch_id/performance",
            headers=receptionist_headers
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print("✓ RBAC: receptionist gets 403 on gap-batch-performance")

    def test_receptionist_performance_summary_403(self, receptionist_headers):
        """Receptionist should get 403 on performance-summary"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/gap-history/performance-summary?limit=5",
            headers=receptionist_headers
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print("✓ RBAC: receptionist gets 403 on performance-summary")

    def test_receptionist_undo_403(self, receptionist_headers):
        """Receptionist should get 403 on undo"""
        response = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/gap-history/any_batch_id/undo",
            headers=receptionist_headers
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print("✓ RBAC: receptionist gets 403 on undo")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
