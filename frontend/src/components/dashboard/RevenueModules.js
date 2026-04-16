import { useState, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Shield, RefreshCw, AlertTriangle, CheckCircle, BarChart3, Play, DollarSign, TrendingUp } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

/* ── PARITY ── */
export const RevenueParity = ({ propertyId }) => {
  const [data, setData] = useState({ items: [], counts: {} });
  const [detecting, setDetecting] = useState(false);
  const load = () => { axios.get(`${API}/revenue/parity/${propertyId}`).then(r => setData(r.data)).catch(() => toast.error("Failed")); };
  useEffect(() => { load(); }, [propertyId]);

  const detect = async () => { setDetecting(true); try { const { data: r } = await axios.post(`${API}/revenue/parity/${propertyId}/detect`); toast.success(r.message); load(); } catch { toast.error("Failed"); } setDetecting(false); };
  const fix = async (id) => { try { await axios.put(`${API}/revenue/parity/${id}/fix`); toast.success("Fixed"); load(); } catch { toast.error("Failed"); } };

  return (
    <div className="space-y-6" data-testid="rev-parity">
      <div className="flex items-center justify-between">
        <div><h2 className="text-lg font-bold text-stone-800">Parity Violations</h2><p className="text-sm text-stone-500">Compare your rates with competitor pricing <span className="text-xs text-stone-400">Currency: GBP (£)</span></p></div>
        <button onClick={detect} disabled={detecting} className="flex items-center gap-2 bg-emerald-500 hover:bg-emerald-600 text-white px-4 py-2 rounded-xl text-sm font-medium disabled:opacity-50" data-testid="rev-detect-parity"><RefreshCw className={`w-4 h-4 ${detecting ? "animate-spin" : ""}`} />Detect Violations</button>
      </div>
      <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-sm text-amber-800">Parity fixes now create <strong>draft overrides</strong> only. Accept and publish them via Approvals & Publish to avoid silent calendar writes.</div>
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white border border-stone-200 rounded-2xl p-5 text-center"><p className="text-3xl font-bold text-red-500">{data.counts.open || 0}</p><p className="text-xs text-stone-400 mt-1">Open Violations</p></div>
        <div className="bg-white border border-stone-200 rounded-2xl p-5 text-center"><p className="text-3xl font-bold text-emerald-500">{data.counts.fixed || 0}</p><p className="text-xs text-stone-400 mt-1">Fixed</p></div>
        <div className="bg-white border border-stone-200 rounded-2xl p-5 text-center"><p className="text-3xl font-bold text-blue-500">{data.counts.total || 0}</p><p className="text-xs text-stone-400 mt-1">Total Detected</p></div>
      </div>
      <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden"><table className="w-full text-sm">
        <thead><tr className="border-b bg-stone-50/50">
          {["Date","Room Category","Your Price","Competitor","Channel","Delta","Status","Actions"].map(h => <th key={h} className="px-3 py-2 text-xs font-semibold text-stone-500 text-center">{h}</th>)}
        </tr></thead>
        <tbody>{data.items.length === 0 ? <tr><td colSpan={8} className="text-center py-12 text-stone-400"><Shield className="w-8 h-8 mx-auto mb-2 text-stone-200" />No violations detected</td></tr> : data.items.map(i => (
          <tr key={i.id} className="border-b border-stone-50">
            <td className="px-3 py-2 text-center text-stone-600">{i.date}</td>
            <td className="px-3 py-2 text-center text-stone-700 font-medium">{i.room_category}</td>
            <td className="px-3 py-2 text-center font-semibold">{cur(i.your_price)}</td>
            <td className="px-3 py-2 text-center">{cur(i.competitor_price)}</td>
            <td className="px-3 py-2 text-center text-stone-500">{i.channel}</td>
            <td className="px-3 py-2 text-center"><span className={`font-semibold ${i.delta > 0 ? "text-red-500" : "text-emerald-600"}`}>{i.delta > 0 ? "+" : ""}{cur(i.delta)}</span></td>
            <td className="px-3 py-2 text-center"><Badge className={`text-[10px] ${i.status === "open" ? "bg-red-100 text-red-700" : "bg-emerald-100 text-emerald-700"}`}>{i.status}</Badge></td>
            <td className="px-3 py-2 text-center">{i.status === "open" && <button onClick={() => fix(i.id)} className="text-xs bg-emerald-500 text-white px-2 py-1 rounded-lg" data-testid={`rev-fix-${i.id}`}>Fix</button>}</td>
          </tr>
        ))}</tbody>
      </table></div>
    </div>
  );
};

/* ── OVERBOOKING ── */
export const RevenueOverbooking = ({ propertyId }) => {
  const [policies, setPolicies] = useState([]);
  const [sim, setSim] = useState(null);
  const [form, setForm] = useState({ room_category: "", buffer_rooms: 0, max_overbook_pct: 5, walk_cost: 150, no_show_rate: 0.05, cancellation_rate: 0.1 });
  const [simulating, setSimulating] = useState(false);

  const load = () => { axios.get(`${API}/revenue/overbooking/${propertyId}`).then(r => setPolicies(r.data.policies)).catch(() => toast.error("Failed")); };
  useEffect(() => { load(); }, [propertyId]);

  const savePolicy = async () => { try { await axios.post(`${API}/revenue/overbooking/${propertyId}`, form); toast.success("Policy saved"); load(); } catch { toast.error("Failed"); } };
  const simulate = async () => { setSimulating(true); try { const { data } = await axios.post(`${API}/revenue/overbooking/${propertyId}/simulate`, {}); setSim(data); } catch { toast.error("Failed"); } setSimulating(false); };

  return (
    <div className="space-y-6" data-testid="rev-overbooking">
      <h2 className="text-lg font-bold text-stone-800">Overbooking Manager</h2>
      <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-sm text-amber-800">Overbooking simulations and adjustments stay <strong>draft</strong> until accepted & published from Approvals & Publish. No inventory changes happen silently.</div>

      <div className="bg-white border border-stone-200 rounded-2xl p-6">
        <div className="flex items-center justify-between mb-4"><h3 className="font-bold text-stone-800">Run Simulation</h3></div>
        <button onClick={simulate} disabled={simulating} className="flex items-center gap-2 bg-violet-600 hover:bg-violet-700 text-white px-5 py-2.5 rounded-xl text-sm font-semibold disabled:opacity-50" data-testid="rev-run-sim"><Play className="w-4 h-4" />{simulating ? "Simulating..." : "Run Simulation"}</button>
      </div>

      {sim && (
        <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden">
          <div className="px-5 py-3 bg-stone-50 border-b font-bold text-sm text-stone-800">Simulation Results (30 days)</div>
          <div className="overflow-x-auto"><table className="w-full text-sm">
            <thead><tr className="border-b bg-stone-50/50">{["Date","On Books","No-Show Est","Cancel Est","Optimal Overbook","Expected Rev","Walk Risk"].map(h => <th key={h} className="px-3 py-2 text-xs font-semibold text-stone-500 text-center">{h}</th>)}</tr></thead>
            <tbody>{sim.simulation.slice(0, 14).map(r => (
              <tr key={r.date} className="border-b border-stone-50">
                <td className="px-3 py-2 text-stone-600">{r.dow} {r.date.split("-").slice(1).join("/")}</td>
                <td className="px-3 py-2 text-center font-semibold">{r.on_books}</td>
                <td className="px-3 py-2 text-center text-stone-500">{r.no_show_est}</td>
                <td className="px-3 py-2 text-center text-stone-500">{r.cancel_est}</td>
                <td className="px-3 py-2 text-center font-semibold text-violet-700">{r.optimal_overbook}</td>
                <td className="px-3 py-2 text-center text-emerald-600">{cur(r.expected_revenue)}</td>
                <td className="px-3 py-2 text-center"><Badge className={`text-[10px] ${r.walk_risk > 0 ? "bg-red-100 text-red-700" : "bg-emerald-100 text-emerald-700"}`}>{r.walk_risk}</Badge></td>
              </tr>
            ))}</tbody>
          </table></div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white border border-stone-200 rounded-2xl p-6">
          <h3 className="font-bold text-stone-800 mb-3">Current Policies</h3>
          {policies.length === 0 ? <p className="text-sm text-stone-400">No policies configured</p> : (
            <table className="w-full text-sm"><thead><tr className="border-b">{["Room Category","Buffer","Max %","Walk Cost"].map(h => <th key={h} className="px-2 py-1 text-xs text-stone-500 text-left">{h}</th>)}</tr></thead>
              <tbody>{policies.map(p => <tr key={p.id} className="border-b border-stone-50"><td className="px-2 py-1.5">{p.room_category}</td><td className="px-2 py-1.5">{p.buffer_rooms}</td><td className="px-2 py-1.5">{p.max_overbook_pct}%</td><td className="px-2 py-1.5">{cur(p.walk_cost)}</td></tr>)}</tbody>
            </table>
          )}
        </div>
        <div className="bg-white border border-stone-200 rounded-2xl p-6">
          <h3 className="font-bold text-stone-800 mb-3">Add Policy</h3>
          <div className="space-y-3">
            <div><label className="text-xs font-semibold text-stone-600">Room Category</label><Input value={form.room_category} onChange={e => setForm(p => ({ ...p, room_category: e.target.value }))} placeholder="Select Category" /></div>
            <div className="grid grid-cols-2 gap-2">
              <div><label className="text-xs font-semibold text-stone-600">Buffer Rooms</label><Input type="number" value={form.buffer_rooms} onChange={e => setForm(p => ({ ...p, buffer_rooms: Number(e.target.value) }))} /></div>
              <div><label className="text-xs font-semibold text-stone-600">Max Overbook %</label><Input value={`${form.max_overbook_pct}%`} onChange={e => setForm(p => ({ ...p, max_overbook_pct: parseFloat(e.target.value) || 0 }))} /></div>
            </div>
            <div><label className="text-xs font-semibold text-stone-600">Walk Cost</label><Input value={form.walk_cost} onChange={e => setForm(p => ({ ...p, walk_cost: parseFloat(e.target.value) || 0 }))} /></div>
            <div className="grid grid-cols-2 gap-2">
              <div><label className="text-xs font-semibold text-stone-600">No-Show Rate</label><Input type="number" step="0.01" value={form.no_show_rate} onChange={e => setForm(p => ({ ...p, no_show_rate: parseFloat(e.target.value) || 0 }))} /></div>
              <div><label className="text-xs font-semibold text-stone-600">Cancellation Rate</label><Input type="number" step="0.01" value={form.cancellation_rate} onChange={e => setForm(p => ({ ...p, cancellation_rate: parseFloat(e.target.value) || 0 }))} /></div>
            </div>
            <button onClick={savePolicy} className="w-full bg-emerald-500 hover:bg-emerald-600 text-white px-4 py-2.5 rounded-xl text-sm font-semibold" data-testid="rev-save-policy">Save Policy</button>
          </div>
        </div>
      </div>
    </div>
  );
};

/* ── ACTION CENTER ── */
export const RevenueActionCenter = ({ propertyId }) => {
  const [data, setData] = useState({ items: [], counts: {} });
  const [refreshing, setRefreshing] = useState(false);
  const load = () => { axios.get(`${API}/revenue/action-center/${propertyId}`).then(r => setData(r.data)).catch(() => toast.error("Failed")); };
  useEffect(() => { load(); }, [propertyId]);
  const refresh = async () => { setRefreshing(true); try { const { data: r } = await axios.post(`${API}/revenue/action-center/${propertyId}/refresh`); toast.success(r.message); load(); } catch { toast.error("Failed"); } setRefreshing(false); };
  const apply = async (id) => { try { await axios.put(`${API}/revenue/action-center/${id}/applied`); toast.success("Applied"); load(); } catch { toast.error("Failed"); } };

  return (
    <div className="space-y-6" data-testid="rev-action-center">
      <div className="flex items-center justify-between">
        <div><h2 className="text-lg font-bold text-stone-800">Action Center</h2><p className="text-sm text-stone-500">System alerts and recommendations</p></div>
        <button onClick={refresh} disabled={refreshing} className="flex items-center gap-2 bg-emerald-500 hover:bg-emerald-600 text-white px-4 py-2 rounded-xl text-sm font-medium disabled:opacity-50" data-testid="rev-refresh-actions"><RefreshCw className={`w-4 h-4 ${refreshing ? "animate-spin" : ""}`} />Refresh</button>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Total Actions", value: data.counts.total || 0, color: "text-blue-600" },
          { label: "Open", value: data.counts.open || 0, color: "text-red-500" },
          { label: "Applied", value: data.counts.applied || 0, color: "text-emerald-600" },
          { label: "High Impact", value: data.counts.high_impact || 0, color: "text-amber-500" },
        ].map(k => (
          <div key={k.label} className="bg-white border border-stone-200 rounded-2xl p-5 text-center"><p className={`text-3xl font-bold ${k.color}`}>{k.value}</p><p className="text-xs text-stone-400 mt-1">{k.label}</p></div>
        ))}
      </div>
      <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden"><table className="w-full text-sm">
        <thead><tr className="border-b bg-stone-50/50">{["Date","Type","Title","Message","Impact","Risk","Status","Actions"].map(h => <th key={h} className="px-3 py-2 text-xs font-semibold text-stone-500 text-center">{h}</th>)}</tr></thead>
        <tbody>{data.items.length === 0 ? <tr><td colSpan={8} className="text-center py-12 text-stone-400"><AlertTriangle className="w-8 h-8 mx-auto mb-2 text-stone-200" />No actions yet. Click Refresh to scan.</td></tr> : data.items.map(i => (
          <tr key={i.id} className="border-b border-stone-50">
            <td className="px-3 py-2 text-center text-stone-500 text-xs">{i.date}</td>
            <td className="px-3 py-2 text-center"><Badge className="text-[10px] bg-violet-100 text-violet-700">{i.type}</Badge></td>
            <td className="px-3 py-2 font-medium text-stone-700">{i.title}</td>
            <td className="px-3 py-2 text-xs text-stone-500 max-w-[200px] truncate">{i.message}</td>
            <td className="px-3 py-2 text-center"><Badge className={`text-[10px] ${i.impact === "high" ? "bg-red-100 text-red-700" : "bg-stone-100 text-stone-600"}`}>{i.impact}</Badge></td>
            <td className="px-3 py-2 text-center"><Badge className={`text-[10px] ${i.risk === "high" ? "bg-red-100 text-red-700" : i.risk === "medium" ? "bg-amber-100 text-amber-700" : "bg-emerald-100 text-emerald-700"}`}>{i.risk}</Badge></td>
            <td className="px-3 py-2 text-center"><Badge className={`text-[10px] ${i.status === "open" ? "bg-amber-100 text-amber-700" : "bg-emerald-100 text-emerald-700"}`}>{i.status}</Badge></td>
            <td className="px-3 py-2 text-center">{i.status === "open" && <button onClick={() => apply(i.id)} className="text-xs bg-emerald-500 text-white px-2 py-1 rounded-lg">Apply</button>}</td>
          </tr>
        ))}</tbody>
      </table></div>
    </div>
  );
};

/* ── PROFIT OS ── */
export const RevenueProfitOS = ({ propertyId }) => {
  const [data, setData] = useState(null);
  useEffect(() => { axios.get(`${API}/revenue/profit-os/${propertyId}`).then(r => setData(r.data)).catch(() => toast.error("Failed")); }, [propertyId]);
  if (!data) return <div className="text-center py-12 text-stone-400">Loading...</div>;

  return (
    <div className="space-y-6" data-testid="rev-profit-os">
      <div className="flex items-center justify-between">
        <div><h2 className="text-lg font-bold text-stone-800">Profit OS</h2><p className="text-sm text-stone-500">Net ADR + Contribution per room night analysis</p></div>
      </div>
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white border border-stone-200 rounded-2xl p-5 text-center"><p className="text-3xl font-bold text-emerald-600">{cur(data.kpis.avg_gross_adr)}</p><p className="text-xs text-stone-400 mt-1">Avg Gross ADR</p></div>
        <div className="bg-white border border-stone-200 rounded-2xl p-5 text-center"><p className="text-3xl font-bold text-blue-600">{cur(data.kpis.avg_net_adr)}</p><p className="text-xs text-stone-400 mt-1">Avg Net ADR</p></div>
        <div className="bg-white border border-stone-200 rounded-2xl p-5 text-center"><p className="text-3xl font-bold text-violet-600">{cur(data.kpis.avg_contribution_par)}</p><p className="text-xs text-stone-400 mt-1">Avg ContributionPAR</p></div>
      </div>
      <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden">
        <div className="px-5 py-3 bg-stone-50 border-b font-bold text-sm text-stone-800">Channel Breakdown</div>
        <table className="w-full text-sm"><thead><tr className="border-b bg-stone-50/50">
          {["Channel","Days","Avg Gross ADR","Avg Net ADR","Commission","Avg ContributionPAR","Total Contribution"].map(h => <th key={h} className="px-3 py-2 text-xs font-semibold text-stone-500 text-center">{h}</th>)}
        </tr></thead>
        <tbody>{data.channels.length === 0 ? <tr><td colSpan={7} className="text-center py-8 text-stone-400">No channel data</td></tr> : data.channels.map(c => (
          <tr key={c.channel} className="border-b border-stone-50">
            <td className="px-3 py-2 font-medium text-stone-700">{c.channel}</td>
            <td className="px-3 py-2 text-center text-stone-600">{c.days}</td>
            <td className="px-3 py-2 text-center text-emerald-600 font-semibold">{cur(c.gross_adr)}</td>
            <td className="px-3 py-2 text-center text-blue-600 font-semibold">{cur(c.net_adr)}</td>
            <td className="px-3 py-2 text-center text-stone-400">{c.commission_pct}%</td>
            <td className="px-3 py-2 text-center text-violet-700 font-semibold">{cur(c.contribution_par)}</td>
            <td className="px-3 py-2 text-center font-semibold">{cur(c.total_contribution)}</td>
          </tr>
        ))}</tbody></table>
      </div>
    </div>
  );
};

/* ── DISTRIBUTION COCKPIT ── */
export const RevenueDistribution = ({ propertyId }) => {
  const [data, setData] = useState(null);
  useEffect(() => { axios.get(`${API}/revenue/distribution/${propertyId}`).then(r => setData(r.data)).catch(() => toast.error("Failed")); }, [propertyId]);
  if (!data) return <div className="text-center py-12 text-stone-400">Loading...</div>;

  return (
    <div className="space-y-6" data-testid="rev-distribution">
      <h2 className="text-lg font-bold text-stone-800">Distribution Cockpit</h2>
      <p className="text-sm text-stone-500">Channel performance and contribution analysis | Period: {data.period?.start} to {data.period?.end}</p>
      <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden">
        <div className="px-5 py-3 bg-stone-50 border-b font-bold text-sm text-stone-800">Channel Performance (Sorted by ContributionPAR)</div>
        <table className="w-full text-sm"><thead><tr className="border-b bg-stone-50/50">
          {["Channel","Days","Bookings","Avg Gross ADR","Avg Net ADR","Avg ContributionPAR","Total ContributionPAR"].map(h => <th key={h} className="px-3 py-2 text-xs font-semibold text-stone-500 text-center">{h}</th>)}
        </tr></thead>
        <tbody>{data.channels.length === 0 ? <tr><td colSpan={7} className="text-center py-8 text-stone-400">No data</td></tr> : data.channels.map(c => (
          <tr key={c.channel} className="border-b border-stone-50">
            <td className="px-3 py-2 font-medium text-stone-700">{c.channel}</td>
            <td className="px-3 py-2 text-center">{c.days}</td>
            <td className="px-3 py-2 text-center">{c.bookings}</td>
            <td className="px-3 py-2 text-center">{cur(c.avg_gross_adr)}</td>
            <td className="px-3 py-2 text-center">{cur(c.avg_net_adr)}</td>
            <td className="px-3 py-2 text-center font-semibold text-emerald-600">{cur(c.avg_contribution_par)}</td>
            <td className="px-3 py-2 text-center font-semibold">{cur(c.total_contribution_par)}</td>
          </tr>
        ))}</tbody></table>
      </div>
    </div>
  );
};

/* ── COMPETITOR INTEL ── */
export const RevenueCompetitors = ({ propertyId }) => {
  const [data, setData] = useState(null);
  useEffect(() => { axios.get(`${API}/revenue/competitors/${propertyId}`).then(r => setData(r.data)).catch(() => toast.error("Failed")); }, [propertyId]);
  if (!data) return <div className="text-center py-12 text-stone-400">Loading...</div>;

  return (
    <div className="space-y-6" data-testid="rev-competitors">
      <div className="flex items-center justify-between">
        <div><h2 className="text-lg font-bold text-stone-800">Competitor Intelligence</h2><p className="text-sm text-stone-500">Rate comparison across your competitive set</p></div>
        <div className="text-right"><p className="text-xs text-stone-400">Your ADR</p><p className="text-xl font-bold text-violet-700">{cur(data.your_adr)}</p></div>
      </div>
      <div className="bg-white border border-stone-200 rounded-2xl p-5">
        <div className="flex items-center justify-between mb-3"><span className="font-bold text-stone-800 text-sm">Market Average</span><span className="text-xl font-bold text-stone-600">{cur(data.market_avg)}</span></div>
        <div className="w-full bg-stone-100 rounded-full h-3 overflow-hidden relative">
          <div className="bg-violet-500 h-3 rounded-full" style={{ width: `${Math.min(100, (data.your_adr / Math.max(data.market_avg * 1.5, 1)) * 100)}%` }} />
          <div className="absolute top-0 h-3 w-0.5 bg-stone-600" style={{ left: `${(data.market_avg / Math.max(data.market_avg * 1.5, 1)) * 100}%` }} />
        </div>
        <div className="flex justify-between mt-1 text-[10px] text-stone-400"><span>Your Rate</span><span>Market Avg</span></div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {data.competitors.map(c => (
          <div key={c.name} className="bg-white border border-stone-200 rounded-2xl p-5" data-testid={`rev-comp-${c.name}`}>
            <div className="flex items-center justify-between mb-3">
              <div><p className="font-bold text-stone-800 text-sm">{c.name}</p><p className="text-xs text-stone-400">{c.stars} stars | {c.rooms} rooms</p></div>
              <div className="text-right"><p className="text-lg font-bold text-stone-800">{cur(c.avg_rate)}</p>
                <p className={`text-xs font-semibold ${c.delta_vs_you > 0 ? "text-red-500" : "text-emerald-600"}`}>{c.delta_vs_you > 0 ? "+" : ""}{cur(c.delta_vs_you)} {c.position}</p></div>
            </div>
            <div className="flex items-end gap-0.5 h-10">
              {c.daily_rates.slice(0, 14).map((r, i) => (
                <div key={i} className={`flex-1 rounded-t-sm ${r.rate > data.your_adr ? "bg-red-300" : "bg-emerald-300"}`}
                  style={{ height: `${Math.max(4, (r.rate / Math.max(data.market_avg * 1.5, 1)) * 40)}px` }} title={`${r.dow}: ${cur(r.rate)}`} />
              ))}
            </div>
            <div className="flex justify-between text-[8px] text-stone-300 mt-0.5">
              {c.daily_rates.slice(0, 14).filter((_, i) => i % 2 === 0).map(r => <span key={r.date}>{r.dow}</span>)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
