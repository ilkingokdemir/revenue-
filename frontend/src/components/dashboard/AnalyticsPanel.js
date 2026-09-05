import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { motion } from "framer-motion";
import { 
  ChartBar, TrendUp, TrendDown, Star, Trophy, Target, Brain, Fire, 
  Smiley, SmileyMeh, SmileySad, CalendarBlank, X, ArrowsClockwise,
  ChatText, CheckCircle, WarningCircle, Lightning, Tag, Users, Buildings,
  Trash, Plus, Sparkle
} from "@phosphor-icons/react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
// iter 389: converted from modal to inline page panel (Dialog imports replaced by shells)
const DialogContent = ({ children, className = "", ...rest }) => (
  <div className={`bg-white border border-stone-200/80 rounded-xl shadow-card p-6 w-full ${className}`} {...rest}>{children}</div>
);
const DialogHeader = ({ children, className = "" }) => <div className={`mb-4 ${className}`}>{children}</div>;
const DialogTitle = ({ children, className = "" }) => <h2 className={`text-lg font-semibold ${className}`}>{children}</h2>;
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import { useTranslation } from "@/i18n";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { API, PLATFORMS, SENTIMENT_COLORS, URGENCY_COLORS } from "./config";
import { StarRating } from "./ReviewComponents";

const AnalyticsPanel = ({ isOpen, onClose }) => {
  const [analytics, setAnalytics] = useState(null);
  const [competitors, setCompetitors] = useState([]);
  const [benchmark, setBenchmark] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [topicCompare, setTopicCompare] = useState(null);
  const { t } = useTranslation();
  const [compIntel, setCompIntel] = useState(null);
  const actGap = async (item, action) => {
    try {
      const { data } = await axios.post(`${API}/reputation/competitor-intel/default/act`, { item, action });
      toast.success(action === "add_amenity" ? `'${item}' web sitesi/OTA olanak listesine eklendi` : data.duplicate ? "Bu fizibilite görevi zaten açık" : `Fizibilite görevi açıldı: ${item}`);
      if (action === "add_amenity") { const r = await axios.get(`${API}/reputation/competitor-intel/default`); setCompIntel(r.data); }
    } catch (e) { toast.error(e.response?.data?.detail || "İşlem yapılamadı"); }
  };
  const [impacts, setImpacts] = useState([]);
  const runImpact = async () => {
    try {
      const { data } = await axios.post(`${API}/reviews/root-cause/impact/run?property_id=all`);
      toast.success(`${data.reported} görev etkisi raporlandı`);
      const r = await axios.get(`${API}/reviews/root-cause/impact?property_id=all`); setImpacts(r.data.items || []);
    } catch (e) { toast.error(e.response?.data?.detail || "Çalıştırılamadı"); }
  };
  const [praiseBusy, setPraiseBusy] = useState(false);
  const runStaffPraise = async () => {
    setPraiseBusy(true);
    try {
      const { data } = await axios.post(`${API}/reviews/staff-praise/run?property_id=all`);
      const w = (data.results || []).filter(r => r.winner);
      toast.success(w.length ? `Haftanın yıldızı: ${w.map(r => `${r.winner} (${r.positive} övgü)`).join(", ")} — yöneticilere bildirildi (MOCK)` : "Son 7 günde övgü alan personel yok");
    } catch (e) { toast.error(e.response?.data?.detail || "Çalıştırılamadı"); }
    finally { setPraiseBusy(false); }
  };
  const [newCompetitor, setNewCompetitor] = useState({ name: "", avg_rating: 4.0, total_reviews: 100, response_rate: 50 });

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [analyticsRes, competitorsRes, benchmarkRes] = await Promise.all([
        axios.get(`${API}/analytics/dashboard`),
        axios.get(`${API}/competitors`),
        axios.get(`${API}/competitors/benchmark`)
      ]);
      setAnalytics(analyticsRes.data);
      setCompetitors(competitorsRes.data);
      setBenchmark(benchmarkRes.data);
      axios.get(`${API}/reputation/topic-compare/default`).then(r => setTopicCompare(r.data)).catch(() => {});
      axios.get(`${API}/reputation/competitor-intel/default`).then(r => setCompIntel(r.data)).catch(() => {});
      axios.get(`${API}/reviews/root-cause/impact?property_id=all`).then(r => setImpacts(r.data.items || [])).catch(() => {});
    } catch (error) {
      console.error("Error fetching analytics:", error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const seedCompetitors = useCallback(async () => {
    try {
      await axios.post(`${API}/competitors/seed`);
      await fetchData();
    } catch (error) {
      console.error("Error seeding competitors:", error);
    }
  }, [fetchData]);

  useEffect(() => {
    if (isOpen) {
      seedCompetitors();
      fetchData();
    }
  }, [isOpen, fetchData, seedCompetitors]);

  const runBatchAnalysis = async () => {
    setIsAnalyzing(true);
    try {
      const result = await axios.post(`${API}/reviews/analyze-batch`);
      toast.success(`Analyzed ${result.data.analyzed} reviews!`);
      await fetchData();
    } catch (error) {
      console.error("Error running analysis:", error);
      toast.error("Failed to run analysis");
    } finally {
      setIsAnalyzing(false);
    }
  };

  const addCompetitor = async () => {
    if (!newCompetitor.name) return;
    try {
      await axios.post(`${API}/competitors`, {
        ...newCompetitor,
        platform: "all"
      });
      toast.success("Competitor added!");
      setNewCompetitor({ name: "", avg_rating: 4.0, total_reviews: 100, response_rate: 50 });
      await fetchData();
    } catch (error) {
      console.error("Error adding competitor:", error);
      toast.error("Failed to add competitor");
    }
  };

  const deleteCompetitor = async (id) => {
    try {
      await axios.delete(`${API}/competitors/${id}`);
      toast.success("Competitor removed");
      await fetchData();
    } catch (error) {
      console.error("Error deleting competitor:", error);
    }
  };

  const getSentimentIcon = (sentiment) => {
    switch (sentiment) {
      case "positive": return <Smiley size={16} weight="fill" className="text-[#5A6B50]" />;
      case "negative": return <SmileySad size={16} weight="fill" className="text-[#C05A44]" />;
      default: return <SmileyMeh size={16} weight="fill" className="text-[#57534E]" />;
    }
  };

  return (
    <DialogContent className="sm:max-w-[900px] max-h-[90vh] overflow-y-auto" data-testid="analytics-dialog">
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2 text-[#1C1917] font-['Work_Sans']">
          <ChartBar size={20} weight="fill" className="text-[#3E5245]" />
          Analytics & Insights
        </DialogTitle>
      </DialogHeader>

      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <ArrowsClockwise size={32} className="animate-spin text-[#3E5245]" />
        </div>
      ) : (
        <Tabs defaultValue="overview" className="w-full">
          <TabsList className="grid w-full grid-cols-3 mb-4">
            <TabsTrigger value="overview" data-testid="analytics-overview-tab">Overview</TabsTrigger>
            <TabsTrigger value="sentiment" data-testid="analytics-sentiment-tab">Sentiment</TabsTrigger>
            <TabsTrigger value="competitors" data-testid="analytics-competitors-tab">Competitors</TabsTrigger>
          </TabsList>

          {/* Overview Tab */}
          <TabsContent value="overview" className="space-y-4">
            {/* Key Metrics */}
            <div className="grid grid-cols-4 gap-3">
              <div className="bg-[#FAF9F6] border border-stone-200 rounded-md p-4">
                <div className="flex items-center gap-2 text-[#57534E] mb-1">
                  <ChatText size={16} />
                  <span className="text-xs uppercase tracking-wider">Reviews</span>
                </div>
                <div className="text-2xl font-semibold text-[#1C1917]">{analytics?.overview?.total_reviews || 0}</div>
              </div>
              <div className="bg-[#FAF9F6] border border-stone-200 rounded-md p-4">
                <div className="flex items-center gap-2 text-[#57534E] mb-1">
                  <Star size={16} weight="fill" className="text-[#D4A373]" />
                  <span className="text-xs uppercase tracking-wider">Avg Rating</span>
                </div>
                <div className="text-2xl font-semibold text-[#1C1917]">{analytics?.overview?.avg_rating || 0}/5</div>
              </div>
              <div className="bg-[#FAF9F6] border border-stone-200 rounded-md p-4">
                <div className="flex items-center gap-2 text-[#57534E] mb-1">
                  <CheckCircle size={16} className="text-[#5A6B50]" />
                  <span className="text-xs uppercase tracking-wider">Response Rate</span>
                </div>
                <div className="text-2xl font-semibold text-[#1C1917]">{analytics?.overview?.response_rate || 0}%</div>
              </div>
              <div className="bg-[#FAF9F6] border border-stone-200 rounded-md p-4">
                <div className="flex items-center gap-2 text-[#57534E] mb-1">
                  <WarningCircle size={16} className="text-[#D4A373]" />
                  <span className="text-xs uppercase tracking-wider">Pending</span>
                </div>
                <div className="text-2xl font-semibold text-[#1C1917]">{analytics?.overview?.pending || 0}</div>
              </div>
            </div>

            {/* Rating Distribution */}
            <div className="bg-white border border-stone-200 rounded-md p-4">
              <h4 className="font-medium text-[#1C1917] mb-3 flex items-center gap-2">
                <Star size={18} className="text-[#D4A373]" />
                Rating Distribution
              </h4>
              <div className="space-y-2">
                {[5, 4, 3, 2, 1].map((rating) => {
                  const count = analytics?.rating_distribution?.[rating] || 0;
                  const total = analytics?.overview?.total_reviews || 1;
                  const percentage = Math.round((count / total) * 100);
                  return (
                    <div key={rating} className="flex items-center gap-3">
                      <span className="w-12 text-sm text-[#57534E]">{rating} star</span>
                      <Progress value={percentage} className="flex-1 h-2" />
                      <span className="w-16 text-sm text-[#57534E] text-right">{count} ({percentage}%)</span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Platform Stats */}
            <div className="bg-white border border-stone-200 rounded-md p-4">
              <h4 className="font-medium text-[#1C1917] mb-3">Platform Performance</h4>
              <div className="grid grid-cols-3 gap-2">
                {analytics?.platform_stats?.map((platform) => (
                  <div key={platform.platform} className="flex items-center justify-between p-2 bg-[#FAF9F6] rounded">
                    <span className="text-sm font-medium">{PLATFORMS[platform.platform]?.name || platform.platform}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-[#57534E]">{platform.count} reviews</span>
                      <Badge className="bg-[#3E5245] text-white">{platform.avg_rating}/5</Badge>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Priority Queue */}
            {analytics?.priority_queue?.length > 0 && (
              <div className="bg-red-50 border border-[#C05A44] rounded-md p-4">
                <h4 className="font-medium text-[#C05A44] mb-3 flex items-center gap-2">
                  <Fire size={18} weight="fill" />
                  Priority Queue - Urgent Reviews
                </h4>
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {analytics.priority_queue.slice(0, 5).map((review) => (
                    <div key={review.id} className="flex items-center justify-between p-2 bg-white rounded border border-stone-200">
                      <div>
                        <span className="font-medium text-sm">{review.guest_name}</span>
                        <span className="text-xs text-[#57534E] ml-2">- {PLATFORMS[review.platform]?.name}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <StarRating rating={review.rating} size={12} />
                        <Badge className={`${URGENCY_COLORS[review.sentiment_analysis?.urgency || 'high']} text-white`}>
                          {review.sentiment_analysis?.urgency || 'urgent'}
                        </Badge>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </TabsContent>

          {/* Sentiment Tab */}
          <TabsContent value="sentiment" className="space-y-4">
            <div className="flex justify-between items-center">
              <h4 className="font-medium text-[#1C1917] flex items-center gap-2">
                <Brain size={18} className="text-[#3E5245]" />
                AI Sentiment Analysis
              </h4>
              <button
                onClick={runBatchAnalysis}
                disabled={isAnalyzing}
                className="bg-[#3E5245] text-white px-3 py-1.5 rounded-md text-sm hover:bg-[#2A3B30] transition-colors disabled:opacity-50 flex items-center gap-2"
                data-testid="run-analysis-btn"
              >
                {isAnalyzing ? <ArrowsClockwise size={14} className="animate-spin" /> : <Sparkle size={14} />}
                {isAnalyzing ? "Analyzing..." : "Run Analysis"}
              </button>
            </div>

            {/* Sentiment Distribution */}
            <div className="grid grid-cols-4 gap-3">
              {Object.entries(analytics?.sentiment_distribution || {}).map(([sentiment, count]) => (
                <div key={sentiment} className={`${SENTIMENT_COLORS[sentiment]?.light || 'bg-stone-100'} border rounded-md p-4`}>
                  <div className="flex items-center gap-2 mb-2">
                    {getSentimentIcon(sentiment)}
                    <span className="text-sm font-medium capitalize">{sentiment}</span>
                  </div>
                  <div className="text-2xl font-semibold">{count}</div>
                </div>
              ))}
            </div>

            {/* Urgency Distribution */}
            <div className="bg-white border border-stone-200 rounded-md p-4">
              <h4 className="font-medium text-[#1C1917] mb-3 flex items-center gap-2">
                <Lightning size={18} className="text-[#D4A373]" />
                Urgency Breakdown
              </h4>
              <div className="flex gap-2">
                {Object.entries(analytics?.urgency_distribution || {}).map(([urgency, count]) => (
                  <div key={urgency} className="flex-1 text-center">
                    <div className={`${URGENCY_COLORS[urgency]} text-white rounded-md p-3 mb-1`}>
                      <div className="text-xl font-semibold">{count}</div>
                    </div>
                    <span className="text-xs text-[#57534E] capitalize">{urgency}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Review Ops: Root Cause + Staff Intelligence */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-white border border-stone-200 rounded-md p-4" data-testid="root-cause-card">
                <h4 className="font-medium text-[#1C1917] mb-1 flex items-center gap-2">
                  <TrendDown size={18} className="text-[#C05A44]" /> {t("ro.root_cause")}
                </h4>
                <p className="text-[11px] text-stone-400 mb-3">{analytics?.root_cause?.negative_reviews ?? 0} negative reviews vs {analytics?.root_cause?.previous_negative_reviews ?? 0} previous period</p>
                <div className="space-y-2">
                  {(analytics?.root_cause?.items || []).slice(0, 5).map((it) => (
                    <div key={it.topic} className="border border-stone-100 rounded p-2" data-testid={`root-cause-${it.topic}`}>
                      <div className="flex items-center justify-between text-sm">
                        <span className="capitalize font-medium">{it.topic}{it.recurring && <span className="ml-1 text-[10px] text-red-600 font-bold">RECURRING</span>}</span>
                        <span className="text-xs">
                          <b>{it.frequency_pct}%</b>
                          <span className={`ml-1 ${it.trend_pts > 0 ? "text-red-600" : "text-emerald-600"}`}>{it.trend_pts > 0 ? "+" : ""}{it.trend_pts} pts</span>
                          <Badge className={`ml-2 ${it.severity === "high" ? "bg-red-100 text-red-700" : it.severity === "medium" ? "bg-amber-100 text-amber-800" : "bg-stone-100 text-stone-600"}`}>{it.severity}</Badge>
                        </span>
                      </div>
                      <p className="text-[11px] text-stone-500 mt-1">→ {it.action}</p>
                    </div>
                  ))}
                  {!(analytics?.root_cause?.items || []).length && <p className="text-xs text-stone-400">No recurring negative topics — analyze reviews first.</p>}
                </div>
                <div className="mt-3 border-t border-stone-100 pt-2" data-testid="root-cause-impact">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-stone-700">Görev Kapanış Etkisi (30g sonra)</span>
                    <button onClick={runImpact} data-testid="root-cause-impact-run-btn" className="text-[10px] px-2 py-0.5 rounded bg-stone-800 text-white">Şimdi hesapla</button>
                  </div>
                  {impacts.length === 0 && <p className="text-[11px] text-stone-400 mt-1">Henüz rapor yok — kapanan görevler 30 gün sonra otomatik raporlanır (07:30).</p>}
                  {impacts.slice(0, 4).map(r => (
                    <div key={r.id} className="text-[11px] mt-1 flex items-center justify-between" data-testid={`impact-${r.topic}`}>
                      <span className="capitalize">{r.topic} <span className="text-stone-400">({new Date(r.closed_at).toLocaleDateString()})</span></span>
                      <span className={r.verdict === "improved" ? "text-emerald-700 font-semibold" : r.verdict === "worse" ? "text-red-600 font-semibold" : "text-stone-500"}>
                        {r.before?.topic_avg_rating ?? "—"}★ → {r.after?.topic_avg_rating ?? "—"}★ · olumsuz %{r.before?.negative_pct} → %{r.after?.negative_pct} · {r.verdict}
                      </span>
                    </div>
                  ))}
                </div>
                <p className="text-[10px] text-stone-400 mt-2" data-testid="root-cause-task-note">high + recurring konular Sabah Karnesi'nde ilgili departmana otomatik görev açar; çözülen görevlerin trendi karneye yazılır.</p>
              </div>
              <div className="bg-white border border-stone-200 rounded-md p-4" data-testid="staff-intel-card">
                <h4 className="font-medium text-[#1C1917] mb-1 flex items-center gap-2">
                  <Users size={18} className="text-[#3E5245]" /> {t("ro.staff_intel")}
                </h4>
                <p className="text-[11px] text-stone-400 mb-3">Staff names mentioned in reviews — praise vs complaints</p>
                <div className="space-y-1.5">
                  {(analytics?.staff_intelligence?.staff || []).slice(0, 8).map((p) => (
                    <div key={p.name} className="flex items-center justify-between text-sm" data-testid={`staff-intel-${p.name}`}>
                      <span className="font-medium">{p.name} <span className="text-[10px] text-stone-400">★ {p.avg_rating}</span></span>
                      <span className="text-xs">
                        <span className="text-stone-500">{p.mentions} mentions</span>
                        <span className="ml-2 text-emerald-700 font-semibold">+{p.positive}</span>
                        <span className={`ml-1 font-semibold ${p.negative >= 2 ? "text-red-600" : "text-stone-400"}`}>−{p.negative}</span>
                      </span>
                    </div>
                  ))}
                  {!(analytics?.staff_intelligence?.staff || []).length && <p className="text-xs text-stone-400">No staff mentions detected yet.</p>}
                </div>
                {analytics?.staff_intelligence?.recurring_complaints?.length > 0 && (
                  <p className="text-[11px] text-red-600 mt-2" data-testid="staff-recurring">Recurring complaints: {analytics.staff_intelligence.recurring_complaints.map(x => x.name).join(", ")}</p>
                )}
                <button onClick={runStaffPraise} disabled={praiseBusy} data-testid="staff-praise-run-btn"
                  className="mt-3 text-[11px] px-2.5 py-1 rounded bg-[#3E5245] text-white hover:bg-[#2A3B30] disabled:opacity-50">
                  {praiseBusy ? "Gönderiliyor…" : "🏆 Haftalık ödül bildirimi gönder (Pazartesi 09:00 otomatik)"}
                </button>
              </div>
            </div>

            {/* Top Topics */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-white border border-stone-200 rounded-md p-4">
                <h4 className="font-medium text-[#1C1917] mb-3 flex items-center gap-2">
                  <Tag size={18} className="text-[#3E5245]" />
                  Top Mentioned Topics
                </h4>
                <div className="space-y-2">
                  {analytics?.top_topics?.slice(0, 6).map((topic, idx) => (
                    <div key={topic.topic} className="flex items-center justify-between">
                      <span className="text-sm capitalize">{topic.topic}</span>
                      <Badge className="bg-[#E8EDE7] text-[#1C1917]">{topic.count}</Badge>
                    </div>
                  ))}
                </div>
              </div>

              <div className="space-y-4">
                {/* Common Issues */}
                <div className="bg-red-50 border border-red-200 rounded-md p-4">
                  <h4 className="font-medium text-[#C05A44] mb-2 flex items-center gap-2">
                    <TrendDown size={16} />
                    Common Issues
                  </h4>
                  <div className="space-y-1">
                    {analytics?.common_issues?.slice(0, 3).map((item) => (
                      <div key={item.issue} className="text-sm text-[#57534E] truncate">
                        • {item.issue} ({item.count})
                      </div>
                    ))}
                    {(!analytics?.common_issues || analytics.common_issues.length === 0) && (
                      <div className="text-sm text-[#57534E]">Run analysis to see issues</div>
                    )}
                  </div>
                </div>

                {/* Common Praises */}
                <div className="bg-[#E8EDE7] border border-[#D5DDD3] rounded-md p-4">
                  <h4 className="font-medium text-[#3E5245] mb-2 flex items-center gap-2">
                    <TrendUp size={16} />
                    Common Praises
                  </h4>
                  <div className="space-y-1">
                    {analytics?.common_praises?.slice(0, 3).map((item) => (
                      <div key={item.praise} className="text-sm text-[#57534E] truncate">
                        • {item.praise} ({item.count})
                      </div>
                    ))}
                    {(!analytics?.common_praises || analytics.common_praises.length === 0) && (
                      <div className="text-sm text-[#57534E]">Run analysis to see praises</div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </TabsContent>

          {/* Competitors Tab */}
          <TabsContent value="competitors" className="space-y-4">
            {compIntel && (
              <div className="bg-white border border-stone-200 rounded-md p-4" data-testid="competitor-intel-card">
                <div className="flex items-center justify-between mb-1">
                  <h4 className="font-medium text-[#1C1917] flex items-center gap-2"><Lightning size={18} className="text-[#C05A44]" /> {t("ro.comp_intel")}</h4>
                  <Badge className={compIntel.mode === "live" ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"}>{compIntel.mode === "live" ? "LIVE" : "SIMULATED"}</Badge>
                </div>
                <p className="text-[11px] text-stone-600 mb-3" data-testid="competitor-intel-insight">{compIntel.insight}</p>
                <div className="grid md:grid-cols-2 gap-3">
                  <div className="border border-red-100 bg-red-50/40 rounded p-3" data-testid="they-have-we-dont">
                    <div className="text-xs font-semibold text-red-800 mb-1">{t("ro.they_have")}</div>
                    {compIntel.they_have_we_dont.length === 0 && <p className="text-[11px] text-stone-400">Fark bulunamadı.</p>}
                    {compIntel.they_have_we_dont.slice(0, 6).map(x => (
                      <div key={x.item} className="text-[11px] mb-2 border-b border-red-100 pb-1.5" data-testid={`gap-item-${x.item.replace(/\s+/g, "-")}`}>
                        <span className="capitalize font-semibold">{x.item}</span> <span className="text-stone-400">({x.competitors} rakip)</span>
                        <div className="text-stone-500">{x.action}</div>
                        <div className="flex gap-1.5 mt-1">
                          <button onClick={() => actGap(x.item, "add_amenity")} data-testid={`gap-add-amenity-${x.item.replace(/\s+/g, "-")}`}
                            className="px-2 py-0.5 rounded bg-emerald-700 text-white text-[10px] hover:bg-emerald-800">Zaten var → olanak listesine ekle</button>
                          <button onClick={() => actGap(x.item, "feasibility_task")} data-testid={`gap-feasibility-${x.item.replace(/\s+/g, "-")}`}
                            className="px-2 py-0.5 rounded bg-stone-800 text-white text-[10px] hover:bg-stone-900">Fizibilite görevi aç</button>
                        </div>
                      </div>
                    ))}
                    {compIntel.their_strength_our_weakness?.length > 0 && <p className="text-[11px] text-red-700 mt-1">Onların gücü / bizim zayıflığımız: {compIntel.their_strength_our_weakness.join(", ")}</p>}
                  </div>
                  <div className="space-y-2">
                    {compIntel.competitors.map(c => (
                      <div key={c.name} className="border border-stone-100 rounded p-2 text-[11px]" data-testid={`competitor-intel-${c.name}`}>
                        <div className="font-semibold text-stone-800">{c.name} <span className="text-stone-400">· {c.reviews_analyzed} yorum</span></div>
                        <div><span className="text-emerald-700">Güçlü:</span> {c.strengths.join(", ") || "—"}</div>
                        <div><span className="text-red-600">Zayıf:</span> {c.weaknesses.join(", ") || "—"}</div>
                        <div><span className="text-stone-500">Övülen olanaklar:</span> {c.amenities_praised.join(", ") || "—"}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
            {topicCompare && (
              <div className="bg-white border border-stone-200 rounded-md p-4" data-testid="topic-compare-card">
                <div className="flex items-center justify-between mb-1">
                  <h4 className="font-medium text-[#1C1917] flex items-center gap-2"><Tag size={18} className="text-[#3E5245]" /> {t("ro.topic_benchmark")} ({topicCompare.days}d)</h4>
                  <Badge className={topicCompare.mode === "live" ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"}>{topicCompare.mode === "live" ? "LIVE (Places API)" : "SIMULATED"}</Badge>
                </div>
                <p className="text-[11px] text-stone-500 mb-3" data-testid="topic-compare-insight">{topicCompare.insight}</p>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead><tr className="text-stone-400 text-left">
                      <th className="py-1">Topic</th><th className="py-1 text-right">Our Business</th>
                      {topicCompare.competitors.map(c => <th key={c.name} className="py-1 text-right">{c.name}</th>)}
                      <th className="py-1 text-right">Gap</th>
                    </tr></thead>
                    <tbody>
                      {topicCompare.rows.map(r => (
                        <tr key={r.topic} className="border-t border-stone-100" data-testid={`topic-row-${r.topic}`}>
                          <td className="py-1.5 capitalize font-medium">{r.topic} <span className="text-stone-400">({r.ours_n})</span></td>
                          <td className="py-1.5 text-right font-semibold">{r.ours ?? "—"}</td>
                          {topicCompare.competitors.map(c => <td key={c.name} className="py-1.5 text-right text-stone-600">{r.competitors[c.name] ?? "—"}</td>)}
                          <td className={`py-1.5 text-right font-bold ${r.gap == null ? "text-stone-400" : r.gap <= -0.3 ? "text-red-600" : r.gap >= 0.3 ? "text-emerald-700" : "text-stone-600"}`}>{r.gap == null ? "—" : (r.gap > 0 ? "+" : "") + r.gap}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
            {/* Your Ranking */}
            {benchmark && (
              <div className="bg-[#E8EDE7] border border-[#D5DDD3] rounded-md p-4">
                <h4 className="font-medium text-[#1C1917] mb-3 flex items-center gap-2">
                  <Trophy size={18} className="text-[#D4A373]" />
                  Your Competitive Position
                </h4>
                <div className="grid grid-cols-3 gap-4">
                  <div className="text-center">
                    <div className="text-3xl font-bold text-[#3E5245]">#{benchmark.ranking?.rating_rank}</div>
                    <div className="text-sm text-[#57534E]">Rating Rank</div>
                    <div className="text-xs text-[#57534E]">of {benchmark.ranking?.total_competitors}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-3xl font-bold text-[#3E5245]">{benchmark.your_hotel?.avg_rating}/5</div>
                    <div className="text-sm text-[#57534E]">Your Rating</div>
                  </div>
                  <div className="text-center">
                    <div className="text-3xl font-bold text-[#3E5245]">{benchmark.your_hotel?.response_rate}%</div>
                    <div className="text-sm text-[#57534E]">Response Rate</div>
                  </div>
                </div>
              </div>
            )}

            {/* Competitor List */}
            <div className="bg-white border border-stone-200 rounded-md p-4">
              <h4 className="font-medium text-[#1C1917] mb-3 flex items-center gap-2">
                <Users size={18} className="text-[#3E5245]" />
                Competitor Comparison
              </h4>
              <div className="space-y-2">
                {/* Your Hotel Row */}
                <div className="flex items-center justify-between p-3 bg-[#E8EDE7] rounded-md border-2 border-[#3E5245]">
                  <div className="flex items-center gap-2">
                    <Buildings size={20} className="text-[#3E5245]" />
                    <span className="font-medium">Your Hotel</span>
                    <Badge className="bg-[#3E5245] text-white">You</Badge>
                  </div>
                  <div className="flex items-center gap-6">
                    <div className="text-center">
                      <div className="font-semibold">{benchmark?.your_hotel?.avg_rating}/5</div>
                      <div className="text-xs text-[#57534E]">Rating</div>
                    </div>
                    <div className="text-center">
                      <div className="font-semibold">{benchmark?.your_hotel?.total_reviews}</div>
                      <div className="text-xs text-[#57534E]">Reviews</div>
                    </div>
                    <div className="text-center">
                      <div className="font-semibold">{benchmark?.your_hotel?.response_rate}%</div>
                      <div className="text-xs text-[#57534E]">Response</div>
                    </div>
                  </div>
                </div>

                {/* Competitors */}
                {competitors.map((comp) => (
                  <div key={comp.id} className="flex items-center justify-between p-3 bg-[#FAF9F6] rounded-md">
                    <div className="flex items-center gap-2">
                      <Target size={20} className="text-[#57534E]" />
                      <span className="font-medium">{comp.name}</span>
                    </div>
                    <div className="flex items-center gap-6">
                      <div className="text-center">
                        <div className="font-semibold">{comp.avg_rating}/5</div>
                        <div className="text-xs text-[#57534E]">Rating</div>
                      </div>
                      <div className="text-center">
                        <div className="font-semibold">{comp.total_reviews}</div>
                        <div className="text-xs text-[#57534E]">Reviews</div>
                      </div>
                      <div className="text-center">
                        <div className="font-semibold">{comp.response_rate}%</div>
                        <div className="text-xs text-[#57534E]">Response</div>
                      </div>
                      <button
                        onClick={() => deleteCompetitor(comp.id)}
                        className="p-1 hover:bg-red-50 rounded transition-colors"
                        data-testid={`delete-competitor-${comp.id}`}
                      >
                        <Trash size={16} className="text-[#C05A44]" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>

              {/* Add Competitor */}
              <div className="mt-4 pt-4 border-t border-stone-200">
                <h5 className="text-sm font-medium text-[#1C1917] mb-2">Add Competitor</h5>
                <div className="flex gap-2">
                  <Input
                    placeholder="Hotel name"
                    value={newCompetitor.name}
                    onChange={(e) => setNewCompetitor(prev => ({ ...prev, name: e.target.value }))}
                    className="flex-1"
                    data-testid="competitor-name-input"
                  />
                  <Input
                    type="number"
                    placeholder="Rating"
                    value={newCompetitor.avg_rating}
                    onChange={(e) => setNewCompetitor(prev => ({ ...prev, avg_rating: parseFloat(e.target.value) }))}
                    className="w-20"
                    step="0.1"
                    min="1"
                    max="5"
                  />
                  <Input
                    type="number"
                    placeholder="Reviews"
                    value={newCompetitor.total_reviews}
                    onChange={(e) => setNewCompetitor(prev => ({ ...prev, total_reviews: parseInt(e.target.value) }))}
                    className="w-24"
                  />
                  <Input
                    type="number"
                    placeholder="Resp %"
                    value={newCompetitor.response_rate}
                    onChange={(e) => setNewCompetitor(prev => ({ ...prev, response_rate: parseFloat(e.target.value) }))}
                    className="w-20"
                  />
                  <button
                    onClick={addCompetitor}
                    disabled={!newCompetitor.name}
                    className="bg-[#3E5245] text-white px-3 py-2 rounded-md hover:bg-[#2A3B30] transition-colors disabled:opacity-50"
                    data-testid="add-competitor-btn"
                  >
                    <Plus size={16} />
                  </button>
                </div>
              </div>
            </div>
          </TabsContent>
        </Tabs>
      )}
    </DialogContent>
  );
};



export { AnalyticsPanel };
