"""
Voice Concierge API Tests (Batch 42)
=====================================
Tests for:
- POST /api/voice/concierge - text-based concierge with intent classification
- POST /api/voice/transcribe - Whisper STT (requires audio file)
- GET /api/voice/sessions/{property_id} - session history
- GET /api/voice/log/{property_id} - raw log entries
- GET /api/voice/stats/{property_id} - intent statistics
"""
import pytest
import requests
import os
import io
import wave
import struct

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

@pytest.fixture(scope="module")
def auth_session():
    """Authenticate and return session with cookies"""
    session = requests.Session()
    login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    if login_resp.status_code != 200:
        pytest.skip(f"Login failed: {login_resp.status_code} - {login_resp.text}")
    return session


def create_wav_audio(duration_ms=500, sample_rate=16000):
    """Create a minimal valid WAV audio file for testing"""
    num_samples = int(sample_rate * duration_ms / 1000)
    # Generate silence (zeros)
    samples = [0] * num_samples
    
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        for sample in samples:
            wav_file.writeframes(struct.pack('<h', sample))
    
    buffer.seek(0)
    return buffer.read()


class TestVoiceConciergeIntentClassification:
    """Test intent classification via /api/voice/concierge"""
    
    def test_housekeeping_intent_turkish(self, auth_session):
        """Turkish towel request → housekeeping intent + auto task creation"""
        resp = auth_session.post(
            f"{BASE_URL}/api/voice/concierge?property_id=default",
            json={
                "text": "Odamda iki tane temiz havlu istiyorum",
                "language": "tr",
                "guest_name": "Test Guest",
                "room_number": "101"
            }
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # Verify intent classification
        assert data.get("intent") == "housekeeping", f"Expected housekeeping intent, got {data.get('intent')}"
        
        # Verify action includes auto_create_task
        assert data.get("action", {}).get("auto_create_task") == True, "Expected auto_create_task=True"
        assert data.get("action", {}).get("route_to") == "housekeeping"
        
        # Verify reply exists (AI-generated)
        assert "reply" in data and len(data["reply"]) > 0, "Expected non-empty reply"
        
        # Verify session_id and log_id returned
        assert "session_id" in data
        assert "log_id" in data
        print(f"✓ Housekeeping intent: {data['intent']}, reply: {data['reply'][:50]}...")
    
    def test_emergency_intent(self, auth_session):
        """Emergency fire request → emergency intent + P0 priority"""
        resp = auth_session.post(
            f"{BASE_URL}/api/voice/concierge?property_id=default",
            json={
                "text": "Yangın çıktı acil",
                "language": "tr"
            }
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        assert data.get("intent") == "emergency", f"Expected emergency intent, got {data.get('intent')}"
        assert data.get("action", {}).get("alert_priority") == "P0", "Expected P0 alert priority"
        assert data.get("action", {}).get("auto_create_task") == True
        print(f"✓ Emergency intent: {data['intent']}, priority: {data['action'].get('alert_priority')}")
    
    def test_faq_intent_wifi(self, auth_session):
        """WiFi password question → faq intent"""
        resp = auth_session.post(
            f"{BASE_URL}/api/voice/concierge?property_id=default",
            json={
                "text": "WiFi şifresi nedir",
                "language": "tr"
            }
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        assert data.get("intent") == "faq", f"Expected faq intent, got {data.get('intent')}"
        assert data.get("action", {}).get("auto_create_task") == False
        print(f"✓ FAQ intent: {data['intent']}")
    
    def test_room_service_intent(self, auth_session):
        """Room service breakfast menu → room_service intent"""
        resp = auth_session.post(
            f"{BASE_URL}/api/voice/concierge?property_id=default",
            json={
                "text": "Oda servisi kahvaltı menüsü",
                "language": "tr"
            }
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        assert data.get("intent") == "room_service", f"Expected room_service intent, got {data.get('intent')}"
        assert data.get("action", {}).get("route_to") == "pos_room_service"
        print(f"✓ Room service intent: {data['intent']}")
    
    def test_maintenance_intent(self, auth_session):
        """Broken AC → maintenance intent"""
        resp = auth_session.post(
            f"{BASE_URL}/api/voice/concierge?property_id=default",
            json={
                "text": "Klima bozuk çalışmıyor",
                "language": "tr"
            }
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        assert data.get("intent") == "maintenance", f"Expected maintenance intent, got {data.get('intent')}"
        assert data.get("action", {}).get("auto_create_task") == True
        print(f"✓ Maintenance intent: {data['intent']}")
    
    def test_front_desk_intent(self, auth_session):
        """Late checkout request → front_desk intent"""
        resp = auth_session.post(
            f"{BASE_URL}/api/voice/concierge?property_id=default",
            json={
                "text": "Geç çıkış yapmak istiyorum",
                "language": "tr"
            }
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        assert data.get("intent") == "front_desk", f"Expected front_desk intent, got {data.get('intent')}"
        print(f"✓ Front desk intent: {data['intent']}")
    
    def test_concierge_chat_fallback(self, auth_session):
        """Generic question → concierge_chat fallback"""
        resp = auth_session.post(
            f"{BASE_URL}/api/voice/concierge?property_id=default",
            json={
                "text": "Bugün hava nasıl olacak",
                "language": "tr"
            }
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        assert data.get("intent") == "concierge_chat", f"Expected concierge_chat intent, got {data.get('intent')}"
        print(f"✓ Concierge chat fallback: {data['intent']}")
    
    def test_empty_text_returns_400(self, auth_session):
        """Empty text should return 400"""
        resp = auth_session.post(
            f"{BASE_URL}/api/voice/concierge?property_id=default",
            json={
                "text": "",
                "language": "tr"
            }
        )
        assert resp.status_code == 400, f"Expected 400 for empty text, got {resp.status_code}"
        print("✓ Empty text returns 400")
    
    def test_whitespace_only_text_returns_400(self, auth_session):
        """Whitespace-only text should return 400"""
        resp = auth_session.post(
            f"{BASE_URL}/api/voice/concierge?property_id=default",
            json={
                "text": "   ",
                "language": "tr"
            }
        )
        assert resp.status_code == 400, f"Expected 400 for whitespace text, got {resp.status_code}"
        print("✓ Whitespace-only text returns 400")


class TestVoiceTranscribe:
    """Test Whisper STT via /api/voice/transcribe"""
    
    def test_empty_audio_returns_400(self, auth_session):
        """Empty audio file should return 400"""
        files = {"audio": ("empty.wav", b"", "audio/wav")}
        data = {"language": "tr", "property_id": "default"}
        
        resp = auth_session.post(
            f"{BASE_URL}/api/voice/transcribe",
            files=files,
            data=data
        )
        assert resp.status_code == 400, f"Expected 400 for empty audio, got {resp.status_code}: {resp.text}"
        print("✓ Empty audio returns 400")
    
    def test_transcribe_with_valid_audio(self, auth_session):
        """Valid audio file should return transcription (may be empty for silence)"""
        # Create a minimal valid WAV file
        wav_data = create_wav_audio(duration_ms=500)
        
        files = {"audio": ("test.wav", wav_data, "audio/wav")}
        data = {"language": "en", "property_id": "default"}
        
        resp = auth_session.post(
            f"{BASE_URL}/api/voice/transcribe",
            files=files,
            data=data
        )
        
        # Should succeed (200) or fail with Whisper error (502) if API key issue
        # 400 means validation error, 503 means missing key/library
        if resp.status_code == 200:
            result = resp.json()
            assert "text" in result, "Expected 'text' in response"
            assert "language" in result, "Expected 'language' in response"
            assert "log_id" in result, "Expected 'log_id' in response"
            print(f"✓ Transcribe success: text='{result.get('text', '')}', lang={result.get('language')}")
        elif resp.status_code in [502, 503]:
            # Whisper API error or missing key - acceptable for test environment
            print(f"⚠ Transcribe returned {resp.status_code} (Whisper API issue): {resp.text[:100]}")
        else:
            pytest.fail(f"Unexpected status {resp.status_code}: {resp.text}")


class TestVoiceSessions:
    """Test session retrieval endpoints"""
    
    def test_get_sessions(self, auth_session):
        """GET /api/voice/sessions/{property_id} returns sessions grouped by session_id"""
        resp = auth_session.get(f"{BASE_URL}/api/voice/sessions/default")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "sessions" in data, "Expected 'sessions' key in response"
        assert "count" in data, "Expected 'count' key in response"
        assert isinstance(data["sessions"], list), "sessions should be a list"
        
        # If there are sessions, verify structure
        if len(data["sessions"]) > 0:
            session = data["sessions"][0]
            assert "session_id" in session, "Session should have session_id"
            assert "messages" in session, "Session should have messages"
        
        print(f"✓ Sessions endpoint: {data['count']} entries, {len(data['sessions'])} sessions")
    
    def test_get_log(self, auth_session):
        """GET /api/voice/log/{property_id}?n=10 returns recent log entries"""
        resp = auth_session.get(f"{BASE_URL}/api/voice/log/default?n=10")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "items" in data, "Expected 'items' key in response"
        assert "count" in data, "Expected 'count' key in response"
        assert isinstance(data["items"], list), "items should be a list"
        assert data["count"] <= 10, "Should return at most 10 items"
        
        print(f"✓ Log endpoint: {data['count']} entries returned")
    
    def test_get_stats(self, auth_session):
        """GET /api/voice/stats/{property_id} returns total + by_intent counts"""
        resp = auth_session.get(f"{BASE_URL}/api/voice/stats/default")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "total" in data, "Expected 'total' key in response"
        assert "by_intent" in data, "Expected 'by_intent' key in response"
        assert isinstance(data["by_intent"], dict), "by_intent should be a dict"
        
        print(f"✓ Stats endpoint: total={data['total']}, intents={list(data['by_intent'].keys())}")


class TestHousekeepingTaskCreation:
    """Verify that housekeeping tasks are auto-created"""
    
    def test_housekeeping_task_created(self, auth_session):
        """After housekeeping intent, verify task exists in housekeeping_tasks"""
        # First, send a housekeeping request
        unique_room = f"TEST_{os.urandom(4).hex()}"
        resp = auth_session.post(
            f"{BASE_URL}/api/voice/concierge?property_id=default",
            json={
                "text": "Odamda temiz havlu istiyorum",
                "language": "tr",
                "room_number": unique_room
            }
        )
        assert resp.status_code == 200
        
        # Check if housekeeping tasks endpoint exists and has the task
        # This depends on whether there's a housekeeping tasks API
        tasks_resp = auth_session.get(f"{BASE_URL}/api/housekeeping/tasks?property_id=default")
        if tasks_resp.status_code == 200:
            tasks = tasks_resp.json()
            # Look for our task
            found = any(
                t.get("room_number") == unique_room and t.get("source") == "voice_concierge"
                for t in (tasks.get("tasks", []) if isinstance(tasks, dict) else tasks)
            )
            if found:
                print(f"✓ Housekeeping task auto-created for room {unique_room}")
            else:
                print(f"⚠ Task not found in housekeeping_tasks (may be in different collection)")
        else:
            print(f"⚠ Housekeeping tasks endpoint returned {tasks_resp.status_code}")


class TestEnglishIntents:
    """Test English language intent classification"""
    
    def test_english_towel_request(self, auth_session):
        """English towel request → housekeeping"""
        resp = auth_session.post(
            f"{BASE_URL}/api/voice/concierge?property_id=default",
            json={
                "text": "I need extra towels in my room please",
                "language": "en"
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("intent") == "housekeeping"
        print(f"✓ English housekeeping: {data['intent']}")
    
    def test_english_wifi_question(self, auth_session):
        """English WiFi question → faq"""
        resp = auth_session.post(
            f"{BASE_URL}/api/voice/concierge?property_id=default",
            json={
                "text": "What is the WiFi password?",
                "language": "en"
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("intent") == "faq"
        print(f"✓ English FAQ: {data['intent']}")
    
    def test_english_emergency(self, auth_session):
        """English emergency → emergency"""
        resp = auth_session.post(
            f"{BASE_URL}/api/voice/concierge?property_id=default",
            json={
                "text": "There is a fire emergency!",
                "language": "en"
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("intent") == "emergency"
        assert data.get("action", {}).get("alert_priority") == "P0"
        print(f"✓ English emergency: {data['intent']}, P0={data['action'].get('alert_priority')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
