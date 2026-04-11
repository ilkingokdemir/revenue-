# Hotel Review Management Module + Booking Engine - PRD

## Original Problem Statement
Hotel management review module for MyHotelBox.com integration. Receive reviews from online platforms, respond with AI-generated unique replies. Role-based team access, approval workflow, multi-property support. Additionally, a Booking Engine module like Mews/Cloudbeds/eviivo with Booking.com-style design that hotel clients can embed on their websites.

## What's Been Implemented

### Booking Engine Module (April 2026)
- **Public Booking Engine** at `/book?property={property_id}`:
  - Booking.com-style blue UI with trust signals (SSL, security badges, verified property)
  - Hero section with property name, rating, and search widget
  - Step-by-step booking flow: Search → Select Room → Guest Details → Confirmation
  - Room cards with photos, amenities, pricing, "Free cancellation" and "Breakfast included" badges
  - "Only X left on our site!" urgency cues for limited availability rooms
  - Guest details form with booking summary sidebar and price breakdown
  - Booking confirmation with MHB-XXXXXXX reference number
  - Mobile-responsive with sticky "Book Now" bar
  - Guest picker (adults, children, rooms)
  - Reviews section displaying verified guest reviews

- **Admin Dashboard - Booking Engine Panel**:
  - Room Types tab: Create, edit, delete room types with photos, amenities, pricing
  - Bookings tab: View all bookings with status management (Check In, Cancel, No Show, Check Out)
  - Copy Booking URL and Preview buttons
  - Live booking URL display

- **Backend API Endpoints**:
  - Public: `/api/booking/property/{id}`, `/api/booking/rooms/{id}`, `/api/booking/availability/{id}`, `/api/booking/reserve`, `/api/booking/reservation/{ref}`, `/api/booking/reviews/{id}`
  - Admin: CRUD `/api/room-types`, `/api/bookings`, `/api/bookings/{id}/status`

- **Sample Data**: 5 room types seeded for "aldgate-flats" (Standard Double £89, Deluxe King £149, Family Suite £219, Superior Twin £109, Executive Suite £349)

### Review Hub Module (Earlier - April 2026)
- Webhook inbound sync for 14 platforms
- GPT-5.2 AI response generation in 16 languages
- Role-based approval workflow (3 roles, 7 departments)
- Real-time widget with red notification popups + sound alerts
- Integration panel with connection testing
- Multi-branch selector with 9 MyHotelBox branches
- Platform sync logging (inbound + outbound attempts)
- Property mapping to MyHotelBox branches
- Embeddable review widget at `/widget`
- API keys, webhooks, delivery logs
- White-label branding

## Architecture
```
frontend/src/
├── App.js (~2770 lines — Dashboard, Sidebar, core views)
├── BookingEngine.js (NEW — Public booking engine page)
├── ReviewWidget.js (Embeddable widget)
├── components/dashboard/
│   ├── config.js
│   ├── ReviewComponents.js
│   ├── IntegrationsPanel.js
│   ├── AnalyticsPanel.js
│   ├── ReportsSettings.js
│   ├── BrandingPanel.js
│   ├── LoginPage.js
│   ├── SyncLogPanel.js
│   ├── PropertyMappingPanel.js
│   ├── BookingEnginePanel.js (NEW — Admin room/booking management)
│   └── index.js (barrel)

backend/
├── server.py (~3800 lines — All API routes, models, auth, webhooks, booking engine)
```

## Key Database Collections
- `reviews`, `users`, `properties`, `webhooks`, `webhook_deliveries`, `api_keys`, `platform_integrations`, `sync_logs`, `branding_settings`
- NEW: `room_types`, `bookings`

## Remaining Work
- Stripe payment integration for booking engine (currently pay-at-hotel only)
- Real outbound API calls to review platforms (requires vendor credentials)
- Google OAuth configuration (user needs to obtain credentials)
- Hotel website template with embeddable booking widget (beyond standalone /book page)
