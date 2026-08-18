/**
 * BeachPosPanel — Elektra-style sunbed POS for beach hotels.
 *
 * Tabs:
 *  1. Şezlonglar (Sunbed grid with today's orders/spend)
 *  2. Sipariş Al (NEW order: pick sunbed + menu items)
 *  3. Bugünün Siparişleri (live order queue with deliver/cancel)
 *  4. Menü
 */
import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Umbrella, Plus, CheckCircle, X, Receipt } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/beach-pos`;

export default function BeachPosPanel({ propertyId }) {
  const [tab, setTab] = useState("sunbeds");
  const [sunbeds, setSunbeds] = useState([]);
  const [menu, setMenu] = useState([]);
  const [orders, setOrders] = useState([]);
  const [orderStats, setOrderStats] = useState({ zone_totals: {}, grand_total: 0 });
  const [cart, setCart] = useState([]);
  const [selectedSunbed, setSelectedSunbed] = useState("");
  const [showSeed, setShowSeed] = useState(false);
  const [seedForm, setSeedForm] = useState({ start: 1, end: 20, zone: "main", prefix: "" });

  const reload = useCallback(async () => {
    if (!propertyId) return;
    try {
      const s = await axios.get(`${API}/sunbeds/${propertyId}`, { withCredentials: true });
      setSunbeds(s.data.items || []);
      const m = await axios.get(`${API}/menu/${propertyId}`, { withCredentials: true });
      setMenu(m.data.items || []);
      const o = await axios.get(`${API}/orders/${propertyId}`, { withCredentials: true });
      setOrders(o.data.items || []);
      setOrderStats({ zone_totals: o.data.zone_totals || {}, grand_total: o.data.grand_total || 0 });
    } catch (e) { toast.error("Yüklenemedi"); }
  }, [propertyId]);

  useEffect(() => { reload(); }, [reload]);

  function addToCart(item) {
    const ex = cart.find(c => c.sku === item.sku);
    if (ex) {
      setCart(cart.map(c => c.sku === item.sku ? {...c, qty: c.qty+1} : c));
    } else {
      setCart([...cart, { sku: item.sku, name: item.name, price: item.price, qty: 1 }]);
    }
  }
  function removeFromCart(sku) {
    setCart(cart.filter(c => c.sku !== sku));
  }
  const cartTotal = cart.reduce((s, c) => s + c.price * c.qty, 0);

  async function submitOrder() {
    if (!selectedSunbed) { toast.error("Şezlong seçin"); return; }
    if (cart.length === 0) { toast.error("Sepet boş"); return; }
    try {
      await axios.post(`${API}/orders`,
        { property_id: propertyId, sunbed_number: selectedSunbed, items: cart },
        { withCredentials: true });
      toast.success("Sipariş alındı 🏖️");
      setCart([]); setSelectedSunbed("");
      reload();
    } catch (e) { toast.error(e?.response?.data?.detail || "Hata"); }
  }

  async function deliver(id) {
    try {
      await axios.post(`${API}/orders/${id}/deliver`, {}, { withCredentials: true });
      toast.success("Teslim edildi");
      reload();
    } catch (e) { toast.error("Hata"); }
  }

  async function cancel(id) {
    if (!window.confirm("Sipariş iptal edilsin mi?")) return;
    try {
      await axios.post(`${API}/orders/${id}/cancel`, { reason: "Müşteri vazgeçti" }, { withCredentials: true });
      reload();
    } catch (e) { toast.error("İptal başarısız"); }
  }

  async function doSeed() {
    try {
      const r = await axios.post(`${API}/sunbeds/bulk-seed/${propertyId}`, seedForm, { withCredentials: true });
      toast.success(`${r.data.created} şezlong eklendi`);
      setShowSeed(false);
      reload();
    } catch (e) { toast.error("Hata"); }
  }

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="beach-pos-panel">
      <div className="flex items-start justify-between gap-4 mb-5 flex-wrap">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">Beach POS (TR Sahil Oteli)</div>
          <h2 className="text-2xl font-semibold text-stone-900 inline-flex items-center gap-2">
            <Umbrella size={22} weight="fill" className="text-orange-500" /> Şezlong & Plaj Sipariş Sistemi
          </h2>
          <p className="text-sm text-stone-500 mt-1">
            Antalya/Bodrum sahil otelleri için Elektra-tarzı sunbed numarasıyla sipariş alma sistemi.
          </p>
        </div>
        <div className="text-right">
          <div className="text-[10px] uppercase tracking-wider text-stone-500">Bugünün Toplam Geliri</div>
          <div className="text-2xl font-semibold text-emerald-600">{orderStats.grand_total.toLocaleString("tr-TR")} TL</div>
        </div>
      </div>

      <div className="flex gap-1 border-b border-stone-200 mb-4">
        {[{k:"sunbeds",l:"Şezlonglar"},{k:"order",l:"Sipariş Al"},{k:"orders",l:`Bugünün Siparişleri (${orders.length})`},{k:"menu",l:`Menü (${menu.length})`}].map(t => (
          <button key={t.k} onClick={() => setTab(t.k)} data-testid={`beach-tab-${t.k}`}
                  className={`px-3 py-2 text-xs font-medium border-b-2 ${tab===t.k ? "border-orange-500 text-orange-700":"border-transparent text-stone-500"}`}>
            {t.l}
          </button>
        ))}
      </div>

      {tab === "sunbeds" && (
        <div>
          <div className="flex justify-end mb-3">
            <button onClick={() => setShowSeed(true)} data-testid="beach-seed-btn"
                    className="text-sm px-3 py-1.5 bg-stone-900 text-white rounded-lg inline-flex items-center gap-1.5">
              <Plus size={13} /> Şezlong Ekle (Toplu)
            </button>
          </div>
          <div className="grid grid-cols-4 md:grid-cols-8 lg:grid-cols-12 gap-2">
            {sunbeds.map(s => (
              <div key={s.id} data-testid={`sunbed-${s.sunbed_number}`}
                   className={`text-center p-2 rounded-lg border ${s.today_orders > 0 ? "bg-orange-50 border-orange-300" : "bg-stone-50 border-stone-200"}`}>
                <div className="text-lg">🏖️</div>
                <div className="text-sm font-bold">{s.sunbed_number}</div>
                <div className="text-[9px] text-stone-500">{s.zone}</div>
                {s.today_orders > 0 && (
                  <div className="text-[10px] text-orange-700 mt-0.5">
                    {s.today_orders}× · {s.today_spend.toFixed(0)}TL
                  </div>
                )}
              </div>
            ))}
            {sunbeds.length === 0 && (
              <div className="col-span-full text-center py-10 text-stone-400 text-sm">Şezlong yok. Toplu ekle butonuyla başlatın.</div>
            )}
          </div>
        </div>
      )}

      {tab === "order" && (
        <div className="grid lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 bg-white border border-stone-200 rounded-xl p-4">
            <h3 className="text-sm font-semibold mb-3">Menü</h3>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
              {menu.map(item => (
                <button key={item.id} onClick={() => addToCart(item)}
                        data-testid={`menu-${item.sku}`}
                        className="text-left p-3 border border-stone-200 rounded-lg hover:bg-orange-50 hover:border-orange-300">
                  <div className="text-[10px] text-stone-500 uppercase tracking-wider">{item.category}</div>
                  <div className="text-sm font-medium mt-0.5">{item.name}</div>
                  <div className="text-sm font-bold text-orange-700 mt-1">{item.price} TL</div>
                </button>
              ))}
            </div>
          </div>
          <div className="bg-white border border-stone-200 rounded-xl p-4 sticky top-4 h-fit">
            <h3 className="text-sm font-semibold mb-3 inline-flex items-center gap-1.5">
              <Receipt size={14} /> Sipariş Sepeti
            </h3>
            <label className="block mb-3">
              <span className="text-xs text-stone-700">Şezlong No</span>
              <select value={selectedSunbed} onChange={e => setSelectedSunbed(e.target.value)}
                      data-testid="beach-sunbed-select"
                      className="w-full px-3 py-1.5 text-sm border border-stone-300 rounded-lg mt-1">
                <option value="">Seçin</option>
                {sunbeds.map(s => <option key={s.id} value={s.sunbed_number}>{`#${s.sunbed_number} (${s.zone})`}</option>)}
              </select>
            </label>
            <div className="space-y-1.5 mb-3">
              {cart.length === 0 ? (
                <div className="text-center text-stone-400 text-xs py-4">Sepet boş</div>
              ) : cart.map(c => (
                <div key={c.sku} className="flex items-center justify-between text-xs">
                  <div>
                    <div className="font-medium">{c.name}</div>
                    <div className="text-stone-500">{c.qty} × {c.price} TL</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold">{(c.qty * c.price).toFixed(0)} TL</span>
                    <button onClick={() => removeFromCart(c.sku)} className="text-rose-500 hover:text-rose-700"><X size={12} /></button>
                  </div>
                </div>
              ))}
            </div>
            <div className="border-t border-stone-200 pt-3 mb-3 flex justify-between font-semibold">
              <span>Toplam</span>
              <span data-testid="beach-cart-total">{cartTotal.toFixed(2)} TL</span>
            </div>
            <button onClick={submitOrder} disabled={!selectedSunbed || cart.length===0}
                    data-testid="beach-submit-order"
                    className="w-full py-2 text-sm font-medium bg-orange-500 text-white rounded-lg hover:bg-orange-600 disabled:opacity-50">
              Siparişi Onayla
            </button>
          </div>
        </div>
      )}

      {tab === "orders" && (
        <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-stone-50 text-[11px] uppercase tracking-wider text-stone-500">
              <tr>
                <th className="px-4 py-2 text-left">Saat</th>
                <th className="px-4 py-2 text-left">Şezlong</th>
                <th className="px-4 py-2 text-left">Ürünler</th>
                <th className="px-4 py-2 text-right">Tutar</th>
                <th className="px-4 py-2 text-center">Durum</th>
                <th className="px-4 py-2 text-right">İşlem</th>
              </tr>
            </thead>
            <tbody>
              {orders.map(o => (
                <tr key={o.id} className="border-t border-stone-100" data-testid={`beach-order-${o.id}`}>
                  <td className="px-4 py-2 text-xs">{o.created_at?.slice(11,16)}</td>
                  <td className="px-4 py-2 font-bold">#{o.sunbed_number}</td>
                  <td className="px-4 py-2 text-xs">{o.items.map(i => `${i.qty}× ${i.name}`).join(", ")}</td>
                  <td className="px-4 py-2 text-right font-semibold">{o.total} TL</td>
                  <td className="px-4 py-2 text-center">
                    <span className={`text-[10px] px-2 py-0.5 rounded-full ${
                      o.status==="delivered" ? "bg-emerald-100 text-emerald-700" :
                      o.status==="cancelled" ? "bg-rose-100 text-rose-700" :
                      "bg-amber-100 text-amber-700"
                    }`}>{o.status}</span>
                  </td>
                  <td className="px-4 py-2 text-right">
                    {o.status === "new" && (
                      <div className="flex gap-1 justify-end">
                        <button onClick={() => deliver(o.id)} data-testid={`beach-deliver-${o.id}`}
                                className="text-xs p-1 text-emerald-600 hover:bg-emerald-50 rounded">
                          <CheckCircle size={14} />
                        </button>
                        <button onClick={() => cancel(o.id)} data-testid={`beach-cancel-${o.id}`}
                                className="text-xs p-1 text-rose-600 hover:bg-rose-50 rounded">
                          <X size={14} />
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
              {orders.length === 0 && (
                <tr><td colSpan={6} className="px-4 py-10 text-center text-stone-400 text-xs">Bugün henüz sipariş yok.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {tab === "menu" && (
        <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-stone-50 text-[11px] uppercase tracking-wider text-stone-500">
              <tr>
                <th className="px-4 py-2 text-left">Kategori</th>
                <th className="px-4 py-2 text-left">Ad</th>
                <th className="px-4 py-2 text-left">SKU</th>
                <th className="px-4 py-2 text-right">Fiyat</th>
              </tr>
            </thead>
            <tbody>
              {menu.map(m => (
                <tr key={m.id} className="border-t border-stone-100">
                  <td className="px-4 py-2 text-xs"><span className="bg-orange-100 text-orange-800 px-2 py-0.5 rounded">{m.category}</span></td>
                  <td className="px-4 py-2 font-medium">{m.name}</td>
                  <td className="px-4 py-2 font-mono text-xs">{m.sku}</td>
                  <td className="px-4 py-2 text-right font-semibold">{m.price} TL</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showSeed && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl w-full max-w-sm shadow-xl">
            <div className="flex items-center justify-between p-4 border-b border-stone-200">
              <h3 className="text-base font-semibold">Toplu Şezlong Ekle</h3>
              <button onClick={() => setShowSeed(false)} className="text-stone-400">✕</button>
            </div>
            <div className="p-4 space-y-2">
              <Inp label="Bölge" v={seedForm.zone} onChange={v => setSeedForm({...seedForm, zone:v})} />
              <Inp label="Önek (örn. A)" v={seedForm.prefix} onChange={v => setSeedForm({...seedForm, prefix:v})} />
              <Inp label="Başlangıç" v={seedForm.start} type="number" onChange={v => setSeedForm({...seedForm, start:parseInt(v)||1})} />
              <Inp label="Bitiş" v={seedForm.end} type="number" onChange={v => setSeedForm({...seedForm, end:parseInt(v)||20})} />
            </div>
            <div className="p-4 border-t border-stone-200 flex justify-end gap-2">
              <button onClick={() => setShowSeed(false)} className="text-xs px-3 py-1.5 border border-stone-300 rounded-lg">İptal</button>
              <button onClick={doSeed} data-testid="beach-seed-save" className="text-xs px-3 py-1.5 bg-stone-900 text-white rounded-lg">Oluştur</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Inp({ label, v, onChange, type="text" }) {
  return (
    <label className="block">
      <span className="text-xs text-stone-700">{label}</span>
      <input value={v||""} type={type} onChange={e => onChange(e.target.value)}
             className="w-full px-3 py-1.5 text-sm border border-stone-300 rounded-lg mt-1" />
    </label>
  );
}
