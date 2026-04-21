import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { motion } from "framer-motion";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import {
  Broom, Bed, CheckCircle, WarningCircle, Wrench, Plus,
  ArrowsClockwise, Clock, X, User, Eye, Lightning,
} from "@phosphor-icons/react";
import { RefreshCw, Search, Filter, Users, ClipboardCheck, AlertTriangle } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STATUS_CONFIG = {
  clean: { label: "Clean", color: "bg-emerald-100 text-emerald-700 border-emerald-300", dot: "bg-emerald-500", ring: "ring-emerald-300" },
  dirty: { label: "Dirty", color: "bg-red-100 text-red-700 border-red-300", dot: "bg-red-500", ring: "ring-red-300" },
  inspected: { label: "Inspected", color: "bg-blue-100 text-blue-700 border-blue-300", dot: "bg-blue-500", ring: "ring-blue-300" },
  in_progress: { label: "Cleaning", color: "bg-amber-100 text-amber-700 border-amber-300", dot: "bg-amber-500", ring: "ring-amber-300" },
  out_of_order: { label: "OOO", color: "bg-stone-200 text-stone-600 border-stone-300", dot: "bg-stone-500", ring: "ring-stone-300" },
};

const PRIORITY_COLORS = { urgent: "bg-red-100 text-red-700", high: "bg-orange-100 text-orange-700", normal: "bg-blue-100 text-blue-700", low: "bg-stone-100 text-stone-600" };

export function HousekeepingPanel({ properties, activePropertyId }) {
  const [rooms, setRooms] = useState([]);
  const [stats, setStats] = useState({});
  const [tasks, setTasks] = useState([]);
  const [maintenance, setMaintenance] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");
  const [tab, setTab] = useState("rooms");
  const [search, setSearch] = useState("");
  const [showNewTask, setShowNewTask] = useState(false);
  const [newTask, setNewTask] = useState({ room_number: "", task_type: "clean", assigned_to: "", priority: "normal", notes: "" });

  const propertyId = activePropertyId && activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "aldgate-flats");

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const statusParam = filter !== "all" ? `?status=${filter}` : "";
      const [roomsRes, statsRes, tasksRes, maintRes] = await Promise.all([
        axios.get(`${API}/housekeeping/rooms/${propertyId}${statusParam}`),
        axios.get(`${API}/housekeeping/rooms/${propertyId}/stats`),
        axios.get(`${API}/housekeeping/tasks/${propertyId}`),
        axios.get(`${API}/housekeeping/maintenance/${propertyId}`),
      ]);
      setRooms(roomsRes.data);
      setStats(statsRes.data);
      setTasks(tasksRes.data);
      setMaintenance(maintRes.data);
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  }, [propertyId, filter]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const updateStatus = async (roomId, status) => {
    try {
      await axios.put(`${API}/housekeeping/rooms/${roomId}/status`, { status });
      toast.success(`Room marked ${status}`);
      fetchData();
    } catch (e) { toast.error("Failed"); }
  };

  const createTask = async () => {
    try {
      await axios.post(`${API}/housekeeping/tasks`, { ...newTask, property_id: propertyId });
      toast.success("Task created"); setShowNewTask(false);
      setNewTask({ room_number: "", task_type: "clean", assigned_to: "", priority: "normal", notes: "" });
      fetchData();
    } catch (e) { toast.error("Failed"); }
  };

  const filteredRooms = rooms.filter(r => !search || r.room_number?.toString().includes(search) || r.floor?.includes(search));

  const tabs = [
    { id: "rooms", label: "Room Board", icon: Bed },
    { id: "tasks", label: `Tasks (${tasks.length})`, icon: ClipboardCheck },
    { id: "maintenance", label: `Maintenance (${maintenance.length})`, icon: Wrench },
  ];

  if (loading) return <div className="flex items-center justify-center h-96"><ArrowsClockwise size={24} className="animate-spin text-stone-300" /></div>;

  return (
    <div className="h-full flex flex-col" data-testid="housekeeping-panel">
      {/* Header */}
      <div className="border-b border-stone-200 bg-white px-6 py-4 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-orange-500 flex items-center justify-center"><Broom size={18} className="text-white" weight="fill" /></div>
          <div><h2 className="text-lg font-bold text-stone-900" style={{ fontFamily: "Outfit, sans-serif" }}>Housekeeping</h2><p className="text-[11px] text-stone-500">Room status, cleaning tasks, maintenance</p></div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setShowNewTask(true)} className="text-xs px-3 py-2 bg-[#2C4C3B] text-white rounded-xl font-bold hover:bg-[#1A3025] flex items-center gap-1" data-testid="new-task-btn"><Plus size={12} /> New Task</button>
        </div>
      </div>

      {/* Stats Bar */}
      <div className="bg-white border-b border-stone-200 px-6 py-3 flex items-center gap-3 flex-shrink-0">
        {Object.entries(STATUS_CONFIG).map(([key, cfg]) => (
          <button key={key} onClick={() => setFilter(filter === key ? "all" : key)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[11px] font-bold border transition-all ${filter === key ? cfg.color + " " + cfg.ring + " ring-2" : "bg-white border-stone-200 text-stone-500 hover:border-stone-300"}`}
            data-testid={`filter-${key}`}>
            <div className={`w-2 h-2 rounded-full ${cfg.dot}`} />
            {cfg.label} ({stats[key] || 0})
          </button>
        ))}
        <div className="flex-1" />
        <div className="relative">
          <Input value={search} onChange={e => setSearch(e.target.value)} placeholder="Room #..." className="h-8 w-28 text-xs pl-7 bg-stone-50" />
          <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-stone-400" />
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white border-b border-stone-200 px-6 flex gap-1 flex-shrink-0">
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-semibold border-b-[3px] transition-all ${tab === t.id ? "border-orange-500 text-orange-600" : "border-transparent text-stone-400"}`}
            data-testid={`hk-tab-${t.id}`}><t.icon size={14} /> {t.label}</button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-6 bg-stone-50">
        {/* Room Board */}
        {tab === "rooms" && (
          <div data-testid="room-board">
            {filteredRooms.length === 0 ? (
              <div className="text-center py-16 text-stone-400"><Bed size={40} className="mx-auto mb-3" /><p className="text-sm">No rooms configured. Rooms are auto-created from bookings.</p></div>
            ) : (
              <div className="grid grid-cols-4 sm:grid-cols-6 lg:grid-cols-8 xl:grid-cols-10 gap-2.5">
                {filteredRooms.map(room => {
                  const cfg = STATUS_CONFIG[room.status] || STATUS_CONFIG.dirty;
                  return (
                    <motion.div key={room.id} whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
                      className={`rounded-xl border-2 p-3 text-center cursor-pointer transition-all hover:shadow-md ${cfg.color}`}
                      data-testid={`room-${room.room_number}`}>
                      <div className="text-lg font-black">{room.room_number}</div>
                      <div className="text-[9px] font-bold uppercase tracking-wider mt-0.5">{cfg.label}</div>
                      {room.floor && <div className="text-[8px] opacity-60 mt-0.5">Floor {room.floor}</div>}
                      <div className="flex justify-center gap-1 mt-2">
                        {room.status === "dirty" && (
                          <button onClick={() => updateStatus(room.id, "in_progress")} className="text-[8px] px-1.5 py-0.5 bg-white/60 rounded-md font-bold hover:bg-white/80">Start</button>
                        )}
                        {room.status === "in_progress" && (
                          <button onClick={() => updateStatus(room.id, "clean")} className="text-[8px] px-1.5 py-0.5 bg-white/60 rounded-md font-bold hover:bg-white/80">Done</button>
                        )}
                        {room.status === "clean" && (
                          <button onClick={() => updateStatus(room.id, "inspected")} className="text-[8px] px-1.5 py-0.5 bg-white/60 rounded-md font-bold hover:bg-white/80">Inspect</button>
                        )}
                      </div>
                    </motion.div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Tasks */}
        {tab === "tasks" && (
          <div className="space-y-2.5" data-testid="tasks-tab">
            {tasks.length === 0 ? (
              <div className="text-center py-16 text-stone-400"><ClipboardCheck size={40} className="mx-auto mb-3" /><p className="text-sm">No pending tasks</p></div>
            ) : tasks.map(task => (
              <div key={task.id} className="bg-white rounded-xl border border-stone-200 p-4 flex items-center justify-between shadow-sm" data-testid={`task-${task.id}`}>
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${task.status === "completed" ? "bg-emerald-100" : task.status === "in_progress" ? "bg-amber-100" : "bg-blue-100"}`}>
                    {task.status === "completed" ? <CheckCircle size={18} className="text-emerald-600" weight="fill" /> : <Broom size={18} className="text-blue-600" />}
                  </div>
                  <div>
                    <div className="text-sm font-bold text-stone-900">Room {task.room_number} — {task.task_type || task.type}</div>
                    <div className="text-[11px] text-stone-500 flex items-center gap-2">
                      {task.assigned_to && <span className="flex items-center gap-0.5"><User size={10} /> {task.assigned_to}</span>}
                      {task.notes && <span>{task.notes}</span>}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge className={`text-[9px] font-bold ${PRIORITY_COLORS[task.priority] || PRIORITY_COLORS.normal}`}>{task.priority}</Badge>
                  <Badge className={`text-[9px] font-bold ${task.status === "completed" ? "bg-emerald-100 text-emerald-700" : task.status === "in_progress" ? "bg-amber-100 text-amber-700" : "bg-blue-100 text-blue-700"}`}>{task.status}</Badge>
                  {task.status !== "completed" && (
                    <button onClick={async () => {
                      const next = task.status === "pending" ? "in_progress" : "completed";
                      await axios.put(`${API}/housekeeping/tasks/${task.id}`, { status: next });
                      toast.success(`Task ${next}`); fetchData();
                    }} className="text-[10px] px-2.5 py-1 bg-[#2C4C3B] text-white rounded-lg font-bold">
                      {task.status === "pending" ? "Start" : "Complete"}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Maintenance */}
        {tab === "maintenance" && (
          <div className="space-y-2.5" data-testid="maintenance-tab">
            {maintenance.length === 0 ? (
              <div className="text-center py-16 text-stone-400"><Wrench size={40} className="mx-auto mb-3" /><p className="text-sm">No maintenance requests</p></div>
            ) : maintenance.map(m => (
              <div key={m.id} className="bg-white rounded-xl border border-stone-200 p-4 flex items-center justify-between shadow-sm" data-testid={`maint-${m.id}`}>
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${m.status === "resolved" ? "bg-emerald-100" : "bg-orange-100"}`}>
                    {m.status === "resolved" ? <CheckCircle size={18} className="text-emerald-600" weight="fill" /> : <AlertTriangle size={18} className="text-orange-600" />}
                  </div>
                  <div>
                    <div className="text-sm font-bold text-stone-900">{m.title || m.description?.slice(0, 40)}</div>
                    <div className="text-[11px] text-stone-500">Room {m.room_number} · {m.category} · {m.description?.slice(0, 60)}</div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge className={`text-[9px] font-bold ${PRIORITY_COLORS[m.priority] || PRIORITY_COLORS.normal}`}>{m.priority}</Badge>
                  <Badge className={`text-[9px] font-bold ${m.status === "resolved" ? "bg-emerald-100 text-emerald-700" : m.status === "in_progress" ? "bg-amber-100 text-amber-700" : "bg-red-100 text-red-700"}`}>{m.status}</Badge>
                  {m.status !== "resolved" && (
                    <button onClick={async () => {
                      const next = m.status === "open" ? "in_progress" : "resolved";
                      await axios.put(`${API}/housekeeping/maintenance/${m.id}`, { status: next });
                      toast.success(`Request ${next}`); fetchData();
                    }} className="text-[10px] px-2.5 py-1 bg-orange-500 text-white rounded-lg font-bold">
                      {m.status === "open" ? "Assign" : "Resolve"}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* New Task Dialog */}
      <Dialog open={showNewTask} onOpenChange={setShowNewTask}>
        <DialogContent className="max-w-md" data-testid="new-task-dialog">
          <DialogHeader><DialogTitle>New Cleaning Task</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <Input value={newTask.room_number} onChange={e => setNewTask(p => ({...p, room_number: e.target.value}))} placeholder="Room Number" data-testid="task-room" />
            <Select value={newTask.task_type} onValueChange={v => setNewTask(p => ({...p, task_type: v}))}>
              <SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="clean">Full Clean</SelectItem>
                <SelectItem value="turndown">Turndown Service</SelectItem>
                <SelectItem value="deep_clean">Deep Clean</SelectItem>
                <SelectItem value="inspection">Inspection</SelectItem>
              </SelectContent>
            </Select>
            <Input value={newTask.assigned_to} onChange={e => setNewTask(p => ({...p, assigned_to: e.target.value}))} placeholder="Assigned to (staff name)" />
            <Select value={newTask.priority} onValueChange={v => setNewTask(p => ({...p, priority: v}))}>
              <SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="urgent">Urgent</SelectItem>
                <SelectItem value="high">High</SelectItem>
                <SelectItem value="normal">Normal</SelectItem>
                <SelectItem value="low">Low</SelectItem>
              </SelectContent>
            </Select>
            <Textarea value={newTask.notes} onChange={e => setNewTask(p => ({...p, notes: e.target.value}))} placeholder="Notes..." rows={2} />
            <button onClick={createTask} className="w-full bg-[#2C4C3B] text-white py-2.5 rounded-xl text-sm font-bold" data-testid="create-task-btn">Create Task</button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
