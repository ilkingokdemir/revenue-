# Hotel Review Management Module + Booking Engine - PRD

## Original Problem Statement
Hotel management PMS software (MyHotelBox.com) needs: review module for 14 platforms with AI responses, booking engine like Mews/Cloudbeds/eviivo with Booking.com-style trust design, Stripe payments, and 10 website templates mimicking Booking.com, Airbnb, Expedia, Hotels.com.

## What's Been Implemented

### 10 Website Templates (April 2026)
Templates at `/book?property={id}&template={templateId}`:
- **Booking.com Style (4)**: Classic Blue, Business Navy, Resort Paradise, Boutique Elegant
- **Airbnb Style (2)**: Modern Stay (photo-grid layout), Experience Plus
- **Expedia Style (2)**: Expedia Deals (yellow member pricing), Expedia VIP (gold luxury)
- **Hotels.com Style (2)**: Hotels Rewards (red, stamps), Family Friendly (purple, kid badges)

Each template has: unique color scheme, header, hero style, platform badges, rating styles, border radius, trust signals. Airbnb templates use photo-grid layout instead of standard hero overlay.

Admin Template Gallery: filter by platform, preview/copy URL per template, active URL display.

### Booking Engine with Stripe (April 2026)
- Step flow: Search → Select Room → Guest Details → Payment → Confirmation
- Stripe Checkout redirect (Pay Now) or Pay at Hotel option
- Room cards with photos, amenities, urgency cues, free cancellation badges
- Admin panel: Room Types CRUD + Bookings management with payment status
- 5 seeded room types (£89–£349)

### Review Hub Module (Earlier)
- 14 platform inbound webhook sync, GPT-5.2 AI responses (16 languages)
- Role-based approval workflow, multi-branch selector (9 branches)
- Real-time widget with red notification popups + sound
- Integration panel with connection testing, property mapping
- Sync logging, API keys, webhooks, branding

## Architecture
```
frontend/src/
├── App.js (~2780 lines)
├── BookingEngine.js (Template-aware booking engine)
├── ReviewWidget.js
├── templates/templateConfig.js (10 template configs)
├── components/dashboard/
│   ├── BookingEnginePanel.js, TemplateGallery.js
│   ├── IntegrationsPanel.js, AnalyticsPanel.js, etc.

backend/server.py (~4200 lines)
```

## DB Collections
reviews, users, properties, webhooks, webhook_deliveries, api_keys,
platform_integrations, sync_logs, branding_settings,
room_types, bookings, payment_transactions

## Remaining Work
- Email booking confirmation (Resend)
- Real outbound sync to review platforms (vendor credentials)
- Google OAuth for review platform connections
- More room type photos (currently using Unsplash placeholders)
