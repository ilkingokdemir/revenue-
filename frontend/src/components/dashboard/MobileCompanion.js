import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import {
  RefreshCw, Bed, DollarSign, LogIn, LogOut, Users, Bell, MessageSquare,
  Sparkles, AlertTriangle, ChevronRight, CheckCircle, Smartphone
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;

export const MobileCompanion = ({ propertyId }) => {
  const [data, setData] = useState(null);
  const [arrivals, setArrivals] = useState(null);
  const [hk, setHk] = useState(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("dashboard");

  const pid = propertyId || "all";

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [dashRes, arrRes, hkRes] = await Promise.all([
        axios.get(`${API}/mobile/dashboard/${pid}`),
        axios.get(`${API}/mobile/arrivals/${pid}`),
        axios.get(`${API}/mobile/housekeeping/${pid}`),
      ]);
      setData(dashRes.data);
      setArrivals(arrRes.data);
      setHk(hkRes.data);
    } catch { /* silent */ }
    setLoading(false);
  }, [pid]);

  useEffect(() => { load(); }, [load]);

  const quickCheckin = async (bookingId) => {
    try {
      await axios.put(`${API}/bookings/timeline/${pid}/status/${bookingId}`, { status: "checked_in" });
      toast.success("Checked in!");
      load();
    } catch { toast.error("Failed"); }
  };

  const toggleHK = async (roomId, newStatus) => {
    try {
      await axios.put(`${API}/housekeeping/rooms/${roomId}`, { housekeeping: newStatus });
      toast.success(`Room updated to ${newStatus}`);
      load();
    } catch { toast.error("Failed"); }
  };

  if (loading && !data) return <div className="flex items-center justify-center py-20 text-stone-400"><RefreshCw className="w-5 h-5 animate-spin mr-2" />Loading...</div>;
  if (!data) return null;

  const t = data.today;
  const actions = data.action_items;

  return (
    <div className="max-w-md mx-auto" data-testid="mobile-companion">
      {/* Mobile Header */}
      <div className="bg-gradient-to-b from-stone-900 to-stone-800 rounded-3xl p-5 text-white mb-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Smartphone className="w-5 h-5 text-violet-400" />
            <h2 className="text-base font-bold" data-testid="mobile-title">Mobile Dashboard</h2>
          </div>
          <button onClick={load} className="p-2 bg-white/10 rounded-lg"><RefreshCw className="w-3.5 h-3.5" /></button>
        </div>

        {/* Tab Bar */}
        <div className="flex gap-1 bg-white/5 rounded-xl p-1 mb-4">
          {[
            { id: "dashboard", label: "Today" },
            { id: "arrivals", label: `Arrivals (${arrivals?.count || 0})` },
            { id: "housekeeping", label: `HK (${hk?.dirty || 0})` },
          ].map(tb => (
            <button key={tb.id} onClick={() => setTab(tb.id)} data-testid={`mobile-tab-${tb.id}`}
              className={`flex-1 py-2 text-xs font-semibold rounded-lg ${tab === tb.id ? "bg-white/15 text-white" : "text-white/40"}`}>
              {tb.label}
            </button>
          ))}
        </div>

        {/* DASHBOARD TAB */}
        {tab === "dashboard" && (
          <>
            {/* Main KPI */}
            <div className="text-center mb-4">
              <p className="text-5xl font-black">{t.occupancy_pct}%</p>
              <p className="text-xs text-white/40">Occupancy ({t.booked_rooms}/{t.total_rooms} rooms)</p>
            </div>

            {/* KPI Grid */}
            <div className="grid grid-cols-3 gap-2 mb-4">
              <div className="bg-white/5 rounded-xl p-3 text-center">
                <DollarSign className="w-4 h-4 mx-auto mb-1 text-emerald-400" />
                <p className="text-lg font-bold">{cur(t.revenue)}</p>
                <p className="text-[8px] text-white/30">Revenue</p>
              </div>
              <div className="bg-white/5 rounded-xl p-3 text-center">
                <LogIn className="w-4 h-4 mx-auto mb-1 text-blue-400" />
                <p className="text-lg font-bold">{t.arrivals}</p>
                <p className="text-[8px] text-white/30">Arrivals</p>
              </div>
              <div className="bg-white/5 rounded-xl p-3 text-center">
                <LogOut className="w-4 h-4 mx-auto mb-1 text-amber-400" />
                <p className="text-lg font-bold">{t.departures}</p>
                <p className="text-[8px] text-white/30">Departures</p>
              </div>
            </div>

            {/* Action Items */}
            <div className="space-y-2">
              <p className="text-[9px] text-white/30 uppercase font-bold">Action Items</p>
              {actions.dirty_rooms > 0 && (
                <div className="flex items-center justify-between bg-white/5 rounded-xl p-3">
                  <span className="flex items-center gap-2 text-xs"><Sparkles className="w-3.5 h-3.5 text-amber-400" />{actions.dirty_rooms} rooms need cleaning</span>
                  <ChevronRight className="w-3.5 h-3.5 text-white/20" />
                </div>
              )}
              {actions.pending_reviews > 0 && (
                <div className="flex items-center justify-between bg-white/5 rounded-xl p-3">
                  <span className="flex items-center gap-2 text-xs"><MessageSquare className="w-3.5 h-3.5 text-blue-400" />{actions.pending_reviews} reviews need response</span>
                  <ChevronRight className="w-3.5 h-3.5 text-white/20" />
                </div>
              )}
              {actions.price_alerts > 0 && (
                <div className="flex items-center justify-between bg-white/5 rounded-xl p-3">
                  <span className="flex items-center gap-2 text-xs"><AlertTriangle className="w-3.5 h-3.5 text-red-400" />{actions.price_alerts} price alerts</span>
                  <ChevronRight className="w-3.5 h-3.5 text-white/20" />
                </div>
              )}
              {actions.unread_notifications > 0 && (
                <div className="flex items-center justify-between bg-white/5 rounded-xl p-3">
                  <span className="flex items-center gap-2 text-xs"><Bell className="w-3.5 h-3.5 text-violet-400" />{actions.unread_notifications} notifications</span>
                  <ChevronRight className="w-3.5 h-3.5 text-white/20" />
                </div>
              )}
            </div>

            {/* Tomorrow Preview */}
            <div className="mt-4 bg-white/5 rounded-xl p-3">
              <p className="text-[9px] text-white/30 uppercase font-bold mb-1">Tomorrow</p>
              <div className="flex items-center justify-between">
                <span className="text-xs text-white/60">{data.tomorrow.occupancy_pct}% occupancy</span>
                <span className="text-xs text-white/60">{data.tomorrow.arrivals} arrivals</span>
              </div>
            </div>
          </>
        )}

        {/* ARRIVALS TAB */}
        {tab === "arrivals" && arrivals && (
          <div className="space-y-2" data-testid="mobile-arrivals">
            <p className="text-[9px] text-white/30 uppercase font-bold">{arrivals.count} Arriving Today</p>
            {arrivals.guests?.length === 0 && <p className="text-xs text-white/40 text-center py-8">No arrivals today</p>}
            {arrivals.guests?.map(g => (
              <div key={g.id} className="bg-white/5 rounded-xl p-3 flex items-center justify-between">
                <div>
                  <p className="text-sm font-bold text-white">{g.name}</p>
                  <div className="flex items-center gap-2 text-[10px] text-white/40">
                    <span>{g.nights}n</span>
                    <span>{g.source}</span>
                    {g.registration && <Badge className="bg-emerald-500/20 text-emerald-400 text-[8px]">Pre-registered</Badge>}
                  </div>
                </div>
                <button onClick={() => quickCheckin(g.id)} data-testid={`mobile-checkin-${g.id}`}
                  className="px-3 py-1.5 text-[11px] font-bold text-white bg-emerald-500 rounded-lg">
                  <CheckCircle className="w-3 h-3 inline mr-1" />Check In
                </button>
              </div>
            ))}
          </div>
        )}

        {/* HOUSEKEEPING TAB */}
        {tab === "housekeeping" && hk && (
          <div className="space-y-2" data-testid="mobile-housekeeping">
            <div className="grid grid-cols-3 gap-2 mb-3">
              <div className="bg-emerald-500/10 rounded-xl p-2 text-center"><p className="text-lg font-bold text-emerald-400">{hk.clean}</p><p className="text-[8px] text-white/30">Clean</p></div>
              <div className="bg-red-500/10 rounded-xl p-2 text-center"><p className="text-lg font-bold text-red-400">{hk.dirty}</p><p className="text-[8px] text-white/30">Dirty</p></div>
              <div className="bg-blue-500/10 rounded-xl p-2 text-center"><p className="text-lg font-bold text-blue-400">{hk.inspected}</p><p className="text-[8px] text-white/30">Inspected</p></div>
            </div>
            {hk.rooms?.dirty?.length > 0 && (
              <>
                <p className="text-[9px] text-white/30 uppercase font-bold">Rooms to Clean</p>
                {hk.rooms.dirty.map(r => (
                  <div key={r.id} className="bg-red-500/10 rounded-xl p-3 flex items-center justify-between">
                    <span className="text-xs text-white">{r.name} <span className="text-white/40">Floor {r.floor}</span></span>
                    <button onClick={() => toggleHK(r.id, "clean")} className="px-2 py-1 text-[10px] font-bold text-white bg-emerald-500 rounded-md">Mark Clean</button>
                  </div>
                ))}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
