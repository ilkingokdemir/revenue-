"""
Data Quality Autopilot — "Üç bağımsız rapor" 2 numaralı önceliği.
Fiyat motorunu besleyen verideki sessiz hataları otomatik tespit eder,
güvenli olanlara tek tık düzeltme sunar.

VERİ NÖBETÇİSİ (Iter 512): workers.data_quality_sentinel_loop her gece (UTC 01)
tüm tesisleri tarar; skor < 70 olursa veya önceki taramaya göre ≥15 puan düşerse
yöneticiye bildirim gönderir.

Dedektörler:
  - mapping_drift        : son 30 günde room_types'ta karşılığı olmayan oda tipiyle gelen rezervasyonlar
  - orphan_rate_overrides: var olmayan room_type_id'ye bağlı fiyat override'ları (AUTO-FIX)
  - price_unit_anomaly   : medyanın 8 katından büyük / %20'sinden küçük override fiyatları (kur/birim hatası)
  - stale_rates          : 7 günden uzun süredir hiç fiyat güncellenmemesi
  - cost_defaults        : CPOR/maliyet ayarlarının hiç doğrulanmamış varsayılanda kalması
  - duplicate_bookings   : aynı e-posta + tarih + oda tipiyle mükerrer rezervasyon şüphesi

Endpoints (/api/data-quality/*):
- GET  /{property_id}         → issues[] + health_score + son taramalar
- POST /{property_id}/fix/orphan_rate_overrides → güvenli temizlik
"""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

SEVERITY_WEIGHTS = {"critical": 25, "warning": 10, "info": 3}


async def _room_type_sets(db, pid: str):
    ids, names = set(), set()
    async for rt in db.room_types.find({"property_id": pid}, {"_id": 0, "id": 1, "name": 1}):
        ids.add(rt.get("id"))
        names.add((rt.get("name") or "").strip().lower())
    return ids, names


async def detect_issues(db, pid: str):
    issues = []
    rt_ids, rt_names = await _room_type_sets(db, pid)
    cutoff30 = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    # 1. mapping drift
    drift = {}
    async for b in db.bookings.find(
            {"property_id": pid, "created_at": {"$gte": cutoff30}},
            {"_id": 0, "room_type": 1}):
        n = (b.get("room_type") or "").strip()
        if n and rt_names and n.lower() not in rt_names:
            drift[n] = drift.get(n, 0) + 1
    if drift:
        issues.append({
            "type": "mapping_drift", "severity": "critical", "count": sum(drift.values()),
            "message": f"Son 30 günde tanımsız oda tipiyle {sum(drift.values())} rezervasyon: {', '.join(list(drift)[:4])}",
            "suggestion": "OTA oda tipi eşleştirmesini (mapping) güncelleyin — bu rezervasyonlar forecast ve fiyat motoruna yanlış giriyor.",
            "auto_fixable": False})

    # 2. orphan rate overrides
    orphans = 0
    async for o in db.rate_overrides.find(
            {"property_id": pid, "room_type_id": {"$nin": ["", None]}},
            {"_id": 0, "room_type_id": 1}):
        if rt_ids and o.get("room_type_id") not in rt_ids:
            orphans += 1
    if orphans:
        issues.append({
            "type": "orphan_rate_overrides", "severity": "warning", "count": orphans,
            "message": f"Silinmiş oda tiplerine bağlı {orphans} fiyat override'ı duruyor.",
            "suggestion": "Tek tıkla temizlenebilir — motor bu kayıtları gereksiz tarıyor.",
            "auto_fixable": True})

    # 3. price unit anomaly
    rates = [o["custom_rate"] async for o in db.rate_overrides.find(
        {"property_id": pid, "custom_rate": {"$gt": 0}}, {"_id": 0, "custom_rate": 1}).limit(3000)]
    if len(rates) >= 10:
        rates.sort()
        median = rates[len(rates) // 2]
        weird = [r for r in rates if r > median * 8 or r < median * 0.2]
        if weird:
            issues.append({
                "type": "price_unit_anomaly", "severity": "critical", "count": len(weird),
                "message": f"Medyan {median:.0f} iken {len(weird)} override aşırı sapıyor (örn. {weird[-1]:.0f}, {weird[0]:.0f}) — kur/birim hatası olabilir.",
                "suggestion": "Bu fiyatları Rate Calendar'da kontrol edin; OTA'ya yanlış birimle gitmiş olabilir.",
                "auto_fixable": False})

    # 4. stale rates
    last = await db.rate_overrides.find_one(
        {"property_id": pid}, {"_id": 0, "updated_at": 1}, sort=[("updated_at", -1)])
    if last and last.get("updated_at"):
        try:
            age_d = (datetime.now(timezone.utc)
                     - datetime.fromisoformat(last["updated_at"])).days
            if age_d > 7:
                issues.append({
                    "type": "stale_rates", "severity": "warning", "count": age_d,
                    "message": f"Son fiyat güncellemesi {age_d} gün önce — envanter bayatlamış olabilir.",
                    "suggestion": "AI fiyatlamayı çalıştırın veya otomasyonun loglarını kontrol edin.",
                    "auto_fixable": False})
        except ValueError:
            pass

    # 5. cost defaults never verified
    pp = await db.profit_pricing_settings.find_one({"property_id": pid}, {"_id": 0, "updated_at": 1})
    if not pp:
        issues.append({
            "type": "cost_defaults", "severity": "info", "count": 1,
            "message": "CPOR / komisyon / maliyet ayarları hiç doğrulanmadı (varsayılan değerler kullanılıyor).",
            "suggestion": "Kâr-öncelikli fiyatlama panelinden gerçek maliyetlerinizi girin — net kâr hesapları buna dayanıyor.",
            "auto_fixable": False})

    # 6. duplicate bookings
    pipeline = [
        {"$match": {"property_id": pid, "created_at": {"$gte": cutoff30},
                    "status": {"$ne": "cancelled"}, "guest_email": {"$nin": ["", None]}}},
        {"$group": {"_id": {"e": "$guest_email", "ci": "$check_in", "rt": "$room_type"},
                    "n": {"$sum": 1}}},
        {"$match": {"n": {"$gt": 1}}}, {"$limit": 20},
    ]
    dups = await db.bookings.aggregate(pipeline).to_list(20)
    if dups:
        issues.append({
            "type": "duplicate_bookings", "severity": "warning", "count": len(dups),
            "message": f"{len(dups)} misafir için aynı tarih+oda tipiyle mükerrer rezervasyon şüphesi.",
            "suggestion": "Çift webhook/senkron kaynaklı olabilir — rezervasyon listesinde e-postayla arayıp doğrulayın.",
            "auto_fixable": False})

    return issues


async def run_dq_scan(db, pid: str, source: str = "manual"):
    """Taramayı çalıştırır, skoru hesaplar, kaydeder. Döner: {score, issues, prev_score}."""
    issues = await detect_issues(db, pid)
    score = max(0, 100 - sum(SEVERITY_WEIGHTS.get(i["severity"], 5) for i in issues))
    prev = await db.data_quality_scans.find_one(
        {"property_id": pid}, {"_id": 0, "health_score": 1}, sort=[("run_at", -1)])
    prev_score = prev["health_score"] if prev else None
    await db.data_quality_scans.insert_one({
        "id": str(uuid.uuid4()), "property_id": pid,
        "run_at": datetime.now(timezone.utc).isoformat(), "source": source,
        "issue_count": len(issues), "health_score": score})
    return {"score": score, "issues": issues, "prev_score": prev_score}


async def run_dq_sentinel(db, pid: str, threshold: int = 70, drop_alert: int = 15):
    """Gece nöbetçisi: tarar, skor düşükse/düşmüşse yöneticiye bildirim atar."""
    res = await run_dq_scan(db, pid, source="sentinel")
    score, prev = res["score"], res["prev_score"]
    reasons = []
    if score < threshold:
        reasons.append(f"skor {score} (eşik {threshold})")
    if prev is not None and prev - score >= drop_alert:
        reasons.append(f"{prev} → {score} ({prev - score} puan düşüş)")
    if reasons:
        crit = [i for i in res["issues"] if i["severity"] == "critical"]
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()), "type": "warning",
            "title": "Veri Nöbetçisi: Veri kalitesi düşük",
            "message": f"Gece taraması ({pid}): {', '.join(reasons)}. "
                       f"{len(res['issues'])} sorun ({len(crit)} kritik): "
                       + "; ".join(i["type"] for i in res["issues"][:4]),
            "category": "revenue", "target_user": "", "target_role": "manager",
            "link_to": "data-quality", "priority": "high",
            "read": False, "created_by": "Veri Nöbetçisi",
            "created_at": datetime.now(timezone.utc).isoformat()})
    return {"score": score, "alerted": bool(reasons)}


def create_data_quality_router(db, require_roles):
    router = APIRouter(prefix="/data-quality", tags=["data-quality"])

    @router.get("/summary/all")
    async def summary_all(u: dict = Depends(require_roles("admin", "manager"))):
        """Nöbetçi özeti: tüm tesislerin son tarama skoru (dashboard sağlık şeridi)."""
        q = {"is_active": {"$ne": False}}
        scoped = u.get("property_ids")
        if scoped and u.get("role") != "admin":
            q["id"] = {"$in": scoped}
        props = await db.properties.find(q, {"_id": 0, "id": 1, "name": 1}).to_list(50)
        out = []
        for p in props:
            scan = await db.data_quality_scans.find_one(
                {"property_id": p["id"]}, {"_id": 0, "health_score": 1, "run_at": 1, "issue_count": 1},
                sort=[("run_at", -1)])
            out.append({"property_id": p["id"], "name": p.get("name") or p["id"],
                        "score": scan["health_score"] if scan else None,
                        "issue_count": scan.get("issue_count") if scan else None,
                        "last_scan": scan.get("run_at") if scan else None})
        scored = [x["score"] for x in out if x["score"] is not None]
        return {"properties": out,
                "avg_score": round(sum(scored) / len(scored), 1) if scored else None}

    @router.get("/{property_id}")
    async def scan(property_id: str,
                   _: dict = Depends(require_roles("admin", "manager"))):
        res = await run_dq_scan(db, property_id, source="manual")
        history = await db.data_quality_scans.find(
            {"property_id": property_id}, {"_id": 0}).sort("run_at", -1).to_list(10)
        return {"property_id": property_id, "health_score": res["score"],
                "issues": res["issues"], "history": history}

    @router.post("/{property_id}/fix/orphan_rate_overrides")
    async def fix_orphans(property_id: str,
                          user: dict = Depends(require_roles("admin", "manager"))):
        rt_ids = {rt.get("id") async for rt in db.room_types.find(
            {"property_id": property_id}, {"_id": 0, "id": 1})}
        if not rt_ids:
            raise HTTPException(400, "Bu tesiste oda tipi tanımı yok — temizlik güvensiz")
        orphan_ids = [o["room_type_id"] async for o in db.rate_overrides.aggregate([
            {"$match": {"property_id": property_id, "room_type_id": {"$nin": ["", None]}}},
            {"$group": {"_id": "$room_type_id"}},
            {"$project": {"_id": 0, "room_type_id": "$_id"}}]) if o["room_type_id"] not in rt_ids]
        r = await db.rate_overrides.delete_many(
            {"property_id": property_id, "room_type_id": {"$in": orphan_ids}}) if orphan_ids else None
        removed = r.deleted_count if r else 0
        await db.data_quality_fixes.insert_one({
            "id": str(uuid.uuid4()), "property_id": property_id,
            "fix": "orphan_rate_overrides", "removed": removed,
            "by": user.get("email", ""), "at": datetime.now(timezone.utc).isoformat()})
        return {"ok": True, "removed": removed}

    return router
