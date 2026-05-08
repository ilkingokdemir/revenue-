/**
 * A/B Test Engine Panel
 * Create experiments, view results with conversion rates and statistical lead.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, FlaskConical, Plus, RefreshCw, Trash2, ToggleLeft, ToggleRight, Trophy } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function ABTestPanel({ propertyId, hotelName = "" }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [adding, setAdding] = useState(false);
  const [active, setActive] = useState(null);
  const [results, setResults] = useState(null);

  const empty = { key: "", name: "", description: "", goal_event: "booking_completed", variants: [{ name: "control", weight: 50, payload: {} }, { name: "variant_a", weight: 50, payload: {} }] };
  const [form, setForm] = useState(empty);

  const refresh = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/ab/experiments?property_id=${propertyId}`);
      setItems(data.items || []);
    } catch { toast.error("Load failed"); }
    setLoading(false);
  }, [propertyId]);

  useEffect(() => { refresh(); }, [refresh]);

  const create = async () => {
    if (!form.key || form.variants.length < 2) return toast.error("Key + 2 variants required");
    try {
      await axios.post(`${API}/ab/experiments`, { property_id: propertyId, ...form });
      toast.success("Experiment created");
      setAdding(false);
      setForm(empty);
      refresh();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  const toggle = async (e) => {
    try {
      await axios.post(`${API}/ab/experiments/${e.id}/toggle`, { active: !e.active });
      toast.success(`Experiment ${!e.active ? "enabled" : "paused"}`);
      refresh();
    } catch { toast.error("Failed"); }
  };

  const remove = async (e) => {
    if (!window.confirm(`Delete experiment "${e.name}"? All results will be lost.`)) return;
    try {
      await axios.delete(`${API}/ab/experiments/${e.id}`);
      toast.success("Deleted");
      refresh();
    } catch { toast.error("Failed"); }
  };

  const view = async (e) => {
    setActive(e);
    try {
      const { data } = await axios.get(`${API}/ab/experiments/${e.id}/results`);
      setResults(data);
    } catch { toast.error("Results failed"); }
  };

  const updateVariant = (idx, field, val) => {
    const next = [...form.variants];
    next[idx] = { ...next[idx], [field]: field === "weight" ? parseInt(val, 10) || 1 : val };
    setForm({ ...form, variants: next });
  };

  const addVariant = () => setForm({ ...form, variants: [...form.variants, { name: `variant_${form.variants.length}`, weight: 50, payload: {} }] });
  const rmVariant = (i) => setForm({ ...form, variants: form.variants.filter((_, j) => j !== i) });

  return (
    <div className="space-y-6" data-testid="ab-test-panel">
      <div>
        <h2 className="text-2xl font-semibold text-stone-100">A/B Test Engine</h2>
        <p className="text-sm text-stone-400 mt-1">{hotelName ? `${hotelName} · ` : ""}Test booking widget variants — CTA copy, hero image, price format. Hash-stable assignment per session.</p>
      </div>

      <div className="flex flex-wrap gap-2">
        <button onClick={refresh} className="text-sm px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-300 flex items-center gap-2">
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />} Refresh
        </button>
        <button data-testid="ab-add-btn" onClick={() => setAdding(true)} className="ml-auto text-sm px-3 py-2 rounded bg-cyan-500/20 border border-cyan-500/40 text-cyan-200 flex items-center gap-2">
          <Plus className="w-4 h-4" /> New experiment
        </button>
      </div>

      {adding && (
        <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4 space-y-2">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <input data-testid="ab-form-key" placeholder="Key (e.g. widget_hero)" value={form.key} onChange={(e) => setForm({ ...form, key: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm" />
            <input placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm" />
          </div>
          <textarea rows={2} placeholder="Description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="w-full px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-xs" />
          <div className="space-y-2">
            <div className="text-xs uppercase tracking-wider text-stone-400">Variants</div>
            {form.variants.map((v, i) => (
              <div key={i} className="flex gap-2 items-center">
                <input placeholder="Variant name" value={v.name} onChange={(e) => updateVariant(i, "name", e.target.value)} className="flex-1 px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-xs" />
                <input type="number" min={1} value={v.weight} onChange={(e) => updateVariant(i, "weight", e.target.value)} className="w-20 px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-xs" />
                <button onClick={() => rmVariant(i)} disabled={form.variants.length <= 2} className="text-xs px-2 py-1 rounded bg-stone-800 border border-stone-700 text-rose-300 disabled:opacity-30">Remove</button>
              </div>
            ))}
            <button onClick={addVariant} className="text-xs px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-300">+ Add variant</button>
          </div>
          <div className="flex gap-2 justify-end">
            <button onClick={() => setAdding(false)} className="text-xs px-3 py-1 rounded bg-stone-800 border border-stone-700 text-stone-300">Cancel</button>
            <button data-testid="ab-create-btn" onClick={create} className="text-xs px-3 py-1 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-200">Create</button>
          </div>
        </div>
      )}

      <div className="grid lg:grid-cols-2 gap-4">
        <div className="rounded-xl border border-stone-800 bg-stone-900/60">
          <div className="px-4 py-2 border-b border-stone-800 text-xs uppercase tracking-wider text-stone-400 flex items-center gap-2">
            <FlaskConical className="w-3 h-3" /> Experiments
          </div>
          <table className="min-w-full text-sm">
            <thead className="text-left text-[10px] uppercase tracking-wider text-stone-500 border-b border-stone-800">
              <tr><th className="px-3 py-2">Key / Name</th><th className="px-3 py-2">Variants</th><th className="px-3 py-2">Status</th><th className="px-3 py-2"></th></tr>
            </thead>
            <tbody>
              {items.map((e) => (
                <tr key={e.id} onClick={() => view(e)} className={`border-t border-stone-800/60 cursor-pointer hover:bg-stone-800/40 ${active?.id === e.id ? "bg-stone-800/60" : ""}`} data-testid="ab-row">
                  <td className="px-3 py-2"><div className="text-stone-100 font-mono text-xs">{e.key}</div><div className="text-[10px] text-stone-400">{e.name}</div></td>
                  <td className="px-3 py-2 text-xs text-stone-400">{e.variants.map((v) => v.name).join(" · ")}</td>
                  <td className="px-3 py-2"><span className={`text-[10px] px-2 py-0.5 rounded border ${e.active ? "bg-emerald-500/20 border-emerald-500/40 text-emerald-200" : "bg-stone-800 border-stone-700 text-stone-400"}`}>{e.active ? "running" : "paused"}</span></td>
                  <td className="px-3 py-2 text-right">
                    <div className="flex gap-1 justify-end" onClick={(ev) => ev.stopPropagation()}>
                      <button onClick={() => toggle(e)} className="text-xs px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-300 flex items-center gap-1">
                        {e.active ? <ToggleRight className="w-3 h-3 text-emerald-300" /> : <ToggleLeft className="w-3 h-3" />}
                      </button>
                      <button onClick={() => remove(e)} className="text-xs px-2 py-1 rounded bg-rose-500/20 border border-rose-500/40 text-rose-200"><Trash2 className="w-3 h-3" /></button>
                    </div>
                  </td>
                </tr>
              ))}
              {items.length === 0 && <tr><td colSpan={4} className="px-3 py-6 text-center text-stone-500">No experiments. Create one to start testing.</td></tr>}
            </tbody>
          </table>
        </div>

        <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4">
          {!active ? (
            <div className="text-center text-stone-500 py-12"><FlaskConical className="w-8 h-8 mx-auto mb-2 opacity-60" />Select an experiment to view results.</div>
          ) : results ? (
            <div className="space-y-3">
              <div className="text-stone-100 font-medium">{active.name}</div>
              <div className="text-xs text-stone-400">Goal: <span className="text-stone-200">{active.goal_event}</span> · {results.total_events} events</div>
              {results.results.map((r) => (
                <div key={r.variant} className={`p-3 rounded-lg border ${r.leader ? "bg-emerald-500/10 border-emerald-500/40" : "bg-stone-800/60 border-stone-800"}`} data-testid="ab-result-row">
                  <div className="flex items-center justify-between">
                    <div className="font-medium text-stone-100 flex items-center gap-2">{r.variant}{r.leader && <Trophy className="w-3 h-3 text-emerald-300" />}</div>
                    <div className={`text-xl font-semibold ${r.leader ? "text-emerald-300" : "text-stone-200"}`}>{r.conversion_rate_pct}%</div>
                  </div>
                  <div className="text-[10px] text-stone-400 grid grid-cols-3 gap-2 mt-1">
                    <span>{r.impressions} impressions</span>
                    <span>{r.conversions} conversions</span>
                    <span>Wilson 95% ≥ {r.wilson_lower_pct}%</span>
                  </div>
                </div>
              ))}
            </div>
          ) : <Loader2 className="w-4 h-4 animate-spin mx-auto text-stone-500" />}
        </div>
      </div>
    </div>
  );
}
