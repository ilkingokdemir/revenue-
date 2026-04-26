/**
 * Currency / FX Rates Panel
 * -------------------------
 * Edit per-property FX overrides + live conversion checker.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, DollarSign, RefreshCw, CheckCircle2 } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function CurrencyPanel({ propertyId, hotelName = "" }) {
  const [rates, setRates] = useState({});
  const [keys, setKeys] = useState([]);
  const [edited, setEdited] = useState({});
  const [test, setTest] = useState({ amount: 100, from: "GBP", to: "EUR" });
  const [result, setResult] = useState(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    const { data } = await axios.get(`${API}/currency/rates?property_id=${propertyId}`);
    setRates(data.rates || {}); setKeys(data.currencies || []); setEdited({});
  }, [propertyId]);

  useEffect(() => { if (propertyId) load(); }, [propertyId, load]);

  const save = async () => {
    setSaving(true);
    try {
      await axios.post(`${API}/currency/rates`, { property_id: propertyId, rates: edited });
      toast.success("Rates saved");
      load();
    } catch { toast.error("Save failed"); }
    setSaving(false);
  };

  const convert = async () => {
    const { data } = await axios.post(`${API}/currency/convert`, { ...test, property_id: propertyId });
    setResult(data);
  };

  return (
    <div className="space-y-6" data-testid="currency-panel">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2">
            <DollarSign className="w-5 h-5 text-emerald-400" />
            <h2 className="text-2xl font-semibold text-stone-100">Multi-Currency Rates</h2>
          </div>
          <p className="text-sm text-stone-400 mt-1">{hotelName ? `${hotelName} · ` : ""}FX overrides for the booking widget. Base is GBP.</p>
        </div>
        <button data-testid="fx-refresh-btn" onClick={load} className="flex items-center gap-2 px-3 py-2 rounded-lg bg-stone-800 hover:bg-stone-700 text-sm text-stone-100 border border-stone-700">
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4">
        <div className="text-stone-100 font-semibold mb-2">Conversion test</div>
        <div className="flex flex-wrap gap-2 items-end">
          <input data-testid="fx-amount" type="number" value={test.amount} onChange={(e) => setTest({ ...test, amount: parseFloat(e.target.value) || 0 })} className="w-28 px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm" />
          <select value={test.from} onChange={(e) => setTest({ ...test, from: e.target.value })} className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm">
            {keys.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <span className="text-stone-500">→</span>
          <select value={test.to} onChange={(e) => setTest({ ...test, to: e.target.value })} className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm">
            {keys.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <button data-testid="fx-convert-btn" onClick={convert} className="px-3 py-2 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 text-sm">Convert</button>
          {result && (
            <span className="text-stone-100 text-sm">
              {result.amount_in} {result.from} = <strong className="text-emerald-300">{result.amount_out} {result.to}</strong>
              <span className="text-stone-500 text-xs ml-2">(rate {result.rate_used})</span>
            </span>
          )}
        </div>
      </div>

      <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="text-stone-100 font-semibold">Rate overrides (vs GBP)</div>
          <button data-testid="fx-save-btn" onClick={save} disabled={saving || !Object.keys(edited).length}
            className="flex items-center gap-2 px-3 py-2 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 text-sm disabled:opacity-50">
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
            Save {Object.keys(edited).length || ""}
          </button>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-2">
          {keys.map((c) => (
            <label key={c} className="flex items-center justify-between bg-stone-800/40 rounded px-2 py-1.5">
              <span className="text-stone-300 font-mono text-xs w-12">{c}</span>
              <input data-testid={`fx-rate-${c}`} type="number" step="0.0001" value={edited[c] ?? rates[c] ?? 0}
                onChange={(e) => setEdited({ ...edited, [c]: parseFloat(e.target.value) || 0 })}
                className="w-24 px-2 py-0.5 rounded bg-stone-900 border border-stone-700 text-stone-100 text-right text-sm" />
            </label>
          ))}
        </div>
      </div>
    </div>
  );
}
