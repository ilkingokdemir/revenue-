import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { ShieldCheck, CheckCircle, XCircle } from "@phosphor-icons/react";
import { Loader2 } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function DecisionAssurancePanel({ propertyId }) {
  const pid = propertyId && propertyId !== "all" ? propertyId : "default";
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [exp, setExp] = useState(null);

  useEffect(() => {
    axios.get(`${API}/decision-assurance/${pid}/experiment`).then(({ data: d }) => setExp(d)).catch(() => {});
  }, [pid]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data: d } = await axios.get(`${API}/decision-assurance/${pid}?days=120`);
      setData(d);
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  if (loading) return <div className="p-10 text-center"><Loader2 className="w-6 h-6 animate-spin mx-auto text-stone-400" /></div>;
  if (!data) return null;
  const s = data.summary;

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-5" data-testid="decision-assurance-panel">
      <div>
        <h1 className="text-xl font-bold text-stone-900 flex items-center gap-2">
          <ShieldCheck size={22} weight="fill" className="text-emerald-600" /> Decision Assurance — Kanıtlı Autopilot
        </h1>
        <p className="text-sm text-stone-500 mt-0.5">
          Her fiyat kararı için: beklenen sonuç bandı (P10/P50/P90), gerçekten uygulandı mı (readback)
          ve konaklama tarihi geçince gözlemlenen etki.
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="p-4 rounded-2xl bg-white border border-stone-200" data-testid="da-decisions-card">
          <div className="text-[10px] uppercase font-bold text-stone-400">Karar (120g)</div>
          <div className="text-lg font-black text-stone-900">{s.decisions}</div>
        </div>
        <div className="p-4 rounded-2xl bg-emerald-50 border border-emerald-200" data-testid="da-applied-card">
          <div className="text-[10px] uppercase font-bold text-emerald-600">Uygulanma (readback)</div>
          <div className="text-lg font-black text-emerald-900">%{s.applied_pct}</div>
        </div>
        <div className="p-4 rounded-2xl bg-white border border-stone-200" data-testid="da-observed-card">
          <div className="text-[10px] uppercase font-bold text-stone-400">Etki ölçülen</div>
          <div className="text-lg font-black text-stone-900">{s.observed_count}</div>
        </div>
        <div className={`p-4 rounded-2xl border ${s.observed_delta_total >= 0 ? "bg-emerald-50 border-emerald-200" : "bg-rose-50 border-rose-200"}`} data-testid="da-delta-card">
          <div className="text-[10px] uppercase font-bold text-stone-500">Toplam Δ vs P50</div>
          <div className={`text-lg font-black ${s.observed_delta_total >= 0 ? "text-emerald-900" : "text-rose-900"}`}>{s.observed_delta_total}</div>
        </div>
      </div>

      <p className="text-[11px] text-stone-400 bg-stone-50 border border-stone-200 rounded-xl px-3 py-2" data-testid="da-disclaimer">
        ⚠ {s.impact_disclaimer}
      </p>

      {exp && (
        <div className="bg-indigo-50 border border-indigo-200 rounded-2xl p-4" data-testid="da-experiment-card">
          <p className="text-[10px] font-black uppercase text-indigo-700 mb-1">🧪 A/B Nedensel Etki (kontrollü holdout)</p>
          {exp.holdout_n > 0 ? (
            <p className="text-sm text-stone-700">
              Uygulanan {exp.applied_n} karar Ø <b>{exp.applied_avg_revenue}</b>/gece · Holdout {exp.holdout_n} karar Ø <b>{exp.holdout_avg_revenue}</b>/gece →
              nedensel uplift: <b className={exp.causal_uplift_per_night >= 0 ? "text-emerald-700" : "text-rose-700"}> {exp.causal_uplift_per_night > 0 ? "+" : ""}{exp.causal_uplift_per_night}/gece</b>
            </p>
          ) : (
            <p className="text-xs text-stone-500">{exp.label} — aktif holdout oranı: %{exp.holdout_pct}. Deney açıkken kararların bir kısmı rastgele uygulanmaz ve gerçek nedensel etki ölçülür.</p>
          )}
        </div>
      )}

      <div className="bg-white border border-stone-200 rounded-2xl divide-y divide-stone-100" data-testid="da-list">
        {data.decisions.length === 0 && <p className="p-6 text-sm text-stone-400 text-center">Son 120 günde fiyat kararı yok — AI fiyatlamayı çalıştırın.</p>}
        {data.decisions.map((d, i) => (
          <div key={i} className="px-4 py-3 flex items-center gap-4 flex-wrap" data-testid={`da-row-${i}`}>
            <div className="w-40">
              <p className="text-xs font-bold text-stone-800">{d.target_date}</p>
              <p className="text-[10px] text-stone-400">{d.room_type || d.source}</p>
            </div>
            <div className="text-xs text-stone-600 w-32">
              {d.prev_rate} → <span className="font-black text-stone-900">{d.new_rate}</span>
              <span className={`ml-1 ${(d.delta_pct || 0) >= 0 ? "text-emerald-600" : "text-rose-600"}`}>({d.delta_pct > 0 ? "+" : ""}{d.delta_pct}%)</span>
            </div>
            <div className="flex-1 min-w-[180px]">
              <div className="flex justify-between text-[9px] text-stone-400 mb-0.5">
                <span>P10 {d.band.p10}</span><span className="font-bold text-stone-600">P50 {d.band.p50}</span><span>P90 {d.band.p90}</span>
              </div>
              <div className="h-1.5 rounded-full bg-gradient-to-r from-rose-200 via-amber-200 to-emerald-300" />
            </div>
            <span className={`flex items-center gap-1 text-[10px] font-bold px-2 py-1 rounded-full ${d.readback.applied ? "bg-emerald-100 text-emerald-700" : "bg-stone-100 text-stone-500"}`} title={d.readback.evidence}>
              {d.readback.applied ? <CheckCircle size={11} weight="fill" /> : <XCircle size={11} />}
              {d.readback.applied ? "Uygulandı" : "Uygulanmadı"}
            </span>
            {d.impact.status === "observed" ? (
              <span className={`text-[10px] font-bold px-2 py-1 rounded-full ${d.impact.delta_vs_p50 >= 0 ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700"}`}>
                Fiili {d.impact.actual_revenue} · Δ {d.impact.delta_vs_p50 > 0 ? "+" : ""}{d.impact.delta_vs_p50} (gözlemsel)
              </span>
            ) : (
              <span className="text-[10px] px-2 py-1 rounded-full bg-stone-50 text-stone-400">Etki bekleniyor</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
