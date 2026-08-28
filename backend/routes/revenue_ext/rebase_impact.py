"""Rebase Etki Analizi — robotun fiyat rebase senaryosunu katkı/başabaş diliyle raporlar."""
import os
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException

HORIZONS = [("0-30", 0, 30), ("31-60", 31, 60), ("61-90", 61, 90)]
ACTIVE = {"$nin": ["cancelled", "no_show"]}


def _now():
    return datetime.now(timezone.utc)


def _nightly(b):
    n = int(b.get("nights") or 0)
    tp = float(b.get("total_price") or 0)
    if n > 0 and tp > 0:
        return tp / n
    return float(b.get("rate") or 0)


def _median(vals):
    s = sorted(vals)
    if not s:
        return 0
    m = len(s) // 2
    return s[m] if len(s) % 2 else (s[m - 1] + s[m]) / 2


async def _gather_defaults(db, pid: str):
    today = _now().date()
    rooms = await db.rooms.find({"property_id": pid}, {"_id": 0, "id": 1, "room_type_id": 1}).to_list(500)
    rt_counts = {}
    for r in rooms:
        rt_counts[r.get("room_type_id", "")] = rt_counts.get(r.get("room_type_id", ""), 0) + 1
    room_types = await db.room_types.find({"property_id": pid}, {"_id": 0, "id": 1, "name": 1, "base_rate": 1}).to_list(30)
    room_types = [rt for rt in room_types if rt_counts.get(rt["id"], 0) > 0] or room_types

    # Gelecek rezervasyonlar (90 gün ufku) + geçmiş 90 gün gerçekleşen
    fut_end = (today + timedelta(days=90)).isoformat()
    past_start = (today - timedelta(days=90)).isoformat()
    future = await db.bookings.find(
        {"property_id": pid, "status": ACTIVE, "check_in": {"$gte": today.isoformat(), "$lt": fut_end}},
        {"_id": 0, "room_type_id": 1, "check_in": 1, "nights": 1, "total_price": 1, "rate": 1}).to_list(3000)
    past = await db.bookings.find(
        {"property_id": pid, "status": ACTIVE, "check_in": {"$gte": past_start, "$lt": today.isoformat()}},
        {"_id": 0, "room_type_id": 1, "check_in": 1, "created_at": 1, "nights": 1, "total_price": 1, "rate": 1, "rate_plan": 1}).to_list(5000)

    # Net bugün: rt × ufuk ortalama gecelik (on-books)
    net_today = {}
    for b in future:
        try:
            lead = (datetime.strptime(b["check_in"], "%Y-%m-%d").date() - today).days
        except (ValueError, KeyError):
            continue
        for hname, lo, hi in HORIZONS:
            if lo <= lead <= hi:
                net_today.setdefault(b.get("room_type_id", ""), {}).setdefault(hname, []).append(_nightly(b))

    # Son-dakika gerçekleşen (rebase hedef önerisi): son 90 günde lead<=7 gün
    lastmin, ratios, leads_rn = {}, [], []
    missing_rate_plan = 0
    for b in past:
        rn = _nightly(b)
        if not b.get("rate_plan"):
            missing_rate_plan += 1
        try:
            ci = datetime.strptime(b["check_in"], "%Y-%m-%d").date()
            cr = datetime.fromisoformat(str(b.get("created_at", "")).replace("Z", "+00:00")).date()
            lead = (ci - cr).days
        except (ValueError, KeyError, TypeError):
            lead = None
        if lead is not None:
            leads_rn.append((lead, int(b.get("nights") or 1)))
            if lead <= 7 and rn > 0:
                lastmin.setdefault(b.get("room_type_id", ""), []).append(rn)
        rate = float(b.get("rate") or 0)
        if rate > 0 and rn > 0 and 0.2 <= rn / rate <= 1.5:
            ratios.append(rn / rate)

    # Misafir-öder çarpanı
    reliable = len(ratios) >= 5
    mult = round(_median(ratios), 3) if reliable else 1.0
    spread = (round(min(ratios), 2), round(max(ratios), 2)) if ratios else (1.0, 1.0)

    # Geçmiş 90 gün doluluk + karma ADR
    sold_rn = sum(int(b.get("nights") or 0) for b in past)
    avail_rn = max(1, len(rooms) * 90)
    occupancy = min(1.0, sold_rn / avail_rn)
    paid_nightlies = [_nightly(b) for b in past if _nightly(b) > 0]
    blended_adr = round(sum(paid_nightlies) / len(paid_nightlies), 2) if paid_nightlies else 0

    # Rezervasyon penceresi dağılımı (oda-gece ağırlıklı)
    total_lead_rn = sum(n for _, n in leads_rn) or 1
    within30 = round(100 * sum(n for l, n in leads_rn if l <= 30) / total_lead_rn, 1)
    beyond90 = round(100 * sum(n for l, n in leads_rn if l > 90) / total_lead_rn, 1)

    grid = []
    for rt in room_types:
        rtid = rt["id"]
        row = {"room_type_id": rtid, "name": rt.get("name", rtid), "rooms": rt_counts.get(rtid, 0), "horizons": {}}
        lm = lastmin.get(rtid, [])
        lm_avg = round(sum(lm) / len(lm), 2) if lm else 0
        for hname, _lo, _hi in HORIZONS:
            vals = net_today.get(rtid, {}).get(hname, [])
            cur = round(sum(vals) / len(vals), 2) if vals else float(rt.get("base_rate") or blended_adr or 100)
            row["horizons"][hname] = {"net_today": cur, "suggested": lm_avg or round(cur * 0.85, 2), "samples": len(vals)}
        grid.append(row)

    return {
        "grid": grid,
        "multiplier": {"value": mult, "reliable": reliable, "samples": len(ratios), "range": spread},
        "occupancy_90d": round(occupancy * 100, 1),
        "blended_adr_90d": blended_adr,
        "total_rooms": len(rooms),
        "sold_room_nights_90d": sold_rn,
        "available_room_nights_90d": avail_rn,
        "booking_window": {"within_30d_pct": within30, "beyond_90d_pct": beyond90},
        "data_quality": {"missing_rate_plan": missing_rate_plan, "past_bookings": len(past)},
    }


def _narrative_tr(rep):
    c = rep["contribution"]
    be = rep["breakeven"]
    m = rep["multiplier"]
    lines = []
    lines.append(f"Otel geneli net fiyat, rebase sonrası ortalama %{abs(rep['weighted_change_pct'])} {'düşüyor' if rep['weighted_change_pct'] < 0 else 'artıyor'}.")
    if m["reliable"]:
        lines.append(f"Misafir-öder çarpanı {m['value']} olarak gözlendi ({m['samples']} rezervasyon, {m['range'][0]}–{m['range'][1]} bandı) — 'Misafir öder' sütunları bu çarpanla tahmindir, tek bir kesin oran yoktur.")
    else:
        lines.append(f"Güvenilir misafir-öder çarpanı bulunamadı ({m['samples']} örnek) — misafir fiyatları net fiyata eşit varsayıldı; gerçek fark bundan sapabilir.")
    lines.append(f"Aynı dolulukta (%{rep['occupancy_90d']}) 90 günde katkı {c['today_total']:,} → {c['after_total']:,} — kayıp £{c['loss']:,}.")
    if be["feasible"]:
        lines.append(f"Başabaş: katkıyı korumak için oda-gece %{be['rn_increase_pct']} artmalı ({be['rn_today']} → {be['rn_needed']}, müsait {be['rn_available']}). Doluluk %{rep['occupancy_90d']} → %{be['occ_needed_pct']}.")
    else:
        lines.append(f"⛔ Başabaş İMKÂNSIZ: gereken {be['rn_needed']} oda-gece, müsait {be['rn_available']} kapasiteyi aşıyor (%{be['occ_needed_pct']} doluluk gerekir). Bu rebase mevcut kapasiteyle katkıyı geri kazanamaz.")
    return lines


def create_rebase_impact_router(db, require_roles):
    router = APIRouter(tags=["rebase-impact"])
    ROLES = ("admin", "manager")

    @router.get("/revenue/rebase-impact/{property_id}/defaults")
    async def rebase_defaults(property_id: str, _u: dict = Depends(require_roles(*ROLES))):
        return await _gather_defaults(db, property_id)

    @router.post("/revenue/rebase-impact/{property_id}/analyze")
    async def rebase_analyze(property_id: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        targets = data.get("targets") or {}
        commission_pct = float(data.get("commission_pct", 15.0))
        variable_cost = float(data.get("variable_cost", 15.0))
        base = await _gather_defaults(db, property_id)
        mult = float(data.get("multiplier") or base["multiplier"]["value"])

        rows, w_today, w_after, w_rooms = [], 0.0, 0.0, 0
        for rt in base["grid"]:
            rtid, n_rooms = rt["room_type_id"], rt["rooms"] or 1
            for hname, _lo, _hi in HORIZONS:
                h = rt["horizons"][hname]
                tgt = float((targets.get(rtid) or {}).get(hname) or h["suggested"])
                chg = round(100 * (tgt - h["net_today"]) / h["net_today"], 1) if h["net_today"] else 0
                rows.append({
                    "room_type_id": rtid, "room_type": rt["name"], "rooms": rt["rooms"], "horizon": hname,
                    "net_today": h["net_today"], "net_after": round(tgt, 2), "change_pct": chg,
                    "guest_today": round(h["net_today"] * mult, 2), "guest_after": round(tgt * mult, 2),
                })
                w_today += h["net_today"] * n_rooms
                w_after += tgt * n_rooms
                w_rooms += n_rooms
        w_today, w_after = w_today / max(1, w_rooms), w_after / max(1, w_rooms)
        weighted_change = round(100 * (w_after - w_today) / w_today, 1) if w_today else 0

        # Katkı analizi — karma misafir ADR üzerinden
        guest_today = base["blended_adr_90d"] or round(w_today * mult, 2)
        guest_after = round(guest_today * (w_after / w_today), 2) if w_today else guest_today
        net_of_comm_today = round(guest_today * (1 - commission_pct / 100), 2)
        net_of_comm_after = round(guest_after * (1 - commission_pct / 100), 2)
        contrib_today = round(net_of_comm_today - variable_cost, 2)
        contrib_after = round(net_of_comm_after - variable_cost, 2)
        rn_today = base["sold_room_nights_90d"]
        rn_avail = base["available_room_nights_90d"]
        today_total = round(contrib_today * rn_today)
        after_total = round(contrib_after * rn_today)
        loss = today_total - after_total

        # Başabaş
        rn_needed = int(round(today_total / contrib_after)) if contrib_after > 0 else 10 ** 9
        feasible = contrib_after > 0 and rn_needed <= rn_avail
        occ_needed = round(100 * rn_needed / rn_avail, 1) if rn_avail else 0
        rn_increase = round(100 * (rn_needed - rn_today) / rn_today, 1) if rn_today else 0

        report = {
            "id": str(uuid.uuid4()), "property_id": property_id,
            "created_at": _now().isoformat(), "created_by": _u.get("email", ""),
            "rows": rows,
            "weighted": {"net_today": round(w_today, 2), "net_after": round(w_after, 2)},
            "weighted_change_pct": weighted_change,
            "multiplier": base["multiplier"] | {"used": mult},
            "commission_pct": commission_pct, "variable_cost": variable_cost,
            "occupancy_90d": base["occupancy_90d"],
            "contribution": {
                "guest_today": guest_today, "guest_after": guest_after,
                "net_of_comm_today": net_of_comm_today, "net_of_comm_after": net_of_comm_after,
                "per_night_today": contrib_today, "per_night_after": contrib_after,
                "today_total": today_total, "after_total": after_total, "loss": loss,
            },
            "breakeven": {
                "rn_today": rn_today, "rn_needed": rn_needed, "rn_available": rn_avail,
                "rn_increase_pct": rn_increase, "occ_needed_pct": occ_needed, "feasible": feasible,
            },
            "caveats": {
                "volume_note": "Hacim etkisi ölçülmedi — bu fiyatların kaç oda fazla satacağı tabloda yok; bunu ancak canlı deney gösterir.",
                "booking_window": base["booking_window"],
                "window_note": f"Oda-gecelerin %{base['booking_window']['within_30d_pct']}'i zaten 30 gün içinde rezerve ediliyor; %{base['booking_window']['beyond_90d_pct']}'i 90 günden önce — indirimin adres alabileceği uzak-vade kitle bu.",
                "data_quality": base["data_quality"],
                "rate_plan_note": f"{base['data_quality']['past_bookings']} rezervasyonun {base['data_quality']['missing_rate_plan']}'inde rate_plan alanı boş — plan bazlı misafir fiyatı tam öngörülemez.",
            },
        }
        report["narrative_tr"] = _narrative_tr(report)
        await db.rebase_reports.insert_one(dict(report))
        report.pop("_id", None)
        return report

    @router.post("/revenue/rebase-impact/{property_id}/ai-comment")
    async def rebase_ai_comment(property_id: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        report_id = data.get("report_id", "")
        rep = await db.rebase_reports.find_one({"id": report_id, "property_id": property_id}, {"_id": 0})
        if not rep:
            raise HTTPException(status_code=404, detail="Rapor bulunamadı")
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            raise HTTPException(status_code=503, detail="AI anahtarı yapılandırılmamış")
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        c = rep["contribution"]
        be = rep["breakeven"]
        summary = (
            f"Otel geneli net fiyat değişimi: %{rep['weighted_change_pct']}. "
            f"Doluluk (son 90g): %{rep['occupancy_90d']}. Karma misafir ADR: £{c['guest_today']} → £{c['guest_after']}. "
            f"Gece başına katkı: £{c['per_night_today']} → £{c['per_night_after']}. "
            f"90 günde katkı kaybı: £{c['loss']}. "
            f"Başabaş: {be['rn_today']} → {be['rn_needed']} oda-gece (müsait {be['rn_available']}), "
            f"gereken doluluk %{be['occ_needed_pct']}, {'ulaşılabilir' if be['feasible'] else 'İMKÂNSIZ'}. "
            f"Misafir-öder çarpanı: {rep['multiplier'].get('used')} (güvenilir: {rep['multiplier'].get('reliable')})."
        )
        chat = LlmChat(api_key=api_key, session_id=f"rebase-{report_id[:8]}",
                       system_message="Sen kıdemli bir otel gelir yönetimi danışmanısın. Türkçe, dürüst, sayılara dayalı ve kısa yaz. Abartma; riskleri net söyle.").with_model("openai", "gpt-5.2")
        resp = await chat.send_message(UserMessage(
            text=f"Şu rebase analizini 4-6 cümlede yorumla ve net bir tavsiye ver (yap/yapma/kısmi):\n{summary}"))
        comment = str(resp)
        await db.rebase_reports.update_one({"id": report_id}, {"$set": {"ai_comment": comment}})
        return {"comment": comment}

    @router.get("/revenue/rebase-impact/{property_id}/history")
    async def rebase_history(property_id: str, _u: dict = Depends(require_roles(*ROLES))):
        rows = await db.rebase_reports.find({"property_id": property_id}, {"_id": 0, "rows": 0}).sort("created_at", -1).to_list(10)
        return {"reports": rows}

    return router
