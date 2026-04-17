import { useState, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Radar, Search, Plus, Trash2, Users, Music, Trophy, Flag, Tent, Mic2, Building2, Calendar, Zap, TrendingUp, AlertTriangle } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const CATEGORY_ICONS = { concert: Music, sports: Trophy, marathon: Flag, festival: Tent, exhibition: Building2, conference: Mic2, theatre: Mic2, other: Calendar };
const IMPACT_COLORS = { mega: "bg-red-500 text-white", large: "bg-orange-500 text-white", medium: "bg-amber-400 text-white", small: "bg-blue-400 text-white" };
const IMPACT_BORDER = { mega: "border-red-200 bg-red-50/30", large: "border-orange-200 bg-orange-50/30", medium: "border-amber-200 bg-amber-50/30", small: "border-blue-200 bg-blue-50/30" };

export const EventIntelligence = ({ propertyId }) => {
  const [events, setEvents] = useState([]);
  const [counts, setCounts] = useState({});
  const [scanning, setScanning] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", date: "", end_date: "", venue: "", category: "concert", estimated_attendance: 50000, description: "" });
  const [scanResult, setScanResult] = useState(null);

  const load = () => {
    axios.get(`${API}/revenue/events/${propertyId}`).then(r => { setEvents(r.data.events || []); setCounts(r.data.counts || {}); }).catch(() => {});
  };
  useEffect(() => { load(); }, [propertyId]);

  const scan = async () => {
    setScanning(true);
    setScanResult(null);
    try {
      const { data } = await axios.post(`${API}/revenue/events/${propertyId}/scan`, { days_ahead: 90, auto_price: true });
      setScanResult(data);
      toast.success(`Found ${data.events_found} events, ${data.prices_adjusted} prices adjusted`);
      load();
    } catch { toast.error("Scan failed"); }
    setScanning(false);
  };

  const addManual = async () => {
    if (!form.name || !form.date) { toast.error("Name and date required"); return; }
    try {
      const { data } = await axios.post(`${API}/revenue/events/${propertyId}/add`, form);
      toast.success(`${form.name} added, ${data.prices_adjusted} prices adjusted`);
      setShowForm(false);
      setForm({ name: "", date: "", end_date: "", venue: "", category: "concert", estimated_attendance: 50000, description: "" });
      load();
    } catch { toast.error("Failed"); }
  };

  const remove = async (id) => {
    try { await axios.delete(`${API}/revenue/events/${id}`); toast.success("Removed"); load(); } catch { toast.error("Failed"); }
  };

  // Group events by month
  const eventsByMonth = {};
  events.forEach(e => {
    const month = e.date?.slice(0, 7) || "unknown";
    if (!eventsByMonth[month]) eventsByMonth[month] = [];
    eventsByMonth[month].push(e);
  });

  return (
    <div className="space-y-6" data-testid="event-intelligence">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 bg-gradient-to-br from-red-500 to-orange-500 rounded-xl flex items-center justify-center">
            <Radar className="w-6 h-6 text-white" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-stone-800">Event Intelligence</h2>
            <p className="text-xs text-stone-400">AI-powered event detection for demand-based pricing</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setShowForm(!showForm)} className="flex items-center gap-1.5 border border-stone-200 text-stone-600 px-3 py-2 rounded-xl text-sm font-medium hover:bg-stone-50" data-testid="event-add-manual">
            <Plus className="w-4 h-4" />Add Event
          </button>
          <button onClick={scan} disabled={scanning}
            className="flex items-center gap-2 bg-red-500 hover:bg-red-600 text-white px-5 py-2.5 rounded-xl text-sm font-semibold disabled:opacity-50" data-testid="event-scan">
            {scanning ? <Search className="w-4 h-4 animate-spin" /> : <Radar className="w-4 h-4" />}
            {scanning ? "Scanning Events..." : "Scan Events (AI)"}
          </button>
        </div>
      </div>

      {/* Scan Result */}
      {scanResult && (
        <div className="bg-gradient-to-r from-red-50 to-orange-50 border border-red-200 rounded-xl p-4" data-testid="event-scan-result">
          <div className="flex items-center gap-2 mb-2">
            <Zap className="w-5 h-5 text-red-500" />
            <span className="font-bold text-red-800">AI Scan Complete</span>
          </div>
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div><span className="text-red-500">Events Found:</span> <strong>{scanResult.events_found}</strong></div>
            <div><span className="text-red-500">Stored:</span> <strong>{scanResult.events_stored}</strong></div>
            <div><span className="text-red-500">Prices Adjusted:</span> <strong>{scanResult.prices_adjusted}</strong></div>
          </div>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-5 gap-3" data-testid="event-kpis">
        {[
          { label: "Critical Demand", value: counts.critical || counts.mega || 0, sub: "HDS 80+ (fills hotels)", cls: "text-red-500" },
          { label: "High Demand", value: counts.high || counts.large || 0, sub: "HDS 60-79 (strong impact)", cls: "text-orange-500" },
          { label: "Moderate", value: counts.moderate || counts.medium || 0, sub: "HDS 40-59", cls: "text-amber-500" },
          { label: "Low Impact", value: counts.low || counts.small || 0, sub: "HDS 20-39", cls: "text-blue-500" },
          { label: "Total Events", value: counts.total || 0, sub: "Hotel-demand events only", cls: "text-violet-600" },
        ].map(k => (
          <div key={k.label} className="bg-white border border-stone-200 rounded-2xl p-4 text-center">
            <p className={`text-2xl font-bold ${k.cls}`}>{k.value}</p>
            <p className="text-[10px] text-stone-400 mt-0.5">{k.label}</p>
            <p className="text-[9px] text-stone-300">{k.sub}</p>
          </div>
        ))}
      </div>

      {/* Smart Hotel Demand Info */}
      <div className="bg-stone-800 rounded-xl p-4 text-white">
        <p className="text-xs font-bold text-cyan-300 mb-1">Smart Hotel Demand Scoring</p>
        <p className="text-[10px] text-white/50 leading-relaxed">Events scored by <strong>Hotel Demand Score (HDS 0-100)</strong> — not just attendance. A 60k local derby scores LOW (fans go home). A 20k UEFA match scores HIGH (away fans need hotels). Evening events, multi-day festivals, touring concerts score highest.</p>
      </div>

      {/* Manual Add Form */}
      {showForm && (
        <div className="bg-white border border-stone-200 rounded-2xl p-5" data-testid="event-form">
          <h3 className="font-bold text-stone-800 mb-4">Add Event Manually</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <Input value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))} placeholder="Event name *" data-testid="event-form-name" />
            <Input type="date" value={form.date} onChange={e => setForm(p => ({ ...p, date: e.target.value }))} data-testid="event-form-date" />
            <Input type="date" value={form.end_date} onChange={e => setForm(p => ({ ...p, end_date: e.target.value }))} placeholder="End date (if multi-day)" />
            <Input value={form.venue} onChange={e => setForm(p => ({ ...p, venue: e.target.value }))} placeholder="Venue" />
            <Select value={form.category} onValueChange={v => setForm(p => ({ ...p, category: v }))}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {["concert","sports","marathon","festival","exhibition","conference","theatre","other"].map(c => <SelectItem key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</SelectItem>)}
              </SelectContent>
            </Select>
            <Input type="number" value={form.estimated_attendance} onChange={e => setForm(p => ({ ...p, estimated_attendance: Number(e.target.value) }))} placeholder="Expected attendance" data-testid="event-form-attendance" />
            <Input type="number" value={form.hotel_demand_score || ""} onChange={e => setForm(p => ({ ...p, hotel_demand_score: Number(e.target.value) }))} placeholder="Hotel Demand Score (0-100)" data-testid="event-form-hds" />
            <Select value={form.visitor_origin || "regional"} onValueChange={v => setForm(p => ({ ...p, visitor_origin: v }))}>
              <SelectTrigger><SelectValue placeholder="Visitor Origin" /></SelectTrigger>
              <SelectContent>
                {["international","national","regional","local"].map(c => <SelectItem key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="mt-3">
            <Input value={form.description} onChange={e => setForm(p => ({ ...p, description: e.target.value }))} placeholder="Description (optional)" />
          </div>
          <div className="flex justify-end gap-2 mt-3">
            <button onClick={() => setShowForm(false)} className="border border-stone-200 text-stone-500 px-4 py-2 rounded-xl text-sm">Cancel</button>
            <button onClick={addManual} className="bg-emerald-500 hover:bg-emerald-600 text-white px-5 py-2 rounded-xl text-sm font-semibold" data-testid="event-form-save">Add & Auto-Price</button>
          </div>
          <div className="mt-3 bg-stone-50 rounded-lg p-3">
            <p className="text-[10px] text-stone-400"><strong>Smart pricing:</strong> Events are scored by Hotel Demand Score (HDS). Critical (HDS 80+): +45%, High (60-79): +30%, Moderate (40-59): +15%, Low (20-39): +5%. Local events where fans go home get minimal/no boost.</p>
          </div>
        </div>
      )}

      {/* Impact Legend */}
      <div className="flex items-center gap-3 text-xs">
        {Object.entries(IMPACT_LEVELS_DISPLAY).map(([key, info]) => (
          <span key={key} className="flex items-center gap-1.5">
            <span className={`w-3 h-3 rounded-full ${info.dot}`} />
            <span className="text-stone-500">{info.label}: +{info.boost}%</span>
          </span>
        ))}
      </div>

      {/* Events List grouped by month */}
      {events.length === 0 ? (
        <div className="bg-white border border-stone-200 rounded-2xl p-12 text-center">
          <Radar className="w-14 h-14 text-stone-200 mx-auto mb-3" />
          <h3 className="font-bold text-stone-600 text-lg mb-1">No Events Detected</h3>
          <p className="text-sm text-stone-400 mb-4">Click "Scan Events (AI)" to detect upcoming concerts, matches, exhibitions, and more using GPT-5.2.</p>
        </div>
      ) : Object.entries(eventsByMonth).map(([month, monthEvents]) => (
        <div key={month}>
          <h3 className="text-sm font-bold text-stone-500 mb-3 uppercase tracking-wider">
            {new Date(month + "-01").toLocaleDateString("en", { month: "long", year: "numeric" })}
          </h3>
          <div className="space-y-2">
            {monthEvents.map(event => {
              const Icon = CATEGORY_ICONS[event.category] || Calendar;
              return (
                <div key={event.id || event.name} className={`border rounded-xl p-4 transition-all hover:shadow-md ${IMPACT_BORDER[event.impact] || "border-stone-200 bg-white"}`} data-testid={`event-${event.id}`}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                        event.impact === "mega" ? "bg-red-100" : event.impact === "large" ? "bg-orange-100" : event.impact === "medium" ? "bg-amber-100" : "bg-blue-100"
                      }`}>
                        <Icon className={`w-5 h-5 ${
                          event.impact === "mega" ? "text-red-500" : event.impact === "large" ? "text-orange-500" : event.impact === "medium" ? "text-amber-500" : "text-blue-500"
                        }`} />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-stone-800">{event.name}</span>
                          <Badge className={`text-[9px] ${IMPACT_COLORS[event.impact] || "bg-stone-200 text-stone-600"}`}>
                            {event.impact?.toUpperCase()}
                          </Badge>
                          <Badge className="text-[9px] bg-stone-100 text-stone-500 capitalize">{event.category}</Badge>
                          {event.confidence && <Badge className={`text-[9px] ${event.confidence === "high" ? "bg-emerald-100 text-emerald-700" : event.confidence === "medium" ? "bg-amber-100 text-amber-700" : "bg-stone-100 text-stone-500"}`}>{event.confidence}</Badge>}
                        </div>
                        <div className="flex items-center gap-4 mt-1 text-xs text-stone-400">
                          <span>{new Date(event.date + "T00:00:00").toLocaleDateString("en", { weekday: "short", month: "short", day: "numeric" })}{event.end_date && event.end_date !== event.date ? ` — ${new Date(event.end_date + "T00:00:00").toLocaleDateString("en", { month: "short", day: "numeric" })}` : ""}</span>
                          {event.venue && <span>{event.venue}</span>}
                          {event.estimated_attendance > 0 && <span className="flex items-center gap-0.5"><Users className="w-3 h-3" />{event.estimated_attendance.toLocaleString()} expected</span>}
                        </div>
                        {event.description && <p className="text-xs text-stone-400 mt-1">{event.description}</p>}
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="text-right">
                        <p className={`text-sm font-bold ${event.impact === "mega" || event.impact === "critical" ? "text-red-500" : event.impact === "large" || event.impact === "high" ? "text-orange-500" : "text-amber-500"}`}>
                          HDS: {event.hotel_demand_score || "—"}
                        </p>
                        <p className="text-[10px] text-stone-400">{event.visitor_origin || "—"}{event.is_evening ? " | evening" : ""}</p>
                        {event.reasoning && <p className="text-[9px] text-stone-300 max-w-[180px] text-right">{event.reasoning}</p>}
                      </div>
                      <button onClick={() => remove(event.id)} className="text-stone-300 hover:text-red-500 p-1 transition-colors">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
};

const IMPACT_LEVELS_DISPLAY = {
  critical: { label: "Critical (HDS 80+)", boost: 45, dot: "bg-red-500" },
  high: { label: "High (HDS 60-79)", boost: 30, dot: "bg-orange-500" },
  moderate: { label: "Moderate (HDS 40-59)", boost: 15, dot: "bg-amber-400" },
  low: { label: "Low (HDS 20-39)", boost: 5, dot: "bg-blue-400" },
};
