import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ForkKnife,
  Fire,
  Snowflake,
  BeerBottle,
  Timer,
  CheckCircle,
  Prohibit,
  ArrowsClockwise,
  ArrowRight,
} from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

const STATION_META = {
  hot: { label: "Hot Kitchen", icon: Fire, color: "rose" },
  cold: { label: "Cold Station", icon: Snowflake, color: "sky" },
  grill: { label: "Grill", icon: Fire, color: "amber" },
  bar: { label: "Bar", icon: BeerBottle, color: "violet" },
  dessert: { label: "Dessert", icon: ForkKnife, color: "pink" },
};

export default function KDSPanel({ propertyId, hotelName }) {
  const [tab, setTab] = useState("kds");

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="kds-panel">
      <div className="mb-5">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          <ForkKnife size={12} weight="fill" className="text-rose-500" />
          <span>Kitchen Ops</span>
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">
          Mutfak Ekran + 86 Listesi · {hotelName || "Property"}
        </h1>
      </div>

      <div className="flex gap-2 mb-5 border-b border-stone-200">
        <TabBtn active={tab === "kds"} onClick={() => setTab("kds")} testId="kds-tab-kds">
          Canlı Ekran
        </TabBtn>
        <TabBtn active={tab === "86"} onClick={() => setTab("86")} testId="kds-tab-86">
          86 Listesi
        </TabBtn>
        <TabBtn active={tab === "recipes"} onClick={() => setTab("recipes")} testId="kds-tab-recipes">
          Reçeteler
        </TabBtn>
      </div>

      {tab === "kds" && <KDSStream propertyId={propertyId} />}
      {tab === "86" && <EightySixList propertyId={propertyId} />}
      {tab === "recipes" && <RecipesTab propertyId={propertyId} />}
    </div>
  );
}

function TabBtn({ active, onClick, children, testId }) {
  return (
    <button
      onClick={onClick}
      data-testid={testId}
      className={`px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition ${
        active
          ? "border-rose-500 text-rose-600"
          : "border-transparent text-stone-500 hover:text-stone-700"
      }`}
    >
      {children}
    </button>
  );
}

function KDSStream({ propertyId }) {
  const [data, setData] = useState({ by_station: {}, counters: {}, orders: [] });
  const [tick, setTick] = useState(0);

  const load = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/api/kds/${propertyId}`);
      setData(data);
    } catch (_) { /* silent */ }
  }, [propertyId]);

  useEffect(() => { load(); }, [load, tick]);

  // Auto-refresh every 10s
  useEffect(() => {
    const t = setInterval(() => setTick((x) => x + 1), 10000);
    return () => clearInterval(t);
  }, []);

  const bump = async (orderId, nextStatus) => {
    try {
      const { data: r } = await axios.post(`${API}/api/kds/bump`, {
        order_id: orderId, next_status: nextStatus,
      });
      toast.success(
        r.deductions?.length > 0
          ? `Bumped · ${r.deductions.length} stok düşürüldü`
          : "Bumped"
      );
      load();
    } catch (_) { toast.error("Bump başarısız"); }
  };

  const stations = Object.keys(data.by_station || {}).sort();

  return (
    <div className="space-y-4" data-testid="kds-stream">
      {/* Counters */}
      <div className="grid grid-cols-4 gap-3">
        <Kpi label="Yeni" value={data.counters?.new || 0} accent="sky" />
        <Kpi label="Hazırlanıyor" value={data.counters?.preparing || 0} accent="amber" />
        <Kpi label="Hazır" value={data.counters?.ready || 0} accent="emerald" />
        <Kpi
          label="En eski (dk)"
          value={Math.round(data.oldest_age_minutes || 0)}
          accent={data.oldest_age_minutes > 10 ? "rose" : "stone"}
        />
      </div>

      {/* Stations */}
      {stations.length === 0 ? (
        <div className="p-8 rounded-xl bg-white border border-stone-200 text-center text-sm text-stone-500">
          Mutfak kuyruğu boş. ✓
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {stations.map((s) => {
            const meta = STATION_META[s] || { label: s, icon: ForkKnife, color: "stone" };
            const Icon = meta.icon;
            const items = data.by_station[s];
            return (
              <div key={s} className="rounded-xl bg-white border border-stone-200 overflow-hidden"
                data-testid={`kds-station-${s}`}>
                <div className={`px-4 py-3 border-b border-stone-200 flex items-center gap-2 bg-${meta.color}-50`}>
                  <Icon size={16} className={`text-${meta.color}-600`} weight="bold" />
                  <div className="font-semibold text-stone-900">{meta.label}</div>
                  <span className="ml-auto text-xs px-2 py-0.5 rounded-full bg-white border border-stone-200 font-mono">
                    {items.length}
                  </span>
                </div>
                <div className="divide-y divide-stone-100 max-h-[60vh] overflow-y-auto">
                  {items.map((it, i) => {
                    const colorCls = {
                      green: "border-l-emerald-500",
                      amber: "border-l-amber-500",
                      red: "border-l-rose-500",
                    }[it.age_color];
                    const statusNext = it.status === "new" ? "preparing" : it.status === "preparing" ? "ready" : "served";
                    return (
                      <div key={`${it.order_id}-${i}`} className={`p-3 border-l-4 ${colorCls}`}>
                        <div className="flex items-start justify-between mb-1">
                          <div className="text-xs text-stone-500 font-mono">
                            #{it.order_number} {it.table && `· Masa ${it.table}`}
                          </div>
                          <div className={`text-xs flex items-center gap-1 font-mono ${
                            it.age_color === "red" ? "text-rose-600" :
                            it.age_color === "amber" ? "text-amber-600" : "text-emerald-600"
                          }`}>
                            <Timer size={10} />
                            {Math.round(it.age_minutes)}dk
                          </div>
                        </div>
                        <div className="text-sm font-semibold text-stone-900">
                          {it.qty}× {it.name}
                        </div>
                        {it.notes && <div className="text-xs text-stone-500 italic mt-0.5">"{it.notes}"</div>}
                        <div className="flex items-center gap-2 mt-2">
                          <span className={`text-[10px] px-2 py-0.5 rounded-full ${
                            it.status === "new" ? "bg-sky-100 text-sky-700" :
                            it.status === "preparing" ? "bg-amber-100 text-amber-700" :
                            "bg-emerald-100 text-emerald-700"
                          }`}>
                            {it.status}
                          </span>
                          <button
                            onClick={() => bump(it.order_id, statusNext)}
                            className="ml-auto text-xs px-2.5 py-1 rounded-md bg-stone-900 text-white hover:bg-stone-700 flex items-center gap-1"
                            data-testid={`kds-bump-${it.order_id}`}
                          >
                            Bump <ArrowRight size={10} />
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function EightySixList({ propertyId }) {
  const [list, setList] = useState([]);
  const [allMenu, setAllMenu] = useState([]);

  const load = useCallback(async () => {
    try {
      const [l, m] = await Promise.all([
        axios.get(`${API}/api/86-list/${propertyId}`),
        axios.get(`${API}/api/pos/menu/${propertyId}`).catch(() => ({ data: { items: [] } })),
      ]);
      setList(l.data.items || []);
      setAllMenu(m?.data?.items || m?.data || []);
    } catch (_) { /* silent */ }
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);

  const toggle = async (itemId, newVal, reason = "") => {
    try {
      await axios.post(`${API}/api/86-list/toggle`, {
        menu_item_id: itemId, on_86: newVal, reason,
      });
      toast.success(newVal ? "Menüden çıkarıldı (86)" : "Menüye geri eklendi");
      load();
    } catch (_) { toast.error("Güncelleme başarısız"); }
  };

  const available = allMenu.filter((i) => !i.on_86);

  return (
    <div className="space-y-4" data-testid="86-list-tab">
      <div className="grid grid-cols-3 gap-3">
        <Kpi label="86 listesindeki" value={list.length} accent="rose" />
        <Kpi label="Menüde aktif" value={available.length} accent="emerald" />
        <Kpi label="Toplam menü" value={allMenu.length} accent="stone" />
      </div>

      {/* Current 86 list */}
      <div className="p-4 rounded-xl bg-white border border-stone-200">
        <h3 className="text-sm font-semibold text-stone-900 mb-3 flex items-center gap-2">
          <Prohibit size={16} className="text-rose-500" />
          Şu anda 86 listesinde ({list.length})
        </h3>
        {list.length === 0 ? (
          <div className="text-xs text-stone-500 py-4 text-center">
            Listede öğe yok. Tüm menü aktif. ✓
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            {list.map((it) => (
              <div key={it.id} className="px-3 py-1.5 rounded-full bg-rose-50 border border-rose-200 text-xs flex items-center gap-2"
                data-testid={`86-chip-${it.id}`}>
                <span className="font-medium text-rose-900">{it.name}</span>
                {it.on_86_reason && <span className="text-rose-600 italic">"{it.on_86_reason}"</span>}
                <button onClick={() => toggle(it.id, false)}
                  className="ml-1 text-rose-600 hover:text-rose-800 font-bold">
                  ×
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Available menu */}
      <div className="p-4 rounded-xl bg-white border border-stone-200">
        <h3 className="text-sm font-semibold text-stone-900 mb-3">Aktif menü · 86'ya ekle</h3>
        <div className="max-h-[50vh] overflow-y-auto">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
            {available.map((it) => (
              <button
                key={it.id}
                onClick={() => {
                  const reason = window.prompt(`"${it.name}" niçin 86'ya?\n(Boş bırak → sessizce ekle)`);
                  if (reason === null) return;
                  toggle(it.id, true, reason || "");
                }}
                className="p-2 rounded-lg border border-stone-200 hover:border-rose-300 hover:bg-rose-50 text-left text-sm transition"
                data-testid={`86-add-${it.id}`}
              >
                <div className="font-medium text-stone-900 truncate">{it.name}</div>
                {it.price && <div className="text-xs text-stone-500">£{it.price}</div>}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function RecipesTab({ propertyId }) {
  const [rows, setRows] = useState([]);
  const [stats, setStats] = useState({});
  const [editing, setEditing] = useState(null);
  const [stockItems, setStockItems] = useState([]);

  const load = useCallback(async () => {
    try {
      const [r, s] = await Promise.all([
        axios.get(`${API}/api/pos-recipes/property/${propertyId}`),
        axios.get(`${API}/api/stock/${propertyId}`).catch(() => ({ data: { items: [] } })),
      ]);
      setRows(r.data.rows || []);
      setStats({ total: r.data.total, with_recipe: r.data.with_recipe });
      setStockItems(s?.data?.items || s?.data || []);
    } catch (_) { /* silent */ }
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-4" data-testid="recipes-tab">
      <div className="grid grid-cols-3 gap-3">
        <Kpi label="Reçeteli ürün" value={stats.with_recipe || 0} accent="emerald" />
        <Kpi label="Reçetesiz" value={(stats.total || 0) - (stats.with_recipe || 0)} accent="amber" />
        <Kpi label="Stok kalemi" value={stockItems.length} accent="stone" />
      </div>

      <div className="p-4 rounded-xl bg-white border border-stone-200">
        <div className="max-h-[60vh] overflow-y-auto divide-y divide-stone-100">
          {rows.map((r) => (
            <div key={r.menu_item_id} className="py-2.5 flex items-center gap-3 text-sm">
              <div className="flex-1 min-w-0">
                <div className="font-medium text-stone-900 truncate">{r.menu_item_name}</div>
                <div className="text-xs text-stone-500 mt-0.5">
                  £{r.price} ·{" "}
                  {r.has_recipe ? (
                    <span className="text-emerald-600">✓ {r.component_count} bileşen</span>
                  ) : (
                    <span className="text-amber-600">Reçete yok</span>
                  )}
                  {r.on_86 && <span className="ml-2 text-rose-600">86</span>}
                </div>
              </div>
              <button
                onClick={() => setEditing({ menu_item_id: r.menu_item_id, name: r.menu_item_name })}
                className="px-2.5 py-1 text-xs bg-stone-100 hover:bg-stone-200 rounded-md"
                data-testid={`recipe-edit-${r.menu_item_id}`}
              >
                {r.has_recipe ? "Düzenle" : "Ekle"}
              </button>
            </div>
          ))}
        </div>
      </div>

      {editing && (
        <RecipeEditor
          menuItem={editing}
          stockItems={stockItems}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); load(); }}
        />
      )}
    </div>
  );
}

function RecipeEditor({ menuItem, stockItems, onClose, onSaved }) {
  const [components, setComponents] = useState([]);

  useEffect(() => {
    axios.get(`${API}/api/pos-recipes/${menuItem.menu_item_id}`)
      .then(({ data }) => setComponents(data.components || []))
      .catch(() => {});
  }, [menuItem.menu_item_id]);

  const addComp = () => setComponents([...components, { stock_item_id: "", qty: 1, unit: "adet" }]);
  const updateComp = (i, patch) => setComponents(components.map((c, idx) => idx === i ? { ...c, ...patch } : c));
  const removeComp = (i) => setComponents(components.filter((_, idx) => idx !== i));

  const save = async () => {
    try {
      await axios.post(`${API}/api/pos-recipes`, {
        menu_item_id: menuItem.menu_item_id,
        components: components.filter((c) => c.stock_item_id),
      });
      toast.success("Reçete kaydedildi");
      onSaved();
    } catch (_) { toast.error("Kaydetme başarısız"); }
  };

  return (
    <div className="fixed inset-0 bg-black/30 z-40 flex items-center justify-center p-4"
      onClick={onClose} data-testid="recipe-editor">
      <div className="bg-white rounded-2xl max-w-lg w-full p-5" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-lg font-bold text-stone-900 mb-1">{menuItem.name} · Reçete</h3>
        <p className="text-xs text-stone-500 mb-4">Her porsiyonda tüketilen stok kalemleri</p>
        <div className="space-y-2 max-h-[40vh] overflow-y-auto">
          {components.length === 0 && (
            <div className="text-xs text-stone-500 italic">Henüz bileşen yok.</div>
          )}
          {components.map((c, i) => (
            <div key={i} className="flex items-center gap-2">
              <select value={c.stock_item_id}
                onChange={(e) => updateComp(i, { stock_item_id: e.target.value })}
                className="flex-1 px-2 py-1.5 rounded border border-stone-300 text-sm">
                <option value="">— Stok seçin —</option>
                {stockItems.map((s) => (
                  <option key={s.id} value={s.id}>{s.name} ({s.unit || "adet"})</option>
                ))}
              </select>
              <input type="number" value={c.qty} step={0.1} min={0}
                onChange={(e) => updateComp(i, { qty: Number(e.target.value) })}
                className="w-20 px-2 py-1.5 rounded border border-stone-300 text-sm" />
              <span className="text-xs text-stone-500 w-10">{c.unit}</span>
              <button onClick={() => removeComp(i)}
                className="text-rose-600 hover:text-rose-800 text-sm font-bold">×</button>
            </div>
          ))}
        </div>
        <button onClick={addComp}
          className="mt-3 text-xs text-rose-600 hover:text-rose-800 flex items-center gap-1">
          + Bileşen ekle
        </button>
        <div className="flex gap-2 mt-5 border-t border-stone-100 pt-4">
          <button onClick={save}
            className="flex-1 px-3 py-2 bg-rose-600 text-white rounded-lg text-sm font-medium hover:bg-rose-700"
            data-testid="recipe-save">
            Kaydet
          </button>
          <button onClick={onClose} className="px-3 py-2 bg-stone-100 text-stone-700 rounded-lg text-sm hover:bg-stone-200">
            İptal
          </button>
        </div>
      </div>
    </div>
  );
}

function Kpi({ label, value, accent }) {
  const m = {
    emerald: "text-emerald-700", rose: "text-rose-600",
    amber: "text-amber-600", sky: "text-sky-700",
    stone: "text-stone-900",
  };
  return (
    <div className="p-3 rounded-xl bg-white border border-stone-200">
      <div className="text-[10px] uppercase tracking-wider text-stone-500 mb-1">{label}</div>
      <div className={`text-2xl font-bold ${m[accent] || m.stone}`}>{value}</div>
    </div>
  );
}
