# Hotel Review Management Module - PRD

## Original Problem Statement
Hotel management review module for MyHotelBox.com integration. Receive reviews from online platforms, respond with AI-generated unique replies. Role-based team access, approval workflow, multi-property support.

## What's Been Implemented

### P0: Real Platform Sync — Inbound Webhooks (April 2026)
- `POST /api/platforms/{platform}/incoming` — receive reviews from any of 14 platforms
- `POST /api/platforms/{platform}/incoming/batch` — batch import reviews
- `GET /api/platforms/{platform}/inbound-url` — get webhook URL + secret for platform config
- Auth: X-Platform-Secret header or API key (rhk_/psk_ prefix)
- Deduplication by external_review_id + platform
- Auto-triggers low-rating alerts and webhook events on new review
- Sync Log: real-time activity log with platform, direction, status, timestamp

### P1: Property Mapping (April 2026)
- `PUT /api/properties/{id}/mapping` — link Review Hub property to MyHotelBox branch
- `GET /api/properties/by-external/{id}` — lookup property by external system ID
- Maps external_id, external_name, external_system (myhotelbox/cloudbeds/other)
- UI: Property Mapping panel in sidebar with edit forms

### P1: Outbound Sync Attempt (April 2026)
- When responding to a review, backend attempts to post reply to originating platform
- Google Business Profile: Full OAuth token + PUT reply API implemented
- Other platforms: Logged as "skipped" until vendor credentials are configured
- All sync attempts logged in sync_logs collection (visible in Sync Log panel)
- `POST /api/integrations/{platform}/test-connection` — test connection to configured platform

### P2: App.js Refactoring (April 2026)
- Reduced from 4600 to ~2760 lines
- Extracted 7 components to /components/dashboard/:
  - IntegrationsPanel.js (800 lines)
  - AnalyticsPanel.js (471 lines)
  - ReportsSettings.js (248 lines)
  - BrandingPanel.js (303 lines)
  - LoginPage.js (103 lines)
  - SyncLogPanel.js (105 lines)
  - PropertyMappingPanel.js (165 lines)
- Barrel exports via index.js
- Shared config.js for API, platformColors, formatApiErrorDetail

### Notification System (April 2026)
- Low-rating alerts: larger popup, warning icon, alarm sound, 15s display
- Normal review alerts: bell icon, chime sound, 8s display
- Red notification badge with unread count
- 20-second polling for new reviews

### Embeddable Widget (April 2026)
- /widget?api_key=rhk_xxx — standalone iframe-embeddable review dashboard
- Stats, review list, AI response generation, filters, dark mode

### Integration Infrastructure (April 2026)
- API keys (rhk_), webhooks (8 events), delivery log, test ping
- Integration Guide with code snippets for Node.js and Python
- Left sidebar with 14+ navigation items
- Platform connection test functionality with Test Connection button
- Save & Test Connection workflow in config wizard

### Multi-Branch Support (April 2026)
- 9 MyHotelBox branches seeded on startup
- "All Branches" dropdown selector in sidebar
- Reviews and stats filter by selected branch

### Core Features
- JWT auth, 3 roles, 7 departments, approval workflow
- GPT-5.2 AI responses, 16 languages
- 14 platform integrations with inbound webhook sync
- Multi-property, white-label branding

## Architecture
```
frontend/src/
├── App.js (~2760 lines — Dashboard, Sidebar, core views)
├── ReviewWidget.js (widget)
├── components/dashboard/
│   ├── config.js (shared constants)
│   ├── ReviewComponents.js
│   ├── IntegrationsPanel.js
│   ├── AnalyticsPanel.js
│   ├── ReportsSettings.js
│   ├── BrandingPanel.js
│   ├── LoginPage.js
│   ├── SyncLogPanel.js
│   ├── PropertyMappingPanel.js
│   └── index.js (barrel)
```

## Remaining Work
- Real outbound API calls to Booking.com, Expedia, TripAdvisor, etc. (requires vendor partner credentials)
- Configure Resend API key for email notifications
- Google OAuth: user needs to obtain Client ID, Secret, and Refresh Token from Google Cloud Console
