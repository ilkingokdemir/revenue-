import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const COLORS = { queued: "bg-amber-100 text-amber-800", running: "bg-sky-100 text-sky-800", done: "bg-emerald-100 text-emerald-800",
  failed: "bg-red-100 text-red-700", failed_soft: "bg-orange-100 text-orange-800" };

export default function JobQueueCard() {
  const [q, setQ] = useState(null);
  const [filter, setFilter] = useState("");
  const load = useCallback(async () => {
    try { const r = await axios.get(`${API}/scheduler/queue`, { params: { limit: 25, status: filter } }); setQ(r.data); } catch { setQ(null); }
  }, [filter]);
  useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t); }, [load]);
  const retry = async (id) => {
    try { await axios.post(`${API}/scheduler/queue/${id}/retry`); toast.success("Yeniden kuyruğa alındı"); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Yeniden denenemedi"); }
  };
  if (!q) return null;
  const c = q.counts || {};
  return (
    <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="job-queue-card">
      <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
        <h2 className="font-semibold text-stone-900">🧵 İş Kuyruğu <span className="text-[11px] text-stone-400 font-normal">eşzamanlı {q.concurrency} · 3 deneme / 30-120-600 sn</span></h2>
        <div className="flex gap-1.5" data-testid="queue-counters">
          {["queued", "running", "done", "failed_soft", "failed"].map(s => (
            <button key={s} onClick={() => setFilter(filter === s ? "" : s)} data-testid={`queue-count-${s}`}
              className={`text-[11px] px-2 py-0.5 rounded-full ${COLORS[s]} ${filter === s ? "ring-2 ring-stone-900" : ""}`}>{s} <b>{c[s] || 0}</b></button>
          ))}
        </div>
      </div>
      <div className="divide-y divide-stone-100 max-h-72 overflow-y-auto">
        {q.items.length === 0 && <p className="text-xs text-stone-400 py-2">Kuyruk boş.</p>}
        {q.items.map(it => (
          <div key={it.id} className="py-1.5 flex items-center justify-between gap-2 text-xs" data-testid={`queue-item-${it.id}`}>
            <div className="min-w-0">
              <span className="font-medium text-stone-800">{it.job}</span> <span className="text-stone-400">· {it.property_id || "all"} · {it.source}</span>
              <div className="text-[10px] text-stone-400 truncate">{it.attempts}/{it.max_attempts} deneme{it.duration_sec != null ? ` · ${it.duration_sec}s` : ""}{it.last_error ? ` · ${it.last_error}` : ""}</div>
            </div>
            <div className="flex items-center gap-1.5 shrink-0">
              <span className={`px-2 py-0.5 rounded-full text-[10px] ${COLORS[it.status] || "bg-stone-100"}`}>{it.status}</span>
              {["failed", "failed_soft", "done"].includes(it.status) && (
                <button onClick={() => retry(it.id)} data-testid={`queue-retry-${it.id}`} className="text-[10px] px-2 py-0.5 rounded bg-stone-800 text-white">Yeniden dene</button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
