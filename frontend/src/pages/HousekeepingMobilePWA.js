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
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast, Toaster } from "sonner";
import {
  Loader2, ChevronRight, LogOut, RefreshCcw, CheckCircle2, Sparkles, Wrench,
  ClipboardCheck, Bed, XCircle,
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

  useEffect(() => {
    if (authToken) {
      axios.defaults.headers.common["Authorization"] = `Bearer ${authToken}`;
    }
  }, [authToken]);

  const load = useCallback(async () => {
    if (!propertyId || !authToken) return;
    setLoading(true);
    try {
      const [rs, st] = await Promise.all([
        axios.get(`${API}/housekeeping/rooms/${propertyId}`),
        axios.get(`${API}/housekeeping/rooms/${propertyId}/stats`),
      ]);
      setRooms(rs.data || []); setStats(st.data);
    } catch (e) {
      if (e.response?.status === 401) {
        setAuthToken(""); localStorage.removeItem("access_token");
      } else toast.error("Yüklenemedi");
    } finally { setLoading(false); }
  }, [propertyId, authToken]);

  useEffect(() => { load(); }, [load]);

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

  const transition = async (room, to) => {
    setBusy(true);
    try {
      await axios.put(`${API}/housekeeping/rooms/${room.id}/status`, { status: to });
      toast.success(`Oda ${room.room_number} → ${STATUS_META[to]?.label || to}`);
      setSelected(null); await load();
    } catch { toast.error("Değiştirilemedi"); } finally { setBusy(false); }
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
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
