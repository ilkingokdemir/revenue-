/**
 * HousekeepingMobilePWA — Mews-parity Batch 3 F3 (iter 360)
 * ---------------------------------------------------------
 * Mobile-first PWA (public route: /hk-mobile/:propertyId) for housekeeping
 * staff. Big-tap buttons, offline-tolerant, staff auth via existing token.
 *
 * Screens:
 *   Login (if not authenticated)
 *   Stats hero (dirty/in_progress/clean/inspected)
 *   Filter bar (dirty · in_progress · clean · all)
 *   Room list — tap → detail sheet with status transition buttons
 */
import { useEffect, useState, useCallback, useRef } from "react";
import axios from "axios";
import { toast, Toaster } from "sonner";
import {
  Loader2, ChevronRight, LogOut, RefreshCcw, CheckCircle2, Sparkles, Wrench,
  ClipboardCheck, Bed, XCircle, Mic, Square, Send,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STATUS_META = {
  dirty:        { emoji: "🧹", label: "Kirli",     ring: "ring-rose-500",    bg: "bg-rose-50",     text: "text-rose-700",    border: "border-rose-200" },
  in_progress:  { emoji: "🧽", label: "Temizleniyor", ring: "ring-amber-500", bg: "bg-amber-50",   text: "text-amber-700",   border: "border-amber-200" },
  clean:        { emoji: "✨", label: "Temiz",      ring: "ring-emerald-500", bg: "bg-emerald-50", text: "text-emerald-700", border: "border-emerald-200" },
  inspected:    { emoji: "✅", label: "Onaylandı",  ring: "ring-sky-500",    bg: "bg-sky-50",      text: "text-sky-700",     border: "border-sky-200" },
  out_of_order: { emoji: "🚫", label: "Arızalı",    ring: "ring-stone-500",  bg: "bg-stone-100",   text: "text-stone-700",   border: "border-stone-300" },
};

const TRANSITIONS = [
  { from: "dirty",       to: "in_progress", label: "Temizliğe Başla" },
  { from: "in_progress", to: "clean",       label: "Temiz Bitirdim" },
  { from: "clean",       to: "inspected",   label: "Onayla" },
  { from: "inspected",   to: "dirty",       label: "Kirli Olarak İşaretle" },
];

export default function HousekeepingMobilePWA() {
  const propertyId = (() => {
    const parts = window.location.pathname.split("/").filter(Boolean);
    return parts[0] === "hk-mobile" ? parts[1] || "" : "";
  })();

  const [authToken, setAuthToken] = useState(() => localStorage.getItem("access_token") || "");
  const [rooms, setRooms] = useState([]);
  const [stats, setStats] = useState(null);
  const [filter, setFilter] = useState("dirty");
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loginErr, setLoginErr] = useState(null);
  const [loginForm, setLoginForm] = useState({ email: "", password: "" });
  const [online, setOnline] = useState(navigator.onLine);
  const QKEY = `hk-queue-${propertyId}`; const CKEY = `hk-cache-${propertyId}`;
  const [queue, setQueue] = useState(() => { try { return JSON.parse(localStorage.getItem(QKEY) || "[]"); } catch { return []; } });
  const [syncing, setSyncing] = useState(false);
  const [issueQueueN, setIssueQueueN] = useState(() => readIssueQueue(propertyId).length);
  const [cachedAt, setCachedAt] = useState(null);
  const saveQueue = (q) => { setQueue(q); localStorage.setItem(QKEY, JSON.stringify(q)); };

  useEffect(() => {
    if (authToken) {
      axios.defaults.headers.common["Authorization"] = `Bearer ${authToken}`;
    }
  }, [authToken]);

  useEffect(() => {
    const on = () => setOnline(true); const off = () => setOnline(false);
    window.addEventListener("online", on); window.addEventListener("offline", off);
    return () => { window.removeEventListener("online", on); window.removeEventListener("offline", off); };
  }, []);

  const computeStats = (list) => ({ total: list.length, dirty: list.filter(r => r.status === "dirty").length, in_progress: list.filter(r => r.status === "in_progress").length,
    clean: list.filter(r => r.status === "clean").length, inspected: list.filter(r => r.status === "inspected").length });

  const load = useCallback(async () => {
    if (!propertyId || !authToken) return;
    setLoading(true);
    try {
      const [rs, st] = await Promise.all([
        axios.get(`${API}/housekeeping/rooms/${propertyId}`, { timeout: 8000 }),
        axios.get(`${API}/housekeeping/rooms/${propertyId}/stats`, { timeout: 8000 }),
      ]);
      let q = []; try { q = JSON.parse(localStorage.getItem(QKEY) || "[]"); } catch { q = []; }
      const merged = (rs.data || []).map(r => { const p = q.find(i => i.room_id === r.id); return p ? { ...r, status: p.to, _pending: true } : r; });
      setRooms(merged); setStats(q.length ? computeStats(merged) : st.data); setCachedAt(null);
      localStorage.setItem(CKEY, JSON.stringify({ rooms: merged, stats: q.length ? computeStats(merged) : st.data, at: new Date().toISOString() }));
    } catch (e) {
      if (e.response?.status === 401) {
        setAuthToken(""); localStorage.removeItem("access_token");
      } else {
        try {
          const c = JSON.parse(localStorage.getItem(CKEY) || "null");
          if (c) { setRooms(c.rooms); setStats(c.stats); setCachedAt(c.at); toast("Çevrimdışı — önbellekten gösteriliyor", { icon: "📴" }); }
          else toast.error("Yüklenemedi");
        } catch { toast.error("Yüklenemedi"); }
      }
    } finally { setLoading(false); }
  }, [propertyId, authToken, CKEY, QKEY]);

  useEffect(() => { load(); }, [load]);

  const sync = useCallback(async () => {
    if (!navigator.onLine || syncing) return;
    let q = []; try { q = JSON.parse(localStorage.getItem(QKEY) || "[]"); } catch { q = []; }
    if (!q.length) return;
    setSyncing(true);
    let ok = 0, conflicts = 0;
    for (const item of q) {
      try {
        await axios.put(`${API}/housekeeping/rooms/${item.room_id}/status`, { status: item.to, base_updated_at: item.base_updated_at, offline_queued_at: item.at }, { timeout: 8000 });
        ok++;
      } catch (e) {
        if (e.response?.status === 409) { conflicts++; toast(`Oda ${item.room_number}: başka biri değiştirdi (${STATUS_META[e.response.data?.current?.status]?.label || "?"})`, { icon: "⚠️" }); }
        else if (!e.response) { setSyncing(false); return; }
      }
      q = q.slice(1); localStorage.setItem(QKEY, JSON.stringify(q)); setQueue(q);
    }
    setSyncing(false);
    if (ok) toast.success(`${ok} değişiklik senkronize edildi${conflicts ? `, ${conflicts} çakışma` : ""}`);
    load();
  }, [QKEY, syncing, load]);

  useEffect(() => { if (online && authToken) sync(); }, [online, authToken, sync]);

  const syncIssues = useCallback(async () => {
    if (!navigator.onLine) return;
    let q = readIssueQueue(propertyId);
    if (!q.length) return;
    let ok = 0;
    for (const it of q) {
      try {
        await axios.post(`${API}/maintenance/issues`, { ...it.payload, offline_reported_at: it.at }, { timeout: 15000 }); ok++;
      } catch (e) { if (!e.response) break; }
      q = q.slice(1); localStorage.setItem(`hk-issues-${propertyId}`, JSON.stringify(q)); setIssueQueueN(q.length);
    }
    if (ok) toast.success(`${ok} arıza bildirimi gönderildi`);
  }, [propertyId]);
  useEffect(() => { if (online && authToken) syncIssues(); }, [online, authToken, syncIssues]);

  const login = async () => {
    setBusy(true); setLoginErr(null);
    try {
      const r = await axios.post(`${API}/auth/login`, loginForm);
      const tok = r.data.token || r.data.access_token;
      localStorage.setItem("access_token", tok); setAuthToken(tok);
    } catch (e) {
      setLoginErr(e.response?.data?.detail || "Giriş başarısız");
    } finally { setBusy(false); }
  };

  const applyLocal = (room, to) => {
    const next = rooms.map(r => (r.id === room.id ? { ...r, status: to, _pending: true } : r));
    setRooms(next); setStats(computeStats(next));
    localStorage.setItem(CKEY, JSON.stringify({ rooms: next, stats: computeStats(next), at: new Date().toISOString() }));
  };
  const enqueue = (room, to) => {
    const q = queue.filter(i => i.room_id !== room.id).concat([{ room_id: room.id, room_number: room.room_number, to, base_updated_at: room.updated_at || "", at: new Date().toISOString() }]);
    saveQueue(q); applyLocal(room, to);
    toast(`Oda ${room.room_number} → ${STATUS_META[to]?.label || to} (kuyrukta, bağlantı gelince gönderilir)`, { icon: "📴" });
  };

  const transition = async (room, to) => {
    setBusy(true);
    try {
      if (!navigator.onLine) { enqueue(room, to); setSelected(null); return; }
      await axios.put(`${API}/housekeeping/rooms/${room.id}/status`, { status: to, base_updated_at: room.updated_at || "" }, { timeout: 8000 });
      toast.success(`Oda ${room.room_number} → ${STATUS_META[to]?.label || to}`);
      setSelected(null); await load();
    } catch (e) {
      if (e.response?.status === 409) { toast(`Oda ${room.room_number} başka biri tarafından değiştirildi — liste yenilendi`, { icon: "⚠️" }); setSelected(null); await load(); }
      else if (!e.response) { enqueue(room, to); setSelected(null); }
      else toast.error("Değiştirilemedi");
    } finally { setBusy(false); }
  };

  // ── Login screen ────────────────────────────────────────────────────
  if (!authToken) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-cyan-600 to-teal-800 flex items-center justify-center p-6" data-testid="hk-mobile-login">
        <Toaster position="top-center" />
        <div className="w-full max-w-sm bg-white rounded-3xl shadow-2xl p-6">
          <div className="text-center mb-6">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-cyan-500 to-teal-600 mx-auto flex items-center justify-center shadow-lg mb-3">
              <Sparkles className="w-8 h-8 text-white" />
            </div>
            <h1 className="text-2xl font-black text-stone-900">Housekeeping</h1>
            <p className="text-xs text-stone-500 mt-1">Mobil personel uygulaması</p>
          </div>
          <div className="space-y-3">
            <input
              type="email" placeholder="E-mail" value={loginForm.email}
              onChange={e => setLoginForm(f => ({ ...f, email: e.target.value }))}
              data-testid="hk-login-email"
              className="w-full px-4 py-3 rounded-xl border-2 border-stone-200 focus:border-cyan-500 outline-none text-base"
            />
            <input
              type="password" placeholder="Şifre" value={loginForm.password}
              onChange={e => setLoginForm(f => ({ ...f, password: e.target.value }))}
              data-testid="hk-login-password"
              className="w-full px-4 py-3 rounded-xl border-2 border-stone-200 focus:border-cyan-500 outline-none text-base"
            />
            {loginErr && <p className="text-sm text-rose-600 font-bold">{loginErr}</p>}
            <button
              onClick={login} disabled={busy || !loginForm.email || !loginForm.password}
              data-testid="hk-login-btn"
              className="w-full py-3.5 rounded-xl bg-cyan-500 hover:bg-cyan-600 text-white font-black disabled:opacity-40 inline-flex items-center justify-center gap-2"
            >
              {busy && <Loader2 className="w-4 h-4 animate-spin" />} Giriş Yap
            </button>
          </div>
        </div>
      </div>
    );
  }

  const filtered = filter === "all" ? rooms : rooms.filter(r => r.status === filter);

  return (
    <div className="min-h-screen bg-stone-100 pb-20" data-testid="hk-mobile-pwa">
      <Toaster position="top-center" />
      {/* Sticky header */}
      <header className="sticky top-0 z-30 bg-gradient-to-r from-cyan-600 to-teal-700 shadow-lg px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-white" />
          <h1 className="text-base font-black text-white">Housekeeping</h1>
        </div>
        <div className="flex items-center gap-1">
          <button onClick={load} disabled={loading} data-testid="hk-refresh" className="p-2 rounded-lg bg-white/10 text-white active:bg-white/20">
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCcw className="w-4 h-4" />}
          </button>
          <button
            onClick={() => { localStorage.removeItem("access_token"); setAuthToken(""); }}
            data-testid="hk-logout"
            className="p-2 rounded-lg bg-white/10 text-white active:bg-white/20"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </header>

      {issueQueueN > 0 && (
        <div className="px-3 py-1.5 text-[11px] font-bold bg-rose-100 text-rose-900 flex items-center justify-between" data-testid="hk-issue-queue-bar">
          <span>🔧 {issueQueueN} arıza bildirimi gönderilmeyi bekliyor</span>
          {online && <button onClick={syncIssues} className="px-2 py-0.5 rounded bg-rose-700 text-white" data-testid="hk-issue-sync-now">Gönder</button>}
        </div>
      )}
      {(!online || queue.length > 0 || cachedAt) && (
        <div className={`px-3 py-2 text-xs font-bold flex items-center justify-between gap-2 ${!online ? "bg-amber-400 text-amber-950" : "bg-sky-100 text-sky-900"}`} data-testid="hk-offline-bar">
          <span data-testid="hk-offline-text">
            {!online ? `📴 Çevrimdışı — değişiklikler cihazda saklanıyor (${queue.length} bekleyen)` : syncing ? "🔄 Senkronize ediliyor…" : queue.length ? `🟢 Bağlantı var — ${queue.length} bekleyen değişiklik` : `Önbellek: ${new Date(cachedAt).toLocaleTimeString("tr-TR")}`}
          </span>
          {online && queue.length > 0 && !syncing && <button onClick={sync} className="px-2.5 py-1 rounded-lg bg-sky-700 text-white" data-testid="hk-sync-now">Şimdi senkronize et</button>}
        </div>
      )}

      {/* Stats grid */}
      {stats && (
        <div className="grid grid-cols-4 gap-1.5 px-3 pt-3" data-testid="hk-stats">
          {[
            ["dirty", stats.dirty, "🧹"],
            ["in_progress", stats.in_progress, "🧽"],
            ["clean", stats.clean, "✨"],
            ["inspected", stats.inspected, "✅"],
          ].map(([key, val, emoji]) => {
            const meta = STATUS_META[key];
            const active = filter === key;
            return (
              <button
                key={key}
                onClick={() => setFilter(key)}
                data-testid={`hk-filter-${key}`}
                className={`rounded-xl border-2 p-2 text-center transition-all active:scale-95 ${active ? `${meta.ring} ring-2 ${meta.bg}` : "bg-white border-stone-200"}`}
              >
                <p className="text-xl">{emoji}</p>
                <p className={`text-xl font-black ${active ? meta.text : "text-stone-900"}`}>{val}</p>
                <p className="text-[9px] text-stone-500 font-bold uppercase">{meta.label}</p>
              </button>
            );
          })}
        </div>
      )}

      {/* Filter chip: all */}
      <div className="px-3 mt-2 flex items-center gap-2">
        <button
          onClick={() => setFilter("all")}
          data-testid="hk-filter-all"
          className={`text-[11px] px-2.5 py-1 rounded-full font-bold ${filter === "all" ? "bg-stone-900 text-white" : "bg-white text-stone-600 border border-stone-200"}`}
        >
          Tümü ({stats?.total || 0})
        </button>
        <p className="text-[10px] text-stone-500 ml-auto">{filtered.length} oda gösteriliyor</p>
      </div>

      {/* Room list */}
      <div className="px-3 mt-3 space-y-2" data-testid="hk-room-list">
        {loading && <div className="text-center py-8"><Loader2 className="w-6 h-6 animate-spin text-stone-400 mx-auto" /></div>}
        {!loading && filtered.length === 0 && (
          <div className="text-center py-12">
            <CheckCircle2 className="w-12 h-12 text-emerald-400 mx-auto mb-2" />
            <p className="text-sm font-bold text-stone-600">Bu kategoride oda yok!</p>
          </div>
        )}
        {filtered.map(room => {
          const meta = STATUS_META[room.status] || STATUS_META.dirty;
          return (
            <button
              key={room.id}
              onClick={() => setSelected(room)}
              data-testid={`hk-room-${room.room_number}`}
              className="w-full bg-white rounded-2xl shadow-sm active:scale-[0.98] transition-transform p-3 flex items-center gap-3"
            >
              <div className={`w-14 h-14 rounded-xl ${meta.bg} border-2 ${meta.border} flex items-center justify-center text-2xl flex-shrink-0`}>
                {meta.emoji}
              </div>
              <div className="flex-1 text-left min-w-0">
                <div className="flex items-center gap-2">
                  <p className="text-lg font-black text-stone-900">Oda {room.room_number}</p>
                  {room.floor && <span className="text-[9px] text-stone-500 uppercase font-bold">Kat {room.floor}</span>}
                  {room._pending && <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 font-bold" data-testid={`hk-pending-${room.room_number}`}>bekliyor</span>}
                </div>
                <p className={`text-xs font-bold ${meta.text}`}>{meta.label}</p>
                {room.notes && <p className="text-[10px] text-stone-500 line-clamp-1 mt-0.5">{room.notes}</p>}
              </div>
              <ChevronRight className="w-5 h-5 text-stone-400" />
            </button>
          );
        })}
      </div>

      {/* Detail sheet */}
      {selected && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-end justify-center" onClick={() => setSelected(null)}>
          <div
            onClick={e => e.stopPropagation()}
            className="w-full max-w-md bg-white rounded-t-3xl shadow-2xl p-5 animate-in slide-in-from-bottom duration-300"
            data-testid="hk-detail-sheet"
          >
            <div className="w-12 h-1 bg-stone-300 rounded-full mx-auto mb-4" />
            <div className="flex items-center gap-3 mb-4">
              <div className={`w-14 h-14 rounded-2xl ${STATUS_META[selected.status]?.bg} border-2 ${STATUS_META[selected.status]?.border} flex items-center justify-center text-3xl`}>
                {STATUS_META[selected.status]?.emoji}
              </div>
              <div className="flex-1">
                <h2 className="text-2xl font-black text-stone-900">Oda {selected.room_number}</h2>
                <p className={`text-sm font-bold ${STATUS_META[selected.status]?.text}`}>
                  Şu an: {STATUS_META[selected.status]?.label}
                </p>
              </div>
              <button onClick={() => setSelected(null)} data-testid="hk-close-sheet" className="p-2 rounded-lg text-stone-400"><XCircle className="w-6 h-6" /></button>
            </div>

            {(selected.notes || selected.floor) && (
              <div className="bg-stone-50 rounded-xl p-3 mb-4 text-xs text-stone-700 space-y-1">
                {selected.floor && <p><b>Kat:</b> {selected.floor}</p>}
                {selected.notes && <p><b>Notlar:</b> {selected.notes}</p>}
                {selected.last_cleaned_at && <p><b>Son temizlik:</b> {selected.last_cleaned_at.slice(0, 16).replace("T", " ")}</p>}
              </div>
            )}

            <div className="space-y-2" data-testid="hk-transitions">
              {TRANSITIONS.filter(t => t.from === selected.status).map(t => {
                const dest = STATUS_META[t.to];
                return (
                  <button
                    key={t.to}
                    onClick={() => transition(selected, t.to)}
                    disabled={busy}
                    data-testid={`hk-transition-${t.to}`}
                    className={`w-full py-4 rounded-2xl ${dest.bg} border-2 ${dest.border} text-base font-black ${dest.text} active:scale-[0.97] transition-transform disabled:opacity-50 inline-flex items-center justify-center gap-2`}
                  >
                    <span className="text-xl">{dest.emoji}</span>
                    {t.label}
                  </button>
                );
              })}
              {/* Mark out-of-order always available */}
              {selected.status !== "out_of_order" && (
                <button
                  onClick={() => transition(selected, "out_of_order")}
                  disabled={busy}
                  data-testid="hk-transition-oos"
                  className="w-full py-3 rounded-2xl bg-stone-100 border-2 border-stone-300 text-sm font-bold text-stone-700 active:scale-[0.97] inline-flex items-center justify-center gap-2"
                >
                  <Wrench className="w-4 h-4" /> Arıza / OOO
                </button>
              )}

              <OfflineIssueReporter propertyId={propertyId} room={selected} online={online} onQueued={() => setIssueQueueN(readIssueQueue(propertyId).length)} />

              {/* Voice damage / maintenance report */}
              <VoiceReporter
                propertyId={propertyId}
                roomNumber={selected.room_number}
                onSubmitted={() => toast.success("Sesli arıza raporu kaydedildi")}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * VoiceReporter — record a short audio message via MediaRecorder,
 * POST to /api/hk/voice-report which will transcribe + create ticket.
 */
function VoiceReporter({ propertyId, roomNumber, onSubmitted }) {
  const [state, setState] = useState("idle"); // idle | recording | preview | uploading | done
  const [blob, setBlob] = useState(null);
  const [transcript, setTranscript] = useState("");
  const [duration, setDuration] = useState(0);
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const timerRef = useRef(null);

  const start = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeCandidates = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
      const mimeType = mimeCandidates.find(m => window.MediaRecorder?.isTypeSupported?.(m)) || "audio/webm";
      const mr = new MediaRecorder(stream, { mimeType });
      chunksRef.current = [];
      mr.ondataavailable = e => e.data.size > 0 && chunksRef.current.push(e.data);
      mr.onstop = () => {
        const b = new Blob(chunksRef.current, { type: mimeType });
        setBlob(b);
        setState("preview");
        stream.getTracks().forEach(t => t.stop());
        clearInterval(timerRef.current);
      };
      mr.start();
      mediaRecorderRef.current = mr;
      setState("recording"); setDuration(0);
      timerRef.current = setInterval(() => setDuration(d => d + 1), 1000);
      // Auto-stop after 60s to prevent runaway recordings
      setTimeout(() => { if (mr.state === "recording") mr.stop(); }, 60000);
    } catch (e) {
      toast.error("Mikrofon erişimi reddedildi");
    }
  };

  const stop = () => {
    if (mediaRecorderRef.current?.state === "recording") {
      mediaRecorderRef.current.stop();
    }
  };

  const send = async () => {
    if (!blob) return;
    setState("uploading");
    try {
      const fd = new FormData();
      fd.append("audio", blob, "voice-report.webm");
      fd.append("property_id", propertyId);
      fd.append("room_number", roomNumber || "");
      fd.append("language", "tr");
      const r = await axios.post(`${process.env.REACT_APP_BACKEND_URL}/api/hk/voice-report`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setTranscript(r.data.transcript || "");
      setState("done");
      onSubmitted?.(r.data);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Ses kaydı gönderilemedi");
      setState("preview");
    }
  };

  const reset = () => { setState("idle"); setBlob(null); setTranscript(""); setDuration(0); };

  return (
    <div className="border-t border-stone-200 pt-3 mt-2" data-testid="hk-voice-reporter">
      <p className="text-[10px] text-stone-500 font-bold uppercase mb-1.5">🎙️ Sesli Arıza Raporu (AI transcribe)</p>
      {state === "idle" && (
        <button
          onClick={start}
          data-testid="hk-voice-start"
          className="w-full py-3 rounded-2xl bg-rose-500 hover:bg-rose-600 text-white text-sm font-bold active:scale-[0.97] inline-flex items-center justify-center gap-2"
        >
          <Mic className="w-4 h-4" /> Kayda Başla
        </button>
      )}
      {state === "recording" && (
        <button
          onClick={stop}
          data-testid="hk-voice-stop"
          className="w-full py-3 rounded-2xl bg-rose-600 text-white text-sm font-bold animate-pulse active:scale-[0.97] inline-flex items-center justify-center gap-2"
        >
          <Square className="w-4 h-4 fill-white" /> Durdur ({duration}s)
        </button>
      )}
      {state === "preview" && (
        <div className="space-y-2">
          <audio controls src={blob && URL.createObjectURL(blob)} className="w-full h-8" data-testid="hk-voice-audio" />
          <div className="flex gap-2">
            <button onClick={reset} className="flex-1 py-2.5 rounded-xl bg-stone-200 text-stone-700 text-sm font-bold">
              İptal
            </button>
            <button
              onClick={send} data-testid="hk-voice-send"
              className="flex-1 py-2.5 rounded-xl bg-emerald-500 text-white text-sm font-bold inline-flex items-center justify-center gap-1"
            >
              <Send className="w-3.5 h-3.5" /> Gönder
            </button>
          </div>
        </div>
      )}
      {state === "uploading" && (
        <div className="py-3 flex items-center justify-center gap-2 text-sm text-stone-600">
          <Loader2 className="w-4 h-4 animate-spin" /> AI transcribe ediyor...
        </div>
      )}
      {state === "done" && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-3" data-testid="hk-voice-result">
          <div className="flex items-center gap-1.5 mb-1">
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            <p className="text-xs font-bold text-emerald-800">Ticket oluşturuldu · AI transcript:</p>
          </div>
          <p className="text-xs text-stone-700 italic">&quot;{transcript}&quot;</p>
          <button onClick={reset} className="mt-2 text-[11px] px-2 py-1 rounded bg-white border border-emerald-300 text-emerald-700 font-bold">
            Yeni Kayıt
          </button>
        </div>
      )}
    </div>
  );
}

export function readIssueQueue(pid) { try { return JSON.parse(localStorage.getItem(`hk-issues-${pid}`) || "[]"); } catch { return []; } }

const ISSUE_CATS = [["plumbing", "Tesisat"], ["electrical", "Elektrik"], ["hvac", "Klima/Isıtma"], ["furniture", "Mobilya"], ["cleaning", "Temizlik"], ["general", "Diğer"]];
function shrinkImage(file) {
  return new Promise((resolve) => {
    const img = new Image(); const url = URL.createObjectURL(file);
    img.onload = () => {
      const max = 900; const k = Math.min(1, max / Math.max(img.width, img.height));
      const c = document.createElement("canvas"); c.width = Math.round(img.width * k); c.height = Math.round(img.height * k);
      c.getContext("2d").drawImage(img, 0, 0, c.width, c.height); URL.revokeObjectURL(url); resolve(c.toDataURL("image/jpeg", 0.7));
    };
    img.onerror = () => resolve(""); img.src = url;
  });
}
export function OfflineIssueReporter({ propertyId, room, online, onQueued }) {
  const [open, setOpen] = useState(false);
  const [cat, setCat] = useState("general");
  const [note, setNote] = useState("");
  const [photo, setPhoto] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    if (!note.trim()) { toast.error("Kısa bir açıklama yazın"); return; }
    const payload = { property_id: propertyId, title: `Oda ${room.room_number} — ${ISSUE_CATS.find(([k]) => k === cat)?.[1] || cat}`, description: note.trim(), category: cat,
      priority: "medium", location: `Oda ${room.room_number}`, room_number: room.room_number, room_id: room.id, photos_before: photo ? [photo] : [], source: "hk_mobile" };
    setBusy(true);
    const enqueue = () => {
      const q = readIssueQueue(propertyId); q.push({ id: `${Date.now()}`, at: new Date().toISOString(), payload });
      localStorage.setItem(`hk-issues-${propertyId}`, JSON.stringify(q)); onQueued?.();
      toast(`Arıza cihazda saklandı — bağlantı gelince gönderilir`, { icon: "📴" });
    };
    try {
      if (!navigator.onLine) enqueue();
      else { await axios.post(`${API}/maintenance/issues`, payload, { timeout: 15000 }); toast.success("Arıza bildirimi gönderildi"); }
      setOpen(false); setNote(""); setPhoto("");
    } catch (e) { if (!e.response) { enqueue(); setOpen(false); setNote(""); setPhoto(""); } else toast.error("Gönderilemedi"); }
    finally { setBusy(false); }
  };
  return (
    <div className="mt-2" data-testid="hk-issue-reporter">
      <button onClick={() => setOpen((v) => !v)} className="w-full py-3 rounded-2xl bg-rose-50 border-2 border-rose-200 text-sm font-bold text-rose-800 active:scale-[0.97]" data-testid="hk-issue-open">🔧 Arıza bildir {online ? "" : "(çevrimdışı)"}</button>
      {open && (
        <div className="mt-2 p-3 rounded-2xl border border-rose-200 bg-white space-y-2">
          <div className="flex flex-wrap gap-1">{ISSUE_CATS.map(([k, l]) => <button key={k} onClick={() => setCat(k)} className={`px-2 py-1 rounded-lg text-xs font-bold border ${cat === k ? "bg-rose-600 text-white border-rose-600" : "border-stone-200 text-stone-600"}`} data-testid={`hk-issue-cat-${k}`}>{l}</button>)}</div>
          <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} placeholder="Ne bozuk? (örn. duş başlığı akıtıyor)" className="w-full rounded-xl border border-stone-300 px-3 py-2 text-sm" data-testid="hk-issue-note" />
          <div className="flex items-center gap-2">
            <label className="px-3 py-2 rounded-xl bg-stone-100 text-xs font-bold text-stone-700 cursor-pointer">📷 Fotoğraf<input type="file" accept="image/*" capture="environment" className="hidden" data-testid="hk-issue-photo" onChange={async (e) => { const f = e.target.files?.[0]; if (f) setPhoto(await shrinkImage(f)); }} /></label>
            {photo && <img src={photo} alt="arıza" className="w-12 h-12 rounded-lg object-cover border" data-testid="hk-issue-photo-preview" />}
            <button onClick={submit} disabled={busy} className="ml-auto px-4 py-2 rounded-xl bg-rose-600 text-white text-sm font-bold disabled:opacity-50" data-testid="hk-issue-submit">{busy ? "…" : online ? "Gönder" : "Cihazda sakla"}</button>
          </div>
        </div>
      )}
    </div>
  );
}
