import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { motion, AnimatePresence } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
const occColor = (o) => o >= 90 ? "bg-emerald-500 text-white" : o >= 70 ? "bg-emerald-400 text-white" : o >= 50 ? "bg-amber-400 text-white" : o >= 25 ? "bg-orange-400 text-white" : o > 0 ? "bg-red-400 text-white" : "bg-stone-100 text-stone-400";

/* ── DASHBOARD TAB ── */
const DashboardTab = ({ propertyId }) => {
  const [kpis, setKpis] = useState(null);
  const [heatmap, setHeatmap] = useState(null);
  const [yoy, setYoy] = useState([]);

  useEffect(() => {
    Promise.all([
      axios.get(`${API}/revenue/dashboard/${propertyId}`),
      axios.get(`${API}/revenue/heatmap?days=14`),
      axios.get(`${API}/revenue/yoy-tables`),
    ]).then(([k, h, y]) => { setKpis(k.data); setHeatmap(h.data); setYoy(y.data); }).catch(() => toast.error("Failed"));
  }, [propertyId]);

  const KpiCard = ({ data, color }) => (
    <div className={`bg-gradient-to-br ${color} rounded-2xl p-5 text-white shadow-lg`}>
      <div className="text-xs font-medium opacity-80 uppercase tracking-wider">{data?.label}</div>
      <div className="text-2xl font-bold mt-1">{cur(data?.revenue)}</div>
      <div className="flex items-center gap-3 mt-2 text-sm">
        <span className="opacity-80">{data?.occupancy}% OCC</span>
        <Badge className={`text-[10px] ${data?.yoy >= 0 ? "bg-white/20 text-white" : "bg-red-600/80 text-white"}`}>
          {data?.yoy >= 0 ? "+" : ""}{data?.yoy}% YOY
        </Badge>
      </div>
    </div>
  );

  return (
    <div data-testid="rev-dashboard-tab">
      {/* KPI Cards */}
      {kpis && <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <KpiCard data={kpis.last_month} color="from-blue-600 to-blue-700" />
        <KpiCard data={kpis.current_month} color="from-violet-600 to-violet-700" />
        <KpiCard data={kpis.next_month} color="from-stone-700 to-stone-800" />
      </div>}

      {/* Occupancy Heatmap */}
      {heatmap && <div className="bg-white border border-stone-200 rounded-2xl p-5 mb-8 overflow-x-auto" data-testid="rev-heatmap">
        <h3 className="font-bold text-stone-800 mb-4">Occupancy Heatmap</h3>
        <table className="w-full text-[10px]">
          <thead><tr><th className="px-2 py-1 text-left text-stone-500 font-semibold min-w-[120px] sticky left-0 bg-white z-10">Property</th>
            {heatmap.dates.map(d => <th key={d} className="px-1 py-1 text-center text-stone-400 min-w-[40px]">{new Date(d + "T00:00:00").toLocaleDateString("en", { day: "numeric", month: "short" })}</th>)}
          </tr></thead>
          <tbody>{heatmap.properties.map(p => (
            <tr key={p.property_id} data-testid={`heatmap-row-${p.property_id}`}>
              <td className="px-2 py-1.5 font-medium text-stone-700 sticky left-0 bg-white z-10 text-xs">{p.name}<div className="text-[9px] text-stone-400">{p.total_rooms} rooms</div></td>
              {p.daily.map(d => (
                <td key={d.date} className="px-0.5 py-0.5">
                  <div className={`rounded px-1 py-1 text-center font-bold ${occColor(d.occupancy)}`} title={`${d.date}: ${d.occupancy}% (${d.booked}/${d.booked + d.available})`}>
                    {d.occupancy}%
                  </div>
                </td>
              ))}
            </tr>
          ))}</tbody>
        </table>
        <div className="flex items-center gap-3 mt-3 text-[10px] text-stone-400">
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-emerald-500" />90%+</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-emerald-400" />70-89%</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-amber-400" />50-69%</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-orange-400" />25-49%</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-red-400" />1-24%</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-stone-100 border" />0%</span>
        </div>
      </div>}

      {/* YOY Property Tables */}
      {yoy.length > 0 && <div className="space-y-6">
        <h3 className="font-bold text-stone-800">Property Revenue (YOY)</h3>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {yoy.map(p => (
            <div key={p.property_id} className="bg-white border border-stone-200 rounded-2xl overflow-hidden" data-testid={`yoy-table-${p.property_id}`}>
              <div className="bg-stone-50 px-4 py-3 border-b flex items-center justify-between">
                <div><span className="font-bold text-stone-800 text-sm">{p.name}</span><span className="text-xs text-stone-400 ml-2">{p.total_rooms} rooms</span></div>
              </div>
              <table className="w-full text-xs">
                <thead><tr className="border-b"><th className="px-3 py-2 text-left text-stone-500">Month</th><th className="px-3 py-2 text-right text-stone-500">2025 REV</th><th className="px-3 py-2 text-center text-stone-500">OCC</th><th className="px-3 py-2 text-right text-stone-500">ADR</th><th className="px-3 py-2 text-right text-stone-500">2026 REV</th><th className="px-3 py-2 text-right text-stone-500">VAR</th></tr></thead>
                <tbody>{p.months.map(m => (
                  <tr key={m.month} className={`border-b border-stone-50 ${m.is_current ? "bg-blue-50/50" : ""}`}>
                    <td className="px-3 py-2 font-medium text-stone-700">{m.month}</td>
                    <td className="px-3 py-2 text-right text-stone-500">{cur(m.prev_rev)}</td>
                    <td className="px-3 py-2 text-center">{m.curr_occ}%</td>
                    <td className="px-3 py-2 text-right">{cur(m.curr_adr)}</td>
                    <td className="px-3 py-2 text-right font-semibold">{cur(m.curr_rev)}</td>
                    <td className="px-3 py-2 text-right"><span className={`font-bold ${m.variance >= 0 ? "text-emerald-600" : "text-red-600"}`}>{m.variance >= 0 ? "+" : ""}{m.variance}%</span></td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          ))}
        </div>
      </div>}
    </div>
  );
};

/* ── RATE CALENDAR TAB (RoomPriceGenie-style) ── */
const RateCalendarTab = ({ propertyId }) => {
  const [cal, setCal] = useState(null);
  const [year, setYear] = useState(new Date().getFullYear());
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const [roomType, setRoomType] = useState("");
  const [viewMode, setViewMode] = useState("prices");

  const load = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/revenue/rate-calendar/${propertyId}?year=${year}&month=${month}${roomType ? `&room_type=${roomType}` : ""}`);
      setCal(data);
    } catch { toast.error("Failed"); }
  }, [propertyId, year, month, roomType]);
  useEffect(() => { load(); }, [load]);

  const navMonth = (dir) => {
    let nm = month + dir;
    let ny = year;
    if (nm > 12) { nm = 1; ny++; }
    if (nm < 1) { nm = 12; ny--; }
    setMonth(nm); setYear(ny);
  };

  if (!cal) return <div className="text-center py-12 text-stone-400">Loading...</div>;

  // Build weeks grid
  const firstDow = new Date(year, month - 1, 1).getDay();
  const offset = firstDow === 0 ? 6 : firstDow - 1; // Monday-start
  const weeks = [];
  let week = Array(7).fill(null);
  for (const d of cal.days) {
    const idx = (offset + d.day - 1) % 7;
    const weekIdx = Math.floor((offset + d.day - 1) / 7);
    if (!weeks[weekIdx]) weeks[weekIdx] = Array(7).fill(null);
    weeks[weekIdx][idx] = d;
  }

  const perf = cal.performance || {};

  return (
    <div data-testid="rev-rate-calendar-tab">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <button onClick={() => navMonth(-1)} className="p-2 hover:bg-stone-100 rounded-lg text-stone-500" data-testid="rev-cal-prev"><svg className="w-5 h-5" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z"/></svg></button>
          <h2 className="text-lg font-bold text-stone-800">{cal.month_name} {year}</h2>
          <button onClick={() => navMonth(1)} className="p-2 hover:bg-stone-100 rounded-lg text-stone-500" data-testid="rev-cal-next"><svg className="w-5 h-5" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"/></svg></button>
        </div>
        <div className="flex items-center gap-2">
          {["prices", "occupancy", "pickup"].map(v => (
            <button key={v} onClick={() => setViewMode(v)} className={`px-3 py-1.5 text-xs font-medium rounded-lg capitalize ${viewMode === v ? "bg-violet-600 text-white" : "text-stone-500 hover:bg-stone-100"}`} data-testid={`rev-cal-view-${v}`}>{v}</button>
          ))}
        </div>
      </div>
      <div className="bg-white border border-stone-200 rounded-2xl p-5 mb-4">
        <div className="flex items-center gap-6 text-sm mb-4">
          <span><strong>{perf.occupancy}%</strong> Occupancy</span>
          <span><strong>{perf.expected_by_today}%</strong> Expected by Today</span>
          <span><strong>{perf.target}%</strong> Target Occupancy</span>
        </div>
        <div className="flex items-center gap-3 mb-4 flex-wrap">
          <div><label className="text-xs text-stone-500 mr-2">Room Type</label>
            <Select value={roomType || cal.room_type?.id || "default"} onValueChange={v => setRoomType(v)}>
              <SelectTrigger className="w-44 h-9 text-sm"><SelectValue /></SelectTrigger>
              <SelectContent>{cal.room_types.map(r => <SelectItem key={r.id} value={r.id}>{r.name}</SelectItem>)}</SelectContent>
            </Select>
          </div>
        </div>
      </div>
      {/* Calendar Grid */}
      <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden">
        <div className="grid grid-cols-7 border-b">
          {["Mo","Tu","We","Th","Fr","Sa","Su"].map(d => <div key={d} className="px-2 py-2 text-center text-xs font-bold text-stone-500 border-r last:border-0">{d}</div>)}
        </div>
        {weeks.map((w, wi) => (
          <div key={wi} className="grid grid-cols-7 border-b last:border-0">
            {w.map((d, di) => (
              <div key={di} className={`border-r last:border-0 min-h-[90px] p-2 ${d?.is_today ? "bg-violet-50 ring-2 ring-violet-300 ring-inset" : d ? "bg-white" : "bg-stone-50"}`} data-testid={d ? `rev-cal-day-${d.day}` : undefined}>
                {d && <>
                  <div className="flex items-center justify-between mb-1">
                    <span className={`text-xs font-bold ${d.is_today ? "text-violet-700" : "text-stone-800"}`}>{d.day}</span>
                    {d.is_today && <span className="text-[8px] bg-violet-600 text-white px-1.5 py-0.5 rounded-full font-bold">Today</span>}
                  </div>
                  {viewMode === "prices" && <>
                    <div className="text-sm font-bold text-violet-700">{cur(d.recommended_rate)}</div>
                    <div className="text-[10px] text-stone-400">{cur(d.pms_rate)} PMS</div>
                  </>}
                  {viewMode === "occupancy" && <>
                    <div className={`text-sm font-bold ${d.occupancy >= 70 ? "text-emerald-600" : d.occupancy >= 40 ? "text-amber-600" : "text-red-500"}`}>{d.occupancy}%</div>
                    <div className="text-[10px] text-stone-400">{d.booked}/{d.booked + d.available}</div>
                  </>}
                  {viewMode === "pickup" && <>
                    <div className="text-sm font-bold text-blue-600">{d.booked}</div>
                    <div className="text-[10px] text-stone-400">{d.available} avail</div>
                  </>}
                  {d.is_full && <Badge className="text-[8px] bg-emerald-500 text-white mt-1">Full</Badge>}
                </>}
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
};

/* ── PRICING STRATEGY TAB (RoomPriceGenie Rooms Setup) ── */
const PricingStrategyTab = ({ propertyId }) => {
  const [data, setData] = useState({ rooms_setup: [], strategy: {} });
  const [subTab, setSubTab] = useState("rooms");

  const load = useCallback(async () => {
    try { const { data: d } = await axios.get(`${API}/revenue/pricing-strategy/${propertyId}`); setData(d); } catch { toast.error("Failed"); }
  }, [propertyId]);
  useEffect(() => { load(); }, [load]);

  return (
    <div data-testid="rev-pricing-tab">
      <div className="flex items-center gap-1 mb-6 overflow-x-auto">
        {[{ id: "rooms", label: "Rooms Setup" }, { id: "dow", label: "Day-of-Week" }, { id: "monthly", label: "Monthly Adjustments" }, { id: "occupancy", label: "Occupancy Strategy" }].map(t => (
          <button key={t.id} onClick={() => setSubTab(t.id)} className={`px-4 py-2 text-sm font-medium rounded-lg whitespace-nowrap ${subTab === t.id ? "bg-violet-600 text-white" : "text-stone-500 hover:bg-stone-100"}`} data-testid={`rev-strat-${t.id}`}>{t.label}</button>
        ))}
      </div>

      {subTab === "rooms" && (
        <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden" data-testid="rev-rooms-setup">
          <div className="bg-stone-50 px-4 py-3 border-b flex justify-between items-center">
            <h3 className="font-bold text-stone-800 text-sm">Rooms Setup</h3>
          </div>
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
            <tbody>{data.rooms_setup.map((r, i) => (
              <tr key={r.id} className={`border-b border-stone-100 ${i === 0 ? "bg-violet-50/30" : ""}`} data-testid={`rev-room-row-${r.id}`}>
                <td className="px-4 py-3 font-semibold text-stone-800">{r.name}</td>
                <td className="px-4 py-3 text-stone-600 capitalize">{r.room_in_pms || r.name}</td>
                <td className="px-4 py-3 text-stone-500">Base Rate</td>
                <td className="px-4 py-3 text-center text-stone-600">{r.number_of_rooms}</td>
                <td className="px-4 py-3 text-center"><Badge className={`text-[10px] ${r.reference_derived === "Reference" ? "bg-violet-100 text-violet-700" : "bg-stone-100 text-stone-600"}`}>{r.reference_derived}</Badge></td>
                <td className="px-4 py-3 text-right font-semibold text-stone-800">{cur(r.base_price)}</td>
                <td className="px-4 py-3 text-right text-stone-500">{r.derivation !== null ? `+${cur(r.derivation)}` : "—"}</td>
                <td className="px-4 py-3 text-right text-stone-500">{cur(r.min_price)}</td>
                <td className="px-4 py-3 text-right text-stone-500">{cur(r.max_price)}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}

      {subTab === "dow" && (
        <div className="bg-white border border-stone-200 rounded-2xl p-6" data-testid="rev-dow-adjustments">
          <h3 className="font-bold text-stone-800 mb-4">Day-of-Week Adjustments</h3>
          <p className="text-sm text-stone-500 mb-4">Set price multipliers for each day of the week relative to the base rate</p>
          <div className="grid grid-cols-7 gap-3">
            {["Mon","Tue","Wed","Thu","Fri","Sat","Sun"].map((d, i) => {
              const val = data.strategy?.dow_adjustments?.[d.toLowerCase()] || 0;
              return (
                <div key={d} className="text-center border border-stone-200 rounded-xl p-4">
                  <div className="text-sm font-bold text-stone-800 mb-2">{d}</div>
                  <div className={`text-lg font-bold ${val > 0 ? "text-emerald-600" : val < 0 ? "text-red-600" : "text-stone-400"}`}>{val > 0 ? "+" : ""}{val}%</div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {subTab === "monthly" && (
        <div className="bg-white border border-stone-200 rounded-2xl p-6" data-testid="rev-monthly-adjustments">
          <h3 className="font-bold text-stone-800 mb-4">Monthly Adjustments</h3>
          <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
            {["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"].map(m => {
              const val = data.strategy?.monthly_adjustments?.[m.toLowerCase()] || 0;
              return (
                <div key={m} className="text-center border border-stone-200 rounded-xl p-3">
                  <div className="text-xs font-bold text-stone-500 mb-1">{m}</div>
                  <div className={`text-base font-bold ${val > 0 ? "text-emerald-600" : val < 0 ? "text-red-600" : "text-stone-400"}`}>{val > 0 ? "+" : ""}{val}%</div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {subTab === "occupancy" && (
        <div className="bg-white border border-stone-200 rounded-2xl p-6" data-testid="rev-occupancy-strategy">
          <h3 className="font-bold text-stone-800 mb-4">Occupancy Strategy</h3>
          <p className="text-sm text-stone-500 mb-4">Dynamic price adjustments based on current occupancy levels</p>
          <div className="space-y-3">
            {[{ range: "90-100%", adj: "+40%", color: "bg-emerald-500", desc: "High demand — maximize revenue" },
              { range: "75-89%", adj: "+20%", color: "bg-emerald-400", desc: "Strong demand — increase rates" },
              { range: "50-74%", adj: "Base", color: "bg-amber-400", desc: "Normal demand — standard pricing" },
              { range: "25-49%", adj: "-15%", color: "bg-orange-400", desc: "Low demand — attract bookings" },
              { range: "0-24%", adj: "-30%", color: "bg-red-400", desc: "Very low — aggressive pricing" },
            ].map(r => (
              <div key={r.range} className="flex items-center gap-4 p-3 border border-stone-200 rounded-xl">
                <div className={`w-3 h-3 rounded-full ${r.color}`} />
                <div className="w-20 font-semibold text-stone-800 text-sm">{r.range}</div>
                <div className={`w-16 font-bold text-sm ${r.adj.includes("+") ? "text-emerald-600" : r.adj.includes("-") ? "text-red-600" : "text-stone-500"}`}>{r.adj}</div>
                <div className="text-xs text-stone-400">{r.desc}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

/* ── MAIN PANEL ── */
const revTabs = [
  { id: "dashboard", label: "Dashboard" },
  { id: "calendar", label: "Rate Calendar" },
  { id: "strategy", label: "Pricing Strategy" },
];

export const RevenuePanel = ({ properties, activePropertyId }) => {
  const [tab, setTab] = useState("dashboard");
  const pid = activePropertyId || "all";

  return (
    <div className="p-5" data-testid="revenue-panel">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-bold text-stone-800">Revenue Management</h2>
          <p className="text-sm text-stone-500">Monitor performance, optimize pricing, maximize revenue</p>
        </div>
      </div>
      <div className="flex items-center gap-1 mb-6 overflow-x-auto pb-1 border-b border-stone-200">
        {revTabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`px-4 py-2.5 text-sm font-medium whitespace-nowrap transition-all border-b-2 -mb-[1px] ${
              tab === t.id ? "text-violet-700 border-violet-500 bg-violet-50/50" : "text-stone-400 border-transparent hover:text-stone-600"
            }`} data-testid={`rev-tab-${t.id}`}>{t.label}</button>
        ))}
      </div>
      <AnimatePresence mode="wait">
        <motion.div key={tab} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
          {tab === "dashboard" && <DashboardTab propertyId={pid} />}
          {tab === "calendar" && <RateCalendarTab propertyId={pid} />}
          {tab === "strategy" && <PricingStrategyTab propertyId={pid} />}
        </motion.div>
      </AnimatePresence>
    </div>
  );
};
