# Hotel Review Management Module - PRD

## Original Problem Statement
Hotel management review module to receive all reviews from online platforms (Booking.com, Airbnb, Expedia, Trip.com, Google, TripAdvisor) and respond with AI-generated replies with manual edit capability.

## What's Been Implemented (January-April 2026)

### Platform Integrations (14 Total)
- **Google Business Profile API** - Full 7-step setup guide with OAuth configuration wizard
- **Booking.com** - 6-step partner program guide with credential wizard
- **TripAdvisor** - 4-step Content API guide with configuration
- **Airbnb** - Setup guide and credential wizard
- **Expedia** - Setup guide and credential wizard
- **Trip.com** - 3-step partner API setup
- **Agoda** - 4-step partner program setup (Booking Holdings)
- **Hotels.com** - 4-step setup via Expedia Partner Central
- **Yelp** - 3-step Fusion API setup
- **Facebook Reviews** - 5-step Meta Graph API setup
- **MakeMyTrip** - 3-step partner extranet setup
- **HRS** - 4-step partner API setup (Europe/business travel)
- **Despegar** - 3-step partner setup (Latin America)
- **Hostelworld** - 3-step API setup (hostels/budget)
- **Manual Import** - CSV upload and form entry for any platform

### White-Label Branding (NEW - April 2026)
- Custom logo upload (stored as base64 in MongoDB, max 2MB)
- Customizable app name and subtitle
- 6 color theme presets (Forest, Ocean, Midnight, Plum, Charcoal, Navy)
- Custom primary & accent color pickers
- "Powered By" footer badge (toggle + custom text)
- Live preview banner showing real-time changes
- All settings persisted to MongoDB

### Core Features
- AI Response Generation (GPT-5.2 via Emergent Key)
- Response Templates (6 default templates)
- AI Sentiment Analysis with auto-suggestions
- Analytics Dashboard with priority queue
- Competitor Benchmarking
- Scheduled Reports (daily/weekly/monthly)
- Email Notifications for negative reviews (Resend)
- Two-way sync framework (mocked - pending real API credentials)

## Architecture
- Frontend: React + Tailwind CSS + Shadcn UI
- Backend: FastAPI + MongoDB
- AI: OpenAI GPT-5.2 (Emergent LLM Key)
- Email: Resend (Emergent Key)

## DB Collections
- reviews, competitors, templates, notification_settings, report_settings
- platform_integrations, branding_settings

## Next Tasks (Prioritized)
1. **P0** - Real bi-directional sync (requires platform API credentials/partner approvals)
2. **P1** - Authentication system for team access
3. **P2** - Refactor App.js (3000+ lines) into modular components
