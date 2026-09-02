import { useState, useCallback } from "react";

export const WIDGET_LANGS = ["en", "tr", "de"];

const D = {
  en: {
    official_site: "OFFICIAL SITE", home: "Home", rooms: "Rooms", book_now: "Book Now", dates: "Dates", guests_rooms: "Guests & Rooms",
    adults: "Adults", children: "Children", room: "Room", rooms_n: "Rooms", done: "Done", search: "Search",
    accommodation: "ACCOMMODATION", our_rooms: "Our Rooms & Suites", gallery: "GALLERY", explore: "Explore Our Property",
    guest_reviews: "GUEST REVIEWS", what_guests_say: "What Our Guests Say", why_direct: "WHY BOOK DIRECT", best_rate: "The Best Rate, Guaranteed",
    modify_search: "Modify Search", night: "night", nights: "nights", rooms_available: "available", for_your_dates: "for your dates",
    no_rooms: "No rooms available", try_dates: "Try different dates or contact us directly.",
    min_stay: "Minimum {n}-night stay", max_stay: "Maximum {n}-night stay",
    score: "Score", per_night: "/night", incl_taxes: "Includes taxes", free_cancel: "Free cancellation", no_prepay: "No prepayment", reserve: "Reserve",
    why_price: "Why this price?", standard_rate: "Standard rate", your_price: "your price", transparent: "Prices are set transparently by demand; no hidden fees.",
    direct: "Direct", save: "save", ota_banner: "Coming from {ota}? Book direct and save {pct}% — same room, free cancellation, no booking fees.",
    ota_generic: "an online travel site",
    your_details: "Your Details", fill_details: "Please fill in your details to complete the reservation", full_name: "Full Name *", email: "Email Address *",
    phone: "Phone Number", special_requests: "Special Requests", room_prefs: "Room Preferences", paid_extras: "(paid extras)", payment: "Payment",
    pay_now: "Pay Now · Card", stripe_secure: "Secure Stripe checkout", pay_at_property: "Pay at Property", no_charge: "No charge today",
    powered_stripe: "Powered by Stripe", no_payment_now: "No payment taken now", proceed_payment: "PROCEED TO PAYMENT", complete_booking: "COMPLETE BOOKING", processing: "Processing...",
    back_rooms: "Back to rooms", summary: "Booking Summary", hotel: "Hotel", check_in: "Check-in", check_out: "Check-out", duration: "Duration", guests: "Guests",
    taxes_fees: "Taxes & fees", included: "Included", total: "Total", promo: "Promo / coupon code",
    payment_cancelled: "Payment Cancelled", payment_received: "Payment Received", booking_confirmed: "Booking Confirmed!", paid: "PAID",
    finalising: "Finalising your reservation. A confirmation email will arrive shortly.", email_sent: "A confirmation email has been sent to {email}.",
    reference: "Reference", free_cancel_48: "Free cancellation up to 48 hours before arrival", paid_stripe: "Payment processed via Stripe",
    no_prepay_property: "No prepayment required — pay at property", back_home: "Back to Home",
    default_subtitle: "Experience exceptional hospitality with our best rate guarantee when you book direct",
    events_kicker: "WHAT'S ON IN THE CITY", events_title: "Upcoming events — book early", events_hint: "Rooms fill up fast on these dates", events_book_early: "Book early for these dates →", events_book_package: "Book with event package",
  },
  tr: {
    official_site: "RESMİ SİTE", home: "Ana Sayfa", rooms: "Odalar", book_now: "Rezervasyon", dates: "Tarihler", guests_rooms: "Misafir & Oda",
    adults: "Yetişkin", children: "Çocuk", room: "Oda", rooms_n: "Oda", done: "Tamam", search: "Ara",
    accommodation: "KONAKLAMA", our_rooms: "Odalarımız & Süitler", gallery: "GALERİ", explore: "Otelimizi Keşfedin",
    guest_reviews: "MİSAFİR YORUMLARI", what_guests_say: "Misafirlerimiz Ne Diyor", why_direct: "NEDEN DİREKT REZERVASYON", best_rate: "En İyi Fiyat, Garantili",
    modify_search: "Aramayı Değiştir", night: "gece", nights: "gece", rooms_available: "müsait", for_your_dates: "tarihleriniz için",
    no_rooms: "Müsait oda yok", try_dates: "Farklı tarihler deneyin veya bizimle iletişime geçin.",
    min_stay: "En az {n} gece konaklama", max_stay: "En fazla {n} gece konaklama",
    score: "Puan", per_night: "/gece", incl_taxes: "Vergiler dahil", free_cancel: "Ücretsiz iptal", no_prepay: "Ön ödeme yok", reserve: "Rezerve Et",
    why_price: "Neden bu fiyat?", standard_rate: "Standart fiyat", your_price: "sizin fiyatınız", transparent: "Fiyatlar talebe göre şeffaf belirlenir; gizli ücret yok.",
    direct: "Direkt", save: "kazanç", ota_banner: "{ota} üzerinden mi geldiniz? Direkt rezervasyonda %{pct} tasarruf — aynı oda, ücretsiz iptal, komisyon yok.",
    ota_generic: "bir seyahat sitesi",
    your_details: "Bilgileriniz", fill_details: "Rezervasyonu tamamlamak için bilgilerinizi girin", full_name: "Ad Soyad *", email: "E-posta *",
    phone: "Telefon", special_requests: "Özel İstekler", room_prefs: "Oda Tercihleri", paid_extras: "(ücretli ekstralar)", payment: "Ödeme",
    pay_now: "Şimdi Öde · Kart", stripe_secure: "Güvenli Stripe ödeme", pay_at_property: "Otelde Öde", no_charge: "Bugün ücret alınmaz",
    powered_stripe: "Stripe altyapısı", no_payment_now: "Şimdi ödeme alınmaz", proceed_payment: "ÖDEMEYE GEÇ", complete_booking: "REZERVASYONU TAMAMLA", processing: "İşleniyor...",
    back_rooms: "Odalara dön", summary: "Rezervasyon Özeti", hotel: "Otel", check_in: "Giriş", check_out: "Çıkış", duration: "Süre", guests: "Misafir",
    taxes_fees: "Vergi & ücretler", included: "Dahil", total: "Toplam", promo: "Promosyon / kupon kodu",
    payment_cancelled: "Ödeme İptal Edildi", payment_received: "Ödeme Alındı", booking_confirmed: "Rezervasyon Onaylandı!", paid: "ÖDENDİ",
    finalising: "Rezervasyonunuz tamamlanıyor. Onay e-postası kısa süre içinde gelecek.", email_sent: "Onay e-postası {email} adresine gönderildi.",
    reference: "Referans", free_cancel_48: "Girişten 48 saat öncesine kadar ücretsiz iptal", paid_stripe: "Ödeme Stripe ile alındı",
    no_prepay_property: "Ön ödeme gerekmez — otelde ödeyin", back_home: "Ana Sayfaya Dön",
    default_subtitle: "Direkt rezervasyonda en iyi fiyat garantisiyle olağanüstü bir konaklama deneyimi",
    events_kicker: "ŞEHİRDE NELER VAR", events_title: "Yaklaşan etkinlikler — erken rezervasyon yapın", events_hint: "Bu tarihlerde odalar hızla doluyor", events_book_early: "Bu tarihlerde erken rezervasyon yapın →", events_book_package: "Paketli rezerve et",
  },
  de: {
    official_site: "OFFIZIELLE SEITE", home: "Start", rooms: "Zimmer", book_now: "Jetzt buchen", dates: "Daten", guests_rooms: "Gäste & Zimmer",
    adults: "Erwachsene", children: "Kinder", room: "Zimmer", rooms_n: "Zimmer", done: "Fertig", search: "Suchen",
    accommodation: "UNTERKUNFT", our_rooms: "Unsere Zimmer & Suiten", gallery: "GALERIE", explore: "Entdecken Sie unser Haus",
    guest_reviews: "GÄSTEBEWERTUNGEN", what_guests_say: "Was unsere Gäste sagen", why_direct: "WARUM DIREKT BUCHEN", best_rate: "Bestpreis, garantiert",
    modify_search: "Suche ändern", night: "Nacht", nights: "Nächte", rooms_available: "verfügbar", for_your_dates: "für Ihre Daten",
    no_rooms: "Keine Zimmer verfügbar", try_dates: "Versuchen Sie andere Daten oder kontaktieren Sie uns direkt.",
    min_stay: "Mindestaufenthalt {n} Nächte", max_stay: "Maximal {n} Nächte",
    score: "Note", per_night: "/Nacht", incl_taxes: "Inkl. Steuern", free_cancel: "Kostenlose Stornierung", no_prepay: "Keine Vorauszahlung", reserve: "Reservieren",
    why_price: "Warum dieser Preis?", standard_rate: "Standardpreis", your_price: "Ihr Preis", transparent: "Preise richten sich transparent nach der Nachfrage; keine versteckten Gebühren.",
    direct: "Direkt", save: "sparen", ota_banner: "Kommen Sie von {ota}? Direkt buchen und {pct}% sparen — gleiches Zimmer, kostenlose Stornierung, keine Buchungsgebühren.",
    ota_generic: "einem Reiseportal",
    your_details: "Ihre Angaben", fill_details: "Bitte füllen Sie Ihre Angaben aus, um die Reservierung abzuschließen", full_name: "Vollständiger Name *", email: "E-Mail-Adresse *",
    phone: "Telefonnummer", special_requests: "Besondere Wünsche", room_prefs: "Zimmerpräferenzen", paid_extras: "(kostenpflichtige Extras)", payment: "Zahlung",
    pay_now: "Jetzt zahlen · Karte", stripe_secure: "Sichere Stripe-Zahlung", pay_at_property: "Vor Ort zahlen", no_charge: "Heute keine Belastung",
    powered_stripe: "Powered by Stripe", no_payment_now: "Jetzt keine Zahlung", proceed_payment: "ZUR ZAHLUNG", complete_booking: "BUCHUNG ABSCHLIESSEN", processing: "Wird verarbeitet...",
    back_rooms: "Zurück zu den Zimmern", summary: "Buchungsübersicht", hotel: "Hotel", check_in: "Anreise", check_out: "Abreise", duration: "Dauer", guests: "Gäste",
    taxes_fees: "Steuern & Gebühren", included: "Inklusive", total: "Gesamt", promo: "Promo- / Gutscheincode",
    payment_cancelled: "Zahlung abgebrochen", payment_received: "Zahlung erhalten", booking_confirmed: "Buchung bestätigt!", paid: "BEZAHLT",
    finalising: "Ihre Reservierung wird abgeschlossen. Eine Bestätigungs-E-Mail folgt in Kürze.", email_sent: "Eine Bestätigungs-E-Mail wurde an {email} gesendet.",
    reference: "Referenz", free_cancel_48: "Kostenlose Stornierung bis 48 Stunden vor Anreise", paid_stripe: "Zahlung über Stripe verarbeitet",
    no_prepay_property: "Keine Vorauszahlung — Zahlung vor Ort", back_home: "Zur Startseite",
    default_subtitle: "Erleben Sie aussergewöhnliche Gastfreundschaft — Bestpreisgarantie bei Direktbuchung",
    events_kicker: "WAS LÄUFT IN DER STADT", events_title: "Kommende Events — früh buchen", events_hint: "An diesen Tagen sind Zimmer schnell ausgebucht", events_book_early: "Für diese Daten früh buchen →", events_book_package: "Mit Event-Paket buchen",
  },
};

export const detectWidgetLang = () => {
  const q = (new URLSearchParams(window.location.search).get("lang") || "").slice(0, 2).toLowerCase();
  if (WIDGET_LANGS.includes(q)) return q;
  const saved = localStorage.getItem("be_lang");
  if (WIDGET_LANGS.includes(saved)) return saved;
  const nav = (navigator.language || "en").slice(0, 2).toLowerCase();
  return WIDGET_LANGS.includes(nav) ? nav : "en";
};

export const useWidgetLang = () => {
  const [lang, setLangState] = useState(detectWidgetLang);
  const setLang = useCallback((l) => { localStorage.setItem("be_lang", l); setLangState(l); }, []);
  const t = useCallback((key, vars) => {
    let s = (D[lang] && D[lang][key]) || D.en[key] || key;
    if (vars) Object.entries(vars).forEach(([k, v]) => { s = s.replace(`{${k}}`, v); });
    return s;
  }, [lang]);
  const nightsLabel = useCallback((n) => `${n} ${n > 1 ? t("nights") : t("night")}`, [t]);
  const pick = useCallback((obj, base) => (obj && (obj[`${base}_${lang}`] || obj[`${base}_en`])) || "", [lang]);
  return { lang, setLang, t, nightsLabel, pick };
};
