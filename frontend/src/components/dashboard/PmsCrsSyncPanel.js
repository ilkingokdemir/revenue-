/**
 * PMS-CRS Two-way Sync Panel
 * Status, manual run buttons, and conflict view between PMS bookings and the
 * internal CRS index that mirrors them across the chain.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, RefreshCw, ArrowUpFromLine, ArrowDownToLine, RotateCw, AlertTriangle, Database } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function PmsCrsSyncPanel({ propertyId, hotelName = "" }) {
  const [status, setStatus] = useState(null);
  const [queue, setQueue] = useState([]);
  const [conflicts, setConflicts] = useState({ items: [], count: 0 });
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);

  const refresh = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const [{ data: s }, { data: q }, { data: c }] = await Promise.all([
        axios.get(`${API}/pms-crs/status?property_id=${propertyId}`),
        axios.get(`${API}/pms-crs/queue?property_id=${propertyId}&limit=50`),
        axios.get(`${API}/pms-crs/conflicts?property_id=${propertyId}`),
      ]);
      setStatus(s);
      setQueue(q.items || []);
      setConflicts(c);
    } catch { toast.error("Load failed"); }
    setLoading(false);
  }, [propertyId]);

  useEffect(() => { refresh(); }, [refresh]);

  const run = async (action) => {
    setRunning(true);
    try {
      const url = `${API}/pms-crs/sync/${action}`;
      const { data } = await axios.post(url, { property_id: propertyId });
      if (action === "push") toast.success(`Pushed: ${data.created} new · ${data.updated} updated · ${data.unchanged} unchanged`);
      else if (action === "pull") toast.success(`Pulled: ${data.applied} applied`);
      else toast.success("Bidirectional sync complete");
      refresh();
    } catch { toast.error("Sync failed"); }
    setRunning(false);
  };

  return (
    <div className="space-y-6" data-testid="pms-crs-panel">
      <div>
        <h2 className="text-2xl font-semibold text-stone-100">PMS ↔ CRS Sync</h2>
        <p className="text-sm text-stone-400 mt-1">{hotelName ? `${hotelName} · ` : ""}Internal Central Reservation System mirror — push PMS bookings out, pull CRS edits back, detect drift.</p>
      </div>

      {status && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <Stat label="PMS bookings" value={status.pms_bookings} />
          <Stat label="CRS records" value={status.crs_records} />
          <Stat label="Drift" value={status.drift} highlight={status.drift !== 0} />
          <Stat label="Pending pull" value={status.crs_dirty_pending_pull} highlight={status.crs_dirty_pending_pull > 0} />
          <Stat label="Conflicts" value={conflicts.count} highlight={conflicts.count > 0} />
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <button data-testid="crs-push-btn" onClick={() => run("push")} disabled={running} className="text-sm px-3 py-2 rounded bg-cyan-500/20 border border-cyan-500/40 text-cyan-200 flex items-center gap-2">
          {running ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowUpFromLine className="w-4 h-4" />} Push PMS → CRS
        </button>
        <button data-testid="crs-pull-btn" onClick={() => run("pull")} disabled={running} className="text-sm px-3 py-2 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 flex items-center gap-2">
          {running ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowDownToLine className="w-4 h-4" />} Pull CRS → PMS
        </button>
        <button data-testid="crs-run-btn" onClick={() => run("run")} disabled={running} className="text-sm px-3 py-2 rounded bg-violet-500/20 border border-violet-500/40 text-violet-200 flex items-center gap-2">
          {running ? <Loader2 className="w-4 h-4 animate-spin" /> : <RotateCw className="w-4 h-4" />} Full reconcile
        </button>
        <button onClick={refresh} className="ml-auto text-sm px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-300 flex items-center gap-2">
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />} Refresh
        </button>
      </div>

      {status?.last_run && (
        <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-3 text-xs text-stone-400">
          <span className="text-stone-300">Last run:</span> {(status.last_run.ran_at || "").slice(0, 19)} ·
          direction <span className="text-stone-200">{status.last_run.direction}</span> ·
          scanned {status.last_run.scanned} ·
          {status.last_run.created !== undefined && <> created {status.last_run.created} · updated {status.last_run.updated} ·</>}
          {status.last_run.applied !== undefined && <> applied {status.last_run.applied} ·</>}
          by {status.last_run.ran_by}
        </div>
      )}

      <div className="grid lg:grid-cols-2 gap-4">
        <div className="rounded-xl border border-stone-800 bg-stone-900/60">
          <div className="px-4 py-2 border-b border-stone-800 text-xs uppercase tracking-wider text-stone-400 flex items-center gap-2">
            <Database className="w-3 h-3" /> Sync queue (latest 50)
          </div>
          <table className="min-w-full text-xs">
            <thead className="text-left text-[10px] uppercase tracking-wider text-stone-500 border-b border-stone-800">
              <tr><th className="px-3 py-2">Time</th><th className="px-3 py-2">Direction</th><th className="px-3 py-2">Op</th><th className="px-3 py-2">Booking</th></tr>
            </thead>
            <tbody>
              {queue.map((q) => (
                <tr key={q.id} className="border-t border-stone-800/60 text-stone-300" data-testid="crs-queue-row">
                  <td className="px-3 py-1 text-stone-400">{(q.queued_at || "").slice(0, 19)}</td>
                  <td className="px-3 py-1">{q.direction}</td>
                  <td className="px-3 py-1">{q.op}</td>
                  <td className="px-3 py-1 font-mono text-[10px]">{q.booking_id?.slice(0, 8)}</td>
                </tr>
              ))}
              {queue.length === 0 && <tr><td colSpan={4} className="px-3 py-6 text-center text-stone-500">Queue empty.</td></tr>}
            </tbody>
          </table>
        </div>

        <div className="rounded-xl border border-stone-800 bg-stone-900/60">
          <div className="px-4 py-2 border-b border-stone-800 text-xs uppercase tracking-wider text-stone-400 flex items-center gap-2">
            <AlertTriangle className="w-3 h-3" /> Conflicts ({conflicts.count})
          </div>
          <table className="min-w-full text-xs">
            <thead className="text-left text-[10px] uppercase tracking-wider text-stone-500 border-b border-stone-800">
              <tr><th className="px-3 py-2">Booking</th><th className="px-3 py-2">Kind</th><th className="px-3 py-2">PMS</th><th className="px-3 py-2">CRS</th></tr>
            </thead>
            <tbody>
              {conflicts.items.map((c, i) => (
                <tr key={i} className="border-t border-stone-800/60 text-stone-300" data-testid="crs-conflict-row">
                  <td className="px-3 py-1 font-mono text-[10px]">{c.booking_id?.slice(0, 8)}</td>
                  <td className="px-3 py-1 text-amber-300">{c.kind}</td>
                  <td className="px-3 py-1">{c.pms_status || "-"} {c.pms_total !== undefined ? `· ${c.pms_total}` : ""}</td>
                  <td className="px-3 py-1">{c.crs_status || "-"} {c.crs_total !== undefined ? `· ${c.crs_total}` : ""}</td>
                </tr>
              ))}
              {conflicts.items.length === 0 && <tr><td colSpan={4} className="px-3 py-6 text-center text-stone-500">No conflicts — fully reconciled.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
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
