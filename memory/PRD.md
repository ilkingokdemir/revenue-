# Hotel Review Management Module - PRD

## Original Problem Statement
Hotel management review module for MyHotelBox.com integration. Receive reviews from online platforms, respond with AI-generated unique replies. Role-based team access, approval workflow, multi-property support.

## What's Been Implemented

### Embeddable Reviews Widget (April 2026)
- Standalone widget at `/widget?api_key=rhk_xxx&property_id=xxx`
- No login required — authenticated via API key query parameter
- Stats bar: total reviews, avg rating, response rate, pending count
- Review list with platform badges, star ratings, status badges
- Detail panel with full review text and AI response generation
- Platform and status filter dropdowns
- Supports `?theme=dark` for dark mode
- Iframe embed code in Integration Guide

### Widget API Endpoints (April 2026)
- GET /api/widget/reviews — list reviews (supports platform, status, limit filters)
- GET /api/widget/stats — review statistics (total, avg rating, response rate, pending)
- POST /api/widget/generate-response — generate AI response from widget
- All authenticated via `verify_api_key` middleware (rhk_ prefix API keys)
- Request count tracking per API key

### Webhook Delivery Log (April 2026)
- Stores last 20 deliveries per webhook in MongoDB
- Shows event type, HTTP status, response time, timestamp
- Auto-populates on test ping, refresh button

### MyHotelBox Integration Guide (April 2026)
- 5-step connection walkthrough
- 8 documented API endpoints
- Code snippets: curl, Node.js, Python webhook handlers
- Webhook payload example with headers
- Iframe embed code for widget

### Webhook Test Ping (April 2026)
- POST /api/webhooks/{id}/test sends sample payload
- Shows HTTP status + response time, handles errors

### Left Sidebar Navigation (April 2026)
- 12 items across 4 sections: Main, Workflow, Connections, Settings

### API Connection Panel (April 2026)
- CRUD for API keys with rhk_ prefix

### Webhooks Panel (April 2026)
- CRUD with 8 event types, toggle, expand, delivery log

### Multi-Property Support
- Property CRUD, 8 types, property_id scoping

### Authentication & Team Management
- JWT auth, 3 roles (Admin/Manager/Receptionist), 7 departments

### Approval Workflow
- Pending -> Draft -> Pending Approval -> Approved/Rejected -> Responded

### AI Response Engine
- GPT-5.2 personalized responses, 16 languages

### Platform Integrations (14)
- Google, Booking.com, TripAdvisor, Airbnb, Expedia, Trip.com, Agoda, Hotels.com, Yelp, Facebook, MakeMyTrip, HRS, Despegar, Hostelworld

### White-Label Branding
- Custom logo, app name, colors

## Next Tasks
1. **P0** - Real bi-directional platform sync (currently MOCKED)
2. **P1** - Property mapping between MyHotelBox branches and Review Hub
3. **P2** - Break down App.js (4500+ lines) into components
