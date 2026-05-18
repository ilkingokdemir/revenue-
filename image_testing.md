# Image Integration Testing Playbook (iter 324)

Image attachments via emergentintegrations:
- Use **base64-encoded images** for all tests (no SVG/BMP/HEIC; only PNG/JPEG/WEBP)
- Real-feature images required (no blank/solid color)
- Resize large images to reasonable bounds before encoding
- Vision endpoint: `POST /api/revenue/market-robot/scrape-booking-vision`
  body: `{booking_url: str, hotel_name?: str, model?: "gpt-4o-mini"|"gpt-5-mini"|"gemini-2.5-flash"}`
  returns: `{ok, hotel_name, room_count, price_per_night, currency, star_rating, raw_extraction, screenshot_size_bytes}`
