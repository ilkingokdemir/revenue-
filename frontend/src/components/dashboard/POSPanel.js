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
  CurrencyGbp, Lightning, Star, CheckCircle,
} from "@phosphor-icons/react";
import { UtensilsCrossed, Wine, Bed, Sparkles, Gift, ShoppingCart, BarChart3, Clock, CreditCard, Banknote, Building, Users, ChefHat, LayoutGrid, QrCode, Percent, Award } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const OUTLET_ICONS = {
  utensils: UtensilsCrossed, wine: Wine, bell: Bed, swim: Wine, spa: Sparkles, gift: Gift,
};

const CATEGORY_COLORS = {
  Starters: "bg-amber-50 text-amber-700 border-amber-200",
  Mains: "bg-red-50 text-red-700 border-red-200",
  Desserts: "bg-pink-50 text-pink-700 border-pink-200",
  "Soft Drinks": "bg-blue-50 text-blue-700 border-blue-200",
  "Hot Drinks": "bg-orange-50 text-orange-700 border-orange-200",
  Wine: "bg-purple-50 text-purple-700 border-purple-200",
  Beer: "bg-amber-50 text-amber-700 border-amber-200",
  Cocktails: "bg-violet-50 text-violet-700 border-violet-200",
  Spa: "bg-teal-50 text-teal-700 border-teal-200",
  "Room Service": "bg-indigo-50 text-indigo-700 border-indigo-200",
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

  const [happyHours, setHappyHours] = useState([]);
  const [showHappyForm, setShowHappyForm] = useState(false);
  const [newHH, setNewHH] = useState({ name: "", start_hour: 16, end_hour: 19, discount_pct: 20, categories: [] });

  const propertyId = (propActivePropertyId && propActivePropertyId !== "all") ? propActivePropertyId : (properties?.[0]?.id || "aldgate-flats");

  const fetchOutlets = useCallback(async () => {
    const { data } = await axios.get(`${API}/pos/outlets/${propertyId}`);
    setOutlets(data);
    if (data.length && !activeOutlet) setActiveOutlet(data[0]);
  }, [propertyId, activeOutlet]);

  const fetchMenu = useCallback(async () => {
    const { data } = await axios.get(`${API}/pos/menu/${propertyId}`);
    setMenu(data);
  }, [propertyId]);

  const fetchOrders = useCallback(async () => {
    const today = new Date().toISOString().slice(0, 10);
    const { data } = await axios.get(`${API}/pos/orders/${propertyId}?date=${today}`);
    setOrders(data);
  }, [propertyId]);

  const fetchKitchen = useCallback(async () => {
    const { data } = await axios.get(`${API}/pos/kitchen/${propertyId}`);
    setKitchenOrders(data);
  }, [propertyId]);

  const fetchReports = useCallback(async () => {
    const { data } = await axios.get(`${API}/pos/reports/${propertyId}`);
    setReports(data);
  }, [propertyId]);

  const fetchHappyHours = useCallback(async () => {
    const { data } = await axios.get(`${API}/pos/happy-hours/${propertyId}`);
    setHappyHours(data);
  }, [propertyId]);

  const fetchTables = useCallback(async () => {
    if (activeOutlet?.id) {
      const { data } = await axios.get(`${API}/pos/tables/${activeOutlet.id}`);
      setTables(data);
    }
  }, [activeOutlet]);

  useEffect(() => {
    setLoading(true);
    Promise.all([fetchOutlets(), fetchMenu()]).then(() => setLoading(false));
  }, [fetchOutlets, fetchMenu]);

  useEffect(() => { if (tab === "orders") fetchOrders(); }, [tab, fetchOrders]);
  useEffect(() => { if (tab === "kitchen") fetchKitchen(); }, [tab, fetchKitchen]);
  useEffect(() => { if (tab === "reports") fetchReports(); }, [tab, fetchReports]);
  useEffect(() => { if (tab === "happy-hour") fetchHappyHours(); }, [tab, fetchHappyHours]);
  useEffect(() => { if (tab === "tables") fetchTables(); }, [tab, fetchTables]);

  const addToCart = (item) => {
    setCart(prev => {
      const existing = prev.find(c => c.id === item.id);
      if (existing) return prev.map(c => c.id === item.id ? { ...c, quantity: c.quantity + 1 } : c);
      return [...prev, { ...item, quantity: 1 }];
    });
  };

  const updateQty = (itemId, delta) => {
    setCart(prev => prev.map(c => c.id === itemId ? { ...c, quantity: Math.max(0, c.quantity + delta) } : c).filter(c => c.quantity > 0));
  };

  const removeFromCart = (itemId) => setCart(prev => prev.filter(c => c.id !== itemId));

  const cartTotal = cart.reduce((s, c) => s + c.price * c.quantity, 0);
  const cartVat = cart.reduce((s, c) => s + (c.price * c.quantity * (c.vat_rate || 20) / 100), 0);

  const placeOrder = async () => {
    if (!cart.length) return toast.error("Add items to the order");
    try {
      const { data } = await axios.post(`${API}/pos/orders`, {
        property_id: propertyId,
        outlet_id: activeOutlet?.id || "",
        outlet_name: activeOutlet?.name || "",
        order_type: orderType,
        table_number: tableNum,
        covers,
        guest_name: guestName,
        room_number: roomNumber,
        items: cart.map(c => ({
          id: c.id, name: c.name, price: c.price, cost: c.cost || 0,
          quantity: c.quantity, vat_rate: c.vat_rate || 20,
          category: c.category, stock_product_id: c.stock_product_id || "",
        })),
      });
      toast.success(`Order ${data.order_number} placed!`);
      setCart([]);
      setTableNum("");
      setGuestName("");
      setRoomNumber("");
      fetchOrders();
    } catch (e) { toast.error("Failed to place order"); }
  };

  const payOrder = async () => {
    if (!payingOrder) return;
    try {
      await axios.post(`${API}/pos/orders/${payingOrder.id}/pay`, {
        payment_method: payMethod, tip,
      });
      toast.success(`Order paid via ${payMethod}`);
      setShowPay(false);
      setPayingOrder(null);
      setTip(0);
      fetchOrders();
    } catch (e) { toast.error("Payment failed"); }
  };

  const updateKitchenStatus = async (orderId, status) => {
    await axios.post(`${API}/pos/kitchen/${orderId}/status`, { status });
    fetchKitchen();
    toast.success(`Order ${status}`);
  };

  const categories = ["all", ...new Set(menu.map(m => m.category))];
  const filteredMenu = menu.filter(m => {
    if (activeCategory !== "all" && m.category !== activeCategory) return false;
    if (menuSearch && !m.name.toLowerCase().includes(menuSearch.toLowerCase())) return false;
    return m.available;
  });

  const tabs = [
    { id: "terminal", label: "POS Terminal", icon: ShoppingCart },
    { id: "tables", label: "Tables", icon: LayoutGrid },
    { id: "kitchen", label: "Kitchen", icon: ChefHat },
    { id: "orders", label: "Orders", icon: Receipt },
    { id: "reports", label: "Reports", icon: BarChart3 },
    { id: "happy-hour", label: "Happy Hour", icon: Percent },
    { id: "qr-code", label: "QR Order", icon: QrCode },
  ];

  if (loading) return <div className="flex items-center justify-center h-96"><ArrowsClockwise size={24} className="animate-spin text-stone-300" /></div>;

  return (
    <div className="h-[calc(100vh-0px)] flex flex-col" data-testid="pos-panel">
      {/* Header */}
      <div className="border-b border-stone-200 bg-white px-5 py-3 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-orange-100 flex items-center justify-center">
            <UtensilsCrossed size={18} className="text-orange-700" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-stone-900">Hotel POS</h2>
            <p className="text-xs text-stone-400">Point of Sale — Restaurant, Bar, Room Service, Spa</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {outlets.map(o => {
            const Icon = OUTLET_ICONS[o.icon] || UtensilsCrossed;
            return (
              <button key={o.id} onClick={() => setActiveOutlet(o)}
                className={`text-[11px] px-3 py-1.5 rounded-lg flex items-center gap-1.5 font-medium transition-colors ${
                  activeOutlet?.id === o.id ? "bg-orange-600 text-white" : "bg-stone-100 text-stone-600 hover:bg-stone-200"
                }`} data-testid={`outlet-${o.id}`}>
                <Icon size={13} /> {o.name}
              </button>
            );
          })}
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-stone-200 bg-white px-5 flex gap-1 flex-shrink-0">
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-medium border-b-2 ${
              tab === t.id ? "border-orange-500 text-orange-700" : "border-transparent text-stone-400 hover:text-stone-600"
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
            <div className="flex-1 flex flex-col bg-stone-50 overflow-hidden">
              <div className="p-3 border-b border-stone-200 bg-white space-y-2">
                <Input value={menuSearch} onChange={e => setMenuSearch(e.target.value)} placeholder="Search menu..." className="h-8 text-xs" data-testid="menu-search" />
                <div className="flex gap-1 flex-wrap">
                  {categories.map(cat => (
                    <button key={cat} onClick={() => setActiveCategory(cat)}
                      className={`text-[10px] px-2 py-1 rounded-full transition-colors ${activeCategory === cat ? "bg-orange-600 text-white" : "bg-stone-100 text-stone-500 hover:bg-stone-200"}`}
                      data-testid={`cat-${cat}`}>{cat === "all" ? "All" : cat}</button>
                  ))}
                </div>
              </div>
              <ScrollArea className="flex-1 p-3">
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
                  {filteredMenu.map(item => (
                    <motion.button key={item.id} whileTap={{ scale: 0.95 }} onClick={() => addToCart(item)}
                      className={`text-left p-3 rounded-xl border transition-colors hover:shadow-sm ${CATEGORY_COLORS[item.category] || "bg-white border-stone-200 text-stone-700"}`}
                      data-testid={`menu-item-${item.id}`}>
                      <div className="text-xs font-semibold truncate">{item.name}</div>
                      <div className="flex items-center justify-between mt-1">
                        <span className="text-sm font-bold">£{item.price.toFixed(2)}</span>
                        <span className="text-[9px] opacity-60">{item.category}</span>
                      </div>
                    </motion.button>
                  ))}
                </div>
              </ScrollArea>
            </div>

            {/* Cart / Order Panel */}
            <div className="w-[340px] border-l border-stone-200 bg-white flex flex-col flex-shrink-0" data-testid="cart-panel">
              <div className="p-3 border-b border-stone-100 space-y-2">
                <div className="flex gap-1">
                  {[
                    { value: "dine_in", label: "Dine In" },
                    { value: "takeaway", label: "Takeaway" },
                    { value: "room_service", label: "Room Service" },
                  ].map(t => (
                    <button key={t.value} onClick={() => setOrderType(t.value)}
                      className={`flex-1 text-[10px] py-1.5 rounded-lg font-medium ${orderType === t.value ? "bg-orange-600 text-white" : "bg-stone-100 text-stone-500"}`}>
                      {t.label}
                    </button>
                  ))}
                </div>
                <div className="grid grid-cols-2 gap-1.5">
                  {orderType === "dine_in" && <Input value={tableNum} onChange={e => setTableNum(e.target.value)} placeholder="Table #" className="h-7 text-[11px]" data-testid="table-input" />}
                  {orderType === "room_service" && <Input value={roomNumber} onChange={e => setRoomNumber(e.target.value)} placeholder="Room #" className="h-7 text-[11px]" data-testid="room-input" />}
                  <Input value={guestName} onChange={e => setGuestName(e.target.value)} placeholder="Guest name" className="h-7 text-[11px]" data-testid="guest-name-input" />
                  <Input type="number" value={covers} onChange={e => setCovers(parseInt(e.target.value) || 1)} placeholder="Covers" className="h-7 text-[11px]" min={1} />
                </div>
              </div>

              <ScrollArea className="flex-1">
                {cart.length === 0 ? (
                  <div className="p-8 text-center text-xs text-stone-400">Tap menu items to add</div>
                ) : (
                  <div className="p-2 space-y-1">
                    <AnimatePresence>
                      {cart.map(item => (
                        <motion.div key={item.id} initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}
                          className="flex items-center gap-2 bg-stone-50 rounded-lg px-2.5 py-2" data-testid={`cart-item-${item.id}`}>
                          <div className="flex-1 min-w-0">
                            <span className="text-xs font-medium text-stone-800 block truncate">{item.name}</span>
                            <span className="text-[10px] text-stone-400">£{item.price.toFixed(2)} each</span>
                          </div>
                          <div className="flex items-center gap-1">
                            <button onClick={() => updateQty(item.id, -1)} className="w-6 h-6 rounded-full bg-stone-200 flex items-center justify-center text-stone-600 hover:bg-stone-300"><Minus size={10} weight="bold" /></button>
                            <span className="text-xs font-bold w-5 text-center">{item.quantity}</span>
                            <button onClick={() => updateQty(item.id, 1)} className="w-6 h-6 rounded-full bg-orange-100 flex items-center justify-center text-orange-600 hover:bg-orange-200"><Plus size={10} weight="bold" /></button>
                          </div>
                          <span className="text-xs font-bold text-stone-800 w-14 text-right">£{(item.price * item.quantity).toFixed(2)}</span>
                          <button onClick={() => removeFromCart(item.id)} className="text-stone-300 hover:text-red-400"><X size={12} /></button>
                        </motion.div>
                      ))}
                    </AnimatePresence>
                  </div>
                )}
              </ScrollArea>

              {cart.length > 0 && (
                <div className="p-3 border-t border-stone-200 space-y-2">
                  <div className="flex justify-between text-xs text-stone-500"><span>Subtotal</span><span>£{cartTotal.toFixed(2)}</span></div>
                  <div className="flex justify-between text-xs text-stone-500"><span>VAT</span><span>£{cartVat.toFixed(2)}</span></div>
                  <div className="flex justify-between text-sm font-bold text-stone-900"><span>Total</span><span>£{(cartTotal + cartVat).toFixed(2)}</span></div>
                  <button onClick={placeOrder}
                    className="w-full bg-orange-600 text-white py-2.5 rounded-xl text-sm font-semibold hover:bg-orange-700 transition-colors flex items-center justify-center gap-2"
                    data-testid="place-order-btn">
                    <Receipt size={16} weight="fill" /> Place Order
                  </button>
                </div>
              )}
            </div>
          </>
        )}

        {/* ========== TABLES ========== */}
        {tab === "tables" && (
          <div className="flex-1 p-6 overflow-y-auto" data-testid="tables-tab">
            <div className="flex items-center justify-between mb-4">
              <span className="text-sm font-semibold text-stone-800">{activeOutlet?.name} — Table Layout</span>
              <button onClick={fetchTables} className="text-xs text-stone-500 hover:text-stone-700"><ArrowsClockwise size={14} /></button>
            </div>
            <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-6 gap-3">
              {tables.map(t => (
                <div key={t.number} onClick={() => { if (t.order) { setPayingOrder(t.order); setShowPay(true); } else { setTableNum(String(t.number)); setTab("terminal"); } }}
                  className={`rounded-xl p-4 text-center cursor-pointer border-2 transition-all ${
                    t.status === "occupied" ? "bg-orange-50 border-orange-300 hover:border-orange-400" : "bg-white border-stone-200 hover:border-emerald-300"
                  }`} data-testid={`table-${t.number}`}>
                  <div className={`text-lg font-bold ${t.status === "occupied" ? "text-orange-700" : "text-stone-400"}`}>{t.number}</div>
                  <div className={`text-[10px] mt-1 font-medium ${t.status === "occupied" ? "text-orange-600" : "text-emerald-600"}`}>
                    {t.status === "occupied" ? `£${t.order?.total || 0}` : "Available"}
                  </div>
                  {t.order && <div className="text-[9px] text-stone-400 mt-0.5">{t.order.items?.length || 0} items</div>}
                </div>
              ))}
              {tables.length === 0 && <div className="col-span-6 text-center py-10 text-stone-400 text-sm">No tables configured for this outlet</div>}
            </div>
          </div>
        )}

        {/* ========== KITCHEN ========== */}
        {tab === "kitchen" && (
          <div className="flex-1 p-4 overflow-y-auto" data-testid="kitchen-tab">
            <div className="flex items-center justify-between mb-4">
              <span className="text-sm font-semibold text-stone-800 flex items-center gap-2"><ChefHat size={16} /> Kitchen Display</span>
              <button onClick={fetchKitchen} className="text-xs text-stone-500"><ArrowsClockwise size={14} /></button>
            </div>
            {kitchenOrders.length === 0 ? (
              <div className="text-center py-16 text-stone-400">No pending kitchen orders</div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {kitchenOrders.map(o => (
                  <div key={o.id} className={`rounded-xl border-2 p-4 ${o.kitchen_status === "new" ? "border-red-300 bg-red-50" : "border-amber-300 bg-amber-50"}`} data-testid={`kitchen-order-${o.id}`}>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-bold text-stone-800">{o.order_number}</span>
                      <Badge className={`text-[9px] ${o.kitchen_status === "new" ? "bg-red-100 text-red-700" : "bg-amber-100 text-amber-700"}`}>{o.kitchen_status}</Badge>
                    </div>
                    <div className="text-[10px] text-stone-500 mb-2">
                      {o.outlet_name} · Table {o.table_number || "—"} · {new Date(o.created_at).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}
                    </div>
                    <div className="space-y-1 mb-3">
                      {o.items?.map((item, i) => (
                        <div key={i} className="flex justify-between text-xs">
                          <span className="text-stone-700">{item.quantity}x {item.name}</span>
                        </div>
                      ))}
                    </div>
                    {o.notes && <div className="text-[10px] text-red-600 mb-2">Note: {o.notes}</div>}
                    <div className="flex gap-1.5">
                      {o.kitchen_status === "new" && (
                        <button onClick={() => updateKitchenStatus(o.id, "preparing")} className="flex-1 text-[10px] py-1.5 bg-amber-500 text-white rounded-lg font-medium" data-testid={`start-${o.id}`}>Start</button>
                      )}
                      {o.kitchen_status === "preparing" && (
                        <button onClick={() => updateKitchenStatus(o.id, "ready")} className="flex-1 text-[10px] py-1.5 bg-emerald-500 text-white rounded-lg font-medium" data-testid={`ready-${o.id}`}>Ready</button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ========== ORDERS ========== */}
        {tab === "orders" && (
          <div className="flex-1 p-4 overflow-y-auto" data-testid="orders-tab">
            <div className="flex items-center justify-between mb-4">
              <span className="text-sm font-semibold text-stone-800">Today's Orders ({orders.length})</span>
              <button onClick={fetchOrders} className="text-xs text-stone-500"><ArrowsClockwise size={14} /></button>
            </div>
            <div className="space-y-2">
              {orders.map(o => (
                <div key={o.id} className="bg-white border border-stone-200 rounded-xl p-3 flex items-center justify-between" data-testid={`order-${o.id}`}>
                  <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${o.payment_status === "paid" ? "bg-emerald-50" : "bg-amber-50"}`}>
                      <Receipt size={16} className={o.payment_status === "paid" ? "text-emerald-600" : "text-amber-600"} />
                    </div>
                    <div>
                      <div className="text-xs font-semibold text-stone-800">{o.order_number} — {o.outlet_name}</div>
                      <div className="text-[10px] text-stone-400">
                        {o.order_type?.replace(/_/g, " ")} · Table {o.table_number || "—"} · {o.items?.length || 0} items · {o.covers} covers
                        {o.guest_name && ` · ${o.guest_name}`}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold text-stone-800">£{o.total}</span>
                    <Badge className={`text-[9px] ${o.payment_status === "paid" ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>{o.payment_status}</Badge>
                    {o.payment_status === "pending" && (
                      <button onClick={() => { setPayingOrder(o); setShowPay(true); }}
                        className="text-[10px] px-2 py-1 bg-emerald-50 text-emerald-700 rounded font-medium" data-testid={`pay-${o.id}`}>Pay</button>
                    )}
                    {o.payment_status === "paid" && !o.receipt_sent && (
                      <button onClick={async () => {
                        const email = prompt("Guest email for receipt:");
                        if (email) {
                          try { await axios.post(`${API}/pos/orders/${o.id}/receipt`, { email }); toast.success("Receipt sent!"); fetchOrders(); } catch (e) { toast.error("Failed"); }
                        }
                      }} className="text-[10px] px-2 py-1 bg-blue-50 text-blue-600 rounded font-medium" data-testid={`receipt-${o.id}`}>Receipt</button>
                    )}
                    {o.receipt_sent && <span className="text-[9px] text-stone-400">Sent</span>}
                  </div>
                </div>
              ))}
              {orders.length === 0 && <div className="text-center py-16 text-stone-400 text-sm">No orders today</div>}
            </div>
          </div>
        )}

        {/* ========== REPORTS ========== */}
        {tab === "reports" && reports && (
          <div className="flex-1 p-6 overflow-y-auto space-y-4" data-testid="reports-tab">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-center">
                <div className="text-2xl font-bold text-emerald-700">£{reports.total_revenue?.toLocaleString()}</div>
                <div className="text-[10px] text-emerald-600">Revenue</div>
              </div>
              <div className="bg-white border border-stone-200 rounded-xl p-4 text-center">
                <div className="text-2xl font-bold text-stone-800">{reports.total_orders}</div>
                <div className="text-[10px] text-stone-500">Orders ({reports.total_covers} covers)</div>
              </div>
              <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-center">
                <div className="text-2xl font-bold text-blue-700">£{reports.avg_check}</div>
                <div className="text-[10px] text-blue-600">Avg Check</div>
              </div>
              <div className="bg-purple-50 border border-purple-200 rounded-xl p-4 text-center">
                <div className="text-2xl font-bold text-purple-700">{reports.gross_margin}%</div>
                <div className="text-[10px] text-purple-600">Gross Margin</div>
              </div>
            </div>

            {/* By Outlet */}
            {Object.keys(reports.by_outlet || {}).length > 0 && (
              <div className="bg-white rounded-xl border border-stone-200 p-4">
                <div className="text-sm font-semibold text-stone-800 mb-2">Revenue by Outlet</div>
                {Object.entries(reports.by_outlet).sort((a, b) => b[1].revenue - a[1].revenue).map(([name, data]) => (
                  <div key={name} className="flex items-center justify-between text-xs py-1.5 border-b border-stone-50">
                    <span className="text-stone-600">{name}</span>
                    <div className="flex items-center gap-3">
                      <span className="text-stone-400">{data.orders} orders · {data.covers} covers</span>
                      <span className="font-bold text-stone-800">£{data.revenue?.toLocaleString()}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Top Items */}
            {reports.top_items?.length > 0 && (
              <div className="bg-white rounded-xl border border-stone-200 p-4">
                <div className="text-sm font-semibold text-stone-800 mb-2">Top Selling Items</div>
                {reports.top_items.map((item, i) => (
                  <div key={i} className="flex items-center justify-between text-xs py-1.5 border-b border-stone-50">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] text-stone-400 w-5">{i + 1}.</span>
                      <span className="text-stone-700 font-medium">{item.name}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-stone-400">{item.qty} sold</span>
                      <span className="font-bold text-stone-800">£{item.revenue?.toLocaleString()}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* By Server */}
            {Object.keys(reports.by_server || {}).length > 0 && (
              <div className="bg-white rounded-xl border border-stone-200 p-4">
                <div className="text-sm font-semibold text-stone-800 mb-2">Server Performance</div>
                {Object.entries(reports.by_server).sort((a, b) => b[1].revenue - a[1].revenue).map(([name, data]) => (
                  <div key={name} className="flex items-center justify-between text-xs py-1.5 border-b border-stone-50">
                    <span className="text-stone-600 flex items-center gap-1"><Users size={12} /> {name}</span>
                    <div className="flex items-center gap-3">
                      <span className="text-stone-400">{data.orders} orders</span>
                      <span className="text-amber-600">£{data.tips} tips</span>
                      <span className="font-bold text-stone-800">£{data.revenue?.toLocaleString()}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {reports.total_orders === 0 && <div className="text-center py-10 text-stone-400 text-sm">No sales data for today</div>}
          </div>
        )}

        {/* ========== HAPPY HOUR ========== */}
        {tab === "happy-hour" && (
          <div className="flex-1 p-6 overflow-y-auto space-y-4" data-testid="happy-hour-tab">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-stone-800 flex items-center gap-2"><Percent size={16} /> Happy Hour & Promotions</span>
              <button onClick={() => setShowHappyForm(true)} className="text-xs px-3 py-1.5 bg-orange-500 text-white rounded-lg font-medium" data-testid="new-happy-hour-btn">
                <Plus size={12} className="inline mr-1" /> New Promotion
              </button>
            </div>
            {happyHours.map(hh => (
              <div key={hh.id} className={`bg-white border rounded-xl p-4 ${hh.enabled ? "border-amber-200" : "border-stone-200 opacity-60"}`} data-testid={`hh-${hh.id}`}>
                <div className="flex items-center justify-between mb-2">
                  <div>
                    <span className="text-sm font-semibold text-stone-800">{hh.name}</span>
                    <span className="text-[10px] text-amber-600 ml-2 bg-amber-50 px-1.5 py-0.5 rounded-full">{hh.discount_pct}% off</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge className={`text-[9px] ${hh.enabled ? "bg-emerald-100 text-emerald-700" : "bg-stone-100 text-stone-500"}`}>{hh.enabled ? "Active" : "Inactive"}</Badge>
                    <button onClick={async () => { await axios.put(`${API}/pos/happy-hours/${hh.id}`, { enabled: !hh.enabled }); fetchHappyHours(); }}
                      className="text-[10px] text-blue-600 hover:text-blue-700" data-testid={`toggle-hh-${hh.id}`}>
                      {hh.enabled ? "Disable" : "Enable"}
                    </button>
                  </div>
                </div>
                <div className="text-xs text-stone-500 space-y-1">
                  <div className="flex items-center gap-2">
                    <Clock size={12} /> {hh.start_hour}:00 — {hh.end_hour}:00
                    <span className="text-[10px] text-stone-400">({hh.days?.join(", ")})</span>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {hh.categories?.map(c => (
                      <span key={c} className="text-[9px] bg-stone-100 text-stone-600 px-1.5 py-0.5 rounded-full">{c}</span>
                    ))}
                    {(!hh.categories || hh.categories.length === 0) && <span className="text-[9px] text-stone-400">All categories</span>}
                  </div>
                </div>
              </div>
            ))}
            {happyHours.length === 0 && <div className="text-center py-10 text-stone-400 text-sm">No promotions configured</div>}

            <Dialog open={showHappyForm} onOpenChange={setShowHappyForm}>
              <DialogContent className="max-w-md"><DialogHeader><DialogTitle>New Happy Hour</DialogTitle></DialogHeader>
                <div className="space-y-2">
                  <Input placeholder="Promotion name" value={newHH.name} onChange={e => setNewHH(p => ({...p, name: e.target.value}))} data-testid="hh-name" />
                  <div className="grid grid-cols-3 gap-2">
                    <div><label className="text-[10px] text-stone-500">Start Hour</label><Input type="number" min={0} max={23} value={newHH.start_hour} onChange={e => setNewHH(p => ({...p, start_hour: parseInt(e.target.value) || 0}))} /></div>
                    <div><label className="text-[10px] text-stone-500">End Hour</label><Input type="number" min={0} max={23} value={newHH.end_hour} onChange={e => setNewHH(p => ({...p, end_hour: parseInt(e.target.value) || 0}))} /></div>
                    <div><label className="text-[10px] text-stone-500">Discount %</label><Input type="number" min={1} max={100} value={newHH.discount_pct} onChange={e => setNewHH(p => ({...p, discount_pct: parseInt(e.target.value) || 0}))} /></div>
                  </div>
                  <button onClick={async () => {
                    if (!newHH.name) return toast.error("Name required");
                    await axios.post(`${API}/pos/happy-hours`, { ...newHH, property_id: propertyId });
                    setShowHappyForm(false); fetchHappyHours(); toast.success("Promotion created");
                  }} className="w-full text-xs py-2 bg-orange-500 text-white rounded-lg font-medium" data-testid="save-hh-btn">Create Promotion</button>
                </div>
              </DialogContent>
            </Dialog>
          </div>
        )}

        {/* ========== QR CODE ========== */}
        {tab === "qr-code" && (
          <div className="flex-1 p-6 overflow-y-auto space-y-4" data-testid="qr-code-tab">
            <div className="text-sm font-semibold text-stone-800 flex items-center gap-2 mb-4"><QrCode size={16} /> QR Code Self-Ordering</div>
            <p className="text-xs text-stone-500 mb-4">Generate QR codes for each outlet. Guests scan with their phone to browse the menu and place orders directly — no app download needed.</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {outlets.filter(o => o.active).map(outlet => {
                const baseUrl = process.env.REACT_APP_BACKEND_URL || "";
                const qrUrl = `${baseUrl}/qr-order/${propertyId}/${outlet.id}`;
                const Icon = OUTLET_ICONS[outlet.icon] || UtensilsCrossed;
                return (
                  <div key={outlet.id} className="bg-white border border-stone-200 rounded-xl p-4" data-testid={`qr-outlet-${outlet.id}`}>
                    <div className="flex items-center gap-2 mb-3">
                      <div className="w-8 h-8 rounded-lg bg-orange-50 flex items-center justify-center"><Icon size={16} className="text-orange-600" /></div>
                      <span className="text-sm font-semibold text-stone-800">{outlet.name}</span>
                    </div>
                    <div className="bg-stone-50 rounded-lg p-3 mb-3">
                      <div className="text-[10px] text-stone-400 mb-1">Order URL</div>
                      <div className="text-[11px] font-mono text-blue-600 break-all">{qrUrl}</div>
                    </div>
                    <div className="flex gap-2">
                      <button onClick={() => { navigator.clipboard.writeText(qrUrl); toast.success("Link copied!"); }}
                        className="flex-1 text-xs py-1.5 bg-blue-50 text-blue-700 rounded-lg font-medium">Copy Link</button>
                      <button onClick={() => { navigator.clipboard.writeText(`${qrUrl}?table=1`); toast.success("Table 1 link copied!"); }}
                        className="flex-1 text-xs py-1.5 bg-stone-100 text-stone-600 rounded-lg font-medium">+ Table #</button>
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 mt-4">
              <h4 className="text-xs font-semibold text-amber-800 mb-1">How It Works</h4>
              <ol className="text-[11px] text-amber-700 space-y-1 list-decimal list-inside">
                <li>Print the QR code or share the link — add <code>?table=5</code> to pre-fill table number</li>
                <li>Guests scan and see the full digital menu with live prices and availability</li>
                <li>Happy Hour discounts are automatically applied if active</li>
                <li>Orders appear instantly on your Kitchen Display and Orders tab</li>
                <li>Process payment when serving — card, cash, or charge to room</li>
              </ol>
            </div>
          </div>
        )}
      </div>

      {/* Payment Dialog */}
      <Dialog open={showPay} onOpenChange={setShowPay}>
        <DialogContent className="max-w-sm" data-testid="payment-dialog">
          <DialogHeader><DialogTitle>Process Payment</DialogTitle></DialogHeader>
          {payingOrder && (
            <div className="space-y-3">
              <div className="text-center py-2">
                <div className="text-3xl font-black text-stone-900">£{payingOrder.total}</div>
                <div className="text-xs text-stone-400">{payingOrder.order_number} · {payingOrder.items?.length || 0} items</div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { value: "card", label: "Card", icon: CreditCard },
                  { value: "cash", label: "Cash", icon: Banknote },
                  { value: "room_charge", label: "Room Charge", icon: Building },
                  { value: "contactless", label: "Contactless", icon: CreditCard },
                ].map(m => (
                  <button key={m.value} onClick={() => setPayMethod(m.value)}
                    className={`flex items-center gap-2 p-3 rounded-xl text-xs font-medium border-2 transition-all ${
                      payMethod === m.value ? "border-orange-500 bg-orange-50 text-orange-700" : "border-stone-200 text-stone-600 hover:border-stone-300"
                    }`} data-testid={`pay-method-${m.value}`}>
                    <m.icon size={16} /> {m.label}
                  </button>
                ))}
              </div>
              {payMethod === "room_charge" && (
                <Input value={roomNumber} onChange={e => setRoomNumber(e.target.value)} placeholder="Room Number" className="h-9 text-sm" />
              )}
              <div>
                <label className="text-[11px] font-medium text-stone-600 mb-1 block">Tip (optional)</label>
                <div className="flex gap-1.5">
                  {[0, 5, 10, 15, 20].map(t => (
                    <button key={t} onClick={() => setTip(t === 0 ? 0 : Math.round(payingOrder.total * t / 100 * 100) / 100)}
                      className={`flex-1 text-[10px] py-1.5 rounded-lg ${tip === Math.round(payingOrder.total * t / 100 * 100) / 100 && t > 0 ? "bg-orange-600 text-white" : "bg-stone-100 text-stone-500"}`}>
                      {t === 0 ? "None" : `${t}%`}
                    </button>
                  ))}
                </div>
                {tip > 0 && <div className="text-[10px] text-stone-400 mt-1 text-right">Tip: £{tip.toFixed(2)} · Total: £{(payingOrder.total + tip).toFixed(2)}</div>}
              </div>
              <button onClick={payOrder}
                className="w-full bg-emerald-600 text-white py-3 rounded-xl text-sm font-bold hover:bg-emerald-700 transition-colors flex items-center justify-center gap-2"
                data-testid="confirm-pay-btn">
                <CheckCircle size={16} weight="fill" /> Pay £{(payingOrder.total + tip).toFixed(2)}
              </button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
