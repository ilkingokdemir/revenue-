import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import { toast } from "sonner";
import { ChatCircle, PaperPlaneTilt, Hash, Lock, Users, Circle } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/team-chat`;
const POLL_MS = 4000;

export default function TeamChatPanel({ user }) {
  const [channels, setChannels] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [lang, setLang] = useState(() => localStorage.getItem("chat_lang") || "");
  const [translations, setTranslations] = useState({});
  const streamRef = useRef(null);

  const loadChannels = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/channels`, { withCredentials: true });
      setChannels(r.data.channels || []);
      // default to #general or first channel on first load
      setActiveId(prev => {
        if (prev) return prev;
        const list = r.data.channels || [];
        const general = list.find(c => c.name === "general");
        return general?.id || list[0]?.id || null;
      });
    } catch (e) { /* silent */ }
  }, []);

  const loadMessages = useCallback(async () => {
    if (!activeId) return;
    setLoading(true);
    try {
      const r = await axios.get(`${API}/channels/${activeId}/messages`, { withCredentials: true });
      setMessages(r.data.messages || []);
      // Mark read
      await axios.post(`${API}/channels/${activeId}/read`, {}, { withCredentials: true });
    } catch (e) {
      if (e?.response?.status === 403) toast.error("Bu kanala erişim yok");
    } finally {
      setLoading(false);
    }
  }, [activeId]);

  useEffect(() => { loadChannels(); }, [loadChannels]);
  useEffect(() => { loadMessages(); }, [loadMessages]);

  // Canlı çeviri (Flexkeeping dil bariyeri paritesi)
  useEffect(() => {
    if (!lang || !activeId || messages.length === 0) return;
    const missing = messages.some(m => !translations[m.id]);
    if (!missing) return;
    axios.post(`${API}/channels/${activeId}/translate`, { lang }, { withCredentials: true })
      .then(r => setTranslations(t => ({ ...t, ...(r.data.translations || {}) })))
      .catch(() => {});
  }, [lang, activeId, messages]); // eslint-disable-line react-hooks/exhaustive-deps

  const changeLang = (v) => {
    setLang(v);
    setTranslations({});
    if (v) localStorage.setItem("chat_lang", v); else localStorage.removeItem("chat_lang");
    if (v) toast.success(`Canlı çeviri açık: mesajlar ${{ tr: "Türkçe", en: "English", de: "Deutsch", ru: "Русский", ar: "العربية", es: "Español" }[v]} gösterilecek`);
  };

  // Auto-poll
  useEffect(() => {
    const t = setInterval(() => {
      loadChannels();
      loadMessages();
    }, POLL_MS);
    return () => clearInterval(t);
  }, [loadChannels, loadMessages]);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    if (streamRef.current) {
      streamRef.current.scrollTop = streamRef.current.scrollHeight;
    }
  }, [messages, activeId]);

  async function send() {
    const body = draft.trim();
    if (!body || !activeId) return;
    setSending(true);
    try {
      await axios.post(`${API}/channels/${activeId}/messages`, { body }, { withCredentials: true });
      setDraft("");
      loadMessages();
      loadChannels();
    } catch (e) {
      toast.error("Mesaj gönderilemedi");
    } finally { setSending(false); }
  }

  const activeChannel = channels.find(c => c.id === activeId);

  return (
    <div className="flex h-[calc(100vh-180px)] bg-white border border-stone-200 rounded-xl overflow-hidden" data-testid="team-chat-panel">
      {/* Channel list */}
      <aside className="w-64 border-r border-stone-200 bg-stone-50 flex flex-col">
        <div className="px-3 py-3 border-b border-stone-200">
          <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-[0.18em] text-stone-500">
            <ChatCircle size={12} weight="fill" className="text-blue-500" />
            <span>Team Chat</span>
          </div>
          <h2 className="text-sm font-semibold text-stone-900 mt-0.5">Kanallar</h2>
        </div>
        <div className="flex-1 overflow-y-auto py-2" data-testid="chat-channel-list">
          {channels.map(c => {
            const Icon = c.kind === "direct" ? Users : c.kind === "general" ? Hash : c.department ? Hash : Lock;
            const active = c.id === activeId;
            return (
              <button
                key={c.id}
                onClick={() => setActiveId(c.id)}
                className={`w-full px-3 py-1.5 text-left text-xs transition-colors flex items-center gap-2 ${
                  active ? "bg-stone-900 text-white" : "text-stone-600 hover:bg-stone-100"
                }`}
                data-testid={`chat-channel-${c.name}`}
              >
                <Icon size={13} className={active ? "text-white" : "text-stone-400"} />
                <span className="flex-1 truncate">{c.name}</span>
                {c.unread_count > 0 && (
                  <span className={`text-[9px] font-semibold rounded-full px-1.5 py-0.5 ${active ? "bg-white text-stone-900" : "bg-rose-500 text-white"}`} data-testid={`chat-unread-${c.name}`}>
                    {c.unread_count}
                  </span>
                )}
              </button>
            );
          })}
          {channels.length === 0 && (
            <div className="px-3 py-4 text-[11px] text-stone-400">Yükleniyor…</div>
          )}
        </div>
      </aside>

      {/* Message stream */}
      <main className="flex-1 flex flex-col min-w-0">
        {activeChannel ? (
          <>
            <div className="px-5 py-3 border-b border-stone-200">
              <div className="flex items-center gap-2">
                <Hash size={14} className="text-stone-400" />
                <h2 className="text-sm font-semibold text-stone-900">{activeChannel.name}</h2>
                <span className="text-[10px] text-stone-400">{activeChannel.kind}</span>
                <span className="ml-auto flex items-center gap-2">
                  <select value={lang} onChange={e => changeLang(e.target.value)} data-testid="chat-translate-select"
                    className="text-[10px] px-1.5 py-1 border border-stone-200 rounded-lg bg-white text-stone-600">
                    <option value="">🌐 Çeviri kapalı</option>
                    <option value="tr">🌐 Türkçe</option>
                    <option value="en">🌐 English</option>
                    <option value="de">🌐 Deutsch</option>
                    <option value="ru">🌐 Русский</option>
                    <option value="ar">🌐 العربية</option>
                    <option value="es">🌐 Español</option>
                  </select>
                  <span className="flex items-center gap-1 text-[10px] text-stone-400">
                    <Circle size={6} weight="fill" className="text-emerald-500" />
                    Canlı (4sn poll)
                  </span>
                </span>
              </div>
              {activeChannel.description && (
                <p className="text-[11px] text-stone-500 mt-0.5">{activeChannel.description}</p>
              )}
            </div>

            <div ref={streamRef} className="flex-1 overflow-y-auto px-5 py-4 space-y-2.5 bg-stone-50" data-testid="chat-message-stream">
              {loading && messages.length === 0 && (
                <div className="text-center py-8 text-stone-400 text-xs">Yükleniyor…</div>
              )}
              {!loading && messages.length === 0 && (
                <div className="text-center py-8 text-stone-400 text-xs" data-testid="chat-empty">
                  Henüz mesaj yok. İlk yazan sen ol.
                </div>
              )}
              {messages.map((m, i) => {
                const sameAuthor = i > 0 && messages[i - 1].author_id === m.author_id;
                const isMe = m.author_id === (user?.id || user?.email);
                return (
                  <div key={m.id} className={`flex gap-2 ${sameAuthor ? "mt-0.5" : "mt-3"}`} data-testid={`chat-message-${m.id}`}>
                    {!sameAuthor ? (
                      <div className={`w-8 h-8 rounded-full text-[10px] font-semibold inline-flex items-center justify-center shrink-0 ${isMe ? "bg-stone-900 text-white" : "bg-indigo-100 text-indigo-700"}`}>
                        {(m.author_name || "?").slice(0, 2).toUpperCase()}
                      </div>
                    ) : (
                      <div className="w-8 shrink-0" />
                    )}
                    <div className="flex-1 min-w-0">
                      {!sameAuthor && (
                        <div className="flex items-baseline gap-2">
                          <span className="text-xs font-semibold text-stone-800">{m.author_name}</span>
                          <span className="text-[10px] text-stone-400">{new Date(m.created_at).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })}</span>
                          {m.author_role && <span className="text-[9px] px-1 py-0.5 bg-stone-200 text-stone-600 rounded">{m.author_role}</span>}
                        </div>
                      )}
                      <div className="text-sm text-stone-800 whitespace-pre-wrap break-words mt-0.5">
                        {m.body}
                      </div>
                      {lang && translations[m.id] && translations[m.id] !== m.body && (
                        <div className="text-xs text-violet-600 italic whitespace-pre-wrap break-words mt-0.5" data-testid={`chat-translation-${m.id}`}>
                          🌐 {translations[m.id]}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="px-5 py-3 border-t border-stone-200 bg-white">
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder={`#${activeChannel.name} kanalına mesaj yaz…`}
                  value={draft}
                  onChange={e => setDraft(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && !e.shiftKey && (e.preventDefault(), send())}
                  className="flex-1 px-3 py-2 text-sm border border-stone-300 rounded-lg focus:outline-none focus:border-stone-500"
                  data-testid="chat-composer-input"
                />
                <button
                  onClick={send}
                  disabled={!draft.trim() || sending}
                  className="px-4 py-2 text-xs font-medium text-white bg-stone-900 rounded-lg hover:bg-stone-800 disabled:opacity-50 inline-flex items-center gap-1.5"
                  data-testid="chat-send-btn"
                >
                  <PaperPlaneTilt size={14} /> Gönder
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-stone-400 text-sm">
            Soldan bir kanal seç
          </div>
        )}
      </main>
    </div>
  );
}
