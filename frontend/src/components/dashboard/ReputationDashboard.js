/**
 * Reputation Dashboard — aggregates reviews from Booking.com / Google / TripAdvisor
 * into a single panel with sentiment trend + AI-generated reply suggestions.
 *
 * Backed by the existing /reviews/* and /reviews/stats/summary endpoints in
 * routes/reviews.py — no new backend work needed for MVP. Real OAuth-based
 * platform syncs land in a follow-up sprint; for now the data model is identical
 * regardless of platform, so the UI is stable across that transition.
 */
import { useState, useEffect, useCallback, useMemo } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Star, Loader2, Sparkles, RefreshCw, Send, Filter, MessageSquare,
  TrendingUp, ThumbsUp, ThumbsDown, AlertCircle,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Platform palette — used for badges and source breakdown chart
const PLATFORM_META = {
  booking: { label: "Booking.com", colour: "#003580", short: "Booking" },
  google: { label: "Google", colour: "#4285f4", short: "Google" },
  tripadvisor: { label: "TripAdvisor", colour: "#34e0a1", short: "Trip" },
  expedia: { label: "Expedia", colour: "#fbcc33", short: "Expedia" },
  airbnb: { label: "Airbnb", colour: "#ff5a5f", short: "Airbnb" },
  direct: { label: "Direct", colour: "#a78bfa", short: "Direct" },
};

const sentimentTone = (s) => {
  if (s === "positive") return { bg: "bg-emerald-500/15", text: "text-emerald-300", ring: "border-emerald-500/30", icon: ThumbsUp };
  if (s === "negative") return { bg: "bg-rose-500/15", text: "text-rose-300", ring: "border-rose-500/30", icon: ThumbsDown };
  return { bg: "bg-amber-500/15", text: "text-amber-300", ring: "border-amber-500/30", icon: AlertCircle };
};

export default function ReputationDashboard({ propertyId, hotelName = "" }) {
  const [stats, setStats] = useState(null);
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState({ platform: "all", sentiment: "all", responded: "all" });
  const [activeReview, setActiveReview] = useState(null);   // currently composing a reply for
  const [draftReply, setDraftReply] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [seeding, setSeeding] = useState(false);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const params = propertyId && propertyId !== "all" ? `?property_id=${propertyId}` : "";
      const [statsRes, reviewsRes] = await Promise.all([
        axios.get(`${API}/reviews/stats/summary${params}`),
        axios.get(`${API}/reviews${params}`),
      ]);
      setStats(statsRes.data);
      setReviews(Array.isArray(reviewsRes.data) ? reviewsRes.data : []);
    } catch { /* ignore */ }
    setLoading(false);
  }, [propertyId]);

  useEffect(() => { loadAll(); }, [loadAll]);

  // Branch hygiene — wipe previous branch's data on switch
  useEffect(() => {
    setStats(null);
    setReviews([]);
    setActiveReview(null);
    setDraftReply("");
  }, [propertyId]);

  const seedDemo = async () => {
    setSeeding(true);
    try {
      const { data } = await axios.post(`${API}/reviews/seed`);
      if (data.seeded) toast.success(`${data.count || ""} demo review eklendi`);
      else toast.info(data.message || "Already seeded");
      await loadAll();
    } catch { toast.error("Seed failed"); }
    setSeeding(false);
  };

  const generateAIReply = async (review) => {
    setAiLoading(true);
    try {
      const { data } = await axios.post(`${API}/reviews/generate-ai-response`, {
        review_id: review.id,
        review_text: review.text || review.review_text || "",
        rating: review.rating,
        guest_name: review.guest_name || review.author || "Guest",
        property_name: hotelName,
      });
      const text = data?.response_text || data?.response || data?.text || "";
      setDraftReply(text);
      toast.success("AI reply hazır — düzenleyip gönderebilirsiniz");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "AI generation failed");
    }
    setAiLoading(false);
  };

  const sendReply = async () => {
    if (!activeReview || !draftReply.trim()) return;
    setSubmitting(true);
    try {
      await axios.put(`${API}/reviews/${activeReview.id}/respond`, {
        response_text: draftReply.trim(),
      });
      toast.success("Yanıt kaydedildi");
      setActiveReview(null);
      setDraftReply("");
      await loadAll();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Save failed");
    }
    setSubmitting(false);
  };

  const filtered = useMemo(() => reviews.filter(r => {
    if (filter.platform !== "all" && (r.platform || "").toLowerCase() !== filter.platform) return false;
    if (filter.sentiment !== "all" && (r.sentiment || "").toLowerCase() !== filter.sentiment) return false;
    if (filter.responded === "responded" && r.response_status !== "responded") return false;
    if (filter.responded === "pending" && r.response_status === "responded") return false;
    return true;
  }), [reviews, filter]);

  const sentimentBreakdown = useMemo(() => {
    const out = { positive: 0, neutral: 0, negative: 0 };
    reviews.forEach(r => {
      const s = (r.sentiment || "").toLowerCase();
      if (s in out) out[s] += 1;
      else if (r.rating >= 4) out.positive += 1;
      else if (r.rating <= 2) out.negative += 1;
      else out.neutral += 1;
    });
    return out;
  }, [reviews]);

  const totalForBars = Math.max(reviews.length, 1);

  return (
    <div className="p-5 space-y-5" data-testid="reputation-dashboard">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-stone-100 flex items-center gap-2">
            <Star className="w-5 h-5 text-amber-400" />
            Reputation
            {hotelName && <>
              <span className="text-stone-500 mx-1">·</span>
              <span className="text-violet-400" data-testid="rep-hotel-name">{hotelName}</span>
            </>}
          </h2>
          <p className="text-xs text-stone-400">
            Booking.com · Google · TripAdvisor review aggregator with AI-powered reply suggestions
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={seedDemo} disabled={seeding}
            data-testid="rep-seed-demo"
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-bold bg-violet-500/15 hover:bg-violet-500/25 text-violet-300 border border-violet-500/30 disabled:opacity-50"
            title="Database boşsa demo review'lar yükle">
            {seeding ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
            Seed demo
          </button>
          <button onClick={loadAll}
            data-testid="rep-refresh"
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-bold bg-stone-800 hover:bg-stone-700 text-stone-200 border border-stone-700">
            <RefreshCw className="w-3.5 h-3.5" />
            Yenile
          </button>
        </div>
      </div>

      {/* KPI cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="rep-kpis">
          <KPI
            icon={Star} tone="amber"
            label="Ort. Puan / Avg Rating"
            value={`${(stats.average_rating ?? 0).toFixed(1)} ★`}
            sub={`${stats.total_reviews} reviews`}
          />
          <KPI
            icon={MessageSquare} tone="cyan"
            label="Yanıt Oranı / Response Rate"
            value={`${stats.response_rate}%`}
            sub={`${stats.responded}/${stats.total_reviews}`}
          />
          <KPI
            icon={AlertCircle} tone="rose"
            label="Bekleyen / Pending"
            value={stats.pending + stats.pending_approval}
            sub={stats.pending_approval ? `${stats.pending_approval} approval` : "yanıt bekliyor"}
          />
          <KPI
            icon={TrendingUp} tone="emerald"
            label="Pozitif / Positive"
            value={`${Math.round((sentimentBreakdown.positive / totalForBars) * 100)}%`}
            sub={`${sentimentBreakdown.positive} review`}
          />
        </div>
      )}

      {/* Sentiment + Source bars */}
      {reviews.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-4" data-testid="rep-sentiment-card">
            <h3 className="text-xs font-bold uppercase tracking-widest text-stone-400 mb-3">Sentiment Breakdown</h3>
            <div className="space-y-2">
              {[
                ["positive", "Pozitif", "#10b981"],
                ["neutral", "Nötr", "#fbbf24"],
                ["negative", "Negatif", "#fb7185"],
              ].map(([key, label, colour]) => {
                const n = sentimentBreakdown[key];
                const pct = (n / totalForBars) * 100;
                return (
                  <div key={key} className="flex items-center gap-3">
                    <span className="text-xs font-bold text-stone-300 w-16">{label}</span>
                    <div className="flex-1 h-3 bg-stone-800 rounded-full overflow-hidden">
                      <div className="h-full transition-all" style={{ width: `${pct}%`, background: colour }} />
                    </div>
                    <span className="text-xs font-black text-stone-200 tabular-nums w-16 text-right">
                      {n} <span className="text-stone-500 font-normal">({pct.toFixed(0)}%)</span>
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          {stats?.by_platform && Object.keys(stats.by_platform).length > 0 && (
            <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-4" data-testid="rep-platforms-card">
              <h3 className="text-xs font-bold uppercase tracking-widest text-stone-400 mb-3">By Platform</h3>
              <div className="space-y-2">
                {Object.entries(stats.by_platform).map(([platform, count]) => {
                  const meta = PLATFORM_META[platform] || { label: platform, colour: "#888", short: platform };
                  const pct = (count / totalForBars) * 100;
                  return (
                    <div key={platform} className="flex items-center gap-3">
                      <span className="text-xs font-bold text-stone-300 w-20" style={{ color: meta.colour }}>{meta.label}</span>
                      <div className="flex-1 h-3 bg-stone-800 rounded-full overflow-hidden">
                        <div className="h-full" style={{ width: `${pct}%`, background: meta.colour }} />
                      </div>
                      <span className="text-xs font-black text-stone-200 tabular-nums w-12 text-right">{count}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2 bg-stone-900/40 border border-stone-800 rounded-xl p-2" data-testid="rep-filters">
        <Filter className="w-4 h-4 text-stone-500" />
        <FilterPill value={filter.platform} onChange={(v) => setFilter({ ...filter, platform: v })}
          options={[["all", "Tüm platformlar"], ["booking", "Booking"], ["google", "Google"], ["tripadvisor", "TripAdvisor"], ["expedia", "Expedia"], ["airbnb", "Airbnb"]]} />
        <FilterPill value={filter.sentiment} onChange={(v) => setFilter({ ...filter, sentiment: v })}
          options={[["all", "Tüm duygular"], ["positive", "Pozitif"], ["neutral", "Nötr"], ["negative", "Negatif"]]} />
        <FilterPill value={filter.responded} onChange={(v) => setFilter({ ...filter, responded: v })}
          options={[["all", "Tümü"], ["pending", "Yanıt bekliyor"], ["responded", "Yanıtlanmış"]]} />
        <span className="ml-auto text-[11px] text-stone-500 tabular-nums">
          <b className="text-stone-200">{filtered.length}</b> / {reviews.length} review
        </span>
      </div>

      {/* Review list */}
      {loading ? (
        <div className="text-center py-12 text-stone-500"><Loader2 className="w-5 h-5 animate-spin inline mr-2" />Yükleniyor…</div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-12 text-stone-500 bg-stone-900/40 border border-stone-800 rounded-2xl">
          {reviews.length === 0
            ? <>Henüz review yok. Üstteki <b>Seed demo</b> butonuna basarak demo verileri yükleyebilirsiniz.</>
            : <>Filtre eşleşmesi yok. Filtreleri sıfırlayın.</>}
        </div>
      ) : (
        <div className="space-y-2" data-testid="rep-review-list">
          {filtered.slice(0, 50).map(r => (
            <ReviewRow key={r.id} review={r}
              onReply={() => { setActiveReview(r); setDraftReply(r.response?.text || r.response_text || ""); }} />
          ))}
        </div>
      )}

      {/* Reply composer modal */}
      {activeReview && (
        <ReplyComposer
          review={activeReview}
          draft={draftReply}
          setDraft={setDraftReply}
          aiLoading={aiLoading}
          submitting={submitting}
          onAI={() => generateAIReply(activeReview)}
          onSend={sendReply}
          onClose={() => { setActiveReview(null); setDraftReply(""); }}
        />
      )}
    </div>
  );
}

function KPI({ icon: Icon, tone, label, value, sub }) {
  const tones = {
    amber: { bg: "bg-amber-500/10", text: "text-amber-300", ring: "border-amber-500/30" },
    cyan: { bg: "bg-cyan-500/10", text: "text-cyan-300", ring: "border-cyan-500/30" },
    emerald: { bg: "bg-emerald-500/10", text: "text-emerald-300", ring: "border-emerald-500/30" },
    rose: { bg: "bg-rose-500/10", text: "text-rose-300", ring: "border-rose-500/30" },
  }[tone];
  return (
    <div className={`rounded-xl p-3 border ${tones.bg} ${tones.ring}`}>
      <div className="flex items-center gap-2 mb-1">
        <Icon className={`w-3.5 h-3.5 ${tones.text}`} />
        <span className="text-[10px] font-bold uppercase tracking-widest text-stone-400">{label}</span>
      </div>
      <div className={`text-2xl font-black ${tones.text} tabular-nums`}>{value}</div>
      {sub && <div className="text-[10px] text-stone-500 mt-0.5">{sub}</div>}
    </div>
  );
}

function FilterPill({ value, onChange, options }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)}
      className="text-[11px] bg-stone-900 border border-stone-700 rounded-lg px-2 py-1 text-stone-200 cursor-pointer hover:border-stone-500">
      {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
    </select>
  );
}

function ReviewRow({ review, onReply }) {
  const platform = (review.platform || "direct").toLowerCase();
  const meta = PLATFORM_META[platform] || PLATFORM_META.direct;
  const tone = sentimentTone(review.sentiment);
  const Icon = tone.icon;
  const responded = review.response_status === "responded" || review.response?.text;
  return (
    <div className="rounded-xl bg-stone-900/60 border border-stone-800 hover:border-stone-700 transition-all p-4"
      data-testid={`rep-review-${review.id}`}>
      <div className="flex flex-wrap items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full" style={{ background: meta.colour + "22", color: meta.colour }}>
            {meta.label}
          </span>
          <span className="flex items-center gap-0.5 text-amber-400 text-xs font-bold">
            {Array.from({ length: review.rating || 0 }).map((_, i) => <Star key={i} className="w-3 h-3 fill-current" />)}
          </span>
          {review.sentiment && (
            <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${tone.bg} ${tone.text} ${tone.ring} flex items-center gap-1`}>
              <Icon className="w-2.5 h-2.5" />
              {review.sentiment}
            </span>
          )}
          {responded && <span className="text-[10px] font-bold text-emerald-300 bg-emerald-500/15 border border-emerald-500/30 rounded-full px-2 py-0.5">Yanıtlandı</span>}
          <span className="text-[10px] text-stone-500">{review.guest_name || review.author || "Guest"}</span>
          {review.created_at && <span className="text-[10px] text-stone-600">· {new Date(review.created_at).toLocaleDateString()}</span>}
        </div>
        <button onClick={onReply}
          data-testid={`rep-review-reply-${review.id}`}
          className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-[11px] font-bold transition-all ${
            responded
              ? "bg-stone-800 text-stone-300 hover:bg-stone-700"
              : "bg-gradient-to-r from-violet-600 to-cyan-600 text-white hover:brightness-110"
          }`}>
          {responded ? "Düzenle" : "Yanıtla"}
        </button>
      </div>
      <p className="text-sm text-stone-200 leading-relaxed">{review.text || review.review_text}</p>
      {responded && (review.response?.text || review.response_text) && (
        <div className="mt-3 pl-4 border-l-2 border-emerald-500/40 bg-emerald-500/5 rounded-r-lg p-2">
          <span className="text-[9px] font-bold uppercase tracking-widest text-emerald-400">Sizin yanıtınız</span>
          <p className="text-xs text-stone-300 mt-1">{review.response?.text || review.response_text}</p>
        </div>
      )}
    </div>
  );
}

function ReplyComposer({ review, draft, setDraft, aiLoading, submitting, onAI, onSend, onClose }) {
  return (
    <div className="fixed inset-0 z-[80] bg-black/60 backdrop-blur-sm flex items-center justify-center p-4"
         onClick={onClose}>
      <div className="bg-stone-950 border border-stone-800 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col"
           onClick={(e) => e.stopPropagation()} data-testid="rep-reply-modal">
        <div className="p-5 border-b border-stone-800">
          <h3 className="text-sm font-bold text-stone-100">Reply to {review.guest_name || review.author || "Guest"}</h3>
          <p className="text-[11px] text-stone-500 mt-1">Original review:</p>
          <blockquote className="text-xs text-stone-300 italic border-l-2 border-stone-700 pl-3 mt-2 line-clamp-3">
            {review.text || review.review_text}
          </blockquote>
        </div>
        <div className="p-5 flex-1 overflow-y-auto">
          <textarea value={draft} onChange={(e) => setDraft(e.target.value)}
            placeholder="Yanıtınızı buraya yazın veya AI'a yazdırın…"
            rows={8}
            data-testid="rep-reply-textarea"
            className="w-full bg-stone-900 border border-stone-700 rounded-xl text-sm text-stone-100 p-3 focus:ring-2 focus:ring-violet-500/40 focus:border-violet-500 outline-none resize-none" />
        </div>
        <div className="flex items-center justify-between gap-2 p-4 border-t border-stone-800">
          <button onClick={onAI} disabled={aiLoading}
            data-testid="rep-reply-ai"
            className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-bold bg-gradient-to-r from-cyan-500 to-violet-500 text-white hover:brightness-110 disabled:opacity-50">
            {aiLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
            {aiLoading ? "Üretiliyor…" : "AI ile yaz"}
          </button>
          <div className="flex items-center gap-2">
            <button onClick={onClose}
              className="px-3 py-2 rounded-xl text-xs font-bold bg-stone-800 text-stone-300 hover:bg-stone-700">
              İptal
            </button>
            <button onClick={onSend} disabled={submitting || !draft.trim()}
              data-testid="rep-reply-send"
              className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-bold bg-emerald-500 text-black hover:brightness-110 disabled:opacity-50">
              {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              {submitting ? "Kaydediliyor…" : "Gönder"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
