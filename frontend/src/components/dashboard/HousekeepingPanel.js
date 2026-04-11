import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import {
  Broom, Bed, CheckCircle, WarningCircle, Wrench, Plus,
  ArrowsClockwise, Clock, X,
} from "@phosphor-icons/react";
import { Badge } from "@/components/ui/badge";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STATUS_CONFIG = {
  clean: { label: "Clean", color: "bg-emerald-100 text-emerald-700 border-emerald-200", dot: "bg-emerald-500" },
  dirty: { label: "Dirty", color: "bg-red-100 text-red-700 border-red-200", dot: "bg-red-500" },
  inspected: { label: "Inspected", color: "bg-blue-100 text-blue-700 border-blue-200", dot: "bg-blue-500" },
  in_progress: { label: "In Progress", color: "bg-amber-100 text-amber-700 border-amber-200", dot: "bg-amber-500" },
  out_of_order: { label: "Out of Order", color: "bg-stone-200 text-stone-600 border-stone-300", dot: "bg-stone-500" },
};

export function HousekeepingPanel({ properties, activePropertyId }) {
  const [rooms, setRooms] = useState([]);
  const [stats, setStats] = useState({});
  const [tasks, setTasks] = useState([]);
  const [maintenance, setMaintenance] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");
  const [tab, setTab] = useState("rooms");

  const propertyId = activePropertyId && activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "city-gate");

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
    } catch (err) {
      console.error(err);
    } finally { setLoading(false); }
  }, [propertyId, filter]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const updateRoomStatus = async (roomId, newStatus) => {
    try {
      await axios.put(`${API}/housekeeping/rooms/${roomId}/status`, { status: newStatus });
      fetchData();
    } catch (err) { console.error(err); }
  };

  const seedRooms = async () => {
    await axios.post(`${API}/housekeeping/rooms/seed/${propertyId}`);
    fetchData();
  };

  const createTask = async (roomNumber, roomTypeId) => {
    await axios.post(`${API}/housekeeping/tasks`, {
      property_id: propertyId, room_number: roomNumber, room_type_id: roomTypeId,
      task_type: "cleaning", priority: "normal", status: "pending",
    });
    fetchData();
  };

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-5" data-testid="housekeeping-panel">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-stone-900 flex items-center gap-2" data-testid="housekeeping-title">
            <Broom size={22} className="text-teal-500" weight="fill" />
            Housekeeping
          </h1>
          <p className="text-sm text-stone-500 mt-0.5">Room status board, tasks & maintenance</p>
        </div>
        <div className="flex items-center gap-2">
          {rooms.length === 0 && (
            <button onClick={seedRooms} className="text-xs px-3 py-1.5 bg-teal-50 text-teal-700 rounded-lg hover:bg-teal-100 font-medium" data-testid="seed-rooms-btn">
              <Plus size={12} className="inline mr-1" /> Seed Rooms
            </button>
          )}
          <button onClick={fetchData} className="h-8 w-8 flex items-center justify-center rounded-lg border border-stone-200 hover:bg-stone-50" data-testid="refresh-hk-btn">
            <ArrowsClockwise size={14} className="text-stone-500" />
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
        {Object.entries(STATUS_CONFIG).map(([key, cfg]) => (
          <button key={key} onClick={() => setFilter(filter === key ? "all" : key)}
            className={`p-2.5 rounded-lg border text-center transition-all ${filter === key ? "ring-2 ring-offset-1 ring-teal-400" : ""} ${cfg.color}`}
            data-testid={`filter-${key}`}>
            <div className="text-lg font-bold">{stats[key] || 0}</div>
            <div className="text-[10px] uppercase tracking-wider font-semibold">{cfg.label}</div>
          </button>
        ))}
        <button onClick={() => setFilter("all")}
          className={`p-2.5 rounded-lg border text-center bg-stone-50 text-stone-700 border-stone-200 ${filter === "all" ? "ring-2 ring-offset-1 ring-teal-400" : ""}`}>
          <div className="text-lg font-bold">{stats.total || 0}</div>
          <div className="text-[10px] uppercase tracking-wider font-semibold">Total</div>
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-stone-200">
        {[
          { id: "rooms", label: "Room Board", icon: Bed },
          { id: "tasks", label: `Tasks (${tasks.length})`, icon: CheckCircle },
          { id: "maintenance", label: `Maintenance (${maintenance.length})`, icon: Wrench },
        ].map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`px-4 py-2.5 text-xs font-medium flex items-center gap-1.5 border-b-2 transition-colors ${
              tab === t.id ? "border-teal-500 text-teal-700" : "border-transparent text-stone-400 hover:text-stone-600"
            }`} data-testid={`tab-${t.id}`}>
            <t.icon size={14} /> {t.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center py-16"><ArrowsClockwise size={24} className="animate-spin text-stone-300" /></div>
      ) : (
        <>
          {tab === "rooms" && (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2" data-testid="room-board">
              {rooms.map(room => {
                const cfg = STATUS_CONFIG[room.status] || STATUS_CONFIG.clean;
                return (
                  <div key={room.id} className={`border rounded-xl p-3 transition-all hover:shadow-sm ${cfg.color}`} data-testid={`room-${room.room_number}`}>
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-sm font-bold">{room.room_number}</span>
                      <div className={`w-2.5 h-2.5 rounded-full ${cfg.dot}`} />
                    </div>
                    <div className="text-[10px] opacity-70 mb-2">Floor {room.floor}</div>
                    <Select value={room.status} onValueChange={(v) => updateRoomStatus(room.id, v)}>
                      <SelectTrigger className="h-7 text-[10px] bg-white/50 border-0">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {Object.entries(STATUS_CONFIG).map(([k, c]) => (
                          <SelectItem key={k} value={k}><span className="text-xs">{c.label}</span></SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {room.status === "dirty" && (
                      <button onClick={() => createTask(room.room_number, room.room_type_id)}
                        className="w-full mt-1.5 text-[10px] py-1 bg-white/60 rounded text-center hover:bg-white/80 font-medium">
                        + Assign Task
                      </button>
                    )}
                  </div>
                );
              })}
              {rooms.length === 0 && (
                <div className="col-span-full text-center py-12 text-stone-400 text-sm">
                  No rooms found. Click "Seed Rooms" to generate sample data.
                </div>
              )}
            </div>
          )}

          {tab === "tasks" && (
            <div className="space-y-2" data-testid="tasks-list">
              {tasks.length === 0 ? (
                <div className="text-center py-12 text-stone-400 text-sm">No tasks yet</div>
              ) : tasks.map(task => (
                <div key={task.id} className="bg-white border border-stone-200 rounded-xl p-3 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${task.status === "completed" ? "bg-emerald-50" : "bg-amber-50"}`}>
                      {task.status === "completed" ? <CheckCircle size={16} className="text-emerald-500" weight="fill" /> : <Clock size={16} className="text-amber-500" />}
                    </div>
                    <div>
                      <div className="text-xs font-semibold text-stone-800">Room {task.room_number} — {task.task_type}</div>
                      <div className="text-[10px] text-stone-400">{task.priority} priority · {task.assigned_name || "Unassigned"}</div>
                    </div>
                  </div>
                  <Badge variant="outline" className="text-[10px]">{task.status}</Badge>
                </div>
              ))}
            </div>
          )}

          {tab === "maintenance" && (
            <div className="space-y-2" data-testid="maintenance-list">
              {maintenance.length === 0 ? (
                <div className="text-center py-12 text-stone-400 text-sm">No maintenance requests</div>
              ) : maintenance.map(req => (
                <div key={req.id} className="bg-white border border-stone-200 rounded-xl p-3 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-red-50">
                      <Wrench size={16} className="text-red-500" />
                    </div>
                    <div>
                      <div className="text-xs font-semibold text-stone-800">Room {req.room_number} — {req.category}</div>
                      <div className="text-[10px] text-stone-400 truncate max-w-[300px]">{req.description}</div>
                    </div>
                  </div>
                  <Badge variant="outline" className={`text-[10px] ${req.status === "resolved" ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}>
                    {req.status}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
