import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import {
  RefreshCw, ChevronLeft, ChevronRight, Calendar, Clock, Users, Play,
  CheckCircle, Trash2, Copy
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const ROLE_COLORS = { receptionist: "bg-emerald-100 text-emerald-700", housekeeper: "bg-blue-100 text-blue-700", maintenance: "bg-amber-100 text-amber-700" };
const STATUS_COLORS = { planned: "bg-stone-200", published: "bg-blue-200", approved: "bg-emerald-200", completed: "bg-violet-200" };
const PRESETS = [
  { id: "morning", label: "Morning", time: "07:00-15:00", color: "#22c55e" },
  { id: "afternoon", label: "Afternoon", time: "12:00-20:00", color: "#06b6d4" },
  { id: "evening", label: "Evening", time: "15:00-23:00", color: "#8b5cf6" },
  { id: "full", label: "Full Day", time: "09:00-17:00", color: "#f59e0b" },
];

export const ShiftScheduler = ({ propertyId }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [weekStart, setWeekStart] = useState(() => {
    const d = new Date(); d.setDate(d.getDate() - d.getDay() + 1);
    return d.toISOString().slice(0, 10);
  });
  const [roleFilter, setRoleFilter] = useState("all");
  const pid = propertyId || "all";

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data: d } = await axios.get(`${API}/operations/shifts/${pid}?week_start=${weekStart}`);
      setData(d);
    } catch { /* silent */ }
    setLoading(false);
  }, [pid, weekStart]);

  useEffect(() => { load(); }, [load]);

  const assignShift = async (staffId, date, preset) => {
    try {
      await axios.post(`${API}/operations/shifts/${pid}/assign`, { staff_id: staffId, date, preset });
      toast.success("Shift assigned");
      load();
    } catch { toast.error("Failed"); }
  };

  const bulkPublish = async (action) => {
    try {
      const { data: r } = await axios.post(`${API}/operations/shifts/${pid}/bulk-publish`, { week_start: weekStart, action });
      toast.success(`${r.updated} shifts ${r.status}`);
      load();
    } catch { toast.error("Failed"); }
  };

  const clearWeek = async () => {
    try {
      await axios.delete(`${API}/operations/shifts/${pid}/clear-week?week_start=${weekStart}`);
      toast.success("Week cleared");
      load();
    } catch { toast.error("Failed"); }
  };

  const navWeek = (dir) => {
    const d = new Date(weekStart);
    d.setDate(d.getDate() + dir * 7);
    setWeekStart(d.toISOString().slice(0, 10));
  };

  if (loading && !data) return <div className="flex items-center justify-center py-20 text-stone-400"><RefreshCw className="w-5 h-5 animate-spin mr-2" />Loading Shifts...</div>;
  if (!data) return null;

  const filtered = roleFilter === "all" ? data.staff : data.staff.filter(s => s.role === roleFilter);

  return (
    <div className="space-y-4" data-testid="shift-scheduler">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Calendar className="w-5 h-5 text-stone-700" />
          <h2 className="text-base font-bold text-stone-800" data-testid="shifts-title">Shift Scheduler</h2>
          <Badge className="bg-stone-100 text-stone-600 text-[10px]">{data.total_staff} staff</Badge>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => bulkPublish("publish")} data-testid="publish-all-btn" className="flex items-center gap-1 px-3 py-1.5 text-xs font-bold text-white bg-emerald-500 rounded-lg hover:bg-emerald-600"><Play className="w-3 h-3" />Publish All</button>
          <button onClick={() => bulkPublish("approve")} className="flex items-center gap-1 px-3 py-1.5 text-xs font-bold text-white bg-blue-500 rounded-lg hover:bg-blue-600"><CheckCircle className="w-3 h-3" />Approve All</button>
          <button onClick={clearWeek} className="flex items-center gap-1 px-3 py-1.5 text-xs font-bold text-red-600 bg-red-50 rounded-lg hover:bg-red-100"><Trash2 className="w-3 h-3" />Clear Week</button>
        </div>
      </div>

      {/* Week Nav + Role Filter */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <button onClick={() => navWeek(-1)} className="p-1.5 hover:bg-stone-100 rounded-lg"><ChevronLeft className="w-4 h-4" /></button>
          <span className="text-sm font-semibold text-stone-700">{data.week_start} — {data.week_end}</span>
          <button onClick={() => navWeek(1)} className="p-1.5 hover:bg-stone-100 rounded-lg"><ChevronRight className="w-4 h-4" /></button>
        </div>
        <div className="flex items-center gap-1 bg-stone-100 rounded-lg p-0.5">
          {["all", "receptionist", "housekeeper", "maintenance"].map(r => (
            <button key={r} onClick={() => setRoleFilter(r)} data-testid={`filter-${r}`}
              className={`px-3 py-1 text-[11px] font-semibold rounded-md ${roleFilter === r ? "bg-white text-stone-800 shadow-sm" : "text-stone-500"}`}>
              {r === "all" ? "All" : r.charAt(0).toUpperCase() + r.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Schedule Grid */}
      <div className="bg-white border border-stone-200 rounded-xl overflow-hidden" data-testid="shift-grid">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-stone-50 border-b border-stone-200">
              <th className="text-left py-3 px-3 font-semibold text-stone-600 w-48">Staff Member</th>
              {data.days.map(d => (
                <th key={d.date} className={`text-center py-3 px-1 font-semibold ${d.dow === "Sat" || d.dow === "Sun" ? "text-blue-600 bg-blue-50/50" : "text-stone-600"}`}>
                  {d.dow}<br /><span className="text-[10px] font-normal">{d.day} {d.month}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map(staff => (
              <tr key={staff.id} className="border-b border-stone-100 hover:bg-stone-50/50">
                <td className="py-2 px-3">
                  <div className="flex items-center gap-2">
                    <div className="w-7 h-7 rounded-full bg-stone-100 flex items-center justify-center text-[10px] font-bold text-stone-600">{staff.name?.[0] || "?"}</div>
                    <div>
                      <p className="font-medium text-stone-700">{staff.name}</p>
                      <div className="flex items-center gap-1">
                        <Badge className={`text-[7px] ${ROLE_COLORS[staff.role] || "bg-stone-100 text-stone-500"}`}>{staff.role}</Badge>
                        <span className="text-[9px] text-stone-400">£{staff.daily_rate}/day</span>
                      </div>
                    </div>
                  </div>
                </td>
                {staff.shifts.map(shift => (
                  <td key={shift.date} className="py-1 px-1 text-center">
                    {shift.status !== "none" ? (
                      <div className="rounded-md px-1 py-1.5 text-[9px] font-bold text-white" style={{ backgroundColor: shift.color || "#22c55e" }} title={`${shift.shift_start} - ${shift.shift_end} (${shift.status})`}>
                        {shift.shift_start}<br/>{shift.shift_end}
                      </div>
                    ) : (
                      <div className="relative group">
                        <div className="h-9 rounded-md border border-dashed border-stone-200 flex items-center justify-center text-stone-300 group-hover:border-blue-300 group-hover:bg-blue-50/50 cursor-pointer">
                          <Clock className="w-3 h-3" />
                        </div>
                        <div className="absolute top-full left-1/2 -translate-x-1/2 mt-1 bg-white border border-stone-200 rounded-lg shadow-lg p-1.5 z-20 hidden group-hover:flex flex-col gap-0.5 min-w-[100px]">
                          {PRESETS.map(p => (
                            <button key={p.id} onClick={() => assignShift(staff.id, shift.date, p.id)} className="text-left px-2 py-1 text-[10px] hover:bg-stone-100 rounded flex items-center gap-1.5">
                              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: p.color }} />
                              {p.label} <span className="text-stone-400">{p.time}</span>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 text-[10px] text-stone-400">
        <span>Status:</span>
        {Object.entries(STATUS_COLORS).map(([k, v]) => (
          <span key={k} className="flex items-center gap-1"><span className={`w-3 h-2 rounded-sm ${v}`} />{k}</span>
        ))}
      </div>
    </div>
  );
};
