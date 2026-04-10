# Hotel Review Management Module - PRD

## Original Problem Statement
Hotel management review module for MyHotelBox.com to receive all reviews from online platforms and respond with AI-generated unique replies. Includes role-based team access and approval workflow.

## What's Been Implemented

### Authentication & Team Management
- JWT auth with httpOnly cookies + Bearer token support
- 3 roles: Admin, Manager, Receptionist
- 7 departments: Front Desk, Management, Housekeeping, Food & Beverage, Maintenance, Spa & Wellness, Concierge
- Admin user management (create/delete), brute force protection

### Approval Workflow
- Status flow: Pending → Draft → Pending Approval → Approved/Rejected → Responded
- Receptionists draft → submit for approval → Managers approve/reject with notes
- Dedicated approval queue dialog

### Unique AI Response Engine
- Every response personalized using specific review details
- Avoids repeating phrases from recent responses
- Unique sessions prevent caching, varied openings and sign-offs

### Multi-Language AI (16 languages)
- Auto-detect guest language, generate in any language, translate to English

### Platform Integrations (14)
- Google, Booking.com, TripAdvisor, Airbnb, Expedia, Trip.com, Agoda, Hotels.com, Yelp, Facebook, MakeMyTrip, HRS, Despegar, Hostelworld

### White-Label Branding
- Custom logo, app name, colors, "Powered By" badge

### API Documentation
- Swagger UI at /api/docs, ReDoc at /api/redoc, OpenAPI JSON at /api/openapi.json

### Code Refactoring
- Extracted shared components into /components/dashboard/ (config.js, ReviewComponents.jsx)
- Barrel exports via index.js

### Core Features
- AI Response Generation (GPT-5.2), Templates, Sentiment Analysis, Analytics, Competitor Benchmarking, Scheduled Reports, Email Notifications

## Architecture
- Frontend: React + Tailwind CSS + Shadcn UI
- Backend: FastAPI + MongoDB + JWT auth
- AI: OpenAI GPT-5.2 (Emergent LLM Key)

## API Docs
- Swagger: /api/docs
- ReDoc: /api/redoc

## Next Tasks
1. **P0** - Real bi-directional platform sync
2. **P2** - Continue refactoring remaining components out of App.js
