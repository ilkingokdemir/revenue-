"""
Automation Settings (iter 412) — unified control center for all autonomous
engines: enable/disable, cron schedule, and tunable parameters per motor.
Motors read live params via get_params() so changes apply on next run.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from typing import Dict
import logging

logger = logging.getLogger(__name__)

JOB_REGISTRY = {
    "upsell_autopilot": {
        "label": "Upsell Auto-Pilot", "category": "revenue",
        "description": "Yaklaşan konaklamalara kişiselleştirilmiş ek hizmet teklifi e-postaları gönderir.",
        "default_cron": (9, 0), "default_enabled": True,
        "params": [
            {"key": "min_score", "label": "Minimum eğilim skoru", "type": "number", "min": 0, "max": 100, "default": 60, "suffix": "puan"},
            {"key": "days_ahead", "label": "Tarama ufku", "type": "number", "min": 1, "max": 60, "default": 14, "suffix": "gün"},
        ],
    },
    "email_nudge": {
        "label": "Akıllı Hatırlatma (Nudge)", "category": "marketing",
        "description": "Açılmamış upsell teklifleri ve kullanılmamış kuponlar için hatırlatma e-postası yollar.",
        "default_cron": (11, 0), "default_enabled": True,
        "params": [
            {"key": "upsell_nudge_hours", "label": "Upsell hatırlatma gecikmesi", "type": "number", "min": 6, "max": 168, "default": 24, "suffix": "saat"},
            {"key": "coupon_nudge_hours", "label": "Kupon hatırlatma gecikmesi", "type": "number", "min": 12, "max": 336, "default": 72, "suffix": "saat"},
        ],
    },
    "daily_pulse": {
        "label": "Günlük Nabız (Daily Pulse)", "category": "reporting",
        "description": "Her sabah gecelik özet raporunu (doluluk, gelir, otomasyon kazanımları) e-posta ile iletir.",
        "default_cron": (7, 0), "default_enabled": True, "params": [],
    },
    "leakage_sweep": {
        "label": "Gelir Sızıntısı Denetçisi", "category": "revenue",
        "description": "No-show cezaları, eksik folyo kalemleri ve tahsil edilmemiş depozitoları tarar.",
        "default_cron": (6, 0), "default_enabled": True, "params": [],
    },
    "cancel_save": {
        "label": "İptal Kurtarma (Cancel-Save)", "category": "revenue",
        "description": "Yüksek iptal riskli rezervasyonlara iptal öncesi indirim kuponu gönderir.",
        "default_cron": (10, 0), "default_enabled": True,
        "params": [
            {"key": "risk_threshold", "label": "Risk skoru eşiği", "type": "number", "min": 30, "max": 95, "default": 65, "suffix": "puan"},
            {"key": "discount_pct", "label": "Kupon indirimi", "type": "number", "min": 5, "max": 30, "default": 10, "suffix": "%"},
        ],
    },
    "deposit_autopilot": {
        "label": "Depozito Autopilot", "category": "risk",
        "description": "Yüksek riskli misafir varışlarına otomatik Stripe depozito talebi gönderir.",
        "default_cron": (12, 0), "default_enabled": True,
        "params": [
            {"key": "days_ahead", "label": "Varış ufku", "type": "number", "min": 1, "max": 30, "default": 14, "suffix": "gün"},
        ],
    },
    "segment_refresh": {
        "label": "Segment Motoru", "category": "guest",
        "description": "Misafirleri her gece otomatik segmentlere ayırır (VIP, sadık, riskli, aile, iş).",
        "default_cron": (5, 0), "default_enabled": True, "params": [],
    },
    "review_autopilot": {
        "label": "Yorum Yanıt Autopilot", "category": "guest",
        "description": "Bekleyen misafir yorumlarına AI yanıtı üretir; pozitifler yayınlanır, negatifler onaya düşer.",
        "default_cron": (8, 0), "default_enabled": True,
        "params": [
            {"key": "max_per_run", "label": "Çalışma başına maks. yanıt", "type": "number", "min": 1, "max": 50, "default": 10, "suffix": "adet"},
        ],
    },
    "monthly_report_card": {
        "label": "Aylık Otomasyon Karnesi", "category": "reporting",
        "description": "Her ayın başında tüm otomasyon motorlarının performans karnesini e-posta ile gönderir.",
        "default_cron": (7, 30), "default_enabled": True, "params": [],
    },
    "arrival_reminder": {
        "label": "Ön Varış E-postası", "category": "guest",
        "description": "Girişe 2 gün kalan misafirlere kendi dilinde (TR/EN/DE) check-in saati, adres + yol tarifi ve ek hizmet teklifleri içeren hatırlatma e-postası gönderir.",
        "default_cron": (10, 0), "default_enabled": True, "params": [],
    },
    "review_request": {
        "label": "Konaklama Sonrası Yorum İsteği", "category": "guest",
        "description": "Çıkıştan 1 gün sonra misafire kendi dilinde (TR/EN/DE) teşekkür + yorum isteği e-postası gönderir; zaten yorum yapmışsa atlar, aynı misafire tekrar gitmez.",
        "default_cron": (11, 0), "default_enabled": True, "params": [],
    },
    "coupon_reminder": {
        "label": "Kupon Hatırlatma (THANKS)", "category": "guest",
        "description": "Kullanılmamış yorum teşekkür kuponlarına süresi dolmadan 30 gün önce misafirin dilinde tek seferlik hatırlatma e-postası gönderir.",
        "default_cron": (12, 0), "default_enabled": True, "params": [],
    },
    "ota_ab_auto_winner": {
        "label": "OTA Şeridi A/B Kazananı", "category": "revenue",
        "description": "OTA→direkt şerit A/B testinde her varyant ≥20 gösterim ve dönüşüm farkı ≥2 puan olduğunda kazanan yüzdeyi otomatik sabitler, testi kapatır ve yöneticilere bildirir.",
        "default_cron": (6, 30), "default_enabled": True, "params": [],
    },
    "uk_payroll_run": {
        "label": "Bordro Robotu (UK)", "category": "finance",
        "description": "Ayın son günü UK bordrosunu otomatik çalıştırır, payslip'leri üretir ve yöneticilere özet e-postası gönderir.",
        "default_cron": (18, 0), "default_enabled": True, "params": [],
    },
    "shift_reminder": {
        "label": "Vardiya Hatırlatması", "category": "hr",
        "description": "Personele yarınki vardiyasını e-posta ve WhatsApp ile hatırlatır (opsiyonel — buradan açıp kapatabilirsiniz).",
        "default_cron": (16, 0), "default_enabled": True, "params": [],
    },
    "doc_expiry_alert": {
        "label": "Belge Süresi Hatırlatıcısı", "category": "hr",
        "description": "Vize, pasaport gibi İK belgelerinin bitiş tarihini izler; 60 gün kala yöneticilere bildirim ve e-posta gönderir.",
        "default_cron": (9, 0), "default_enabled": True, "params": [],
    },
    "weekly_report": {
        "label": "Haftalık Yönetim Raporu", "category": "reporting",
        "description": "Her pazartesi son 7 günün anahtar göstergelerini önceki hafta karşılaştırmasıyla e-postalar.",
        "default_cron": (7, 0), "default_dow": 0, "default_enabled": True, "params": [],
    },
    "rebook_sweep": {
        "label": "Rebook Kupon Motoru", "category": "marketing",
        "description": "Çıkış yapan misafirlere yeniden rezervasyon kuponu planlar ve gönderir.",
        "default_cron": (9, 30), "default_enabled": True, "params": [],
    },
    "abandoned_recovery": {
        "label": "Terk Edilmiş Sepet Kurtarma", "category": "marketing",
        "description": "Yarım kalan rezervasyon denemelerine teşvik e-postası göndererek geri kazanır.",
        "default_cron": (10, 30), "default_enabled": True, "params": [],
    },
    "ai_pricing_auto_apply": {
        "label": "AI Fiyat Auto-Apply", "category": "revenue",
        "description": "AI fiyat önerilerini gece otomatik uygular (hassas — varsayılan kapalı).",
        "default_cron": (2, 0), "default_enabled": False, "params": [],
    },
    "comp_radar": {
        "label": "Rakip Fiyat Radarı", "category": "revenue",
        "description": "Rakip fiyatlarını her gece tarar; pazar altı/üstü fiyat fırsatlarını işaretler.",
        "default_cron": (4, 30), "default_enabled": True,
        "params": [
            {"key": "days_ahead", "label": "Tarama ufku", "type": "number", "min": 7, "max": 30, "default": 14, "suffix": "gün"},
            {"key": "threshold_pct", "label": "Fark eşiği", "type": "number", "min": 5, "max": 30, "default": 10, "suffix": "%"},
        ],
    },
    "vcc_auto_charge": {
        "label": "VCC Otomatik Tahsilat", "category": "finance",
        "description": "OTA rezervasyonlarındaki sanal kartları (Booking.com/Expedia VCC) tespit eder ve aktivasyon gününde otomatik tahsil eder. Başarısız/vadesi geçen kartlar için uyarı üretir.",
        "default_cron": (6, 0), "default_enabled": True, "params": [],
    },
    "invoice_reminders": {
        "label": "Fatura Hatırlatma Botu", "category": "finance",
        "description": "Vadesi geçen city-ledger faturalarına kademeli (7/21/22+ gün) ödeme linkli hatırlatma e-postası gönderir. 22+ günde yöneticiye kritik uyarı düşer.",
        "default_cron": (7, 0), "default_enabled": True, "params": [],
    },
    "owner_summary_monthly": {
        "label": "Aylık Sahip Özeti", "category": "finance",
        "description": "Her ayın 1'inde bir önceki ayın sahip/yatırımcı özetini hazırlar ve yöneticiye bildirir (PDF panelden indirilebilir, sahibe e-postalanabilir).",
        "default_cron": (8, 0), "default_enabled": True, "params": [],
    },
    "overbooking_auto_move": {
        "label": "Overbooking Otomatik Kaydırma", "category": "distribution",
        "description": "OTA'dan gelen rezervasyon dolu odaya düşerse misafiri ANINDA aynı tip boş odaya taşır ve resepsiyonu bilgilendirir (farklı oda tipine asla taşımaz). Gece süpürmesi açık kalan çakışmaları da dener.",
        "default_cron": (5, 30), "default_enabled": True, "params": [],
    },
    "ota_sync_watchdog": {
        "label": "OTA Senkron Watchdog", "category": "distribution",
        "description": "Başarısız OTA güncellemelerini yeniden dener, geciken kanallar için uyarı açar ve eski/boş tarih hücrelerini otomatik push'lar (Auto-Freshness).",
        "default_cron": (6, 30), "default_enabled": True,
        "params": [
            {"key": "stale_hours", "label": "Gecikme eşiği", "type": "number", "min": 4, "max": 96, "default": 24, "suffix": "saat"},
            {"key": "max_requeue", "label": "Çalışma başına maks. yeniden kuyruk", "type": "number", "min": 1, "max": 50, "default": 10, "suffix": "adet"},
            {"key": "freshness_hours", "label": "Tazelik eşiği (Auto-Freshness)", "type": "number", "min": 24, "max": 168, "default": 72, "suffix": "saat"},
            {"key": "freshness_days", "label": "Tazelik ufku", "type": "number", "min": 7, "max": 30, "default": 14, "suffix": "gün"},
            {"key": "max_auto_push", "label": "Çalışma başına maks. otomatik push (0=kapalı)", "type": "number", "min": 0, "max": 100, "default": 30, "suffix": "adet"},
        ],
    },
    "ar_recon": {
        "label": "AR Mutabakat Agent'ı", "category": "finance",
        "description": "Gelen banka ödemelerini açık faturalarla akıllı eşleştirir (kısmi/fazla/toplu ödeme dahil).",
        "default_cron": (7, 30), "default_enabled": True, "params": [],
    },
    "waitlist_match": {
        "label": "Bekleme Listesi Eşleştirici", "category": "guest",
        "description": "Müsaitlik açılınca bekleme listesindeki misafirlere otomatik rezervasyon teklifi e-postası gönderir.",
        "default_cron": (8, 15), "default_enabled": True,
        "params": [
            {"key": "offer_ttl_hours", "label": "Teklif geçerlilik süresi", "type": "number", "min": 12, "max": 168, "default": 48, "suffix": "saat"},
        ],
    },
    "hk_dispatch": {
        "label": "HK Otomatik Görev Dağıtımı", "category": "guest",
        "description": "Check-out olan odaları en az yüklü kat görevlisine atar; bugün varış olan odalara öncelik verir.",
        "default_cron": (6, 45), "default_enabled": True, "params": [],
    },
    "res_quality": {
        "label": "Rezervasyon Kalite Kontrolü", "category": "guest",
        "description": "Yaklaşan varışları hatalara karşı tarar (eksik iletişim, sıfır fiyat, çift kayıt) ve iletişim bilgilerini otomatik tamamlar.",
        "default_cron": (5, 30), "default_enabled": True, "params": [],
    },
    "vcc_recovery": {
        "label": "VCC Gelir Kurtarma", "category": "finance",
        "description": "OTA sanal kart tutarsızlıklarını tarar (unutulmuş çekim, süresi dolmuş kart, eksik yükleme, iptal ücreti) ve kurtarılabilir geliri raporlar.",
        "default_cron": (7, 0), "default_enabled": True, "params": [],
    },
    "allotment_release": {
        "label": "Kontenjan Otomatik Release", "category": "distribution",
        "description": "Release penceresine giren satılmamış tur operatörü kontenjanlarını otomatik serbest bırakır ve yöneticiye bildirir.",
        "default_cron": (5, 45), "default_enabled": True, "params": [],
    },
    "restriction_advisor": {
        "label": "AI Kısıtlama Danışmanı", "category": "revenue",
        "description": "Yüksek talepli geceler için MLOS (min konaklama) ve CTA (varışa kapalı) önerileri üretir; onayla tek tıkla tüm kanallara uygulanır.",
        "default_cron": (5, 15), "default_enabled": True, "params": [],
    },
    "gap_filler": {
        "label": "AI Boşluk Doldurma Kampanyaları", "category": "marketing",
        "description": "Düşük doluluklu tarih pencereleri için otomatik promo kodu + e-posta/WhatsApp kampanya taslağı üretir.",
        "default_cron": (6, 10), "default_enabled": True, "params": [],
    },
    "returning_guest_watch": {
        "label": "Dönen Misafir Takibi", "category": "guest",
        "description": "48 saat içinde varışı olan, kayıtlı tercihi (sessiz oda, sağlık, yemek) veya geçmiş olayı bulunan misafirleri resepsiyona bildirir.",
        "default_cron": (6, 30), "default_enabled": True, "params": [],
    },
}

CATEGORY_META = {
    "revenue": "Gelir Motorları",
    "marketing": "Pazarlama Motorları",
    "guest": "Misafir Deneyimi",
    "risk": "Risk & Güvence",
    "reporting": "Raporlama",
    "distribution": "Dağıtım & OTA",
    "finance": "Finans & Tahsilat",
    "hr": "İK & Vardiya",
}


async def get_params(db, job: str, defaults: Dict) -> Dict:
    """Live tunable params for a motor. Falls back to defaults."""
    doc = await db.automation_params.find_one({"job": job}, {"_id": 0}) or {}
    saved = doc.get("params") or {}
    out = dict(defaults)
    for k in defaults:
        if k in saved and saved[k] is not None:
            out[k] = saved[k]
    return out


def create_automation_settings_router(db, require_roles):
    router = APIRouter()

    async def _config_for(job: str) -> dict:
        cfg = await db.scheduler_config.find_one({"job": job, "property_id": "all"}, {"_id": 0})
        if not cfg:
            cfg = await db.scheduler_config.find_one({"job": job}, {"_id": 0})
        return cfg

    @router.get("/automation/settings")
    async def list_settings(current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc).isoformat()
        out = []
        for job, meta in JOB_REGISTRY.items():
            cfg = await _config_for(job)
            if not cfg:
                cfg = {
                    "property_id": "all", "job": job,
                    "enabled": meta["default_enabled"],
                    "cron_hour": meta["default_cron"][0],
                    "cron_minute": meta["default_cron"][1],
                    "cron_dow": meta.get("default_dow"), "notes": "",
                    "updated_at": now, "updated_by": "auto-seed",
                }
                await db.scheduler_config.update_one(
                    {"property_id": "all", "job": job}, {"$set": cfg}, upsert=True)
            pdoc = await db.automation_params.find_one({"job": job}, {"_id": 0}) or {}
            saved = pdoc.get("params") or {}
            params = []
            for p in meta["params"]:
                params.append({**p, "value": saved.get(p["key"], p["default"])})
            last_hist = await db.scheduler_history.find_one(
                {"job": job}, {"_id": 0}, sort=[("ran_at", -1)])
            out.append({
                "job": job,
                "label": meta["label"],
                "category": meta["category"],
                "category_label": CATEGORY_META[meta["category"]],
                "description": meta["description"],
                "enabled": bool(cfg.get("enabled")),
                "cron_hour": cfg.get("cron_hour", meta["default_cron"][0]),
                "cron_minute": cfg.get("cron_minute", meta["default_cron"][1]),
                "cron_dow": cfg.get("cron_dow"),
                "property_id": cfg.get("property_id", "all"),
                "params": params,
                "last_run_at": cfg.get("last_run_at") or (last_hist or {}).get("ran_at"),
                "last_run_result": cfg.get("last_run_result") or (last_hist or {}).get("result"),
                "last_run_error": (last_hist or {}).get("error"),
                "updated_at": cfg.get("updated_at"),
                "updated_by": cfg.get("updated_by"),
            })
        return {"jobs": out, "categories": CATEGORY_META}

    @router.put("/automation/settings/{job}")
    async def update_settings(job: str, data: Dict,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        meta = JOB_REGISTRY.get(job)
        if not meta:
            raise HTTPException(status_code=404, detail=f"Unknown job: {job}")
        cfg = await _config_for(job)
        pid = (cfg or {}).get("property_id", "all")
        now = datetime.now(timezone.utc).isoformat()

        upd = {"updated_at": now, "updated_by": current_user.get("name", "")}
        if "enabled" in data:
            upd["enabled"] = bool(data["enabled"])
        if "cron_hour" in data:
            h = int(data["cron_hour"])
            if not (0 <= h <= 23):
                raise HTTPException(status_code=400, detail="cron_hour 0-23")
            upd["cron_hour"] = h
        if "cron_minute" in data:
            m = int(data["cron_minute"])
            if not (0 <= m <= 59):
                raise HTTPException(status_code=400, detail="cron_minute 0-59")
            upd["cron_minute"] = m
        if "cron_dow" in data:
            dow = data["cron_dow"]
            if dow is not None:
                dow = int(dow)
                if not (0 <= dow <= 6):
                    raise HTTPException(status_code=400, detail="cron_dow 0-6")
            upd["cron_dow"] = dow
        await db.scheduler_config.update_one(
            {"property_id": pid, "job": job},
            {"$set": {**upd, "property_id": pid, "job": job}}, upsert=True)

        if "params" in data and isinstance(data["params"], dict):
            valid_keys = {p["key"]: p for p in meta["params"]}
            clean = {}
            for k, v in data["params"].items():
                if k not in valid_keys:
                    continue
                spec = valid_keys[k]
                try:
                    v = float(v)
                except (TypeError, ValueError):
                    raise HTTPException(status_code=400, detail=f"{k} sayısal olmalı")
                if v < spec["min"] or v > spec["max"]:
                    raise HTTPException(
                        status_code=400,
                        detail=f"{spec['label']}: {spec['min']}-{spec['max']} aralığında olmalı")
                clean[k] = int(v) if float(v).is_integer() else v
            if clean:
                await db.automation_params.update_one(
                    {"job": job},
                    {"$set": {"job": job, "updated_at": now,
                              "updated_by": current_user.get("name", ""),
                              **{f"params.{k}": v for k, v in clean.items()}}},
                    upsert=True)

        return {"ok": True, "job": job}

    return router
