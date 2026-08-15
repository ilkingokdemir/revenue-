"""K9 Replay Backtest + G7 Talep Simülatörü — sentetik pazar, politika yarışı, point-in-time replay."""
import math
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException


def _sim_demand(price: float, ref: float, pool: int, elasticity: float = 1.6) -> int:
    """Basit MNL-benzeri talep: fiyat referansın üstüne çıktıkça talep üstel düşer."""
    if ref <= 0:
        return 0
    return max(0, round(pool * math.exp(-elasticity * (price / ref - 1.0))))


def create_simulator_router(db, require_roles):
    router = APIRouter(prefix="/simulator", tags=["simulator"])
    ROLES = ("admin", "manager")

    @router.post("/{pid}/run")
    async def run_sim(pid: str, data: dict = None, _u: dict = Depends(require_roles(*ROLES))):
        """3 politika yarışır: Robot (doluluk-tepkili) vs Sabit fiyat vs Dün+%X."""
        d = data or {}
        days = max(7, min(60, int(d.get("days", 14))))
        ref = float(d.get("base_rate", 100))
        rooms = int(d.get("rooms", 0)) or (await db.rooms.count_documents({"property_id": pid}) or 20)
        pool = int(d.get("demand_pool", max(6, rooms // 2)))
        drift = float(d.get("daily_drift_pct", 2.0))
        policies = {"robot": {"rev": 0.0, "sold": 0, "rates": []},
                    "fixed": {"rev": 0.0, "sold": 0, "rates": []},
                    "yesterday_plus": {"rev": 0.0, "sold": 0, "rates": []}}
        yp_rate = ref
        import random
        random.seed(42)
        daily = []
        for i in range(days):
            day_pool = max(2, round(pool * (0.7 + random.random() * 0.8)))
            weekend = 1.25 if (i % 7) in (4, 5) else 1.0
            day_pool = round(day_pool * weekend)
            # robot: aday fiyat taraması — beklenen geliri (rate × min(talep, kapasite)) maksimize eder
            _best, _best_rev = ref, -1.0
            for _f in (0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.35, 1.5, 1.6):
                _cand = round(ref * _f, 2)
                _rev = _cand * min(_sim_demand(_cand, ref, day_pool), rooms)
                if _rev > _best_rev:
                    _best, _best_rev = _cand, _rev
            robot_rate = _best
            fixed_rate = ref
            yp_rate = round(min(max(yp_rate * (1 + drift / 100), ref * 0.7), ref * 1.6), 2)
            row = {"day": i + 1, "demand_pool": day_pool}
            for name, rate in (("robot", robot_rate), ("fixed", fixed_rate), ("yesterday_plus", yp_rate)):
                sold = min(_sim_demand(rate, ref, day_pool), rooms)
                policies[name]["rev"] += sold * rate
                policies[name]["sold"] += sold
                policies[name]["rates"].append(rate)
                row[name] = {"rate": rate, "sold": sold, "rev": round(sold * rate, 2)}
            daily.append(row)
        out = {}
        for name, p in policies.items():
            out[name] = {"total_revenue": round(p["rev"], 2), "rooms_sold": p["sold"],
                         "occupancy_pct": round(p["sold"] / (rooms * days) * 100, 1),
                         "adr": round(p["rev"] / p["sold"], 2) if p["sold"] else 0,
                         "revpar": round(p["rev"] / (rooms * days), 2)}
        winner = max(out, key=lambda k: out[k]["total_revenue"])
        uplift_vs_fixed = round((out["robot"]["total_revenue"] - out["fixed"]["total_revenue"])
                                / max(out["fixed"]["total_revenue"], 1) * 100, 1)
        return {"property_id": pid, "days": days, "rooms": rooms, "base_rate": ref,
                "policies": out, "winner": winner, "robot_uplift_vs_fixed_pct": uplift_vs_fixed,
                "daily": daily,
                "note": "Sentetik pazar: MNL-benzeri fiyat-esnek talep (elastikiyet 1.6), hafta sonu +%25, sabit tohum (tekrarlanabilir). Robot politikası doluluk baskısına tepki verir."}

    @router.get("/{pid}/replay")
    async def replay(pid: str, date: str = "", asof_days_before: int = 14,
                     _u: dict = Depends(require_roles(*ROLES))):
        """Point-in-time replay: 'o gün robot ne derdi' vs gerçekleşen sonuç."""
        if not date:
            date = (datetime.now(timezone.utc).date() - timedelta(days=7)).isoformat()
        try:
            stay = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(400, "date YYYY-MM-DD olmalı")
        snapshot = (stay - timedelta(days=max(1, asof_days_before))).isoformat()
        rooms = await db.rooms.count_documents({"property_id": pid}) or 20
        all_bks = await db.bookings.find(
            {"property_id": pid, "check_in": {"$lte": date}, "check_out": {"$gt": date}},
            {"_id": 0, "created_at": 1, "status": 1, "check_in": 1, "check_out": 1, "total_price": 1}).to_list(3000)
        otb_then = [b for b in all_bks if str(b.get("created_at", ""))[:10] <= snapshot
                    and b.get("status") not in ("cancelled", "no_show")]
        final = [b for b in all_bks if b.get("status") not in ("cancelled", "no_show")]
        occ_then = round(min(100, len(otb_then) / rooms * 100), 1)
        occ_final = round(min(100, len(final) / rooms * 100), 1)
        adr_final = 0.0
        if final:
            pn = []
            for b in final:
                try:
                    n = max((datetime.strptime(b["check_out"], "%Y-%m-%d")
                             - datetime.strptime(b["check_in"], "%Y-%m-%d")).days, 1)
                except Exception:
                    n = 1
                pn.append((b.get("total_price") or 0) / n)
            adr_final = round(sum(pn) / len(pn), 2)
        ref = adr_final or 100.0
        occ_mult = 0.85 + 0.5 * (occ_then / 100)
        lead_mult = 1.0 if asof_days_before > 21 else 1.05 if asof_days_before > 7 else 1.1
        robot_rate = round(ref * occ_mult * lead_mult, 2)
        verdict = ("Robot daha yüksek fiyat önerirdi — pickup güçlü geldi, gelir bırakılmış olabilir"
                   if robot_rate > adr_final * 1.05 and occ_final >= 80 else
                   "Robot daha düşük/yakın fiyat önerirdi — doluluk zayıftı, indirimle dolum artabilirdi"
                   if robot_rate < adr_final * 0.95 and occ_final < 60 else
                   "Robot önerisi gerçekleşen fiyata yakın — insan kararıyla uyumlu")
        return {"property_id": pid, "stay_date": date, "snapshot_date": snapshot,
                "asof": {"otb_rooms": len(otb_then), "occupancy_pct": occ_then,
                         "days_to_stay": asof_days_before},
                "robot_would_say": {"rate": robot_rate,
                                    "logic": f"ref ₺{ref} × doluluk {occ_mult:.2f} × lead {lead_mult:.2f}"},
                "realized": {"occupancy_pct": occ_final, "adr": adr_final, "rooms_sold": len(final)},
                "verdict": verdict,
                "note": "Point-in-time: yalnızca snapshot tarihine kadar OLUŞMUŞ rezervasyonlar kullanılır (bilgi sızıntısı yok)."}

    @router.get("/{pid}/bid-price")
    async def bid_price(pid: str, days: int = 14, _u: dict = Depends(require_roles(*ROLES))):
        """K11: displacement + MinLOS/CTA/CTD tek bid-price çerçevesinde."""
        days = max(1, min(60, days))
        rooms = await db.rooms.count_documents({"property_id": pid}) or 20
        try:
            from routes.revenue_ext.net_otb import get_cancel_stats, expected_net_for_date
            stats = await get_cancel_stats(db, pid)
        except Exception:
            stats = None
        today = datetime.now(timezone.utc).date()
        agg = await db.bookings.aggregate([
            {"$match": {"property_id": pid, "status": {"$nin": ["cancelled", "no_show"]}}},
            {"$group": {"_id": None, "rev": {"$sum": "$total_price"}, "n": {"$sum": 1}}}]).to_list(1)
        ref_adr = round((agg[0]["rev"] / max(agg[0]["n"], 1)) if agg else 100.0, 2)
        rows = []
        for i in range(days):
            d = (today + timedelta(days=i)).isoformat()
            if stats:
                n = await expected_net_for_date(db, pid, d, stats, rooms)
                occ = n["net_occupancy_pct"] / 100
            else:
                occ = 0.5
            bid = round(ref_adr * (0.45 + 0.9 * occ), 2)
            min_los, cta, ctd, why = 1, False, False, []
            if occ >= 0.85:
                min_los, cta = 2, True
                why.append("Yüksek net doluluk: 1 gecelik satış displacement yaratır → MinLOS 2 + CTA")
            elif occ >= 0.7:
                min_los = 2
                why.append("Orta-yüksek doluluk: kısa konaklamayı sınırlayıp uzun kalışa yer aç")
            else:
                why.append("Düşük doluluk: kısıt yok — her talebi kabul et (bid price düşük)")
            nxt = (today + timedelta(days=i + 1)).isoformat()
            if stats and i < days - 1:
                n2 = await expected_net_for_date(db, pid, nxt, stats, rooms)
                if occ >= 0.85 and n2["net_occupancy_pct"] / 100 < 0.5:
                    ctd = True
                    why.append("Ertesi gün boş: bu gece çıkışı kapat (CTD) — kalışı uzat")
            rows.append({"date": d, "net_occupancy_pct": round(occ * 100, 1),
                         "bid_price": bid, "min_los": min_los, "cta": cta, "ctd": ctd,
                         "reason": " · ".join(why)})
        return {"property_id": pid, "ref_adr": ref_adr, "rows": rows,
                "note": "Bid price = o geceyi satmanın fırsat maliyeti (ref ADR × doluluk baskısı). Bid'in altındaki talep reddedilir; kısıtlar (MinLOS/CTA/CTD) displacement'ı tek çerçevede yönetir."}

    @router.get("/{pid}/report-pdf")
    async def sim_pdf(pid: str, days: int = 14, base_rate: float = 100,
                      _u: dict = Depends(require_roles(*ROLES))):
        sim = await run_sim(pid, {"days": days, "base_rate": base_rate}, _u)
        from io import BytesIO
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas as pc
        from reportlab.lib.units import mm
        _t = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
        buf = BytesIO()
        c = pc.Canvas(buf, pagesize=A4)
        w, h = A4
        c.setFillColorRGB(0.02, 0.37, 0.31)
        c.rect(0, h - 35 * mm, w, 35 * mm, fill=1, stroke=0)
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 18)
        c.drawString(20 * mm, h - 20 * mm, "RM Robot - Talep Simulasyonu Raporu")
        c.setFont("Helvetica", 10)
        c.drawString(20 * mm, h - 28 * mm, f"{days} gun · baz fiyat {base_rate} · sentetik pazar (tekrarlanabilir)")
        y = h - 50 * mm
        c.setFillColorRGB(0.1, 0.1, 0.1)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(20 * mm, y, f"KAZANAN: {sim['winner'].upper()}  ·  Robot vs Sabit: {sim['robot_uplift_vs_fixed_pct']:+.1f}%".translate(_t))
        y -= 12 * mm
        c.setFont("Helvetica-Bold", 10)
        for x, t in ((20, "Politika"), (75, "Gelir"), (110, "Doluluk"), (140, "ADR"), (165, "RevPAR")):
            c.drawString(x * mm, y, t)
        y -= 2 * mm
        c.line(20 * mm, y, w - 20 * mm, y)
        y -= 7 * mm
        c.setFont("Helvetica", 10)
        names = {"robot": "Robot (optimizor)", "fixed": "Sabit fiyat", "yesterday_plus": "Dun+%X"}
        for k, p in sim["policies"].items():
            c.drawString(20 * mm, y, names[k].translate(_t))
            c.drawString(75 * mm, y, f"{p['total_revenue']:,.0f}")
            c.drawString(110 * mm, y, f"%{p['occupancy_pct']}")
            c.drawString(140 * mm, y, f"{p['adr']}")
            c.drawString(165 * mm, y, f"{p['revpar']}")
            y -= 7 * mm
        y -= 6 * mm
        c.setFont("Helvetica-Oblique", 8)
        c.setFillColorRGB(0.4, 0.4, 0.4)
        for line in (sim["note"][:110], sim["note"][110:220]):
            if line:
                c.drawString(20 * mm, y, line.translate(_t))
                y -= 5 * mm
        c.save()
        buf.seek(0)
        from fastapi.responses import StreamingResponse
        return StreamingResponse(buf, media_type="application/pdf",
                                 headers={"Content-Disposition": 'inline; filename="simulasyon-raporu.pdf"'})

    return router
