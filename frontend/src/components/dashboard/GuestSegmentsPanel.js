import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  UsersThree, ArrowsClockwise, Crown, ShieldWarning, Heart, Buildings,
  Baby, Sparkle, User, CheckCircle, XCircle,
} from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;
const fmt = (v) => `£${Number(v || 0).toLocaleString("en-GB", { maximumFractionDigits: 0 })}`;

const SEG_ICON = { vip: Crown, riskli: ShieldWarning, sadik: Heart, aile: Baby, is: Buildings, yeni: Sparkle, standart: User };
const SEG_CLS = {
  amber: "bg-amber-50 border-amber-200 text-amber-700",
  rose: "bg-rose-50 border-rose-200 text-rose-700",
  emerald: "bg-emerald-50 border-emerald-200 text-emerald-700",
  sky: "bg-sky-50 border-sky-200 text-sky-700",
  violet: "bg-violet-50 border-violet-200 text-violet-700",
  cyan: "bg-cyan-50 border-cyan-200 text-cyan-700",
  stone: "bg-stone-50 border-stone-200 text-stone-600",
};
const MOTOR_TR = {
  cancel_save: "İptal Kurtarma",
  upsell_autopilot: "Upsell",
  deposit_autopilot: "Depozito",
  email_nudge: "Hatırlatma",
};

export default function GuestSegmentsPanel() {
  const [data, setData] = useState(null);
  const [strategy, setStrategy] = useState(null);
  const [perf, setPerf] = useState(null);
  const [selected, setSelected] = useState("");
  const [guests, setGuests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");

  const load = useCallback(async () => {
    try {
      const [s, st, pf] = await Promise.all([
        axios.get(`${API}/api/guests/segments/summary`),
        axios.get(`${API}/api/guests/segments/strategy`),
        axios.get(`${API}/api/guests/segments/performance?days=90`),
      ]);
      setData(s.data);
      setStrategy(st.data);
      setPerf(pf.data);
    } catch { toast.error("Segment verisi yüklenemedi"); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const refresh = async () => {
    setBusy("refresh");
    try {
      const r = await axios.post(`${API}/api/guests/segments/refresh`, {});
      toast.success(`${r.data.classified} misafir yeniden segmentlendi`);
      await load();
      if (selected) selectSegment(selected);
    } catch { toast.error("Yenileme başarısız"); }
    finally { setBusy(""); }
  };

  const selectSegment = async (seg) => {
    setSelected(seg);
    try {
      const r = await axios.get(`${API}/api/guests/segments/list?segment=${seg}`);
      setGuests(r.data.guests);
    } catch { toast.error("Misafir listesi yüklenemedi"); }
  };

  const toggleStrategy = async (segment, motor, value) => {
    setBusy(`${segment}-${motor}`);
    try {
      await axios.put(`${API}/api/guests/segments/strategy/${segment}`, { [motor]: value });
      setStrategy((st) => ({
        ...st,
        strategies: st.strategies.map((s) => s.segment === segment ? { ...s, [motor]: value } : s),
      }));
      toast.success(`${MOTOR_TR[motor]} ${value ? "açıldı" : "kapatıldı"}`);
    } catch { toast.error("Güncelleme başarısız"); }
    finally { setBusy(""); }
  };

  if (loading) return <div className="p-8 text-stone-400 text-sm" data-testid="segments-loading">Yükleniyor…</div>;
  if (!data) return <div className="p-8 text-stone-400 text-sm">Veri yok</div>;

  return (
    <div className="space-y-6" data-testid="guest-segments-panel">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
            <UsersThree size={12} weight="fill" className="text-violet-600" />
            <span>Segment Motoru</span>
          </div>
          <h2 className="text-xl font-semibold text-stone-900">Misafir segmentleri & autopilot stratejisi</h2>
          <p className="text-xs text-stone-500 mt-1">
            {data.total_guests} misafir otomatik sınıflandırıldı
            {data.refreshed_at && ` — son yenileme: ${new Date(data.refreshed_at).toLocaleString("tr-TR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })}`}
            . Her gece 05:00'te otomatik güncellenir.
          </p>
        </div>
        <button onClick={refresh} disabled={busy === "refresh"} data-testid="segments-refresh-btn"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-white bg-stone-900 rounded-lg px-4 py-2 hover:bg-stone-800 disabled:opacity-50">
          <ArrowsClockwise size={14} className={busy === "refresh" ? "animate-spin" : ""} />
          {busy === "refresh" ? "Sınıflandırılıyor…" : "Segmentleri yenile"}
        </button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-7 gap-3">
        {data.segments.map((s) => {
          const Icon = SEG_ICON[s.segment] || User;
          return (
            <button key={s.segment} onClick={() => selectSegment(s.segment)}
              data-testid={`segment-card-${s.segment}`}
              className={`text-left border rounded-xl p-3 transition-all ${SEG_CLS[s.color]} ${selected === s.segment ? "ring-2 ring-stone-900 ring-offset-1" : "hover:shadow-sm"}`}>
              <Icon size={18} weight="fill" />
              <div className="font-semibold text-sm mt-1.5">{s.label}</div>
              <div className="text-2xl font-bold mt-0.5" data-testid={`segment-count-${s.segment}`}>{s.count}</div>
              <div className="text-[10px] opacity-75 mt-0.5">{fmt(s.revenue)} gelir</div>
            </button>
          );
        })}
      </div>

      <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-stone-100">
          <h3 className="text-sm font-semibold text-stone-900">Segment × Autopilot strateji matrisi</h3>
          <p className="text-[11px] text-stone-500 mt-0.5">Kapalı hücrelerde o motor, o segmentteki misafirlere hiçbir şey göndermez. Örn: VIP'lere indirim kuponu ve depozito talebi gitmez.</p>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-[11px] uppercase tracking-wide text-stone-400 border-b border-stone-100">
              <th className="text-left px-4 py-2 font-medium">Segment</th>
              {strategy?.motors.map((m) => (
                <th key={m} className="text-center px-2 py-2 font-medium">{MOTOR_TR[m]}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {strategy?.strategies.map((s) => (
              <tr key={s.segment} className="border-b border-stone-50 last:border-0">
                <td className="px-4 py-2.5 font-medium text-stone-800">{s.label}</td>
                {strategy.motors.map((m) => (
                  <td key={m} className="text-center px-2 py-2.5">
                    <button onClick={() => toggleStrategy(s.segment, m, !s[m])}
                      disabled={busy === `${s.segment}-${m}`}
                      data-testid={`strategy-${s.segment}-${m}`}
                      className="inline-flex items-center justify-center disabled:opacity-40">
                      {s[m]
                        ? <CheckCircle size={20} weight="fill" className="text-emerald-500 hover:text-emerald-600" />
                        : <XCircle size={20} weight="fill" className="text-stone-300 hover:text-stone-400" />}
                    </button>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {perf && (
        <div className="bg-white border border-stone-200 rounded-xl overflow-hidden" data-testid="segment-performance">
          <div className="px-4 py-3 border-b border-stone-100">
            <h3 className="text-sm font-semibold text-stone-900">Segment performansı — upsell teklifleri (son {perf.days} gün)</h3>
            <p className="text-[11px] text-stone-500 mt-0.5">{perf.total_offers} teklif analiz edildi. Düşük kabul oranlı segmentlerin stratejisini gözden geçirin.</p>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[11px] uppercase tracking-wide text-stone-400 border-b border-stone-100">
                <th className="text-left px-4 py-2 font-medium">Segment</th>
                <th className="text-right px-2 py-2 font-medium">Gönderilen</th>
                <th className="text-right px-2 py-2 font-medium">Görüntülenen</th>
                <th className="text-right px-2 py-2 font-medium">Kabul</th>
                <th className="text-left px-4 py-2 font-medium w-48">Kabul oranı</th>
                <th className="text-right px-4 py-2 font-medium">Gelir</th>
              </tr>
            </thead>
            <tbody>
              {perf.segments.filter((s) => s.sent > 0).map((s) => (
                <tr key={s.segment} className="border-b border-stone-50 last:border-0" data-testid={`perf-row-${s.segment}`}>
                  <td className="px-4 py-2.5 font-medium text-stone-800">{s.label}</td>
                  <td className="px-2 py-2.5 text-right text-stone-600">{s.sent}</td>
                  <td className="px-2 py-2.5 text-right text-stone-600">{s.viewed} <span className="text-[10px] text-stone-400">(%{s.view_rate})</span></td>
                  <td className="px-2 py-2.5 text-right font-medium text-emerald-600">{s.accepted}</td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-1.5 bg-stone-100 rounded-full overflow-hidden">
                        <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${Math.min(s.acceptance_rate, 100)}%` }} />
                      </div>
                      <span className="text-xs font-medium text-stone-700 w-10 text-right">%{s.acceptance_rate}</span>
                    </div>
                  </td>
                  <td className="px-4 py-2.5 text-right font-medium text-stone-800">{fmt(s.revenue)}</td>
                </tr>
              ))}
              {perf.segments.every((s) => s.sent === 0) && (
                <tr><td colSpan={6} className="px-4 py-5 text-xs text-stone-400">Bu dönemde teklif gönderilmedi — Upsell Auto-Pilot çalıştıkça veriler burada birikecek.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {selected && (
        <div className="bg-white border border-stone-200 rounded-xl overflow-hidden" data-testid="segment-guest-list">
          <div className="px-4 py-3 border-b border-stone-100 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-stone-900">
              {data.segments.find((s) => s.segment === selected)?.label} segmenti — {guests.length} misafir
            </h3>
            <span className="text-[11px] text-stone-400">{data.segments.find((s) => s.segment === selected)?.description}</span>
          </div>
          {guests.length === 0 ? (
            <div className="px-4 py-6 text-xs text-stone-400">Bu segmentte misafir yok</div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[11px] uppercase tracking-wide text-stone-400 border-b border-stone-100">
                  <th className="text-left px-4 py-2 font-medium">Misafir</th>
                  <th className="text-left px-2 py-2 font-medium">E-posta</th>
                  <th className="text-right px-2 py-2 font-medium">Konaklama</th>
                  <th className="text-right px-2 py-2 font-medium">Harcama</th>
                  <th className="text-right px-4 py-2 font-medium">Son konaklama</th>
                </tr>
              </thead>
              <tbody>
                {guests.map((g) => (
                  <tr key={g.email} className="border-b border-stone-50 last:border-0 hover:bg-stone-50/50">
                    <td className="px-4 py-2 font-medium text-stone-800">{g.name || "—"}{g.vip && <Crown size={12} weight="fill" className="inline ml-1 text-amber-500" />}</td>
                    <td className="px-2 py-2 text-stone-500 text-xs">{g.email}</td>
                    <td className="px-2 py-2 text-right text-stone-600">{g.total_stays || 0}</td>
                    <td className="px-2 py-2 text-right font-medium text-stone-800">{fmt(g.total_spend)}</td>
                    <td className="px-4 py-2 text-right text-xs text-stone-500">{g.last_stay ? g.last_stay.slice(0, 10) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
