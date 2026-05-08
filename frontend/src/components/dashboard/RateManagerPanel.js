import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { motion } from "framer-motion";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Plus, Trash2, Calendar, TrendingUp, DollarSign, Percent, Sun, Snowflake } from "lucide-react";
import { Lightning, CalendarBlank, CurrencyDollar, ArrowsClockwise } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];
const DAY_SHORT = { monday: "Mon", tuesday: "Tue", wednesday: "Wed", thursday: "Thu", friday: "Fri", saturday: "Sat", sunday: "Sun" };

export function RateManagerPanel({ properties, activePropertyId: propId }) {
  const activePropertyId = propId || "all";
  const [plans, setPlans] = useState([]);
  const [seasons, setSeasons] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedPlan, setSelectedPlan] = useState(null);
  const [calendar, setCalendar] = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const [showSeason, setShowSeason] = useState(false);
  const [tab, setTab] = useState("plans"); // plans, calendar, seasons

  const fetchData = useCallback(async () => {
    try {
      const [plansRes, seasonsRes] = await Promise.all([
        axios.get(`${API}/rate-manager/plans/${activePropertyId}`),
        axios.get(`${API}/rate-manager/seasons/${activePropertyId}`),
      ]);
      setPlans(plansRes.data);
      setSeasons(seasonsRes.data);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [activePropertyId]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const loadCalendar = async (plan) => {
    setSelectedPlan(plan);
    try {
      const { data } = await axios.get(`${API}/rate-manager/calendar/${plan.id}`);
      setCalendar(data);
      setTab("calendar");
    } catch { toast.error("Failed to load calendar"); }
  };

  return (
    <div className="p-6 space-y-5" data-testid="rate-manager-panel">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-stone-800" data-testid="rate-manager-title">Rate Manager</h1>
          <p className="text-sm text-stone-500 mt-0.5">Dynamic pricing — occupancy, seasons, day-of-week</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setShowSeason(true)} className="px-3 py-2 text-xs font-medium border border-stone-200 rounded-lg hover:bg-stone-50 flex items-center gap-1.5" data-testid="btn-add-season">
            <Sun size={14} /> Add Season
          </button>
          <button onClick={() => setShowCreate(true)} className="px-4 py-2 bg-[#1e3a5f] text-white text-sm font-semibold rounded-lg hover:bg-[#15304f] flex items-center gap-1.5" data-testid="btn-new-plan">
            <Plus size={14} /> New Rate Plan
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-stone-100 p-1 rounded-lg w-fit" data-testid="rate-tabs">
        {[
          { id: "plans", label: "Rate Plans", icon: <DollarSign size={13} /> },
          { id: "calendar", label: "Rate Calendar", icon: <Calendar size={13} /> },
          { id: "seasons", label: "Seasons", icon: <Sun size={13} /> },
        ].map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} className={`px-3 py-1.5 text-xs font-medium rounded-md flex items-center gap-1.5 transition ${tab === t.id ? "bg-white shadow-sm text-stone-800" : "text-stone-500"}`} data-testid={`rate-tab-${t.id}`}>
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {/* Plans Tab */}
      {tab === "plans" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4" data-testid="plans-grid">
          {plans.length === 0 && !loading && (
            <div className="col-span-2 p-12 text-center text-stone-400 bg-white rounded-xl border border-stone-200/60">
              <DollarSign className="w-10 h-10 mx-auto mb-3 text-stone-300" />
              <p className="text-sm">No rate plans yet. Create one to start dynamic pricing.</p>
            </div>
          )}
          {plans.map(plan => (
            <div key={plan.id} className="bg-white rounded-xl border border-stone-200/60 p-5 hover:shadow-sm transition" data-testid={`plan-${plan.id}`}>
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h3 className="text-base font-semibold text-stone-800">{plan.name}</h3>
                  <p className="text-xs text-stone-400">{plan.room_type || "All rooms"}</p>
                </div>
                <div className="text-right">
                  <p className="text-2xl font-bold text-[#1e3a5f]">{plan.currency} {plan.base_rate}</p>
                  <p className="text-[10px] text-stone-400">base rate / night</p>
                </div>
              </div>

              {/* Day multipliers bar */}
              <div className="flex gap-1 mb-3" data-testid="day-bars">
                {DAYS.map(d => {
                  const m = plan.day_multipliers?.[d] || 1;
                  const pct = Math.min((m / 2) * 100, 100);
                  return (
                    <div key={d} className="flex-1 text-center">
                      <div className="h-8 bg-stone-100 rounded-sm relative overflow-hidden">
                        <div className={`absolute bottom-0 left-0 right-0 rounded-sm ${m > 1.2 ? "bg-emerald-400" : m < 0.9 ? "bg-red-300" : "bg-blue-300"}`} style={{ height: `${pct}%` }} />
                      </div>
                      <p className="text-[8px] text-stone-400 mt-0.5">{DAY_SHORT[d]}</p>
                      <p className="text-[8px] font-bold text-stone-600">{m}x</p>
                    </div>
                  );
                })}
              </div>

              {/* Occupancy rules */}
              <div className="flex gap-2 flex-wrap mb-3">
                {(plan.occupancy_rules || []).map((r, i) => (
                  <span key={i} className="text-[9px] px-2 py-0.5 bg-stone-100 rounded text-stone-600">
                    {r.threshold}%+ occ → +{r.adjustment}%
                  </span>
                ))}
              </div>

              {plan.min_rate > 0 && <p className="text-[10px] text-stone-400">Min: {plan.currency} {plan.min_rate} / Max: {plan.currency} {plan.max_rate}</p>}

              <div className="flex gap-2 mt-3 pt-3 border-t border-stone-100">
                <button onClick={() => loadCalendar(plan)} className="flex-1 py-2 text-xs font-medium text-[#1e3a5f] border border-[#1e3a5f]/20 rounded-lg hover:bg-[#1e3a5f]/5 flex items-center justify-center gap-1.5" data-testid={`btn-calendar-${plan.id}`}>
                  <Calendar size={12} /> View Calendar
                </button>
                <button onClick={async () => { await axios.delete(`${API}/rate-manager/plans/${plan.id}`); toast.success("Deleted"); fetchData(); }} className="px-3 py-2 text-xs text-red-500 border border-red-200 rounded-lg hover:bg-red-50" data-testid={`btn-delete-plan-${plan.id}`}>
                  <Trash2 size={12} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Calendar Tab */}
      {tab === "calendar" && calendar && (
        <div className="space-y-4" data-testid="rate-calendar">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-semibold text-stone-800">{calendar.plan_name} — 30 Day Forecast</h3>
              <p className="text-xs text-stone-500">Estimated rates based on occupancy & day-of-week rules</p>
            </div>
            <button onClick={() => setTab("plans")} className="text-xs text-stone-500 hover:text-stone-700">Back to plans</button>
          </div>
          <div className="bg-white rounded-xl border border-stone-200/60 overflow-hidden">
            <div className="grid grid-cols-[80px_1fr_80px_70px_80px] gap-2 px-4 py-2.5 bg-stone-50 text-[10px] font-semibold text-stone-500 uppercase tracking-wide border-b">
              <span>Date</span><span>Rate</span><span>Base</span><span>Mult.</span><span>Est. Occ</span>
            </div>
            <ScrollArea className="max-h-[50vh]">
              {calendar.days.map((day, i) => {
                const diff = day.calculated_rate - day.base_rate;
                const pct = day.base_rate > 0 ? Math.round((diff / day.base_rate) * 100) : 0;
                return (
                  <div key={i} className={`grid grid-cols-[80px_1fr_80px_70px_80px] gap-2 px-4 py-2.5 border-b border-stone-100 items-center ${day.is_weekend ? "bg-amber-50/30" : ""}`} data-testid={`cal-day-${day.date}`}>
                    <div>
                      <p className="text-xs font-medium text-stone-800">{day.day}</p>
                      <p className="text-[10px] text-stone-400">{new Date(day.date + "T00:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" })}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-base font-bold text-[#1e3a5f]">{calendar.currency} {day.calculated_rate}</span>
                      {diff !== 0 && (
                        <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${diff > 0 ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}>
                          {diff > 0 ? "+" : ""}{pct}%
                        </span>
                      )}
                    </div>
                    <span className="text-xs text-stone-500">{calendar.currency} {day.base_rate}</span>
                    <span className="text-xs text-stone-600">{day.multiplier}x</span>
                    <div className="flex items-center gap-1">
                      <div className="flex-1 h-1.5 bg-stone-100 rounded-full overflow-hidden">
                        <div className={`h-full rounded-full ${day.est_occupancy > 85 ? "bg-red-400" : day.est_occupancy > 70 ? "bg-amber-400" : "bg-emerald-400"}`} style={{ width: `${day.est_occupancy}%` }} />
                      </div>
                      <span className="text-[10px] text-stone-500 w-8 text-right">{day.est_occupancy}%</span>
                    </div>
                  </div>
                );
              })}
            </ScrollArea>
          </div>
        </div>
      )}

      {/* Seasons Tab */}
      {tab === "seasons" && (
        <div className="space-y-4" data-testid="seasons-tab">
          <p className="text-sm text-stone-500">Define seasonal pricing periods that apply across your rate plans</p>
          <div className="bg-white rounded-xl border border-stone-200/60 overflow-hidden">
            <div className="grid grid-cols-[1fr_100px_100px_100px_60px] gap-2 px-4 py-2.5 bg-stone-50 text-[10px] font-semibold text-stone-500 uppercase border-b">
              <span>Season</span><span>Start</span><span>End</span><span>Adjustment</span><span></span>
            </div>
            {seasons.length === 0 ? (
              <div className="p-8 text-center text-stone-400 text-sm">No seasons defined. Add high/low season periods.</div>
            ) : seasons.map(s => (
              <div key={s.id} className="grid grid-cols-[1fr_100px_100px_100px_60px] gap-2 px-4 py-3 border-b border-stone-100 items-center" data-testid={`season-${s.id}`}>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full" style={{ background: s.color || "#3b82f6" }} />
                  <span className="text-sm font-medium text-stone-800">{s.name}</span>
                </div>
                <span className="text-xs text-stone-600">{s.start_date}</span>
                <span className="text-xs text-stone-600">{s.end_date}</span>
                <span className={`text-xs font-bold ${s.adjustment_pct > 0 ? "text-emerald-600" : s.adjustment_pct < 0 ? "text-red-600" : "text-stone-500"}`}>
                  {s.adjustment_pct > 0 ? "+" : ""}{s.adjustment_pct}%
                </span>
                <button onClick={async () => { await axios.delete(`${API}/rate-manager/seasons/${s.id}`); toast.success("Deleted"); fetchData(); }} className="p-1 text-stone-400 hover:text-red-500">
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Create Plan Dialog */}
      <CreatePlanDialog open={showCreate} onClose={() => setShowCreate(false)} propertyId={activePropertyId} seasons={seasons} onCreated={() => { setShowCreate(false); fetchData(); }} />

      {/* Create Season Dialog */}
      <CreateSeasonDialog open={showSeason} onClose={() => setShowSeason(false)} propertyId={activePropertyId} onCreated={() => { setShowSeason(false); fetchData(); }} />
    </div>
  );
}

function CreatePlanDialog({ open, onClose, propertyId, seasons, onCreated }) {
  const [form, setForm] = useState({
    name: "", room_type: "", base_rate: 100, currency: "GBP", min_rate: 0, max_rate: 0,
    day_multipliers: { monday: 1, tuesday: 1, wednesday: 1, thursday: 1, friday: 1.1, saturday: 1.2, sunday: 1.1 },
    occupancy_rules: [
      { threshold: 50, adjustment: 0 },
      { threshold: 70, adjustment: 10 },
      { threshold: 85, adjustment: 25 },
      { threshold: 95, adjustment: 50 },
    ],
  });

  const create = async () => {
    if (!form.name) return;
    try {
      await axios.post(`${API}/rate-manager/plans`, { ...form, property_id: propertyId, seasons });
      toast.success("Rate plan created!"); onCreated();
    } catch { toast.error("Failed"); }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-lg" data-testid="create-plan-dialog">
        <DialogHeader><DialogTitle>New Rate Plan</DialogTitle></DialogHeader>
        <ScrollArea className="max-h-[60vh]">
          <div className="space-y-4 pr-2">
            <div className="grid grid-cols-2 gap-3">
              <div><label className="text-xs font-medium text-stone-600 mb-1 block">Plan Name *</label>
                <Input value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))} placeholder="e.g. Standard Pricing" data-testid="plan-name" /></div>
              <div><label className="text-xs font-medium text-stone-600 mb-1 block">Room Type</label>
                <Input value={form.room_type} onChange={e => setForm(p => ({ ...p, room_type: e.target.value }))} placeholder="e.g. Deluxe, Standard" /></div>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div><label className="text-xs font-medium text-stone-600 mb-1 block">Base Rate *</label>
                <Input type="number" value={form.base_rate} onChange={e => setForm(p => ({ ...p, base_rate: Number(e.target.value) }))} data-testid="plan-base-rate" /></div>
              <div><label className="text-xs font-medium text-stone-600 mb-1 block">Min Rate</label>
                <Input type="number" value={form.min_rate} onChange={e => setForm(p => ({ ...p, min_rate: Number(e.target.value) }))} /></div>
              <div><label className="text-xs font-medium text-stone-600 mb-1 block">Max Rate</label>
                <Input type="number" value={form.max_rate} onChange={e => setForm(p => ({ ...p, max_rate: Number(e.target.value) }))} /></div>
            </div>

            {/* Day Multipliers */}
            <div>
              <label className="text-xs font-semibold text-stone-700 mb-2 block">Day-of-Week Multipliers</label>
              <div className="grid grid-cols-7 gap-1.5">
                {DAYS.map(d => (
                  <div key={d} className="text-center">
                    <p className="text-[9px] text-stone-500 mb-1">{DAY_SHORT[d]}</p>
                    <Input type="number" step="0.1" min="0.5" max="3" value={form.day_multipliers[d]} onChange={e => setForm(p => ({ ...p, day_multipliers: { ...p.day_multipliers, [d]: Number(e.target.value) } }))} className="h-8 text-xs text-center p-0" data-testid={`mult-${d}`} />
                  </div>
                ))}
              </div>
              <p className="text-[10px] text-stone-400 mt-1">1.0 = base rate, 1.2 = +20%, 0.8 = -20%</p>
            </div>

            {/* Occupancy Rules */}
            <div>
              <label className="text-xs font-semibold text-stone-700 mb-2 block">Occupancy-Based Pricing</label>
              <div className="space-y-1.5">
                {form.occupancy_rules.map((rule, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <span className="text-xs text-stone-500 w-6">{rule.threshold}%+</span>
                    <div className="flex-1 h-1.5 bg-stone-100 rounded-full overflow-hidden">
                      <div className={`h-full rounded-full ${rule.adjustment > 20 ? "bg-emerald-500" : rule.adjustment > 0 ? "bg-blue-400" : "bg-stone-300"}`} style={{ width: `${Math.min(rule.adjustment + 10, 100)}%` }} />
                    </div>
                    <Input type="number" value={rule.adjustment} onChange={e => {
                      const rules = [...form.occupancy_rules];
                      rules[i] = { ...rules[i], adjustment: Number(e.target.value) };
                      setForm(p => ({ ...p, occupancy_rules: rules }));
                    }} className="w-16 h-7 text-xs text-center" />
                    <span className="text-[10px] text-stone-400">%</span>
                  </div>
                ))}
              </div>
            </div>

            <button onClick={create} className="w-full py-2.5 bg-[#1e3a5f] text-white text-sm font-bold rounded-xl" data-testid="btn-create-plan">Create Rate Plan</button>
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
}

function CreateSeasonDialog({ open, onClose, propertyId, onCreated }) {
  const [form, setForm] = useState({ name: "", start_date: "", end_date: "", adjustment_pct: 20, color: "#3b82f6" });

  const create = async () => {
    if (!form.name || !form.start_date || !form.end_date) return;
    try {
      await axios.post(`${API}/rate-manager/seasons`, { ...form, property_id: propertyId });
      toast.success("Season created!"); setForm({ name: "", start_date: "", end_date: "", adjustment_pct: 20, color: "#3b82f6" }); onCreated();
    } catch { toast.error("Failed"); }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-sm" data-testid="create-season-dialog">
        <DialogHeader><DialogTitle>Add Season</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <Input value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))} placeholder="e.g. Summer Peak, Christmas" data-testid="season-name" />
          <div className="grid grid-cols-2 gap-3">
            <div><label className="text-xs text-stone-600 mb-1 block">Start Date</label>
              <Input type="date" value={form.start_date} onChange={e => setForm(p => ({ ...p, start_date: e.target.value }))} data-testid="season-start" /></div>
            <div><label className="text-xs text-stone-600 mb-1 block">End Date</label>
              <Input type="date" value={form.end_date} onChange={e => setForm(p => ({ ...p, end_date: e.target.value }))} data-testid="season-end" /></div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className="text-xs text-stone-600 mb-1 block">Rate Adjustment %</label>
              <Input type="number" value={form.adjustment_pct} onChange={e => setForm(p => ({ ...p, adjustment_pct: Number(e.target.value) }))} data-testid="season-adj" />
              <p className="text-[10px] text-stone-400 mt-0.5">+20 = 20% higher, -15 = 15% lower</p></div>
            <div><label className="text-xs text-stone-600 mb-1 block">Color</label>
              <input type="color" value={form.color} onChange={e => setForm(p => ({ ...p, color: e.target.value }))} className="w-full h-9 rounded-lg cursor-pointer" /></div>
          </div>
          <button onClick={create} className="w-full py-2.5 bg-[#1e3a5f] text-white text-sm font-bold rounded-xl" data-testid="btn-create-season">Add Season</button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
