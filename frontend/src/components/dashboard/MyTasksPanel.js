import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import { toast } from "sonner";
import { motion } from "framer-motion";
import { Badge } from "@/components/ui/badge";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const MyTasksPanel = ({ user }) => {
  const [data, setData] = useState(null);
  const prevUrgentIds = useRef(null);

  const playDing = () => {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      [880, 1174.7].forEach((f, i) => {
        const o = ctx.createOscillator(); const g = ctx.createGain();
        o.frequency.value = f; o.type = "sine";
        o.connect(g); g.connect(ctx.destination);
        g.gain.setValueAtTime(0.15, ctx.currentTime + i * 0.18);
        g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + i * 0.18 + 0.4);
        o.start(ctx.currentTime + i * 0.18); o.stop(ctx.currentTime + i * 0.18 + 0.45);
      });
    } catch { /* audio unavailable */ }
  };

  const load = useCallback(async () => {
    try {
      const { data: d } = await axios.get(`${API}/my-tasks`);
      setData(d);
      const urgentIds = (d.hk_tasks || []).filter(t => t.priority === "urgent").map(t => t.id);
      if (prevUrgentIds.current !== null) {
        const fresh = urgentIds.filter(id => !prevUrgentIds.current.includes(id));
        if (fresh.length > 0) {
          playDing();
          toast.warning(`⚡ ${fresh.length} yeni öncelikli oda temizliği atandı!`, { duration: 8000 });
        }
      }
      prevUrgentIds.current = urgentIds;
    } catch { /* silent */ }
  }, []);
  useEffect(() => { load(); const iv = setInterval(load, 30000); return () => clearInterval(iv); }, [load]);

  const updateHkStatus = async (taskId, status) => {
    try {
      await axios.put(`${API}/housekeeping/tasks/${taskId}`, { status });
      toast.success(status === "in_progress" ? "Göreve başlandı" : "Görev tamamlandı ✓");
      load();
    } catch { toast.error("Güncellenemedi"); }
  };

  const [newTask, setNewTask] = useState("");
  const addPersonal = async () => {
    if (!newTask.trim()) return;
    try {
      await axios.post(`${API}/my-tasks/personal`, { text: newTask.trim() });
      setNewTask("");
      toast.success("Görev eklendi ✓");
      load();
    } catch { toast.error("Eklenemedi"); }
  };
  const donePersonal = async (id) => {
    try {
      await axios.put(`${API}/my-tasks/personal/${id}`, { done: true });
      toast.success("Görev tamamlandı ✓");
      load();
    } catch { toast.error("Güncellenemedi"); }
  };

  const s = data?.summary || {};
  const greeting = () => {
    const h = new Date().getHours();
    if (h < 12) return "Good morning";
    if (h < 17) return "Good afternoon";
    return "Good evening";
  };

  const statCards = [
    { label: "Shifts Today", value: s.shifts_today || 0, color: "from-blue-500 to-blue-600", icon: "M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" },
    { label: "Week Shifts", value: s.shifts_this_week || 0, color: "from-violet-500 to-violet-600", icon: "M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" },
    { label: "Handover Notes", value: s.pending_handovers || 0, color: "from-amber-500 to-amber-600", icon: "M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" },
    { label: "Active Routines", value: s.active_routines || 0, color: "from-emerald-500 to-emerald-600", icon: "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" },
    { label: "Maintenance", value: s.open_maintenance || 0, color: "from-red-500 to-red-600", icon: "M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" },
    { label: "Notifications", value: data?.unread_notifications || 0, color: "from-stone-500 to-stone-600", icon: "M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" },
  ];

  const statusColors = { planned: "bg-blue-100 text-blue-700", published: "bg-emerald-100 text-emerald-700", completed: "bg-amber-100 text-amber-700", approved: "bg-violet-100 text-violet-700" };
  const priorityColors = { low: "bg-stone-100 text-stone-500", normal: "bg-blue-100 text-blue-600", high: "bg-orange-100 text-orange-700", critical: "bg-red-100 text-red-700" };

  return (
    <div className="p-5" data-testid="my-tasks-panel">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-stone-900">{greeting()}, {data?.user?.name || user?.name || "Staff"}</h1>
        <p className="text-sm text-stone-500 mt-1">Here's your daily overview — {new Date().toLocaleDateString("en", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
        {statCards.map((c, i) => (
          <motion.div key={c.label} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}
            className={`bg-gradient-to-br ${c.color} rounded-xl p-4 text-white shadow-lg shadow-black/10`} data-testid={`task-stat-${c.label.toLowerCase().replace(/\s/g, '-')}`}>
            <svg className="w-5 h-5 mb-2 opacity-70" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={c.icon} /></svg>
            <div className="text-2xl font-bold">{data ? c.value : "..."}</div>
            <div className="text-xs opacity-80 mt-0.5">{c.label}</div>
          </motion.div>
        ))}
      </div>

      {/* Kişisel Görevler */}
      <div className="mb-6 bg-white border-2 border-violet-200 rounded-2xl p-5" data-testid="my-personal-tasks-section">
        <h3 className="font-bold text-stone-800 mb-3">📝 Kişisel Görevlerim ({(data?.personal_tasks || []).length})</h3>
        <div className="flex gap-2 mb-3">
          <input value={newTask} onChange={(e) => setNewTask(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addPersonal()}
            placeholder="Yeni görev yaz ve Enter'a bas…" data-testid="my-tasks-new-input"
            className="flex-1 px-3 py-2 border border-stone-300 rounded-xl text-sm" />
          <button onClick={addPersonal} data-testid="my-tasks-add-btn"
            className="px-4 py-2 bg-violet-600 text-white text-sm font-bold rounded-xl hover:bg-violet-700">+ Yeni Görev</button>
        </div>
        {(data?.personal_tasks || []).length === 0 ? (
          <p className="text-xs text-stone-400" data-testid="my-tasks-empty">Açık kişisel göreviniz yok — yukarıdan ekleyebilirsiniz.</p>
        ) : (
          <div className="space-y-1.5">
            {data.personal_tasks.map((t) => (
              <label key={t.id} className="flex items-center gap-2.5 bg-stone-50 border border-stone-200 rounded-xl px-3 py-2 cursor-pointer hover:bg-stone-100"
                data-testid={`my-personal-task-${t.id}`}>
                <input type="checkbox" onChange={() => donePersonal(t.id)} data-testid={`my-personal-done-${t.id}`} />
                <span className="text-sm text-stone-700">{t.text}</span>
              </label>
            ))}
          </div>
        )}
      </div>

      {(data?.hk_tasks || []).length > 0 && (
        <div className="mb-6 bg-white border-2 border-cyan-200 rounded-2xl p-5" data-testid="my-hk-tasks-section">
          <h3 className="font-bold text-stone-800 mb-3 flex items-center gap-2">
            <svg className="w-5 h-5 text-cyan-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
            Bugünkü Temizlik Görevlerim ({data.summary?.hk_open || 0})
            {(data.summary?.hk_urgent || 0) > 0 && (
              <span className="text-[10px] px-2 py-0.5 bg-rose-100 text-rose-700 rounded-full font-bold animate-pulse">
                ⚡ {data.summary.hk_urgent} öncelikli
              </span>
            )}
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
            {data.hk_tasks.map(t => (
              <div key={t.id} data-testid={`my-hk-task-${t.id}`}
                className={`rounded-xl border px-3 py-2.5 ${t.priority === "urgent" ? "border-rose-300 bg-rose-50" : "border-stone-200 bg-stone-50"}`}>
                <div className="flex items-center gap-2 text-sm font-semibold text-stone-800">
                  {t.priority === "urgent" && <span className="text-rose-600">⚡</span>}
                  Oda {t.room_number}
                  <span className={`ml-auto text-[10px] px-1.5 py-0.5 rounded-full ${t.status === "in_progress" ? "bg-sky-100 text-sky-700" : "bg-amber-100 text-amber-700"}`}>
                    {t.status === "in_progress" ? "devam ediyor" : "bekliyor"}
                  </span>
                </div>
                <div className="text-[11px] text-stone-500 mt-1 line-clamp-2">{typeof t.notes === "string" ? t.notes : ""}</div>
                <div className="flex gap-1.5 mt-2">
                  {t.status === "pending" && (
                    <button onClick={() => updateHkStatus(t.id, "in_progress")} data-testid={`my-hk-start-${t.id}`}
                      className="flex-1 px-2 py-1 text-[11px] font-semibold bg-sky-600 text-white rounded-lg hover:bg-sky-700">Başla</button>
                  )}
                  <button onClick={() => updateHkStatus(t.id, "completed")} data-testid={`my-hk-done-${t.id}`}
                    className="flex-1 px-2 py-1 text-[11px] font-semibold bg-emerald-600 text-white rounded-lg hover:bg-emerald-700">Tamamlandı ✓</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Today's Shifts */}
        <div className="bg-white border border-stone-200 rounded-2xl p-5" data-testid="tasks-shifts-section">
          <h3 className="font-bold text-stone-800 mb-3 flex items-center gap-2">
            <svg className="w-5 h-5 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
            Today's Shifts
          </h3>
          {(data?.today_shifts || []).length === 0 ? (
            <div className="text-center py-6 text-stone-400 text-sm">No shifts scheduled for today</div>
          ) : data.today_shifts.map(s => (
            <div key={s.id} className="flex items-center justify-between p-3 border border-stone-100 rounded-lg mb-2" data-testid={`task-shift-${s.id}`}>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center text-blue-600 font-bold text-sm">{s.start_time}</div>
                <div><div className="text-sm font-medium text-stone-800">{s.start_time} — {s.end_time}</div><div className="text-xs text-stone-400 capitalize">{s.property_id} &middot; {s.role}</div></div>
              </div>
              <Badge className={`text-[10px] ${statusColors[s.status] || "bg-stone-100"}`}>{s.status}</Badge>
            </div>
          ))}
          {(data?.week_shifts || []).length > 0 && (
            <div className="mt-3 pt-3 border-t border-stone-100">
              <p className="text-xs text-stone-400 font-medium mb-2">This Week ({data.week_shifts.length} shifts)</p>
              <div className="flex gap-1 flex-wrap">{data.week_shifts.map(s => (
                <span key={s.id} className={`text-[10px] px-2 py-1 rounded ${s.date === data.date ? "bg-blue-100 text-blue-700 font-bold" : "bg-stone-100 text-stone-500"}`}>
                  {new Date(s.date + "T00:00:00").toLocaleDateString("en", { weekday: "short" })} {s.start_time}
                </span>
              ))}</div>
            </div>
          )}
        </div>

        {/* Handover Notes */}
        <div className="bg-white border border-stone-200 rounded-2xl p-5" data-testid="tasks-handover-section">
          <h3 className="font-bold text-stone-800 mb-3 flex items-center gap-2">
            <svg className="w-5 h-5 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" /></svg>
            Pending Handover Notes
          </h3>
          {(data?.handover_notes || []).length === 0 ? (
            <div className="text-center py-6 text-stone-400 text-sm">No pending handover notes</div>
          ) : data.handover_notes.map(n => (
            <div key={n.id} className="p-3 border border-stone-100 rounded-lg mb-2" data-testid={`task-handover-${n.id}`}>
              <div className="flex items-center gap-2 mb-1">
                <Badge className={`text-[9px] uppercase ${priorityColors[n.priority] || "bg-stone-100"}`}>{n.priority}</Badge>
                <Badge className="text-[9px] bg-sky-100 text-sky-600 uppercase">{n.note_type}</Badge>
              </div>
              <p className="text-sm text-stone-700 line-clamp-2">{n.content}</p>
              <div className="text-[10px] text-stone-400 mt-1">{n.author} &middot; {n.created_at ? new Date(n.created_at).toLocaleString() : ""}</div>
            </div>
          ))}
        </div>

        {/* Active Routines */}
        <div className="bg-white border border-stone-200 rounded-2xl p-5" data-testid="tasks-routines-section">
          <h3 className="font-bold text-stone-800 mb-3 flex items-center gap-2">
            <svg className="w-5 h-5 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" /></svg>
            Active Routines
          </h3>
          {(data?.routines || []).length === 0 ? (
            <div className="text-center py-6 text-stone-400 text-sm">No active routines</div>
          ) : data.routines.map(r => (
            <div key={r.id} className="flex items-center justify-between p-3 border border-stone-100 rounded-lg mb-2" data-testid={`task-routine-${r.id}`}>
              <div><div className="text-sm font-medium text-stone-800">{r.template_name}</div><div className="text-xs text-stone-400">Shift: {r.shift} &middot; Started by: {r.user}</div></div>
              <div className="text-right"><div className="text-sm font-bold text-stone-700">{r.completed_tasks}/{r.total_tasks}</div><div className="text-[10px] text-stone-400">tasks</div></div>
            </div>
          ))}
        </div>

        {/* Maintenance */}
        <div className="bg-white border border-stone-200 rounded-2xl p-5" data-testid="tasks-maintenance-section">
          <h3 className="font-bold text-stone-800 mb-3 flex items-center gap-2">
            <svg className="w-5 h-5 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /></svg>
            Open Maintenance
          </h3>
          {(data?.maintenance || []).length === 0 ? (
            <div className="text-center py-6 text-stone-400 text-sm">No assigned maintenance tasks</div>
          ) : data.maintenance.map(m => (
            <div key={m.id} className="p-3 border border-stone-100 rounded-lg mb-2" data-testid={`task-maint-${m.id}`}>
              <div className="text-sm font-medium text-stone-800">{m.issue || m.title}</div>
              <div className="flex items-center gap-2 mt-1">
                <Badge className={`text-[9px] ${m.priority === "high" || m.priority === "urgent" ? "bg-red-100 text-red-700" : "bg-amber-100 text-amber-600"}`}>{m.priority}</Badge>
                <span className="text-[10px] text-stone-400">{m.location || m.room} &middot; {m.status}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
