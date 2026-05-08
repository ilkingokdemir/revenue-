/**
 * Tax Presets & Resort Fee Panel
 * ------------------------------
 * One-click apply UK / EU / US / TR tax stacks. Quick-add a flat resort fee.
 * Lists currently active tax_profiles for the property.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, Globe, Plus, RefreshCw, CheckCircle2, X, Sparkles } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function TaxPresetsPanel({ propertyId, hotelName = "" }) {
  const [presets, setPresets] = useState([]);
  const [active, setActive] = useState([]);
  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState("");
  const [showResort, setShowResort] = useState(false);
  const [resortLabel, setResortLabel] = useState("Resort fee");
  const [resortRate, setResortRate] = useState(35);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [p, prof] = await Promise.all([
        axios.get(`${API}/tax-presets/`),
        axios.get(`${API}/tax-config/profiles?property_id=${propertyId}`),
      ]);
      setPresets(p.data.presets || []);
      setActive((prof.data || []).filter((x) => x.active));
    } catch { toast.error("Failed to load"); }
    setLoading(false);
  }, [propertyId]);

  useEffect(() => { if (propertyId) load(); }, [propertyId, load]);

  const apply = async (code, replace = false) => {
    if (!propertyId) return;
    setApplying(code);
    try {
      await axios.post(`${API}/tax-presets/apply`, { property_id: propertyId, preset_code: code, replace_existing: replace });
      toast.success(`${code} applied`);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Apply failed"); }
    setApplying("");
  };

  const addResortFee = async () => {
    if (!propertyId || resortRate <= 0) return toast.error("Rate > 0 required");
    try {
      await axios.post(`${API}/tax-presets/resort-fee/quick-add`, {
        property_id: propertyId, label: resortLabel, rate: resortRate,
      });
      toast.success("Resort fee added");
      setShowResort(false); load();
    } catch { toast.error("Add failed"); }
  };

  return (
    <div className="space-y-6" data-testid="tax-presets-panel">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Globe className="w-5 h-5 text-emerald-400" />
            <h2 className="text-2xl font-semibold text-stone-100">Tax Presets & Resort Fees</h2>
          </div>
          <p className="text-sm text-stone-400 mt-1">
            {hotelName ? `${hotelName} · ` : ""}One-click country tax stack — VAT, city tax, tourism levy, resort fees.
          </p>
        </div>
        <div className="flex gap-2">
          <button data-testid="tax-resort-fee-btn" onClick={() => setShowResort(true)}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/40 text-amber-200 text-sm">
            <Plus className="w-4 h-4" /> Add resort fee
          </button>
          <button data-testid="tax-refresh-btn" onClick={load}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-stone-800 hover:bg-stone-700 text-sm text-stone-100 border border-stone-700">
            <RefreshCw className="w-4 h-4" /> Refresh
          </button>
        </div>
      </div>

      {/* Active profiles */}
      <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-5">
        <div className="text-stone-100 font-semibold mb-3">Active tax profiles</div>
        {active.length === 0 ? (
          <div className="text-sm text-stone-500">No active tax profile yet — apply a preset below.</div>
        ) : (
          <div className="space-y-2">
            {active.map((p) => (
              <div key={p.id} className="border border-stone-800 rounded-lg p-3 bg-stone-800/40">
                <div className="flex items-center justify-between mb-2">
                  <div className="text-stone-100 font-medium">{p.name}</div>
                  {p.preset_code && (
                    <span className="px-2 py-0.5 text-[10px] uppercase tracking-wider bg-emerald-500/15 text-emerald-300 rounded">
                      preset {p.preset_code}
                    </span>
                  )}
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-1 text-xs text-stone-300">
                  {(p.rules || []).map((r, i) => (
                    <div key={i} className="flex justify-between border-b border-stone-700/40 py-1">
                      <span>{r.label}</span>
                      <span className="text-stone-500">{r.basis}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Preset gallery */}
      <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-5">
        <div className="text-stone-100 font-semibold mb-3">Country presets</div>
        {loading ? (
          <div className="flex items-center justify-center py-8 text-stone-500"><Loader2 className="w-6 h-6 animate-spin" /></div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {presets.map((p) => (
              <div key={p.code} data-testid="tax-preset-card"
                className="rounded-lg border border-stone-800 bg-stone-800/40 p-3">
                <div className="flex items-center justify-between mb-2">
                  <div>
                    <div className="text-stone-100 font-medium">{p.name}</div>
                    <div className="text-[10px] text-stone-500">{p.code} · {p.currency}</div>
                  </div>
                  <button data-testid={`apply-preset-${p.code}`}
                    onClick={() => apply(p.code, active.length > 0)} disabled={applying === p.code}
                    className="flex items-center gap-1 px-2 py-1 rounded text-xs bg-emerald-500/20 border border-emerald-500/40 text-emerald-200">
                    {applying === p.code ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
                    {active.length > 0 ? "Replace" : "Apply"}
                  </button>
                </div>
                <ul className="text-xs text-stone-400 space-y-0.5">
                  {p.preview.map((line, i) => (
                    <li key={i} className="flex items-start gap-1">
                      <span className="text-stone-600">•</span><span>{line}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </div>

      {showResort && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={() => setShowResort(false)}>
          <div className="bg-stone-900 border border-stone-800 rounded-xl max-w-md w-full p-5" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <div className="text-stone-100 font-semibold">Quick-add resort/destination fee</div>
              <button onClick={() => setShowResort(false)} className="p-1 rounded hover:bg-stone-800 text-stone-500">
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="space-y-3 text-sm">
              <input value={resortLabel} onChange={(e) => setResortLabel(e.target.value)}
                placeholder="Label" className="w-full px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100" />
              <input type="number" value={resortRate} onChange={(e) => setResortRate(parseFloat(e.target.value) || 0)}
                placeholder="Rate per night" className="w-full px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100" />
              <div className="text-xs text-stone-500">Posts as a per-night charge to room folio. Appended to the active tax profile, or creates one if none exists.</div>
            </div>
            <div className="flex justify-end gap-2 mt-4">
              <button onClick={() => setShowResort(false)} className="px-3 py-1.5 rounded bg-stone-800 text-stone-300 text-sm">Cancel</button>
              <button data-testid="tax-resort-save" onClick={addResortFee}
                className="flex items-center gap-2 px-3 py-1.5 rounded bg-amber-500/20 border border-amber-500/40 text-amber-200 text-sm">
                <CheckCircle2 className="w-4 h-4" /> Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
