import { useState, useEffect, useCallback, useMemo } from "react";
import axios from "axios";
import { Car, Users, Briefcase, Zap, Lock, Umbrella, Box, Clock, CheckCircle2, ChevronLeft } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

const KIND_META = {
  parking: { icon: Car, label: "Otopark" },
  ev_charger: { icon: Zap, label: "EV Şarj" },
  meeting_room: { icon: Users, label: "Toplantı Odası" },
  cabana: { icon: Umbrella, label: "Co-working / Cabana" },
  locker: { icon: Lock, label: "Dolap / Emanet" },
  other: { icon: Box, label: "Diğer" },
};

const todayISO = () => new Date().toISOString().slice(0, 10);

export default function SpacesPublicPage() {
  const pid = useMemo(() => {
    const parts = window.location.pathname.split("/").filter(Boolean);
    return parts.length > 1 ? parts[1] : "all";
  }, []);
  const [day, setDay] = useState(todayISO());
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null); // space being booked
  const [startHour, setStartHour] = useState(null);
  const [duration, setDuration] = useState(1);
  const [form, setForm] = useState({ guest_name: "", guest_email: "", guest_phone: "" });
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(null); // confirmed booking
  const [error, setError] = useState("");
  const [payState, setPayState] = useState(""); // "", "redirecting", "paid", "checking"

  // Handle Stripe return (?payment=success&sb=...&session_id=...)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("payment") === "success" && params.get("sb")) {
      setPayState("checking");
      const check = async (attempt = 0) => {
        try {
          const r = await axios.get(`${API}/api/public/spaces/pay-status/${params.get("sb")}?session_id=${params.get("session_id") || ""}`);
          if (r.data.status === "paid") {
            setDone(r.data.booking); setSelected(null); setPayState("paid");
            window.history.replaceState({}, "", window.location.pathname);
            return;
          }
        } catch { /* ignore */ }
        if (attempt < 5) setTimeout(() => check(attempt + 1), 2000);
        else setPayState("");
      };
      check();
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const payNow = async () => {
    if (!done) return;
    setPayState("redirecting");
    try {
      const r = await axios.post(`${API}/api/public/spaces/pay/${done.id}`);
      window.location.href = r.data.url;
    } catch (e) {
      setPayState("");
      setError(e.response?.data?.detail || "Ödeme başlatılamadı");
    }
  };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/api/public/spaces/${pid}?day=${day}`, { withCredentials: false });
      setData(r.data);
    } catch { setData(null); }
    finally { setLoading(false); }
  }, [pid, day]);
  useEffect(() => { load(); }, [load]);

  const busyHours = (space) => {
    const set = new Set();
    (space.busy || []).forEach((b) => {
      const s = new Date(b.start), e = new Date(b.end);
      const sameDayStart = b.start.slice(0, 10) === day ? s.getHours() : 0;
      const sameDayEnd = b.end.slice(0, 10) === day ? e.getHours() + (e.getMinutes() > 0 ? 1 : 0) : 24;
      for (let h = sameDayStart; h < sameDayEnd; h++) set.add(h);
    });
    return set;
  };

  const openBooking = (space) => {
    setSelected(space); setStartHour(null); setDuration(1); setDone(null); setError("");
  };

  const hourly = selected?.unit_minutes != null;
  const price = selected ? (hourly ? duration * (selected.rate_per_unit || 0) : selected.rate_per_unit || 0) : 0;
  const currency = selected?.currency === "GBP" ? "£" : (selected?.currency || "") + " ";

  const canFit = (space, h, dur) => {
    const bset = busyHours(space);
    if (h < space.open_hour || h + dur > space.close_hour) return false;
    for (let i = h; i < h + dur; i++) if (bset.has(i)) return false;
    return true;
  };

  const submit = async () => {
    setError("");
    if (!form.guest_name.trim()) { setError("Lütfen adınızı girin."); return; }
    if (hourly && startHour == null) { setError("Lütfen başlangıç saati seçin."); return; }
    setBusy(true);
    try {
      const start = hourly ? `${day}T${String(startHour).padStart(2, "0")}:00:00` : `${day}T00:00:00`;
      const endH = hourly ? startHour + duration : 24;
      const end = hourly
        ? `${day}T${String(endH).padStart(2, "0")}:00:00`
        : `${day}T23:59:00`;
      const r = await axios.post(`${API}/api/public/spaces/book`, {
        space_id: selected.id, start, end, ...form,
      }, { withCredentials: false });
      setDone(r.data.booking);
      load();
    } catch (e) {
      setError(e.response?.data?.detail || "Rezervasyon yapılamadı, lütfen farklı saat deneyin.");
    } finally { setBusy(false); }
  };

  if (loading && !data) {
    return <div className="min-h-screen bg-stone-100 flex items-center justify-center text-stone-400" data-testid="public-spaces-loading">Yükleniyor…</div>;
  }

  return (
    <div className="min-h-screen bg-stone-100" style={{ fontFamily: "'Inter', sans-serif" }}>
      <header className="bg-stone-900 text-white px-6 py-5">
        <div className="max-w-3xl mx-auto">
          <div className="text-[11px] uppercase tracking-widest text-stone-400">{data?.property_name || "Otel"}</div>
          <h1 className="text-2xl font-bold mt-0.5" data-testid="public-spaces-title">Alan & Saatlik Rezervasyon</h1>
          <p className="text-xs text-stone-400 mt-1">Toplantı odası, otopark, co-working ve daha fazlasını dakikalar içinde ayırtın.</p>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-6 space-y-4">
        {done ? (
          <div className="bg-white rounded-2xl shadow-sm p-8 text-center" data-testid="public-booking-success">
            <CheckCircle2 className="w-12 h-12 text-emerald-500 mx-auto mb-3" />
            <h2 className="text-lg font-bold text-stone-900">Rezervasyonunuz onaylandı!</h2>
            <p className="text-sm text-stone-600 mt-2">
              <b>{done.space_name}</b> · {done.start.slice(0, 10)} {done.start.slice(11, 16)}–{done.end.slice(11, 16)}
            </p>
            <p className="text-2xl font-black text-stone-900 mt-2">{currency || "£"}{done.price}</p>
            {payState === "paid" || done.payment_status === "paid" ? (
              <p className="text-sm font-bold text-emerald-600 mt-2" data-testid="public-paid-badge">✓ Ödeme alındı — her şey hazır!</p>
            ) : payState === "checking" ? (
              <p className="text-xs text-stone-400 mt-1" data-testid="public-pay-checking">Ödeme doğrulanıyor…</p>
            ) : (
              <>
                <p className="text-xs text-stone-400 mt-1">Referans: {done.id.slice(0, 8).toUpperCase()} · Ödemeyi şimdi yapabilir veya girişte ödeyebilirsiniz.</p>
                <button onClick={payNow} disabled={payState === "redirecting"} data-testid="public-pay-now-btn"
                  className="mt-4 w-full px-5 py-3 text-sm font-bold text-white bg-indigo-600 rounded-xl hover:bg-indigo-700 disabled:opacity-50">
                  {payState === "redirecting" ? "Yönlendiriliyor…" : "💳 Kartla şimdi öde"}
                </button>
                {error && <p className="text-xs text-rose-500 mt-2">{error}</p>}
              </>
            )}
            <button onClick={() => { setDone(null); setSelected(null); setPayState(""); }} data-testid="public-book-another"
              className="mt-4 px-5 py-2.5 text-sm font-semibold text-stone-700 border border-stone-300 rounded-xl hover:bg-stone-50">
              Yeni rezervasyon yap
            </button>
          </div>
        ) : selected ? (
          <div className="bg-white rounded-2xl shadow-sm p-6" data-testid="public-booking-form">
            <button onClick={() => setSelected(null)} className="flex items-center gap-1 text-xs text-stone-500 hover:text-stone-900 mb-3" data-testid="public-back-btn">
              <ChevronLeft className="w-3.5 h-3.5" /> Tüm alanlar
            </button>
            <h2 className="text-lg font-bold text-stone-900">{selected.name}</h2>
            <p className="text-xs text-stone-500 mt-0.5">{selected.description}</p>
            <p className="text-xs text-stone-400 mt-1">{day} · Açık: {selected.open_hour}:00–{selected.close_hour}:00</p>

            {hourly ? (
              <>
                <div className="mt-4">
                  <div className="text-xs font-semibold text-stone-700 mb-2">Başlangıç saati</div>
                  <div className="flex flex-wrap gap-1.5">
                    {Array.from({ length: Math.max(selected.close_hour - selected.open_hour, 0) }, (_, i) => selected.open_hour + i).map((h) => {
                      const ok = canFit(selected, h, duration);
                      return (
                        <button key={h} disabled={!ok} onClick={() => setStartHour(h)} data-testid={`hour-${h}`}
                          className={`w-14 py-1.5 text-xs font-semibold rounded-lg border transition-colors ${startHour === h ? "bg-stone-900 text-white border-stone-900" : ok ? "bg-white text-stone-700 border-stone-300 hover:border-stone-900" : "bg-stone-100 text-stone-300 border-stone-100 line-through cursor-not-allowed"}`}>
                          {String(h).padStart(2, "0")}:00
                        </button>
                      );
                    })}
                  </div>
                </div>
                <div className="mt-4">
                  <div className="text-xs font-semibold text-stone-700 mb-2">Süre</div>
                  <div className="flex gap-1.5">
                    {[1, 2, 3, 4, 6, 8].map((d) => (
                      <button key={d} onClick={() => { setDuration(d); if (startHour != null && !canFit(selected, startHour, d)) setStartHour(null); }}
                        data-testid={`duration-${d}`}
                        className={`px-3 py-1.5 text-xs font-semibold rounded-lg border ${duration === d ? "bg-stone-900 text-white border-stone-900" : "bg-white text-stone-700 border-stone-300 hover:border-stone-900"}`}>
                        {d} saat
                      </button>
                    ))}
                  </div>
                </div>
              </>
            ) : (
              <div className="mt-4 text-xs text-stone-600 bg-stone-50 rounded-xl p-3">Bu alan günlük ücretlendirilir — seçilen tarih için tam gün ayrılır.</div>
            )}

            <div className="mt-5 grid grid-cols-1 sm:grid-cols-3 gap-2">
              <input value={form.guest_name} onChange={(e) => setForm({ ...form, guest_name: e.target.value })}
                placeholder="Ad Soyad *" data-testid="public-guest-name"
                className="border border-stone-300 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:border-stone-900" />
              <input value={form.guest_email} onChange={(e) => setForm({ ...form, guest_email: e.target.value })}
                placeholder="E-posta" data-testid="public-guest-email"
                className="border border-stone-300 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:border-stone-900" />
              <input value={form.guest_phone} onChange={(e) => setForm({ ...form, guest_phone: e.target.value })}
                placeholder="Telefon" data-testid="public-guest-phone"
                className="border border-stone-300 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:border-stone-900" />
            </div>

            {error && <div className="mt-3 text-xs text-rose-600 bg-rose-50 border border-rose-200 rounded-lg px-3 py-2" data-testid="public-book-error">{error}</div>}

            <div className="mt-5 flex items-center justify-between bg-stone-50 rounded-xl px-4 py-3">
              <div>
                <div className="text-[10px] uppercase tracking-wide text-stone-400">Toplam</div>
                <div className="text-xl font-black text-stone-900" data-testid="public-total-price">{currency}{price.toFixed(2)}</div>
              </div>
              <button onClick={submit} disabled={busy} data-testid="public-confirm-btn"
                className="px-6 py-3 text-sm font-bold text-white bg-emerald-600 rounded-xl hover:bg-emerald-700 disabled:opacity-50">
                {busy ? "Ayırtılıyor…" : "Rezervasyonu Onayla"}
              </button>
            </div>
          </div>
        ) : (
          <>
            <div className="bg-white rounded-2xl shadow-sm p-4 flex items-center gap-3">
              <Clock className="w-4 h-4 text-stone-400" />
              <label className="text-xs font-semibold text-stone-700">Tarih</label>
              <input type="date" value={day} min={todayISO()} onChange={(e) => setDay(e.target.value)}
                data-testid="public-date-input"
                className="border border-stone-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-stone-900" />
            </div>
            {(data?.spaces || []).length === 0 ? (
              <div className="bg-white rounded-2xl shadow-sm p-10 text-center text-sm text-stone-400">Bu tesiste rezerve edilebilir alan bulunmuyor.</div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {data.spaces.map((s) => {
                  const meta = KIND_META[s.kind] || KIND_META.other;
                  const Icon = meta.icon;
                  const bset = busyHours(s);
                  const openHours = Math.max(s.close_hour - s.open_hour, 0);
                  const freeCount = Array.from({ length: openHours }, (_, i) => s.open_hour + i).filter((h) => !bset.has(h)).length;
                  return (
                    <div key={s.id} className="bg-white rounded-2xl shadow-sm p-5 flex flex-col" data-testid={`public-space-${s.id}`}>
                      <div className="flex items-start justify-between">
                        <div className="w-10 h-10 rounded-xl bg-stone-900 text-white flex items-center justify-center"><Icon className="w-5 h-5" /></div>
                        <span className="text-[10px] font-semibold uppercase tracking-wide text-stone-400 bg-stone-100 rounded-full px-2 py-1">{meta.label}</span>
                      </div>
                      <h3 className="text-sm font-bold text-stone-900 mt-3">{s.name}</h3>
                      <p className="text-xs text-stone-500 mt-1 flex-1">{s.description}</p>
                      <div className="flex items-center justify-between mt-3">
                        <div>
                          <span className="text-lg font-black text-stone-900">{s.currency === "GBP" ? "£" : s.currency}{s.rate_per_unit}</span>
                          <span className="text-[11px] text-stone-400"> / {s.unit_minutes ? "saat" : "gün"}</span>
                          {s.unit_minutes != null && <div className="text-[10px] text-emerald-600 font-medium">{freeCount} saat müsait</div>}
                        </div>
                        <button onClick={() => openBooking(s)} data-testid={`public-select-${s.id}`}
                          className="px-4 py-2 text-xs font-bold text-white bg-stone-900 rounded-xl hover:bg-stone-700">
                          Ayırt
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}
        <p className="text-center text-[10px] text-stone-400 pt-2">Powered by MyHotelBox Spaces</p>
      </main>
    </div>
  );
}
