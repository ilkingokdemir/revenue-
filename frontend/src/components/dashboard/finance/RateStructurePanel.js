import { useState, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Tags, RefreshCw, Plus, X, Link2, Ticket, Percent, Globe,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const EMPTY_PRODUCT = {
  property_id: "default", name: "", code: "", kind: "flex",
  meal_plan: "room_only", cancellation_policy: "free_24h", cancellation_fee_pct: 0,
  min_los: 1, max_los: 30, min_advance_days: 0, max_advance_days: 365,
  inclusions: [], active: true, notes: "",
};
const EMPTY_DERIVED = { property_id: "default", name: "", parent_product_id: "", basis: "percent", adjustment: -10, active: true };
const EMPTY_CHANNEL = {
  property_id: "default", channel: "booking_com", external_room_code: "", external_rate_code: "",
  room_type_id: "", rate_product_id: "", active: true, notes: "",
};
const EMPTY_PROMO = {
  property_id: "default", code: "", kind: "percent", amount: 10,
  valid_from: "", valid_to: "", max_uses: 0, min_nights: 1, active: true,
};

const KIND_LABEL = {
  flex: "Flexible (BAR)", non_refundable: "Non-Refundable", advance_purchase: "Advance Purchase",
  corporate: "Corporate", package: "Package",
};

export const RateStructurePanel = ({ user, propertyId }) => {
  const [tab, setTab] = useState("products");
  const [products, setProducts] = useState([]);
  const [derived, setDerived] = useState([]);
  const [channelCodes, setChannelCodes] = useState([]);
  const [promos, setPromos] = useState([]);
  const [roomTypes, setRoomTypes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [productForm, setProductForm] = useState(null);
  const [derivedForm, setDerivedForm] = useState(null);
  const [channelForm, setChannelForm] = useState(null);
  const [promoForm, setPromoForm] = useState(null);

  const loadAll = async () => {
    setLoading(true);
    try {
      const pid = propertyId && propertyId !== "all" ? propertyId : "";
      const qs = pid ? `?property_id=${pid}` : "";
      const [p, d, c, pr, rt] = await Promise.all([
        axios.get(`${API}/rate-structure/products${qs}`),
        axios.get(`${API}/rate-structure/derived${qs}`),
        axios.get(`${API}/rate-structure/channel-codes${qs}`),
        axios.get(`${API}/rate-structure/promo-codes${qs}`),
        axios.get(`${API}/room-types${qs}`).catch(() => ({ data: [] })),
      ]);
      setProducts(p.data || []);
      setDerived(d.data || []);
      setChannelCodes(c.data || []);
      setPromos(pr.data || []);
      setRoomTypes(rt.data || []);
    } catch (e) { toast.error("Failed to load rate structure"); }
    finally { setLoading(false); }
  };
  useEffect(() => { loadAll(); /* eslint-disable-next-line */ }, [propertyId]);

  // ---- Product ----
  const saveProduct = async () => {
    if (!productForm.name || !productForm.code) return toast.error("Name and code required");
    try {
      if (productForm.id) await axios.put(`${API}/rate-structure/products/${productForm.id}`, productForm);
      else await axios.post(`${API}/rate-structure/products`, productForm);
      toast.success("Saved");
      setProductForm(null); loadAll();
    } catch (e) { toast.error(e?.response?.data?.detail || "Save failed"); }
  };
  const deleteProduct = async (id) => {
    if (!window.confirm("Delete this rate product and its derived rates?")) return;
    try { await axios.delete(`${API}/rate-structure/products/${id}`); toast.success("Deleted"); loadAll(); }
    catch (e) { toast.error("Failed"); }
  };

  // ---- Derived ----
  const saveDerived = async () => {
    if (!derivedForm.name || !derivedForm.parent_product_id) return toast.error("Name and parent required");
    try {
      await axios.post(`${API}/rate-structure/derived`, derivedForm);
      toast.success("Derived rate created");
      setDerivedForm(null); loadAll();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };
  const deleteDerived = async (id) => {
    try { await axios.delete(`${API}/rate-structure/derived/${id}`); loadAll(); }
    catch (e) { toast.error("Failed"); }
  };

  // ---- Channel ----
  const saveChannel = async () => {
    if (!channelForm.external_room_code || !channelForm.room_type_id) return toast.error("External code and room type required");
    try {
      if (channelForm.id) await axios.put(`${API}/rate-structure/channel-codes/${channelForm.id}`, channelForm);
      else await axios.post(`${API}/rate-structure/channel-codes`, channelForm);
      toast.success("Mapping saved");
      setChannelForm(null); loadAll();
    } catch (e) { toast.error("Failed"); }
  };
  const deleteChannel = async (id) => {
    try { await axios.delete(`${API}/rate-structure/channel-codes/${id}`); loadAll(); }
    catch (e) { toast.error("Failed"); }
  };

  // ---- Promo ----
  const savePromo = async () => {
    if (!promoForm.code) return toast.error("Code required");
    try {
      if (promoForm.id) await axios.put(`${API}/rate-structure/promo-codes/${promoForm.id}`, promoForm);
      else await axios.post(`${API}/rate-structure/promo-codes`, promoForm);
      toast.success("Saved");
      setPromoForm(null); loadAll();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };
  const deletePromo = async (id) => {
    try { await axios.delete(`${API}/rate-structure/promo-codes/${id}`); loadAll(); }
    catch (e) { toast.error("Failed"); }
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto" data-testid="rate-structure-panel">
      <div className="bg-gradient-to-br from-fuchsia-50 via-pink-50 to-white border border-fuchsia-100 rounded-2xl p-6">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-wider text-fuchsia-700">
              <Tags className="w-4 h-4" />Rate Structure · Product Catalogue
            </div>
            <h1 className="text-3xl font-black text-stone-900 mt-1">Rate Plans &amp; OTA Mapping</h1>
            <p className="text-sm text-stone-600 mt-1">
              Rate products (BAR, Non-Refundable, Packages…), derived rates, channel codes, promo codes.
            </p>
          </div>
          <button onClick={loadAll} className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-stone-200 hover:border-stone-300 rounded-lg text-xs font-semibold">
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />Refresh
          </button>
        </div>
      </div>

      <div className="flex gap-2 border-b border-stone-200 overflow-x-auto">
        {[
          { id: "products", label: "Rate Products", icon: Tags, n: products.length },
          { id: "derived", label: "Derived Rates", icon: Link2, n: derived.length },
          { id: "channels", label: "OTA Mapping", icon: Globe, n: channelCodes.length },
          { id: "promos", label: "Promo Codes", icon: Ticket, n: promos.length },
        ].map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)} data-testid={`rs-tab-${t.id}`}
            className={`flex items-center gap-1.5 px-4 py-2 text-sm font-semibold border-b-2 -mb-px whitespace-nowrap ${
              tab === t.id ? "border-fuchsia-500 text-stone-900" : "border-transparent text-stone-400 hover:text-stone-700"
            }`}>
            <t.icon className="w-3.5 h-3.5" />{t.label}
            <span className="ml-1 px-1.5 py-0.5 rounded bg-stone-100 text-[10px] font-bold">{t.n}</span>
          </button>
        ))}
      </div>

      {tab === "products" && (
        <div className="space-y-3">
          <div className="flex justify-end">
            <button onClick={() => setProductForm({ ...EMPTY_PRODUCT, property_id: propertyId || "default" })}
              data-testid="rs-new-product"
              className="flex items-center gap-1.5 px-4 py-2 bg-fuchsia-600 hover:bg-fuchsia-700 text-white rounded-lg text-sm font-semibold">
              <Plus className="w-4 h-4" />New Product
            </button>
          </div>
          <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-stone-50 text-[10px] uppercase text-stone-500">
                <tr>
                  <th className="p-3 text-left">Code</th>
                  <th className="p-3 text-left">Name</th>
                  <th className="p-3 text-left">Kind</th>
                  <th className="p-3 text-left">Meal Plan</th>
                  <th className="p-3 text-left">Cancellation</th>
                  <th className="p-3 text-center">LOS</th>
                  <th className="p-3 text-center">Active</th>
                  <th className="p-3"></th>
                </tr>
              </thead>
              <tbody>
                {products.length === 0 && <tr><td colSpan={8} className="p-8 text-center text-stone-400">No rate products yet. Create your first.</td></tr>}
                {products.map(p => (
                  <tr key={p.id} className="border-t border-stone-100 hover:bg-stone-50" data-testid={`rs-product-${p.code}`}>
                    <td className="p-3 font-mono font-bold text-fuchsia-700">{p.code}</td>
                    <td className="p-3 font-semibold text-stone-800">{p.name}</td>
                    <td className="p-3 text-xs text-stone-500">{KIND_LABEL[p.kind] || p.kind}</td>
                    <td className="p-3 text-xs text-stone-500">{(p.meal_plan || "").replace(/_/g, " ")}</td>
                    <td className="p-3 text-xs text-stone-500">{p.cancellation_policy?.replace(/_/g, " ")}</td>
                    <td className="p-3 text-xs text-center text-stone-500">{p.min_los}-{p.max_los}</td>
                    <td className="p-3 text-center">
                      <span className={`inline-block px-2 py-0.5 text-[10px] font-bold rounded-full ${p.active ? "bg-emerald-100 text-emerald-700" : "bg-stone-100 text-stone-500"}`}>
                        {p.active ? "ON" : "OFF"}
                      </span>
                    </td>
                    <td className="p-3 text-center">
                      <button onClick={() => setProductForm({ ...p })} className="text-xs text-sky-600 hover:underline mr-2">Edit</button>
                      <button onClick={() => deleteProduct(p.id)} className="text-xs text-rose-600 hover:underline">Delete</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "derived" && (
        <div className="space-y-3">
          <div className="flex justify-end">
            <button onClick={() => setDerivedForm({ ...EMPTY_DERIVED, property_id: propertyId || "default" })}
              data-testid="rs-new-derived"
              disabled={products.length === 0}
              className="flex items-center gap-1.5 px-4 py-2 bg-fuchsia-600 hover:bg-fuchsia-700 disabled:bg-stone-300 text-white rounded-lg text-sm font-semibold">
              <Plus className="w-4 h-4" />New Derived Rate
            </button>
          </div>
          <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-stone-50 text-[10px] uppercase text-stone-500">
                <tr>
                  <th className="p-3 text-left">Name</th>
                  <th className="p-3 text-left">Parent</th>
                  <th className="p-3 text-center">Basis</th>
                  <th className="p-3 text-right">Adjustment</th>
                  <th className="p-3 text-right">E.g. from £100</th>
                  <th className="p-3"></th>
                </tr>
              </thead>
              <tbody>
                {derived.length === 0 && <tr><td colSpan={6} className="p-8 text-center text-stone-400">No derived rates. Create a rate product first.</td></tr>}
                {derived.map(d => {
                  const example = d.basis === "percent" ? 100 * (1 + d.adjustment / 100) : 100 + d.adjustment;
                  return (
                    <tr key={d.id} className="border-t border-stone-100 hover:bg-stone-50">
                      <td className="p-3 font-semibold">{d.name}</td>
                      <td className="p-3 text-xs"><span className="font-mono text-fuchsia-700">{d.parent_code}</span> {d.parent_name}</td>
                      <td className="p-3 text-center text-xs">{d.basis}</td>
                      <td className="p-3 text-right font-mono">{d.basis === "percent" ? `${d.adjustment > 0 ? "+" : ""}${d.adjustment}%` : `£${d.adjustment}`}</td>
                      <td className="p-3 text-right font-bold text-fuchsia-700">£{example.toFixed(2)}</td>
                      <td className="p-3 text-center">
                        <button onClick={() => deleteDerived(d.id)} className="text-xs text-rose-600 hover:underline">Delete</button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "channels" && (
        <div className="space-y-3">
          <div className="flex justify-end">
            <button onClick={() => setChannelForm({ ...EMPTY_CHANNEL, property_id: propertyId || "default" })}
              data-testid="rs-new-channel"
              className="flex items-center gap-1.5 px-4 py-2 bg-fuchsia-600 hover:bg-fuchsia-700 text-white rounded-lg text-sm font-semibold">
              <Plus className="w-4 h-4" />New Mapping
            </button>
          </div>
          <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-stone-50 text-[10px] uppercase text-stone-500">
                <tr>
                  <th className="p-3 text-left">Channel</th>
                  <th className="p-3 text-left">External Room Code</th>
                  <th className="p-3 text-left">External Rate Code</th>
                  <th className="p-3 text-left">→ Our Room</th>
                  <th className="p-3 text-left">→ Our Rate Product</th>
                  <th className="p-3"></th>
                </tr>
              </thead>
              <tbody>
                {channelCodes.length === 0 && <tr><td colSpan={6} className="p-8 text-center text-stone-400">No channel mappings yet.</td></tr>}
                {channelCodes.map(c => (
                  <tr key={c.id} className="border-t border-stone-100 hover:bg-stone-50">
                    <td className="p-3"><span className="inline-block px-2 py-0.5 rounded bg-indigo-100 text-indigo-700 text-[10px] font-bold uppercase">{c.channel.replace(/_/g, ".")}</span></td>
                    <td className="p-3 font-mono text-xs">{c.external_room_code}</td>
                    <td className="p-3 font-mono text-xs text-stone-500">{c.external_rate_code || "—"}</td>
                    <td className="p-3 text-stone-800">{c.room_type_name}</td>
                    <td className="p-3 text-xs text-stone-500">{c.rate_product_name || "—"}</td>
                    <td className="p-3 text-center">
                      <button onClick={() => setChannelForm({ ...c })} className="text-xs text-sky-600 hover:underline mr-2">Edit</button>
                      <button onClick={() => deleteChannel(c.id)} className="text-xs text-rose-600 hover:underline">Delete</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "promos" && (
        <div className="space-y-3">
          <div className="flex justify-end">
            <button onClick={() => setPromoForm({ ...EMPTY_PROMO, property_id: propertyId || "default" })}
              data-testid="rs-new-promo"
              className="flex items-center gap-1.5 px-4 py-2 bg-fuchsia-600 hover:bg-fuchsia-700 text-white rounded-lg text-sm font-semibold">
              <Plus className="w-4 h-4" />New Promo
            </button>
          </div>
          <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-stone-50 text-[10px] uppercase text-stone-500">
                <tr>
                  <th className="p-3 text-left">Code</th>
                  <th className="p-3 text-left">Discount</th>
                  <th className="p-3 text-left">Valid Window</th>
                  <th className="p-3 text-right">Min Nights</th>
                  <th className="p-3 text-right">Uses</th>
                  <th className="p-3 text-center">Active</th>
                  <th className="p-3"></th>
                </tr>
              </thead>
              <tbody>
                {promos.length === 0 && <tr><td colSpan={7} className="p-8 text-center text-stone-400">No promo codes yet.</td></tr>}
                {promos.map(p => (
                  <tr key={p.id} className="border-t border-stone-100 hover:bg-stone-50">
                    <td className="p-3 font-mono font-bold text-fuchsia-700">{p.code}</td>
                    <td className="p-3">
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-amber-100 text-amber-700 text-xs font-bold">
                        <Percent className="w-3 h-3" />{p.amount}{p.kind === "percent" ? "%" : "£"}
                      </span>
                    </td>
                    <td className="p-3 text-xs text-stone-500">{p.valid_from || "—"} → {p.valid_to || "—"}</td>
                    <td className="p-3 text-right">{p.min_nights}</td>
                    <td className="p-3 text-right">{p.used}{p.max_uses > 0 ? ` / ${p.max_uses}` : ""}</td>
                    <td className="p-3 text-center">
                      <span className={`inline-block px-2 py-0.5 text-[10px] font-bold rounded-full ${p.active ? "bg-emerald-100 text-emerald-700" : "bg-stone-100 text-stone-500"}`}>
                        {p.active ? "ON" : "OFF"}
                      </span>
                    </td>
                    <td className="p-3 text-center">
                      <button onClick={() => setPromoForm({ ...p })} className="text-xs text-sky-600 hover:underline mr-2">Edit</button>
                      <button onClick={() => deletePromo(p.id)} className="text-xs text-rose-600 hover:underline">Delete</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Modals */}
      {productForm && (
        <Modal title={productForm.id ? "Edit Rate Product" : "New Rate Product"} onClose={() => setProductForm(null)}>
          <div className="grid grid-cols-2 gap-3">
            <F label="Name *"><input value={productForm.name} onChange={e => setProductForm({ ...productForm, name: e.target.value })} data-testid="rs-form-prod-name" className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" /></F>
            <F label="Code *"><input value={productForm.code} onChange={e => setProductForm({ ...productForm, code: e.target.value.toUpperCase() })} data-testid="rs-form-prod-code" maxLength={8} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm font-mono uppercase" /></F>
            <F label="Kind">
              <select value={productForm.kind} onChange={e => setProductForm({ ...productForm, kind: e.target.value })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm">
                {Object.entries(KIND_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </F>
            <F label="Meal Plan">
              <select value={productForm.meal_plan} onChange={e => setProductForm({ ...productForm, meal_plan: e.target.value })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm">
                <option value="room_only">Room only</option>
                <option value="bed_breakfast">Bed & Breakfast</option>
                <option value="half_board">Half Board</option>
                <option value="full_board">Full Board</option>
                <option value="all_inclusive">All Inclusive</option>
              </select>
            </F>
            <F label="Cancellation">
              <select value={productForm.cancellation_policy} onChange={e => setProductForm({ ...productForm, cancellation_policy: e.target.value })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm">
                <option value="free_24h">Free up to 24h before</option>
                <option value="free_48h">Free up to 48h before</option>
                <option value="free_72h">Free up to 72h before</option>
                <option value="non_refundable">Non-refundable</option>
                <option value="custom">Custom</option>
              </select>
            </F>
            <F label="Cancel fee %"><input type="number" value={productForm.cancellation_fee_pct} onChange={e => setProductForm({ ...productForm, cancellation_fee_pct: parseFloat(e.target.value) || 0 })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" /></F>
            <F label="Min LOS"><input type="number" value={productForm.min_los} onChange={e => setProductForm({ ...productForm, min_los: parseInt(e.target.value) || 1 })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" /></F>
            <F label="Max LOS"><input type="number" value={productForm.max_los} onChange={e => setProductForm({ ...productForm, max_los: parseInt(e.target.value) || 30 })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" /></F>
            <F label="Min Advance Days"><input type="number" value={productForm.min_advance_days} onChange={e => setProductForm({ ...productForm, min_advance_days: parseInt(e.target.value) || 0 })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" /></F>
            <F label="Max Advance Days"><input type="number" value={productForm.max_advance_days} onChange={e => setProductForm({ ...productForm, max_advance_days: parseInt(e.target.value) || 365 })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" /></F>
            <div className="col-span-2">
              <F label="Notes"><textarea rows={2} value={productForm.notes} onChange={e => setProductForm({ ...productForm, notes: e.target.value })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" /></F>
            </div>
            <label className="col-span-2 flex items-center gap-2 text-sm">
              <input type="checkbox" checked={productForm.active} onChange={e => setProductForm({ ...productForm, active: e.target.checked })} /> Active
            </label>
          </div>
          <SaveBar onCancel={() => setProductForm(null)} onSave={saveProduct} testId="rs-save-product" />
        </Modal>
      )}

      {derivedForm && (
        <Modal title="New Derived Rate" onClose={() => setDerivedForm(null)}>
          <div className="grid grid-cols-2 gap-3">
            <F label="Name *"><input value={derivedForm.name} onChange={e => setDerivedForm({ ...derivedForm, name: e.target.value })} data-testid="rs-form-der-name" className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" placeholder="BAR -10% Mobile" /></F>
            <F label="Parent Product *">
              <select value={derivedForm.parent_product_id} onChange={e => setDerivedForm({ ...derivedForm, parent_product_id: e.target.value })} data-testid="rs-form-der-parent" className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm">
                <option value="">— Select —</option>
                {products.map(p => <option key={p.id} value={p.id}>{`${p.code} · ${p.name}`}</option>)}
              </select>
            </F>
            <F label="Basis">
              <select value={derivedForm.basis} onChange={e => setDerivedForm({ ...derivedForm, basis: e.target.value })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm">
                <option value="percent">Percent (%)</option>
                <option value="flat">Flat (£)</option>
              </select>
            </F>
            <F label={`Adjustment (${derivedForm.basis === "percent" ? "%" : "£"})`}>
              <input type="number" step="0.01" value={derivedForm.adjustment} onChange={e => setDerivedForm({ ...derivedForm, adjustment: parseFloat(e.target.value) || 0 })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" />
            </F>
          </div>
          <SaveBar onCancel={() => setDerivedForm(null)} onSave={saveDerived} testId="rs-save-derived" />
        </Modal>
      )}

      {channelForm && (
        <Modal title={channelForm.id ? "Edit Channel Mapping" : "New Channel Mapping"} onClose={() => setChannelForm(null)}>
          <div className="grid grid-cols-2 gap-3">
            <F label="Channel">
              <select value={channelForm.channel} onChange={e => setChannelForm({ ...channelForm, channel: e.target.value })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm">
                <option value="booking_com">Booking.com</option>
                <option value="expedia">Expedia</option>
                <option value="airbnb">Airbnb</option>
                <option value="hotels_com">Hotels.com</option>
                <option value="agoda">Agoda</option>
              </select>
            </F>
            <F label="External Room Code *"><input value={channelForm.external_room_code} onChange={e => setChannelForm({ ...channelForm, external_room_code: e.target.value })} data-testid="rs-form-ch-roomcode" className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm font-mono" /></F>
            <F label="External Rate Code"><input value={channelForm.external_rate_code} onChange={e => setChannelForm({ ...channelForm, external_rate_code: e.target.value })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm font-mono" /></F>
            <F label="→ Our Room Type *">
              <select value={channelForm.room_type_id} onChange={e => setChannelForm({ ...channelForm, room_type_id: e.target.value })} data-testid="rs-form-ch-room" className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm">
                <option value="">— Select —</option>
                {roomTypes.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
              </select>
            </F>
            <F label="→ Our Rate Product">
              <select value={channelForm.rate_product_id} onChange={e => setChannelForm({ ...channelForm, rate_product_id: e.target.value })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm">
                <option value="">— Optional —</option>
                {products.map(p => <option key={p.id} value={p.id}>{`${p.code} · ${p.name}`}</option>)}
              </select>
            </F>
            <div className="col-span-2">
              <F label="Notes"><input value={channelForm.notes} onChange={e => setChannelForm({ ...channelForm, notes: e.target.value })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" /></F>
            </div>
          </div>
          <SaveBar onCancel={() => setChannelForm(null)} onSave={saveChannel} testId="rs-save-channel" />
        </Modal>
      )}

      {promoForm && (
        <Modal title={promoForm.id ? "Edit Promo Code" : "New Promo Code"} onClose={() => setPromoForm(null)}>
          <div className="grid grid-cols-2 gap-3">
            <F label="Code *"><input value={promoForm.code} onChange={e => setPromoForm({ ...promoForm, code: e.target.value.toUpperCase() })} data-testid="rs-form-promo-code" maxLength={20} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm font-mono uppercase" /></F>
            <F label="Kind">
              <select value={promoForm.kind} onChange={e => setPromoForm({ ...promoForm, kind: e.target.value })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm">
                <option value="percent">Percent (%)</option>
                <option value="flat">Flat (£)</option>
              </select>
            </F>
            <F label={`Amount (${promoForm.kind === "percent" ? "%" : "£"}) *`}><input type="number" value={promoForm.amount} onChange={e => setPromoForm({ ...promoForm, amount: parseFloat(e.target.value) || 0 })} data-testid="rs-form-promo-amount" className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" /></F>
            <F label="Min Nights"><input type="number" value={promoForm.min_nights} onChange={e => setPromoForm({ ...promoForm, min_nights: parseInt(e.target.value) || 1 })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" /></F>
            <F label="Valid From"><input type="date" value={promoForm.valid_from || ""} onChange={e => setPromoForm({ ...promoForm, valid_from: e.target.value })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" /></F>
            <F label="Valid To"><input type="date" value={promoForm.valid_to || ""} onChange={e => setPromoForm({ ...promoForm, valid_to: e.target.value })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" /></F>
            <F label="Max Uses (0 = unlimited)"><input type="number" value={promoForm.max_uses} onChange={e => setPromoForm({ ...promoForm, max_uses: parseInt(e.target.value) || 0 })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" /></F>
            <label className="col-span-2 flex items-center gap-2 text-sm">
              <input type="checkbox" checked={promoForm.active} onChange={e => setPromoForm({ ...promoForm, active: e.target.checked })} /> Active
            </label>
          </div>
          <SaveBar onCancel={() => setPromoForm(null)} onSave={savePromo} testId="rs-save-promo" />
        </Modal>
      )}
    </div>
  );
};

const F = ({ label, children }) => (
  <div>
    <label className="block text-[10px] font-bold uppercase text-stone-500 mb-1">{label}</label>
    {children}
  </div>
);

const SaveBar = ({ onCancel, onSave, testId }) => (
  <div className="flex justify-end gap-2 mt-4">
    <button onClick={onCancel} className="px-4 py-2 text-sm">Cancel</button>
    <button onClick={onSave} data-testid={testId} className="px-4 py-2 bg-fuchsia-600 hover:bg-fuchsia-700 text-white rounded-lg text-sm font-semibold">Save</button>
  </div>
);

const Modal = ({ title, onClose, children }) => (
  <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" onClick={onClose}>
    <div className="bg-white rounded-2xl p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-bold text-stone-900">{title}</h2>
        <button onClick={onClose} className="p-1 hover:bg-stone-100 rounded-lg"><X className="w-4 h-4 text-stone-500" /></button>
      </div>
      {children}
    </div>
  </div>
);

// Shared input styling handled inline above.
export default RateStructurePanel;
