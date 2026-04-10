# Hotel Review Management Module - PRD

## Original Problem Statement
Hotel management review module for MyHotelBox.com integration. Receive reviews from online platforms, respond with AI-generated unique replies. Role-based team access, approval workflow, multi-property support.

## What's Been Implemented

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
- 66 documented endpoints

### Authentication & Team Management
- JWT auth with httpOnly cookies + Bearer token
- 3 roles: Admin, Manager, Receptionist
- 7 departments: Front Desk, Management, Housekeeping, F&B, Maintenance, Spa, Concierge
- Brute force protection

### Approval Workflow
- Pending → Draft → Pending Approval → Approved/Rejected → Responded
- Manager/Admin approval queue

### Unique AI Response Engine
- Personalized, non-repetitive responses using GPT-5.2
- 16 languages, auto-detect, translate to English

### Platform Integrations (14)
- Google, Booking.com, TripAdvisor, Airbnb, Expedia, Trip.com, Agoda, Hotels.com, Yelp, Facebook, MakeMyTrip, HRS, Despegar, Hostelworld

### White-Label Branding
- Custom logo, app name, colors, "Powered By" badge

### Code Structure
- /components/dashboard/ — Extracted ReviewComponents, config
- Backend: FastAPI + MongoDB + JWT
- Frontend: React + Tailwind + Shadcn

## Integration with MyHotelBox.com
- All endpoints prefixed with /api/
- JWT or Bearer token auth for server-to-server
- property_id scopes all data per hotel
- Full OpenAPI spec at /api/openapi.json

## Next Tasks
1. **P0** - Real bi-directional platform sync
2. **P2** - Continue component extraction from App.js
