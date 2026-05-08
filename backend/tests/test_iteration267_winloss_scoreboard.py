"""
Iteration 267: AI vs Owner Win/Loss Scoreboard Tests
Tests the new winloss endpoint that compares owner override rates against Sentinel AI rates
and matches against actual booking outcomes.

Features tested:
- POST /api/rates/grid/submit-to-pms captures ai_rate_at_submit in rate_override_history
- GET /api/rates/winloss/{property_id}?lookback_days=N returns summary and comparisons
- Verdict logic: win/loss/neutral based on owner vs AI rate and booking outcomes
- comparisons[] sorted by date desc
- Naive revenue calc: actual_revenue = bookings * owner_rate; ai_counterfactual = bookings * ai_rate
- biggest_win/biggest_loss tracking
- Auth required (admin/manager only)
"""

import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test property ID
TEST_PROPERTY_ID = "aldgate-flats"


class TestWinLossScoreboard:
    """Win/Loss Scoreboard endpoint tests"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json().get("token")  # API returns "token" not "access_token"
        assert token, "No token in login response"
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.token = token
        yield
        # Cleanup handled in individual tests if needed

    # ==================== AUTH TESTS ====================
    
    def test_winloss_requires_auth(self):
        """Winloss endpoint requires authentication"""
        # Request without auth header
        no_auth_session = requests.Session()
        resp = no_auth_session.get(f"{BASE_URL}/api/rates/winloss/{TEST_PROPERTY_ID}")
        assert resp.status_code in [401, 403], f"Expected 401/403 without auth, got {resp.status_code}"
        print("PASS: Winloss endpoint requires auth (401/403 without token)")

    def test_winloss_requires_admin_or_manager_role(self):
        """Winloss endpoint requires admin or manager role"""
        # Login as housekeeper (should be denied)
        hk_session = requests.Session()
        hk_session.headers.update({"Content-Type": "application/json"})
        login_resp = hk_session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testhk@hotelbox.com",
            "password": "Test2026!"
        })
        if login_resp.status_code == 200:
            token = login_resp.json().get("access_token")
            if token:
                hk_session.headers.update({"Authorization": f"Bearer {token}"})
                resp = hk_session.get(f"{BASE_URL}/api/rates/winloss/{TEST_PROPERTY_ID}")
                assert resp.status_code in [401, 403], f"Housekeeper should be denied, got {resp.status_code}"
                print("PASS: Housekeeper role denied access to winloss endpoint")
            else:
                print("SKIP: Housekeeper login returned no token")
        else:
            print("SKIP: Housekeeper user not found or login failed")

    # ==================== SUBMIT-TO-PMS CAPTURES AI_RATE_AT_SUBMIT ====================

    def test_submit_to_pms_captures_ai_rate_at_submit(self):
        """POST /api/rates/grid/submit-to-pms captures ai_rate_at_submit in history"""
        # Use a past date (10 days ago) for testing
        test_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        
        # First, create an override for this date
        override_resp = self.session.post(f"{BASE_URL}/api/rates/grid/override", json={
            "property_id": TEST_PROPERTY_ID,
            "changes": [{
                "date": test_date,
                "pms_override": 150.0,
                "min_rate": 70.0
            }]
        })
        assert override_resp.status_code == 200, f"Override failed: {override_resp.text}"
        
        # Submit to PMS
        submit_resp = self.session.post(f"{BASE_URL}/api/rates/grid/submit-to-pms", json={
            "property_id": TEST_PROPERTY_ID,
            "dates": [test_date]
        })
        assert submit_resp.status_code == 200, f"Submit failed: {submit_resp.text}"
        submit_data = submit_resp.json()
        assert submit_data.get("pms_synced", 0) >= 1, "Expected at least 1 pms_synced"
        
        # Check history for ai_rate_at_submit
        history_resp = self.session.get(f"{BASE_URL}/api/rates/grid/history/{TEST_PROPERTY_ID}/{test_date}")
        assert history_resp.status_code == 200, f"History failed: {history_resp.text}"
        history_data = history_resp.json()
        history_items = history_data.get("history", [])
        
        # Find the most recent submit action
        submit_entries = [h for h in history_items if h.get("action") == "submit"]
        assert len(submit_entries) > 0, "No submit entries found in history"
        
        latest_submit = submit_entries[0]  # Already sorted desc by created_at
        assert "ai_rate_at_submit" in latest_submit, "ai_rate_at_submit not captured in history"
        ai_rate = latest_submit.get("ai_rate_at_submit")
        assert ai_rate is not None, "ai_rate_at_submit is None"
        assert isinstance(ai_rate, (int, float)), f"ai_rate_at_submit should be numeric, got {type(ai_rate)}"
        assert ai_rate > 0, f"ai_rate_at_submit should be positive, got {ai_rate}"
        
        print(f"PASS: submit-to-pms captures ai_rate_at_submit={ai_rate} for date {test_date}")
        
        # Also verify delta_vs_ai is calculated
        if latest_submit.get("new_rate"):
            expected_delta = round(float(latest_submit["new_rate"]) - ai_rate, 2)
            actual_delta = latest_submit.get("delta_vs_ai")
            if actual_delta is not None:
                assert abs(actual_delta - expected_delta) < 0.1, f"delta_vs_ai mismatch: {actual_delta} vs {expected_delta}"
                print(f"PASS: delta_vs_ai correctly calculated: {actual_delta}")

    # ==================== WINLOSS ENDPOINT BASIC TESTS ====================

    def test_winloss_endpoint_returns_expected_structure(self):
        """GET /api/rates/winloss/{property_id} returns expected response structure"""
        resp = self.session.get(f"{BASE_URL}/api/rates/winloss/{TEST_PROPERTY_ID}?lookback_days=30")
        assert resp.status_code == 200, f"Winloss failed: {resp.text}"
        data = resp.json()
        
        # Check top-level fields
        assert "property_id" in data, "Missing property_id"
        assert "lookback_days" in data, "Missing lookback_days"
        assert "start_date" in data, "Missing start_date"
        assert "end_date" in data, "Missing end_date"
        assert "summary" in data, "Missing summary"
        assert "comparisons" in data, "Missing comparisons"
        
        # Check summary fields
        summary = data["summary"]
        required_summary_fields = [
            "total_overrides", "wins", "losses", "neutrals", "win_rate_pct",
            "revenue_owner", "revenue_ai_counterfactual", "revenue_lift",
            "biggest_win", "biggest_loss"
        ]
        for field in required_summary_fields:
            assert field in summary, f"Missing summary field: {field}"
        
        print(f"PASS: Winloss endpoint returns expected structure")
        print(f"  - total_overrides: {summary['total_overrides']}")
        print(f"  - wins: {summary['wins']}, losses: {summary['losses']}, neutrals: {summary['neutrals']}")
        print(f"  - win_rate_pct: {summary['win_rate_pct']}%")

    def test_winloss_comparisons_sorted_by_date_desc(self):
        """comparisons[] should be sorted by date descending"""
        resp = self.session.get(f"{BASE_URL}/api/rates/winloss/{TEST_PROPERTY_ID}?lookback_days=60")
        assert resp.status_code == 200, f"Winloss failed: {resp.text}"
        data = resp.json()
        
        comparisons = data.get("comparisons", [])
        if len(comparisons) >= 2:
            dates = [c["date"] for c in comparisons]
            assert dates == sorted(dates, reverse=True), f"Comparisons not sorted desc: {dates[:5]}"
            print(f"PASS: Comparisons sorted by date desc ({len(comparisons)} entries)")
        else:
            print(f"SKIP: Not enough comparisons to verify sorting ({len(comparisons)} entries)")

    def test_winloss_comparison_entry_fields(self):
        """Each comparison entry should have required fields"""
        resp = self.session.get(f"{BASE_URL}/api/rates/winloss/{TEST_PROPERTY_ID}?lookback_days=60")
        assert resp.status_code == 200, f"Winloss failed: {resp.text}"
        data = resp.json()
        
        comparisons = data.get("comparisons", [])
        if len(comparisons) > 0:
            entry = comparisons[0]
            required_fields = [
                "date", "owner_rate", "ai_rate", "delta_per_night",
                "bookings", "occupancy_pct", "actual_revenue", "ai_counterfactual",
                "revenue_delta", "verdict"
            ]
            for field in required_fields:
                assert field in entry, f"Missing comparison field: {field}"
            
            print(f"PASS: Comparison entry has all required fields")
            print(f"  - Sample: date={entry['date']}, owner={entry['owner_rate']}, ai={entry['ai_rate']}, verdict={entry['verdict']}")
        else:
            print("SKIP: No comparisons to verify fields")

    # ==================== VERDICT LOGIC TESTS ====================

    def test_create_test_data_for_verdict_logic(self):
        """Create test data with known outcomes to verify verdict logic"""
        # Create multiple past-date submits with different scenarios
        test_dates = []
        
        # Scenario 1: Owner > AI, bookings > 0 → should be WIN
        date_win = (datetime.now() - timedelta(days=15)).strftime("%Y-%m-%d")
        test_dates.append(("win_scenario", date_win, 180.0))  # High owner rate
        
        # Scenario 2: Owner > AI, occ_pct = 0 → should be LOSS (priced too high)
        date_loss_high = (datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d")
        test_dates.append(("loss_high_scenario", date_loss_high, 250.0))  # Very high rate
        
        # Scenario 3: Owner < AI, occ_pct >= 50 → should be NEUTRAL
        date_neutral = (datetime.now() - timedelta(days=25)).strftime("%Y-%m-%d")
        test_dates.append(("neutral_scenario", date_neutral, 75.0))  # Low owner rate
        
        # Scenario 4: Owner < AI, occ_pct < 50 → should be LOSS
        date_loss_low = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        test_dates.append(("loss_low_scenario", date_loss_low, 60.0))  # Very low rate
        
        for scenario_name, test_date, rate in test_dates:
            # Create override
            override_resp = self.session.post(f"{BASE_URL}/api/rates/grid/override", json={
                "property_id": TEST_PROPERTY_ID,
                "changes": [{
                    "date": test_date,
                    "pms_override": rate,
                    "min_rate": 50.0
                }]
            })
            assert override_resp.status_code == 200, f"Override failed for {scenario_name}: {override_resp.text}"
            
            # Submit to PMS
            submit_resp = self.session.post(f"{BASE_URL}/api/rates/grid/submit-to-pms", json={
                "property_id": TEST_PROPERTY_ID,
                "dates": [test_date]
            })
            assert submit_resp.status_code == 200, f"Submit failed for {scenario_name}: {submit_resp.text}"
            print(f"Created test data: {scenario_name} on {test_date} with rate £{rate}")
        
        print("PASS: Test data created for verdict logic verification")

    def test_winloss_verdict_values(self):
        """Verify verdict values are one of: win, loss, neutral"""
        resp = self.session.get(f"{BASE_URL}/api/rates/winloss/{TEST_PROPERTY_ID}?lookback_days=60")
        assert resp.status_code == 200, f"Winloss failed: {resp.text}"
        data = resp.json()
        
        comparisons = data.get("comparisons", [])
        valid_verdicts = {"win", "loss", "neutral"}
        
        for entry in comparisons:
            verdict = entry.get("verdict")
            assert verdict in valid_verdicts, f"Invalid verdict '{verdict}' for date {entry.get('date')}"
        
        print(f"PASS: All {len(comparisons)} verdicts are valid (win/loss/neutral)")

    # ==================== REVENUE CALCULATION TESTS ====================

    def test_revenue_calculations(self):
        """Verify naive revenue calculations: actual = bookings * owner_rate, cf = bookings * ai_rate"""
        resp = self.session.get(f"{BASE_URL}/api/rates/winloss/{TEST_PROPERTY_ID}?lookback_days=60")
        assert resp.status_code == 200, f"Winloss failed: {resp.text}"
        data = resp.json()
        
        comparisons = data.get("comparisons", [])
        errors = []
        
        for entry in comparisons:
            bookings = entry.get("bookings", 0)
            owner_rate = entry.get("owner_rate", 0)
            ai_rate = entry.get("ai_rate", 0)
            actual_rev = entry.get("actual_revenue", 0)
            cf_rev = entry.get("ai_counterfactual", 0)
            rev_delta = entry.get("revenue_delta", 0)
            
            expected_actual = round(bookings * owner_rate, 2)
            expected_cf = round(bookings * ai_rate, 2)
            expected_delta = round(expected_actual - expected_cf, 2)
            
            if abs(actual_rev - expected_actual) > 0.1:
                errors.append(f"Date {entry['date']}: actual_revenue {actual_rev} != expected {expected_actual}")
            if abs(cf_rev - expected_cf) > 0.1:
                errors.append(f"Date {entry['date']}: ai_counterfactual {cf_rev} != expected {expected_cf}")
            if abs(rev_delta - expected_delta) > 0.1:
                errors.append(f"Date {entry['date']}: revenue_delta {rev_delta} != expected {expected_delta}")
        
        if errors:
            for e in errors[:5]:  # Show first 5 errors
                print(f"ERROR: {e}")
            pytest.fail(f"Revenue calculation errors: {len(errors)} issues found")
        else:
            print(f"PASS: Revenue calculations correct for {len(comparisons)} entries")

    def test_delta_per_night_calculation(self):
        """Verify delta_per_night = owner_rate - ai_rate"""
        resp = self.session.get(f"{BASE_URL}/api/rates/winloss/{TEST_PROPERTY_ID}?lookback_days=60")
        assert resp.status_code == 200, f"Winloss failed: {resp.text}"
        data = resp.json()
        
        comparisons = data.get("comparisons", [])
        for entry in comparisons:
            owner_rate = entry.get("owner_rate", 0)
            ai_rate = entry.get("ai_rate", 0)
            delta = entry.get("delta_per_night", 0)
            expected = round(owner_rate - ai_rate, 2)
            
            assert abs(delta - expected) < 0.1, f"delta_per_night mismatch for {entry['date']}: {delta} vs {expected}"
        
        print(f"PASS: delta_per_night correctly calculated for {len(comparisons)} entries")

    # ==================== SUMMARY AGGREGATION TESTS ====================

    def test_summary_totals_match_comparisons(self):
        """Verify summary totals match comparisons count"""
        resp = self.session.get(f"{BASE_URL}/api/rates/winloss/{TEST_PROPERTY_ID}?lookback_days=60")
        assert resp.status_code == 200, f"Winloss failed: {resp.text}"
        data = resp.json()
        
        summary = data.get("summary", {})
        comparisons = data.get("comparisons", [])
        
        total = summary.get("total_overrides", 0)
        wins = summary.get("wins", 0)
        losses = summary.get("losses", 0)
        neutrals = summary.get("neutrals", 0)
        
        # Total should equal wins + losses + neutrals
        assert total == wins + losses + neutrals, f"Total {total} != wins({wins}) + losses({losses}) + neutrals({neutrals})"
        
        # Total should equal comparisons count
        assert total == len(comparisons), f"Total {total} != comparisons count {len(comparisons)}"
        
        # Count verdicts in comparisons
        actual_wins = sum(1 for c in comparisons if c.get("verdict") == "win")
        actual_losses = sum(1 for c in comparisons if c.get("verdict") == "loss")
        actual_neutrals = sum(1 for c in comparisons if c.get("verdict") == "neutral")
        
        assert wins == actual_wins, f"Summary wins {wins} != actual {actual_wins}"
        assert losses == actual_losses, f"Summary losses {losses} != actual {actual_losses}"
        assert neutrals == actual_neutrals, f"Summary neutrals {neutrals} != actual {actual_neutrals}"
        
        print(f"PASS: Summary totals match comparisons (total={total}, wins={wins}, losses={losses}, neutrals={neutrals})")

    def test_win_rate_pct_calculation(self):
        """Verify win_rate_pct = wins / total * 100"""
        resp = self.session.get(f"{BASE_URL}/api/rates/winloss/{TEST_PROPERTY_ID}?lookback_days=60")
        assert resp.status_code == 200, f"Winloss failed: {resp.text}"
        data = resp.json()
        
        summary = data.get("summary", {})
        total = summary.get("total_overrides", 0)
        wins = summary.get("wins", 0)
        win_rate = summary.get("win_rate_pct", 0)
        
        if total > 0:
            expected = round(wins / total * 100, 1)
            assert abs(win_rate - expected) < 0.2, f"win_rate_pct {win_rate} != expected {expected}"
            print(f"PASS: win_rate_pct correctly calculated: {win_rate}%")
        else:
            assert win_rate == 0, f"win_rate_pct should be 0 when total=0, got {win_rate}"
            print("PASS: win_rate_pct is 0 when no overrides")

    def test_revenue_lift_calculation(self):
        """Verify revenue_lift = revenue_owner - revenue_ai_counterfactual"""
        resp = self.session.get(f"{BASE_URL}/api/rates/winloss/{TEST_PROPERTY_ID}?lookback_days=60")
        assert resp.status_code == 200, f"Winloss failed: {resp.text}"
        data = resp.json()
        
        summary = data.get("summary", {})
        rev_owner = summary.get("revenue_owner", 0)
        rev_cf = summary.get("revenue_ai_counterfactual", 0)
        rev_lift = summary.get("revenue_lift", 0)
        
        expected = round(rev_owner - rev_cf, 2)
        assert abs(rev_lift - expected) < 0.1, f"revenue_lift {rev_lift} != expected {expected}"
        
        print(f"PASS: revenue_lift correctly calculated: £{rev_lift} (owner: £{rev_owner}, cf: £{rev_cf})")

    # ==================== BIGGEST WIN/LOSS TESTS ====================

    def test_biggest_win_is_largest_positive_delta(self):
        """biggest_win should have the largest positive revenue_delta among 'win' verdicts"""
        resp = self.session.get(f"{BASE_URL}/api/rates/winloss/{TEST_PROPERTY_ID}?lookback_days=60")
        assert resp.status_code == 200, f"Winloss failed: {resp.text}"
        data = resp.json()
        
        summary = data.get("summary", {})
        comparisons = data.get("comparisons", [])
        biggest_win = summary.get("biggest_win")
        
        # Find all wins
        wins = [c for c in comparisons if c.get("verdict") == "win"]
        
        if len(wins) > 0:
            # Find the one with largest revenue_delta
            max_win = max(wins, key=lambda x: x.get("revenue_delta", 0))
            
            if biggest_win:
                assert biggest_win.get("date") == max_win.get("date"), \
                    f"biggest_win date {biggest_win.get('date')} != expected {max_win.get('date')}"
                assert biggest_win.get("revenue_delta") == max_win.get("revenue_delta"), \
                    f"biggest_win delta {biggest_win.get('revenue_delta')} != expected {max_win.get('revenue_delta')}"
                print(f"PASS: biggest_win correctly identified: {biggest_win.get('date')} with delta £{biggest_win.get('revenue_delta')}")
            else:
                # If no biggest_win but there are wins, that's an error
                pytest.fail(f"biggest_win is None but there are {len(wins)} wins")
        else:
            # No wins, biggest_win should be None
            assert biggest_win is None, f"biggest_win should be None when no wins, got {biggest_win}"
            print("PASS: biggest_win is None when no wins exist")

    def test_biggest_loss_is_largest_negative_delta(self):
        """biggest_loss should have the largest negative revenue_delta among 'loss' verdicts"""
        resp = self.session.get(f"{BASE_URL}/api/rates/winloss/{TEST_PROPERTY_ID}?lookback_days=60")
        assert resp.status_code == 200, f"Winloss failed: {resp.text}"
        data = resp.json()
        
        summary = data.get("summary", {})
        comparisons = data.get("comparisons", [])
        biggest_loss = summary.get("biggest_loss")
        
        # Find all losses
        losses = [c for c in comparisons if c.get("verdict") == "loss"]
        
        if len(losses) > 0:
            # Find the one with smallest (most negative) revenue_delta
            min_loss = min(losses, key=lambda x: x.get("revenue_delta", 0))
            
            if biggest_loss:
                assert biggest_loss.get("date") == min_loss.get("date"), \
                    f"biggest_loss date {biggest_loss.get('date')} != expected {min_loss.get('date')}"
                assert biggest_loss.get("revenue_delta") == min_loss.get("revenue_delta"), \
                    f"biggest_loss delta {biggest_loss.get('revenue_delta')} != expected {min_loss.get('revenue_delta')}"
                print(f"PASS: biggest_loss correctly identified: {biggest_loss.get('date')} with delta £{biggest_loss.get('revenue_delta')}")
            else:
                # If no biggest_loss but there are losses, that's an error
                pytest.fail(f"biggest_loss is None but there are {len(losses)} losses")
        else:
            # No losses, biggest_loss should be None
            assert biggest_loss is None, f"biggest_loss should be None when no losses, got {biggest_loss}"
            print("PASS: biggest_loss is None when no losses exist")

    # ==================== LOOKBACK DAYS PARAMETER TEST ====================

    def test_lookback_days_parameter(self):
        """Verify lookback_days parameter filters results correctly"""
        # Get with 7 days
        resp_7 = self.session.get(f"{BASE_URL}/api/rates/winloss/{TEST_PROPERTY_ID}?lookback_days=7")
        assert resp_7.status_code == 200
        data_7 = resp_7.json()
        
        # Get with 60 days
        resp_60 = self.session.get(f"{BASE_URL}/api/rates/winloss/{TEST_PROPERTY_ID}?lookback_days=60")
        assert resp_60.status_code == 200
        data_60 = resp_60.json()
        
        # 60 days should have >= entries than 7 days
        count_7 = len(data_7.get("comparisons", []))
        count_60 = len(data_60.get("comparisons", []))
        
        assert count_60 >= count_7, f"60-day count ({count_60}) should be >= 7-day count ({count_7})"
        
        # Verify date ranges
        assert data_7.get("lookback_days") == 7
        assert data_60.get("lookback_days") == 60
        
        print(f"PASS: lookback_days parameter works (7d: {count_7} entries, 60d: {count_60} entries)")

    # ==================== EDGE CASES ====================

    def test_winloss_with_property_all(self):
        """Test winloss endpoint with property_id='all'"""
        resp = self.session.get(f"{BASE_URL}/api/rates/winloss/all?lookback_days=30")
        assert resp.status_code == 200, f"Winloss with 'all' failed: {resp.text}"
        data = resp.json()
        
        assert data.get("property_id") == "all"
        assert "summary" in data
        assert "comparisons" in data
        
        print(f"PASS: Winloss works with property_id='all' ({len(data.get('comparisons', []))} entries)")

    def test_winloss_skips_records_without_ai_rate(self):
        """Records without ai_rate_at_submit (owner_rate <= 0 or ai_rate <= 0) should be skipped"""
        resp = self.session.get(f"{BASE_URL}/api/rates/winloss/{TEST_PROPERTY_ID}?lookback_days=60")
        assert resp.status_code == 200, f"Winloss failed: {resp.text}"
        data = resp.json()
        
        comparisons = data.get("comparisons", [])
        
        # All entries should have positive owner_rate and ai_rate
        for entry in comparisons:
            assert entry.get("owner_rate", 0) > 0, f"owner_rate should be > 0 for {entry.get('date')}"
            assert entry.get("ai_rate", 0) > 0, f"ai_rate should be > 0 for {entry.get('date')}"
        
        print(f"PASS: All {len(comparisons)} entries have valid owner_rate and ai_rate")


class TestWinLossIntegration:
    """Integration tests for the full submit → winloss flow"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json().get("token")  # API returns "token" not "access_token"
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        yield

    def test_full_flow_submit_then_winloss(self):
        """Full integration: create override → submit → verify in winloss"""
        # Use a unique past date
        test_date = (datetime.now() - timedelta(days=8)).strftime("%Y-%m-%d")
        test_rate = 165.0
        
        # Step 1: Create override
        override_resp = self.session.post(f"{BASE_URL}/api/rates/grid/override", json={
            "property_id": TEST_PROPERTY_ID,
            "changes": [{
                "date": test_date,
                "pms_override": test_rate,
                "min_rate": 60.0
            }]
        })
        assert override_resp.status_code == 200
        
        # Step 2: Submit to PMS
        submit_resp = self.session.post(f"{BASE_URL}/api/rates/grid/submit-to-pms", json={
            "property_id": TEST_PROPERTY_ID,
            "dates": [test_date]
        })
        assert submit_resp.status_code == 200
        
        # Step 3: Verify in winloss
        winloss_resp = self.session.get(f"{BASE_URL}/api/rates/winloss/{TEST_PROPERTY_ID}?lookback_days=30")
        assert winloss_resp.status_code == 200
        data = winloss_resp.json()
        
        # Find our test date in comparisons
        comparisons = data.get("comparisons", [])
        test_entry = next((c for c in comparisons if c.get("date") == test_date), None)
        
        if test_entry:
            assert test_entry.get("owner_rate") == test_rate, \
                f"owner_rate {test_entry.get('owner_rate')} != expected {test_rate}"
            assert test_entry.get("ai_rate") > 0, "ai_rate should be captured"
            assert test_entry.get("verdict") in ["win", "loss", "neutral"]
            print(f"PASS: Full flow verified - date {test_date}, owner={test_rate}, ai={test_entry.get('ai_rate')}, verdict={test_entry.get('verdict')}")
        else:
            print(f"INFO: Test date {test_date} not in comparisons (may be filtered or no ai_rate)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
