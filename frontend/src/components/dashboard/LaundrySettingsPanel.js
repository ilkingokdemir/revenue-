/**
 * Laundry Settings Panel (Iter 165.4) — parity with MyHotelBox settings side
 *
 * Two tabs:
 *  1. Providers — external laundry services CRUD
 *  2. Contracts — pricing agreements (Per Piece / Flat Rate / Hybrid)
 *
 * Matches the competitor screenshots: provider status + active contracts count,
 * pricing model selector, pickup/return day-of-week schedule.
 */
import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Plus, Trash2, Pencil, ShieldCheck, Users } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

const PRICING_MODELS = [
  { k: "per_piece", l: "Per Piece", d: "Charged per item sent" },
  { k: "flat_rate", l: "Flat Rate", d: "Fixed fee per billing period" },
  { k: "hybrid",    l: "Hybrid (Quota + Overage)", d: "Included pieces + overage £/piece" },
];

const LaundrySettingsPanel = ({ activePropertyId }) => {
  const pid = activePropertyId || "aldgate-flats";
  const [tab, setTab] = useState("providers");

  return (
    <div className="p-6 space-y-4" data-testid="laundry-settings-panel">
      <div>
        <div className="text-xs text-stone-400">Settings</div>
        <h2 className="text-2xl font-bold">Laundry Settings</h2>
        <p className="text-sm text-stone-500">Manage providers and contracts for external laundry services.</p>
      </div>

      <div className="flex gap-1 border-b border-stone-200">
        {["providers", "contracts"].map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-5 py-2.5 text-sm font-semibold capitalize border-b-2 transition ${tab === t ? "border-emerald-600 text-emerald-700" : "border-transparent text-stone-500"}`}
            data-testid={`laundry-settings-tab-${t}`}>
            {t === "providers" ? "Laundry Providers" : "Laundry Contracts"}
          </button>
        ))}
      </div>

      {tab === "providers" && <ProvidersTab pid={pid} />}
      {tab === "contracts" && <ContractsTab pid={pid} />}
    </div>
  );
};

/* ═══════════ PROVIDERS ═══════════ */
const ProvidersTab = ({ pid }) => {
  const [rows, setRows] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const empty = { name: "", contact_name: "", contact_email: "", contact_phone: "", address: "", notes: "" };
  const [form, setForm] = useState(empty);

  const load = useCallback(async () => {
    try { const { data } = await axios.get(`${API}/laundry/providers/${pid}`); setRows(data.providers || []); }
    catch { /* */ }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  const open = (row = null) => {
    setEditing(row);
    setForm(row ? { ...empty, ...row } : empty);
    setShowForm(true);
  };

  const save = async () => {
    if (!form.name) return toast.error("Name required");
    try {
      if (editing) {
        await axios.put(`${API}/laundry/providers/${editing.id}`, form);
        toast.success("Provider updated");
      } else {
        await axios.post(`${API}/laundry/providers/${pid}`, form);
        toast.success("Provider added");
      }
      setShowForm(false); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const del = async (id) => {
    if (!window.confirm("Delete this provider? (fails if active contracts exist)")) return;
    try { await axios.delete(`${API}/laundry/providers/${id}`); toast.success("Deleted"); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const toggle = async (row) => {
    const next = row.status === "active" ? "inactive" : "active";
    await axios.put(`${API}/laundry/providers/${row.id}`, { status: next });
    load();
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm text-stone-500">Manage external laundry service providers</p>
        <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700 text-white" onClick={() => open()} data-testid="laundry-provider-new">
          <Plus className="w-4 h-4 mr-1" /> Add Provider
        </Button>
      </div>

      <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
        {rows.length === 0 ? (
          <p className="p-12 text-center text-sm text-stone-400">No providers yet — click <b>Add Provider</b> to start.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-stone-50 border-b border-stone-200">
              <tr>
                <th className="text-left py-3 px-4 font-semibold text-stone-600">Provider Name</th>
                <th className="text-left py-3 px-4 font-semibold text-stone-600">Contact</th>
                <th className="text-center py-3 px-4 font-semibold text-stone-600">Active Contracts</th>
                <th className="text-center py-3 px-4 font-semibold text-stone-600">Status</th>
                <th className="text-right py-3 px-4 font-semibold text-stone-600">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(r => (
                <tr key={r.id} className="border-b border-stone-100 hover:bg-stone-50/50" data-testid={`laundry-provider-row-${r.id.slice(0,6)}`}>
                  <td className="py-3 px-4 font-semibold text-stone-800">{r.name}</td>
                  <td className="py-3 px-4 text-stone-600">
                    <div>{r.contact_name || "—"}</div>
                    <div className="text-xs text-stone-400">{r.contact_email} {r.contact_phone && `· ${r.contact_phone}`}</div>
                  </td>
                  <td className="py-3 px-4 text-center font-bold text-emerald-600">{r.active_contracts || 0}</td>
                  <td className="py-3 px-4 text-center">
                    <button onClick={() => toggle(r)} className="cursor-pointer" data-testid={`laundry-provider-toggle-${r.id.slice(0,6)}`}>
                      <Badge className={r.status === "active" ? "bg-emerald-100 text-emerald-700" : "bg-stone-100 text-stone-600"}>{r.status}</Badge>
                    </button>
                  </td>
                  <td className="py-3 px-4 text-right">
                    <button onClick={() => open(r)} className="text-stone-500 hover:text-blue-600 mr-2"><Pencil className="w-4 h-4 inline" /></button>
                    <button onClick={() => del(r.id)} className="text-rose-500 hover:text-rose-700"><Trash2 className="w-4 h-4 inline" /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showForm && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-6" onClick={() => setShowForm(false)}>
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full" onClick={e => e.stopPropagation()}>
            <div className="p-4 border-b border-stone-100 flex items-center justify-between">
              <h3 className="font-bold">{editing ? "Edit Provider" : "New Provider"}</h3>
              <button onClick={() => setShowForm(false)} className="text-stone-400 text-2xl leading-none">×</button>
            </div>
            <div className="p-4 space-y-3">
              <input autoFocus value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="Provider Name *" className="w-full px-3 py-2 border rounded-lg text-sm" data-testid="laundry-provider-name" />
              <input value={form.contact_name} onChange={e => setForm(f => ({ ...f, contact_name: e.target.value }))} placeholder="Contact person" className="w-full px-3 py-2 border rounded-lg text-sm" />
              <div className="grid grid-cols-2 gap-3">
                <input value={form.contact_email} onChange={e => setForm(f => ({ ...f, contact_email: e.target.value }))} placeholder="Email" className="px-3 py-2 border rounded-lg text-sm" />
                <input value={form.contact_phone} onChange={e => setForm(f => ({ ...f, contact_phone: e.target.value }))} placeholder="Phone" className="px-3 py-2 border rounded-lg text-sm" />
              </div>
              <input value={form.address} onChange={e => setForm(f => ({ ...f, address: e.target.value }))} placeholder="Address" className="w-full px-3 py-2 border rounded-lg text-sm" />
              <textarea value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} placeholder="Notes" className="w-full px-3 py-2 border rounded-lg text-sm" rows={2} />
            </div>
            <div className="p-4 border-t border-stone-100 flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => setShowForm(false)}>Cancel</Button>
              <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700 text-white" onClick={save} data-testid="laundry-provider-save">{editing ? "Save" : "Add"}</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

/* ═══════════ CONTRACTS ═══════════ */
const ContractsTab = ({ pid }) => {
  const [rows, setRows] = useState([]);
  const [providers, setProviders] = useState([]);
  const [catalog, setCatalog] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [filterProvider, setFilterProvider] = useState("");
  const today = new Date().toISOString().slice(0, 10);
  const empty = {
    provider_id: "", pricing_model: "per_piece",
    flat_amount: 0, quota: 0, overage_rate: 0,
    billing_period: "monthly", currency: "GBP",
    start_date: today, end_date: "",
    dispatch_days: [], return_days: [],
    rates: [], terms: "", active: true,
  };
  const [form, setForm] = useState(empty);

  const load = useCallback(async () => {
    try {
      const [c, p, cat] = await Promise.all([
        axios.get(`${API}/laundry/contracts/${pid}`),
        axios.get(`${API}/laundry/providers/${pid}`),
        axios.get(`${API}/laundry/catalog`),
      ]);
      setRows(c.data.contracts || []); setProviders(p.data.providers || []);
      setCatalog(cat.data.items || []);
    } catch { /* */ }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  const open = () => {
    setForm({ ...empty, provider_id: providers[0]?.id || "",
              rates: (catalog || []).map(it => ({ item_id: it.id, name: it.name, rate: 0 })) });
    setShowForm(true);
  };

  const toggleDay = (field, day) => {
    setForm(f => {
      const list = f[field] || [];
      const next = list.includes(day) ? list.filter(d => d !== day) : [...list, day];
      return { ...f, [field]: next };
    });
  };

  const updateRate = (i, v) => setForm(f => {
    const arr = [...f.rates]; arr[i] = { ...arr[i], rate: parseFloat(v) || 0 }; return { ...f, rates: arr };
  });

  const save = async () => {
    if (!form.provider_id) return toast.error("Select a provider");
    try {
      await axios.post(`${API}/laundry/contracts/${pid}`, form);
      toast.success("Contract created");
      setShowForm(false); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const del = async (id) => {
    if (!window.confirm("Delete this contract?")) return;
    await axios.delete(`${API}/laundry/contracts/${pid}/${id}`);
    toast.success("Deleted"); load();
  };

  const visible = rows.filter(r => !filterProvider || r.provider_id === filterProvider);
  const pmLabel = (k) => PRICING_MODELS.find(m => m.k === k)?.l || k;
  const isHybrid = form.pricing_model === "hybrid";
  const isFlat = form.pricing_model === "flat_rate";

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-stone-500">Manage pricing agreements with laundry providers</p>
        <div className="flex items-center gap-2">
          <select value={filterProvider} onChange={e => setFilterProvider(e.target.value)} className="px-3 py-2 border rounded-lg text-sm" data-testid="laundry-contracts-filter">
            <option value="">All Providers</option>
            {providers.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700 text-white" onClick={open} data-testid="laundry-contract-new">
            <Plus className="w-4 h-4 mr-1" /> Add Contract
          </Button>
        </div>
      </div>

      <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
        {visible.length === 0 ? (
          <p className="p-12 text-center text-sm text-stone-400">No contracts yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-stone-50 border-b border-stone-200">
              <tr>
                <th className="text-left py-3 px-4 font-semibold text-stone-600">Provider</th>
                <th className="text-left py-3 px-4 font-semibold text-stone-600">Pricing Model</th>
                <th className="text-right py-3 px-4 font-semibold text-stone-600">Flat Amount</th>
                <th className="text-center py-3 px-4 font-semibold text-stone-600">Quota</th>
                <th className="text-center py-3 px-4 font-semibold text-stone-600">Period</th>
                <th className="text-center py-3 px-4 font-semibold text-stone-600">Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {visible.map(r => (
                <tr key={r.id} className="border-b border-stone-100 hover:bg-stone-50/50" data-testid={`laundry-contract-row-${r.id.slice(0,6)}`}>
                  <td className="py-3 px-4 font-semibold text-stone-800">{r.provider_name || r.vendor || "—"}</td>
                  <td className="py-3 px-4">
                    <Badge className="bg-blue-100 text-blue-700">{pmLabel(r.pricing_model || "per_piece")}</Badge>
                  </td>
                  <td className="py-3 px-4 text-right font-mono">{r.flat_amount ? `${r.currency || "GBP"} ${r.flat_amount.toFixed(2)}` : "—"}</td>
                  <td className="py-3 px-4 text-center">{r.quota ? `${r.quota} pc` : "—"}</td>
                  <td className="py-3 px-4 text-center text-xs text-stone-500">
                    {r.start_date || "—"} — {r.end_date || "Ongoing"}
                  </td>
                  <td className="py-3 px-4 text-center">
                    <Badge className={r.active ? "bg-emerald-100 text-emerald-700" : "bg-stone-100 text-stone-600"}>{r.active ? "Active" : "Inactive"}</Badge>
                  </td>
                  <td className="py-3 px-4 text-right">
                    <button onClick={() => del(r.id)} className="text-rose-500 hover:text-rose-700"><Trash2 className="w-4 h-4 inline" /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showForm && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-6" onClick={() => setShowForm(false)}>
          <div className="bg-white rounded-2xl shadow-2xl max-w-3xl w-full max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="p-4 border-b border-stone-100 flex items-center justify-between">
              <h3 className="font-bold">New Contract</h3>
              <button onClick={() => setShowForm(false)} className="text-stone-400 text-2xl leading-none">×</button>
            </div>
            <div className="p-4 space-y-4">
              {/* Details */}
              <div className="border border-stone-200 rounded-xl p-3 space-y-3">
                <div className="text-xs font-semibold text-stone-600 uppercase">Contract Details</div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-stone-500">Provider *</label>
                    <select value={form.provider_id} onChange={e => setForm(f => ({ ...f, provider_id: e.target.value }))} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" data-testid="laundry-contract-provider">
                      <option value="">Select…</option>
                      {providers.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-stone-500">Pricing Model *</label>
                    <select value={form.pricing_model} onChange={e => setForm(f => ({ ...f, pricing_model: e.target.value }))} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" data-testid="laundry-contract-pricing">
                      {PRICING_MODELS.map(m => <option key={m.k} value={m.k}>{m.l}</option>)}
                    </select>
                    <p className="text-xs text-stone-400 mt-1">{PRICING_MODELS.find(m => m.k === form.pricing_model)?.d}</p>
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="text-xs text-stone-500">Start Date</label>
                    <input type="date" value={form.start_date} onChange={e => setForm(f => ({ ...f, start_date: e.target.value }))} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" />
                  </div>
                  <div>
                    <label className="text-xs text-stone-500">End Date (optional)</label>
                    <input type="date" value={form.end_date} onChange={e => setForm(f => ({ ...f, end_date: e.target.value }))} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" />
                  </div>
                  <div>
                    <label className="text-xs text-stone-500">Currency</label>
                    <select value={form.currency} onChange={e => setForm(f => ({ ...f, currency: e.target.value }))} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm">
                      <option>GBP</option><option>USD</option><option>EUR</option><option>TRY</option>
                    </select>
                  </div>
                </div>

                {/* Pricing-model-specific fields */}
                {(isFlat || isHybrid) && (
                  <div className="grid grid-cols-3 gap-3">
                    <div>
                      <label className="text-xs text-stone-500">{isHybrid ? "Monthly Flat £" : "Flat Amount £"}</label>
                      <input type="number" step="0.01" value={form.flat_amount} onChange={e => setForm(f => ({ ...f, flat_amount: parseFloat(e.target.value) || 0 }))} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" data-testid="laundry-contract-flat" />
                    </div>
                    {isHybrid && <>
                      <div>
                        <label className="text-xs text-stone-500">Quota (pieces included)</label>
                        <input type="number" value={form.quota} onChange={e => setForm(f => ({ ...f, quota: parseInt(e.target.value) || 0 }))} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" data-testid="laundry-contract-quota" />
                      </div>
                      <div>
                        <label className="text-xs text-stone-500">Overage £/piece</label>
                        <input type="number" step="0.01" value={form.overage_rate} onChange={e => setForm(f => ({ ...f, overage_rate: parseFloat(e.target.value) || 0 }))} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" data-testid="laundry-contract-overage" />
                      </div>
                    </>}
                    <div>
                      <label className="text-xs text-stone-500">Billing Period</label>
                      <select value={form.billing_period} onChange={e => setForm(f => ({ ...f, billing_period: e.target.value }))} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm">
                        <option value="weekly">Weekly</option><option value="monthly">Monthly</option><option value="yearly">Yearly</option>
                      </select>
                    </div>
                  </div>
                )}
              </div>

              {/* Schedule */}
              <div className="border border-stone-200 rounded-xl p-3 space-y-3">
                <div className="text-xs font-semibold text-stone-600 uppercase">Pickup & Return Schedule</div>
                {["dispatch_days", "return_days"].map(field => (
                  <div key={field}>
                    <label className="text-xs text-stone-500 capitalize">{field.replace("_", " ")}</label>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {DAYS.map(d => (
                        <button key={d} onClick={() => toggleDay(field, d)}
                          className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition ${(form[field] || []).includes(d) ? "bg-emerald-600 text-white border-emerald-600" : "bg-white text-stone-600 border-stone-200 hover:bg-stone-50"}`}
                          data-testid={`laundry-contract-${field}-${d.toLowerCase()}`}>
                          {d.slice(0, 3)}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>

              {/* Per-piece rates */}
              {form.pricing_model === "per_piece" && (
                <div className="border border-stone-200 rounded-xl p-3">
                  <div className="text-xs font-semibold text-stone-600 uppercase mb-2">Per-Item Rates</div>
                  <div className="grid grid-cols-2 gap-2">
                    {form.rates.map((r, i) => (
                      <div key={i} className="flex items-center gap-2 text-sm">
                        <span className="flex-1 text-stone-700">{r.name}</span>
                        <span className="text-stone-400">£</span>
                        <input type="number" step="0.01" value={r.rate} onChange={e => updateRate(i, e.target.value)} className="w-20 px-2 py-1 border rounded text-xs text-right" />
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={form.active} onChange={e => setForm(f => ({ ...f, active: e.target.checked }))} />
                <span>Contract is Active</span>
              </label>
            </div>
            <div className="p-4 border-t border-stone-100 flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => setShowForm(false)}>Cancel</Button>
              <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700 text-white" onClick={save} data-testid="laundry-contract-save">Create Contract</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default LaundrySettingsPanel;
