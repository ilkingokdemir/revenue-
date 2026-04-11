import { useState, useEffect } from "react";
import { Star, CheckCircle, Buildings, Heart } from "@phosphor-icons/react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function ReviewCollectionPage() {
  const params = new URLSearchParams(window.location.search);
  const propertyId = params.get("property") || "";
  const bookingRef = params.get("ref") || "";

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [rating, setRating] = useState(0);
  const [hoverRating, setHoverRating] = useState(0);
  const [title, setTitle] = useState("");
  const [reviewText, setReviewText] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!propertyId || !bookingRef) { setLoading(false); return; }
    fetch(`${API}/review-collection/page/${propertyId}/${bookingRef}`)
      .then(r => r.json())
      .then(d => { setData(d); if (d.already_reviewed) setSubmitted(true); })
      .catch(() => setError("Unable to load review page"))
      .finally(() => setLoading(false));
  }, [propertyId, bookingRef]);

  const handleSubmit = async () => {
    if (rating === 0) { setError("Please select a rating"); return; }
    if (!reviewText.trim()) { setError("Please write a short review"); return; }
    setError("");
    try {
      const res = await fetch(
        `${API}/review-collection/submit?property_id=${propertyId}&booking_ref=${bookingRef}&rating=${rating}&title=${encodeURIComponent(title)}&review_text=${encodeURIComponent(reviewText)}&guest_name=${encodeURIComponent(data?.booking?.guest_name || "")}`,
        { method: "POST" }
      );
      if (!res.ok) { const d = await res.json(); setError(d.detail || "Submission failed"); return; }
      setSubmitted(true);
    } catch { setError("Failed to submit. Please try again."); }
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
        <h1 className="text-xl font-bold text-slate-800">Review Link Invalid</h1>
        <p className="text-slate-500 mt-2">This review link may have expired or is incomplete.</p>
      </div>
    </div>
  );

  if (submitted) return (
    <div className="min-h-screen bg-gradient-to-br from-emerald-50 to-teal-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl p-8 text-center max-w-md" data-testid="review-submitted">
        <div className="w-16 h-16 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <Heart size={32} weight="fill" className="text-emerald-600" />
        </div>
        <h1 className="text-2xl font-bold text-slate-900 mb-2">Thank You!</h1>
        <p className="text-slate-500">Your feedback means the world to us. It helps other guests and helps us improve.</p>
        <div className="flex justify-center gap-1 mt-4">
          {[1,2,3,4,5].map(s => <Star key={s} size={24} weight="fill" className={s <= rating ? "text-amber-400" : "text-slate-200"} />)}
        </div>
      </div>
    </div>
  );

  const starLabels = ["", "Poor", "Fair", "Good", "Very Good", "Excellent"];
  const activeRating = hoverRating || rating;

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-indigo-50 flex items-center justify-center p-4" data-testid="review-collection-page">
      <div className="bg-white rounded-2xl shadow-xl max-w-lg w-full overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-slate-800 to-slate-900 px-6 py-8 text-white text-center">
          <Buildings size={28} weight="fill" className="mx-auto mb-2 opacity-70" />
          <h1 className="text-xl font-bold">{data.property?.name}</h1>
          <p className="text-sm opacity-70 mt-1">
            {data.booking?.guest_name} &middot; {data.booking?.check_in && new Date(data.booking.check_in).toLocaleDateString("en-GB", { month: "short", day: "numeric" })} — {data.booking?.check_out && new Date(data.booking.check_out).toLocaleDateString("en-GB", { month: "short", day: "numeric", year: "numeric" })}
          </p>
        </div>

        <div className="p-6">
          <h2 className="text-lg font-semibold text-slate-900 text-center mb-1">How was your stay?</h2>
          <p className="text-sm text-slate-500 text-center mb-6">Your honest feedback helps us improve</p>

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
            placeholder="Summarize your experience (optional)"
            className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm mb-3 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            data-testid="review-title-input" />

          {/* Review Text */}
          <textarea value={reviewText} onChange={e => setReviewText(e.target.value)}
            placeholder="Tell us about your stay — the room, service, location, anything that stood out..."
            rows={4} className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm resize-none mb-4 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            data-testid="review-text-input" />

          {error && <p className="text-red-500 text-sm mb-3" data-testid="review-error">{error}</p>}

          <button onClick={handleSubmit} disabled={rating === 0}
            className="w-full bg-slate-900 text-white py-3.5 rounded-xl font-semibold text-sm hover:bg-slate-800 transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            data-testid="submit-review-btn">
            <CheckCircle size={18} weight="bold" /> Submit Review
          </button>
          <p className="text-[11px] text-slate-400 text-center mt-3">Your review will be shared publicly to help future guests</p>
        </div>
      </div>
    </div>
  );
}
