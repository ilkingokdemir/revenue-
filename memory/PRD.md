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

### P2: App.js Refactoring (April 2026)
- Reduced from 4600 to 3000 lines
- Extracted 5 components to /components/dashboard/:
  - IntegrationsPanel.js (765 lines)
  - AnalyticsPanel.js (471 lines)
  - ReportsSettings.js (248 lines)
  - BrandingPanel.js (303 lines)
  - LoginPage.js (103 lines)
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

### Core Features
- JWT auth, 3 roles, 7 departments, approval workflow
- GPT-5.2 AI responses, 16 languages
- 14 platform integrations with inbound webhook sync
- Multi-property, white-label branding

## Architecture
```
frontend/src/
├── App.js (3000 lines — Dashboard, Sidebar, core views)
├── ReviewWidget.js (widget)
├── components/dashboard/
│   ├── config.js (shared constants)
│   ├── ReviewComponents.js
│   ├── IntegrationsPanel.js
│   ├── AnalyticsPanel.js
│   ├── ReportsSettings.js
│   ├── BrandingPanel.js
│   ├── LoginPage.js
│   └── index.js (barrel)
```

## Remaining Work
- Outbound response posting to platforms (currently mocked — responses are generated but not pushed back)
- Configure Resend API key for email notifications
- Further App.js extraction (still 3000 lines)
