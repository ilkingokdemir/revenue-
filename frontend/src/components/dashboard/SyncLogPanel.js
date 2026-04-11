import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { ArrowsClockwise, Info } from "@phosphor-icons/react";
import { API } from "./config";

const SyncLogPanel = () => {
  const [logs, setLogs] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [filterPlatform, setFilterPlatform] = useState("");

  const fetchLogs = useCallback(async () => {
    setIsLoading(true);
    try {
      let url = `${API}/sync-logs?limit=50`;
      if (filterPlatform) url += `&platform=${filterPlatform}`;
      const { data } = await axios.get(url);
      setLogs(data);
    } catch (e) {
      toast.error("Failed to load sync logs");
    } finally {
      setIsLoading(false);
    }
  }, [filterPlatform]);

  useEffect(() => { fetchLogs(); }, [fetchLogs]);

  return (
    <div className="p-5" data-testid="sync-log-panel">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-lg font-semibold text-stone-800" data-testid="sync-log-title">Sync Log</h2>
          <p className="text-sm text-stone-500 mt-0.5">Real-time activity log of review syncing across platforms</p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={filterPlatform}
            onChange={(e) => setFilterPlatform(e.target.value)}
            className="text-xs border border-stone-200 rounded-lg px-2 py-1.5 bg-white text-stone-700"
            data-testid="sync-filter-platform"
          >
            <option value="">All Platforms</option>
            {["google","booking.com","tripadvisor","airbnb","expedia","trip.com","agoda","hotels.com","yelp","facebook","makemytrip","hrs","despegar","hostelworld","booking-engine"].map(p => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
          <button onClick={fetchLogs} className="p-1.5 text-stone-400 hover:text-stone-600" data-testid="refresh-sync-logs">
            <ArrowsClockwise size={14} className={isLoading ? "animate-spin" : ""} />
          </button>
        </div>
      </div>

      {/* Inbound Webhook Info */}
      <div className="bg-stone-50 border border-stone-200 rounded-lg p-4 mb-4">
        <div className="flex items-center gap-2 mb-2">
          <Info size={16} className="text-stone-500" />
          <h3 className="text-sm font-medium text-stone-700">How Platform Sync Works</h3>
        </div>
        <div className="text-xs text-stone-600 space-y-1">
          <p>Platforms push reviews to your unique inbound webhook URL. Each platform gets its own endpoint and secret for verification.</p>
          <p>Go to <span className="font-medium text-emerald-700">Integrations</span> &rarr; select a platform &rarr; <span className="font-medium text-emerald-700">Setup Guide</span> to get your inbound URL.</p>
        </div>
      </div>

      {/* Log Entries */}
      {isLoading ? (
        <div className="flex justify-center py-12"><ArrowsClockwise size={24} className="animate-spin text-stone-400" /></div>
      ) : logs.length === 0 ? (
        <div className="text-center py-12 bg-white border border-stone-200 rounded-lg" data-testid="no-sync-logs">
          <ArrowsClockwise size={32} className="mx-auto text-stone-300 mb-3" />
          <p className="text-sm text-stone-500">No sync activity yet</p>
          <p className="text-xs text-stone-400 mt-1">Activity will appear here when platforms push reviews</p>
        </div>
      ) : (
        <div className="space-y-1.5" data-testid="sync-logs-list">
          {logs.map((log) => (
            <div key={log.id} className="bg-white border border-stone-200 rounded-lg px-4 py-3 flex items-center gap-3" data-testid={`sync-log-${log.id}`}>
              <div className={`w-2 h-2 rounded-full flex-shrink-0 ${log.status === "success" ? "bg-emerald-500" : log.status === "skipped" ? "bg-amber-400" : "bg-red-500"}`} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium text-stone-700 capitalize">{log.platform}</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${log.direction === "inbound" ? "bg-blue-50 text-blue-700" : "bg-purple-50 text-purple-700"}`}>
                    {log.direction}
                  </span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${log.status === "success" ? "bg-emerald-50 text-emerald-700" : log.status === "skipped" ? "bg-amber-50 text-amber-700" : "bg-red-50 text-red-700"}`}>
                    {log.status}
                  </span>
                </div>
                {log.message && <p className="text-[10px] text-stone-500 mt-0.5">{log.message}</p>}
              </div>
              <span className="text-[10px] text-stone-400 flex-shrink-0">{new Date(log.timestamp).toLocaleString()}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export { SyncLogPanel };
