/**
 * Public Mid-stay Survey Page (no auth)
 * Guest opens this via a link they receive on day 2 of their stay.
 */
import { useEffect, useState } from "react";
import axios from "axios";
import { Star, Loader2, CheckCircle2 } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const CATEGORIES = [
  { id: "room", label: "Room" }, { id: "clean", label: "Cleanliness" }, { id: "food", label: "Food & drink" },
  { id: "front_desk", label: "Front desk" }, { id: "wifi", label: "Wi-Fi / tech" }, { id: "noise", label: "Noise" },
  { id: "other", label: "Other" },
];

export default function MidStaySurveyPublicPage({ inviteId }) {
  const [invite, setInvite] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [score, setScore] = useState(0);
  const [hover, setHover] = useState(0);
  const [category, setCategory] = useState("other");
  const [comment, setComment] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [serviceRecovery, setServiceRecovery] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await axios.get(`${API}/mid-stay/invite/${inviteId}`);
        setInvite(data);
      } catch (e) {
        setError(e.response?.data?.detail || "Survey link not found.");
      }
      setLoading(false);
    })();
  }, [inviteId]);

  const submit = async () => {
    if (score < 1) { setError("Please pick a score."); return; }
    try {
      const { data } = await axios.post(`${API}/mid-stay/invite/${inviteId}/submit`, { score, category, comment });
      setSubmitted(true);
      setServiceRecovery(data.service_recovery_opened);
    } catch (e) {
      setError(e.response?.data?.detail || "Submission failed");
    }
  };

  if (loading) return <div className="min-h-screen flex items-center justify-center bg-stone-50"><Loader2 className="w-8 h-8 animate-spin text-stone-400" /></div>;
  if (error && !invite) return <div className="min-h-screen flex items-center justify-center bg-stone-50 p-6"><div className="bg-white rounded-xl shadow p-6 text-center max-w-md"><div className="text-rose-600 font-medium mb-2">{error}</div><div className="text-stone-500 text-sm">Please contact reception if you'd like to share feedback.</div></div></div>;
  if (invite?.already_responded || submitted) {
    return (
      <div className="min-h-screen bg-stone-50 flex items-center justify-center p-6">
        <div className="bg-white rounded-xl shadow p-8 text-center max-w-md" data-testid="ms-thanks">
          <CheckCircle2 className="w-16 h-16 text-emerald-500 mx-auto mb-3" />
          <h1 className="text-2xl font-semibold text-stone-900 mb-2">Thank you!</h1>
          <p className="text-stone-600">Your feedback helps us serve you better during the rest of your stay.</p>
          {serviceRecovery && (
            <p className="mt-4 text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded p-3">A team member will reach out to you shortly.</p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-stone-50 flex items-center justify-center p-6">
      <div className="bg-white rounded-xl shadow p-8 max-w-md w-full" data-testid="ms-public-form">
        <h1 className="text-2xl font-semibold text-stone-900">{invite.hotel_name}</h1>
        <p className="text-stone-500 text-sm mt-1">Hi {invite.guest_name?.split(" ")[0] || "there"}, how is your stay so far?</p>

        <div className="my-6 flex items-center justify-center gap-2">
          {[1, 2, 3, 4, 5].map((i) => (
            <button key={i} type="button" data-testid={`ms-star-${i}`}
              onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(0)} onClick={() => setScore(i)}
              className="transition transform hover:scale-110">
              <Star className={`w-10 h-10 ${(hover || score) >= i ? "fill-amber-400 text-amber-400" : "text-stone-300"}`} />
            </button>
          ))}
        </div>

        <label className="block text-xs uppercase tracking-wider text-stone-500 mb-1">What stood out?</label>
        <select value={category} onChange={(e) => setCategory(e.target.value)} className="w-full px-3 py-2 border border-stone-300 rounded mb-3 text-sm">
          {CATEGORIES.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
        </select>

        <label className="block text-xs uppercase tracking-wider text-stone-500 mb-1">Any details?</label>
        <textarea data-testid="ms-comment" rows={3} value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Optional…" className="w-full px-3 py-2 border border-stone-300 rounded text-sm" />

        {error && <div className="mt-3 text-sm text-rose-600">{error}</div>}

        <button data-testid="ms-submit-btn" onClick={submit} className="mt-5 w-full py-3 bg-stone-900 text-white rounded font-medium hover:bg-stone-800 transition">Send feedback</button>
      </div>
    </div>
  );
}
