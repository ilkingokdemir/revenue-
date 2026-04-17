import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger,
  DialogFooter, DialogDescription,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import {
  RefreshCw, Plus, CheckCircle2, AlertTriangle, Clock, Flame, Utensils,
  Shield, Award, Umbrella, Lock, BookOpen, FolderCheck, ExternalLink,
  Edit3, Trash2, FileCheck, AlertCircle,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const ICON_MAP = { flame: Flame, utensils: Utensils, shield: Shield, award: Award, umbrella: Umbrella, lock: Lock, book: BookOpen };
const STATUS_STYLE = {
  compliant:       { color: "bg-emerald-100 text-emerald-700 border-emerald-200", icon: CheckCircle2, label: "Compliant" },
  expiring_soon:   { color: "bg-amber-100 text-amber-700 border-amber-200",       icon: Clock,        label: "Expiring Soon" },
  overdue:         { color: "bg-red-100 text-red-700 border-red-200",             icon: AlertTriangle,label: "Overdue" },
  action_needed:   { color: "bg-blue-100 text-blue-700 border-blue-200",          icon: AlertCircle,  label: "Action Needed" },
  not_applicable:  { color: "bg-stone-100 text-stone-500 border-stone-200",       icon: FileCheck,    label: "N/A" },
};

export const ComplianceRegister = ({ propertyId, user }) => {
  const [categories, setCategories] = useState([]);
  const [data, setData] = useState({ items: [], kpis: {} });
  const [loading, setLoading] = useState(true);
  const [activeCat, setActiveCat] = useState("");
  const [activeStatus, setActiveStatus] = useState("");
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({
    title: "", category: "hs", description: "", due_date: "", status: "compliant",
    assigned_to: "", evidence_url: "", frequency: "annual", notes: "",
  });

  const pid = propertyId || "all";
  const isManager = user?.role === "admin" || user?.role === "manager";

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [c, i] = await Promise.all([
        axios.get(`${API}/compliance/categories/${pid}`),
        axios.get(`${API}/compliance/items/${pid}${activeCat ? `?category=${activeCat}` : ""}${activeStatus ? `${activeCat ? "&" : "?"}status=${activeStatus}` : ""}`),
      ]);
      setCategories(c.data.categories || []);
      setData(i.data || { items: [], kpis: {} });
    } catch { /* silent */ }
    setLoading(false);
  }, [pid, activeCat, activeStatus]);

  useEffect(() => { load(); }, [load]);

  const openNew = () => {
    setEditing(null);
    setForm({ title: "", category: activeCat || "hs", description: "", due_date: "", status: "compliant", assigned_to: "", evidence_url: "", frequency: "annual", notes: "" });
    setOpen(true);
  };
  const openEdit = (item) => {
    setEditing(item);
    setForm({
      title: item.title, category: item.category, description: item.description || "",
      due_date: item.due_date || "", status: item.status || "compliant",
      assigned_to: item.assigned_to || "", evidence_url: item.evidence_url || "",
      frequency: item.frequency || "annual", notes: item.notes || "",
    });
    setOpen(true);
  };

  const submit = async () => {
    if (!form.title.trim()) { toast.error("Title required"); return; }
    try {
      if (editing) {
        await axios.put(`${API}/compliance/items/${pid}/${editing.id}`, form);
        toast.success("Updated");
      } else {
        await axios.post(`${API}/compliance/items/${pid}`, form);
        toast.success("Created");
      }
      setOpen(false);
      load();
    } catch { toast.error("Failed"); }
  };

  const markChecked = async (id) => {
    try {
      await axios.post(`${API}/compliance/items/${pid}/${id}/check`);
      toast.success("Marked as checked");
      load();
    } catch { toast.error("Failed"); }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this compliance item?")) return;
    try {
      await axios.delete(`${API}/compliance/items/${pid}/${id}`);
      toast.success("Deleted");
      load();
    } catch { toast.error("Failed"); }
  };

  const k = data.kpis;

  return (
    <div className="space-y-5" data-testid="compliance-register">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <FolderCheck className="w-5 h-5 text-stone-700" />
          <h2 className="text-base font-bold text-stone-800" data-testid="compliance-title">Compliance Register</h2>
        </div>
        {isManager && (
          <Button size="sm" onClick={openNew} className="bg-stone-800 hover:bg-stone-700 text-white" data-testid="new-compliance-btn">
            <Plus className="w-4 h-4 mr-1.5" />New Item
          </Button>
        )}
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-5 gap-3" data-testid="compliance-kpis">
        <div className="bg-stone-50 border border-stone-200 rounded-xl p-4 text-center"><p className="text-2xl font-black text-stone-700">{k.total || 0}</p><p className="text-[10px] text-stone-500">Total Items</p></div>
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-center"><CheckCircle2 className="w-4 h-4 mx-auto mb-1 text-emerald-600" /><p className="text-2xl font-black text-emerald-700">{k.compliant || 0}</p><p className="text-[10px] text-emerald-600">Compliant</p></div>
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-center"><Clock className="w-4 h-4 mx-auto mb-1 text-amber-600" /><p className="text-2xl font-black text-amber-700">{k.expiring_soon || 0}</p><p className="text-[10px] text-amber-600">Expiring ≤30d</p></div>
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-center"><AlertTriangle className="w-4 h-4 mx-auto mb-1 text-red-600" /><p className="text-2xl font-black text-red-700">{k.overdue || 0}</p><p className="text-[10px] text-red-600">Overdue</p></div>
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-center"><AlertCircle className="w-4 h-4 mx-auto mb-1 text-blue-600" /><p className="text-2xl font-black text-blue-700">{k.action_needed || 0}</p><p className="text-[10px] text-blue-600">Action Needed</p></div>
      </div>

      {/* Categories */}
      <div className="flex items-center gap-2 flex-wrap" data-testid="compliance-categories">
        <button onClick={() => setActiveCat("")} data-testid="cat-all"
          className={`px-3 py-1.5 text-xs font-semibold rounded-lg border transition ${!activeCat ? "bg-stone-800 text-white border-stone-800" : "bg-white text-stone-600 border-stone-200 hover:border-stone-400"}`}>
          All Categories
        </button>
        {categories.map(c => {
          const Icon = ICON_MAP[c.icon] || Shield;
          const sel = activeCat === c.id;
          return (
            <button key={c.id} onClick={() => setActiveCat(sel ? "" : c.id)} data-testid={`cat-${c.id}`}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg border transition flex items-center gap-1.5 ${sel ? "text-white border-transparent" : "bg-white border-stone-200 hover:border-stone-400"}`}
              style={sel ? { backgroundColor: c.color } : { color: c.color }}>
              <Icon className="w-3.5 h-3.5" />{c.name}
              {(c.overdue > 0 || c.expiring_soon > 0) && (
                <span className={`ml-0.5 text-[9px] font-bold rounded-full px-1.5 ${sel ? "bg-white/20" : "bg-red-500 text-white"}`}>
                  {c.overdue + c.expiring_soon}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Status filter */}
      <div className="flex items-center gap-1 bg-stone-100 rounded-lg p-0.5 w-fit">
        {["", "compliant", "expiring_soon", "overdue", "action_needed"].map(s => (
          <button key={s || "all"} onClick={() => setActiveStatus(s)} data-testid={`status-${s || "all"}`}
            className={`px-3 py-1 text-[11px] font-semibold rounded-md capitalize ${activeStatus === s ? "bg-white text-stone-800 shadow-sm" : "text-stone-500"}`}>
            {s ? STATUS_STYLE[s]?.label : "All"}
          </button>
        ))}
      </div>

      {/* Items Table */}
      {loading ? (
        <div className="flex items-center justify-center py-20 text-stone-400"><RefreshCw className="w-5 h-5 animate-spin mr-2" />Loading...</div>
      ) : data.items.length === 0 ? (
        <div className="text-center py-16 text-stone-400" data-testid="empty-state">
          <FolderCheck className="w-10 h-10 mx-auto mb-3 opacity-40" />
          <p className="text-sm">No compliance items yet. Add your first to track deadlines.</p>
        </div>
      ) : (
        <div className="bg-white border border-stone-200 rounded-xl overflow-hidden" data-testid="compliance-table">
          <table className="w-full text-xs">
            <thead className="bg-stone-50 border-b border-stone-200">
              <tr>
                <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Title</th>
                <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Category</th>
                <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Status</th>
                <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Due Date</th>
                <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Last Checked</th>
                <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Frequency</th>
                <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Assigned</th>
                <th className="text-right py-2.5 px-3 font-semibold text-stone-600">Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map(item => {
                const style = STATUS_STYLE[item.computed_status] || STATUS_STYLE.action_needed;
                const cat = categories.find(c => c.id === item.category);
                const Icon = style.icon;
                return (
                  <tr key={item.id} className="border-b border-stone-100 hover:bg-stone-50/50" data-testid={`compliance-row-${item.id}`}>
                    <td className="py-2.5 px-3">
                      <div className="font-semibold text-stone-700">{item.title}</div>
                      {item.description && <div className="text-[10px] text-stone-400 truncate max-w-xs">{item.description}</div>}
                    </td>
                    <td className="py-2.5 px-3">
                      {cat && <Badge className="text-[9px]" style={{ backgroundColor: `${cat.color}20`, color: cat.color }}>{cat.name}</Badge>}
                    </td>
                    <td className="py-2.5 px-3">
                      <Badge className={`${style.color} border text-[9px]`}><Icon className="w-2.5 h-2.5 inline mr-1" />{style.label}</Badge>
                    </td>
                    <td className="py-2.5 px-3 text-stone-600">{item.due_date || "—"}</td>
                    <td className="py-2.5 px-3 text-stone-600">{item.last_checked || "—"}</td>
                    <td className="py-2.5 px-3 text-stone-600 capitalize">{item.frequency}</td>
                    <td className="py-2.5 px-3 text-stone-600">{item.assigned_to || "—"}</td>
                    <td className="py-2.5 px-3 text-right">
                      <div className="inline-flex items-center gap-0.5">
                        {item.evidence_url && (
                          <a href={item.evidence_url} target="_blank" rel="noopener noreferrer" className="p-1.5 hover:bg-stone-100 rounded" title="View evidence">
                            <ExternalLink className="w-3 h-3 text-blue-500" />
                          </a>
                        )}
                        <button onClick={() => markChecked(item.id)} className="p-1.5 hover:bg-emerald-50 rounded" title="Mark as checked today" data-testid={`check-btn-${item.id}`}>
                          <CheckCircle2 className="w-3 h-3 text-emerald-500" />
                        </button>
                        {isManager && (
                          <>
                            <button onClick={() => openEdit(item)} className="p-1.5 hover:bg-stone-100 rounded"><Edit3 className="w-3 h-3 text-stone-500" /></button>
                            <button onClick={() => remove(item.id)} className="p-1.5 hover:bg-red-50 rounded"><Trash2 className="w-3 h-3 text-red-500" /></button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Dialog */}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editing ? "Edit" : "New"} Compliance Item</DialogTitle>
            <DialogDescription>Track regulatory, safety, and operational obligations.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <label className="text-xs font-semibold text-stone-600">Title</label>
              <Input value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} placeholder="e.g. Fire Extinguisher Annual Inspection" data-testid="compliance-title-input" />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs font-semibold text-stone-600">Category</label>
                <Select value={form.category} onValueChange={v => setForm({ ...form, category: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {categories.map(c => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-xs font-semibold text-stone-600">Frequency</label>
                <Select value={form.frequency} onValueChange={v => setForm({ ...form, frequency: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="weekly">Weekly</SelectItem>
                    <SelectItem value="monthly">Monthly</SelectItem>
                    <SelectItem value="quarterly">Quarterly</SelectItem>
                    <SelectItem value="annual">Annual</SelectItem>
                    <SelectItem value="once">One-off</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs font-semibold text-stone-600">Due Date</label>
                <Input type="date" value={form.due_date} onChange={e => setForm({ ...form, due_date: e.target.value })} data-testid="compliance-due-input" />
              </div>
              <div>
                <label className="text-xs font-semibold text-stone-600">Last Checked</label>
                <Input type="date" value={form.last_checked || ""} onChange={e => setForm({ ...form, last_checked: e.target.value })} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs font-semibold text-stone-600">Assigned To</label>
                <Input value={form.assigned_to} onChange={e => setForm({ ...form, assigned_to: e.target.value })} placeholder="Staff name" />
              </div>
              <div>
                <label className="text-xs font-semibold text-stone-600">Status</label>
                <Select value={form.status} onValueChange={v => setForm({ ...form, status: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="compliant">Compliant</SelectItem>
                    <SelectItem value="action_needed">Action Needed</SelectItem>
                    <SelectItem value="not_applicable">Not Applicable</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div>
              <label className="text-xs font-semibold text-stone-600">Evidence URL</label>
              <Input value={form.evidence_url} onChange={e => setForm({ ...form, evidence_url: e.target.value })} placeholder="https://... (certificate, photo, document)" />
            </div>
            <div>
              <label className="text-xs font-semibold text-stone-600">Description</label>
              <Textarea value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} rows={2} />
            </div>
            <div>
              <label className="text-xs font-semibold text-stone-600">Notes</label>
              <Textarea value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} rows={2} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" size="sm" onClick={() => setOpen(false)}>Cancel</Button>
            <Button size="sm" className="bg-stone-800 hover:bg-stone-700 text-white" onClick={submit} data-testid="compliance-submit-btn">
              {editing ? "Update" : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};
