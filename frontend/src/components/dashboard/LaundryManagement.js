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
  RefreshCw, Plus, Truck, Package, FileText, Shirt, CheckCircle2,
  Trash2, ArrowDown, Building2,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const TABS = [
  { id: "dispatches", label: "Dispatches", icon: Truck },
  { id: "stock",      label: "Stock",      icon: Package },
  { id: "contracts",  label: "Contracts",  icon: FileText },
];

const DISPATCH_STATUS_STYLE = {
  pending:  "bg-stone-100 text-stone-600",
  sent:     "bg-amber-100 text-amber-700",
  received: "bg-emerald-100 text-emerald-700",
  invoiced: "bg-blue-100 text-blue-700",
  paid:     "bg-violet-100 text-violet-700",
};

export const LaundryManagement = ({ propertyId, user }) => {
  const [tab, setTab] = useState("dispatches");
  const [dispatches, setDispatches] = useState({ dispatches: [], kpis: {} });
  const [stock, setStock] = useState([]);
  const [contracts, setContracts] = useState([]);
  const [catalog, setCatalog] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dispOpen, setDispOpen] = useState(false);
  const [contractOpen, setContractOpen] = useState(false);
  const [dispForm, setDispForm] = useState({ vendor: "", sent_date: new Date().toISOString().slice(0, 10), expected_return: "", items: [], notes: "" });
  const [contractForm, setContractForm] = useState({
    vendor: "", contact_name: "", contact_email: "", contact_phone: "",
    start_date: "", end_date: "", pickup_schedule: "weekly", terms: "", rates: [], active: true,
  });

  const pid = propertyId || "all";
  const isManager = user?.role === "admin" || user?.role === "manager";

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [d, s, c, cat] = await Promise.all([
        axios.get(`${API}/laundry/dispatches/${pid}`),
        axios.get(`${API}/laundry/stock/${pid}`),
        axios.get(`${API}/laundry/contracts/${pid}`).catch(() => ({ data: { contracts: [] } })),
        axios.get(`${API}/laundry/catalog`),
      ]);
      setDispatches(d.data);
      setStock(s.data.stock || []);
      setContracts(c.data.contracts || []);
      setCatalog(cat.data.items || []);
    } catch { /* silent */ }
    setLoading(false);
  }, [pid]);

  useEffect(() => { load(); }, [load]);

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
    if (!dispForm.vendor.trim() || dispForm.items.length === 0) {
      toast.error("Vendor and at least one item required"); return;
    }
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

  const updateStockCell = async (item_id, field, value) => {
    const row = stock.find(s => s.item_id === item_id);
    try {
      await axios.put(`${API}/laundry/stock/${pid}/${item_id}`, {
        [field]: parseInt(value) || 0,
        name: row?.name || item_id,
      });
      load();
    } catch { toast.error("Failed"); }
  };

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
    try {
      await axios.delete(`${API}/laundry/contracts/${pid}/${id}`);
      toast.success("Deleted");
      load();
    } catch { toast.error("Failed"); }
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

  const k = dispatches.kpis || {};

  return (
    <div className="space-y-5" data-testid="laundry-management">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Shirt className="w-5 h-5 text-stone-700" />
          <h2 className="text-base font-bold text-stone-800" data-testid="laundry-title">Laundry Management</h2>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-5 gap-3" data-testid="laundry-kpis">
        <div className="bg-stone-50 border border-stone-200 rounded-xl p-4 text-center"><p className="text-2xl font-black text-stone-700">{k.total_items || 0}</p><p className="text-[10px] text-stone-500">Items Sent (YTD)</p></div>
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-center"><Truck className="w-4 h-4 mx-auto mb-1 text-amber-600" /><p className="text-2xl font-black text-amber-700">{k.sent || 0}</p><p className="text-[10px] text-amber-600">Sent</p></div>
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-center"><CheckCircle2 className="w-4 h-4 mx-auto mb-1 text-emerald-600" /><p className="text-2xl font-black text-emerald-700">{k.received || 0}</p><p className="text-[10px] text-emerald-600">Received</p></div>
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-center"><Building2 className="w-4 h-4 mx-auto mb-1 text-blue-600" /><p className="text-2xl font-black text-blue-700">{contracts.length}</p><p className="text-[10px] text-blue-600">Active Contracts</p></div>
        <div className="bg-violet-50 border border-violet-200 rounded-xl p-4 text-center"><p className="text-2xl font-black text-violet-700">£{k.total_cost?.toFixed(0) || 0}</p><p className="text-[10px] text-violet-600">Total Spend</p></div>
      </div>

      {/* Tabs */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1 bg-stone-100 rounded-lg p-0.5">
          {TABS.map(t => {
            const Icon = t.icon;
            return (
              <button key={t.id} onClick={() => setTab(t.id)} data-testid={`tab-${t.id}`}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-md ${tab === t.id ? "bg-white text-stone-800 shadow-sm" : "text-stone-500"}`}>
                <Icon className="w-3.5 h-3.5" />{t.label}
              </button>
            );
          })}
        </div>
        {tab === "dispatches" && (
          <Button size="sm" onClick={() => setDispOpen(true)} className="bg-stone-800 hover:bg-stone-700 text-white" data-testid="new-dispatch-btn">
            <Plus className="w-4 h-4 mr-1.5" />New Dispatch
          </Button>
        )}
        {tab === "contracts" && isManager && (
          <Button size="sm" onClick={() => setContractOpen(true)} className="bg-stone-800 hover:bg-stone-700 text-white" data-testid="new-contract-btn">
            <Plus className="w-4 h-4 mr-1.5" />New Contract
          </Button>
        )}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20 text-stone-400"><RefreshCw className="w-5 h-5 animate-spin mr-2" />Loading...</div>
      ) : (
        <>
          {/* Dispatches Tab */}
          {tab === "dispatches" && (
            <div className="bg-white border border-stone-200 rounded-xl overflow-hidden" data-testid="dispatches-table">
              {dispatches.dispatches.length === 0 ? (
                <p className="text-center text-sm text-stone-400 py-12">No dispatches yet.</p>
              ) : (
                <table className="w-full text-xs">
                  <thead className="bg-stone-50 border-b border-stone-200">
                    <tr>
                      <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Vendor</th>
                      <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Sent</th>
                      <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Expected</th>
                      <th className="text-center py-2.5 px-3 font-semibold text-stone-600">Items</th>
                      <th className="text-right py-2.5 px-3 font-semibold text-stone-600">Cost</th>
                      <th className="text-center py-2.5 px-3 font-semibold text-stone-600">Status</th>
                      <th className="text-right py-2.5 px-3 font-semibold text-stone-600">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dispatches.dispatches.map(d => (
                      <tr key={d.id} className="border-b border-stone-100 hover:bg-stone-50/50" data-testid={`dispatch-row-${d.id}`}>
                        <td className="py-2.5 px-3 font-semibold text-stone-700">{d.vendor}</td>
                        <td className="py-2.5 px-3 text-stone-600">{d.sent_date}</td>
                        <td className="py-2.5 px-3 text-stone-600">{d.expected_return || "—"}</td>
                        <td className="py-2.5 px-3 text-center font-semibold text-stone-700">{d.items.reduce((s, i) => s + i.qty_sent, 0)}</td>
                        <td className="py-2.5 px-3 text-right font-mono text-stone-700">£{d.total_cost?.toFixed(2)}</td>
                        <td className="py-2.5 px-3 text-center">
                          <Badge className={`${DISPATCH_STATUS_STYLE[d.status] || "bg-stone-100"} text-[9px] capitalize`}>{d.status}</Badge>
                        </td>
                        <td className="py-2.5 px-3 text-right">
                          {d.status === "sent" && (
                            <button onClick={() => receiveDispatch(d)} className="text-[10px] px-2 py-1 bg-emerald-50 text-emerald-700 rounded hover:bg-emerald-100 font-semibold" data-testid={`receive-btn-${d.id}`}>
                              <ArrowDown className="w-3 h-3 inline mr-1" />Receive
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {/* Stock Tab */}
          {tab === "stock" && (
            <div className="bg-white border border-stone-200 rounded-xl overflow-hidden" data-testid="stock-table">
              <table className="w-full text-xs">
                <thead className="bg-stone-50 border-b border-stone-200">
                  <tr>
                    <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Item</th>
                    <th className="text-center py-2.5 px-3 font-semibold text-emerald-600">Clean</th>
                    <th className="text-center py-2.5 px-3 font-semibold text-amber-600">Dirty</th>
                    <th className="text-center py-2.5 px-3 font-semibold text-blue-600">In Transit</th>
                    <th className="text-center py-2.5 px-3 font-semibold text-red-500">Damaged</th>
                    <th className="text-center py-2.5 px-3 font-semibold text-stone-600">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {stock.map(s => (
                    <tr key={s.item_id} className="border-b border-stone-100 hover:bg-stone-50/50" data-testid={`stock-row-${s.item_id}`}>
                      <td className="py-2 px-3 font-semibold text-stone-700">{s.name}</td>
                      <td className="py-2 px-3 text-center">
                        <input type="number" value={s.on_hand_clean} onChange={e => updateStockCell(s.item_id, "on_hand_clean", e.target.value)} className="w-16 text-center border border-stone-200 rounded px-1 py-0.5 text-xs" data-testid={`stock-clean-${s.item_id}`} />
                      </td>
                      <td className="py-2 px-3 text-center">
                        <input type="number" value={s.dirty} onChange={e => updateStockCell(s.item_id, "dirty", e.target.value)} className="w-16 text-center border border-stone-200 rounded px-1 py-0.5 text-xs" />
                      </td>
                      <td className="py-2 px-3 text-center font-semibold text-blue-600">{s.in_transit}</td>
                      <td className="py-2 px-3 text-center">
                        <input type="number" value={s.damaged} onChange={e => updateStockCell(s.item_id, "damaged", e.target.value)} className="w-16 text-center border border-stone-200 rounded px-1 py-0.5 text-xs" />
                      </td>
                      <td className="py-2 px-3 text-center font-bold text-stone-800">{s.total}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Contracts Tab */}
          {tab === "contracts" && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3" data-testid="contracts-list">
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
                          <div key={i} className="flex justify-between text-stone-600">
                            <span className="truncate">{r.name}</span>
                            <span className="font-mono">£{parseFloat(r.rate).toFixed(2)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {c.terms && <p className="text-[10px] text-stone-500 mt-2 line-clamp-2">{c.terms}</p>}
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* Dispatch Dialog */}
      <Dialog open={dispOpen} onOpenChange={setDispOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>New Laundry Dispatch</DialogTitle>
            <DialogDescription>Send linen to a vendor and track the return.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-3 gap-2">
              <div>
                <label className="text-xs font-semibold text-stone-600">Vendor</label>
                <Input value={dispForm.vendor} onChange={e => setDispForm({ ...dispForm, vendor: e.target.value })} data-testid="dispatch-vendor-input" />
              </div>
              <div>
                <label className="text-xs font-semibold text-stone-600">Sent Date</label>
                <Input type="date" value={dispForm.sent_date} onChange={e => setDispForm({ ...dispForm, sent_date: e.target.value })} />
              </div>
              <div>
                <label className="text-xs font-semibold text-stone-600">Expected Return</label>
                <Input type="date" value={dispForm.expected_return} onChange={e => setDispForm({ ...dispForm, expected_return: e.target.value })} />
              </div>
            </div>
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs font-semibold text-stone-600">Items</label>
                <Button size="sm" variant="outline" onClick={addDispItem} data-testid="add-dispatch-item"><Plus className="w-3 h-3 mr-1" />Add Line</Button>
              </div>
              {dispForm.items.length === 0 && <p className="text-[10px] text-stone-400 py-2">No items yet. Click "Add Line" to start.</p>}
              {dispForm.items.map((it, i) => (
                <div key={i} className="grid grid-cols-12 gap-1.5 mb-1.5 items-center">
                  <Select value={it.item_id} onValueChange={v => updateDispItem(i, { item_id: v })}>
                    <SelectTrigger className="col-span-6 h-8 text-xs"><SelectValue placeholder="Select item" /></SelectTrigger>
                    <SelectContent>
                      {catalog.map(c => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
                    </SelectContent>
                  </Select>
                  <Input type="number" value={it.qty_sent} onChange={e => updateDispItem(i, { qty_sent: parseInt(e.target.value) || 0 })} placeholder="Qty" className="col-span-2 h-8 text-xs" />
                  <Input type="number" step="0.01" value={it.rate} onChange={e => updateDispItem(i, { rate: parseFloat(e.target.value) || 0 })} placeholder="Rate £" className="col-span-3 h-8 text-xs" />
                  <button onClick={() => removeDispItem(i)} className="col-span-1 text-red-500 hover:bg-red-50 rounded p-1"><Trash2 className="w-3 h-3" /></button>
                </div>
              ))}
            </div>
            <div>
              <label className="text-xs font-semibold text-stone-600">Notes</label>
              <Textarea value={dispForm.notes} onChange={e => setDispForm({ ...dispForm, notes: e.target.value })} rows={2} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" size="sm" onClick={() => setDispOpen(false)}>Cancel</Button>
            <Button size="sm" className="bg-stone-800 hover:bg-stone-700 text-white" onClick={submitDispatch} data-testid="dispatch-submit-btn">Create Dispatch</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Contract Dialog */}
      <Dialog open={contractOpen} onOpenChange={setContractOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>New Laundry Contract</DialogTitle>
            <DialogDescription>Set up rate card and terms with a laundry vendor.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs font-semibold text-stone-600">Vendor</label>
                <Input value={contractForm.vendor} onChange={e => setContractForm({ ...contractForm, vendor: e.target.value })} data-testid="contract-vendor-input" />
              </div>
              <div>
                <label className="text-xs font-semibold text-stone-600">Pickup Schedule</label>
                <Select value={contractForm.pickup_schedule} onValueChange={v => setContractForm({ ...contractForm, pickup_schedule: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="daily">Daily</SelectItem>
                    <SelectItem value="weekly">Weekly</SelectItem>
                    <SelectItem value="biweekly">Bi-Weekly</SelectItem>
                    <SelectItem value="monthly">Monthly</SelectItem>
                    <SelectItem value="on_demand">On Demand</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-2">
              <Input placeholder="Contact Name" value={contractForm.contact_name} onChange={e => setContractForm({ ...contractForm, contact_name: e.target.value })} />
              <Input placeholder="Email" value={contractForm.contact_email} onChange={e => setContractForm({ ...contractForm, contact_email: e.target.value })} />
              <Input placeholder="Phone" value={contractForm.contact_phone} onChange={e => setContractForm({ ...contractForm, contact_phone: e.target.value })} />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs font-semibold text-stone-600">Start Date</label>
                <Input type="date" value={contractForm.start_date} onChange={e => setContractForm({ ...contractForm, start_date: e.target.value })} />
              </div>
              <div>
                <label className="text-xs font-semibold text-stone-600">End Date</label>
                <Input type="date" value={contractForm.end_date} onChange={e => setContractForm({ ...contractForm, end_date: e.target.value })} />
              </div>
            </div>
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs font-semibold text-stone-600">Rate Card</label>
                <Button size="sm" variant="outline" onClick={addRate}><Plus className="w-3 h-3 mr-1" />Add Rate</Button>
              </div>
              {contractForm.rates.map((r, i) => (
                <div key={i} className="grid grid-cols-12 gap-1.5 mb-1.5">
                  <Select value={r.item_id} onValueChange={v => updateRate(i, { item_id: v })}>
                    <SelectTrigger className="col-span-8 h-8 text-xs"><SelectValue placeholder="Select item" /></SelectTrigger>
                    <SelectContent>
                      {catalog.map(c => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
                    </SelectContent>
                  </Select>
                  <Input type="number" step="0.01" value={r.rate} onChange={e => updateRate(i, { rate: parseFloat(e.target.value) || 0 })} placeholder="£ per item" className="col-span-4 h-8 text-xs" />
                </div>
              ))}
            </div>
            <div>
              <label className="text-xs font-semibold text-stone-600">Terms</label>
              <Textarea value={contractForm.terms} onChange={e => setContractForm({ ...contractForm, terms: e.target.value })} rows={3} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" size="sm" onClick={() => setContractOpen(false)}>Cancel</Button>
            <Button size="sm" className="bg-stone-800 hover:bg-stone-700 text-white" onClick={submitContract} data-testid="contract-submit-btn">Create Contract</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};
