/**
 * AgentsPanel — Mews-style Agentic AI orchestration.
 *
 * Lists pre-seeded agents (Guest Recovery, Operations Optimize, Revenue Pulse),
 * allows running one, viewing the run's plan + actions taken, and approving
 * or rejecting proposed actions.
 */
import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Robot, Play, CheckCircle, X, ClockCounterClockwise, Sparkle } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function AgentsPanel() {
  const [agents, setAgents] = useState([]);
  const [runs, setRuns] = useState({}); // agent_id -> list
  const [selectedRun, setSelectedRun] = useState(null);
  const [running, setRunning] = useState({});

  const reload = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/agents`, { withCredentials: true });
      setAgents(r.data.items || []);
    } catch (e) { toast.error("Yüklenemedi"); }
  }, []);

  useEffect(() => { reload(); }, [reload]);

  async function runAgent(id) {
    setRunning({...running, [id]: true });
    try {
      const r = await axios.post(`${API}/agents/${id}/run`, {}, { withCredentials: true });
      toast.success(`Agent çalıştırıldı — ${r.data.actions_taken.length} aksiyon`);
      setSelectedRun(r.data);
      loadRuns(id);
      reload();
    } catch (e) { toast.error("Hata"); }
    finally { setRunning({...running, [id]: false }); }
  }

  async function loadRuns(aid) {
    try {
      const r = await axios.get(`${API}/agents/${aid}/runs`, { withCredentials: true });
      setRuns({...runs, [aid]: r.data.items || []});
    } catch (e) {}
  }

  async function approve(runId) {
    try {
      await axios.post(`${API}/agents/runs/${runId}/approve`, {}, { withCredentials: true });
      toast.success("Onaylandı"); reload();
      if (selectedRun?.id === runId) setSelectedRun({...selectedRun, status: "approved"});
    } catch (e) { toast.error("Hata"); }
  }

  async function reject(runId) {
    const reason = window.prompt("Reddetme nedeni:") || "";
    try {
      await axios.post(`${API}/agents/runs/${runId}/reject`, { reason }, { withCredentials: true });
      toast.success("Reddedildi"); reload();
      if (selectedRun?.id === runId) setSelectedRun({...selectedRun, status: "rejected"});
    } catch (e) { toast.error("Hata"); }
  }

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="agents-panel">
      <div className="mb-5">
        <div className="text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">ReveniQ Agentic AI 2026</div>
        <h2 className="text-2xl font-semibold text-stone-900 inline-flex items-center gap-2">
          <Robot size={22} weight="fill" className="text-indigo-600" /> Otonom AI Agent'lar
        </h2>
        <p className="text-sm text-stone-500 mt-1">
          Departmanlar arası iş akışlarını planlayan, yürüten ve onaylama bekleyen otonom ajanlar.
        </p>
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <div className="space-y-3">
          {agents.map(a => (
            <div key={a.id} data-testid={`agent-${a.id}`}
                 className="bg-white border border-stone-200 rounded-xl p-4">
              <div className="flex items-start justify-between mb-2">
                <div>
                  <h3 className="font-semibold text-stone-900 inline-flex items-center gap-1.5">
                    <Sparkle size={14} className="text-indigo-600" /> {a.name}
                  </h3>
                  <div className="text-[10px] uppercase tracking-wider text-stone-400 mt-0.5">
                    {a.category} · {a.tools.length} araç · {a.total_runs} çalışma
                  </div>
                </div>
                <span className={`text-[10px] px-2 py-0.5 rounded-full ${a.is_active ? "bg-emerald-100 text-emerald-700" : "bg-stone-100 text-stone-500"}`}>
                  {a.is_active ? "AKTİF" : "PASİF"}
                </span>
              </div>
              <p className="text-xs text-stone-600 leading-relaxed">{a.mission}</p>
              <div className="flex flex-wrap gap-1 mt-2">
                {a.tools.map(t => <span key={t} className="text-[10px] bg-indigo-50 text-indigo-700 px-1.5 py-0.5 rounded font-mono">{t}</span>)}
              </div>
              <div className="flex gap-2 mt-3 pt-3 border-t border-stone-100">
                <button onClick={() => runAgent(a.id)} disabled={running[a.id] || !a.is_active}
                        data-testid={`agent-run-${a.id}`}
                        className="text-xs px-3 py-1.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 inline-flex items-center gap-1.5 disabled:opacity-50">
                  <Play size={11} weight="fill" /> {running[a.id] ? "Çalışıyor…" : "Çalıştır"}
                </button>
                <button onClick={() => loadRuns(a.id)} data-testid={`agent-history-${a.id}`}
                        className="text-xs px-3 py-1.5 bg-stone-100 text-stone-700 rounded-lg inline-flex items-center gap-1.5">
                  <ClockCounterClockwise size={11} /> Geçmiş
                </button>
              </div>
              {(runs[a.id] || []).length > 0 && (
                <div className="mt-3 space-y-1 max-h-32 overflow-y-auto">
                  {runs[a.id].slice(0, 5).map(r => (
                    <button key={r.id} onClick={() => setSelectedRun(r)}
                            className={`w-full text-left text-[11px] px-2 py-1 rounded ${selectedRun?.id===r.id ? "bg-indigo-50" : "hover:bg-stone-50"}`}>
                      <span className={`inline-block w-2 h-2 rounded-full mr-1.5 ${
                        r.status==="approved" ? "bg-emerald-500" :
                        r.status==="rejected" ? "bg-rose-500" :
                        r.status==="pending_approval" ? "bg-amber-500" :
                        "bg-stone-300"
                      }`} />
                      {r.started_at?.slice(0, 19)?.replace("T", " ")} · {r.status}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>

        <div className="bg-white border border-stone-200 rounded-xl p-4 sticky top-4 h-fit max-h-[80vh] overflow-y-auto">
          <h3 className="font-semibold text-sm mb-2">Run Detayı</h3>
          {!selectedRun ? (
            <div className="text-center text-stone-400 text-xs py-8">Bir agent çalıştırın ya da geçmişten seçin.</div>
          ) : (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="text-sm font-semibold">{selectedRun.agent_name}</div>
                <span className={`text-[10px] px-2 py-0.5 rounded-full ${
                  selectedRun.status==="approved" ? "bg-emerald-100 text-emerald-700" :
                  selectedRun.status==="rejected" ? "bg-rose-100 text-rose-700" :
                  selectedRun.status==="pending_approval" ? "bg-amber-100 text-amber-700" :
                  "bg-stone-100 text-stone-700"
                }`} data-testid="run-status">{selectedRun.status}</span>
              </div>
              <div className="text-[10px] text-stone-500">{selectedRun.started_at} · {selectedRun.started_by}</div>

              {selectedRun.results?.executive_summary && (
                <div className="bg-indigo-50 border border-indigo-200 rounded p-3 text-xs text-indigo-900">
                  <div className="font-semibold mb-1">🤖 Yönetici Özeti</div>
                  {selectedRun.results.executive_summary}
                </div>
              )}

              <div>
                <div className="text-[11px] uppercase tracking-wider text-stone-500 mb-1">Aksiyon Adımları ({selectedRun.actions_taken?.length || 0})</div>
                {(selectedRun.actions_taken || []).map((a, i) => (
                  <div key={i} className="text-xs bg-stone-50 border border-stone-200 rounded p-2 mb-1">
                    <div className="font-mono text-indigo-700">{a.tool}</div>
                    {a.found !== undefined && <div className="text-stone-600">Bulgu: {a.found}</div>}
                    {a.drafts && <div className="text-stone-600">{a.drafts.length} özür taslağı</div>}
                    {a.vouchers && <div className="text-stone-600">{a.vouchers.length} voucher önerisi</div>}
                    {a.tickets && <div className="text-stone-600">{a.tickets.length} bakım ticket</div>}
                    {a.promos && <div className="text-stone-600">{a.promos.length} promosyon önerisi</div>}
                    {a.amount !== undefined && <div className="text-stone-600">Tahmini kayıp: £{a.amount}</div>}
                  </div>
                ))}
              </div>

              {selectedRun.status === "pending_approval" && (
                <div className="flex gap-2 pt-3 border-t border-stone-200">
                  <button onClick={() => approve(selectedRun.id)} data-testid="run-approve-btn"
                          className="flex-1 py-1.5 text-xs bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 inline-flex items-center justify-center gap-1.5">
                    <CheckCircle size={12} weight="fill" /> Onayla
                  </button>
                  <button onClick={() => reject(selectedRun.id)} data-testid="run-reject-btn"
                          className="flex-1 py-1.5 text-xs bg-rose-600 text-white rounded-lg hover:bg-rose-700 inline-flex items-center justify-center gap-1.5">
                    <X size={12} weight="bold" /> Reddet
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
