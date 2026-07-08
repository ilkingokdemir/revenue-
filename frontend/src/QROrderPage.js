import { useState, useEffect } from "react";
import axios from "axios";
import { motion, AnimatePresence } from "framer-motion";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function QROrderPage({ propertyId, outletId }) {
  const [menu, setMenu] = useState(null);
  const [cart, setCart] = useState([]);
  const [activeCat, setActiveCat] = useState("all");
  const [search, setSearch] = useState("");
  const [guestName, setGuestName] = useState("");
  const [roomNum, setRoomNum] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const urlParams = new URLSearchParams(window.location.search);
  const tableNum = urlParams.get("table") || "";

  useEffect(() => {
    axios.get(`${API}/pos/public/menu/${propertyId}/${outletId}?table=${tableNum}`)
      .then(r => setMenu(r.data))
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false));
  }, [propertyId, outletId, tableNum]);

  const addToCart = (item) => {
    setCart(prev => {
      const ex = prev.find(c => c.id === item.id);
      if (ex) return prev.map(c => c.id === item.id ? { ...c, quantity: c.quantity + 1 } : c);
      return [...prev, { ...item, quantity: 1 }];
    });
  };
  const updateQty = (id, d) => setCart(prev => prev.map(c => c.id === id ? { ...c, quantity: Math.max(0, c.quantity + d) } : c).filter(c => c.quantity > 0));
  const cartTotal = cart.reduce((s, c) => s + c.price * c.quantity, 0);
  const cartVat = cart.reduce((s, c) => s + c.price * c.quantity * (c.vat_rate || 20) / 100, 0);

  const placeOrder = async () => {
    if (!cart.length) return;
    setSubmitting(true);
    try {
      const { data } = await axios.post(`${API}/pos/public/order`, {
        property_id: propertyId, outlet_id: outletId,
        outlet_name: menu?.outlet_name || "",
        table_number: tableNum, guest_name: guestName, room_number: roomNum,
        notes, covers: 1,
        items: cart.map(c => ({
          id: c.id, name: c.name, price: c.price, cost: c.cost || 0,
          quantity: c.quantity, vat_rate: c.vat_rate || 20, category: c.category,
        })),
      });
      setSubmitted(data);
    } catch (e) { alert("Failed to place order"); }
    setSubmitting(false);
  };

  if (loading) return (
    <div className="min-h-screen bg-stone-50 flex items-center justify-center">
      <div className="w-8 h-8 border-2 border-orange-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );

  if (loadError || !menu) return (
    <div className="min-h-screen bg-stone-50 flex items-center justify-center p-6" data-testid="qr-order-error">
      <div className="text-center max-w-sm">
        <div className="text-4xl mb-3">🍽️</div>
        <h1 className="text-lg font-bold text-stone-900 mb-1">Menü bulunamadı</h1>
        <p className="text-sm text-stone-500">Bu QR kod geçersiz veya outlet artık aktif değil. Lütfen personelden yeni bir QR kod isteyin.</p>
      </div>
    </div>
  );

  if (submitted) return (
    <div className="min-h-screen bg-gradient-to-b from-emerald-50 to-white flex items-center justify-center p-4">
      <motion.div initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="text-center max-w-sm">
        <div className="w-16 h-16 rounded-full bg-emerald-100 flex items-center justify-center mx-auto mb-4">
          <span className="text-3xl">✓</span>
        </div>
        <h1 className="text-xl font-bold text-stone-900 mb-2">Order Received!</h1>
        <p className="text-stone-600 text-sm">Order #{submitted.order_number}</p>
        <p className="text-lg font-bold text-emerald-700 my-2">£{submitted.total}</p>
        <p className="text-xs text-stone-400">Your order has been sent to the kitchen. A member of our team will bring it to you shortly.</p>
        <button onClick={() => { setSubmitted(null); setCart([]); }} className="mt-6 bg-stone-900 text-white px-6 py-2.5 rounded-xl text-sm font-medium">Order More</button>
      </motion.div>
    </div>
  );

  const filtered = (menu?.menu_items || []).filter(m => {
    if (activeCat !== "all" && m.category !== activeCat) return false;
    if (search && !m.name.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="min-h-screen bg-stone-50">
      {/* Header */}
      <div className="bg-white border-b border-stone-200 px-4 py-4 sticky top-0 z-10">
        <div className="max-w-lg mx-auto">
          <h1 className="text-lg font-bold text-stone-900">{menu?.hotel_name}</h1>
          <p className="text-xs text-stone-500">{menu?.outlet_name} {tableNum && `· Table ${tableNum}`}</p>
          {menu?.happy_hour_active && (
            <div className="mt-1 text-[10px] bg-amber-100 text-amber-800 px-2 py-0.5 rounded-full inline-block font-medium">
              🎉 {menu.happy_hour_name || "Happy Hour"} — Discounts Active!
            </div>
          )}
        </div>
      </div>

      <div className="max-w-lg mx-auto px-4 py-4">
        {/* Search */}
        <input type="text" value={search} onChange={e => setSearch(e.target.value)}
          placeholder="Search menu..." className="w-full border border-stone-200 rounded-xl px-4 py-2.5 text-sm mb-3 focus:outline-none focus:ring-2 focus:ring-orange-500" />

        {/* Categories */}
        <div className="flex gap-1.5 overflow-x-auto pb-2 mb-3 -mx-1 px-1">
          {["all", ...(menu?.categories || [])].map(cat => (
            <button key={cat} onClick={() => setActiveCat(cat)}
              className={`text-xs px-3 py-1.5 rounded-full whitespace-nowrap font-medium ${activeCat === cat ? "bg-stone-900 text-white" : "bg-white text-stone-600 border border-stone-200"}`}>
              {cat === "all" ? "All" : cat}
            </button>
          ))}
        </div>

        {/* Menu Items */}
        <div className="space-y-2 mb-32">
          {filtered.map(item => {
            const inCart = cart.find(c => c.id === item.id);
            return (
              <div key={item.id} className="bg-white rounded-xl border border-stone-200 p-3 flex items-center justify-between">
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-stone-800">{item.name}</div>
                  <div className="flex items-center gap-2 mt-0.5">
                    {item.happy_hour && <span className="text-[9px] bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded-full">Happy Hour</span>}
                    <span className="text-[10px] text-stone-400">{item.category}</span>
                    {item.allergens?.length > 0 && <span className="text-[9px] text-red-500">{item.allergens.join(", ")}</span>}
                  </div>
                </div>
                <div className="flex items-center gap-2 ml-2">
                  <div className="text-right">
                    <span className="text-sm font-bold text-stone-800">£{item.price.toFixed(2)}</span>
                    {item.happy_hour && item.original_price && (
                      <span className="text-[10px] text-stone-400 line-through block">£{item.original_price.toFixed(2)}</span>
                    )}
                  </div>
                  {inCart ? (
                    <div className="flex items-center gap-1">
                      <button onClick={() => updateQty(item.id, -1)} className="w-7 h-7 rounded-full bg-stone-100 flex items-center justify-center text-stone-600 text-sm font-bold">−</button>
                      <span className="text-sm font-bold w-5 text-center">{inCart.quantity}</span>
                      <button onClick={() => updateQty(item.id, 1)} className="w-7 h-7 rounded-full bg-orange-500 flex items-center justify-center text-white text-sm font-bold">+</button>
                    </div>
                  ) : (
                    <button onClick={() => addToCart(item)} className="w-8 h-8 rounded-full bg-orange-500 flex items-center justify-center text-white text-lg font-bold">+</button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Cart Footer */}
      {cart.length > 0 && (
        <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-stone-200 p-4 shadow-lg z-20">
          <div className="max-w-lg mx-auto">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-stone-500">{cart.reduce((s, c) => s + c.quantity, 0)} items</span>
              <span className="text-base font-bold text-stone-900">£{(cartTotal + cartVat).toFixed(2)}</span>
            </div>
            <div className="grid grid-cols-2 gap-2 mb-2">
              <input value={guestName} onChange={e => setGuestName(e.target.value)} placeholder="Your name" className="border border-stone-200 rounded-lg px-3 py-2 text-sm" />
              <input value={roomNum} onChange={e => setRoomNum(e.target.value)} placeholder="Room # (optional)" className="border border-stone-200 rounded-lg px-3 py-2 text-sm" />
            </div>
            <button onClick={placeOrder} disabled={submitting}
              className="w-full bg-orange-500 text-white py-3 rounded-xl text-sm font-bold hover:bg-orange-600 disabled:opacity-50">
              {submitting ? "Placing Order..." : `Place Order · £${(cartTotal + cartVat).toFixed(2)}`}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
