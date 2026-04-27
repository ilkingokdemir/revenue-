/**
 * Pre-arrival Drip Email Sequence Panel
 * Manage stage templates (T-7, T-3, T-1, T+0) and view scheduled dispatches.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, Mail, Plus, RefreshCw, Send, Trash2, Eye } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const STAGES = [
  { id: "t_minus_7", label: "T-7 days · Welcome" },
  { id: "t_minus_3", label: "T-3 days · Upsell window" },
  { id: "t_minus_1", label: "T-1 day · Final reminder" },
  { id: "t_zero", label: "T+0 · On-arrival" },
];

export default function PreArrivalDripPanel({ propertyId, hotelName = "" }) {
  const [tab, setTab] = useState("templates");
  const [templates, setTemplates] = useState([]);
  const [dispatches, setDispatches] = useState({ items: [], by_stage: {}, sent: 0, pending: 0, count: 0 });
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({ stage: "t_minus_7", language: "en", subject: "", body: "", channel: "email", active: true });
  const [preview, setPreview] = useState(null);

  const refresh = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const [{ data: t }, { data: d }] = await Promise.all([
        axios.get(`${API}/pre-arrival/${propertyId}/templates`),
        axios.get(`${API}/pre-arrival/${propertyId}/dispatches?days=14`),
      ]);
      setTemplates(t.items || []);
      setDispatches(d);
    } catch { toast.error("Load failed"); }
    setLoading(false);
  }, [propertyId]);

  useEffect(() => { refresh(); }, [refresh]);

  const save = async () => {
    if (!form.subject || !form.body) return toast.error("Subject + body required");
    try {
      await axios.post(`${API}/pre-arrival/templates`, { property_id: propertyId, ...form });
      toast.success("Template saved");
      setForm({ ...form, subject: "", body: "" });
      refresh();
    } catch { toast.error("Failed"); }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete template?")) return;
    try {
      await axios.delete(`${API}/pre-arrival/templates/${id}`);
      toast.success("Deleted");
      refresh();
    } catch { toast.error("Failed"); }
  };

  const sweep = async () => {
    try {
      const { data } = await axios.post(`${API}/pre-arrival/sweep`, { property_id: propertyId });
      toast.success(`Scheduled ${data.scheduled} dispatches`);
      refresh();
    } catch { toast.error("Sweep failed"); }
  };

  const showPreview = async (d) => {
    try {
      const { data } = await axios.post(`${API}/pre-arrival/dispatches/${d.id}/preview`, {});
      setPreview(data);
    } catch { toast.error("Preview failed"); }
  };

  return (
    <div className="space-y-6" data-testid="pre-arrival-panel">
      <div>
        <h2 className="text-2xl font-semibold text-stone-100">Pre-arrival Drip Sequence</h2>
        <p className="text-sm text-stone-400 mt-1">{hotelName ? `${hotelName} · ` : ""}Staged comms before check-in: welcome → upsell → reminder → on-arrival.</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {STAGES.map((s) => (
          <Stat key={s.id} label={s.label} value={dispatches.by_stage[s.id] || 0} />
        ))}
      </div>

      <div className="flex gap-2 flex-wrap">
        <button data-testid="pa-sweep-btn" onClick={sweep} className="text-sm px-3 py-2 rounded bg-cyan-500/20 border border-cyan-500/40 text-cyan-200 flex items-center gap-2"><Send className="w-4 h-4" /> Run sweep</button>
        <button onClick={refresh} className="text-sm px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-300 flex items-center gap-2">
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />} Refresh
        </button>
        <div className="ml-auto flex gap-1">
          {["templates", "dispatches"].map((t) => (
            <button key={t} data-testid={`pa-tab-${t}`} onClick={() => setTab(t)} className={`text-xs px-3 py-1 rounded border ${tab === t ? "bg-cyan-500/20 border-cyan-500/40 text-cyan-200" : "bg-stone-800 border-stone-700 text-stone-300"}`}>{t}</button>
          ))}
        </div>
      </div>

      {tab === "templates" ? (
        <div className="grid lg:grid-cols-2 gap-4">
          <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4 space-y-2">
            <div className="text-xs uppercase tracking-wider text-stone-400">New / edit template</div>
            <div className="grid grid-cols-3 gap-2">
              <select value={form.stage} onChange={(e) => setForm({ ...form, stage: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-xs">
                {STAGES.map((s) => <option key={s.id} value={s.id}>{s.id}</option>)}
              </select>
              <select value={form.language} onChange={(e) => setForm({ ...form, language: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-xs">
                {["en", "tr", "de", "fr", "es", "ar", "ru"].map((l) => <option key={l} value={l}>{l}</option>)}
              </select>
              <select value={form.channel} onChange={(e) => setForm({ ...form, channel: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-xs">
                {["email", "sms", "whatsapp"].map((l) => <option key={l} value={l}>{l}</option>)}
              </select>
            </div>
            <input data-testid="pa-subject-input" placeholder="Subject (use {guest_name}, {hotel_name}, {checkin_date}…)" value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} className="w-full px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm" />
            <textarea data-testid="pa-body-input" rows={6} placeholder="Body" value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} className="w-full px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm" />
            <div className="text-[10px] text-stone-500">Merge tags: {"{guest_name}"} {"{first_name}"} {"{checkin_date}"} {"{checkout_date}"} {"{hotel_name}"} {"{hotel_phone}"} {"{room_type}"} {"{booking_ref}"}</div>
            <button data-testid="pa-save-btn" onClick={save} className="w-full px-3 py-2 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 text-sm">Save template</button>
          </div>

          <div className="rounded-xl border border-stone-800 bg-stone-900/60 overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="text-left text-[10px] uppercase tracking-wider text-stone-500 border-b border-stone-800">
                <tr><th className="px-3 py-2">Stage</th><th className="px-3 py-2">Lang</th><th className="px-3 py-2">Subject</th><th className="px-3 py-2"></th></tr>
              </thead>
              <tbody>
                {templates.map((t) => (
                  <tr key={t.id} className="border-t border-stone-800/60 text-stone-200" data-testid="pa-template-row">
                    <td className="px-3 py-2 text-xs font-mono">{t.stage}</td>
                    <td className="px-3 py-2 text-xs">{t.language}</td>
                    <td className="px-3 py-2 text-xs truncate max-w-xs">{t.subject}</td>
                    <td className="px-3 py-2 text-right">
                      <button onClick={() => remove(t.id)} className="text-xs px-2 py-1 rounded bg-rose-500/20 border border-rose-500/40 text-rose-200"><Trash2 className="w-3 h-3" /></button>
                    </td>
                  </tr>
                ))}
                {templates.length === 0 && <tr><td colSpan={4} className="px-3 py-6 text-center text-stone-500"><Mail className="w-5 h-5 mx-auto mb-1 opacity-60" />No templates yet.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <>
          <div className="rounded-xl border border-stone-800 bg-stone-900/60 overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="text-left text-[10px] uppercase tracking-wider text-stone-500 border-b border-stone-800">
                <tr><th className="px-3 py-2">Scheduled</th><th className="px-3 py-2">Stage</th><th className="px-3 py-2">Channel</th><th className="px-3 py-2">To</th><th className="px-3 py-2">Subject</th><th className="px-3 py-2">Status</th><th className="px-3 py-2"></th></tr>
              </thead>
              <tbody>
                {dispatches.items.map((d) => (
                  <tr key={d.id} className="border-t border-stone-800/60 text-stone-200" data-testid="pa-dispatch-row">
                    <td className="px-3 py-2 text-xs text-stone-400">{(d.scheduled_for || "").slice(0, 16)}</td>
                    <td className="px-3 py-2 text-xs font-mono">{d.stage}</td>
                    <td className="px-3 py-2 text-xs">{d.channel}</td>
                    <td className="px-3 py-2 text-xs text-stone-400">{d.to_email || d.to_phone || "—"}</td>
                    <td className="px-3 py-2 text-xs truncate max-w-xs">{d.subject_preview}</td>
                    <td className="px-3 py-2"><span className={`text-[10px] px-2 py-0.5 rounded border ${d.status === "sent" ? "bg-emerald-500/20 border-emerald-500/40 text-emerald-200" : d.status === "failed" ? "bg-rose-500/20 border-rose-500/40 text-rose-200" : "bg-amber-500/20 border-amber-500/40 text-amber-200"}`}>{d.status}</span></td>
                    <td className="px-3 py-2 text-right">
                      <button data-testid="pa-preview-btn" onClick={() => showPreview(d)} className="text-xs px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-300 flex items-center gap-1 ml-auto"><Eye className="w-3 h-3" /> Preview</button>
                    </td>
                  </tr>
                ))}
                {dispatches.items.length === 0 && <tr><td colSpan={7} className="px-3 py-6 text-center text-stone-500">No dispatches scheduled. Run sweep to enrol due bookings.</td></tr>}
              </tbody>
            </table>
          </div>

          {preview && (
            <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4 space-y-2" data-testid="pa-preview-box">
              <div className="text-xs uppercase tracking-wider text-stone-400">Rendered preview · {preview.channel} · {preview.stage}</div>
              <div className="text-stone-300 text-xs">To: <span className="font-mono">{preview.to_email}</span></div>
              <div className="text-stone-100 font-medium">{preview.subject}</div>
              <pre className="text-xs bg-stone-950 border border-stone-800 rounded p-3 overflow-x-auto whitespace-pre-wrap text-stone-200">{preview.body}</pre>
              <button onClick={() => setPreview(null)} className="text-xs text-stone-400 hover:text-stone-200">Close</button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="p-3 rounded-lg border border-stone-800 bg-stone-800/60">
      <div className="text-[10px] uppercase tracking-wider text-stone-400 mb-1">{label}</div>
      <div className="text-lg font-semibold text-stone-100">{value}</div>
    </div>
  );
}
