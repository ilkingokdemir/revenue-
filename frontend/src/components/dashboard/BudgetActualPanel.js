import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { CurrencyGbp, FloppyDisk, ChartLine } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/budget`;

const MONTHS = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];

export default function BudgetActualPanel({ propertyId = "default" }) {
  const [year, setYear] = useState(new Date().getFullYear().toString());
  const [budget, setBudget] = useState({ rows: [] });
  const [variance, setVariance] = useState(null);
  const [triple, setTriple] = useState(null);
  const [tab, setTab] = useState("budget");
  const [loading, setLoading] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const [b, v, t] = await Promise.all([
        axios.get(`${API}/${propertyId}/${year}`, { withCredentials: true }),
        axios.get(`${API}/${propertyId}/variance?year=${year}`, { withCredentials: true }),
        axios.get(`${API}/${propertyId}/triple?year=${year}`, { withCredentials: true }),
      ]);
      setBudget(b.data || { rows: [] });
      setVariance(v.data);
      setTriple(t.data);
    } catch (e) { toast.error("Yüklenemedi"); }
    finally { setLoading(false); }
  }, [propertyId, year]);

  useEffect(() => { reload(); }, [reload]);

  function updateRow(i, field, value) {
    const next = [...budget.rows];
    next[i] = { ...next[i], [field]: Number(value || 0) };
    setBudget({ rows: next });
  }

  async function save() {
    try {
      await axios.put(`${API}/${propertyId}/${year}`, { rows: budget.rows }, { withCredentials: true });
      toast.success("Bütçe kaydedildi");
      reload();
    } catch (e) { toast.error("Kaydedilemedi"); }
  }

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="budget-actual-panel">
      <div className="mb-4 flex items-start justify-between gap-3 flex-wrap">
        <div>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
            <CurrencyGbp size={12} weight="fill" className="text-emerald-500" />
            <span>Finance Planning</span>
          </div>
          <h1 className="text-2xl font-semibold text-stone-900">Bütçe vs Gerçekleşen</h1>
          <p className="text-sm text-stone-500 mt-1 max-w-2xl">
            Aylık gelir/oda bütçesini girin, gerçekleşen rakamlarla karşılaştırın ve sapmaları izleyin.
          </p>
        </div>
        <select value={year} onChange={e => setYear(e.target.value)}
                className="px-3 py-1.5 text-xs border border-stone-300 rounded-lg" data-testid="budget-year-select">
          {[0, 1, -1].map(d => {
            const y = (new Date().getFullYear() + d).toString();
            return <option key={y} value={y}>{y}</option>;
          })}
        </select>
      </div>

      <div className="flex gap-1 mb-4 border-b border-stone-200">
        <button onClick={() => setTab("budget")} data-testid="budget-tab-budget"
                className={`px-4 py-2 text-xs font-medium border-b-2 ${tab === "budget" ? "border-stone-900 text-stone-900" : "border-transparent text-stone-500"}`}>
          Bütçe Tablosu
        </button>
        <button onClick={() => setTab("variance")} data-testid="budget-tab-variance"
                className={`px-4 py-2 text-xs font-medium border-b-2 ${tab === "variance" ? "border-stone-900 text-stone-900" : "border-transparent text-stone-500"}`}>
          Sapma Analizi
        </button>
        <button onClick={() => setTab("triple")} data-testid="budget-tab-triple"
                className={`px-4 py-2 text-xs font-medium border-b-2 ${tab === "triple" ? "border-stone-900 text-stone-900" : "border-transparent text-stone-500"}`}>
          Bütçe · Forecast · Gerçekleşen
        </button>
        {tab === "budget" && (
          <button onClick={save} className="ml-auto px-3 py-1.5 text-xs text-white bg-stone-900 rounded-lg inline-flex items-center gap-1.5 mb-1" data-testid="budget-save">
            <FloppyDisk size={13} /> Kaydet
          </button>
        )}
      </div>

      {loading && <div className="text-center py-12 text-stone-400 text-sm">Yükleniyor…</div>}

      {!loading && tab === "budget" && (
        <div className="bg-white border border-stone-200 rounded-xl overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-stone-50 text-[11px] uppercase tracking-wider text-stone-500">
              <tr>
                <th className="px-3 py-2 text-left">Ay</th>
                <th className="px-3 py-2 text-left">Gelir Bütçesi</th>
                <th className="px-3 py-2 text-left">Oda Hedefi</th>
                <th className="px-3 py-2 text-left">ADR Hedefi</th>
                <th className="px-3 py-2 text-left">Gider Bütçesi</th>
                <th className="px-3 py-2 text-left">NOI Bütçesi</th>
              </tr>
            </thead>
            <tbody>
              {budget.rows.map((r, i) => (
                <tr key={r.month} className="border-t border-stone-100" data-testid={`budget-row-${r.month}`}>
                  <td className="px-3 py-1.5 font-medium">{MONTHS[i]}</td>
                  {["revenue_budget", "rooms_budget", "adr_budget", "expense_budget", "noi_budget"].map(f => (
                    <td key={f} className="px-3 py-1">
                      <input type="number" value={r[f] || 0} onChange={e => updateRow(i, f, e.target.value)}
                             className="w-28 px-2 py-1 text-sm border border-stone-200 rounded" />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && tab === "variance" && variance && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            <Metric label="Bütçe (yıllık)" value={`£${variance.totals?.revenue_budget?.toFixed(0)}`} />
            <Metric label="Gerçekleşen" value={`£${variance.totals?.revenue_actual?.toFixed(0)}`} />
            <Metric label="Sapma" value={`£${variance.totals?.revenue_variance?.toFixed(0)}`}
                    positive={variance.totals?.revenue_variance >= 0} />
            <Metric label="Gerçek Gece" value={variance.totals?.nights_actual} />
          </div>
          <div className="bg-white border border-stone-200 rounded-xl overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-stone-50 text-[11px] uppercase tracking-wider text-stone-500">
                <tr>
                  <th className="px-3 py-2 text-left">Ay</th>
                  <th className="px-3 py-2 text-right">Bütçe</th>
                  <th className="px-3 py-2 text-right">Gerçekleşen</th>
                  <th className="px-3 py-2 text-right">Sapma</th>
                  <th className="px-3 py-2 text-right">%</th>
                  <th className="px-3 py-2 text-right">ADR Bütçe</th>
                  <th className="px-3 py-2 text-right">ADR Gerç.</th>
                </tr>
              </thead>
              <tbody>
                {(variance.rows || []).map((r, i) => (
                  <tr key={r.month} className="border-t border-stone-100" data-testid={`variance-row-${r.month}`}>
                    <td className="px-3 py-1.5 font-medium">{MONTHS[i]}</td>
                    <td className="px-3 py-1.5 text-right">£{r.revenue_budget?.toFixed(0)}</td>
                    <td className="px-3 py-1.5 text-right">£{r.revenue_actual?.toFixed(0)}</td>
                    <td className={`px-3 py-1.5 text-right font-medium ${r.revenue_variance >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
                      £{r.revenue_variance?.toFixed(0)}
                    </td>
                    <td className={`px-3 py-1.5 text-right text-xs ${r.revenue_variance_pct >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
                      {r.revenue_variance_pct?.toFixed(1)}%
                    </td>
                    <td className="px-3 py-1.5 text-right text-xs">£{r.adr_budget?.toFixed(0)}</td>
                    <td className="px-3 py-1.5 text-right text-xs">£{r.adr_actual?.toFixed(0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {!loading && tab === "triple" && triple && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            <Metric label="Bütçe (yıl)" value={`£${triple.totals.budget.toLocaleString("tr-TR")}`} />
            <Metric label="Forecast (yıl)" value={`£${triple.totals.forecast.toLocaleString("tr-TR")}`} />
            <Metric label="Gerçekleşen (bugüne dek)" value={`£${triple.totals.actual.toLocaleString("tr-TR")}`} positive={triple.totals.actual >= triple.totals.budget * (new Date().getMonth() + 1) / 12} />
            <div className="bg-white border border-stone-200 rounded-xl p-3">
              <div className="text-[10px] uppercase tracking-wider text-stone-500">Forecast kaynağı</div>
              <div className="text-xs font-semibold mt-1 text-indigo-600" data-testid="triple-forecast-source">{triple.forecast_source}</div>
            </div>
          </div>
          <div className="bg-white border border-stone-200 rounded-xl overflow-x-auto" data-testid="triple-table">
            <table className="w-full text-sm">
              <thead className="bg-stone-50 text-[11px] uppercase tracking-wider text-stone-500">
                <tr>
                  <th className="px-3 py-2 text-left">Ay</th>
                  <th className="px-3 py-2 text-right">Bütçe</th>
                  <th className="px-3 py-2 text-right">Forecast</th>
                  <th className="px-3 py-2 text-right">Fcst vs Bütçe</th>
                  <th className="px-3 py-2 text-right">Gerçekleşen</th>
                  <th className="px-3 py-2 text-right">Gerç. vs Bütçe</th>
                </tr>
              </thead>
              <tbody>
                {triple.rows.map((r, i) => (
                  <tr key={r.month} className="border-t border-stone-100" data-testid={`triple-row-${r.month}`}>
                    <td className="px-3 py-1.5 font-medium">{MONTHS[i]}</td>
                    <td className="px-3 py-1.5 text-right">£{r.budget.toFixed(0)}</td>
                    <td className="px-3 py-1.5 text-right text-indigo-700 font-medium">{r.forecast != null ? `£${r.forecast.toFixed(0)}` : "—"}</td>
                    <td className={`px-3 py-1.5 text-right text-xs font-medium ${r.forecast_vs_budget_pct == null ? "text-stone-300" : r.forecast_vs_budget_pct >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
                      {r.forecast_vs_budget_pct != null ? `${r.forecast_vs_budget_pct >= 0 ? "+" : ""}${r.forecast_vs_budget_pct.toFixed(1)}%` : "—"}
                    </td>
                    <td className="px-3 py-1.5 text-right font-semibold">{r.actual != null ? `£${r.actual.toFixed(0)}` : <span className="text-stone-300">gelecek</span>}</td>
                    <td className={`px-3 py-1.5 text-right text-xs font-medium ${r.actual_vs_budget_pct == null ? "text-stone-300" : r.actual_vs_budget_pct >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
                      {r.actual_vs_budget_pct != null ? `${r.actual_vs_budget_pct >= 0 ? "+" : ""}${r.actual_vs_budget_pct.toFixed(1)}%` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-[11px] text-stone-400 mt-2">Forecast, kilitli bir Forecast Planlama sürümü varsa ondan gelir ("tek doğru"); yoksa canlı AI forecast kullanılır. Geçmiş aylar gerçekleşen, gelecek aylar forecast ile okunur.</p>
        </>
      )}
    </div>
  );
}

function Metric({ label, value, positive }) {
  return (
    <div className="bg-white border border-stone-200 rounded-xl p-3">
      <div className="text-[10px] uppercase tracking-wider text-stone-500">{label}</div>
      <div className={`text-lg font-semibold mt-0.5 ${positive === true ? "text-emerald-600" : positive === false ? "text-rose-600" : "text-stone-900"}`}>{value}</div>
    </div>
  );
}
