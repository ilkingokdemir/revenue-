/**
 * Service Recovery Panel
 * ----------------------
 * Log guest complaints with auto AI severity classification (GPT-5.2),
 * recommend a recovery action (apology / discount / room move / refund),
 * and track resolution time + total compensation issued.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Loader2, ShieldAlert, RefreshCw, Plus, X, CheckCircle2, Clock, Sparkles,
  Filter, Trash2, AlertTriangle,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const SEVERITY_META = {
  low:      { label: "Low",      color: "bg-emerald-500/15 text-emerald-300 border-emerald-500/40" },
  medium:   { label: "Medium",   color: "bg-amber-500/15 text-amber-300 border-amber-500/40" },
  high:     { label: "High",     color: "bg-orange-500/15 text-orange-300 border-orange-500/40" },
  critical: { label: "Critical", color: "bg-rose-500/15 text-rose-300 border-rose-500/40" },
};

const STATUS_META = {
  open:        { label: "Open",        color: "bg-stone-700/40 text-stone-200 border-stone-600" },
  in_progress: { label: "In progress", color: "bg-blue-500/15 text-blue-300 border-blue-500/40" },
  resolved:    { label: "Resolved",    color: "bg-emerald-500/15 text-emerald-300 border-emerald-500/40" },
  closed:      { label: "Closed",      color: "bg-stone-700/40 text-stone-400 border-stone-700" },
};

const fmt = (n) => `£${Number(n || 0).toFixed(2)}`;

export default function ServiceRecoveryPanel({ propertyId, hotelName = "" }) {
  const [items, setItems] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState({ status: "", category: "" });
  const [showCreate, setShowCreate] = useState(false);
  const [edit, setEdit] = useState(null);

  const load = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filter.status)   params.append("status", filter.status);
      if (filter.category) params.append("category", filter.category);
      const [list, s] = await Promise.all([
        axios.get(`${API}/service-recovery/${propertyId}?${params.toString()}`),
        axios.get(`${API}/service-recovery/${propertyId}/stats`),
      ]);
      setItems(list.data || []);
      setStats(s.data);
    } catch { toast.error("Failed to load complaints"); }
    setLoading(false);
  }, [propertyId, filter.status, filter.category]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setItems([]); setStats(null); }, [propertyId]);

  return (
    <div className="space-y-6" data-testid="service-recovery-panel">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-5 h-5 text-rose-400" />
            <h2 className="text-2xl font-semibold text-stone-100">Service Recovery</h2>
            <span className="px-2 py-0.5 text-[10px] uppercase tracking-wider bg-rose-500/15 text-rose-300 rounded">
              AI-classified
            </span>
          </div>
          <p className="text-sm text-stone-400 mt-1">
            {hotelName ? `${hotelName} · ` : ""}Log complaints, auto-rank severity & track resolution.
          </p>
        </div>
        <div className="flex gap-2">
          <button data-testid="recovery-refresh-btn" onClick={load}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-stone-800 hover:bg-stone-700 text-sm text-stone-100 border border-stone-700">
            <RefreshCw className="w-4 h-4" /> Refresh
          </button>
          <button data-testid="recovery-create-btn" onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 border border-rose-500/40 text-rose-200 text-sm">
            <Plus className="w-4 h-4" /> Log complaint
          </button>
        </div>
      </div>

      {/* KPIs */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <Stat label="Total" value={stats.total} />
          <Stat label="Open" value={stats.open} highlight={stats.open > 0} />
          <Stat label="Resolved" value={stats.resolved} />
          <Stat label="Compensation" value={fmt(stats.compensation_total)} />
          <Stat label="Avg resolution"
                value={stats.avg_resolution_minutes
                  ? `${Math.round(stats.avg_resolution_minutes / 60)}h ${Math.round(stats.avg_resolution_minutes % 60)}m`
                  : "—"} />
        </div>
      )}

      {/* Severity breakdown */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4">
            <div className="text-[10px] uppercase tracking-wider text-stone-400 mb-3">By severity</div>
            <div className="space-y-2">
              {Object.entries(stats.by_severity || {}).map(([s, n]) => (
                <SeverityBar key={s} severity={s} count={n} max={Math.max(...Object.values(stats.by_severity || {1: 1}), 1)} />
              ))}
            </div>
          </div>
          <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4">
            <div className="text-[10px] uppercase tracking-wider text-stone-400 mb-3">By category</div>
            <div className="grid grid-cols-2 gap-2 text-sm">
              {Object.entries(stats.by_category || {}).sort((a,b) => b[1]-a[1]).map(([c, n]) => (
                <div key={c} className="flex items-center justify-between bg-stone-800/40 px-2 py-1 rounded">
                  <span className="text-stone-300 capitalize">{c.replaceAll("_", " ")}</span>
                  <span className="text-stone-100 font-mono">{n}</span>
                </div>
              ))}
              {Object.keys(stats.by_category || {}).length === 0 && (
                <div className="text-stone-500 text-xs col-span-2">No data yet.</div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-2 flex-wrap">
        <Filter className="w-4 h-4 text-stone-500" />
        <select data-testid="recovery-filter-status" value={filter.status}
          onChange={(e) => setFilter({ ...filter, status: e.target.value })}
          className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-xs">
          <option value="">All status</option>
          <option value="open">Open</option>
          <option value="in_progress">In progress</option>
          <option value="resolved">Resolved</option>
          <option value="closed">Closed</option>
        </select>
        <select data-testid="recovery-filter-category" value={filter.category}
          onChange={(e) => setFilter({ ...filter, category: e.target.value })}
          className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-xs">
          <option value="">All categories</option>
          {(stats?.categories || []).map((c) => (
            <option key={c} value={c}>{c.replaceAll("_", " ")}</option>
          ))}
        </select>
      </div>

      {/* List */}
      {loading ? (
        <div className="flex items-center justify-center py-12 text-stone-500">
          <Loader2 className="w-6 h-6 animate-spin" />
        </div>
      ) : items.length === 0 ? (
        <div className="text-center text-stone-500 py-12">No complaints logged in this window.</div>
      ) : (
        <div className="space-y-2">
          {items.map((c) => (
            <ComplaintRow key={c.id} c={c} onEdit={() => setEdit(c)} onReload={load} />
          ))}
        </div>
      )}

      {showCreate && (
        <CreateModal propertyId={propertyId} categories={stats?.categories || []}
          onClose={() => setShowCreate(false)} onSaved={() => { setShowCreate(false); load(); }} />
      )}
      {edit && (
        <EditModal complaint={edit} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); load(); }} />
      )}
    </div>
  );
}

function SeverityBar({ severity, count, max }) {
  const meta = SEVERITY_META[severity] || SEVERITY_META.medium;
  const pct = Math.max(2, Math.round((count / max) * 100));
  return (
    <div>
      <div className="flex items-center justify-between text-xs mb-0.5">
        <span className={`px-2 py-0.5 rounded border text-[10px] ${meta.color}`}>{meta.label}</span>
        <span className="text-stone-300 font-mono">{count}</span>
      </div>
      <div className="h-1.5 bg-stone-800 rounded">
        <div className={`h-full rounded ${severity === "critical" ? "bg-rose-500" :
          severity === "high" ? "bg-orange-500" :
          severity === "medium" ? "bg-amber-500" : "bg-emerald-500"}`}
          style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function ComplaintRow({ c, onEdit, onReload }) {
  const sev = SEVERITY_META[c.severity] || SEVERITY_META.medium;
  const st  = STATUS_META[c.status] || STATUS_META.open;
  const remove = async () => {
    if (!window.confirm("Delete this complaint?")) return;
    try {
      await axios.delete(`${API}/service-recovery/${c.id}`);
      toast.success("Deleted");
      onReload();
    } catch { toast.error("Delete failed"); }
  };
  return (
    <div data-testid="complaint-row" className="rounded-lg border border-stone-800 bg-stone-900/60 p-3 hover:bg-stone-900 transition">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className={`px-2 py-0.5 rounded border text-[10px] ${sev.color}`}>{sev.label}</span>
            <span className={`px-2 py-0.5 rounded border text-[10px] ${st.color}`}>{st.label}</span>
            <span className="text-stone-500 text-[11px] capitalize">{(c.category || "other").replaceAll("_", " ")}</span>
            {c.guest_name && <span className="text-stone-300 text-xs">· {c.guest_name}</span>}
            {c.room_number && <span className="text-stone-400 text-xs">· Rm {c.room_number}</span>}
          </div>
          <div className="text-sm text-stone-200 mb-1 line-clamp-2">{c.text}</div>
          {c.ai_summary && (
            <div className="flex items-start gap-1 text-xs text-purple-300/80">
              <Sparkles className="w-3 h-3 mt-0.5 flex-shrink-0" />
              <span><span className="font-medium">AI:</span> {c.ai_summary} → <em className="capitalize">{(c.ai_action || "").replaceAll("_", " ")}</em></span>
            </div>
          )}
        </div>
        <div className="flex flex-col items-end gap-1">
          <div className="text-[10px] text-stone-500">{new Date(c.created_at).toLocaleString()}</div>
          {c.compensation_amount > 0 && (
            <div className="text-xs text-emerald-300">Comp: {fmt(c.compensation_amount)}</div>
          )}
          <div className="flex items-center gap-1">
            <button data-testid="complaint-edit-btn" onClick={onEdit}
              className="text-[11px] px-2 py-0.5 rounded bg-stone-800 hover:bg-stone-700 text-stone-200 border border-stone-700">
              Update
            </button>
            <button onClick={remove} className="p-1 rounded text-stone-500 hover:text-rose-400">
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function CreateModal({ propertyId, categories, onClose, onSaved }) {
  const [form, setForm] = useState({
    text: "", category: "other", channel: "in_person",
    guest_name: "", room_number: "", booking_id: "",
  });
  const [saving, setSaving] = useState(false);
  const submit = async () => {
    if (!form.text.trim()) return toast.error("Complaint text required");
    setSaving(true);
    try {
      await axios.post(`${API}/service-recovery`, { property_id: propertyId, ...form });
      toast.success("Logged · severity classified");
      onSaved();
    } catch (e) { toast.error(e?.response?.data?.detail || "Save failed"); }
    setSaving(false);
  };
  return (
    <Modal title="Log a complaint" onClose={onClose}>
      <div className="space-y-3">
        <textarea data-testid="complaint-text" rows={4} placeholder="What did the guest report?"
          value={form.text} onChange={(e) => setForm({ ...form, text: e.target.value })}
          className="w-full px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm" />
        <div className="grid grid-cols-2 gap-2">
          <select data-testid="complaint-category" value={form.category}
            onChange={(e) => setForm({ ...form, category: e.target.value })}
            className="w-full px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm">
            {categories.map((c) => <option key={c} value={c}>{c.replaceAll("_", " ")}</option>)}
          </select>
          <select data-testid="complaint-channel" value={form.channel}
            onChange={(e) => setForm({ ...form, channel: e.target.value })}
            className="w-full px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm">
            {["in_person", "email", "phone", "review", "messaging"].map((c) =>
              <option key={c} value={c}>{c.replaceAll("_", " ")}</option>)}
          </select>
          <input value={form.guest_name} placeholder="Guest name (opt.)"
            onChange={(e) => setForm({ ...form, guest_name: e.target.value })}
            className="w-full px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm" />
          <input value={form.room_number} placeholder="Room # (opt.)"
            onChange={(e) => setForm({ ...form, room_number: e.target.value })}
            className="w-full px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm" />
        </div>
      </div>
      <div className="flex justify-end gap-2 mt-4">
        <button onClick={onClose} className="px-3 py-1.5 rounded bg-stone-800 text-stone-300 text-sm">Cancel</button>
        <button data-testid="complaint-save-btn" onClick={submit} disabled={saving}
          className="flex items-center gap-2 px-3 py-1.5 rounded bg-rose-500/20 border border-rose-500/40 text-rose-200 text-sm">
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
          Save & classify
        </button>
      </div>
    </Modal>
  );
}

function EditModal({ complaint, onClose, onSaved }) {
  const [form, setForm] = useState({
    status: complaint.status,
    compensation_amount: complaint.compensation_amount || 0,
    compensation_type: complaint.compensation_type || "",
    resolution_notes: complaint.resolution_notes || "",
  });
  const [saving, setSaving] = useState(false);
  const save = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/service-recovery/${complaint.id}`, form);
      toast.success("Updated");
      onSaved();
    } catch { toast.error("Save failed"); }
    setSaving(false);
  };
  return (
    <Modal title={`Update — ${complaint.guest_name || "Complaint"}`} onClose={onClose}>
      <div className="space-y-3">
        <div className="bg-stone-800/60 rounded p-2 text-xs text-stone-300 line-clamp-3">{complaint.text}</div>
        {complaint.ai_summary && (
          <div className="flex items-start gap-1 text-xs text-purple-300/80 bg-purple-500/5 border border-purple-500/30 rounded p-2">
            <Sparkles className="w-3 h-3 mt-0.5" />
            <span>AI: {complaint.ai_summary} → suggests <em className="capitalize">{complaint.ai_action?.replaceAll("_", " ")}</em></span>
          </div>
        )}
        <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}
          className="w-full px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm">
          {Object.keys(STATUS_META).map((s) => <option key={s} value={s}>{STATUS_META[s].label}</option>)}
        </select>
        <div className="grid grid-cols-2 gap-2">
          <input type="number" min={0} step={0.01} placeholder="Compensation £" value={form.compensation_amount}
            onChange={(e) => setForm({ ...form, compensation_amount: parseFloat(e.target.value) || 0 })}
            className="w-full px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm" />
          <input placeholder="Comp type (e.g. discount, comp night)" value={form.compensation_type}
            onChange={(e) => setForm({ ...form, compensation_type: e.target.value })}
            className="w-full px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm" />
        </div>
        <textarea rows={3} placeholder="Resolution notes" value={form.resolution_notes}
          onChange={(e) => setForm({ ...form, resolution_notes: e.target.value })}
          className="w-full px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm" />
      </div>
      <div className="flex justify-end gap-2 mt-4">
        <button onClick={onClose} className="px-3 py-1.5 rounded bg-stone-800 text-stone-300 text-sm">Cancel</button>
        <button data-testid="complaint-update-save" onClick={save} disabled={saving}
          className="flex items-center gap-2 px-3 py-1.5 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 text-sm">
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
          Save
        </button>
      </div>
    </Modal>
  );
}

function Modal({ title, children, onClose }) {
  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-stone-900 border border-stone-800 rounded-xl max-w-lg w-full p-5" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-3">
          <div className="text-stone-100 font-semibold">{title}</div>
          <button onClick={onClose} className="p-1 rounded hover:bg-stone-800 text-stone-500">
            <X className="w-4 h-4" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

function Stat({ label, value, highlight = false }) {
  return (
    <div className={`p-3 rounded-lg border ${highlight ? "bg-rose-500/10 border-rose-500/40" : "bg-stone-800/60 border-stone-800"}`}>
      <div className="text-[10px] uppercase tracking-wider text-stone-400 mb-1">{label}</div>
      <div className={`text-lg font-semibold ${highlight ? "text-rose-200" : "text-stone-100"}`}>{value}</div>
    </div>
  );
}
