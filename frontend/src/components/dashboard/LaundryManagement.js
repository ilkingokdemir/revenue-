import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger,
  DialogFooter, DialogDescription,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import {
  RefreshCw, Plus, Send, Package, FileText, Shirt, CheckCircle2,
  Trash2, ArrowDown, Building2, Inbox, DoorOpen, BarChart3, AlertCircle,
  Calendar, FileBarChart, ShieldCheck, RotateCcw, Download, Sparkles,
  TrendingUp,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const TABS = [
  { id: "dispatch",  label: "Dispatch",  icon: Send,     color: "bg-orange-500",  subtitle: "Send to laundry" },
  { id: "deliveries",label: "Deliveries",icon: Inbox,    color: "bg-emerald-500", subtitle: "Receive from laundry" },
  { id: "forecast",  label: "Next Order", icon: Sparkles, color: "bg-fuchsia-500", subtitle: "Forecast & order" },
  { id: "usage",     label: "Daily Usage",icon: DoorOpen, color: "bg-blue-500",   subtitle: "Room collections" },
  { id: "stock",     label: "Stock",      icon: Package, color: "bg-violet-500",  subtitle: "Inventory levels" },
  { id: "contracts", label: "Contracts",  icon: FileText, color: "bg-stone-500",  subtitle: "Vendor agreements" },
];

const REPORTS = [
  { id: "daily-usage",   label: "Daily Usage Report",  desc: "Room-wise daily usage breakdown",     icon: FileText,     color: "bg-blue-100 text-blue-600" },
  { id: "count",         label: "Count Report",        desc: "Aggregated usage with anomalies",     icon: BarChart3,    color: "bg-emerald-100 text-emerald-600" },
  { id: "order",         label: "Order Report",        desc: "Order vs Received comparison",        icon: Package,      color: "bg-violet-100 text-violet-600" },
  { id: "dispatch",      label: "Dispatch Report",     desc: "Dirty send with date ranges",         icon: Send,         color: "bg-amber-100 text-amber-600" },
  { id: "monthly-audit", label: "Monthly Audit",       desc: "End of month audit report",           icon: ShieldCheck,  color: "bg-red-100 text-red-600" },
  { id: "group-update",  label: "Group Update",        desc: "Rolling cycle ledger",                icon: RotateCcw,    color: "bg-indigo-100 text-indigo-600" },
];

const DISPATCH_STATUS_STYLE = {
  pending:  "bg-stone-100 text-stone-600",
  sent:     "bg-amber-100 text-amber-700",
  received: "bg-emerald-100 text-emerald-700",
  invoiced: "bg-blue-100 text-blue-700",
  paid:     "bg-violet-100 text-violet-700",
};

export const LaundryManagement = ({ propertyId, user, permissions }) => {
  const [tab, setTab] = useState("dispatch");
  const [dispatches, setDispatches] = useState({ dispatches: [], kpis: {} });
  const [usage, setUsage] = useState({ records: [], count: 0 });
  const [stock, setStock] = useState([]);
  const [contracts, setContracts] = useState([]);
  const [catalog, setCatalog] = useState([]);
  const [rooms, setRooms] = useState([]);
  const [loading, setLoading] = useState(true);

  const [dispOpen, setDispOpen] = useState(false);
  const [contractOpen, setContractOpen] = useState(false);
  const [usageOpen, setUsageOpen] = useState(false);
  const [reportOpen, setReportOpen] = useState(null);
  const [reportData, setReportData] = useState(null);
  const [reportLoading, setReportLoading] = useState(false);

  const [dispForm, setDispForm] = useState({ vendor: "", sent_date: new Date().toISOString().slice(0, 10), expected_return: "", items: [], notes: "" });
  const [contractForm, setContractForm] = useState({
    vendor: "", contact_name: "", contact_email: "", contact_phone: "",
    start_date: "", end_date: "", pickup_schedule: "weekly", terms: "", rates: [], active: true,
  });
  const [usageForm, setUsageForm] = useState({ date: new Date().toISOString().slice(0, 10), room_id: "", room_number: "", items: [] });

  const pid = propertyId || "all";
  const isManager = user?.role === "admin" || user?.role === "manager";
  // Permission-gated cost visibility: configured by admin in Roles & Permissions.
  // Legacy admin always allowed; otherwise requires `view_laundry_costs` perm.
  const canSeeCosts = !!permissions?.is_legacy_admin
                   || !!permissions?.permissions?.has?.("view_laundry_costs");
  // Filter tabs: housekeeper + receptionist should NOT see contracts
  const visibleTabs = TABS.filter(t => t.id !== "contracts" || canSeeCosts);
  // If a restricted user somehow has 'contracts' selected, force them to dispatch
  useEffect(() => {
    if (!canSeeCosts && tab === "contracts") setTab("dispatch");
  }, [canSeeCosts, tab]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [d, u, s, c, cat, rm] = await Promise.all([
        axios.get(`${API}/laundry/dispatches/${pid}`),
        axios.get(`${API}/laundry/usage/${pid}`),
        axios.get(`${API}/laundry/stock/${pid}`),
        axios.get(`${API}/laundry/contracts/${pid}`).catch(() => ({ data: { contracts: [] } })),
        axios.get(`${API}/laundry/catalog`, { params: { property_id: pid } }),
        axios.get(`${API}/rooms`).catch(() => ({ data: [] })),
      ]);
      setDispatches(d.data);
      setUsage(u.data);
      setStock(s.data.stock || []);
      setContracts(c.data.contracts || []);
      setCatalog(cat.data.items || []);
      setRooms(Array.isArray(rm.data) ? rm.data : (rm.data.rooms || []));
    } catch { /* silent */ }
    setLoading(false);
  }, [pid]);

  useEffect(() => { load(); }, [load]);

  // ============ DISPATCH HELPERS ============
  const addDispItem = () => setDispForm(f => ({ ...f, items: [...f.items, { item_id: "", name: "", qty_sent: 0, rate: 0 }] }));
  const updateDispItem = (idx, patch) => {
    setDispForm(f => {
      const items = [...f.items];
      items[idx] = { ...items[idx], ...patch };
      if (patch.item_id) {
        const c = catalog.find(x => x.id === patch.item_id);
        if (c) items[idx].name = c.name;
      }
      return { ...f, items };
    });
  };
  const removeDispItem = (idx) => setDispForm(f => ({ ...f, items: f.items.filter((_, i) => i !== idx) }));
  const submitDispatch = async () => {
    if (!dispForm.vendor.trim() || dispForm.items.length === 0) { toast.error("Vendor and at least one item required"); return; }
    try {
      await axios.post(`${API}/laundry/dispatches/${pid}`, dispForm);
      toast.success("Dispatch created");
      setDispOpen(false);
      setDispForm({ vendor: "", sent_date: new Date().toISOString().slice(0, 10), expected_return: "", items: [], notes: "" });
      load();
    } catch { toast.error("Failed"); }
  };
  const receiveDispatch = async (d) => {
    if (!window.confirm(`Mark ${d.vendor} dispatch as received (full qty)?`)) return;
    try {
      await axios.post(`${API}/laundry/dispatches/${pid}/${d.id}/receive`, { items: d.items.map(i => ({ item_id: i.item_id, qty_received: i.qty_sent })) });
      toast.success("Received");
      load();
    } catch { toast.error("Failed"); }
  };

  // ============ USAGE HELPERS ============
  const addUsageItem = () => setUsageForm(f => ({ ...f, items: [...f.items, { item_id: "", item_name: "", clean_used: 0, dirty_collected: 0 }] }));
  const updateUsageItem = (idx, patch) => setUsageForm(f => {
    const items = [...f.items];
    items[idx] = { ...items[idx], ...patch };
    if (patch.item_id) {
      const c = catalog.find(x => x.id === patch.item_id);
      if (c) items[idx].item_name = c.name;
    }
    return { ...f, items };
  });
  const removeUsageItem = (idx) => setUsageForm(f => ({ ...f, items: f.items.filter((_, i) => i !== idx) }));
  const submitUsage = async () => {
    if (!usageForm.room_number.trim() || usageForm.items.length === 0) { toast.error("Room and items required"); return; }
    const validItems = usageForm.items.filter(i => (i.clean_used || 0) > 0 || (i.dirty_collected || 0) > 0);
    if (validItems.length === 0) { toast.error("At least one item with clean used or dirty collected > 0"); return; }
    try {
      await axios.post(`${API}/laundry/usage/${pid}`, { ...usageForm, items: validItems });
      toast.success(`Recorded ${validItems.length} item(s) for room ${usageForm.room_number}`);
      setUsageOpen(false);
      setUsageForm({ date: new Date().toISOString().slice(0, 10), room_id: "", room_number: "", notes: "", items: [] });
      load();
    } catch { toast.error("Failed"); }
  };
  const deleteUsage = async (id) => {
    if (!window.confirm("Delete this usage record? Stock will be reversed.")) return;
    try { await axios.delete(`${API}/laundry/usage/${pid}/${id}`); toast.success("Deleted"); load(); } catch { toast.error("Failed"); }
  };

  // ============ STOCK ============
  const updateStockCell = async (item_id, field, value) => {
    const row = stock.find(s => s.item_id === item_id);
    try {
      await axios.put(`${API}/laundry/stock/${pid}/${item_id}`, { [field]: parseInt(value) || 0, name: row?.name || item_id });
      load();
    } catch { toast.error("Failed"); }
  };

  // ============ CONTRACTS ============
  const submitContract = async () => {
    if (!contractForm.vendor.trim()) { toast.error("Vendor required"); return; }
    try {
      await axios.post(`${API}/laundry/contracts/${pid}`, contractForm);
      toast.success("Contract added");
      setContractOpen(false);
      setContractForm({ vendor: "", contact_name: "", contact_email: "", contact_phone: "", start_date: "", end_date: "", pickup_schedule: "weekly", terms: "", rates: [], active: true });
      load();
    } catch { toast.error("Failed"); }
  };
  const deleteContract = async (id) => {
    if (!window.confirm("Delete this contract?")) return;
    try { await axios.delete(`${API}/laundry/contracts/${pid}/${id}`); toast.success("Deleted"); load(); } catch { toast.error("Failed"); }
  };
  const addRate = () => setContractForm(f => ({ ...f, rates: [...f.rates, { item_id: "", name: "", rate: 0 }] }));
  const updateRate = (i, patch) => setContractForm(f => {
    const rates = [...f.rates];
    rates[i] = { ...rates[i], ...patch };
    if (patch.item_id) {
      const c = catalog.find(x => x.id === patch.item_id);
      if (c) rates[i].name = c.name;
    }
    return { ...f, rates };
  });

  // ============ REPORTS ============
  const openReport = async (rep) => {
    setReportOpen(rep);
    setReportLoading(true);
    setReportData(null);
    try {
      const { data } = await axios.get(`${API}/laundry/reports/${pid}/${rep.id}`);
      setReportData(data);
    } catch { toast.error("Failed to load report"); }
    setReportLoading(false);
  };
  const exportCSV = () => {
    if (!reportData || !reportOpen) return;
    let csv = "";
    if (reportOpen.id === "daily-usage") {
      csv = "Date,Room,Item,Qty,Recorded By\n" + (reportData.rows || []).map(r => `${r.date},${r.room_number},${r.item_name},${r.qty},${r.recorded_by}`).join("\n");
    } else if (reportOpen.id === "count") {
      csv = "Item,Total,Days Active,Rooms Active,Daily Avg,Anomaly\n" + (reportData.items || []).map(i => `${i.item},${i.total},${i.days_active},${i.rooms_active},${i.daily_avg},${i.anomaly}`).join("\n");
    } else if (reportOpen.id === "order") {
      csv = "Item,Sent,Received,Variance\n" + (reportData.items || []).map(i => `${i.item},${i.sent},${i.received},${i.variance}`).join("\n");
    } else if (reportOpen.id === "monthly-audit") {
      csv = "Item,Clean,Dirty,In Transit,Damaged,Used,Dispatched,Total\n" + (reportData.audit || []).map(a => `${a.item},${a.clean},${a.dirty},${a.in_transit},${a.damaged},${a.used_in_period},${a.dispatched_in_period},${a.total_inventory}`).join("\n");
    } else if (reportOpen.id === "group-update") {
      csv = "Date,Type,Item,Qty,Ref\n" + (reportData.events || []).map(e => `${e.date},${e.type},${e.item},${e.qty},${e.ref}`).join("\n");
    }
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `laundry-${reportOpen.id}-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
  };

  const k = dispatches.kpis || {};
  const deliveries = (dispatches.dispatches || []).filter(d => d.status === "received");
  const sentDispatches = (dispatches.dispatches || []).filter(d => d.status !== "received");

  const fmt = (n) => `£${Number(n || 0).toLocaleString()}`;

  return (
    <div className="space-y-5" data-testid="laundry-management">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <Shirt className="w-5 h-5 text-stone-700" />
            <h2 className="text-base font-bold text-stone-800" data-testid="laundry-title">Laundry Management</h2>
          </div>
          <p className="text-[11px] text-stone-500 mt-0.5">Manage dispatches, deliveries and view reports</p>
        </div>
      </div>

      {/* KPIs */}
      <div className={`grid gap-3 ${canSeeCosts ? "grid-cols-5" : "grid-cols-3"}`} data-testid="laundry-kpis">
        <div className="bg-stone-50 border border-stone-200 rounded-xl p-4 text-center"><p className="text-2xl font-black text-stone-700">{k.total_items || 0}</p><p className="text-[10px] text-stone-500">Items Sent YTD</p></div>
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-center"><Send className="w-4 h-4 mx-auto mb-1 text-amber-600" /><p className="text-2xl font-black text-amber-700">{k.sent || 0}</p><p className="text-[10px] text-amber-600">Awaiting Return</p></div>
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-center"><CheckCircle2 className="w-4 h-4 mx-auto mb-1 text-emerald-600" /><p className="text-2xl font-black text-emerald-700">{k.received || 0}</p><p className="text-[10px] text-emerald-600">Deliveries</p></div>
        {canSeeCosts && (
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-center"><Building2 className="w-4 h-4 mx-auto mb-1 text-blue-600" /><p className="text-2xl font-black text-blue-700">{contracts.length}</p><p className="text-[10px] text-blue-600">Contracts</p></div>
        )}
        {canSeeCosts && (
          <div className="bg-violet-50 border border-violet-200 rounded-xl p-4 text-center"><p className="text-2xl font-black text-violet-700">{fmt(k.total_cost)}</p><p className="text-[10px] text-violet-600">Total Spend</p></div>
        )}
      </div>

      {/* Big Colored Tiles (like the mobile screenshot) */}
      <div className={`grid grid-cols-2 gap-3 ${visibleTabs.length === 6 ? "md:grid-cols-6" : visibleTabs.length === 5 ? "md:grid-cols-5" : "md:grid-cols-4"}`} data-testid="laundry-tiles">
        {visibleTabs.map(t => {
          const Icon = t.icon;
          const active = tab === t.id;
          return (
            <button key={t.id} onClick={() => setTab(t.id)} data-testid={`tab-${t.id}`}
              className={`${t.color} text-white rounded-xl p-4 text-left transition-all ${active ? "ring-4 ring-offset-2 ring-stone-800 scale-[1.02]" : "hover:scale-[1.02] opacity-90 hover:opacity-100"}`}>
              <div className="w-10 h-10 bg-white/20 rounded-lg flex items-center justify-center mb-3">
                <Icon className="w-5 h-5" />
              </div>
              <h3 className="text-sm font-black">{t.label}</h3>
              <p className="text-[11px] opacity-90">{t.subtitle}</p>
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      {loading ? (
        <div className="flex items-center justify-center py-20 text-stone-400"><RefreshCw className="w-5 h-5 animate-spin mr-2" />Loading...</div>
      ) : (
        <>
          {/* DISPATCH */}
          {tab === "dispatch" && (
            <div className="bg-white border border-stone-200 rounded-xl overflow-hidden" data-testid="dispatch-panel">
              <div className="p-3 border-b border-stone-200 flex items-center justify-between">
                <h3 className="text-sm font-bold text-stone-800">Awaiting Return ({sentDispatches.length})</h3>
                <Button size="sm" onClick={() => setDispOpen(true)} className="bg-stone-800 hover:bg-stone-700 text-white" data-testid="new-dispatch-btn">
                  <Plus className="w-4 h-4 mr-1.5" />New Dispatch
                </Button>
              </div>
              {sentDispatches.length === 0 ? (
                <p className="text-center text-sm text-stone-400 py-12">No dispatches awaiting return.</p>
              ) : (
                <table className="w-full text-xs">
                  <thead className="bg-stone-50 border-b border-stone-200">
                    <tr>
                      <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Vendor</th>
                      <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Sent</th>
                      <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Expected</th>
                      <th className="text-center py-2.5 px-3 font-semibold text-stone-600">Items</th>
                      {canSeeCosts && <th className="text-right py-2.5 px-3 font-semibold text-stone-600">Cost</th>}
                      <th className="text-center py-2.5 px-3 font-semibold text-stone-600">Status</th>
                      <th className="text-right py-2.5 px-3 font-semibold text-stone-600">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sentDispatches.map(d => (
                      <tr key={d.id} className="border-b border-stone-100 hover:bg-stone-50/50" data-testid={`dispatch-row-${d.id}`}>
                        <td className="py-2.5 px-3 font-semibold text-stone-700">{d.vendor}</td>
                        <td className="py-2.5 px-3 text-stone-600">{d.sent_date}</td>
                        <td className="py-2.5 px-3 text-stone-600">{d.expected_return || "—"}</td>
                        <td className="py-2.5 px-3 text-center font-semibold text-stone-700">{d.items.reduce((s, i) => s + i.qty_sent, 0)}</td>
                        {canSeeCosts && <td className="py-2.5 px-3 text-right font-mono text-stone-700">£{d.total_cost?.toFixed(2)}</td>}
                        <td className="py-2.5 px-3 text-center"><Badge className={`${DISPATCH_STATUS_STYLE[d.status] || "bg-stone-100"} text-[9px] capitalize`}>{d.status}</Badge></td>
                        <td className="py-2.5 px-3 text-right">
                          <button onClick={() => receiveDispatch(d)} className="text-[10px] px-2 py-1 bg-emerald-50 text-emerald-700 rounded hover:bg-emerald-100 font-semibold" data-testid={`receive-btn-${d.id}`}>
                            <ArrowDown className="w-3 h-3 inline mr-1" />Receive
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {/* DELIVERIES */}
          {tab === "deliveries" && (
            <DeliveriesTab pid={pid} dispatches={sentDispatches} stock={stock} />
          )}

          {/* FORECAST */}
          {tab === "forecast" && (
            <ForecastTab pid={pid} onCreated={load} canSeeCosts={canSeeCosts} />
          )}

          {/* DAILY USAGE */}
          {tab === "usage" && (
            <div className="bg-white border border-stone-200 rounded-xl overflow-hidden" data-testid="usage-panel">
              <div className="p-3 border-b border-stone-200 flex items-center justify-between">
                <h3 className="text-sm font-bold text-stone-800">Room-by-Room Usage ({usage.count})</h3>
                <Button size="sm" onClick={() => setUsageOpen(true)} className="bg-stone-800 hover:bg-stone-700 text-white" data-testid="new-usage-btn">
                  <Plus className="w-4 h-4 mr-1.5" />Record Usage
                </Button>
              </div>
              {usage.records.length === 0 ? (
                <p className="text-center text-sm text-stone-400 py-12">No usage recorded. Record a room's daily linen collection to track circulation.</p>
              ) : (
                <table className="w-full text-xs">
                  <thead className="bg-stone-50 border-b border-stone-200">
                    <tr>
                      <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Date</th>
                      <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Room</th>
                      <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Item</th>
                      <th className="text-center py-2.5 px-3 font-semibold text-emerald-700">Clean Used ↓</th>
                      <th className="text-center py-2.5 px-3 font-semibold text-amber-700">Dirty Collected ↑</th>
                      <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Notes</th>
                      <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Recorded By</th>
                      <th className="text-right py-2.5 px-3 font-semibold text-stone-600"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {usage.records.map(r => {
                      const clean = r.clean_used ?? r.qty ?? 0;
                      const dirty = r.dirty_collected ?? r.qty ?? 0;
                      const mismatch = clean !== dirty;
                      return (
                      <tr key={r.id} className="border-b border-stone-100 hover:bg-stone-50/50" data-testid={`usage-row-${r.id}`}>
                        <td className="py-2 px-3 text-stone-600">{r.date}</td>
                        <td className="py-2 px-3 font-semibold text-stone-700">{r.room_number}</td>
                        <td className="py-2 px-3 text-stone-700">{r.item_name}</td>
                        <td className="py-2 px-3 text-center font-bold text-emerald-700">{clean}</td>
                        <td className="py-2 px-3 text-center">
                          <span className={`font-bold ${mismatch ? "text-rose-600" : "text-amber-700"}`}>{dirty}</span>
                          {mismatch && <span className="ml-1 text-[9px] text-rose-500" title="Differs from clean used">≠</span>}
                        </td>
                        <td className="py-2 px-3 text-[10px] text-stone-500 italic">{r.notes || "—"}</td>
                        <td className="py-2 px-3 text-[10px] text-stone-500">{r.recorded_by}</td>
                        <td className="py-2 px-3 text-right">
                          {isManager && <button onClick={() => deleteUsage(r.id)} className="p-1 hover:bg-red-50 rounded"><Trash2 className="w-3 h-3 text-red-500" /></button>}
                        </td>
                      </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {/* STOCK */}
          {tab === "stock" && (
            <StockTab pid={pid} stock={stock} updateStockCell={updateStockCell} />
          )}

          {/* CONTRACTS */}
          {tab === "contracts" && (
            <div data-testid="contracts-panel">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-bold text-stone-800">Laundry Contracts ({contracts.length})</h3>
                {isManager && (
                  <Button size="sm" onClick={() => setContractOpen(true)} className="bg-stone-800 hover:bg-stone-700 text-white" data-testid="new-contract-btn">
                    <Plus className="w-4 h-4 mr-1.5" />New Contract
                  </Button>
                )}
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                {contracts.length === 0 ? (
                  <p className="text-center text-sm text-stone-400 py-12 col-span-2">No contracts yet.</p>
                ) : contracts.map(c => (
                  <div key={c.id} className="bg-white border border-stone-200 rounded-xl p-4" data-testid={`contract-card-${c.id}`}>
                    <div className="flex items-start justify-between">
                      <div>
                        <h4 className="text-sm font-bold text-stone-800">{c.vendor}</h4>
                        <p className="text-[10px] text-stone-400">{c.contact_name} · {c.contact_email}</p>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <Badge className={c.active ? "bg-emerald-100 text-emerald-700 text-[9px]" : "bg-stone-100 text-stone-500 text-[9px]"}>{c.active ? "Active" : "Inactive"}</Badge>
                        {isManager && <button onClick={() => deleteContract(c.id)} className="p-1 hover:bg-red-50 rounded"><Trash2 className="w-3 h-3 text-red-500" /></button>}
                      </div>
                    </div>
                    <div className="mt-2 flex items-center gap-3 text-[10px] text-stone-500">
                      <span>{c.start_date || "—"} → {c.end_date || "open"}</span>
                      <span>Pickup: {c.pickup_schedule}</span>
                    </div>
                    {c.rates?.length > 0 && (
                      <div className="mt-3 pt-2 border-t border-stone-100">
                        <p className="text-[10px] font-semibold text-stone-600 mb-1">Rates ({c.rates.length})</p>
                        <div className="grid grid-cols-2 gap-1 text-[10px]">
                          {c.rates.slice(0, 6).map((r, i) => (
                            <div key={i} className="flex justify-between text-stone-600"><span className="truncate">{r.name}</span><span className="font-mono">£{parseFloat(r.rate).toFixed(2)}</span></div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* REPORTS SECTION */}
      <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="laundry-reports">
        <h3 className="text-sm font-bold text-stone-800 mb-3 flex items-center gap-2">
          <FileBarChart className="w-4 h-4" />Reports
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
          {REPORTS.map(r => {
            const Icon = r.icon;
            return (
              <button key={r.id} onClick={() => openReport(r)} data-testid={`report-${r.id}`}
                className="flex items-center gap-3 p-3 rounded-lg border border-stone-200 hover:border-stone-400 hover:bg-stone-50 text-left transition">
                <div className={`w-10 h-10 rounded-lg ${r.color} flex items-center justify-center flex-shrink-0`}>
                  <Icon className="w-5 h-5" />
                </div>
                <div className="min-w-0">
                  <h4 className="text-xs font-bold text-stone-800">{r.label}</h4>
                  <p className="text-[10px] text-stone-500 truncate">{r.desc}</p>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Report Viewer Dialog */}
      <Dialog open={!!reportOpen} onOpenChange={o => !o && setReportOpen(null)}>
        <DialogContent className="max-w-4xl max-h-[85vh] overflow-y-auto" data-testid="report-viewer">
          <DialogHeader>
            <DialogTitle className="flex items-center justify-between">
              <span>{reportOpen?.label}</span>
              {reportData && <Button size="sm" variant="outline" onClick={exportCSV}><Download className="w-3 h-3 mr-1" />Export CSV</Button>}
            </DialogTitle>
            <DialogDescription>{reportOpen?.desc} {reportData?.start && `· ${reportData.start} → ${reportData.end}`}</DialogDescription>
          </DialogHeader>
          {reportLoading ? (
            <div className="flex items-center justify-center py-10 text-stone-400"><RefreshCw className="w-5 h-5 animate-spin mr-2" />Loading report...</div>
          ) : !reportData ? null : (
            <div className="space-y-3">
              {reportOpen?.id === "daily-usage" && (
                <>
                  <div className="grid grid-cols-3 gap-2">
                    <div className="bg-stone-50 p-3 rounded-lg"><p className="text-[10px] text-stone-500">Total Items Used</p><p className="text-lg font-bold text-stone-800">{reportData.total_items}</p></div>
                    <div className="bg-stone-50 p-3 rounded-lg"><p className="text-[10px] text-stone-500">Unique Rooms</p><p className="text-lg font-bold text-stone-800">{Object.keys(reportData.by_room || {}).length}</p></div>
                    <div className="bg-stone-50 p-3 rounded-lg"><p className="text-[10px] text-stone-500">Active Days</p><p className="text-lg font-bold text-stone-800">{Object.keys(reportData.by_date || {}).length}</p></div>
                  </div>
                  <table className="w-full text-xs">
                    <thead className="bg-stone-50"><tr><th className="text-left p-2">Date</th><th className="text-left p-2">Room</th><th className="text-left p-2">Item</th><th className="text-center p-2">Qty</th></tr></thead>
                    <tbody>
                      {(reportData.rows || []).slice(0, 100).map((r, i) => (
                        <tr key={i} className="border-t border-stone-100"><td className="p-2">{r.date}</td><td className="p-2 font-semibold">{r.room_number}</td><td className="p-2">{r.item_name}</td><td className="p-2 text-center font-bold text-blue-700">{r.qty}</td></tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}
              {reportOpen?.id === "count" && (
                <table className="w-full text-xs">
                  <thead className="bg-stone-50"><tr><th className="text-left p-2">Item</th><th className="text-center p-2">Total</th><th className="text-center p-2">Days</th><th className="text-center p-2">Rooms</th><th className="text-center p-2">Daily Avg</th><th className="text-center p-2">Anomaly</th></tr></thead>
                  <tbody>
                    {(reportData.items || []).map((r, i) => (
                      <tr key={i} className="border-t border-stone-100"><td className="p-2 font-semibold">{r.item}</td><td className="p-2 text-center font-bold">{r.total}</td><td className="p-2 text-center">{r.days_active}</td><td className="p-2 text-center">{r.rooms_active}</td><td className="p-2 text-center">{r.daily_avg}</td><td className="p-2 text-center">{r.anomaly && <Badge className="bg-red-100 text-red-700 text-[9px]"><AlertCircle className="w-2 h-2 inline mr-0.5" />Anomaly</Badge>}</td></tr>
                    ))}
                  </tbody>
                </table>
              )}
              {reportOpen?.id === "order" && (
                <table className="w-full text-xs">
                  <thead className="bg-stone-50"><tr><th className="text-left p-2">Item</th><th className="text-center p-2">Sent</th><th className="text-center p-2">Received</th><th className="text-center p-2">Variance</th></tr></thead>
                  <tbody>
                    {(reportData.items || []).map((r, i) => (
                      <tr key={i} className="border-t border-stone-100"><td className="p-2 font-semibold">{r.item}</td><td className="p-2 text-center">{r.sent}</td><td className="p-2 text-center text-emerald-700">{r.received}</td><td className={`p-2 text-center font-bold ${r.variance > 0 ? "text-red-600" : "text-stone-400"}`}>{r.variance === 0 ? "—" : `-${r.variance}`}</td></tr>
                    ))}
                  </tbody>
                </table>
              )}
              {reportOpen?.id === "dispatch" && (
                <>
                  <div className="grid grid-cols-3 gap-2">
                    <div className="bg-stone-50 p-3 rounded-lg"><p className="text-[10px] text-stone-500">Total Dispatches</p><p className="text-lg font-bold">{reportData.dispatches?.length || 0}</p></div>
                    <div className="bg-stone-50 p-3 rounded-lg"><p className="text-[10px] text-stone-500">Items Sent</p><p className="text-lg font-bold">{reportData.total_items}</p></div>
                    <div className="bg-stone-50 p-3 rounded-lg"><p className="text-[10px] text-stone-500">Total Cost</p><p className="text-lg font-bold text-violet-700">£{reportData.total_cost?.toFixed(2)}</p></div>
                  </div>
                  <table className="w-full text-xs">
                    <thead className="bg-stone-50"><tr><th className="text-left p-2">Date</th><th className="text-left p-2">Vendor</th><th className="text-center p-2">Items</th><th className="text-right p-2">Cost</th><th className="text-center p-2">Status</th></tr></thead>
                    <tbody>
                      {(reportData.dispatches || []).map((d, i) => (
                        <tr key={i} className="border-t border-stone-100"><td className="p-2">{d.sent_date}</td><td className="p-2 font-semibold">{d.vendor}</td><td className="p-2 text-center">{d.items?.reduce((s, it) => s + it.qty_sent, 0)}</td><td className="p-2 text-right font-mono">£{d.total_cost?.toFixed(2)}</td><td className="p-2 text-center"><Badge className={`${DISPATCH_STATUS_STYLE[d.status]} text-[9px]`}>{d.status}</Badge></td></tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}
              {reportOpen?.id === "monthly-audit" && (
                <table className="w-full text-xs">
                  <thead className="bg-stone-50"><tr><th className="text-left p-2">Item</th><th className="text-center p-2">Clean</th><th className="text-center p-2">Dirty</th><th className="text-center p-2">In Transit</th><th className="text-center p-2">Damaged</th><th className="text-center p-2">Used</th><th className="text-center p-2">Dispatched</th><th className="text-center p-2">Total</th></tr></thead>
                  <tbody>
                    {(reportData.audit || []).map((a, i) => (
                      <tr key={i} className="border-t border-stone-100"><td className="p-2 font-semibold">{a.item}</td><td className="p-2 text-center text-emerald-700">{a.clean}</td><td className="p-2 text-center text-amber-700">{a.dirty}</td><td className="p-2 text-center text-blue-700">{a.in_transit}</td><td className="p-2 text-center text-red-600">{a.damaged}</td><td className="p-2 text-center">{a.used_in_period}</td><td className="p-2 text-center">{a.dispatched_in_period}</td><td className="p-2 text-center font-bold">{a.total_inventory}</td></tr>
                    ))}
                  </tbody>
                </table>
              )}
              {reportOpen?.id === "group-update" && (
                <table className="w-full text-xs">
                  <thead className="bg-stone-50"><tr><th className="text-left p-2">Date</th><th className="text-left p-2">Type</th><th className="text-left p-2">Item/Ref</th><th className="text-center p-2">Qty</th><th className="text-center p-2">Δ Clean</th><th className="text-center p-2">Δ Dirty</th></tr></thead>
                  <tbody>
                    {(reportData.events || []).slice(0, 100).map((e, i) => (
                      <tr key={i} className="border-t border-stone-100"><td className="p-2">{e.date}</td><td className="p-2"><Badge className="bg-stone-100 text-stone-600 text-[9px]">{e.type}</Badge></td><td className="p-2">{e.item} {e.ref ? `· ${e.ref}` : ""}</td><td className="p-2 text-center">{e.qty}</td><td className={`p-2 text-center font-mono ${e.delta_clean > 0 ? "text-emerald-700" : e.delta_clean < 0 ? "text-red-600" : "text-stone-400"}`}>{e.delta_clean > 0 ? "+" : ""}{e.delta_clean}</td><td className={`p-2 text-center font-mono ${e.delta_dirty > 0 ? "text-amber-700" : e.delta_dirty < 0 ? "text-emerald-700" : "text-stone-400"}`}>{e.delta_dirty > 0 ? "+" : ""}{e.delta_dirty}</td></tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Dispatch Dialog */}
      <Dialog open={dispOpen} onOpenChange={setDispOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle>New Laundry Dispatch</DialogTitle><DialogDescription>Send linen to a vendor and track the return.</DialogDescription></DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-3 gap-2">
              <div><label className="text-xs font-semibold text-stone-600">Vendor</label><Input value={dispForm.vendor} onChange={e => setDispForm({ ...dispForm, vendor: e.target.value })} data-testid="dispatch-vendor-input" /></div>
              <div><label className="text-xs font-semibold text-stone-600">Sent Date</label><Input type="date" value={dispForm.sent_date} onChange={e => setDispForm({ ...dispForm, sent_date: e.target.value })} /></div>
              <div><label className="text-xs font-semibold text-stone-600">Expected Return</label><Input type="date" value={dispForm.expected_return} onChange={e => setDispForm({ ...dispForm, expected_return: e.target.value })} /></div>
            </div>
            <div>
              <div className="flex items-center justify-between mb-1"><label className="text-xs font-semibold text-stone-600">Items</label><Button size="sm" variant="outline" onClick={addDispItem} data-testid="add-dispatch-item"><Plus className="w-3 h-3 mr-1" />Add Line</Button></div>
              {dispForm.items.length === 0 && <p className="text-[10px] text-stone-400 py-2">No items yet. Click "Add Line" to start.</p>}
              {dispForm.items.map((it, i) => (
                <div key={i} className="grid grid-cols-12 gap-1.5 mb-1.5 items-center">
                  <Select value={it.item_id} onValueChange={v => updateDispItem(i, { item_id: v })}>
                    <SelectTrigger className="col-span-6 h-8 text-xs"><SelectValue placeholder="Select item" /></SelectTrigger>
                    <SelectContent>{catalog.map(c => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}</SelectContent>
                  </Select>
                  <Input type="number" value={it.qty_sent} onChange={e => updateDispItem(i, { qty_sent: parseInt(e.target.value) || 0 })} placeholder="Qty" className="col-span-2 h-8 text-xs" />
                  <Input type="number" step="0.01" value={it.rate} onChange={e => updateDispItem(i, { rate: parseFloat(e.target.value) || 0 })} placeholder="Rate £" className="col-span-3 h-8 text-xs" />
                  <button onClick={() => removeDispItem(i)} className="col-span-1 text-red-500 hover:bg-red-50 rounded p-1"><Trash2 className="w-3 h-3" /></button>
                </div>
              ))}
            </div>
            <div><label className="text-xs font-semibold text-stone-600">Notes</label><Textarea value={dispForm.notes} onChange={e => setDispForm({ ...dispForm, notes: e.target.value })} rows={2} /></div>
          </div>
          <DialogFooter><Button variant="outline" size="sm" onClick={() => setDispOpen(false)}>Cancel</Button><Button size="sm" className="bg-stone-800 hover:bg-stone-700 text-white" onClick={submitDispatch} data-testid="dispatch-submit-btn">Create Dispatch</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Usage Dialog */}
      <Dialog open={usageOpen} onOpenChange={setUsageOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle>Record Room Usage</DialogTitle><DialogDescription>Log linen collected from a specific room. This updates stock (clean→dirty) automatically.</DialogDescription></DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-3 gap-2">
              <div><label className="text-xs font-semibold text-stone-600">Date</label><Input type="date" value={usageForm.date} onChange={e => setUsageForm({ ...usageForm, date: e.target.value })} data-testid="usage-date-input" /></div>
              <div className="col-span-2">
                <label className="text-xs font-semibold text-stone-600">Room</label>
                {rooms.length > 0 ? (
                  <Select value={usageForm.room_id} onValueChange={v => {
                    const r = rooms.find(x => (x.id || x.room_id) === v);
                    setUsageForm({ ...usageForm, room_id: v, room_number: r?.number || r?.room_number || v });
                  }}>
                    <SelectTrigger data-testid="usage-room-select"><SelectValue placeholder="Select room" /></SelectTrigger>
                    <SelectContent>{rooms.slice(0, 100).map(r => <SelectItem key={r.id || r.room_id} value={r.id || r.room_id}>{r.number || r.room_number || r.name}</SelectItem>)}</SelectContent>
                  </Select>
                ) : (
                  <Input value={usageForm.room_number} onChange={e => setUsageForm({ ...usageForm, room_number: e.target.value, room_id: e.target.value })} placeholder="Room number (e.g. 204)" data-testid="usage-room-input" />
                )}
              </div>
            </div>
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs font-semibold text-stone-600">Housekeeping Record</label>
                <Button size="sm" variant="outline" onClick={addUsageItem} data-testid="add-usage-item"><Plus className="w-3 h-3 mr-1" />Add Item</Button>
              </div>
              <p className="text-[10px] text-stone-500 mb-2">
                <b>Clean Used</b> = pieces brought from clean stock into the room ·
                <b className="ml-1">Dirty Collected</b> = pieces taken from the room to laundry
              </p>
              {usageForm.items.length === 0 && <p className="text-[10px] text-stone-400 py-2">Add at least one item to record.</p>}
              {usageForm.items.length > 0 && (
                <div className="grid grid-cols-12 gap-1.5 mb-1 text-[10px] font-bold uppercase text-stone-500">
                  <div className="col-span-6">Item</div>
                  <div className="col-span-2 text-center">Clean Used ↓</div>
                  <div className="col-span-2 text-center">Dirty Collected ↑</div>
                  <div className="col-span-2"></div>
                </div>
              )}
              {usageForm.items.map((it, i) => (
                <div key={i} className="grid grid-cols-12 gap-1.5 mb-1.5 items-center">
                  <Select value={it.item_id} onValueChange={v => updateUsageItem(i, { item_id: v })}>
                    <SelectTrigger className="col-span-6 h-8 text-xs"><SelectValue placeholder="Select item" /></SelectTrigger>
                    <SelectContent>{catalog.map(c => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}</SelectContent>
                  </Select>
                  <Input type="number" min="0" value={it.clean_used || 0}
                         onChange={e => updateUsageItem(i, { clean_used: parseInt(e.target.value) || 0 })}
                         placeholder="Clean" className="col-span-2 h-8 text-xs text-right bg-emerald-50 border-emerald-200" data-testid={`usage-clean-${i}`} />
                  <Input type="number" min="0" value={it.dirty_collected || 0}
                         onChange={e => updateUsageItem(i, { dirty_collected: parseInt(e.target.value) || 0 })}
                         placeholder="Dirty" className="col-span-2 h-8 text-xs text-right bg-amber-50 border-amber-200" data-testid={`usage-dirty-${i}`} />
                  <div className="col-span-2 flex items-center justify-end gap-1">
                    {(it.clean_used || 0) !== (it.dirty_collected || 0) && (it.clean_used || it.dirty_collected) ? (
                      <span className="text-[9px] text-rose-500 font-semibold" title="Clean used and dirty collected differ">≠</span>
                    ) : null}
                    <button onClick={() => removeUsageItem(i)} className="text-red-500 hover:bg-red-50 rounded p-1"><Trash2 className="w-3 h-3" /></button>
                  </div>
                </div>
              ))}
              <div className="mt-3">
                <label className="text-xs font-semibold text-stone-600">Notes (optional)</label>
                <Input value={usageForm.notes || ""} onChange={e => setUsageForm(f => ({ ...f, notes: e.target.value }))}
                       placeholder="e.g. extra towel requested, sheet damage, etc." className="h-8 text-xs" data-testid="usage-notes-input" />
              </div>
            </div>
          </div>
          <DialogFooter><Button variant="outline" size="sm" onClick={() => setUsageOpen(false)}>Cancel</Button><Button size="sm" className="bg-stone-800 hover:bg-stone-700 text-white" onClick={submitUsage} data-testid="usage-submit-btn">Record</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Contract Dialog */}
      <Dialog open={contractOpen} onOpenChange={setContractOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle>New Laundry Contract</DialogTitle><DialogDescription>Set up rate card and terms with a laundry vendor.</DialogDescription></DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <div><label className="text-xs font-semibold text-stone-600">Vendor</label><Input value={contractForm.vendor} onChange={e => setContractForm({ ...contractForm, vendor: e.target.value })} data-testid="contract-vendor-input" /></div>
              <div><label className="text-xs font-semibold text-stone-600">Pickup Schedule</label><Select value={contractForm.pickup_schedule} onValueChange={v => setContractForm({ ...contractForm, pickup_schedule: v })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="daily">Daily</SelectItem><SelectItem value="weekly">Weekly</SelectItem><SelectItem value="biweekly">Bi-Weekly</SelectItem><SelectItem value="monthly">Monthly</SelectItem><SelectItem value="on_demand">On Demand</SelectItem></SelectContent></Select></div>
            </div>
            <div className="grid grid-cols-3 gap-2">
              <Input placeholder="Contact Name" value={contractForm.contact_name} onChange={e => setContractForm({ ...contractForm, contact_name: e.target.value })} />
              <Input placeholder="Email" value={contractForm.contact_email} onChange={e => setContractForm({ ...contractForm, contact_email: e.target.value })} />
              <Input placeholder="Phone" value={contractForm.contact_phone} onChange={e => setContractForm({ ...contractForm, contact_phone: e.target.value })} />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div><label className="text-xs font-semibold text-stone-600">Start Date</label><Input type="date" value={contractForm.start_date} onChange={e => setContractForm({ ...contractForm, start_date: e.target.value })} /></div>
              <div><label className="text-xs font-semibold text-stone-600">End Date</label><Input type="date" value={contractForm.end_date} onChange={e => setContractForm({ ...contractForm, end_date: e.target.value })} /></div>
            </div>
            <div>
              <div className="flex items-center justify-between mb-1"><label className="text-xs font-semibold text-stone-600">Rate Card</label><Button size="sm" variant="outline" onClick={addRate}><Plus className="w-3 h-3 mr-1" />Add Rate</Button></div>
              {contractForm.rates.map((r, i) => (
                <div key={i} className="grid grid-cols-12 gap-1.5 mb-1.5">
                  <Select value={r.item_id} onValueChange={v => updateRate(i, { item_id: v })}><SelectTrigger className="col-span-8 h-8 text-xs"><SelectValue placeholder="Select item" /></SelectTrigger><SelectContent>{catalog.map(c => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}</SelectContent></Select>
                  <Input type="number" step="0.01" value={r.rate} onChange={e => updateRate(i, { rate: parseFloat(e.target.value) || 0 })} placeholder="£ per item" className="col-span-4 h-8 text-xs" />
                </div>
              ))}
            </div>
            <div><label className="text-xs font-semibold text-stone-600">Terms</label><Textarea value={contractForm.terms} onChange={e => setContractForm({ ...contractForm, terms: e.target.value })} rows={3} /></div>
          </div>
          <DialogFooter><Button variant="outline" size="sm" onClick={() => setContractOpen(false)}>Cancel</Button><Button size="sm" className="bg-stone-800 hover:bg-stone-700 text-white" onClick={submitContract} data-testid="contract-submit-btn">Create Contract</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

/* ═══════════ STOCK TAB — with transactions (maintenance/disposal/write-off) ═══════════ */
const StockTab = ({ pid, stock, updateStockCell }) => {
  const [txns, setTxns] = useState([]);
  const [stats, setStats] = useState({});
  const [filter, setFilter] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [txType, setTxType] = useState("maintenance");
  const today = new Date().toISOString().slice(0, 10);
  const [form, setForm] = useState({
    item_id: "", name: "", quantity: 1, unit_cost: 0,
    transaction_date: today, reason: "", notes: "",
  });

  const loadTxns = async () => {
    try {
      const qs = filter ? `?tx_type=${filter}` : "";
      const { data } = await axios.get(`${API}/laundry/stock-transactions/${pid}${qs}`);
      setTxns(data.rows || []); setStats(data.stats || {});
    } catch { /* */ }
  };
  useEffect(() => { loadTxns(); /* eslint-disable-next-line */ }, [pid, filter]);

  const save = async () => {
    if (!form.item_id) return toast.error("Select an item");
    try {
      await axios.post(`${API}/laundry/stock-transactions/${pid}`, { ...form, tx_type: txType, reason: form.reason || txType });
      toast.success(`${txType} recorded`);
      setShowForm(false);
      setForm({ item_id: "", name: "", quantity: 1, unit_cost: 0, transaction_date: today, reason: "", notes: "" });
      loadTxns();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const del = async (id) => {
    if (!window.confirm("Delete this transaction?")) return;
    await axios.delete(`${API}/laundry/stock-transactions/${id}`);
    toast.success("Deleted"); loadTxns();
  };

  const openForm = (type) => { setTxType(type); setForm(f => ({ ...f, reason: type })); setShowForm(true); };

  const typeBadge = (t) => ({
    maintenance: "bg-amber-100 text-amber-700",
    disposal:    "bg-rose-100 text-rose-700",
    write_off:   "bg-stone-200 text-stone-700",
    found:       "bg-emerald-100 text-emerald-700",
    stock_in:    "bg-blue-100 text-blue-700",
    stock_out:   "bg-violet-100 text-violet-700",
  }[t] || "bg-stone-100 text-stone-600");

  return (
    <div className="space-y-3" data-testid="stock-panel">
      {/* Quick-action buttons */}
      <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
        {[
          { k: "maintenance", l: "Maintenance",  c: "border-amber-300 text-amber-700 hover:bg-amber-50" },
          { k: "disposal",    l: "Disposal",     c: "border-rose-300 text-rose-700 hover:bg-rose-50" },
          { k: "write_off",   l: "Write-Off",    c: "border-stone-300 text-stone-700 hover:bg-stone-100" },
          { k: "found",       l: "Found",        c: "border-emerald-300 text-emerald-700 hover:bg-emerald-50" },
          { k: "stock_in",    l: "Stock In",     c: "border-blue-300 text-blue-700 hover:bg-blue-50" },
          { k: "stock_out",   l: "Stock Out",    c: "border-violet-300 text-violet-700 hover:bg-violet-50" },
        ].map(b => (
          <button key={b.k} onClick={() => openForm(b.k)} className={`px-3 py-2.5 border rounded-xl text-xs font-semibold ${b.c}`} data-testid={`stock-tx-${b.k}-btn`}>
            + Record {b.l}
          </button>
        ))}
      </div>

      {/* Stat chips */}
      {Object.keys(stats).length > 0 && (
        <div className="flex gap-2 flex-wrap">
          {Object.entries(stats).map(([k, v]) => (
            <button key={k} onClick={() => setFilter(filter === k ? "" : k)} className={`px-3 py-1.5 rounded-lg text-xs border transition ${filter === k ? "bg-blue-50 border-blue-300" : "bg-white border-stone-200"}`}>
              <span className="font-semibold capitalize">{k.replace("_", " ")}</span>
              <span className="text-stone-500 ml-2">{v.count} · {v.qty} items · £{v.cost.toFixed(2)}</span>
            </button>
          ))}
          {filter && <button onClick={() => setFilter("")} className="px-2 py-1 text-xs text-stone-500 hover:text-stone-700">Clear filter ×</button>}
        </div>
      )}

      {/* Current Stock table */}
      <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
        <div className="px-3 py-2 bg-stone-50 border-b border-stone-200 text-xs font-bold text-stone-700">Current Stock Levels</div>
        <table className="w-full text-xs">
          <thead className="bg-stone-50 border-b border-stone-200">
            <tr>
              <th className="text-left py-2 px-3 font-semibold text-stone-600">Item</th>
              <th className="text-center py-2 px-3 font-semibold text-emerald-600">Clean</th>
              <th className="text-center py-2 px-3 font-semibold text-amber-600">Dirty</th>
              <th className="text-center py-2 px-3 font-semibold text-blue-600">In Transit</th>
              <th className="text-center py-2 px-3 font-semibold text-red-500">Damaged</th>
              <th className="text-center py-2 px-3 font-semibold text-stone-600">Total</th>
            </tr>
          </thead>
          <tbody>
            {stock.map(s => (
              <tr key={s.item_id} className="border-b border-stone-100 hover:bg-stone-50/50" data-testid={`stock-row-${s.item_id}`}>
                <td className="py-2 px-3 font-semibold text-stone-700">{s.name}</td>
                <td className="py-2 px-3 text-center"><input type="number" value={s.on_hand_clean} onChange={e => updateStockCell(s.item_id, "on_hand_clean", e.target.value)} className="w-16 text-center border border-stone-200 rounded px-1 py-0.5 text-xs" /></td>
                <td className="py-2 px-3 text-center"><input type="number" value={s.dirty} onChange={e => updateStockCell(s.item_id, "dirty", e.target.value)} className="w-16 text-center border border-stone-200 rounded px-1 py-0.5 text-xs" /></td>
                <td className="py-2 px-3 text-center font-semibold text-blue-600">{s.in_transit}</td>
                <td className="py-2 px-3 text-center"><input type="number" value={s.damaged} onChange={e => updateStockCell(s.item_id, "damaged", e.target.value)} className="w-16 text-center border border-stone-200 rounded px-1 py-0.5 text-xs" /></td>
                <td className="py-2 px-3 text-center font-bold text-stone-800">{s.total}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Transaction history */}
      <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
        <div className="px-3 py-2 bg-stone-50 border-b border-stone-200 text-xs font-bold text-stone-700">Transaction History ({txns.length})</div>
        {txns.length === 0 ? (
          <p className="text-center text-sm text-stone-400 py-8">No transactions yet — use the buttons above to record one.</p>
        ) : (
          <table className="w-full text-xs">
            <thead className="bg-stone-50 border-b border-stone-200">
              <tr>
                <th className="text-left py-2 px-3 font-semibold text-stone-600">Date</th>
                <th className="text-left py-2 px-3 font-semibold text-stone-600">Type</th>
                <th className="text-left py-2 px-3 font-semibold text-stone-600">Item</th>
                <th className="text-center py-2 px-3 font-semibold text-stone-600">Qty</th>
                <th className="text-right py-2 px-3 font-semibold text-stone-600">Unit £</th>
                <th className="text-right py-2 px-3 font-semibold text-stone-600">Total</th>
                <th className="text-left py-2 px-3 font-semibold text-stone-600">Reason / Notes</th>
                <th className="text-left py-2 px-3 font-semibold text-stone-600">By</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {txns.map(t => (
                <tr key={t.id} className="border-b border-stone-100 hover:bg-stone-50/50" data-testid={`stock-tx-row-${t.id.slice(0,6)}`}>
                  <td className="py-2 px-3 text-stone-600">{t.transaction_date}</td>
                  <td className="py-2 px-3"><Badge className={`${typeBadge(t.tx_type)} text-[10px]`}>{t.tx_type.replace("_", " ")}</Badge></td>
                  <td className="py-2 px-3 font-semibold text-stone-700">{t.name || t.item_id}</td>
                  <td className="py-2 px-3 text-center font-mono">{t.quantity}</td>
                  <td className="py-2 px-3 text-right font-mono">£{t.unit_cost?.toFixed(2)}</td>
                  <td className="py-2 px-3 text-right font-mono font-bold">£{t.total_cost?.toFixed(2)}</td>
                  <td className="py-2 px-3 text-stone-600 truncate max-w-xs">{t.notes || t.reason}</td>
                  <td className="py-2 px-3 text-stone-500 text-[10px]">{t.created_by}</td>
                  <td><button onClick={() => del(t.id)} className="text-rose-500 text-xs px-2">×</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Record Transaction Modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-6" onClick={() => setShowForm(false)}>
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full" onClick={e => e.stopPropagation()}>
            <div className="p-4 border-b border-stone-100 flex items-center justify-between">
              <h3 className="font-bold capitalize">Record {txType.replace("_", " ")}</h3>
              <button onClick={() => setShowForm(false)} className="text-stone-400 hover:text-stone-600 text-2xl leading-none">×</button>
            </div>
            <div className="p-4 space-y-3">
              <div>
                <label className="text-xs text-stone-500">Item *</label>
                <select value={form.item_id} onChange={e => {
                  const match = stock.find(s => s.item_id === e.target.value);
                  setForm(f => ({ ...f, item_id: e.target.value, name: match?.name || "" }));
                }} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" data-testid="stock-tx-item">
                  <option value="">Select item…</option>
                  {stock.map(s => <option key={s.item_id} value={s.item_id}>{s.name}</option>)}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-stone-500">Quantity *</label>
                  <input type="number" min="1" value={form.quantity} onChange={e => setForm(f => ({ ...f, quantity: parseInt(e.target.value) || 1 }))} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" data-testid="stock-tx-qty" />
                </div>
                <div>
                  <label className="text-xs text-stone-500">Unit Cost £</label>
                  <input type="number" step="0.01" value={form.unit_cost} onChange={e => setForm(f => ({ ...f, unit_cost: parseFloat(e.target.value) || 0 }))} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" />
                </div>
              </div>
              <div>
                <label className="text-xs text-stone-500">Transaction Date *</label>
                <input type="date" value={form.transaction_date} onChange={e => setForm(f => ({ ...f, transaction_date: e.target.value }))} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" />
              </div>
              <div>
                <label className="text-xs text-stone-500">Reason</label>
                <input value={form.reason} onChange={e => setForm(f => ({ ...f, reason: e.target.value }))} placeholder={txType} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" />
              </div>
              <div>
                <label className="text-xs text-stone-500">Notes</label>
                <textarea value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" rows={3} placeholder="Any details (e.g. 'Guest damage — room 204, stain couldn't be removed')" />
              </div>
              <div className="bg-stone-50 border border-stone-200 rounded-lg p-2 text-xs flex justify-between">
                <span className="text-stone-500">Total impact:</span>
                <span className="font-mono font-bold">£{(form.quantity * form.unit_cost).toFixed(2)}</span>
              </div>
            </div>
            <div className="p-4 border-t border-stone-100 flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => setShowForm(false)}>Cancel</Button>
              <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700 text-white" onClick={save} data-testid="stock-tx-submit">Record</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
const DeliveriesTab = ({ pid, dispatches, stock }) => {
  const [rows, setRows] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const emptyItem = { item_id: "", name: "", qty_received: 0, qty_shortage: 0, qty_damage: 0, qty_rejected: 0, reason: "", unit_cost: 0 };
  const today = new Date().toISOString().slice(0, 10);
  const [form, setForm] = useState({
    dispatch_id: "", delivery_date: today,
    invoice_number: "", notes: "", items: [{ ...emptyItem }],
  });

  const load = async () => {
    try { const { data } = await axios.get(`${API}/laundry/deliveries/${pid}`); setRows(data.rows || []); }
    catch { /* */ }
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [pid]);

  const save = async () => {
    if (form.items.length === 0 || !form.items.some(i => i.item_id)) return toast.error("Add at least one item");
    try {
      await axios.post(`${API}/laundry/deliveries/${pid}`, form);
      toast.success("Delivery recorded");
      setShowForm(false);
      setForm({ dispatch_id: "", delivery_date: today, invoice_number: "", notes: "", items: [{ ...emptyItem }] });
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const del = async (id) => {
    if (!window.confirm("Delete this delivery record?")) return;
    await axios.delete(`${API}/laundry/deliveries/${id}`);
    toast.success("Deleted"); load();
  };

  const addItem = () => setForm(f => ({ ...f, items: [...f.items, { ...emptyItem }] }));
  const updItem = (i, k, v) => setForm(f => { const arr = [...f.items]; arr[i] = { ...arr[i], [k]: v }; return { ...f, items: arr }; });
  const rmItem = (i) => setForm(f => { const arr = [...f.items]; arr.splice(i, 1); return { ...f, items: arr }; });

  const loadFromDispatch = (dispatch_id) => {
    const d = dispatches.find(x => x.id === dispatch_id);
    if (!d) return;
    setForm(f => ({
      ...f, dispatch_id,
      items: (d.items || []).map(it => ({
        ...emptyItem, item_id: it.item_id, name: it.name,
        qty_received: it.qty_sent,
        unit_cost: it.unit_cost || 0,
      })),
    }));
  };

  const gross = form.items.reduce((s, it) => s + Number(it.qty_received || 0) * Number(it.unit_cost || 0), 0);
  const deduction = form.items.reduce((s, it) => s + (Number(it.qty_shortage || 0) + Number(it.qty_damage || 0) + Number(it.qty_rejected || 0)) * Number(it.unit_cost || 0), 0);
  const net = gross - deduction;

  const statusBadge = (s) => s === "complete" ? "bg-emerald-100 text-emerald-700" : s === "short" ? "bg-rose-100 text-rose-700" : "bg-amber-100 text-amber-700";

  return (
    <div className="space-y-3" data-testid="deliveries-panel">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-bold text-stone-800">Laundry Deliveries ({rows.length})</h3>
          <p className="text-xs text-stone-500">Track items received from laundry company with discrepancy tracking.</p>
        </div>
        <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700 text-white" onClick={() => setShowForm(true)} data-testid="delivery-new-btn">
          + Record Delivery
        </Button>
      </div>

      <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
        {rows.length === 0 ? (
          <p className="text-center text-sm text-stone-400 py-12">No deliveries recorded yet.</p>
        ) : (
          <table className="w-full text-xs">
            <thead className="bg-stone-50 border-b border-stone-200">
              <tr>
                <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Date</th>
                <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Invoice #</th>
                <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Linked Dispatch</th>
                <th className="text-right py-2.5 px-3 font-semibold text-stone-600">Gross</th>
                <th className="text-right py-2.5 px-3 font-semibold text-stone-600">Deduction</th>
                <th className="text-right py-2.5 px-3 font-semibold text-stone-600">Net Payable</th>
                <th className="text-center py-2.5 px-3 font-semibold text-stone-600">Coverage</th>
                <th className="text-center py-2.5 px-3 font-semibold text-stone-600">Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map(r => (
                <tr key={r.id} className="border-b border-stone-100 hover:bg-stone-50/50" data-testid={`delivery-row-${r.id.slice(0,6)}`}>
                  <td className="py-2.5 px-3 text-stone-700">{r.delivery_date}</td>
                  <td className="py-2.5 px-3 font-mono text-stone-600">{r.invoice_number || "—"}</td>
                  <td className="py-2.5 px-3 text-stone-600">{r.dispatch_summary ? `${r.dispatch_summary.vendor} · ${r.dispatch_summary.dispatch_date}` : "—"}</td>
                  <td className="py-2.5 px-3 text-right font-mono text-stone-700">£{r.gross_amount?.toFixed(2)}</td>
                  <td className="py-2.5 px-3 text-right font-mono text-rose-600">£{r.deduction_amount?.toFixed(2)}</td>
                  <td className="py-2.5 px-3 text-right font-mono font-bold text-emerald-700">£{r.net_payable?.toFixed(2)}</td>
                  <td className="py-2.5 px-3 text-center text-stone-700">{r.coverage_pct != null ? `${r.coverage_pct}%` : "—"}</td>
                  <td className="py-2.5 px-3 text-center"><Badge className={statusBadge(r.status)}>{r.status}</Badge></td>
                  <td><button onClick={() => del(r.id)} className="text-rose-500 text-xs">Del</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Record Delivery Modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-6" onClick={() => setShowForm(false)}>
          <div className="bg-white rounded-2xl shadow-2xl max-w-3xl w-full max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="p-4 border-b border-stone-100 flex items-center justify-between">
              <div>
                <h3 className="font-bold">Record Delivery</h3>
                <p className="text-xs text-stone-500">Record items received from laundry company.</p>
              </div>
              <button onClick={() => setShowForm(false)} className="text-stone-400 hover:text-stone-600 text-2xl leading-none">×</button>
            </div>
            <div className="p-4 space-y-4">
              {/* Link to Dispatch */}
              <div className="border border-stone-200 rounded-xl p-3 space-y-3">
                <div className="text-xs font-semibold text-stone-600 uppercase">Link to Dispatch</div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-stone-500">Select Dispatch</label>
                    <select value={form.dispatch_id} onChange={e => loadFromDispatch(e.target.value)} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" data-testid="delivery-dispatch-select">
                      <option value="">None (no comparison)</option>
                      {dispatches.map(d => <option key={d.id} value={d.id}>{d.vendor} · {d.sent_date} · {d.items?.length || 0} items</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-stone-500">Delivery Date *</label>
                    <input type="date" value={form.delivery_date} onChange={e => setForm(f => ({ ...f, delivery_date: e.target.value }))} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" data-testid="delivery-date" />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-stone-500">Delivery Note / Invoice Number</label>
                    <input value={form.invoice_number} onChange={e => setForm(f => ({ ...f, invoice_number: e.target.value }))} placeholder="e.g. INV-2026-001" className="w-full mt-1 px-3 py-2 border rounded-lg text-sm font-mono" data-testid="delivery-invoice" />
                  </div>
                  <div>
                    <label className="text-xs text-stone-500">Notes</label>
                    <input value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} placeholder="Any additional notes…" className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" />
                  </div>
                </div>
              </div>

              {/* Items */}
              <div className="border border-stone-200 rounded-xl p-3">
                <div className="flex items-center justify-between mb-2">
                  <div className="text-xs font-semibold text-stone-600 uppercase">Items</div>
                  <button onClick={addItem} className="text-xs px-2 py-1 rounded border border-emerald-300 text-emerald-700" data-testid="delivery-add-item">+ Add Item</button>
                </div>
                <div className="grid grid-cols-[2fr,repeat(5,1fr),auto] gap-2 text-[10px] font-semibold text-stone-500 uppercase px-1 mb-1">
                  <div>Item</div><div>Received</div><div>Shortage</div><div>Damage</div><div>Rejected</div><div>Cost £</div><div></div>
                </div>
                {form.items.map((it, i) => (
                  <div key={i} className="grid grid-cols-[2fr,repeat(5,1fr),auto] gap-2 items-center mb-1">
                    <select value={it.item_id} onChange={e => {
                      const match = stock.find(s => s.item_id === e.target.value);
                      updItem(i, "item_id", e.target.value);
                      if (match) updItem(i, "name", match.name);
                    }} className="px-2 py-1 border rounded text-xs">
                      <option value="">Select item…</option>
                      {stock.map(s => <option key={s.item_id} value={s.item_id}>{s.name}</option>)}
                    </select>
                    <input type="number" min="0" value={it.qty_received} onChange={e => updItem(i, "qty_received", parseInt(e.target.value) || 0)} className="px-2 py-1 border rounded text-xs" />
                    <input type="number" min="0" value={it.qty_shortage} onChange={e => updItem(i, "qty_shortage", parseInt(e.target.value) || 0)} className="px-2 py-1 border rounded text-xs" />
                    <input type="number" min="0" value={it.qty_damage} onChange={e => updItem(i, "qty_damage", parseInt(e.target.value) || 0)} className="px-2 py-1 border rounded text-xs" />
                    <input type="number" min="0" value={it.qty_rejected} onChange={e => updItem(i, "qty_rejected", parseInt(e.target.value) || 0)} className="px-2 py-1 border rounded text-xs" />
                    <input type="number" step="0.01" min="0" value={it.unit_cost} onChange={e => updItem(i, "unit_cost", parseFloat(e.target.value) || 0)} className="px-2 py-1 border rounded text-xs" />
                    <button onClick={() => rmItem(i)} className="text-rose-500 text-xs">×</button>
                  </div>
                ))}
                {form.items.some(it => it.qty_shortage || it.qty_damage || it.qty_rejected) && (
                  <div className="mt-2 space-y-1">
                    {form.items.map((it, i) => ((it.qty_shortage || it.qty_damage || it.qty_rejected) ? (
                      <input key={i} value={it.reason} onChange={e => updItem(i, "reason", e.target.value)} placeholder={`Reason for ${it.name || "this item"} discrepancy…`} className="w-full px-2 py-1 border rounded text-xs bg-rose-50" />
                    ) : null))}
                  </div>
                )}
              </div>

              {/* Totals */}
              <div className="border border-stone-200 rounded-xl p-3 text-sm">
                <div className="flex justify-between py-1"><span className="text-stone-600">Gross Amount:</span><span className="font-mono">£{gross.toFixed(2)}</span></div>
                <div className="flex justify-between py-1"><span className="text-stone-600">Deductions:</span><span className="font-mono text-rose-600">-£{deduction.toFixed(2)}</span></div>
                <div className="flex justify-between py-1 border-t border-stone-200 mt-1 pt-2"><span className="font-bold">Net Payable:</span><span className="font-mono font-bold text-emerald-700">£{net.toFixed(2)}</span></div>
              </div>
            </div>
            <div className="p-4 border-t border-stone-100 flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => setShowForm(false)}>Cancel</Button>
              <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700 text-white" onClick={save} data-testid="delivery-submit-btn">Record Delivery</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};


/* ═══════════════════ ORDER FORECAST TAB ═══════════════════ */
const ForecastTab = ({ pid, onCreated, canSeeCosts = true }) => {
  const nextMonday = () => {
    const d = new Date();
    const day = d.getDay();                 // 0=Sun, 1=Mon, ...
    const diff = (8 - day) % 7 || 7;        // days until next Monday (>=1)
    d.setDate(d.getDate() + diff);
    return d.toISOString().slice(0, 10);
  };
  const [delivery, setDelivery] = useState(nextMonday());
  const [horizon, setHorizon] = useState(7);
  const [everyN, setEveryN] = useState(2);
  const [providers, setProviders] = useState([]);
  const [vendor, setVendor] = useState("");
  const [forecast, setForecast] = useState(null);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [editableItems, setEditableItems] = useState([]);  // user can override order qty
  const [globalBuffer, setGlobalBuffer] = useState(0);     // safety stock % applied to all

  const applyBuffer = (shortfall, pct) => Math.ceil((shortfall || 0) * (1 + (pct || 0) / 100));

  const runForecast = useCallback(async () => {
    if (!delivery) { toast.error("Pick a delivery date"); return; }
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/laundry/forecast/${pid}`, {
        params: { delivery_date: delivery, horizon_days: horizon, in_house_cleaning_every: everyN },
      });
      setForecast(data);
      setEditableItems(data.items.map(i => ({
        ...i,
        buffer_pct: globalBuffer,
        order_qty: applyBuffer(i.shortfall, globalBuffer),
      })));
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed to compute forecast"); }
    setLoading(false);
  }, [pid, delivery, horizon, everyN, globalBuffer]);

  useEffect(() => {
    axios.get(`${API}/laundry/providers/${pid}`).then(r => {
      const active = (r.data.providers || []).filter(p => p.status === "active");
      setProviders(active);
      if (active.length && !vendor) setVendor(active[0].name);
    }).catch(() => setProviders([]));
    runForecast();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pid]);

  const updateQty = (item_id, v) => {
    setEditableItems(arr => arr.map(x => x.item_id === item_id ? { ...x, order_qty: Math.max(0, parseInt(v) || 0) } : x));
  };

  const updateBuffer = (item_id, pct) => {
    setEditableItems(arr => arr.map(x => {
      if (x.item_id !== item_id) return x;
      const p = parseInt(pct) || 0;
      return { ...x, buffer_pct: p, order_qty: applyBuffer(x.shortfall, p) };
    }));
  };

  const applyGlobalBuffer = (pct) => {
    const p = parseInt(pct) || 0;
    setGlobalBuffer(p);
    setEditableItems(arr => arr.map(x => ({
      ...x, buffer_pct: p, order_qty: applyBuffer(x.shortfall, p),
    })));
  };

  const totals = () => {
    const qty = editableItems.reduce((s, x) => s + (x.order_qty || 0), 0);
    const cost = editableItems.reduce((s, x) => s + (x.order_qty || 0) * (x.washing_cost || 0), 0);
    return { qty, cost };
  };

  const createOrder = async () => {
    const lines = editableItems.filter(i => (i.order_qty || 0) > 0);
    if (!lines.length) return toast.error("No items to order");
    if (!vendor) return toast.error("Select a provider/vendor");
    if (!window.confirm(`Create dispatch to ${vendor} for ${lines.length} items (${totals().qty} pieces, est. £${totals().cost.toFixed(2)})?`)) return;
    setCreating(true);
    try {
      await axios.post(`${API}/laundry/forecast/${pid}/create-dispatch`, {
        vendor, delivery_date: delivery, horizon_days: horizon, in_house_cleaning_every: everyN,
        items: lines.map(l => ({
          item_id: l.item_id, name: l.name,
          qty_sent: l.order_qty, rate: l.washing_cost || 0,
        })),
      });
      toast.success(`Dispatch created — ${totals().qty} pieces → ${vendor}`);
      onCreated && onCreated();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    setCreating(false);
  };

  const fmt = (n) => `£${Number(n || 0).toFixed(2)}`;
  const t = totals();
  const daily = forecast?.daily || [];
  const maxEvents = Math.max(1, ...daily.map(d => d.events));

  return (
    <div className="space-y-4" data-testid="forecast-panel">
      {/* Controls */}
      <div className="bg-gradient-to-br from-fuchsia-50 to-white border border-fuchsia-200 rounded-xl p-4">
        <div className="flex items-center gap-2 mb-3">
          <Sparkles className="w-4 h-4 text-fuchsia-600" />
          <h3 className="text-sm font-bold text-stone-800">Smart Order Forecast</h3>
          <span className="text-xs text-stone-500">Computes next-week linen needs based on arrivals + in-house cleanings</span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
          <div>
            <label className="text-[11px] font-semibold text-stone-500 uppercase">Delivery Date</label>
            <input type="date" value={delivery} onChange={e => setDelivery(e.target.value)} className="w-full mt-1 px-3 py-2 border border-stone-200 rounded-lg text-sm" data-testid="forecast-delivery-date" />
          </div>
          <div>
            <label className="text-[11px] font-semibold text-stone-500 uppercase">Forecast Horizon</label>
            <select value={horizon} onChange={e => setHorizon(parseInt(e.target.value))} className="w-full mt-1 px-3 py-2 border border-stone-200 rounded-lg text-sm" data-testid="forecast-horizon">
              <option value={3}>3 days</option>
              <option value={7}>7 days (1 week)</option>
              <option value={14}>14 days (2 weeks)</option>
              <option value={30}>30 days</option>
            </select>
          </div>
          <div>
            <label className="text-[11px] font-semibold text-stone-500 uppercase">In-house Clean Every</label>
            <select value={everyN} onChange={e => setEveryN(parseInt(e.target.value))} className="w-full mt-1 px-3 py-2 border border-stone-200 rounded-lg text-sm" data-testid="forecast-every-n">
              <option value={1}>Daily</option>
              <option value={2}>Every 2 days</option>
              <option value={3}>Every 3 days</option>
              <option value={7}>Weekly</option>
            </select>
          </div>
          <div>
            <label className="text-[11px] font-semibold text-stone-500 uppercase">Provider / Vendor</label>
            {providers.length > 0 ? (
              <select value={vendor} onChange={e => setVendor(e.target.value)} className="w-full mt-1 px-3 py-2 border border-stone-200 rounded-lg text-sm" data-testid="forecast-vendor">
                {providers.map(p => <option key={p.id} value={p.name}>{p.name}</option>)}
              </select>
            ) : (
              <input value={vendor} onChange={e => setVendor(e.target.value)} placeholder="Vendor name" className="w-full mt-1 px-3 py-2 border border-stone-200 rounded-lg text-sm" />
            )}
          </div>
          <div className="md:col-span-2 flex items-end">
            <Button size="sm" className="w-full bg-fuchsia-600 hover:bg-fuchsia-700 text-white" onClick={runForecast} disabled={loading} data-testid="forecast-run">
              {loading ? <RefreshCw className="w-4 h-4 mr-1 animate-spin" /> : <TrendingUp className="w-4 h-4 mr-1" />}
              {loading ? "Computing..." : "Recompute Forecast"}
            </Button>
          </div>
        </div>
      </div>

      {forecast && (
        <>
          {/* Summary KPIs */}
          <div className={`grid gap-3 ${canSeeCosts ? "grid-cols-2 md:grid-cols-6" : "grid-cols-2 md:grid-cols-5"}`}>
            <div className="bg-white border border-stone-200 rounded-xl p-4 text-center">
              <p className="text-2xl font-black text-stone-700">{forecast.bookings_in_window}</p>
              <p className="text-[11px] text-stone-500">Bookings in window</p>
            </div>
            <div className="bg-rose-50 border border-rose-200 rounded-xl p-4 text-center" title={`Cleaning events between today and ${delivery}`}>
              <p className="text-2xl font-black text-rose-600">{forecast.pre_delivery_events || 0}</p>
              <p className="text-[11px] text-rose-600">Pre-delivery events ({forecast.pre_delivery_days || 0}d)</p>
            </div>
            <div className="bg-white border border-stone-200 rounded-xl p-4 text-center">
              <p className="text-2xl font-black text-blue-600">{forecast.total_cleaning_events}</p>
              <p className="text-[11px] text-stone-500">Horizon cleaning events</p>
            </div>
            <div className="bg-white border border-stone-200 rounded-xl p-4 text-center">
              <p className="text-2xl font-black text-fuchsia-600">{t.qty}</p>
              <p className="text-[11px] text-stone-500">Total pieces to order</p>
            </div>
            {canSeeCosts && (
              <div className="bg-white border border-stone-200 rounded-xl p-4 text-center">
                <p className="text-2xl font-black text-emerald-600">{fmt(t.cost)}</p>
                <p className="text-[11px] text-stone-500">Estimated cost</p>
              </div>
            )}
            <div className="bg-white border border-stone-200 rounded-xl p-4 text-center">
              <p className="text-2xl font-black text-amber-600">{editableItems.filter(i => i.order_qty > 0).length}</p>
              <p className="text-[11px] text-stone-500">Items to order</p>
            </div>
          </div>

          {/* Daily breakdown */}
          <div className="bg-white border border-stone-200 rounded-xl p-4">
            <h4 className="text-sm font-bold text-stone-800 mb-2">Daily Cleaning Events</h4>
            <div className="flex items-end gap-2 h-28" data-testid="forecast-daily">
              {daily.map(d => {
                const h = (d.events / maxEvents) * 100;
                const dd = new Date(d.date);
                const label = dd.toLocaleDateString("en-GB", { weekday: "short", day: "numeric" });
                return (
                  <div key={d.date} className="flex-1 flex flex-col items-center justify-end gap-1">
                    <div className="text-xs font-bold text-stone-700">{d.events || ""}</div>
                    <div className="w-full bg-stone-100 rounded-t relative overflow-hidden" style={{ height: "70%" }}>
                      {d.arrivals > 0 && (
                        <div className="absolute bottom-0 left-0 right-0 bg-emerald-500"
                             style={{ height: `${(d.arrivals / maxEvents) * 100}%` }}
                             title={`${d.arrivals} arrivals`} />
                      )}
                      {d.in_house_cleanings > 0 && (
                        <div className="absolute left-0 right-0 bg-blue-500"
                             style={{ bottom: `${(d.arrivals / maxEvents) * 100}%`,
                                      height: `${(d.in_house_cleanings / maxEvents) * 100}%` }}
                             title={`${d.in_house_cleanings} in-house cleanings`} />
                      )}
                    </div>
                    <div className="text-[10px] text-stone-500 text-center leading-tight">{label}</div>
                  </div>
                );
              })}
            </div>
            <div className="flex items-center gap-4 mt-2 text-xs text-stone-500">
              <span className="flex items-center gap-1"><span className="w-3 h-3 bg-emerald-500 rounded"></span>Arrivals (new guests)</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 bg-blue-500 rounded"></span>In-house cleanings (every {everyN}d)</span>
            </div>
          </div>

          {/* Order table */}
          <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
            <div className="p-3 border-b border-stone-200 flex items-center justify-between flex-wrap gap-2">
              <div className="flex items-center gap-3">
                <h4 className="text-sm font-bold text-stone-800">Suggested Order</h4>
                <div className="flex items-center gap-2 bg-amber-50 border border-amber-200 rounded-lg px-3 py-1.5">
                  <span className="text-xs font-semibold text-amber-800">Safety Buffer</span>
                  <select value={globalBuffer} onChange={e => applyGlobalBuffer(e.target.value)}
                          className="text-xs border border-amber-300 rounded bg-white px-2 py-0.5 font-mono font-bold text-amber-700"
                          data-testid="forecast-global-buffer">
                    <option value={0}>None</option>
                    <option value={5}>+5%</option>
                    <option value={10}>+10%</option>
                    <option value={15}>+15%</option>
                    <option value={20}>+20%</option>
                    <option value={25}>+25%</option>
                  </select>
                  <span className="text-[11px] text-amber-700">applies to all rows</span>
                </div>
              </div>
              <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700 text-white" onClick={createOrder} disabled={creating || t.qty === 0} data-testid="forecast-create-dispatch">
                {creating ? <RefreshCw className="w-4 h-4 mr-1 animate-spin" /> : <Send className="w-4 h-4 mr-1" />}
                Create Dispatch → {vendor || "vendor"}
              </Button>
            </div>
            <table className="w-full text-sm">
              <thead className="bg-stone-50 border-b border-stone-200">
                <tr>
                  <th className="text-left py-2 px-3 font-semibold text-stone-600">Item</th>
                  <th className="text-center py-2 px-3 font-semibold text-stone-600">Per Cleaning</th>
                  <th className="text-center py-2 px-3 font-semibold text-stone-600" title="Current clean stock on hand today">Stock Now</th>
                  <th className="text-center py-2 px-3 font-semibold text-stone-600" title={`Consumed between today and ${delivery} (pre-delivery)`}>Used Before Delivery</th>
                  <th className="text-center py-2 px-3 font-semibold text-stone-600" title="Stock Now minus Used Before Delivery">Remain @ Delivery</th>
                  <th className="text-center py-2 px-3 font-semibold text-stone-600" title={`Pieces needed during the ${horizon}-day horizon after delivery`}>Horizon Need</th>
                  <th className="text-center py-2 px-3 font-semibold text-stone-600">Shortfall</th>
                  <th className="text-center py-2 px-3 font-semibold text-stone-600">Safety +%</th>
                  <th className="text-center py-2 px-3 font-semibold text-stone-600">Order Qty</th>
                  {canSeeCosts && <th className="text-right py-2 px-3 font-semibold text-stone-600">Unit £</th>}
                  {canSeeCosts && <th className="text-right py-2 px-3 font-semibold text-stone-600">Line Total</th>}
                </tr>
              </thead>
              <tbody>
                {editableItems.map(i => {
                  const line = (i.order_qty || 0) * (i.washing_cost || 0);
                  const extraQty = (i.order_qty || 0) - (i.shortfall || 0);
                  return (
                    <tr key={i.item_id} className={`border-b border-stone-100 ${i.shortfall > 0 ? "" : "opacity-60"}`} data-testid={`forecast-row-${i.item_id}`}>
                      <td className="py-2 px-3 font-semibold text-stone-800">{i.name}</td>
                      <td className="py-2 px-3 text-center text-stone-600">× {i.per_cleaning_qty}</td>
                      <td className="py-2 px-3 text-center font-mono text-stone-700">{i.on_hand_clean}</td>
                      <td className="py-2 px-3 text-center font-mono text-rose-600">
                        {i.used_before_delivery > 0 ? `-${i.used_before_delivery}` : "0"}
                      </td>
                      <td className="py-2 px-3 text-center font-mono font-bold text-blue-700">{i.remaining_at_delivery}</td>
                      <td className="py-2 px-3 text-center font-mono text-stone-700">{i.needed}</td>
                      <td className="py-2 px-3 text-center">
                        {i.shortfall > 0
                          ? <Badge className="bg-rose-100 text-rose-700 font-mono">{i.shortfall}</Badge>
                          : <Badge className="bg-emerald-100 text-emerald-700 font-mono">OK</Badge>}
                      </td>
                      <td className="py-2 px-3 text-center">
                        <select value={i.buffer_pct || 0} onChange={e => updateBuffer(i.item_id, e.target.value)}
                                className="w-20 px-1 py-1 border border-stone-200 rounded text-xs font-mono font-bold text-amber-700 bg-amber-50"
                                data-testid={`forecast-buffer-${i.item_id}`}>
                          <option value={0}>0%</option>
                          <option value={5}>+5%</option>
                          <option value={10}>+10%</option>
                          <option value={15}>+15%</option>
                          <option value={20}>+20%</option>
                          <option value={25}>+25%</option>
                          <option value={30}>+30%</option>
                          <option value={50}>+50%</option>
                        </select>
                      </td>
                      <td className="py-2 px-3 text-center">
                        <div className="flex flex-col items-center">
                          <input type="number" min="0" value={i.order_qty || 0}
                                 onChange={e => updateQty(i.item_id, e.target.value)}
                                 className="w-20 px-2 py-1 border border-stone-200 rounded text-sm text-right font-mono"
                                 data-testid={`forecast-qty-${i.item_id}`} />
                          {extraQty > 0 && (
                            <span className="text-[10px] text-amber-600 font-mono mt-0.5">+{extraQty} safety</span>
                          )}
                        </div>
                      </td>
                      <td className="py-2 px-3 text-right font-mono text-stone-600">{canSeeCosts ? fmt(i.washing_cost) : null}</td>
                      <td className="py-2 px-3 text-right font-mono font-bold text-stone-800">{canSeeCosts ? fmt(line) : null}</td>
                    </tr>
                  );
                })}
              </tbody>
              <tfoot className="bg-stone-50 border-t-2 border-stone-200">
                <tr>
                  <td colSpan={8} className="py-2 px-3 text-right font-bold text-stone-700">Totals</td>
                  <td className="py-2 px-3 text-center font-mono font-black text-fuchsia-700">{t.qty}</td>
                  {canSeeCosts && <td></td>}
                  {canSeeCosts && <td className="py-2 px-3 text-right font-mono font-black text-stone-900">{fmt(t.cost)}</td>}
                </tr>
              </tfoot>
            </table>
          </div>
        </>
      )}
    </div>
  );
};
