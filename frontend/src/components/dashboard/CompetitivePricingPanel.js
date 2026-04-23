/**
 * CompetitivePricingPanel — Rule-based auto pricing that feeds neighborhood
 * competitor prices into rate overrides.
 *
 *   Mode: below_avg / match_avg / below_min / match_min / above_min
 *   Offset: ±%
 *   Guardrails: min_rate_pct / max_rate_pct of base rate
 *   Demand gate: only apply when unavail% >= threshold
 */
import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Target, Loader2, Play, Save, CheckCircle2, AlertTriangle } from "lucide-react";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => "£" + (Number(v) || 0).toLocaleString("en-GB", { maximumFractionDigits: 0 });

const MODES = [
  { id: "below_avg",  label: "Ortalamanın altı", ref: "Ort. fiyat" },
  { id: "match_avg",  label: "Ortalamaya eşit",  ref: "Ort. fiyat" },
  { id: "below_min",  label: "En düşüğün altı",  ref: "En düşük fiyat" },
  { id: "match_min",  label: "En düşüğe eşit",   ref: "En düşük fiyat" },
  { id: "above_min",  label: "En düşüğün üstü",  ref: "En düşük fiyat" },
];

export default function CompetitivePricingPanel({ propertyId }) {
  const [cfg, setCfg] = useState(null);
  const [recs, setRecs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [applying, setApplying] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [{ data: c }, { data: r }] = await Promise.all([
        axios.get(`${API}/revenue/market-robot/${propertyId}/competitive-config`),
        axios.get(`${API}/revenue/market-robot/${propertyId}/competitive-recommendations?days=30`),
      ]);
      setCfg(c);
      setRecs(r.recommendations || []);
    } catch { /* noop */ }
    setLoading(false);
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);

  const save = async () => {
    setSaving(true);
    try {
      const { data } = await axios.put(`${API}/revenue/market-robot/${propertyId}/competitive-config`, cfg);
      setCfg(data);
      toast.success("Rekabetçi fiyat kuralı kaydedildi");
      load();
    } catch { toast.error("Kayıt başarısız"); }
    setSaving(false);
  };

  const apply = async () => {
    setApplying(true);
    try {
      const { data } = await axios.post(`${API}/revenue/market-robot/${propertyId}/apply-competitive-pricing`, { days: 30 });
      toast.success(`${data.applied} fiyat güncellemesi uygulandı`);
      load();
    } catch { toast.error("Uygulama başarısız"); }
    setApplying(false);
  };

  if (!cfg) {
    return (
      <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-6 text-center">
        <Loader2 className="w-5 h-5 text-stone-500 animate-spin mx-auto" />
      </div>
    );
  }

  // Summary KPIs
  const applicable = recs.filter(r => !r.skipped_low_demand);
  const avgDelta = applicable.length ? (applicable.reduce((a, b) => a + b.delta_vs_current_pct, 0) / applicable.length).toFixed(1) : "0.0";
  const biggest = applicable.reduce((max, r) => Math.abs(r.delta_vs_current_pct) > Math.abs(max?.delta_vs_current_pct || 0) ? r : max, null);

  return (
    <div className="bg-stone-900/60 border border-violet-500/30 rounded-2xl p-5 space-y-5" data-testid="competitive-pricing-panel">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-violet-500/20 flex items-center justify-center">
            <Target className="w-5 h-5 text-violet-400" />
          </div>
          <div>
            <h3 className="text-sm font-black text-violet-300">Rekabetçi Fiyat Kuralı</h3>
            <p className="text-[11px] text-stone-400 mt-0.5">
              Komşu Booking fiyatlarına göre otomatik rate önerileri üretir.
              {cfg.last_apply_at && (
                <span className="text-emerald-400 ml-1">· Son uygulama: {new Date(cfg.last_apply_at).toLocaleString()} ({cfg.last_apply_count})</span>
              )}
            </p>
          </div>
        </div>
        <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold ${cfg.enabled ? "bg-emerald-500/20 text-emerald-300" : "bg-stone-700/50 text-stone-400"}`}>
          {cfg.enabled ? <CheckCircle2 className="w-3.5 h-3.5" /> : <AlertTriangle className="w-3.5 h-3.5" />}
          {cfg.enabled ? "Aktif" : "Devre dışı"}
        </div>
      </div>

      {/* Rule builder */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <div>
          <label className="block text-[10px] font-bold uppercase text-stone-400 mb-1.5 tracking-wider">Hedef Mod</label>
          <select value={cfg.target_mode} onChange={e => setCfg({ ...cfg, target_mode: e.target.value })}
            className="w-full px-3 py-2.5 text-sm bg-stone-950 border border-stone-700 rounded-lg text-stone-100"
            data-testid="cp-mode">
            {MODES.map(m => <option key={m.id} value={m.id}>{m.label}</option>)}
          </select>
          <p className="text-[9px] text-stone-500 mt-1">Referans: {MODES.find(m => m.id === cfg.target_mode)?.ref}</p>
        </div>
        <div>
          <label className="block text-[10px] font-bold uppercase text-stone-400 mb-1.5 tracking-wider">
            Offset <span className="text-violet-300">({cfg.target_offset_pct > 0 ? "+" : ""}{cfg.target_offset_pct}%)</span>
          </label>
          <input type="range" min="-20" max="20" step="0.5" value={cfg.target_offset_pct}
            onChange={e => setCfg({ ...cfg, target_offset_pct: parseFloat(e.target.value) })}
            className="w-full accent-violet-500" data-testid="cp-offset" />
          <div className="flex justify-between text-[9px] text-stone-500"><span>-20%</span><span>0%</span><span>+20%</span></div>
        </div>
        <div>
          <label className="block text-[10px] font-bold uppercase text-stone-400 mb-1.5 tracking-wider">Alt Sınır (base %)</label>
          <input type="number" value={cfg.min_rate_pct} min="10" max="100"
            onChange={e => setCfg({ ...cfg, min_rate_pct: parseInt(e.target.value) || 60 })}
            className="w-full px-3 py-2.5 text-sm bg-stone-950 border border-stone-700 rounded-lg text-stone-100 tabular-nums"
            data-testid="cp-min-pct" />
        </div>
        <div>
          <label className="block text-[10px] font-bold uppercase text-stone-400 mb-1.5 tracking-wider">Üst Sınır (base %)</label>
          <input type="number" value={cfg.max_rate_pct} min="100" max="500"
            onChange={e => setCfg({ ...cfg, max_rate_pct: parseInt(e.target.value) || 250 })}
            className="w-full px-3 py-2.5 text-sm bg-stone-950 border border-stone-700 rounded-lg text-stone-100 tabular-nums"
            data-testid="cp-max-pct" />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 items-end">
        <div>
          <label className="block text-[10px] font-bold uppercase text-stone-400 mb-1.5 tracking-wider">Talep eşiği ≥ (demand %)</label>
          <input type="number" value={cfg.only_apply_if_demand_gte} min="0" max="100"
            onChange={e => setCfg({ ...cfg, only_apply_if_demand_gte: parseInt(e.target.value) || 0 })}
            className="w-full px-3 py-2.5 text-sm bg-stone-950 border border-stone-700 rounded-lg text-stone-100 tabular-nums"
            data-testid="cp-demand-gate" />
          <p className="text-[9px] text-stone-500 mt-1">Sadece bu seviyede doluluk olan günlere uygula</p>
        </div>
        <label className="flex items-center gap-2 px-3 py-2.5 bg-stone-950 border border-stone-700 rounded-lg cursor-pointer hover:border-violet-500/50" data-testid="cp-enable-row">
          <input type="checkbox" checked={cfg.enabled} onChange={e => setCfg({ ...cfg, enabled: e.target.checked })} className="accent-violet-500" data-testid="cp-enabled" />
          <span className="text-xs text-stone-200">Kural aktif</span>
        </label>
        <label className="flex items-center gap-2 px-3 py-2.5 bg-stone-950 border border-stone-700 rounded-lg cursor-pointer hover:border-violet-500/50" data-testid="cp-auto-row">
          <input type="checkbox" checked={cfg.auto_apply} onChange={e => setCfg({ ...cfg, auto_apply: e.target.checked })} className="accent-violet-500" data-testid="cp-auto-apply" />
          <span className="text-xs text-stone-200">Otomatik uygula (her scan sonrası)</span>
        </label>
      </div>

      <div className="flex flex-wrap gap-2">
        <button onClick={save} disabled={saving}
          className="flex items-center gap-2 px-4 py-2.5 bg-violet-500/20 hover:bg-violet-500/30 text-violet-200 font-bold rounded-lg border border-violet-500/40 text-xs disabled:opacity-60"
          data-testid="cp-save">
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          Kaydet
        </button>
        <button onClick={apply} disabled={applying || applicable.length === 0}
          className="flex items-center gap-2 px-4 py-2.5 bg-emerald-500 hover:bg-emerald-400 text-black font-black rounded-lg text-xs shadow-lg shadow-emerald-500/30 disabled:opacity-50"
          data-testid="cp-apply">
          {applying ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
          Şimdi Uygula ({applicable.length} öneri)
        </button>
      </div>

      {/* Summary + recommendations preview */}
      {recs.length > 0 && (
        <div className="grid grid-cols-3 gap-3 pt-2 border-t border-stone-800">
          <Stat label="Uygulanabilir" value={applicable.length} hint={`${recs.length - applicable.length} talep eşiğinin altında`} />
          <Stat label="Ortalama Δ" value={`${avgDelta}%`} hint="Mevcuta göre değişim" />
          <Stat label="En büyük değişim" value={biggest ? `${biggest.delta_vs_current_pct > 0 ? "+" : ""}${biggest.delta_vs_current_pct}%` : "—"} hint={biggest ? `${biggest.date} · ${cur(biggest.current_rate)} → ${cur(biggest.suggested_rate)}` : ""} />
        </div>
      )}

      {/* Preview table (first 10) */}
      {recs.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-stone-800" data-testid="cp-preview">
          <table className="w-full text-xs">
            <thead className="bg-stone-950/80 text-stone-300">
              <tr className="border-b border-stone-800">
                <th className="text-left py-2 pl-3 pr-2 font-bold text-[10px] uppercase tracking-widest">Tarih</th>
                <th className="text-left px-2 font-bold text-[10px] uppercase tracking-widest">Oda Tipi</th>
                <th className="text-right px-2 font-bold text-[10px] uppercase tracking-widest">Mevcut £</th>
                <th className="text-right px-2 font-bold text-[10px] uppercase tracking-widest">Pazar Ort.</th>
                <th className="text-right px-2 font-bold text-[10px] uppercase tracking-widest">Öneri £</th>
                <th className="text-right px-2 font-bold text-[10px] uppercase tracking-widest">Δ</th>
                <th className="text-right pr-3 pl-2 font-bold text-[10px] uppercase tracking-widest">Durum</th>
              </tr>
            </thead>
            <tbody>
              {recs.slice(0, 10).map((r, idx) => (
                <tr key={idx} className="border-b border-stone-800/40 hover:bg-violet-500/5">
                  <td className="py-2 pl-3 pr-2 text-stone-200 font-semibold tabular-nums">{r.date}</td>
                  <td className="px-2 text-stone-300 truncate max-w-[160px]">{r.room_type_name}</td>
                  <td className="text-right px-2 text-stone-400 tabular-nums">{cur(r.current_rate)}</td>
                  <td className="text-right px-2 text-amber-300 tabular-nums">{cur(r.market_avg)}</td>
                  <td className="text-right px-2 text-violet-300 font-black tabular-nums">{cur(r.suggested_rate)}</td>
                  <td className={`text-right px-2 font-bold tabular-nums ${r.delta_vs_current_pct > 0 ? "text-emerald-300" : r.delta_vs_current_pct < 0 ? "text-rose-300" : "text-stone-500"}`}>
                    {r.delta_vs_current_pct > 0 ? "+" : ""}{r.delta_vs_current_pct}%
                  </td>
                  <td className="text-right pr-3 pl-2">
                    {r.skipped_low_demand
                      ? <span className="text-[9px] text-stone-500 bg-stone-800/50 px-1.5 py-0.5 rounded">Düşük talep</span>
                      : r.clamped
                        ? <span className="text-[9px] text-amber-300 bg-amber-500/15 px-1.5 py-0.5 rounded">Sınırlandı</span>
                        : <span className="text-[9px] text-emerald-300 bg-emerald-500/15 px-1.5 py-0.5 rounded">Hazır</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {recs.length > 10 && (
            <div className="text-center py-2 text-[10px] text-stone-500 bg-stone-950/50">+ {recs.length - 10} daha (Şimdi Uygula'ya basınca hepsi işlenir)</div>
          )}
        </div>
      )}

      {loading && <div className="text-center py-3"><Loader2 className="w-4 h-4 animate-spin text-stone-500 mx-auto" /></div>}
    </div>
  );
}

function Stat({ label, value, hint }) {
  return (
    <div className="bg-stone-950/60 border border-stone-800 rounded-lg p-3">
      <p className="text-[9px] font-bold uppercase tracking-widest text-stone-400">{label}</p>
      <p className="text-lg font-black text-violet-300 tabular-nums mt-1">{value}</p>
      {hint && <p className="text-[9px] text-stone-500 mt-0.5">{hint}</p>}
    </div>
  );
}
