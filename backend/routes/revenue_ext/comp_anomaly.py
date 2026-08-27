"""Rakip Veri Anomali Düzeltme — sapkın rakip fiyatlarını otomatik ayıklar (IDeaS paritesi).
Kaynaklar: comp_rate_snapshots (compset taramaları) + market_competitors.prices."""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
from typing import Dict, List
import uuid

DEFAULTS = {"enabled": True, "z_threshold": 3.0, "low_pct": 45.0, "high_pct": 250.0}


def _now():
    return datetime.now(timezone.utc)


def _median(v: List[float]) -> float:
    s = sorted(v)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def _detect(series: List[Dict], cfg: Dict) -> List[Dict]:
    """series: [{rate, ...meta}] tek rakibe ait. Robust z-score (median/MAD) + yüzde bandı."""
    rates = [s["rate"] for s in series if s.get("rate")]
    if len(rates) < 5:
        return []
    med = _median(rates)
    mad = _median([abs(r - med) for r in rates]) or med * 0.05 or 1
    out = []
    for s in series:
        r = s.get("rate") or 0
        if r <= 0:
            continue
        z = abs(r - med) / (1.4826 * mad)
        pct = r / med * 100
        reason = None
        if pct < cfg["low_pct"]:
            reason = f"medyanın %{100 - pct:.0f} altında (£{r:.0f} vs £{med:.0f}) — muhtemel tek oda kalıntısı/hatalı tarama"
        elif pct > cfg["high_pct"]:
            reason = f"medyanın %{pct - 100:.0f} üstünde (£{r:.0f} vs £{med:.0f}) — muhtemel suit/paket fiyatı karışması"
        elif z > cfg["z_threshold"]:
            reason = f"robust z-skor {z:.1f} > {cfg['z_threshold']:g} (£{r:.0f} vs medyan £{med:.0f})"
        if reason:
            out.append({**s, "median": round(med, 2), "z": round(z, 1), "reason": reason})
    return out


def robust_band_filter(rates: List[float], low_pct: float = 45.0,
                       high_pct: float = 250.0):
    """Saf fonksiyon: medyan bandı dışındaki fiyatları ayıklar → (temiz, atılan_sayısı)."""
    vals = [float(r) for r in rates if r and float(r) > 0]
    if len(vals) < 3:
        return vals, 0
    med = _median(vals)
    clean = [v for v in vals if low_pct <= v / med * 100 <= high_pct]
    return (clean or vals), len(vals) - len(clean or vals)


async def clean_comp_entries(db, pid: str, date: str, entries: List[Dict]):
    """entries: [{comp_name, rate}] → yoksayılanlar + bant dışılar ayıklanır.
    Dönen: (temiz_rate_listesi, atılan_sayısı)."""
    cfg = {**DEFAULTS, **(await db.comp_anomaly_config.find_one(
        {"property_id": pid}, {"_id": 0}) or {})}
    if not cfg.get("enabled", True):
        return [e["rate"] for e in entries if e.get("rate")], 0
    ignored = set()
    async for i in db.comp_anomaly_ignores.find(
            {"property_id": pid}, {"_id": 0, "key": 1}):
        ignored.add(i["key"])
    kept = []
    dropped = 0
    for e in entries:
        r = float(e.get("rate") or 0)
        if r <= 0:
            continue
        key = f"compset|{e.get('comp_name', '')}|{date}|{r:.0f}"
        if key in ignored:
            dropped += 1
            continue
        kept.append(r)
    clean, band_dropped = robust_band_filter(kept, cfg["low_pct"], cfg["high_pct"])
    return clean, dropped + band_dropped


def create_comp_anomaly_router(db, require_roles):
    router = APIRouter(prefix="/comp-anomaly", tags=["comp-anomaly"])
    ROLES = ("admin", "manager")

    async def _cfg(pid: str) -> Dict:
        doc = await db.comp_anomaly_config.find_one({"property_id": pid}, {"_id": 0})
        return {**DEFAULTS, **(doc or {})}

    async def _ignored(pid: str) -> set:
        keys = set()
        async for i in db.comp_anomaly_ignores.find({"property_id": pid}, {"_id": 0, "key": 1}):
            keys.add(i["key"])
        return keys

    async def _scan(pid: str, days: int) -> List[Dict]:
        cfg = await _cfg(pid)
        since = (_now() - timedelta(days=min(days, 180))).date().isoformat()
        ignored = await _ignored(pid)
        anomalies = []
        # 1) compset tarama anlık görüntüleri (rakip başına seri)
        by_comp: Dict[str, List[Dict]] = {}
        async for s in db.comp_rate_snapshots.find(
                {"property_id": pid, "date": {"$gte": since}},
                {"_id": 0, "comp_id": 1, "comp_name": 1, "date": 1, "rate": 1}):
            by_comp.setdefault(s.get("comp_id", "?"), []).append(
                {"source": "compset", "comp_name": s.get("comp_name", ""),
                 "date": s["date"], "rate": float(s.get("rate") or 0)})
        for series in by_comp.values():
            anomalies += _detect(series, cfg)
        # 2) market_competitors günlük fiyat listeleri (gün-içi all_prices sapkınları)
        async for mc in db.market_competitors.find(
                {"property_id": {"$in": [pid, "all"]}}, {"_id": 0, "name": 1, "prices": 1}):
            flat = []
            for p in (mc.get("prices") or []):
                lp = float(p.get("lowest_price") or 0)
                if lp > 0:
                    flat.append({"source": "scraper", "comp_name": mc.get("name", ""),
                                 "date": p.get("date", ""), "rate": lp})
            anomalies += _detect(flat, cfg)
        for a in anomalies:
            a["key"] = f"{a['source']}|{a['comp_name']}|{a['date']}|{a['rate']:.0f}"
            a["ignored"] = a["key"] in ignored
        anomalies.sort(key=lambda x: -x["z"])
        return anomalies

    @router.get("/{pid}")
    async def get_anomalies(pid: str, days: int = 90,
                            _u: dict = Depends(require_roles(*ROLES))):
        cfg = await _cfg(pid)
        anomalies = await _scan(pid, days)
        active = [a for a in anomalies if not a["ignored"]]
        return {"property_id": pid, "config": cfg,
                "anomalies": anomalies[:100],
                "total": len(anomalies), "active": len(active),
                "ignored": len(anomalies) - len(active),
                "note": "Sapkın fiyatlar (robust z-skor + yüzde bandı) fiyat motoruna girmeden ayıklanır. 'Yoksay' işaretlenen kayıtlar rakip medyan hesaplarından düşülür."}

    @router.put("/{pid}/config")
    async def put_config(pid: str, data: Dict, u: dict = Depends(require_roles(*ROLES))):
        cfg = {"enabled": bool(data.get("enabled", True)),
               "z_threshold": max(1.5, min(float(data.get("z_threshold", 3.0) or 3.0), 6.0)),
               "low_pct": max(10.0, min(float(data.get("low_pct", 45.0) or 45.0), 90.0)),
               "high_pct": max(120.0, min(float(data.get("high_pct", 250.0) or 250.0), 500.0))}
        await db.comp_anomaly_config.update_one(
            {"property_id": pid},
            {"$set": {**cfg, "updated_at": _now().isoformat(),
                      "updated_by": u.get("name") or u.get("email", "")}}, upsert=True)
        return {"ok": True, "config": cfg}

    @router.post("/{pid}/ignore")
    async def ignore_one(pid: str, data: Dict, u: dict = Depends(require_roles(*ROLES))):
        key = data.get("key", "")
        if not key:
            return {"ok": False}
        await db.comp_anomaly_ignores.update_one(
            {"property_id": pid, "key": key},
            {"$set": {"reason": data.get("reason", ""), "by": u.get("name", ""),
                      "created_at": _now().isoformat()}}, upsert=True)
        return {"ok": True}

    @router.post("/{pid}/ignore-all")
    async def ignore_all(pid: str, u: dict = Depends(require_roles(*ROLES))):
        anomalies = await _scan(pid, 90)
        n = 0
        for a in anomalies:
            if a["ignored"]:
                continue
            await db.comp_anomaly_ignores.update_one(
                {"property_id": pid, "key": a["key"]},
                {"$set": {"reason": a["reason"], "by": u.get("name", ""),
                          "created_at": _now().isoformat()}}, upsert=True)
            n += 1
        return {"ok": True, "ignored": n}

    @router.get("/{pid}/clean-median")
    async def clean_median(pid: str, date: str = "",
                           _u: dict = Depends(require_roles(*ROLES))):
        """Diğer modüller için: verilen günün ayıklanmış rakip medyanı."""
        if not date:
            date = _now().date().isoformat()
        ignored = await _ignored(pid)
        rates_raw, rates_clean = [], []
        async for s in db.comp_rate_snapshots.find(
                {"property_id": pid, "date": date}, {"_id": 0}):
            r = float(s.get("rate") or 0)
            if r <= 0:
                continue
            rates_raw.append(r)
            key = f"compset|{s.get('comp_name','')}|{date}|{r:.0f}"
            if key not in ignored:
                rates_clean.append(r)
        return {"date": date,
                "raw_median": round(_median(rates_raw), 2) if rates_raw else None,
                "clean_median": round(_median(rates_clean), 2) if rates_clean else None,
                "raw_count": len(rates_raw), "clean_count": len(rates_clean)}

    return router
