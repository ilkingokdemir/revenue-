# MyHotelBox — Product Requirements Document

## Overview
Hotel management software (www.myhotelbox.com) providing two core modules:
1. **Review Hub** — Centralized review management across 14 platforms with AI-powered responses
2. **Booking Engine** — Direct booking system with 10 website templates, Stripe payments, and email confirmations

## Tech Stack
- **Frontend**: React, Tailwind CSS, Shadcn UI, Framer Motion
- **Backend**: FastAPI, MongoDB (Motor async driver)
- **AI**: OpenAI GPT-5.2 via Emergent LLM Key
- **Payments**: Stripe Checkout (test mode)
- **Email**: Resend via emergentintegrations
- **Auth**: JWT with bcrypt password hashing

## Architecture
```
/app/backend/
  server.py        — Main FastAPI app, routes, startup/seeding
  models.py        — All Pydantic models (extracted)
  auth.py          — Auth utilities (extracted)
  database.py      — MongoDB connection (extracted)
  routes/           — (placeholder for future route extraction)

/app/frontend/src/
  App.js            — Admin dashboard (auth, sidebar, panels)
  BookingEngine.js  — Public booking page coordinator
  ReviewWidget.js   — Embeddable review widget
  templates/
    templateConfig.js    — 10 template configurations
    HeroSection.js       — Hero/search section (extracted)
    RoomCards.js         — Room preview & selection (extracted)
    GuestDetailsStep.js  — Guest form & payment (extracted)
    ConfirmationStep.js  — Booking confirmation (extracted)
    SearchWidget.js      — Date/guest search widget (extracted)
    PhotoCarousel.js     — Room photo carousel (extracted)
  components/dashboard/  — Admin panel components
```

## Database Collections
- `reviews`, `users`, `properties`, `webhooks`, `webhook_deliveries`
- `api_keys`, `sync_logs`, `platform_integrations`, `notification_settings`
- `report_settings`, `response_templates`, `competitors`, `branding`
- `room_types`, `bookings`, `checkout_sessions`

## Completed Features

### Review Hub
- 14-platform integration with inbound webhooks
- AI response generation (GPT-5.2) with tone/language control
- Response approval workflow (draft → pending_approval → approved/rejected)
- Response templates with categories
- Analytics dashboard with sentiment analysis
- Competitor benchmarking
- Notification & report settings
- Embeddable review widget (/widget)
- API key management for widget access
- Property mapping for multi-branch hotels
- Sync log for monitoring inbound/outbound activity

### Booking Engine
- 10 distinct website templates (Booking.com x4, Airbnb x2, Expedia x2, Hotels.com x2)
- Full booking flow: search → room selection → guest details → payment → confirmation
- Stripe Checkout integration for card payments
- Pay-at-hotel option
- Resend email confirmations
- Multi-property support (9 seeded branches, 45 room types)
- Room photo carousel with multi-image galleries
- Admin template gallery with preview
- Admin rooms & bookings management panel

### Connections & Integrations
- Platform credentials configuration with test connection
- Outbound webhook events for both reviews AND bookings (12 total events)
- Enhanced bi-directional outbound review sync (Google, Booking.com, TripAdvisor, Expedia)
- Outbound sync status dashboard (GET /api/integrations/outbound-status)
- Bulk sync for pending responses (POST /api/integrations/sync-all-outbound)
- Integration guide documentation panel

### Infrastructure
- JWT authentication with role-based access (admin, manager, receptionist)
- White-label branding settings
- Multi-property branch filtering
- Backend module extraction (models.py, auth.py, database.py)
- Frontend template component refactoring (6 components)

## Known Limitations
- Outbound platform sync (Booking.com, TripAdvisor, Expedia) requires real vendor API credentials
- Email confirmations require Resend API configuration
- Stripe in test mode

## Backlog
- P2: Extract remaining route handlers from server.py into /routes/ modules
- P2: Further App.js modularization (extract inline panels)
- P3: Real-time availability calendar for booking engine
- P3: Guest messaging/chat within booking engine
