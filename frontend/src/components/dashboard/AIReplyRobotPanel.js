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
  ClipboardPaste, Copy, Settings2,
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
    if (tab === "settings" && propertyId) loadConfig();
  }, [tab, propertyId, loadConfig]);

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
                  <p className="text-xs text-stone-500 mb-1">{selected.source_type === "review" ? "Misafir Yorumu" : "Misafir Şikayeti"} — {selected.guest_name}</p>
                  <p className="text-sm text-stone-200 whitespace-pre-wrap">{selected.text}</p>
                </div>
                <button data-testid="ai-robot-generate-btn" onClick={() => generateDraft(selected)} disabled={drafting}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-sm font-medium text-white">
                  {drafting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                  {drafting ? "Robot yazıyor…" : draft ? "Yeniden Oluştur" : "AI Taslak Oluştur"}
                </button>
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
            </>
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
