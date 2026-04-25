/**
 * Sustainability / ESG Dashboard — competitive wedge (most PMS lack this).
 * Shows a 0-100 ESG score with letter grade, intensity vs baseline metrics
 * (kWh/RN, water L/RN, waste kg/RN, CO2 kg/RN), monthly utility log, and
 * a checklist of green initiatives that flow into the score.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Loader2, Leaf, Plus, Trash2, RefreshCw, Zap, Droplets, Trash, Cloud,
  Settings, TrendingDown, TrendingUp, Check, X,
} from "lucide-react";
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from "recharts";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const fmt = (v, d = 1) => Number(v ?? 0).toLocaleString("en-GB", { maximumFractionDigits: d, minimumFractionDigits: 0 });

const GRADE_COLOR = {
  "A+": "text-emerald-300 bg-emerald-500/15 border-emerald-500/30",
  "A":  "text-emerald-300 bg-emerald-500/15 border-emerald-500/30",
  "B":  "text-cyan-300 bg-cyan-500/15 border-cyan-500/30",
  "C":  "text-amber-300 bg-amber-500/15 border-amber-500/30",
  "D":  "text-rose-300 bg-rose-500/15 border-rose-500/30",
};

export default function SustainabilityPanel({ propertyId, hotelName = "" }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showConfig, setShowConfig] = useState(false);
  const [config, setConfig] = useState(null);
  const [reading, setReading] = useState({ month: "", kwh: "", water_litres: "", waste_kg: "", gas_kwh: "", notes: "" });
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/esg/${propertyId}/dashboard?months=12`);
      setData(data);
    } catch { toast.error("Failed to load"); }
    setLoading(false);
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setData(null); setShowConfig(false); }, [propertyId]);

  const openConfig = async () => {
    try {
      const { data } = await axios.get(`${API}/esg/${propertyId}/config`);
      setConfig(data);
      setShowConfig(true);
    } catch { toast.error("Failed to load config"); }
  };

  const saveConfig = async () => {
    setSaving(true);
    try {
      await axios.post(`${API}/esg/${propertyId}/config`, config);
      toast.success("Saved");
      load();
      setShowConfig(false);
    } catch { toast.error("Save failed"); }
    setSaving(false);
  };

  const toggleInitiative = (key) => {
    setConfig(c => ({
      ...c,
      initiatives: c.initiatives.map(i => i.key === key ? { ...i, active: !i.active } : i),
    }));
  };

  const addReading = async () => {
    if (!reading.month) return toast.error("Month required");
    setSaving(true);
    try {
      await axios.post(`${API}/esg/${propertyId}/reading`, reading);
      toast.success("Reading saved");
      setReading({ month: "", kwh: "", water_litres: "", waste_kg: "", gas_kwh: "", notes: "" });
      load();
    } catch { toast.error("Save failed"); }
    setSaving(false);
  };

  const deleteReading = async (id) => {
    try {
      await axios.delete(`${API}/esg/${propertyId}/reading/${id}`);
      load();
    } catch { toast.error("Delete failed"); }
  };

  if (loading && !data) return <div className="p-12 text-center text-stone-400"><Loader2 className="w-5 h-5 animate-spin inline mr-2" />Computing ESG score…</div>;

  const trend = data?.trend || [];
  const initiatives = data?.initiatives || [];
  const score = data?.esg_score ?? 0;
  const grade = data?.grade || "—";
  const gradeCls = GRADE_COLOR[grade] || GRADE_COLOR["C"];
  const latest = data?.latest;

  const intensityChartData = trend.map(t => ({
    m: t.month,
    kWh: t.kwh_per_rn,
    water: t.water_per_rn,
    waste: t.waste_per_rn ? t.waste_per_rn * 100 : 0,  // scale for chart visibility
    co2: t.co2_per_rn,
  }));

  return (
    <div className="p-5 space-y-5" data-testid="sustainability-panel">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-stone-100 flex items-center gap-2">
            <Leaf className="w-5 h-5 text-emerald-400" />Sustainability & ESG
            {hotelName && <><span className="text-stone-500 mx-1">·</span><span className="text-violet-400">{hotelName}</span></>}
          </h2>
          <p className="text-xs text-stone-400">Per-room-night intensity · vs property baselines · green initiatives</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={openConfig} data-testid="esg-config-btn"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-stone-800 hover:bg-stone-700 text-white text-xs font-bold">
            <Settings className="w-3.5 h-3.5" />Configure
          </button>
          <button onClick={load} disabled={loading} data-testid="esg-refresh"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-stone-800 hover:bg-stone-700 text-white text-xs font-bold">
            {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}Refresh
          </button>
        </div>
      </div>

      {/* Score header */}
      <div className="bg-gradient-to-br from-emerald-900/40 via-teal-900/30 to-stone-900/40 border border-emerald-500/30 rounded-2xl p-5" data-testid="esg-header">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-center">
          <div className="text-center md:text-left">
            <div className="text-[10px] uppercase tracking-widest text-emerald-300 font-bold mb-1">ESG Score</div>
            <div className="flex items-baseline gap-2 justify-center md:justify-start">
              <span className="text-6xl font-black text-stone-100 tabular-nums">{score}</span>
              <span className="text-2xl text-stone-400">/100</span>
            </div>
          </div>
          <div className="text-center">
            <div className={`inline-block text-5xl font-black px-4 py-2 rounded-2xl border ${gradeCls}`} data-testid="esg-grade">{grade}</div>
          </div>
          <div className="space-y-2 col-span-2">
            <Bar label="Intensity vs baseline" value={data?.intensity_score} max={100} color="bg-cyan-500" />
            <Bar label={`Initiatives (${data?.active_initiatives_count || 0}/${data?.total_initiatives_count || 10})`} value={data?.initiatives_score} max={100} color="bg-emerald-500" />
          </div>
        </div>
      </div>

      {/* Latest month tiles */}
      {latest && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="esg-latest">
          <Tile icon={Zap}     label="Electricity"  value={`${fmt(latest.kwh_per_rn)} kWh/RN`}      delta={latest.kwh_vs_baseline_pct}   inverted />
          <Tile icon={Droplets} label="Water"        value={`${fmt(latest.water_per_rn)} L/RN`}      delta={latest.water_vs_baseline_pct} inverted />
          <Tile icon={Trash}    label="Waste"        value={`${fmt(latest.waste_per_rn, 2)} kg/RN`}  delta={latest.waste_vs_baseline_pct} inverted />
          <Tile icon={Cloud}    label="CO₂ emitted"  value={`${fmt(latest.co2_per_rn)} kg/RN`}        sub={`${fmt(latest.co2_total_kg, 0)} kg total`} />
        </div>
      )}

      {/* Trend chart */}
      {trend.length > 0 && (
        <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-4" data-testid="esg-trend">
          <h3 className="text-sm font-bold text-stone-100 mb-2">Per-room-night intensity trend</h3>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={intensityChartData}>
              <CartesianGrid stroke="#27272a" strokeDasharray="3 3" />
              <XAxis dataKey="m" stroke="#71717a" style={{ fontSize: 11 }} />
              <YAxis stroke="#71717a" style={{ fontSize: 11 }} />
              <Tooltip contentStyle={{ background: "#0c0a09", border: "1px solid #292524", borderRadius: 8, fontSize: 12 }} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Line type="monotone" dataKey="kWh"   stroke="#06b6d4" strokeWidth={2} dot={{ r: 3 }} />
              <Line type="monotone" dataKey="water" stroke="#3b82f6" strokeWidth={2} dot={{ r: 3 }} />
              <Line type="monotone" dataKey="co2"   stroke="#a855f7" strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Initiatives list */}
      <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-4" data-testid="esg-initiatives">
        <h3 className="text-sm font-bold text-stone-100 mb-3 flex items-center gap-2">
          <Leaf className="w-4 h-4 text-emerald-400" />Green initiatives
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          {initiatives.map(i => (
            <div key={i.key} className={`flex items-center gap-2 p-2 rounded-lg border ${i.active ? "bg-emerald-500/10 border-emerald-500/30" : "bg-stone-800/40 border-stone-700"}`} data-testid={`esg-init-${i.key}`}>
              <div className={`w-5 h-5 rounded flex items-center justify-center flex-shrink-0 ${i.active ? "bg-emerald-500 text-white" : "bg-stone-700 text-stone-500"}`}>
                {i.active ? <Check className="w-3 h-3" /> : <X className="w-3 h-3" />}
              </div>
              <span className={`text-xs flex-1 ${i.active ? "text-stone-100" : "text-stone-400"}`}>{i.label}</span>
              <span className="text-[9px] tabular-nums text-stone-500">+{i.weight}</span>
            </div>
          ))}
        </div>
        <p className="text-[10px] text-stone-500 mt-3">Configure initiatives in <strong>Configure</strong> to activate.</p>
      </div>

      {/* Add reading + log */}
      <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-4" data-testid="esg-readings">
        <h3 className="text-sm font-bold text-stone-100 mb-3">Monthly utility readings</h3>
        <div className="grid grid-cols-2 md:grid-cols-6 gap-2 mb-3">
          <input type="month" value={reading.month} onChange={e => setReading({ ...reading, month: e.target.value })}
            className="bg-stone-800 border border-stone-700 text-stone-100 text-xs rounded-lg px-2 py-1.5"
            data-testid="esg-reading-month" />
          <input type="number" value={reading.kwh} onChange={e => setReading({ ...reading, kwh: e.target.value })}
            placeholder="Electricity kWh"
            className="bg-stone-800 border border-stone-700 text-stone-100 text-xs rounded-lg px-2 py-1.5 tabular-nums"
            data-testid="esg-reading-kwh" />
          <input type="number" value={reading.water_litres} onChange={e => setReading({ ...reading, water_litres: e.target.value })}
            placeholder="Water L"
            className="bg-stone-800 border border-stone-700 text-stone-100 text-xs rounded-lg px-2 py-1.5 tabular-nums"
            data-testid="esg-reading-water" />
          <input type="number" value={reading.waste_kg} onChange={e => setReading({ ...reading, waste_kg: e.target.value })}
            placeholder="Waste kg"
            className="bg-stone-800 border border-stone-700 text-stone-100 text-xs rounded-lg px-2 py-1.5 tabular-nums"
            data-testid="esg-reading-waste" />
          <input type="number" value={reading.gas_kwh} onChange={e => setReading({ ...reading, gas_kwh: e.target.value })}
            placeholder="Gas kWh"
            className="bg-stone-800 border border-stone-700 text-stone-100 text-xs rounded-lg px-2 py-1.5 tabular-nums" />
          <button onClick={addReading} disabled={saving || !reading.month}
            data-testid="esg-reading-save"
            className="flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold disabled:opacity-50">
            {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}Add
          </button>
        </div>
        {trend.length > 0 ? (
          <table className="w-full text-xs">
            <thead><tr className="text-stone-400 border-b border-stone-800">
              <th className="text-left py-1.5 px-2">Month</th>
              <th className="text-right py-1.5 px-2">RN</th>
              <th className="text-right py-1.5 px-2">kWh/RN</th>
              <th className="text-right py-1.5 px-2">Water L/RN</th>
              <th className="text-right py-1.5 px-2">Waste kg/RN</th>
              <th className="text-right py-1.5 px-2">CO₂ kg/RN</th>
              <th className="w-8"></th>
            </tr></thead>
            <tbody>
              {trend.slice().reverse().map(t => (
                <tr key={t.id} className="border-b border-stone-800/50">
                  <td className="py-1.5 px-2 font-mono text-stone-200">{t.month}</td>
                  <td className="py-1.5 px-2 text-right tabular-nums text-stone-200">{t.room_nights}</td>
                  <td className="py-1.5 px-2 text-right tabular-nums text-cyan-300">{fmt(t.kwh_per_rn)}</td>
                  <td className="py-1.5 px-2 text-right tabular-nums text-blue-300">{fmt(t.water_per_rn)}</td>
                  <td className="py-1.5 px-2 text-right tabular-nums text-amber-300">{fmt(t.waste_per_rn, 2)}</td>
                  <td className="py-1.5 px-2 text-right tabular-nums text-violet-300">{fmt(t.co2_per_rn)}</td>
                  <td className="py-1.5 px-2 text-right">
                    <button onClick={() => deleteReading(t.id)} className="text-stone-500 hover:text-rose-400">
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-xs text-stone-500 text-center py-4">No readings yet. Add your first month above.</p>
        )}
      </div>

      {/* Config modal */}
      {showConfig && config && (
        <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4" onClick={() => setShowConfig(false)}>
          <div onClick={e => e.stopPropagation()} className="bg-stone-900 border border-stone-700 rounded-2xl p-5 w-full max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="esg-config-modal">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-bold text-stone-100">ESG Configuration</h3>
              <button onClick={() => setShowConfig(false)} className="text-stone-400 hover:text-white"><X className="w-4 h-4" /></button>
            </div>
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <ConfigInput label="Baseline kWh / room-night"   value={config.kwh_baseline_per_rn}   onChange={v => setConfig({ ...config, kwh_baseline_per_rn:   v })} />
                <ConfigInput label="Baseline water L / room-night" value={config.water_baseline_per_rn} onChange={v => setConfig({ ...config, water_baseline_per_rn: v })} />
                <ConfigInput label="Baseline waste kg / room-night" value={config.waste_baseline_per_rn} onChange={v => setConfig({ ...config, waste_baseline_per_rn: v })} />
                <ConfigInput label="CO₂ factor (kg/kWh)"          value={config.co2_factor_grid}      onChange={v => setConfig({ ...config, co2_factor_grid:       v })} step="0.001" />
              </div>
              <div className="border-t border-stone-700 pt-3">
                <div className="text-xs font-bold text-stone-200 mb-2">Active green initiatives</div>
                <div className="grid grid-cols-1 gap-1.5 max-h-72 overflow-y-auto">
                  {config.initiatives.map(i => (
                    <label key={i.key} className="flex items-center gap-2 p-2 rounded-lg bg-stone-800/40 hover:bg-stone-800 cursor-pointer">
                      <input type="checkbox" checked={!!i.active} onChange={() => toggleInitiative(i.key)} className="accent-emerald-500" data-testid={`esg-cfg-init-${i.key}`} />
                      <span className="text-xs text-stone-200 flex-1">{i.label}</span>
                      <span className="text-[10px] tabular-nums text-stone-500">+{i.weight}</span>
                    </label>
                  ))}
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button onClick={() => setShowConfig(false)} className="px-3 py-1.5 rounded-lg bg-stone-700 hover:bg-stone-600 text-stone-200 text-xs font-bold">Cancel</button>
                <button onClick={saveConfig} disabled={saving} data-testid="esg-cfg-save"
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold">
                  {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}Save
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Bar({ label, value, max, color }) {
  const v = value ?? 0;
  const pct = Math.min(100, Math.max(0, (v / max) * 100));
  return (
    <div>
      <div className="flex justify-between text-[10px] uppercase tracking-widest text-stone-400 font-bold mb-1">
        <span>{label}</span><span className="tabular-nums">{value == null ? "—" : value}</span>
      </div>
      <div className="h-2 bg-stone-700 rounded-full overflow-hidden">
        <div className={`h-full ${color} transition-all`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function Tile({ icon: Icon, label, value, delta, sub, inverted }) {
  // For consumption metrics, NEGATIVE delta is GOOD (less consumption).
  let dColor = "text-stone-400";
  let DIcon = TrendingUp;
  if (delta != null) {
    const isGood = inverted ? delta <= 0 : delta >= 0;
    dColor = isGood ? "text-emerald-300" : "text-rose-300";
    DIcon = delta >= 0 ? TrendingUp : TrendingDown;
  }
  return (
    <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-3">
      <div className="text-[10px] uppercase tracking-widest text-stone-500 font-bold mb-1 flex items-center gap-1">
        <Icon className="w-3 h-3" />{label}
      </div>
      <div className="text-lg font-black text-stone-100 tabular-nums">{value}</div>
      {sub && <div className="text-[10px] text-stone-500 mt-0.5">{sub}</div>}
      {delta != null && (
        <div className={`text-[10px] font-bold tabular-nums mt-1 flex items-center gap-0.5 ${dColor}`}>
          <DIcon className="w-3 h-3" />{delta > 0 ? "+" : ""}{delta}% vs baseline
        </div>
      )}
    </div>
  );
}

function ConfigInput({ label, value, onChange, step = "0.1" }) {
  return (
    <div>
      <label className="block text-[10px] uppercase tracking-widest text-stone-500 font-bold mb-1">{label}</label>
      <input type="number" step={step} value={value} onChange={e => onChange(parseFloat(e.target.value) || 0)}
        className="w-full bg-stone-800 border border-stone-700 text-stone-100 text-sm rounded-lg px-3 py-2 tabular-nums" />
    </div>
  );
}
