import { useState, useEffect } from "react";
import axios from "axios";
import { motion } from "framer-motion";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const EMOJI_SCALE = ["😠", "😟", "😕", "🙁", "😐", "🙂", "😊", "😃", "😍", "🤩", "🥳"];

export default function GuestSurveyPage({ token }) {
  const [survey, setSurvey] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitted, setSubmitted] = useState(false);
  const [reviewPrompt, setReviewPrompt] = useState(null);
  const [nps, setNps] = useState(null);
  const [catRatings, setCatRatings] = useState({});
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const { data } = await axios.get(`${API}/surveys/public/${token}`);
        if (data.completed) {
          setSubmitted(true);
        }
        setSurvey(data);
      } catch (e) {
        setError("Survey not found or has expired.");
      }
      setLoading(false);
    };
    load();
  }, [token]);

  const submit = async () => {
    if (nps === null) return;
    setSubmitting(true);
    try {
      const { data } = await axios.post(`${API}/surveys/public/${token}`, {
        nps_score: nps,
        category_ratings: catRatings,
        comment,
      });
      if (data?.review_prompt?.show) setReviewPrompt(data.review_prompt);
      setSubmitted(true);
    } catch (e) {
      setError("Failed to submit. Please try again.");
    }
    setSubmitting(false);
  };

  if (loading) return (
    <div className="min-h-screen bg-stone-50 flex items-center justify-center">
      <div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );

  if (error) return (
    <div className="min-h-screen bg-stone-50 flex items-center justify-center p-4">
      <div className="text-center">
        <p className="text-lg text-stone-600">{error}</p>
      </div>
    </div>
  );

  if (submitted) return (
    <div className="min-h-screen bg-gradient-to-b from-emerald-50 to-white flex items-center justify-center p-4">
      <motion.div initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="text-center max-w-md">
        <div className="w-20 h-20 rounded-full bg-emerald-100 flex items-center justify-center mx-auto mb-6">
          <span className="text-4xl">🙏</span>
        </div>
        <h1 className="text-2xl font-bold text-stone-900 mb-3">Thank You!</h1>
        <p className="text-stone-600">{survey?.thank_you_message || "Your feedback has been submitted. We truly appreciate you taking the time to share your experience."}</p>
        {reviewPrompt?.show && (
          <div className="mt-6 p-4 rounded-xl bg-amber-50 border border-amber-200 space-y-3" data-testid="survey-review-prompt">
            <p className="text-sm text-stone-700">{reviewPrompt.message}</p>
            <div className="flex gap-2 justify-center flex-wrap">
              {reviewPrompt.tripadvisor_url && (
                <a data-testid="survey-tripadvisor-btn" href={reviewPrompt.tripadvisor_url} target="_blank" rel="noreferrer"
                  className="px-4 py-2 rounded-full bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium">
                  ⭐ TripAdvisor'da Değerlendir
                </a>
              )}
              {reviewPrompt.google_url && (
                <a data-testid="survey-google-btn" href={reviewPrompt.google_url} target="_blank" rel="noreferrer"
                  className="px-4 py-2 rounded-full bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium">
                  Google'da Değerlendir
                </a>
              )}
            </div>
          </div>
        )}
      </motion.div>
    </div>
  );

  return (
    <div className="min-h-screen bg-gradient-to-b from-stone-50 to-white">
      <div className="max-w-xl mx-auto px-4 py-10">
        <motion.div initial={{ y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }}>
          {/* Header */}
          <div className="text-center mb-8">
            <h1 className="text-2xl font-bold text-stone-900 mb-1">{survey?.hotel_name || "Hotel"}</h1>
            <p className="text-stone-500">How was your stay?</p>
            {survey?.check_in && survey?.check_out && (
              <p className="text-xs text-stone-400 mt-1">{survey.check_in} — {survey.check_out}</p>
            )}
          </div>

          {/* NPS Section */}
          <div className="bg-white rounded-2xl shadow-sm border border-stone-200 p-6 mb-6" data-testid="nps-section">
            <h2 className="text-base font-semibold text-stone-800 mb-1">How likely are you to recommend us?</h2>
            <p className="text-xs text-stone-400 mb-5">On a scale of 0 to 10</p>

            <div className="flex justify-center gap-1.5 mb-3">
              {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(score => (
                <button key={score} onClick={() => setNps(score)}
                  className={`w-10 h-10 rounded-xl text-sm font-bold transition-all ${
                    nps === score
                      ? score >= 9 ? "bg-emerald-500 text-white scale-110 shadow-lg" : score >= 7 ? "bg-amber-400 text-white scale-110 shadow-lg" : "bg-red-500 text-white scale-110 shadow-lg"
                      : "bg-stone-100 text-stone-600 hover:bg-stone-200"
                  }`} data-testid={`nps-btn-${score}`}>
                  {score}
                </button>
              ))}
            </div>
            <div className="flex justify-between text-[10px] text-stone-400 px-1">
              <span>Not at all likely</span>
              <span>Extremely likely</span>
            </div>
            {nps !== null && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                className="text-center mt-4">
                <span className="text-3xl">{EMOJI_SCALE[nps]}</span>
              </motion.div>
            )}
          </div>

          {/* Category Ratings */}
          {survey?.survey_type === "detailed" && survey?.categories?.length > 0 && (
            <div className="bg-white rounded-2xl shadow-sm border border-stone-200 p-6 mb-6" data-testid="category-section">
              <h2 className="text-base font-semibold text-stone-800 mb-4">Rate your experience</h2>
              <div className="space-y-4">
                {survey.categories.filter(c => c.enabled).map(cat => (
                  <div key={cat.key}>
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-sm text-stone-700">{cat.label}</span>
                      {catRatings[cat.key] && (
                        <span className="text-xs font-medium text-stone-500">{catRatings[cat.key]}/5</span>
                      )}
                    </div>
                    <div className="flex gap-2">
                      {[1, 2, 3, 4, 5].map(star => (
                        <button key={star} onClick={() => setCatRatings(prev => ({ ...prev, [cat.key]: star }))}
                          className={`flex-1 h-9 rounded-lg text-sm font-medium transition-all ${
                            catRatings[cat.key] >= star
                              ? star >= 4 ? "bg-emerald-500 text-white" : star >= 3 ? "bg-amber-400 text-white" : "bg-red-400 text-white"
                              : "bg-stone-100 text-stone-500 hover:bg-stone-200"
                          }`} data-testid={`cat-${cat.key}-star-${star}`}>
                          {star}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Comment */}
          <div className="bg-white rounded-2xl shadow-sm border border-stone-200 p-6 mb-6" data-testid="comment-section">
            <h2 className="text-base font-semibold text-stone-800 mb-2">Any additional feedback?</h2>
            <textarea
              value={comment} onChange={e => setComment(e.target.value)}
              placeholder="Tell us what you loved or what we can improve..."
              rows={4}
              className="w-full border border-stone-200 rounded-xl px-4 py-3 text-sm text-stone-700 placeholder-stone-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent resize-none"
              data-testid="survey-comment"
            />
          </div>

          {/* Submit */}
          <button onClick={submit} disabled={nps === null || submitting}
            className="w-full bg-emerald-600 text-white py-3.5 rounded-xl text-base font-semibold hover:bg-emerald-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            data-testid="submit-survey-btn">
            {submitting ? "Submitting..." : "Submit Feedback"}
          </button>

          <p className="text-center text-[10px] text-stone-400 mt-4">Your feedback is anonymous and helps us improve.</p>
        </motion.div>
      </div>
    </div>
  );
}
