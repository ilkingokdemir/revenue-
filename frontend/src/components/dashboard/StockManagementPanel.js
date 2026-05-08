import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import {
  Package, Plus, ArrowsClockwise, WarningCircle, Trash,
  CurrencyGbp, ChartBar, ForkKnife, Wine, ShoppingCart,
  ArrowDown, ArrowUp, MagnifyingGlass,
} from "@phosphor-icons/react";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const CATEGORIES = ["food","beverage","spirits","wine","beer","soft_drinks","dairy","meat","produce","dry_goods","cleaning","supplies","other"];
const UNITS = ["kg","g","l","ml","pcs","bottles","cases","portions","packs"];
const MOVEMENT_TYPES = ["purchase","usage","waste","transfer_in","transfer_out","adjustment","stocktake"];

const WASTE_REASONS = ["expired","spoiled","overproduction","damaged","spillage","theft_suspected","quality_issue","other"];

function SuppliersPOsTab({ propertyId }) {
  const [suppliers, setSuppliers] = useState([]);
  const [orders, setOrders] = useState([]);
  const [showAddSupplier, setShowAddSupplier] = useState(false);
  const [showAddPO, setShowAddPO] = useState(false);
  const [newSupplier, setNewSupplier] = useState({ name: "", email: "", phone: "" });
  const [newPO, setNewPO] = useState({ supplier_name: "", items: [{ product_name: "", quantity: 0, unit: "pcs", unit_cost: 0 }] });

  const fetch = useCallback(async () => {
    const [sR, oR] = await Promise.all([
      axios.get(`${API}/stock/suppliers/${propertyId}`),
      axios.get(`${API}/stock/purchase-orders/${propertyId}`),
    ]);
    setSuppliers(sR.data); setOrders(oR.data);
  }, [propertyId]);
  useEffect(() => { fetch(); }, [fetch]);

  const addSupplier = async () => {
    await axios.post(`${API}/stock/suppliers`, { ...newSupplier, property_id: propertyId });
    setShowAddSupplier(false); setNewSupplier({ name: "", email: "", phone: "" }); fetch();
  };
  const addPO = async () => {
    await axios.post(`${API}/stock/purchase-orders`, { ...newPO, property_id: propertyId });
    setShowAddPO(false); fetch();
  };
  const receivePO = async (id) => { await axios.put(`${API}/stock/purchase-orders/${id}/receive`); fetch(); };

  return (
    <div className="space-y-4" data-testid="suppliers-tab">
      <div className="flex gap-2 justify-end">
        <button onClick={() => setShowAddSupplier(true)} className="text-xs px-3 py-1.5 bg-stone-100 text-stone-700 rounded-lg font-medium"><Plus size={12} className="inline mr-1" />Supplier</button>
        <button onClick={() => setShowAddPO(true)} className="text-xs px-3 py-1.5 bg-blue-500 text-white rounded-lg font-medium"><Plus size={12} className="inline mr-1" />Purchase Order</button>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div>
          <div className="text-sm font-semibold text-stone-700 mb-2">Suppliers ({suppliers.length})</div>
          {suppliers.map(s => (
            <div key={s.id} className="bg-white border border-stone-200 rounded-lg p-3 mb-1.5">
              <div className="text-xs font-semibold text-stone-800">{s.name}</div>
              <div className="text-[10px] text-stone-400">{s.email} · {s.phone} · {s.payment_terms}</div>
            </div>
          ))}
        </div>
        <div>
          <div className="text-sm font-semibold text-stone-700 mb-2">Purchase Orders ({orders.length})</div>
          {orders.map(o => (
            <div key={o.id} className="bg-white border border-stone-200 rounded-lg p-3 mb-1.5 flex justify-between items-center">
              <div>
                <div className="text-xs font-semibold text-stone-800">{o.supplier_name} — £{o.total_amount}</div>
                <div className="text-[10px] text-stone-400">{o.items?.length || 0} items · {o.created_at?.slice(0, 10)}</div>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="outline" className={`text-[9px] ${o.status === "received" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>{o.status}</Badge>
                {o.status === "draft" && <button onClick={() => receivePO(o.id)} className="text-[10px] px-2 py-1 bg-emerald-50 text-emerald-600 rounded">Receive</button>}
              </div>
            </div>
          ))}
        </div>
      </div>
      <Dialog open={showAddSupplier} onOpenChange={setShowAddSupplier}>
        <DialogContent className="max-w-sm"><DialogHeader><DialogTitle>Add Supplier</DialogTitle></DialogHeader>
          <div className="space-y-2">
            <Input placeholder="Supplier name" value={newSupplier.name} onChange={e => setNewSupplier(p => ({...p, name: e.target.value}))} />
            <Input placeholder="Email" value={newSupplier.email} onChange={e => setNewSupplier(p => ({...p, email: e.target.value}))} />
            <Input placeholder="Phone" value={newSupplier.phone} onChange={e => setNewSupplier(p => ({...p, phone: e.target.value}))} />
            <button onClick={addSupplier} className="w-full text-xs py-2 bg-emerald-500 text-white rounded-lg font-medium">Save</button>
          </div>
        </DialogContent>
      </Dialog>
      <Dialog open={showAddPO} onOpenChange={setShowAddPO}>
        <DialogContent className="max-w-md"><DialogHeader><DialogTitle>Create Purchase Order</DialogTitle></DialogHeader>
          <div className="space-y-2">
            <Input placeholder="Supplier name" value={newPO.supplier_name} onChange={e => setNewPO(p => ({...p, supplier_name: e.target.value}))} />
            {newPO.items.map((item, i) => (
              <div key={i} className="grid grid-cols-4 gap-1">
                <Input placeholder="Product" className="col-span-2 text-xs" value={item.product_name} onChange={e => { const items = [...newPO.items]; items[i].product_name = e.target.value; setNewPO(p => ({...p, items})); }} />
                <Input type="number" placeholder="Qty" className="text-xs" value={item.quantity || ""} onChange={e => { const items = [...newPO.items]; items[i].quantity = parseFloat(e.target.value) || 0; setNewPO(p => ({...p, items})); }} />
                <Input type="number" placeholder="£/unit" className="text-xs" value={item.unit_cost || ""} onChange={e => { const items = [...newPO.items]; items[i].unit_cost = parseFloat(e.target.value) || 0; setNewPO(p => ({...p, items})); }} />
              </div>
            ))}
            <button onClick={() => setNewPO(p => ({...p, items: [...p.items, { product_name: "", quantity: 0, unit: "pcs", unit_cost: 0 }]}))} className="text-[10px] text-blue-600">+ Add item</button>
            <button onClick={addPO} className="w-full text-xs py-2 bg-blue-500 text-white rounded-lg font-medium">Create PO</button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function StockCountsTab({ propertyId }) {
  const [sheets, setSheets] = useState([]);
  const fetch = useCallback(async () => {
    const r = await axios.get(`${API}/stock/count-sheets/${propertyId}`);
    setSheets(r.data);
  }, [propertyId]);
  useEffect(() => { fetch(); }, [fetch]);
  const createSheet = async () => { await axios.post(`${API}/stock/count-sheets`, { property_id: propertyId }); fetch(); };
  const completeSheet = async (id) => { await axios.post(`${API}/stock/count-sheets/${id}/complete`); fetch(); };

  return (
    <div className="space-y-3" data-testid="counts-tab">
      <div className="flex justify-end">
        <button onClick={createSheet} className="text-xs px-3 py-1.5 bg-emerald-500 text-white rounded-lg font-medium" data-testid="new-count-btn"><Plus size={12} className="inline mr-1" />New Stock Count</button>
      </div>
      {sheets.length === 0 ? <div className="text-center py-12 text-stone-400 text-sm">No stock counts yet</div> :
        sheets.map(s => (
          <div key={s.id} className="bg-white border border-stone-200 rounded-xl p-4">
            <div className="flex justify-between items-center mb-2">
              <div>
                <div className="text-xs font-semibold text-stone-800">{s.name}</div>
                <div className="text-[10px] text-stone-400">{s.items?.length || 0} products · by {s.counted_by} · {s.created_at?.slice(0, 16)}</div>
              </div>
              <div className="flex items-center gap-2">
                <Badge className={`text-[9px] ${s.status === "completed" ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>{s.status}</Badge>
                {s.total_variance_cost > 0 && <span className="text-[10px] text-red-500 font-bold">£{s.total_variance_cost} variance</span>}
                {s.status !== "completed" && <button onClick={() => completeSheet(s.id)} className="text-[10px] px-2 py-1 bg-emerald-50 text-emerald-600 rounded">Complete</button>}
              </div>
            </div>
          </div>
        ))}
    </div>
  );
}

function TheoVsActualTab({ propertyId }) {
  const [data, setData] = useState(null);
  const fetch = useCallback(async () => {
    const r = await axios.get(`${API}/stock/theoretical-vs-actual/${propertyId}`);
    setData(r.data);
  }, [propertyId]);
  useEffect(() => { fetch(); }, [fetch]);

  if (!data) return <div className="flex justify-center py-16"><ArrowsClockwise size={24} className="animate-spin text-stone-300" /></div>;

  return (
    <div className="space-y-3" data-testid="theo-tab">
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-white border border-stone-200 rounded-xl p-3 text-center">
          <div className="text-xl font-bold text-stone-800">{data.products?.length || 0}</div>
          <div className="text-[10px] text-stone-500 uppercase">Products Checked</div>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-3 text-center">
          <div className="text-xl font-bold text-red-500">{data.flagged_count}</div>
          <div className="text-[10px] text-stone-500 uppercase">Flagged</div>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-3 text-center">
          <div className="text-xl font-bold text-red-600">£{data.total_variance_cost}</div>
          <div className="text-[10px] text-stone-500 uppercase">Variance Cost</div>
        </div>
      </div>
      <div className="space-y-1.5">
        {data.products?.map(p => (
          <div key={p.product_id} className={`bg-white border rounded-lg p-2.5 flex justify-between text-xs ${p.flag !== "ok" ? "border-red-200" : "border-stone-200"}`}>
            <div className="flex items-center gap-2">
              <span className="font-medium text-stone-700">{p.product_name}</span>
              {p.flag !== "ok" && <Badge className="text-[8px] bg-red-100 text-red-700">{p.flag.replace("_", " ")}</Badge>}
            </div>
            <div className="flex items-center gap-4 text-stone-500">
              <span>Theo: {p.theoretical}</span>
              <span>Actual: {p.actual}</span>
              <span className={p.difference_cost > 0 ? "text-red-500 font-bold" : ""}>£{p.difference_cost}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function FoodCostDashboardTab({ propertyId }) {
  const [data, setData] = useState(null);
  useEffect(() => { axios.get(`${API}/stock/food-cost-dashboard/${propertyId}`).then(r => setData(r.data)).catch(() => {}); }, [propertyId]);
  if (!data) return <div className="flex justify-center py-16"><ArrowsClockwise size={24} className="animate-spin text-stone-300" /></div>;
  const statusColor = data.status === "on_target" ? "text-emerald-600 bg-emerald-50 border-emerald-200" : data.status === "high" ? "text-red-600 bg-red-50 border-red-200" : "text-amber-600 bg-amber-50 border-amber-200";
  return (
    <div className="space-y-4" data-testid="food-cost-tab">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className={`border rounded-xl p-4 text-center ${statusColor}`}>
          <div className="text-3xl font-black">{data.food_cost_pct}%</div>
          <div className="text-[10px] uppercase font-semibold">Food Cost %</div>
          <div className="text-[9px] mt-1">Target: {data.target_range.min}-{data.target_range.max}%</div>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-4 text-center">
          <div className="text-xl font-bold text-stone-800">£{data.cogs}</div><div className="text-[10px] text-stone-500 uppercase">COGS</div>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-4 text-center">
          <div className="text-xl font-bold text-emerald-600">£{data.revenue}</div><div className="text-[10px] text-stone-500 uppercase">F&B Revenue</div>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-4 text-center">
          <div className="text-xl font-bold text-stone-800">£{data.purchases}</div><div className="text-[10px] text-stone-500 uppercase">Purchases</div>
        </div>
      </div>
      {Object.keys(data.by_outlet || {}).length > 0 && (
        <div className="bg-white border border-stone-200 rounded-xl p-4">
          <div className="text-sm font-semibold text-stone-800 mb-2">Cost by Outlet</div>
          {Object.entries(data.by_outlet).map(([outlet, d]) => (
            <div key={outlet} className="flex justify-between text-xs py-1.5 border-b border-stone-50">
              <span className="text-stone-600">{outlet}</span><span className="font-medium text-stone-800">£{d.cost} ({d.movements} movements)</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function MenuEngineeringTab({ propertyId }) {
  const [data, setData] = useState(null);
  useEffect(() => { axios.get(`${API}/stock/menu-engineering/${propertyId}`).then(r => setData(r.data)).catch(() => {}); }, [propertyId]);
  if (!data) return <div className="flex justify-center py-16"><ArrowsClockwise size={24} className="animate-spin text-stone-300" /></div>;
  const classColors = { star: "bg-amber-100 text-amber-700 border-amber-200", puzzle: "bg-blue-100 text-blue-700 border-blue-200", plowhorse: "bg-stone-100 text-stone-600 border-stone-200", dog: "bg-red-100 text-red-600 border-red-200" };
  const classEmoji = { star: "High margin + High sales", puzzle: "High margin + Low sales", plowhorse: "Low margin + High sales", dog: "Low margin + Low sales" };
  return (
    <div className="space-y-4" data-testid="menu-eng-tab">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {["star", "puzzle", "plowhorse", "dog"].map(c => (
          <div key={c} className={`border rounded-xl p-3 text-center ${classColors[c]}`}>
            <div className="text-2xl font-bold">{data.summary?.[c + "s"] || 0}</div>
            <div className="text-[10px] uppercase font-semibold">{c}s</div>
            <div className="text-[8px] mt-0.5 opacity-70">{classEmoji[c]}</div>
          </div>
        ))}
      </div>
      {data.recommendations && (data.recommendations.promote?.length > 0 || data.recommendations.reprice?.length > 0) && (
        <div className="bg-white border border-stone-200 rounded-xl p-4">
          <div className="text-sm font-semibold text-stone-800 mb-2">Recommendations</div>
          {data.recommendations.promote?.length > 0 && <div className="text-xs text-blue-600 mb-1">Promote (puzzles): {data.recommendations.promote.join(", ")}</div>}
          {data.recommendations.reprice?.length > 0 && <div className="text-xs text-amber-600 mb-1">Reprice (plowhorses): {data.recommendations.reprice.join(", ")}</div>}
          {data.recommendations.remove_or_rework?.length > 0 && <div className="text-xs text-red-500">Rework/remove (dogs): {data.recommendations.remove_or_rework.join(", ")}</div>}
        </div>
      )}
      <div className="space-y-1.5">
        {data.recipes?.map(r => (
          <div key={r.id} className={`bg-white border rounded-lg p-2.5 flex justify-between text-xs ${classColors[r.menu_class] || "border-stone-200"}`}>
            <div><span className="font-semibold">{r.name}</span> <Badge className="text-[8px] ml-1">{r.menu_class}</Badge></div>
            <div className="flex gap-3 text-stone-500">
              <span>Cost: £{r.total_cost}</span><span>Sell: £{r.sell_price}</span><span>Margin: {r.margin_pct}%</span><span>Sales: {r.total_sales || 0}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function TurnoverTab({ propertyId }) {
  const [data, setData] = useState(null);
  useEffect(() => { axios.get(`${API}/stock/turnover-rate/${propertyId}`).then(r => setData(r.data)).catch(() => {}); }, [propertyId]);
  if (!data) return <div className="flex justify-center py-16"><ArrowsClockwise size={24} className="animate-spin text-stone-300" /></div>;
  const statusColor = data.status === "optimal" ? "text-emerald-600 bg-emerald-50 border-emerald-200" : data.status === "slow" ? "text-red-600 bg-red-50 border-red-200" : "text-amber-600 bg-amber-50 border-amber-200";
  return (
    <div className="space-y-4" data-testid="turnover-tab">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className={`border rounded-xl p-4 text-center ${statusColor}`}>
          <div className="text-3xl font-black">{data.monthly_turnover}x</div>
          <div className="text-[10px] uppercase font-semibold">Monthly Turnover</div>
          <div className="text-[9px] mt-1">Target: {data.target.min}-{data.target.max}x</div>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-4 text-center">
          <div className="text-xl font-bold text-stone-800">£{data.cogs}</div><div className="text-[10px] text-stone-500 uppercase">COGS (period)</div>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-4 text-center">
          <div className="text-xl font-bold text-stone-800">£{data.avg_inventory_value}</div><div className="text-[10px] text-stone-500 uppercase">Avg Inventory</div>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-4 text-center">
          <div className="text-xl font-bold text-red-500">{data.slow_movers_count}</div><div className="text-[10px] text-stone-500 uppercase">Slow Movers (£{data.slow_movers_value})</div>
        </div>
      </div>
      {data.products?.length > 0 && (
        <div className="space-y-1">
          {data.products.map((p, i) => (
            <div key={i} className="bg-white border border-stone-200 rounded-lg p-2 flex justify-between text-xs">
              <span className="font-medium text-stone-700">{p.product}</span>
              <div className="flex gap-3 text-stone-500">
                <span>Turnover: {p.turnover}x</span><span>Value: £{p.stock_value}</span>
                <Badge className={`text-[8px] ${p.status === "optimal" ? "bg-emerald-50 text-emerald-700" : p.status === "slow" ? "bg-red-50 text-red-700" : "bg-amber-50 text-amber-700"}`}>{p.status}</Badge>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function PerishableTab({ propertyId }) {
  const [data, setData] = useState(null);
  useEffect(() => { axios.get(`${API}/stock/perishable-alerts/${propertyId}`).then(r => setData(r.data)).catch(() => {}); }, [propertyId]);
  if (!data) return <div className="flex justify-center py-16"><ArrowsClockwise size={24} className="animate-spin text-stone-300" /></div>;
  return (
    <div className="space-y-3" data-testid="perishable-tab">
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-white border border-stone-200 rounded-xl p-3 text-center">
          <div className="text-xl font-bold text-red-500">{data.count}</div><div className="text-[10px] text-stone-500 uppercase">Expiry Alerts</div>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-3 text-center">
          <div className="text-xl font-bold text-red-600">£{data.total_at_risk_value}</div><div className="text-[10px] text-stone-500 uppercase">At-Risk Value</div>
        </div>
      </div>
      {data.alerts?.length === 0 ? <div className="text-center py-12 text-stone-400 text-sm">No perishable alerts. Set expiry_days on products to enable tracking.</div> :
        data.alerts?.map((a, i) => (
          <div key={i} className={`bg-white border rounded-xl p-3 flex justify-between ${a.status === "expired" ? "border-red-300 bg-red-50" : a.status === "critical" ? "border-amber-300 bg-amber-50" : "border-stone-200"}`}>
            <div>
              <div className="text-xs font-semibold text-stone-800">{a.name}</div>
              <div className="text-[10px] text-stone-400">Stock: {a.current_stock} {a.unit} · Purchased: {a.last_purchased} · Shelf life: {a.shelf_life_days}d</div>
            </div>
            <div className="text-right">
              <div className={`text-sm font-bold ${a.days_remaining < 0 ? "text-red-600" : "text-amber-600"}`}>{a.days_remaining}d</div>
              <Badge className={`text-[8px] ${a.status === "expired" ? "bg-red-100 text-red-700" : a.status === "critical" ? "bg-amber-100 text-amber-700" : "bg-yellow-100 text-yellow-700"}`}>{a.status}</Badge>
            </div>
          </div>
        ))}
    </div>
  );
}

export function StockManagementPanel({ properties, activePropertyId }) {
  const [tab, setTab] = useState("products");
  const [products, setProducts] = useState([]);
  const [recipes, setRecipes] = useState([]);
  const [movements, setMovements] = useState([]);
  const [outlets, setOutlets] = useState([]);
  const [stats, setStats] = useState({});
  const [aiCost, setAiCost] = useState(null);
  const [variances, setVariances] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [showAdd, setShowAdd] = useState(false);
  const [showMovement, setShowMovement] = useState(false);
  const [showRecipe, setShowRecipe] = useState(false);
  const [newProduct, setNewProduct] = useState({ name: "", category: "other", unit: "pcs", cost_price: 0, reorder_level: 0, current_stock: 0 });
  const [newMovement, setNewMovement] = useState({ product_id: "", movement_type: "purchase", quantity: 0, outlet: "", notes: "" });
  const [newRecipe, setNewRecipe] = useState({ name: "", outlet: "restaurant", sell_price: 0, ingredients: [] });

  const [showCatalog, setShowCatalog] = useState(false);
  const [catalog, setCatalog] = useState(null);
  const [selectedCatalogItems, setSelectedCatalogItems] = useState([]);
  const [catalogFilter, setCatalogFilter] = useState("all");

  const propertyId = activePropertyId && activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "city-gate");

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const searchParam = search ? `?search=${search}` : "";
      const [prodR, recR, movR, outR, stR, varR] = await Promise.all([
        axios.get(`${API}/stock/products/${propertyId}${searchParam}`),
        axios.get(`${API}/stock/recipes/${propertyId}`),
        axios.get(`${API}/stock/movements/${propertyId}`),
        axios.get(`${API}/stock/outlets/${propertyId}`),
        axios.get(`${API}/stock/stats/${propertyId}`),
        axios.get(`${API}/stock/variances/${propertyId}`),
      ]);
      setProducts(prodR.data); setRecipes(recR.data); setMovements(movR.data);
      setOutlets(outR.data); setStats(stR.data); setVariances(varR.data);
      axios.get(`${API}/stock/all-inclusive-cost/${propertyId}`).then(r => setAiCost(r.data)).catch(() => {});
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  }, [propertyId, search]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const addProduct = async () => {
    if (!newProduct.name) return;
    await axios.post(`${API}/stock/products`, { ...newProduct, property_id: propertyId });
    setShowAdd(false); setNewProduct({ name: "", category: "other", unit: "pcs", cost_price: 0, reorder_level: 0, current_stock: 0 });
    fetchData();
  };
  const deleteProduct = async (id) => { await axios.delete(`${API}/stock/products/${id}`); fetchData(); };
  const recordMovement = async () => {
    if (!newMovement.product_id || !newMovement.quantity) return;
    await axios.post(`${API}/stock/movements`, { ...newMovement, property_id: propertyId });
    setShowMovement(false); setNewMovement({ product_id: "", movement_type: "purchase", quantity: 0, outlet: "", notes: "" });
    fetchData();
  };
  const addRecipe = async () => {
    if (!newRecipe.name) return;
    await axios.post(`${API}/stock/recipes`, { ...newRecipe, property_id: propertyId });
    setShowRecipe(false); setNewRecipe({ name: "", outlet: "restaurant", sell_price: 0, ingredients: [] });
    fetchData();
  };
  const runVariance = async () => { await axios.post(`${API}/stock/variance/${propertyId}`); fetchData(); };

  const openCatalog = async () => {
    const res = await axios.get(`${API}/stock/catalog`);
    setCatalog(res.data);
    setSelectedCatalogItems([]);
    setCatalogFilter("all");
    setShowCatalog(true);
  };
  const toggleCatalogItem = (name) => {
    setSelectedCatalogItems(prev => prev.includes(name) ? prev.filter(n => n !== name) : [...prev, name]);
  };
  const addSelectedFromCatalog = async () => {
    if (selectedCatalogItems.length === 0) return;
    await axios.post(`${API}/stock/catalog/add`, { property_id: propertyId, products: selectedCatalogItems });
    setShowCatalog(false);
    fetchData();
  };
  const addAllCategory = async (category) => {
    await axios.post(`${API}/stock/catalog/add-all`, { property_id: propertyId, category });
    setShowCatalog(false);
    fetchData();
  };

  const TABS = [
    { id: "products", label: "Products", icon: Package },
    { id: "recipes", label: "Recipes", icon: ForkKnife },
    { id: "movements", label: "Movements", icon: ShoppingCart },
    { id: "suppliers", label: "Suppliers & POs", icon: ShoppingCart },
    { id: "counts", label: "Stock Counts", icon: ChartBar },
    { id: "cost", label: "Cost %", icon: CurrencyGbp },
    { id: "menu-eng", label: "Menu Engineering", icon: ChartBar },
    { id: "theo", label: "Theo vs Actual", icon: WarningCircle },
    { id: "turnover", label: "Turnover", icon: ArrowsClockwise },
    { id: "perishable", label: "Expiry Alerts", icon: WarningCircle },
    { id: "variances", label: `Variances (${variances.length})`, icon: WarningCircle },
  ];

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-5" data-testid="stock-panel">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-stone-900 flex items-center gap-2" data-testid="stock-title">
            <Package size={22} className="text-emerald-600" weight="fill" /> Stock Management
          </h1>
          <p className="text-sm text-stone-500 mt-0.5">F&B inventory, recipes, cost control & theft prevention</p>
        </div>
        <div className="flex gap-2">
          <button onClick={openCatalog} className="text-xs px-3 py-1.5 bg-violet-50 text-violet-700 rounded-lg hover:bg-violet-100 font-medium" data-testid="browse-catalog-btn">
            <Package size={12} className="inline mr-1" /> Browse Catalog
          </button>
          <button onClick={() => setShowMovement(true)} className="text-xs px-3 py-1.5 bg-blue-50 text-blue-700 rounded-lg hover:bg-blue-100 font-medium" data-testid="record-movement-btn">
            <ShoppingCart size={12} className="inline mr-1" /> Record Movement
          </button>
          <button onClick={() => setShowAdd(true)} className="text-xs px-3 py-1.5 bg-emerald-500 text-white rounded-lg hover:bg-emerald-600 font-medium" data-testid="add-product-btn">
            <Plus size={12} className="inline mr-1" /> Add Product
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
        <div className="bg-white border border-stone-200 rounded-xl p-3 text-center">
          <div className="text-lg font-bold text-stone-800">{stats.total_products || 0}</div>
          <div className="text-[10px] text-stone-500 uppercase">Products</div>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-3 text-center">
          <div className="text-lg font-bold text-stone-800">{stats.total_recipes || 0}</div>
          <div className="text-[10px] text-stone-500 uppercase">Recipes</div>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-3 text-center">
          <div className="text-lg font-bold text-emerald-600">£{stats.stock_value || 0}</div>
          <div className="text-[10px] text-stone-500 uppercase">Stock Value</div>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-3 text-center">
          <div className="text-lg font-bold text-stone-800">{stats.total_movements || 0}</div>
          <div className="text-[10px] text-stone-500 uppercase">Movements</div>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-3 text-center">
          <div className="text-lg font-bold text-amber-600">{stats.low_stock_count || 0}</div>
          <div className="text-[10px] text-stone-500 uppercase">Low Stock</div>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-3 text-center">
          <div className="text-lg font-bold text-red-500">{stats.flagged_variances || 0}</div>
          <div className="text-[10px] text-stone-500 uppercase">Variances</div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-stone-200 overflow-x-auto">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} className={`px-3 py-2.5 text-xs font-medium flex items-center gap-1.5 border-b-2 whitespace-nowrap ${tab === t.id ? "border-emerald-500 text-emerald-700" : "border-transparent text-stone-400 hover:text-stone-600"}`} data-testid={`tab-${t.id}`}>
            <t.icon size={14} /> {t.label}
          </button>
        ))}
      </div>

      {loading ? <div className="flex justify-center py-16"><ArrowsClockwise size={24} className="animate-spin text-stone-300" /></div> : (<>
        {tab === "products" && (
          <div className="space-y-2" data-testid="products-list">
            <Input placeholder="Search products..." value={search} onChange={e => setSearch(e.target.value)} className="h-9 text-sm max-w-xs" />
            {products.length === 0 ? <div className="text-center py-12 text-stone-400 text-sm">No products. Add your first product!</div> :
              products.map(p => (
                <div key={p.id} className="bg-white border border-stone-200 rounded-xl p-3 flex items-center justify-between" data-testid={`product-${p.id}`}>
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-emerald-50 flex items-center justify-center">
                      <Package size={16} className="text-emerald-600" />
                    </div>
                    <div>
                      <div className="text-xs font-semibold text-stone-800">{p.name}</div>
                      <div className="flex items-center gap-2 text-[10px] text-stone-400">
                        <Badge variant="outline" className="text-[9px]">{p.category}</Badge>
                        <span>£{p.cost_price}/{p.unit}</span>
                        {p.supplier && <span>· {p.supplier}</span>}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="text-right">
                      <div className={`text-sm font-bold ${p.current_stock <= p.reorder_level && p.reorder_level > 0 ? "text-red-500" : "text-stone-800"}`}>
                        {p.current_stock} {p.unit}
                      </div>
                      {p.reorder_level > 0 && p.current_stock <= p.reorder_level && (
                        <div className="text-[9px] text-red-400">Below reorder ({p.reorder_level})</div>
                      )}
                    </div>
                    <button onClick={() => deleteProduct(p.id)} className="text-stone-300 hover:text-red-400"><Trash size={14} /></button>
                  </div>
                </div>
              ))}
          </div>
        )}

        {tab === "recipes" && (
          <div className="space-y-2" data-testid="recipes-list">
            <div className="flex justify-end">
              <button onClick={() => setShowRecipe(true)} className="text-xs px-3 py-1.5 bg-emerald-50 text-emerald-700 rounded-lg font-medium" data-testid="add-recipe-btn">
                <Plus size={12} className="inline mr-1" /> Add Recipe
              </button>
            </div>
            {recipes.length === 0 ? <div className="text-center py-12 text-stone-400 text-sm">No recipes yet</div> :
              recipes.map(r => (
                <div key={r.id} className="bg-white border border-stone-200 rounded-xl p-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-xs font-semibold text-stone-800">{r.name}</div>
                      <div className="text-[10px] text-stone-400">{r.outlet} · {r.ingredients?.length || 0} ingredients</div>
                    </div>
                    <div className="text-right">
                      <div className="text-xs">Cost: <span className="font-bold text-red-500">£{r.total_cost}</span> → Sell: <span className="font-bold text-emerald-600">£{r.sell_price}</span></div>
                      <div className="text-[10px] text-stone-500">Margin: {r.margin_pct}%</div>
                    </div>
                  </div>
                  {r.ingredients?.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {r.ingredients.map((ing, i) => (
                        <Badge key={i} variant="outline" className="text-[9px]">{ing.product_name || ing.product_id}: {ing.quantity}{ing.unit}</Badge>
                      ))}
                    </div>
                  )}
                </div>
              ))}
          </div>
        )}

        {tab === "movements" && (
          <div className="space-y-1.5" data-testid="movements-list">
            {movements.length === 0 ? <div className="text-center py-12 text-stone-400 text-sm">No movements recorded</div> :
              movements.map(m => (
                <div key={m.id} className="bg-white border border-stone-200 rounded-lg p-2.5 flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <div className={`w-6 h-6 rounded flex items-center justify-center ${m.movement_type === "purchase" ? "bg-emerald-50" : m.movement_type === "waste" ? "bg-red-50" : "bg-blue-50"}`}>
                      {m.movement_type === "purchase" ? <ArrowDown size={12} className="text-emerald-500" /> : <ArrowUp size={12} className="text-blue-500" />}
                    </div>
                    <span className="font-medium text-stone-700">{m.product_name}</span>
                    <Badge variant="outline" className="text-[9px]">{m.movement_type}</Badge>
                  </div>
                  <div className="flex items-center gap-3 text-stone-500">
                    <span>{m.quantity} {m.unit}</span>
                    {m.cost > 0 && <span>£{m.cost}</span>}
                    <span className="text-[10px]">{m.created_at?.slice(0, 10)}</span>
                  </div>
                </div>
              ))}
          </div>
        )}

        {tab === "suppliers" && (
          <SuppliersPOsTab propertyId={propertyId} />
        )}

        {tab === "counts" && (
          <StockCountsTab propertyId={propertyId} />
        )}

        {tab === "cost" && (
          <FoodCostDashboardTab propertyId={propertyId} />
        )}

        {tab === "menu-eng" && (
          <MenuEngineeringTab propertyId={propertyId} />
        )}

        {tab === "theo" && (
          <TheoVsActualTab propertyId={propertyId} />
        )}

        {tab === "variances" && (
          <div className="space-y-2" data-testid="variances-list">
            <button onClick={runVariance} className="text-xs px-3 py-1.5 bg-red-50 text-red-700 rounded-lg font-medium" data-testid="run-variance-btn">
              <WarningCircle size={12} className="inline mr-1" /> Run Variance Check
            </button>
            {variances.length === 0 ? <div className="text-center py-12 text-stone-400 text-sm">No variances detected. Run a check above.</div> :
              variances.map(v => (
                <div key={v.id} className="bg-white border border-red-100 rounded-xl p-3 flex items-center justify-between">
                  <div>
                    <div className="text-xs font-semibold text-stone-800">{v.product_name}</div>
                    <div className="text-[10px] text-stone-400">Expected: {v.expected_stock} | Actual: {v.actual_stock} | Variance: {v.variance} ({v.variance_pct}%)</div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-bold text-red-500">£{v.variance_cost}</div>
                    <Badge className="text-[9px] bg-red-100 text-red-700">{v.status}</Badge>
                  </div>
                </div>
              ))}
          </div>
        )}

        {tab === "turnover" && (
          <TurnoverTab propertyId={propertyId} />
        )}

        {tab === "perishable" && (
          <PerishableTab propertyId={propertyId} />
        )}
      </>)}

      {/* Add Product Dialog */}
      <Dialog open={showAdd} onOpenChange={setShowAdd}>
        <DialogContent className="max-w-md">
          <DialogHeader><DialogTitle>Add Product</DialogTitle></DialogHeader>
          <div className="space-y-2">
            <Input placeholder="Product name" value={newProduct.name} onChange={e => setNewProduct(p => ({...p, name: e.target.value}))} data-testid="product-name" />
            <div className="grid grid-cols-2 gap-2">
              <Select value={newProduct.category} onValueChange={v => setNewProduct(p => ({...p, category: v}))}>
                <SelectTrigger className="h-9 text-xs"><SelectValue /></SelectTrigger>
                <SelectContent>{CATEGORIES.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
              </Select>
              <Select value={newProduct.unit} onValueChange={v => setNewProduct(p => ({...p, unit: v}))}>
                <SelectTrigger className="h-9 text-xs"><SelectValue /></SelectTrigger>
                <SelectContent>{UNITS.map(u => <SelectItem key={u} value={u}>{u}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-3 gap-2">
              <Input type="number" placeholder="Cost price" value={newProduct.cost_price || ""} onChange={e => setNewProduct(p => ({...p, cost_price: parseFloat(e.target.value) || 0}))} />
              <Input type="number" placeholder="Current stock" value={newProduct.current_stock || ""} onChange={e => setNewProduct(p => ({...p, current_stock: parseFloat(e.target.value) || 0}))} />
              <Input type="number" placeholder="Reorder level" value={newProduct.reorder_level || ""} onChange={e => setNewProduct(p => ({...p, reorder_level: parseFloat(e.target.value) || 0}))} />
            </div>
            <button onClick={addProduct} className="w-full text-xs py-2 bg-emerald-500 text-white rounded-lg font-medium" data-testid="save-product">Save Product</button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Record Movement Dialog */}
      <Dialog open={showMovement} onOpenChange={setShowMovement}>
        <DialogContent className="max-w-md">
          <DialogHeader><DialogTitle>Record Stock Movement</DialogTitle></DialogHeader>
          <div className="space-y-2">
            <Select value={newMovement.product_id} onValueChange={v => setNewMovement(p => ({...p, product_id: v}))}>
              <SelectTrigger className="h-9 text-xs" data-testid="movement-product"><SelectValue placeholder="Select product" /></SelectTrigger>
              <SelectContent>{products.map(p => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}</SelectContent>
            </Select>
            <div className="grid grid-cols-2 gap-2">
              <Select value={newMovement.movement_type} onValueChange={v => setNewMovement(p => ({...p, movement_type: v}))}>
                <SelectTrigger className="h-9 text-xs"><SelectValue /></SelectTrigger>
                <SelectContent>{MOVEMENT_TYPES.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
              </Select>
              <Input type="number" placeholder="Quantity" value={newMovement.quantity || ""} onChange={e => setNewMovement(p => ({...p, quantity: parseFloat(e.target.value) || 0}))} data-testid="movement-qty" />
            </div>
            <Input placeholder="Notes" value={newMovement.notes} onChange={e => setNewMovement(p => ({...p, notes: e.target.value}))} />
            <button onClick={recordMovement} className="w-full text-xs py-2 bg-blue-500 text-white rounded-lg font-medium" data-testid="save-movement">Record Movement</button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Add Recipe Dialog */}
      <Dialog open={showRecipe} onOpenChange={setShowRecipe}>
        <DialogContent className="max-w-md">
          <DialogHeader><DialogTitle>Add Recipe</DialogTitle></DialogHeader>
          <div className="space-y-2">
            <Input placeholder="Recipe name (e.g., Mojito)" value={newRecipe.name} onChange={e => setNewRecipe(p => ({...p, name: e.target.value}))} data-testid="recipe-name" />
            <div className="grid grid-cols-2 gap-2">
              <Select value={newRecipe.outlet} onValueChange={v => setNewRecipe(p => ({...p, outlet: v}))}>
                <SelectTrigger className="h-9 text-xs"><SelectValue /></SelectTrigger>
                <SelectContent>{outlets.map(o => <SelectItem key={o.id} value={o.outlet_type}>{o.name}</SelectItem>)}</SelectContent>
              </Select>
              <Input type="number" placeholder="Sell price" value={newRecipe.sell_price || ""} onChange={e => setNewRecipe(p => ({...p, sell_price: parseFloat(e.target.value) || 0}))} />
            </div>
            <button onClick={addRecipe} className="w-full text-xs py-2 bg-emerald-500 text-white rounded-lg font-medium" data-testid="save-recipe">Save Recipe</button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Browse Catalog Dialog */}
      <Dialog open={showCatalog} onOpenChange={setShowCatalog}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader><DialogTitle>Product Catalog ({catalog?.total || 0} items)</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="flex gap-1 flex-wrap">
              <button onClick={() => setCatalogFilter("all")} className={`text-[10px] px-2 py-1 rounded-lg ${catalogFilter === "all" ? "bg-violet-500 text-white" : "bg-stone-100 text-stone-600"}`}>All</button>
              {catalog && Object.keys(catalog.categories || {}).map(cat => (
                <button key={cat} onClick={() => setCatalogFilter(cat)} className={`text-[10px] px-2 py-1 rounded-lg capitalize ${catalogFilter === cat ? "bg-violet-500 text-white" : "bg-stone-100 text-stone-600"}`}>
                  {cat.replace(/_/g, " ")}
                </button>
              ))}
            </div>
            <div className="flex gap-2">
              <button onClick={addSelectedFromCatalog} disabled={selectedCatalogItems.length === 0}
                className="text-xs px-3 py-1.5 bg-emerald-500 text-white rounded-lg font-medium disabled:opacity-40" data-testid="add-selected-catalog">
                Add Selected ({selectedCatalogItems.length})
              </button>
              {catalogFilter !== "all" && (
                <button onClick={() => addAllCategory(catalogFilter)} className="text-xs px-3 py-1.5 bg-violet-500 text-white rounded-lg font-medium" data-testid="add-all-category">
                  Add All {catalogFilter.replace(/_/g, " ")}
                </button>
              )}
            </div>
            {catalog && Object.entries(catalog.categories || {}).filter(([cat]) => catalogFilter === "all" || cat === catalogFilter).map(([cat, items]) => (
              <div key={cat}>
                <div className="text-xs font-semibold text-stone-700 capitalize mb-1.5 mt-2">{cat.replace(/_/g, " ")} ({items.length})</div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-1">
                  {items.map(item => (
                    <button key={item.name} onClick={() => toggleCatalogItem(item.name)}
                      className={`text-left p-2 rounded-lg border text-xs transition-all ${selectedCatalogItems.includes(item.name) ? "border-violet-300 bg-violet-50 ring-1 ring-violet-200" : "border-stone-200 hover:border-stone-300"}`}>
                      <div className="font-medium text-stone-800">{item.name}</div>
                      <div className="text-[10px] text-stone-400">£{item.cost_price}/{item.unit}{item.expiry_days ? ` · ${item.expiry_days}d shelf` : ""}{item.allergens?.length ? ` · ${item.allergens.join(",")}` : ""}</div>
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
