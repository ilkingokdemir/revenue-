import { useState, useEffect, useMemo } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Globe2, RefreshCw, Plus, X, TrendingUp, Banknote,
  ArrowLeftRight, Building2, AlertTriangle,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const fmt = (v, cur = "GBP", sym = "£") =>
  `${sym}${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const EMPTY_RATE = { code: "", rate_to_base: 1, as_of: "", notes: "" };

export const CurrencyFxPanel = ({ user }) => {
  const [tab, setTab] = useState("overview");
  const [settings, setSettings] = useState(null);
  const [rates, setRates] = useState([]);
  const [aging, setAging] = useState(null);
  const [portfolio, setPortfolio] = useState(null);
  const [loading, setLoading] = useState(false);
  const [rateForm, setRateForm] = useState(null);
  const [converter, setConverter] = useState({ amount: 100, source: "EUR", target: "GBP", result: null });

  const sym = (code) => settings?.symbols?.[code] || code + " ";

  const loadAll = async () => {
    setLoading(true);
    try {
      const [s, r, a, p] = await Promise.all([
        axios.get(`${API}/currency-fx/settings`),
        axios.get(`${API}/currency-fx/rates`),
        axios.get(`${API}/currency-fx/ar-aging`),
        axios.get(`${API}/currency-fx/portfolio-summary`),
      ]);
      setSettings(s.data);
      setRates(r.data || []);
      setAging(a.data);
      setPortfolio(p.data);
    } catch (e) {
      toast.error("Failed to load currency data");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { loadAll(); }, []);

  const saveSettings = async (patch) => {
    try {
      const body = { ...settings, ...patch };
      const { data } = await axios.put(`${API}/currency-fx/settings`, body);
      toast.success("Settings saved");
      setSettings((s) => ({ ...s, ...data }));
      loadAll();
    } catch (e) { toast.error("Failed to save"); }
  };

  const saveRate = async () => {
    if (!rateForm.code || !rateForm.rate_to_base) return toast.error("Code and rate required");
    try {
      await axios.post(`${API}/currency-fx/rates`, {
        code: rateForm.code.toUpperCase(),
        rate_to_base: parseFloat(rateForm.rate_to_base),
        as_of: rateForm.as_of || undefined,
        notes: rateForm.notes || "",
      });
      toast.success("Rate saved");
      setRateForm(null);
      loadAll();
    } catch (e) { toast.error(e?.response?.data?.detail || "Save failed"); }
  };

  const deleteRate = async (code) => {
    if (!window.confirm(`Delete rate for ${code}?`)) return;
    try {
      await axios.delete(`${API}/currency-fx/rates/${code}`);
      toast.success("Deleted");
      loadAll();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const runConvert = async () => {
    try {
      const { data } = await axios.post(`${API}/currency-fx/convert`, {
        amount: parseFloat(converter.amount || 0),
        source: converter.source,
        target: converter.target,
      });
      setConverter((c) => ({ ...c, result: data }));
    } catch (e) { toast.error("Convert failed"); }
  };

  const base = settings?.base_currency || "GBP";
  const baseSym = sym(base);

  const totalAr = aging?.total || 0;
  const totalRev = portfolio?.totals?.revenue_base || 0;
  const totalArPort = portfolio?.totals?.ar_base || 0;
  const overdue = useMemo(() => {
    if (!aging) return 0;
    const b = aging.buckets || {};
    return (b.d30 || 0) + (b.d60 || 0) + (b.d90 || 0) + (b.over90 || 0);
  }, [aging]);

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto" data-testid="currency-fx-panel">
      {/* Header */}
      <div className="bg-gradient-to-br from-indigo-50 via-sky-50 to-white border border-indigo-100 rounded-2xl p-6">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-wider text-indigo-700">
              <Globe2 className="w-4 h-4" />Multi-Currency · Portfolio
            </div>
            <h1 className="text-3xl font-black text-stone-900 mt-1">Currency &amp; FX</h1>
            <p className="text-sm text-stone-600 mt-1">
              Consolidate revenue &amp; receivables across properties. Base currency: <b>{base}</b>.
              {aging?.as_of && <span className="text-stone-400"> · As of {aging.as_of}</span>}
            </p>
          </div>
          <button onClick={loadAll} data-testid="fx-refresh"
            className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-stone-200 hover:border-stone-300 rounded-lg text-xs font-semibold">
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />Refresh
          </button>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-5">
          <KPI label={`Portfolio Revenue (${base})`} value={fmt(totalRev, base, baseSym)} tint="emerald" />
          <KPI label={`Total Open AR (${base})`} value={fmt(totalAr, base, baseSym)} tint="sky" />
          <KPI label={`Overdue (${base})`} value={fmt(overdue, base, baseSym)} tint={overdue > 0 ? "rose" : "stone"} />
          <KPI label="Active Currencies" value={rates.length} tint="amber" />
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-stone-200 overflow-x-auto">
        {[
          { id: "overview", label: "Portfolio Consolidation", icon: Building2 },
          { id: "ar", label: "Consolidated AR Aging", icon: AlertTriangle },
          { id: "rates", label: "FX Rate Table", icon: TrendingUp },
          { id: "convert", label: "Converter", icon: ArrowLeftRight },
          { id: "settings", label: "Settings", icon: Banknote },
        ].map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)} data-testid={`fx-tab-${t.id}`}
            className={`flex items-center gap-1.5 px-4 py-2 text-sm font-semibold border-b-2 -mb-px whitespace-nowrap ${
              tab === t.id ? "border-indigo-500 text-stone-900" : "border-transparent text-stone-400 hover:text-stone-700"
            }`}>
            <t.icon className="w-3.5 h-3.5" />{t.label}
          </button>
        ))}
      </div>

      {/* Portfolio overview */}
      {tab === "overview" && portfolio && (
        <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-stone-50 text-[10px] uppercase text-stone-500">
              <tr>
                <th className="p-3 text-left">Property</th>
                <th className="p-3 text-center">Native Currency</th>
                <th className="p-3 text-right">Revenue (native)</th>
                <th className="p-3 text-right">Revenue ({base})</th>
                <th className="p-3 text-right">Open AR (native)</th>
                <th className="p-3 text-right">Open AR ({base})</th>
              </tr>
            </thead>
            <tbody>
              {portfolio.properties.length === 0 && (
                <tr><td colSpan={6} className="p-8 text-center text-stone-400">No properties configured.</td></tr>
              )}
              {portfolio.properties.map((p) => (
                <tr key={p.property_id} className="border-t border-stone-100 hover:bg-stone-50"
                    data-testid={`fx-row-${p.property_id}`}>
                  <td className="p-3 font-semibold text-stone-800">{p.property_name}</td>
                  <td className="p-3 text-center">
                    <span className="inline-block px-2 py-0.5 rounded-full bg-stone-100 text-[10px] font-bold text-stone-600">{p.currency}</span>
                  </td>
                  <td className="p-3 text-right text-stone-600 text-xs">{fmt(p.revenue_native, p.currency, sym(p.currency))}</td>
                  <td className="p-3 text-right font-bold text-emerald-600">{fmt(p.revenue_base, base, baseSym)}</td>
                  <td className="p-3 text-right text-stone-600 text-xs">{fmt(p.ar_native, p.currency, sym(p.currency))}</td>
                  <td className={`p-3 text-right font-bold ${p.ar_base > 0 ? "text-amber-600" : "text-stone-400"}`}>
                    {fmt(p.ar_base, base, baseSym)}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot className="bg-stone-100 font-bold">
              <tr>
                <td className="p-3" colSpan={3}>Portfolio Total</td>
                <td className="p-3 text-right text-emerald-700">{fmt(portfolio.totals.revenue_base, base, baseSym)}</td>
                <td className="p-3"></td>
                <td className="p-3 text-right text-amber-700">{fmt(portfolio.totals.ar_base, base, baseSym)}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}

      {/* AR aging consolidated */}
      {tab === "ar" && aging && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {[
              { k: "current", label: "Current", tint: "emerald" },
              { k: "d30", label: "1-30 days", tint: "sky" },
              { k: "d60", label: "31-60 days", tint: "amber" },
              { k: "d90", label: "61-90 days", tint: "orange" },
              { k: "over90", label: "90+ days", tint: "rose" },
            ].map((b) => (
              <KPI key={b.k} label={b.label} value={fmt(aging.buckets[b.k] || 0, base, baseSym)} tint={b.tint} />
            ))}
          </div>
          <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b border-stone-200 bg-stone-50">
              <h3 className="text-sm font-bold text-stone-800">By Currency</h3>
              <p className="text-[11px] text-stone-500">Open invoices normalised to {base} using latest FX rates.</p>
            </div>
            <table className="w-full text-sm">
              <thead className="bg-stone-50 text-[10px] uppercase text-stone-500">
                <tr>
                  <th className="p-3 text-left">Currency</th>
                  <th className="p-3 text-right">Rate → {base}</th>
                  <th className="p-3 text-right">Invoices</th>
                  <th className="p-3 text-right">Open (native)</th>
                  <th className="p-3 text-right">Open ({base})</th>
                </tr>
              </thead>
              <tbody>
                {aging.by_currency.length === 0 && (
                  <tr><td colSpan={5} className="p-8 text-center text-stone-400">No open receivables.</td></tr>
                )}
                {aging.by_currency.map((r) => (
                  <tr key={r.currency} className="border-t border-stone-100">
                    <td className="p-3 font-semibold">{r.currency}</td>
                    <td className="p-3 text-right font-mono text-xs">{Number(r.rate).toFixed(4)}</td>
                    <td className="p-3 text-right">{r.invoices}</td>
                    <td className="p-3 text-right text-stone-600 text-xs">{fmt(r.native_total, r.currency, sym(r.currency))}</td>
                    <td className="p-3 text-right font-bold text-amber-700">{fmt(r.base_total, base, baseSym)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="bg-stone-100 font-bold">
                <tr>
                  <td className="p-3" colSpan={4}>Consolidated Total</td>
                  <td className="p-3 text-right text-amber-700">{fmt(aging.total, base, baseSym)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      )}

      {/* FX rate table */}
      {tab === "rates" && (
        <div className="space-y-3">
          <div className="flex justify-end">
            <button onClick={() => setRateForm({ ...EMPTY_RATE })} data-testid="fx-new-rate"
              className="flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-semibold">
              <Plus className="w-4 h-4" /> Add / Update Rate
            </button>
          </div>
          <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-stone-50 text-[10px] uppercase text-stone-500">
                <tr>
                  <th className="p-3 text-left">Code</th>
                  <th className="p-3 text-right">Rate to {base}</th>
                  <th className="p-3 text-left">As Of</th>
                  <th className="p-3 text-left">Source</th>
                  <th className="p-3 text-left">Notes</th>
                  <th className="p-3 text-center">Actions</th>
                </tr>
              </thead>
              <tbody>
                {rates.length === 0 && (
                  <tr><td colSpan={6} className="p-8 text-center text-stone-400">No FX rates configured.</td></tr>
                )}
                {rates.map((r) => (
                  <tr key={r.code} className="border-t border-stone-100 hover:bg-stone-50" data-testid={`fx-rate-${r.code}`}>
                    <td className="p-3 font-bold text-stone-800">{r.code} <span className="text-stone-400 font-normal">{sym(r.code)}</span></td>
                    <td className="p-3 text-right font-mono">{Number(r.rate_to_base).toFixed(6)}</td>
                    <td className="p-3 text-xs text-stone-500">{r.as_of}</td>
                    <td className="p-3 text-xs text-stone-500">{r.source}</td>
                    <td className="p-3 text-xs text-stone-500">{r.notes}</td>
                    <td className="p-3 text-center">
                      <button onClick={() => setRateForm({ ...r })} className="text-xs text-sky-600 hover:underline mr-2">Edit</button>
                      {r.code !== base && (
                        <button onClick={() => deleteRate(r.code)} className="text-xs text-rose-600 hover:underline">Delete</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-[11px] text-stone-500 bg-stone-50 border border-stone-200 rounded-lg p-3">
            <b>Rate convention:</b> <code className="font-mono">rate_to_base</code> = value of 1 unit of <i>code</i>
            expressed in the base currency ({base}). E.g. if base is GBP and 1 EUR = 0.86 GBP, enter <b>0.86</b>.
          </p>
        </div>
      )}

      {/* Converter */}
      {tab === "convert" && (
        <div className="bg-white border border-stone-200 rounded-xl p-6 max-w-2xl">
          <h3 className="text-lg font-bold text-stone-900 mb-4">Quick Converter</h3>
          <div className="grid grid-cols-4 gap-3 items-end">
            <Field label="Amount">
              <input type="number" value={converter.amount}
                onChange={(e) => setConverter({ ...converter, amount: e.target.value })}
                data-testid="fx-convert-amount"
                className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" />
            </Field>
            <Field label="From">
              <select value={converter.source}
                onChange={(e) => setConverter({ ...converter, source: e.target.value })}
                data-testid="fx-convert-from"
                className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm">
                {(settings?.available_codes || []).map((c) => <option key={c}>{c}</option>)}
              </select>
            </Field>
            <Field label="To">
              <select value={converter.target}
                onChange={(e) => setConverter({ ...converter, target: e.target.value })}
                data-testid="fx-convert-to"
                className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm">
                {(settings?.available_codes || []).map((c) => <option key={c}>{c}</option>)}
              </select>
            </Field>
            <button onClick={runConvert} data-testid="fx-convert-btn"
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-semibold h-10">
              Convert
            </button>
          </div>
          {converter.result && (
            <div className="mt-5 bg-indigo-50 border border-indigo-200 rounded-xl p-4">
              <div className="text-[11px] text-indigo-700 font-bold uppercase">Result</div>
              <div className="text-3xl font-black text-stone-900 mt-1">
                {fmt(converter.result.converted, converter.result.to, sym(converter.result.to))}
              </div>
              <div className="text-xs text-stone-500 mt-1">
                {fmt(converter.result.amount, converter.result.from, sym(converter.result.from))} →
                {" "}{converter.result.to} · normalised via {converter.result.base_currency}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Settings */}
      {tab === "settings" && settings && (
        <div className="bg-white border border-stone-200 rounded-xl p-6 max-w-xl space-y-4">
          <h3 className="text-lg font-bold text-stone-900">Portfolio Currency Settings</h3>
          <Field label="Base Currency (reporting)">
            <select value={settings.base_currency}
              onChange={(e) => saveSettings({ base_currency: e.target.value })}
              data-testid="fx-base-currency"
              className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm">
              {(settings.available_codes || []).map((c) => <option key={c}>{c}</option>)}
            </select>
            <p className="text-[11px] text-stone-400 mt-1">
              All revenue &amp; AR consolidation reports are expressed in this currency.
            </p>
          </Field>
          <Field label="Rounding Mode">
            <select value={settings.rounding_mode || "banker"}
              onChange={(e) => saveSettings({ rounding_mode: e.target.value })}
              className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm">
              <option value="banker">Banker's rounding (default)</option>
              <option value="half_up">Half up</option>
              <option value="down">Truncate (down)</option>
            </select>
          </Field>
        </div>
      )}

      {/* Rate modal */}
      {rateForm && (
        <Modal title={rateForm.id ? `Update ${rateForm.code}` : "Add FX Rate"} onClose={() => setRateForm(null)}>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Currency Code *">
              <input value={rateForm.code} onChange={(e) => setRateForm({ ...rateForm, code: e.target.value.toUpperCase() })}
                maxLength={3} data-testid="fx-form-code"
                className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm uppercase" placeholder="EUR" />
            </Field>
            <Field label={`Rate to ${base} *`}>
              <input type="number" step="0.0001" value={rateForm.rate_to_base}
                onChange={(e) => setRateForm({ ...rateForm, rate_to_base: e.target.value })}
                data-testid="fx-form-rate"
                className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" />
            </Field>
            <Field label="As Of (date)">
              <input type="date" value={rateForm.as_of || ""}
                onChange={(e) => setRateForm({ ...rateForm, as_of: e.target.value })}
                className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" />
            </Field>
            <Field label="Notes">
              <input value={rateForm.notes || ""} onChange={(e) => setRateForm({ ...rateForm, notes: e.target.value })}
                className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" />
            </Field>
          </div>
          <div className="flex justify-end gap-2 mt-4">
            <button onClick={() => setRateForm(null)} className="px-4 py-2 text-sm">Cancel</button>
            <button onClick={saveRate} data-testid="fx-form-save"
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-semibold">
              Save
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
};

const KPI = ({ label, value, tint = "stone" }) => {
  const tints = {
    emerald: "from-emerald-500 to-teal-600",
    rose: "from-rose-500 to-red-600",
    sky: "from-sky-500 to-blue-600",
    amber: "from-amber-500 to-orange-600",
    orange: "from-orange-500 to-rose-600",
    stone: "from-stone-400 to-stone-600",
  };
  return (
    <div className={`rounded-xl p-4 text-white bg-gradient-to-br ${tints[tint]}`}>
      <div className="text-[10px] font-bold uppercase opacity-80">{label}</div>
      <div className="text-2xl font-black mt-1">{value}</div>
    </div>
  );
};

const Field = ({ label, children }) => (
  <div>
    <label className="block text-[10px] font-bold uppercase text-stone-500 mb-1">{label}</label>
    {children}
  </div>
);

const Modal = ({ title, onClose, children }) => (
  <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" onClick={onClose}>
    <div className="bg-white rounded-2xl p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-bold text-stone-900">{title}</h2>
        <button onClick={onClose} className="p-1 hover:bg-stone-100 rounded-lg"><X className="w-4 h-4 text-stone-500" /></button>
      </div>
      {children}
    </div>
  </div>
);

export default CurrencyFxPanel;
