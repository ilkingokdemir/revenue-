/**
 * AI Yanıt Robotu — öğrenen yanıt asistanı.
 * Yorum + şikayet gelen kutusu, AI taslak, düzenle & gönder,
 * her düzenlemeden öğrenilen kurallar.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Bot, RefreshCw, Sparkles, Send, Loader2, Star, ShieldAlert,
  GraduationCap, Trash2, Plus, Inbox, CheckCircle2, Pencil, Layers, TrendingUp,
  ClipboardPaste, Copy, Settings2, ImageIcon,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const StatBox = ({ label, value, sub, testId }) => (
  <div data-testid={testId} className="bg-stone-900 border border-stone-800 rounded-xl p-4">
    <p className="text-xs uppercase tracking-wider text-stone-500">{label}</p>
    <p className="text-2xl font-semibold text-stone-100 mt-1">{value}</p>
    {sub && <p className="text-[11px] text-stone-500 mt-0.5">{sub}</p>}
  </div>
);

export default function AIReplyRobotPanel({ propertyId, hotelName = "" }) {
  const [tab, setTab] = useState("inbox");
  const [inbox, setInbox] = useState({ items: [], review_count: 0, complaint_count: 0 });
  const [lessons, setLessons] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(null);
  const [draft, setDraft] = useState(null);
  const [draftText, setDraftText] = useState("");
  const [drafting, setDrafting] = useState(false);
  const [sending, setSending] = useState(false);
  const [newRule, setNewRule] = useState("");
  const [bulkDrafting, setBulkDrafting] = useState(false);
  const [report, setReport] = useState(null);
  const [pasteText, setPasteText] = useState("");
  const [pasteKind, setPasteKind] = useState("review");
  const [pasteGuest, setPasteGuest] = useState("");
  const [filter, setFilter] = useState("all");
  const [qualityWarning, setQualityWarning] = useState(null);
  const [config, setConfig] = useState(null);
  const [savingConfig, setSavingConfig] = useState(false);
  const [sources, setSources] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const [bench, setBench] = useState(null);
  const [benchComps, setBenchComps] = useState([]);
  const [scanning, setScanning] = useState(false);
  const [portfolio, setPortfolio] = useState(null);
  const [catData, setCatData] = useState(null);
  const [categorizing, setCategorizing] = useState(false);
  const [qrUrl, setQrUrl] = useState(null);
  const [insight, setInsight] = useState(null);
  const [insightLoading, setInsightLoading] = useState(false);
  const [voicePlaying, setVoicePlaying] = useState(false);
  const [winbackStats, setWinbackStats] = useState(null);
  const [winbackOffers, setWinbackOffers] = useState([]);
  const [insightTasks, setInsightTasks] = useState([]);
  const [spy, setSpy] = useState(null);
  const [spying, setSpying] = useState(false);
  const [socialDrafts, setSocialDrafts] = useState([]);
  const [editingDraft, setEditingDraft] = useState(null);
  const [editDraftText, setEditDraftText] = useState("");
  const [imagingDraft, setImagingDraft] = useState(null);
  const [imageStyle, setImageStyle] = useState("sicak");
  const [packagingDraft, setPackagingDraft] = useState(null);
  const [publishDates, setPublishDates] = useState({});
  const [socialCalendar, setSocialCalendar] = useState([]);
  const [previewDraft, setPreviewDraft] = useState(null);
  const [surveyDrafting, setSurveyDrafting] = useState(false);
  const [archiveProperty, setArchiveProperty] = useState("");
  const [propList, setPropList] = useState([]);
  const archivePid = archiveProperty || propertyId;
  const [pendingDrafts, setPendingDrafts] = useState([]);
  const [refineNotes, setRefineNotes] = useState({});
  const [refiningDraft, setRefiningDraft] = useState(null);
  const [bulkApproving, setBulkApproving] = useState(false);

  const runInsight = async () => {
    setInsightLoading(true);
    try {
      const { data } = await axios.post(`${API}/ai-agent/insight-report/${propertyId}`);
      setInsight(data);
      toast.success("İçgörü raporu hazır");
    } catch (e) { toast.error(e?.response?.data?.detail || "Rapor oluşturulamadı"); }
    setInsightLoading(false);
  };

  const playVoice = async () => {
    setVoicePlaying(true);
    try {
      const { data } = await axios.get(`${API}/ai-agent/voice-summary/${propertyId}`);
      if (data.audio_base64) {
        const audio = new Audio(`data:audio/mp3;base64,${data.audio_base64}`);
        audio.onended = () => setVoicePlaying(false);
        await audio.play();
        toast.success("Sesli özet çalıyor");
      } else {
        toast.error("Ses üretilemedi");
        setVoicePlaying(false);
      }
    } catch { toast.error("Sesli özet alınamadı"); setVoicePlaying(false); }
  };

  const loadBench = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/reputation/benchmark/${propertyId}`);
      setBench(data);
      setBenchComps(data.competitors.length ? data.competitors : [{ name: "", place_id: "" }]);
    } catch { /* silent */ }
  }, [propertyId]);

  const saveComps = async () => {
    try {
      await axios.put(`${API}/reputation/config/${propertyId}`, { competitors: benchComps.filter(c => c.name.trim()) });
      toast.success("Rakipler kaydedildi");
    } catch { toast.error("Kaydedilemedi"); }
  };

  const scanBench = async () => {
    setScanning(true);
    try {
      await saveComps();
      await axios.post(`${API}/reputation/scan/${propertyId}`);
      toast.success("İtibar taraması tamamlandı");
      loadBench();
    } catch { toast.error("Tarama başarısız"); }
    setScanning(false);
  };

  const runCategorize = async () => {
    setCategorizing(true);
    try {
      const { data } = await axios.post(`${API}/ai-agent/categorize/${propertyId}`);
      toast.success(`${data.categorized} yorum kategorilere puanlandı`);
      const { data: c } = await axios.get(`${API}/ai-agent/categories/${propertyId}`);
      setCatData(c);
    } catch { toast.error("Analiz başarısız"); }
    setCategorizing(false);
  };

  const loadConfig = useCallback(async () => {
    if (!propertyId) return;
    try {
      const [{ data: c }, { data: s }] = await Promise.all([
        axios.get(`${API}/ai-agent/config/${propertyId}`),
        axios.get(`${API}/review-sources/${propertyId}`),
      ]);
      setConfig(c); setSources(s);
    } catch { /* silent */ }
  }, [propertyId]);

  const saveSources = async () => {
    try {
      const { data } = await axios.put(`${API}/review-sources/${propertyId}`, sources);
      setSources(data);
      toast.success("Yorum kaynakları kaydedildi");
    } catch { toast.error("Kaydedilemedi"); }
  };

  const syncNow = async () => {
    setSyncing(true);
    try {
      const { data } = await axios.post(`${API}/review-sources/${propertyId}/sync-now`);
      toast.success(`Senkron tamamlandı — ${data.total_new} yeni yorum eklendi`);
      loadConfig(); load();
    } catch { toast.error("Senkron başarısız"); }
    setSyncing(false);
  };

  const saveConfig = async () => {
    setSavingConfig(true);
    try {
      const { data } = await axios.put(`${API}/ai-agent/config/${propertyId}`, config);
      setConfig(data);
      toast.success("Robot ayarları kaydedildi");
    } catch { toast.error("Ayarlar kaydedilemedi"); }
    setSavingConfig(false);
  };

  const load = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const [i, l, s] = await Promise.all([
        axios.get(`${API}/ai-agent/inbox/${propertyId}`),
        axios.get(`${API}/ai-agent/lessons/${propertyId}`),
        axios.get(`${API}/ai-agent/stats/${propertyId}`),
      ]);
      setInbox(i.data); setLessons(l.data.items || []); setStats(s.data);
    } catch { toast.error("AI robot verileri yüklenemedi"); }
    setLoading(false);
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setSelected(null); setDraft(null); setDraftText(""); setReport(null); }, [propertyId]);

  useEffect(() => {
    if (tab === "report" && propertyId) {
      axios.get(`${API}/ai-agent/report/${propertyId}`)
        .then(({ data }) => setReport(data))
        .catch(() => toast.error("Rapor yüklenemedi"));
    }
    if (tab === "settings" && propertyId) {
      loadConfig();
      axios.get(`${API}/surveys/qr-image/${propertyId}`, { responseType: "blob" })
        .then((r) => setQrUrl(URL.createObjectURL(r.data))).catch(() => {});
    }
    if (tab === "benchmark" && propertyId) loadBench();
    if (tab === "portfolio") {
      axios.get(`${API}/ai-agent/portfolio-report`).then(({ data }) => setPortfolio(data)).catch(() => {});
    }
    if (tab === "report" && propertyId) {
      axios.get(`${API}/ai-agent/categories/${propertyId}`).then(({ data }) => setCatData(data)).catch(() => {});
      axios.get(`${API}/ai-agent/insight-report/${propertyId}/latest`).then(({ data }) => data?.id && setInsight(data)).catch(() => {});
      axios.get(`${API}/ai-agent/insight-tasks/${propertyId}`).then(({ data }) => setInsightTasks(data.items || [])).catch(() => {});
      axios.get(`${API}/ai-agent/winback-stats/${propertyId}`).then(({ data }) => setWinbackStats(data)).catch(() => {});
      axios.get(`${API}/ai-agent/winback-offers/${propertyId}`).then(({ data }) => setWinbackOffers(data.items || [])).catch(() => {});
    }
    if (tab === "benchmark" && propertyId) {
      axios.get(`${API}/reputation/competitor-spy/${propertyId}/latest`).then(({ data }) => data?.id && setSpy(data)).catch(() => {});
      axios.get(`${API}/properties`).then(({ data }) => setPropList(Array.isArray(data) ? data : data.items || data.properties || [])).catch(() => {});
      axios.get(`${API}/reputation/social-drafts-pending`).then(({ data }) => setPendingDrafts(data.items || [])).catch(() => {});
    }
    if (tab === "benchmark" && archivePid) {
      axios.get(`${API}/reputation/social-drafts/${archivePid}`).then(({ data }) => setSocialDrafts(data.items || [])).catch(() => {});
      axios.get(`${API}/reputation/social-calendar/${archivePid}`).then(({ data }) => setSocialCalendar(data.items || [])).catch(() => {});
    }
  }, [tab, propertyId, archivePid, loadConfig, loadBench]);

  const bulkDraft = async () => {
    setBulkDrafting(true);
    try {
      const { data } = await axios.post(`${API}/ai-agent/batch-draft/${propertyId}`, {});
      toast.success(`${data.drafted_count} taslak hazırlandı${data.skipped_existing ? ` (${data.skipped_existing} zaten taslaklı)` : ""} — onay kuyruğunda`);
      load();
    } catch { toast.error("Toplu taslak başarısız"); }
    setBulkDrafting(false);
  };

  const generateDraft = async (item) => {
    setDrafting(true);
    try {
      const { data } = await axios.post(`${API}/ai-agent/draft`, {
        property_id: propertyId, source_type: item.source_type, source_id: item.source_id,
      });
      setDraft(data); setDraftText(data.ai_text);
      toast.success(data.lessons_applied > 0
        ? `Taslak hazır — ${data.lessons_applied} öğrenilmiş kural uygulandı`
        : "Taslak hazır");
    } catch { toast.error("Taslak oluşturulamadı"); }
    setDrafting(false);
  };

  const generatePasteDraft = async () => {
    if (!pasteText.trim()) { toast.error("Önce müşteri metnini yapıştırın"); return; }
    setDrafting(true);
    try {
      const { data } = await axios.post(`${API}/ai-agent/draft/paste`, {
        property_id: propertyId, kind: pasteKind,
        text: pasteText.trim(), guest_name: pasteGuest.trim() || undefined,
      });
      setDraft(data); setDraftText(data.ai_text);
      toast.success(data.lessons_applied > 0
        ? `Yanıt hazır — ${data.lessons_applied} öğrenilmiş kural uygulandı`
        : "Yanıt hazır");
    } catch { toast.error("Yanıt oluşturulamadı"); }
    setDrafting(false);
  };

  const copyDraft = async () => {
    try {
      await navigator.clipboard.writeText(draftText);
      toast.success("Yanıt panoya kopyalandı");
    } catch { toast.error("Kopyalanamadı"); }
  };

  const openPasteMode = () => {
    setSelected({ manual: true });
    setDraft(null); setDraftText(""); setPasteText(""); setPasteGuest(""); setQualityWarning(null);
    setTab("inbox");
  };

  const QualityWarningBox = () => qualityWarning ? (
    <div data-testid="ai-robot-quality-warning" className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/40 space-y-2">
      <p className="text-xs font-medium text-rose-300">
        ⚠ Kalite skoru düşük: {qualityWarning.score}/100
      </p>
      <p className="text-[11px] text-stone-300">{qualityWarning.verdict}</p>
      <div className="flex gap-2">
        <button data-testid="ai-robot-warning-edit-btn" onClick={() => setQualityWarning(null)}
          className="flex-1 px-3 py-1.5 rounded-lg bg-stone-800 hover:bg-stone-700 border border-stone-700 text-xs text-stone-100">
          Düzenlemeye Devam
        </button>
        <button data-testid="ai-robot-warning-send-btn" onClick={() => sendResponse(true)}
          className="flex-1 px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-xs text-white">
          Yine de Gönder
        </button>
      </div>
    </div>
  ) : null;

  const sendResponse = async (force = false) => {
    if (!draft) return;
    setSending(true);
    if (!force) {
      try {
        const { data: qc } = await axios.post(`${API}/ai-agent/quality-check`, {
          draft_id: draft.id, final_text: draftText,
        });
        if (qc.warn) { setQualityWarning(qc); setSending(false); return; }
      } catch { /* skor alınamazsa gönderime engel olma */ }
    }
    setQualityWarning(null);
    try {
      const { data } = await axios.post(`${API}/ai-agent/send/${draft.id}`, { final_text: draftText });
      if (data.google_queued) {
        toast.info("Yanıt Google yayın kuyruğuna eklendi (API onayı bekleniyor)");
      }
      if (selected?.manual) {
        try { await navigator.clipboard.writeText(draftText); } catch { /* silent */ }
        toast.success(data.was_edited && data.learned_count > 0
          ? `Yanıt panoya kopyalandı — robot ${data.learned_count} yeni kural öğrendi 🎓`
          : "Yanıt onaylandı ve panoya kopyalandı — platforma yapıştırabilirsiniz");
      } else if (data.was_edited && data.learned_count > 0) {
        toast.success(`Yanıt gönderildi — robot ${data.learned_count} yeni kural öğrendi 🎓`);
      } else if (data.was_edited) {
        toast.success("Yanıt gönderildi — düzenlemeniz örnek olarak kaydedildi");
      } else {
        toast.success("Yanıt onaylandı ve gönderildi");
      }
      setSelected(null); setDraft(null); setDraftText("");
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gönderilemedi"); }
    setSending(false);
  };

  const addRule = async () => {
    if (!newRule.trim()) return;
    try {
      await axios.post(`${API}/ai-agent/lessons/${propertyId}`, { rule: newRule.trim() });
      setNewRule(""); toast.success("Kural eklendi"); load();
    } catch { toast.error("Kural eklenemedi"); }
  };

  const deleteRule = async (id) => {
    try {
      await axios.delete(`${API}/ai-agent/lessons/${propertyId}/${id}`);
      toast.success("Kural kaldırıldı"); load();
    } catch { toast.error("Silinemedi"); }
  };

  const openItem = async (item) => {
    setSelected(item); setDraft(null); setDraftText(item.ai_draft || ""); setQualityWarning(null);
    if (item.ai_draft) {
      try {
        const { data } = await axios.get(`${API}/ai-agent/draft/latest`, {
          params: { source_type: item.source_type, source_id: item.source_id },
        });
        if (data?.id) { setDraft(data); setDraftText(data.ai_text); }
      } catch { /* silent */ }
    }
  };

  return (
    <div className="space-y-6" data-testid="ai-reply-robot-panel">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Bot className="w-6 h-6 text-violet-400" />
            <h2 className="text-2xl font-semibold text-stone-100">AI Yanıt Robotu</h2>
            <span className="px-2 py-0.5 text-[10px] uppercase tracking-wider bg-violet-500/15 text-violet-300 rounded">
              Öğrenen Agent
            </span>
          </div>
          <p className="text-sm text-stone-400 mt-1">
            {hotelName ? `${hotelName} · ` : ""}Yorum ve şikayetlere AI taslak → düzenle → gönder. Her düzenlemeden öğrenir.
          </p>
        </div>
        <div className="flex gap-2">
          <button data-testid="ai-robot-voice-btn" onClick={playVoice} disabled={voicePlaying}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-stone-800 hover:bg-stone-700 disabled:opacity-50 text-sm text-stone-100 border border-stone-700">
            {voicePlaying ? <Loader2 className="w-4 h-4 animate-spin" /> : "🔊"} Sesli Özet
          </button>
          <button data-testid="ai-robot-bulk-draft-btn" onClick={bulkDraft} disabled={bulkDrafting || !inbox.items.length}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-sm text-white">
            {bulkDrafting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Layers className="w-4 h-4" />}
            {bulkDrafting ? "Taslaklar hazırlanıyor…" : "Tümüne Taslak Hazırla"}
          </button>
          <button data-testid="ai-robot-refresh-btn" onClick={load}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-stone-800 hover:bg-stone-700 text-sm text-stone-100 border border-stone-700">
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> Yenile
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <StatBox testId="ai-robot-stat-inbox" label="Bekleyen" value={inbox.count ?? inbox.items.length}
          sub={`${inbox.review_count} yorum · ${inbox.complaint_count} şikayet`} />
        <StatBox testId="ai-robot-stat-sent" label="Gönderilen" value={stats?.sent ?? 0}
          sub={stats?.by_type ? `${stats.by_type.review.sent} yorum · ${stats.by_type.complaint.sent} şikayet` : ""} />
        <StatBox testId="ai-robot-stat-approval" label="Onay Oranı" value={`${stats?.approval_rate ?? 0}%`}
          sub={stats?.by_type ? `Yorum %${stats.by_type.review.approval_rate} · Şikayet %${stats.by_type.complaint.approval_rate}` : "Düzenlemesiz onay"} />
        <StatBox testId="ai-robot-stat-edit" label="Düzenleme Oranı" value={`${stats?.edit_rate ?? 0}%`} sub="Öğrenme kaynağı" />
        <StatBox testId="ai-robot-stat-lessons" label="Öğrenilen Kural" value={stats?.lessons ?? 0} />
      </div>

      <div className="flex gap-2 border-b border-stone-800 pb-2">
        <button data-testid="ai-robot-tab-inbox" onClick={() => setTab("inbox")}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm ${tab === "inbox" ? "bg-violet-500/15 text-violet-300" : "text-stone-400 hover:text-stone-200"}`}>
          <Inbox className="w-4 h-4" /> Gelen Kutusu
        </button>
        <button data-testid="ai-robot-tab-lessons" onClick={() => setTab("lessons")}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm ${tab === "lessons" ? "bg-violet-500/15 text-violet-300" : "text-stone-400 hover:text-stone-200"}`}>
          <GraduationCap className="w-4 h-4" /> Robotun Öğrendikleri ({lessons.length})
        </button>
        <button data-testid="ai-robot-tab-report" onClick={() => setTab("report")}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm ${tab === "report" ? "bg-violet-500/15 text-violet-300" : "text-stone-400 hover:text-stone-200"}`}>
          <TrendingUp className="w-4 h-4" /> Öğrenme Raporu
        </button>
        <button data-testid="ai-robot-tab-benchmark" onClick={() => setTab("benchmark")}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm ${tab === "benchmark" ? "bg-violet-500/15 text-violet-300" : "text-stone-400 hover:text-stone-200"}`}>
          <Star className="w-4 h-4" /> Benchmark
        </button>
        <button data-testid="ai-robot-tab-portfolio" onClick={() => setTab("portfolio")}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm ${tab === "portfolio" ? "bg-violet-500/15 text-violet-300" : "text-stone-400 hover:text-stone-200"}`}>
          <Layers className="w-4 h-4" /> Portföy
        </button>
        <button data-testid="ai-robot-tab-settings" onClick={() => setTab("settings")}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm ${tab === "settings" ? "bg-violet-500/15 text-violet-300" : "text-stone-400 hover:text-stone-200"}`}>
          <Settings2 className="w-4 h-4" /> Ayarlar
        </button>
      </div>

      {tab === "inbox" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="space-y-2 max-h-[70vh] overflow-y-auto pr-1" data-testid="ai-robot-inbox-list">
            <div className="flex gap-1.5 sticky top-0 bg-stone-950/90 backdrop-blur-sm z-10 pb-1">
              {[
                { id: "all", label: `Tümü (${inbox.count ?? inbox.items.length})` },
                { id: "review", label: `★ Yorumlar (${inbox.review_count ?? 0})` },
                { id: "complaint", label: `⚠ Şikayetler (${inbox.complaint_count ?? 0})` },
              ].map((f) => (
                <button key={f.id} data-testid={`ai-robot-filter-${f.id}`} onClick={() => setFilter(f.id)}
                  className={`px-3 py-1.5 rounded-full text-xs border transition-colors ${filter === f.id
                    ? (f.id === "complaint" ? "border-rose-500/60 bg-rose-500/10 text-rose-300"
                      : f.id === "review" ? "border-amber-500/60 bg-amber-500/10 text-amber-300"
                      : "border-violet-500/60 bg-violet-500/10 text-violet-300")
                    : "border-stone-700 text-stone-400 hover:text-stone-200"}`}>
                  {f.label}
                </button>
              ))}
            </div>
            <button data-testid="ai-robot-paste-open-btn" onClick={openPasteMode}
              className={`w-full flex items-center gap-2 p-3 rounded-xl border border-dashed transition-colors text-sm ${selected?.manual ? "border-violet-500/60 bg-violet-500/10 text-violet-300" : "border-stone-700 text-stone-400 hover:border-violet-500/50 hover:text-violet-300"}`}>
              <ClipboardPaste className="w-4 h-4" />
              Dışarıdan Metin Yapıştır — Google, Booking, e-posta yorumu/şikayeti
            </button>
            {loading && <div className="p-6 text-center text-stone-400 text-sm"><Loader2 className="w-5 h-5 mx-auto animate-spin mb-2" />Yükleniyor…</div>}
            {!loading && inbox.items.filter((i) => filter === "all" || i.source_type === filter).length === 0 && (
              <div className="p-8 text-center text-stone-500 text-sm border border-dashed border-stone-800 rounded-xl">
                <CheckCircle2 className="w-6 h-6 mx-auto mb-2 text-emerald-400" />
                {filter === "complaint" ? "Tüm şikayetler yanıtlandı 🎉" : filter === "review" ? "Tüm yorumlar yanıtlandı 🎉" : "Tüm yorum ve şikayetler yanıtlandı 🎉"}
              </div>
            )}
            {inbox.items.filter((i) => filter === "all" || i.source_type === filter).map((it) => (
              <button key={`${it.source_type}-${it.source_id}`}
                data-testid={`ai-robot-inbox-item-${it.source_id}`}
                onClick={() => openItem(it)}
                className={`w-full text-left p-3 rounded-xl border transition-colors ${selected?.source_id === it.source_id ? "border-violet-500/60 bg-violet-500/10" : "border-stone-800 bg-stone-900 hover:border-stone-700"}`}>
                <div className="flex items-center gap-2 mb-1">
                  {it.source_type === "review"
                    ? <Star className="w-4 h-4 text-amber-400" />
                    : <ShieldAlert className="w-4 h-4 text-rose-400" />}
                  <span className="text-sm font-medium text-stone-100">{it.guest_name}</span>
                  <span className="text-[11px] text-stone-500">{it.title}</span>
                  <span className={`ml-auto px-1.5 py-0.5 text-[10px] rounded ${it.source_type === "review" ? "bg-amber-500/15 text-amber-300" : "bg-rose-500/15 text-rose-300"}`}>
                    {it.source_type === "review" ? "Yorum" : "Şikayet"}
                  </span>
                  {it.sla_breached && (
                    <span data-testid={`sla-badge-${it.source_id}`} className="px-1.5 py-0.5 text-[10px] rounded bg-red-600/25 text-red-300 font-semibold">
                      ⏰ SLA aşıldı
                    </span>
                  )}
                </div>
                <p className="text-xs text-stone-400 line-clamp-2">{it.text}</p>
                {it.ai_draft && <p className="text-[10px] text-violet-400 mt-1">✦ AI taslağı mevcut</p>}
              </button>
            ))}
          </div>

          <div className="bg-stone-900 border border-stone-800 rounded-xl p-4 h-fit sticky top-4" data-testid="ai-robot-draft-panel">
            {!selected ? (
              <div className="p-8 text-center text-stone-500 text-sm">
                <Bot className="w-8 h-8 mx-auto mb-2 text-stone-600" />
                Yanıtlamak için soldan bir yorum veya şikayet seçin — ya da harici metin yapıştırın
              </div>
            ) : selected.manual ? (
              <div className="space-y-3" data-testid="ai-robot-paste-form">
                <p className="text-sm font-medium text-stone-200 flex items-center gap-2">
                  <ClipboardPaste className="w-4 h-4 text-violet-400" /> Müşteri metnini yapıştırın
                </p>
                <div className="flex gap-2">
                  <button data-testid="ai-robot-paste-kind-review" onClick={() => setPasteKind("review")}
                    className={`flex-1 px-3 py-1.5 rounded-lg text-xs border ${pasteKind === "review" ? "border-amber-500/60 bg-amber-500/10 text-amber-300" : "border-stone-700 text-stone-400"}`}>
                    ★ Yorum
                  </button>
                  <button data-testid="ai-robot-paste-kind-complaint" onClick={() => setPasteKind("complaint")}
                    className={`flex-1 px-3 py-1.5 rounded-lg text-xs border ${pasteKind === "complaint" ? "border-rose-500/60 bg-rose-500/10 text-rose-300" : "border-stone-700 text-stone-400"}`}>
                    ⚠ Şikayet
                  </button>
                </div>
                <input data-testid="ai-robot-paste-guest-input" value={pasteGuest}
                  onChange={(e) => setPasteGuest(e.target.value)}
                  placeholder="Misafir adı (opsiyonel)"
                  className="w-full px-3 py-2 rounded-lg bg-stone-950 border border-stone-700 text-sm text-stone-100 focus:border-violet-500 outline-none" />
                <textarea data-testid="ai-robot-paste-textarea" value={pasteText}
                  onChange={(e) => setPasteText(e.target.value)} rows={5}
                  placeholder="Müşterinin yorumunu veya şikayet metnini buraya yapıştırın…"
                  className="w-full p-3 rounded-lg bg-stone-950 border border-stone-700 text-sm text-stone-100 focus:border-violet-500 outline-none resize-y" />
                <button data-testid="ai-robot-paste-generate-btn" onClick={generatePasteDraft}
                  disabled={drafting || !pasteText.trim()}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-sm font-medium text-white">
                  {drafting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                  {drafting ? "Robot yazıyor…" : draft ? "Yeniden Oluştur" : "AI Yanıt Oluştur"}
                </button>
                {draft && (
                  <>
                    <textarea data-testid="ai-robot-draft-textarea" value={draftText}
                      onChange={(e) => setDraftText(e.target.value)} rows={8}
                      className="w-full p-3 rounded-lg bg-stone-950 border border-stone-700 text-sm text-stone-100 focus:border-violet-500 outline-none resize-y" />
                    <QualityWarningBox />
                    <div className="flex gap-2">
                      <button data-testid="ai-robot-copy-btn" onClick={copyDraft}
                        className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-stone-800 hover:bg-stone-700 border border-stone-700 text-sm text-stone-100">
                        <Copy className="w-4 h-4" /> Kopyala
                      </button>
                      <button data-testid="ai-robot-send-btn" onClick={() => sendResponse()}
                        disabled={sending || !draftText.trim()}
                        className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-sm font-medium text-white">
                        {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                        {sending ? "Kaydediliyor…" : "Onayla & Kopyala"}
                      </button>
                    </div>
                    <p className="text-[10px] text-stone-500 text-center">
                      Onayladığınızda yanıt panoya kopyalanır — Google/Booking'e yapıştırın. Düzenlemeleriniz robota öğretilir.
                    </p>
                  </>
                )}
              </div>
            ) : (
              <div className="space-y-3">
                <div className="p-3 rounded-lg bg-stone-950 border border-stone-800">
                  <div className="flex items-center justify-between mb-1">
                    <p className="text-xs text-stone-500">{selected.source_type === "review" ? "Misafir Yorumu" : "Misafir Şikayeti"} — {selected.guest_name}</p>
                    {selected.source_type === "complaint" && (
                      <button data-testid="ai-robot-tracking-link-btn"
                        onClick={async () => {
                          try {
                            const { data } = await axios.get(`${API}/service-recovery/${selected.source_id}/tracking-link`);
                            await navigator.clipboard.writeText(data.url);
                            toast.success("Misafir takip linki panoya kopyalandı");
                          } catch { toast.error("Link alınamadı"); }
                        }}
                        className="px-2 py-0.5 rounded text-[10px] bg-stone-800 hover:bg-stone-700 border border-stone-700 text-stone-300">
                        🔗 Takip Linki
                      </button>
                    )}
                  </div>
                  <p className="text-sm text-stone-200 whitespace-pre-wrap">{selected.text}</p>
                </div>
                <button data-testid="ai-robot-generate-btn" onClick={() => generateDraft(selected)} disabled={drafting}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-sm font-medium text-white">
                  {drafting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                  {drafting ? "Robot yazıyor…" : draft ? "Yeniden Oluştur" : "AI Taslak Oluştur"}
                </button>
                {(selected.source_type === "complaint" || (selected.rating && selected.rating <= 3)) && (
                  <button data-testid="ai-robot-winback-btn"
                    onClick={async () => {
                      try {
                        toast.info("Geri kazanım teklifi hazırlanıyor…");
                        const { data } = await axios.post(`${API}/ai-agent/winback`, {
                          property_id: propertyId, source_type: selected.source_type,
                          source_id: selected.source_id, discount_pct: 15,
                        });
                        await navigator.clipboard.writeText(data.message);
                        toast.success(data.email_queued
                          ? `%${data.discount_pct} teklif e-posta kuyruğuna eklendi ve panoya kopyalandı`
                          : `%${data.discount_pct} teklif panoya kopyalandı (kod: ${data.code})`);
                      } catch { toast.error("Teklif oluşturulamadı"); }
                    }}
                    className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-amber-600/80 hover:bg-amber-500 text-xs font-medium text-white">
                    🎁 %15 Geri Kazanım Teklifi Oluştur
                  </button>
                )}
                {(draft || draftText) && (
                  <>
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <p className="text-xs text-stone-500 flex items-center gap-1"><Pencil className="w-3 h-3" /> Taslağı inceleyin, düzenleyin ve gönderin</p>
                        {draft?.lessons_applied > 0 && (
                          <span className="text-[10px] text-violet-400">{draft.lessons_applied} kural uygulandı</span>
                        )}
                      </div>
                      <textarea data-testid="ai-robot-draft-textarea" value={draftText}
                        onChange={(e) => setDraftText(e.target.value)} rows={8}
                        className="w-full p-3 rounded-lg bg-stone-950 border border-stone-700 text-sm text-stone-100 focus:border-violet-500 outline-none resize-y" />
                    </div>
                    <QualityWarningBox />
                    <button data-testid="ai-robot-send-btn" onClick={() => sendResponse()}
                      disabled={sending || !draft || !draftText.trim()}
                      className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-sm font-medium text-white">
                      {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                      {sending ? "Gönderiliyor…" : "Onayla & Müşteriye Gönder"}
                    </button>
                    <p className="text-[10px] text-stone-500 text-center">
                      Metni değiştirirseniz robot farkı analiz eder ve bir daha aynı hatayı yapmamayı öğrenir.
                    </p>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {tab === "report" && (
        <div className="space-y-4 max-w-4xl" data-testid="ai-robot-report">
          {!report ? (
            <div className="p-8 text-center text-stone-400 text-sm"><Loader2 className="w-5 h-5 mx-auto animate-spin mb-2" />Rapor yükleniyor…</div>
          ) : (
            <>
              <div className="flex items-center justify-between">
                <div />
                <button data-testid="ai-robot-monthly-pdf-btn"
                  onClick={async () => {
                    try {
                      const r = await axios.get(`${API}/ai-agent/monthly-report-pdf/${propertyId}`, { responseType: "blob" });
                      const url = URL.createObjectURL(r.data);
                      const a = document.createElement("a");
                      a.href = url; a.download = `robot-karne-${propertyId}.pdf`; a.click();
                      URL.revokeObjectURL(url);
                      toast.success("Aylık karne indirildi");
                    } catch { toast.error("PDF oluşturulamadı"); }
                  }}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-stone-800 hover:bg-stone-700 border border-stone-700 text-xs text-stone-100">
                  📄 Aylık Karne (PDF)
                </button>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                <StatBox testId="ai-report-sent" label={`Son ${report.weeks} Hafta Gönderim`} value={report.totals.sent} />
                <StatBox testId="ai-report-edited" label="Düzenlenen" value={report.totals.edited} />
                <StatBox testId="ai-report-lessons" label="Öğrenilen Kural" value={report.totals.lessons_learned} />
                <StatBox testId="ai-report-quality" label="Ø Kalite Skoru"
                  value={report.totals.avg_quality !== null && report.totals.avg_quality !== undefined ? `${report.totals.avg_quality}/100` : "—"}
                  sub="AI değerlendirmesi" />
                <StatBox testId="ai-report-trend" label="Onay Oranı Trendi"
                  value={report.totals.trend === null ? "—" : `${report.totals.trend > 0 ? "+" : ""}${report.totals.trend}%`}
                  sub={report.totals.first_week_approval !== null ? `${report.totals.first_week_approval}% → ${report.totals.last_week_approval}%` : "Yeterli veri yok"} />
              </div>
              {winbackStats && (
                <div data-testid="ai-robot-winback-stats" className="bg-stone-900 border border-stone-800 rounded-xl p-4">
                  <p className="text-sm font-medium text-stone-200 mb-3">🎁 Geri Kazanım Takibi</p>
                  <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                    <StatBox testId="winback-total" label="Üretilen Teklif" value={winbackStats.total} />
                    <StatBox testId="winback-queued" label="E-posta Kuyruğunda" value={winbackStats.email_queued} />
                    <StatBox testId="winback-redeemed" label="Kullanılan Kod" value={winbackStats.redeemed} />
                    <StatBox testId="winback-expired" label="Süresi Dolan" value={winbackStats.expired ?? 0} sub="30 gün geçerlilik" />
                    <StatBox testId="winback-rate" label="Dönüşüm Oranı" value={`%${winbackStats.redeem_rate}`} sub="Kod kullanım oranı" />
                  </div>
                  {winbackOffers.length > 0 && (
                    <div className="mt-3 space-y-1.5" data-testid="winback-offer-list">
                      {winbackOffers.map((o) => (
                        <div key={o.id} data-testid={`winback-offer-${o.id}`} className="flex items-center gap-2 p-2 rounded-lg bg-stone-950 border border-stone-800 text-xs">
                          <span className="text-stone-200 font-medium w-28 truncate shrink-0">{o.guest_name}</span>
                          <span className="text-violet-300 shrink-0 font-mono">WELCOME{o.discount_pct}</span>
                          <span className="text-stone-500 flex-1 truncate hidden md:inline">{o.message}</span>
                          <span className="text-stone-600 shrink-0">{(o.created_at || "").slice(0, 10)}</span>
                          {!o.redeemed && !o.expired && o.reminder_sent && (
                            <span data-testid={`winback-reminder-${o.id}`} className="shrink-0 px-1.5 py-0.5 rounded bg-sky-500/15 text-sky-300 text-[10px]">🔔 Hatırlatıldı</span>
                          )}
                          {o.redeemed ? (
                            <span className="shrink-0 px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 text-[10px]">
                              {o.redeemed_via === "reservation" ? "✓ Rezervasyonda kullanıldı (otomatik)" : "✓ Kullanıldı"}
                            </span>
                          ) : o.expired ? (
                            <span data-testid={`winback-expired-${o.id}`} className="shrink-0 px-2 py-0.5 rounded bg-rose-500/15 text-rose-300 text-[10px]">⏱ Süresi doldu</span>
                          ) : (
                            <button data-testid={`winback-redeem-${o.id}`}
                              onClick={async () => {
                                try {
                                  await axios.post(`${API}/ai-agent/winback/${o.id}/redeem`);
                                  setWinbackOffers((prev) => prev.map((x) => x.id === o.id ? { ...x, redeemed: true } : x));
                                  setWinbackStats((prev) => {
                                    const redeemed = (prev?.redeemed || 0) + 1;
                                    return { ...prev, redeemed, redeem_rate: prev?.total ? Math.round(redeemed / prev.total * 1000) / 10 : 0 };
                                  });
                                  toast.success("Kod kullanıldı olarak işaretlendi 🎉");
                                } catch { toast.error("İşaretlenemedi"); }
                              }}
                              className="shrink-0 px-2 py-0.5 rounded text-[10px] bg-emerald-600/80 hover:bg-emerald-500 text-white">
                              Kullanıldı İşaretle
                            </button>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
              {report.gbp_queue_pending > 0 && (
                <div data-testid="ai-report-gbp-queue" className="flex items-center gap-2 p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-xs text-amber-300">
                  <Send className="w-4 h-4 shrink-0" />
                  {report.gbp_queue_pending} yanıt Google yayın kuyruğunda bekliyor (Google Business API onayı sonrası otomatik yayınlanacak)
                </div>
              )}
              <details data-testid="ai-robot-gbp-guide" className="bg-stone-900 border border-stone-800 rounded-xl p-4 text-sm text-stone-300">
                <summary className="cursor-pointer font-medium text-stone-200 select-none">
                  📋 Google Business Profile API Onay Başvurusu — Adım Adım Rehber
                </summary>
                <ol className="mt-3 space-y-2 pl-5 list-decimal text-xs text-stone-400">
                  <li><b className="text-stone-300">Ön koşulları sağlayın:</b> Google Business Profile'ınız en az <b>60 gündür doğrulanmış ve aktif</b> olmalı; otelinizi temsil eden bir web siteniz bulunmalı.</li>
                  <li><b className="text-stone-300">Google Cloud projesi açın:</b> console.cloud.google.com → yeni proje oluşturun ve <b>Proje Numarası</b>'nı not edin.</li>
                  <li><b className="text-stone-300">API erişim başvurusu yapın:</b> Google'ın "GBP API contact form"unu doldurun (developers.google.com/my-business/content/prereqs adresindeki bağlantı). Başvuruyu, işletme profilinde <b>sahip/yönetici</b> olan e-posta ile yapın ve proje numarasını belirtin.</li>
                  <li><b className="text-stone-300">Onayı kontrol edin:</b> APIs &amp; Services → Quotas'ta kota <b>0 QPM ise onaylanmadı, 300 QPM ise onaylandı</b> demektir (genelde 2 hafta sürer).</li>
                  <li><b className="text-stone-300">API'leri etkinleştirin:</b> Onay sonrası "Google My Business API" + Account Management + Business Information API'lerini etkinleştirin.</li>
                  <li><b className="text-stone-300">OAuth ekranını yapılandırın:</b> Consent screen'e uygulama adı, gizlilik politikası URL'si ekleyin; scope: <code className="text-violet-300">business.manage</code>. Web tipi OAuth Client ID + Secret oluşturun.</li>
                  <li><b className="text-stone-300">Bize iletin:</b> Client ID + Client Secret'ı paylaşın → sistemde <code className="text-violet-300">GBP_LIVE=true</code> yapılıp kuyrukta bekleyen tüm yanıtlar otomatik yayınlanır.</li>
                </ol>
                <p className="mt-2 text-[10px] text-stone-500">Not: Google sandbox sunmuyor; onay gelene kadar yanıtlar güvenle kuyrukta bekletiliyor.</p>
              </details>
              <div className="bg-stone-900 border border-stone-800 rounded-xl p-4 space-y-3" data-testid="ai-robot-insight">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium text-stone-200">🕵️ İçgörü & Teftiş Raporu — kim, ne dedi, ne yapmalı</p>
                  <div className="flex gap-2">
                    {insight && (
                      <button data-testid="ai-robot-insight-pdf-btn"
                        onClick={async () => {
                          try {
                            const r = await axios.get(`${API}/ai-agent/insight-pdf/${propertyId}`, { responseType: "blob" });
                            const url = URL.createObjectURL(r.data);
                            const a = document.createElement("a");
                            a.href = url; a.download = `icgoru-${propertyId}.pdf`; a.click();
                            URL.revokeObjectURL(url);
                          } catch { toast.error("PDF oluşturulamadı"); }
                        }}
                        className="px-3 py-1.5 rounded-lg bg-stone-800 hover:bg-stone-700 border border-stone-700 text-xs text-stone-100">
                        📄 PDF
                      </button>
                    )}
                    <button data-testid="ai-robot-insight-btn" onClick={runInsight} disabled={insightLoading}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-xs text-white">
                      {insightLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                      {insightLoading ? "Analiz ediliyor…" : insight ? "Yeniden Analiz Et" : "Rapor Oluştur"}
                    </button>
                  </div>
                </div>
                {!insight ? (
                  <p className="text-xs text-stone-500">Robot tüm olumsuz yorumları ve şikayetleri okuyup yönetici raporu çıkarır: kim ne konuda şikayetçi, hangi alanlar geliştirilmeli, somut tavsiyeler.</p>
                ) : (
                  <div className="space-y-4 text-sm">
                    <p className="text-stone-300 text-xs italic">{insight.report?.ozet}</p>
                    <div>
                      <p className="text-xs font-semibold text-amber-300 mb-1.5">Kim, ne ile ilgili kötü değerlendirdi?</p>
                      <div className="space-y-1">
                        {(insight.report?.kim_ne_dedi || []).map((k, i) => (
                          <div key={i} className="flex gap-2 text-xs">
                            <span className="text-stone-200 font-medium w-28 shrink-0 truncate">{k.misafir}</span>
                            <span className="text-violet-300 w-24 shrink-0 truncate">{k.konu}</span>
                            <span className="text-stone-400">{k.sorun}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-rose-300 mb-1.5">Geliştirilmesi gerekenler</p>
                      {(insight.report?.gelistirme_alanlari || []).map((g, i) => (
                        <div key={i} className="flex gap-2 text-xs mb-1">
                          <span className={`px-1.5 rounded shrink-0 ${g.oncelik === "yüksek" ? "bg-rose-500/20 text-rose-300" : g.oncelik === "orta" ? "bg-amber-500/20 text-amber-300" : "bg-stone-700 text-stone-300"}`}>{g.oncelik}</span>
                          <span className="text-stone-200 font-medium">{g.alan}</span>
                          <span className="text-stone-500">— {g.kanit}</span>
                        </div>
                      ))}
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-emerald-300 mb-1.5">Robotun tavsiyeleri</p>
                      {(insight.report?.tavsiyeler || []).map((t, i) => {
                        const task = insightTasks.find((x) => x.title === (t.tavsiye || "").slice(0, 120));
                        return (
                        <div key={i} className="flex items-start gap-2 mb-1">
                          <p className="flex-1 text-xs text-stone-300">✅ <b>{t.tavsiye}</b> <span className="text-stone-500">→ {t.beklenen_etki}</span></p>
                          {task ? (
                            <span data-testid={`insight-task-status-${i}`} className={`shrink-0 px-2 py-0.5 rounded text-[10px] ${["done", "completed", "closed", "resolved"].includes(task.status) ? "bg-emerald-500/20 text-emerald-300" : "bg-amber-500/20 text-amber-300"}`}>
                              {["done", "completed", "closed", "resolved"].includes(task.status) ? "✓ Tamamlandı" : "⏳ Görev açık"}
                            </span>
                          ) : (
                          <button data-testid={`insight-task-btn-${i}`}
                            onClick={async () => {
                              try {
                                const { data } = await axios.post(`${API}/ai-agent/insight-task/${propertyId}`, { tavsiye: t.tavsiye, etki: t.beklenen_etki });
                                toast.success(data.created ? "Yönetime görev açıldı" : "Bu tavsiye için zaten açık görev var");
                                axios.get(`${API}/ai-agent/insight-tasks/${propertyId}`).then(({ data: d }) => setInsightTasks(d.items || [])).catch(() => {});
                              } catch { toast.error("Görev açılamadı"); }
                            }}
                            className="shrink-0 px-2 py-0.5 rounded text-[10px] bg-emerald-600/80 hover:bg-emerald-500 text-white">
                            Görev Aç
                          </button>
                          )}
                        </div>
                        );
                      })}
                    </div>
                    {insight.report?.sikayet_teftis && (
                      <div className="p-3 rounded-lg bg-stone-950 border border-stone-800 text-xs space-y-1">
                        <p className="font-semibold text-stone-200">Şikayet Teftişi</p>
                        <p className="text-stone-400">En sık kategori: <span className="text-stone-200">{insight.report.sikayet_teftis.en_sik_kategori}</span></p>
                        <p className="text-stone-400">Kritik bulgu: <span className="text-stone-200">{insight.report.sikayet_teftis.kritik_bulgu}</span></p>
                        <p className="text-rose-300">Acil aksiyon: {insight.report.sikayet_teftis.acil_aksiyon}</p>
                      </div>
                    )}
                    <p className="text-[10px] text-stone-600">{insight.neg_review_count} olumsuz yorum + {insight.complaint_count} şikayet analiz edildi · {(insight.created_at || "").slice(0, 16).replace("T", " ")}</p>
                  </div>
                )}
              </div>
              <div className="bg-stone-900 border border-stone-800 rounded-xl p-4 space-y-3" data-testid="ai-robot-categories">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium text-stone-200">Kategori Analizi (Semantik)</p>
                  <button data-testid="ai-robot-categorize-btn" onClick={runCategorize} disabled={categorizing}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-xs text-white">
                    {categorizing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                    Yorumları Analiz Et
                  </button>
                </div>
                {catData?.categories?.some((c) => c.avg !== null) ? (
                  <>
                    {catData.weakest && (
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-[11px] text-rose-300">⚠ En zayıf alan: <b>{catData.weakest.replace("_", " ")}</b></p>
                        <button data-testid="ai-robot-weak-task-btn"
                          onClick={async () => {
                            try {
                              const { data } = await axios.post(`${API}/ai-agent/weak-area-task/${propertyId}`);
                              toast.success(data.created
                                ? `${data.department} departmanına iyileştirme görevi açıldı`
                                : "Bu alan için zaten açık bir görev var");
                            } catch { toast.error("Görev açılamadı"); }
                          }}
                          className="px-3 py-1 rounded-lg bg-rose-600/80 hover:bg-rose-500 text-[11px] text-white">
                          Departmana Görev Aç
                        </button>
                      </div>
                    )}
                    {catData.categories.map((c) => (
                      <div key={c.category} className="flex items-center gap-3">
                        <span className="w-32 text-xs text-stone-400 capitalize">{c.category.replace("_", " ")}</span>
                        <div className="flex-1 h-2 rounded-full bg-stone-800 overflow-hidden">
                          <div className={`h-full ${(c.avg || 0) >= 4 ? "bg-emerald-500" : (c.avg || 0) >= 3 ? "bg-amber-500" : "bg-rose-500"}`}
                            style={{ width: `${((c.avg || 0) / 5) * 100}%` }} />
                        </div>
                        <span className="w-20 text-xs text-stone-300 text-right">{c.avg ?? "—"} <span className="text-stone-600">({c.mentions})</span></span>
                      </div>
                    ))}
                  </>
                ) : (
                  <p className="text-xs text-stone-500">Henüz analiz yok — "Yorumları Analiz Et" ile yorumları temizlik/personel/konum/yemek/oda/fiyat kategorilerine puanlatın.</p>
                )}
              </div>
              <div className="bg-stone-900 border border-stone-800 rounded-xl p-4 space-y-3">
                <p className="text-sm font-medium text-stone-200 flex items-center gap-2"><TrendingUp className="w-4 h-4 text-violet-400" /> Haftalık Gelişim</p>
                {report.series.map((w) => (
                  <div key={w.week_start} data-testid={`ai-report-week-${w.week_start}`} className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-stone-400">{w.week_start} haftası</span>
                      <span className="text-stone-300">
                        {w.sent} gönderim · {w.edited} düzenleme · {w.lessons_learned} kural
                        {w.avg_quality !== null && w.avg_quality !== undefined && <span className="text-emerald-300 ml-2">Ø {w.avg_quality} kalite</span>}
                        {w.approval_rate !== null && <span className="text-violet-300 ml-2">%{w.approval_rate} onay</span>}
                      </span>
                    </div>
                    <div className="h-2 rounded-full bg-stone-800 overflow-hidden">
                      <div className="h-full bg-violet-500 transition-all"
                        style={{ width: `${w.approval_rate ?? 0}%` }} />
                    </div>
                    {w.lesson_rules.length > 0 && (
                      <ul className="pl-4 pt-1 space-y-0.5">
                        {w.lesson_rules.map((r, i) => (
                          <li key={i} className="text-[11px] text-stone-500 list-disc">{r}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {tab === "settings" && (
        <div className="max-w-xl space-y-4" data-testid="ai-robot-settings">
          {!config ? (
            <div className="p-6 text-center text-stone-400 text-sm"><Loader2 className="w-5 h-5 mx-auto animate-spin mb-2" />Ayarlar yükleniyor…</div>
          ) : (
            <>
              <div className="space-y-1.5">
                <label className="text-xs text-stone-400">Yanıt imzası</label>
                <input data-testid="ai-robot-config-signoff" value={config.sign_off}
                  onChange={(e) => setConfig({ ...config, sign_off: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg bg-stone-900 border border-stone-700 text-sm text-stone-100 focus:border-violet-500 outline-none" />
                <p className="text-[10px] text-stone-500">Her yanıtın sonuna "— {config.sign_off || "Yönetim"}" olarak eklenir</p>
              </div>
              <div className="space-y-1.5">
                <label className="text-xs text-stone-400">Yanıt tonu</label>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { id: "professional", label: "Profesyonel" },
                    { id: "warm", label: "Sıcak & İçten" },
                    { id: "friendly", label: "Samimi" },
                    { id: "formal", label: "Resmi & Kurumsal" },
                  ].map((t) => (
                    <button key={t.id} data-testid={`ai-robot-config-tone-${t.id}`}
                      onClick={() => setConfig({ ...config, tone: t.id })}
                      className={`px-3 py-2 rounded-lg text-xs border ${config.tone === t.id ? "border-violet-500/60 bg-violet-500/10 text-violet-300" : "border-stone-700 text-stone-400 hover:text-stone-200"}`}>
                      {t.label}
                    </button>
                  ))}
                </div>
              </div>
              <div className="space-y-1.5">
                <label className="text-xs text-stone-400">Kalite uyarı eşiği: <span className="text-violet-300 font-medium">{config.warn_threshold}</span>/100</label>
                <input data-testid="ai-robot-config-threshold" type="range" min="0" max="100" step="5"
                  value={config.warn_threshold}
                  onChange={(e) => setConfig({ ...config, warn_threshold: parseInt(e.target.value) })}
                  className="w-full accent-violet-500" />
                <p className="text-[10px] text-stone-500">Kalite skoru bu değerin altında kalan yanıtlarda göndermeden önce uyarı gösterilir</p>
              </div>
              <div className="space-y-1.5">
                <label className="text-xs text-stone-400">Şikayet yanıt süresi hedefi (SLA): <span className="text-violet-300 font-medium">{config.sla_minutes ?? 60}</span> dakika</label>
                <input data-testid="ai-robot-config-sla" type="range" min="15" max="480" step="15"
                  value={config.sla_minutes ?? 60}
                  onChange={(e) => setConfig({ ...config, sla_minutes: parseInt(e.target.value) })}
                  className="w-full accent-violet-500" />
                <p className="text-[10px] text-stone-500">Bu süre içinde yanıtlanmayan şikayetlerde yöneticiye push uyarısı gider ve kayıt "SLA aşıldı" işaretlenir</p>
              </div>
              <div className="space-y-1.5">
                <label className="text-xs text-stone-400">Haftalık rapor e-postası</label>
                <input data-testid="ai-robot-config-email" type="email" value={config.report_email}
                  onChange={(e) => setConfig({ ...config, report_email: e.target.value })}
                  placeholder="yonetici@otel.com"
                  className="w-full px-3 py-2 rounded-lg bg-stone-900 border border-stone-700 text-sm text-stone-100 focus:border-violet-500 outline-none" />
                <p className="text-[10px] text-stone-500">Robotun haftalık performans özeti her pazartesi 08:00'de bu adrese gönderilir</p>
              </div>
              <button data-testid="ai-robot-config-save" onClick={saveConfig} disabled={savingConfig}
                className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-sm font-medium text-white">
                {savingConfig ? <Loader2 className="w-4 h-4 animate-spin" /> : <Settings2 className="w-4 h-4" />}
                Ayarları Kaydet
              </button>

              {sources && (
                <div className="pt-4 mt-4 border-t border-stone-800 space-y-3" data-testid="ai-robot-sources-section">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium text-stone-200">Yorum Kaynakları</p>
                    <span className={`px-2 py-0.5 text-[10px] rounded ${sources.google_live ? "bg-emerald-500/15 text-emerald-300" : "bg-amber-500/15 text-amber-300"}`}>
                      {sources.google_live ? "Google API bağlı" : "Simülasyon modu"}
                    </span>
                  </div>
                  <p className="text-[10px] text-stone-500">
                    Her sabah 05:30'da Google/Booking yorumları otomatik çekilir, 06:00'da robot taslakları hazırlar.
                    {!sources.google_live && " Gerçek Google yorumları için Google Places API anahtarı gerekir."}
                  </p>
                  <div className="space-y-1.5">
                    <label className="text-xs text-stone-400">Google Place ID</label>
                    <input data-testid="ai-robot-source-placeid" value={sources.google_place_id}
                      onChange={(e) => setSources({ ...sources, google_place_id: e.target.value })}
                      placeholder="ChIJ... (Google Place ID Finder'dan)"
                      className="w-full px-3 py-2 rounded-lg bg-stone-900 border border-stone-700 text-sm text-stone-100 focus:border-violet-500 outline-none" />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs text-stone-400">Booking.com otel sayfası URL</label>
                    <input data-testid="ai-robot-source-booking" value={sources.booking_url}
                      onChange={(e) => setSources({ ...sources, booking_url: e.target.value })}
                      placeholder="https://www.booking.com/hotel/..."
                      className="w-full px-3 py-2 rounded-lg bg-stone-900 border border-stone-700 text-sm text-stone-100 focus:border-violet-500 outline-none" />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs text-stone-400">TripAdvisor otel sayfası URL <span className="text-stone-600">(yüksek puanlı anket misafiri buraya yönlendirilir)</span></label>
                    <input data-testid="ai-robot-source-tripadvisor" value={sources.tripadvisor_url || ""}
                      onChange={(e) => setSources({ ...sources, tripadvisor_url: e.target.value })}
                      placeholder="https://www.tripadvisor.com/Hotel_Review-..."
                      className="w-full px-3 py-2 rounded-lg bg-stone-900 border border-stone-700 text-sm text-stone-100 focus:border-violet-500 outline-none" />
                  </div>
                  <div className="flex gap-2">
                    <button data-testid="ai-robot-source-save" onClick={saveSources}
                      className="px-4 py-2 rounded-lg bg-stone-800 hover:bg-stone-700 border border-stone-700 text-xs text-stone-100">
                      Kaynakları Kaydet
                    </button>
                    <button data-testid="ai-robot-source-sync" onClick={syncNow} disabled={syncing}
                      className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-xs text-white">
                      {syncing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
                      Şimdi Senkronize Et
                    </button>
                  </div>
                  {sources.last_sync_at && (
                    <p className="text-[10px] text-stone-500" data-testid="ai-robot-source-lastsync">
                      Son senkron: {sources.last_sync_at.slice(0, 16).replace("T", " ")} · {sources.last_result?.total_new ?? 0} yeni yorum
                    </p>
                  )}
                </div>
              )}

              <div className="pt-4 mt-4 border-t border-stone-800 space-y-2" data-testid="ai-robot-qr-section">
                <p className="text-sm font-medium text-stone-200">Her-An Anket QR Kodu</p>
                <p className="text-[10px] text-stone-500">Lobiye/odalara asın — misafir taratınca anında anket açılır. Düşük skorlu anketler otomatik şikayet olarak robota düşer.</p>
                {qrUrl && <img data-testid="ai-robot-qr-img" src={qrUrl} alt="Anket QR" className="w-36 h-36 rounded-lg bg-white p-1" />}
                <a data-testid="ai-robot-qr-link" href={`/survey/qr-${propertyId}`} target="_blank" rel="noreferrer"
                  className="text-[11px] text-violet-300 underline block">Anket sayfasını aç: /survey/qr-{propertyId}</a>
              </div>
            </>
          )}
        </div>
      )}

      {tab === "benchmark" && (
        <div className="max-w-3xl space-y-4" data-testid="ai-robot-benchmark">
          <div className="flex items-center gap-2">
            <p className="text-sm font-medium text-stone-200">İtibar Benchmark'ı — 5 rakibe kadar takip</p>
            {bench && (
              <span className={`px-2 py-0.5 text-[10px] rounded ${bench.google_live ? "bg-emerald-500/15 text-emerald-300" : "bg-amber-500/15 text-amber-300"}`}>
                {bench.google_live ? "Google API bağlı" : "Simülasyon modu"}
              </span>
            )}
          </div>
          <div className="space-y-2">
            {benchComps.map((c, i) => (
              <div key={i} className="flex gap-2">
                <input data-testid={`bench-comp-name-${i}`} value={c.name}
                  onChange={(e) => setBenchComps(benchComps.map((x, j) => j === i ? { ...x, name: e.target.value } : x))}
                  placeholder={`Rakip ${i + 1} adı`}
                  className="flex-1 px-3 py-2 rounded-lg bg-stone-900 border border-stone-700 text-sm text-stone-100 focus:border-violet-500 outline-none" />
                <input value={c.place_id}
                  onChange={(e) => setBenchComps(benchComps.map((x, j) => j === i ? { ...x, place_id: e.target.value } : x))}
                  placeholder="Google Place ID (opsiyonel)"
                  className="flex-1 px-3 py-2 rounded-lg bg-stone-900 border border-stone-700 text-sm text-stone-100 focus:border-violet-500 outline-none" />
              </div>
            ))}
            <div className="flex gap-2">
              {benchComps.length < 5 && (
                <button data-testid="bench-add-comp" onClick={() => setBenchComps([...benchComps, { name: "", place_id: "" }])}
                  className="px-3 py-1.5 rounded-lg bg-stone-800 border border-stone-700 text-xs text-stone-300">+ Rakip Ekle</button>
              )}
              <button data-testid="bench-scan-btn" onClick={scanBench} disabled={scanning}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-xs text-white">
                {scanning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Star className="w-3.5 h-3.5" />}
                Kaydet & Şimdi Tara
              </button>
            </div>
          </div>
          {bench?.table?.length > 0 && (
            <div className="bg-stone-900 border border-stone-800 rounded-xl overflow-hidden" data-testid="bench-table">
              <table className="w-full text-sm">
                <thead><tr className="text-left text-[10px] uppercase tracking-wider text-stone-500 border-b border-stone-800">
                  <th className="p-3">#</th><th className="p-3">Otel</th><th className="p-3">Puan</th><th className="p-3">Yorum</th><th className="p-3">30g Trend</th>
                </tr></thead>
                <tbody>
                  {bench.table.map((row) => (
                    <tr key={row.name} className={`border-b border-stone-800/50 ${row.entity === "self" ? "bg-violet-500/10" : ""}`}>
                      <td className="p-3 text-stone-400">{row.rank}</td>
                      <td className="p-3 text-stone-100">{row.entity === "self" ? "🏨 " : ""}{row.name}</td>
                      <td className="p-3 font-semibold text-amber-300">{row.rating ?? "—"}</td>
                      <td className="p-3 text-stone-400">{row.review_count ?? "—"}</td>
                      <td className={`p-3 ${row.trend > 0 ? "text-emerald-400" : row.trend < 0 ? "text-rose-400" : "text-stone-500"}`}>
                        {row.trend > 0 ? "▲" : row.trend < 0 ? "▼" : "—"} {row.trend !== 0 ? Math.abs(row.trend) : ""}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="bg-stone-900 border border-stone-800 rounded-xl p-4 space-y-3" data-testid="bench-spy">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-stone-200">🕵️ Rakip Yorum Casusu — zayıf noktalarını keşfedin</p>
              <button data-testid="bench-spy-btn" disabled={spying}
                onClick={async () => {
                  setSpying(true);
                  try {
                    const { data } = await axios.post(`${API}/reputation/competitor-spy/${propertyId}`);
                    setSpy(data);
                    toast.success("Rakip yorumları analiz edildi");
                  } catch (e) { toast.error(e?.response?.data?.detail || "Analiz başarısız"); }
                  setSpying(false);
                }}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-xs text-white">
                {spying ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                {spy ? "Yeniden Tara" : "Rakipleri Tara"}
              </button>
            </div>
            {!spy ? (
              <p className="text-xs text-stone-500">Rakiplerinizin son yorumlarındaki tekrar eden şikayetleri bulur; sizin güçlü olduğunuz alanları pazarlama fırsatına çevirir. (Google Places anahtarı gelene kadar simülasyon modu)</p>
            ) : (
              <div className="space-y-3">
                {(spy.rows || []).map((r, i) => (
                  <div key={i} data-testid={`spy-row-${i}`} className="p-3 rounded-lg bg-stone-950 border border-stone-800">
                    <div className="flex items-center gap-2 mb-1.5">
                      <p className="text-xs font-semibold text-stone-100">{r.name}</p>
                      <span className="px-1.5 py-0.5 rounded text-[9px] bg-amber-500/15 text-amber-300">{r.mode === "simulated" ? "simülasyon" : "canlı"}</span>
                    </div>
                    {(r.weaknesses || []).map((w, j) => (
                      <div key={j} className="flex items-start gap-2 mb-0.5">
                        <p className="text-xs text-stone-400 flex-1">
                          <span className="text-rose-300 font-medium">{w.konu}:</span> {w.bulgu}
                        </p>
                        {w.bizim_puan != null && (
                          <span data-testid={`spy-our-score-${i}-${j}`}
                            className={`shrink-0 px-1.5 py-0.5 rounded text-[10px] ${w.bizim_puan >= 3.5 ? "bg-emerald-500/15 text-emerald-300" : "bg-amber-500/15 text-amber-300"}`}>
                            Biz: {w.bizim_puan}/5
                          </span>
                        )}
                      </div>
                    ))}
                    <p className={`text-[11px] mt-1.5 ${(r.firsat || "").startsWith("KANITLI") ? "text-emerald-300 font-semibold" : "text-emerald-300"}`}>💡 {r.firsat}</p>
                    {(r.firsat || "").startsWith("KANITLI") && (
                      <button data-testid={`spy-marketing-btn-${i}`}
                        onClick={async () => {
                          try {
                            toast.info("Sosyal medya taslağı hazırlanıyor…");
                            const w0 = (r.weaknesses || [])[0] || {};
                            const { data } = await axios.post(`${API}/reputation/spy-opportunity/${propertyId}`, {
                              konu: w0.konu, firsat: r.firsat, competitor: r.name, bizim_puan: w0.bizim_puan,
                            });
                            await navigator.clipboard.writeText(data.social_draft);
                            toast.success(data.task_created
                              ? "Pazarlamaya görev açıldı — sosyal medya taslağı panoya kopyalandı 📣"
                              : "Görev zaten açıktı — taslak panoya kopyalandı");
                          } catch { toast.error("Gönderilemedi"); }
                        }}
                        className="mt-1.5 px-2.5 py-1 rounded-lg text-[10px] bg-violet-600/80 hover:bg-violet-500 text-white">
                        📣 Pazarlamaya Gönder (görev + sosyal medya taslağı)
                      </button>
                    )}
                  </div>
                ))}
                <p className="text-[10px] text-stone-600">Son tarama: {(spy.created_at || "").slice(0, 16).replace("T", " ")}</p>
              </div>
            )}
          </div>
          {pendingDrafts.length > 0 && (
            <div className="bg-amber-950/40 border border-amber-800/40 rounded-xl p-4 space-y-2" data-testid="pending-approvals">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium text-amber-200">⏳ Onay Bekleyen Otomatik Taslaklar ({pendingDrafts.length}) — tüm şubeler</p>
                <button data-testid="bulk-approve-btn" disabled={bulkApproving}
                  onClick={async () => {
                    setBulkApproving(true);
                    try {
                      const { data } = await axios.post(`${API}/reputation/social-drafts/approve-bulk`, {
                        draft_ids: pendingDrafts.map((p) => p.id),
                      });
                      toast.success(`${data.approved} taslak toplu onaylandı ✅`);
                      setPendingDrafts([]);
                      axios.get(`${API}/reputation/social-drafts/${archivePid}`).then(({ data: d }) => setSocialDrafts(d.items || [])).catch(() => {});
                    } catch { toast.error("Toplu onay başarısız"); }
                    setBulkApproving(false);
                  }}
                  className="px-3 py-1.5 rounded-lg text-xs bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white">
                  {bulkApproving ? "Onaylanıyor…" : `✅ Tümünü Onayla (${pendingDrafts.length})`}
                </button>
              </div>
              {pendingDrafts.map((p) => (
                <div key={p.id} data-testid={`pending-draft-${p.id}`} className="flex items-center gap-2 p-2 rounded-lg bg-stone-950 border border-stone-800 text-xs">
                  <span className="shrink-0 px-1.5 py-0.5 rounded bg-violet-500/15 text-violet-300 text-[10px] w-28 truncate">{p.property_name}</span>
                  <span className="text-stone-400 flex-1 truncate">{p.draft}</span>
                  <button data-testid={`pending-approve-${p.id}`}
                    onClick={async () => {
                      try {
                        await axios.put(`${API}/reputation/social-drafts/${p.id}/approve`);
                        setPendingDrafts((prev) => prev.filter((x) => x.id !== p.id));
                        setSocialDrafts((prev) => prev.map((x) => x.id === p.id ? { ...x, approved: true } : x));
                        toast.success("Onaylandı ✅");
                      } catch { toast.error("Onaylanamadı"); }
                    }}
                    className="shrink-0 px-2 py-0.5 rounded text-[10px] bg-emerald-600/80 hover:bg-emerald-500 text-white">
                    Onayla
                  </button>
                </div>
              ))}
            </div>
          )}
          <div className="bg-stone-900 border border-stone-800 rounded-xl p-4 space-y-2" data-testid="social-draft-archive">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <p className="text-sm font-medium text-stone-200">🗂️ Sosyal Taslak Arşivi ({socialDrafts.length})</p>
                <div className="flex items-center gap-3">
                  {propList.length > 1 && (
                    <label className="flex items-center gap-1.5 text-[10px] text-stone-500">
                      Şube:
                      <select data-testid="archive-property-select" value={archivePid}
                        onChange={(e) => setArchiveProperty(e.target.value)}
                        className="px-2 py-1 rounded bg-stone-950 border border-stone-700 text-[11px] text-stone-200 outline-none max-w-[160px]">
                        {propList.map((p) => (
                          <option key={p.id} value={p.id}>{p.name || p.id}</option>
                        ))}
                      </select>
                    </label>
                  )}
                  <button data-testid="survey-to-draft-btn" disabled={surveyDrafting}
                    onClick={async () => {
                      setSurveyDrafting(true);
                      try {
                        const { data } = await axios.post(`${API}/reputation/survey-to-draft/${archivePid}`);
                        toast.success(`${data.guest} adlı misafirin övgüsü taslağa çevrildi 🎉`);
                        const { data: d } = await axios.get(`${API}/reputation/social-drafts/${archivePid}`);
                        setSocialDrafts(d.items || []);
                      } catch (e) { toast.error(e?.response?.data?.detail || "Taslak üretilemedi"); }
                      setSurveyDrafting(false);
                    }}
                    className="px-2.5 py-1 rounded-lg text-[10px] bg-amber-600/80 hover:bg-amber-500 disabled:opacity-50 text-white">
                    {surveyDrafting ? "Üretiliyor…" : "🎉 Anket Övgüsünden Taslak"}
                  </button>
                  <label className="flex items-center gap-1.5 text-[10px] text-stone-500">
                    Görsel stili:
                    <select data-testid="social-image-style-select" value={imageStyle}
                      onChange={(e) => setImageStyle(e.target.value)}
                      className="px-2 py-1 rounded bg-stone-950 border border-stone-700 text-[11px] text-stone-200 outline-none">
                      <option value="sicak">Sıcak</option>
                      <option value="minimal">Minimal</option>
                      <option value="luks">Lüks</option>
                    </select>
                  </label>
                </div>
              </div>
              {socialDrafts.map((d) => (
                <div key={d.id} data-testid={`social-draft-${d.id}`} className="p-3 rounded-lg bg-stone-950 border border-stone-800">
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-1.5">
                      <span className="text-[10px] text-violet-300 uppercase tracking-wider">{d.topic}{d.edited ? " · düzenlendi" : ""}</span>
                      {d.auto && !d.approved && (
                        <span data-testid={`social-draft-pending-${d.id}`} className="px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-300 text-[9px]">🤖 onay bekliyor</span>
                      )}
                      {d.auto && d.approved && (
                        <span className="px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300 text-[9px]">🤖 onaylandı</span>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] text-stone-600">{(d.created_at || "").slice(0, 16).replace("T", " ")}</span>
                      {d.auto && !d.approved && (
                        <button data-testid={`social-draft-approve-${d.id}`}
                          onClick={async () => {
                            try {
                              await axios.put(`${API}/reputation/social-drafts/${d.id}/approve`);
                              setSocialDrafts((prev) => prev.map((x) => x.id === d.id ? { ...x, approved: true } : x));
                              toast.success("Taslak onaylandı ✅");
                            } catch { toast.error("Onaylanamadı"); }
                          }}
                          className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] bg-emerald-600/80 hover:bg-emerald-500 text-white">
                          ✅ Onayla
                        </button>
                      )}
                      {!d.image_url && (
                        <button data-testid={`social-draft-quick-${d.id}`} disabled={imagingDraft === d.id}
                          onClick={async () => {
                            setImagingDraft(d.id);
                            toast.info("Görsel üretiliyor + paketleniyor… (~20 sn)");
                            try {
                              const { data } = await axios.post(`${API}/reputation/social-drafts/${d.id}/image`, { style: imageStyle });
                              await axios.post(`${API}/reputation/social-drafts/${d.id}/send-package`, { publish_date: publishDates[d.id] || "" });
                              setSocialDrafts((prev) => prev.map((x) => x.id === d.id ? { ...x, image_url: `${data.image_url}?t=${Date.now()}` } : x));
                              axios.get(`${API}/reputation/social-calendar/${archivePid}`).then(({ data: c }) => setSocialCalendar(c.items || [])).catch(() => {});
                              toast.success("⚡ Görsel üretildi ve paket pazarlamaya gönderildi");
                            } catch (e) { toast.error(e?.response?.data?.detail || "İşlem başarısız"); }
                            setImagingDraft(null);
                          }}
                          className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] bg-amber-600/80 hover:bg-amber-500 disabled:opacity-50 text-white">
                          {imagingDraft === d.id ? <Loader2 className="w-3 h-3 animate-spin" /> : null} ⚡ Görsel + Paket
                        </button>
                      )}
                      <button data-testid={`social-draft-variants-${d.id}`} disabled={imagingDraft === d.id}
                        onClick={async () => {
                          setImagingDraft(d.id);
                          toast.info("3 görsel varyasyonu üretiliyor… (~20 sn)");
                          try {
                            const { data } = await axios.post(`${API}/reputation/social-drafts/${d.id}/image`, { style: imageStyle, variants: 3 });
                            setSocialDrafts((prev) => prev.map((x) => x.id === d.id ? { ...x, image_variants: data.variants } : x));
                            toast.success(`${data.variants.length} varyasyon hazır — favorinizi seçin 🎨`);
                          } catch (e) { toast.error(e?.response?.data?.detail || "Varyasyonlar üretilemedi"); }
                          setImagingDraft(null);
                        }}
                        className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] bg-fuchsia-600/80 hover:bg-fuchsia-500 disabled:opacity-50 text-white">
                        🎨 3 Varyasyon
                      </button>
                      <button data-testid={`social-draft-image-${d.id}`} disabled={imagingDraft === d.id}
                        onClick={async () => {
                          setImagingDraft(d.id);
                          toast.info("Görsel üretiliyor… (~15 sn)");
                          try {
                            const { data } = await axios.post(`${API}/reputation/social-drafts/${d.id}/image`, { style: imageStyle });
                            setSocialDrafts((prev) => prev.map((x) => x.id === d.id ? { ...x, image_url: `${data.image_url}?t=${Date.now()}` } : x));
                            toast.success("Görsel hazır 🖼️");
                          } catch (e) { toast.error(e?.response?.data?.detail || "Görsel üretilemedi"); }
                          setImagingDraft(null);
                        }}
                        className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] bg-violet-600/80 hover:bg-violet-500 disabled:opacity-50 text-white">
                        {imagingDraft === d.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <ImageIcon className="w-3 h-3" />}
                        {d.image_url ? "Yeni Görsel" : "Görsel Üret"}
                      </button>
                      <button data-testid={`social-draft-edit-${d.id}`}
                        onClick={() => {
                          if (editingDraft === d.id) { setEditingDraft(null); return; }
                          setEditingDraft(d.id); setEditDraftText(d.draft);
                        }}
                        className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] bg-stone-800 hover:bg-stone-700 border border-stone-700 text-stone-300">
                        <Pencil className="w-3 h-3" /> {editingDraft === d.id ? "Vazgeç" : "Düzenle"}
                      </button>
                      <button data-testid={`social-draft-copy-${d.id}`}
                        onClick={async () => {
                          try {
                            await navigator.clipboard.writeText(d.draft);
                            toast.success("Taslak panoya kopyalandı");
                          } catch { toast.error("Kopyalanamadı"); }
                        }}
                        className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] bg-stone-800 hover:bg-stone-700 border border-stone-700 text-stone-300">
                        <Copy className="w-3 h-3" /> Kopyala
                      </button>
                    </div>
                  </div>
                  {editingDraft === d.id ? (
                    <div className="space-y-2">
                      <textarea data-testid={`social-draft-textarea-${d.id}`} value={editDraftText}
                        onChange={(e) => setEditDraftText(e.target.value)} rows={4}
                        className="w-full p-2 rounded-lg bg-stone-900 border border-stone-700 text-xs text-stone-100 focus:border-violet-500 outline-none resize-y" />
                      <button data-testid={`social-draft-save-${d.id}`}
                        onClick={async () => {
                          try {
                            await axios.put(`${API}/reputation/social-drafts/${d.id}`, { draft: editDraftText });
                            setSocialDrafts((prev) => prev.map((x) => x.id === d.id ? { ...x, draft: editDraftText, edited: true } : x));
                            setEditingDraft(null);
                            toast.success("Taslak güncellendi");
                          } catch { toast.error("Kaydedilemedi"); }
                        }}
                        className="px-3 py-1 rounded-lg text-[11px] bg-emerald-600 hover:bg-emerald-500 text-white">
                        Kaydet
                      </button>
                    </div>
                  ) : (
                    <p className="text-xs text-stone-300 whitespace-pre-wrap">{d.draft}</p>
                  )}
                  {d.image_variants?.length > 0 && (
                    <div className="mt-2">
                      <p className="text-[10px] text-stone-500 mb-1.5">Favorinizi seçin:</p>
                      <div className="flex gap-2 flex-wrap">
                        {d.image_variants.map((v, vi) => {
                          const selected = (d.image_url || "").split("?")[0] === v;
                          return (
                            <button key={vi} data-testid={`variant-select-${d.id}-${vi}`}
                              onClick={async () => {
                                try {
                                  await axios.post(`${API}/reputation/social-drafts/${d.id}/select-image`, { image_url: v });
                                  setSocialDrafts((prev) => prev.map((x) => x.id === d.id ? { ...x, image_url: `${v}?t=${Date.now()}` } : x));
                                  toast.success("Görsel seçildi ✓");
                                } catch { toast.error("Seçilemedi"); }
                              }}
                              className={`relative rounded-lg overflow-hidden border-2 ${selected ? "border-emerald-400" : "border-stone-700 hover:border-stone-500"}`}>
                              <img src={`${process.env.REACT_APP_BACKEND_URL}${v}`} alt={`varyasyon ${vi + 1}`}
                                className="w-24 h-24 object-cover" />
                              {selected && (
                                <span className="absolute top-1 right-1 bg-emerald-500 text-white text-[9px] px-1 rounded">✓</span>
                              )}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  )}
                  {d.image_url && (
                    <div className="mt-2">
                      <a href={`${process.env.REACT_APP_BACKEND_URL}${d.image_url.split("?")[0]}`} target="_blank" rel="noreferrer">
                        <img data-testid={`social-draft-img-${d.id}`}
                          src={`${process.env.REACT_APP_BACKEND_URL}${d.image_url}`}
                          alt={d.topic}
                          className="rounded-lg border border-stone-800 max-h-56 object-cover" />
                      </a>
                      <div className="flex items-center gap-2 mt-2 flex-wrap">
                        <button data-testid={`social-draft-preview-${d.id}`}
                          onClick={() => setPreviewDraft(d)}
                          className="px-2.5 py-1 rounded-lg text-[10px] bg-stone-800 hover:bg-stone-700 border border-stone-700 text-stone-200">
                          📱 Önizleme
                        </button>
                        <button data-testid={`social-draft-download-${d.id}`}
                          onClick={async () => {
                            try {
                              const res = await fetch(`${process.env.REACT_APP_BACKEND_URL}${d.image_url.split("?")[0]}`);
                              const blob = await res.blob();
                              const url = URL.createObjectURL(blob);
                              const a = document.createElement("a");
                              a.href = url;
                              a.download = `sosyal-${(d.topic || "gorsel").replace(/\s+/g, "-")}.png`;
                              a.click();
                              URL.revokeObjectURL(url);
                              toast.success("Görsel indirildi — Instagram'a yüklemeye hazır 📲");
                            } catch { toast.error("İndirilemedi"); }
                          }}
                          className="px-2.5 py-1 rounded-lg text-[10px] bg-stone-800 hover:bg-stone-700 border border-stone-700 text-stone-200">
                          ⬇️ Görseli İndir
                        </button>
                        <input data-testid={`social-publish-date-${d.id}`} type="date"
                          value={publishDates[d.id] || d.publish_date || ""}
                          onChange={(e) => setPublishDates((p) => ({ ...p, [d.id]: e.target.value }))}
                          className="px-2 py-1 rounded-lg text-[10px] bg-stone-950 border border-stone-700 text-stone-300 outline-none" />
                        <button data-testid={`social-draft-package-${d.id}`} disabled={packagingDraft === d.id}
                          onClick={async () => {
                            setPackagingDraft(d.id);
                            try {
                              const pd = publishDates[d.id] || d.publish_date || "";
                              const { data } = await axios.post(`${API}/reputation/social-drafts/${d.id}/send-package`, { publish_date: pd });
                              toast.success(data.task_created
                                ? "📦 Hazır paket pazarlama görevine iliştirildi"
                                : data.date_updated ? "Yayın tarihi güncellendi 📅" : "Bu taslak için paket görevi zaten açık");
                              axios.get(`${API}/reputation/social-calendar/${archivePid}`).then(({ data: c }) => setSocialCalendar(c.items || [])).catch(() => {});
                            } catch { toast.error("Paket gönderilemedi"); }
                            setPackagingDraft(null);
                          }}
                          className="px-2.5 py-1 rounded-lg text-[10px] bg-emerald-600/80 hover:bg-emerald-500 disabled:opacity-50 text-white">
                          {packagingDraft === d.id ? "Gönderiliyor…" : "📦 Pakete Gönder (metin + görsel)"}
                        </button>
                        <div className="flex items-center gap-1">
                          <input data-testid={`refine-note-${d.id}`} type="text"
                            placeholder="Görsel notu: daha aydınlık olsun…"
                            value={refineNotes[d.id] || ""}
                            onChange={(e) => setRefineNotes((p) => ({ ...p, [d.id]: e.target.value }))}
                            className="px-2 py-1 rounded-lg text-[10px] bg-stone-950 border border-stone-700 text-stone-200 outline-none focus:border-violet-500 w-48" />
                          <button data-testid={`refine-btn-${d.id}`} disabled={refiningDraft === d.id || !(refineNotes[d.id] || "").trim()}
                            onClick={async () => {
                              setRefiningDraft(d.id);
                              toast.info("Görsel notunuza göre yenileniyor… (~15 sn)");
                              try {
                                const { data } = await axios.post(`${API}/reputation/social-drafts/${d.id}/refine-image`, { note: refineNotes[d.id] });
                                setSocialDrafts((prev) => prev.map((x) => x.id === d.id ? { ...x, image_url: `${data.image_url}?t=${Date.now()}` } : x));
                                setRefineNotes((p) => ({ ...p, [d.id]: "" }));
                                toast.success("Görsel notunuza göre yenilendi 🪄");
                              } catch (e) { toast.error(e?.response?.data?.detail || "Yenilenemedi"); }
                              setRefiningDraft(null);
                            }}
                            className="px-2 py-1 rounded-lg text-[10px] bg-violet-600/80 hover:bg-violet-500 disabled:opacity-40 text-white">
                            {refiningDraft === d.id ? "…" : "🪄 İyileştir"}
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ))}
              {socialDrafts.length === 0 && (
                <p className="text-xs text-stone-500 py-3 text-center">Bu şube için henüz taslak yok — "🎉 Anket Övgüsünden Taslak" ile başlayın.</p>
              )}
            </div>
          {socialCalendar.length > 0 && (
            <div className="bg-stone-900 border border-stone-800 rounded-xl p-4 space-y-2" data-testid="social-calendar">
              <p className="text-sm font-medium text-stone-200">📅 Yayın Planı ({socialCalendar.length})</p>
              {socialCalendar.map((c) => (
                <div key={c.draft_id} data-testid={`calendar-item-${c.draft_id}`} className="flex items-center gap-3 p-2 rounded-lg bg-stone-950 border border-stone-800 text-xs">
                  <span className={`shrink-0 w-24 font-mono ${c.publish_date ? "text-amber-300" : "text-stone-600"}`}>
                    {c.publish_date || "tarihsiz"}
                  </span>
                  {c.image_url && (
                    <img src={`${process.env.REACT_APP_BACKEND_URL}${c.image_url.split("?")[0]}`} alt=""
                      className="w-8 h-8 rounded object-cover border border-stone-800 shrink-0" />
                  )}
                  <span className="text-violet-300 uppercase text-[10px] shrink-0">{c.topic}</span>
                  <span className="text-stone-500 flex-1 truncate">{c.draft}</span>
                  <span className={`shrink-0 px-1.5 py-0.5 rounded text-[10px] ${["done", "completed", "closed"].includes(c.task_status) ? "bg-emerald-500/15 text-emerald-300" : "bg-amber-500/15 text-amber-300"}`}>
                    {["done", "completed", "closed"].includes(c.task_status) ? "✓ Yayınlandı" : "⏳ Bekliyor"}
                  </span>
                </div>
              ))}
            </div>
          )}
          {previewDraft && (
            <div data-testid="instagram-preview-modal" onClick={() => setPreviewDraft(null)}
              className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
              <div onClick={(e) => e.stopPropagation()}
                className="w-[340px] bg-stone-950 border border-stone-700 rounded-3xl overflow-hidden shadow-2xl">
                <div className="flex items-center justify-between px-3 py-2.5 border-b border-stone-800">
                  <div className="flex items-center gap-2">
                    <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-amber-500 to-rose-500 flex items-center justify-center text-[11px] font-bold text-white">
                      {(hotelName || "O").slice(0, 1).toUpperCase()}
                    </div>
                    <span className="text-xs font-semibold text-stone-100">{(hotelName || "otelimiz").toLowerCase().replace(/\s+/g, "")}</span>
                  </div>
                  <button data-testid="preview-close-btn" onClick={() => setPreviewDraft(null)} className="text-stone-500 hover:text-stone-200 text-lg leading-none">×</button>
                </div>
                {previewDraft.image_url ? (
                  <img src={`${process.env.REACT_APP_BACKEND_URL}${previewDraft.image_url.split("?")[0]}`} alt=""
                    className="w-full aspect-square object-cover" />
                ) : (
                  <div className="w-full aspect-square bg-stone-900 flex items-center justify-center text-stone-600 text-xs">Görsel yok — "Görsel Üret" ile ekleyin</div>
                )}
                <div className="px-3 py-2 flex items-center gap-3 text-stone-300">
                  <Star className="w-4 h-4" /><Send className="w-4 h-4" /><Copy className="w-4 h-4" />
                </div>
                <p className="px-3 pb-3 text-xs text-stone-200 leading-relaxed">
                  <span className="font-semibold">{(hotelName || "otelimiz").toLowerCase().replace(/\s+/g, "")}</span>{" "}
                  {previewDraft.draft}
                </p>
              </div>
            </div>
          )}
        </div>
      )}

      {tab === "portfolio" && (
        <div className="space-y-3" data-testid="ai-robot-portfolio">
          <p className="text-sm font-medium text-stone-200">Portföy Roll-up — tüm şubelerin yorum & robot performansı karşılaştırması</p>
          {!portfolio ? (
            <div className="p-6 text-center text-stone-400 text-sm"><Loader2 className="w-5 h-5 mx-auto animate-spin" /></div>
          ) : (
            <div className="bg-stone-900 border border-stone-800 rounded-xl overflow-x-auto">
              <table className="w-full text-sm min-w-[860px]">
                <thead><tr className="text-left text-[10px] uppercase tracking-wider text-stone-500 border-b border-stone-800">
                  <th className="p-3">Tesis</th><th className="p-3">Ø Puan</th><th className="p-3">30g Trend</th><th className="p-3">Yorum</th><th className="p-3">Anket</th><th className="p-3">Gönderilen</th><th className="p-3">Onay %</th>
                  <th className="p-3">Ø Kalite</th><th className="p-3">Bekleyen Yorum</th><th className="p-3">Açık Şikayet</th><th className="p-3">Kural</th>
                </tr></thead>
                <tbody>
                  {(() => {
                    const rated = portfolio.rows.filter((r) => r.avg_rating != null);
                    const best = rated.length ? Math.max(...rated.map((r) => r.avg_rating)) : null;
                    const worst = rated.length > 1 ? Math.min(...rated.map((r) => r.avg_rating)) : null;
                    return portfolio.rows.map((r) => (
                    <tr key={r.property_id} data-testid={`portfolio-row-${r.property_id}`} className="border-b border-stone-800/50">
                      <td className="p-3 text-stone-100">{r.name}</td>
                      <td className="p-3 font-semibold">
                        {r.avg_rating != null ? (
                          <span className={r.avg_rating === best ? "text-emerald-300" : r.avg_rating === worst ? "text-rose-300" : "text-amber-300"}>
                            {r.avg_rating}{r.avg_rating === best ? " 🏆" : r.avg_rating === worst ? " ⚠" : ""}
                          </span>
                        ) : <span className="text-stone-600">—</span>}
                      </td>
                      <td className="p-3" data-testid={`portfolio-trend-${r.property_id}`}>
                        {r.rating_trend != null ? (
                          <span className={r.rating_trend > 0 ? "text-emerald-400" : r.rating_trend < 0 ? "text-rose-400" : "text-stone-500"}>
                            {r.rating_trend > 0 ? "▲" : r.rating_trend < 0 ? "▼" : "—"} {r.rating_trend !== 0 ? Math.abs(r.rating_trend) : ""}
                          </span>
                        ) : <span className="text-stone-600">—</span>}
                      </td>
                      <td className="p-3 text-stone-400">{r.review_count ?? "—"}</td>
                      <td className="p-3 text-stone-300">{r.survey_score ?? "—"}</td>
                      <td className="p-3 text-stone-300">{r.sent}</td>
                      <td className="p-3 text-violet-300">{r.approval_rate !== null ? `%${r.approval_rate}` : "—"}</td>
                      <td className="p-3 text-emerald-300">{r.avg_quality ?? "—"}</td>
                      <td className={`p-3 ${r.pending_reviews > 0 ? "text-amber-300" : "text-stone-500"}`}>{r.pending_reviews}</td>
                      <td className={`p-3 ${r.open_complaints > 0 ? "text-rose-300" : "text-stone-500"}`}>{r.open_complaints}</td>
                      <td className="p-3 text-stone-400">{r.lessons}</td>
                    </tr>
                    ));
                  })()}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {tab === "lessons" && (
        <div className="space-y-3 max-w-3xl" data-testid="ai-robot-lessons-list">
          <div className="flex gap-2">
            <input data-testid="ai-robot-new-rule-input" value={newRule}
              onChange={(e) => setNewRule(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addRule()}
              placeholder="Manuel kural ekle — ör: 'Yanıtlarda misafire her zaman adıyla hitap et'"
              className="flex-1 px-3 py-2 rounded-lg bg-stone-900 border border-stone-700 text-sm text-stone-100 focus:border-violet-500 outline-none" />
            <button data-testid="ai-robot-add-rule-btn" onClick={addRule}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 text-sm text-white">
              <Plus className="w-4 h-4" /> Ekle
            </button>
          </div>
          {lessons.length === 0 && (
            <div className="p-8 text-center text-stone-500 text-sm border border-dashed border-stone-800 rounded-xl">
              <GraduationCap className="w-6 h-6 mx-auto mb-2 text-stone-600" />
              Robot henüz kural öğrenmedi. Taslakları düzenleyip gönderdikçe burada kurallar birikecek.
            </div>
          )}
          {lessons.map((l) => (
            <div key={l.id} data-testid={`ai-robot-lesson-${l.id}`}
              className="flex items-start gap-3 p-3 rounded-xl bg-stone-900 border border-stone-800">
              <GraduationCap className="w-4 h-4 text-violet-400 mt-0.5 shrink-0" />
              <div className="flex-1">
                <p className="text-sm text-stone-200">{l.rule}</p>
                <p className="text-[10px] text-stone-500 mt-0.5">
                  {l.source === "manual" ? "Manuel eklendi" : "Düzenlemeden öğrenildi"} · {(l.created_at || "").slice(0, 10)}
                </p>
              </div>
              <button data-testid={`ai-robot-delete-lesson-${l.id}`} onClick={() => deleteRule(l.id)}
                className="p-1.5 rounded-lg hover:bg-stone-800 text-stone-500 hover:text-rose-400">
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
