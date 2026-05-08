import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  Copy,
  Sparkles,
  Trash2,
  Plus,
  AlertTriangle,
  X,
  Send,
  Users,
  TrendingUp,
  Clock,
  Coffee,
  Sun,
  Moon,
  Sunrise,
  CheckCircle,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const PRESETS = [
  { id: "morning", label: "Sabah", time: "07:00–15:00", start: "07:00", end: "15:00", color: "#10b981", icon: Sunrise },
  { id: "afternoon", label: "Öğle", time: "12:00–20:00", start: "12:00", end: "20:00", color: "#06b6d4", icon: Sun },
  { id: "evening", label: "Akşam", time: "15:00–23:00", start: "15:00", end: "23:00", color: "#8b5cf6", icon: Coffee },
  { id: "night", label: "Gece", time: "23:00–07:00", start: "23:00", end: "07:00", color: "#ef4444", icon: Moon },
];

const STATUS_COLORS = {
  draft: "ring-stone-300 bg-stone-50",
  planned: "ring-stone-300 bg-stone-100",
  published: "ring-blue-400 bg-blue-50",
  approved: "ring-emerald-400 bg-emerald-50",
  completed: "ring-violet-400 bg-violet-50",
};

const ROLE_BADGE = {
  receptionist: "bg-emerald-100 text-emerald-700",
  housekeeper: "bg-sky-100 text-sky-700",
  maintenance: "bg-amber-100 text-amber-700",
  chef: "bg-rose-100 text-rose-700",
};

// Vivid, well-spaced hues — each ~22° apart on the color wheel for max distinction.
// Each cell uses the SOLID color so staff and shift visually match 1:1.
const STAFF_PALETTE = [
  { solid: "#dc2626", soft: "#fee2e2", text: "#ffffff" }, // red
  { solid: "#ea580c", soft: "#ffedd5", text: "#ffffff" }, // orange
  { solid: "#ca8a04", soft: "#fef9c3", text: "#ffffff" }, // amber-dark
  { solid: "#16a34a", soft: "#dcfce7", text: "#ffffff" }, // green
  { solid: "#0891b2", soft: "#cffafe", text: "#ffffff" }, // cyan
  { solid: "#2563eb", soft: "#dbeafe", text: "#ffffff" }, // blue
  { solid: "#7c3aed", soft: "#ede9fe", text: "#ffffff" }, // violet
  { solid: "#c026d3", soft: "#f5d0fe", text: "#ffffff" }, // fuchsia
  { solid: "#db2777", soft: "#fce7f3", text: "#ffffff" }, // pink
  { solid: "#0d9488", soft: "#ccfbf1", text: "#ffffff" }, // teal
  { solid: "#65a30d", soft: "#ecfccb", text: "#ffffff" }, // lime
  { solid: "#4338ca", soft: "#e0e7ff", text: "#ffffff" }, // indigo
  { solid: "#0284c7", soft: "#e0f2fe", text: "#ffffff" }, // sky
  { solid: "#9333ea", soft: "#f3e8ff", text: "#ffffff" }, // purple
  { solid: "#be123c", soft: "#ffe4e6", text: "#ffffff" }, // rose
  { solid: "#1e293b", soft: "#e2e8f0", text: "#ffffff" }, // slate-dark
];

function colorForStaff(staffId) {
  const id = String(staffId || "");
  let h = 0;
  for (let i = 0; i < id.length; i += 1) h = (h * 31 + id.charCodeAt(i)) >>> 0;
  return STAFF_PALETTE[h % STAFF_PALETTE.length];
}

function startOfWeekISO(d) {
  const x = new Date(d);
  const dow = x.getDay() || 7; // Mon=1
  x.setDate(x.getDate() - (dow - 1));
  return x.toISOString().slice(0, 10);
}
function addDays(iso, n) {
  const d = new Date(iso);
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
}
function fmtDate(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString("tr-TR", { day: "2-digit", month: "short" });
}

export const ShiftScheduler = ({ propertyId }) => {
  const pid = propertyId || "all";
  const [weekStart, setWeekStart] = useState(() => startOfWeekISO(new Date()));
  const [staff, setStaff] = useState([]);
  const [shifts, setShifts] = useState([]);
  const [conflicts, setConflicts] = useState([]);
  const [needs, setNeeds] = useState([]);
  const [payroll, setPayroll] = useState([]);
  const [loading, setLoading] = useState(false);
  const [editor, setEditor] = useState(null); // {staff, date, shift?}
  const [aiBusy, setAiBusy] = useState(false);
  const [aiPreview, setAiPreview] = useState(null);
  const dragRef = useRef(null);

  const days = useMemo(
    () => Array.from({ length: 7 }, (_, i) => addDays(weekStart, i)),
    [weekStart]
  );

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const [s, e, c, n, p] = await Promise.all([
        axios.get(`${API}/shifts/staff/${pid}`, { withCredentials: true }),
        axios.get(`${API}/shifts/entries/${pid}?week_start=${weekStart}`, { withCredentials: true }),
        axios.get(`${API}/shifts/conflicts/${pid}?week_start=${weekStart}`, { withCredentials: true }),
        axios.get(`${API}/shifts/occupancy-needs/${pid}?week_start=${weekStart}`, { withCredentials: true }),
        axios.get(`${API}/shifts/payroll/${pid}?week_start=${weekStart}`, { withCredentials: true }),
      ]);
      setStaff(s.data || []);
      setShifts(e.data || []);
      setConflicts(c.data?.conflicts || []);
      setNeeds(n.data?.days || []);
      setPayroll(p.data || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [pid, weekStart]);

  useEffect(() => { reload(); }, [reload]);

  const shiftAt = (staffId, date) =>
    shifts.find((s) => s.staff_id === staffId && s.date === date);

  const conflictsAt = (staffId, date) =>
    conflicts.filter((c) => c.staff_id === staffId && (!c.date || c.date === date));

  const totalCost = useMemo(
    () => payroll.reduce((a, b) => a + (b.total_pay || 0), 0),
    [payroll]
  );
  const totalHours = useMemo(
    () => payroll.reduce((a, b) => a + (b.total_hours || 0), 0),
    [payroll]
  );

  async function saveShift({ staff: st, date, preset, start_time, end_time, notes, status }) {
    try {
      const startT = preset?.start || start_time || "09:00";
      const endT = preset?.end || end_time || "17:00";
      const payRate = parseFloat(st.pay_rate) || 0;
      const payType = st.pay_type || "daily";
      const [sh, sm] = startT.split(":").map(Number);
      const [eh, em] = endT.split(":").map(Number);
      let hrs = ((eh * 60 + em) - (sh * 60 + sm)) / 60;
      if (hrs < 0) hrs += 24;
      const earned = payType === "hourly" ? Math.round(hrs * payRate * 100) / 100 : payRate;
      await axios.post(
        `${API}/shifts/entries`,
        {
          property_id: st.property_id || pid,
          staff_id: st.id,
          staff_name: st.name,
          role: st.role,
          date,
          week_start: weekStart,
          start_time: startT,
          end_time: endT,
          hours_worked: Math.round(hrs * 100) / 100,
          pay_type: payType,
          pay_rate: payRate,
          earned_amount: earned,
          status: status || "planned",
          notes: notes || "",
        },
        { withCredentials: true }
      );
      toast.success("Vardiya eklendi");
      setEditor(null);
      reload();
    } catch (e) {
      toast.error("Kayıt başarısız");
    }
  }

  async function deleteShift(shift) {
    if (!shift?.id) return;
    try {
      await axios.delete(`${API}/shifts/entries/${shift.id}`, { withCredentials: true });
      toast.success("Vardiya silindi");
      setEditor(null);
      reload();
    } catch (e) {
      toast.error("Silme başarısız");
    }
  }

  async function copyPrevWeek() {
    const prev = addDays(weekStart, -7);
    if (!confirm(`${prev} haftası kopyalansın mı?`)) return;
    try {
      await axios.post(
        `${API}/shifts/bulk/copy-week`,
        { source_week: prev, target_week: weekStart, property_id: pid },
        { withCredentials: true }
      );
      toast.success("Hafta kopyalandı");
      reload();
    } catch {
      toast.error("Kopyalama başarısız");
    }
  }

  async function publishAll() {
    try {
      const r = await axios.post(
        `${API}/shifts/bulk/publish-all`,
        { week_start: weekStart, property_id: pid },
        { withCredentials: true }
      );
      toast.success(`${r.data.published} vardiya yayınlandı`);
      reload();
    } catch {
      toast.error("Yayınlama başarısız");
    }
  }

  async function clearWeek() {
    if (!confirm("Bu haftadaki TÜM vardiyalar silinsin mi?")) return;
    try {
      await axios.post(
        `${API}/shifts/bulk/clear-week`,
        { week_start: weekStart, property_id: pid },
        { withCredentials: true }
      );
      toast.success("Hafta temizlendi");
      reload();
    } catch {
      toast.error("Temizleme başarısız");
    }
  }

  async function aiSuggest() {
    setAiBusy(true);
    try {
      const r = await axios.post(
        `${API}/shifts/ai-suggest/${pid}`,
        { week_start: weekStart },
        { withCredentials: true }
      );
      const list = r.data?.suggestions || [];
      if (list.length === 0) {
        toast.error("AI öneri üretemedi — personel listesini kontrol edin");
      } else {
        setAiPreview({ list, week_start: weekStart });
        toast.success(`AI ${list.length} vardiya önerdi`);
      }
    } catch {
      toast.error("AI çağrısı başarısız");
    }
    setAiBusy(false);
  }

  async function aiApply() {
    if (!aiPreview) return;
    try {
      await axios.post(
        `${API}/shifts/ai-apply/${pid}`,
        { week_start: aiPreview.week_start, suggestions: aiPreview.list },
        { withCredentials: true }
      );
      toast.success(`${aiPreview.list.length} öneri taslak olarak eklendi`);
      setAiPreview(null);
      reload();
    } catch {
      toast.error("Uygulama başarısız");
    }
  }

  // ==================== Drag & Drop ====================
  function onDragStart(e, shift) {
    dragRef.current = shift;
    e.dataTransfer.effectAllowed = "move";
  }
  async function onDrop(e, staffId, date) {
    e.preventDefault();
    const s = dragRef.current;
    dragRef.current = null;
    if (!s || (s.staff_id === staffId && s.date === date)) return;
    try {
      await axios.put(
        `${API}/shifts/entries/${s.id}`,
        { staff_id: staffId, date, week_start: weekStart },
        { withCredentials: true }
      );
      toast.success("Vardiya taşındı");
      reload();
    } catch {
      toast.error("Taşıma başarısız");
    }
  }

  return (
    <div className="space-y-4" data-testid="shift-scheduler-v2">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Vardiya Planlayıcı <span className="text-emerald-600 text-sm font-medium ml-1">RotaPro v2</span></h1>
          <p className="text-sm text-stone-500">
            Drag & drop · Şablonlar · AI auto-schedule · TR İş Kanunu uyumu · Doluluğa göre öneri
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => setWeekStart(addDays(weekStart, -7))}
            className="p-2 rounded-md bg-stone-100 hover:bg-stone-200"
            data-testid="prev-week-btn"
          >
            <ChevronLeft size={16} />
          </button>
          <span className="text-sm font-medium px-2" data-testid="week-label">
            {fmtDate(weekStart)} — {fmtDate(addDays(weekStart, 6))}
          </span>
          <button
            onClick={() => setWeekStart(addDays(weekStart, 7))}
            className="p-2 rounded-md bg-stone-100 hover:bg-stone-200"
            data-testid="next-week-btn"
          >
            <ChevronRight size={16} />
          </button>
          <button
            onClick={() => setWeekStart(startOfWeekISO(new Date()))}
            className="text-xs px-3 py-2 rounded-md bg-stone-100 hover:bg-stone-200"
            data-testid="this-week-btn"
          >
            Bu hafta
          </button>
          <button
            onClick={reload}
            className="p-2 rounded-md bg-stone-100 hover:bg-stone-200"
            disabled={loading}
            data-testid="reload-btn"
          >
            <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
          </button>
        </div>
      </div>

      {/* Stats strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Toplam saat" value={`${totalHours.toFixed(1)}h`} icon={Clock} color="text-sky-600" />
        <Stat label="Haftalık maliyet" value={`£${totalCost.toFixed(2)}`} icon={TrendingUp} color="text-emerald-600" />
        <Stat label="Personel" value={staff.length} icon={Users} color="text-violet-600" />
        <Stat
          label="Çakışma"
          value={conflicts.length}
          icon={AlertTriangle}
          color={conflicts.length ? "text-red-600" : "text-stone-400"}
          testId="conflicts-count"
        />
      </div>

      {/* Action buttons */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={copyPrevWeek}
          className="text-sm px-3 py-2 rounded-md bg-stone-800 text-white hover:bg-stone-900 inline-flex items-center gap-2"
          data-testid="copy-prev-week-btn"
        >
          <Copy size={14} /> Önceki haftayı kopyala
        </button>
        <button
          onClick={aiSuggest}
          disabled={aiBusy}
          className="text-sm px-3 py-2 rounded-md bg-gradient-to-r from-violet-500 to-fuchsia-500 text-white hover:opacity-90 inline-flex items-center gap-2 disabled:opacity-50"
          data-testid="ai-suggest-btn"
        >
          <Sparkles size={14} /> {aiBusy ? "AI düşünüyor…" : "AI Auto-Schedule"}
        </button>
        <button
          onClick={publishAll}
          className="text-sm px-3 py-2 rounded-md bg-emerald-600 text-white hover:bg-emerald-700 inline-flex items-center gap-2"
          data-testid="publish-all-btn"
        >
          <Send size={14} /> Tümünü yayınla
        </button>
        <button
          onClick={clearWeek}
          className="text-sm px-3 py-2 rounded-md bg-red-50 text-red-700 hover:bg-red-100 inline-flex items-center gap-2"
          data-testid="clear-week-btn"
        >
          <Trash2 size={14} /> Haftayı temizle
        </button>
      </div>

      {/* Conflicts banner */}
      {conflicts.length > 0 && (
        <div
          className="rounded-xl border border-red-200 bg-red-50/70 p-3 space-y-1"
          data-testid="conflicts-panel"
        >
          <div className="flex items-center gap-2 font-semibold text-red-800 text-sm">
            <AlertTriangle size={14} /> {conflicts.length} çakışma / uyarı
          </div>
          <ul className="text-xs text-red-700 space-y-0.5 max-h-32 overflow-y-auto">
            {conflicts.slice(0, 8).map((c, i) => (
              <li key={i}>
                <span className="font-medium">{c.staff_name}</span> · {c.message}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* AI preview */}
      {aiPreview && (
        <div className="rounded-xl border border-violet-200 bg-violet-50 p-3 space-y-2" data-testid="ai-preview">
          <div className="flex items-center justify-between">
            <div className="text-sm font-semibold text-violet-800 inline-flex items-center gap-1.5">
              <Sparkles size={14} /> AI {aiPreview.list.length} vardiya önerdi
            </div>
            <div className="flex gap-2">
              <button
                onClick={aiApply}
                className="text-xs px-3 py-1.5 rounded-md bg-violet-600 text-white"
                data-testid="ai-apply-btn"
              >
                Taslak olarak ekle
              </button>
              <button
                onClick={() => setAiPreview(null)}
                className="text-xs px-2 py-1.5 rounded-md bg-stone-200"
                data-testid="ai-cancel-btn"
              >
                Reddet
              </button>
            </div>
          </div>
          <div className="text-xs text-stone-600 line-clamp-2">
            Doluluğa göre öneriler: {aiPreview.list.slice(0, 5).map((s) =>
              `${s.role} ${s.start_time}-${s.end_time}`
            ).join(" · ")}{aiPreview.list.length > 5 ? "…" : ""}
          </div>
        </div>
      )}

      {/* Grid */}
      <div className="border rounded-xl bg-white overflow-x-auto">
        <table className="w-full text-xs" data-testid="shift-grid">
          <thead>
            <tr className="text-stone-500 border-b">
              <th className="text-left px-3 py-3 sticky left-0 bg-white z-10 min-w-[180px]">Personel</th>
              {days.map((d) => {
                const need = needs.find((n) => n.date === d);
                const dt = new Date(d);
                return (
                  <th key={d} className="px-2 py-2 min-w-[160px]">
                    <div className="font-medium text-stone-700 capitalize">
                      {dt.toLocaleDateString("tr-TR", { weekday: "short" })}
                    </div>
                    <div className="text-stone-400">{fmtDate(d)}</div>
                    {need && (
                      <div className="text-[10px] mt-1 text-stone-500">
                        Doluluk: <span className={need.occupancy_pct > 70 ? "text-red-600 font-semibold" : "text-emerald-700"}>
                          {need.occupancy_pct}%
                        </span>
                      </div>
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {staff.length === 0 && (
              <tr>
                <td colSpan={8} className="text-center text-stone-400 py-12 text-sm">
                  Henüz personel yok. Önce <span className="font-medium">Personel Yönetimi</span>'nden ekleyin
                  veya AI Auto-Schedule butonu ile başlayın.
                </td>
              </tr>
            )}
            {staff.map((st) => {
              const total = payroll.find((p) => p.staff_id === st.id);
              const c = colorForStaff(st.id);
              return (
                <tr key={st.id} className="border-b last:border-b-0 hover:bg-stone-50">
                  <td className="px-3 py-2 sticky left-0 bg-white z-10" style={{ borderLeft: `4px solid ${c.solid}` }}>
                    <div className="flex items-start gap-2">
                      <span
                        className="shrink-0 w-7 h-7 rounded-full flex items-center justify-center font-semibold text-[12px]"
                        style={{ backgroundColor: c.solid, color: c.text }}
                        data-testid={`staff-avatar-${st.id}`}
                      >
                        {(st.name || "?").trim().split(/\s+/).map(s => s[0]).slice(0, 2).join("").toUpperCase()}
                      </span>
                      <div className="min-w-0">
                        <div className="font-medium text-stone-800 truncate">{st.name}</div>
                        <div className="flex items-center gap-1 mt-0.5 flex-wrap">
                          <span className={`text-[10px] px-1.5 py-0.5 rounded ${ROLE_BADGE[st.role] || "bg-stone-100"}`}>
                            {st.role}
                          </span>
                          <span className="text-[10px] text-stone-400">
                            £{st.pay_rate}/{st.pay_type === "hourly" ? "sa" : "gün"}
                          </span>
                        </div>
                        {total && (
                          <div className="text-[10px] text-stone-500 mt-1">
                            {total.total_hours?.toFixed(1)}h · £{total.total_pay?.toFixed(2)}
                          </div>
                        )}
                      </div>
                    </div>
                  </td>
                  {days.map((d) => {
                    const sh = shiftAt(st.id, d);
                    const cf = conflictsAt(st.id, d);
                    return (
                      <td
                        key={d}
                        className="px-1.5 py-1.5"
                        onDragOver={(e) => e.preventDefault()}
                        onDrop={(e) => onDrop(e, st.id, d)}
                      >
                        {sh ? (
                          <div
                            draggable
                            onDragStart={(e) => onDragStart(e, sh)}
                            onClick={() => setEditor({ staff: st, date: d, shift: sh })}
                            className={`cursor-grab active:cursor-grabbing rounded-lg px-2 py-1.5 text-[11px] hover:shadow-lg transition relative font-medium`}
                            style={{
                              backgroundColor: c.solid,
                              color: c.text,
                              boxShadow: sh.status === "approved"
                                ? `0 0 0 2px white, 0 0 0 4px ${c.solid}`
                                : sh.status === "published"
                                  ? `0 0 0 1px white, 0 0 0 2px ${c.solid}`
                                  : "none",
                              opacity: sh.status === "draft" ? 0.55 : 1,
                            }}
                            data-testid={`shift-${st.id}-${d}`}
                          >
                            <div className="font-semibold leading-tight">
                              {sh.start_time}–{sh.end_time}
                            </div>
                            <div className="text-[10px]" style={{ color: c.text, opacity: 0.85 }}>
                              {sh.hours_worked?.toFixed?.(1) || sh.hours_worked}h · £{sh.earned_amount?.toFixed?.(2) || sh.earned_amount}
                            </div>
                            {cf.length > 0 && (
                              <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-red-600 text-white text-[9px] flex items-center justify-center font-bold ring-2 ring-white">
                                !
                              </span>
                            )}
                            {sh.status === "approved" && (
                              <CheckCircle size={10} className="absolute -bottom-0.5 -right-0.5 text-emerald-600 bg-white rounded-full" />
                            )}
                          </div>
                        ) : (
                          <button
                            onClick={() => setEditor({ staff: st, date: d })}
                            className="w-full h-12 rounded-lg border border-dashed border-stone-200 text-stone-300 hover:border-emerald-400 hover:text-emerald-500 hover:bg-emerald-50 transition flex items-center justify-center"
                            data-testid={`add-shift-${st.id}-${d}`}
                          >
                            <Plus size={14} />
                          </button>
                        )}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Status legend */}
      <div className="flex items-center gap-3 flex-wrap text-xs text-stone-500">
        <span className="font-medium text-stone-600">Durum:</span>
        <span className="inline-flex items-center gap-1.5"><span className="w-3 h-3 rounded opacity-70 bg-stone-400" /> Taslak</span>
        <span className="inline-flex items-center gap-1.5"><span className="w-3 h-3 rounded ring-1 ring-stone-500 bg-stone-200" /> Yayında</span>
        <span className="inline-flex items-center gap-1.5"><span className="w-3 h-3 rounded ring-2 ring-stone-700 bg-stone-200" /> Onaylı</span>
        <span>·</span>
        <span><span className="font-medium text-stone-600">Renk</span> = personel kimliği · hücreyi sürükleyerek başka güne/personele taşıyın</span>
      </div>

      {/* Editor modal */}
      {editor && (
        <ShiftEditor
          editor={editor}
          onSave={saveShift}
          onDelete={deleteShift}
          onClose={() => setEditor(null)}
        />
      )}
    </div>
  );
};

function Stat({ label, value, icon: Icon, color, testId }) {
  return (
    <div className="rounded-xl border bg-white p-3" data-testid={testId}>
      <div className="text-[10px] uppercase tracking-wider text-stone-500 mb-1 flex items-center gap-1">
        <Icon size={11} /> {label}
      </div>
      <div className={`text-xl font-semibold ${color}`}>{value}</div>
    </div>
  );
}

function Legend() { return null; } // kept as no-op for backward compat


function ShiftEditor({ editor, onSave, onDelete, onClose }) {
  const { staff, date, shift } = editor;
  const [start, setStart] = useState(shift?.start_time || "09:00");
  const [end, setEnd] = useState(shift?.end_time || "17:00");
  const [notes, setNotes] = useState(shift?.notes || "");
  const [status, setStatus] = useState(shift?.status || "planned");

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-end md:items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-white rounded-2xl w-full max-w-md p-5 space-y-4 shadow-xl"
        onClick={(e) => e.stopPropagation()}
        data-testid="shift-editor"
      >
        <div className="flex items-start justify-between">
          <div>
            <h2 className="font-semibold text-lg">{staff.name}</h2>
            <p className="text-xs text-stone-500">
              {new Date(date).toLocaleDateString("tr-TR", { weekday: "long", day: "numeric", month: "long" })}
              {" · "}
              <span className={`text-[10px] px-1.5 py-0.5 rounded ${ROLE_BADGE[staff.role] || "bg-stone-100"}`}>
                {staff.role}
              </span>
            </p>
          </div>
          <button onClick={onClose} className="p-1 rounded hover:bg-stone-100" data-testid="editor-close-btn">
            <X size={18} />
          </button>
        </div>

        {/* Templates */}
        <div>
          <div className="text-[10px] uppercase tracking-wider text-stone-500 mb-2">Hızlı şablon</div>
          <div className="grid grid-cols-2 gap-2">
            {PRESETS.map((p) => {
              const Icon = p.icon;
              return (
                <button
                  key={p.id}
                  onClick={() => { setStart(p.start); setEnd(p.end); }}
                  className="rounded-lg border border-stone-200 px-3 py-2 hover:border-stone-400 text-left flex items-center gap-2 text-sm"
                  data-testid={`preset-${p.id}`}
                >
                  <Icon size={14} style={{ color: p.color }} />
                  <div className="leading-tight">
                    <div className="font-medium">{p.label}</div>
                    <div className="text-[10px] text-stone-500">{p.time}</div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Custom hours */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-[10px] uppercase tracking-wider text-stone-500 block mb-1">Başlangıç</label>
            <input
              type="time"
              value={start}
              onChange={(e) => setStart(e.target.value)}
              className="w-full border rounded-md px-2 py-1.5 text-sm"
              data-testid="editor-start-input"
            />
          </div>
          <div>
            <label className="text-[10px] uppercase tracking-wider text-stone-500 block mb-1">Bitiş</label>
            <input
              type="time"
              value={end}
              onChange={(e) => setEnd(e.target.value)}
              className="w-full border rounded-md px-2 py-1.5 text-sm"
              data-testid="editor-end-input"
            />
          </div>
        </div>

        <div>
          <label className="text-[10px] uppercase tracking-wider text-stone-500 block mb-1">Not</label>
          <input
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="örn. Mola 13:00–14:00"
            className="w-full border rounded-md px-2 py-1.5 text-sm"
            data-testid="editor-notes-input"
          />
        </div>

        {shift && (
          <div>
            <label className="text-[10px] uppercase tracking-wider text-stone-500 block mb-1">Durum</label>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="w-full border rounded-md px-2 py-1.5 text-sm bg-white"
              data-testid="editor-status-input"
            >
              <option value="draft">Taslak</option>
              <option value="planned">Planlandı</option>
              <option value="published">Yayında</option>
              <option value="completed">Tamamlandı</option>
              <option value="approved">Onaylandı</option>
            </select>
          </div>
        )}

        <div className="flex justify-between gap-2 pt-2 border-t">
          {shift ? (
            <button
              onClick={() => onDelete(shift)}
              className="text-sm px-3 py-2 rounded-md bg-red-50 text-red-700 hover:bg-red-100"
              data-testid="editor-delete-btn"
            >
              Sil
            </button>
          ) : <div />}
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="text-sm px-3 py-2 rounded-md bg-stone-100"
              data-testid="editor-cancel-btn"
            >
              İptal
            </button>
            <button
              onClick={() =>
                onSave({
                  staff,
                  date,
                  start_time: start,
                  end_time: end,
                  notes,
                  status,
                })
              }
              className="text-sm px-4 py-2 rounded-md bg-emerald-600 text-white hover:bg-emerald-700"
              data-testid="editor-save-btn"
            >
              Kaydet
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ShiftScheduler;
