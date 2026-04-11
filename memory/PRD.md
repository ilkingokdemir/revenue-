# MyHotelBox — Product Requirements Document

## Overview
Hotel management software (www.myhotelbox.com) providing two core modules:
1. **Review Hub** — Centralized review management across 14 platforms with AI-powered responses
2. **Booking Engine** — Direct booking system with 10 website templates, Stripe payments, email confirmations, competitive features, and multi-language support

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
  BookingEngine.js  — Public booking page coordinator (with LanguageProvider)
  ReviewWidget.js   — Embeddable review widget
  i18n/
    translations.js     — 12-language translation dictionary (~100 keys each)
    LanguageContext.js   — React context providing t() function, lang, isRTL
    LanguageSelector.js  — Dropdown component with flags
  templates/
    templateConfig.js    — 10 template configurations
    HeroSection.js       — Hero/search section (i18n)
    RoomCards.js         — Room preview & selection (i18n)
    GuestDetailsStep.js  — Guest form, add-ons, promo codes & payment (i18n)
    ConfirmationStep.js  — Booking confirmation (i18n)
    SearchWidget.js      — Date/guest search widget (i18n)
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
- `translation_overrides` — Custom per-property per-language translation overrides

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
- Template Customization Panel (tested iteration_28 - 100%)
- Promo Codes (tested iteration_29 - 100%)
- Add-on Services (tested iteration_29 - 100%)
- Hotel Policies (tested iteration_29 - 100%)
- Property Facilities (tested iteration_29 - 100%)
- Expanded Amenity Picker — 160+ amenities in 10 categories (tested iteration_29 - 100%)
- Room Editor with unlimited photos (tested iteration_29 - 100%)
- **Multi-Language Support** — 12 languages (EN, FR, DE, ES, IT, PT, AR, ZH, JA, KO, NL, RU) with RTL for Arabic, language selector in header, URL param persistence, localStorage save, backend admin translation overrides, AI auto-translate (tested iteration_30 - 100%)

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
- P1: Channel Manager integration (sync availability across OTAs)
- P1: Guest Review Collection (post-stay email with review form)
- P2: Extract remaining route handlers from server.py into /routes/ modules
- P2: Further App.js modularization
- P3: Real-time availability calendar for booking engine
- P3: Guest messaging/chat within booking engine
- P3: Guest Portal for returning guests (booking history, re-booking)
