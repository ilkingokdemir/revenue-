# Hotel Review Management Module - PRD

## Original Problem Statement
Hotel management review module for MyHotelBox.com integration. Receive reviews from online platforms, respond with AI-generated unique replies. Role-based team access, approval workflow, multi-property support.

## What's Been Implemented

### MyHotelBox Integration Guide (April 2026)
- Dedicated Integration Guide page with 5-step connection walkthrough
- References MyHotelBox property mapping (e.g., ALDGATE FLATS)
- 8 documented API endpoints with method/path/description
- 4 code snippets: curl fetch reviews, curl AI response, Node.js webhook handler, Python webhook handler
- Webhook payload example with headers documentation
- Copy-to-clipboard on all code blocks

### Webhook Delivery Log (April 2026)
- Stores last 20 deliveries per webhook in MongoDB (webhook_deliveries collection)
- Shows event type, HTTP status, response time (ms), timestamp
- Auto-populates on test ping and webhook events
- Refresh button for real-time log updates
- Tracks success/failure for debugging MyHotelBox integration

### Webhook Test Ping (April 2026)
- POST /api/webhooks/{id}/test sends sample payload to endpoint
- Shows HTTP status + response time in UI
- Handles timeout, connection refused, and generic errors
- Updates delivery count and logs to webhook_deliveries

### Left Sidebar Navigation (April 2026)
- 12 items across 4 sections: Main, Workflow, Connections, Settings
- Connections: Integrations, API Connection, Webhooks, Integration Guide

### API Connection Panel (April 2026)
- CRUD for API keys with rhk_ prefix
- Quick Start docs, Swagger link, admin-only

### Webhooks Panel (April 2026)
- CRUD with 8 event types, toggle, expand details
- Secret management, delivery tracking, delivery log

### Multi-Property Support (April 2026)
- Property CRUD, 8 types, property_id scoping, selector

### Authentication & Team Management
- JWT auth, 3 roles (Admin/Manager/Receptionist), 7 departments, brute force protection

### Approval Workflow
- Pending -> Draft -> Pending Approval -> Approved/Rejected -> Responded

### AI Response Engine
- GPT-5.2 personalized responses, 16 languages, auto-detect

### Platform Integrations (14)
- Google, Booking.com, TripAdvisor, Airbnb, Expedia, Trip.com, Agoda, Hotels.com, Yelp, Facebook, MakeMyTrip, HRS, Despegar, Hostelworld

### White-Label Branding
- Custom logo, app name, colors, "Powered By" badge

## Integration with MyHotelBox.com
- All endpoints prefixed with /api/
- JWT or Bearer token auth (rhk_ API keys) for server-to-server
- property_id maps to MyHotelBox branches (e.g., ALDGATE FLATS)
- Webhooks send real-time events to MyHotelBox endpoints
- Full OpenAPI spec at /api/docs
- Integration Guide with code examples for Node.js and Python

## Next Tasks
1. **P0** - Real bi-directional platform sync (currently MOCKED)
2. **P2** - Break down App.js (4500+ lines) into components
