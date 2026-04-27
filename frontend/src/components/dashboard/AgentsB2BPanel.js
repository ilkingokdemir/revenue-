/**
 * Travel Agent / Corporate B2B Portal Panel
 * -----------------------------------------
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, Briefcase, Plus, RefreshCw, Trash2, X, CheckCircle2, FileSpreadsheet } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const fmt = (n) => `£${Number(n || 0).toFixed(2)}`;

export default function AgentsB2BPanel({ propertyId, hotelName = "" }) {
  const [tab, setTab] = useState("agents");
  const [agents, setAgents] = useState([]);
  const [editing, setEditing] = useState(null);
  const [report, setReport] = useState(null);

  const load = useCallback(async () => {
    if (!propertyId) return;
    const { data } = await axios.get(`${API}/agents/${propertyId}`);
    setAgents(data || []);
  }, [propertyId]);

  const loadReport = useCallback(async () => {
    if (!propertyId) return;
    const today = new Date().toISOString().slice(0, 10);
    const from = new Date(Date.now() - 30 * 24 * 3600 * 1000).toISOString().slice(0, 10);
    const { data } = await axios.get(`${API}/agents/${propertyId}/commission-report?from_date=${from}&to_date=${today}`);
    setReport(data);
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (tab === "report") loadReport(); }, [tab, loadReport]);
  useEffect(() => { setAgents([]); setReport(null); }, [propertyId]);

  const remove = async (id) => {
    if (!window.confirm("Deactivate agent?")) return;
    await axios.delete(`${API}/agents/${propertyId}/${id}`); load();
  };

  return (
    <div className="space-y-6" data-testid="b2b-panel">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Briefcase className="w-5 h-5 text-slate-300" />
            <h2 className="text-2xl font-semibold text-stone-100">Travel Agent / Corporate Portal</h2>
          </div>
          <p className="text-sm text-stone-400 mt-1">{hotelName ? `${hotelName} · ` : ""}Negotiated rates, commission tracking, book-on-behalf.</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setTab("agents")} data-testid="b2b-tab-agents"
            className={`px-3 py-2 rounded-lg text-sm border ${tab === "agents" ? "bg-cyan-500/20 border-cyan-500/40 text-cyan-200" : "bg-stone-800 border-stone-700 text-stone-300"}`}>Agents</button>
          <button onClick={() => setTab("report")} data-testid="b2b-tab-report"
            className={`px-3 py-2 rounded-lg text-sm border ${tab === "report" ? "bg-cyan-500/20 border-cyan-500/40 text-cyan-200" : "bg-stone-800 border-stone-700 text-stone-300"}`}>Commission report</button>
        </div>
      </div>

      {tab === "agents" && (
        <>
          <div className="flex justify-end">
            <button data-testid="b2b-new-agent" onClick={() => setEditing({})}
              className="flex items-center gap-2 px-3 py-2 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 text-sm">
              <Plus className="w-4 h-4" /> New agent
            </button>
          </div>
          {agents.length === 0 ? (
            <div className="text-stone-500 text-sm">No agents yet.</div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {agents.map((a) => (
                <div key={a.id} data-testid="b2b-agent-card" className="rounded-xl border border-stone-800 bg-stone-900/60 p-4">
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div>
                      <div className="text-stone-100 font-semibold">{a.name}</div>
                      <div className="text-xs text-stone-500">
                        {a.type} {a.iata && `· IATA ${a.iata}`} · {a.contact_person}
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <button onClick={() => setEditing(a)} className="text-xs px-2 py-0.5 rounded bg-stone-800 text-stone-300 border border-stone-700">Edit</button>
                      <button onClick={() => remove(a.id)} className="p-1 rounded text-stone-500 hover:text-rose-400"><Trash2 className="w-3.5 h-3.5" /></button>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <Mini label="Discount">{a.negotiated_discount_pct}%</Mini>
                    <Mini label="Commission">{a.commission_pct}%</Mini>
                    <Mini label="Credit">{fmt(a.credit_limit)}</Mini>
                    <Mini label="Terms">{a.billing_terms}</Mini>
                  </div>
                  {a.email && <div className="mt-2 text-[11px] text-stone-400">{a.email}{a.phone ? ` · ${a.phone}` : ""}</div>}
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {tab === "report" && (
        report ? (
          <div className="space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <Stat label="Bookings (30d)" value={report.bookings_count} />
              <Stat label="Total revenue" value={fmt(report.total_revenue)} />
              <Stat label="Total commission" value={fmt(report.total_commission)} highlight />
              <Stat label="Active agents" value={report.agents.length} />
            </div>
            <div className="rounded-xl border border-stone-800 bg-stone-900/60 overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="text-left text-[10px] uppercase tracking-wider text-stone-500 border-b border-stone-800">
                  <tr><th className="px-3 py-2">Agent</th><th className="px-3 py-2">IATA</th><th className="px-3 py-2 text-right">Bookings</th><th className="px-3 py-2 text-right">Revenue</th><th className="px-3 py-2 text-right">Commission</th></tr>
                </thead>
                <tbody>
                  {report.agents.map((a) => (
                    <tr key={a.agent_id || a.agent_name} className="border-t border-stone-800/60 text-stone-200" data-testid="b2b-report-row">
                      <td className="px-3 py-2">{a.agent_name}</td>
                      <td className="px-3 py-2 text-xs text-stone-400">{a.agent_iata || "—"}</td>
                      <td className="px-3 py-2 text-right">{a.bookings}</td>
                      <td className="px-3 py-2 text-right">{fmt(a.revenue)}</td>
                      <td className="px-3 py-2 text-right text-emerald-300">{fmt(a.commission)}</td>
                    </tr>
                  ))}
                  {report.agents.length === 0 && <tr><td colSpan={5} className="px-3 py-3 text-center text-stone-500">No agent bookings in this window.</td></tr>}
                </tbody>
              </table>
            </div>
          </div>
        ) : <Loader2 className="w-5 h-5 animate-spin text-stone-500" />
      )}

      {editing !== null && (
        <Editor propertyId={propertyId} agent={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />
      )}
    </div>
  );
}

function Editor({ propertyId, agent, onClose, onSaved }) {
  const [f, setF] = useState({
    id: agent.id,
    name: agent.name || "",
    type: agent.type || "travel_agent",
    iata: agent.iata || "",
    email: agent.email || "",
    phone: agent.phone || "",
    contact_person: agent.contact_person || "",
    negotiated_discount_pct: agent.negotiated_discount_pct || 0,
    commission_pct: agent.commission_pct ?? 10,
    credit_limit: agent.credit_limit || 0,
    billing_terms: agent.billing_terms || "Net 30",
  });
  const [saving, setSaving] = useState(false);
  const save = async () => {
    if (!f.name) return toast.error("Name required");
    setSaving(true);
    try { await axios.post(`${API}/agents/${propertyId}`, f); toast.success("Saved"); onSaved(); }
    catch { toast.error("Save failed"); }
    setSaving(false);
  };
  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-stone-900 border border-stone-800 rounded-xl max-w-lg w-full p-5" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-3">
          <div className="text-stone-100 font-semibold">{f.id ? "Edit agent" : "New agent"}</div>
          <button onClick={onClose} className="p-1 rounded hover:bg-stone-800 text-stone-500"><X className="w-4 h-4" /></button>
        </div>
        <div className="grid grid-cols-2 gap-2 text-sm">
          <input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="Agent / company name" className="col-span-2 px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100" />
          <select value={f.type} onChange={(e) => setF({ ...f, type: e.target.value })} className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100">
            {["travel_agent", "corporate", "wholesaler"].map((t) => <option key={t} value={t}>{t.replaceAll("_", " ")}</option>)}
          </select>
          <input value={f.iata} onChange={(e) => setF({ ...f, iata: e.target.value })} placeholder="IATA #" className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100" />
          <input value={f.contact_person} onChange={(e) => setF({ ...f, contact_person: e.target.value })} placeholder="Contact person" className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100" />
          <input value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} placeholder="Email" className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100" />
          <input value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} placeholder="Phone" className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100" />
          <input type="number" step="0.5" value={f.negotiated_discount_pct} onChange={(e) => setF({ ...f, negotiated_discount_pct: parseFloat(e.target.value) || 0 })} placeholder="Discount %" className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100" />
          <input type="number" step="0.5" value={f.commission_pct} onChange={(e) => setF({ ...f, commission_pct: parseFloat(e.target.value) || 0 })} placeholder="Commission %" className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100" />
          <input type="number" step="0.01" value={f.credit_limit} onChange={(e) => setF({ ...f, credit_limit: parseFloat(e.target.value) || 0 })} placeholder="Credit limit" className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100" />
          <input value={f.billing_terms} onChange={(e) => setF({ ...f, billing_terms: e.target.value })} placeholder="Billing terms" className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100" />
        </div>
        <div className="flex justify-end gap-2 mt-4">
          <button onClick={onClose} className="px-3 py-1.5 rounded bg-stone-800 text-stone-300 text-sm">Cancel</button>
          <button data-testid="b2b-save-agent" onClick={save} disabled={saving}
            className="flex items-center gap-2 px-3 py-1.5 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 text-sm">
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />} Save
          </button>
        </div>
      </div>
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
function Mini({ label, children }) {
  return (
    <div className="bg-stone-800/40 rounded px-2 py-1">
      <div className="text-[9px] uppercase tracking-wider text-stone-500">{label}</div>
      <div className="text-stone-200 text-sm">{children}</div>
    </div>
  );
}
