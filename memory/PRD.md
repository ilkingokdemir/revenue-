# Hotel Review Management Module - PRD

## Original Problem Statement
Hotel management review module to receive all reviews from online platforms (Booking.com, Airbnb, Expedia, Trip.com, Google, TripAdvisor) and respond with AI-generated replies with manual edit capability.

## User Personas
- **Hotel Manager**: Primary user who monitors and responds to guest reviews across multiple platforms
- **Guest Relations Staff**: Team members who handle daily review management

## Core Requirements (Static)
1. Centralized dashboard to view all reviews from multiple OTA platforms
2. AI-powered response generation with different tone options (professional, friendly, apologetic)
3. Manual editing capability before publishing responses
4. Review filtering by platform and response status
5. Analytics overview (total reviews, average rating, response rate, pending count)
6. Email notifications for negative reviews (1-2 stars)
7. Response templates for quick replies

## What's Been Implemented (January 2026)

### Backend (FastAPI + MongoDB)
- Review CRUD API endpoints with filtering
- AI response generation using OpenAI GPT-5.2 via Emergent integrations
- Statistics endpoint for dashboard metrics
- Mock data seeding for demo purposes
- Email notification system for negative reviews
  - Notification settings API (GET/PUT)
  - Test notification endpoint
  - Configurable threshold (1, 2, or 3 stars)
  - Demo mode logging (with Resend integration ready)
- **Response Templates System**
  - Template CRUD API (create, read, update, delete)
  - Category-based organization (positive, negative, neutral, complaint, praise)
  - Usage tracking
  - 6 pre-seeded default templates
  - Placeholder support ({guest_name})

### Frontend (React + Tailwind)
- Organic & Earthy themed dashboard (Moss Green, Sage, Terracotta palette)
- Stats cards: Total Reviews, Average Rating, Response Rate, Pending
- Review list with platform badges and status indicators
- Review detail panel with AI Response Assistant
- Tone selector (Professional/Friendly/Apologetic)
- Typewriter effect for AI-generated responses
- Editable textarea for response customization
- Publish/Update response functionality
- Email Notifications Settings Dialog
  - Enable/disable toggle
  - Email address configuration
  - Alert threshold selection
  - Test notification button
- **Response Templates Manager**
  - Browse Templates tab with category filters
  - Create New tab for custom templates
  - Edit and delete functionality
  - "Use This Template" quick apply
  - Automatic placeholder replacement

### Platforms Supported (MOCKED for demo)
- Booking.com
- Airbnb
- Expedia
- TripAdvisor
- Google
- Trip.com

## Architecture
```
Frontend (React) → Backend (FastAPI) → MongoDB
                         ↓
              OpenAI GPT-5.2 (via Emergent)
                         ↓
              Resend Email Service (for notifications)
```

## Prioritized Backlog

### P0 (Critical - Next Phase)
- Real API integration with platform partner APIs (when credentials available)
- Two-way sync for posting responses back to platforms
- Production Resend API key for real email delivery

### P1 (High Priority)
- User authentication for multi-user access
- Multiple notification recipients
- Template analytics (most used, by category)

### P2 (Medium Priority)
- Sentiment analysis on reviews
- Response performance analytics
- Bulk response actions
- Weekly/monthly review summary reports
- Template sharing between team members

## Next Tasks
1. Obtain API credentials from Booking.com, Airbnb, Google Business Profile
2. Configure production Resend API key for real email delivery
3. Add user authentication module
