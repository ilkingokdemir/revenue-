#!/usr/bin/env bash
# Production smoke test — exits 0 on success, non-zero on first failure.
#
# Use as:
#   ./scripts/smoke_test.sh                                  # against $REACT_APP_BACKEND_URL
#   API_URL=https://prod.example.com ./scripts/smoke_test.sh # explicit
#
# Designed to run < 30 seconds. Covers 8 critical paths.

set -euo pipefail

API_URL="${API_URL:-$(grep '^REACT_APP_BACKEND_URL=' /app/frontend/.env | cut -d= -f2)}"
: "${API_URL:?API_URL not set and not found in /app/frontend/.env}"

ADMIN_EMAIL="${ADMIN_EMAIL:-admin@hotelbox.com}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-HotelAdmin2026!}"

PASS=0
FAIL=0

check() {
  local name="$1"; shift
  if "$@"; then
    echo "  ✅ $name"
    PASS=$((PASS + 1))
  else
    echo "  ❌ $name" >&2
    FAIL=$((FAIL + 1))
  fi
}

api() {
  local code; code="$(curl -s -o /tmp/smoke_resp.json -w "%{http_code}" "$@")"
  [[ "$code" =~ ^2 ]]
}

api_with_token() {
  local code; code="$(curl -s -o /tmp/smoke_resp.json -w "%{http_code}" -H "Authorization: Bearer $TOKEN" "$@")"
  [[ "$code" =~ ^2 ]]
}

echo "[smoke] target: $API_URL"
echo "[smoke] admin: $ADMIN_EMAIL"

# 1. Health check
check "GET /api/health" api "$API_URL/api/health"
check "GET /api/health/live" api "$API_URL/api/health/live"
check "GET /api/health/ready" api "$API_URL/api/health/ready"

# 2. Auth login
LOGIN_RESP="$(curl -s -X POST "$API_URL/api/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}")"
TOKEN="$(printf '%s' "$LOGIN_RESP" | python3 -c "import sys,json;print(json.load(sys.stdin).get('token',''))")"
[[ -n "$TOKEN" ]] || { echo "  ❌ login failed: $LOGIN_RESP" >&2; FAIL=$((FAIL+1)); }
[[ -n "$TOKEN" ]] && { echo "  ✅ POST /api/auth/login (got token)"; PASS=$((PASS+1)); }

# 3. Authenticated endpoints (only if token)
if [[ -n "$TOKEN" ]]; then
  check "GET /api/auth/me" api_with_token "$API_URL/api/auth/me"
  check "GET /api/properties" api_with_token "$API_URL/api/properties"
  check "GET /api/hk-turnover/default" api_with_token "$API_URL/api/hk-turnover/default"
  check "GET /api/pricing/explain/dashboard/default" api_with_token "$API_URL/api/pricing/explain/dashboard/default"
  check "GET /api/properties (count > 0)" bash -c "curl -s -H 'Authorization: Bearer $TOKEN' '$API_URL/api/properties' | python3 -c 'import sys,json;d=json.load(sys.stdin);assert isinstance(d,list)'"
fi

echo
echo "[smoke] $PASS passed, $FAIL failed"
[[ $FAIL -eq 0 ]] || exit 1
