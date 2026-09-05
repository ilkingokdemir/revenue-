import { useState, useEffect, useCallback, Fragment } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Plus, Trash, PencilSimple, Check, X } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const EMPTY = { name: "", name_tr: "", name_de: "", code: "custom", adjustment_type: "pct", adjustment_value: 0, cancellation_type: "free", free_cancel_hours: 48, includes: [], deposit_pct: 0, sort_order: 10, badge: "", is_default: false };

function PlanForm({ value, onChange, onSave, onCancel, saving }) {
  const v = value;
  const set = (k, x) => onChange({ ...v, [k]: x });
  const inp = "border border-stone-200 rounded-lg px-2.5 py-1.5 text-xs w-full";
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-2 bg-stone-50 border border-stone-200 rounded-xl p-3" data-testid="rate-plan-form">
      <input className={inp} placeholder="Ad (EN)" value={v.name} onChange={(e) => set("name", e.target.value)} data-testid="rp-name" />
      <input className={inp} placeholder="Ad (TR)" value={v.name_tr} onChange={(e) => set("name_tr", e.target.value)} data-testid="rp-name-tr" />
      <input className={inp} placeholder="Ad (DE)" value={v.name_de} onChange={(e) => set("name_de", e.target.value)} />
      <input className={inp} placeholder="Kod" value={v.code} onChange={(e) => set("code", e.target.value)} />
      <select className={inp} value={v.adjustment_type} onChange={(e) => set("adjustment_type", e.target.value)} data-testid="rp-adj-type">
        <option value="pct">Yüzde fark (%)</option><option value="fixed_per_night">Sabit / gece</option>
      </select>
      <input className={inp} type="number" step="0.5" placeholder="Fark (örn. -10 / +15)" value={v.adjustment_value} onChange={(e) => set("adjustment_value", e.target.value)} data-testid="rp-adj-value" />
      <select className={inp} value={v.cancellation_type} onChange={(e) => set("cancellation_type", e.target.value)} data-testid="rp-cancel">
        <option value="free">Ücretsiz iptal</option><option value="non_refundable">İade edilmez</option>
      </select>
      <input className={inp} type="number" placeholder="Ücretsiz iptal (saat)" value={v.free_cancel_hours} onChange={(e) => set("free_cancel_hours", e.target.value)} disabled={v.cancellation_type !== "free"} />
      <input className={inp} type="number" placeholder="Ön ödeme %" value={v.deposit_pct} onChange={(e) => set("deposit_pct", e.target.value)} data-testid="rp-deposit" />
      <select className={inp} value={v.badge} onChange={(e) => set("badge", e.target.value)}>
        <option value="">Rozet yok</option><option value="popular">Popüler</option><option value="save">Tasarruf</option>
      </select>
      <label className="flex items-center gap-2 text-xs text-stone-700"><input type="checkbox" checked={v.includes?.includes("breakfast")} onChange={(e) => set("includes", e.target.checked ? ["breakfast"] : [])} data-testid="rp-breakfast" /> Kahvaltı dahil</label>
      <label className="flex items-center gap-2 text-xs text-stone-700"><input type="checkbox" checked={!!v.is_default} onChange={(e) => set("is_default", e.target.checked)} /> Varsayılan plan</label>
      <div className="col-span-2 md:col-span-4 flex justify-end gap-2">
        <button onClick={onCancel} className="px-3 py-1.5 text-xs rounded-lg border border-stone-200 inline-flex items-center gap-1"><X size={12} /> İptal</button>
        <button onClick={onSave} disabled={saving || !v.name} className="px-3 py-1.5 text-xs rounded-lg bg-stone-900 text-white inline-flex items-center gap-1 disabled:opacity-50" data-testid="rp-save"><Check size={12} /> Kaydet</button>
      </div>
    </div>
  );
}

export default function RatePlansCard({ propertyId }) {
  const [props, setProps] = useState([]);
  const [pid, setPid] = useState(propertyId && propertyId !== "all" ? propertyId : "");
  const [plans, setPlans] = useState([]);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    axios.get(`${API}/properties`, { withCredentials: true }).then(({ data }) => {
      const list = Array.isArray(data) ? data : data.items || data.properties || [];
      setProps(list);
      if (!pid && list[0]) setPid(list[0].id);
    }).catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const reload = useCallback(() => {
    if (!pid) return;
    axios.get(`${API}/be-rate-plans/${pid}`, { withCredentials: true }).then(({ data }) => setPlans(data || [])).catch(() => toast.error("Planlar yüklenemedi"));
  }, [pid]);
  useEffect(() => { reload(); }, [reload]);

  const save = async () => {
    setSaving(true);
    try {
      const body = { ...form, adjustment_value: Number(form.adjustment_value || 0), free_cancel_hours: Number(form.free_cancel_hours || 0), deposit_pct: Number(form.deposit_pct || 0), sort_order: Number(form.sort_order || 10) };
      if (editing === "new") await axios.post(`${API}/be-rate-plans/${pid}`, body, { withCredentials: true });
      else await axios.put(`${API}/be-rate-plans/${pid}/${editing}`, body, { withCredentials: true });
      toast.success("Plan kaydedildi"); setEditing(null); setForm(EMPTY); reload();
    } catch (e) { toast.error(e.response?.data?.detail || "Kaydedilemedi"); }
    finally { setSaving(false); }
  };
  const remove = async (id) => {
    await axios.delete(`${API}/be-rate-plans/${pid}/${id}`, { withCredentials: true }).catch(() => {});
    toast.success("Silindi"); reload();
  };
  const toggle = async (p) => {
    await axios.put(`${API}/be-rate-plans/${pid}/${p.id}`, { is_active: !p.is_active }, { withCredentials: true }).catch(() => {});
    reload();
  };

  return (
    <div className="space-y-3" data-testid="rate-plans-card">
      <div className="flex items-center gap-3 flex-wrap">
        <select value={pid} onChange={(e) => setPid(e.target.value)} className="border border-stone-200 rounded-lg px-2.5 py-1.5 text-xs" data-testid="rp-property-select">
          {props.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        <p className="text-xs text-stone-500 flex-1">Misafir booking engine'de bu planları oda başına yan yana görür. Fark, odanın temel fiyatına uygulanır.</p>
        <button onClick={() => { setEditing("new"); setForm(EMPTY); }} className="px-3 py-1.5 text-xs text-white bg-stone-900 rounded-lg inline-flex items-center gap-1.5" data-testid="rp-add-btn"><Plus size={13} /> Plan Ekle</button>
      </div>
      {editing === "new" && <PlanForm value={form} onChange={setForm} onSave={save} onCancel={() => setEditing(null)} saving={saving} />}
      <div className="border border-stone-200 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-stone-50 text-xs text-stone-500"><tr>
            <th className="px-4 py-2 text-left">Plan</th><th className="px-4 py-2 text-left">Fiyat farkı</th><th className="px-4 py-2 text-left">İptal</th><th className="px-4 py-2 text-left">Dahil</th><th className="px-4 py-2 text-left">Ön ödeme</th><th className="px-4 py-2 text-left">Durum</th><th className="px-4 py-2 text-right">İşlem</th>
          </tr></thead>
          <tbody>
            {plans.map((p) => (
              <Fragment key={p.id}>
                <tr className="border-t border-stone-100" data-testid={`rp-row-${p.code}`}>
                  <td className="px-4 py-2 font-medium text-stone-800">{p.name_tr || p.name} {p.is_default && <span className="text-[10px] text-stone-400">(varsayılan)</span>} {p.badge && <span className="text-[10px] bg-amber-100 text-amber-700 rounded px-1">{p.badge}</span>}</td>
                  <td className="px-4 py-2 text-xs">{p.adjustment_type === "pct" ? `${p.adjustment_value > 0 ? "+" : ""}${p.adjustment_value}%` : `${p.adjustment_value > 0 ? "+" : ""}£${p.adjustment_value}/gece`}</td>
                  <td className="px-4 py-2 text-xs">{p.cancellation_type === "free" ? `Ücretsiz (${p.free_cancel_hours}s)` : "İade edilmez"}</td>
                  <td className="px-4 py-2 text-xs">{p.includes?.includes("breakfast") ? "Kahvaltı" : "—"}</td>
                  <td className="px-4 py-2 text-xs">{p.deposit_pct ? `%${p.deposit_pct}` : "Yok"}</td>
                  <td className="px-4 py-2"><button onClick={() => toggle(p)} className={`text-xs ${p.is_active !== false ? "text-emerald-600" : "text-stone-400"}`} data-testid={`rp-toggle-${p.code}`}>{p.is_active !== false ? "Aktif" : "Pasif"}</button></td>
                  <td className="px-4 py-2 text-right">
                    <button onClick={() => { setEditing(p.id); setForm({ ...EMPTY, ...p }); }} className="p-1 text-stone-500 hover:text-stone-900" data-testid={`rp-edit-${p.code}`}><PencilSimple size={14} /></button>
                    <button onClick={() => remove(p.id)} className="p-1 text-stone-400 hover:text-red-600" data-testid={`rp-delete-${p.code}`}><Trash size={14} /></button>
                  </td>
                </tr>
                {editing === p.id && <tr><td colSpan={7} className="p-2"><PlanForm value={form} onChange={setForm} onSave={save} onCancel={() => setEditing(null)} saving={saving} /></td></tr>}
              </Fragment>
            ))}
            {plans.length === 0 && <tr><td colSpan={7} className="px-4 py-8 text-center text-xs text-stone-400">Plan yok</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
