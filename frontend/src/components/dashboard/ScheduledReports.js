import { useState, useEffect } from "react";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import {
  RefreshCw, Plus, FileText, Clock, Mail, Trash2, Play, Settings2, Calendar,
  BarChart3, Users, Bed, Sparkles, CheckCircle
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const REPORT_TYPES = [
  { id: "daily_summary", label: "Daily Summary", icon: Calendar },
  { id: "weekly_summary", label: "Weekly Summary", icon: BarChart3 },
  { id: "monthly_summary", label: "Monthly Summary", icon: BarChart3 },
];

const FREQ_OPTIONS = [
  { id: "daily", label: "Daily" },
  { id: "weekly", label: "Weekly" },
  { id: "monthly", label: "Monthly" },
];

const SECTION_OPTIONS = [
  { id: "occupancy", label: "Occupancy" },
  { id: "revenue", label: "Revenue" },
  { id: "arrivals", label: "Arrivals" },
  { id: "departures", label: "Departures" },
  { id: "housekeeping", label: "Housekeeping" },
];

export const ScheduledReports = ({ propertyId }) => {
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [preview, setPreview] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [form, setForm] = useState({
    name: "Daily Summary", type: "daily_summary", frequency: "daily",
    time: "08:00", recipients: "", sections: ["occupancy", "revenue", "arrivals", "departures", "housekeeping"],
    format: "pdf", enabled: true,
  });

  const pid = propertyId || "all";

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/scheduled-reports/${pid}`);
      setReports(data.reports || []);
    } catch { /* silent */ }
    setLoading(false);
  };

  useEffect(() => { load(); }, [pid]);

  const createReport = async () => {
    try {
      await axios.post(`${API}/scheduled-reports/${pid}`, {
        ...form,
        recipients: form.recipients.split(",").map(e => e.trim()).filter(Boolean),
      });
      toast.success("Report scheduled");
      setShowCreate(false);
      load();
    } catch { toast.error("Failed to create"); }
  };

  const deleteReport = async (id) => {
    try {
      await axios.delete(`${API}/scheduled-reports/${pid}/${id}`);
      toast.success("Report deleted");
      load();
    } catch { toast.error("Failed"); }
  };

  const toggleReport = async (id, enabled) => {
    try {
      await axios.put(`${API}/scheduled-reports/${pid}/${id}`, { enabled: !enabled });
      load();
    } catch { /* silent */ }
  };

  const generateNow = async (id) => {
    setGenerating(true);
    try {
      const { data } = id
        ? await axios.post(`${API}/scheduled-reports/${pid}/generate-now/${id}`)
        : await axios.post(`${API}/scheduled-reports/${pid}/preview`);
      setPreview(data);
      toast.success("Report generated");
    } catch { toast.error("Generation failed"); }
    setGenerating(false);
  };

  const toggleSection = (s) => {
    setForm(prev => ({
      ...prev,
      sections: prev.sections.includes(s) ? prev.sections.filter(x => x !== s) : [...prev.sections, s],
    }));
  };

  if (loading) return <div className="flex items-center justify-center py-20 text-stone-400"><RefreshCw className="w-5 h-5 animate-spin mr-2" />Loading...</div>;

  return (
    <div className="space-y-5" data-testid="scheduled-reports">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-stone-800" data-testid="reports-title">Scheduled Reports</h2>
          <p className="text-xs text-stone-500">Auto-generate and email reports to your team</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => generateNow(null)} disabled={generating} data-testid="preview-report-btn"
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold text-stone-600 bg-white border border-stone-200 rounded-lg hover:bg-stone-50">
            <Play className="w-3.5 h-3.5" />{generating ? "Generating..." : "Preview Report"}
          </button>
          <button onClick={() => setShowCreate(true)} data-testid="create-report-btn"
            className="flex items-center gap-1.5 px-4 py-2 text-xs font-bold text-white bg-stone-800 rounded-lg hover:bg-stone-700">
            <Plus className="w-3.5 h-3.5" />Schedule Report
          </button>
        </div>
      </div>

      {/* Create Form */}
      {showCreate && (
        <div className="bg-white border border-stone-200 rounded-xl p-5 space-y-4" data-testid="create-report-form">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-[10px] text-stone-500 uppercase block mb-1">Report Name</label>
              <input value={form.name} onChange={e => setForm({...form, name: e.target.value})}
                className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="text-[10px] text-stone-500 uppercase block mb-1">Frequency</label>
              <select value={form.frequency} onChange={e => setForm({...form, frequency: e.target.value})}
                className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm">
                {FREQ_OPTIONS.map(f => <option key={f.id} value={f.id}>{f.label}</option>)}
              </select>
            </div>
            <div>
              <label className="text-[10px] text-stone-500 uppercase block mb-1">Send Time</label>
              <input type="time" value={form.time} onChange={e => setForm({...form, time: e.target.value})}
                className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="text-[10px] text-stone-500 uppercase block mb-1">Recipients (comma-separated)</label>
              <input value={form.recipients} onChange={e => setForm({...form, recipients: e.target.value})} placeholder="manager@hotel.com, gm@hotel.com"
                className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" />
            </div>
          </div>
          <div>
            <label className="text-[10px] text-stone-500 uppercase block mb-2">Sections</label>
            <div className="flex flex-wrap gap-2">
              {SECTION_OPTIONS.map(s => (
                <button key={s.id} onClick={() => toggleSection(s.id)} data-testid={`section-${s.id}`}
                  className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-all ${form.sections.includes(s.id) ? "bg-stone-800 text-white border-stone-800" : "bg-white text-stone-500 border-stone-200"}`}>
                  {s.label}
                </button>
              ))}
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <button onClick={() => setShowCreate(false)} className="px-4 py-2 text-xs text-stone-500 hover:text-stone-700">Cancel</button>
            <button onClick={createReport} data-testid="save-report-btn"
              className="px-4 py-2 text-xs font-bold text-white bg-emerald-500 rounded-lg hover:bg-emerald-600">Save Schedule</button>
          </div>
        </div>
      )}

      {/* Report List */}
      <div className="space-y-3" data-testid="report-list">
        {reports.length === 0 && !showCreate ? (
          <div className="bg-white border border-stone-200 rounded-xl p-12 text-center">
            <FileText className="w-10 h-10 text-stone-300 mx-auto mb-3" />
            <p className="text-sm font-bold text-stone-700">No scheduled reports yet</p>
            <p className="text-xs text-stone-400 mt-1">Create your first report to auto-email daily summaries to your team</p>
          </div>
        ) : (
          reports.map(r => (
            <div key={r.id} className={`bg-white border rounded-xl p-4 flex items-center justify-between ${r.enabled ? "border-stone-200" : "border-stone-100 opacity-60"}`} data-testid={`report-${r.id}`}>
              <div className="flex items-center gap-3">
                <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${r.enabled ? "bg-emerald-50" : "bg-stone-100"}`}>
                  <FileText className={`w-4 h-4 ${r.enabled ? "text-emerald-600" : "text-stone-400"}`} />
                </div>
                <div>
                  <p className="text-sm font-bold text-stone-800">{r.name}</p>
                  <div className="flex items-center gap-2 text-[10px] text-stone-400">
                    <span className="flex items-center gap-0.5"><Clock className="w-3 h-3" />{r.frequency} at {r.time}</span>
                    <span className="flex items-center gap-0.5"><Mail className="w-3 h-3" />{(r.recipients || []).length} recipient(s)</span>
                    {r.last_sent && <span>Last: {new Date(r.last_sent).toLocaleDateString("en-GB")}</span>}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge className={`text-[9px] ${r.enabled ? "bg-emerald-50 text-emerald-700" : "bg-stone-100 text-stone-500"}`}>{r.enabled ? "Active" : "Paused"}</Badge>
                <button onClick={() => toggleReport(r.id, r.enabled)} className="p-1.5 text-stone-400 hover:text-stone-600 rounded-lg hover:bg-stone-100">
                  <Settings2 className="w-3.5 h-3.5" />
                </button>
                <button onClick={() => generateNow(r.id)} className="p-1.5 text-emerald-500 hover:text-emerald-700 rounded-lg hover:bg-emerald-50" data-testid={`run-report-${r.id}`}>
                  <Play className="w-3.5 h-3.5" />
                </button>
                <button onClick={() => deleteReport(r.id)} className="p-1.5 text-red-400 hover:text-red-600 rounded-lg hover:bg-red-50">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Preview */}
      {preview && (
        <div className="bg-white border border-stone-200 rounded-xl p-5" data-testid="report-preview">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-bold text-stone-800">{preview.report_type?.replace("_", " ").replace(/\b\w/g, l => l.toUpperCase())}</h3>
              <p className="text-[10px] text-stone-400">{preview.property} — {new Date(preview.generated_at).toLocaleString("en-GB")}</p>
            </div>
            <button onClick={() => setPreview(null)} className="text-stone-400 hover:text-stone-600 text-xs">Close</button>
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
            {preview.sections?.occupancy && (
              <div className="bg-blue-50 rounded-xl p-3 text-center">
                <Bed className="w-4 h-4 mx-auto mb-1 text-blue-600" />
                <p className="text-xl font-black text-blue-700">{preview.sections.occupancy.occupancy_pct}%</p>
                <p className="text-[9px] text-blue-500">Occupancy ({preview.sections.occupancy.booked}/{preview.sections.occupancy.total_rooms})</p>
              </div>
            )}
            {preview.sections?.revenue && (
              <div className="bg-emerald-50 rounded-xl p-3 text-center">
                <BarChart3 className="w-4 h-4 mx-auto mb-1 text-emerald-600" />
                <p className="text-xl font-black text-emerald-700">£{preview.sections.revenue.todays_revenue}</p>
                <p className="text-[9px] text-emerald-500">Revenue (ADR: £{preview.sections.revenue.avg_daily_rate})</p>
              </div>
            )}
            {preview.sections?.arrivals && (
              <div className="bg-amber-50 rounded-xl p-3 text-center">
                <Users className="w-4 h-4 mx-auto mb-1 text-amber-600" />
                <p className="text-xl font-black text-amber-700">{preview.sections.arrivals.count}</p>
                <p className="text-[9px] text-amber-500">Arrivals today</p>
              </div>
            )}
            {preview.sections?.departures && (
              <div className="bg-violet-50 rounded-xl p-3 text-center">
                <Users className="w-4 h-4 mx-auto mb-1 text-violet-600" />
                <p className="text-xl font-black text-violet-700">{preview.sections.departures.count}</p>
                <p className="text-[9px] text-violet-500">Departures today</p>
              </div>
            )}
            {preview.sections?.housekeeping && (
              <div className="bg-stone-50 rounded-xl p-3 text-center">
                <Sparkles className="w-4 h-4 mx-auto mb-1 text-stone-600" />
                <p className="text-xl font-black text-stone-700">{preview.sections.housekeeping.clean + preview.sections.housekeeping.inspected}</p>
                <p className="text-[9px] text-stone-500">Clean ({preview.sections.housekeeping.dirty} dirty)</p>
              </div>
            )}
          </div>

          {preview.sections?.arrivals?.guests?.length > 0 && (
            <div className="mt-4">
              <p className="text-[10px] text-stone-500 uppercase font-bold mb-2">Today's Arrivals</p>
              <div className="space-y-1">
                {preview.sections.arrivals.guests.map((g, i) => (
                  <div key={i} className="flex items-center justify-between text-xs py-1 border-b border-stone-100">
                    <span className="font-medium text-stone-700">{g.name}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-stone-400">{g.nights} night(s)</span>
                      <Badge className="text-[8px] bg-stone-100 text-stone-600">{g.status}</Badge>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
