import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Leaf, FilePdf, TrendUp, TrendDown, Plus, X } from "@phosphor-icons/react";

const API_PFX = `${process.env.REACT_APP_BACKEND_URL}/api/esg`;

const SCOPE_COLOR = {
  scope1: "bg-amber-500",
  scope2: "bg-sky-500",
  scope3: "bg-violet-500",
};

export default function CarbonReportingV2Panel({ propertyId = "default" }) {
  const [year, setYear] = useState(new Date().getFullYear().toString());
  const [scope, setScope] = useState(null);
  const [yoy, setYoy] = useState(null);
  const [offsets, setOffsets] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showOffset, setShowOffset] = useState(false);
  const [offsetForm, setOffsetForm] = useState({ tonnes_co2e: "", amount_paid: "", provider: "Verified UK Woodland" });

  const reload = useCallback(async () => {
    if (!propertyId || propertyId === "all") return;
    setLoading(true);
    try {
      const [s, y, o] = await Promise.all([
        axios.get(`${API_PFX}/${propertyId}/scope-breakdown?year=${year}`, { withCredentials: true }),
        axios.get(`${API_PFX}/${propertyId}/yoy?year=${year}`, { withCredentials: true }),
        axios.get(`${API_PFX}/${propertyId}/offset-purchases?year=${year}`, { withCredentials: true }),
      ]);
      setScope(s.data); setYoy(y.data); setOffsets(o.data);
    } catch (e) { toast.error("Veriler yüklenemedi"); }
    finally { setLoading(false); }
  }, [propertyId, year]);

  useEffect(() => { reload(); }, [reload]);

  async function addOffset() {
    try {
      await axios.post(`${API_PFX}/${propertyId}/offset-purchases`, {
        tonnes_co2e: Number(offsetForm.tonnes_co2e || 0),
        amount_paid: Number(offsetForm.amount_paid || 0),
        provider: offsetForm.provider,
      }, { withCredentials: true });
      toast.success("Karbon offset kaydedildi");
      setShowOffset(false); setOffsetForm({ tonnes_co2e: "", amount_paid: "", provider: "Verified UK Woodland" });
      reload();
    } catch (e) { toast.error(e?.response?.data?.detail || "Kaydedilemedi"); }
  }

  async function downloadReport() {
    try {
      const t = localStorage.getItem("access_token") || "";
      const res = await fetch(`${API_PFX}/${propertyId}/report.pdf?year=${year}`, {
        credentials: "include",
        headers: t ? { Authorization: `Bearer ${t}` } : {},
      });
      if (!res.ok) throw new Error();
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `carbon_report_${propertyId.slice(0, 8)}_${year}.pdf`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
    } catch { toast.error("PDF indirilemedi"); }
  }

  if (propertyId === "all") {
    return (
      <div className="p-5 text-center text-stone-500 text-sm" data-testid="carbon-v2-empty">
        Lütfen üst menüden bir mülk seçin. Karbon raporu mülke özgüdür.
      </div>
    );
  }

  const netKg = scope ? Math.max(0, scope.total_kg - (offsets?.total_tonnes_offset || 0) * 1000) : 0;
  const offsetPct = scope && scope.total_kg
    ? Math.min(100, Math.round((offsets?.total_tonnes_offset || 0) * 1000 / scope.total_kg * 100))
    : 0;

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="carbon-v2-panel">
      <div className="mb-5 flex items-start justify-between gap-3 flex-wrap">
        <div>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
            <Leaf size={12} weight="fill" className="text-emerald-500" />
            <span>Carbon Reporting v2 · GHG Protocol</span>
          </div>
          <h1 className="text-2xl font-semibold text-stone-900">Karbon Raporu (Green Key / Green Globe uyumlu)</h1>
          <p className="text-sm text-stone-500 mt-1 max-w-2xl">
            Scope 1/2/3 emisyonlarınız, yıllık değişim, gönüllü karbon offset alımları ve sertifikasyon için A4 PDF.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select value={year} onChange={e => setYear(e.target.value)} data-testid="carbon-year"
                  className="px-3 py-1.5 text-xs border border-stone-300 rounded-lg bg-white">
            {[0, -1, -2].map(d => {
              const y = (new Date().getFullYear() + d).toString();
              return <option key={y} value={y}>{y}</option>;
            })}
          </select>
          <button onClick={downloadReport} data-testid="carbon-pdf-btn"
                  className="px-3 py-1.5 text-xs text-white bg-emerald-700 rounded-lg inline-flex items-center gap-1.5 hover:bg-emerald-800">
            <FilePdf size={13} /> PDF İndir
          </button>
        </div>
      </div>

      {loading && <div className="text-center py-12 text-stone-400 text-sm">Yükleniyor…</div>}

      {!loading && scope && (
        <>
          {/* Headline */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
            <KPI label="Brüt Emisyon (tCO₂e)" value={scope.total_tonnes.toFixed(2)} color="text-stone-900" />
            <KPI label="Offset Alındı (t)" value={(offsets?.total_tonnes_offset || 0).toFixed(2)} color="text-emerald-700" />
            <KPI label="Net Emisyon (t)" value={(netKg / 1000).toFixed(2)} color="text-amber-600" />
            <KPI label="Offset Kapsamı" value={`${offsetPct}%`} color={offsetPct >= 50 ? "text-emerald-700" : "text-stone-700"} />
          </div>

          {/* Scope breakdown */}
          <div className="bg-white border border-stone-200 rounded-xl p-4 mb-5" data-testid="carbon-scope">
            <h3 className="text-sm font-semibold mb-3">GHG Protokol Scope Dağılımı</h3>
            <div className="flex h-8 rounded overflow-hidden mb-3 bg-stone-100">
              <div className={SCOPE_COLOR.scope1} style={{ width: `${scope.scope1_pct}%` }} title={`Scope 1: ${scope.scope1_pct}%`}></div>
              <div className={SCOPE_COLOR.scope2} style={{ width: `${scope.scope2_pct}%` }} title={`Scope 2: ${scope.scope2_pct}%`}></div>
              <div className={SCOPE_COLOR.scope3} style={{ width: `${scope.scope3_pct}%` }} title={`Scope 3: ${scope.scope3_pct}%`}></div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-xs">
              <ScopeRow color="bg-amber-500" label="Scope 1 · Doğrudan (gaz, on-site yakıt)"
                        kg={scope.scope1_kg} pct={scope.scope1_pct} />
              <ScopeRow color="bg-sky-500" label="Scope 2 · Dolaylı (şebeke elektriği)"
                        kg={scope.scope2_kg} pct={scope.scope2_pct} />
              <ScopeRow color="bg-violet-500" label="Scope 3 · Diğer dolaylı (atık, tedarik)"
                        kg={scope.scope3_kg} pct={scope.scope3_pct} />
            </div>
            <div className="mt-3 text-[11px] text-stone-500">
              Faktörler · Elektrik: <b>{scope.factors_used.grid_electricity}</b> kg CO₂e/kWh ·
              Gaz: <b>{scope.factors_used.natural_gas}</b> · Atık: <b>{scope.factors_used.waste_landfill}</b> ·
              {scope.months_with_data} ay verisi
            </div>
          </div>

          {/* YoY */}
          {yoy && (
            <div className="bg-white border border-stone-200 rounded-xl overflow-hidden mb-5" data-testid="carbon-yoy">
              <div className="px-4 py-2.5 border-b border-stone-200 text-sm font-semibold">
                Yıldan Yıla Değişim ({yoy.prev_year} → {yoy.year})
              </div>
              <table className="w-full text-sm">
                <thead className="bg-stone-50 text-[11px] uppercase tracking-wider text-stone-500">
                  <tr>
                    <th className="px-4 py-2 text-left">Metrik</th>
                    <th className="px-4 py-2 text-right">{yoy.prev_year}</th>
                    <th className="px-4 py-2 text-right">{yoy.year}</th>
                    <th className="px-4 py-2 text-right">Değişim</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    { k: "kwh", label: "Elektrik (kWh)" },
                    { k: "gas_kwh", label: "Gaz (kWh)" },
                    { k: "water_litres", label: "Su (litre)" },
                    { k: "waste_kg", label: "Atık (kg)" },
                  ].map(m => {
                    const c = yoy.change_pct[m.k];
                    const goodIfNegative = true;
                    const color = goodIfNegative ? (c <= 0 ? "text-emerald-600" : "text-rose-600") : "text-stone-700";
                    return (
                      <tr key={m.k} className="border-t border-stone-100">
                        <td className="px-4 py-2">{m.label}</td>
                        <td className="px-4 py-2 text-right">{yoy.previous[m.k].toLocaleString("tr-TR")}</td>
                        <td className="px-4 py-2 text-right">{yoy.current[m.k].toLocaleString("tr-TR")}</td>
                        <td className={`px-4 py-2 text-right font-semibold inline-flex items-center justify-end gap-1 ${color}`}>
                          {c >= 0 ? <TrendUp size={12} /> : <TrendDown size={12} />}
                          {c >= 0 ? "+" : ""}{c.toFixed(1)}%
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Offsets */}
          <div className="bg-white border border-stone-200 rounded-xl overflow-hidden mb-5" data-testid="carbon-offsets">
            <div className="px-4 py-2.5 border-b border-stone-200 flex items-center justify-between">
              <h3 className="text-sm font-semibold">
                Karbon Offset Alımları · <span className="text-emerald-700">{(offsets?.total_tonnes_offset || 0).toFixed(2)} t · £{(offsets?.total_spend || 0).toFixed(2)}</span>
              </h3>
              <button onClick={() => setShowOffset(true)} data-testid="carbon-add-offset"
                      className="text-xs px-2.5 py-1 bg-emerald-700 text-white rounded inline-flex items-center gap-1 hover:bg-emerald-800">
                <Plus size={12} /> Offset Ekle
              </button>
            </div>
            {(offsets?.purchases || []).length === 0 ? (
              <div className="text-center py-8 text-stone-400 text-xs" data-testid="carbon-offsets-empty">Henüz karbon offset alımı yok.</div>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-stone-50 text-[11px] uppercase tracking-wider text-stone-500">
                  <tr>
                    <th className="px-4 py-2 text-left">Tarih</th>
                    <th className="px-4 py-2 text-left">Sağlayıcı</th>
                    <th className="px-4 py-2 text-right">Ton CO₂e</th>
                    <th className="px-4 py-2 text-right">Tutar</th>
                  </tr>
                </thead>
                <tbody>
                  {offsets.purchases.map(p => (
                    <tr key={p.id} className="border-t border-stone-100" data-testid={`carbon-offset-${p.id}`}>
                      <td className="px-4 py-2 text-xs">{new Date(p.purchased_at).toLocaleDateString("tr-TR")}</td>
                      <td className="px-4 py-2 text-xs">{p.provider}</td>
                      <td className="px-4 py-2 text-right">{p.tonnes_co2e.toFixed(3)}</td>
                      <td className="px-4 py-2 text-right">£{p.amount_paid.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}

      {showOffset && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={() => setShowOffset(false)}>
          <div className="bg-white rounded-xl w-full max-w-md p-5" onClick={e => e.stopPropagation()} data-testid="carbon-offset-modal">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-semibold">Karbon Offset Ekle</h3>
              <button onClick={() => setShowOffset(false)}><X size={16} /></button>
            </div>
            <div className="space-y-3">
              <label className="block text-xs text-stone-700">Ton CO₂e
                <input type="number" step="0.01" value={offsetForm.tonnes_co2e}
                       onChange={e => setOffsetForm({ ...offsetForm, tonnes_co2e: e.target.value })}
                       className="w-full mt-1 px-3 py-2 text-sm border border-stone-300 rounded-lg"
                       data-testid="carbon-offset-tonnes" />
              </label>
              <label className="block text-xs text-stone-700">Ödenen tutar (£)
                <input type="number" step="0.01" value={offsetForm.amount_paid}
                       onChange={e => setOffsetForm({ ...offsetForm, amount_paid: e.target.value })}
                       className="w-full mt-1 px-3 py-2 text-sm border border-stone-300 rounded-lg"
                       data-testid="carbon-offset-amount" />
              </label>
              <label className="block text-xs text-stone-700">Sağlayıcı
                <input value={offsetForm.provider}
                       onChange={e => setOffsetForm({ ...offsetForm, provider: e.target.value })}
                       className="w-full mt-1 px-3 py-2 text-sm border border-stone-300 rounded-lg" />
              </label>
              <button onClick={addOffset} disabled={!Number(offsetForm.tonnes_co2e)} data-testid="carbon-offset-save"
                      className="w-full py-2 text-sm text-white bg-emerald-700 rounded-lg disabled:opacity-50">
                Kaydet
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function KPI({ label, value, color }) {
  return (
    <div className="bg-white border border-stone-200 rounded-xl p-3">
      <div className="text-[10px] uppercase tracking-wider text-stone-500">{label}</div>
      <div className={`text-xl font-semibold mt-0.5 ${color || "text-stone-900"}`}>{value}</div>
    </div>
  );
}

function ScopeRow({ color, label, kg, pct }) {
  return (
    <div className="flex items-center gap-2">
      <span className={`w-3 h-3 rounded ${color}`}></span>
      <span className="flex-1 truncate">{label}</span>
      <span className="text-stone-500">{kg.toLocaleString("tr-TR")} kg · {pct}%</span>
    </div>
  );
}
