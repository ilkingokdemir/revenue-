# Hotel Review Management Module - PRD

## Original Problem Statement
Hotel management review module for MyHotelBox.com integration. Receive reviews from online platforms, respond with AI-generated unique replies. Role-based team access, approval workflow, multi-property support.

## What's Been Implemented

### Left Sidebar Navigation (April 2026)
- Full left sidebar layout with dark theme (stone-900)
- 4 sections: Main, Workflow, Connections, Settings
- 11 navigation items: Reviews, Analytics, Templates, Approvals, Integrations, API Connection, Webhooks, Alerts, Reports, Branding, Team
- Active state with emerald accent border
- User info + logout at bottom

### API Connection Panel (April 2026)
- CRUD for API keys (create with label, list with masked keys, delete)
- Keys prefixed with `rhk_` for easy identification
- Quick Start documentation card with code sample
- Link to Swagger API documentation
- Admin-only access

### Webhooks Panel (April 2026)
- CRUD for webhooks (create with URL/label/events, list, toggle, delete)
- 8 subscribable events: review.created, review.responded, review.approved, review.rejected, response.generated, response.published, rating.low, rating.high
- Expandable details: secret, delivery count, failure count, last triggered, subscribed events
- Toggle switch for active/paused state
- Admin-only creation/deletion, manager can view

### Multi-Property Support (April 2026)
- Property CRUD API (create, read, update, delete)
- 8 property types: hotel, resort, hostel, apartment, villa, boutique, motel, bed & breakfast
- All reviews scoped by property_id
- Property selector in dashboard header (auto-shown when >1 property)
- Default property auto-created, migration for existing data
- Stats/analytics filtered per property

### API Documentation
- Swagger UI: /api/docs
- ReDoc: /api/redoc
- OpenAPI JSON: /api/openapi.json

### Authentication & Team Management
- JWT auth with httpOnly cookies + Bearer token
- 3 roles: Admin, Manager, Receptionist
- 7 departments: Front Desk, Management, Housekeeping, F&B, Maintenance, Spa, Concierge
- Brute force protection

### Approval Workflow
- Pending -> Draft -> Pending Approval -> Approved/Rejected -> Responded
- Manager/Admin approval queue

### Unique AI Response Engine
- Personalized, non-repetitive responses using GPT-5.2
- 16 languages, auto-detect, translate to English

### Platform Integrations (14)
- Google, Booking.com, TripAdvisor, Airbnb, Expedia, Trip.com, Agoda, Hotels.com, Yelp, Facebook, MakeMyTrip, HRS, Despegar, Hostelworld

### White-Label Branding
- Custom logo, app name, colors, "Powered By" badge

### Code Structure
- /components/dashboard/ -- Extracted ReviewComponents, config
- Backend: FastAPI + MongoDB + JWT
- Frontend: React + Tailwind + Shadcn

## Integration with MyHotelBox.com
- All endpoints prefixed with /api/
- JWT or Bearer token auth for server-to-server
- property_id scopes all data per hotel
- Full OpenAPI spec at /api/openapi.json
- API keys (rhk_ prefix) for external integration
- Webhooks for real-time event notifications

## Next Tasks
1. **P0** - Real bi-directional platform sync (currently MOCKED)
2. **P2** - Continue component extraction from App.js (3800+ lines)
