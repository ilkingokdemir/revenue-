import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Package, TrendUp, ShoppingCartSimple, Plus, X } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/booking-engine`;

const TABS = [
  { id: "packages", label: "Paketler", icon: Package },
  { id: "upsells", label: "Upsell", icon: TrendUp },
  { id: "abandoned", label: "Bırakılan Sepetler", icon: ShoppingCartSimple },
];

export default function BookingEngineV2Panel({ propertyId = "all" }) {
  const [tab, setTab] = useState("packages");
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({});

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      let url = "";
      if (tab === "packages") url = `${API}/packages?property_id=${propertyId}`;
      if (tab === "upsells") url = `${API}/upsells?property_id=${propertyId}`;
      if (tab === "abandoned") url = `${API}/cart/abandoned?days=14`;
      const r = await axios.get(url, { withCredentials: true });
      setItems(r.data.packages || r.data.upsells || r.data.carts || []);
    } catch (e) { toast.error("Yüklenemedi"); }
    finally { setLoading(false); }
  }, [tab, propertyId]);

  useEffect(() => { reload(); }, [reload]);

  async function create() {
    try {
      if (tab === "packages") {
        await axios.post(`${API}/packages`, {
          name: form.name, description: form.description || "",
          property_id: propertyId, discount_percent: Number(form.discount_percent || 0),
          extras: [],
        }, { withCredentials: true });
      } else if (tab === "upsells") {
        await axios.post(`${API}/upsells`, {
          name: form.name, description: form.description || "",
          property_id: propertyId, target: form.target || "booking_confirmation",
          type: form.type || "room_upgrade", payload: {},
        }, { withCredentials: true });
      }
      toast.success("Oluşturuldu");
      setShowCreate(false); setForm({}); reload();
    } catch (e) { toast.error("Kaydedilemedi"); }
  }

  async function recover(cartId) {
    try {
      await axios.post(`${API}/cart/recover/${cartId}`, {}, { withCredentials: true });
      toast.success("Kurtarma maili kuyruğa eklendi");
      reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Mail kuyruğa alınamadı");
    }
  }

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="booking-engine-v2-panel">
      <div className="mb-4">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          <Package size={12} weight="fill" className="text-violet-500" />
          <span>Conversion Tools</span>
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">Booking Engine v2</h1>
        <p className="text-sm text-stone-500 mt-1 max-w-2xl">
          Paket inşası, upsell teklifleri ve bırakılan sepet kurtarma — direkt rezervasyon dönüşümünüzü artırın.
        </p>
      </div>

      <div className="flex gap-1 mb-4 border-b border-stone-200">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
                  data-testid={`be-tab-${t.id}`}
                  className={`px-4 py-2 text-xs font-medium inline-flex items-center gap-1.5 border-b-2 transition-colors ${tab === t.id ? "border-stone-900 text-stone-900" : "border-transparent text-stone-500 hover:text-stone-700"}`}>
            <t.icon size={13} /> {t.label}
          </button>
        ))}
        {tab !== "abandoned" && (
          <button onClick={() => setShowCreate(true)} data-testid="be-create-btn"
                  className="ml-auto px-3 py-1.5 text-xs text-white bg-stone-900 rounded-lg inline-flex items-center gap-1.5 mb-1">
            <Plus size={13} /> Ekle
          </button>
        )}
      </div>

      {loading && <div className="text-center py-12 text-stone-400 text-sm">Yükleniyor…</div>}

      {!loading && items.length === 0 && (
        <div className="text-center py-12 text-stone-400 text-sm" data-testid="be-empty">
          Henüz kayıt yok.
        </div>
      )}

      {!loading && items.length > 0 && (
        <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-stone-50 text-[11px] uppercase tracking-wider text-stone-500">
              <tr>
                {tab === "packages" && (<><th className="px-4 py-2 text-left">Paket</th><th className="px-4 py-2 text-left">İndirim</th><th className="px-4 py-2 text-left">Rezervasyon</th><th className="px-4 py-2 text-left">Durum</th></>)}
                {tab === "upsells" && (<><th className="px-4 py-2 text-left">Teklif</th><th className="px-4 py-2 text-left">Tetik</th><th className="px-4 py-2 text-left">Sunum/Kabul</th><th className="px-4 py-2 text-left">Durum</th></>)}
                {tab === "abandoned" && (<><th className="px-4 py-2 text-left">E-posta</th><th className="px-4 py-2 text-left">Adım</th><th className="px-4 py-2 text-left">Tarih</th><th className="px-4 py-2 text-right">Aksiyon</th></>)}
              </tr>
            </thead>
            <tbody>
              {items.map(it => (
                <tr key={it.id} className="border-t border-stone-100" data-testid={`be-row-${it.id}`}>
                  {tab === "packages" && (<><td className="px-4 py-2 font-medium text-stone-800">{it.name}</td><td className="px-4 py-2">{it.discount_percent}%</td><td className="px-4 py-2">{it.bookings_count || 0}</td><td className="px-4 py-2">{it.active ? <span className="text-emerald-600">Aktif</span> : <span className="text-stone-400">Pasif</span>}</td></>)}
                  {tab === "upsells" && (<><td className="px-4 py-2 font-medium text-stone-800">{it.name}</td><td className="px-4 py-2 text-xs">{it.target}</td><td className="px-4 py-2">{it.presented_count || 0}/{it.accepted_count || 0}</td><td className="px-4 py-2">{it.active ? <span className="text-emerald-600">Aktif</span> : <span className="text-stone-400">Pasif</span>}</td></>)}
                  {tab === "abandoned" && (<><td className="px-4 py-2">{it.guest_email || "—"}</td><td className="px-4 py-2 text-xs">{it.step}</td><td className="px-4 py-2 text-xs">{new Date(it.created_at).toLocaleString("tr-TR")}</td><td className="px-4 py-2 text-right">
                    {it.guest_email && !it.recovery_queued && (
                      <button onClick={() => recover(it.id)} data-testid={`be-recover-${it.id}`}
                              className="text-xs px-2 py-1 bg-rose-50 text-rose-700 rounded hover:bg-rose-100">
                        Kurtarma maili
                      </button>
                    )}
                    {it.recovery_queued && <span className="text-xs text-stone-400">Kuyrukta</span>}
                  </td></>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showCreate && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={() => setShowCreate(false)}>
          <div className="bg-white rounded-xl w-full max-w-md p-5" onClick={e => e.stopPropagation()} data-testid="be-create-modal">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-semibold">{tab === "packages" ? "Yeni Paket" : "Yeni Upsell"}</h3>
              <button onClick={() => setShowCreate(false)}><X size={16} /></button>
            </div>
            <div className="space-y-3">
              <input placeholder="Ad" value={form.name || ""} onChange={e => setForm({ ...form, name: e.target.value })}
                     className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg" data-testid="be-form-name" />
              <textarea placeholder="Açıklama" value={form.description || ""} onChange={e => setForm({ ...form, description: e.target.value })}
                        className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg" rows={2} />
              {tab === "packages" && (
                <input type="number" placeholder="İndirim %" value={form.discount_percent || ""}
                       onChange={e => setForm({ ...form, discount_percent: e.target.value })}
                       className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg" />
              )}
              {tab === "upsells" && (
                <select value={form.target || "booking_confirmation"} onChange={e => setForm({ ...form, target: e.target.value })}
                        className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg">
                  <option value="booking_confirmation">Rezervasyon Onayı</option>
                  <option value="pre_arrival">Varış Öncesi</option>
                  <option value="in_stay">Konaklama Sırasında</option>
                </select>
              )}
              <button onClick={create} disabled={!form.name} data-testid="be-form-save"
                      className="w-full py-2 text-sm text-white bg-stone-900 rounded-lg disabled:opacity-50">
                Kaydet
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
