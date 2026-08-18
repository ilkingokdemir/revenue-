/**
 * Door-Lock Audit + Owner Portal Combined Panel
 * ---------------------------------------------
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, Lock, Building, RefreshCw, Plus, AlertTriangle } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const fmt = (n) => `£${Number(n || 0).toFixed(2)}`;

export default function SecurityOwnerPanel({ propertyId, hotelName = "" }) {
  const [tab, setTab] = useState("locks");
  return (
    <div className="space-y-6" data-testid="security-owner-panel">
      <div>
        <h2 className="text-2xl font-semibold text-stone-100">Security & Ownership</h2>
        <p className="text-sm text-stone-400 mt-1">{hotelName ? `${hotelName} · ` : ""}Door-lock audit log + serviced-apartment owner portal.</p>
      </div>
      <div className="flex gap-2">
        <Tab active={tab === "locks"} onClick={() => setTab("locks")} testId="so-tab-locks" icon={Lock}>Door-lock audit</Tab>
        <Tab active={tab === "owner"} onClick={() => setTab("owner")} testId="so-tab-owner" icon={Building}>Owner portal</Tab>
      </div>
      {tab === "locks" ? <DoorLockTab propertyId={propertyId} /> : <OwnerTab />}
    </div>
  );
}

function Tab({ active, onClick, icon: Icon, testId, children }) {
  return (
    <button data-testid={testId} onClick={onClick}
      className={`px-3 py-2 rounded-lg text-sm border flex items-center gap-2 ${active
        ? "bg-cyan-500/20 border-cyan-500/40 text-cyan-200"
        : "bg-stone-800 border-stone-700 text-stone-300 hover:bg-stone-700"}`}>
      <Icon className="w-4 h-4" />{children}
    </button>
  );
}

function DoorLockTab({ propertyId }) {
  const [data, setData] = useState({ items: [], denied_count: 0, master_key_uses: 0 });
  const [filter, setFilter] = useState({ days: 7, room: "", method: "", result: "" });
  const [loading, setLoading] = useState(false);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ room_number: "", method: "card", actor_role: "guest", actor_name: "", result: "success" });

  const load = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const params = new URLSearchParams({ days: filter.days });
      if (filter.room) params.append("room_number", filter.room);
      if (filter.method) params.append("method", filter.method);
      if (filter.result) params.append("result", filter.result);
      const { data } = await axios.get(`${API}/door-locks/${propertyId}/log?${params}`);
      setData(data);
    } catch { toast.error("Load failed"); }
    setLoading(false);
  }, [propertyId, filter]);

  useEffect(() => { load(); }, [load]);

  const add = async () => {
    if (!form.room_number) return toast.error("Room # required");
    try {
      await axios.post(`${API}/door-locks/log`, { property_id: propertyId, ...form });
      toast.success("Logged"); setAdding(false);
      setForm({ ...form, room_number: "" });
      load();
    } catch { toast.error("Log failed"); }
  };

  return (
    <div className="space-y-3" data-testid="door-lock-tab">
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <Stat label="Events" value={data.items.length} />
        <Stat label="Denied" value={data.denied_count} highlight={data.denied_count > 0} />
        <Stat label="Master key uses" value={data.master_key_uses} />
      </div>

      <div className="flex flex-wrap gap-2">
        <select value={filter.days} onChange={(e) => setFilter({ ...filter, days: parseInt(e.target.value, 10) })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-xs">
          {[1, 7, 14, 30].map((d) => <option key={d} value={d}>{`${d}d`}</option>)}
        </select>
        <input data-testid="lock-filter-room" placeholder="Room #" value={filter.room} onChange={(e) => setFilter({ ...filter, room: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-xs w-24" />
        <select value={filter.method} onChange={(e) => setFilter({ ...filter, method: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-xs">
          <option value="">All methods</option>
          {["card", "pin", "mobile_key", "master", "maintenance", "failed_attempt"].map((m) => <option key={m} value={m}>{m}</option>)}
        </select>
        <select value={filter.result} onChange={(e) => setFilter({ ...filter, result: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-xs">
          <option value="">All results</option>{["success", "denied", "error"].map((r) => <option key={r} value={r}>{r}</option>)}
        </select>
        <button data-testid="lock-refresh-btn" onClick={load} className="text-xs px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-300 flex items-center gap-1">
          <RefreshCw className="w-3 h-3" /> Refresh
        </button>
        <button data-testid="lock-add-btn" onClick={() => setAdding(true)} className="ml-auto text-xs px-2 py-1 rounded bg-cyan-500/20 border border-cyan-500/40 text-cyan-200 flex items-center gap-1">
          <Plus className="w-3 h-3" /> Manual entry
        </button>
      </div>

      {adding && (
        <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-3 grid grid-cols-2 md:grid-cols-5 gap-2 text-xs">
          <input placeholder="Room #" value={form.room_number} onChange={(e) => setForm({ ...form, room_number: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" />
          <select value={form.method} onChange={(e) => setForm({ ...form, method: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100">
            {["card", "pin", "mobile_key", "master", "maintenance", "failed_attempt"].map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
          <select value={form.actor_role} onChange={(e) => setForm({ ...form, actor_role: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100">
            {["guest", "staff", "maintenance", "unknown"].map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
          <input placeholder="Actor name" value={form.actor_name} onChange={(e) => setForm({ ...form, actor_name: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" />
          <select value={form.result} onChange={(e) => setForm({ ...form, result: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100">
            {["success", "denied", "error"].map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
          <button data-testid="lock-add-save" onClick={add} className="col-span-2 md:col-span-5 px-2 py-1 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 text-xs">Save event</button>
        </div>
      )}

      {loading ? <Loader2 className="w-5 h-5 animate-spin text-stone-500" /> : (
        <div className="rounded-xl border border-stone-800 bg-stone-900/60 overflow-x-auto">
          <table className="min-w-full text-xs">
            <thead className="text-left text-[10px] uppercase tracking-wider text-stone-500 border-b border-stone-800">
              <tr><th className="px-2 py-2">When</th><th className="px-2 py-2">Room</th><th className="px-2 py-2">Method</th><th className="px-2 py-2">Actor</th><th className="px-2 py-2">Result</th></tr>
            </thead>
            <tbody>
              {data.items.map((e) => (
                <tr key={e.id} className={`border-t border-stone-800/60 ${e.result === "denied" ? "bg-rose-500/5" : ""}`} data-testid="lock-event-row">
                  <td className="px-2 py-1 text-stone-400">{new Date(e.logged_at).toLocaleString().slice(0, 17)}</td>
                  <td className="px-2 py-1 text-stone-100">{e.room_number}</td>
                  <td className="px-2 py-1 text-stone-300">{e.method}</td>
                  <td className="px-2 py-1 text-stone-300">{e.actor_name || e.actor_role}</td>
                  <td className={`px-2 py-1 ${e.result === "success" ? "text-emerald-300" : e.result === "denied" ? "text-rose-300" : "text-amber-300"}`}>
                    {e.result === "denied" && <AlertTriangle className="w-3 h-3 inline mr-1" />}{e.result}
                  </td>
                </tr>
              ))}
              {data.items.length === 0 && <tr><td colSpan={5} className="px-2 py-4 text-center text-stone-500">No events.</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function OwnerTab() {
  const [ownerId, setOwnerId] = useState("");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const fetchSummary = async () => {
    if (!ownerId) return toast.error("Owner ID required");
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/owner-portal/${ownerId}/summary?days=30`);
      setData(data);
    } catch { toast.error("Load failed"); }
    setLoading(false);
  };
  return (
    <div className="space-y-3" data-testid="owner-tab">
      <div className="flex gap-2 flex-wrap">
        <input data-testid="owner-id-input" value={ownerId} onChange={(e) => setOwnerId(e.target.value)} placeholder="Owner ID"
          className="flex-1 min-w-[200px] px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm" />
        <button data-testid="owner-load-btn" onClick={fetchSummary}
          className="flex items-center gap-2 px-3 py-2 rounded bg-cyan-500/20 border border-cyan-500/40 text-cyan-200 text-sm">
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Building className="w-4 h-4" />} Load summary
        </button>
      </div>
      {data && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <Stat label="Properties" value={data.properties.length} />
            <Stat label="Bookings" value={data.totals.bookings} />
            <Stat label="Gross revenue" value={fmt(data.totals.gross)} />
            <Stat label="Mgmt fees" value={fmt(data.totals.fees_deducted)} />
            <Stat label="Net payout" value={fmt(data.totals.net_payout)} highlight />
          </div>
          <div className="rounded-xl border border-stone-800 bg-stone-900/60 overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="text-left text-[10px] uppercase tracking-wider text-stone-500 border-b border-stone-800">
                <tr>
                  <th className="px-3 py-2">Property</th><th className="px-3 py-2 text-right">Bookings</th>
                  <th className="px-3 py-2 text-right">Gross</th><th className="px-3 py-2 text-right">Mgmt%</th>
                  <th className="px-3 py-2 text-right">Net payout</th>
                </tr>
              </thead>
              <tbody>
                {data.properties.map((p) => (
                  <tr key={p.property_id} className="border-t border-stone-800/60 text-stone-200" data-testid="owner-prop-row">
                    <td className="px-3 py-2">{p.name}</td>
                    <td className="px-3 py-2 text-right">{p.bookings}</td>
                    <td className="px-3 py-2 text-right">{fmt(p.gross)}</td>
                    <td className="px-3 py-2 text-right text-stone-400 text-xs">{p.management_fee_pct}%</td>
                    <td className="px-3 py-2 text-right text-emerald-300">{fmt(p.net_payout)}</td>
                  </tr>
                ))}
                {data.properties.length === 0 && <tr><td colSpan={5} className="px-3 py-3 text-center text-stone-500">No properties linked to this owner.</td></tr>}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

function Stat({ label, value, highlight = false }) {
  return (
    <div className={`p-3 rounded-lg border ${highlight ? "bg-emerald-500/10 border-emerald-500/40" : "bg-stone-800/60 border-stone-800"}`}>
      <div className="text-[10px] uppercase tracking-wider text-stone-400 mb-1">{label}</div>
      <div className={`text-lg font-semibold ${highlight ? "text-emerald-200" : "text-stone-100"}`}>{value}</div>
    </div>
  );
}
