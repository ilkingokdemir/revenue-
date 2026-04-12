# My Hotel Box - Product Requirements Document

## Original Problem Statement
Hotel management software "My Hotel Box" — full-stack platform rivaling Chatlyn (messaging), M3 (accounting), Apicbase (stock), Prostay (POS), Cloudbeds (payments). Do NOT build: Channel Manager, Dynamic Pricing, Space Bookings.

## Tech Stack
React + Tailwind + Shadcn UI | FastAPI + MongoDB | OpenAI GPT-5.2, Resend, Stripe, iyzico, PayTR

## What's Been Implemented

### Payment Gateway (Cloudbeds-level)
- Stripe Virtual Payments, iyzico/PayTR Virtual Checkout (Turkish), Guest Payment Portal, Payment Reminders
- Physical Card Terminals, Payment Dashboard, Transaction management

### Real Outbound Messaging (NEW)
- **WhatsApp**: Real Meta Cloud API integration with send/receive
- **Telegram**: Real Bot API integration with send/receive
- **SMS**: Real Twilio integration with send/receive
- **Email**: Resend integration (active)
- **Inbound Webhooks**: /api/messaging/webhook/whatsapp|telegram|twilio
- **Connection Verification**: /api/messaging/verify-connection/{channel}
- **Channel Settings UI**: Setup guides, webhook URLs, credential fields, Verify Connection buttons

### Other Modules (All Complete)
Booking Engine, Review Hub, Unified Messaging, Guest Surveys, Accounting (18 tabs), POS, Stock Management

## Testing: 64 iterations, all passing

## How to Go Live
1. **WhatsApp**: Enter Meta Phone Number ID + Access Token in Channel Settings, set webhook to /api/messaging/webhook/whatsapp
2. **Telegram**: Enter Bot Token, set webhook to /api/messaging/webhook/telegram
3. **SMS**: Enter Twilio Account SID + Auth Token + Phone Number, set webhook to /api/messaging/webhook/twilio
4. **Turkish Payments**: Enter iyzico/PayTR API keys in Terminal Settings
