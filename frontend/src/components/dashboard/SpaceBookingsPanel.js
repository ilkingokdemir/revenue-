import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  CalendarBlank, Clock, Users, CurrencyGbp, CheckCircle, X, ArrowsClockwise,
  PresentationChart, Door, Car, FlowerLotus,
} from "@phosphor-icons/react";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export function SpaceBookingsPanel({ properties }) {
  const [bookings, setBookings] = useState([]);
  const [stats, setStats] = useState(null);
  const [spaces, setSpaces] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterDate, setFilterDate] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const propertyId = properties?.[0]?.id || "aldgate-flats";

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      let url = `${API}/spaces/admin/bookings/${propertyId}`;
      const params = [];
      if (filterDate) params.push(`date=${filterDate}`);
      if (filterStatus) params.push(`status=${filterStatus}`);
      if (params.length) url += `?${params.join("&")}`;
      const [bRes, sRes, spRes] = await Promise.all([
        axios.get(url),
        axios.get(`${API}/spaces/admin/stats/${propertyId}`),
        axios.get(`${API}/spaces/${propertyId}`),
      ]);
      setBookings(bRes.data);
      setStats(sRes.data);
      setSpaces(spRes.data);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [propertyId, filterDate, filterStatus]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const updateStatus = async (bookingId, status) => {
    try {
      await axios.put(`${API}/spaces/admin/bookings/${bookingId}/status?status=${status}`);
      toast.success(`Booking ${status}`);
      fetchAll();
    } catch (e) { toast.error("Failed to update"); }
  };

  const seedSpaces = async () => {
    try {
      await axios.post(`${API}/spaces/seed/${propertyId}`);
      toast.success("Spaces seeded");
      fetchAll();
    } catch (e) { toast.error("Failed to seed spaces"); }
  };

  const CATEGORY_ICONS = { business: PresentationChart, workspace: Door, events: Users, parking: Car, wellness: FlowerLotus };

  return (
    <div className="p-5" data-testid="space-bookings-panel">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-lg font-semibold text-stone-900">Space & Hourly Bookings</h2>
          <p className="text-sm text-stone-500">Manage meeting rooms, parking, events, and more</p>
        </div>
        <div className="flex items-center gap-2">
          {spaces.length === 0 && (
            <button onClick={seedSpaces} className="text-xs bg-blue-50 text-blue-700 px-3 py-1.5 rounded-lg hover:bg-blue-100 font-medium" data-testid="seed-spaces-btn">
              Seed Demo Spaces
            </button>
          )}
          <button onClick={fetchAll} className="text-xs bg-stone-100 text-stone-600 px-3 py-1.5 rounded-lg hover:bg-stone-200 flex items-center gap-1" data-testid="refresh-spaces-btn">
            <ArrowsClockwise size={12} /> Refresh
          </button>
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-5">
          {[
            { icon: CalendarBlank, label: "Total Bookings", value: stats.total_bookings },
            { icon: CheckCircle, label: "Confirmed", value: stats.confirmed },
            { icon: Clock, label: "Today", value: stats.today },
            { icon: CurrencyGbp, label: "Revenue", value: `£${Math.round(stats.total_revenue)}` },
            { icon: Clock, label: "Total Hours", value: `${Math.round(stats.total_hours)}h` },
            { icon: Door, label: "Active Spaces", value: stats.spaces_count },
          ].map(s => (
            <div key={s.label} className="bg-white border border-stone-200 rounded-xl p-4" data-testid={`stat-${s.label.toLowerCase().replace(/\s/g, '-')}`}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] text-stone-400 uppercase tracking-wider font-semibold">{s.label}</span>
                <s.icon size={14} className="text-stone-400" />
              </div>
              <span className="text-xl font-bold text-stone-900">{s.value}</span>
            </div>
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-3 mb-4">
        <input type="date" value={filterDate} onChange={e => setFilterDate(e.target.value)}
          className="text-xs border border-stone-200 rounded-lg px-3 py-2 bg-white" data-testid="filter-date" />
        <Select value={filterStatus} onValueChange={setFilterStatus}>
          <SelectTrigger className="w-40 h-9 text-xs border-stone-200"><SelectValue placeholder="All Status" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="confirmed">Confirmed</SelectItem>
            <SelectItem value="cancelled">Cancelled</SelectItem>
            <SelectItem value="completed">Completed</SelectItem>
          </SelectContent>
        </Select>
        {(filterDate || filterStatus) && (
          <button onClick={() => { setFilterDate(""); setFilterStatus(""); }} className="text-xs text-stone-500 hover:text-stone-700">Clear</button>
        )}
      </div>

      {/* Available Spaces Grid */}
      {spaces.length > 0 && (
        <div className="mb-6">
          <h3 className="text-sm font-semibold text-stone-700 mb-3">Available Spaces</h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2">
            {spaces.map(s => {
              const Icon = CATEGORY_ICONS[s.category] || PresentationChart;
              return (
                <div key={s.id} className="bg-white border border-stone-200 rounded-lg p-3 text-center" data-testid={`admin-space-${s.id}`}>
                  <Icon size={18} className="mx-auto text-stone-500 mb-1" />
                  <span className="text-[11px] font-medium text-stone-800 block truncate">{s.name}</span>
                  <span className="text-xs text-emerald-600 font-bold">£{s.hourly_rate}/hr</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Bookings Table */}
      <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
        <table className="w-full" data-testid="bookings-table">
          <thead>
            <tr className="bg-stone-50 border-b border-stone-200">
              <th className="text-left px-4 py-3 text-[11px] font-semibold text-stone-500 uppercase">Guest</th>
              <th className="text-left px-4 py-3 text-[11px] font-semibold text-stone-500 uppercase">Space</th>
              <th className="text-left px-4 py-3 text-[11px] font-semibold text-stone-500 uppercase">Date</th>
              <th className="text-left px-4 py-3 text-[11px] font-semibold text-stone-500 uppercase">Time</th>
              <th className="text-left px-4 py-3 text-[11px] font-semibold text-stone-500 uppercase">Hours</th>
              <th className="text-left px-4 py-3 text-[11px] font-semibold text-stone-500 uppercase">Price</th>
              <th className="text-left px-4 py-3 text-[11px] font-semibold text-stone-500 uppercase">Status</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={8} className="py-10 text-center"><ArrowsClockwise size={20} className="mx-auto animate-spin text-stone-300" /></td></tr>
            ) : bookings.length === 0 ? (
              <tr><td colSpan={8} className="py-10 text-center text-sm text-stone-400">No bookings found</td></tr>
            ) : (
              bookings.map(b => (
                <tr key={b.id} className="border-b border-stone-50 hover:bg-stone-50 transition-colors" data-testid={`booking-row-${b.id}`}>
                  <td className="px-4 py-3">
                    <div className="text-sm font-medium text-stone-900">{b.guest_name}</div>
                    <div className="text-[11px] text-stone-400">{b.guest_email}</div>
                  </td>
                  <td className="px-4 py-3 text-sm text-stone-700">{b.space_name}</td>
                  <td className="px-4 py-3 text-sm text-stone-700">{b.booking_date}</td>
                  <td className="px-4 py-3 text-sm text-stone-700">{b.start_time} — {b.end_time}</td>
                  <td className="px-4 py-3 text-sm text-stone-700">{b.hours}h</td>
                  <td className="px-4 py-3 text-sm font-semibold text-stone-900">£{b.total_price}</td>
                  <td className="px-4 py-3">
                    <span className={`text-[10px] font-medium px-2 py-1 rounded-full ${
                      b.status === "confirmed" ? "bg-emerald-50 text-emerald-700" :
                      b.status === "cancelled" ? "bg-red-50 text-red-700" :
                      "bg-stone-100 text-stone-600"
                    }`}>{b.status}</span>
                  </td>
                  <td className="px-4 py-3">
                    {b.status === "confirmed" && (
                      <div className="flex gap-1">
                        <button onClick={() => updateStatus(b.id, "completed")} className="text-[10px] bg-emerald-50 text-emerald-700 px-2 py-1 rounded hover:bg-emerald-100" data-testid={`complete-${b.id}`}>
                          Complete
                        </button>
                        <button onClick={() => updateStatus(b.id, "cancelled")} className="text-[10px] bg-red-50 text-red-600 px-2 py-1 rounded hover:bg-red-100" data-testid={`cancel-${b.id}`}>
                          Cancel
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
