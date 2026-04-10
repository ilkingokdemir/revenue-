# Hotel Review Management Module - PRD

## Original Problem Statement
Hotel management review module to receive all reviews from online platforms (Booking.com, Airbnb, Expedia, Trip.com, Google, TripAdvisor) and respond with AI-generated replies with manual edit capability.

## Competitor Analysis (Based on Birdeye, TrustYou, ReviewTrackers)
- AI-powered sentiment analysis ✅
- Multi-platform review aggregation ✅
- Response templates ✅
- Analytics dashboards ✅
- Competitor benchmarking ✅
- Priority queues for urgent reviews ✅
- Automated scheduled reports ✅

## User Personas
- **Hotel Manager**: Primary user who monitors and responds to guest reviews
- **Guest Relations Staff**: Team members handling daily review management
- **Owner/GM**: Views analytics, reports, and competitive positioning

## Core Requirements (Static)
1. Centralized dashboard for multi-platform reviews
2. AI-powered response generation with tone options
3. Manual editing capability before publishing
4. Review filtering by platform and status
5. Analytics overview with actionable insights
6. Email notifications for negative reviews
7. Response templates for quick replies
8. AI sentiment analysis with auto-suggestions
9. Competitor benchmarking for market positioning
10. Automated scheduled performance reports

## What's Been Implemented (January 2026)

### Backend (FastAPI + MongoDB)
- Review CRUD API with filtering
- AI response generation (OpenAI GPT-5.2)
- Statistics endpoint
- Mock data seeding
- Email notifications (Resend)
- Response templates CRUD
- AI Sentiment Analysis
  - Individual & batch analysis
  - Sentiment detection (positive/negative/neutral/mixed)
  - Urgency levels (low/medium/high/critical)
  - Topic extraction
  - Key issues & praises identification
  - Template suggestions based on sentiment
- Analytics Dashboard API
  - Overview metrics
  - Rating distribution
  - Platform performance
  - Urgency breakdown
  - Top topics
  - Common issues/praises
  - Priority queue
- Competitor Benchmarking
  - CRUD for competitors
  - Ranking calculation
  - Demo competitor seeding
- **Scheduled Reports**
  - Report settings API (GET/PUT)
  - HTML report generation
  - Preview endpoint
  - Send now endpoint
  - Report logging
  - Configurable content (competitors, sentiment, action items)
  - Frequency options (daily/weekly/monthly)

### Frontend (React + Tailwind)
- Organic & Earthy themed dashboard
- Stats cards: Reviews, Rating, Response Rate, Pending
- Review list with platform badges and status
- Review detail panel with AI Response Assistant
- Tone selector (Professional/Friendly/Apologetic)
- Typewriter effect for AI responses
- Email Notifications Settings
- Response Templates Manager
- Smart Analysis Section
  - Analyze Review button
  - Sentiment badges (sentiment, urgency, tone)
  - Topic tags
  - Key issues/praises
  - Suggested templates with one-click apply
- Analytics & Insights Dialog
  - Overview tab: metrics, rating distribution, platform stats, priority queue
  - Sentiment tab: sentiment distribution, urgency breakdown, top topics
  - Competitors tab: ranking, comparison table, add competitor form
- **Scheduled Reports Dialog**
  - Enable/disable toggle
  - Email configuration
  - Frequency selector (daily/weekly/monthly)
  - Content toggles (competitors, sentiment, action items)
  - Preview button with modal
  - Send Now button
  - Save Settings
  - Last sent timestamp

### Platforms Supported (MOCKED for demo)
- Booking.com, Airbnb, Expedia, TripAdvisor, Google, Trip.com

## Architecture
```
Frontend (React) → Backend (FastAPI) → MongoDB
                         ↓
              OpenAI GPT-5.2 (Sentiment + Responses)
                         ↓
              Resend (Notifications + Reports)
```

## Report Contents
- Key metrics (reviews, rating, response rate, pending)
- Rating distribution with visual bars
- Sentiment summary with color badges
- Competitive position (#X of Y hotels)
- Competitor comparison table
- Action items & recommendations

## Prioritized Backlog

### P0 (Next Phase)
- Real API integration with platforms
- Production email delivery
- Two-way sync for responses

### P1 (High Priority)
- User authentication
- Multiple notification recipients
- Webhook for scheduled jobs (cron)

### P2 (Medium Priority)
- Trend analysis over time
- Team collaboration features
- White-label customization

## Next Tasks
1. Obtain platform API credentials
2. Configure production Resend key
3. Add user authentication
4. Set up cron job for scheduled reports
