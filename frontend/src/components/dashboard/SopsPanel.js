import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { BookOpen, Plus, CheckCircle, X, ListChecks } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const CATEGORIES = [
  "housekeeping", "maintenance", "front-office", "fnb",
  "safety", "security", "compliance", "guest-service", "other",
];
const ROLES = ["receptionist", "housekeeping", "maintenance", "manager", "fnb", "admin"];

export default function SopsPanel({ propertyId = "all", user }) {
  const [sops, setSops] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({ category: "", q: "", status: "" });
  const [showCreate, setShowCreate] = useState(false);
  const [selected, setSelected] = useState(null); // detail open
  const isManager = ["admin", "manager"].includes(user?.role);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const params = { property_id: propertyId, ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== "")) };
      const r = await axios.get(`${API}/sops`, { params, withCredentials: true });
      setSops(r.data.sops || []);
    } catch (e) {
      toast.error("SOP'lar yüklenemedi");
    } finally { setLoading(false); }
  }, [propertyId, filters]);

  useEffect(() => { reload(); }, [reload]);

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="sops-panel">
      <div className="mb-5 flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
            <BookOpen size={12} weight="fill" className="text-indigo-500" />
            <span>Quality Assurance</span>
          </div>
          <h1 className="text-2xl font-semibold text-stone-900">SOP Kütüphanesi</h1>
          <p className="text-sm text-stone-500 mt-1 max-w-2xl">
            Standart Operasyon Prosedürleri — her departman için yazılı, adım adım iş akışları. Personel okudum işaretler, yönetim takip eder.
          </p>
        </div>
        {isManager && (
          <button
            onClick={() => setShowCreate(true)}
            className="px-3 py-1.5 text-xs font-medium text-white bg-stone-900 rounded-lg hover:bg-stone-800 inline-flex items-center gap-1.5"
            data-testid="sop-create-btn"
          >
            <Plus size={14} /> Yeni SOP
          </button>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-4">
        <input
          placeholder="Ara…"
          value={filters.q}
          onChange={e => setFilters(f => ({ ...f, q: e.target.value }))}
          className="px-3 py-1.5 text-xs bg-white border border-stone-300 rounded col-span-2"
          data-testid="sop-search"
        />
        <select value={filters.category} onChange={e => setFilters(f => ({ ...f, category: e.target.value }))}
          className="px-2 py-1.5 text-xs bg-white border border-stone-300 rounded" data-testid="sop-filter-category">
          <option value="">Tüm kategoriler</option>
          {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        {isManager && (
          <select value={filters.status} onChange={e => setFilters(f => ({ ...f, status: e.target.value }))}
            className="px-2 py-1.5 text-xs bg-white border border-stone-300 rounded" data-testid="sop-filter-status">
            <option value="">Tüm durumlar</option>
            <option value="draft">Taslak</option>
            <option value="published">Yayımlanmış</option>
            <option value="archived">Arşivli</option>
          </select>
        )}
      </div>

      {loading ? (
        <div className="py-12 text-center text-stone-400">Yükleniyor…</div>
      ) : sops.length === 0 ? (
        <div className="py-12 text-center text-stone-400 bg-white border border-stone-200 rounded-xl" data-testid="sops-empty">
          Henüz SOP yok. {isManager && "Yukarıdan oluştur."}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {sops.map(s => (
            <button
              key={s.id}
              onClick={() => setSelected(s)}
              className="text-left bg-white border border-stone-200 rounded-xl p-4 hover:border-stone-300 hover:shadow-sm transition"
              data-testid={`sop-card-${s.id}`}
            >
              <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                <span className="text-[10px] px-1.5 py-0.5 bg-indigo-50 text-indigo-700 rounded">{s.category}</span>
                <span className="text-[10px] px-1.5 py-0.5 bg-stone-100 text-stone-600 rounded">v{s.version}</span>
                {s.status === "draft" && <span className="text-[10px] px-1.5 py-0.5 bg-amber-50 text-amber-700 rounded">Taslak</span>}
                {s.status === "archived" && <span className="text-[10px] px-1.5 py-0.5 bg-stone-200 text-stone-600 rounded">Arşivli</span>}
                {s.required && <span className="text-[10px] px-1.5 py-0.5 bg-rose-50 text-rose-700 rounded">Zorunlu</span>}
              </div>
              <h3 className="text-sm font-semibold text-stone-900 mb-1">{s.title}</h3>
              {s.description && <p className="text-xs text-stone-500 line-clamp-2">{s.description}</p>}
              <div className="flex items-center justify-between mt-3 pt-3 border-t border-stone-100">
                <span className="text-[10px] text-stone-400">{s.ack_count} okudu</span>
                {s.acknowledged_by_me ? (
                  <span className="text-[10px] text-emerald-600 inline-flex items-center gap-1"><CheckCircle size={11} weight="fill" /> Okundu</span>
                ) : (
                  <span className="text-[10px] text-stone-400">Okunmadı</span>
                )}
              </div>
            </button>
          ))}
        </div>
      )}

      {showCreate && (
        <CreateSopModal onClose={() => setShowCreate(false)} onCreated={() => { setShowCreate(false); reload(); }} />
      )}
      {selected && (
        <SopDetailModal sop={selected} isManager={isManager} onClose={() => setSelected(null)} onChanged={() => { setSelected(null); reload(); }} />
      )}
    </div>
  );
}

function CreateSopModal({ onClose, onCreated }) {
  const [form, setForm] = useState({
    title: "", description: "", category: "housekeeping",
    target_roles: ["housekeeping"], required: false,
    steps: [{ order: 1, text: "", estimated_minutes: null }],
  });
  const [saving, setSaving] = useState(false);

  function setStep(i, key, val) {
    const next = [...form.steps];
    next[i] = { ...next[i], [key]: val };
    setForm(f => ({ ...f, steps: next }));
  }
  function addStep() {
    setForm(f => ({ ...f, steps: [...f.steps, { order: f.steps.length + 1, text: "", estimated_minutes: null }] }));
  }
  function removeStep(i) {
    const next = form.steps.filter((_, idx) => idx !== i).map((s, idx) => ({ ...s, order: idx + 1 }));
    setForm(f => ({ ...f, steps: next }));
  }
  function toggleRole(r) {
    const has = form.target_roles.includes(r);
    setForm(f => ({ ...f, target_roles: has ? f.target_roles.filter(x => x !== r) : [...f.target_roles, r] }));
  }

  async function submit() {
    if (form.title.trim().length < 2) { toast.error("Başlık çok kısa"); return; }
    if (form.steps.some(s => !s.text)) { toast.error("Tüm adımları doldur"); return; }
    setSaving(true);
    try {
      await axios.post(`${API}/sops`, form, { withCredentials: true });
      toast.success("SOP oluşturuldu (taslak)");
      onCreated();
    } catch (e) {
      toast.error("Oluşturulamadı: " + (e?.response?.data?.detail || e.message));
    } finally { setSaving(false); }
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-xl max-w-2xl w-full p-5 max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()} data-testid="sop-create-modal">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Yeni SOP</h2>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-900"><X size={20} /></button>
        </div>
        <div className="space-y-3">
          <input
            placeholder="Başlık (örn: Check-in prosedürü)"
            value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
            className="w-full px-3 py-2 text-sm border border-stone-300 rounded" data-testid="sop-input-title" autoFocus
          />
          <textarea
            placeholder="Kısa açıklama"
            value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
            rows={2} className="w-full px-3 py-2 text-sm border border-stone-300 rounded resize-none"
          />
          <div className="grid grid-cols-2 gap-2">
            <select value={form.category} onChange={e => setForm(f => ({ ...f, category: e.target.value }))}
              className="px-2 py-1.5 text-xs border border-stone-300 rounded">
              {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
            <label className="inline-flex items-center gap-1.5 text-xs text-stone-700 px-2 py-1.5">
              <input type="checkbox" checked={form.required} onChange={e => setForm(f => ({ ...f, required: e.target.checked }))} />
              Zorunlu okuma
            </label>
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-wider text-stone-500 mb-1.5">Hedef Roller</div>
            <div className="flex gap-1.5 flex-wrap">
              {ROLES.map(r => (
                <button key={r} type="button" onClick={() => toggleRole(r)}
                  className={`text-[10px] px-2 py-1 rounded border ${form.target_roles.includes(r) ? "bg-indigo-50 border-indigo-300 text-indigo-700" : "bg-white border-stone-200 text-stone-500"}`}>
                  {r}
                </button>
              ))}
            </div>
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-wider text-stone-500 mb-1.5">Adımlar</div>
            <div className="space-y-1.5">
              {form.steps.map((s, i) => (
                <div key={i} className="flex gap-2 items-start" data-testid={`sop-step-${i}`}>
                  <span className="text-xs text-stone-400 pt-2 w-5">{i + 1}.</span>
                  <input
                    placeholder={`Adım ${i + 1} (örn: Misafir kimliğini kontrol et)`}
                    value={s.text} onChange={e => setStep(i, "text", e.target.value)}
                    className="flex-1 px-2 py-1.5 text-xs border border-stone-300 rounded"
                  />
                  <input type="number" placeholder="dk" value={s.estimated_minutes || ""}
                    onChange={e => setStep(i, "estimated_minutes", e.target.value ? Number(e.target.value) : null)}
                    className="w-16 px-2 py-1.5 text-xs border border-stone-300 rounded"
                  />
                  {form.steps.length > 1 && (
                    <button onClick={() => removeStep(i)} className="text-rose-500 hover:text-rose-700 pt-2"><X size={14} /></button>
                  )}
                </div>
              ))}
            </div>
            <button onClick={addStep} className="mt-2 text-xs text-stone-600 hover:text-stone-900 inline-flex items-center gap-1" data-testid="sop-add-step">
              <Plus size={12} /> Adım Ekle
            </button>
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-5">
          <button onClick={onClose} className="px-3 py-1.5 text-xs text-stone-600">İptal</button>
          <button onClick={submit} disabled={saving} className="px-3 py-1.5 text-xs font-medium text-white bg-stone-900 rounded hover:bg-stone-800 disabled:opacity-50" data-testid="sop-create-submit">
            {saving ? "Kaydediliyor…" : "Taslak Olarak Kaydet"}
          </button>
        </div>
      </div>
    </div>
  );
}

function SopDetailModal({ sop: initial, isManager, onClose, onChanged }) {
  const [sop, setSop] = useState(initial);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    // Always fetch full detail with steps
    axios.get(`${API}/sops/${initial.id}`, { withCredentials: true })
      .then(r => setSop(r.data))
      .catch(() => {});
  }, [initial.id]);

  async function publish() {
    setBusy(true);
    try { await axios.post(`${API}/sops/${sop.id}/publish`, {}, { withCredentials: true }); toast.success("Yayımlandı"); onChanged(); }
    catch { toast.error("Yayımlanamadı"); } finally { setBusy(false); }
  }
  async function ack() {
    setBusy(true);
    try { await axios.post(`${API}/sops/${sop.id}/acknowledge`, {}, { withCredentials: true }); toast.success("Okudum olarak işaretlendi"); onChanged(); }
    catch { toast.error("İşaretlenemedi"); } finally { setBusy(false); }
  }
  async function archive() {
    setBusy(true);
    try { await axios.patch(`${API}/sops/${sop.id}`, { status: "archived" }, { withCredentials: true }); toast.success("Arşivlendi"); onChanged(); }
    catch { toast.error("Arşivlenemedi"); } finally { setBusy(false); }
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-xl max-w-2xl w-full p-5 max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()} data-testid="sop-detail-modal">
        <div className="flex items-start justify-between mb-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <span className="text-[10px] px-1.5 py-0.5 bg-indigo-50 text-indigo-700 rounded">{sop.category}</span>
              <span className="text-[10px] px-1.5 py-0.5 bg-stone-100 text-stone-600 rounded">v{sop.version}</span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded ${sop.status === "published" ? "bg-emerald-50 text-emerald-700" : sop.status === "draft" ? "bg-amber-50 text-amber-700" : "bg-stone-200 text-stone-600"}`}>
                {sop.status}
              </span>
            </div>
            <h2 className="text-lg font-semibold text-stone-900">{sop.title}</h2>
            {sop.description && <p className="text-sm text-stone-500 mt-0.5">{sop.description}</p>}
          </div>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-900"><X size={20} /></button>
        </div>
        <div>
          <div className="text-[11px] uppercase tracking-wider text-stone-500 mb-2 inline-flex items-center gap-1"><ListChecks size={12} /> Adımlar</div>
          <ol className="space-y-2">
            {(sop.steps || []).map((s, i) => (
              <li key={i} className="flex gap-3 text-sm text-stone-700">
                <span className="font-mono text-xs text-indigo-600 bg-indigo-50 rounded w-6 h-6 inline-flex items-center justify-center shrink-0">{s.order || i + 1}</span>
                <div className="flex-1">
                  <div>{s.text}</div>
                  {s.estimated_minutes && <div className="text-[10px] text-stone-400 mt-0.5">~{s.estimated_minutes} dk</div>}
                </div>
              </li>
            ))}
          </ol>
        </div>
        <div className="flex justify-end gap-2 mt-5 pt-4 border-t border-stone-100">
          {isManager && sop.status === "draft" && (
            <button onClick={publish} disabled={busy} className="px-3 py-1.5 text-xs font-medium text-white bg-emerald-600 rounded hover:bg-emerald-700 disabled:opacity-50" data-testid="sop-publish">
              Yayımla
            </button>
          )}
          {isManager && sop.status !== "archived" && (
            <button onClick={archive} disabled={busy} className="px-3 py-1.5 text-xs text-stone-600 hover:text-stone-900" data-testid="sop-archive">
              Arşivle
            </button>
          )}
          {sop.status === "published" && !sop.acknowledged_by_me && (
            <button onClick={ack} disabled={busy} className="px-3 py-1.5 text-xs font-medium text-white bg-indigo-600 rounded hover:bg-indigo-700 disabled:opacity-50" data-testid="sop-ack">
              Okudum, Anladım
            </button>
          )}
          <button onClick={onClose} className="px-3 py-1.5 text-xs text-stone-600">Kapat</button>
        </div>
      </div>
    </div>
  );
}
