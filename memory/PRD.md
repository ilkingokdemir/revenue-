# MyHotelBox — Product Requirements Document

## Overview
Hotel management software (www.myhotelbox.com) providing two core modules:
1. **Review Hub** — Centralized review management across 14 platforms with AI-powered responses
2. **Booking Engine** — Direct booking system with 10 website templates, Stripe payments, email confirmations, and competitive features matching Mews/Cloudbeds/Eviivo

## Tech Stack
- **Frontend**: React, Tailwind CSS, Shadcn UI
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

/app/frontend/src/
  App.js            — Admin dashboard (auth, sidebar, panels)
  BookingEngine.js  — Public booking page coordinator
  ReviewWidget.js   — Embeddable review widget
  templates/
    templateConfig.js    — 10 template configurations
    HeroSection.js       — Hero/search section
    RoomCards.js         — Room preview & selection
    GuestDetailsStep.js  — Guest form, add-ons, promo codes & payment
    ConfirmationStep.js  — Booking confirmation
    SearchWidget.js      — Date/guest search widget
    PhotoCarousel.js     — Room photo carousel
  components/dashboard/
    TemplateCustomizer.js — Per-property template customization with live preview
    TemplateGallery.js    — Template selection gallery
    BookingEnginePanel.js — Room & booking management
    RoomEditor.js         — Room editor with unlimited photos & 160+ amenities
    AmenityPicker.js      — Category-based amenity picker (10 categories)
    PromoCodesPanel.js    — Promo code CRUD management
    AddOnsPanel.js        — Add-on services CRUD management
    PoliciesPanel.js      — Hotel policies & facilities management
    ...other panels
```

## Database Collections
- `reviews`, `users`, `properties`, `webhooks`, `webhook_deliveries`
- `api_keys`, `sync_logs`, `platform_integrations`, `notification_settings`
- `report_settings`, `response_templates`, `competitors`, `branding`
- `room_types`, `bookings`, `checkout_sessions`
- `template_settings` — Per-property template customization
- `promo_codes` — Discount codes with validation rules
- `add_ons` — Extra services (per_stay/per_night/per_person pricing)
- `hotel_policies` — Check-in/out, cancellation, house rules, payment methods
- `property_facilities` — Selected property-level facilities

## Completed Features

### Review Hub
- 14-platform integration with inbound webhooks
- AI response generation (GPT-5.2) with tone/language control
- Response approval workflow (draft > pending_approval > approved/rejected)
- Response templates with categories
- Analytics dashboard with sentiment analysis
- Competitor benchmarking
- Notification & report settings
- Embeddable review widget (/widget)
- API key management for widget access
- Property mapping for multi-branch hotels
- Sync log for monitoring inbound/outbound activity

### Booking Engine
- 10 distinct website templates
- Full booking flow: search > room selection > guest details > payment > confirmation
- Stripe Checkout integration + Pay-at-hotel
- Resend email confirmations
- Multi-property support (9 seeded branches, 45 room types)
- Room photo carousel with multi-image galleries
- Admin template gallery with preview
- Admin rooms & bookings management panel
- **Template Customization Panel** (tested iteration_28 - 100%)
- **Promo Codes** — Create/toggle/delete codes, percentage/fixed discounts, min nights/amount, date validity, max uses, public validation endpoint (tested iteration_29 - 100%)
- **Add-on Services** — CRUD with categories (transport, dining, experience, wellness, etc.), per_stay/per_night/per_person pricing, toggle active (tested iteration_29 - 100%)
- **Hotel Policies** — Check-in/out times, cancellation (free/moderate/strict/custom), house rules, children/pet/smoking policies, payment methods, damage deposit (tested iteration_29 - 100%)
- **Property Facilities** — 8 categories of property-level facilities (general, dining, wellness, business, transport, outdoor, family, laundry) (tested iteration_29 - 100%)
- **Expanded Amenity Picker** — 10 categories, 160+ amenities with search and custom addition (tested iteration_29 - 100%)
- **Room Editor** — 4 tabs (Details, Photos, Amenities, Pricing) with unlimited photo support (tested iteration_29 - 100%)
- **Public Booking Engine Integration** — Facilities section, policies display, add-on selection in checkout, promo code validation in checkout (tested iteration_29 - 100%)

### Connections & Integrations
- Platform credentials configuration with test connection
- Outbound webhook events for reviews AND bookings (12 total events)
- Enhanced bi-directional outbound review sync
- Outbound sync status dashboard
- Bulk sync for pending responses
- Integration guide documentation panel

### Infrastructure
- JWT authentication with role-based access (admin, manager, receptionist)
- White-label branding settings
- Multi-property branch filtering
- Backend module extraction (models.py, auth.py, database.py)
- Frontend template component refactoring (6 components)

## Known Limitations
- Outbound platform sync requires real vendor API credentials
- Email confirmations require Resend API configuration
- Stripe in test mode

## Backlog (Prioritized)
- P1: Real bi-directional outbound sync to review platforms (needs real vendor API credentials)
- P2: Extract remaining route handlers from server.py into /routes/ modules
- P2: Further App.js modularization
- P3: Real-time availability calendar for booking engine
- P3: Guest messaging/chat within booking engine
- P3: Guest Portal for returning guests (booking history, re-booking)
