import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Warning, Plus, CheckCircle, X, ClockClockwise, ArrowRight } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const SEV = {
  critical: { color: "bg-rose-100 text-rose-800 border-rose-300", label: "Critical" },
  major:    { color: "bg-amber-100 text-amber-800 border-amber-300", label: "Major" },
  minor:    { color: "bg-sky-100 text-sky-800 border-sky-300", label: "Minor" },
  info:     { color: "bg-stone-100 text-stone-700 border-stone-300", label: "Info" },
};
const DEPTS = ["front-office", "housekeeping", "maintenance", "fnb", "management", "security", "other"];
const SHIFTS = ["morning", "afternoon", "night"];

export default function GlitchLogPanel({ propertyId = "all" }) {
  const [glitches, setGlitches] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({ shift: "", severity: "", department: "", status: "open", days: 7 });
  const [showCreate, setShowCreate] = useState(false);
  const [handover, setHandover] = useState(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const params = Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== ""));
      const r = await axios.get(`${API}/glitch-log/${propertyId}`, { params, withCredentials: true });
      setGlitches(r.data.glitches || []);
    } catch (e) {
      toast.error("Glitch log yüklenemedi");
    } finally { setLoading(false); }
  }, [propertyId, filters]);

  useEffect(() => { reload(); }, [reload]);

  async function patch(id, body) {
    try {
      await axios.patch(`${API}/glitch-log/${id}`, body, { withCredentials: true });
      reload();
    } catch (e) { toast.error("Güncellenemedi"); }
  }
  async function ack(id) {
    try {
      await axios.post(`${API}/glitch-log/${id}/acknowledge`, {}, { withCredentials: true });
      reload();
    } catch (e) { toast.error("Onaylanamadı"); }
  }
  async function loadHandover() {
    try {
      const r = await axios.get(`${API}/glitch-log/handover/${propertyId}`, { withCredentials: true });
      setHandover(r.data);
    } catch (e) { toast.error("Handover yüklenemedi"); }
  }

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="glitch-log-panel">
      <div className="mb-5 flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
            <Warning size={12} weight="fill" className="text-amber-500" />
            <span>Quality Assurance</span>
          </div>
          <h1 className="text-2xl font-semibold text-stone-900">Glitch Log & Vardiya Devri</h1>
          <p className="text-sm text-stone-500 mt-1 max-w-2xl">
            Günlük arızalar, misafir şikayetleri ve vardiyadan vardiyaya iletilmesi gereken her şey. Bir bakışta — kimse atlamaz.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={loadHandover}
            className="px-3 py-1.5 text-xs font-medium text-stone-700 bg-white border border-stone-300 rounded-lg hover:bg-stone-50 inline-flex items-center gap-1.5"
            data-testid="glitch-handover-btn"
          >
            <ArrowRight size={14} /> Vardiya Devri
          </button>
          <button
            onClick={() => setShowCreate(true)}
            className="px-3 py-1.5 text-xs font-medium text-white bg-stone-900 rounded-lg hover:bg-stone-800 inline-flex items-center gap-1.5"
            data-testid="glitch-create-btn"
          >
            <Plus size={14} /> Yeni Glitch
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mb-4">
        <select value={filters.status} onChange={e => setFilters(f => ({ ...f, status: e.target.value }))}
          className="px-2 py-1.5 text-xs bg-white border border-stone-300 rounded" data-testid="glitch-filter-status">
          <option value="">Tüm durumlar</option>
          <option value="open">Açık</option>
          <option value="resolved">Çözümlendi</option>
          <option value="dismissed">İptal</option>
        </select>
        <select value={filters.severity} onChange={e => setFilters(f => ({ ...f, severity: e.target.value }))}
          className="px-2 py-1.5 text-xs bg-white border border-stone-300 rounded" data-testid="glitch-filter-severity">
          <option value="">Tüm öncelikler</option>
          {Object.entries(SEV).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
        <select value={filters.shift} onChange={e => setFilters(f => ({ ...f, shift: e.target.value }))}
          className="px-2 py-1.5 text-xs bg-white border border-stone-300 rounded" data-testid="glitch-filter-shift">
          <option value="">Tüm vardiyalar</option>
          {SHIFTS.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={filters.department} onChange={e => setFilters(f => ({ ...f, department: e.target.value }))}
          className="px-2 py-1.5 text-xs bg-white border border-stone-300 rounded" data-testid="glitch-filter-dept">
          <option value="">Tüm departmanlar</option>
          {DEPTS.map(d => <option key={d} value={d}>{d}</option>)}
        </select>
        <select value={filters.days} onChange={e => setFilters(f => ({ ...f, days: Number(e.target.value) }))}
          className="px-2 py-1.5 text-xs bg-white border border-stone-300 rounded" data-testid="glitch-filter-days">
          <option value={1}>Bugün</option>
          <option value={3}>Son 3 gün</option>
          <option value={7}>Son 7 gün</option>
          <option value={30}>Son 30 gün</option>
        </select>
      </div>

      {loading ? (
        <div className="py-12 text-center text-stone-400">Yükleniyor…</div>
      ) : glitches.length === 0 ? (
        <div className="py-12 text-center text-stone-400 bg-white border border-stone-200 rounded-xl" data-testid="glitch-empty">
          Bu filtrelerde glitch yok 🎉
        </div>
      ) : (
        <div className="space-y-2">
          {glitches.map(g => {
            const sev = SEV[g.severity] || SEV.minor;
            return (
              <div key={g.id} className="bg-white border border-stone-200 rounded-xl p-4" data-testid={`glitch-${g.id}`}>
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <span className={`px-2 py-0.5 text-[10px] font-medium border rounded ${sev.color}`}>{sev.label}</span>
                      <span className="text-[10px] px-1.5 py-0.5 bg-stone-100 text-stone-600 rounded font-mono">{g.department}</span>
                      <span className="text-[10px] px-1.5 py-0.5 bg-stone-100 text-stone-600 rounded">{g.shift}</span>
                      {g.related_room && <span className="text-[10px] px-1.5 py-0.5 bg-stone-100 text-stone-600 rounded">🛏 {g.related_room}</span>}
                      {g.status === "resolved" && <span className="text-[10px] px-1.5 py-0.5 bg-emerald-100 text-emerald-700 rounded">✓ Çözümlendi</span>}
                      {g.status === "dismissed" && <span className="text-[10px] px-1.5 py-0.5 bg-stone-200 text-stone-600 rounded">İptal</span>}
                    </div>
                    <h3 className="text-sm font-semibold text-stone-900 truncate">{g.title}</h3>
                    {g.description && <p className="text-xs text-stone-500 mt-0.5 line-clamp-2">{g.description}</p>}
                    <div className="flex items-center gap-3 mt-2 text-[10px] text-stone-400">
                      <span>{g.date}</span>
                      <span>by {g.created_by}</span>
                      <span>{g.ack_count} okudu</span>
                    </div>
                  </div>
                  <div className="flex flex-col gap-1.5 shrink-0">
                    {!g.acknowledged_by_me && (
                      <button onClick={() => ack(g.id)} className="text-[10px] px-2 py-1 bg-sky-50 text-sky-700 border border-sky-200 rounded hover:bg-sky-100" data-testid={`glitch-ack-${g.id}`}>
                        Okudum
                      </button>
                    )}
                    {g.status === "open" && (
                      <button onClick={() => patch(g.id, { status: "resolved", resolution: "Done" })} className="text-[10px] px-2 py-1 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded hover:bg-emerald-100" data-testid={`glitch-resolve-${g.id}`}>
                        <CheckCircle size={11} className="inline mr-1" />Çöz
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {showCreate && (
        <CreateGlitchModal propertyId={propertyId} onClose={() => setShowCreate(false)} onCreated={() => { setShowCreate(false); reload(); }} />
      )}
      {handover && (
        <HandoverModal data={handover} onClose={() => setHandover(null)} />
      )}
    </div>
  );
}

function CreateGlitchModal({ propertyId, onClose, onCreated }) {
  const [form, setForm] = useState({
    property_id: propertyId === "all" ? "default" : propertyId,
    title: "", description: "", severity: "minor",
    department: "front-office", shift: "morning",
    related_room: "", related_booking_ref: "", needs_followup: true,
  });
  const [saving, setSaving] = useState(false);

  async function submit() {
    if (form.title.trim().length < 2) { toast.error("Başlık çok kısa"); return; }
    setSaving(true);
    try {
      await axios.post(`${API}/glitch-log`, form, { withCredentials: true });
      toast.success("Glitch kaydedildi");
      onCreated();
    } catch (e) {
      toast.error("Kaydedilemedi: " + (e?.response?.data?.detail || e.message));
    } finally { setSaving(false); }
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-xl max-w-xl w-full p-5" onClick={e => e.stopPropagation()} data-testid="glitch-create-modal">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Yeni Glitch</h2>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-900"><X size={20} /></button>
        </div>
        <div className="space-y-3">
          <input
            placeholder="Başlık (örn: Resepsiyon yazıcı bozuk)"
            value={form.title}
            onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
            className="w-full px-3 py-2 text-sm border border-stone-300 rounded"
            data-testid="glitch-input-title"
            autoFocus
          />
          <textarea
            placeholder="Detay (isteğe bağlı)"
            value={form.description}
            onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
            rows={3}
            className="w-full px-3 py-2 text-sm border border-stone-300 rounded resize-none"
            data-testid="glitch-input-desc"
          />
          <div className="grid grid-cols-3 gap-2">
            <select value={form.severity} onChange={e => setForm(f => ({ ...f, severity: e.target.value }))}
              className="px-2 py-1.5 text-xs border border-stone-300 rounded" data-testid="glitch-input-severity">
              {Object.entries(SEV).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
            </select>
            <select value={form.department} onChange={e => setForm(f => ({ ...f, department: e.target.value }))}
              className="px-2 py-1.5 text-xs border border-stone-300 rounded" data-testid="glitch-input-dept">
              {DEPTS.map(d => <option key={d} value={d}>{d}</option>)}
            </select>
            <select value={form.shift} onChange={e => setForm(f => ({ ...f, shift: e.target.value }))}
              className="px-2 py-1.5 text-xs border border-stone-300 rounded" data-testid="glitch-input-shift">
              {SHIFTS.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <input placeholder="Oda no (ops.)" value={form.related_room}
              onChange={e => setForm(f => ({ ...f, related_room: e.target.value }))}
              className="px-2 py-1.5 text-xs border border-stone-300 rounded" />
            <input placeholder="Booking ref (ops.)" value={form.related_booking_ref}
              onChange={e => setForm(f => ({ ...f, related_booking_ref: e.target.value }))}
              className="px-2 py-1.5 text-xs border border-stone-300 rounded" />
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-5">
          <button onClick={onClose} className="px-3 py-1.5 text-xs text-stone-600">İptal</button>
          <button onClick={submit} disabled={saving} className="px-3 py-1.5 text-xs font-medium text-white bg-stone-900 rounded hover:bg-stone-800 disabled:opacity-50" data-testid="glitch-create-submit">
            {saving ? "Kaydediliyor…" : "Kaydet"}
          </button>
        </div>
      </div>
    </div>
  );
}

function HandoverModal({ data, onClose }) {
  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-xl max-w-2xl w-full p-5 max-h-[85vh] overflow-y-auto" onClick={e => e.stopPropagation()} data-testid="glitch-handover-modal">
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="text-[10px] uppercase tracking-wider text-stone-500"><ClockClockwise size={12} className="inline" /> Vardiya Devri</div>
            <h2 className="text-lg font-semibold">{data.date} · Açık Glitchler ({data.summary.total_open})</h2>
          </div>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-900"><X size={20} /></button>
        </div>
        <div className="space-y-4">
          {["critical", "major", "minor", "info"].map(sev => {
            const items = data.items_by_severity[sev] || [];
            if (items.length === 0) return null;
            const cfg = SEV[sev];
            return (
              <div key={sev}>
                <div className={`text-[11px] uppercase tracking-wider font-semibold mb-2 px-2 py-0.5 inline-block rounded ${cfg.color}`}>
                  {cfg.label} ({items.length})
                </div>
                <ul className="space-y-1.5">
                  {items.map(g => (
                    <li key={g.id} className="text-xs text-stone-700 pl-3 border-l-2 border-stone-200">
                      <span className="font-medium">{g.title}</span>
                      <span className="text-stone-400 ml-2">· {g.department} · {g.shift}</span>
                      {g.related_room && <span className="text-stone-400 ml-1">· 🛏 {g.related_room}</span>}
                      {g.description && <div className="text-[11px] text-stone-500 mt-0.5">{g.description}</div>}
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
          {data.summary.total_open === 0 && (
            <div className="text-center py-8 text-stone-400 text-sm">🎉 Tüm glitchler çözüldü. Smooth handover.</div>
          )}
        </div>
      </div>
    </div>
  );
}
