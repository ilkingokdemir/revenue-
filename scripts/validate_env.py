#!/usr/bin/env python3
"""
Boot-time env var validator.

Run before starting backend in production:
    python3 /app/scripts/validate_env.py && uvicorn server:app

Exits non-zero if a REQUIRED var is missing.
Prints a warning per missing RECOMMENDED var.

Reads from /app/backend/.env if present, then env.
"""
import os
import sys
from pathlib import Path

# Best-effort load .env files into os.environ for validation
def _load_dotenv(path: Path):
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

_load_dotenv(Path("/app/backend/.env"))
_load_dotenv(Path("/app/frontend/.env"))

REQUIRED = ["MONGO_URL", "DB_NAME"]
RECOMMENDED = {
    "EMERGENT_LLM_KEY": "AI features (Pricing Explain, HK Turnover scoring, Copilot, Anomaly) will be disabled.",
    "JWT_SECRET": "Auth tokens will use a derived dev secret — NOT safe for production.",
    "STRIPE_API_KEY": "Tipping, deposits, gift cards, pre-auth will be disabled.",
}
PRODUCTION_RECOMMENDED = {
    "RESEND_API_KEY": "Transactional email (booking confirmations, invoices, surveys) will be disabled.",
    "TWILIO_ACCOUNT_SID": "SMS + WhatsApp messaging will be disabled.",
    "ONFIDO_API_KEY": "Self check-in passport OCR will be disabled.",
    "SENTRY_DSN": "Production error monitoring will be disabled.",
    "REACT_APP_BACKEND_URL": "Frontend cannot reach the API.",
}


def colorize(text, color):
    if not sys.stdout.isatty():
        return text
    codes = {"red": 31, "yellow": 33, "green": 32, "cyan": 36, "bold": 1}
    return f"\033[{codes.get(color, 0)}m{text}\033[0m"


def main() -> int:
    print(colorize("=== Env Validation ===", "bold"))

    missing_required = [k for k in REQUIRED if not os.environ.get(k)]
    if missing_required:
        for k in missing_required:
            print(colorize(f"  ❌ MISSING REQUIRED: {k}", "red"))
        print(colorize("Cannot boot. Set the variables and retry.", "red"))
        return 2

    print(colorize(f"  ✅ All {len(REQUIRED)} required vars set", "green"))

    missing_recommended = []
    for k, why in RECOMMENDED.items():
        if not os.environ.get(k):
            missing_recommended.append((k, why))
            print(colorize(f"  ⚠️  RECOMMENDED missing: {k}", "yellow"))
            print(f"     reason: {why}")

    if not missing_recommended:
        print(colorize(f"  ✅ All {len(RECOMMENDED)} recommended vars set", "green"))

    is_prod = os.environ.get("APP_ENV", "dev").lower() in ("prod", "production")
    if is_prod:
        for k, why in PRODUCTION_RECOMMENDED.items():
            if not os.environ.get(k):
                print(colorize(f"  ⚠️  PROD missing: {k}", "yellow"))
                print(f"     reason: {why}")

    print(colorize("=== OK ===", "green"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
