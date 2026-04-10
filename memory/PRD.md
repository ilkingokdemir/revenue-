# Hotel Review Management Module - PRD

## Original Problem Statement
Hotel management review module to receive all reviews from online platforms (Booking.com, Airbnb, Expedia, Trip.com, Google, TripAdvisor) and respond with AI-generated replies with manual edit capability.

## What's Been Implemented (January-April 2026)

### Platform Integrations (14 Total)
- Google Business Profile, Booking.com, TripAdvisor, Airbnb, Expedia, Trip.com
- Agoda, Hotels.com, Yelp, Facebook Reviews, MakeMyTrip, HRS, Despegar, Hostelworld
- Manual Import (CSV + form entry)
- Each platform has setup guides, config wizards, and credential forms

### White-Label Branding
- Custom logo upload (base64 in MongoDB, max 2MB)
- App name, subtitle, primary/accent colors, 6 presets
- "Powered By" footer badge (toggle + text)
- Live preview, persisted to MongoDB

### UI/UX Redesign (April 2026)
- DM Sans font (Google Fonts CDN)
- Organic & Earthy hospitality theme
- Rounded-xl cards with subtle shadows
- Slim header nav with lightweight nav links
- Emerald-tinted AI Response panel
- Pill-shaped platform badges
- Custom scrollbar, review item hover/active states
- Polished empty states

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

## Next Tasks (Prioritized)
1. **P0** - Real bi-directional sync (requires platform API credentials/partner approvals)
2. **P1** - Authentication system for team access
3. **P2** - Refactor App.js (3000+ lines) into modular components
