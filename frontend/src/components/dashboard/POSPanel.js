import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { motion, AnimatePresence } from "framer-motion";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import {
  Plus, Minus, ArrowsClockwise, Trash, X, Receipt,
  CurrencyGbp, Lightning, Star, CheckCircle, Note,
} from "@phosphor-icons/react";
import { UtensilsCrossed, Wine, Bed, Sparkles, Gift, ShoppingCart, BarChart3, Clock, CreditCard, Banknote, Building, Users, ChefHat, LayoutGrid, QrCode, Percent, Award, SplitSquareHorizontal, Tag, FileText, Ban, RefreshCw } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const OUTLET_ICONS = { utensils: UtensilsCrossed, wine: Wine, bell: Bed, swim: Wine, spa: Sparkles, gift: Gift };

const CAT_BG = {
  Starters: "#FEF3C7", Mains: "#FEE2E2", Desserts: "#FCE7F3", "Soft Drinks": "#DBEAFE",
  "Hot Drinks": "#FFEDD5", Wine: "#F3E8FF", Beer: "#FEF3C7", Cocktails: "#EDE9FE",
  Spa: "#CCFBF1", "Room Service": "#E0E7FF",
};
const CAT_TEXT = {
  Starters: "#92400E", Mains: "#991B1B", Desserts: "#9D174D", "Soft Drinks": "#1E40AF",
  "Hot Drinks": "#9A3412", Wine: "#6B21A8", Beer: "#92400E", Cocktails: "#5B21B6",
  Spa: "#115E59", "Room Service": "#3730A3",
};

export function POSPanel({ properties, user, activePropertyId: propActivePropertyId }) {
  const [tab, setTab] = useState("terminal");
  const [outlets, setOutlets] = useState([]);
  const [activeOutlet, setActiveOutlet] = useState(null);
  const [menu, setMenu] = useState([]);
  const [cart, setCart] = useState([]);
  const [orders, setOrders] = useState([]);
  const [kitchenOrders, setKitchenOrders] = useState([]);
  const [reports, setReports] = useState(null);
  const [tables, setTables] = useState([]);
  const [loading, setLoading] = useState(true);
  const [menuSearch, setMenuSearch] = useState("");
  const [activeCategory, setActiveCategory] = useState("all");
  const [orderType, setOrderType] = useState("dine_in");
  const [tableNum, setTableNum] = useState("");
  const [guestName, setGuestName] = useState("");
  const [roomNumber, setRoomNumber] = useState("");
  const [covers, setCovers] = useState(1);
  const [showPay, setShowPay] = useState(false);
  const [payingOrder, setPayingOrder] = useState(null);
  const [payMethod, setPayMethod] = useState("card");
  const [tip, setTip] = useState(0);
  const [showUpsell, setShowUpsell] = useState(false);
  const [upsellSuggestions, setUpsellSuggestions] = useState([]);
  const [upselling, setUpselling] = useState(false);
  const [happyHours, setHappyHours] = useState([]);
  const [showHappyForm, setShowHappyForm] = useState(false);
  const [newHH, setNewHH] = useState({ name: "", start_hour: 16, end_hour: 19, discount_pct: 20, categories: [] });
  // New state
  const [orderDiscount, setOrderDiscount] = useState(0);
  const [orderNotes, setOrderNotes] = useState("");
  const [itemNotes, setItemNotes] = useState({});
  const [editingNote, setEditingNote] = useState(null);
  const [splitCount, setSplitCount] = useState(1);
  const [showSplit, setShowSplit] = useState(false);
  const [showReceipt, setShowReceipt] = useState(false);
  const [receiptOrder, setReceiptOrder] = useState(null);
  const [showVoid, setShowVoid] = useState(false);
  const [voidOrder, setVoidOrder] = useState(null);
  const [voidReason, setVoidReason] = useState("");
  const [stockStatus, setStockStatus] = useState(null);
  const [stockMovements, setStockMovements] = useState([]);
  const [linkingStock, setLinkingStock] = useState(false);

  const propertyId = (propActivePropertyId && propActivePropertyId !== "all") ? propActivePropertyId : (properties?.[0]?.id || "aldgate-flats");

  const fetchOutlets = useCallback(async () => {
    const { data } = await axios.get(`${API}/pos/outlets/${propertyId}`);
    setOutlets(data);
    if (data.length && !activeOutlet) setActiveOutlet(data[0]);
  }, [propertyId, activeOutlet]);
  const fetchMenu = useCallback(async () => { const { data } = await axios.get(`${API}/pos/menu/${propertyId}`); setMenu(data); }, [propertyId]);
  const fetchOrders = useCallback(async () => { const today = new Date().toISOString().slice(0, 10); const { data } = await axios.get(`${API}/pos/orders/${propertyId}?date=${today}`); setOrders(data); }, [propertyId]);
  const fetchKitchen = useCallback(async () => { const { data } = await axios.get(`${API}/pos/kitchen/${propertyId}`); setKitchenOrders(data); }, [propertyId]);
  const fetchReports = useCallback(async () => { const { data } = await axios.get(`${API}/pos/reports/${propertyId}`); setReports(data); }, [propertyId]);
  const fetchHappyHours = useCallback(async () => { const { data } = await axios.get(`${API}/pos/happy-hours/${propertyId}`); setHappyHours(data); }, [propertyId]);
  const fetchTables = useCallback(async () => { if (activeOutlet?.id) { const { data } = await axios.get(`${API}/pos/tables/${activeOutlet.id}`); setTables(data); } }, [activeOutlet]);
  const fetchStockStatus = useCallback(async () => {
    try {
      const [status, movements] = await Promise.all([
        axios.get(`${API}/pos/stock-status/${propertyId}`),
        axios.get(`${API}/pos/stock-movements/${propertyId}`),
      ]);
      setStockStatus(status.data);
      setStockMovements(movements.data);
    } catch (e) { /* ignore */ }
  }, [propertyId]);

  useEffect(() => { setLoading(true); Promise.all([fetchOutlets(), fetchMenu()]).then(() => setLoading(false)); }, [fetchOutlets, fetchMenu]);
  useEffect(() => { if (tab === "orders") fetchOrders(); }, [tab, fetchOrders]);
  useEffect(() => { if (tab === "kitchen") fetchKitchen(); }, [tab, fetchKitchen]);
  useEffect(() => { if (tab === "reports") fetchReports(); }, [tab, fetchReports]);
  useEffect(() => { if (tab === "happy-hour") fetchHappyHours(); }, [tab, fetchHappyHours]);
  useEffect(() => { if (tab === "tables") fetchTables(); }, [tab, fetchTables]);
  useEffect(() => { if (tab === "stock") fetchStockStatus(); }, [tab, fetchStockStatus]);

  const addToCart = (item) => {
    setCart(prev => {
      const existing = prev.find(c => c.id === item.id);
      if (existing) return prev.map(c => c.id === item.id ? { ...c, quantity: c.quantity + 1 } : c);
      return [...prev, { ...item, quantity: 1 }];
    });
  };
  const updateQty = (itemId, delta) => { setCart(prev => prev.map(c => c.id === itemId ? { ...c, quantity: Math.max(0, c.quantity + delta) } : c).filter(c => c.quantity > 0)); };
  const removeFromCart = (itemId) => { setCart(prev => prev.filter(c => c.id !== itemId)); setItemNotes(prev => { const n = {...prev}; delete n[itemId]; return n; }); };

  const cartSubtotal = cart.reduce((s, c) => s + c.price * c.quantity, 0);
  const discountAmt = orderDiscount > 0 ? Math.round(cartSubtotal * orderDiscount / 100 * 100) / 100 : 0;
  const cartAfterDiscount = cartSubtotal - discountAmt;
  const cartVat = cart.reduce((s, c) => s + (c.price * c.quantity * (c.vat_rate || 20) / 100), 0) * (1 - orderDiscount / 100);
  const cartTotal = cartAfterDiscount + cartVat;

  const placeOrder = async () => {
    if (!cart.length) return toast.error("Add items to the order");
    try {
      const { data } = await axios.post(`${API}/pos/orders`, {
        property_id: propertyId, outlet_id: activeOutlet?.id || "", outlet_name: activeOutlet?.name || "",
        order_type: orderType, table_number: tableNum, covers, guest_name: guestName, room_number: roomNumber,
        notes: orderNotes,
        items: cart.map(c => ({
          id: c.id, name: c.name, price: c.price, cost: c.cost || 0, quantity: c.quantity,
          vat_rate: c.vat_rate || 20, category: c.category, stock_product_id: c.stock_product_id || "",
          notes: itemNotes[c.id] || "",
        })),
      });
      toast.success(`Order ${data.order_number} placed!`);
      setCart([]); setTableNum(""); setGuestName(""); setRoomNumber(""); setOrderNotes(""); setOrderDiscount(0); setItemNotes({}); setUpsellSuggestions([]);
      fetchOrders();
    } catch (e) { toast.error("Failed to place order"); }
  };

  const getUpsellSuggestions = async () => {
    if (!cart.length) return;
    setUpselling(true);
    try {
      const { data } = await axios.post(`${API}/pos/ai-upsell`, { property_id: propertyId, cart_items: cart.map(c => ({ name: c.name, quantity: c.quantity, category: c.category, price: c.price })), guest_name: guestName });
      setUpsellSuggestions(data.suggestions || []); setShowUpsell(true);
    } catch (e) { toast.error("Upsell failed"); }
    finally { setUpselling(false); }
  };

  const payOrder = async () => {
    if (!payingOrder) return;
    try {
      if (payMethod === "terminal") {
        const { data } = await axios.post(`${API}/terminal/quick-pay/${payingOrder.id}`, { tip });
        if (data.status === "sent_to_reader") {
          toast.success("Amount sent to card reader!");
          const poll = setInterval(async () => { try { const { data: s } = await axios.get(`${API}/terminal/stripe/payment-status/${data.payment_intent_id}`); if (s.payment_status === "paid") { clearInterval(poll); toast.success("Payment confirmed!"); setShowPay(false); setPayingOrder(null); setTip(0); fetchOrders(); } } catch {} }, 3000);
          setTimeout(() => clearInterval(poll), 120000);
        } else toast.error(data.message || "Failed");
      } else {
        await axios.post(`${API}/pos/orders/${payingOrder.id}/pay`, { payment_method: payMethod, tip });
        toast.success(`Order paid via ${payMethod}`);
        setShowPay(false); setPayingOrder(null); setTip(0); fetchOrders();
      }
    } catch (e) { toast.error("Payment failed"); }
  };

  const updateKitchenStatus = async (orderId, status) => { await axios.post(`${API}/pos/kitchen/${orderId}/status`, { status }); fetchKitchen(); toast.success(`Order ${status}`); };

  const voidOrderAction = async () => {
    if (!voidOrder) return;
    try {
      await axios.post(`${API}/pos/orders/${voidOrder.id}/pay`, { payment_method: "void", tip: 0 });
      toast.success(`Order ${voidOrder.order_number} voided`);
      setShowVoid(false); setVoidOrder(null); setVoidReason(""); fetchOrders();
    } catch (e) { toast.error("Void failed"); }
  };

  const categories = ["all", ...new Set(menu.map(m => m.category))];
  const filteredMenu = menu.filter(m => {
    if (activeCategory !== "all" && m.category !== activeCategory) return false;
    if (menuSearch && !m.name.toLowerCase().includes(menuSearch.toLowerCase())) return false;
    return m.available;
  });

  const tabs = [
    { id: "terminal", label: "POS Terminal", icon: ShoppingCart },
    { id: "tables", label: "Floor Plan", icon: LayoutGrid },
    { id: "kitchen", label: "Kitchen", icon: ChefHat },
    { id: "orders", label: "Orders", icon: Receipt },
    { id: "reports", label: "Reports", icon: BarChart3 },
    { id: "happy-hour", label: "Happy Hour", icon: Percent },
    { id: "stock", label: "Stock", icon: Award },
    { id: "qr-code", label: "QR Order", icon: QrCode },
  ];

  if (loading) return <div className="flex items-center justify-center h-96"><ArrowsClockwise size={24} className="animate-spin text-[#D4A373]" /></div>;

  return (
    <div className="h-[calc(100vh-0px)] flex flex-col" data-testid="pos-panel" style={{ fontFamily: "Manrope, sans-serif" }}>
      {/* Header */}
      <div className="border-b border-[#E5E0D8] bg-white px-5 py-3 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#2C4C3B] flex items-center justify-center shadow-sm">
            <UtensilsCrossed size={18} className="text-white" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-[#1C1917]" style={{ fontFamily: "Outfit, sans-serif" }}>Hotel POS</h2>
            <p className="text-[11px] text-[#78716C]">Restaurant, Bar, Room Service, Spa</p>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          {outlets.map(o => {
            const Icon = OUTLET_ICONS[o.icon] || UtensilsCrossed;
            return (
              <button key={o.id} onClick={() => setActiveOutlet(o)}
                className={`text-[11px] px-3 py-2 rounded-xl flex items-center gap-1.5 font-semibold transition-all ${
                  activeOutlet?.id === o.id ? "bg-[#2C4C3B] text-white shadow-md" : "bg-[#F0EBE1] text-[#44403C] hover:bg-[#EAE5DC]"
                }`} data-testid={`outlet-${o.id}`}>
                <Icon size={13} /> {o.name}
              </button>
            );
          })}
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-[#E5E0D8] bg-white px-5 flex gap-0.5 flex-shrink-0">
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-semibold border-b-[3px] transition-all ${
              tab === t.id ? "border-[#2C4C3B] text-[#2C4C3B]" : "border-transparent text-[#A8A29E] hover:text-[#57534E]"
            }`} data-testid={`pos-tab-${t.id}`}>
            <t.icon size={14} /> {t.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-hidden flex">
        {/* ========== POS TERMINAL ========== */}
        {tab === "terminal" && (
          <>
            {/* Menu Grid */}
            <div className="flex-1 flex flex-col bg-[#F9F8F6] overflow-hidden">
              <div className="p-3 border-b border-[#E5E0D8] bg-white space-y-2.5">
                <div className="relative">
                  <Input value={menuSearch} onChange={e => setMenuSearch(e.target.value)} placeholder="Search menu items..." className="h-9 text-xs pl-9 bg-[#F9F8F6] border-[#E5E0D8] rounded-xl" data-testid="menu-search" />
                  <ShoppingCart size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#A8A29E]" />
                </div>
                <div className="flex gap-1.5 flex-wrap">
                  {categories.map(cat => (
                    <button key={cat} onClick={() => setActiveCategory(cat)}
                      className={`text-[10px] px-3 py-1.5 rounded-full font-semibold transition-all ${activeCategory === cat ? "bg-[#2C4C3B] text-white shadow-sm" : "bg-[#F0EBE1] text-[#57534E] hover:bg-[#EAE5DC]"}`}
                      data-testid={`cat-${cat}`}>{cat === "all" ? "All" : cat}</button>
                  ))}
                </div>
              </div>
              <ScrollArea className="flex-1 p-3">
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2.5">
                  {filteredMenu.map(item => {
                    const inCart = cart.find(c => c.id === item.id);
                    return (
                      <motion.button key={item.id} whileTap={{ scale: 0.95 }} whileHover={{ scale: 1.02 }} onClick={() => addToCart(item)}
                        className="text-left rounded-2xl border-2 overflow-hidden transition-all relative group"
                        style={{ backgroundColor: CAT_BG[item.category] || "#F9F8F6", borderColor: inCart ? "#2C4C3B" : (CAT_BG[item.category] || "#E5E0D8") }}
                        data-testid={`menu-item-${item.id}`}>
                        <div className="p-3.5">
                          <div className="text-xs font-bold truncate" style={{ color: CAT_TEXT[item.category] || "#1C1917" }}>{item.name}</div>
                          <div className="flex items-center justify-between mt-2">
                            <span className="text-base font-black" style={{ color: CAT_TEXT[item.category] || "#1C1917" }}>£{item.price.toFixed(2)}</span>
                            <span className="text-[9px] font-medium opacity-50 uppercase tracking-wider">{item.category}</span>
                          </div>
                        </div>
                        {inCart && (
                          <div className="absolute top-2 right-2 w-6 h-6 rounded-full bg-[#2C4C3B] text-white text-[10px] font-bold flex items-center justify-center shadow-lg">
                            {inCart.quantity}
                          </div>
                        )}
                        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/[0.03] transition-colors rounded-2xl" />
                      </motion.button>
                    );
                  })}
                </div>
              </ScrollArea>
            </div>

            {/* Cart / Order Panel */}
            <div className="w-[380px] border-l border-[#E5E0D8] bg-white flex flex-col flex-shrink-0" data-testid="cart-panel">
              {/* Order Type & Info */}
              <div className="p-3.5 border-b border-[#EAE5DC] space-y-2.5">
                <div className="flex gap-1">
                  {[
                    { value: "dine_in", label: "Dine In", icon: "🍽" },
                    { value: "takeaway", label: "Takeaway", icon: "🥡" },
                    { value: "room_service", label: "Room Service", icon: "🛎" },
                  ].map(t => (
                    <button key={t.value} onClick={() => setOrderType(t.value)}
                      className={`flex-1 text-[10px] py-2 rounded-xl font-bold transition-all ${orderType === t.value ? "bg-[#2C4C3B] text-white shadow-md" : "bg-[#F0EBE1] text-[#57534E]"}`}>
                      {t.icon} {t.label}
                    </button>
                  ))}
                </div>
                <div className="grid grid-cols-2 gap-1.5">
                  {orderType === "dine_in" && <Input value={tableNum} onChange={e => setTableNum(e.target.value)} placeholder="Table #" className="h-8 text-[11px] bg-[#F9F8F6] border-[#E5E0D8] rounded-lg" data-testid="table-input" />}
                  {orderType === "room_service" && <Input value={roomNumber} onChange={e => setRoomNumber(e.target.value)} placeholder="Room #" className="h-8 text-[11px] bg-[#F9F8F6] border-[#E5E0D8] rounded-lg" data-testid="room-input" />}
                  <Input value={guestName} onChange={e => setGuestName(e.target.value)} placeholder="Guest name" className="h-8 text-[11px] bg-[#F9F8F6] border-[#E5E0D8] rounded-lg" data-testid="guest-name-input" />
                  {orderType === "dine_in" && <Input type="number" value={covers} onChange={e => setCovers(parseInt(e.target.value) || 1)} placeholder="Covers" className="h-8 text-[11px] bg-[#F9F8F6] border-[#E5E0D8] rounded-lg" min={1} />}
                </div>
              </div>

              {/* Cart Items */}
              <ScrollArea className="flex-1">
                {cart.length === 0 ? (
                  <div className="p-10 text-center">
                    <ShoppingCart size={32} className="mx-auto text-[#D6D3D1] mb-3" />
                    <p className="text-xs text-[#A8A29E] font-medium">Tap menu items to add</p>
                  </div>
                ) : (
                  <div className="p-2.5 space-y-1">
                    <AnimatePresence>
                      {cart.map(item => (
                        <motion.div key={item.id} initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}
                          className="bg-[#F9F8F6] rounded-xl px-3 py-2.5 border border-[#EAE5DC]" data-testid={`cart-item-${item.id}`}>
                          <div className="flex items-center gap-2">
                            <div className="flex-1 min-w-0">
                              <span className="text-xs font-bold text-[#1C1917] block truncate">{item.name}</span>
                              <span className="text-[10px] text-[#A8A29E]">£{item.price.toFixed(2)} each</span>
                            </div>
                            <div className="flex items-center gap-1">
                              <button onClick={() => updateQty(item.id, -1)} className="w-7 h-7 rounded-lg bg-white border border-[#E5E0D8] flex items-center justify-center text-[#57534E] hover:bg-[#EAE5DC] transition-colors"><Minus size={10} weight="bold" /></button>
                              <span className="text-xs font-black w-6 text-center text-[#2C4C3B]">{item.quantity}</span>
                              <button onClick={() => updateQty(item.id, 1)} className="w-7 h-7 rounded-lg bg-[#2C4C3B] flex items-center justify-center text-white hover:bg-[#1A3025] transition-colors"><Plus size={10} weight="bold" /></button>
                            </div>
                            <span className="text-xs font-black text-[#1C1917] w-14 text-right">£{(item.price * item.quantity).toFixed(2)}</span>
                            <button onClick={() => removeFromCart(item.id)} className="text-[#D6D3D1] hover:text-[#9B4837] transition-colors"><X size={12} weight="bold" /></button>
                          </div>
                          {/* Item Note */}
                          {itemNotes[item.id] && <div className="mt-1.5 text-[10px] text-[#D4A373] bg-[#FEF3C7] px-2 py-1 rounded-md">{itemNotes[item.id]}</div>}
                          {editingNote === item.id ? (
                            <div className="mt-1.5 flex gap-1">
                              <Input value={itemNotes[item.id] || ""} onChange={e => setItemNotes(p => ({...p, [item.id]: e.target.value}))}
                                placeholder="No onions, medium rare..." className="h-7 text-[10px] flex-1 bg-white rounded-md" autoFocus onKeyDown={e => e.key === "Enter" && setEditingNote(null)} />
                              <button onClick={() => setEditingNote(null)} className="text-[10px] px-2 bg-[#2C4C3B] text-white rounded-md font-medium">OK</button>
                            </div>
                          ) : (
                            <button onClick={() => setEditingNote(item.id)} className="mt-1 text-[9px] text-[#A8A29E] hover:text-[#D4A373] flex items-center gap-0.5">
                              <Note size={10} /> {itemNotes[item.id] ? "Edit note" : "Add note"}
                            </button>
                          )}
                        </motion.div>
                      ))}
                    </AnimatePresence>
                  </div>
                )}
              </ScrollArea>

              {/* Cart Footer */}
              {cart.length > 0 && (
                <div className="p-3.5 border-t border-[#E5E0D8] space-y-2.5 bg-white">
                  {/* AI Upsell */}
                  {upsellSuggestions.length > 0 && showUpsell && (
                    <div className="bg-[#F3E8FF] border border-[#D8B4FE] rounded-xl p-2.5" data-testid="upsell-panel">
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-[10px] font-bold text-[#6B21A8] uppercase tracking-wider flex items-center gap-1"><Sparkles size={10} /> AI Suggests</span>
                        <button onClick={() => setShowUpsell(false)} className="text-[10px] text-[#A78BFA]">Hide</button>
                      </div>
                      {upsellSuggestions.map((s, i) => (
                        <button key={i} onClick={() => { const mi = menu.find(m => m.name === s.name); if (mi) addToCart(mi); }}
                          className="w-full text-left flex items-center justify-between text-xs bg-white rounded-lg px-2.5 py-1.5 mb-1 hover:bg-[#F3E8FF] transition-colors" data-testid={`upsell-${i}`}>
                          <div className="flex-1 min-w-0"><span className="font-semibold text-[#44403C]">{s.name}</span><span className="text-[9px] text-[#A78BFA] block">{s.reason}</span></div>
                          <span className="text-xs font-bold text-[#6B21A8] ml-2">+£{s.price?.toFixed(2)}</span>
                        </button>
                      ))}
                    </div>
                  )}

                  {/* Actions Row */}
                  <div className="flex gap-1.5">
                    <button onClick={getUpsellSuggestions} disabled={upselling}
                      className="flex-1 text-[10px] py-1.5 bg-[#F3E8FF] text-[#6B21A8] rounded-lg font-bold hover:bg-[#EDE9FE] disabled:opacity-50 flex items-center justify-center gap-1" data-testid="ai-upsell-btn">
                      <Sparkles size={10} /> {upselling ? "..." : "AI Upsell"}
                    </button>
                    <button onClick={() => { const d = prompt("Discount % (e.g. 10, 15, 20):"); if (d && !isNaN(d)) setOrderDiscount(Math.min(100, Math.max(0, parseInt(d)))); }}
                      className="flex-1 text-[10px] py-1.5 bg-[#FEF3C7] text-[#92400E] rounded-lg font-bold hover:bg-[#FDE68A] flex items-center justify-center gap-1" data-testid="discount-btn">
                      <Tag size={10} /> {orderDiscount > 0 ? `${orderDiscount}% Off` : "Discount"}
                    </button>
                    <button onClick={() => { const n = prompt("Order notes:", orderNotes); if (n !== null) setOrderNotes(n); }}
                      className="flex-1 text-[10px] py-1.5 bg-[#F0EBE1] text-[#57534E] rounded-lg font-bold hover:bg-[#EAE5DC] flex items-center justify-center gap-1" data-testid="order-notes-btn">
                      <FileText size={10} /> Notes
                    </button>
                  </div>

                  {/* Order Notes Display */}
                  {orderNotes && <div className="text-[10px] text-[#D4A373] bg-[#FFFBEB] px-2.5 py-1.5 rounded-lg border border-[#FDE68A]">{orderNotes}</div>}

                  {/* Totals */}
                  <div className="bg-[#F9F8F6] rounded-xl p-3 space-y-1.5">
                    <div className="flex justify-between text-xs text-[#78716C]"><span>Subtotal ({cart.reduce((s,c) => s+c.quantity, 0)} items)</span><span>£{cartSubtotal.toFixed(2)}</span></div>
                    {orderDiscount > 0 && <div className="flex justify-between text-xs text-[#9B4837] font-semibold"><span>Discount ({orderDiscount}%)</span><span>-£{discountAmt.toFixed(2)}</span></div>}
                    <div className="flex justify-between text-xs text-[#78716C]"><span>VAT</span><span>£{cartVat.toFixed(2)}</span></div>
                    <div className="border-t border-[#E5E0D8] pt-1.5 flex justify-between text-base font-black text-[#1C1917]"><span>Total</span><span>£{cartTotal.toFixed(2)}</span></div>
                  </div>

                  <button onClick={placeOrder}
                    className="w-full bg-[#2C4C3B] text-white py-3 rounded-xl text-sm font-bold hover:bg-[#1A3025] transition-all flex items-center justify-center gap-2 shadow-lg active:scale-[0.98]"
                    data-testid="place-order-btn">
                    <Receipt size={16} weight="fill" /> Place Order — £{cartTotal.toFixed(2)}
                  </button>
                </div>
              )}
            </div>
          </>
        )}

        {/* ========== FLOOR PLAN ========== */}
        {tab === "tables" && (
          <div className="flex-1 p-6 overflow-y-auto bg-[#F9F8F6]" data-testid="tables-tab">
            <div className="flex items-center justify-between mb-5">
              <div>
                <span className="text-base font-bold text-[#1C1917]" style={{ fontFamily: "Outfit, sans-serif" }}>{activeOutlet?.name} — Floor Plan</span>
                <p className="text-[11px] text-[#A8A29E]">Click available table to start order, occupied table to view/pay</p>
              </div>
              <button onClick={fetchTables} className="text-xs text-[#78716C] hover:text-[#2C4C3B] flex items-center gap-1"><RefreshCw size={12} /> Refresh</button>
            </div>
            {/* Legend */}
            <div className="flex gap-4 mb-5">
              <div className="flex items-center gap-1.5 text-[10px] text-[#78716C]"><div className="w-4 h-4 rounded bg-[#D1FAE5] border-2 border-[#6EE7B7]" /> Available</div>
              <div className="flex items-center gap-1.5 text-[10px] text-[#78716C]"><div className="w-4 h-4 rounded bg-[#FEF3C7] border-2 border-[#FCD34D]" /> Occupied</div>
              <div className="flex items-center gap-1.5 text-[10px] text-[#78716C]"><div className="w-4 h-4 rounded bg-[#FEE2E2] border-2 border-[#FCA5A5]" /> Needs Attention</div>
            </div>
            <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-6 gap-4">
              {tables.map(t => {
                const isOccupied = t.status === "occupied";
                return (
                  <motion.div key={t.number} whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
                    onClick={() => { if (t.order) { setPayingOrder(t.order); setShowPay(true); } else { setTableNum(String(t.number)); setTab("terminal"); } }}
                    className={`rounded-2xl p-5 text-center cursor-pointer border-2 transition-all shadow-sm hover:shadow-md ${
                      isOccupied ? "bg-[#FEF3C7] border-[#FCD34D]" : "bg-[#D1FAE5] border-[#6EE7B7] hover:border-[#34D399]"
                    }`} data-testid={`table-${t.number}`}>
                    <div className={`text-2xl font-black ${isOccupied ? "text-[#92400E]" : "text-[#065F46]"}`}>{t.number}</div>
                    <div className={`text-[11px] mt-1.5 font-bold ${isOccupied ? "text-[#B45309]" : "text-[#059669]"}`}>
                      {isOccupied ? `£${t.order?.total || 0}` : "Available"}
                    </div>
                    {t.order && <div className="text-[9px] text-[#78716C] mt-1">{t.order.items?.length || 0} items · {t.order.covers || 1} covers</div>}
                    {t.order?.guest_name && <div className="text-[9px] text-[#D4A373] mt-0.5 font-medium">{t.order.guest_name}</div>}
                  </motion.div>
                );
              })}
              {tables.length === 0 && <div className="col-span-6 text-center py-16 text-[#A8A29E] text-sm">No tables configured</div>}
            </div>
          </div>
        )}

        {/* ========== KITCHEN DISPLAY ========== */}
        {tab === "kitchen" && (
          <div className="flex-1 p-4 overflow-y-auto bg-[#F9F8F6]" data-testid="kitchen-tab">
            <div className="flex items-center justify-between mb-4">
              <span className="text-base font-bold text-[#1C1917] flex items-center gap-2" style={{ fontFamily: "Outfit, sans-serif" }}><ChefHat size={18} className="text-[#2C4C3B]" /> Kitchen Display</span>
              <button onClick={fetchKitchen} className="text-xs text-[#78716C] flex items-center gap-1"><RefreshCw size={12} /> Refresh</button>
            </div>
            {/* Timeline Legend */}
            <div className="flex gap-3 mb-4">
              <div className="flex items-center gap-1.5 text-[10px] font-semibold"><div className="w-3 h-3 rounded-full bg-[#9B4837]" /> New</div>
              <div className="flex items-center gap-1.5 text-[10px] font-semibold"><div className="w-3 h-3 rounded-full bg-[#D4A373]" /> Preparing</div>
              <div className="flex items-center gap-1.5 text-[10px] font-semibold"><div className="w-3 h-3 rounded-full bg-[#2C4C3B]" /> Ready</div>
            </div>
            {kitchenOrders.length === 0 ? (
              <div className="text-center py-16 text-[#A8A29E]"><ChefHat size={40} className="mx-auto mb-3 text-[#D6D3D1]" /><p>No pending kitchen orders</p></div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {kitchenOrders.map(o => {
                  const statusColor = o.kitchen_status === "new" ? "#9B4837" : o.kitchen_status === "preparing" ? "#D4A373" : "#2C4C3B";
                  const elapsed = Math.round((Date.now() - new Date(o.created_at).getTime()) / 60000);
                  return (
                    <motion.div key={o.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                      className="rounded-2xl border-2 p-4 bg-white shadow-sm" style={{ borderColor: statusColor }} data-testid={`kitchen-order-${o.id}`}>
                      <div className="flex items-center justify-between mb-2.5">
                        <span className="text-sm font-black text-[#1C1917]">{o.order_number}</span>
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] font-bold text-[#78716C] flex items-center gap-0.5"><Clock size={10} /> {elapsed}m</span>
                          <Badge className="text-[9px] font-bold text-white" style={{ backgroundColor: statusColor }}>{o.kitchen_status}</Badge>
                        </div>
                      </div>
                      <div className="text-[10px] text-[#A8A29E] mb-2.5 flex gap-2">
                        <span>{o.outlet_name}</span>
                        {o.table_number && <span className="font-semibold text-[#57534E]">Table {o.table_number}</span>}
                        <span>{new Date(o.created_at).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}</span>
                      </div>
                      {/* Progress Bar */}
                      <div className="w-full h-1.5 bg-[#EAE5DC] rounded-full mb-3">
                        <div className="h-full rounded-full transition-all" style={{ backgroundColor: statusColor, width: o.kitchen_status === "new" ? "33%" : o.kitchen_status === "preparing" ? "66%" : "100%" }} />
                      </div>
                      <div className="space-y-1 mb-3">
                        {o.items?.map((item, i) => (
                          <div key={i} className="flex justify-between text-xs items-center">
                            <span className="text-[#44403C] font-medium"><span className="font-bold text-[#2C4C3B] mr-1">{item.quantity}x</span> {item.name}</span>
                            {item.notes && <span className="text-[9px] text-[#D4A373] bg-[#FEF3C7] px-1.5 py-0.5 rounded">{item.notes}</span>}
                          </div>
                        ))}
                      </div>
                      {o.notes && <div className="text-[10px] text-[#9B4837] bg-[#FEF2F2] px-2.5 py-1.5 rounded-lg mb-2.5 font-medium">{o.notes}</div>}
                      <div className="flex gap-1.5">
                        {o.kitchen_status === "new" && (
                          <button onClick={() => updateKitchenStatus(o.id, "preparing")} className="flex-1 text-[11px] py-2 bg-[#D4A373] text-white rounded-xl font-bold hover:bg-[#C48B5E] transition-all" data-testid={`start-${o.id}`}>Start Preparing</button>
                        )}
                        {o.kitchen_status === "preparing" && (
                          <button onClick={() => updateKitchenStatus(o.id, "ready")} className="flex-1 text-[11px] py-2 bg-[#2C4C3B] text-white rounded-xl font-bold hover:bg-[#1A3025] transition-all" data-testid={`ready-${o.id}`}>Mark Ready</button>
                        )}
                      </div>
                    </motion.div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* ========== ORDERS ========== */}
        {tab === "orders" && (
          <div className="flex-1 p-4 overflow-y-auto bg-[#F9F8F6]" data-testid="orders-tab">
            <div className="flex items-center justify-between mb-4">
              <span className="text-base font-bold text-[#1C1917]" style={{ fontFamily: "Outfit, sans-serif" }}>Today's Orders ({orders.length})</span>
              <button onClick={fetchOrders} className="text-xs text-[#78716C] flex items-center gap-1"><RefreshCw size={12} /> Refresh</button>
            </div>
            <div className="space-y-2.5">
              {orders.map(o => (
                <motion.div key={o.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                  className="bg-white border border-[#E5E0D8] rounded-2xl p-4 hover:shadow-md transition-all" data-testid={`order-${o.id}`}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className={`w-11 h-11 rounded-xl flex items-center justify-center ${o.payment_status === "paid" ? "bg-[#D1FAE5]" : o.payment_status === "void" ? "bg-[#FEE2E2]" : "bg-[#FEF3C7]"}`}>
                        {o.payment_status === "void" ? <Ban size={18} className="text-[#9B4837]" /> : <Receipt size={18} className={o.payment_status === "paid" ? "text-[#059669]" : "text-[#D4A373]"} />}
                      </div>
                      <div>
                        <div className="text-sm font-bold text-[#1C1917]">{o.order_number} <span className="text-[#A8A29E] font-normal">— {o.outlet_name}</span></div>
                        <div className="text-[10px] text-[#A8A29E] flex items-center gap-1.5">
                          <span className="capitalize">{o.order_type?.replace(/_/g, " ")}</span>
                          {o.table_number && <><span>·</span><span className="font-semibold text-[#57534E]">Table {o.table_number}</span></>}
                          <span>·</span><span>{o.items?.length || 0} items</span>
                          {o.guest_name && <><span>·</span><span className="text-[#D4A373] font-medium">{o.guest_name}</span></>}
                          <span>·</span><span>{new Date(o.created_at).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}</span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2.5">
                      <span className="text-base font-black text-[#1C1917]">£{o.total}</span>
                      <Badge className={`text-[9px] font-bold ${o.payment_status === "paid" ? "bg-[#D1FAE5] text-[#059669]" : o.payment_status === "void" ? "bg-[#FEE2E2] text-[#9B4837]" : "bg-[#FEF3C7] text-[#D4A373]"}`}>{o.payment_status}</Badge>
                      <div className="flex gap-1">
                        {o.payment_status === "pending" && (
                          <>
                            <button onClick={() => { setPayingOrder(o); setShowPay(true); }}
                              className="text-[10px] px-2.5 py-1.5 bg-[#2C4C3B] text-white rounded-lg font-bold hover:bg-[#1A3025]" data-testid={`pay-${o.id}`}>Pay</button>
                            <button onClick={() => { setShowSplit(true); setPayingOrder(o); }}
                              className="text-[10px] px-2.5 py-1.5 bg-[#F0EBE1] text-[#57534E] rounded-lg font-bold hover:bg-[#EAE5DC]" data-testid={`split-${o.id}`}>Split</button>
                            <button onClick={() => { setVoidOrder(o); setShowVoid(true); }}
                              className="text-[10px] px-2.5 py-1.5 bg-[#FEF2F2] text-[#9B4837] rounded-lg font-bold hover:bg-[#FEE2E2]" data-testid={`void-${o.id}`}>Void</button>
                          </>
                        )}
                        {o.payment_status === "paid" && (
                          <button onClick={() => { setReceiptOrder(o); setShowReceipt(true); }}
                            className="text-[10px] px-2.5 py-1.5 bg-[#F0EBE1] text-[#57534E] rounded-lg font-bold hover:bg-[#EAE5DC]" data-testid={`receipt-${o.id}`}>Receipt</button>
                        )}
                      </div>
                    </div>
                  </div>
                </motion.div>
              ))}
              {orders.length === 0 && <div className="text-center py-16 text-[#A8A29E] text-sm">No orders today</div>}
            </div>
          </div>
        )}

        {/* ========== REPORTS ========== */}
        {tab === "reports" && reports && (
          <div className="flex-1 p-6 overflow-y-auto space-y-5 bg-[#F9F8F6]" data-testid="reports-tab">
            {/* KPI Cards */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                { label: "Revenue", value: `£${reports.total_revenue?.toLocaleString()}`, bg: "#D1FAE5", color: "#065F46", sub: "Today" },
                { label: "Orders", value: reports.total_orders, bg: "#F9F8F6", color: "#1C1917", sub: `${reports.total_covers} covers` },
                { label: "Avg Check", value: `£${reports.avg_check}`, bg: "#DBEAFE", color: "#1E40AF", sub: "Per order" },
                { label: "Margin", value: `${reports.gross_margin}%`, bg: "#F3E8FF", color: "#6B21A8", sub: "Gross profit" },
              ].map((kpi, i) => (
                <div key={i} className="rounded-2xl p-5 text-center border border-[#E5E0D8] shadow-sm" style={{ backgroundColor: kpi.bg }}>
                  <div className="text-2xl font-black" style={{ color: kpi.color }}>{kpi.value}</div>
                  <div className="text-[11px] font-semibold mt-0.5" style={{ color: kpi.color, opacity: 0.7 }}>{kpi.label}</div>
                  <div className="text-[9px] mt-1 opacity-50" style={{ color: kpi.color }}>{kpi.sub}</div>
                </div>
              ))}
            </div>

            {/* Revenue by Outlet */}
            {Object.keys(reports.by_outlet || {}).length > 0 && (
              <div className="bg-white rounded-2xl border border-[#E5E0D8] p-5 shadow-sm">
                <div className="text-sm font-bold text-[#1C1917] mb-3" style={{ fontFamily: "Outfit, sans-serif" }}>Revenue by Outlet</div>
                {Object.entries(reports.by_outlet).sort((a, b) => b[1].revenue - a[1].revenue).map(([name, data]) => {
                  const maxRev = Math.max(...Object.values(reports.by_outlet).map(d => d.revenue), 1);
                  return (
                    <div key={name} className="mb-2.5">
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span className="text-[#57534E] font-semibold">{name}</span>
                        <span className="font-black text-[#1C1917]">£{data.revenue?.toLocaleString()}</span>
                      </div>
                      <div className="w-full h-3 bg-[#EAE5DC] rounded-full overflow-hidden">
                        <motion.div initial={{ width: 0 }} animate={{ width: `${(data.revenue / maxRev * 100)}%` }} transition={{ duration: 0.8 }}
                          className="h-full rounded-full bg-[#2C4C3B]" />
                      </div>
                      <div className="text-[9px] text-[#A8A29E] mt-0.5">{data.orders} orders · {data.covers} covers</div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Top Selling Items */}
            {reports.top_items?.length > 0 && (
              <div className="bg-white rounded-2xl border border-[#E5E0D8] p-5 shadow-sm">
                <div className="text-sm font-bold text-[#1C1917] mb-3" style={{ fontFamily: "Outfit, sans-serif" }}>Top Selling Items</div>
                {reports.top_items.map((item, i) => (
                  <div key={i} className="flex items-center gap-3 py-2 border-b border-[#F0EBE1] last:border-0">
                    <div className={`w-7 h-7 rounded-lg flex items-center justify-center text-[10px] font-black ${i < 3 ? "bg-[#FEF3C7] text-[#92400E]" : "bg-[#F0EBE1] text-[#78716C]"}`}>{i + 1}</div>
                    <div className="flex-1"><span className="text-xs font-semibold text-[#1C1917]">{item.name}</span></div>
                    <span className="text-[10px] text-[#A8A29E] font-medium">{item.qty} sold</span>
                    <span className="text-xs font-black text-[#1C1917]">£{item.revenue?.toLocaleString()}</span>
                  </div>
                ))}
              </div>
            )}

            {/* By Server */}
            {Object.keys(reports.by_server || {}).length > 0 && (
              <div className="bg-white rounded-2xl border border-[#E5E0D8] p-5 shadow-sm">
                <div className="text-sm font-bold text-[#1C1917] mb-3" style={{ fontFamily: "Outfit, sans-serif" }}>Staff Performance</div>
                {Object.entries(reports.by_server).sort((a, b) => b[1].revenue - a[1].revenue).map(([name, data]) => (
                  <div key={name} className="flex items-center justify-between text-xs py-2 border-b border-[#F0EBE1] last:border-0">
                    <span className="text-[#57534E] font-semibold flex items-center gap-1.5"><Users size={12} className="text-[#A8A29E]" /> {name}</span>
                    <div className="flex items-center gap-4">
                      <span className="text-[#A8A29E]">{data.orders} orders</span>
                      {data.tips > 0 && <span className="text-[#D4A373] font-bold">£{data.tips} tips</span>}
                      <span className="font-black text-[#1C1917]">£{data.revenue?.toLocaleString()}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
            {reports.total_orders === 0 && <div className="text-center py-16 text-[#A8A29E] text-sm">No sales data for today</div>}
          </div>
        )}

        {/* ========== HAPPY HOUR ========== */}
        {tab === "happy-hour" && (
          <div className="flex-1 p-6 overflow-y-auto space-y-4 bg-[#F9F8F6]" data-testid="happy-hour-tab">
            <div className="flex items-center justify-between">
              <span className="text-base font-bold text-[#1C1917] flex items-center gap-2" style={{ fontFamily: "Outfit, sans-serif" }}><Percent size={16} className="text-[#D4A373]" /> Happy Hour & Promotions</span>
              <button onClick={() => setShowHappyForm(true)} className="text-xs px-4 py-2 bg-[#2C4C3B] text-white rounded-xl font-bold hover:bg-[#1A3025]" data-testid="new-happy-hour-btn">
                <Plus size={12} className="inline mr-1" /> New Promotion
              </button>
            </div>
            {happyHours.map(hh => (
              <div key={hh.id} className={`bg-white border-2 rounded-2xl p-5 shadow-sm ${hh.enabled ? "border-[#D4A373]" : "border-[#E5E0D8] opacity-60"}`} data-testid={`hh-${hh.id}`}>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold text-[#1C1917]">{hh.name}</span>
                    <span className="text-[10px] font-bold text-[#D4A373] bg-[#FEF3C7] px-2 py-0.5 rounded-full">{hh.discount_pct}% off</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge className={`text-[9px] font-bold ${hh.enabled ? "bg-[#D1FAE5] text-[#059669]" : "bg-[#EAE5DC] text-[#78716C]"}`}>{hh.enabled ? "Active" : "Inactive"}</Badge>
                    <button onClick={async () => { await axios.put(`${API}/pos/happy-hours/${hh.id}`, { enabled: !hh.enabled }); fetchHappyHours(); }}
                      className="text-[10px] text-[#2C4C3B] hover:text-[#1A3025] font-bold" data-testid={`toggle-hh-${hh.id}`}>{hh.enabled ? "Disable" : "Enable"}</button>
                  </div>
                </div>
                <div className="text-xs text-[#78716C] flex items-center gap-2"><Clock size={12} /> {hh.start_hour}:00 — {hh.end_hour}:00</div>
              </div>
            ))}
            {happyHours.length === 0 && <div className="text-center py-16 text-[#A8A29E] text-sm">No promotions configured</div>}
            <Dialog open={showHappyForm} onOpenChange={setShowHappyForm}>
              <DialogContent className="max-w-md"><DialogHeader><DialogTitle>New Happy Hour</DialogTitle></DialogHeader>
                <div className="space-y-3">
                  <Input placeholder="Promotion name" value={newHH.name} onChange={e => setNewHH(p => ({...p, name: e.target.value}))} data-testid="hh-name" />
                  <div className="grid grid-cols-3 gap-2">
                    <div><label className="text-[10px] text-[#78716C] font-medium">Start Hour</label><Input type="number" min={0} max={23} value={newHH.start_hour} onChange={e => setNewHH(p => ({...p, start_hour: parseInt(e.target.value) || 0}))} /></div>
                    <div><label className="text-[10px] text-[#78716C] font-medium">End Hour</label><Input type="number" min={0} max={23} value={newHH.end_hour} onChange={e => setNewHH(p => ({...p, end_hour: parseInt(e.target.value) || 0}))} /></div>
                    <div><label className="text-[10px] text-[#78716C] font-medium">Discount %</label><Input type="number" min={1} max={100} value={newHH.discount_pct} onChange={e => setNewHH(p => ({...p, discount_pct: parseInt(e.target.value) || 0}))} /></div>
                  </div>
                  <button onClick={async () => { if (!newHH.name) return toast.error("Name required"); await axios.post(`${API}/pos/happy-hours`, { ...newHH, property_id: propertyId }); setShowHappyForm(false); fetchHappyHours(); toast.success("Promotion created"); }}
                    className="w-full text-xs py-2.5 bg-[#2C4C3B] text-white rounded-xl font-bold" data-testid="save-hh-btn">Create Promotion</button>
                </div>
              </DialogContent>
            </Dialog>
          </div>
        )}

        {/* ========== STOCK TAB ========== */}
        {tab === "stock" && (
          <div className="flex-1 p-6 overflow-y-auto space-y-4 bg-[#F9F8F6]" data-testid="stock-tab">
            <div className="flex items-center justify-between">
              <span className="text-base font-bold text-[#1C1917] flex items-center gap-2" style={{ fontFamily: "Outfit, sans-serif" }}><Award size={18} className="text-[#2C4C3B]" /> Stock & Inventory</span>
              <div className="flex gap-2">
                <button onClick={fetchStockStatus} className="text-xs text-[#78716C] flex items-center gap-1"><RefreshCw size={12} /> Refresh</button>
                <button onClick={async () => { setLinkingStock(true); try { const { data } = await axios.post(`${API}/pos/link-stock/${propertyId}`); toast.success(data.message); fetchStockStatus(); fetchMenu(); } catch (e) { toast.error("Failed"); } finally { setLinkingStock(false); } }}
                  disabled={linkingStock}
                  className="text-xs px-4 py-2 bg-[#2C4C3B] text-white rounded-xl font-bold hover:bg-[#1A3025] disabled:opacity-50 flex items-center gap-1"
                  data-testid="link-stock-btn">
                  {linkingStock ? <ArrowsClockwise size={12} className="animate-spin" /> : <Plus size={12} />}
                  {linkingStock ? "Linking..." : "Auto-Link Stock"}
                </button>
              </div>
            </div>

            {stockStatus && (
              <>
                {/* Summary Cards */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="bg-white rounded-2xl p-4 border border-[#E5E0D8] text-center">
                    <div className="text-2xl font-black text-[#1C1917]">{stockStatus.total_items}</div>
                    <div className="text-[10px] text-[#A8A29E] font-semibold">Menu Items</div>
                  </div>
                  <div className="bg-[#D1FAE5] rounded-2xl p-4 border border-[#6EE7B7] text-center">
                    <div className="text-2xl font-black text-[#065F46]">{stockStatus.total_linked}</div>
                    <div className="text-[10px] text-[#059669] font-semibold">Stock Linked</div>
                  </div>
                  <div className="bg-[#FEF3C7] rounded-2xl p-4 border border-[#FCD34D] text-center">
                    <div className="text-2xl font-black text-[#92400E]">{stockStatus.low_stock?.length || 0}</div>
                    <div className="text-[10px] text-[#B45309] font-semibold">Low Stock</div>
                  </div>
                  <div className="bg-[#FEE2E2] rounded-2xl p-4 border border-[#FCA5A5] text-center">
                    <div className="text-2xl font-black text-[#9B4837]">{stockStatus.out_of_stock?.length || 0}</div>
                    <div className="text-[10px] text-[#DC2626] font-semibold">Out of Stock</div>
                  </div>
                </div>

                {/* Alerts */}
                {(stockStatus.low_stock?.length > 0 || stockStatus.out_of_stock?.length > 0) && (
                  <div className="space-y-2">
                    {stockStatus.out_of_stock?.map((name, i) => (
                      <div key={i} className="bg-[#FEF2F2] border-2 border-[#FCA5A5] rounded-xl px-4 py-3 flex items-center justify-between">
                        <div className="flex items-center gap-2"><Ban size={14} className="text-[#DC2626]" /><span className="text-xs font-bold text-[#9B4837]">{name}</span></div>
                        <Badge className="text-[9px] bg-[#FEE2E2] text-[#DC2626] font-bold">OUT OF STOCK</Badge>
                      </div>
                    ))}
                    {stockStatus.low_stock?.map((item, i) => (
                      <div key={i} className="bg-[#FFFBEB] border-2 border-[#FCD34D] rounded-xl px-4 py-3 flex items-center justify-between">
                        <div className="flex items-center gap-2"><Lightning size={14} className="text-[#D4A373]" weight="fill" /><span className="text-xs font-bold text-[#92400E]">{item.name}</span></div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-[#B45309] font-bold">{item.quantity} left</span>
                          <span className="text-[9px] text-[#A8A29E]">min: {item.min_stock}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Stock Levels Table */}
                <div className="bg-white rounded-2xl border border-[#E5E0D8] overflow-hidden">
                  <div className="px-5 py-3 border-b border-[#EAE5DC] bg-[#F9F8F6]">
                    <span className="text-xs font-bold text-[#57534E] uppercase tracking-wider">Menu Item Stock Levels</span>
                  </div>
                  <div className="max-h-[300px] overflow-y-auto">
                    {stockStatus.items?.map(item => (
                      <div key={item.id} className="flex items-center justify-between px-5 py-2.5 border-b border-[#F0EBE1] last:border-0 hover:bg-[#F9F8F6]">
                        <div className="flex items-center gap-2">
                          <div className={`w-2 h-2 rounded-full ${item.stock_linked ? (item.stock_quantity <= 0 ? "bg-[#DC2626]" : item.stock_quantity <= (item.min_stock || 5) ? "bg-[#F59E0B]" : "bg-[#22C55E]") : "bg-[#D6D3D1]"}`} />
                          <span className="text-xs font-semibold text-[#1C1917]">{item.name}</span>
                          <span className="text-[9px] text-[#A8A29E]">{item.category}</span>
                        </div>
                        <div className="flex items-center gap-3">
                          {item.stock_linked ? (
                            <span className={`text-xs font-bold ${item.stock_quantity <= 0 ? "text-[#DC2626]" : item.stock_quantity <= (item.min_stock || 5) ? "text-[#F59E0B]" : "text-[#22C55E]"}`}>{item.stock_quantity} in stock</span>
                          ) : (
                            <span className="text-[10px] text-[#D6D3D1]">Not linked</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Stock Movements */}
                {stockMovements.length > 0 && (
                  <div className="bg-white rounded-2xl border border-[#E5E0D8] overflow-hidden">
                    <div className="px-5 py-3 border-b border-[#EAE5DC] bg-[#F9F8F6]">
                      <span className="text-xs font-bold text-[#57534E] uppercase tracking-wider">Recent Stock Movements</span>
                    </div>
                    <div className="max-h-[250px] overflow-y-auto">
                      {stockMovements.map(m => (
                        <div key={m.id} className="flex items-center justify-between px-5 py-2.5 border-b border-[#F0EBE1] last:border-0">
                          <div className="flex items-center gap-2">
                            <div className={`w-6 h-6 rounded-lg flex items-center justify-center text-[9px] font-bold ${m.type === "pos_sale" ? "bg-[#FEE2E2] text-[#DC2626]" : "bg-[#D1FAE5] text-[#22C55E]"}`}>
                              {m.quantity > 0 ? "+" : ""}{m.quantity}
                            </div>
                            <div>
                              <span className="text-xs font-semibold text-[#1C1917]">{m.item_name}</span>
                              <span className="text-[9px] text-[#A8A29E] block">{m.reference}</span>
                            </div>
                          </div>
                          <span className="text-[10px] text-[#A8A29E]">{m.created_at?.slice(11, 16)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
            {!stockStatus && <div className="text-center py-16 text-[#A8A29E] text-sm">Loading stock data...</div>}
          </div>
        )}

        {/* ========== QR CODE ========== */}
        {tab === "qr-code" && (
          <div className="flex-1 p-6 overflow-y-auto space-y-4 bg-[#F9F8F6]" data-testid="qr-code-tab">
            <div className="text-base font-bold text-[#1C1917] flex items-center gap-2 mb-2" style={{ fontFamily: "Outfit, sans-serif" }}><QrCode size={18} className="text-[#2C4C3B]" /> QR Code Self-Ordering</div>
            <p className="text-xs text-[#78716C]">Generate QR codes for each outlet. Guests scan to browse menu and order directly.</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {outlets.filter(o => o.active).map(outlet => {
                const qrUrl = `${process.env.REACT_APP_BACKEND_URL || ""}/qr-order/${propertyId}/${outlet.id}`;
                const kioskUrl = `${process.env.REACT_APP_BACKEND_URL || ""}/kiosk/${propertyId}/${outlet.id}`;
                const Icon = OUTLET_ICONS[outlet.icon] || UtensilsCrossed;
                return (
                  <div key={outlet.id} className="bg-white border border-[#E5E0D8] rounded-2xl p-5 shadow-sm" data-testid={`qr-outlet-${outlet.id}`}>
                    <div className="flex items-center gap-2 mb-3">
                      <div className="w-9 h-9 rounded-xl bg-[#2C4C3B] flex items-center justify-center"><Icon size={16} className="text-white" /></div>
                      <span className="text-sm font-bold text-[#1C1917]">{outlet.name}</span>
                    </div>
                    <div className="bg-[#F9F8F6] rounded-xl p-3 mb-3">
                      <div className="text-[10px] text-[#A8A29E] mb-1 font-medium">Guest Order URL</div>
                      <div className="text-[11px] font-mono text-[#2C4C3B] break-all">{qrUrl}</div>
                    </div>
                    <div className="flex gap-2">
                      <button onClick={() => { navigator.clipboard?.writeText(qrUrl); toast.success("Link copied!"); }} className="flex-1 text-xs py-2 bg-[#2C4C3B] text-white rounded-xl font-bold">Copy QR Link</button>
                      <button onClick={() => { navigator.clipboard?.writeText(kioskUrl); toast.success("Kiosk link copied!"); }} className="flex-1 text-xs py-2 bg-[#F0EBE1] text-[#57534E] rounded-xl font-bold">Kiosk Link</button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* ========== PAYMENT DIALOG ========== */}
      <Dialog open={showPay} onOpenChange={setShowPay}>
        <DialogContent className="max-w-sm" data-testid="payment-dialog">
          <DialogHeader><DialogTitle className="font-bold" style={{ fontFamily: "Outfit, sans-serif" }}>Process Payment</DialogTitle></DialogHeader>
          {payingOrder && (
            <div className="space-y-3">
              <div className="text-center py-3 bg-[#F9F8F6] rounded-2xl">
                <div className="text-4xl font-black text-[#1C1917]">£{payingOrder.total}</div>
                <div className="text-xs text-[#A8A29E] mt-1">{payingOrder.order_number} · {payingOrder.items?.length || 0} items</div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { value: "card", label: "Card", icon: CreditCard, color: "#2C4C3B" },
                  { value: "cash", label: "Cash", icon: Banknote, color: "#065F46" },
                  { value: "room_charge", label: "Room Charge", icon: Building, color: "#1E40AF" },
                  { value: "terminal", label: "Card Terminal", icon: CreditCard, color: "#6B21A8" },
                ].map(m => (
                  <button key={m.value} onClick={() => setPayMethod(m.value)}
                    className={`flex items-center gap-2 p-3.5 rounded-xl text-xs font-bold border-2 transition-all ${
                      payMethod === m.value ? "text-white shadow-md" : "border-[#E5E0D8] text-[#57534E] hover:border-[#D4A373]"
                    }`} style={payMethod === m.value ? { backgroundColor: m.color, borderColor: m.color } : {}} data-testid={`pay-method-${m.value}`}>
                    <m.icon size={16} /> {m.label}
                  </button>
                ))}
              </div>
              {payMethod === "room_charge" && <Input value={roomNumber} onChange={e => setRoomNumber(e.target.value)} placeholder="Room Number" className="h-9 text-sm" />}
              <div>
                <label className="text-[11px] font-bold text-[#57534E] mb-1.5 block">Tip</label>
                <div className="flex gap-1.5">
                  {[0, 5, 10, 15, 20].map(t => (
                    <button key={t} onClick={() => setTip(t === 0 ? 0 : Math.round(payingOrder.total * t / 100 * 100) / 100)}
                      className={`flex-1 text-[10px] py-2 rounded-xl font-bold transition-all ${tip === Math.round(payingOrder.total * t / 100 * 100) / 100 && t > 0 ? "bg-[#D4A373] text-white" : "bg-[#F0EBE1] text-[#57534E]"}`}>
                      {t === 0 ? "None" : `${t}%`}
                    </button>
                  ))}
                </div>
                {tip > 0 && <div className="text-[10px] text-[#A8A29E] mt-1.5 text-right">Tip: £{tip.toFixed(2)} · Total: £{(payingOrder.total + tip).toFixed(2)}</div>}
              </div>
              <button onClick={payOrder}
                className="w-full bg-[#2C4C3B] text-white py-3.5 rounded-xl text-sm font-black hover:bg-[#1A3025] transition-all flex items-center justify-center gap-2 shadow-lg"
                data-testid="confirm-pay-btn">
                <CheckCircle size={16} weight="fill" /> Pay £{(payingOrder.total + tip).toFixed(2)}
              </button>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* ========== SPLIT BILL DIALOG ========== */}
      <Dialog open={showSplit} onOpenChange={setShowSplit}>
        <DialogContent className="max-w-sm" data-testid="split-dialog">
          <DialogHeader><DialogTitle className="font-bold flex items-center gap-2" style={{ fontFamily: "Outfit, sans-serif" }}><SplitSquareHorizontal size={18} /> Split Bill</DialogTitle></DialogHeader>
          {payingOrder && (
            <div className="space-y-4">
              <div className="text-center py-3 bg-[#F9F8F6] rounded-2xl">
                <div className="text-2xl font-black text-[#1C1917]">£{payingOrder.total}</div>
                <div className="text-xs text-[#A8A29E]">{payingOrder.order_number}</div>
              </div>
              <div>
                <label className="text-[11px] font-bold text-[#57534E] mb-1.5 block">Split between</label>
                <div className="flex gap-1.5">
                  {[2, 3, 4, 5, 6].map(n => (
                    <button key={n} onClick={() => setSplitCount(n)}
                      className={`flex-1 py-2.5 rounded-xl text-sm font-black transition-all ${splitCount === n ? "bg-[#2C4C3B] text-white shadow-md" : "bg-[#F0EBE1] text-[#57534E]"}`}>{n}</button>
                  ))}
                </div>
              </div>
              <div className="bg-[#D1FAE5] rounded-2xl p-4 text-center">
                <div className="text-[10px] text-[#065F46] font-semibold uppercase tracking-wider">Each person pays</div>
                <div className="text-3xl font-black text-[#065F46] mt-1">£{(payingOrder.total / splitCount).toFixed(2)}</div>
              </div>
              <button onClick={() => { toast.success(`Bill split ${splitCount} ways — £${(payingOrder.total / splitCount).toFixed(2)} each`); setShowSplit(false); }}
                className="w-full bg-[#2C4C3B] text-white py-3 rounded-xl text-sm font-bold" data-testid="confirm-split-btn">
                Confirm Split — {splitCount} ways
              </button>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* ========== RECEIPT PREVIEW DIALOG ========== */}
      <Dialog open={showReceipt} onOpenChange={setShowReceipt}>
        <DialogContent className="max-w-xs" data-testid="receipt-dialog">
          <DialogHeader><DialogTitle className="font-bold" style={{ fontFamily: "Outfit, sans-serif" }}>Receipt Preview</DialogTitle></DialogHeader>
          {receiptOrder && (
            <div className="space-y-3">
              <div className="bg-[#F9F8F6] rounded-xl p-4 font-mono text-xs space-y-1.5 border border-dashed border-[#D6D3D1]">
                <div className="text-center font-bold text-sm mb-2">{receiptOrder.outlet_name || "Hotel"}</div>
                <div className="text-center text-[10px] text-[#A8A29E]">{new Date(receiptOrder.created_at).toLocaleString("en-GB")}</div>
                <div className="border-t border-dashed border-[#D6D3D1] my-2" />
                <div className="text-[10px] text-[#A8A29E]">Order: {receiptOrder.order_number} · Table: {receiptOrder.table_number || "—"}</div>
                <div className="border-t border-dashed border-[#D6D3D1] my-2" />
                {receiptOrder.items?.map((item, i) => (
                  <div key={i} className="flex justify-between"><span>{item.quantity}x {item.name}</span><span>£{(item.price * item.quantity).toFixed(2)}</span></div>
                ))}
                <div className="border-t border-dashed border-[#D6D3D1] my-2" />
                <div className="flex justify-between font-bold text-sm"><span>TOTAL</span><span>£{receiptOrder.total}</span></div>
                {receiptOrder.payment_method && <div className="text-[10px] text-[#A8A29E] text-center mt-1">Paid by {receiptOrder.payment_method}</div>}
                <div className="text-center text-[10px] text-[#A8A29E] mt-2">Thank you!</div>
              </div>
              <button onClick={async () => {
                const email = prompt("Guest email for receipt:");
                if (email) { try { await axios.post(`${API}/pos/orders/${receiptOrder.id}/receipt`, { email }); toast.success("Receipt emailed!"); setShowReceipt(false); } catch { toast.error("Failed"); } }
              }} className="w-full bg-[#2C4C3B] text-white py-2.5 rounded-xl text-xs font-bold" data-testid="email-receipt-btn">Email Receipt</button>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* ========== VOID ORDER DIALOG ========== */}
      <Dialog open={showVoid} onOpenChange={setShowVoid}>
        <DialogContent className="max-w-sm" data-testid="void-dialog">
          <DialogHeader><DialogTitle className="font-bold text-[#9B4837] flex items-center gap-2" style={{ fontFamily: "Outfit, sans-serif" }}><Ban size={18} /> Void Order</DialogTitle></DialogHeader>
          {voidOrder && (
            <div className="space-y-3">
              <div className="bg-[#FEF2F2] rounded-xl p-4 text-center">
                <div className="text-xl font-black text-[#9B4837]">{voidOrder.order_number}</div>
                <div className="text-sm font-bold text-[#9B4837] mt-1">£{voidOrder.total}</div>
              </div>
              <div>
                <label className="text-[11px] font-bold text-[#57534E] mb-1 block">Void Reason</label>
                <Input value={voidReason} onChange={e => setVoidReason(e.target.value)} placeholder="e.g. Customer changed mind, wrong order..." className="text-sm" data-testid="void-reason" />
              </div>
              <button onClick={voidOrderAction}
                className="w-full bg-[#9B4837] text-white py-3 rounded-xl text-sm font-bold hover:bg-[#7F3A2D]" data-testid="confirm-void-btn">
                Void Order
              </button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
