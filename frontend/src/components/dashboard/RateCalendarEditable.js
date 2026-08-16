import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { X, Check, Edit3, Upload } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;

export const RateCalendarEditable = ({ propertyId }) => {
  const [cal, setCal] = useState(null);
  const [year, setYear] = useState(new Date().getFullYear());
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const [roomType, setRoomType] = useState("");
  const [viewMode, setViewMode] = useState("prices");
  const [editingDay, setEditingDay] = useState(null);
  const [editValue, setEditValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [bulkMode, setBulkMode] = useState(false);
  const [bulkDays, setBulkDays] = useState([]);
  const [bulkRate, setBulkRate] = useState("");
  const [holidays, setHolidays] = useState({});
  const [events, setEvents] = useState({});
  const [holidayPct, setHolidayPct] = useState(5);
  const [holidayPrompt, setHolidayPrompt] = useState(null);
  const [eventPrompt, setEventPrompt] = useState(null);
  const [bulkHolidayOpen, setBulkHolidayOpen] = useState(false);

  useEffect(() => {
    if (!propertyId) return;
    axios.get(`${API}/demand-signals/${propertyId}/events?days=90`)
      .then(r => {
        const map = {};
        (r.data.events || []).forEach(e => { map[e.date] = e; });
        setEvents(map);
      }).catch(() => {});
  }, [propertyId]);

  const applyBulkHoliday = async () => {
    try {
      const r = await axios.post(`${API}/demand-signals/${propertyId}/apply-holiday-markup`, {
        room_type_id: roomType || cal?.room_type?.id || ""
      });
      toast.success(`${r.data.applied.length} tatile +%${r.data.pct} zam uygulandı${r.data.skipped.length ? ` (${r.data.skipped.length} gün manuel override nedeniyle atlandı)` : ""}`);
      setBulkHolidayOpen(false);
      load();
    } catch { toast.error("Toplu zam uygulanamadı"); }
  };

  useEffect(() => {
    if (!propertyId) return;
    axios.get(`${API}/demand-signals/${propertyId}/config`)
      .then(r => setHolidayPct(Number(r.data.holiday_pct) || 5)).catch(() => {});
  }, [propertyId]);

  useEffect(() => {
    if (!propertyId) return;
    axios.get(`${API}/demand-signals/${propertyId}/holidays?days=90`)
      .then(r => {
        const map = {};
        (r.data.holidays || []).forEach(h => { map[h.date] = h.name; });
        setHolidays(map);
      }).catch(() => {});
  }, [propertyId]);

  const load = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/revenue/rate-calendar/${propertyId}?year=${year}&month=${month}${roomType ? `&room_type=${roomType}` : ""}`);
      setCal(data);
    } catch { toast.error("Failed"); }
  }, [propertyId, year, month, roomType]);
  useEffect(() => { load(); }, [load]);

  const navMonth = (dir) => {
    let nm = month + dir, ny = year;
    if (nm > 12) { nm = 1; ny++; }
    if (nm < 1) { nm = 12; ny--; }
    setMonth(nm); setYear(ny); setEditingDay(null); setBulkDays([]);
  };

  const saveRate = async (date, rate) => {
    setSaving(true);
    try {
      await axios.put(`${API}/revenue/rate-override/${propertyId}`, {
        date, custom_rate: rate || null, room_type_id: roomType || cal?.room_type?.id || ""
      });
      toast.success(rate ? `Rate set to £${rate}` : "Override removed");
      setEditingDay(null);
      setEditValue("");
      load();
    } catch { toast.error("Failed to save"); }
    setSaving(false);
  };

  const clearOverride = async (date) => {
    setSaving(true);
    try {
      await axios.put(`${API}/revenue/rate-override/${propertyId}`, {
        date, custom_rate: null, room_type_id: roomType || cal?.room_type?.id || ""
      });
      toast.success("Override cleared");
      load();
    } catch { toast.error("Failed"); }
    setSaving(false);
  };

  const saveBulk = async () => {
    if (!bulkRate || bulkDays.length === 0) { toast.error("Select days and enter a rate"); return; }
    setSaving(true);
    try {
      for (const date of bulkDays) {
        await axios.put(`${API}/revenue/rate-override/${propertyId}`, {
          date, custom_rate: Number(bulkRate), room_type_id: roomType || cal?.room_type?.id || ""
        });
      }
      toast.success(`Rate £${bulkRate} applied to ${bulkDays.length} days`);
      setBulkDays([]); setBulkRate(""); setBulkMode(false); load();
    } catch { toast.error("Failed"); }
    setSaving(false);
  };

  const toggleBulkDay = (date) => {
    setBulkDays(prev => prev.includes(date) ? prev.filter(d => d !== date) : [...prev, date]);
  };

  if (!cal) return <div className="text-center py-12 text-stone-400">Loading...</div>;

  const firstDow = new Date(year, month - 1, 1).getDay();
  const offset = firstDow === 0 ? 6 : firstDow - 1;
  const weeks = [];
  for (const d of cal.days) {
    const wi = Math.floor((offset + d.day - 1) / 7);
    const di = (offset + d.day - 1) % 7;
    if (!weeks[wi]) weeks[wi] = Array(7).fill(null);
    weeks[wi][di] = d;
  }
  const perf = cal.performance || {};
  const overrideCount = cal.days.filter(d => d.has_override).length;

  return (
    <div data-testid="rev-rate-calendar-tab">
      {/* Header */}
      <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <button onClick={() => navMonth(-1)} className="p-2 hover:bg-stone-100 rounded-lg text-stone-500" data-testid="rev-cal-prev">
            <svg className="w-5 h-5" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z"/></svg>
          </button>
          <h2 className="text-lg font-bold text-stone-800">{cal.month_name} {year}</h2>
          <button onClick={() => navMonth(1)} className="p-2 hover:bg-stone-100 rounded-lg text-stone-500" data-testid="rev-cal-next">
            <svg className="w-5 h-5" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"/></svg>
          </button>
        </div>
        <div className="flex items-center gap-2">
          {["prices", "occupancy", "pickup"].map(v => (
            <button key={v} onClick={() => setViewMode(v)}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg capitalize ${viewMode === v ? "bg-violet-600 text-white" : "text-stone-500 hover:bg-stone-100"}`}
              data-testid={`rev-cal-view-${v}`}>{v}</button>
          ))}
          <div className="w-px h-5 bg-stone-200 mx-1" />
          <button onClick={() => { setBulkMode(!bulkMode); setBulkDays([]); }}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg ${bulkMode ? "bg-amber-500 text-white" : "text-stone-500 hover:bg-stone-100 border border-stone-200"}`}
            data-testid="rev-cal-bulk">Bulk Edit</button>
          <button onClick={() => setBulkHolidayOpen(true)} disabled={Object.keys(holidays).length === 0}
            className="px-3 py-1.5 text-xs font-medium rounded-lg bg-teal-600 text-white disabled:opacity-40"
            data-testid="rev-cal-bulk-holiday-btn">🎌 Tüm Tatillere Zam</button>
        </div>
      </div>

      {/* Performance + Controls */}
      <div className="bg-white border border-stone-200 rounded-2xl p-5 mb-4">
        <div className="flex items-center gap-6 text-sm mb-4">
          <span><strong>{perf.occupancy}%</strong> Occupancy</span>
          <span><strong>{perf.expected_by_today}%</strong> Expected by Today</span>
          <span><strong>{perf.target}%</strong> Target</span>
          {overrideCount > 0 && <Badge className="bg-amber-100 text-amber-700 text-xs">{overrideCount} custom rate{overrideCount > 1 ? "s" : ""}</Badge>}
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <div>
            <label className="text-xs text-stone-500 mr-2">Room Type</label>
            <Select value={roomType || cal.room_type?.id || "default"} onValueChange={v => setRoomType(v)}>
              <SelectTrigger className="w-44 h-9 text-sm"><SelectValue /></SelectTrigger>
              <SelectContent>{[...new Map(cal.room_types.map(r => [r.id, r])).values()].map(r => <SelectItem key={r.id} value={r.id}>{r.name}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="text-xs text-stone-400 flex items-center gap-1">
            <Edit3 className="w-3 h-3" /> Click any day to set a custom rate
          </div>
        </div>
      </div>

      {/* Bulk Edit Bar */}
      {bulkMode && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-4 flex items-center gap-4" data-testid="rev-cal-bulk-bar">
          <span className="text-sm font-medium text-amber-800">Bulk Edit:</span>
          <span className="text-xs text-amber-600">{bulkDays.length} day{bulkDays.length !== 1 ? "s" : ""} selected</span>
          <Input type="number" value={bulkRate} onChange={e => setBulkRate(e.target.value)} placeholder="Rate (£)" className="w-28 h-8 text-sm" data-testid="rev-cal-bulk-rate" />
          <button onClick={saveBulk} disabled={saving || !bulkRate || bulkDays.length === 0}
            className="flex items-center gap-1 bg-amber-500 hover:bg-amber-600 text-white px-3 py-1.5 rounded-lg text-xs font-medium disabled:opacity-50" data-testid="rev-cal-bulk-save">
            <Upload className="w-3 h-3" />Apply to {bulkDays.length} days
          </button>
          <button onClick={() => { setBulkMode(false); setBulkDays([]); }} className="text-xs text-stone-500 hover:text-stone-700">Cancel</button>
        </div>
      )}

      {/* Calendar Grid */}
      <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden">
        <div className="grid grid-cols-7 border-b">
          {["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"].map(d => (
            <div key={d} className="px-2 py-2 text-center text-xs font-bold text-stone-500 border-r last:border-0">{d}</div>
          ))}
        </div>
        {weeks.map((w, wi) => (
          <div key={wi} className="grid grid-cols-7 border-b last:border-0">
            {w.map((d, di) => (
              <div key={di}
                className={`border-r last:border-0 min-h-[100px] p-2 transition-all cursor-pointer group relative ${
                  d?.is_today ? "bg-violet-50 ring-2 ring-violet-300 ring-inset" :
                  d?.has_override ? "bg-amber-50/50" :
                  bulkMode && d && bulkDays.includes(d.date) ? "bg-blue-50 ring-2 ring-blue-300 ring-inset" :
                  d ? "bg-white hover:bg-stone-50" : "bg-stone-50"
                }`}
                onClick={() => {
                  if (!d) return;
                  if (bulkMode) { toggleBulkDay(d.date); return; }
                  if (viewMode === "prices" && editingDay !== d.date) {
                    setEditingDay(d.date);
                    setEditValue(d.custom_rate || d.recommended_rate || "");
                  }
                }}
                data-testid={d ? `rev-cal-day-${d.day}` : undefined}>
                {d && <>
                  <div className="flex items-center justify-between mb-1">
                    <span className={`text-xs font-bold ${d.is_today ? "text-violet-700" : "text-stone-800"}`}>{d.day}</span>
                    <div className="flex items-center gap-0.5">
                      {d.is_today && <span className="text-[7px] bg-violet-600 text-white px-1 py-0.5 rounded-full font-bold">Today</span>}
                      {d.has_override && !bulkMode && (
                        <button onClick={(e) => { e.stopPropagation(); clearOverride(d.date); }}
                          className="opacity-0 group-hover:opacity-100 text-red-400 hover:text-red-600 transition-opacity" data-testid={`rev-cal-clear-${d.day}`}>
                          <X className="w-3 h-3" />
                        </button>
                      )}
                      {bulkMode && bulkDays.includes(d.date) && <Check className="w-3 h-3 text-blue-600" />}
                    </div>
                  </div>

                  {viewMode === "prices" && editingDay === d.date ? (
                    <div className="space-y-1" onClick={e => e.stopPropagation()}>
                      <Input type="number" value={editValue} onChange={e => setEditValue(e.target.value)} autoFocus
                        className="h-7 text-sm font-bold text-center w-full" data-testid={`rev-cal-edit-${d.day}`}
                        onKeyDown={e => { if (e.key === "Enter") saveRate(d.date, editValue); if (e.key === "Escape") setEditingDay(null); }} />
                      <div className="flex gap-1">
                        <button onClick={() => saveRate(d.date, editValue)} disabled={saving}
                          className="flex-1 bg-emerald-500 text-white text-[9px] py-0.5 rounded font-medium" data-testid={`rev-cal-save-${d.day}`}>
                          <Check className="w-2.5 h-2.5 mx-auto" />
                        </button>
                        <button onClick={() => setEditingDay(null)}
                          className="flex-1 bg-stone-200 text-stone-600 text-[9px] py-0.5 rounded font-medium">
                          <X className="w-2.5 h-2.5 mx-auto" />
                        </button>
                      </div>
                    </div>
                  ) : viewMode === "prices" ? (
                    <>
                      {d.has_override ? (
                        <>
                          <div className="text-sm font-bold text-amber-600">{cur(d.custom_rate)}</div>
                          <div className="text-[9px] text-stone-400 line-through">{cur(d.recommended_rate)} rec</div>
                        </>
                      ) : (
                        <>
                          <div className="text-sm font-bold text-violet-700">{cur(d.recommended_rate)}</div>
                          <div className="text-[10px] text-stone-400">{cur(d.pms_rate)} PMS</div>
                        </>
                      )}
                      <div className="opacity-0 group-hover:opacity-100 transition-opacity mt-0.5">
                        <span className="text-[8px] text-violet-500 font-medium flex items-center gap-0.5"><Edit3 className="w-2.5 h-2.5" />click to edit</span>
                      </div>
                    </>
                  ) : null}

                  {viewMode === "occupancy" && (
                    <>
                      <div className={`text-sm font-bold ${d.occupancy >= 70 ? "text-emerald-600" : d.occupancy >= 40 ? "text-amber-600" : "text-red-500"}`}>{d.occupancy}%</div>
                      <div className="text-[10px] text-stone-400">{d.booked}/{d.booked + d.available}</div>
                    </>
                  )}
                  {viewMode === "pickup" && (
                    <>
                      <div className="text-sm font-bold text-blue-600">{d.booked}</div>
                      <div className="text-[10px] text-stone-400">{d.available} avail</div>
                    </>
                  )}
                  {d.is_full && <Badge className="text-[8px] bg-emerald-500 text-white mt-1">Full</Badge>}
                  {(holidays[d.date] || events[d.date]) && (
                    <div className="absolute bottom-0 left-0 right-0 flex flex-col">
                      {events[d.date] && (
                        <div className="bg-violet-500/90 hover:bg-violet-600 text-white text-[8px] font-bold px-1.5 py-0.5 truncate cursor-pointer"
                          title={`${events[d.date].titles.join(" · ")} — etkinlik zammı önerisi için tıkla (+%${events[d.date].boost_pct})`}
                          data-testid={`rev-cal-event-${d.day}`}
                          onClick={(e) => {
                            e.stopPropagation();
                            const base = Math.round(Number(d.custom_rate || d.recommended_rate || 0));
                            const pct = Number(events[d.date].boost_pct) || 0;
                            setEventPrompt({ date: d.date, titles: events[d.date].titles, pct, base,
                              suggested: Math.round(base * (1 + pct / 100)) });
                          }}>
                          🎪 {events[d.date].titles[0]}{events[d.date].titles.length > 1 ? ` +${events[d.date].titles.length - 1}` : ""}
                        </div>
                      )}
                      {holidays[d.date] && (
                        <div className="bg-teal-500/90 hover:bg-teal-600 text-white text-[8px] font-bold px-1.5 py-0.5 truncate cursor-pointer"
                          title={`${holidays[d.date]} — tatil zammı önerisi için tıkla`} data-testid={`rev-cal-holiday-${d.day}`}
                          onClick={(e) => {
                            e.stopPropagation();
                            const base = Math.round(Number(d.custom_rate || d.recommended_rate || 0));
                            setHolidayPrompt({ date: d.date, day: d.day, name: holidays[d.date], base,
                              suggested: Math.round(base * (1 + holidayPct / 100)) });
                          }}>
                          🎌 {holidays[d.date]}
                        </div>
                      )}
                    </div>
                  )}
                </>}
              </div>
            ))}
          </div>
        ))}
      </div>

      {/* Bulk Holiday Markup Confirm */}
      {bulkHolidayOpen && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center" onClick={() => setBulkHolidayOpen(false)}>
          <div className="bg-white rounded-2xl p-5 w-[400px] shadow-2xl" onClick={e => e.stopPropagation()} data-testid="rev-cal-bulk-holiday-modal">
            <div className="text-sm font-black text-stone-800 mb-1">🎌 Tüm Tatillere Toplu Zam</div>
            <p className="text-xs text-stone-500 mb-3">Önümüzdeki 90 gündeki <b>{Object.keys(holidays).length} resmi tatile</b> önerilen <b className="text-teal-700">+%{holidayPct}</b> zam uygulanacak. Manuel girdiğiniz fiyatlar korunur; sadece otomatik/tatil günleri güncellenir.</p>
            <div className="max-h-36 overflow-auto space-y-1 mb-4">
              {Object.entries(holidays).sort().map(([d, n]) => (
                <div key={d} className="text-[11px] bg-teal-50 border border-teal-100 rounded px-2 py-1">{d} — {n}</div>
              ))}
            </div>
            <div className="flex gap-2">
              <button onClick={applyBulkHoliday} className="flex-1 bg-teal-600 hover:bg-teal-700 text-white text-sm font-bold py-2 rounded-xl" data-testid="rev-cal-bulk-holiday-apply">Onayla ve Uygula</button>
              <button onClick={() => setBulkHolidayOpen(false)} className="px-4 py-2 border border-stone-300 rounded-xl text-sm text-stone-600" data-testid="rev-cal-bulk-holiday-cancel">Vazgeç</button>
            </div>
          </div>
        </div>
      )}

      {/* Event Rate Prompt */}
      {eventPrompt && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center" onClick={() => setEventPrompt(null)}>
          <div className="bg-white rounded-2xl p-5 w-[380px] shadow-2xl" onClick={e => e.stopPropagation()} data-testid="rev-cal-event-modal">
            <div className="text-sm font-black text-stone-800 mb-1">🎪 {eventPrompt.titles.join(" · ")}</div>
            <div className="text-xs text-stone-500 mb-3">{eventPrompt.date} — etkinlik sinyaline göre önerilen zam: <b className="text-violet-700">+%{eventPrompt.pct}</b> (kapasite × mesafe ağırlıklı boost)</div>
            <div className="flex items-center justify-center gap-3 bg-violet-50 border border-violet-200 rounded-xl py-3 mb-4">
              <span className="text-sm text-stone-500 line-through">{cur(eventPrompt.base)}</span>
              <span className="text-stone-400">→</span>
              <span className="text-xl font-black text-violet-700" data-testid="rev-cal-event-suggested">{cur(eventPrompt.suggested)}</span>
            </div>
            <div className="flex gap-2">
              <button onClick={async () => { await saveRate(eventPrompt.date, eventPrompt.suggested); setEventPrompt(null); }}
                disabled={saving || !eventPrompt.base || eventPrompt.pct <= 0}
                className="flex-1 bg-violet-600 hover:bg-violet-700 text-white text-sm font-bold py-2 rounded-xl disabled:opacity-50" data-testid="rev-cal-event-apply">
                Zammı Uygula
              </button>
              <button onClick={() => setEventPrompt(null)} className="px-4 py-2 border border-stone-300 rounded-xl text-sm text-stone-600" data-testid="rev-cal-event-cancel">Vazgeç</button>
            </div>
          </div>
        </div>
      )}

      {/* Holiday Rate Prompt */}
      {holidayPrompt && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center" onClick={() => setHolidayPrompt(null)}>
          <div className="bg-white rounded-2xl p-5 w-[360px] shadow-2xl" onClick={e => e.stopPropagation()} data-testid="rev-cal-holiday-modal">
            <div className="text-sm font-black text-stone-800 mb-1">🎌 {holidayPrompt.name}</div>
            <div className="text-xs text-stone-500 mb-3">{holidayPrompt.date} — resmi tatil için önerilen zam: <b className="text-teal-700">+%{holidayPct}</b> (sinyal ayarlarındaki tatil çarpanı)</div>
            <div className="flex items-center justify-center gap-3 bg-teal-50 border border-teal-200 rounded-xl py-3 mb-4">
              <span className="text-sm text-stone-500 line-through">{cur(holidayPrompt.base)}</span>
              <span className="text-stone-400">→</span>
              <span className="text-xl font-black text-teal-700" data-testid="rev-cal-holiday-suggested">{cur(holidayPrompt.suggested)}</span>
            </div>
            <div className="flex gap-2">
              <button onClick={async () => { await saveRate(holidayPrompt.date, holidayPrompt.suggested); setHolidayPrompt(null); }}
                disabled={saving || !holidayPrompt.base}
                className="flex-1 bg-teal-600 hover:bg-teal-700 text-white text-sm font-bold py-2 rounded-xl disabled:opacity-50" data-testid="rev-cal-holiday-apply">
                Zammı Uygula
              </button>
              <button onClick={() => setHolidayPrompt(null)} className="px-4 py-2 border border-stone-300 rounded-xl text-sm text-stone-600" data-testid="rev-cal-holiday-cancel">Vazgeç</button>
            </div>
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="flex items-center gap-4 mt-3 text-[10px] text-stone-400">
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-violet-50 border border-violet-300" />Today</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-amber-50 border border-amber-200" />Custom Rate</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-white border border-stone-200" />Auto-priced</span>
        <span className="flex items-center gap-1" data-testid="rev-cal-holiday-legend"><span className="w-3 h-3 rounded bg-teal-500" />Resmi Tatil (90 gün)</span>
        <span className="flex items-center gap-1" data-testid="rev-cal-event-legend"><span className="w-3 h-3 rounded bg-violet-500" />Etkinlik (konser/fuar)</span>
      </div>
    </div>
  );
};
