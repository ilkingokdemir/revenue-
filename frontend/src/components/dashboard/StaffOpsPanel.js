/**
 * Staff Operations Panel — Clock-In/Out + Tip Pool
 * ------------------------------------------------
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, Clock, RefreshCw, LogIn, LogOut, Coins, PieChart } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const fmt = (n) => `£${Number(n || 0).toFixed(2)}`;

export default function StaffOpsPanel({ propertyId, hotelName = "" }) {
  const today = new Date().toISOString().slice(0, 10);
  const [tab, setTab] = useState("clock");
  const [active, setActive] = useState([]);
  const [shifts, setShifts] = useState([]);
  const [summary, setSummary] = useState(null);
  const [name, setName] = useState("");
  const [role, setRole] = useState("server");
  const [tipAmount, setTipAmount] = useState(0);
  const [tipSource, setTipSource] = useState("card");

  const load = useCallback(async () => {
    if (!propertyId) return;
    const [a, sh, su] = await Promise.all([
      axios.get(`${API}/staff/${propertyId}/active`),
      axios.get(`${API}/staff/${propertyId}/shifts?days=7`),
      axios.get(`${API}/tip-pool/${propertyId}/summary?shift_date=${today}`),
    ]);
    setActive(a.data || []); setShifts(sh.data || []); setSummary(su.data);
  }, [propertyId, today]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setActive([]); setShifts([]); setSummary(null); }, [propertyId]);

  const clockIn = async () => {
    if (!name) return toast.error("Name required");
    await axios.post(`${API}/staff/clock-in`, { property_id: propertyId, staff_name: name, role });
    toast.success(`${name} clocked in`); setName(""); load();
  };
  const clockOut = async (id) => {
    await axios.post(`${API}/staff/clock-out/${id}`);
    toast.success("Clocked out"); load();
  };
  const addTip = async () => {
    if (tipAmount <= 0) return toast.error("Amount > 0");
    await axios.post(`${API}/tip-pool/${propertyId}/contribute`, { amount: tipAmount, source: tipSource, shift_date: today });
    toast.success(`${fmt(tipAmount)} added to pool`); setTipAmount(0); load();
  };
  const distribute = async () => {
    if (!window.confirm(`Distribute today's tip pool (${fmt(summary?.pending_pool_total || 0)})?`)) return;
    try {
      const { data } = await axios.post(`${API}/tip-pool/${propertyId}/distribute`, { shift_date: today });
      if (data.ok) toast.success(`Distributed across ${data.distribution.allocations.length} staff`);
      else toast.warning(data.reason);
      load();
    } catch { toast.error("Distribute failed"); }
  };

  return (
    <div className="space-y-6" data-testid="staff-ops-panel">
      <div>
        <h2 className="text-2xl font-semibold text-stone-100">Staff Operations</h2>
        <p className="text-sm text-stone-400 mt-1">{hotelName ? `${hotelName} · ` : ""}Clock-in, shift tracking, tip-pool distribution.</p>
      </div>
      <div className="flex gap-2">
        <Tab active={tab === "clock"} onClick={() => setTab("clock")} icon={Clock} testId="staff-tab-clock">Clock-in / Shifts</Tab>
        <Tab active={tab === "tips"} onClick={() => setTab("tips")} icon={Coins} testId="staff-tab-tips">Tip Pool</Tab>
        <button data-testid="staff-refresh" onClick={load} className="ml-auto flex items-center gap-1 px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-300 text-sm">
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      {tab === "clock" && (
        <div className="space-y-4">
          <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4 flex flex-wrap gap-2">
            <input data-testid="staff-clockin-name" placeholder="Staff name" value={name} onChange={(e) => setName(e.target.value)}
              className="flex-1 min-w-[160px] px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm" />
            <select value={role} onChange={(e) => setRole(e.target.value)} className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm">
              {["server", "bartender", "host", "busser", "runner", "kitchen", "manager", "other"].map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
            <button data-testid="staff-clockin-btn" onClick={clockIn}
              className="flex items-center gap-2 px-3 py-2 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 text-sm">
              <LogIn className="w-4 h-4" /> Clock in
            </button>
          </div>

          <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4">
            <div className="text-stone-100 font-semibold mb-2">Currently clocked-in ({active.length})</div>
            {active.length === 0 ? <div className="text-sm text-stone-500">Nobody on shift.</div> : (
              <div className="space-y-1">
                {active.map((e) => (
                  <div key={e.id} data-testid="staff-active-row" className="flex items-center justify-between bg-stone-800/40 rounded px-2 py-1 text-sm">
                    <div>
                      <span className="text-stone-100">{e.staff_name}</span>
                      <span className="text-xs text-stone-500 ml-2">{e.role} · since {new Date(e.clock_in).toLocaleTimeString().slice(0, 5)}</span>
                    </div>
                    <button data-testid="staff-clockout-btn" onClick={() => clockOut(e.id)}
                      className="flex items-center gap-1 text-xs px-2 py-1 rounded bg-stone-800 hover:bg-rose-500/20 text-stone-200 border border-stone-700">
                      <LogOut className="w-3 h-3" /> Clock out
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4">
            <div className="text-stone-100 font-semibold mb-2">Recent shifts (7d)</div>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="text-left text-[10px] uppercase tracking-wider text-stone-500 border-b border-stone-800">
                  <tr><th className="px-2 py-1">Staff</th><th className="px-2 py-1">Role</th><th className="px-2 py-1">In</th><th className="px-2 py-1">Out</th><th className="px-2 py-1 text-right">Hours</th></tr>
                </thead>
                <tbody>
                  {shifts.map((s) => (
                    <tr key={s.id} className="border-t border-stone-800/60 text-stone-200">
                      <td className="px-2 py-1">{s.staff_name}</td>
                      <td className="px-2 py-1 text-stone-400 text-xs">{s.role}</td>
                      <td className="px-2 py-1 text-xs text-stone-400">{new Date(s.clock_in).toLocaleString().slice(0, 17)}</td>
                      <td className="px-2 py-1 text-xs text-stone-400">{s.clock_out ? new Date(s.clock_out).toLocaleString().slice(0, 17) : "—"}</td>
                      <td className="px-2 py-1 text-right">{s.duration_min ? (s.duration_min / 60).toFixed(2) : "—"}</td>
                    </tr>
                  ))}
                  {shifts.length === 0 && <tr><td colSpan={5} className="px-2 py-3 text-center text-stone-500">No shifts.</td></tr>}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {tab === "tips" && summary && (
        <div className="space-y-4">
          <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4 grid grid-cols-1 md:grid-cols-3 gap-3">
            <Stat label="Today's pending pool" value={fmt(summary.pending_pool_total)} highlight />
            <Stat label="Contributions" value={summary.pending_contributions.length} />
            <Stat label="Active staff" value={active.length} />
          </div>

          <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4 flex flex-wrap gap-2">
            <input data-testid="staff-tip-amount" type="number" value={tipAmount} onChange={(e) => setTipAmount(parseFloat(e.target.value) || 0)}
              placeholder="Tip £" className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm w-32" />
            <select value={tipSource} onChange={(e) => setTipSource(e.target.value)} className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm">
              {["card", "cash", "service_charge"].map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
            </select>
            <button data-testid="staff-tip-add" onClick={addTip}
              className="flex items-center gap-2 px-3 py-2 rounded bg-amber-500/20 border border-amber-500/40 text-amber-200 text-sm">
              <Coins className="w-4 h-4" /> Add to pool
            </button>
            <button data-testid="staff-tip-distribute" onClick={distribute} disabled={summary.pending_pool_total <= 0}
              className="ml-auto flex items-center gap-2 px-3 py-2 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 text-sm disabled:opacity-50">
              <PieChart className="w-4 h-4" /> Distribute pool
            </button>
          </div>

          {summary.recent_distributions?.length > 0 && (
            <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4">
              <div className="text-stone-100 font-semibold mb-2">Recent distributions</div>
              {summary.recent_distributions.map((d) => (
                <div key={d.id} className="border border-stone-800 rounded p-2 mb-2 bg-stone-800/30">
                  <div className="flex items-center justify-between text-sm mb-1">
                    <span className="text-stone-100 font-medium">{d.shift_date}</span>
                    <span className="text-stone-300">{fmt(d.pool_total)}</span>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-1 text-xs">
                    {d.allocations.map((a) => (
                      <div key={a.staff_name} className="flex items-center justify-between bg-stone-900/60 rounded px-2 py-1">
                        <span className="text-stone-300">{a.staff_name}</span>
                        <span className="text-emerald-300">{fmt(a.share)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Tab({ active, onClick, icon: Icon, testId, children }) {
  return (
    <button onClick={onClick} data-testid={testId}
      className={`px-3 py-2 rounded-lg text-sm border flex items-center gap-2 ${active
        ? "bg-cyan-500/20 border-cyan-500/40 text-cyan-200"
        : "bg-stone-800 border-stone-700 text-stone-300 hover:bg-stone-700"}`}>
      <Icon className="w-4 h-4" />{children}
    </button>
  );
}

function Stat({ label, value, highlight = false }) {
  return (
    <div className={`p-3 rounded-lg border ${highlight ? "bg-amber-500/10 border-amber-500/40" : "bg-stone-800/60 border-stone-800"}`}>
      <div className="text-[10px] uppercase tracking-wider text-stone-400 mb-1">{label}</div>
      <div className={`text-lg font-semibold ${highlight ? "text-amber-200" : "text-stone-100"}`}>{value}</div>
    </div>
  );
}
