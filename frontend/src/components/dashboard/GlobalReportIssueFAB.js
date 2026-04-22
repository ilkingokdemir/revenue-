/**
 * Global "Report Maintenance Issue" Floating Action Button
 * Available to ALL departments (reception, housekeeping, maintenance, management, kitchen)
 * Lets any staff member quickly log a maintenance issue without navigating away.
 */
import { useState, useEffect, useRef } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Wrench, X, Plus, Camera } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const FAB_I18N = {
  en: {
    flag: "🇬🇧",
    fab: "Report Issue", title: "Report Maintenance Issue",
    subtitle: "Fast reporting — any staff, any device",
    titlePh: "Short issue title *", descPh: "Describe the issue (optional)",
    category: "Category", priority: "Priority", location: "Location",
    roomNo: "Room number", takePhoto: "Add photo",
    photos: "Photos", photoLimit: "Max 3 photos",
    branch: "Branch", pickBranch: "Please select a branch first",
    submit: "Submit", submitting: "Submitting...", cancel: "Cancel",
    success: "Issue reported!", failed: "Failed to submit",
    catGeneral: "General", catPlumb: "Plumbing", catElec: "Electrical", catHvac: "HVAC",
    catFurn: "Furniture", catAppl: "Appliance", catStruc: "Structural",
    catClean: "Cleaning", catPest: "Pest", catSafe: "Safety", catIt: "IT",
    priLow: "Low", priMed: "Medium", priHigh: "High", priCrit: "Critical",
    required: "Title required",
  },
  tr: {
    flag: "🇹🇷",
    fab: "Arıza Bildir", title: "Bakım Arızası Bildir",
    subtitle: "Hızlı bildirim — tüm personel, her cihazdan",
    titlePh: "Kısa arıza başlığı *", descPh: "Arızayı açıklayın (opsiyonel)",
    category: "Kategori", priority: "Öncelik", location: "Konum",
    roomNo: "Oda numarası", takePhoto: "Fotoğraf ekle",
    photos: "Fotoğraflar", photoLimit: "En fazla 3 fotoğraf",
    branch: "Şube", pickBranch: "Lütfen önce bir şube seçin",
    submit: "Kaydet", submitting: "Kaydediliyor...", cancel: "İptal",
    success: "Arıza kaydedildi!", failed: "Kayıt başarısız",
    catGeneral: "Genel", catPlumb: "Tesisat", catElec: "Elektrik", catHvac: "HVAC",
    catFurn: "Mobilya", catAppl: "Beyaz Eşya", catStruc: "Yapısal",
    catClean: "Temizlik", catPest: "Haşere", catSafe: "Güvenlik", catIt: "BT",
    priLow: "Düşük", priMed: "Orta", priHigh: "Yüksek", priCrit: "Kritik",
    required: "Başlık gerekli",
  },
};

const CATEGORIES = [
  { key: "general", tr: "catGeneral", icon: "🔨" },
  { key: "plumbing", tr: "catPlumb", icon: "🔧" },
  { key: "electrical", tr: "catElec", icon: "⚡" },
  { key: "hvac", tr: "catHvac", icon: "❄️" },
  { key: "furniture", tr: "catFurn", icon: "🪑" },
  { key: "appliance", tr: "catAppl", icon: "🧊" },
  { key: "structural", tr: "catStruc", icon: "🏗️" },
  { key: "pest_control", tr: "catPest", icon: "🐛" },
  { key: "it_network", tr: "catIt", icon: "📡" },
  { key: "safety", tr: "catSafe", icon: "🛡️" },
];

export default function GlobalReportIssueFAB({ propertyId, currentUser, properties = [] }) {
  const [open, setOpen] = useState(false);
  const [lang, setLang] = useState(() => localStorage.getItem("maint_lang") || "en");
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({ title: "", description: "", category: "general", priority: "medium", location: "", room_number: "" });
  const [photos, setPhotos] = useState([]);
  const [selectedPid, setSelectedPid] = useState("");
  const fileRef = useRef(null);

  useEffect(() => {
    const onStorage = () => setLang(localStorage.getItem("maint_lang") || "en");
    window.addEventListener("storage", onStorage);
    const onOpen = () => setOpen(true);
    window.addEventListener("open-report-issue", onOpen);
    return () => {
      window.removeEventListener("storage", onStorage);
      window.removeEventListener("open-report-issue", onOpen);
    };
  }, []);

  const L = FAB_I18N[lang] || FAB_I18N.en;

  // Show when user is logged in (property picker appears inside modal if "all")
  if (!currentUser) return null;

  // Effective property id: user's explicit modal pick wins; otherwise the prop
  const effectivePid = selectedPid || (propertyId && propertyId !== "all" ? propertyId : "");

  const reset = () => {
    setForm({ title: "", description: "", category: "general", priority: "medium", location: "", room_number: "" });
    setPhotos([]);
    setSelectedPid("");
  };

  const handlePhoto = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (photos.length >= 3) { toast.error(L.photoLimit); e.target.value = ""; return; }
    const reader = new FileReader();
    reader.onload = (ev) => setPhotos(prev => [...prev, { file, preview: ev.target.result }]);
    reader.readAsDataURL(file);
    e.target.value = "";
  };

  const submit = async () => {
    if (!form.title.trim()) { toast.error(L.required); return; }
    if (!effectivePid) { toast.error(L.pickBranch); return; }
    setSubmitting(true);
    try {
      const { data } = await axios.post(`${API}/maintenance/issues`, {
        ...form,
        property_id: effectivePid,
      });
      // Upload photos best-effort (continue even if one fails)
      for (const p of photos) {
        const fd = new FormData();
        fd.append("file", p.file);
        fd.append("photo_type", "before");
        try {
          await axios.post(`${API}/maintenance/upload-photo/${data.id}`, fd,
            { headers: { "Content-Type": "multipart/form-data" } });
        } catch { /* best-effort */ }
      }
      toast.success(L.success);
      window.dispatchEvent(new CustomEvent("issue-created", { detail: { id: data.id } }));
      reset();
      setOpen(false);
    } catch (e) {
      toast.error(e?.response?.data?.detail || L.failed);
    }
    setSubmitting(false);
  };

  return (
    <>
      {/* FAB cluster — language pill + main FAB, fixed bottom-right */}
      <div className="fixed bottom-20 right-6 z-40 flex flex-col items-end gap-2" data-testid="fab-cluster">
        <div className="flex gap-0.5 bg-white rounded-full shadow-lg p-1 border border-stone-200" data-testid="fab-lang-pill">
          {Object.keys(FAB_I18N).map(c => (
            <button key={c} onClick={() => { setLang(c); localStorage.setItem("maint_lang", c); }}
              className={`px-2 py-0.5 text-[10px] font-semibold rounded-full transition ${lang === c ? "bg-orange-500 text-white shadow" : "text-stone-500 hover:text-stone-700"}`}
              data-testid={`fab-pill-lang-${c}`}>
              {FAB_I18N[c].flag} {c.toUpperCase()}
            </button>
          ))}
        </div>
        <button
          onClick={() => setOpen(true)}
          data-testid="global-report-issue-fab"
          className="flex items-center gap-2 bg-gradient-to-br from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700 text-white font-semibold px-4 py-3 rounded-full shadow-2xl hover:shadow-orange-500/40 transition-all group"
          title={L.fab}>
          <Wrench size={18} weight="fill" className="group-hover:rotate-12 transition-transform" />
          <span className="hidden sm:inline text-sm">{L.fab}</span>
        </button>
      </div>

      {/* Modal */}
      {open && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4" onClick={() => setOpen(false)}>
          <div className="bg-white w-full sm:max-w-md rounded-t-3xl sm:rounded-2xl shadow-2xl max-h-[92vh] overflow-hidden flex flex-col" onClick={e => e.stopPropagation()} data-testid="global-report-issue-modal">
            {/* Header */}
            <div className="px-5 py-3.5 bg-gradient-to-r from-orange-500 to-orange-600 text-white flex items-center justify-between">
              <div>
                <h2 className="font-bold text-base">{L.title}</h2>
                <p className="text-[10px] opacity-90">{L.subtitle}</p>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="flex gap-0.5 bg-white/20 rounded-md p-0.5">
                  {Object.keys(FAB_I18N).map(c => (
                    <button key={c} onClick={() => { setLang(c); localStorage.setItem("maint_lang", c); }}
                      className={`px-1.5 py-0.5 text-[10px] font-semibold rounded ${lang === c ? "bg-white text-orange-700" : "text-white/80"}`}
                      data-testid={`fab-lang-${c}`}>
                      {FAB_I18N[c].flag} {c.toUpperCase()}
                    </button>
                  ))}
                </div>
                <button onClick={() => setOpen(false)} className="p-1 hover:bg-white/20 rounded"><X size={18} /></button>
              </div>
            </div>

            {/* Body */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {/* Branch picker — always visible */}
              <div>
                <label className="text-[10px] font-bold uppercase text-stone-500 block mb-1">{L.branch} *</label>
                <select
                  value={effectivePid}
                  onChange={e => setSelectedPid(e.target.value)}
                  className="w-full px-3 py-2.5 text-sm border border-stone-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-orange-400 bg-white"
                  data-testid="fab-branch-picker">
                  <option value="">— {L.branch} —</option>
                  {properties.map(p => (
                    <option key={p.id} value={p.id}>{p.name || p.id}</option>
                  ))}
                </select>
              </div>

              <input
                value={form.title}
                onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
                placeholder={L.titlePh}
                className="w-full px-3 py-2.5 text-sm border border-stone-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-orange-400"
                data-testid="fab-title"
                autoFocus
              />

              {/* Category pills */}
              <div>
                <label className="text-[10px] font-bold uppercase text-stone-500 block mb-1">{L.category}</label>
                <div className="grid grid-cols-4 gap-1.5">
                  {CATEGORIES.map(c => (
                    <button
                      key={c.key}
                      onClick={() => setForm(f => ({ ...f, category: c.key }))}
                      className={`text-[10px] py-2 rounded-lg transition flex flex-col items-center gap-0.5 ${form.category === c.key ? "bg-orange-100 text-orange-800 ring-2 ring-orange-400" : "bg-stone-50 text-stone-600 hover:bg-stone-100"}`}
                      data-testid={`fab-cat-${c.key}`}>
                      <span className="text-base leading-none">{c.icon}</span>
                      <span className="font-medium truncate w-full text-center">{L[c.tr]}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Priority pills */}
              <div>
                <label className="text-[10px] font-bold uppercase text-stone-500 block mb-1">{L.priority}</label>
                <div className="grid grid-cols-4 gap-1.5">
                  {[
                    { k: "low", l: L.priLow, cls: "bg-stone-100 text-stone-600", active: "ring-2 ring-stone-500" },
                    { k: "medium", l: L.priMed, cls: "bg-amber-100 text-amber-700", active: "ring-2 ring-amber-500" },
                    { k: "high", l: L.priHigh, cls: "bg-orange-100 text-orange-700", active: "ring-2 ring-orange-500" },
                    { k: "critical", l: L.priCrit, cls: "bg-red-100 text-red-700", active: "ring-2 ring-red-500" },
                  ].map(p => (
                    <button key={p.k} onClick={() => setForm(f => ({ ...f, priority: p.k }))}
                      className={`text-xs py-2 rounded-lg font-semibold ${p.cls} ${form.priority === p.k ? p.active : "opacity-70"}`}
                      data-testid={`fab-pri-${p.k}`}>
                      {p.l}
                    </button>
                  ))}
                </div>
              </div>

              {/* Location + Room */}
              <div className="grid grid-cols-2 gap-2">
                <input value={form.location} onChange={e => setForm(f => ({ ...f, location: e.target.value }))}
                  placeholder={L.location} className="px-3 py-2 text-sm border border-stone-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-orange-400" data-testid="fab-location" />
                <input value={form.room_number} onChange={e => setForm(f => ({ ...f, room_number: e.target.value }))}
                  placeholder={L.roomNo} className="px-3 py-2 text-sm border border-stone-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-orange-400" data-testid="fab-room" />
              </div>

              {/* Description */}
              <textarea value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                placeholder={L.descPh} rows={2}
                className="w-full px-3 py-2 text-sm border border-stone-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-orange-400 resize-none"
                data-testid="fab-desc" />

              {/* Photos (up to 3) */}
              <div>
                <label className="text-[10px] font-bold uppercase text-stone-500 block mb-1">
                  {L.photos} <span className="text-stone-400 font-normal normal-case">({photos.length}/3)</span>
                </label>
                <input ref={fileRef} type="file" accept="image/*" capture="environment"
                  onChange={handlePhoto} className="hidden" data-testid="fab-photo-input" />
                <div className="flex gap-2 flex-wrap">
                  {photos.map((p, i) => (
                    <div key={i} className="relative w-20 h-20 rounded-lg overflow-hidden border border-stone-200 group">
                      <img src={p.preview} alt={`issue-${i}`} className="w-full h-full object-cover" />
                      <button onClick={() => setPhotos(prev => prev.filter((_, idx) => idx !== i))}
                        className="absolute top-0.5 right-0.5 bg-black/60 hover:bg-black/80 text-white w-5 h-5 rounded-full text-[10px] flex items-center justify-center"
                        data-testid={`fab-photo-remove-${i}`}>×</button>
                    </div>
                  ))}
                  {photos.length < 3 && (
                    <button onClick={() => fileRef.current?.click()}
                      className="w-20 h-20 flex flex-col items-center justify-center gap-1 border-2 border-dashed border-stone-300 rounded-lg text-[10px] text-stone-500 hover:border-orange-400 hover:text-orange-600 transition"
                      data-testid="fab-photo-btn">
                      <Camera size={18} />
                      <span className="font-medium">{L.takePhoto}</span>
                    </button>
                  )}
                </div>
              </div>
            </div>

            {/* Footer */}
            <div className="px-4 py-3 border-t border-stone-100 flex items-center justify-end gap-2 bg-stone-50">
              <button onClick={() => setOpen(false)}
                className="px-3 py-2 text-xs font-medium text-stone-600 hover:bg-stone-100 rounded-lg" data-testid="fab-cancel">
                {L.cancel}
              </button>
              <button onClick={submit} disabled={submitting}
                className="flex items-center gap-1.5 px-4 py-2 text-xs font-bold bg-orange-500 hover:bg-orange-600 disabled:bg-stone-300 text-white rounded-lg shadow-sm"
                data-testid="fab-submit">
                <Plus size={13} /> {submitting ? L.submitting : L.submit}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
