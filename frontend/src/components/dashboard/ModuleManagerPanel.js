import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { LayoutGrid, EyeOff, Eye, RotateCcw, ArrowRight, Search } from "lucide-react";
import { buildMenuSections } from "../../navigation/menuSections";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Panel içi bağımsız çeviri: nav.* anahtarlarını okunur ada çevirir
const fallbackT = (k) =>
  k.startsWith("nav.") || k.startsWith("section_label.")
    ? k.split(".").pop().replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
    : k;

export default function ModuleManagerPanel() {
  const [overrides, setOverrides] = useState({});
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const sections = buildMenuSections(fallbackT, { role: "admin" });
  const sectionLabels = sections.map((s) => s.label);

  const load = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/menu-overrides`);
      setOverrides(data.overrides || {});
    } catch { toast.error("Modül ayarları yüklenemedi"); }
    setLoading(false);
  }, []);
  useEffect(() => { load(); }, [load]);

  const notify = () => window.dispatchEvent(new Event("menu-overrides-changed"));

  const saveOverride = async (moduleId, ov) => {
    try {
      if (!ov.section && !ov.hidden) {
        await axios.delete(`${API}/menu-overrides/${moduleId}`);
        setOverrides((o) => { const n = { ...o }; delete n[moduleId]; return n; });
        toast.success("Varsayılana döndü");
      } else {
        await axios.put(`${API}/menu-overrides/${moduleId}`, ov);
        setOverrides((o) => ({ ...o, [moduleId]: ov }));
        toast.success(ov.hidden ? "Modül gizlendi" : "Modül taşındı");
      }
      notify();
    } catch (e) { toast.error(e.response?.data?.detail || "Kaydedilemedi"); }
  };

  const resetAll = async () => {
    if (!window.confirm("Tüm modül taşıma/gizleme ayarları silinsin mi?")) return;
    try {
      await axios.post(`${API}/menu-overrides/reset`);
      setOverrides({});
      notify();
      toast.success("Tüm modüller varsayılan bölümlerine döndü");
    } catch { toast.error("Sıfırlanamadı"); }
  };

  const overrideCount = Object.keys(overrides).length;
  const q = search.trim().toLowerCase();

  if (loading) return <div className="p-8 text-sm text-stone-500">Yükleniyor…</div>;

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-5" data-testid="module-manager-panel">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-black text-stone-900 flex items-center gap-2">
            <LayoutGrid className="w-5 h-5 text-violet-600" /> Modül Yöneticisi
          </h1>
          <p className="text-xs text-stone-500 mt-1">
            Modülleri bölümler arasında taşıyın veya gizleyin — değişiklikler tüm kullanıcıların sol menüsüne anında yansır.
            {overrideCount > 0 && <span className="ml-1 font-bold text-violet-700">({overrideCount} özelleştirme aktif)</span>}
          </p>
        </div>
        <button onClick={resetAll} disabled={overrideCount === 0} data-testid="module-manager-reset"
          className="flex items-center gap-1.5 px-3 py-2 text-xs font-bold text-rose-700 bg-rose-50 border border-rose-200 rounded-xl hover:bg-rose-100 disabled:opacity-40">
          <RotateCcw className="w-3.5 h-3.5" /> Varsayılana Dön
        </button>
      </div>

      <div className="relative">
        <Search className="w-4 h-4 text-stone-400 absolute left-3 top-1/2 -translate-y-1/2" />
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Modül ara… (ör. loyalty, housekeeping)"
          data-testid="module-manager-search"
          className="w-full border border-stone-200 rounded-xl pl-9 pr-3 py-2 text-sm" />
      </div>

      {sections.map((section) => {
        const items = section.items.filter((it) => !it.divider && it.id &&
          (!q || (it.name || "").toLowerCase().includes(q) || it.id.toLowerCase().includes(q)));
        if (items.length === 0) return null;
        return (
          <div key={section.label} className="bg-white border border-stone-200 rounded-2xl overflow-hidden" data-testid={`mm-section-${section.label.replace(/[^a-zA-Z0-9]+/g, "-").toLowerCase()}`}>
            <div className="px-4 py-2.5 bg-stone-50 border-b border-stone-100">
              <span className="text-[11px] font-black uppercase tracking-wide text-stone-600">{section.label}</span>
              <span className="ml-2 text-[10px] text-stone-400">{items.length} modül</span>
            </div>
            <div className="divide-y divide-stone-50">
              {items.map((it) => {
                const ov = overrides[it.id] || {};
                const effSection = ov.section || section.label;
                const isHidden = !!ov.hidden;
                const changed = !!overrides[it.id];
                return (
                  <div key={it.id} className={`flex items-center gap-3 px-4 py-2 ${isHidden ? "opacity-50" : ""}`} data-testid={`mm-row-${it.id}`}>
                    <span className="text-xs font-semibold text-stone-800 flex-1 truncate">{it.name}</span>
                    {changed && !isHidden && ov.section && (
                      <span className="inline-flex items-center gap-1 text-[9px] font-bold text-violet-700 bg-violet-50 px-1.5 py-0.5 rounded-full">
                        <ArrowRight className="w-2.5 h-2.5" /> {ov.section}
                      </span>
                    )}
                    {isHidden && <span className="text-[9px] font-bold text-rose-600 bg-rose-50 px-1.5 py-0.5 rounded-full">GİZLİ</span>}
                    <select value={effSection}
                      onChange={(e) => saveOverride(it.id, e.target.value === section.label ? { hidden: isHidden } : { section: e.target.value, hidden: isHidden })}
                      data-testid={`mm-move-${it.id}`}
                      className="text-[11px] border border-stone-200 rounded-lg px-2 py-1 bg-white max-w-[180px]">
                      {sectionLabels.map((l) => <option key={l} value={l}>{l}</option>)}
                    </select>
                    <button
                      onClick={() => saveOverride(it.id, isHidden ? (ov.section ? { section: ov.section } : {}) : { ...(ov.section ? { section: ov.section } : {}), hidden: true })}
                      data-testid={`mm-hide-${it.id}`}
                      title={isHidden ? "Göster" : "Gizle"}
                      className={`p-1.5 rounded-lg border ${isHidden ? "text-emerald-600 border-emerald-200 bg-emerald-50 hover:bg-emerald-100" : "text-stone-500 border-stone-200 hover:bg-stone-50"}`}>
                      {isHidden ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
