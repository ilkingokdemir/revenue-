import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Save, RotateCcw, Settings2, CalendarDays, BarChart3, Target, Clock, Shield, Bed } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;

const SUB_TABS = [
  { id: "rooms", label: "Rooms Setup", icon: Bed },
  { id: "dow", label: "Day-of-Week", icon: CalendarDays },
  { id: "monthly", label: "Monthly", icon: BarChart3 },
  { id: "occupancy", label: "Occupancy", icon: Target },
  { id: "min-stay", label: "Min Stay", icon: Settings2 },
  { id: "lead-time", label: "Lead Time", icon: Clock },
  { id: "surge", label: "Surge Protection", icon: Shield },
];

export const RevenuePricingStrategy = ({ propertyId }) => {
  const [data, setData] = useState({ rooms_setup: [], strategy: {}, room_types: [] });
  const [subTab, setSubTab] = useState("rooms");
  const [saving, setSaving] = useState(false);
  const [strategy, setStrategy] = useState({});

  const load = useCallback(async () => {
    try {
      const { data: d } = await axios.get(`${API}/revenue/pricing-strategy-full/${propertyId}`);
      setData(d);
      setStrategy(d.strategy || {});
    } catch { toast.error("Failed to load strategy"); }
  }, [propertyId]);
  useEffect(() => { load(); }, [load]);

  const saveStrategy = async (updates) => {
    setSaving(true);
    try {
      const merged = { ...strategy, ...updates };
      await axios.put(`${API}/revenue/pricing-strategy/${propertyId}`, merged);
      setStrategy(merged);
      toast.success("Strategy saved");
    } catch { toast.error("Save failed"); }
    setSaving(false);
  };

  return (
    <div data-testid="rev-pricing-strategy">
      <div className="flex items-center gap-1 mb-6 overflow-x-auto pb-1">
        {SUB_TABS.map(t => (
          <button key={t.id} onClick={() => setSubTab(t.id)}
            className={`flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-lg whitespace-nowrap transition-all ${
              subTab === t.id ? "bg-violet-600 text-white shadow-lg shadow-violet-200" : "text-stone-500 hover:bg-stone-100"
            }`} data-testid={`rev-strat-${t.id}`}>
            <t.icon className="w-3.5 h-3.5" />{t.label}
          </button>
        ))}
      </div>

      {subTab === "rooms" && <RoomsSetupTab rooms={data.rooms_setup} />}
      {subTab === "dow" && <DowTab strategy={strategy} onSave={saveStrategy} saving={saving} />}
      {subTab === "monthly" && <MonthlyTab strategy={strategy} onSave={saveStrategy} saving={saving} />}
      {subTab === "occupancy" && <OccupancyTab strategy={strategy} onSave={saveStrategy} saving={saving} />}
      {subTab === "min-stay" && <MinStayTab strategy={strategy} onSave={saveStrategy} saving={saving} roomTypes={data.room_types} />}
      {subTab === "lead-time" && <LeadTimeTab strategy={strategy} onSave={saveStrategy} saving={saving} />}
      {subTab === "surge" && <SurgeTab strategy={strategy} onSave={saveStrategy} saving={saving} />}
    </div>
  );
};

/* ── ROOMS SETUP ── */
const RoomsSetupTab = ({ rooms }) => (
  <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden" data-testid="rev-rooms-setup">
    <div className="bg-stone-50 px-4 py-3 border-b flex justify-between items-center">
      <h3 className="font-bold text-stone-800 text-sm">Rooms Setup</h3>
      <span className="text-xs text-stone-400">Sum: {rooms.reduce((s, r) => s + (r.number_of_rooms || 0), 0)} rooms</span>
    </div>
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead><tr className="border-b bg-stone-50/50">
          <th className="px-4 py-2.5 text-left text-xs font-semibold text-stone-500">Name</th>
          <th className="px-4 py-2.5 text-left text-xs font-semibold text-stone-500">Room in PMS</th>
          <th className="px-4 py-2.5 text-left text-xs font-semibold text-stone-500">Rate in PMS</th>
          <th className="px-4 py-2.5 text-center text-xs font-semibold text-stone-500">Rooms</th>
          <th className="px-4 py-2.5 text-center text-xs font-semibold text-stone-500">Ref/Derived</th>
          <th className="px-4 py-2.5 text-right text-xs font-semibold text-stone-500">Base Price</th>
          <th className="px-4 py-2.5 text-right text-xs font-semibold text-stone-500">Derivation</th>
          <th className="px-4 py-2.5 text-right text-xs font-semibold text-stone-500">Min Price</th>
          <th className="px-4 py-2.5 text-right text-xs font-semibold text-stone-500">Max Price</th>
        </tr></thead>
        <tbody>{rooms.map((r, i) => (
          <tr key={r.id || i} className={`border-b border-stone-100 ${i === 0 ? "bg-violet-50/30" : ""}`} data-testid={`rev-room-row-${r.id}`}>
            <td className="px-4 py-3 font-semibold text-stone-800">{r.name}</td>
            <td className="px-4 py-3 text-stone-600 capitalize">{r.room_in_pms || r.name}</td>
            <td className="px-4 py-3 text-stone-500">Base Rate</td>
            <td className="px-4 py-3 text-center text-stone-600">{r.number_of_rooms}</td>
            <td className="px-4 py-3 text-center">
              <Badge className={`text-[10px] ${r.reference_derived === "Reference" ? "bg-violet-100 text-violet-700" : "bg-stone-100 text-stone-600"}`}>
                {r.reference_derived}
              </Badge>
            </td>
            <td className="px-4 py-3 text-right font-semibold text-stone-800">{cur(r.base_price)}</td>
            <td className="px-4 py-3 text-right text-stone-500">{r.derivation !== null ? `+${cur(r.derivation)}` : "—"}</td>
            <td className="px-4 py-3 text-right text-stone-500">{cur(r.min_price)}</td>
            <td className="px-4 py-3 text-right text-stone-500">{cur(r.max_price)}</td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  </div>
);

/* ── DAY-OF-WEEK ── */
const DowTab = ({ strategy, onSave, saving }) => {
  const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const [vals, setVals] = useState({});
  useEffect(() => { setVals(strategy?.dow_adjustments || {}); }, [strategy]);

  const set = (d, v) => setVals(p => ({ ...p, [d.toLowerCase()]: Number(v) || 0 }));

  return (
    <div className="bg-white border border-stone-200 rounded-2xl p-6" data-testid="rev-dow-adjustments">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-bold text-stone-800">Day-of-Week Adjustments</h3>
          <p className="text-sm text-stone-500 mt-1">Adjust price recommendations by day of the week to match demand patterns.</p>
        </div>
        <button onClick={() => onSave({ dow_adjustments: vals })} disabled={saving}
          className="flex items-center gap-2 bg-violet-600 hover:bg-violet-700 text-white px-4 py-2 rounded-xl text-sm font-medium disabled:opacity-50" data-testid="rev-dow-save">
          <Save className="w-4 h-4" />{saving ? "Saving..." : "Save"}
        </button>
      </div>
      {/* Chart placeholder */}
      <div className="bg-stone-50 rounded-xl p-4 mb-6">
        <div className="flex items-end gap-3 h-28">
          {days.map(d => {
            const v = vals[d.toLowerCase()] || 0;
            const h = Math.max(8, Math.abs(v) * 2 + 20);
            return (
              <div key={d} className="flex-1 flex flex-col items-center gap-1">
                <span className={`text-[10px] font-bold ${v > 0 ? "text-emerald-600" : v < 0 ? "text-red-500" : "text-stone-400"}`}>
                  {v > 0 ? "+" : ""}{v}%
                </span>
                <div className={`w-full rounded-t-md transition-all ${v > 0 ? "bg-emerald-400" : v < 0 ? "bg-red-400" : "bg-stone-200"}`}
                  style={{ height: `${h}px` }} />
                <span className="text-xs font-medium text-stone-500">{d}</span>
              </div>
            );
          })}
        </div>
      </div>
      {/* Input row */}
      <div className="grid grid-cols-7 gap-3">
        {days.map(d => (
          <div key={d} className="text-center">
            <label className="text-xs font-bold text-stone-600 block mb-2">{d}</label>
            <div className="relative">
              <Input type="number" value={vals[d.toLowerCase()] || 0}
                onChange={e => set(d, e.target.value)}
                className="text-center text-sm font-semibold h-10 pr-6" data-testid={`rev-dow-${d.toLowerCase()}`} />
              <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-stone-400">%</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

/* ── MONTHLY ── */
const MonthlyTab = ({ strategy, onSave, saving }) => {
  const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  const [vals, setVals] = useState({});
  useEffect(() => { setVals(strategy?.monthly_adjustments || {}); }, [strategy]);

  const set = (m, v) => setVals(p => ({ ...p, [m.toLowerCase()]: Number(v) || 0 }));

  return (
    <div className="bg-white border border-stone-200 rounded-2xl p-6" data-testid="rev-monthly-adjustments">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-bold text-stone-800">Monthly Adjustments</h3>
          <p className="text-sm text-stone-500 mt-1">Adjust price recommendations by month to account for seasonal demand.</p>
        </div>
        <button onClick={() => onSave({ monthly_adjustments: vals })} disabled={saving}
          className="flex items-center gap-2 bg-violet-600 hover:bg-violet-700 text-white px-4 py-2 rounded-xl text-sm font-medium disabled:opacity-50" data-testid="rev-monthly-save">
          <Save className="w-4 h-4" />{saving ? "Saving..." : "Save"}
        </button>
      </div>
      {/* Chart */}
      <div className="bg-stone-50 rounded-xl p-4 mb-6">
        <div className="flex items-end gap-2 h-28">
          {months.map(m => {
            const v = vals[m.toLowerCase()] || 0;
            const h = Math.max(8, Math.abs(v) * 1.5 + 20);
            return (
              <div key={m} className="flex-1 flex flex-col items-center gap-1">
                <span className={`text-[9px] font-bold ${v > 0 ? "text-emerald-600" : v < 0 ? "text-red-500" : "text-stone-400"}`}>
                  {v > 0 ? "+" : ""}{v}%
                </span>
                <div className={`w-full rounded-t-md transition-all ${v > 0 ? "bg-emerald-400" : v < 0 ? "bg-red-400" : "bg-stone-200"}`}
                  style={{ height: `${h}px` }} />
                <span className="text-[9px] font-medium text-stone-500">{m}</span>
              </div>
            );
          })}
        </div>
      </div>
      <div className="grid grid-cols-4 md:grid-cols-6 gap-3">
        {months.map(m => (
          <div key={m} className="text-center">
            <label className="text-xs font-bold text-stone-600 block mb-2">{m}</label>
            <div className="relative">
              <Input type="number" value={vals[m.toLowerCase()] || 0}
                onChange={e => set(m, e.target.value)}
                className="text-center text-sm font-semibold h-10 pr-6" data-testid={`rev-monthly-${m.toLowerCase()}`} />
              <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-stone-400">%</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

/* ── OCCUPANCY STRATEGY ── */
const OccupancyTab = ({ strategy, onSave, saving }) => {
  const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  const [targets, setTargets] = useState({});
  const [agg, setAgg] = useState(1.0);
  useEffect(() => {
    setTargets(strategy?.target_occupancy || {});
    setAgg(strategy?.aggressiveness || 1.0);
  }, [strategy]);

  return (
    <div className="space-y-6" data-testid="rev-occupancy-strategy">
      {/* Target Occupancy */}
      <div className="bg-white border border-stone-200 rounded-2xl p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="font-bold text-stone-800">Target Occupancy</h3>
            <p className="text-sm text-stone-500 mt-1">Set expected occupancy so the system adjusts prices to reach targets. Low targets mean less price reduction in quiet times. Going above 90% can adversely affect revenue.</p>
          </div>
          <button onClick={() => onSave({ target_occupancy: targets, aggressiveness: agg })} disabled={saving}
            className="flex items-center gap-2 bg-violet-600 hover:bg-violet-700 text-white px-4 py-2 rounded-xl text-sm font-medium disabled:opacity-50" data-testid="rev-occ-save">
            <Save className="w-4 h-4" />{saving ? "Saving..." : "Save"}
          </button>
        </div>
        <div className="grid grid-cols-4 md:grid-cols-6 gap-3">
          {months.map(m => (
            <div key={m} className="text-center border border-stone-200 rounded-xl p-3">
              <label className="text-xs font-bold text-stone-500 block mb-2">{m}</label>
              <div className="relative">
                <Input type="number" min={0} max={100} value={targets[m.toLowerCase()] || 60}
                  onChange={e => setTargets(p => ({ ...p, [m.toLowerCase()]: Number(e.target.value) || 60 }))}
                  className="text-center text-sm font-semibold h-10 pr-6" data-testid={`rev-occ-${m.toLowerCase()}`} />
                <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-stone-400">%</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Aggressiveness */}
      <div className="bg-white border border-stone-200 rounded-2xl p-6">
        <h3 className="font-bold text-stone-800 mb-2">Aggressiveness</h3>
        <p className="text-sm text-stone-500 mb-4">Controls how aggressively the system adjusts prices. 1.0 = Balanced, &gt;1.0 = Aggressive, &lt;1.0 = Conservative.</p>
        <div className="flex items-center gap-4">
          <span className="text-xs text-stone-400 font-medium">Conservative</span>
          <input type="range" min="0.5" max="2.0" step="0.1" value={agg}
            onChange={e => setAgg(parseFloat(e.target.value))}
            className="flex-1 h-2 appearance-none bg-stone-200 rounded-full accent-violet-600" data-testid="rev-aggressiveness" />
          <span className="text-xs text-stone-400 font-medium">Aggressive</span>
          <Badge className="bg-violet-100 text-violet-700 text-sm font-bold min-w-[50px] text-center">{agg}x</Badge>
        </div>
      </div>

      {/* Occupancy Rules Display */}
      <div className="bg-white border border-stone-200 rounded-2xl p-6">
        <h3 className="font-bold text-stone-800 mb-4">Dynamic Pricing Rules</h3>
        <div className="space-y-3">
          {[{ range: "90-100%", adj: "+40%", color: "bg-emerald-500", desc: "High demand — maximize revenue" },
            { range: "75-89%", adj: "+20%", color: "bg-emerald-400", desc: "Strong demand — increase rates" },
            { range: "50-74%", adj: "Base", color: "bg-amber-400", desc: "Normal demand — standard pricing" },
            { range: "25-49%", adj: "-15%", color: "bg-orange-400", desc: "Low demand — attract bookings" },
            { range: "0-24%", adj: "-30%", color: "bg-red-400", desc: "Very low — aggressive pricing" },
          ].map(r => (
            <div key={r.range} className="flex items-center gap-4 p-3 border border-stone-200 rounded-xl">
              <div className={`w-3 h-3 rounded-full ${r.color} flex-shrink-0`} />
              <div className="w-20 font-semibold text-stone-800 text-sm">{r.range}</div>
              <div className={`w-16 font-bold text-sm ${r.adj.includes("+") ? "text-emerald-600" : r.adj.includes("-") ? "text-red-600" : "text-stone-500"}`}>{r.adj}</div>
              <div className="text-xs text-stone-400">{r.desc}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

/* ── MINIMUM STAY ── */
const MinStayTab = ({ strategy, onSave, saving, roomTypes }) => {
  const [settings, setSettings] = useState({ min_stay: 1, orphan_gap_enabled: false, fixed_override: false, room_types: [] });
  useEffect(() => { setSettings(strategy?.min_stay_settings || { min_stay: 1, orphan_gap_enabled: false, fixed_override: false, room_types: [] }); }, [strategy]);

  const update = (k, v) => setSettings(p => ({ ...p, [k]: v }));

  return (
    <div className="space-y-6" data-testid="rev-min-stay">
      <div className="bg-white border border-stone-200 rounded-2xl p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="font-bold text-stone-800">Orphan Gap Correction</h3>
            <p className="text-sm text-stone-500 mt-1">Automatically reduce minimum stay restrictions when the number of available nights between bookings is shorter than the restriction.</p>
          </div>
          <button onClick={() => onSave({ min_stay_settings: settings })} disabled={saving}
            className="flex items-center gap-2 bg-violet-600 hover:bg-violet-700 text-white px-4 py-2 rounded-xl text-sm font-medium disabled:opacity-50" data-testid="rev-minstay-save">
            <Save className="w-4 h-4" />{saving ? "Saving..." : "Save"}
          </button>
        </div>
        <div className="bg-blue-50 border border-blue-100 rounded-xl p-4 mb-6 text-sm text-blue-800">
          <strong>Example:</strong> If minimum stay is 4 nights but only 3 consecutive nights are available between bookings, the restriction will be reduced to 3 nights for that gap.
        </div>
        <div className="space-y-5">
          <div>
            <label className="text-sm font-semibold text-stone-700 block mb-2">Minimum stay</label>
            <p className="text-xs text-stone-400 mb-2">Define the lowest minimum stay orphan gap correction can reduce to.</p>
            <Input type="number" min={1} max={14} value={settings.min_stay}
              onChange={e => update("min_stay", Number(e.target.value) || 1)}
              className="w-32 h-10" data-testid="rev-minstay-input" placeholder="Add a number" />
          </div>
          <div className="flex items-center justify-between border border-stone-200 rounded-xl p-4">
            <div>
              <label className="text-sm font-semibold text-stone-700">Fixed restriction override</label>
              <p className="text-xs text-stone-400 mt-0.5">Enable to allow orphan gap correction to override fixed restrictions.</p>
            </div>
            <Switch checked={settings.fixed_override} onCheckedChange={v => update("fixed_override", v)} data-testid="rev-minstay-override" />
          </div>
          <div>
            <label className="text-sm font-semibold text-stone-700 block mb-2">Room types to apply</label>
            <div className="flex flex-wrap gap-2">
              {(roomTypes || []).map(rt => (
                <button key={rt.id} onClick={() => {
                  const current = settings.room_types || [];
                  update("room_types", current.includes(rt.id) ? current.filter(x => x !== rt.id) : [...current, rt.id]);
                }}
                  className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-all ${
                    (settings.room_types || []).includes(rt.id) ? "bg-violet-50 border-violet-300 text-violet-700" : "bg-white border-stone-200 text-stone-500 hover:border-stone-300"
                  }`}>{rt.name}</button>
              ))}
              {(!roomTypes || roomTypes.length === 0) && <span className="text-xs text-stone-400">No room types configured</span>}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

/* ── LEAD TIME ── */
const LeadTimeTab = ({ strategy, onSave, saving }) => {
  const windows = [
    { key: "6_months_plus", label: "6 Months +" },
    { key: "3_months_plus", label: "3 Months +" },
    { key: "1_5_3_months", label: "1.5-3 Months" },
    { key: "4_6_weeks", label: "4-6 Weeks" },
    { key: "2_4_weeks", label: "2-4 Weeks" },
    { key: "1_2_weeks", label: "1-2 Weeks" },
    { key: "4_7_days", label: "4-7 Days" },
    { key: "2_3_days", label: "2-3 Days" },
    { key: "last_day", label: "Last Day" },
  ];
  const [vals, setVals] = useState({});
  useEffect(() => { setVals(strategy?.lead_time_adjustments || {}); }, [strategy]);

  return (
    <div className="bg-white border border-stone-200 rounded-2xl p-6" data-testid="rev-lead-time">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-bold text-stone-800">Lead Time Adjustments</h3>
          <p className="text-sm text-stone-500 mt-1">Rolling adjustments based on lead time to check-in. Reduce prices additionally before guest arrival to boost bookings in specific windows.</p>
        </div>
        <button onClick={() => onSave({ lead_time_adjustments: vals })} disabled={saving}
          className="flex items-center gap-2 bg-violet-600 hover:bg-violet-700 text-white px-4 py-2 rounded-xl text-sm font-medium disabled:opacity-50" data-testid="rev-leadtime-save">
          <Save className="w-4 h-4" />{saving ? "Saving..." : "Save"}
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b">
              {windows.map(w => (
                <th key={w.key} className="px-3 py-2 text-xs font-semibold text-stone-500 text-center whitespace-nowrap">{w.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              {windows.map(w => (
                <td key={w.key} className="px-2 py-3">
                  <div className="relative">
                    <Input type="number" value={vals[w.key] || 0}
                      onChange={e => setVals(p => ({ ...p, [w.key]: Number(e.target.value) || 0 }))}
                      className="text-center text-sm font-semibold h-10 pr-6 w-20 mx-auto" data-testid={`rev-lt-${w.key}`} />
                    <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-stone-400">%</span>
                  </div>
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
};

/* ── SURGE PROTECTION ── */
const SurgeTab = ({ strategy, onSave, saving }) => {
  const [settings, setSettings] = useState({ enabled: false, booking_threshold: 100, days_to_go: 30, recipients: [], dont_send_email: false });
  useEffect(() => { setSettings(strategy?.surge_protection || { enabled: false, booking_threshold: 100, days_to_go: 30, recipients: [], dont_send_email: false }); }, [strategy]);

  const update = (k, v) => setSettings(p => ({ ...p, [k]: v }));

  return (
    <div className="space-y-6" data-testid="rev-surge-protection">
      <div className="bg-white border border-stone-200 rounded-2xl p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="font-bold text-stone-800">Surge Protection</h3>
            <p className="text-sm text-stone-500 mt-1">
              When you receive <strong>{settings.booking_threshold}</strong> bookings for a single date within 24 hours and with more than <strong>{settings.days_to_go}</strong> days to go, you'll be notified of a Surge.
            </p>
          </div>
          <button onClick={() => onSave({ surge_protection: settings })} disabled={saving}
            className="flex items-center gap-2 bg-violet-600 hover:bg-violet-700 text-white px-4 py-2 rounded-xl text-sm font-medium disabled:opacity-50" data-testid="rev-surge-save">
            <Save className="w-4 h-4" />{saving ? "Saving..." : "Save"}
          </button>
        </div>
        <div className="space-y-5">
          <div>
            <label className="text-sm font-semibold text-stone-700 block mb-2">Number of bookings to trigger surge protection</label>
            <Input type="number" min={1} value={settings.booking_threshold}
              onChange={e => update("booking_threshold", Number(e.target.value) || 100)}
              className="w-40 h-10" data-testid="rev-surge-threshold" />
          </div>
          <div>
            <label className="text-sm font-semibold text-stone-700 block mb-2">Only check after this many days to go</label>
            <Input type="number" min={1} value={settings.days_to_go}
              onChange={e => update("days_to_go", Number(e.target.value) || 30)}
              className="w-40 h-10" data-testid="rev-surge-days" />
          </div>
          <div className="flex items-center gap-3 border border-stone-200 rounded-xl p-4">
            <Switch checked={settings.dont_send_email} onCheckedChange={v => update("dont_send_email", v)} data-testid="rev-surge-noemail" />
            <label className="text-sm text-stone-600">Don't send email notifications</label>
          </div>
          <div className="flex gap-3">
            <button onClick={() => update("booking_threshold", 100) || update("days_to_go", 30)}
              className="flex items-center gap-2 border border-stone-300 text-stone-600 px-4 py-2 rounded-xl text-sm font-medium hover:bg-stone-50">
              <RotateCcw className="w-3.5 h-3.5" />Set Default
            </button>
          </div>
        </div>
      </div>

      {/* Event Logs placeholder */}
      <div className="bg-white border border-stone-200 rounded-2xl p-6">
        <h3 className="font-bold text-stone-800 mb-3">Surge Protection Event Logs</h3>
        <div className="text-center py-8">
          <Shield className="w-10 h-10 text-stone-200 mx-auto mb-2" />
          <p className="text-sm text-stone-500">No surge events detected</p>
          <p className="text-xs text-stone-400">Events will appear here when booking surges are detected.</p>
        </div>
      </div>
    </div>
  );
};
