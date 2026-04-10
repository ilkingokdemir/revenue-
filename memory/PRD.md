# Hotel Review Management Module - PRD

## Original Problem Statement
Hotel management review module to receive all reviews from online platforms (Booking.com, Airbnb, Expedia, Trip.com, Google, TripAdvisor) and respond with AI-generated replies with manual edit capability.

## What's Been Implemented (January-April 2026)

### Platform Integrations (14 Total)
- Google, Booking.com, TripAdvisor, Airbnb, Expedia, Trip.com
- Agoda, Hotels.com, Yelp, Facebook Reviews, MakeMyTrip, HRS, Despegar, Hostelworld
- Manual Import (CSV + form entry)

### Multi-Language AI Response Generator (NEW - April 2026)
- Auto-detects guest's language from review text (GPT-5.2)
- 16 supported languages: English, French, German, Spanish, Italian, Portuguese, Chinese, Japanese, Korean, Arabic, Russian, Dutch, Thai, Hindi, Turkish
- Language selector dropdown with "Auto-detect" default
- AI generates replies in selected/detected language
- "Translate to English" one-click button for staff verification
- Language detection badge shows under review with confidence score

### White-Label Branding
- Custom logo, app name, subtitle, primary/accent colors, 6 presets
- "Powered By" footer badge, live preview, persisted to MongoDB

### UI/UX Design
- DM Sans font, organic earthy hospitality theme
- Rounded-xl cards, slim nav, emerald AI panel, pill badges
- Custom scrollbar, hover/active states, polished empty states

### Core Features
- AI Response Generation (GPT-5.2 via Emergent Key)
- Response Templates (6 default templates)
- AI Sentiment Analysis with auto-suggestions
- Analytics Dashboard with priority queue
- Competitor Benchmarking
- Scheduled Reports (daily/weekly/monthly)
- Email Notifications for negative reviews (Resend)

## Architecture
- Frontend: React + Tailwind CSS + Shadcn UI
- Backend: FastAPI + MongoDB
- AI: OpenAI GPT-5.2 (Emergent LLM Key)
- Email: Resend (Emergent Key)

## DB Collections
- reviews, competitors, templates, notification_settings, report_settings
- platform_integrations, branding_settings

## API Endpoints
- Reviews: GET/POST /api/reviews, POST /api/reviews/generate-ai-response, POST /api/reviews/{id}/detect-language, POST /api/reviews/translate
- Languages: GET /api/languages
- Analytics: GET /api/analytics/overview, GET /api/analytics/dashboard
- Templates: GET/POST/PUT/DELETE /api/templates
- Integrations: GET /api/integrations, PUT /api/integrations/{platform}/configure
- Branding: GET/PUT /api/branding, POST/DELETE /api/branding/logo
- Settings: GET/PUT /api/settings/notifications, GET/PUT /api/settings/reports

## Next Tasks (Prioritized)
1. **P0** - Real bi-directional sync (requires platform API credentials/partner approvals)
2. **P1** - Authentication system for team access
3. **P2** - Refactor App.js (3200+ lines) into modular components
