# Hotel Review Management Module - PRD

## Original Problem Statement
Hotel management review module to receive all reviews from online platforms and respond with AI-generated replies. Integrated with MyHotelBox.com.

## What's Been Implemented

### Authentication & Team Management (April 2026)
- JWT auth with httpOnly cookies + Bearer token support
- 3 roles: Admin, Manager, Receptionist
- 7 hotel departments: Front Desk, Management, Housekeeping, Food & Beverage, Maintenance, Spa & Wellness, Concierge
- Admin can create/delete users, assign roles & departments
- Brute force protection (5 attempts = 15 min lockout)
- Auto-seeded admin account on startup

### Approval Workflow (April 2026)
- Status flow: Pending → Draft → Pending Approval → Approved/Rejected → Responded
- Receptionists draft AI responses, submit for approval
- Managers/Admins approve or reject with notes
- Approval queue dialog for managers
- Status filter includes all workflow states

### Unique AI Response Engine (April 2026)
- Every response is unique and personalized
- References specific review details (room, dates, experiences)
- Avoids reusing opening lines from recent responses
- Unique session IDs prevent caching
- Varied sentence structure and creative sign-offs

### Multi-Language AI (April 2026)
- 16 languages supported
- Auto-detects guest language with confidence score
- Generates replies in selected/detected language
- "Translate to English" button for staff verification

### Platform Integrations (14 Total)
- Google, Booking.com, TripAdvisor, Airbnb, Expedia, Trip.com
- Agoda, Hotels.com, Yelp, Facebook, MakeMyTrip, HRS, Despegar, Hostelworld

### White-Label Branding
- Custom logo, app name, colors, "Powered By" badge

### UI/UX
- DM Sans font, earthy hospitality theme, rounded cards, emerald AI panel

### Core Features
- AI Response Generation (GPT-5.2 via Emergent Key)
- Response Templates, Sentiment Analysis, Analytics, Competitor Benchmarking
- Scheduled Reports, Email Notifications (Resend)

## Architecture
- Frontend: React + Tailwind CSS + Shadcn UI
- Backend: FastAPI + MongoDB
- AI: OpenAI GPT-5.2 (Emergent LLM Key)
- Auth: JWT + bcrypt + httpOnly cookies

## Next Tasks
1. **P0** - Real bi-directional platform sync
2. **P2** - Refactor App.js (3700+ lines) into modular components
