import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Headset, MessageSquare, X, Send, RefreshCw, Inbox, Bell, BellOff } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const auth = () => ({ Authorization: `Bearer ${localStorage.getItem("access_token")}` });

// Tiny "ding" sound generator via Web Audio API — no asset file needed.
let _audioCtx = null;
const playDing = () => {
  try {
    if (!_audioCtx) _audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const ctx = _audioCtx;
    const now = ctx.currentTime;
    // Two-tone bell: C6 (1046Hz) → E6 (1318Hz)
    [1046.5, 1318.5].forEach((freq, i) => {
      const o = ctx.createOscillator();
      const g = ctx.createGain();
      o.type = "sine";
      o.frequency.value = freq;
      g.gain.setValueAtTime(0.0001, now + i * 0.12);
      g.gain.exponentialRampToValueAtTime(0.22, now + i * 0.12 + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, now + i * 0.12 + 0.35);
      o.connect(g); g.connect(ctx.destination);
      o.start(now + i * 0.12); o.stop(now + i * 0.12 + 0.4);
    });
  } catch (e) { /* silent */ }
};

const LiveChatInboxPanel = ({ propertyId }) => {
  const [sessions, setSessions] = useState([]);
  const [active, setActive] = useState(null);
  const [thread, setThread] = useState([]);
  const [reply, setReply] = useState("");
  const [statusFilter, setStatusFilter] = useState("active");
  const [busy, setBusy] = useState(false);
  const [notifPerm, setNotifPerm] = useState(typeof Notification !== "undefined" ? Notification.permission : "denied");
  const bottomRef = useRef(null);
  const pollRef = useRef(null);
  const lastSnapRef = useRef({ unreadTotal: 0, sessionIds: new Set() });

  const loadSessions = useCallback(async () => {
    if (!propertyId || propertyId === "all") return;
    try {
      const r = await axios.get(`${API}/chatbot/${propertyId}/handoff/sessions`, {
        params: { status: statusFilter }, headers: auth(),
      });
      const items = r.data.items || [];
      setSessions(items);

      // Detect change → notify
      const activeOnly = items.filter(s => s.status === "active");
      const newUnreadTotal = activeOnly.reduce((a, s) => a + (s.unread_count || 0), 0);
      const currentIds = new Set(activeOnly.map(s => s.session_id));
      const newSession = [...currentIds].find(id => !lastSnapRef.current.sessionIds.has(id));
      const unreadIncreased = newUnreadTotal > lastSnapRef.current.unreadTotal;

      if (lastSnapRef.current.sessionIds.size > 0 && (newSession || unreadIncreased)) {
        playDing();
        if (typeof Notification !== "undefined" && Notification.permission === "granted") {
          const body = newSession
            ? "Yeni canlı destek talebi geldi"
            : `${newUnreadTotal} okunmamış mesaj`;
          try {
            const n = new Notification("🔔 Live Chat", { body, tag: "handoff", icon: "/favicon.ico" });
            n.onclick = () => { window.focus(); n.close(); };
          } catch (_) { /* notification API failed silently */ }
        }
      }
      lastSnapRef.current = { unreadTotal: newUnreadTotal, sessionIds: currentIds };
    } catch (e) { /* silent during poll */ }
  }, [propertyId, statusFilter]);

  const loadThread = useCallback(async (session_id) => {
    if (!session_id) return;
    try {
      const r = await axios.get(
        `${API}/chatbot/${propertyId}/handoff/sessions/${session_id}/messages`,
        { headers: auth() }
      );
      setThread(r.data.messages || []);
      setActive(r.data.session || { session_id });
      setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
    } catch (e) { toast.error("Mesajlar yüklenemedi"); }
  }, [propertyId]);

  // Initial load + 5s sessions poll
  useEffect(() => { loadSessions(); }, [loadSessions]);
  useEffect(() => {
    if (!propertyId || propertyId === "all") return;
    const t = setInterval(loadSessions, 5000);
    return () => clearInterval(t);
  }, [propertyId, loadSessions]);

  // Active thread polling
  useEffect(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    if (!active?.session_id) return;
    pollRef.current = setInterval(() => loadThread(active.session_id), 4000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [active?.session_id, loadThread]);

  const sendReply = async () => {
    if (!reply.trim() || !active) return;
    setBusy(true);
    try {
      await axios.post(
        `${API}/chatbot/${propertyId}/handoff/sessions/${active.session_id}/reply`,
        { text: reply }, { headers: auth() }
      );
      setReply("");
      await loadThread(active.session_id);
    } catch (e) { toast.error("Gönderilemedi"); }
    setBusy(false);
  };

  const closeSession = async () => {
    if (!active) return;
    if (!window.confirm("Bu görüşmeyi kapatmak istediğine emin misin?")) return;
    try {
      await axios.post(
        `${API}/chatbot/${propertyId}/handoff/sessions/${active.session_id}/close`,
        {}, { headers: auth() }
      );
      toast.success("Görüşme kapatıldı");
      setActive(null); setThread([]);
      loadSessions();
    } catch { toast.error("Kapatılamadı"); }
  };

  if (!propertyId || propertyId === "all") {
    return (
      <div className="bg-white border border-stone-200 rounded-2xl p-6" data-testid="live-chat-empty">
        <div className="flex items-center gap-3"><Headset className="w-6 h-6 text-emerald-600" />
          <p className="text-stone-600">Live Chat Inbox için lütfen bir otel seçin.</p>
        </div>
      </div>
    );
  }

  const activeCount = sessions.filter(s => s.status === "active").length;
  const totalUnread = sessions.reduce((a, s) => a + (s.unread_count || 0), 0);

  return (
    <div className="space-y-4" data-testid="live-chat-panel">
      {/* HEADER */}
      <div className="relative overflow-hidden rounded-2xl border border-emerald-200 bg-gradient-to-br from-emerald-600 via-teal-600 to-cyan-600 p-5 text-white">
        <div className="absolute -top-12 -right-12 w-48 h-48 bg-white/10 rounded-full blur-3xl"></div>
        <div className="relative flex items-start justify-between gap-4 flex-wrap">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Headset className="w-5 h-5" />
              <span className="text-xs uppercase tracking-widest font-bold opacity-80">Guest Experience · Live Chat</span>
            </div>
            <h2 className="text-2xl font-bold">Canlı Destek Inbox</h2>
            <p className="text-sm opacity-85 mt-1">Handoff olan misafirleri yanıtla · Gerçek zamanlı</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right">
              <div className="text-2xl font-bold tabular-nums">{activeCount}</div>
              <div className="text-[10px] opacity-80">aktif görüşme</div>
            </div>
            <div className="text-right">
              <div className="text-2xl font-bold tabular-nums">{totalUnread}</div>
              <div className="text-[10px] opacity-80">okunmamış</div>
            </div>
            <button data-testid="live-refresh" onClick={loadSessions} className="px-3 py-2 bg-white/15 hover:bg-white/25 rounded-lg text-sm font-medium flex items-center gap-2">
              <RefreshCw className="w-4 h-4" /> Yenile
            </button>
            {typeof Notification !== "undefined" && (
              <button
                data-testid="live-notif-toggle"
                onClick={async () => {
                  if (notifPerm === "granted") {
                    toast.info("Bildirimler tarayıcı ayarlarından kapatılabilir");
                    playDing(); // demo
                    return;
                  }
                  try {
                    const p = await Notification.requestPermission();
                    setNotifPerm(p);
                    if (p === "granted") { playDing(); toast.success("Bildirimler açıldı"); }
                    else toast.warning("Bildirim izni reddedildi");
                  } catch { toast.error("Bildirim isteği başarısız"); }
                }}
                className="px-3 py-2 bg-white/15 hover:bg-white/25 rounded-lg text-sm font-medium flex items-center gap-2"
                title={notifPerm === "granted" ? "Bildirimler aktif (test için tıkla)" : "Browser bildirimleri aç"}
              >
                {notifPerm === "granted" ? <Bell className="w-4 h-4" /> : <BellOff className="w-4 h-4" />}
                {notifPerm === "granted" ? "Sesli" : "Bildirimi Aç"}
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 min-h-[560px]">
        {/* SESSION LIST */}
        <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden flex flex-col" data-testid="live-sessions-list">
          <div className="p-3 border-b border-stone-100 flex items-center gap-2">
            <Inbox className="w-4 h-4 text-stone-500" />
            <h4 className="text-sm font-bold text-stone-800 flex-1">Oturumlar</h4>
            <div className="flex gap-1">
              {["active", "closed", "all"].map(s => (
                <button key={s} onClick={() => setStatusFilter(s)}
                  className={`text-[10px] px-2 py-0.5 rounded ${statusFilter === s ? "bg-emerald-600 text-white" : "bg-stone-100 text-stone-600"}`}
                  data-testid={`live-filter-${s}`}>
                  {s === "active" ? "aktif" : s === "closed" ? "kapalı" : "tümü"}
                </button>
              ))}
            </div>
          </div>
          <div className="flex-1 overflow-y-auto max-h-[520px]">
            {sessions.length === 0 && (
              <div className="p-8 text-center text-stone-400 text-sm">
                <MessageSquare className="w-8 h-8 mx-auto mb-2 opacity-30" />
                Henüz handoff yok
              </div>
            )}
            {sessions.map((s, idx) => (
              <button key={s.id} onClick={() => loadThread(s.session_id)}
                data-testid={`live-session-${idx}`}
                className={`w-full text-left p-3 border-b border-stone-100 hover:bg-stone-50 transition ${active?.session_id === s.session_id ? "bg-emerald-50" : ""}`}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-mono text-stone-500 truncate" title={s.session_id}>{s.session_id.slice(0, 14)}…</span>
                  {s.unread_count > 0 && (
                    <span className="text-[10px] bg-rose-600 text-white px-1.5 py-0.5 rounded-full font-bold">{s.unread_count}</span>
                  )}
                </div>
                <div className="text-xs text-stone-700 truncate">{s.last_message_text || "—"}</div>
                <div className="flex items-center justify-between mt-1">
                  <span className={`text-[10px] px-1.5 py-0.5 rounded ${s.status === "active" ? "bg-emerald-100 text-emerald-700" : "bg-stone-100 text-stone-500"}`}>{s.status}</span>
                  <span className="text-[10px] text-stone-400">{s.last_message_at ? new Date(s.last_message_at).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" }) : ""}</span>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* THREAD */}
        <div className="lg:col-span-2 bg-white border border-stone-200 rounded-2xl flex flex-col overflow-hidden" data-testid="live-thread">
          {!active && (
            <div className="flex-1 flex items-center justify-center text-stone-400 text-sm">
              <div className="text-center">
                <Headset className="w-10 h-10 mx-auto mb-2 opacity-30" />
                Sol panelden bir görüşme seç
              </div>
            </div>
          )}
          {active && (
            <>
              <div className="p-3 border-b border-stone-100 flex items-center justify-between">
                <div>
                  <div className="font-mono text-xs text-stone-500 truncate">{active.session_id}</div>
                  <div className="text-[10px] text-stone-400">
                    Açıldı: {active.started_at ? new Date(active.started_at).toLocaleString("tr-TR") : "—"}
                    {active.reason && <span> · {active.reason}</span>}
                  </div>
                </div>
                {active.status === "active" && (
                  <button data-testid="live-close-btn" onClick={closeSession} className="text-xs px-2 py-1 rounded border border-rose-200 text-rose-700 hover:bg-rose-50">
                    <X className="w-3 h-3 inline-block mr-1" /> Kapat
                  </button>
                )}
              </div>
              <div className="flex-1 overflow-y-auto p-4 space-y-2 bg-stone-50 max-h-[420px]">
                {thread.map((m, i) => {
                  const isStaff = m.sender === "staff";
                  const isSys = m.sender === "system";
                  return (
                    <div key={m.id} className={`flex ${isStaff ? "justify-end" : "justify-center"}`}>
                      {isSys ? (
                        <div className="text-[10px] px-2 py-1 rounded bg-amber-50 text-amber-700 border border-amber-100">{m.text}</div>
                      ) : (
                        <div className={`max-w-[75%] p-2.5 rounded-xl text-sm ${isStaff ? "bg-emerald-600 text-white rounded-br-sm" : "bg-white border border-stone-200 text-stone-800 rounded-bl-sm"}`}>
                          <div className="text-[10px] opacity-70 mb-0.5">{isStaff ? (m.sender_name || "Sen") : "Misafir"} · {new Date(m.created_at).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })}</div>
                          {m.text}
                        </div>
                      )}
                    </div>
                  );
                })}
                <div ref={bottomRef} />
              </div>
              {active.status === "active" && (
                <div className="p-3 border-t border-stone-100 flex gap-2">
                  <input
                    data-testid="live-reply-input"
                    value={reply}
                    onChange={(e) => setReply(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && (e.preventDefault(), sendReply())}
                    placeholder="Yanıt yaz… (Enter)"
                    className="flex-1 px-3 py-2 border border-stone-200 rounded-lg text-sm focus:outline-none focus:border-emerald-500"
                  />
                  <button data-testid="live-reply-btn" onClick={sendReply} disabled={busy || !reply.trim()}
                    className="px-3 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-sm font-bold flex items-center gap-1 disabled:opacity-50">
                    <Send className="w-3.5 h-3.5" /> Gönder
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export { LiveChatInboxPanel };
export default LiveChatInboxPanel;
