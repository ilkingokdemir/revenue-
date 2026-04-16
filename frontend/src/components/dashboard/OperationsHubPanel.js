import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { motion, AnimatePresence } from "framer-motion";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Textarea } from "@/components/ui/textarea";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/* ─────────────── RECEPTION REPORT TAB ─────────────── */
const ReceptionTab = ({ propertyId }) => {
  const [data, setData] = useState(null);
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (fromDate) params.append("from_date", fromDate);
      if (toDate) params.append("to_date", toDate);
      const { data: d } = await axios.get(`${API}/operations/reception/${propertyId}?${params}`);
      setData(d);
    } catch { toast.error("Failed to load reception data"); }
    setLoading(false);
  }, [propertyId, fromDate, toDate]);

  useEffect(() => { load(); }, [load]);

  const stats = data?.stats || {};
  const kpis = [
    { label: "Bookings Created", value: stats.bookings_created || 0, color: "from-blue-500 to-blue-600", icon: "M19 4h-1V2h-2v2H8V2H6v2H5c-1.11 0-1.99.9-1.99 2L3 20a2 2 0 002 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2z" },
    { label: "Check-ins", value: stats.check_ins || 0, color: "from-emerald-500 to-emerald-600", icon: "M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" },
    { label: "Check-outs", value: stats.check_outs || 0, color: "from-violet-500 to-violet-600", icon: "M10.09 15.59L11.5 17l5-5-5-5-1.41 1.41L12.67 11H3v2h9.67l-2.58 2.59z" },
    { label: "Cancellations", value: stats.cancellations || 0, color: "from-red-500 to-red-600", icon: "M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" },
    { label: "Routine Runs", value: stats.routine_runs || 0, color: "from-amber-500 to-amber-600", icon: "M12 4V1L8 5l4 4V6c3.31 0 6 2.69 6 6 0 1.01-.25 1.97-.7 2.8l1.46 1.46A7.93 7.93 0 0020 12c0-4.42-3.58-8-8-8zm0 14c-3.31 0-6-2.69-6-6 0-1.01.25-1.97.7-2.8L5.24 7.74A7.93 7.93 0 004 12c0 4.42 3.58 8 8 8v3l4-4-4-4v3z" },
  ];

  const DetailTable = ({ title, rows, columns }) => (
    <div className="mt-6" data-testid={`reception-table-${title.toLowerCase().replace(/\s/g, '-')}`}>
      <h3 className="text-sm font-semibold text-stone-700 mb-3">{title}</h3>
      {rows.length === 0 ? (
        <div className="text-center py-8 text-stone-400 text-sm bg-stone-50 rounded-lg border border-dashed border-stone-200">No records for this period</div>
      ) : (
        <div className="overflow-x-auto border border-stone-200 rounded-lg">
          <table className="w-full text-sm">
            <thead><tr className="bg-stone-50 border-b border-stone-200">
              {columns.map(c => <th key={c.key} className="px-4 py-2.5 text-left text-xs font-semibold text-stone-500 uppercase tracking-wider">{c.label}</th>)}
            </tr></thead>
            <tbody>{rows.map((r, i) => (
              <tr key={i} className="border-b border-stone-100 hover:bg-stone-50/50 transition-colors">
                {columns.map(c => <td key={c.key} className="px-4 py-2.5 text-stone-600">{r[c.key] || "—"}</td>)}
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
    </div>
  );

  return (
    <div data-testid="reception-tab">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-bold text-stone-800">Reception Report</h2>
          <p className="text-sm text-stone-500">Track receptionist activity across bookings, check-ins, and routines</p>
        </div>
      </div>
      <div className="flex items-center gap-3 mb-6 flex-wrap">
        <div className="flex items-center gap-2">
          <label className="text-xs font-medium text-stone-500">From</label>
          <Input type="date" value={fromDate} onChange={e => setFromDate(e.target.value)} className="w-40 h-9 text-sm" data-testid="reception-from-date" />
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs font-medium text-stone-500">To</label>
          <Input type="date" value={toDate} onChange={e => setToDate(e.target.value)} className="w-40 h-9 text-sm" data-testid="reception-to-date" />
        </div>
        <button onClick={() => { setFromDate(""); setToDate(""); }} className="text-xs text-stone-400 hover:text-stone-600" data-testid="reception-reset">Reset</button>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
        {kpis.map(k => (
          <motion.div key={k.label} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
            className={`bg-gradient-to-br ${k.color} rounded-xl p-4 text-white shadow-lg shadow-black/10`} data-testid={`kpi-${k.label.toLowerCase().replace(/\s/g, '-')}`}>
            <div className="flex items-center gap-2 mb-1">
              <svg className="w-4 h-4 opacity-80" viewBox="0 0 24 24" fill="currentColor"><path d={k.icon}/></svg>
              <span className="text-xs font-medium opacity-90">{k.label}</span>
            </div>
            <div className="text-2xl font-bold">{loading ? "..." : k.value}</div>
          </motion.div>
        ))}
      </div>
      <DetailTable title="Bookings Created" rows={data?.bookings || []}
        columns={[{ key: "guest", label: "Guest" }, { key: "branch", label: "Branch" }, { key: "created_by", label: "Created By" }, { key: "created_at", label: "Created At" }]} />
      <DetailTable title="Check-ins" rows={data?.checkins || []}
        columns={[{ key: "guest", label: "Guest" }, { key: "branch", label: "Branch" }, { key: "checked_in_by", label: "Checked In By" }, { key: "checked_in_at", label: "Checked In At" }]} />
      <DetailTable title="Check-outs" rows={data?.checkouts || []}
        columns={[{ key: "guest", label: "Guest" }, { key: "branch", label: "Branch" }, { key: "checked_out_by", label: "Checked Out By" }, { key: "checked_out_at", label: "Checked Out At" }]} />
    </div>
  );
};

/* ─────────────── ROUTINE TEMPLATES TAB ─────────────── */
const RoutineTemplatesTab = ({ propertyId }) => {
  const [templates, setTemplates] = useState([]);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", steps: [""], role: "receptionist", shift: "default", property_id: "" });
  const [editId, setEditId] = useState(null);

  const load = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/operations/routine-templates/${propertyId}`);
      setTemplates(data);
    } catch { toast.error("Failed to load templates"); }
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);

  const save = async () => {
    try {
      const payload = { ...form, steps: form.steps.filter(s => s.trim()), property_id: form.property_id || propertyId };
      if (editId) {
        await axios.put(`${API}/operations/routine-templates/${editId}`, payload);
        toast.success("Template updated");
      } else {
        await axios.post(`${API}/operations/routine-templates`, payload);
        toast.success("Template created");
      }
      setShowCreate(false); setEditId(null);
      setForm({ name: "", description: "", steps: [""], role: "receptionist", shift: "default", property_id: "" });
      load();
    } catch { toast.error("Save failed"); }
  };

  const startRoutine = async (id) => {
    try {
      await axios.post(`${API}/operations/routine-templates/${id}/start`);
      toast.success("Routine started!");
    } catch { toast.error("Failed to start routine"); }
  };

  const deleteTemplate = async (id) => {
    try {
      await axios.delete(`${API}/operations/routine-templates/${id}`);
      toast.success("Template deleted");
      load();
    } catch { toast.error("Delete failed"); }
  };

  const openEdit = (t) => {
    setForm({ name: t.name, description: t.description, steps: t.steps?.length ? t.steps : [""], role: t.role, shift: t.shift, property_id: t.property_id });
    setEditId(t.id);
    setShowCreate(true);
  };

  return (
    <div data-testid="routine-templates-tab">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-bold text-stone-800">Routine Templates</h2>
          <p className="text-sm text-stone-500">Define daily front-desk routines, required steps, and branch/shift targeting</p>
        </div>
        <button onClick={() => { setEditId(null); setForm({ name: "", description: "", steps: [""], role: "receptionist", shift: "default", property_id: "" }); setShowCreate(true); }}
          className="flex items-center gap-2 px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700 transition-colors shadow-sm" data-testid="new-template-btn">
          <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z"/></svg>
          New Template
        </button>
      </div>
      {templates.length === 0 ? (
        <div className="text-center py-16 text-stone-400">
          <svg className="w-12 h-12 mx-auto mb-3 text-stone-300" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/></svg>
          <p className="font-medium">No templates yet</p>
          <p className="text-sm mt-1">Create your first routine template to get started</p>
        </div>
      ) : (
        <div className="space-y-3">
          {templates.map(t => (
            <motion.div key={t.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }}
              className="border border-stone-200 rounded-xl p-4 bg-white hover:shadow-md transition-all group" data-testid={`template-card-${t.id}`}>
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="font-semibold text-stone-800 truncate">{t.name}</h3>
                    <Badge variant={t.is_active ? "default" : "secondary"} className={`text-[10px] ${t.is_active ? "bg-emerald-100 text-emerald-700" : "bg-stone-100 text-stone-500"}`}>
                      {t.is_active ? "Active" : "Inactive"}
                    </Badge>
                    <span className="text-[10px] text-stone-400">v{t.version || "1.0"}</span>
                  </div>
                  <p className="text-sm text-stone-500 line-clamp-2 mb-2">{t.description || "No description"}</p>
                  <div className="flex items-center gap-3 text-xs text-stone-400">
                    <span className="flex items-center gap-1 bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full font-medium">
                      {t.steps?.length || 0} steps
                    </span>
                    <span>{t.property_id === "any" ? "Any branch" : t.property_id} &middot; {t.role} &middot; Shift: {t.shift}</span>
                  </div>
                </div>
                <div className="flex items-center gap-1 ml-3 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button onClick={() => startRoutine(t.id)} className="p-2 text-emerald-500 hover:bg-emerald-50 rounded-lg transition-colors" title="Start Routine" data-testid={`start-routine-${t.id}`}>
                    <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z"/></svg>
                  </button>
                  <button onClick={() => openEdit(t)} className="p-2 text-stone-400 hover:bg-stone-100 rounded-lg transition-colors" title="Edit" data-testid={`edit-template-${t.id}`}>
                    <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z"/></svg>
                  </button>
                  <button onClick={() => deleteTemplate(t.id)} className="p-2 text-red-400 hover:bg-red-50 rounded-lg transition-colors" title="Delete" data-testid={`delete-template-${t.id}`}>
                    <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9z"/></svg>
                  </button>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      )}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="max-w-lg" data-testid="template-dialog">
          <DialogHeader><DialogTitle>{editId ? "Edit Template" : "New Routine Template"}</DialogTitle></DialogHeader>
          <div className="space-y-4 mt-2">
            <div><label className="text-xs font-medium text-stone-500 mb-1 block">Name</label>
              <Input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="e.g. Morning Receptionist Routine" data-testid="template-name-input" /></div>
            <div><label className="text-xs font-medium text-stone-500 mb-1 block">Description</label>
              <Textarea value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} rows={2} placeholder="Brief description..." data-testid="template-desc-input" /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><label className="text-xs font-medium text-stone-500 mb-1 block">Role</label>
                <Select value={form.role} onValueChange={v => setForm({ ...form, role: v })}>
                  <SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="receptionist">Receptionist</SelectItem>
                    <SelectItem value="housekeeper">Housekeeper</SelectItem>
                    <SelectItem value="maintenance">Maintenance</SelectItem>
                    <SelectItem value="manager">Manager</SelectItem>
                  </SelectContent>
                </Select></div>
              <div><label className="text-xs font-medium text-stone-500 mb-1 block">Shift</label>
                <Input value={form.shift} onChange={e => setForm({ ...form, shift: e.target.value })} placeholder="default / morning / mid" data-testid="template-shift-input" /></div>
            </div>
            <div><label className="text-xs font-medium text-stone-500 mb-1 block">Steps</label>
              <div className="space-y-2">{form.steps.map((s, i) => (
                <div key={i} className="flex items-center gap-2">
                  <span className="w-6 h-6 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center text-xs font-bold flex-shrink-0">{i + 1}</span>
                  <Input value={s} onChange={e => { const ns = [...form.steps]; ns[i] = e.target.value; setForm({ ...form, steps: ns }); }} placeholder={`Step ${i + 1}`} className="flex-1" data-testid={`template-step-${i}`} />
                  {form.steps.length > 1 && <button onClick={() => setForm({ ...form, steps: form.steps.filter((_, j) => j !== i) })} className="text-red-400 hover:text-red-600"><svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"/></svg></button>}
                </div>
              ))}</div>
              <button onClick={() => setForm({ ...form, steps: [...form.steps, ""] })} className="mt-2 text-xs text-emerald-600 hover:text-emerald-700 font-medium" data-testid="add-step-btn">+ Add Step</button>
            </div>
            <button onClick={save} className="w-full py-2.5 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700 transition-colors" data-testid="save-template-btn">
              {editId ? "Update Template" : "Create Template"}
            </button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

/* ─────────────── ROUTINE HISTORY TAB ─────────────── */
const RoutineHistoryTab = ({ propertyId }) => {
  const [runs, setRuns] = useState([]);
  const [rstats, setRstats] = useState({});
  const [filters, setFilters] = useState({ shift: "", status: "" });
  const [viewRun, setViewRun] = useState(null);

  const load = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (filters.shift) params.append("shift", filters.shift);
      if (filters.status) params.append("status", filters.status);
      const [{ data: h }, { data: s }] = await Promise.all([
        axios.get(`${API}/operations/routine-history/${propertyId}?${params}`),
        axios.get(`${API}/operations/routine-history/stats/${propertyId}`),
      ]);
      setRuns(h); setRstats(s);
    } catch { toast.error("Failed to load history"); }
  }, [propertyId, filters]);

  useEffect(() => { load(); }, [load]);

  const completeTask = async (runId, taskIndex) => {
    try {
      const { data } = await axios.put(`${API}/operations/routine-history/${runId}/task/${taskIndex}`, { completed: true });
      setViewRun(data);
      load();
      toast.success("Task completed");
    } catch { toast.error("Failed"); }
  };

  const statCards = [
    { label: "Total Runs", value: rstats.total || 0, color: "bg-blue-500" },
    { label: "Completed", value: rstats.completed || 0, color: "bg-emerald-500" },
    { label: "In Progress", value: rstats.incomplete || 0, color: "bg-amber-500" },
    { label: "Completion Rate", value: `${rstats.completion_rate || 0}%`, color: "bg-violet-500" },
  ];

  return (
    <div data-testid="routine-history-tab">
      <div className="mb-6">
        <h2 className="text-lg font-bold text-stone-800">Routine History</h2>
        <p className="text-sm text-stone-500">View completed and in-progress routines across all branches</p>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        {statCards.map(c => (
          <div key={c.label} className={`${c.color} rounded-xl p-4 text-white shadow-lg shadow-black/10`} data-testid={`rh-stat-${c.label.toLowerCase().replace(/\s/g, '-')}`}>
            <div className="text-xs font-medium opacity-80">{c.label}</div>
            <div className="text-2xl font-bold mt-1">{c.value}</div>
          </div>
        ))}
      </div>
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <div className="flex items-center gap-2">
          <label className="text-xs font-medium text-stone-500">Shift</label>
          <Input value={filters.shift} onChange={e => setFilters(p => ({ ...p, shift: e.target.value }))} placeholder="Search shift..." className="w-36 h-9 text-sm" data-testid="rh-filter-shift" />
        </div>
        <Select value={filters.status} onValueChange={v => setFilters(p => ({ ...p, status: v }))}>
          <SelectTrigger className="w-36 h-9 text-sm"><SelectValue placeholder="All Statuses" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all_statuses">All Statuses</SelectItem>
            <SelectItem value="in_progress">In Progress</SelectItem>
            <SelectItem value="completed">Completed</SelectItem>
          </SelectContent>
        </Select>
      </div>
      {runs.length === 0 ? (
        <div className="text-center py-12 text-stone-400 text-sm">No routine runs found</div>
      ) : (
        <div className="border border-stone-200 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead><tr className="bg-stone-50 border-b border-stone-200">
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-stone-500 uppercase">Date</th>
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-stone-500 uppercase">Template</th>
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-stone-500 uppercase">Shift</th>
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-stone-500 uppercase">User</th>
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-stone-500 uppercase">Status</th>
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-stone-500 uppercase">Tasks</th>
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-stone-500 uppercase">Actions</th>
            </tr></thead>
            <tbody>{runs.map(r => {
              const pct = r.total_tasks > 0 ? Math.round((r.completed_tasks / r.total_tasks) * 100) : 0;
              return (
                <tr key={r.id} className="border-b border-stone-100 hover:bg-stone-50/50 transition-colors" data-testid={`rh-row-${r.id}`}>
                  <td className="px-4 py-2.5 text-stone-600">{r.created_at ? new Date(r.created_at).toLocaleDateString() : "—"}</td>
                  <td className="px-4 py-2.5 text-stone-800 font-medium">{r.template_name}</td>
                  <td className="px-4 py-2.5"><Badge className="bg-blue-50 text-blue-600 text-[10px]">{r.shift}</Badge></td>
                  <td className="px-4 py-2.5 text-stone-600">{r.user}</td>
                  <td className="px-4 py-2.5"><Badge className={`text-[10px] ${r.status === "completed" ? "bg-emerald-50 text-emerald-600" : "bg-amber-50 text-amber-600"}`}>{r.status}</Badge></td>
                  <td className="px-4 py-2.5 w-40">
                    <div className="flex items-center gap-2">
                      <Progress value={pct} className="h-1.5 flex-1" />
                      <span className="text-xs text-stone-500 whitespace-nowrap">{r.completed_tasks}/{r.total_tasks}</span>
                    </div>
                  </td>
                  <td className="px-4 py-2.5">
                    <button onClick={() => setViewRun(r)} className="text-xs text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1" data-testid={`rh-view-${r.id}`}>
                      <svg className="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor"><path d="M10 12a2 2 0 100-4 2 2 0 000 4z"/><path fillRule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z"/></svg>
                      View
                    </button>
                  </td>
                </tr>
              );
            })}</tbody>
          </table>
        </div>
      )}
      <Dialog open={!!viewRun} onOpenChange={() => setViewRun(null)}>
        <DialogContent className="max-w-lg" data-testid="routine-run-dialog">
          <DialogHeader><DialogTitle>Routine: {viewRun?.template_name}</DialogTitle></DialogHeader>
          <div className="space-y-2 mt-3">{viewRun?.tasks?.map((t, i) => (
            <div key={i} className={`flex items-center gap-3 p-3 rounded-lg border transition-colors ${t.completed ? "bg-emerald-50/50 border-emerald-200" : "bg-white border-stone-200"}`}>
              <button onClick={() => !t.completed && completeTask(viewRun.id, i)} disabled={t.completed}
                className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 transition-colors ${t.completed ? "bg-emerald-500 text-white" : "border-2 border-stone-300 hover:border-emerald-400"}`} data-testid={`task-check-${i}`}>
                {t.completed && <svg className="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"/></svg>}
              </button>
              <span className={`text-sm flex-1 ${t.completed ? "text-stone-400 line-through" : "text-stone-700"}`}>{t.step}</span>
            </div>
          ))}</div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

/* ─────────────── PASS OVER DUTIES TAB ─────────────── */
const PassOverDutiesTab = ({ propertyId }) => {
  const [notes, setNotes] = useState([]);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ content: "", note_type: "general", priority: "normal", owner: "", role_target: "", due_date: "" });
  const [filters, setFilters] = useState({ note_type: "", priority: "", status: "" });
  const [search, setSearch] = useState("");

  const load = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (filters.note_type) params.append("note_type", filters.note_type);
      if (filters.priority) params.append("priority", filters.priority);
      if (filters.status) params.append("status", filters.status);
      const { data } = await axios.get(`${API}/operations/handover/${propertyId}?${params}`);
      setNotes(data);
    } catch { toast.error("Failed to load notes"); }
  }, [propertyId, filters]);

  useEffect(() => { load(); }, [load]);

  const saveNote = async () => {
    try {
      await axios.post(`${API}/operations/handover`, { ...form, property_id: propertyId });
      toast.success("Note created");
      setShowCreate(false);
      setForm({ content: "", note_type: "general", priority: "normal", owner: "", role_target: "", due_date: "" });
      load();
    } catch { toast.error("Failed to create note"); }
  };

  const resolveNote = async (id) => {
    try {
      await axios.put(`${API}/operations/handover/${id}`, { status: "resolved" });
      toast.success("Note resolved");
      load();
    } catch { toast.error("Failed"); }
  };

  const deleteNote = async (id) => {
    try {
      await axios.delete(`${API}/operations/handover/${id}`);
      toast.success("Note deleted"); load();
    } catch { toast.error("Failed"); }
  };

  const filtered = notes.filter(n => !search || n.content?.toLowerCase().includes(search.toLowerCase()));
  const typeColors = { general: "bg-stone-100 text-stone-600", urgent: "bg-red-100 text-red-700", maintenance: "bg-amber-100 text-amber-700", guest: "bg-blue-100 text-blue-700", billing: "bg-violet-100 text-violet-700" };
  const priorityColors = { low: "bg-stone-100 text-stone-500", normal: "bg-blue-100 text-blue-600", high: "bg-orange-100 text-orange-700", critical: "bg-red-100 text-red-700" };

  return (
    <div data-testid="pass-over-duties-tab">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-bold text-stone-800">Pass Over Duties</h2>
          <p className="text-sm text-stone-500">Shift handover notes, reminders, and mentions in one operational timeline</p>
        </div>
        <button onClick={() => setShowCreate(true)} className="flex items-center gap-2 px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700 transition-colors shadow-sm" data-testid="new-note-btn">
          <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z"/></svg>
          New Note
        </button>
      </div>
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <Input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search note content..." className="w-56 h-9 text-sm" data-testid="pod-search" />
        <Select value={filters.note_type || "all_types"} onValueChange={v => setFilters(p => ({ ...p, note_type: v === "all_types" ? "" : v }))}>
          <SelectTrigger className="w-32 h-9 text-sm"><SelectValue placeholder="All Types" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all_types">All Types</SelectItem>
            <SelectItem value="general">General</SelectItem>
            <SelectItem value="urgent">Urgent</SelectItem>
            <SelectItem value="maintenance">Maintenance</SelectItem>
            <SelectItem value="guest">Guest</SelectItem>
            <SelectItem value="billing">Billing</SelectItem>
          </SelectContent>
        </Select>
        <Select value={filters.priority || "all_priorities"} onValueChange={v => setFilters(p => ({ ...p, priority: v === "all_priorities" ? "" : v }))}>
          <SelectTrigger className="w-36 h-9 text-sm"><SelectValue placeholder="All Priorities" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all_priorities">All Priorities</SelectItem>
            <SelectItem value="low">Low</SelectItem>
            <SelectItem value="normal">Normal</SelectItem>
            <SelectItem value="high">High</SelectItem>
            <SelectItem value="critical">Critical</SelectItem>
          </SelectContent>
        </Select>
        <Select value={filters.status || "all_statuses"} onValueChange={v => setFilters(p => ({ ...p, status: v === "all_statuses" ? "" : v }))}>
          <SelectTrigger className="w-32 h-9 text-sm"><SelectValue placeholder="All Statuses" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all_statuses">All Statuses</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="resolved">Resolved</SelectItem>
          </SelectContent>
        </Select>
      </div>
      {filtered.length === 0 ? (
        <div className="text-center py-16 text-stone-400">
          <svg className="w-12 h-12 mx-auto mb-3 text-stone-300" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg>
          <p className="font-medium">No handover notes</p>
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-[10px] uppercase tracking-wider font-bold text-stone-400">Open Notes ({filtered.filter(n => n.status === "pending").length})</p>
          {filtered.map(n => (
            <motion.div key={n.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }}
              className={`border rounded-xl p-4 transition-all ${n.status === "resolved" ? "bg-stone-50 border-stone-200 opacity-60" : "bg-white border-stone-200 hover:shadow-md"}`} data-testid={`note-card-${n.id}`}>
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2 flex-wrap">
                    <Badge className={`text-[10px] uppercase ${typeColors[n.note_type] || typeColors.general}`}>{n.note_type}</Badge>
                    <Badge className={`text-[10px] uppercase ${priorityColors[n.priority] || priorityColors.normal}`}>{n.priority}</Badge>
                    <Badge className={`text-[10px] uppercase ${n.status === "resolved" ? "bg-emerald-100 text-emerald-600" : "bg-sky-100 text-sky-600"}`}>{n.status}</Badge>
                  </div>
                  <p className="text-sm text-stone-700 leading-relaxed">{n.content}</p>
                  <div className="flex items-center gap-4 mt-3 text-xs text-stone-400">
                    <span className="flex items-center gap-1">
                      <svg className="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z"/></svg>
                      {n.author}
                    </span>
                    {n.owner && <span>Owner: {n.owner}</span>}
                    <span className="flex items-center gap-1">
                      <svg className="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M6 2a1 1 0 00-1 1v1H4a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V6a2 2 0 00-2-2h-1V3a1 1 0 10-2 0v1H7V3a1 1 0 00-1-1zm0 5a1 1 0 000 2h8a1 1 0 100-2H6z"/></svg>
                      {n.created_at ? new Date(n.created_at).toLocaleString() : "—"}
                    </span>
                  </div>
                </div>
                {n.status !== "resolved" && (
                  <div className="flex items-center gap-1 flex-shrink-0">
                    <button onClick={() => resolveNote(n.id)} className="p-2 text-emerald-500 hover:bg-emerald-50 rounded-lg" title="Resolve" data-testid={`resolve-note-${n.id}`}>
                      <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"/></svg>
                    </button>
                    <button onClick={() => deleteNote(n.id)} className="p-2 text-red-400 hover:bg-red-50 rounded-lg" title="Delete" data-testid={`delete-note-${n.id}`}>
                      <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9z"/></svg>
                    </button>
                  </div>
                )}
              </div>
            </motion.div>
          ))}
        </div>
      )}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="max-w-lg" data-testid="note-dialog">
          <DialogHeader><DialogTitle>New Handover Note</DialogTitle></DialogHeader>
          <div className="space-y-4 mt-2">
            <div><label className="text-xs font-medium text-stone-500 mb-1 block">Note</label>
              <Textarea value={form.content} onChange={e => setForm({ ...form, content: e.target.value })} rows={4} placeholder="Describe the handover note..." data-testid="note-content-input" /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><label className="text-xs font-medium text-stone-500 mb-1 block">Type</label>
                <Select value={form.note_type} onValueChange={v => setForm({ ...form, note_type: v })}>
                  <SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="general">General</SelectItem>
                    <SelectItem value="urgent">Urgent</SelectItem>
                    <SelectItem value="maintenance">Maintenance</SelectItem>
                    <SelectItem value="guest">Guest</SelectItem>
                    <SelectItem value="billing">Billing</SelectItem>
                  </SelectContent>
                </Select></div>
              <div><label className="text-xs font-medium text-stone-500 mb-1 block">Priority</label>
                <Select value={form.priority} onValueChange={v => setForm({ ...form, priority: v })}>
                  <SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="low">Low</SelectItem>
                    <SelectItem value="normal">Normal</SelectItem>
                    <SelectItem value="high">High</SelectItem>
                    <SelectItem value="critical">Critical</SelectItem>
                  </SelectContent>
                </Select></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><label className="text-xs font-medium text-stone-500 mb-1 block">Owner/Assignee</label>
                <Input value={form.owner} onChange={e => setForm({ ...form, owner: e.target.value })} placeholder="e.g. Cigdem" data-testid="note-owner-input" /></div>
              <div><label className="text-xs font-medium text-stone-500 mb-1 block">Target Role</label>
                <Input value={form.role_target} onChange={e => setForm({ ...form, role_target: e.target.value })} placeholder="e.g. receptionist" data-testid="note-role-input" /></div>
            </div>
            <button onClick={saveNote} className="w-full py-2.5 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700 transition-colors" data-testid="save-note-btn">
              Create Note
            </button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

/* ─────────────── LAUNDRY MANAGEMENT TAB ─────────────── */
const LaundryTab = ({ propertyId }) => {
  const [items, setItems] = useState([]);
  const [stats, setStats] = useState({});
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ room_number: "", guest_name: "", items: "", total_pieces: 0, notes: "" });
  const [filter, setFilter] = useState("");

  const load = useCallback(async () => {
    try {
      const params = filter ? `?status=${filter}` : "";
      const [{ data: i }, { data: s }] = await Promise.all([
        axios.get(`${API}/operations/laundry/${propertyId}${params}`),
        axios.get(`${API}/operations/laundry/stats/${propertyId}`),
      ]);
      setItems(i); setStats(s);
    } catch { toast.error("Failed to load laundry data"); }
  }, [propertyId, filter]);

  useEffect(() => { load(); }, [load]);

  const create = async () => {
    try {
      await axios.post(`${API}/operations/laundry`, {
        property_id: propertyId, room_number: form.room_number, guest_name: form.guest_name,
        items: form.items.split(",").map(i => i.trim()).filter(Boolean), total_pieces: parseInt(form.total_pieces) || 0, notes: form.notes,
      });
      toast.success("Laundry dispatched"); setShowCreate(false);
      setForm({ room_number: "", guest_name: "", items: "", total_pieces: 0, notes: "" }); load();
    } catch { toast.error("Failed"); }
  };

  const updateStatus = async (id, status) => {
    try {
      await axios.put(`${API}/operations/laundry/${id}`, { status });
      toast.success(`Marked as ${status}`); load();
    } catch { toast.error("Failed"); }
  };

  const actionCards = [
    { label: "Dispatch", desc: "Send to laundry", color: "from-orange-500 to-orange-600", icon: "M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z", action: () => setShowCreate(true) },
    { label: "Deliveries", desc: "Receive from laundry", color: "from-emerald-500 to-emerald-600", icon: "M5 3a2 2 0 00-2 2v2a2 2 0 002 2h2a2 2 0 002-2V5a2 2 0 00-2-2H5zM5 11a2 2 0 00-2 2v2a2 2 0 002 2h2a2 2 0 002-2v-2a2 2 0 00-2-2H5zM11 5a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V5zM14 11a1 1 0 011 1v1h1a1 1 0 110 2h-1v1a1 1 0 11-2 0v-1h-1a1 1 0 110-2h1v-1a1 1 0 011-1z", action: () => setFilter("sent") },
    { label: "Daily Usage", desc: "Room collections", color: "from-blue-500 to-blue-600", icon: "M6 2a1 1 0 00-1 1v1H4a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V6a2 2 0 00-2-2h-1V3a1 1 0 10-2 0v1H7V3a1 1 0 00-1-1zm0 5a1 1 0 000 2h8a1 1 0 100-2H6z", action: () => setFilter("") },
    { label: "Stock", desc: "Inventory levels", color: "from-violet-500 to-violet-600", icon: "M4 3a2 2 0 100 4h12a2 2 0 100-4H4zM3 8h14v7a2 2 0 01-2 2H5a2 2 0 01-2-2V8zm5 3a1 1 0 011-1h2a1 1 0 110 2H9a1 1 0 01-1-1z", action: () => setFilter("in_progress") },
  ];

  const statusColors = { sent: "bg-orange-100 text-orange-700", in_progress: "bg-blue-100 text-blue-700", returned: "bg-emerald-100 text-emerald-700" };

  return (
    <div data-testid="laundry-tab">
      <div className="mb-6">
        <h2 className="text-lg font-bold text-stone-800">Laundry Management</h2>
        <p className="text-sm text-stone-500">Manage dispatches, deliveries and view reports</p>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        {actionCards.map(c => (
          <motion.button key={c.label} onClick={c.action} whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
            className={`bg-gradient-to-br ${c.color} rounded-2xl p-5 text-left text-white shadow-lg shadow-black/10 transition-all hover:shadow-xl`} data-testid={`laundry-action-${c.label.toLowerCase()}`}>
            <svg className="w-8 h-8 mb-2 opacity-80" viewBox="0 0 20 20" fill="currentColor"><path d={c.icon}/></svg>
            <div className="font-bold text-base">{c.label}</div>
            <div className="text-xs opacity-80 mt-0.5">{c.desc}</div>
          </motion.button>
        ))}
      </div>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-stone-700">
          Items ({stats.total || 0}) &middot; Sent: {stats.sent || 0} &middot; In Progress: {stats.in_progress || 0} &middot; Returned: {stats.returned || 0}
        </h3>
        <Select value={filter || "all_filter"} onValueChange={v => setFilter(v === "all_filter" ? "" : v)}>
          <SelectTrigger className="w-32 h-9 text-sm"><SelectValue placeholder="All" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all_filter">All</SelectItem>
            <SelectItem value="sent">Sent</SelectItem>
            <SelectItem value="in_progress">In Progress</SelectItem>
            <SelectItem value="returned">Returned</SelectItem>
          </SelectContent>
        </Select>
      </div>
      {items.length === 0 ? (
        <div className="text-center py-12 text-stone-400 text-sm">No laundry records yet</div>
      ) : (
        <div className="space-y-2">{items.map(item => (
          <div key={item.id} className="flex items-center justify-between border border-stone-200 rounded-lg p-3 bg-white hover:shadow-sm transition-all" data-testid={`laundry-item-${item.id}`}>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-stone-100 flex items-center justify-center text-stone-400">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"/></svg>
              </div>
              <div>
                <div className="text-sm font-medium text-stone-800">Room {item.room_number} {item.guest_name && `- ${item.guest_name}`}</div>
                <div className="text-xs text-stone-400">{item.total_pieces} pieces &middot; {item.sent_by} &middot; {item.sent_at ? new Date(item.sent_at).toLocaleString() : ""}</div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Badge className={`text-[10px] ${statusColors[item.status] || "bg-stone-100 text-stone-500"}`}>{item.status}</Badge>
              {item.status === "sent" && <button onClick={() => updateStatus(item.id, "in_progress")} className="text-xs text-blue-600 hover:underline" data-testid={`laundry-progress-${item.id}`}>Start</button>}
              {item.status === "in_progress" && <button onClick={() => updateStatus(item.id, "returned")} className="text-xs text-emerald-600 hover:underline" data-testid={`laundry-return-${item.id}`}>Return</button>}
            </div>
          </div>
        ))}</div>
      )}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="max-w-md" data-testid="laundry-dialog">
          <DialogHeader><DialogTitle>Dispatch Laundry</DialogTitle></DialogHeader>
          <div className="space-y-4 mt-2">
            <div className="grid grid-cols-2 gap-3">
              <div><label className="text-xs font-medium text-stone-500 mb-1 block">Room</label>
                <Input value={form.room_number} onChange={e => setForm({ ...form, room_number: e.target.value })} placeholder="e.g. 302" data-testid="laundry-room-input" /></div>
              <div><label className="text-xs font-medium text-stone-500 mb-1 block">Guest</label>
                <Input value={form.guest_name} onChange={e => setForm({ ...form, guest_name: e.target.value })} placeholder="Guest name" data-testid="laundry-guest-input" /></div>
            </div>
            <div><label className="text-xs font-medium text-stone-500 mb-1 block">Items (comma-separated)</label>
              <Input value={form.items} onChange={e => setForm({ ...form, items: e.target.value })} placeholder="Towels, Sheets, Pillowcases" data-testid="laundry-items-input" /></div>
            <div><label className="text-xs font-medium text-stone-500 mb-1 block">Total Pieces</label>
              <Input type="number" value={form.total_pieces} onChange={e => setForm({ ...form, total_pieces: e.target.value })} data-testid="laundry-pieces-input" /></div>
            <div><label className="text-xs font-medium text-stone-500 mb-1 block">Notes</label>
              <Textarea value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} rows={2} data-testid="laundry-notes-input" /></div>
            <button onClick={create} className="w-full py-2.5 bg-orange-500 text-white rounded-lg text-sm font-medium hover:bg-orange-600 transition-colors" data-testid="laundry-dispatch-btn">
              Dispatch to Laundry
            </button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

/* ─────────────── COMPLIANCE TAB ─────────────── */
const ComplianceTab = ({ propertyId }) => {
  const [checks, setChecks] = useState([]);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ title: "", description: "", check_type: "safety", frequency: "monthly", scheduled_date: "", inspector: "", checklist_items: [""] });

  const load = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/operations/compliance/${propertyId}`);
      setChecks(data);
    } catch { toast.error("Failed to load compliance"); }
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);

  const create = async () => {
    try {
      await axios.post(`${API}/operations/compliance`, {
        ...form, property_id: propertyId, checklist_items: form.checklist_items.filter(i => i.trim()),
      });
      toast.success("Check scheduled"); setShowCreate(false);
      setForm({ title: "", description: "", check_type: "safety", frequency: "monthly", scheduled_date: "", inspector: "", checklist_items: [""] });
      load();
    } catch { toast.error("Failed"); }
  };

  const updateCheck = async (id, updates) => {
    try {
      await axios.put(`${API}/operations/compliance/${id}`, updates);
      toast.success("Updated"); load();
    } catch { toast.error("Failed"); }
  };

  const typeIcons = { safety: "M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z", fire: "M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z", health: "M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z", electrical: "M13 10V3L4 14h7v7l9-11h-7z", hygiene: "M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01" };
  const statusColors = { scheduled: "bg-blue-100 text-blue-700", in_progress: "bg-amber-100 text-amber-700", completed: "bg-emerald-100 text-emerald-700" };
  const resultColors = { pass: "bg-emerald-100 text-emerald-700", fail: "bg-red-100 text-red-700" };

  return (
    <div data-testid="compliance-tab">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-bold text-stone-800">Compliance Checks</h2>
          <p className="text-sm text-stone-500">Schedule and track safety, fire, and hygiene inspections</p>
        </div>
        <button onClick={() => setShowCreate(true)} className="flex items-center gap-2 px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700 transition-colors shadow-sm" data-testid="new-compliance-btn">
          <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z"/></svg>
          New Check
        </button>
      </div>
      {checks.length === 0 ? (
        <div className="text-center py-16 text-stone-400">
          <svg className="w-12 h-12 mx-auto mb-3 text-stone-300" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={typeIcons.safety}/></svg>
          <p className="font-medium">No compliance checks scheduled</p>
        </div>
      ) : (
        <div className="space-y-3">{checks.map(c => (
          <div key={c.id} className="border border-stone-200 rounded-xl p-4 bg-white hover:shadow-md transition-all" data-testid={`compliance-card-${c.id}`}>
            <div className="flex items-start justify-between">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-lg bg-stone-100 flex items-center justify-center flex-shrink-0">
                  <svg className="w-5 h-5 text-stone-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={typeIcons[c.check_type] || typeIcons.safety}/></svg>
                </div>
                <div>
                  <h3 className="font-semibold text-stone-800">{c.title}</h3>
                  <p className="text-xs text-stone-500 mt-0.5">{c.description}</p>
                  <div className="flex items-center gap-2 mt-2 flex-wrap">
                    <Badge className={`text-[10px] ${statusColors[c.status] || "bg-stone-100 text-stone-500"}`}>{c.status}</Badge>
                    {c.result && <Badge className={`text-[10px] ${resultColors[c.result] || ""}`}>{c.result}</Badge>}
                    <span className="text-[10px] text-stone-400 capitalize">{c.check_type} &middot; {c.frequency}</span>
                    {c.scheduled_date && <span className="text-[10px] text-stone-400">Due: {c.scheduled_date}</span>}
                    {c.inspector && <span className="text-[10px] text-stone-400">Inspector: {c.inspector}</span>}
                  </div>
                  {c.checklist?.length > 0 && (
                    <div className="mt-2 text-xs text-stone-400">{c.checklist.filter(i => i.passed).length}/{c.checklist.length} items passed</div>
                  )}
                </div>
              </div>
              <div className="flex gap-1">
                {c.status !== "completed" && (
                  <button onClick={() => updateCheck(c.id, { status: "completed", checklist: c.checklist?.map(i => ({ ...i, passed: true })) })}
                    className="p-2 text-emerald-500 hover:bg-emerald-50 rounded-lg" title="Complete" data-testid={`complete-compliance-${c.id}`}>
                    <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"/></svg>
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}</div>
      )}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="max-w-lg" data-testid="compliance-dialog">
          <DialogHeader><DialogTitle>Schedule Compliance Check</DialogTitle></DialogHeader>
          <div className="space-y-4 mt-2">
            <div><label className="text-xs font-medium text-stone-500 mb-1 block">Title</label>
              <Input value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} placeholder="e.g. Monthly Fire Safety" data-testid="compliance-title-input" /></div>
            <div><label className="text-xs font-medium text-stone-500 mb-1 block">Description</label>
              <Textarea value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} rows={2} data-testid="compliance-desc-input" /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><label className="text-xs font-medium text-stone-500 mb-1 block">Type</label>
                <Select value={form.check_type} onValueChange={v => setForm({ ...form, check_type: v })}>
                  <SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="safety">Safety</SelectItem>
                    <SelectItem value="fire">Fire</SelectItem>
                    <SelectItem value="health">Health</SelectItem>
                    <SelectItem value="electrical">Electrical</SelectItem>
                    <SelectItem value="hygiene">Hygiene</SelectItem>
                  </SelectContent>
                </Select></div>
              <div><label className="text-xs font-medium text-stone-500 mb-1 block">Frequency</label>
                <Select value={form.frequency} onValueChange={v => setForm({ ...form, frequency: v })}>
                  <SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="daily">Daily</SelectItem>
                    <SelectItem value="weekly">Weekly</SelectItem>
                    <SelectItem value="monthly">Monthly</SelectItem>
                    <SelectItem value="quarterly">Quarterly</SelectItem>
                    <SelectItem value="annually">Annually</SelectItem>
                  </SelectContent>
                </Select></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><label className="text-xs font-medium text-stone-500 mb-1 block">Scheduled Date</label>
                <Input type="date" value={form.scheduled_date} onChange={e => setForm({ ...form, scheduled_date: e.target.value })} data-testid="compliance-date-input" /></div>
              <div><label className="text-xs font-medium text-stone-500 mb-1 block">Inspector</label>
                <Input value={form.inspector} onChange={e => setForm({ ...form, inspector: e.target.value })} placeholder="Name" data-testid="compliance-inspector-input" /></div>
            </div>
            <div><label className="text-xs font-medium text-stone-500 mb-1 block">Checklist Items</label>
              <div className="space-y-2">{form.checklist_items.map((item, i) => (
                <div key={i} className="flex items-center gap-2">
                  <Input value={item} onChange={e => { const ni = [...form.checklist_items]; ni[i] = e.target.value; setForm({ ...form, checklist_items: ni }); }} placeholder={`Item ${i + 1}`} className="flex-1" data-testid={`compliance-item-${i}`} />
                  {form.checklist_items.length > 1 && <button onClick={() => setForm({ ...form, checklist_items: form.checklist_items.filter((_, j) => j !== i) })} className="text-red-400">
                    <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"/></svg>
                  </button>}
                </div>
              ))}</div>
              <button onClick={() => setForm({ ...form, checklist_items: [...form.checklist_items, ""] })} className="mt-2 text-xs text-emerald-600 hover:text-emerald-700 font-medium" data-testid="add-checklist-btn">+ Add Item</button>
            </div>
            <button onClick={create} className="w-full py-2.5 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700 transition-colors" data-testid="save-compliance-btn">
              Schedule Check
            </button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

/* ─────────────── SHIFT SCHEDULER TAB ─────────────── */
const ShiftSchedulerTab = ({ propertyId }) => {
  const [staff, setStaff] = useState([]);
  const [shifts, setShifts] = useState([]);
  const [weekStart, setWeekStart] = useState(() => {
    const d = new Date(); d.setDate(d.getDate() - d.getDay() + 1);
    return d.toISOString().split("T")[0];
  });
  const [roleFilter, setRoleFilter] = useState("");
  const [search, setSearch] = useState("");
  const [showAddStaff, setShowAddStaff] = useState(false);
  const [showAddShift, setShowAddShift] = useState(null);
  const [staffForm, setStaffForm] = useState({ name: "", role: "housekeeper", pay_type: "daily", pay_rate: 80, currency: "GBP" });
  const [shiftForm, setShiftForm] = useState({ start_time: "09:00", end_time: "17:00", notes: "" });

  const getDays = () => {
    const days = [];
    const start = new Date(weekStart + "T00:00:00");
    for (let i = 0; i < 7; i++) {
      const d = new Date(start); d.setDate(start.getDate() + i);
      days.push({ date: d.toISOString().split("T")[0], day: d.toLocaleDateString("en", { weekday: "short" }), num: d.getDate(), month: d.toLocaleDateString("en", { month: "short" }) });
    }
    return days;
  };

  const load = useCallback(async () => {
    try {
      const [{ data: s }, { data: e }] = await Promise.all([
        axios.get(`${API}/shifts/staff/${propertyId}${roleFilter ? `?role=${roleFilter}` : ""}`),
        axios.get(`${API}/shifts/entries/${propertyId}?week_start=${weekStart}`),
      ]);
      setStaff(s); setShifts(e);
    } catch { toast.error("Failed to load shifts"); }
  }, [propertyId, weekStart, roleFilter]);

  useEffect(() => { load(); }, [load]);

  const navWeek = (dir) => {
    const d = new Date(weekStart + "T00:00:00");
    d.setDate(d.getDate() + (dir * 7));
    setWeekStart(d.toISOString().split("T")[0]);
  };

  const addStaff = async () => {
    try {
      await axios.post(`${API}/shifts/staff`, { ...staffForm, property_id: propertyId });
      toast.success("Staff added"); setShowAddStaff(false);
      setStaffForm({ name: "", role: "housekeeper", pay_type: "daily", pay_rate: 80, currency: "GBP" }); load();
    } catch { toast.error("Failed"); }
  };

  const addShift = async () => {
    if (!showAddShift) return;
    try {
      const s = staff.find(st => st.id === showAddShift.staffId);
      await axios.post(`${API}/shifts/entries`, {
        property_id: propertyId, staff_id: showAddShift.staffId, staff_name: s?.name || "", role: s?.role || "",
        date: showAddShift.date, week_start: weekStart, start_time: shiftForm.start_time, end_time: shiftForm.end_time,
        notes: shiftForm.notes, pay_type: s?.pay_type || "daily", pay_rate: s?.pay_rate || 0,
      });
      toast.success("Shift created"); setShowAddShift(null);
      setShiftForm({ start_time: "09:00", end_time: "17:00", notes: "" }); load();
    } catch { toast.error("Failed"); }
  };

  const deleteShift = async (id) => {
    try { await axios.delete(`${API}/shifts/entries/${id}`); toast.success("Deleted"); load(); } catch { toast.error("Failed"); }
  };

  const bulkAction = async (action) => {
    try {
      await axios.post(`${API}/shifts/bulk/${action}`, { week_start: weekStart, property_id: propertyId });
      toast.success(`${action.replace("-", " ")} done`); load();
    } catch { toast.error("Failed"); }
  };

  const days = getDays();
  const weekEnd = days[6];
  const filteredStaff = staff.filter(s => !search || s.name?.toLowerCase().includes(search.toLowerCase()));
  const shiftColors = { planned: "bg-blue-500", published: "bg-emerald-500", completed: "bg-amber-500", approved: "bg-violet-500", draft: "bg-stone-400" };

  return (
    <div data-testid="shift-scheduler-tab">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-bold text-stone-800">Shift Scheduler</h2>
          <p className="text-sm text-stone-500">Manage staff shifts and payroll</p>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={() => navWeek(-1)} className="p-2 hover:bg-stone-100 rounded-lg text-stone-500" data-testid="shift-prev-week">
            <svg className="w-5 h-5" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z"/></svg>
          </button>
          <span className="text-sm font-semibold text-stone-700 bg-stone-100 px-4 py-1.5 rounded-lg" data-testid="shift-week-label">
            {days[0]?.num} {days[0]?.month} - {weekEnd?.num} {weekEnd?.month}
          </span>
          <button onClick={() => navWeek(1)} className="p-2 hover:bg-stone-100 rounded-lg text-stone-500" data-testid="shift-next-week">
            <svg className="w-5 h-5" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"/></svg>
          </button>
        </div>
      </div>

      <div className="flex items-center gap-3 mb-3 flex-wrap">
        <div className="flex items-center gap-1 text-xs font-medium text-stone-500">
          FILTER BY ROLE
          {["", "housekeeper", "maintenance", "receptionist"].map(r => (
            <button key={r} onClick={() => setRoleFilter(r)}
              className={`px-2.5 py-1 rounded-md transition-colors ${roleFilter === r ? "bg-blue-500 text-white" : "text-stone-500 hover:bg-stone-100"}`} data-testid={`shift-role-${r || "all"}`}>
              {r || "All"}
            </button>
          ))}
        </div>
        <Input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search by name..." className="w-40 h-8 text-xs" data-testid="shift-search" />
        <button onClick={() => setShowAddStaff(true)} className="text-xs text-emerald-600 hover:text-emerald-700 font-medium" data-testid="add-staff-btn">+ Add Staff</button>
      </div>

      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <button onClick={() => bulkAction("publish-all")} className="px-3 py-1.5 text-xs font-medium text-stone-600 border border-stone-200 rounded-lg hover:bg-stone-50 transition-colors" data-testid="shift-publish-all">Publish All</button>
        <button onClick={() => bulkAction("mark-completed")} className="px-3 py-1.5 text-xs font-medium text-white bg-emerald-500 rounded-lg hover:bg-emerald-600 transition-colors" data-testid="shift-mark-completed">Mark All Completed</button>
        <button onClick={() => bulkAction("approve-completed")} className="px-3 py-1.5 text-xs font-medium text-white bg-blue-500 rounded-lg hover:bg-blue-600 transition-colors" data-testid="shift-approve-all">Approve All Completed</button>
        <button onClick={async () => {
          try { const { data } = await axios.post(`${API}/shifts/sync-to-salaries`, { week_start: weekStart, property_id: propertyId });
            toast.success(`${data.synced} salary entries created from ${data.total_shifts_processed} shifts`);
          } catch { toast.error("Failed to sync"); }
        }} className="px-3 py-1.5 text-xs font-medium text-white bg-violet-500 rounded-lg hover:bg-violet-600 transition-colors" data-testid="shift-sync-salaries">Sync to Payroll</button>
        <button onClick={() => { if (window.confirm("Clear all shifts for this week?")) bulkAction("clear-week"); }}
          className="px-3 py-1.5 text-xs font-medium text-red-600 border border-red-200 rounded-lg hover:bg-red-50 transition-colors" data-testid="shift-clear-week">Clear Week</button>
        <div className="flex items-center gap-2 ml-auto text-[10px] text-stone-400">
          {Object.entries(shiftColors).map(([k, c]) => <span key={k} className="flex items-center gap-1"><span className={`w-2.5 h-2.5 rounded-sm ${c}`}/>{k}</span>)}
        </div>
      </div>

      <div className="border border-stone-200 rounded-xl overflow-hidden bg-white">
        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="shift-calendar-table">
            <thead>
              <tr className="bg-stone-50 border-b border-stone-200">
                <th className="px-4 py-3 text-left text-xs font-semibold text-stone-500 w-48 sticky left-0 bg-stone-50 z-10">Staff Member</th>
                {days.map(d => (
                  <th key={d.date} className="px-2 py-3 text-center text-xs font-semibold text-stone-500 min-w-[120px]">
                    <div className="font-bold">{d.day}</div>
                    <div className="text-stone-400 font-normal">{d.num} {d.month}</div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filteredStaff.length === 0 ? (
                <tr><td colSpan={8} className="text-center py-12 text-stone-400 text-sm">No staff members. Add staff to start scheduling.</td></tr>
              ) : filteredStaff.map(s => (
                <tr key={s.id} className="border-b border-stone-100 hover:bg-stone-50/30" data-testid={`shift-row-${s.id}`}>
                  <td className="px-4 py-3 sticky left-0 bg-white z-10">
                    <div className="font-medium text-stone-800">{s.name}</div>
                    <div className="text-xs text-stone-400 capitalize">{s.role}</div>
                    <div className="flex items-center gap-1 mt-0.5">
                      <Badge className="text-[9px] bg-amber-50 text-amber-600 capitalize">{s.pay_type}</Badge>
                      <span className="text-[10px] text-stone-400">{s.currency === "GBP" ? "\u00A3" : s.currency}{s.pay_rate}</span>
                    </div>
                  </td>
                  {days.map(d => {
                    const dayShifts = shifts.filter(sh => sh.staff_id === s.id && sh.date === d.date);
                    return (
                      <td key={d.date} className="px-1 py-2 align-top min-w-[120px]" data-testid={`shift-cell-${s.id}-${d.date}`}>
                        {dayShifts.map(sh => (
                          <div key={sh.id} className={`${shiftColors[sh.status] || "bg-stone-400"} text-white text-[10px] font-medium px-2 py-1.5 rounded-md mb-1 group`}>
                            <div className="flex items-center justify-between">
                              <span>{sh.start_time}-{sh.end_time}</span>
                              <button onClick={() => deleteShift(sh.id)} className="opacity-0 group-hover:opacity-100 ml-1" data-testid={`delete-shift-${sh.id}`}>
                                <svg className="w-3 h-3" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"/></svg>
                              </button>
                            </div>
                            <div className="text-[9px] opacity-80 mt-0.5">{sh.hours_worked || "8"}h &middot; £{sh.earned_amount || sh.pay_rate || 0}</div>
                          </div>
                        ))}
                        <button onClick={() => setShowAddShift({ staffId: s.id, date: d.date })}
                          className="w-full h-6 border border-dashed border-stone-200 rounded-md text-stone-300 hover:border-emerald-300 hover:text-emerald-400 transition-colors flex items-center justify-center" data-testid={`add-shift-${s.id}-${d.date}`}>
                          <svg className="w-3 h-3" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z"/></svg>
                        </button>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <Dialog open={showAddStaff} onOpenChange={setShowAddStaff}>
        <DialogContent className="max-w-sm" data-testid="add-staff-dialog">
          <DialogHeader><DialogTitle>Add Staff Member</DialogTitle></DialogHeader>
          <div className="space-y-3 mt-2">
            <Input value={staffForm.name} onChange={e => setStaffForm({ ...staffForm, name: e.target.value })} placeholder="Full name" data-testid="staff-name-input" />
            <Select value={staffForm.role} onValueChange={v => setStaffForm({ ...staffForm, role: v })}>
              <SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="housekeeper">Housekeeper</SelectItem>
                <SelectItem value="receptionist">Receptionist</SelectItem>
                <SelectItem value="maintenance">Maintenance</SelectItem>
                <SelectItem value="manager">Manager</SelectItem>
              </SelectContent>
            </Select>
            <div className="grid grid-cols-2 gap-3">
              <Select value={staffForm.pay_type} onValueChange={v => setStaffForm({ ...staffForm, pay_type: v })}>
                <SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="daily">Daily</SelectItem><SelectItem value="hourly">Hourly</SelectItem></SelectContent>
              </Select>
              <Input type="number" value={staffForm.pay_rate} onChange={e => setStaffForm({ ...staffForm, pay_rate: parseFloat(e.target.value) || 0 })} placeholder="Rate" data-testid="staff-rate-input" />
            </div>
            <button onClick={addStaff} className="w-full py-2.5 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700 transition-colors" data-testid="save-staff-btn">Add Staff</button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={!!showAddShift} onOpenChange={() => setShowAddShift(null)}>
        <DialogContent className="max-w-sm" data-testid="add-shift-dialog">
          <DialogHeader><DialogTitle>Add Shift</DialogTitle></DialogHeader>
          <div className="space-y-3 mt-2">
            <div className="text-sm text-stone-500">Date: <strong>{showAddShift?.date}</strong></div>
            <div className="grid grid-cols-2 gap-3">
              <div><label className="text-xs text-stone-500 mb-1 block">Start</label>
                <Input type="time" value={shiftForm.start_time} onChange={e => setShiftForm({ ...shiftForm, start_time: e.target.value })} data-testid="shift-start-input" /></div>
              <div><label className="text-xs text-stone-500 mb-1 block">End</label>
                <Input type="time" value={shiftForm.end_time} onChange={e => setShiftForm({ ...shiftForm, end_time: e.target.value })} data-testid="shift-end-input" /></div>
            </div>
            <Input value={shiftForm.notes} onChange={e => setShiftForm({ ...shiftForm, notes: e.target.value })} placeholder="Notes (optional)" data-testid="shift-notes-input" />
            <button onClick={addShift} className="w-full py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors" data-testid="save-shift-btn">Add Shift</button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

/* ─────────────── MAIN OPERATIONS HUB PANEL ─────────────── */
const tabs = [
  { id: "reception", label: "Reception", icon: "M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" },
  { id: "routines", label: "Routine Templates", icon: "M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" },
  { id: "history", label: "Routine History", icon: "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" },
  { id: "handover", label: "Pass Over Duties", icon: "M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" },
  { id: "laundry", label: "Laundry", icon: "M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" },
  { id: "compliance", label: "Compliance", icon: "M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" },
  { id: "shifts", label: "Shifts", icon: "M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" },
];

export const OperationsHubPanel = ({ properties, activePropertyId }) => {
  const [activeTab, setActiveTab] = useState("reception");
  const pid = activePropertyId || "all";

  return (
    <div className="p-5" data-testid="operations-hub-panel">
      {/* Tab Navigation */}
      <div className="flex items-center gap-1 mb-6 overflow-x-auto pb-1 border-b border-stone-200">
        {tabs.map(tab => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium whitespace-nowrap transition-all border-b-2 -mb-[1px] ${
              activeTab === tab.id
                ? "text-emerald-700 border-emerald-500 bg-emerald-50/50"
                : "text-stone-400 border-transparent hover:text-stone-600 hover:border-stone-300"
            }`} data-testid={`ops-tab-${tab.id}`}>
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={tab.icon}/></svg>
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <AnimatePresence mode="wait">
        <motion.div key={activeTab} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}>
          {activeTab === "reception" && <ReceptionTab propertyId={pid} />}
          {activeTab === "routines" && <RoutineTemplatesTab propertyId={pid} />}
          {activeTab === "history" && <RoutineHistoryTab propertyId={pid} />}
          {activeTab === "handover" && <PassOverDutiesTab propertyId={pid} />}
          {activeTab === "laundry" && <LaundryTab propertyId={pid} />}
          {activeTab === "compliance" && <ComplianceTab propertyId={pid} />}
          {activeTab === "shifts" && <ShiftSchedulerTab propertyId={pid} />}
        </motion.div>
      </AnimatePresence>
    </div>
  );
};
