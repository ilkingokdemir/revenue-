"""Robot Güven Merkezi — guardrail config/ihlal logu, öneri kabul oranı raporu, shadow mode."""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

REJECT_TAG_LABELS = {
    "too_aggressive": "Çok agresif artış",
    "too_low": "Gereksiz indirim",
    "event_unknown": "Motor etkinliği bilmiyor",
    "segment_mismatch": "Segment/kanal uyumsuz",
    "data_wrong": "Veri hatalı",
    "strategy_conflict": "Stratejiye aykırı",
    "other": "Diğer",
}

BLIND_SPOT_RECS = {
    "too_aggressive": "Adım tavanını (max_up_pct) düşürmeyi veya otonom güven eşiğini yükseltmeyi değerlendirin.",
    "too_low": "Taban fiyat / bid-price alt sınırını gözden geçirin; gereksiz indirim baskısı olabilir.",
    "event_unknown": "Etkinlik sinyal kaynaklarını genişletin (tarama yarıçapı, venue listesi, takvim sinyalleri).",
    "segment_mismatch": "Segment/kanal bazlı fiyat katmanlarını ve kanal kurallarını motor konfigürasyonuna işleyin.",
    "data_wrong": "PMS/OTB veri senkronunu ve pazar tarama tazeliğini kontrol edin.",
    "strategy_conflict": "Strateji dönemlerini (fiyat dondurma, promosyon) motor kısıtı olarak tanımlayın.",
    "other": "Serbest metin nedenlerini inceleyip yeni etiket türetin.",
}


async def run_outcome_evaluation(db, limit: int = 200) -> dict:
    """K2: tarihi geçmiş uygulanmış fiyat kararlarının GERÇEKLEŞEN sonucunu kaydeder."""
    today = datetime.now(timezone.utc).date().isoformat()
    decs = await db.ai_pricing_decisions.find(
        {"status": {"$in": ["accepted", "auto-applied"]}, "date": {"$lt": today},
         "outcome_recorded": {"$exists": False}},
        {"_id": 0}).to_list(limit)
    evaluated = 0
    rooms_cache = {}
    for d in decs:
        pid = d["property_id"]
        if pid not in rooms_cache:
            rooms_cache[pid] = await db.rooms.count_documents({"property_id": pid}) or 20
        bks = await db.bookings.find(
            {"property_id": pid, "check_in": {"$lte": d["date"]}, "check_out": {"$gt": d["date"]},
             "status": {"$nin": ["cancelled", "no_show"]}},
            {"_id": 0, "check_in": 1, "check_out": 1, "total_price": 1}).to_list(2000)
        occ = round(min(100, len(bks) / rooms_cache[pid] * 100), 1)
        adr = 0.0
        if bks:
            per_night = []
            for b in bks:
                try:
                    n = max((datetime.strptime(b["check_out"], "%Y-%m-%d")
                             - datetime.strptime(b["check_in"], "%Y-%m-%d")).days, 1)
                except Exception:
                    n = 1
                per_night.append((b.get("total_price") or 0) / n)
            adr = round(sum(per_night) / len(per_night), 2)
        occ_at_dec = float(d.get("occupancy_pct") or 0)
        outcome = {"realized_occupancy_pct": occ, "realized_adr": adr,
                   "occ_at_decision": occ_at_dec, "occ_delta": round(occ - occ_at_dec, 1),
                   "decision_rate": d.get("new_rate"), "evaluated_at": datetime.now(timezone.utc).isoformat()}
        await db.ai_pricing_decisions.update_one(
            {"property_id": pid, "date": d["date"], "room_type_id": d.get("room_type_id", "")},
            {"$set": {"outcome_recorded": True, "outcome": outcome}})
        await db.decision_outcomes.insert_one({"property_id": pid, "date": d["date"],
                                               "status": d["status"], **outcome})
        evaluated += 1
    return {"evaluated": evaluated}


async def run_shadow_snapshot(db, pid: str) -> dict:
    """Robot önerilerini push ETMEDEN kaydeder — otelin gerçek fiyatıyla kıyas için."""
    import routes.revenue_ext.ai_pricing_engine as eng
    builder = getattr(eng, "BUILD_SUGGESTIONS", None)
    if builder is None:
        raise HTTPException(500, "Fiyat motoru henüz başlatılmadı")
    payload = await builder(pid, 30, use_llm=False)
    today = datetime.now(timezone.utc).date().isoformat()
    n = 0
    for s in payload.get("suggestions", []):
        human = float(s.get("current_rate") or 0)
        robot = float(s.get("suggested_rate") or 0)
        diff_pct = round((robot - human) / human * 100, 1) if human else None
        await db.shadow_log.update_one(
            {"property_id": pid, "snapshot_date": today, "date": s["date"],
             "room_type_id": s.get("room_type_id", "")},
            {"$set": {"property_id": pid, "snapshot_date": today, "date": s["date"],
                      "room_type_id": s.get("room_type_id", ""),
                      "robot_rate": robot, "human_rate": human, "diff_pct": diff_pct,
                      "occupancy_pct": s.get("occupancy_pct"),
                      "rationale": s.get("rationale"),
                      "created_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True)
        n += 1
    return {"snapshot_date": today, "recorded": n}


def create_trust_center_router(db, require_roles):
    router = APIRouter(tags=["trust-center"])
    ROLES = ("admin", "manager")

    # ---------- G1: Guardrail config + ihlal logu ----------
    @router.get("/guardrails/{pid}/config")
    async def get_gr_config(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        g = await db.guardrail_config.find_one({"property_id": pid}, {"_id": 0}) or {}
        bcount = await db.bookings.count_documents({"property_id": pid})
        return {"property_id": pid,
                "max_up_pct": float(g.get("max_up_pct", g.get("max_step_pct", 15))),
                "max_down_pct": float(g.get("max_down_pct", g.get("max_step_pct", 15))),
                "cold_start_mode": g.get("cold_start_mode", "auto"),
                "cold_start_active": g.get("cold_start_mode", "auto") == "auto" and bcount < 100,
                "daily_push_limit": int(g.get("daily_push_limit", 50))}

    @router.put("/guardrails/{pid}/config")
    async def put_gr_config(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        upd = {"property_id": pid,
               "max_up_pct": max(1.0, min(50.0, float(data.get("max_up_pct", data.get("max_step_pct", 15))))),
               "max_down_pct": max(0.0, min(50.0, float(data.get("max_down_pct", data.get("max_step_pct", 15))))),
               "cold_start_mode": data.get("cold_start_mode") if data.get("cold_start_mode") in ("auto", "off") else "auto",
               "daily_push_limit": max(1, min(500, int(data.get("daily_push_limit", 50)))),
               "updated_at": datetime.now(timezone.utc).isoformat()}
        await db.guardrail_config.update_one({"property_id": pid}, {"$set": upd}, upsert=True)
        return {"ok": True, **{k: upd[k] for k in ("max_up_pct", "max_down_pct", "cold_start_mode", "daily_push_limit")}}

    # ---------- K3: Kill Switch ----------
    @router.get("/kill-switch/{pid}")
    async def kill_status(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        ks = await db.kill_switch.find_one(
            {"property_id": {"$in": [pid, "global"]}, "active": True}, {"_id": 0})
        return {"active": bool(ks), "scope": (ks or {}).get("property_id"), "since": (ks or {}).get("activated_at")}

    @router.post("/kill-switch/{pid}/activate")
    async def kill_on(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        now = datetime.now(timezone.utc).isoformat()
        await db.kill_switch.update_one(
            {"property_id": pid},
            {"$set": {"property_id": pid, "active": True, "activated_at": now,
                      "activated_by": _u.get("name", "")}}, upsert=True)
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()), "type": "warning", "title": "🛑 KILL SWITCH AKTİF",
            "message": f"Tüm robot fiyat push'ları durduruldu ({pid}). Tekrar açana kadar hiçbir otomatik fiyat uygulanmaz.",
            "category": "revenue", "target_user": "", "target_role": "manager",
            "link_to": "trust-center", "priority": "high", "read": False,
            "created_by": _u.get("name", ""), "created_at": now})
        return {"ok": True, "active": True}

    @router.post("/kill-switch/{pid}/deactivate")
    async def kill_off(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        await db.kill_switch.update_one({"property_id": pid}, {"$set": {"active": False}})
        return {"ok": True, "active": False}

    # ---------- K2: Karar sonuç takibi ----------
    @router.get("/rms-acceptance/{pid}/outcomes")
    async def outcomes(pid: str, limit: int = 20, _u: dict = Depends(require_roles(*ROLES))):
        rows = await db.decision_outcomes.find(
            {"property_id": pid}, {"_id": 0}).sort("date", -1).to_list(min(limit, 100))
        n = len(rows)
        return {"outcomes": rows, "count": n,
                "avg_occ_delta": round(sum(r["occ_delta"] for r in rows) / n, 1) if n else None,
                "note": "Karar → gerçekleşen sonuç zinciri: fiyat kararı anındaki doluluk vs tarihin nihai doluluk/ADR'si."}

    @router.post("/rms-acceptance/{pid}/evaluate-outcomes")
    async def evaluate_now(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        return {"ok": True, **(await run_outcome_evaluation(db))}

    @router.get("/guardrails/{pid}/violations")
    async def violations(pid: str, limit: int = 50, _u: dict = Depends(require_roles(*ROLES))):
        rows = await db.guardrail_violations.find(
            {"property_id": pid}, {"_id": 0}).sort("created_at", -1).to_list(min(limit, 200))
        today_start = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00")
        pushed_today = await db.ai_pricing_decisions.count_documents({
            "property_id": pid, "decided_at": {"$gte": today_start},
            "status": {"$in": ["accepted", "auto-applied"]}})
        return {"violations": rows, "pushed_today": pushed_today}

    # ---------- G2: Öneri kabul oranı raporu ----------
    @router.get("/rms-acceptance/{pid}/report")
    async def acceptance_report(pid: str, weeks: int = 8, _u: dict = Depends(require_roles(*ROLES))):
        weeks = max(2, min(26, weeks))
        since = (datetime.now(timezone.utc) - timedelta(weeks=weeks)).isoformat()
        decs = await db.ai_pricing_decisions.find(
            {"property_id": pid, "decided_at": {"$gte": since}},
            {"_id": 0, "status": 1, "decided_at": 1, "reason": 1, "reason_tag": 1}).to_list(10000)
        weekly, reasons, tag_counts = {}, {}, {}
        acc_total, rej_total, auto_total = 0, 0, 0
        for d in decs:
            try:
                wk = datetime.fromisoformat(d["decided_at"].replace("Z", "")).strftime("%G-W%V")
            except Exception:
                continue
            w = weekly.setdefault(wk, {"week": wk, "accepted": 0, "rejected": 0, "auto_applied": 0})
            st = d.get("status")
            if st == "accepted":
                w["accepted"] += 1
                acc_total += 1
            elif st == "auto-applied":
                w["auto_applied"] += 1
                auto_total += 1
            elif st == "rejected":
                w["rejected"] += 1
                rej_total += 1
                reason = (d.get("reason") or "belirtilmedi").strip()[:60]
                reasons[reason] = reasons.get(reason, 0) + 1
                if d.get("reason_tag"):
                    tag_counts[d["reason_tag"]] = tag_counts.get(d["reason_tag"], 0) + 1
        out = sorted(weekly.values(), key=lambda x: x["week"])
        for w in out:
            decided = w["accepted"] + w["auto_applied"] + w["rejected"]
            w["acceptance_rate_pct"] = round((w["accepted"] + w["auto_applied"]) / decided * 100, 1) if decided else None
        decided_all = acc_total + auto_total + rej_total
        monthly_tags = {}
        for d in decs:
            if d.get("status") == "rejected" and d.get("reason_tag"):
                mk = str(d.get("decided_at") or "")[:7]
                monthly_tags.setdefault(mk, {})
                monthly_tags[mk][d["reason_tag"]] = monthly_tags[mk].get(d["reason_tag"], 0) + 1
        blind_spot = None
        if tag_counts:
            top_tag, top_n = max(tag_counts.items(), key=lambda x: x[1])
            total_tagged = sum(tag_counts.values())
            blind_spot = {"tag": top_tag, "label": REJECT_TAG_LABELS.get(top_tag, top_tag),
                          "count": top_n, "total_tagged": total_tagged,
                          "share_pct": round(top_n / total_tagged * 100, 0),
                          "recommendation": BLIND_SPOT_RECS.get(top_tag, "")}
        return {"property_id": pid, "weeks": out,
                "blind_spot": blind_spot,
                "monthly_tags": [{"month": k, "tags": {t: n for t, n in v.items()},
                                  "labels": {t: REJECT_TAG_LABELS.get(t, t) for t in v}}
                                 for k, v in sorted(monthly_tags.items())],
                "reasons": sorted([{"reason": k, "count": v} for k, v in reasons.items()],
                                  key=lambda x: -x["count"])[:10],
                "reason_tags": sorted([{"tag": k, "label": REJECT_TAG_LABELS.get(k, k), "count": v}
                                       for k, v in tag_counts.items()], key=lambda x: -x["count"]),
                "tag_taxonomy": [{"tag": k, "label": v} for k, v in REJECT_TAG_LABELS.items()],
                "total_accepted": acc_total, "total_auto_applied": auto_total,
                "total_rejected": rej_total,
                "overall_acceptance_pct": round((acc_total + auto_total) / decided_all * 100, 1) if decided_all else None,
                "target_pct": 70,
                "note": "Hedef kabul oranı ≥%70. Red nedenleri modelin kör nokta haritasıdır — etiketli veri olarak saklanır."}

    # ---------- D1: Uyum İlkeleri Anayasası ----------
    @router.get("/compliance-principles")
    async def compliance_principles(_u: dict = Depends(require_roles(*ROLES))):
        import os
        path = "/app/memory/UYUM_ILKELERI_D1.md"
        if not os.path.exists(path):
            raise HTTPException(404, "Uyum ilkeleri belgesi bulunamadı")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        return {"title": "Uyum İlkeleri Anayasası (D1)", "content": content,
                "updated_at": datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc).isoformat()}

    @router.post("/rms-acceptance/{pid}/blind-spot-alert/run")
    async def run_blind_spot_alert(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        from workers import check_blind_spot_alert
        return await check_blind_spot_alert(db, pid)

    # ---------- Rakip Karşılaştırma (Gap Analizi) PDF ----------
    @router.get("/competitive-gap-pdf")
    async def competitive_gap_pdf(pid: str = "", customer: str = "",
                                  _u: dict = Depends(require_roles(*ROLES))):
        """Rakip gap analizi tablosu — müşteri sunumu için markalı PDF."""
        ts = {}
        if pid:
            ts = await db.template_settings.find_one({"property_id": pid}, {"_id": 0}) or {}
        logo_url = (ts.get("logo_url") or "").strip()
        hotel_name = (ts.get("hotel_name") or "").strip()
        customer = (customer or "").strip()[:60]
        rows = [
            ("G1", "Tek adim +-% limit + gunluk push tavani", "VAR", "Asimetrik adim limiti + cold-start korumasi + gunluk tavan + ihlal logu"),
            ("G2", "Kabul orani + red nedeni taksonomisi", "VAR", "8 haftalik kabul raporu + 7 etiketli red taksonomisi + kor nokta radari"),
            ("G3", "Uyum ilkeleri anayasasi (D1)", "VAR", "6 ilke, Robot Guven Merkezi'nde goruntulenebilir"),
            ("G4", "Beklenen Net OTB (p_cancel)", "VAR", "Lead/kanal/iade bazli iptal+no-show modeli, overbooking optimizer"),
            ("G5", "Iptal modeli kalibrasyonu", "VAR", "Aylik otomatik kalibrasyon + Brier + veri-guven kapisi"),
            ("G6", "Shadow Mode + cikis kriterleri", "VAR", ">=28 gun + uyum >=%60 yazili cikis kriteri"),
            ("G7", "Talep simulatoru / backtest", "VAR", "Point-in-time replay + politika taramasi + nedensel analiz"),
            ("G8", "Lisansli rate shopping", "KISMI", "scraper/licensed/mock mod anahtari hazir - feed sozlesmesi karar bekliyor"),
            ("G9", "Esneklik randomizasyonu", "VAR", "Guc analizli fiyat deneyi + dogal deney tespiti"),
            ("G10", "Havuz veri izni / transfer learning", "VAR", "Tesis bazli consent bayragi + benchmark haric tutma"),
            ("+", "HotelRunner yazma adaptoru", "VAR", "Canli push + drift auto-repush"),
            ("+", "Hava durumu sinyali", "VAR", "open-meteo, otel bazli ayarlanabilir carpan, motora entegre"),
            ("+", "Resmi tatil takvimi", "VAR", "Nager.Date, tatil/arife carpani, motora entegre"),
            ("+", "KVKK/GDPR modulu", "VAR", "Veri arama/export/silme + denetim logu"),
            ("+", "Grup wash + rate parity monitor", "VAR", "Grup wash robotu + kanal parite izleme"),
            ("+", "RGI / MPI / ARI endeksleri", "VAR", "STR dilinde haftalik endeks kaniti"),
            ("+", "Haftalik + aylik yonetici PDF", "VAR", "Kanal performans + yonetici ozeti PDF'leri"),
        ]
        uniques = ["Kanit zarfi + guven semantigi", "Bid-price displacement agi (MinLOS/CTA/CTD)",
                   "Publisher sertifikasyonu + kill switch tatbikat robotu",
                   "Kanal ekonomisi (komisyon/VAT/promo ile net katki)",
                   "Fiyat faktor selalesi + aciklanabilir oneri kaniti"]
        from io import BytesIO
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas as pc
        from reportlab.lib.units import mm
        buf = BytesIO()
        c = pc.Canvas(buf, pagesize=A4)
        w, hh = A4
        _t = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
        c.setFillColorRGB(0.05, 0.09, 0.16)
        c.rect(0, hh - 30 * mm, w, 30 * mm, fill=1, stroke=0)
        if logo_url:
            try:
                import httpx
                from reportlab.lib.utils import ImageReader
                async with httpx.AsyncClient(timeout=10, follow_redirects=True) as cl:
                    lr = await cl.get(logo_url)
                if lr.status_code == 200:
                    img = ImageReader(BytesIO(lr.content))
                    iw, ih = img.getSize()
                    lw = 24 * mm
                    lh = lw * ih / iw
                    c.drawImage(img, w - lw - 10 * mm, hh - lh - 5 * mm, width=lw, height=lh,
                                mask="auto", preserveAspectRatio=True)
            except Exception:
                pass
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(16 * mm, hh - 12 * mm, "Rakip Gap Analizi - Kapsam Karsilastirmasi")
        c.setFont("Helvetica", 9)
        c.drawString(16 * mm, hh - 19 * mm,
                     f"MyHotelBox RMS · {datetime.now(timezone.utc).date().isoformat()} · 17 kalemde 16 VAR / 1 KISMI")
        brand_line = ""
        if customer:
            brand_line = f"{customer} icin hazirlanmistir"
        elif hotel_name:
            brand_line = f"{hotel_name} icin hazirlanmistir"
        if brand_line:
            c.setFont("Helvetica-BoldOblique", 10)
            c.setFillColorRGB(0.99, 0.85, 0.4)
            c.drawString(16 * mm, hh - 26 * mm, brand_line.translate(_t))
        y = hh - 40 * mm
        for code, item, st, note in rows:
            if y < 26 * mm:
                c.showPage()
                y = hh - 20 * mm
            c.setFont("Helvetica-Bold", 9)
            c.setFillColorRGB(0.15, 0.15, 0.15)
            c.drawString(16 * mm, y, f"{code}  {item}")
            c.setFillColorRGB(*(0.02, 0.45, 0.35) if st == "VAR" else (0.8, 0.55, 0.05))
            c.drawRightString(w - 16 * mm, y, st)
            y -= 4.6 * mm
            c.setFont("Helvetica", 8)
            c.setFillColorRGB(0.42, 0.42, 0.42)
            c.drawString(22 * mm, y, note[:110])
            y -= 6.2 * mm
        y -= 3 * mm
        if y < 50 * mm:
            c.showPage()
            y = hh - 20 * mm
        c.setFont("Helvetica-Bold", 11)
        c.setFillColorRGB(0.1, 0.1, 0.1)
        c.drawString(16 * mm, y, "Rakip listesinde hic olmayan farklarimiz")
        y -= 7 * mm
        c.setFont("Helvetica", 8.5)
        for u in uniques:
            c.setFillColorRGB(0.25, 0.25, 0.25)
            c.drawString(22 * mm, y, "+ " + u)
            y -= 5.5 * mm
        y -= 4 * mm
        c.setFont("Helvetica-Oblique", 7.5)
        c.setFillColorRGB(0.45, 0.45, 0.45)
        c.drawString(16 * mm, y, "G8 notu: lisansli feed teknik olarak hazir; saglayici sozlesmesi (OTA Insight/Lighthouse vb.) ticari karardir.")
        c.save()
        buf.seek(0)
        from fastapi.responses import StreamingResponse
        return StreamingResponse(buf, media_type="application/pdf",
                                 headers={"Content-Disposition": 'inline; filename="rakip-gap-analizi.pdf"'})

    # ---------- G6: Shadow Mode ----------
    @router.get("/shadow-mode/{pid}/status")
    async def shadow_status(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        s = await db.shadow_mode.find_one({"property_id": pid}, {"_id": 0}) or {}
        snaps = await db.shadow_log.distinct("snapshot_date", {"property_id": pid})
        return {"property_id": pid, "active": bool(s.get("active")),
                "started_at": s.get("started_at"), "snapshot_days": len(snaps)}

    @router.post("/shadow-mode/{pid}/start")
    async def shadow_start(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        await db.shadow_mode.update_one(
            {"property_id": pid},
            {"$set": {"property_id": pid, "active": True,
                      "started_at": datetime.now(timezone.utc).isoformat(),
                      "started_by": _u.get("name", "")}}, upsert=True)
        return {"ok": True, "active": True,
                "note": "Shadow mode AÇIK: robot her gün önerir ama HİÇBİR fiyat push edilmez. 4 hafta sonunda kıyas raporunu inceleyin."}

    @router.post("/shadow-mode/{pid}/stop")
    async def shadow_stop(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        await db.shadow_mode.update_one({"property_id": pid}, {"$set": {"active": False}})
        return {"ok": True, "active": False}

    @router.post("/shadow-mode/{pid}/snapshot")
    async def shadow_snapshot(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        return {"ok": True, **(await run_shadow_snapshot(db, pid))}

    @router.get("/shadow-mode/{pid}/report")
    async def shadow_report(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        rows = await db.shadow_log.find(
            {"property_id": pid, "diff_pct": {"$ne": None}}, {"_id": 0}).to_list(20000)
        if not rows:
            return {"property_id": pid, "samples": 0, "weeks": [],
                    "note": "Henüz shadow verisi yok — shadow mode'u başlatın veya manuel snapshot alın."}
        diffs = [r["diff_pct"] for r in rows]
        agree = sum(1 for d in diffs if abs(d) <= 5)
        higher = sum(1 for d in diffs if d > 5)
        lower = sum(1 for d in diffs if d < -5)
        weekly = {}
        for r in rows:
            wk = datetime.strptime(r["snapshot_date"], "%Y-%m-%d").strftime("%G-W%V")
            w = weekly.setdefault(wk, {"week": wk, "n": 0, "sum_diff": 0.0, "agree": 0})
            w["n"] += 1
            w["sum_diff"] += r["diff_pct"]
            w["agree"] += 1 if abs(r["diff_pct"]) <= 5 else 0
        out = []
        for w in sorted(weekly.values(), key=lambda x: x["week"]):
            out.append({"week": w["week"], "samples": w["n"],
                        "avg_diff_pct": round(w["sum_diff"] / w["n"], 1),
                        "agreement_pct": round(w["agree"] / w["n"] * 100, 1)})
        snaps = sorted({r["snapshot_date"] for r in rows})
        agreement_pct = round(agree / len(diffs) * 100, 1)
        exit_ready = len(snaps) >= 28 and agreement_pct >= 60
        return {"property_id": pid, "samples": len(rows),
                "snapshot_days": len(snaps), "first_snapshot": snaps[0], "last_snapshot": snaps[-1],
                "avg_diff_pct": round(sum(diffs) / len(diffs), 1),
                "agreement_pct": agreement_pct,
                "robot_higher_pct": round(higher / len(diffs) * 100, 1),
                "robot_lower_pct": round(lower / len(diffs) * 100, 1),
                "weeks": out,
                "exit_criteria": {"min_days": 28, "min_agreement_pct": 60,
                                  "days_done": len(snaps), "ready_for_live": exit_ready},
                "note": "Uyum = |fark| ≤ %5. Çıkış kriteri: ≥28 gün snapshot VE uyum ≥%60 → canlıya geçmeye hazır."}

    return router
