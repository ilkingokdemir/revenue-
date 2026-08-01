# Image Integration Testing Playbook
- Always use base64-encoded images (JPEG/PNG/WEBP only) for tests.
- No blank/solid-color images — must contain real visual features (text, edges, shadows).
- Re-detect MIME after any transformation; animated images → first frame only.
- Resize large images to reasonable bounds.
- ID verification endpoint: POST /api/id-verification/verify {booking_id, image_base64} (admin token gerekli). Test images should look like ID documents (name text visible) for meaningful extraction; a photo with readable printed name is enough.
