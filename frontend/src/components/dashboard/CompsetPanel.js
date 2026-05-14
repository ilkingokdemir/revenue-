import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Crosshair, Plus, X, Sparkle, Trash } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/compset`;

export default function CompsetPanel({ propertyId = "default" }) {
  const [items, setItems] = useState([]);
  const [snapshot, setSnapshot] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({});

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const [c, s] = await Promise.all([
        axios.get(`${API}/${propertyId}`, { withCredentials: true }),
        axios.get(`${API}/${propertyId}/snapshot`, { withCredentials: true }),
      ]);
      setItems(c.data.competitors || []);
      setSnapshot(s.data.competitors || []);
    } catch (e) { toast.error("Yüklenemedi"); }
    finally { setLoading(false); }
  }, [propertyId]);

  useEffect(() => { reload(); }, [reload]);

  async function discover() {
    try {
      const r = await axios.post(`${API}/${propertyId}/discover`, {}, { withCredentials: true });
      toast.success(`${r.data.count} rakip eklendi`);
      reload();
    } catch (e) { toast.error("Keşfedilemedi"); }
  }

  async function addManual() {
    try {
      await axios.post(`${API}/${propertyId}/add`, {
        name: form.name, stars: Number(form.stars || 4),
        rooms: Number(form.rooms || 0),
        distance_km: Number(form.distance_km || 1),
      }, { withCredentials: true });
      toast.success("Rakip eklendi");
      setShowAdd(false); setForm({}); reload();
    } catch (e) { toast.error("Eklenemedi"); }
  }

  async function remove(id) {
    if (!window.confirm("Rakip kaldırılsın mı?")) return;
    try {
      await axios.delete(`${API}/${propertyId}/${id}`, { withCredentials: true });
      reload();
    } catch (e) { toast.error("Kaldırılamadı"); }
  }

  const rateMap = Object.fromEntries(snapshot.map(s => [s.id, s]));

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="compset-panel">
      <div className="mb-4 flex items-start justify-between gap-3 flex-wrap">
        <div>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
            <Crosshair size={12} weight="fill" className="text-sky-500" />
            <span>Competitive Set</span>
          </div>
          <h1 className="text-2xl font-semibold text-stone-900">Compset Yönetimi</h1>
          <p className="text-sm text-stone-500 mt-1 max-w-2xl">
            Yakın rakipleri keşfedin, manuel ekleyin ve son fiyat anlık görüntülerini izleyin.
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={discover} className="px-3 py-1.5 text-xs text-stone-700 bg-white border border-stone-300 rounded-lg inline-flex items-center gap-1.5" data-testid="compset-discover">
            <Sparkle size={13} /> Otomatik Keşif
          </button>
          <button onClick={() => setShowAdd(true)} className="px-3 py-1.5 text-xs text-white bg-stone-900 rounded-lg inline-flex items-center gap-1.5" data-testid="compset-add">
            <Plus size={13} /> Manuel Ekle
          </button>
        </div>
      </div>

      {loading && <div className="text-center py-12 text-stone-400 text-sm">Yükleniyor…</div>}

      {!loading && items.length === 0 && (
        <div className="text-center py-12 text-stone-400 text-sm" data-testid="compset-empty">
          Henüz rakip yok. "Otomatik Keşif" ile başlayın.
        </div>
      )}

      {!loading && items.length > 0 && (
        <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-stone-50 text-[11px] uppercase tracking-wider text-stone-500">
              <tr>
                <th className="px-4 py-2 text-left">Rakip</th>
                <th className="px-4 py-2 text-left">Yıldız</th>
                <th className="px-4 py-2 text-left">Oda</th>
                <th className="px-4 py-2 text-left">Mesafe</th>
                <th className="px-4 py-2 text-right">Son Fiyat</th>
                <th className="px-4 py-2 text-left">Durum</th>
                <th className="px-4 py-2 text-left">Kaynak</th>
                <th className="px-4 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {items.map(c => {
                const snap = rateMap[c.id] || {};
                return (
                  <tr key={c.id} className="border-t border-stone-100" data-testid={`compset-row-${c.id}`}>
                    <td className="px-4 py-2 font-medium">{c.name}</td>
                    <td className="px-4 py-2 text-amber-600">{"★".repeat(c.stars || 0)}</td>
                    <td className="px-4 py-2 text-xs">{c.rooms || "—"}</td>
                    <td className="px-4 py-2 text-xs">{c.distance_km ? `${c.distance_km} km` : "—"}</td>
                    <td className="px-4 py-2 text-right font-medium">£{snap.last_rate?.toFixed(2) || "—"}</td>
                    <td className="px-4 py-2 text-xs">{snap.last_availability || "—"}</td>
                    <td className="px-4 py-2 text-xs text-stone-500">{c.source}</td>
                    <td className="px-4 py-2 text-right">
                      <button onClick={() => remove(c.id)} className="text-stone-400 hover:text-rose-500" data-testid={`compset-remove-${c.id}`}>
                        <Trash size={14} />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {showAdd && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={() => setShowAdd(false)}>
          <div className="bg-white rounded-xl w-full max-w-md p-5" onClick={e => e.stopPropagation()} data-testid="compset-add-modal">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-semibold">Manuel Rakip Ekle</h3>
              <button onClick={() => setShowAdd(false)}><X size={16} /></button>
            </div>
            <div className="space-y-3">
              <input placeholder="Otel adı" value={form.name || ""} onChange={e => setForm({ ...form, name: e.target.value })}
                     className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg" data-testid="compset-form-name" />
              <div className="grid grid-cols-3 gap-2">
                <input type="number" placeholder="Yıldız" value={form.stars || ""} onChange={e => setForm({ ...form, stars: e.target.value })}
                       className="px-3 py-2 text-sm border border-stone-300 rounded-lg" />
                <input type="number" placeholder="Oda" value={form.rooms || ""} onChange={e => setForm({ ...form, rooms: e.target.value })}
                       className="px-3 py-2 text-sm border border-stone-300 rounded-lg" />
                <input type="number" step="0.1" placeholder="km" value={form.distance_km || ""} onChange={e => setForm({ ...form, distance_km: e.target.value })}
                       className="px-3 py-2 text-sm border border-stone-300 rounded-lg" />
              </div>
              <button onClick={addManual} disabled={!form.name} className="w-full py-2 text-sm text-white bg-stone-900 rounded-lg disabled:opacity-50" data-testid="compset-form-save">
                Kaydet
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
