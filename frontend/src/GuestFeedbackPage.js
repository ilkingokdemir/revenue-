import { useState, useEffect } from "react";
import axios from "axios";
import { motion } from "framer-motion";
import { useTranslation } from "@/i18n";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function GuestFeedbackPage({ token }) {
  const { t } = useTranslation();
  const [feedback, setFeedback] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [selectedResponse, setSelectedResponse] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const autoResponse = params.get("r");
    if (autoResponse === "all_good" || autoResponse === "need_help") {
      setSelectedResponse(autoResponse);
    }

    const load = async () => {
      try {
        const { data } = await axios.get(`${API}/guest-journey/feedback/${token}`);
        setFeedback(data);
        if (data.status === "responded") setSubmitted(true);
      } catch {
        setError("Feedback link not found or has expired.");
      }
      setLoading(false);
    };
    load();
  }, [token]);

  const submit = async () => {
    if (!selectedResponse) return;
    setSubmitting(true);
    try {
      await axios.post(`${API}/guest-journey/feedback/${token}`, {
        response: selectedResponse,
        message,
      });
      setSubmitted(true);
    } catch {
      alert("Failed to submit. Please try again.");
    }
    setSubmitting(false);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-stone-50 to-stone-100 flex items-center justify-center">
        <div className="w-8 h-8 border-3 border-stone-300 border-t-stone-700 rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-stone-50 to-stone-100 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-lg p-8 max-w-md w-full text-center" data-testid="feedback-error">
          <div className="w-16 h-16 rounded-full bg-red-50 flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" /></svg>
          </div>
          <h2 className="text-lg font-semibold text-stone-800 mb-2">Link Not Found</h2>
          <p className="text-stone-500 text-sm">{error}</p>
        </div>
      </div>
    );
  }

  if (submitted) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-emerald-50 to-stone-50 flex items-center justify-center p-4" data-testid="feedback-submitted">
        <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="bg-white rounded-2xl shadow-lg p-8 max-w-md w-full text-center">
          <div className="w-20 h-20 bg-emerald-50 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-10 h-10 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
          </div>
          <h2 className="text-xl font-bold text-stone-800 mb-2">{t("feedback.thank_you")}</h2>
          <p className="text-stone-500 text-sm">{selectedResponse === "need_help" ? t("feedback.help_soon") : t("feedback.glad")}</p>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-stone-50 via-emerald-50/20 to-stone-50 flex items-center justify-center p-4" data-testid="guest-feedback-page">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="bg-white rounded-2xl shadow-lg max-w-md w-full overflow-hidden">
        {/* Header */}
        <div className="bg-[#2C4C3B] text-white p-6 text-center relative" data-testid="feedback-header">
          <h1 className="text-lg font-bold">{feedback?.hotel_name || "Hotel"}</h1>
          <p className="text-white/70 text-sm mt-1">{t("feedback.title")}</p>
          <div className="absolute right-4 top-4"><LanguageSwitcher compact /></div>
        </div>

        <div className="p-6">
          <p className="text-stone-600 text-sm text-center mb-6">
            Hi <strong>{feedback?.guest_name || "Guest"}</strong>, we hope you're enjoying your stay. Is there anything we can help with?
          </p>

          {/* Response Options */}
          <div className="grid grid-cols-2 gap-3 mb-5" data-testid="feedback-options">
            <button data-testid="btn-all-good" onClick={() => setSelectedResponse("all_good")} className={`p-5 rounded-xl border-2 text-center transition-all ${selectedResponse === "all_good" ? "border-emerald-500 bg-emerald-50" : "border-stone-200 hover:border-emerald-300"}`}>
              <div className="text-3xl mb-2">
                <svg className="w-10 h-10 mx-auto text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M14.828 14.828a4 4 0 01-5.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
              </div>
              <p className="font-semibold text-sm text-stone-800">{t("feedback.all_good")}</p>
            </button>
            <button data-testid="btn-need-help" onClick={() => setSelectedResponse("need_help")} className={`p-5 rounded-xl border-2 text-center transition-all ${selectedResponse === "need_help" ? "border-amber-500 bg-amber-50" : "border-stone-200 hover:border-amber-300"}`}>
              <div className="text-3xl mb-2">
                <svg className="w-10 h-10 mx-auto text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" /></svg>
              </div>
              <p className="font-semibold text-sm text-stone-800">{t("feedback.need_help")}</p>
            </button>
          </div>

          {/* Message if need help */}
          {selectedResponse === "need_help" && (
            <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} className="mb-5">
              <label className="block text-xs font-medium text-stone-600 mb-1.5">Tell us how we can help</label>
              <textarea data-testid="feedback-message" value={message} onChange={(e) => setMessage(e.target.value)} rows={3} className="w-full px-3 py-2.5 rounded-lg border border-stone-200 text-sm focus:ring-2 focus:ring-amber-200 focus:border-amber-400 outline-none transition resize-none" placeholder="e.g. Room temperature issue, extra towels needed..." />
            </motion.div>
          )}

          <button data-testid="btn-submit-feedback" onClick={submit} disabled={!selectedResponse || submitting} className="w-full py-3 bg-[#2C4C3B] text-white text-sm font-semibold rounded-lg hover:bg-[#234030] disabled:opacity-40 disabled:cursor-not-allowed transition">
            {submitting ? t("common.loading") : t("feedback.submit")}
          </button>
        </div>

        <div className="text-center pb-4 text-[10px] text-stone-300">
          Booking Ref: {feedback?.booking_ref || "—"}
        </div>
      </motion.div>
    </div>
  );
}
