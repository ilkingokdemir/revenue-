import { useState, useEffect, useRef } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Inbox, Send, MessageCircle, MessageSquare, Mail, RefreshCw, Search,
  CheckCheck, Plus, X, Sparkles, Loader2,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const CHANNEL_META = {
  whatsapp:   { label: "WhatsApp",     icon: MessageCircle, bg: "bg-emerald-100", fg: "text-emerald-700" },
  sms:        { label: "SMS",          icon: MessageSquare, bg: "bg-sky-100",     fg: "text-sky-700" },
  email:      { label: "Email",        icon: Mail,          bg: "bg-violet-100",  fg: "text-violet-700" },
  booking_com:{ label: "Booking.com",  icon: MessageSquare, bg: "bg-indigo-100",  fg: "text-indigo-700" },
  airbnb:     { label: "Airbnb",       icon: MessageSquare, bg: "bg-rose-100",    fg: "text-rose-700" },
  direct:     { label: "Direct",       icon: MessageSquare, bg: "bg-stone-100",   fg: "text-stone-700" },
};

const formatTime = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  const today = new Date();
  if (d.toDateString() === today.toDateString()) {
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }
  return d.toLocaleDateString([], { month: "short", day: "numeric" });
};

export const UnifiedInboxPanel = () => {
  const [threads, setThreads] = useState([]);
  const [activeKey, setActiveKey] = useState(null);
  const [messages, setMessages] = useState([]);
  const [channel, setChannel] = useState("whatsapp");
  const [draft, setDraft] = useState("");
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [suggesting, setSuggesting] = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const msgsEnd = useRef(null);

  const loadThreads = async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/inbox/threads`);
      setThreads(data || []);
    } catch { toast.error("Failed to load inbox"); }
    setLoading(false);
  };
  const loadMessages = async (key) => {
    try {
      const { data } = await axios.get(`${API}/inbox/threads/${encodeURIComponent(key)}/messages`);
      setMessages(data || []);
      await axios.post(`${API}/inbox/mark-read/${encodeURIComponent(key)}`);
      loadThreads();
      setTimeout(() => msgsEnd.current?.scrollIntoView({ behavior: "smooth" }), 100);
    } catch { toast.error("Failed to load thread"); }
  };
  useEffect(() => { loadThreads(); }, []);

  const pickThread = (t) => { setActiveKey(t.guest_key); loadMessages(t.guest_key); };

  const send = async () => {
    if (!activeKey || !draft.trim()) return;
    try {
      await axios.post(`${API}/inbox/threads/${encodeURIComponent(activeKey)}/send`,
        { channel, body: draft.trim() });
      setDraft("");
      setSuggestions([]);
      loadMessages(activeKey);
    } catch { toast.error("Send failed"); }
  };

  const aiSuggest = async () => {
    if (!activeKey) return;
    setSuggesting(true);
    setSuggestions([]);
    try {
      const { data } = await axios.post(
        `${API}/inbox/threads/${encodeURIComponent(activeKey)}/ai-suggest`,
        { channel, hotel_name: "" }
      );
      setSuggestions(data?.suggestions || []);
      if (data?.fallback) toast.message("AI fallback (no key) — heuristic templates shown");
    } catch (e) { toast.error("AI suggest failed"); }
    setSuggesting(false);
  };

  // --- Demo / test flow helper: send a mock inbound message to seed a thread ---
  const [testOpen, setTestOpen] = useState(false);
  const sendTestInbound = async (payload) => {
    try {
      await axios.post(`${API}/inbox/webhook/${payload.channel}`, payload);
      toast.success("Mock inbound delivered");
      setTestOpen(false);
      loadThreads();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const filtered = q.trim()
    ? threads.filter(t => (t.guest_name || "").toLowerCase().includes(q.toLowerCase())
        || (t.guest_key || "").toLowerCase().includes(q.toLowerCase())
        || (t.last_preview || "").toLowerCase().includes(q.toLowerCase()))
    : threads;

  const activeThread = threads.find(t => t.guest_key === activeKey);

  return (
    <div className="p-6 space-y-4" data-testid="unified-inbox-panel">
      <div className="bg-gradient-to-br from-stone-900 via-slate-900 to-emerald-900 rounded-2xl p-6 text-white shadow-xl">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-emerald-300">
              <Inbox className="w-4 h-4" /> Unified Inbox
            </div>
            <h1 className="text-3xl font-black mt-2">One thread per guest</h1>
            <p className="text-sm text-stone-300 mt-1">WhatsApp · SMS · Email · Booking.com · Airbnb — merged by guest, not by channel</p>
          </div>
          <div className="flex gap-2">
            <button onClick={() => setTestOpen(true)} data-testid="inbox-mock-inbound"
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-white/10 hover:bg-white/20 text-xs font-semibold">
              <Plus className="w-3.5 h-3.5" />Mock Inbound
            </button>
            <button onClick={loadThreads} data-testid="inbox-refresh"
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-white/10 hover:bg-white/20 text-xs font-semibold">
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />Refresh
            </button>
          </div>
        </div>
      </div>

      {/* AI Agent control bar */}
      <AgentBar />

      {/* Split pane — thread list (left) + conversation (right) */}
      <div className="grid grid-cols-[340px_1fr] gap-4 h-[calc(100vh-280px)] min-h-[500px]">
        {/* Threads list */}
        <div className="bg-white border border-stone-200 rounded-xl flex flex-col overflow-hidden">
          <div className="p-3 border-b border-stone-100">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-stone-400" />
              <input value={q} onChange={e => setQ(e.target.value)} placeholder="Search threads…"
                className="w-full pl-9 pr-3 py-2 text-sm border border-stone-200 rounded-lg bg-stone-50"
                data-testid="inbox-search" />
            </div>
          </div>
          <div className="flex-1 overflow-y-auto">
            {filtered.length === 0 && (
              <div className="p-8 text-center text-stone-400 text-sm">
                No threads yet. Use <strong>Mock Inbound</strong> to seed a test conversation, or wire real channel webhooks to <code className="text-[10px] bg-stone-100 px-1 py-0.5 rounded">/api/inbox/webhook/&#123;channel&#125;</code>.
              </div>
            )}
            {filtered.map(t => {
              const m = CHANNEL_META[t.last_channel] || CHANNEL_META.direct;
              const Icon = m.icon;
              return (
                <button key={t.guest_key} onClick={() => pickThread(t)}
                  data-testid={`thread-${t.guest_key}`}
                  className={`w-full text-left p-3 border-b border-stone-50 flex gap-3 transition
                    ${activeKey === t.guest_key ? "bg-emerald-50/70" : "hover:bg-stone-50"}`}>
                  <div className={`w-10 h-10 rounded-full ${m.bg} ${m.fg} flex items-center justify-center flex-shrink-0`}>
                    <Icon className="w-4 h-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-baseline justify-between gap-2">
                      <p className="font-semibold text-sm text-stone-900 truncate">{t.guest_name || t.guest_key}</p>
                      <span className="text-[10px] text-stone-400 flex-shrink-0">{formatTime(t.last_at)}</span>
                    </div>
                    <p className="text-xs text-stone-500 truncate">
                      {t.last_direction === "outbound" ? <CheckCheck className="inline w-3 h-3 mr-1 text-emerald-500" /> : null}
                      {t.last_preview || "—"}
                    </p>
                    <div className="flex items-center gap-1 mt-1">
                      {(t.channels || []).map(c => {
                        const cm = CHANNEL_META[c] || CHANNEL_META.direct;
                        return <span key={c} className={`text-[9px] px-1.5 py-0.5 rounded ${cm.bg} ${cm.fg}`}>{cm.label}</span>;
                      })}
                      {t.unread > 0 && <span className="ml-auto text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-emerald-600 text-white">{t.unread}</span>}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Conversation pane */}
        <div className="bg-white border border-stone-200 rounded-xl flex flex-col overflow-hidden">
          {!activeKey ? (
            <div className="flex-1 flex items-center justify-center text-stone-400 text-sm">
              <div className="text-center">
                <Inbox className="w-12 h-12 mx-auto mb-3 opacity-30" />
                <p>Select a thread to view the conversation</p>
              </div>
            </div>
          ) : (<>
            {/* Thread header */}
            <div className="p-3 border-b border-stone-100 flex items-center justify-between">
              <div>
                <p className="font-semibold text-stone-900">{activeThread?.guest_name || activeKey}</p>
                <p className="text-[11px] text-stone-400">{activeKey}</p>
              </div>
              {(activeThread?.channels || []).map(c => {
                const cm = CHANNEL_META[c] || CHANNEL_META.direct;
                return <span key={c} className={`text-[10px] px-2 py-1 rounded ${cm.bg} ${cm.fg} ml-1`}>{cm.label}</span>;
              })}
            </div>

            {/* Messages — WhatsApp-style bubbles */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-stone-50">
              {messages.map(m => {
                const cm = CHANNEL_META[m.channel] || CHANNEL_META.direct;
                const out = m.direction === "outbound";
                return (
                  <div key={m.id} className={`flex ${out ? "justify-end" : "justify-start"}`}>
                    <div className={`max-w-[65%] rounded-2xl px-3 py-2 text-sm shadow-sm
                      ${out ? "bg-emerald-600 text-white rounded-br-sm" : "bg-white text-stone-800 rounded-bl-sm border border-stone-100"}`}>
                      <div className={`flex items-center gap-1 text-[10px] mb-1 ${out ? "text-emerald-100" : cm.fg}`}>
                        <cm.icon className="w-3 h-3" />
                        <span className="font-semibold">{cm.label}</span>
                        {m.agent && <span className="ml-1 px-1.5 py-0.5 rounded-full bg-violet-500/80 text-white font-bold" data-testid="ai-agent-badge">🤖 AI Agent</span>}
                        {m.needs_human && <span className="ml-1 px-1.5 py-0.5 rounded-full bg-rose-500 text-white font-bold" data-testid="needs-human-badge">İnsana devredildi</span>}
                        <span className={`ml-1 ${out ? "text-emerald-200" : "text-stone-400"}`}>· {formatTime(m.created_at)}</span>
                      </div>
                      <p className="whitespace-pre-wrap leading-relaxed">{m.body}</p>
                    </div>
                  </div>
                );
              })}
              {messages.length === 0 && <p className="text-center text-sm text-stone-400 py-12">No messages in this thread yet.</p>}
              <div ref={msgsEnd} />
            </div>

            {/* Composer */}
            <div className="p-3 border-t border-stone-100 space-y-2">
              <div className="flex items-center gap-2">
                <label className="text-[10px] text-stone-400 uppercase font-bold">Reply via</label>
                <select value={channel} onChange={e => setChannel(e.target.value)} data-testid="inbox-channel-select"
                  className="text-xs border border-stone-200 rounded px-2 py-1 bg-stone-50">
                  {Object.entries(CHANNEL_META).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
                </select>
                <button onClick={aiSuggest} disabled={suggesting} data-testid="inbox-ai-suggest-btn"
                  className="ml-auto flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-bold rounded-lg bg-violet-600 hover:bg-violet-700 text-white disabled:opacity-60">
                  {suggesting ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
                  {suggesting ? "Thinking…" : "AI Suggest"}
                </button>
              </div>
              {suggestions.length > 0 && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-2" data-testid="inbox-suggestions">
                  {suggestions.map((s, i) => (
                    <button key={i} onClick={() => { setDraft(s.body); setSuggestions([]); }}
                      data-testid={`inbox-suggestion-${s.tone || i}`}
                      className="text-left p-2.5 rounded-lg border border-violet-200 bg-violet-50/60 hover:bg-violet-50 hover:border-violet-400 transition">
                      <div className="text-[9px] uppercase font-black tracking-widest text-violet-600 mb-1">{s.tone || `option ${i+1}`}</div>
                      <p className="text-[11px] text-stone-700 line-clamp-4 whitespace-pre-wrap">{s.body}</p>
                    </button>
                  ))}
                </div>
              )}
              <div className="flex gap-2">
                <textarea value={draft} onChange={e => setDraft(e.target.value)}
                  onKeyDown={e => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) send(); }}
                  placeholder="Type your reply… (⌘/Ctrl+Enter to send)" rows={2}
                  data-testid="inbox-draft"
                  className="flex-1 border border-stone-200 rounded-lg px-3 py-2 text-sm resize-none" />
                <button onClick={send} disabled={!draft.trim()} data-testid="inbox-send-btn"
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:bg-stone-300 text-white rounded-lg text-sm font-semibold flex items-center gap-1.5">
                  <Send className="w-3.5 h-3.5" />Send
                </button>
              </div>
            </div>
          </>)}
        </div>
      </div>

      {/* Mock Inbound — quick way to seed threads without real channel providers */}
      {testOpen && <MockInboundModal onClose={() => setTestOpen(false)} onSend={sendTestInbound} />}
    </div>
  );
};

const AgentBar = () => {
  const [cfg, setCfg] = useState(null);
  const [stats, setStats] = useState(null);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    try {
      const [c, s] = await Promise.all([
        axios.get(`${API}/inbox/agent/config`),
        axios.get(`${API}/inbox/agent/stats?days=7`),
      ]);
      setCfg(c.data);
      setStats(s.data);
    } catch { /* silent */ }
  };
  useEffect(() => { load(); }, []);

  const update = async (patch) => {
    setSaving(true);
    try {
      const { data } = await axios.put(`${API}/inbox/agent/config`, patch);
      setCfg(data);
      toast.success(patch.enabled !== undefined ? (patch.enabled ? "AI Agent açıldı — basit sorular otonom cevaplanacak" : "AI Agent kapatıldı") : "Eşik güncellendi");
    } catch (e) { toast.error(e?.response?.data?.detail || "Güncellenemedi"); }
    setSaving(false);
  };

  if (!cfg) return null;
  return (
    <div className="bg-white border border-violet-200 rounded-xl p-3 flex items-center gap-4 flex-wrap" data-testid="inbox-agent-bar">
      <button onClick={() => update({ enabled: !cfg.enabled })} disabled={saving} data-testid="agent-toggle-btn"
        className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold transition
          ${cfg.enabled ? "bg-violet-600 text-white" : "bg-stone-100 text-stone-500 hover:bg-stone-200"}`}>
        <Sparkles className="w-3.5 h-3.5" />
        AI Agent: {cfg.enabled ? "AÇIK" : "KAPALI"}
      </button>
      <div className="flex items-center gap-1.5 text-xs text-stone-600">
        <span>Güven eşiği:</span>
        <input type="number" min={40} max={95} defaultValue={cfg.threshold} data-testid="agent-threshold-input"
          onBlur={e => { const v = parseInt(e.target.value); if (v >= 40 && v <= 95 && v !== cfg.threshold) update({ threshold: v }); }}
          className="w-16 px-2 py-1 border border-stone-200 rounded text-center" />
        <span className="text-stone-400">%</span>
      </div>
      {stats && (
        <div className="ml-auto flex items-center gap-4 text-xs" data-testid="agent-stats">
          <span className="text-violet-700 font-semibold">🤖 {stats.auto_replied} otonom cevap</span>
          <span className="text-rose-600 font-semibold">{stats.escalated} insana devir</span>
          <span className="text-stone-400">otomasyon %{stats.automation_rate} (7g)</span>
        </div>
      )}
      <p className="w-full text-[11px] text-stone-400 -mt-1">Basit misafir soruları (WiFi, kahvaltı, check-in saati) chatbot FAQ bilgi tabanından otonom cevaplanır; hassas konular veya düşük güven skorunda konuşma insana devredilir.</p>
    </div>
  );
};

const MockInboundModal = ({ onClose, onSend }) => {
  const [channel, setChannel] = useState("whatsapp");
  const [guestKey, setGuestKey] = useState("");
  const [guestName, setGuestName] = useState("");
  const [body, setBody] = useState("");

  const submit = () => {
    if (!guestKey.trim() || !body.trim()) return toast.error("guest_key and body required");
    onSend({
      channel,
      guest_key: guestKey.trim(),
      guest_name: guestName.trim() || guestKey.trim(),
      from: guestKey.trim(),
      body: body.trim(),
    });
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl p-6 w-full max-w-md" onClick={e => e.stopPropagation()} data-testid="mock-inbound-modal">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-stone-900">Mock Inbound Message</h2>
          <button onClick={onClose} className="p-1 hover:bg-stone-100 rounded-lg"><X className="w-4 h-4 text-stone-500" /></button>
        </div>
        <p className="text-xs text-stone-500 mb-3">Simulates an inbound webhook call. In production, your WhatsApp/SMS/email provider POSTs to <code className="text-[10px] bg-stone-100 px-1 py-0.5 rounded">/api/inbox/webhook/&#123;channel&#125;</code>.</p>
        <div className="space-y-3">
          <div>
            <label className="block text-[10px] font-bold uppercase text-stone-500 mb-1">Channel</label>
            <select value={channel} onChange={e => setChannel(e.target.value)} data-testid="mock-channel"
              className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm">
              {Object.entries(CHANNEL_META).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-[10px] font-bold uppercase text-stone-500 mb-1">Guest Key (email/phone)</label>
            <input value={guestKey} onChange={e => setGuestKey(e.target.value)}
              placeholder="+44 7700 900123 or jane@example.com"
              data-testid="mock-guest-key"
              className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-[10px] font-bold uppercase text-stone-500 mb-1">Guest Name</label>
            <input value={guestName} onChange={e => setGuestName(e.target.value)}
              className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-[10px] font-bold uppercase text-stone-500 mb-1">Message body</label>
            <textarea value={body} onChange={e => setBody(e.target.value)} rows={3} data-testid="mock-body"
              className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" />
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-4">
          <button onClick={onClose} className="px-4 py-2 text-sm">Cancel</button>
          <button onClick={submit} data-testid="mock-send" className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-sm font-semibold">Send Mock Inbound</button>
        </div>
      </div>
    </div>
  );
};

export default UnifiedInboxPanel;
