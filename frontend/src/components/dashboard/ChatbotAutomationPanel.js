import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Bot, Sparkles, MessageSquare, Hash, Heart, Settings, Trash2,
  CheckCircle2, Send, RefreshCw, Plus, Play, Globe, Code,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const auth = () => ({ Authorization: `Bearer ${localStorage.getItem("access_token")}` });

const TONES = [
  { id: "professional", label: "Profesyonel" },
  { id: "friendly", label: "Samimi" },
  { id: "casual", label: "Rahat" },
  { id: "polished", label: "Şık" },
  { id: "humorous", label: "Esprili" },
];
const ACTIONS = [
  { id: "reply_guest", label: "Misafire Yanıtla" },
  { id: "create_ticket", label: "Ticket Oluştur" },
  { id: "notify_team_chat", label: "Team Chat'i Bilgilendir" },
  { id: "send_email", label: "E-posta Gönder" },
  { id: "send_sms", label: "SMS Gönder" },
];

const TabBtn = ({ id, active, onClick, icon: Icon, label, count }) => (
  <button
    data-testid={`chatbot-tab-${id}`}
    onClick={onClick}
    className={`px-3 py-2 rounded-lg text-sm font-medium flex items-center gap-2 transition ${
      active ? "bg-violet-600 text-white" : "bg-white text-stone-600 border border-stone-200 hover:border-stone-300"
    }`}
  >
    <Icon className="w-4 h-4" />
    {label}
    {count != null && (
      <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${active ? "bg-white/20" : "bg-stone-100"}`}>{count}</span>
    )}
  </button>
);

const ChatbotAutomationPanel = ({ propertyId }) => {
  const [tab, setTab] = useState("settings");
  const [settings, setSettings] = useState(null);
  const [intents, setIntents] = useState([]);
  const [keywords, setKeywords] = useState([]);
  const [sentActs, setSentActs] = useState([]);
  const [sources, setSources] = useState([]);
  const [runs, setRuns] = useState([]);
  const [busy, setBusy] = useState(false);

  // Form state
  const [newIntent, setNewIntent] = useState({ name: "", trigger_phrases: "", action_type: "reply_guest", reply_text: "", sentiment: "any" });
  const [newKw, setNewKw] = useState({ command: "", action_type: "reply_guest", reply_text: "" });
  const [newSa, setNewSa] = useState({ sentiment: "negative", action_type: "notify_team_chat", reply_text: "" });
  const [genUrl, setGenUrl] = useState("");
  const [genTone, setGenTone] = useState("friendly");
  const [testText, setTestText] = useState("");
  const [testResult, setTestResult] = useState(null);

  const refresh = useCallback(async () => {
    if (!propertyId || propertyId === "all") return;
    try {
      const [s, i, k, sa, src, r] = await Promise.all([
        axios.get(`${API}/chatbot/${propertyId}/settings`, { headers: auth() }),
        axios.get(`${API}/chatbot/${propertyId}/intents`, { headers: auth() }),
        axios.get(`${API}/chatbot/${propertyId}/keywords`, { headers: auth() }),
        axios.get(`${API}/chatbot/${propertyId}/sentiment-actions`, { headers: auth() }),
        axios.get(`${API}/chatbot/${propertyId}/content-sources`, { headers: auth() }),
        axios.get(`${API}/chatbot/${propertyId}/runs?limit=50`, { headers: auth() }),
      ]);
      setSettings(s.data);
      setIntents(i.data.items || []);
      setKeywords(k.data.items || []);
      setSentActs(sa.data.items || []);
      setSources(src.data.items || []);
      setRuns(r.data.items || []);
    } catch (e) {
      console.error("chatbot load failed", e);
    }
  }, [propertyId]);

  useEffect(() => { refresh(); }, [refresh]);

  const saveSettings = async (patch) => {
    if (!settings) return;
    try {
      const r = await axios.put(`${API}/chatbot/${propertyId}/settings`, { ...settings, ...patch }, { headers: auth() });
      setSettings(r.data);
      toast.success("Ayarlar kaydedildi");
    } catch { toast.error("Ayarlar kaydedilemedi"); }
  };

  const addIntent = async () => {
    if (!newIntent.name || !newIntent.trigger_phrases) {
      toast.error("İsim ve trigger phrases gerekli");
      return;
    }
    setBusy(true);
    try {
      await axios.post(`${API}/chatbot/${propertyId}/intents`, {
        ...newIntent,
        trigger_phrases: newIntent.trigger_phrases.split(",").map(s => s.trim()).filter(Boolean),
      }, { headers: auth() });
      toast.success("Intent eklendi");
      setNewIntent({ name: "", trigger_phrases: "", action_type: "reply_guest", reply_text: "", sentiment: "any" });
      refresh();
    } catch (e) { toast.error(e?.response?.data?.detail || "Intent eklenemedi"); }
    setBusy(false);
  };

  const delIntent = async (id) => {
    await axios.delete(`${API}/chatbot/intents/${id}`, { headers: auth() });
    toast.success("Silindi");
    refresh();
  };

  const addKw = async () => {
    if (!newKw.command) { toast.error("Komut gerekli"); return; }
    setBusy(true);
    try {
      await axios.post(`${API}/chatbot/${propertyId}/keywords`, newKw, { headers: auth() });
      toast.success("Keyword eklendi");
      setNewKw({ command: "", action_type: "reply_guest", reply_text: "" });
      refresh();
    } catch (e) { toast.error("Keyword eklenemedi"); }
    setBusy(false);
  };

  const delKw = async (id) => {
    await axios.delete(`${API}/chatbot/keywords/${id}`, { headers: auth() });
    refresh();
  };

  const addSa = async () => {
    setBusy(true);
    try {
      await axios.post(`${API}/chatbot/${propertyId}/sentiment-actions`, newSa, { headers: auth() });
      toast.success("Sentiment aksiyonu eklendi");
      setNewSa({ sentiment: "negative", action_type: "notify_team_chat", reply_text: "" });
      refresh();
    } catch { toast.error("Eklenemedi"); }
    setBusy(false);
  };

  const delSa = async (id) => {
    await axios.delete(`${API}/chatbot/sentiment-actions/${id}`, { headers: auth() });
    refresh();
  };

  const generateFromUrl = async () => {
    if (!genUrl) { toast.error("URL gerekli"); return; }
    setBusy(true);
    toast.info("AI 10 FAQ üretiyor… bu 10-20 saniye sürer.");
    try {
      const r = await axios.post(`${API}/chatbot/${propertyId}/content-sources/generate`,
        { url: genUrl, tone: genTone, language: settings?.default_language || "tr" }, { headers: auth() });
      toast.success(`${r.data.created} intent oluşturuldu`);
      setGenUrl("");
      refresh();
    } catch (e) { toast.error(e?.response?.data?.detail || "AI üretim başarısız"); }
    setBusy(false);
  };

  const runTest = async () => {
    if (!testText) return;
    try {
      const r = await axios.post(`${API}/chatbot/${propertyId}/test`, { text: testText }, { headers: auth() });
      setTestResult(r.data);
    } catch (e) { toast.error("Test başarısız"); }
  };

  if (!propertyId || propertyId === "all") {
    return (
      <div className="bg-white border border-stone-200 rounded-2xl p-6" data-testid="chatbot-panel-empty">
        <div className="flex items-center gap-3"><Bot className="w-6 h-6 text-violet-600" />
          <div>
            <p className="text-stone-600 font-semibold">Chatbot Automations için lütfen bir otel seçin.</p>
            <p className="text-xs text-stone-400 mt-1">Sol menünün üstündeki şube seçicisinden ("All Branches") tek bir otel seçtiğinizde bu panel aktifleşir.</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="chatbot-panel">
      {/* HEADER */}
      <div className="relative overflow-hidden rounded-2xl border border-violet-200 bg-gradient-to-br from-violet-600 via-fuchsia-600 to-indigo-700 p-6 text-white">
        <div className="absolute -top-12 -right-12 w-48 h-48 bg-white/10 rounded-full blur-3xl"></div>
        <div className="relative flex items-start justify-between gap-4 flex-wrap">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Bot className="w-5 h-5" />
              <span className="text-xs uppercase tracking-widest font-bold opacity-80">Guest Experience · Chatbot</span>
            </div>
            <h2 className="text-2xl font-bold">Akıllı Yanıt Motoru</h2>
            <p className="text-sm opacity-85 mt-1">
              Intent + Keyword + Sentiment ile guest chat'i otomatikleştir
            </p>
          </div>
          <button data-testid="chatbot-refresh" onClick={refresh}
            className="px-3 py-2 bg-white/15 hover:bg-white/25 rounded-lg text-sm font-medium flex items-center gap-2">
            <RefreshCw className="w-4 h-4" /> Yenile
          </button>
        </div>
      </div>

      {/* TABS */}
      <div className="flex items-center gap-2 flex-wrap">
        <TabBtn id="settings" active={tab === "settings"} onClick={() => setTab("settings")} icon={Settings} label="Ayarlar" />
        <TabBtn id="intents" active={tab === "intents"} onClick={() => setTab("intents")} icon={MessageSquare} label="Intent & Yanıtlar" count={intents.length} />
        <TabBtn id="keywords" active={tab === "keywords"} onClick={() => setTab("keywords")} icon={Hash} label="Keyword Komutlar" count={keywords.length} />
        <TabBtn id="sentiment" active={tab === "sentiment"} onClick={() => setTab("sentiment")} icon={Heart} label="Sentiment" count={sentActs.length} />
        <TabBtn id="sources" active={tab === "sources"} onClick={() => setTab("sources")} icon={Sparkles} label="AI Kaynaklar" count={sources.length} />
        <TabBtn id="embed" active={tab === "embed"} onClick={() => setTab("embed")} icon={Code} label="Embed Widget" />
        <TabBtn id="runs" active={tab === "runs"} onClick={() => setTab("runs")} icon={Play} label="Çalışma Geçmişi" count={runs.length} />
      </div>

      {/* SETTINGS */}
      {tab === "settings" && settings && (
        <div className="bg-white border border-stone-200 rounded-2xl p-6 space-y-4" data-testid="chatbot-settings">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Row label="Chatbot Açık" desc="Tüm otomasyonlar aktif"><Switch data-testid="chatbot-cfg-enabled" checked={!!settings.enabled} onCheckedChange={(v) => saveSettings({ enabled: v })} /></Row>
            <Row label="Live Chat Yanıtları" desc="Live Chat içinde otomatik yanıt"><Switch checked={!!settings.guest_replies_live_chat} onCheckedChange={(v) => saveSettings({ guest_replies_live_chat: v })} /></Row>
            <Row label="Guest Chat Yanıtları" desc="Guest Chat içinde otomatik yanıt"><Switch checked={!!settings.guest_replies_guest_chat} onCheckedChange={(v) => saveSettings({ guest_replies_guest_chat: v })} /></Row>
            <Row label="Çeviri (Gelen)" desc="Guest mesajını TR'ye çevir"><Switch checked={!!settings.translation_inbound} onCheckedChange={(v) => saveSettings({ translation_inbound: v })} /></Row>
            <Row label="Çeviri (Giden)" desc="Yanıtı guest dilinde çevir"><Switch checked={!!settings.translation_outbound} onCheckedChange={(v) => saveSettings({ translation_outbound: v })} /></Row>
            <Row label="Varsayılan Ton" desc="AI üretim için">
              <Select value={settings.default_tone} onValueChange={(v) => saveSettings({ default_tone: v })}>
                <SelectTrigger className="w-32"><SelectValue /></SelectTrigger>
                <SelectContent>{TONES.map(t => <SelectItem key={t.id} value={t.id}>{t.label}</SelectItem>)}</SelectContent>
              </Select>
            </Row>
          </div>
          <div>
            <label className="text-xs font-semibold text-stone-700">Fallback Mesajı (eşleşme yoksa)</label>
            <Textarea data-testid="chatbot-cfg-fallback" value={settings.fallback_message} onChange={(e) => setSettings({ ...settings, fallback_message: e.target.value })} onBlur={(e) => saveSettings({ fallback_message: e.target.value })} className="mt-1" rows={2} />
          </div>
          <div>
            <label className="text-xs font-semibold text-stone-700">Handoff Keywords (virgülle, insana bağlanır)</label>
            <Input value={(settings.handoff_keywords || []).join(", ")} onChange={(e) => setSettings({ ...settings, handoff_keywords: e.target.value.split(",").map(s => s.trim()) })} onBlur={(e) => saveSettings({ handoff_keywords: e.target.value.split(",").map(s => s.trim()).filter(Boolean) })} className="mt-1" />
          </div>

          {/* LIVE TESTER */}
          <div className="mt-4 p-4 rounded-xl border border-violet-200 bg-violet-50">
            <div className="flex items-center gap-2 mb-2"><Send className="w-4 h-4 text-violet-700" /><h4 className="font-bold text-violet-900">Canlı Test</h4></div>
            <div className="flex gap-2">
              <Input data-testid="chatbot-test-input" placeholder="Misafir mesajı yaz, örn. 'wifi şifresi nedir'" value={testText} onChange={(e) => setTestText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && runTest()} />
              <button data-testid="chatbot-test-btn" onClick={runTest} className="px-3 py-2 bg-violet-600 text-white rounded-lg text-sm font-bold">Test Et</button>
            </div>
            {testResult && (
              <div className="mt-3 p-3 rounded bg-white border border-stone-200 text-xs">
                <div><b>Eşleşme:</b> {testResult.matched ? "✓" : "✗"} · <b>Tür:</b> {testResult.match_type || "-"} · <b>Duygu:</b> {testResult.sentiment || "-"}</div>
                {testResult.intent && (
                  <div className="mt-1"><b>{testResult.intent.name || testResult.intent.command}:</b> {testResult.intent.reply_text}</div>
                )}
                {testResult.fallback_message && <div className="mt-1 text-stone-500">Fallback: {testResult.fallback_message}</div>}
              </div>
            )}
          </div>
        </div>
      )}

      {/* INTENTS */}
      {tab === "intents" && (
        <div className="bg-white border border-stone-200 rounded-2xl p-6 space-y-4" data-testid="chatbot-intents">
          <div className="p-4 rounded-xl border border-stone-200 bg-stone-50 grid grid-cols-1 md:grid-cols-2 gap-3">
            <Input placeholder="Intent adı (örn. Wi-Fi sorgusu)" value={newIntent.name} onChange={(e) => setNewIntent({ ...newIntent, name: e.target.value })} data-testid="chatbot-intent-name" />
            <Input placeholder="Trigger phrases (virgülle: wifi, internet, şifre)" value={newIntent.trigger_phrases} onChange={(e) => setNewIntent({ ...newIntent, trigger_phrases: e.target.value })} data-testid="chatbot-intent-phrases" />
            <Select value={newIntent.action_type} onValueChange={(v) => setNewIntent({ ...newIntent, action_type: v })}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>{ACTIONS.map(a => <SelectItem key={a.id} value={a.id}>{a.label}</SelectItem>)}</SelectContent>
            </Select>
            <Select value={newIntent.sentiment} onValueChange={(v) => setNewIntent({ ...newIntent, sentiment: v })}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="any">Tüm duygular</SelectItem>
                <SelectItem value="positive">Pozitif</SelectItem>
                <SelectItem value="negative">Negatif</SelectItem>
                <SelectItem value="neutral">Nötr</SelectItem>
              </SelectContent>
            </Select>
            <Textarea placeholder="Yanıt metni" value={newIntent.reply_text} onChange={(e) => setNewIntent({ ...newIntent, reply_text: e.target.value })} className="md:col-span-2" rows={2} data-testid="chatbot-intent-reply" />
            <button onClick={addIntent} disabled={busy} className="md:col-span-2 px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white rounded-lg text-sm font-bold flex items-center justify-center gap-2 disabled:opacity-50" data-testid="chatbot-intent-add">
              <Plus className="w-4 h-4" /> Intent Ekle
            </button>
          </div>
          <div className="space-y-2 max-h-[500px] overflow-y-auto">
            {intents.length === 0 && <div className="text-stone-400 text-center py-8 text-sm">Henüz intent yok. AI ile üretmek için "AI Kaynaklar" sekmesine geç.</div>}
            {intents.map((it, idx) => (
              <div key={it.id} className="p-3 rounded-lg border border-stone-200 bg-white flex items-start justify-between gap-3" data-testid={`chatbot-intent-${idx}`}>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <CheckCircle2 className={`w-4 h-4 ${it.enabled ? "text-emerald-600" : "text-stone-300"}`} />
                    <h5 className="font-bold text-stone-800">{it.name}</h5>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-stone-100 text-stone-600 font-mono">{it.category}</span>
                    {it.sentiment !== "any" && <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-800">{it.sentiment}</span>}
                  </div>
                  <div className="text-xs text-stone-500 mb-1">Triggers: {(it.trigger_phrases || []).join(" · ")}</div>
                  <div className="text-xs text-stone-700 italic">"{it.reply_text?.slice(0, 200)}"</div>
                </div>
                <button onClick={() => delIntent(it.id)} className="p-2 hover:bg-rose-50 rounded text-rose-600" data-testid={`chatbot-intent-del-${idx}`}><Trash2 className="w-4 h-4" /></button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* KEYWORDS */}
      {tab === "keywords" && (
        <div className="bg-white border border-stone-200 rounded-2xl p-6 space-y-4" data-testid="chatbot-keywords">
          <div className="p-4 rounded-xl border border-stone-200 bg-stone-50 grid grid-cols-1 md:grid-cols-3 gap-3">
            <Input placeholder="Komut kelimesi (örn. refund)" value={newKw.command} onChange={(e) => setNewKw({ ...newKw, command: e.target.value })} />
            <Select value={newKw.action_type} onValueChange={(v) => setNewKw({ ...newKw, action_type: v })}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>{ACTIONS.map(a => <SelectItem key={a.id} value={a.id}>{a.label}</SelectItem>)}</SelectContent>
            </Select>
            <button onClick={addKw} disabled={busy} className="px-3 py-2 bg-violet-600 text-white rounded-lg text-sm font-bold disabled:opacity-50">Ekle</button>
            <Textarea placeholder="Yanıt" value={newKw.reply_text} onChange={(e) => setNewKw({ ...newKw, reply_text: e.target.value })} className="md:col-span-3" rows={2} />
          </div>
          <div className="space-y-2">
            {keywords.map((kw, idx) => (
              <div key={kw.id} className="p-3 rounded border border-stone-200 flex items-center justify-between">
                <div><b className="font-mono">{kw.command}</b> · <span className="text-xs text-stone-500">{ACTIONS.find(a => a.id === kw.action_type)?.label}</span></div>
                <button onClick={() => delKw(kw.id)} className="p-1.5 hover:bg-rose-50 rounded text-rose-600"><Trash2 className="w-4 h-4" /></button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* SENTIMENT */}
      {tab === "sentiment" && (
        <div className="bg-white border border-stone-200 rounded-2xl p-6 space-y-4" data-testid="chatbot-sentiment">
          <div className="p-4 rounded-xl border border-stone-200 bg-stone-50 grid grid-cols-1 md:grid-cols-3 gap-3">
            <Select value={newSa.sentiment} onValueChange={(v) => setNewSa({ ...newSa, sentiment: v })}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="positive">Pozitif</SelectItem>
                <SelectItem value="negative">Negatif</SelectItem>
              </SelectContent>
            </Select>
            <Select value={newSa.action_type} onValueChange={(v) => setNewSa({ ...newSa, action_type: v })}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>{ACTIONS.map(a => <SelectItem key={a.id} value={a.id}>{a.label}</SelectItem>)}</SelectContent>
            </Select>
            <button onClick={addSa} disabled={busy} className="px-3 py-2 bg-violet-600 text-white rounded-lg text-sm font-bold disabled:opacity-50">Ekle</button>
            <Textarea placeholder="Yanıt / Mesaj" value={newSa.reply_text} onChange={(e) => setNewSa({ ...newSa, reply_text: e.target.value })} className="md:col-span-3" rows={2} />
          </div>
          <div className="space-y-2">
            {sentActs.map((sa, idx) => (
              <div key={sa.id} className="p-3 rounded border border-stone-200 flex items-center justify-between">
                <div>
                  <span className={`text-[11px] font-bold px-1.5 py-0.5 rounded ${sa.sentiment === "positive" ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700"}`}>{sa.sentiment}</span>
                  <span className="ml-2 text-sm">{ACTIONS.find(a => a.id === sa.action_type)?.label}</span>
                  {sa.reply_text && <span className="ml-3 text-xs text-stone-500 italic">"{sa.reply_text.slice(0, 80)}"</span>}
                </div>
                <button onClick={() => delSa(sa.id)} className="p-1.5 hover:bg-rose-50 rounded text-rose-600"><Trash2 className="w-4 h-4" /></button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* AI SOURCES */}
      {tab === "sources" && (
        <div className="bg-white border border-stone-200 rounded-2xl p-6 space-y-4" data-testid="chatbot-sources">
          <div className="p-5 rounded-xl border border-violet-200 bg-gradient-to-br from-violet-50 to-indigo-50">
            <div className="flex items-center gap-2 mb-3">
              <Sparkles className="w-5 h-5 text-violet-600" />
              <h4 className="font-bold text-stone-900">AI ile Otomatik FAQ Üret</h4>
            </div>
            <p className="text-sm text-stone-600 mb-3">Otel websitenin veya TripAdvisor URL'nin link'ini ver, GPT-4o-mini 10 FAQ intent üretsin (wifi, kahvaltı, check-in, vs).</p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <Input data-testid="chatbot-gen-url" placeholder="https://hotel.com" value={genUrl} onChange={(e) => setGenUrl(e.target.value)} className="md:col-span-2" />
              <Select value={genTone} onValueChange={setGenTone}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{TONES.map(t => <SelectItem key={t.id} value={t.id}>{t.label}</SelectItem>)}</SelectContent>
              </Select>
              <button data-testid="chatbot-gen-btn" onClick={generateFromUrl} disabled={busy} className="md:col-span-3 px-4 py-2 bg-gradient-to-r from-violet-600 to-indigo-600 text-white rounded-lg text-sm font-bold flex items-center justify-center gap-2 disabled:opacity-50">
                <Sparkles className="w-4 h-4" /> {busy ? "AI Üretiyor…" : "10 FAQ Üret"}
              </button>
            </div>
          </div>
          <div className="space-y-2">
            {sources.map((s, idx) => (
              <div key={idx} className="p-3 rounded border border-stone-200 flex items-center justify-between">
                <div>
                  <Globe className="w-3 h-3 inline mr-2 text-stone-400" />
                  <span className="text-sm">{s.url}</span>
                  <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-stone-100">{s.tone}</span>
                </div>
                <span className="text-xs text-stone-500">{s.intents_created} intent · {new Date(s.last_generated_at).toLocaleString("tr-TR")}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* EMBED */}
      {tab === "embed" && (
        <EmbedTab propertyId={propertyId} />
      )}

      {/* RUNS */}
      {tab === "runs" && (
        <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden" data-testid="chatbot-runs">
          <table className="w-full text-sm">
            <thead className="bg-stone-50 border-b border-stone-200">
              <tr className="text-left text-[11px] uppercase tracking-wider text-stone-600">
                <th className="px-3 py-2.5">Zaman</th>
                <th className="px-3 py-2.5">Mesaj</th>
                <th className="px-3 py-2.5">Eşleşme</th>
                <th className="px-3 py-2.5">Aksiyon</th>
                <th className="px-3 py-2.5">Duygu</th>
              </tr>
            </thead>
            <tbody>
              {runs.length === 0 && <tr><td colSpan={5} className="px-3 py-10 text-center text-stone-400">Henüz çalışma yok. Ayarlar → Canlı Test ile dene.</td></tr>}
              {runs.map((r, idx) => (
                <tr key={r.id} className="border-b border-stone-100">
                  <td className="px-3 py-2 text-xs text-stone-500 font-mono">{new Date(r.created_at).toLocaleString("tr-TR")}</td>
                  <td className="px-3 py-2 text-xs">{r.text?.slice(0, 80)}</td>
                  <td className="px-3 py-2"><span className={`text-[10px] px-1.5 py-0.5 rounded font-bold ${r.match_type === "none" ? "bg-stone-100 text-stone-600" : "bg-emerald-100 text-emerald-700"}`}>{r.match_type}</span></td>
                  <td className="px-3 py-2 text-xs">{r.action_type || "-"}</td>
                  <td className="px-3 py-2 text-xs">{r.sentiment || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

const Row = ({ label, desc, children }) => (
  <div className="flex items-center justify-between gap-3 p-3 rounded-lg bg-stone-50 border border-stone-200">
    <div className="flex-1 min-w-0">
      <div className="text-sm font-semibold text-stone-800">{label}</div>
      <div className="text-xs text-stone-500">{desc}</div>
    </div>
    {children}
  </div>
);

const EmbedTab = ({ propertyId }) => {
  const widgetBase = (process.env.REACT_APP_BACKEND_URL || "").replace(/\/$/, "");
  const widgetUrl = widgetBase + "/chat-widget.html?property_id=" + propertyId + "&api=" + widgetBase;
  const floatingSnippet =
    '<!-- Hotel Guest Chat -->\n' +
    '<div id="hotel-chat-host" style="position:fixed;bottom:20px;right:20px;z-index:9999;"></div>\n' +
    '<script>(function(){\n' +
    '  var host=document.getElementById("hotel-chat-host");\n' +
    '  var btn=document.createElement("button");\n' +
    '  btn.style.cssText="all:unset;cursor:pointer;width:60px;height:60px;border-radius:50%;background:linear-gradient(135deg,#6d28d9,#4f46e5);box-shadow:0 10px 30px rgba(109,40,217,0.4);display:flex;align-items:center;justify-content:center;color:#fff;font-size:28px;";\n' +
    '  btn.innerHTML="\\uD83D\\uDCAC";\n' +
    '  var open=false, frame;\n' +
    '  btn.onclick=function(){\n' +
    '    open=!open;\n' +
    '    if(open){\n' +
    '      frame=document.createElement("iframe");\n' +
    '      frame.src=' + JSON.stringify(widgetUrl) + ';\n' +
    '      frame.style.cssText="position:fixed;bottom:90px;right:20px;width:380px;height:560px;border:0;border-radius:12px;box-shadow:0 12px 40px rgba(0,0,0,0.18);background:#fff;z-index:9998;";\n' +
    '      document.body.appendChild(frame);\n' +
    '    } else if(frame) frame.remove();\n' +
    '  };\n' +
    '  host.appendChild(btn);\n' +
    '})();</script>';
  const inlineSnippet =
    '<iframe\n' +
    '  src="' + widgetUrl + '"\n' +
    '  style="width:380px;height:560px;border:0;border-radius:12px;box-shadow:0 8px 24px rgba(0,0,0,0.12)"\n' +
    '  title="Guest Chat"\n' +
    '></iframe>';
  return (
    <div className="bg-white border border-stone-200 rounded-2xl p-6 space-y-4" data-testid="chatbot-embed">
      <div className="flex items-center gap-2">
        <Code className="w-5 h-5 text-violet-600" />
        <h3 className="font-bold text-stone-900">Embed Widget Kodu</h3>
      </div>
      <p className="text-sm text-stone-600">
        Aşağıdaki kodu otel web sitenizin <code className="bg-stone-100 px-1 rounded">&lt;/body&gt;</code> etiketinden hemen önce yapıştırın.
        Misafirler sağ alt köşede chat balonu görecek.
      </p>

      <div className="p-4 rounded-xl border border-violet-200 bg-violet-50">
        <h4 className="text-xs font-bold text-violet-900 mb-2">Canlı Önizleme</h4>
        <iframe
          data-testid="chatbot-embed-preview"
          title="Chat Widget Preview"
          src={widgetUrl}
          style={{ width: "100%", maxWidth: 380, height: 540, border: 0, borderRadius: 12, background: "#fff" }}
        />
      </div>

      <div>
        <label className="text-xs font-semibold text-stone-700 mb-1.5 block">Floating Bubble (önerilen)</label>
        <pre data-testid="chatbot-embed-snippet" className="bg-stone-900 text-emerald-300 p-3 rounded-lg text-xs font-mono overflow-x-auto whitespace-pre-wrap">{floatingSnippet}</pre>
        <button
          data-testid="chatbot-embed-copy"
          onClick={() => {
            navigator.clipboard.writeText(floatingSnippet);
            toast.success("Kod kopyalandı!");
          }}
          className="mt-2 px-3 py-1.5 bg-violet-600 text-white rounded-lg text-xs font-bold"
        >
          Kodu Kopyala
        </button>
      </div>

      <div>
        <label className="text-xs font-semibold text-stone-700 mb-1.5 block">Inline iframe (sayfa içine doğrudan)</label>
        <pre className="bg-stone-900 text-emerald-300 p-3 rounded-lg text-xs font-mono overflow-x-auto whitespace-pre-wrap">{inlineSnippet}</pre>
      </div>

      <div className="text-xs text-stone-500 space-y-1 p-3 bg-stone-50 rounded-lg border border-stone-200">
        <div>🔓 <b>Public endpoint</b>: <code className="bg-white px-1 rounded">POST /api/public/chatbot/{propertyId}/chat</code></div>
        <div>⚡ Rate limit: 20 mesaj / 5 dakika (session_id başına)</div>
        <div>📝 Çalışmalar <b>Çalışma Geçmişi</b> sekmesinde <code className="bg-white px-1 rounded">source: "widget"</code> ile kayıtlı</div>
      </div>
    </div>
  );
};

export { ChatbotAutomationPanel };
