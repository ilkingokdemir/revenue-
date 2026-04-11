# MyHotelBox — Product Requirements Document

## Overview
Hotel management software (www.myhotelbox.com) providing two core modules:
1. **Review Hub** — Centralized review management across 14 platforms with AI-powered responses
2. **Booking Engine** — Direct booking system with 10 templates, Stripe payments, multi-language, competitive features matching Mews/Cloudbeds/Eviivo/Hotelchamp

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
  server.py, models.py, auth.py, database.py

/app/frontend/src/
  App.js, BookingEngine.js, ReviewWidget.js
  i18n/ (translations.js, LanguageContext.js, LanguageSelector.js)
  templates/ (HeroSection, RoomCards, GuestDetailsStep, ConfirmationStep, SearchWidget,
              PhotoCarousel, SmartUpsellEngine, PriceComparisonWidget,
              SocialProofNotifications, GoogleHotelStructuredData)
  components/dashboard/ (TemplateCustomizer, RoomEditor, AmenityPicker,
                         PromoCodesPanel, AddOnsPanel, PoliciesPanel, etc.)
```

## Completed Features

### Booking Engine — Core
- 10 website templates with live customizer
- Full booking flow: search > room selection > guest details > payment > confirmation
- Stripe Checkout + Pay-at-hotel
- Resend email confirmations
- Multi-property support (9 branches, 45 room types)
- Room photo carousel with multi-image galleries

### Booking Engine — Competitive Features (P0)
- **Multi-Language** (12 languages, RTL Arabic, URL persistence) — iteration_30 100%
- **Promo Codes** (CRUD, validation, checkout integration) — iteration_29 100%
- **Add-on Services** (per_stay/night/person pricing, categories) — iteration_29 100%
- **Hotel Policies** (check-in/out, cancellation, house rules) — iteration_29 100%
- **Property Facilities** (8 categories, 50+ options) — iteration_29 100%
- **Amenity Picker** (160+ amenities, 10 categories) — iteration_29 100%
- **Room Editor** (unlimited photos, 4-tab layout) — iteration_29 100%
- **Smart Upsell Engine** (10 templates, CRUD, auto-suggest in checkout) — iteration_31 100%
- **Price Comparison Widget** (OTA vs direct pricing, savings display) — iteration_31 100%
- **Social Proof Notifications** (viewing count, recent bookings, low stock alerts) — iteration_31 100%
- **Google Hotel Structured Data** (JSON-LD for Google Maps/Search SEO) — iteration_31 100%

### Review Hub
- 14-platform integration with inbound webhooks
- AI response generation (GPT-5.2)
- Response approval workflow
- Response templates, analytics, competitor benchmarking
- Embeddable review widget, API key management
- Notification & report settings

### Infrastructure
- JWT auth (admin, manager, receptionist)
- White-label branding, multi-property filtering
- Backend modular architecture, frontend component refactoring
- Outbound webhook events (12 event types)

## Database Collections
reviews, users, properties, webhooks, webhook_deliveries, api_keys, sync_logs,
platform_integrations, notification_settings, report_settings, response_templates,
competitors, branding, room_types, bookings, checkout_sessions, template_settings,
promo_codes, add_ons, hotel_policies, property_facilities, translation_overrides,
upsell_items, social_proof_settings

## Backlog (Prioritized)
- P1: Channel Manager integration (sync availability across OTAs)
- P1: Guest Review Collection (post-stay email with review form)
- P1: Visual Drag-and-Drop Availability Calendar (eviivo-style)
- P2: Mobile Self-Check-in (Mews-style)
- P2: Guest Portal (booking history, re-booking)
- P2: Revenue Management / Dynamic Pricing
- P2: Extract server.py routes into /routes/ modules
- P3: Guest messaging/chat
