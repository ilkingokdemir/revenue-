# Channel Manager · Competitor Benchmark + MVP Build Map
_Iter 160 · Feb 2026_

---

## Part 1 · Competitor Feature Matrix

| Feature | Mews | Cloudbeds (MyAllocator) | SiteMinder | Eviivo | STAAH | **You** |
|---|---|---|---|---|---|---|
| # of channels | 100+ | 350+ | 450+ | 50+ | 200+ | **9** (Booking.com, Expedia, Airbnb, Hotels.com, Agoda, Trip.com, Google Hotels, Trivago, Direct) |
| 2-way sync (rates + avail + inventory) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ (simulated) |
| **Restrictions** — MinLOS, MaxLOS, CTA, CTD, StopSell | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ **GAP** |
| **Reservation delivery** — OTA books → appears in PMS | ✅ webhook | ✅ webhook | ✅ webhook | ✅ webhook | ✅ webhook | ❌ **GAP** |
| **iCal sync** for Airbnb/VRBO | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ **GAP** |
| **Room/Rate-plan mapping** | ✅ UI | ✅ UI | ✅ UI | ✅ UI | ✅ UI | ⚠️ partial |
| **Parity monitoring** | ✅ | ⚠️ | ✅ | ⚠️ | ✅ | ❌ **GAP** |
| Rate markup / derivation rules | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Push logs / audit | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Retry queue with backoff | ✅ | ✅ | ✅ | ⚠️ | ✅ | ❌ |
| Channel performance leaderboard | ✅ | ✅ | ⚠️ | ⚠️ | ⚠️ | ⚠️ partial |
| Content sync (photos/amenities) | ✅ | ✅ | ✅ | ⚠️ | ⚠️ | ❌ (nice-to-have) |
| Pooled inventory | ✅ | ✅ | ✅ | ⚠️ | ✅ | ⚠️ partial |
| OTA-specific rate plans (virtual, promo, mobile) | ✅ | ✅ | ✅ | ⚠️ | ✅ | ❌ (nice-to-have) |

---

## Part 2 · What's Really Missing (Pareto 80/20)

Of the 13 missing capabilities, **the 5 that drive 80% of the value** for a first-class Channel Manager MVP:

### 🔴 P0 (must-have)
1. **Restrictions Engine** — MinLOS, MaxLOS, CTA, CTD, StopSell per channel × date. Without this, you can't run yield strategies like "min 3 nights for Friday–Sunday Booking.com" or "stop sell on Expedia for Christmas week."
2. **Inbound Reservation Delivery** — MVP via (a) manual OTA entry + (b) iCal URL polling for Airbnb/VRBO. Real-time webhooks for Booking.com/Expedia require partner API keys.
3. **Parity Monitor** — detects when a channel's effective rate drifts outside configured tolerance (e.g. ±5%). Critical for contract compliance.

### 🟠 P1 (should-have)
4. **Room/Rate-plan Mapping UI** — clear matrix of {our room_type → channel-specific room_id} and {our rate_plan → channel rate code}. Already partially present in `PropertyMappingPanel`, needs channel-specific extension.
5. **Sync Queue with Retry** — failed pushes re-queued with exponential backoff (1min, 5min, 15min, 1hr). Ops visibility into stuck syncs.

### 🟢 P2 (nice-to-have)
6. Content sync · 7. Pooled inventory UI · 8. OTA-specific rate plans · 9. More channel connectors · 10. Live webhook receivers (need partner credentials)

---

## Part 3 · MVP Build — Iter 160

Shipping the **3 P0 items in one iteration** with full backend + frontend + testing. P1/P2 can follow if you want.

### 🛠 Feature 1 · Restrictions Engine
**Collection**: `channel_restrictions`
```
{
  id, property_id, channel_id, date,
  min_los, max_los, closed_to_arrival, closed_to_departure, stop_sell,
  room_type_id?  (null = all rooms),
  updated_at, updated_by
}
```
**Endpoints** (`routes/channel_restrictions.py`):
- `GET /api/channel-restrictions/{property_id}?from_date=&to_date=&channel_id=` — grid data
- `PUT /api/channel-restrictions/{property_id}/bulk` — bulk upsert for date range × channels
- `DELETE /api/channel-restrictions/{id}`
- Integrates with the existing `push_rates` endpoint — restrictions pushed alongside rates in the payload.

**UI** (`ChannelRestrictionsPanel`): date-range × channel matrix with quick-toggle chips for Stop Sell, CTA, CTD. Inline editors for MinLOS/MaxLOS.

### 🛠 Feature 2 · Inbound Reservations
**Collection**: `inbound_reservations` + auto-creates `bookings`
**Endpoints** (`routes/channel_inbound.py`):
- `POST /api/channel-inbound/manual` — paste-based OTA reservation entry with mandatory fields (channel, channel_booking_ref, guest_name, check_in, check_out, room_type, total_price). Creates our own booking + links to channel_reference.
- `POST /api/channel-inbound/ical/fetch` — pulls an iCal URL and imports VEVENTs as bookings. Dedupe by UID.
- `GET /api/channel-inbound/pending/{property_id}` — recent inbound awaiting review / confirmation.
- `POST /api/channel-inbound/confirm/{id}` — move from pending to active booking.
- Already registered `channel_inbound` job in scheduler for nightly iCal pulls.

**UI** (`ChannelInboundPanel`): two tabs — "Manual Entry" form and "iCal Sources" list with last-pull timestamp + pull-now button.

### 🛠 Feature 3 · Parity Monitor
**Endpoints** (`routes/channel_parity.py`):
- `GET /api/channel-parity/{property_id}?days=14&tolerance=5` — for each channel × date, computes effective rate (our rate × markup rule), compares to direct-website baseline, flags violations > tolerance %. Returns {violations[], by_channel[], summary}.
- `POST /api/channel-parity/config` — set per-property tolerance + alert email.
- Parity check runs as a scheduled job (uses existing scheduler engine from Iter 159).

**UI** (`ChannelParityPanel`): violation table + heat-strip per channel showing which dates are out of parity.

---

## Part 4 · Build Timeline

Single iteration:
1. Backend: 3 new route files, 3 new collections, scheduler hook (~25 min)
2. Frontend: 3 new panels (reuse existing ChannelManager grid pattern)
3. Sidebar wiring under "Channel Manager" umbrella
4. Testing agent covers 100% of new endpoints + UI flows

**Not shipping now** (need external credentials or too large):
- Live webhook receivers for Booking.com/Expedia (need partner API keys)
- Content sync (requires channel content APIs)
- 100+ additional channel connectors (each is a separate integration)

---

## Part 5 · Post-MVP Roadmap

After Iter 160, remaining channel-manager gaps:
- Room/Rate-plan Mapping UI extensions (~0.5d)
- Sync Queue with Retry backoff (~0.5d)
- Live Booking.com Commercial API webhook receiver (needs Booking.com partner agreement)
- Live Expedia Partner Central webhook receiver (needs Expedia partner agreement)
- Airbnb listings API (needs Airbnb partner — very restricted)
- Real-time WebSocket updates to the rate grid when OTA bookings arrive

These are business-dev blockers more than engineering ones.
