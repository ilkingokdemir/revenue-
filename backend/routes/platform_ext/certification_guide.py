"""Sertifika / canlıya geçiş rehberi — adım adım checklist + env/db'den otomatik durum."""
import os
from fastapi import APIRouter, Depends


def create_certification_guide_router(db, require_roles):
    router = APIRouter()

    async def _status():
        gbp = await db.google_tokens.count_documents({"status": "connected"})
        wa = bool(os.environ.get("TWILIO_ACCOUNT_SID") and os.environ.get("TWILIO_AUTH_TOKEN"))
        stripe_live = (os.environ.get("STRIPE_API_KEY") or os.environ.get("STRIPE_SECRET_KEY") or "").startswith("sk_live")
        stripe_test = bool(os.environ.get("STRIPE_API_KEY") or os.environ.get("STRIPE_SECRET_KEY"))
        bcom = await db.platform_integrations.count_documents({"platform": "booking.com", "status": {"$in": ["connected", "active"]}})
        exp = await db.platform_integrations.count_documents({"platform": "expedia", "status": {"$in": ["connected", "active"]}})
        return {"gbp": gbp > 0, "gbp_client": bool(os.environ.get("GOOGLE_CLIENT_ID")), "wa": wa, "resend": bool(os.environ.get("RESEND_API_KEY")),
                "stripe_live": stripe_live, "stripe_test": stripe_test, "booking": bcom > 0, "expedia": exp > 0,
                "sso": bool(os.environ.get("GOOGLE_SSO_CLIENT_ID") or os.environ.get("MS_SSO_CLIENT_ID")),
                "xero": bool(os.environ.get("XERO_CLIENT_ID")), "qbo": bool(os.environ.get("QBO_CLIENT_ID")), "efatura": bool(os.environ.get("EFATURA_INTEGRATOR_KEY"))}

    @router.get("/certifications/guide")
    async def guide(_: dict = Depends(require_roles("admin", "manager"))):
        st = await _status()
        base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
        G = [
            {"id": "booking", "title": "Booking.com Connectivity Partner", "eta": "6–10 hafta", "done": st["booking"], "url": "https://connect.booking.com/",
             "steps": ["connect.booking.com'da Connectivity Partner başvurusu (şirket + ürün bilgisi)", "Teknik anket + API test hesabı (Provider ID) al",
                       "Sandbox'ta ARI push, rezervasyon çekme ve modifikasyon testleri", "Sertifikasyon çağrısı → canlı Provider ID/anahtar",
                       "Anahtarları Integrations → Booking.com → Configure'a gir, ilk oteli bağla"], "env": ["Integrations paneli (platform_integrations)"]},
            {"id": "expedia", "title": "Expedia Group EQC / Partner Central API", "eta": "4–8 hafta", "done": st["expedia"], "url": "https://developers.expediagroup.com/supply/lodging",
             "steps": ["developers.expediagroup.com → Lodging Supply API başvurusu", "Test otel (EQC test property) ve API kimlik bilgileri",
                       "Product/Availability/Booking Retrieval sertifikasyon senaryoları", "Canlı anahtar → Integrations → Expedia"], "env": ["Integrations paneli"]},
            {"id": "whatsapp", "title": "WhatsApp Business API (Twilio)", "eta": "1–2 hafta", "done": st["wa"], "url": "https://www.twilio.com/whatsapp",
             "steps": ["Meta Business Manager doğrulaması (şirket belgesi)", "Twilio hesabı → WhatsApp Sender kaydı (telefon numarası, display name)",
                       "Şablon (template) onayları: karne, yorum isteği, ön varış", "TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_WHATSAPP_FROM → backend .env"],
             "env": ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_WHATSAPP_FROM"]},
            {"id": "resend", "title": "E-posta (Resend) canlı", "eta": "1 gün", "done": st["resend"], "url": "https://resend.com/domains",
             "steps": ["Resend'de domain ekle → SPF/DKIM/DMARC DNS kayıtları", "API key oluştur → RESEND_API_KEY", "Gönderen adresini (noreply@otel.com) doğrula"], "env": ["RESEND_API_KEY", "RESEND_FROM"]},
            {"id": "stripe", "title": "Stripe canlı ödeme", "eta": "1–3 gün", "done": st["stripe_live"], "url": "https://dashboard.stripe.com/account/onboarding",
             "steps": ["Stripe hesabını 'claim' et / KYC (şirket, banka hesabı)", "Canlı anahtar sk_live_… → STRIPE_API_KEY (test anahtarı yerine)",
                       "Webhook endpoint'i canlıya al: " + f"{base}/api/webhook/stripe", "3DS/SCA testini gerçek kartla yap; payout takvimini ayarla"],
             "env": ["STRIPE_API_KEY", "STRIPE_WEBHOOK_SECRET"], "note": "Test anahtarı " + ("mevcut" if st["stripe_test"] else "yok")},
            {"id": "gbp", "title": "Google Business Profile (yorum yanıtı canlı)", "eta": "2–4 hafta (API erişim onayı)", "done": st["gbp"], "url": "https://developers.google.com/my-business/content/prereqs",
             "steps": ["Google Cloud projesi → Business Profile API erişim formu (onay bekleyin)", "OAuth istemcisi (Web) → redirect URI: " + f"{base}/api/gbp/oauth/callback",
                       "GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET → backend .env", "Yayın Modu & Onay Kuralları → 'Google ile bağlan' → konum seç", "İlk yanıtı Approval Center'dan yayımla"],
             "env": ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "TOKEN_ENCRYPTION_KEY (ops.)"], "note": "OAuth istemcisi " + ("hazır" if st["gbp_client"] else "yok")},
            {"id": "sso", "title": "Kurumsal giriş (Google Workspace / Microsoft 365)", "eta": "1 gün", "done": st["sso"], "url": "https://console.cloud.google.com/apis/credentials",
             "steps": ["Google: OAuth istemcisi (Web) → redirect " + f"{base}/api/auth/sso/google/callback", "Microsoft: Entra → App registration → redirect " + f"{base}/api/auth/sso/microsoft/callback",
                       "GOOGLE_SSO_CLIENT_ID/SECRET veya MS_SSO_CLIENT_ID/SECRET/TENANT_ID → .env", "Admin → Organizasyonlar: izinli alan / hd / tenant tanımla"],
             "env": ["GOOGLE_SSO_CLIENT_ID", "GOOGLE_SSO_CLIENT_SECRET", "MS_SSO_CLIENT_ID", "MS_SSO_CLIENT_SECRET", "MS_SSO_TENANT_ID"]},
            {"id": "accounting", "title": "Xero / QuickBooks / e-Fatura", "eta": "1–2 gün", "done": st["xero"] or st["qbo"] or st["efatura"], "url": "https://developer.xero.com/app/manage",
             "steps": ["Xero: developer.xero.com → app → redirect " + f"{base}/api/accounting/oauth/xero/callback", "QuickBooks: developer.intuit.com → app (sandbox→prod) → redirect " + f"{base}/api/accounting/oauth/qbo/callback",
                       "e-Fatura: GİB özel entegratör (Logo, Foriba, Uyumsoft…) API anahtarı → EFATURA_INTEGRATOR_KEY", "Reports → Accounting Export → hesap kodlarını eşle, 'Şimdi gönder'"],
             "env": ["XERO_CLIENT_ID", "XERO_CLIENT_SECRET", "QBO_CLIENT_ID", "QBO_CLIENT_SECRET", "EFATURA_INTEGRATOR_KEY"]},
        ]
        done = sum(1 for g in G if g["done"])
        return {"items": G, "done": done, "total": len(G), "progress_pct": round(done / len(G) * 100), "status": st}

    return router
