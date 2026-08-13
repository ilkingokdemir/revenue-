"""
Profit-First Pricing (Net Contribution) — BEONx/Propeter paritesi.
Fiyat kararlarını brüt ciro yerine NET KÂR üzerinden değerlendirir:
  net = oda fiyatı − OTA komisyonu − CPOR (dolu oda başı maliyet) + beklenen ekstra harcama (kanal bazlı)

Endpoints (/api/profit-pricing/*):
- GET  /{property_id}?days=14        → kanal × tarih net katkı matrisi + bulgular
- GET  /{property_id}/settings       → CPOR + kanal bazlı ancillary ayarları
- PUT  /{property_id}/settings       → ayarları güncelle
- GET  /{property_id}/autopilot      → otopilot durumu + aktif stop-sell'ler + log
- POST /{property_id}/autopilot      → {enabled: bool}
- POST /{property_id}/autopilot/run  → manuel tetik

KÂR OTOPİLOTU: gece yarısı (UTC 00) cron ile çalışır (workers.profit_autopilot_loop).
Ortalama net katkısı ≤ 0 olan OTA kanalları için channel_stop_sells kaydı açar,
net pozitife dönen kanalların otomatik stop-sell'ini kaldırır ve yöneticiye bildirim atar.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict

from fastapi import APIRouter, Depends

from routes.distribution.push_history import resolve_rate
from routes.integrations_pkg.ota_commission import _get_rate, DEFAULT_RATES, CHANNEL_LABELS

DEFAULT_SETTINGS = {
    "cpor": 18.0,  # cost per occupied room (temizlik, amenity, enerji)
    "payment_fee_pct": 1.5,  # POS/sanal pos ödeme ücreti (%)
    "direct_acquisition_cost": 5.0,  # direct rezervasyon başına pazarlama/sadakat maliyeti / oda-gece
    "ancillary": {  # kanal bazlı beklenen ekstra harcama / oda-gece (F&B, spa, upsell)
        "direct": 22.0, "booking_com": 10.0, "expedia": 8.0,
        "airbnb": 6.0, "agoda": 8.0, "trip_com": 8.0,
    },
    "refund_risk_pct": {  # kanal bazlı beklenen iptal/iade/chargeback kaybı (%)
        "direct": 3.0, "booking_com": 8.0, "expedia": 8.0,
        "airbnb": 5.0, "agoda": 8.0, "trip_com": 8.0,
    },
    "promo_funding_pct": {  # OTA kampanya fonlaması (otelin cebinden çıkan indirim %)
        "direct": 0.0, "booking_com": 0.0, "expedia": 0.0,
        "airbnb": 0.0, "agoda": 0.0, "trip_com": 0.0,
    },
}


async def _get_settings(db, pid: str) -> Dict:
    row = await db.profit_pricing_settings.find_one({"property_id": pid}, {"_id": 0})
    if not row:
        return {k: (dict(v) if isinstance(v, dict) else v) for k, v in DEFAULT_SETTINGS.items()}
    out = {}
    for key in ("ancillary", "refund_risk_pct", "promo_funding_pct"):
        merged = dict(DEFAULT_SETTINGS[key])
        merged.update(row.get(key) or {})
        out[key] = merged
    out["cpor"] = float(row.get("cpor", DEFAULT_SETTINGS["cpor"]))
    out["payment_fee_pct"] = float(row.get("payment_fee_pct", DEFAULT_SETTINGS["payment_fee_pct"]))
    out["direct_acquisition_cost"] = float(row.get("direct_acquisition_cost", DEFAULT_SETTINGS["direct_acquisition_cost"]))
    out["autopilot_enabled"] = bool(row.get("autopilot_enabled", False))
    return out


async def compute_channel_nets(db, property_id: str, days: int = 14) -> Dict:
    s = await _get_settings(db, property_id)
    cpor, anc = s["cpor"], s["ancillary"]
    pay_fee = s["payment_fee_pct"] / 100
    dac = s["direct_acquisition_cost"]
    refund = {ch: v / 100 for ch, v in s["refund_risk_pct"].items()}
    promo = {ch: v / 100 for ch, v in s["promo_funding_pct"].items()}
    comm = {ch: await _get_rate(db, ch, property_id) for ch in DEFAULT_RATES}
    today = datetime.now(timezone.utc).date()
    rows, ch_totals = [], {ch: 0.0 for ch in DEFAULT_RATES}
    for i in range(days):
        d = (today + timedelta(days=i)).isoformat()
        gross, src = await resolve_rate(db, property_id, d)
        cells = {}
        for ch in DEFAULT_RATES:
            commission = round(gross * comm[ch], 2)
            deductions = round(
                commission + gross * pay_fee + cpor
                + gross * refund.get(ch, 0) + gross * promo.get(ch, 0)
                + (dac if ch == "direct" else 0), 2)
            net = round(gross - deductions + anc.get(ch, 0), 2)
            cells[ch] = {"gross": round(gross, 2), "commission": commission,
                         "deductions": deductions, "net": net}
            ch_totals[ch] += net
        rows.append({"date": d, "gross": round(gross, 2), "rate_source": src, "channels": cells})
    ch_avg = {ch: round(v / days, 2) for ch, v in ch_totals.items()}
    return {"settings": s, "commission_rates": comm, "rows": rows, "channel_net_avg": ch_avg}


async def run_profit_autopilot(db, property_id: str, days: int = 14, trigger: str = "cron") -> Dict:
    """Negatif net kanalları otomatik stop-sell'e alır; pozitife dönenleri serbest bırakır."""
    s = await _get_settings(db, property_id)
    if trigger == "cron" and not s.get("autopilot_enabled"):
        return {"ok": True, "skipped": "autopilot_disabled"}
    data = await compute_channel_nets(db, property_id, days)
    ch_avg = data["channel_net_avg"]
    now = datetime.now(timezone.utc).isoformat()
    today = datetime.now(timezone.utc).date()
    to_date = (today + timedelta(days=days)).isoformat()
    actions = []
    for ch, net in ch_avg.items():
        if ch == "direct":
            continue
        label = CHANNEL_LABELS.get(ch, ch)
        if net <= 0:
            existing = await db.channel_stop_sells.find_one(
                {"property_id": property_id, "channel": ch, "active": True,
                 "source": "profit_autopilot"}, {"_id": 0, "id": 1})
            if existing:
                await db.channel_stop_sells.update_one(
                    {"id": existing["id"]},
                    {"$set": {"to_date": to_date, "net_avg": net, "renewed_at": now}})
                actions.append({"channel": ch, "action": "renewed", "net_avg": net})
            else:
                await db.channel_stop_sells.insert_one({
                    "id": str(uuid.uuid4()), "property_id": property_id, "channel": ch,
                    "from_date": today.isoformat(), "to_date": to_date, "active": True,
                    "source": "profit_autopilot", "net_avg": net,
                    "reason": f"Ø net katkı {net} (negatif) — Kâr Otopilotu stop-sell",
                    "created_at": now})
                await db.notifications.insert_one({
                    "id": str(uuid.uuid4()), "type": "warning",
                    "title": "Kâr Otopilotu: Kanal stop-sell",
                    "message": f"{label} kanalı komisyon+CPOR sonrası ZARAR ediyor (Ø net {net}). "
                               f"{today.isoformat()} → {to_date} arası otomatik stop-sell alındı.",
                    "category": "revenue", "target_user": "", "target_role": "manager",
                    "link_to": "profit-pricing", "priority": "high",
                    "read": False, "created_by": "Kâr Otopilotu", "created_at": now})
                actions.append({"channel": ch, "action": "stop_sell", "net_avg": net})
        else:
            r = await db.channel_stop_sells.update_many(
                {"property_id": property_id, "channel": ch, "active": True,
                 "source": "profit_autopilot"},
                {"$set": {"active": False, "released_at": now, "release_net_avg": net}})
            if r.modified_count:
                await db.notifications.insert_one({
                    "id": str(uuid.uuid4()), "type": "success",
                    "title": "Kâr Otopilotu: Kanal yeniden açıldı",
                    "message": f"{label} net katkısı pozitife döndü (Ø {net}) — stop-sell kaldırıldı.",
                    "category": "revenue", "target_user": "", "target_role": "manager",
                    "link_to": "profit-pricing", "priority": "medium",
                    "read": False, "created_by": "Kâr Otopilotu", "created_at": now})
                actions.append({"channel": ch, "action": "released", "net_avg": net})
    await db.profit_autopilot_log.insert_one({
        "id": str(uuid.uuid4()), "property_id": property_id, "run_at": now,
        "trigger": trigger, "actions": actions, "channel_net_avg": ch_avg})
    return {"ok": True, "trigger": trigger, "actions": actions, "channel_net_avg": ch_avg}


def create_profit_pricing_router(db, require_roles):
    router = APIRouter(prefix="/profit-pricing", tags=["profit-pricing"])

    @router.get("/{property_id}/settings")
    async def get_settings(property_id: str,
                           _: dict = Depends(require_roles("admin", "manager"))):
        s = await _get_settings(db, property_id)
        return {**s, "channel_labels": CHANNEL_LABELS}

    @router.put("/{property_id}/settings")
    async def put_settings(property_id: str, body: Dict,
                           _: dict = Depends(require_roles("admin", "manager"))):
        cpor = max(0.0, float(body.get("cpor", DEFAULT_SETTINGS["cpor"]) or 0))
        pay_fee = max(0.0, min(float(body.get("payment_fee_pct", DEFAULT_SETTINGS["payment_fee_pct"]) or 0), 10))
        dac = max(0.0, float(body.get("direct_acquisition_cost", DEFAULT_SETTINGS["direct_acquisition_cost"]) or 0))
        upd = {"property_id": property_id, "cpor": cpor, "payment_fee_pct": pay_fee,
               "direct_acquisition_cost": dac,
               "updated_at": datetime.now(timezone.utc).isoformat()}
        for key in ("ancillary", "refund_risk_pct", "promo_funding_pct"):
            merged = {}
            for ch in DEFAULT_RATES:
                try:
                    merged[ch] = max(0.0, float((body.get(key) or {}).get(ch, DEFAULT_SETTINGS[key].get(ch, 0))))
                except (TypeError, ValueError):
                    merged[ch] = DEFAULT_SETTINGS[key].get(ch, 0)
            upd[key] = merged
        await db.profit_pricing_settings.update_one(
            {"property_id": property_id}, {"$set": upd}, upsert=True)
        return {"ok": True, **{k: v for k, v in upd.items() if k not in ("property_id", "updated_at")}}

    @router.get("/{property_id}/autopilot")
    async def autopilot_status(property_id: str,
                               _: dict = Depends(require_roles("admin", "manager"))):
        s = await _get_settings(db, property_id)
        active = await db.channel_stop_sells.find(
            {"property_id": property_id, "active": True, "source": "profit_autopilot"},
            {"_id": 0}).to_list(20)
        logs = await db.profit_autopilot_log.find(
            {"property_id": property_id}, {"_id": 0}).sort("run_at", -1).to_list(10)
        return {"enabled": s.get("autopilot_enabled", False),
                "channel_labels": CHANNEL_LABELS,
                "active_stop_sells": active,
                "last_run": logs[0]["run_at"] if logs else None,
                "log": logs}

    @router.post("/{property_id}/autopilot")
    async def autopilot_toggle(property_id: str, body: Dict,
                               _: dict = Depends(require_roles("admin", "manager"))):
        enabled = bool(body.get("enabled"))
        await db.profit_pricing_settings.update_one(
            {"property_id": property_id},
            {"$set": {"property_id": property_id, "autopilot_enabled": enabled,
                      "updated_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True)
        return {"ok": True, "enabled": enabled}

    @router.post("/{property_id}/autopilot/run")
    async def autopilot_run(property_id: str,
                            _: dict = Depends(require_roles("admin", "manager"))):
        return await run_profit_autopilot(db, property_id, trigger="manual")

    @router.get("/{property_id}")
    async def profit_matrix(property_id: str, days: int = 14,
                            _: dict = Depends(require_roles("admin", "manager"))):
        days = max(3, min(days, 30))
        data = await compute_channel_nets(db, property_id, days)
        s, comm, rows, ch_avg = data["settings"], data["commission_rates"], data["rows"], data["channel_net_avg"]
        direct_net = ch_avg.get("direct", 0)
        findings = []
        for ch in DEFAULT_RATES:
            if ch == "direct":
                continue
            gap = round(direct_net - ch_avg[ch], 2)
            gap_pct = round(gap / direct_net * 100, 1) if direct_net else 0
            avg_gross = rows[0]["gross"] if rows else 0
            if ch_avg[ch] <= 0:
                findings.append({
                    "channel": ch, "label": CHANNEL_LABELS.get(ch, ch), "severity": "critical",
                    "net_avg": ch_avg[ch], "gap_vs_direct": gap,
                    "suggestion": f"{CHANNEL_LABELS.get(ch, ch)} kanalında net katkı NEGATİF — bu tarihlerde stop-sell veya en az %{max(5, round((abs(ch_avg[ch]) + 5) / max(avg_gross, 1) * 100))} kanal fiyat artışı önerilir."})
            elif gap_pct >= 15:
                markup = round(gap / max(1 - comm[ch], 0.01), 2)
                findings.append({
                    "channel": ch, "label": CHANNEL_LABELS.get(ch, ch), "severity": "warning",
                    "net_avg": ch_avg[ch], "gap_vs_direct": gap,
                    "suggestion": f"{CHANNEL_LABELS.get(ch, ch)} net kârı direktten %{gap_pct} düşük — kanal fiyatına +{markup} eklenirse net eşitlenir; ya da direct-conversion kuponu ile misafiri direkte çekin."})

        best = max(ch_avg, key=ch_avg.get)
        worst = min(ch_avg, key=ch_avg.get)
        return {
            "property_id": property_id, "days": days,
            "settings": {k: s[k] for k in ("cpor", "payment_fee_pct", "direct_acquisition_cost",
                                           "ancillary", "refund_risk_pct", "promo_funding_pct")},
            "autopilot_enabled": s.get("autopilot_enabled", False),
            "commission_rates": comm, "channel_labels": CHANNEL_LABELS,
            "channel_net_avg": ch_avg,
            "summary": {
                "best_channel": {"channel": best, "label": CHANNEL_LABELS.get(best, best), "net_avg": ch_avg[best]},
                "worst_channel": {"channel": worst, "label": CHANNEL_LABELS.get(worst, worst), "net_avg": ch_avg[worst]},
                "direct_premium": round(direct_net - ch_avg[worst], 2),
            },
            "findings": findings, "matrix": rows,
        }

    return router
