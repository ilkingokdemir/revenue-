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
  DialogFooter,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import {
  RefreshCw, Plus, AlertTriangle, CheckCircle2, Archive, Trash2,
  MessageSquare, Clock, User, Siren, ArrowRightLeft, Filter,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const PRIORITY_STYLE = {
  critical: { bg: "bg-red-50 border-red-300", badge: "bg-red-500 text-white", icon: "text-red-500" },
  high:     { bg: "bg-amber-50 border-amber-300", badge: "bg-amber-500 text-white", icon: "text-amber-500" },
  normal:   { bg: "bg-stone-50 border-stone-200", badge: "bg-stone-400 text-white", icon: "text-stone-500" },
  low:      { bg: "bg-blue-50 border-blue-200", badge: "bg-blue-400 text-white", icon: "text-blue-500" },
};
const CATEGORY_STYLE = {
  general: "bg-stone-100 text-stone-600",
  maintenance: "bg-amber-100 text-amber-700",
  guest: "bg-violet-100 text-violet-700",
  housekeeping: "bg-blue-100 text-blue-700",
  reception: "bg-emerald-100 text-emerald-700",
  finance: "bg-rose-100 text-rose-700",
};
const SHIFT_LABEL = { morning: "Morning", afternoon: "Afternoon", evening: "Evening", night: "Night" };

export const PassOverDuties = ({ propertyId, user }) => {
  const [data, setData] = useState({ items: [], counts: {}, total: 0 });
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("open");
  const [priorityFilter, setPriorityFilter] = useState("all");
  const [open, setOpen] = useState(false);
  const [staffList, setStaffList] = useState([]);
  const [form, setForm] = useState({
    title: "", message: "", priority: "normal", category: "general", shift: "morning", mentions: [],
  });

  const pid = propertyId || "all";

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = [];
      if (statusFilter !== "all") params.push(`status=${statusFilter}`);
      if (priorityFilter !== "all") params.push(`priority=${priorityFilter}`);
      const qs = params.length ? `?${params.join("&")}` : "";
      const { data: d } = await axios.get(`${API}/operations/pass-over/${pid}${qs}`);
      setData(d);
    } catch { /* silent */ }
    setLoading(false);
  }, [pid, statusFilter, priorityFilter]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    axios.get(`${API}/users`).then(r => setStaffList(r.data || [])).catch(() => {});
  }, []);

  const submit = async () => {
    if (!form.title.trim()) {
      toast.error("Title required");
      return;
    }
    try {
      await axios.post(`${API}/operations/pass-over/${pid}`, form);
      toast.success("Pass-over created");
      setOpen(false);
      setForm({ title: "", message: "", priority: "normal", category: "general", shift: "morning", mentions: [] });
      load();
    } catch {
      toast.error("Failed to create pass-over");
    }
  };

  const acknowledge = async (id) => {
    try {
      await axios.post(`${API}/operations/pass-over/${pid}/${id}/acknowledge`);
      toast.success("Acknowledged");
      load();
    } catch { toast.error("Failed"); }
  };
  const archive = async (id) => {
    try {
      await axios.post(`${API}/operations/pass-over/${pid}/${id}/archive`);
      toast.success("Archived");
      load();
    } catch { toast.error("Failed"); }
  };
  const remove = async (id) => {
    if (!window.confirm("Delete this pass-over?")) return;
    try {
      await axios.delete(`${API}/operations/pass-over/${pid}/${id}`);
      toast.success("Deleted");
      load();
    } catch { toast.error("Failed"); }
  };

  const toggleMention = (name) => {
    setForm(f => ({
      ...f,
      mentions: f.mentions.includes(name) ? f.mentions.filter(n => n !== name) : [...f.mentions, name],
    }));
  };

  const counts = data.counts || {};
  const isManager = user?.role === "admin" || user?.role === "manager";

  return (
    <div className="space-y-5" data-testid="pass-over-duties">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <ArrowRightLeft className="w-5 h-5 text-stone-700" />
          <h2 className="text-base font-bold text-stone-800" data-testid="pass-over-title">Pass Over Duties</h2>
          <Badge className="bg-stone-100 text-stone-600 text-[10px]">{data.total} total</Badge>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button size="sm" className="bg-stone-800 hover:bg-stone-700 text-white" data-testid="new-pass-over-btn">
              <Plus className="w-4 h-4 mr-1.5" />New Pass Over
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg">
            <DialogHeader><DialogTitle>Create Shift Handover</DialogTitle></DialogHeader>
            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-stone-600">Title</label>
                <Input value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} placeholder="e.g. Room 204 boiler issue" data-testid="pass-over-title-input" />
              </div>
              <div>
                <label className="text-xs font-semibold text-stone-600">Message / Instructions</label>
                <Textarea value={form.message} onChange={e => setForm({ ...form, message: e.target.value })} rows={4} placeholder="Details of what the next shift needs to know or action..." data-testid="pass-over-message-input" />
              </div>
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="text-xs font-semibold text-stone-600">Priority</label>
                  <Select value={form.priority} onValueChange={v => setForm({ ...form, priority: v })}>
                    <SelectTrigger data-testid="pass-over-priority-select"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="low">Low</SelectItem>
                      <SelectItem value="normal">Normal</SelectItem>
                      <SelectItem value="high">High</SelectItem>
                      <SelectItem value="critical">Critical</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label className="text-xs font-semibold text-stone-600">Category</label>
                  <Select value={form.category} onValueChange={v => setForm({ ...form, category: v })}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="general">General</SelectItem>
                      <SelectItem value="maintenance">Maintenance</SelectItem>
                      <SelectItem value="guest">Guest</SelectItem>
                      <SelectItem value="housekeeping">Housekeeping</SelectItem>
                      <SelectItem value="reception">Reception</SelectItem>
                      <SelectItem value="finance">Finance</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label className="text-xs font-semibold text-stone-600">Shift</label>
                  <Select value={form.shift} onValueChange={v => setForm({ ...form, shift: v })}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="morning">Morning</SelectItem>
                      <SelectItem value="afternoon">Afternoon</SelectItem>
                      <SelectItem value="evening">Evening</SelectItem>
                      <SelectItem value="night">Night</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div>
                <label className="text-xs font-semibold text-stone-600">Mention Staff ({form.mentions.length})</label>
                <div className="flex flex-wrap gap-1.5 mt-1 max-h-24 overflow-y-auto p-2 bg-stone-50 rounded-lg">
                  {staffList.length === 0 && <span className="text-[10px] text-stone-400">No staff loaded</span>}
                  {staffList.map(s => {
                    const name = s.name || s.email;
                    const sel = form.mentions.includes(name);
                    return (
                      <button key={s.id || s.email} onClick={() => toggleMention(name)} type="button"
                        className={`px-2 py-0.5 text-[10px] rounded-full border transition ${sel ? "bg-stone-800 text-white border-stone-800" : "bg-white text-stone-600 border-stone-200 hover:border-stone-400"}`}>
                        @{name}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" size="sm" onClick={() => setOpen(false)}>Cancel</Button>
              <Button size="sm" className="bg-stone-800 hover:bg-stone-700 text-white" onClick={submit} data-testid="pass-over-submit-btn">Create</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2 flex-wrap">
        <div className="flex items-center gap-1 bg-stone-100 rounded-lg p-0.5">
          {["open", "acknowledged", "archived", "all"].map(s => (
            <button key={s} onClick={() => setStatusFilter(s)} data-testid={`filter-status-${s}`}
              className={`px-3 py-1 text-[11px] font-semibold rounded-md capitalize ${statusFilter === s ? "bg-white text-stone-800 shadow-sm" : "text-stone-500"}`}>
              {s} {counts[s] !== undefined ? `(${counts[s]})` : ""}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1 bg-stone-100 rounded-lg p-0.5">
          <Filter className="w-3 h-3 text-stone-400 ml-1.5" />
          {["all", "critical", "high", "normal", "low"].map(p => (
            <button key={p} onClick={() => setPriorityFilter(p)}
              className={`px-2.5 py-1 text-[11px] font-semibold rounded-md capitalize ${priorityFilter === p ? "bg-white text-stone-800 shadow-sm" : "text-stone-500"}`}>
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* Cards */}
      {loading ? (
        <div className="flex items-center justify-center py-20 text-stone-400">
          <RefreshCw className="w-5 h-5 animate-spin mr-2" />Loading...
        </div>
      ) : data.items.length === 0 ? (
        <div className="text-center py-16 text-stone-400" data-testid="empty-state">
          <MessageSquare className="w-10 h-10 mx-auto mb-3 opacity-40" />
          <p className="text-sm">No pass-overs found. Create one to hand over to the next shift.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3" data-testid="pass-over-list">
          {data.items.map(item => {
            const style = PRIORITY_STYLE[item.priority] || PRIORITY_STYLE.normal;
            return (
              <div key={item.id} className={`border-2 rounded-xl p-4 ${style.bg}`} data-testid={`pass-over-card-${item.id}`}>
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-start gap-2 flex-1 min-w-0">
                    {item.priority === "critical" ? <Siren className={`w-5 h-5 flex-shrink-0 ${style.icon}`} />
                      : item.priority === "high" ? <AlertTriangle className={`w-5 h-5 flex-shrink-0 ${style.icon}`} />
                      : <MessageSquare className={`w-5 h-5 flex-shrink-0 ${style.icon}`} />}
                    <div className="flex-1 min-w-0">
                      <h4 className="text-sm font-bold text-stone-800 truncate">{item.title}</h4>
                      <div className="flex items-center gap-1.5 mt-1 flex-wrap">
                        <Badge className={`${style.badge} text-[9px] uppercase`}>{item.priority}</Badge>
                        <Badge className={`${CATEGORY_STYLE[item.category] || "bg-stone-100 text-stone-600"} text-[9px] capitalize`}>{item.category}</Badge>
                        {item.shift && <Badge className="bg-white border border-stone-200 text-stone-600 text-[9px]">{SHIFT_LABEL[item.shift] || item.shift}</Badge>}
                        {item.status === "acknowledged" && <Badge className="bg-emerald-100 text-emerald-700 text-[9px]"><CheckCircle2 className="w-2.5 h-2.5 inline mr-0.5" />Acknowledged</Badge>}
                        {item.status === "archived" && <Badge className="bg-stone-200 text-stone-600 text-[9px]">Archived</Badge>}
                      </div>
                    </div>
                  </div>
                </div>
                {item.message && <p className="text-xs text-stone-600 mt-2 whitespace-pre-wrap line-clamp-4">{item.message}</p>}
                {item.mentions?.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {item.mentions.map((m, i) => <span key={i} className="text-[10px] px-1.5 py-0.5 bg-white border border-stone-200 rounded text-stone-600">@{m}</span>)}
                  </div>
                )}
                <div className="flex items-center justify-between mt-3 pt-2 border-t border-stone-200/70">
                  <div className="flex items-center gap-2 text-[10px] text-stone-500">
                    <span className="flex items-center gap-1"><User className="w-3 h-3" />{item.from_user}</span>
                    <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{item.created_at?.slice(0, 16).replace("T", " ")}</span>
                    {item.acknowledgements?.length > 0 && <span className="flex items-center gap-1 text-emerald-600 font-semibold"><CheckCircle2 className="w-3 h-3" />{item.acknowledgements.length} ack</span>}
                  </div>
                  <div className="flex items-center gap-1">
                    {item.status !== "acknowledged" && item.status !== "archived" && (
                      <Button size="sm" variant="outline" className="h-6 text-[10px] px-2" onClick={() => acknowledge(item.id)} data-testid={`ack-btn-${item.id}`}>
                        <CheckCircle2 className="w-3 h-3 mr-1" />Ack
                      </Button>
                    )}
                    {isManager && item.status !== "archived" && (
                      <Button size="sm" variant="ghost" className="h-6 text-[10px] px-2 text-stone-500" onClick={() => archive(item.id)}>
                        <Archive className="w-3 h-3" />
                      </Button>
                    )}
                    {isManager && (
                      <Button size="sm" variant="ghost" className="h-6 text-[10px] px-2 text-red-500" onClick={() => remove(item.id)}>
                        <Trash2 className="w-3 h-3" />
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
