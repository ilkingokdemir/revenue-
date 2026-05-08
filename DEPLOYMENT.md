# My Hotel Box — Deployment & Operations Guide
**Version:** 1.0.247 · **Updated:** Feb 2026

This guide takes you from a fresh Linux box to a running production instance in ~30 minutes.

---

## 1. Architecture
```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  React frontend  │     │  FastAPI backend │     │     MongoDB      │
│  (port 3000)     │ ──▶ │  (port 8001)     │ ──▶ │  (port 27017)    │
└──────────────────┘     └──────────────────┘     └──────────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────────────┐
                    │  External services (optional)   │
                    │  • Emergent LLM (AI)            │
                    │  • Stripe (payments)            │
                    │  • Resend (email)               │
                    │  • Twilio (SMS/WA)              │
                    │  • Onfido / Veriff (ID OCR)     │
                    │  • Booking.com / Expedia (OTA)  │
                    │  • Salto / Assa Abloy (locks)   │
                    └─────────────────────────────────┘
```

## 2. Prerequisites
- Linux server (Ubuntu 22.04 LTS recommended), 4 vCPU, 8 GB RAM, 50 GB SSD minimum
- Python 3.11+, Node 18+, Yarn, MongoDB 7+
- Domain with HTTPS (Let's Encrypt via nginx)
- Optional: Docker if you prefer containers

## 3. First-time setup

```bash
# 1. Clone and install
git clone <your-repo> /app
cd /app/backend && pip install -r requirements.txt
cd /app/frontend && yarn install

# 2. Configure environment (replace with real values)
cp /app/backend/.env.example /app/backend/.env
$EDITOR /app/backend/.env
cp /app/frontend/.env.example /app/frontend/.env
$EDITOR /app/frontend/.env

# 3. Validate env
python3 /app/scripts/validate_env.py

# 4. Start MongoDB (skip if already running)
sudo systemctl start mongod

# 5. Boot via supervisor (preferred) or directly:
cd /app/backend && uvicorn server:app --host 0.0.0.0 --port 8001
cd /app/frontend && yarn build && serve -s build -p 3000

# 6. Verify with smoke test
./scripts/smoke_test.sh
```

## 4. Required environment variables

### `/app/backend/.env`
| Var | Required | Notes |
|---|---|---|
| `MONGO_URL` | ✅ | e.g. `mongodb://localhost:27017` |
| `DB_NAME` | ✅ | e.g. `myhotelbox_prod` |
| `JWT_SECRET` | ✅ in prod | min 32 chars random |
| `EMERGENT_LLM_KEY` | recommended | enables all AI features |
| `STRIPE_API_KEY` | for payments | `sk_live_...` |
| `RESEND_API_KEY` | for email | from resend.com |
| `TWILIO_ACCOUNT_SID` + `TWILIO_AUTH_TOKEN` | for SMS/WA | from twilio.com |
| `ONFIDO_API_KEY` | for ID OCR | from onfido.com |
| `SENTRY_DSN` | for error monitoring | from sentry.io |
| `APP_ENV` | recommended | `production` enables stricter checks |

### `/app/frontend/.env`
| Var | Required | Notes |
|---|---|---|
| `REACT_APP_BACKEND_URL` | ✅ | full URL incl. https |
| `REACT_APP_SENTRY_DSN` | optional | if set, enables Sentry on frontend |
| `REACT_APP_VERSION` | optional | shown in error reports |

## 5. Operations

### Daily backups
```bash
# Cron entry (3:15 AM UTC every day, 30-day retention)
15 3 * * * /app/scripts/backup_mongo.sh /var/backups/myhotelbox 30 >> /var/log/mongo-backup.log 2>&1
```

### Health monitoring
- **Liveness:** `GET /api/health/live` (always 200 if process alive)
- **Readiness:** `GET /api/health/ready` (200 if DB ready, 503 otherwise)
- **Deep:** `GET /api/health` (DB ping + LLM key + Stripe key + disk + uptime)

Wire these into UptimeRobot / BetterStack / Pingdom for alerting.

### Logs
- Backend logs: `tail -f /var/log/supervisor/backend.*.log`
- Each request line includes a `request_id=` token for correlation
- In production set `APP_ENV=production` and forward to Loki / Datadog / CloudWatch

### Rate limits
- Auth `POST /api/auth/login`: 5 attempts / 15 min per IP+email (built-in lockout)
- AI endpoints: rely on Emergent LLM Key budget; configure top-up reminders

### Restart
```bash
sudo supervisorctl restart backend
sudo supervisorctl restart frontend
```

## 6. Scaling notes
- **<100 properties / <500 active users:** single 4 vCPU server is enough
- **100-500 properties:** split MongoDB to a managed Atlas cluster, double backend
- **500+ properties:** multi-region read replicas, CDN for static, Redis for rate limiter (replace in-memory)

## 7. Production cutover checklist
- [ ] Real DNS + HTTPS cert in place
- [ ] `APP_ENV=production` set
- [ ] All required env vars validated by `validate_env.py`
- [ ] Daily Mongo backup cron installed and tested
- [ ] Sentry DSN set on backend + frontend
- [ ] Smoke test passes
- [ ] Stripe live key tested with a real $1 test charge
- [ ] Email sending tested via Resend
- [ ] Legal pages (Terms / Privacy / DPA) deployed at `/legal/*`
- [ ] Admin password rotated from default seed
- [ ] Test user accounts (`/app/memory/test_credentials.md`) deleted or disabled

## 8. Recovery
```bash
# Restore from latest backup
ARCHIVE=$(ls -1t /var/backups/myhotelbox/*.archive.gz | head -1)
mongorestore --gzip --archive="$ARCHIVE" --drop
```

## 9. Support escalation
1. Check `/api/health` → identify degraded subsystem
2. `tail -n 200 /var/log/supervisor/backend.err.log` → find error with `request_id`
3. Search Sentry for the same `request_id` to get the user-facing context
4. If LLM-related: check Emergent LLM Key balance in dashboard
5. If Stripe-related: check stripe.com dashboard for the same `request_id` (set as `metadata`)

---

For module-by-module functionality see `/app/memory/PRD.md`.
For competitive positioning see `/app/memory/COMPETITIVE_ANALYSIS.md`.
For production gap roadmap see `/app/memory/PRODUCTION_READINESS.md`.
