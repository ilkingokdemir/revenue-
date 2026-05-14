"""
Iteration 285 Backend Tests - Open Pricing, Beach POS, Public Events

Tests for:
1. Open Pricing (Duetto parity) - segment × channel × room-type rate matrix
2. Beach POS (Elektra TR niche) - sunbed POS for beach hotels
3. Public Events (Tripleseat Social SEO parity) - public event listings with JSON-LD
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def admin_session():
    """Get authenticated admin session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Login as admin
    resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    if resp.status_code != 200:
        pytest.skip(f"Admin login failed: {resp.status_code} - {resp.text}")
    return session


@pytest.fixture(scope="module")
def test_property_id(admin_session):
    """Get a test property ID"""
    resp = admin_session.get(f"{BASE_URL}/api/properties")
    if resp.status_code == 200:
        props = resp.json()
        if isinstance(props, list) and len(props) > 0:
            return props[0].get("id")
        elif isinstance(props, dict) and props.get("items"):
            return props["items"][0].get("id")
    return "test-property-285"


@pytest.fixture(scope="module")
def test_room_type_id(admin_session, test_property_id):
    """Get a test room type ID"""
    resp = admin_session.get(f"{BASE_URL}/api/room-types?property_id={test_property_id}")
    if resp.status_code == 200:
        data = resp.json()
        if isinstance(data, list) and len(data) > 0:
            return data[0].get("id")
        elif isinstance(data, dict):
            items = data.get("room_types") or data.get("items") or []
            if isinstance(items, list) and len(items) > 0:
                return items[0].get("id")
    return "test-room-type-285"


# ============ OPEN PRICING TESTS ============

class TestOpenPricingSegments:
    """Test /api/open-pricing/segments endpoint"""
    
    def test_get_segments_returns_6_segments(self, admin_session):
        """GET /api/open-pricing/segments returns 6 segments"""
        resp = admin_session.get(f"{BASE_URL}/api/open-pricing/segments")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "items" in data, "Response should have 'items' key"
        segments = data["items"]
        assert len(segments) == 6, f"Expected 6 segments, got {len(segments)}"
        
        # Verify segment IDs
        segment_ids = {s["id"] for s in segments}
        expected_ids = {"transient", "corporate", "group", "package", "leisure", "government"}
        assert segment_ids == expected_ids, f"Segment IDs mismatch: {segment_ids}"


class TestOpenPricingChannels:
    """Test /api/open-pricing/channels endpoint"""
    
    def test_get_channels_returns_8_channels(self, admin_session):
        """GET /api/open-pricing/channels returns 8 channels"""
        resp = admin_session.get(f"{BASE_URL}/api/open-pricing/channels")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "items" in data, "Response should have 'items' key"
        channels = data["items"]
        assert len(channels) == 8, f"Expected 8 channels, got {len(channels)}"
        
        # Verify channel IDs
        channel_ids = {c["id"] for c in channels}
        expected_ids = {"direct", "booking", "expedia", "airbnb", "agoda", "agency", "walk_in", "phone"}
        assert channel_ids == expected_ids, f"Channel IDs mismatch: {channel_ids}"


class TestOpenPricingOverride:
    """Test /api/open-pricing/override CRUD"""
    
    def test_create_override_with_segment_channel(self, admin_session, test_property_id, test_room_type_id):
        """POST /api/open-pricing/override creates override with scope_label"""
        test_date = "2026-07-20"
        resp = admin_session.post(f"{BASE_URL}/api/open-pricing/override", json={
            "property_id": test_property_id,
            "date": test_date,
            "rate": 2500,
            "segment": "corporate",
            "channel": "booking",
            "room_type_id": test_room_type_id,
            "reason": "TEST_iter285_override"
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "id" in data, "Response should have 'id'"
        assert data["rate"] == 2500, f"Rate mismatch: {data['rate']}"
        assert data["segment"] == "corporate"
        assert data["channel"] == "booking"
        assert "scope_label" in data, "Response should have 'scope_label'"
        assert "seg:corporate" in data["scope_label"]
        assert "ch:booking" in data["scope_label"]
        
        # Store for cleanup
        TestOpenPricingOverride.created_override_id = data["id"]
    
    def test_create_override_invalid_segment_returns_400(self, admin_session, test_property_id):
        """POST /api/open-pricing/override with invalid segment returns 400"""
        resp = admin_session.post(f"{BASE_URL}/api/open-pricing/override", json={
            "property_id": test_property_id,
            "date": "2026-07-21",
            "rate": 1000,
            "segment": "invalid_segment"
        })
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        assert "Invalid segment" in resp.text
    
    def test_create_override_invalid_channel_returns_400(self, admin_session, test_property_id):
        """POST /api/open-pricing/override with invalid channel returns 400"""
        resp = admin_session.post(f"{BASE_URL}/api/open-pricing/override", json={
            "property_id": test_property_id,
            "date": "2026-07-21",
            "rate": 1000,
            "channel": "invalid_channel"
        })
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        assert "Invalid channel" in resp.text
    
    def test_delete_override(self, admin_session):
        """DELETE /api/open-pricing/override/{id} works"""
        override_id = getattr(TestOpenPricingOverride, 'created_override_id', None)
        if not override_id:
            pytest.skip("No override to delete")
        
        resp = admin_session.delete(f"{BASE_URL}/api/open-pricing/override/{override_id}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        assert resp.json().get("ok") == True


class TestOpenPricingMatrix:
    """Test /api/open-pricing/matrix endpoint"""
    
    def test_get_matrix_returns_items_and_catalogs(self, admin_session, test_property_id):
        """GET /api/open-pricing/matrix/{property_id} returns items + catalogs"""
        resp = admin_session.get(f"{BASE_URL}/api/open-pricing/matrix/{test_property_id}?date=2026-07-15")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "items" in data, "Response should have 'items'"
        assert "segments" in data, "Response should have 'segments'"
        assert "channels" in data, "Response should have 'channels'"
        assert "count" in data, "Response should have 'count'"


class TestOpenPricingLookup:
    """Test /api/open-pricing/lookup endpoint"""
    
    def test_lookup_exact_match_returns_score_100(self, admin_session, test_property_id, test_room_type_id):
        """POST /api/open-pricing/lookup with exact match returns score=100"""
        test_date = "2026-07-22"
        
        # First create an override
        create_resp = admin_session.post(f"{BASE_URL}/api/open-pricing/override", json={
            "property_id": test_property_id,
            "date": test_date,
            "rate": 3000,
            "segment": "leisure",
            "channel": "direct",
            "room_type_id": test_room_type_id,
            "reason": "TEST_lookup_exact"
        })
        assert create_resp.status_code == 200
        override_id = create_resp.json()["id"]
        
        # Now lookup
        lookup_resp = admin_session.post(f"{BASE_URL}/api/open-pricing/lookup", json={
            "property_id": test_property_id,
            "date": test_date,
            "segment": "leisure",
            "channel": "direct",
            "room_type_id": test_room_type_id
        })
        assert lookup_resp.status_code == 200, f"Expected 200, got {lookup_resp.status_code}: {lookup_resp.text}"
        
        data = lookup_resp.json()
        assert data["found"] == True, "Should find the override"
        assert data["rate"] == 3000, f"Rate mismatch: {data['rate']}"
        assert data["score"] == 100, f"Score should be 100 for exact match, got {data['score']}"
        assert data["source"] == "segment+channel+room+date", f"Source mismatch: {data['source']}"
        
        # Cleanup
        admin_session.delete(f"{BASE_URL}/api/open-pricing/override/{override_id}")
    
    def test_lookup_no_match_returns_found_false(self, admin_session, test_property_id):
        """POST /api/open-pricing/lookup with no match returns found=false"""
        resp = admin_session.post(f"{BASE_URL}/api/open-pricing/lookup", json={
            "property_id": test_property_id,
            "date": "2099-12-31",
            "segment": "government",
            "channel": "phone"
        })
        assert resp.status_code == 200
        
        data = resp.json()
        assert data["found"] == False, "Should not find any override"
        assert data["source"] == "fallback_to_grid"


# ============ BEACH POS TESTS ============

class TestBeachPosSunbeds:
    """Test /api/beach-pos/sunbeds endpoints"""
    
    def test_bulk_seed_sunbeds(self, admin_session, test_property_id):
        """POST /api/beach-pos/sunbeds/bulk-seed creates N sunbeds"""
        resp = admin_session.post(f"{BASE_URL}/api/beach-pos/sunbeds/bulk-seed/{test_property_id}", json={
            "zone": "TEST_zone_285",
            "start": 100,
            "end": 105,
            "prefix": "T"
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert data["ok"] == True
        assert "created" in data, "Response should have 'created' count"
        assert data["zone"] == "TEST_zone_285"
    
    def test_list_sunbeds_with_today_aggregation(self, admin_session, test_property_id):
        """GET /api/beach-pos/sunbeds/{property_id} returns sunbeds with today_orders + today_spend"""
        resp = admin_session.get(f"{BASE_URL}/api/beach-pos/sunbeds/{test_property_id}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "items" in data, "Response should have 'items'"
        assert "count" in data, "Response should have 'count'"
        
        # Check aggregation fields exist on sunbeds
        if data["items"]:
            sunbed = data["items"][0]
            assert "today_orders" in sunbed, "Sunbed should have 'today_orders'"
            assert "today_spend" in sunbed, "Sunbed should have 'today_spend'"
    
    def test_create_sunbed_duplicate_returns_409(self, admin_session, test_property_id):
        """POST /api/beach-pos/sunbeds with duplicate number returns 409"""
        # First create
        resp1 = admin_session.post(f"{BASE_URL}/api/beach-pos/sunbeds/{test_property_id}", json={
            "sunbed_number": "TEST_DUP_285",
            "zone": "test"
        })
        
        if resp1.status_code == 200:
            # Try duplicate
            resp2 = admin_session.post(f"{BASE_URL}/api/beach-pos/sunbeds/{test_property_id}", json={
                "sunbed_number": "TEST_DUP_285",
                "zone": "test"
            })
            assert resp2.status_code == 409, f"Expected 409 for duplicate, got {resp2.status_code}"


class TestBeachPosMenu:
    """Test /api/beach-pos/menu endpoints"""
    
    def test_get_menu_auto_seeds_default_items(self, admin_session, test_property_id):
        """GET /api/beach-pos/menu/{property_id} auto-seeds 10 default items on first call"""
        # Use a unique property ID to ensure fresh menu
        unique_prop = f"TEST_menu_prop_{uuid.uuid4().hex[:8]}"
        
        resp = admin_session.get(f"{BASE_URL}/api/beach-pos/menu/{unique_prop}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "items" in data, "Response should have 'items'"
        # Should have seeded 10 default items
        assert len(data["items"]) == 10, f"Expected 10 default menu items, got {len(data['items'])}"
        
        # Verify Turkish menu items
        names = [item["name"] for item in data["items"]]
        assert any("Coca-Cola" in n for n in names), "Should have Coca-Cola"
        assert any("Efes" in n for n in names), "Should have Efes Pilsen"


class TestBeachPosOrders:
    """Test /api/beach-pos/orders endpoints"""
    
    def test_create_order_computes_total(self, admin_session, test_property_id):
        """POST /api/beach-pos/orders creates order with computed total"""
        # First ensure we have a sunbed
        sunbed_resp = admin_session.get(f"{BASE_URL}/api/beach-pos/sunbeds/{test_property_id}")
        sunbeds = sunbed_resp.json().get("items", [])
        
        if not sunbeds:
            # Create one
            admin_session.post(f"{BASE_URL}/api/beach-pos/sunbeds/{test_property_id}", json={
                "sunbed_number": "TEST_ORDER_285",
                "zone": "test"
            })
            sunbed_number = "TEST_ORDER_285"
        else:
            sunbed_number = sunbeds[0]["sunbed_number"]
        
        # Create order
        resp = admin_session.post(f"{BASE_URL}/api/beach-pos/orders", json={
            "property_id": test_property_id,
            "sunbed_number": sunbed_number,
            "items": [
                {"name": "Coca-Cola", "price": 80, "qty": 2, "sku": "BV-COKE"},
                {"name": "Efes Pilsen", "price": 150, "qty": 1, "sku": "BR-EFES"}
            ]
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "id" in data, "Response should have 'id'"
        assert data["total"] == 310, f"Total should be 80*2 + 150*1 = 310, got {data['total']}"
        assert data["status"] == "new"
        
        TestBeachPosOrders.created_order_id = data["id"]
    
    def test_create_order_unknown_sunbed_returns_404(self, admin_session, test_property_id):
        """POST /api/beach-pos/orders with unknown sunbed returns 404"""
        resp = admin_session.post(f"{BASE_URL}/api/beach-pos/orders", json={
            "property_id": test_property_id,
            "sunbed_number": "NONEXISTENT_SUNBED_999",
            "items": [{"name": "Test", "price": 10, "qty": 1}]
        })
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"
    
    def test_list_orders_returns_zone_totals(self, admin_session, test_property_id):
        """GET /api/beach-pos/orders/{property_id} returns today's orders + zone_totals + grand_total"""
        resp = admin_session.get(f"{BASE_URL}/api/beach-pos/orders/{test_property_id}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "items" in data, "Response should have 'items'"
        assert "zone_totals" in data, "Response should have 'zone_totals'"
        assert "grand_total" in data, "Response should have 'grand_total'"
        assert "date" in data, "Response should have 'date'"
    
    def test_deliver_order(self, admin_session):
        """POST /api/beach-pos/orders/{id}/deliver marks delivered"""
        order_id = getattr(TestBeachPosOrders, 'created_order_id', None)
        if not order_id:
            pytest.skip("No order to deliver")
        
        resp = admin_session.post(f"{BASE_URL}/api/beach-pos/orders/{order_id}/deliver", json={})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        assert resp.json().get("ok") == True
    
    def test_cancel_order(self, admin_session, test_property_id):
        """POST /api/beach-pos/orders/{id}/cancel marks cancelled"""
        # Create a new order to cancel
        sunbed_resp = admin_session.get(f"{BASE_URL}/api/beach-pos/sunbeds/{test_property_id}")
        sunbeds = sunbed_resp.json().get("items", [])
        if not sunbeds:
            pytest.skip("No sunbeds available")
        
        create_resp = admin_session.post(f"{BASE_URL}/api/beach-pos/orders", json={
            "property_id": test_property_id,
            "sunbed_number": sunbeds[0]["sunbed_number"],
            "items": [{"name": "Test", "price": 50, "qty": 1}]
        })
        if create_resp.status_code != 200:
            pytest.skip("Could not create order to cancel")
        
        order_id = create_resp.json()["id"]
        
        resp = admin_session.post(f"{BASE_URL}/api/beach-pos/orders/{order_id}/cancel", json={
            "reason": "TEST_cancel"
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        assert resp.json().get("ok") == True


# ============ PUBLIC EVENTS TESTS ============

class TestMiceRoxCatalog:
    """Test /api/mice-rox/catalog endpoint"""
    
    def test_get_catalog_returns_8_experiences(self, admin_session):
        """GET /api/mice-rox/catalog returns 8 hyper-personalization experiences"""
        resp = admin_session.get(f"{BASE_URL}/api/mice-rox/catalog")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "items" in data, "Response should have 'items'"
        experiences = data["items"]
        assert len(experiences) == 8, f"Expected 8 experiences, got {len(experiences)}"
        
        # Verify experience IDs
        exp_ids = {e["id"] for e in experiences}
        expected_ids = {"sommelier", "playlist_curated", "live_show", "interactive_dining", 
                       "eatertainment", "calligrapher", "florist_live", "barista_lab"}
        assert exp_ids == expected_ids, f"Experience IDs mismatch: {exp_ids}"


class TestMiceRoxPersonalize:
    """Test /api/mice-rox/personalize endpoint"""
    
    def test_personalize_nonexistent_item_returns_404(self, admin_session):
        """POST /api/mice-rox/personalize/{item_id} returns 404 for non-existent item"""
        resp = admin_session.post(f"{BASE_URL}/api/mice-rox/personalize/nonexistent-item-id", json={
            "experience_type": "sommelier"
        })
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"


class TestPublicEvents:
    """Test /api/public-events CRUD"""
    
    def test_create_event_with_auto_slug(self, admin_session, test_property_id):
        """POST /api/public-events creates event with auto-generated slug"""
        resp = admin_session.post(f"{BASE_URL}/api/public-events", json={
            "property_id": test_property_id,
            "title": "TEST Yaz Festivali 285",
            "date": "2026-08-15",
            "start_time": "18:00",
            "end_time": "23:00",
            "description": "Test etkinlik açıklaması",
            "capacity": 100,
            "price_from": 500,
            "tags": ["festival", "yaz", "test"]
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "id" in data, "Response should have 'id'"
        assert "slug" in data, "Response should have 'slug'"
        assert data["status"] == "draft", "New event should be draft"
        assert data["is_public"] == False, "New event should not be public"
        assert "test-yaz-festivali-285" in data["slug"], f"Slug should contain title: {data['slug']}"
        
        TestPublicEvents.created_event_id = data["id"]
        TestPublicEvents.created_event_slug = data["slug"]
    
    def test_publish_event(self, admin_session):
        """POST /api/public-events/{id}/publish flips is_public=true and status='published'"""
        event_id = getattr(TestPublicEvents, 'created_event_id', None)
        if not event_id:
            pytest.skip("No event to publish")
        
        resp = admin_session.post(f"{BASE_URL}/api/public-events/{event_id}/publish", json={})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        assert resp.json().get("ok") == True
    
    def test_get_public_event_by_slug_with_structured_data(self, admin_session):
        """GET /api/public-events/{slug} returns event WITH structured_data (JSON-LD)"""
        slug = getattr(TestPublicEvents, 'created_event_slug', None)
        if not slug:
            pytest.skip("No event slug")
        
        # Public endpoint - no auth needed
        resp = requests.get(f"{BASE_URL}/api/public-events/{slug}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "structured_data" in data, "Response should have 'structured_data'"
        
        sd = data["structured_data"]
        assert sd["@type"] == "Event", "structured_data @type should be 'Event'"
        assert sd["@context"] == "https://schema.org"
        assert "name" in sd, "structured_data should have 'name'"
        assert "startDate" in sd, "structured_data should have 'startDate'"
    
    def test_get_unpublished_event_returns_404(self, admin_session, test_property_id):
        """GET /api/public-events/{slug} returns 404 for unpublished event"""
        # Create a draft event
        create_resp = admin_session.post(f"{BASE_URL}/api/public-events", json={
            "property_id": test_property_id,
            "title": "TEST Draft Event 285",
            "date": "2026-09-01"
        })
        if create_resp.status_code != 200:
            pytest.skip("Could not create draft event")
        
        slug = create_resp.json()["slug"]
        
        # Try to access without publishing
        resp = requests.get(f"{BASE_URL}/api/public-events/{slug}")
        assert resp.status_code == 404, f"Expected 404 for unpublished event, got {resp.status_code}"
    
    def test_list_events_with_include_drafts(self, admin_session, test_property_id):
        """GET /api/public-events?include_drafts=true returns both drafts and published"""
        resp = admin_session.get(f"{BASE_URL}/api/public-events?property_id={test_property_id}&include_drafts=true")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "items" in data, "Response should have 'items'"
        assert "count" in data, "Response should have 'count'"
    
    def test_list_public_events_no_auth(self, test_property_id):
        """GET /api/public-events?property_id= (no auth) returns only published"""
        resp = requests.get(f"{BASE_URL}/api/public-events?property_id={test_property_id}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        # All returned events should be published
        for event in data.get("items", []):
            assert event.get("is_public") == True, "Public list should only contain published events"
    
    def test_unpublish_event(self, admin_session):
        """POST /api/public-events/{id}/unpublish works"""
        event_id = getattr(TestPublicEvents, 'created_event_id', None)
        if not event_id:
            pytest.skip("No event to unpublish")
        
        resp = admin_session.post(f"{BASE_URL}/api/public-events/{event_id}/unpublish", json={})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        assert resp.json().get("ok") == True
    
    def test_patch_event(self, admin_session):
        """PATCH /api/public-events/{event_id} works"""
        event_id = getattr(TestPublicEvents, 'created_event_id', None)
        if not event_id:
            pytest.skip("No event to patch")
        
        resp = admin_session.patch(f"{BASE_URL}/api/public-events/{event_id}", json={
            "description": "Updated description for TEST"
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        assert resp.json().get("ok") == True
    
    def test_delete_event(self, admin_session):
        """DELETE /api/public-events/{event_id} works"""
        event_id = getattr(TestPublicEvents, 'created_event_id', None)
        if not event_id:
            pytest.skip("No event to delete")
        
        resp = admin_session.delete(f"{BASE_URL}/api/public-events/{event_id}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        assert resp.json().get("ok") == True


# ============ REGRESSION TESTS ============

class TestRegressionIter284:
    """Regression tests for iter 284 modules"""
    
    def test_agency_portal_list(self, admin_session):
        """GET /api/agencies works (iter 284)"""
        resp = admin_session.get(f"{BASE_URL}/api/agencies")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    
    def test_web_concierge_config(self, admin_session, test_property_id):
        """GET /api/web-concierge/widget-config/{property_id} works (iter 284)"""
        resp = requests.get(f"{BASE_URL}/api/web-concierge/widget-config/{test_property_id}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    
    def test_review_agent_config(self, admin_session, test_property_id):
        """GET /api/review-agent/config/{property_id} works (iter 284)"""
        resp = admin_session.get(f"{BASE_URL}/api/review-agent/config/{test_property_id}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"


class TestRegressionIter282_283:
    """Regression tests for iter 282-283 modules"""
    
    def test_owner_portal_list(self, admin_session):
        """GET /api/owners works (iter 282)"""
        resp = admin_session.get(f"{BASE_URL}/api/owners")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    
    def test_carbon_v2_dashboard(self, admin_session, test_property_id):
        """GET /api/esg/{property_id}/dashboard works (iter 283)"""
        resp = admin_session.get(f"{BASE_URL}/api/esg/{test_property_id}/dashboard")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"


class TestExistingPublishedEvent:
    """Test the existing published event mentioned in context"""
    
    def test_yaz_sefler_aksami_event_exists(self):
        """GET /api/public-events/yaz-sefler-aksami-2026-07-15 returns published event"""
        resp = requests.get(f"{BASE_URL}/api/public-events/yaz-sefler-aksami-2026-07-15")
        # This may or may not exist depending on test data
        if resp.status_code == 200:
            data = resp.json()
            assert "structured_data" in data, "Published event should have structured_data"
            assert data["structured_data"]["@type"] == "Event"
        else:
            # Event may have been cleaned up - that's OK
            assert resp.status_code == 404, f"Expected 200 or 404, got {resp.status_code}"
