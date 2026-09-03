import { useState, useEffect } from "react";
import { Star, CheckCircle, Buildings, Heart } from "@phosphor-icons/react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const R = {
  en: { load_err: "Unable to load review page", pick: "Please select a rating", write: "Please write a short review", fail: "Submission failed", retry: "Failed to submit. Please try again.",
    invalid: "Review Link Invalid", invalid_p: "This review link may have expired or is incomplete.", thanks: "Thank You!", thanks_p: "Your feedback means the world to us. It helps other guests and helps us improve.",
    stars: ["", "Poor", "Fair", "Good", "Very Good", "Excellent"], how: "How was your stay?", honest: "Your honest feedback helps us improve",
    title_ph: "Summarize your experience (optional)", text_ph: "Tell us about your stay — the room, service, location, anything that stood out...", submit: "Submit Review", public: "Your review will be shared publicly to help future guests", locale: "en-GB",
    gift: "Your thank-you gift: {pct}% off your next stay", gift_valid: "Valid until {until} · one use · direct bookings only · also sent by e-mail", gift_cta: "Book your next stay" },
  tr: { load_err: "Yorum sayfası yüklenemedi", pick: "Lütfen bir puan seçin", write: "Lütfen kısa bir yorum yazın", fail: "Gönderim başarısız", retry: "Gönderilemedi. Lütfen tekrar deneyin.",
    invalid: "Yorum Bağlantısı Geçersiz", invalid_p: "Bu bağlantının süresi dolmuş ya da eksik olabilir.", thanks: "Teşekkürler!", thanks_p: "Geri bildiriminiz bizim için çok değerli. Diğer misafirlere ve gelişmemize yardımcı olur.",
    stars: ["", "Zayıf", "Orta", "İyi", "Çok İyi", "Mükemmel"], how: "Konaklamanız nasıldı?", honest: "Dürüst geri bildiriminiz gelişmemize yardımcı olur",
    title_ph: "Deneyiminizi özetleyin (isteğe bağlı)", text_ph: "Konaklamanızı anlatın — oda, hizmet, konum, öne çıkan her şey...", submit: "Yorumu Gönder", public: "Yorumunuz gelecek misafirlere yardımcı olmak için herkese açık paylaşılır", locale: "tr-TR",
    gift: "Teşekkür hediyeniz: sonraki konaklamada %{pct} indirim", gift_valid: "{until} tarihine kadar geçerli · tek kullanım · yalnızca direkt rezervasyon · e-postayla da gönderildi", gift_cta: "Sonraki konaklamanızı planlayın" },
  de: { load_err: "Bewertungsseite konnte nicht geladen werden", pick: "Bitte wählen Sie eine Bewertung", write: "Bitte schreiben Sie eine kurze Bewertung", fail: "Übermittlung fehlgeschlagen", retry: "Senden fehlgeschlagen. Bitte erneut versuchen.",
    invalid: "Bewertungslink ungültig", invalid_p: "Dieser Link ist möglicherweise abgelaufen oder unvollständig.", thanks: "Vielen Dank!", thanks_p: "Ihr Feedback bedeutet uns viel. Es hilft anderen Gästen und uns, besser zu werden.",
    stars: ["", "Schlecht", "Mässig", "Gut", "Sehr gut", "Ausgezeichnet"], how: "Wie war Ihr Aufenthalt?", honest: "Ihr ehrliches Feedback hilft uns, besser zu werden",
    title_ph: "Fassen Sie Ihr Erlebnis zusammen (optional)", text_ph: "Erzählen Sie von Ihrem Aufenthalt — Zimmer, Service, Lage, alles, was auffiel...", submit: "Bewertung senden", public: "Ihre Bewertung wird öffentlich geteilt, um künftigen Gästen zu helfen", locale: "de-DE",
    gift: "Ihr Dankeschön: {pct}% Rabatt auf den nächsten Aufenthalt", gift_valid: "Gültig bis {until} · einmalig · nur Direktbuchungen · auch per E-Mail gesendet", gift_cta: "Nächsten Aufenthalt buchen" },
};

export default function ReviewCollectionPage() {
  const params = new URLSearchParams(window.location.search);
  const propertyId = params.get("property") || "";
  const bookingRef = params.get("ref") || "";
  const langParam = (params.get("lang") || (navigator.language || "en").slice(0, 2)).toLowerCase();
  const t = R[langParam] || R.en;

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [rating, setRating] = useState(0);
  const [hoverRating, setHoverRating] = useState(0);
  const [title, setTitle] = useState("");
  const [reviewText, setReviewText] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [coupon, setCoupon] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!propertyId || !bookingRef) { setLoading(false); return; }
    fetch(`${API}/review-collection/page/${propertyId}/${bookingRef}`)
      .then(r => r.json())
      .then(d => { setData(d); if (d.already_reviewed) setSubmitted(true); })
      .catch(() => setError(t.load_err))
      .finally(() => setLoading(false));
  }, [propertyId, bookingRef]);

  const handleSubmit = async () => {
    if (rating === 0) { setError(t.pick); return; }
    if (!reviewText.trim()) { setError(t.write); return; }
    setError("");
    try {
      const res = await fetch(
        `${API}/review-collection/submit?property_id=${propertyId}&booking_ref=${bookingRef}&rating=${rating}&title=${encodeURIComponent(title)}&review_text=${encodeURIComponent(reviewText)}&guest_name=${encodeURIComponent(data?.booking?.guest_name || "")}`,
        { method: "POST" }
      );
      if (!res.ok) { const d = await res.json(); setError(d.detail || t.fail); return; }
      const ok = await res.json().catch(() => ({}));
      if (ok?.coupon) setCoupon(ok.coupon);
      setSubmitted(true);
    } catch { setError(t.retry); }
  };

  if (loading) return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center">
      <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
    </div>
  );

  if (!propertyId || !bookingRef || !data) return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-lg p-8 text-center max-w-md">
        <Buildings size={48} className="mx-auto text-slate-300 mb-4" />
        <h1 className="text-xl font-bold text-slate-800">{t.invalid}</h1>
        <p className="text-slate-500 mt-2">{t.invalid_p}</p>
      </div>
    </div>
  );

  if (submitted) return (
    <div className="min-h-screen bg-gradient-to-br from-emerald-50 to-teal-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl p-8 text-center max-w-md" data-testid="review-submitted">
        <div className="w-16 h-16 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <Heart size={32} weight="fill" className="text-emerald-600" />
        </div>
        <h1 className="text-2xl font-bold text-slate-900 mb-2">{t.thanks}</h1>
        <p className="text-slate-500">{t.thanks_p}</p>
        {coupon && (
          <div className="mt-5 bg-blue-50 border-2 border-dashed border-blue-300 rounded-xl p-4" data-testid="review-coupon">
            <div className="text-xs font-semibold text-blue-700 uppercase tracking-wide">{t.gift.replace("{pct}", coupon.pct)}</div>
            <div className="text-2xl font-extrabold tracking-[3px] text-blue-900 my-1" data-testid="review-coupon-code">{coupon.code}</div>
            <div className="text-[11px] text-slate-500">{t.gift_valid.replace("{until}", coupon.valid_to)}</div>
            <a href={`/book/${propertyId}?coupon=${coupon.code}&lang=${langParam}`} className="inline-block mt-3 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg px-4 py-2" data-testid="review-coupon-book">{t.gift_cta}</a>
          </div>
        )}
        <div className="flex justify-center gap-1 mt-4">
          {[1,2,3,4,5].map(s => <Star key={s} size={24} weight="fill" className={s <= rating ? "text-amber-400" : "text-slate-200"} />)}
        </div>
      </div>
    </div>
  );

  const starLabels = t.stars;
  const activeRating = hoverRating || rating;

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-indigo-50 flex items-center justify-center p-4" data-testid="review-collection-page">
      <div className="bg-white rounded-2xl shadow-xl max-w-lg w-full overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-slate-800 to-slate-900 px-6 py-8 text-white text-center">
          <Buildings size={28} weight="fill" className="mx-auto mb-2 opacity-70" />
          <h1 className="text-xl font-bold">{data.property?.name}</h1>
          <p className="text-sm opacity-70 mt-1">
            {data.booking?.guest_name} &middot; {data.booking?.check_in && new Date(data.booking.check_in).toLocaleDateString(t.locale, { month: "short", day: "numeric" })} — {data.booking?.check_out && new Date(data.booking.check_out).toLocaleDateString(t.locale, { month: "short", day: "numeric", year: "numeric" })}
          </p>
        </div>

        <div className="p-6">
          <h2 className="text-lg font-semibold text-slate-900 text-center mb-1" data-testid="review-title">{t.how}</h2>
          <p className="text-sm text-slate-500 text-center mb-6">{t.honest}</p>

          {/* Star Rating */}
          <div className="text-center mb-6" data-testid="star-rating">
            <div className="flex justify-center gap-2 mb-2">
              {[1,2,3,4,5].map(s => (
                <button key={s} onClick={() => setRating(s)} onMouseEnter={() => setHoverRating(s)} onMouseLeave={() => setHoverRating(0)}
                  className="transition-transform hover:scale-110" data-testid={`star-${s}`}>
                  <Star size={40} weight={s <= activeRating ? "fill" : "regular"}
                    className={s <= activeRating ? "text-amber-400" : "text-slate-200"} />
                </button>
              ))}
            </div>
            {activeRating > 0 && <span className="text-sm font-medium text-slate-600">{starLabels[activeRating]}</span>}
          </div>

          {/* Title */}
          <input value={title} onChange={e => setTitle(e.target.value)}
            placeholder={t.title_ph}
            className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm mb-3 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            data-testid="review-title-input" />

          {/* Review Text */}
          <textarea value={reviewText} onChange={e => setReviewText(e.target.value)}
            placeholder={t.text_ph}
            rows={4} className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm resize-none mb-4 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            data-testid="review-text-input" />

          {error && <p className="text-red-500 text-sm mb-3" data-testid="review-error">{error}</p>}

          <button onClick={handleSubmit} disabled={rating === 0}
            className="w-full bg-slate-900 text-white py-3.5 rounded-xl font-semibold text-sm hover:bg-slate-800 transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            data-testid="submit-review-btn">
            <CheckCircle size={18} weight="bold" /> {t.submit}
          </button>
          <p className="text-[11px] text-slate-400 text-center mt-3">{t.public}</p>
        </div>
      </div>
    </div>
  );
}
