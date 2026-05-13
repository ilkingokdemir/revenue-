import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { CloudArrowUp, Gear, ArrowClockwise, CheckCircle, XCircle, Warning } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/channels/v2`;

export default function ChannelManagerV2Panel() {
  const [adapters, setAdapters] = useState([]);
  const [queue, setQueue] = useState([]);
  const [history, setHistory] = useState([]);
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState("adapters");

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const [a, q, h, hl] = await Promise.all([
        axios.get(`${API}/adapters`, { withCredentials: true }),
        axios.get(`${API}/queue?limit=50`, { withCredentials: true }),
        axios.get(`${API}/history?limit=50`, { withCredentials: true }),
        axios.get(`${API}/health`, { withCredentials: true }),
      ]);
      setAdapters(a.data.adapters || []);
      setQueue(q.data.jobs || []);
      setHistory(h.data.history || []);
      setHealth(hl.data);
    } catch (e) { toast.error("Yüklenemedi"); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { reload(); }, [reload]);
  useEffect(() => { const t = setInterval(reload, 5000); return () => clearInterval(t); }, [reload]);

  async function testPush(adapter) {
    try {
      await axios.post(`${API}/queue/push`, {
        adapter,
        job_type: "rate_push",
        property_id: "default",
        payload: { date: new Date().toISOString().slice(0, 10), rate: 150, test: true },
      }, { withCredentials: true });
      toast.success("Test sync kuyruğa eklendi");
      reload();
    } catch { toast.error("Push edilemedi"); }
  }

  async function retry(jobId) {
    try {
      await axios.post(`${API}/queue/${jobId}/retry`, {}, { withCredentials: true });
      toast.success("Retry kuyruğa eklendi");
      reload();
    } catch { toast.error("Retry başarısız"); }
  }

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="channels-v2-panel">
      <div className="mb-5">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          <CloudArrowUp size={12} weight="fill" className="text-cyan-500" />
          <span>Distribution</span>
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">Channel Manager v2</h1>
        <p className="text-sm text-stone-500 mt-1 max-w-2xl">
          Production-ready OTA sync engine — Booking, Expedia, Airbnb, Agoda, Hotels.com, Google. Retry, backoff, audit trail.
        </p>
        {health && (
          <div className="mt-3 inline-flex gap-3 text-xs">
            <span className="px-2 py-1 bg-stone-50 border border-stone-200 rounded">
              Kuyrukta: <strong>{health.queue?.pending || 0}</strong>
            </span>
            <span className="px-2 py-1 bg-rose-50 border border-rose-200 text-rose-700 rounded">
              Başarısız: <strong>{health.queue?.failed || 0}</strong>
            </span>
          </div>
        )}
      </div>

      <div className="flex gap-1 mb-4 border-b border-stone-200">
        {[
          ["adapters", "OTA Adapterları"],
          ["queue", `Kuyruk (${queue.length})`],
          ["history", "Geçmiş"],
        ].map(([k, label]) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            data-testid={`channels-tab-${k}`}
            className={`px-3 py-2 text-xs font-medium border-b-2 -mb-px ${
              tab === k ? "border-stone-900 text-stone-900" : "border-transparent text-stone-500 hover:text-stone-800"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "adapters" && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {adapters.map(a => (
            <div key={a.adapter} className="bg-white border border-stone-200 rounded-xl p-4" data-testid={`adapter-${a.adapter}`}>
              <div className="flex items-start justify-between mb-2">
                <div>
                  <h3 className="text-sm font-semibold text-stone-900">{a.name}</h3>
                  <div className="text-[10px] text-stone-400 font-mono mt-0.5">{a.protocol} · {a.rate_limit_per_min}/dk</div>
                </div>
                {a.configured ? (
                  <span className="text-[10px] px-1.5 py-0.5 bg-emerald-50 text-emerald-700 rounded">Bağlı</span>
                ) : (
                  <span className="text-[10px] px-1.5 py-0.5 bg-stone-100 text-stone-500 rounded">Yapılandırılmadı</span>
                )}
              </div>
              <div className="mt-3 pt-3 border-t border-stone-100">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-stone-500">7 gün başarı oranı</span>
                  <span className="font-semibold text-stone-900">
                    {(a.health_7d.success_rate * 100).toFixed(0)}% ({a.health_7d.total_attempts})
                  </span>
                </div>
                <div className="mt-1 h-1.5 bg-stone-100 rounded overflow-hidden">
                  <div className="h-full bg-emerald-500" style={{ width: `${a.health_7d.success_rate * 100}%` }} />
                </div>
              </div>
              <button onClick={() => testPush(a.adapter)} className="mt-3 w-full text-xs px-3 py-1.5 bg-stone-900 text-white rounded hover:bg-stone-800" data-testid={`adapter-test-${a.adapter}`}>
                Test Sync Gönder
              </button>
            </div>
          ))}
        </div>
      )}

      {tab === "queue" && (
        <div className="bg-white border border-stone-200 rounded-xl divide-y divide-stone-100">
          {queue.length === 0 ? (
            <div className="p-8 text-center text-stone-400 text-sm">Kuyruk boş.</div>
          ) : queue.map(j => (
            <div key={j.id} className="p-3 flex items-center gap-3 text-xs" data-testid={`queue-job-${j.id}`}>
              <span className={`px-1.5 py-0.5 rounded text-[10px] font-mono ${
                j.status === "completed" ? "bg-emerald-50 text-emerald-700" :
                j.status === "failed" ? "bg-rose-50 text-rose-700" :
                j.status === "in-flight" ? "bg-blue-50 text-blue-700" :
                "bg-amber-50 text-amber-700"
              }`}>{j.status}</span>
              <span className="font-mono text-stone-500">{j.adapter}</span>
              <span className="text-stone-700">{j.job_type}</span>
              <span className="flex-1 text-stone-400 text-[10px]">attempts: {j.attempt_count}</span>
              {j.last_error && <span className="text-rose-500 text-[10px] max-w-xs truncate">{j.last_error}</span>}
              {(j.status === "failed" || j.status === "pending") && (
                <button onClick={() => retry(j.id)} className="text-stone-500 hover:text-stone-900" data-testid={`queue-retry-${j.id}`}>
                  <ArrowClockwise size={14} />
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {tab === "history" && (
        <div className="bg-white border border-stone-200 rounded-xl divide-y divide-stone-100">
          {history.length === 0 ? (
            <div className="p-8 text-center text-stone-400 text-sm">Henüz geçmiş yok.</div>
          ) : history.map(h => (
            <div key={h.id} className="p-3 flex items-center gap-3 text-xs">
              {h.ok ? <CheckCircle size={14} className="text-emerald-500 shrink-0" /> : <XCircle size={14} className="text-rose-500 shrink-0" />}
              <span className="font-mono text-[10px] text-stone-400">{new Date(h.created_at).toLocaleString("tr-TR")}</span>
              <span className="px-1.5 py-0.5 bg-stone-100 rounded font-mono text-[10px]">{h.adapter}</span>
              <span className="text-stone-700">{h.job_type}</span>
              {h.ota_ref && <span className="font-mono text-[10px] text-emerald-600">{h.ota_ref}</span>}
              {h.error && <span className="text-rose-500">{h.error}: {h.detail}</span>}
            </div>
          ))}
        </div>
      )}

      {loading && <div className="mt-4 text-center text-stone-400 text-xs">Güncelleniyor…</div>}
    </div>
  );
}
