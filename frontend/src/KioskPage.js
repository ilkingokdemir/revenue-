import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { motion, AnimatePresence } from "framer-motion";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const CAT_COLORS = {
  Starters: "#f59e0b", Mains: "#ef4444", Desserts: "#ec4899", Wine: "#8b5cf6",
  Beer: "#d97706", Cocktails: "#7c3aed", "Soft Drinks": "#3b82f6", "Hot Drinks": "#ea580c",
  Spa: "#14b8a6", "Room Service": "#6366f1",
};

export default function KioskPage({ propertyId, outletId }) {
  const [menu, setMenu] = useState(null);
  const [cart, setCart] = useState([]);
  const [activeCat, setActiveCat] = useState("all");
  const [loading, setLoading] = useState(true);
  const [paying, setPaying] = useState(false);
  const [completed, setCompleted] = useState(null);
  const [guestName, setGuestName] = useState("");
  const [idle, setIdle] = useState(true);

  useEffect(() => {
    axios.get(`${API}/pos/public/menu/${propertyId}/${outletId}`)
      .then(r => setMenu(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [propertyId, outletId]);

  // Auto-reset to idle after 60s of no interaction on completed screen
  useEffect(() => {
    if (completed) {
      const timer = setTimeout(() => { setCompleted(null); setCart([]); setIdle(true); setGuestName(""); }, 15000);
      return () => clearTimeout(timer);
    }
  }, [completed]);

  const addToCart = (item) => {
    setIdle(false);
    setCart(prev => {
      const ex = prev.find(c => c.id === item.id);
      if (ex) return prev.map(c => c.id === item.id ? { ...c, quantity: c.quantity + 1 } : c);
      return [...prev, { ...item, quantity: 1 }];
    });
  };
  const updateQty = (id, d) => setCart(prev => prev.map(c => c.id === id ? { ...c, quantity: Math.max(0, c.quantity + d) } : c).filter(c => c.quantity > 0));
  const cartTotal = cart.reduce((s, c) => s + c.price * c.quantity, 0);
  const cartVat = cart.reduce((s, c) => s + c.price * c.quantity * (c.vat_rate || 20) / 100, 0);
  const grandTotal = cartTotal + cartVat;

  const placeOrder = async () => {
    if (!cart.length) return;
    setPaying(true);
    try {
      const { data } = await axios.post(`${API}/pos/kiosk/order`, {
        property_id: propertyId, outlet_id: outletId,
        outlet_name: menu?.outlet_name || "",
        guest_name: guestName || "Kiosk Guest",
        payment_method: "card",
        items: cart.map(c => ({
          id: c.id, name: c.name, price: c.price, cost: c.cost || 0,
          quantity: c.quantity, vat_rate: c.vat_rate || 20, category: c.category,
        })),
      });
      setCompleted(data);
      setCart([]);
    } catch (e) { alert("Order failed. Please try again."); }
    setPaying(false);
  };

  if (loading) return (
    <div className="min-h-screen bg-stone-900 flex items-center justify-center">
      <div className="w-12 h-12 border-3 border-orange-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );

  // Idle / Welcome Screen
  if (idle && !cart.length) return (
    <div className="min-h-screen bg-gradient-to-b from-stone-900 to-stone-800 flex items-center justify-center cursor-pointer" onClick={() => setIdle(false)}>
      <motion.div initial={{ scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="text-center">
        <div className="w-24 h-24 rounded-3xl bg-orange-500 flex items-center justify-center mx-auto mb-8">
          <span className="text-5xl">🍽</span>
        </div>
        <h1 className="text-4xl font-black text-white mb-3">{menu?.hotel_name}</h1>
        <p className="text-xl text-stone-400 mb-2">{menu?.outlet_name}</p>
        <motion.p animate={{ opacity: [0.5, 1, 0.5] }} transition={{ repeat: Infinity, duration: 2 }}
          className="text-lg text-orange-400 font-medium mt-8">Tap anywhere to start ordering</motion.p>
      </motion.div>
    </div>
  );

  // Completed Screen
  if (completed) return (
    <div className="min-h-screen bg-gradient-to-b from-emerald-900 to-emerald-800 flex items-center justify-center">
      <motion.div initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="text-center">
        <div className="w-24 h-24 rounded-full bg-emerald-500 flex items-center justify-center mx-auto mb-6">
          <span className="text-5xl text-white">✓</span>
        </div>
        <h1 className="text-3xl font-black text-white mb-3">Order Placed!</h1>
        <p className="text-5xl font-black text-emerald-300 mb-2">#{completed.order_number}</p>
        <p className="text-xl text-emerald-200">£{completed.total}</p>
        <p className="text-stone-400 mt-4 text-sm">Please collect your order when called.</p>
        <p className="text-stone-500 mt-8 text-xs">Screen will reset automatically...</p>
      </motion.div>
    </div>
  );

  const filtered = (menu?.menu_items || []).filter(m => {
    if (activeCat !== "all" && m.category !== activeCat) return false;
    return true;
  });

  return (
    <div className="min-h-screen bg-stone-900 flex">
      {/* Left: Categories */}
      <div className="w-56 bg-stone-800 flex flex-col border-r border-stone-700 flex-shrink-0">
        <div className="p-4 border-b border-stone-700">
          <h2 className="text-base font-bold text-white">{menu?.outlet_name}</h2>
          <p className="text-[10px] text-stone-500">{menu?.hotel_name}</p>
        </div>
        <div className="flex-1 overflow-y-auto py-2">
          <button onClick={() => setActiveCat("all")}
            className={`w-full text-left px-4 py-3 text-sm font-medium transition-colors ${activeCat === "all" ? "bg-orange-500 text-white" : "text-stone-400 hover:text-white hover:bg-stone-700"}`}>
            All Items
          </button>
          {(menu?.categories || []).map(cat => (
            <button key={cat} onClick={() => setActiveCat(cat)}
              className={`w-full text-left px-4 py-3 text-sm font-medium transition-colors flex items-center gap-2 ${activeCat === cat ? "bg-orange-500 text-white" : "text-stone-400 hover:text-white hover:bg-stone-700"}`}>
              <span className="w-2.5 h-2.5 rounded-full" style={{ background: CAT_COLORS[cat] || "#64748b" }} />
              {cat}
            </button>
          ))}
        </div>
        <div className="p-3 border-t border-stone-700">
          <button onClick={() => { setCart([]); setIdle(true); setGuestName(""); }}
            className="w-full text-xs py-2 bg-stone-700 text-stone-400 rounded-lg hover:bg-stone-600">Cancel Order</button>
        </div>
      </div>

      {/* Center: Menu Grid */}
      <div className="flex-1 overflow-y-auto p-4">
        {menu?.happy_hour_active && (
          <div className="mb-4 bg-gradient-to-r from-amber-500/20 to-orange-500/20 border border-amber-500/30 rounded-xl px-4 py-2.5 text-amber-300 text-sm font-medium">
            🎉 {menu.happy_hour_name || "Happy Hour"} is active — Special prices on selected items!
          </div>
        )}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          {filtered.map(item => {
            const inCart = cart.find(c => c.id === item.id);
            return (
              <motion.button key={item.id} whileTap={{ scale: 0.95 }} onClick={() => addToCart(item)}
                className="relative text-left bg-stone-800 border border-stone-700 rounded-2xl p-4 hover:border-orange-500/50 transition-colors">
                <div className="text-sm font-semibold text-white mb-1">{item.name}</div>
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] px-1.5 py-0.5 rounded-full" style={{ background: `${CAT_COLORS[item.category] || "#64748b"}20`, color: CAT_COLORS[item.category] || "#64748b" }}>{item.category}</span>
                  {item.happy_hour && <span className="text-[9px] bg-amber-500/20 text-amber-400 px-1.5 py-0.5 rounded-full">Sale</span>}
                </div>
                <div className="mt-2 flex items-center justify-between">
                  <span className="text-lg font-black text-orange-400">£{item.price.toFixed(2)}</span>
                  {item.happy_hour && item.original_price && (
                    <span className="text-xs text-stone-500 line-through">£{item.original_price.toFixed(2)}</span>
                  )}
                </div>
                {inCart && (
                  <div className="absolute top-2 right-2 w-7 h-7 rounded-full bg-orange-500 text-white text-xs font-bold flex items-center justify-center">
                    {inCart.quantity}
                  </div>
                )}
              </motion.button>
            );
          })}
        </div>
      </div>

      {/* Right: Cart */}
      <div className="w-80 bg-stone-800 border-l border-stone-700 flex flex-col flex-shrink-0">
        <div className="p-4 border-b border-stone-700">
          <h3 className="text-base font-bold text-white">Your Order</h3>
          <p className="text-[10px] text-stone-500">{cart.reduce((s, c) => s + c.quantity, 0)} items</p>
        </div>
        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          <AnimatePresence>
            {cart.map(item => (
              <motion.div key={item.id} initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}
                className="bg-stone-700/50 rounded-xl px-3 py-2.5">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-medium text-white truncate flex-1">{item.name}</span>
                  <span className="text-sm font-bold text-orange-400 ml-2">£{(item.price * item.quantity).toFixed(2)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-stone-500">£{item.price.toFixed(2)} each</span>
                  <div className="flex items-center gap-2">
                    <button onClick={() => updateQty(item.id, -1)} className="w-8 h-8 rounded-lg bg-stone-600 text-white text-lg flex items-center justify-center hover:bg-stone-500">−</button>
                    <span className="text-white font-bold text-sm w-5 text-center">{item.quantity}</span>
                    <button onClick={() => updateQty(item.id, 1)} className="w-8 h-8 rounded-lg bg-orange-500 text-white text-lg flex items-center justify-center hover:bg-orange-400">+</button>
                  </div>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
          {cart.length === 0 && <div className="text-center py-12 text-stone-600 text-sm">Tap items to add to your order</div>}
        </div>

        {cart.length > 0 && (
          <div className="p-4 border-t border-stone-700 space-y-3">
            <input value={guestName} onChange={e => setGuestName(e.target.value)} placeholder="Your name (optional)"
              className="w-full bg-stone-700 border-0 rounded-lg px-3 py-2 text-sm text-white placeholder-stone-500 focus:outline-none focus:ring-2 focus:ring-orange-500" />
            <div className="space-y-1 text-sm">
              <div className="flex justify-between text-stone-400"><span>Subtotal</span><span>£{cartTotal.toFixed(2)}</span></div>
              <div className="flex justify-between text-stone-400"><span>VAT (20%)</span><span>£{cartVat.toFixed(2)}</span></div>
              <div className="flex justify-between text-xl font-black text-white pt-1 border-t border-stone-700"><span>Total</span><span>£{grandTotal.toFixed(2)}</span></div>
            </div>
            <button onClick={placeOrder} disabled={paying}
              className="w-full bg-orange-500 text-white py-4 rounded-2xl text-lg font-black hover:bg-orange-400 disabled:opacity-50 transition-colors">
              {paying ? "Processing..." : `Pay £${grandTotal.toFixed(2)}`}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
