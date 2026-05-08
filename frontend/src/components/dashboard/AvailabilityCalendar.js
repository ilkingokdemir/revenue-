import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import {
  CalendarBlank, CaretLeft, CaretRight, Bed, Users,
  ArrowsClockwise, Eye,
} from "@phosphor-icons/react";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function getOccColor(pct) {
  if (pct === 0) return "bg-stone-50 text-stone-400";
  if (pct < 30) return "bg-emerald-50 text-emerald-700 border-emerald-200";
  if (pct < 60) return "bg-amber-50 text-amber-700 border-amber-200";
  if (pct < 85) return "bg-orange-50 text-orange-700 border-orange-200";
  return "bg-red-50 text-red-700 border-red-200";
}

function getOccBarColor(pct) {
  if (pct < 30) return "bg-emerald-400";
  if (pct < 60) return "bg-amber-400";
  if (pct < 85) return "bg-orange-400";
  return "bg-red-400";
}

export function AvailabilityCalendar({ properties, activePropertyId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [month, setMonth] = useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  });
  const [selectedDay, setSelectedDay] = useState(null);

  const propertyId = activePropertyId || "all";

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/availability/calendar/${propertyId}?month=${month}`);
      setData(res.data);
    } catch (err) {
      console.error("Failed to fetch availability:", err);
    } finally {
      setLoading(false);
    }
  }, [propertyId, month]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const navigateMonth = (dir) => {
    const [y, m] = month.split("-").map(Number);
    let newM = m + dir;
    let newY = y;
    if (newM > 12) { newM = 1; newY++; }
    if (newM < 1) { newM = 12; newY--; }
    setMonth(`${newY}-${String(newM).padStart(2, "0")}`);
    setSelectedDay(null);
  };

  const monthLabel = (() => {
    const [y, m] = month.split("-");
    return new Date(Number(y), Number(m) - 1).toLocaleDateString("en-GB", { month: "long", year: "numeric" });
  })();

  const today = new Date().toISOString().slice(0, 10);
  const days = data?.days || {};
  const summary = data?.summary || {};
  const roomTypes = data?.room_types || [];

  // Calculate first day offset for calendar grid
  const firstDayDate = new Date(`${month}-01T00:00:00`);
  const firstDayOfWeek = (firstDayDate.getDay() + 6) % 7; // Monday=0

  const selectedDayData = selectedDay ? days[selectedDay] : null;

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-5" data-testid="availability-calendar-panel">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-stone-900 flex items-center gap-2" data-testid="calendar-title">
            <CalendarBlank size={22} className="text-blue-500" weight="fill" />
            Availability Calendar
          </h1>
          <p className="text-sm text-stone-500 mt-0.5">Real-time room availability & occupancy</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => navigateMonth(-1)} className="h-8 w-8 flex items-center justify-center rounded-lg border border-stone-200 hover:bg-stone-50" data-testid="prev-month-btn">
            <CaretLeft size={14} className="text-stone-500" />
          </button>
          <div className="text-sm font-semibold text-stone-800 w-36 text-center" data-testid="month-label">{monthLabel}</div>
          <button onClick={() => navigateMonth(1)} className="h-8 w-8 flex items-center justify-center rounded-lg border border-stone-200 hover:bg-stone-50" data-testid="next-month-btn">
            <CaretRight size={14} className="text-stone-500" />
          </button>
          <button onClick={fetchData} className="h-8 w-8 flex items-center justify-center rounded-lg border border-stone-200 hover:bg-stone-50 ml-2" data-testid="refresh-cal-btn">
            <ArrowsClockwise size={14} className="text-stone-500" />
          </button>
        </div>
      </div>

      {/* Summary row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-white border border-stone-200 rounded-xl p-3 text-center">
          <div className="text-lg font-bold text-stone-800">{summary.avg_occupancy || 0}%</div>
          <div className="text-[10px] text-stone-500 uppercase tracking-wider">Avg Occupancy</div>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-3 text-center">
          <div className="text-lg font-bold text-stone-800">{summary.total_bookings || 0}</div>
          <div className="text-[10px] text-stone-500 uppercase tracking-wider">Bookings</div>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-3 text-center">
          <div className="text-lg font-bold text-emerald-700">{summary.lowest_occupancy || 0}%</div>
          <div className="text-[10px] text-stone-500 uppercase tracking-wider">Lowest Day</div>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-3 text-center">
          <div className="text-lg font-bold text-red-600">{summary.peak_occupancy || 0}%</div>
          <div className="text-[10px] text-stone-500 uppercase tracking-wider">Peak Day</div>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <ArrowsClockwise size={24} className="text-stone-400 animate-spin" />
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          {/* Calendar Grid */}
          <div className="lg:col-span-2">
            <div className="bg-white border border-stone-200 rounded-xl p-4">
              {/* Weekday headers */}
              <div className="grid grid-cols-7 gap-1 mb-1">
                {WEEKDAYS.map(d => (
                  <div key={d} className="text-[10px] font-semibold text-stone-400 uppercase text-center py-1">{d}</div>
                ))}
              </div>
              {/* Calendar cells */}
              <div className="grid grid-cols-7 gap-1" data-testid="calendar-grid">
                {Array.from({ length: firstDayOfWeek }).map((_, i) => (
                  <div key={`empty-${i}`} className="h-16" />
                ))}
                {Object.keys(days).sort().map(dateStr => {
                  const day = days[dateStr];
                  const dayNum = parseInt(dateStr.split("-")[2]);
                  const isToday = dateStr === today;
                  const isSelected = dateStr === selectedDay;
                  const occColor = getOccColor(day.occupancy_pct);

                  return (
                    <button
                      key={dateStr}
                      onClick={() => setSelectedDay(dateStr === selectedDay ? null : dateStr)}
                      className={`h-16 rounded-lg border transition-all flex flex-col items-center justify-center gap-0.5 ${occColor} ${
                        isSelected ? "ring-2 ring-blue-400 ring-offset-1" : ""
                      } ${isToday ? "border-blue-400 border-2" : "border-transparent"} hover:scale-[1.03]`}
                      data-testid={`cal-day-${dateStr}`}
                    >
                      <span className={`text-xs font-semibold ${isToday ? "text-blue-600" : ""}`}>{dayNum}</span>
                      {day.total_rooms > 0 ? (
                        <>
                          <span className="text-[10px] font-bold">{day.occupancy_pct}%</span>
                          <div className="w-8 h-1 rounded-full bg-stone-200 overflow-hidden">
                            <div className={`h-full rounded-full ${getOccBarColor(day.occupancy_pct)}`} style={{ width: `${day.occupancy_pct}%` }} />
                          </div>
                        </>
                      ) : (
                        <span className="text-[9px] text-stone-300">{day.bookings_count > 0 ? `${day.bookings_count} bk` : "—"}</span>
                      )}
                    </button>
                  );
                })}
              </div>
              {/* Legend */}
              <div className="flex items-center gap-3 mt-3 pt-3 border-t border-stone-100 justify-center">
                <div className="flex items-center gap-1"><div className="w-3 h-3 rounded bg-emerald-100 border border-emerald-300" /><span className="text-[10px] text-stone-500">&lt;30%</span></div>
                <div className="flex items-center gap-1"><div className="w-3 h-3 rounded bg-amber-100 border border-amber-300" /><span className="text-[10px] text-stone-500">30-60%</span></div>
                <div className="flex items-center gap-1"><div className="w-3 h-3 rounded bg-orange-100 border border-orange-300" /><span className="text-[10px] text-stone-500">60-85%</span></div>
                <div className="flex items-center gap-1"><div className="w-3 h-3 rounded bg-red-100 border border-red-300" /><span className="text-[10px] text-stone-500">&gt;85%</span></div>
              </div>
            </div>
          </div>

          {/* Detail Panel */}
          <div className="space-y-4">
            {selectedDayData ? (
              <>
                <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="day-detail">
                  <div className="text-sm font-semibold text-stone-800 mb-3 flex items-center gap-2">
                    <CalendarBlank size={14} className="text-blue-500" />
                    {new Date(selectedDay + "T00:00:00").toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" })}
                  </div>

                  <div className="grid grid-cols-3 gap-2 mb-3">
                    <div className="text-center p-2 bg-stone-50 rounded-lg">
                      <div className="text-base font-bold text-stone-800">{selectedDayData.total_rooms}</div>
                      <div className="text-[9px] text-stone-500">Total</div>
                    </div>
                    <div className="text-center p-2 bg-red-50 rounded-lg">
                      <div className="text-base font-bold text-red-600">{selectedDayData.occupied}</div>
                      <div className="text-[9px] text-stone-500">Occupied</div>
                    </div>
                    <div className="text-center p-2 bg-emerald-50 rounded-lg">
                      <div className="text-base font-bold text-emerald-600">{selectedDayData.available}</div>
                      <div className="text-[9px] text-stone-500">Available</div>
                    </div>
                  </div>

                  {/* Room type breakdown */}
                  {selectedDayData.rooms?.filter(r => r.total > 0).length > 0 && (
                    <div className="space-y-1.5">
                      <div className="text-[11px] font-medium text-stone-600">By Room Type</div>
                      {selectedDayData.rooms.filter(r => r.total > 0).map(r => (
                        <div key={r.room_type_id} className="flex items-center justify-between text-xs">
                          <span className="text-stone-600 truncate max-w-[120px]">{r.room_type_id}</span>
                          <div className="flex items-center gap-1.5">
                            <span className="text-emerald-600 font-medium">{r.available}</span>
                            <span className="text-stone-400">/</span>
                            <span className="text-stone-500">{r.total}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Day bookings */}
                {selectedDayData.bookings?.length > 0 && (
                  <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="day-bookings">
                    <div className="text-[11px] font-semibold text-stone-600 mb-2">
                      Guests ({selectedDayData.bookings_count})
                    </div>
                    <div className="space-y-1.5">
                      {selectedDayData.bookings.map((b, i) => (
                        <div key={i} className="flex items-center justify-between text-xs p-1.5 bg-stone-50 rounded">
                          <div className="flex items-center gap-1.5">
                            <Users size={12} className="text-stone-400" />
                            <span className="font-medium text-stone-700">{b.guest}</span>
                          </div>
                          <span className="text-stone-400 text-[10px]">{b.ref}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="bg-white border border-stone-200 rounded-xl p-8 text-center">
                <Eye size={28} className="text-stone-300 mx-auto mb-2" />
                <p className="text-sm text-stone-500">Click a day to view details</p>
              </div>
            )}

            {/* Room type summary */}
            {roomTypes.length > 0 && (
              <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="room-types-summary">
                <div className="text-[11px] font-semibold text-stone-600 mb-2 flex items-center gap-1.5">
                  <Bed size={13} className="text-blue-500" />
                  Room Types ({roomTypes.length})
                </div>
                <div className="space-y-1.5">
                  {roomTypes.map(rt => (
                    <div key={rt.id} className="flex items-center justify-between text-xs">
                      <span className="text-stone-600 truncate max-w-[140px]">{rt.name}</span>
                      <span className="text-stone-400">{rt.total_rooms} rooms</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
