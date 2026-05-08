import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import { motion, AnimatePresence } from "framer-motion";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const typeStyles = {
  warning: { bg: "bg-amber-50", border: "border-amber-200", icon: "text-amber-500", dot: "bg-amber-500" },
  error: { bg: "bg-red-50", border: "border-red-200", icon: "text-red-500", dot: "bg-red-500" },
  success: { bg: "bg-emerald-50", border: "border-emerald-200", icon: "text-emerald-500", dot: "bg-emerald-500" },
  info: { bg: "bg-blue-50", border: "border-blue-200", icon: "text-blue-500", dot: "bg-blue-500" },
};

const categoryLabels = {
  sla_breach: "SLA Breach",
  handover_alert: "Handover",
  compliance_due: "Compliance",
  routine_alert: "Routines",
  shift_update: "Shifts",
  price_intelligence: "Price Intel",
  general: "General",
};

const timeAgo = (iso) => {
  if (!iso) return "";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
};

export const NotificationBell = ({ onNavigate }) => {
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [filter, setFilter] = useState("all");
  const panelRef = useRef(null);

  const load = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/notifications?limit=30`);
      setNotifications(data.notifications || []);
      setUnreadCount(data.unread_count || 0);
    } catch {
      // silent
    }
  }, []);

  useEffect(() => { load(); const iv = setInterval(load, 30000); return () => clearInterval(iv); }, [load]);

  useEffect(() => {
    const handleClick = (e) => {
      if (panelRef.current && !panelRef.current.contains(e.target)) setOpen(false);
    };
    if (open) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  const markRead = async (id) => {
    try {
      await axios.put(`${API}/notifications/${id}/read`);
      load();
    } catch { /* silent */ }
  };

  const markAllRead = async () => {
    try {
      await axios.put(`${API}/notifications/read-all`);
      load();
    } catch { /* silent */ }
  };

  const generateCheck = async () => {
    try {
      const { data } = await axios.post(`${API}/notifications/generate-check`);
      if (data.generated > 0) load();
    } catch { /* silent */ }
  };

  const handleNotifClick = (n) => {
    markRead(n.id);
    if (n.link_to && onNavigate) {
      onNavigate(n.link_to);
      setOpen(false);
    }
  };

  const filtered = filter === "all" ? notifications : filter === "unread" ? notifications.filter(n => !n.read) : notifications.filter(n => n.category === filter);

  return (
    <div className="relative" ref={panelRef} data-testid="notification-bell-container">
      <button onClick={() => { setOpen(!open); if (!open) generateCheck(); }}
        className="relative p-2 text-stone-400 hover:text-stone-200 transition-colors rounded-lg hover:bg-stone-800" data-testid="notification-bell-btn">
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
        </svg>
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 w-5 h-5 bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center animate-pulse" data-testid="notification-unread-count">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div initial={{ opacity: 0, y: -8, scale: 0.95 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -8, scale: 0.95 }}
            transition={{ duration: 0.15 }}
            className="fixed left-60 top-4 w-96 bg-white rounded-xl shadow-2xl border border-stone-200 z-[60] overflow-hidden lg:left-60 max-lg:right-4 max-lg:left-auto max-lg:top-16" data-testid="notification-panel">
            {/* Header */}
            <div className="p-4 border-b border-stone-100 bg-stone-50/50">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-bold text-stone-800 text-sm">Notifications</h3>
                <div className="flex items-center gap-2">
                  {unreadCount > 0 && (
                    <button onClick={markAllRead} className="text-[11px] text-blue-600 hover:text-blue-700 font-medium" data-testid="mark-all-read-btn">
                      Mark all read
                    </button>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-1 overflow-x-auto">
                {[
                  { id: "all", label: "All" },
                  { id: "unread", label: `Unread (${unreadCount})` },
                  { id: "price_intelligence", label: "Price Intel" },
                  { id: "sla_breach", label: "SLA" },
                  { id: "handover_alert", label: "Handover" },
                  { id: "compliance_due", label: "Compliance" },
                ].map(f => (
                  <button key={f.id} onClick={() => setFilter(f.id)}
                    className={`px-2.5 py-1 text-[11px] font-medium rounded-md whitespace-nowrap transition-colors ${
                      filter === f.id ? "bg-stone-800 text-white" : "text-stone-500 hover:bg-stone-200"
                    }`} data-testid={`notif-filter-${f.id}`}>{f.label}</button>
                ))}
              </div>
            </div>

            {/* List */}
            <div className="max-h-[400px] overflow-y-auto" data-testid="notification-list">
              {filtered.length === 0 ? (
                <div className="py-12 text-center text-stone-400">
                  <svg className="w-10 h-10 mx-auto mb-2 text-stone-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                  </svg>
                  <p className="text-sm font-medium">All clear!</p>
                  <p className="text-xs mt-0.5">No notifications to show</p>
                </div>
              ) : (
                filtered.map(n => {
                  const s = typeStyles[n.type] || typeStyles.info;
                  return (
                    <button key={n.id} onClick={() => handleNotifClick(n)}
                      className={`w-full text-left p-3.5 border-b border-stone-100 hover:bg-stone-50 transition-colors flex gap-3 ${!n.read ? "bg-blue-50/30" : ""}`} data-testid={`notification-item-${n.id}`}>
                      <div className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${!n.read ? s.dot : "bg-stone-200"}`} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-0.5">
                          <span className={`text-[10px] font-bold uppercase ${s.icon}`}>{categoryLabels[n.category] || n.category}</span>
                          {n.priority === "high" && <span className="text-[9px] bg-red-100 text-red-600 px-1.5 py-0.5 rounded-full font-bold">HIGH</span>}
                        </div>
                        <p className={`text-sm leading-snug ${!n.read ? "font-semibold text-stone-800" : "text-stone-600"}`}>{n.title}</p>
                        <p className="text-xs text-stone-400 mt-0.5 line-clamp-2">{n.message}</p>
                        <div className="flex items-center gap-2 mt-1.5 text-[10px] text-stone-400">
                          <span>{n.created_by}</span>
                          <span>&middot;</span>
                          <span>{timeAgo(n.created_at)}</span>
                        </div>
                      </div>
                    </button>
                  );
                })
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
