import { useState, useEffect, useCallback, useMemo } from "react";
import axios from "axios";
import { toast } from "sonner";
import { UsersThree, Plus, X, MagnifyingGlass, ArrowCounterClockwise } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const DEPT_LABELS = {
  front_desk: "Ön Büro",
  management: "Yönetim",
  housekeeping: "Housekeeping",
  food_beverage: "Yiyecek & İçecek",
  maintenance: "Teknik Servis",
  spa_wellness: "Spa & Wellness",
  concierge: "Concierge",
};

export function DepartmentShortcutsPanel({ catalog = [], onChanged }) {
  const [dept, setDept] = useState("front_desk");
  const [items, setItems] = useState([]);
  const [isDefault, setIsDefault] = useState(false);
  const [query, setQuery] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/department-shortcuts/${dept}`);
      setItems(data.items || []);
      setIsDefault(!!data.is_default);
    } catch { toast.error("Kısayollar yüklenemedi"); }
  }, [dept]);
  useEffect(() => { load(); }, [load]);

  const save = async (next) => {
    setSaving(true);
    try {
      await axios.put(`${API}/department-shortcuts/${dept}`, { items: next });
      setItems(next);
      setIsDefault(false);
      onChanged?.();
    } catch (e) { toast.error(e?.response?.data?.detail || "Kaydedilemedi"); }
    finally { setSaving(false); }
  };

  const byId = useMemo(() => Object.fromEntries(catalog.map(c => [c.id, c])), [catalog]);
  const results = useMemo(() => {
    if (!query) return [];
    const q = query.toLowerCase();
    return catalog
      .filter(c => !items.includes(c.id) && (c.name.toLowerCase().includes(q) || c.id.includes(q) || (c.group || "").toLowerCase().includes(q)))
      .slice(0, 8);
  }, [query, catalog, items]);

  return (
    <div className="max-w-3xl mx-auto space-y-5" data-testid="dept-shortcuts-panel">
      <div>
        <h1 className="text-xl font-bold text-stone-900 flex items-center gap-2">
          <UsersThree size={22} className="text-indigo-500" weight="fill" />
          Departman Kısayolları
        </h1>
        <p className="text-sm text-stone-500 mt-0.5">
          Her departman için kenar çubuğunda hazır görünen görev kısayollarını ekleyin / çıkarın.
          O departmandaki tüm kullanıcılar bu listeyi görür.
        </p>
      </div>

      {/* Department tabs */}
      <div className="flex flex-wrap gap-1.5" data-testid="dept-tabs">
        {Object.entries(DEPT_LABELS).map(([id, label]) => (
          <button key={id} onClick={() => { setDept(id); setQuery(""); }}
            data-testid={`dept-tab-${id}`}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${
              dept === id ? "bg-indigo-600 text-white" : "bg-white border border-stone-200 text-stone-600 hover:border-stone-400"}`}>
            {label}
          </button>
        ))}
      </div>

      {/* Current items */}
      <div className="bg-white border border-stone-200 rounded-2xl p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-black text-stone-900">
            {DEPT_LABELS[dept]} kısayolları ({items.length}/15)
          </h2>
          {isDefault && <span className="text-[10px] px-2 py-0.5 rounded-full bg-stone-100 text-stone-500 font-bold uppercase">Varsayılan</span>}
        </div>
        <div className="flex flex-wrap gap-2 mt-3" data-testid="dept-items">
          {items.length === 0 && <p className="text-xs text-stone-400">Henüz kısayol yok — aşağıdan ekleyin.</p>}
          {items.map(id => {
            const c = byId[id];
            return (
              <span key={id} data-testid={`dept-item-${id}`}
                className="inline-flex items-center gap-1.5 pl-3 pr-1.5 py-1.5 rounded-xl bg-indigo-50 border border-indigo-200 text-indigo-800 text-xs font-semibold">
                {c?.icon ? <c.icon size={13} /> : null}
                {c?.name || id}
                <button onClick={() => save(items.filter(x => x !== id))} disabled={saving}
                  data-testid={`dept-remove-${id}`} title="Çıkar"
                  className="p-0.5 rounded-md hover:bg-indigo-200 text-indigo-500">
                  <X size={12} weight="bold" />
                </button>
              </span>
            );
          })}
        </div>

        {/* Add via search */}
        <div className="mt-4 relative">
          <div className="flex items-center gap-2 border border-stone-300 rounded-xl px-3 py-2 focus-within:border-indigo-400">
            <MagnifyingGlass size={14} className="text-stone-400" />
            <input value={query} onChange={e => setQuery(e.target.value)}
              placeholder="Ekran ara ve ekle... (ör. arrivals, POS, housekeeping)"
              data-testid="dept-search-input"
              className="flex-1 text-sm outline-none bg-transparent" />
          </div>
          {results.length > 0 && (
            <div className="absolute z-10 mt-1 w-full bg-white border border-stone-200 rounded-xl shadow-lg overflow-hidden" data-testid="dept-search-results">
              {results.map(c => (
                <button key={c.id} onClick={() => { save([...items, c.id]); setQuery(""); }}
                  disabled={saving || items.length >= 15}
                  data-testid={`dept-add-${c.id}`}
                  className="w-full flex items-center gap-2.5 px-3 py-2 text-left text-sm hover:bg-indigo-50 disabled:opacity-40">
                  <Plus size={13} className="text-indigo-500" />
                  {c.icon ? <c.icon size={15} className="text-stone-500" /> : null}
                  <span className="flex-1">{c.name}</span>
                  <span className="text-[10px] text-stone-400 uppercase">{c.group}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        <button onClick={() => save([])} disabled={saving || items.length === 0}
          data-testid="dept-clear-btn"
          className="mt-4 inline-flex items-center gap-1.5 text-xs font-semibold text-stone-400 hover:text-rose-600 disabled:opacity-40">
          <ArrowCounterClockwise size={13} /> Tümünü temizle
        </button>
      </div>
    </div>
  );
}
