import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ForkKnife,
  Plus,
  Trash,
  Calculator,
  ChartLineUp,
  ArrowsClockwise,
  WarningCircle,
  CheckCircle,
} from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

const blankRecipe = {
  name: "",
  category: "Mains",
  yields: 1,
  sell_price: 0,
  target_margin_pct: 70,
  lines: [],
  pos_menu_item_id: "",
  notes: "",
};

const blankIng = { name: "", unit: "g", cost_per_unit: 0, waste_pct: 0, supplier: "" };

export default function RecipeCogsPanel({ propertyId = "default" }) {
  const [tab, setTab] = useState("recipes");
  const [recipes, setRecipes] = useState([]);
  const [ingredients, setIngredients] = useState([]);
  const [dash, setDash] = useState(null);
  const [forecast, setForecast] = useState(null);
  const [editing, setEditing] = useState(null);
  const [newIng, setNewIng] = useState(blankIng);

  const reload = useCallback(async () => {
    try {
      const [r, i, d] = await Promise.all([
        axios.get(`${API}/api/recipes/${propertyId}`, { withCredentials: true }),
        axios.get(`${API}/api/ingredients/${propertyId}`, { withCredentials: true }),
        axios.get(`${API}/api/recipes/${propertyId}/dashboard`, { withCredentials: true }),
      ]);
      setRecipes(r.data.items || []);
      setIngredients(i.data.items || []);
      setDash(d.data);
    } catch (e) {
      toast.error("Veri yüklenemedi");
    }
  }, [propertyId]);

  useEffect(() => { reload(); }, [reload]);

  const saveRecipe = async () => {
    if (!editing.name) return toast.error("Tarif adı gerekli");
    try {
      const url = editing.id
        ? `${API}/api/recipes/${propertyId}/${editing.id}`
        : `${API}/api/recipes/${propertyId}`;
      const method = editing.id ? "put" : "post";
      const r = await axios[method](url, editing, { withCredentials: true });
      toast.success("Kaydedildi");
      setEditing(null);
      reload();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Kaydedilemedi");
    }
  };

  const removeRecipe = async (id) => {
    if (!window.confirm("Tarif silinsin mi?")) return;
    try {
      await axios.delete(`${API}/api/recipes/${propertyId}/${id}`, { withCredentials: true });
      toast.success("Silindi");
      reload();
    } catch (e) {
      toast.error("Silinemedi");
    }
  };

  const addIngredient = async () => {
    if (!newIng.name) return toast.error("Malzeme adı gerekli");
    try {
      await axios.post(`${API}/api/ingredients/${propertyId}`, newIng, { withCredentials: true });
      setNewIng(blankIng);
      reload();
      toast.success("Malzeme eklendi");
    } catch {
      toast.error("Eklenemedi");
    }
  };

  const removeIng = async (id) => {
    try {
      await axios.delete(`${API}/api/ingredients/${propertyId}/${id}`, { withCredentials: true });
      reload();
    } catch {}
  };

  const runForecast = async () => {
    try {
      const r = await axios.post(`${API}/api/recipes/${propertyId}/forecast-week`, {}, { withCredentials: true });
      setForecast(r.data);
      toast.success(`Tahmin hazır: ${r.data.items?.length || 0} malzeme`);
    } catch {
      toast.error("Tahmin başarısız");
    }
  };

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="recipe-cogs-panel">
      <div className="mb-5 flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
            <ForkKnife size={12} weight="fill" className="text-rose-500" />
            <span>Food & Events · Recipe COGS</span>
          </div>
          <h1 className="text-2xl font-semibold text-stone-900">Reçete maliyetleri (COGS)</h1>
          <p className="text-sm text-stone-500 mt-1 max-w-2xl">
            Malzeme ağacı, alt-reçeteler ve modifier'lar ile tabak başı maliyet & marj hesabı.
            POS satışlarınızla haftalık malzeme öngörüsü.
          </p>
        </div>
        <button onClick={reload} className="px-3 py-2 bg-stone-100 text-stone-700 rounded-md text-sm hover:bg-stone-200 flex items-center gap-2" data-testid="recipe-refresh">
          <ArrowsClockwise size={14} /> Yenile
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5" data-testid="recipe-kpis">
        <Kpi label="Tarif sayısı" value={dash?.recipe_count ?? 0} icon={ForkKnife} />
        <Kpi label="Malzeme sayısı" value={dash?.ingredient_count ?? 0} icon={Calculator} />
        <Kpi label="Ortalama marj" value={`${dash?.avg_margin_pct ?? 0}%`} icon={ChartLineUp} tone={(dash?.avg_margin_pct ?? 0) >= 65 ? "ok" : "warn"} />
        <Kpi label="Hedefin altı" value={dash?.items_below_target ?? 0} icon={WarningCircle} tone={(dash?.items_below_target ?? 0) > 0 ? "bad" : "ok"} />
      </div>

      <div className="flex border-b border-stone-200 mb-4">
        {[["recipes", "Tarifler"], ["ingredients", "Malzemeler"], ["under", "Düşük marjlılar"], ["forecast", "Haftalık tahmin"]].map(([k, l]) => (
          <button key={k} onClick={() => setTab(k)} data-testid={`recipe-tab-${k}`}
            className={`px-4 py-2 text-sm border-b-2 ${tab === k ? "border-indigo-600 text-indigo-700 font-medium" : "border-transparent text-stone-500 hover:text-stone-800"}`}>{l}</button>
        ))}
      </div>

      {tab === "recipes" && (
        <div className="bg-white border border-stone-200 rounded-lg p-3" data-testid="recipe-list">
          <button onClick={() => setEditing({ ...blankRecipe })}
            className="mb-3 px-3 py-1.5 bg-indigo-600 text-white rounded text-sm flex items-center gap-1 hover:bg-indigo-700" data-testid="recipe-new-btn">
            <Plus size={14} /> Yeni tarif
          </button>
          {recipes.length === 0 && <p className="text-xs text-stone-400 italic p-3">Henüz tarif yok.</p>}
          <table className="w-full text-sm">
            <thead><tr className="text-left text-xs text-stone-500 border-b border-stone-200">
              <th className="py-1 pr-2">Tarif</th><th className="py-1 pr-2">Kategori</th><th className="py-1 pr-2">Tabak maliyeti</th><th className="py-1 pr-2">Satış</th><th className="py-1 pr-2">Marj</th><th></th>
            </tr></thead>
            <tbody>
              {recipes.map((r) => (
                <tr key={r.id} className="border-b border-stone-100 hover:bg-stone-50">
                  <td className="py-1.5 pr-2 font-medium">{r.name}</td>
                  <td className="py-1.5 pr-2 text-stone-500">{r.category}</td>
                  <td className="py-1.5 pr-2 font-mono">{r.cogs?.cogs_per_plate?.toFixed(2)}</td>
                  <td className="py-1.5 pr-2 font-mono">{r.sell_price?.toFixed(2)}</td>
                  <td className="py-1.5 pr-2"><MarginPill margin={r.cogs?.current_margin_pct} target={r.target_margin_pct} /></td>
                  <td className="py-1.5 pr-2 flex gap-1">
                    <button onClick={() => setEditing({ ...r })} className="text-xs text-indigo-600 hover:underline" data-testid={`recipe-edit-${r.id}`}>Düzenle</button>
                    <button onClick={() => removeRecipe(r.id)} className="text-xs text-red-600 hover:underline" data-testid={`recipe-delete-${r.id}`}>Sil</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "ingredients" && (
        <div className="bg-white border border-stone-200 rounded-lg p-3" data-testid="ing-list">
          <div className="grid grid-cols-1 md:grid-cols-6 gap-2 items-end mb-3">
            <Input label="Ad" v={newIng.name} setV={(v) => setNewIng({ ...newIng, name: v })} testId="ing-name" />
            <Input label="Birim" v={newIng.unit} setV={(v) => setNewIng({ ...newIng, unit: v })} testId="ing-unit" />
            <Input label="Birim maliyeti" type="number" v={newIng.cost_per_unit} setV={(v) => setNewIng({ ...newIng, cost_per_unit: parseFloat(v) || 0 })} testId="ing-cost" />
            <Input label="Fire %" type="number" v={newIng.waste_pct} setV={(v) => setNewIng({ ...newIng, waste_pct: parseFloat(v) || 0 })} testId="ing-waste" />
            <Input label="Tedarikçi" v={newIng.supplier} setV={(v) => setNewIng({ ...newIng, supplier: v })} testId="ing-supplier" />
            <button onClick={addIngredient} data-testid="ing-add" className="px-3 py-1.5 bg-emerald-600 text-white rounded text-sm hover:bg-emerald-700">+ Ekle</button>
          </div>
          {ingredients.length === 0 && <p className="text-xs text-stone-400 italic p-3">Henüz malzeme yok.</p>}
          <table className="w-full text-sm">
            <thead><tr className="text-left text-xs text-stone-500 border-b border-stone-200"><th>Ad</th><th>Birim</th><th>Maliyet</th><th>Fire</th><th>Tedarikçi</th><th></th></tr></thead>
            <tbody>
              {ingredients.map((i) => (
                <tr key={i.id} className="border-b border-stone-100">
                  <td className="py-1.5">{i.name}</td>
                  <td className="py-1.5 font-mono text-xs">{i.unit}</td>
                  <td className="py-1.5 font-mono">{(i.cost_per_unit || 0).toFixed(3)}</td>
                  <td className="py-1.5 font-mono">{i.waste_pct || 0}%</td>
                  <td className="py-1.5 text-stone-500">{i.supplier || "—"}</td>
                  <td className="py-1.5"><button onClick={() => removeIng(i.id)} className="text-red-600 text-xs hover:underline">Sil</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "under" && dash && (
        <div className="bg-white border border-stone-200 rounded-lg p-3" data-testid="recipe-under">
          {dash.underperformers.length === 0
            ? <p className="text-sm text-emerald-700 p-3"><CheckCircle weight="fill" className="inline" /> Tüm tarifler hedefin üstünde — hepsi sağlıklı.</p>
            : <table className="w-full text-sm">
                <thead><tr className="text-left text-xs text-stone-500 border-b border-stone-200"><th>Tarif</th><th>Mevcut marj</th><th>Hedef</th><th>Önerilen fiyat</th></tr></thead>
                <tbody>
                  {dash.underperformers.map((u) => (
                    <tr key={u.id} className="border-b border-stone-100">
                      <td className="py-1.5">{u.name}</td>
                      <td className="py-1.5 text-red-600 font-mono">{u.margin}%</td>
                      <td className="py-1.5 font-mono">{u.target}%</td>
                      <td className="py-1.5 font-mono font-semibold text-emerald-700">{u.suggested_price.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
          }
        </div>
      )}

      {tab === "forecast" && (
        <div className="bg-white border border-stone-200 rounded-lg p-3" data-testid="recipe-forecast">
          <button onClick={runForecast} className="mb-3 px-3 py-1.5 bg-violet-600 text-white rounded text-sm hover:bg-violet-700" data-testid="forecast-run">
            Tahmini hesapla (son 14 gün × tarifler)
          </button>
          {forecast && (
            <>
              <p className="text-sm mb-2">Toplam haftalık malzeme bütçesi: <b>{forecast.total_weekly_cost?.toFixed(2)}</b></p>
              <table className="w-full text-sm">
                <thead><tr className="text-left text-xs text-stone-500 border-b border-stone-200"><th>Malzeme</th><th>Haftalık miktar</th><th>Birim</th><th>Maliyet</th></tr></thead>
                <tbody>
                  {forecast.items.map((f) => (
                    <tr key={f.ingredient_id} className="border-b border-stone-100">
                      <td className="py-1.5">{f.name}</td>
                      <td className="py-1.5 font-mono">{f.weekly_qty}</td>
                      <td className="py-1.5 font-mono text-xs">{f.unit}</td>
                      <td className="py-1.5 font-mono">{f.weekly_cost.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      )}

      {editing && (
        <div className="fixed inset-0 bg-black/40 flex items-start justify-center z-50 p-6 overflow-auto" onClick={() => setEditing(null)} data-testid="recipe-modal">
          <div className="bg-white rounded-lg w-full max-w-3xl p-5" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-semibold mb-3">{editing.id ? "Tarif düzenle" : "Yeni tarif"}</h2>
            <div className="grid grid-cols-2 gap-3 mb-3">
              <Input label="Ad" v={editing.name} setV={(v) => setEditing({ ...editing, name: v })} testId="r-name" />
              <Input label="Kategori" v={editing.category} setV={(v) => setEditing({ ...editing, category: v })} testId="r-cat" />
              <Input label="Tabak/batch" type="number" v={editing.yields} setV={(v) => setEditing({ ...editing, yields: parseInt(v) || 1 })} testId="r-yields" />
              <Input label="Satış fiyatı" type="number" v={editing.sell_price} setV={(v) => setEditing({ ...editing, sell_price: parseFloat(v) || 0 })} testId="r-price" />
              <Input label="Hedef marj %" type="number" v={editing.target_margin_pct} setV={(v) => setEditing({ ...editing, target_margin_pct: parseFloat(v) || 0 })} testId="r-target" />
              <Input label="POS menü ID" v={editing.pos_menu_item_id} setV={(v) => setEditing({ ...editing, pos_menu_item_id: v })} testId="r-pos" />
            </div>
            <h3 className="text-sm font-semibold mb-2">Malzemeler</h3>
            {(editing.lines || []).map((l, idx) => (
              <div key={idx} className="grid grid-cols-12 gap-2 mb-1 items-center">
                <select className="col-span-7 text-sm border border-stone-200 rounded px-2 py-1" value={l.ingredient_id || ""}
                  onChange={(e) => {
                    const next = [...editing.lines]; next[idx] = { ...next[idx], ingredient_id: e.target.value }; setEditing({ ...editing, lines: next });
                  }} data-testid={`r-line-ing-${idx}`}>
                  <option value="">— Malzeme seç —</option>
                  {ingredients.map((i) => <option key={i.id} value={i.id}>{i.name} ({i.unit}, {i.cost_per_unit})</option>)}
                </select>
                <input type="number" className="col-span-3 text-sm border border-stone-200 rounded px-2 py-1" value={l.qty} placeholder="qty"
                  onChange={(e) => {
                    const next = [...editing.lines]; next[idx] = { ...next[idx], qty: parseFloat(e.target.value) || 0 }; setEditing({ ...editing, lines: next });
                  }} data-testid={`r-line-qty-${idx}`} />
                <button className="col-span-2 text-red-600 text-xs"
                  onClick={() => setEditing({ ...editing, lines: editing.lines.filter((_, i) => i !== idx) })}>Sil</button>
              </div>
            ))}
            <button onClick={() => setEditing({ ...editing, lines: [...(editing.lines || []), { ingredient_id: "", qty: 0 }] })}
              className="text-xs text-indigo-600 hover:underline mb-3" data-testid="r-add-line">+ Malzeme satırı ekle</button>
            <div className="flex justify-end gap-2 pt-3 border-t border-stone-100">
              <button onClick={() => setEditing(null)} className="px-3 py-1.5 bg-stone-100 rounded text-sm">Vazgeç</button>
              <button onClick={saveRecipe} data-testid="r-save" className="px-4 py-1.5 bg-indigo-600 text-white rounded text-sm hover:bg-indigo-700">Kaydet</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const Kpi = ({ label, value, icon: Icon, tone }) => (
  <div className={`bg-white border rounded-lg p-3 ${tone === "ok" ? "border-emerald-200" : tone === "bad" ? "border-red-200" : tone === "warn" ? "border-amber-200" : "border-stone-200"}`}>
    <div className="flex items-center justify-between text-stone-500 mb-1"><span className="text-[10px] uppercase tracking-wide">{label}</span>{Icon && <Icon size={14} />}</div>
    <div className="text-lg font-semibold text-stone-900">{value}</div>
  </div>
);

const Input = ({ label, v, setV, type = "text", testId }) => (
  <div>
    <label className="text-xs text-stone-500 mb-1 block">{label}</label>
    <input type={type} value={v ?? ""} onChange={(e) => setV(e.target.value)} className="w-full text-sm border border-stone-200 rounded px-3 py-1.5" data-testid={testId} />
  </div>
);

const MarginPill = ({ margin, target }) => {
  if (margin == null || isNaN(margin)) return <span className="text-stone-300">—</span>;
  const ok = margin >= (target || 70);
  return <span className={`text-[11px] px-2 py-0.5 rounded font-medium ${ok ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>{margin.toFixed(1)}%</span>;
};
