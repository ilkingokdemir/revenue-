import { useState, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { ExportButton } from "./RevenueExports";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;

export const RevenueAnalytics = ({ propertyId }) => {
  const [subTab, setSubTab] = useState("performance");
  return (
    <div data-testid="rev-analytics">
      <div className="flex items-center gap-1 mb-6 border-b border-stone-200 overflow-x-auto">
        {[{id:"performance",label:"Performance"},{id:"pickup",label:"Pickup Report"},{id:"budget",label:"Budget Variance"}].map(t => (
          <button key={t.id} onClick={() => setSubTab(t.id)} className={`px-4 py-2.5 text-sm font-medium whitespace-nowrap border-b-2 -mb-[1px] ${subTab === t.id ? "text-violet-700 border-violet-500" : "text-stone-400 border-transparent hover:text-stone-600"}`} data-testid={`rev-analytics-${t.id}`}>{t.label}</button>
        ))}
      </div>
      {subTab === "performance" && <PerformanceTab propertyId={propertyId} />}
      {subTab === "pickup" && <PickupTab propertyId={propertyId} />}
      {subTab === "budget" && <BudgetTab propertyId={propertyId} />}
    </div>
  );
};

const PerformanceTab = ({ propertyId }) => {
  const [data, setData] = useState(null);
  const [period, setPeriod] = useState("mtd");
  useEffect(() => { axios.get(`${API}/revenue/analytics/performance/${propertyId}?period=${period}`).then(r => setData(r.data)).catch(() => toast.error("Failed")); }, [propertyId, period]);
  if (!data) return <div className="text-center py-12 text-stone-400">Loading...</div>;
  const { kpis, daily, dow_performance, segments, trends } = data;

  return (
    <div className="space-y-6" data-testid="rev-performance">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-stone-800">Performance Analytics</h2>
        <div className="flex items-center gap-2">
          <ExportButton endpoint={`/revenue/export/performance/${propertyId}?period=${period}`} label="Performance" />
          {["mtd","last30","last90"].map(p => (
            <button key={p} onClick={() => setPeriod(p)} className={`px-3 py-1.5 text-xs font-medium rounded-lg ${period === p ? "bg-violet-100 text-violet-700" : "text-stone-400 hover:bg-stone-50"}`}>{p === "mtd" ? "MTD" : p === "last30" ? "Last 30" : "Last 90"}</button>
          ))}
        </div>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Occupancy", value: `${kpis.occupancy}%`, sdly: `SDLY: ${kpis.sdly_occ}%` },
          { label: "ADR", value: cur(kpis.adr), sdly: `SDLY: ${cur(kpis.sdly_adr)}` },
          { label: "RevPAR", value: cur(kpis.revpar), sdly: `SDLY: ${cur(kpis.sdly_revpar)}` },
          { label: "Room Revenue", value: cur(kpis.room_revenue), sdly: `${kpis.nights_sold} room nights sold` },
        ].map(k => (
          <div key={k.label} className="bg-white border border-stone-200 rounded-2xl p-5">
            <p className="text-xs text-stone-400">{k.label}</p>
            <p className="text-2xl font-bold text-stone-800 mt-1">{k.value}</p>
            <p className="text-[10px] text-stone-400 mt-1">{k.sdly}</p>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white border border-stone-200 rounded-2xl p-5">
          <h3 className="font-bold text-stone-800 mb-4">Day of Week Performance</h3>
          <div className="space-y-3">{dow_performance.map(d => (
            <div key={d.dow} className="flex items-center gap-3">
              <span className="w-8 text-sm font-medium text-stone-600">{d.dow}</span>
              <div className="flex-1 bg-stone-100 rounded-full h-4 overflow-hidden"><div className="bg-violet-500 h-4 rounded-full" style={{ width: `${d.occupancy}%` }} /></div>
              <span className="w-12 text-sm font-semibold text-stone-700 text-right">{d.occupancy}%</span>
              <span className="w-12 text-xs text-stone-400 text-right">{cur(d.adr)}</span>
            </div>
          ))}</div>
        </div>
        <div className="bg-white border border-stone-200 rounded-2xl p-5">
          <h3 className="font-bold text-stone-800 mb-4">Segment Mix</h3>
          {segments.length === 0 ? <p className="text-sm text-stone-400">No segment data available</p> : (
            <div className="space-y-3">{segments.map(s => (
              <div key={s.name} className="flex items-center gap-3">
                <span className="w-2 h-2 rounded-full bg-emerald-500 flex-shrink-0" />
                <span className="flex-1 text-sm font-medium text-stone-700">{s.name}</span>
                <div className="w-32 bg-stone-100 rounded-full h-2 overflow-hidden"><div className="bg-emerald-500 h-2 rounded-full" style={{ width: `${s.pct}%` }} /></div>
                <span className="w-12 text-sm font-semibold text-stone-700 text-right">{s.pct}%</span>
                <span className="w-10 text-xs text-stone-400 text-right">{s.nights}</span>
              </div>
            ))}</div>
          )}
        </div>
      </div>
      <div className="bg-stone-800 rounded-2xl p-5 text-white">
        <h3 className="font-bold mb-3">Trend Analysis</h3>
        <div className="flex gap-6">
          {[{ label: "Occupancy Trend", val: trends.occupancy }, { label: "ADR Trend", val: trends.adr }].map(t => (
            <div key={t.label} className="bg-stone-700/50 rounded-xl px-4 py-3">
              <p className="text-xs text-stone-400">{t.label}</p>
              <div className="flex items-center gap-2 mt-1">
                {t.val === "Up" ? <TrendingUp className="w-4 h-4 text-emerald-400" /> : t.val === "Down" ? <TrendingDown className="w-4 h-4 text-red-400" /> : <Minus className="w-4 h-4 text-stone-400" />}
                <span className={`font-bold ${t.val === "Up" ? "text-emerald-400" : t.val === "Down" ? "text-red-400" : "text-stone-300"}`}>{t.val}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

const PickupTab = ({ propertyId }) => {
  const [data, setData] = useState(null);
  useEffect(() => { axios.get(`${API}/revenue/analytics/pickup/${propertyId}`).then(r => setData(r.data)).catch(() => toast.error("Failed")); }, [propertyId]);
  if (!data) return <div className="text-center py-12 text-stone-400">Loading...</div>;
  const { kpis, rows } = data;
  const paceColor = (p) => p === "Ahead" ? "bg-emerald-100 text-emerald-700" : p === "Behind" ? "bg-red-100 text-red-700" : "bg-blue-100 text-blue-700";
  const occBar = (o) => o >= 80 ? "bg-emerald-500" : o >= 50 ? "bg-amber-400" : o > 0 ? "bg-red-400" : "bg-stone-200";

  return (
    <div className="space-y-6" data-testid="rev-pickup">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-stone-800">Pickup Report</h2>
        <ExportButton endpoint={`/revenue/export/pickup/${propertyId}`} label="Pickup" />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Total On Books", value: kpis.total_on_books, sub: "Room nights confirmed", color: "text-blue-600" },
          { label: "Remaining to Sell", value: kpis.remaining_to_sell, sub: "Available room nights", color: "text-violet-600" },
          { label: "Avg Occupancy", value: `${kpis.avg_occupancy}%`, sub: "Current booking level" },
          { label: "Room Revenue On Books", value: cur(kpis.room_revenue), sub: "Confirmed revenue" },
        ].map(k => (
          <div key={k.label} className="bg-white border border-stone-200 rounded-2xl p-5">
            <p className="text-xs text-stone-400">{k.label}</p>
            <p className={`text-2xl font-bold mt-1 ${k.color || "text-stone-800"}`}>{k.value}</p>
            <p className="text-[10px] text-stone-400 mt-1">{k.sub}</p>
          </div>
        ))}
      </div>
      <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden">
        <div className="px-5 py-3 bg-stone-50 border-b flex items-center justify-between">
          <span className="font-bold text-stone-800 text-sm">Daily Pickup Detail</span>
          <div className="flex gap-3 text-xs text-stone-400">
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-emerald-100 border border-emerald-200" />Ahead</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-blue-100 border border-blue-200" />On Pace</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-red-100 border border-red-200" />Behind</span>
          </div>
        </div>
        <div className="overflow-x-auto"><table className="w-full text-sm">
          <thead><tr className="border-b bg-stone-50/50">
            {["Date","Days Out","On Books","Remaining","Occupancy","ADR","SDLY","vs SDLY","Pace"].map(h =>
              <th key={h} className="px-3 py-2 text-xs font-semibold text-stone-500 text-center whitespace-nowrap">{h}</th>
            )}
          </tr></thead>
          <tbody>{rows.slice(0, 21).map(r => (
            <tr key={r.date} className={`border-b border-stone-50 ${r.is_today ? "bg-violet-50/30" : ""}`}>
              <td className="px-3 py-2.5"><div className="font-medium text-stone-700">{r.day_name}</div><div className="text-[10px] text-stone-400">{r.day_date}</div></td>
              <td className="px-3 py-2.5 text-center text-stone-500 text-xs">{r.days_out}</td>
              <td className="px-3 py-2.5 text-center font-semibold text-emerald-600">{r.on_books}</td>
              <td className="px-3 py-2.5 text-center text-violet-600">{r.remaining}</td>
              <td className="px-3 py-2.5"><div className="flex items-center gap-2 justify-center"><div className="w-16 bg-stone-100 rounded-full h-2.5 overflow-hidden"><div className={`h-2.5 rounded-full ${occBar(r.occupancy)}`} style={{ width: `${r.occupancy}%` }} /></div><span className="text-xs font-medium text-stone-600 w-10">{r.occupancy}%</span></div></td>
              <td className="px-3 py-2.5 text-center text-stone-700">{cur(r.adr)}</td>
              <td className="px-3 py-2.5 text-center text-stone-400">{r.sdly}</td>
              <td className="px-3 py-2.5 text-center"><span className={`font-semibold text-xs ${r.vs_sdly > 0 ? "text-emerald-600" : r.vs_sdly < 0 ? "text-red-500" : "text-stone-400"}`}>{r.vs_sdly > 0 ? "+" : ""}{r.vs_sdly}%</span></td>
              <td className="px-3 py-2.5 text-center"><Badge className={`text-[10px] ${paceColor(r.pace)}`}>{r.pace}</Badge></td>
            </tr>
          ))}</tbody>
        </table></div>
      </div>
    </div>
  );
};

const BudgetTab = ({ propertyId }) => {
  const [data, setData] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ target_occupancy: 75, target_adr: 80, target_revenue: 5000 });
  useEffect(() => { axios.get(`${API}/revenue/analytics/budget/${propertyId}`).then(r => setData(r.data)).catch(() => toast.error("Failed")); }, [propertyId]);

  const saveBudget = async () => {
    try { await axios.post(`${API}/revenue/analytics/budget/${propertyId}`, form); toast.success("Budget saved"); setShowForm(false); } catch { toast.error("Failed"); }
  };

  if (!data) return <div className="text-center py-12 text-stone-400">Loading...</div>;
  const { kpis, daily, has_budget, exceeding_budget } = data;

  return (
    <div className="space-y-6" data-testid="rev-budget">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-stone-800">Budget Variance</h2>
        <div className="flex items-center gap-2">
          <ExportButton endpoint={`/revenue/export/budget/${propertyId}`} label="Budget" />
          <button onClick={() => setShowForm(!showForm)} className="bg-amber-500 hover:bg-amber-600 text-white px-4 py-2 rounded-xl text-sm font-medium" data-testid="rev-set-budget">+ Set Budget</button>
        </div>
      </div>
      {!has_budget && <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-sm text-amber-800 font-medium">No budget defined for this period. Set budget targets to track variance and performance.</div>}
      {showForm && (
        <div className="bg-white border border-stone-200 rounded-2xl p-5 grid grid-cols-1 md:grid-cols-4 gap-3">
          <div><label className="text-xs font-semibold text-stone-600 block mb-1">Target Occupancy %</label><input type="number" value={form.target_occupancy} onChange={e => setForm(p => ({ ...p, target_occupancy: Number(e.target.value) }))} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" /></div>
          <div><label className="text-xs font-semibold text-stone-600 block mb-1">Target ADR (£)</label><input type="number" value={form.target_adr} onChange={e => setForm(p => ({ ...p, target_adr: Number(e.target.value) }))} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" /></div>
          <div><label className="text-xs font-semibold text-stone-600 block mb-1">Target Revenue (£)</label><input type="number" value={form.target_revenue} onChange={e => setForm(p => ({ ...p, target_revenue: Number(e.target.value) }))} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" /></div>
          <div className="flex items-end"><button onClick={saveBudget} className="bg-emerald-500 hover:bg-emerald-600 text-white px-4 py-2 rounded-xl text-sm font-medium w-full" data-testid="rev-save-budget">Save Budget</button></div>
        </div>
      )}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Occupancy", value: `${kpis.occupancy}%`, budget: `Budget: ${kpis.budget_occ}%` },
          { label: "ADR", value: cur(kpis.adr), budget: `Budget: ${cur(kpis.budget_adr)}` },
          { label: "RevPAR", value: cur(kpis.revpar), budget: "" },
          { label: "Room Revenue", value: cur(kpis.room_revenue), budget: `Budget: ${cur(kpis.budget_rev)}` },
        ].map(k => (
          <div key={k.label} className="bg-white border border-stone-200 rounded-2xl p-5">
            <p className="text-xs text-stone-400">{k.label}</p>
            <p className="text-2xl font-bold text-stone-800 mt-1">{k.value}</p>
            <p className="text-[10px] text-stone-400 mt-1">{k.budget}</p>
          </div>
        ))}
      </div>
      {exceeding_budget && <div className="bg-emerald-50 border border-emerald-200 rounded-xl px-4 py-3 text-sm text-emerald-800 font-medium">Excellent! Revenue is exceeding budget by more than 10%.</div>}
      <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden">
        <div className="px-5 py-3 bg-stone-50 border-b font-bold text-stone-800 text-sm">Daily Breakdown</div>
        <div className="overflow-x-auto"><table className="w-full text-sm">
          <thead><tr className="border-b bg-stone-50/50">
            {["Date","Actual Occ","Budget Occ","Occ Variance","Actual Rev","Budget Rev","Rev Variance"].map(h =>
              <th key={h} className="px-3 py-2 text-xs font-semibold text-stone-500 text-center">{h}</th>
            )}
          </tr></thead>
          <tbody>{daily.map(r => (
            <tr key={r.date} className="border-b border-stone-50">
              <td className="px-3 py-2 font-medium text-stone-700 whitespace-nowrap">{r.day_label}</td>
              <td className="px-3 py-2 text-center font-semibold">{r.actual_occ}%</td>
              <td className="px-3 py-2 text-center text-stone-400">{r.budget_occ > 0 ? `${r.budget_occ}%` : "—%"}</td>
              <td className="px-3 py-2 text-center"><span className={r.variance_occ !== null ? (r.variance_occ >= 0 ? "text-emerald-600" : "text-red-500") : "text-stone-300"}>{r.variance_occ !== null ? `${r.variance_occ > 0 ? "+" : ""}${r.variance_occ}pp` : "—"}</span></td>
              <td className="px-3 py-2 text-center font-semibold">{cur(r.actual_rev)}</td>
              <td className="px-3 py-2 text-center text-stone-400">{r.budget_rev > 0 ? cur(r.budget_rev) : "£—"}</td>
              <td className="px-3 py-2 text-center"><span className={r.variance_rev !== null ? (r.variance_rev >= 0 ? "text-emerald-600" : "text-red-500") : "text-stone-300"}>{r.variance_rev !== null ? cur(r.variance_rev) : "—"}</span></td>
            </tr>
          ))}</tbody>
        </table></div>
      </div>
    </div>
  );
};
