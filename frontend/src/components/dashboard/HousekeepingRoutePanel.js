/**
 * Housekeeping Route Optimizer — daily cleaning round in priority + proximity
 * order. Calls /api/housekeeping/route/{property_id} which returns a sorted
 * list of rooms with kind (checkout/arrival_ready/stayover), score, tags
 * (vip/checkout/arrival/in-progress/dirty), and a cumulative ETA.
 *
 * Lets housekeepers see the optimal order and click each row to flip status.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Loader2, Route, RefreshCw, Crown, ArrowDownToLine, ArrowUpToLine, Clock,
  CheckCircle2, AlertCircle, Bed,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const KIND_META = {
  checkout:        { color: "bg-amber-500/15 border-amber-500/40 text-amber-300",     icon: ArrowUpToLine,   label: "Checkout" },
  arrival_ready:   { color: "bg-cyan-500/15 border-cyan-500/40 text-cyan-300",        icon: ArrowDownToLine, label: "Arrival" },
  stayover:        { color: "bg-stone-700/40 border-stone-600 text-stone-300",        icon: Bed,             label: "Stayover" },
};

const STATUS_COLOR = {
  clean:        "text-emerald-400",
  inspected:    "text-emerald-400",
  in_progress:  "text-amber-400",
  dirty:        "text-rose-400",
  out_of_order: "text-stone-500",
};

const fmtMins = (m) => {
  const h = Math.floor(m / 60), mm = m % 60;
  return h > 0 ? `${h}h ${mm}m` : `${mm}m`;
};

export default function HousekeepingRoutePanel({ propertyId, hotelName = "" }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [completing, setCompleting] = useState(null);

  const load = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/housekeeping/route/${propertyId}`);
      setData(data);
    } catch { toast.error("Failed to load route"); }
    setLoading(false);
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setData(null); }, [propertyId]);

  const markClean = async (r) => {
    if (!r.room_id) return;
    setCompleting(r.room_id);
    try {
      await axios.put(`${API}/housekeeping/rooms/${r.room_id}/status`, { status: "clean" });
      toast.success(`Room ${r.room_number} cleaned`);
      load();
    } catch { toast.error("Update failed"); }
    setCompleting(null);
  };

  const rounds = data?.rounds || [];

  return (
    <div className="p-5 space-y-5" data-testid="housekeeping-route-panel">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-stone-100 flex items-center gap-2">
            <Route className="w-5 h-5 text-cyan-400" />Housekeeping Route Optimizer
            {hotelName && <><span className="text-stone-500 mx-1">·</span><span className="text-violet-400">{hotelName}</span></>}
          </h2>
          <p className="text-xs text-stone-400">Today's cleaning round in priority + proximity order</p>
        </div>
        <button onClick={load} disabled={loading} data-testid="hk-route-refresh"
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-stone-800 hover:bg-stone-700 text-white text-xs font-bold">
          {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}Refresh
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3" data-testid="hk-route-stats">
        <Stat label="Rooms in round"     value={data?.total_rooms ?? 0}        color="text-stone-200" />
        <Stat label="Checkouts"          value={data?.checkouts ?? 0}          color="text-amber-300" />
        <Stat label="Arrivals"           value={data?.arrivals ?? 0}           color="text-cyan-300" />
        <Stat label="VIP rooms"          value={data?.vip_count ?? 0}          color="text-violet-300" />
        <Stat label="Total ETA"          value={fmtMins(data?.total_estimated_minutes || 0)} color="text-emerald-300" />
      </div>

      {/* Round list */}
      {rounds.length > 0 ? (
        <div className="bg-stone-900/60 border border-stone-800 rounded-2xl overflow-hidden" data-testid="hk-route-list">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-stone-400 border-b border-stone-800 bg-stone-900/80 sticky top-0">
                <th className="text-center py-2 px-2 w-12">#</th>
                <th className="text-left py-2 px-2">Room</th>
                <th className="text-left py-2 px-2">Type</th>
                <th className="text-center py-2 px-2">Kind</th>
                <th className="text-left py-2 px-2">Tags</th>
                <th className="text-left py-2 px-2">Guest</th>
                <th className="text-center py-2 px-2">Status</th>
                <th className="text-right py-2 px-2">ETA</th>
                <th className="text-right py-2 px-2">Action</th>
              </tr>
            </thead>
            <tbody>
              {rounds.map(r => {
                const meta = KIND_META[r.kind] || KIND_META.stayover;
                const isVip = r.tags?.includes("vip");
                return (
                  <tr key={r.room_id} className={`border-b border-stone-800/50 ${isVip ? "bg-violet-500/5" : "hover:bg-stone-800/30"}`} data-testid={`hk-route-row-${r.room_number}`}>
                    <td className="text-center py-2 px-2 font-mono text-stone-500 tabular-nums">{r.position}</td>
                    <td className="py-2 px-2">
                      <div className="font-bold text-stone-100">{r.room_number}</div>
                      <div className="text-[10px] text-stone-500">Floor {r.floor || "—"}</div>
                    </td>
                    <td className="py-2 px-2 text-stone-400">{r.room_type || "—"}</td>
                    <td className="py-2 px-2 text-center">
                      <span className={`inline-flex items-center gap-1 text-[10px] uppercase font-black tracking-widest px-1.5 py-0.5 rounded border ${meta.color}`}>
                        <meta.icon className="w-3 h-3" />{meta.label}
                      </span>
                    </td>
                    <td className="py-2 px-2">
                      <div className="flex flex-wrap gap-1">
                        {(r.tags || []).map(t => (
                          <span key={t} className={`text-[9px] uppercase font-bold px-1 py-0.5 rounded ${t === "vip" ? "bg-violet-500/20 text-violet-300 border border-violet-500/40" : "bg-stone-700 text-stone-300"}`}>
                            {t === "vip" && <Crown className="w-2.5 h-2.5 inline mr-0.5" />}{t}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="py-2 px-2 text-stone-300 truncate max-w-[140px]">{r.guest_name || "—"}</td>
                    <td className="py-2 px-2 text-center">
                      <span className={`text-[10px] font-bold uppercase tabular-nums ${STATUS_COLOR[r.status] || "text-stone-400"}`}>{r.status || "—"}</span>
                    </td>
                    <td className="py-2 px-2 text-right">
                      <div className="text-stone-300 tabular-nums">{fmtMins(r.eta_minutes_from_start)}</div>
                      <div className="text-[9px] text-stone-500">+{r.estimated_minutes}m</div>
                    </td>
                    <td className="py-2 px-2 text-right">
                      <button onClick={() => markClean(r)} disabled={completing === r.room_id || r.status === "clean"}
                        data-testid={`hk-route-clean-${r.room_number}`}
                        className="flex items-center gap-1 ml-auto px-2 py-1 rounded bg-emerald-600 hover:bg-emerald-700 text-white text-[10px] font-bold disabled:opacity-40 disabled:bg-stone-700">
                        {completing === r.room_id ? <Loader2 className="w-3 h-3 animate-spin" /> : <CheckCircle2 className="w-3 h-3" />}
                        {r.status === "clean" ? "Done" : "Mark clean"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : !loading && (
        <div className="text-center py-16 text-stone-500" data-testid="hk-route-empty">
          <Route className="w-10 h-10 mx-auto mb-3 opacity-40" />
          <p className="text-sm">No cleaning round needed today — all rooms are clean.</p>
          <p className="text-[11px] mt-1">Run room status seed if rooms aren't loaded.</p>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, color }) {
  return (
    <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-3">
      <div className="text-[10px] uppercase tracking-widest text-stone-500 font-bold mb-1">{label}</div>
      <div className={`text-2xl font-black tabular-nums ${color}`}>{value}</div>
    </div>
  );
}
