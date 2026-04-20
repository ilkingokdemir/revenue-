/**
 * Group Blocks Panel (Iter 165) — parity with Mews/Eviivo/Cloudbeds/SiteMinder.
 *
 * Single-file panel handling: list · create · edit · cancel · materialize.
 * Backend: /api/group-blocks/*
 */
import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Plus, Trash2, Users, Calendar as CalIcon, CheckCircle2, AlertTriangle, Search, Sparkles } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STATUS_BADGE = {
  tentative: "bg-amber-100 text-amber-700",
  definite:  "bg-emerald-100 text-emerald-700",
  cancelled: "bg-rose-100 text-rose-700",
};

const GroupBlocksPanel = ({ activePropertyId }) => {
  const pid = activePropertyId || "aldgate-flats";
  const [data, setData] = useState({ rows: [], stats: {} });
  const [rooms, setRooms] = useState([]);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);

  const today = new Date().toISOString().slice(0, 10);
  const plus7 = new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 10);

  const empty = {
    name: "", code: "", from_date: today, to_date: plus7, cutoff_date: "",
    status: "tentative", contact_name: "", contact_email: "", contact_phone: "",
    company: "", notes: "", allocations: [],
  };
  const [form, setForm] = useState(empty);

  const load = useCallback(async () => {
    try {
      const qs = new URLSearchParams();
      if (search) qs.set("search", search);
      if (statusFilter) qs.set("status", statusFilter);
      const [blocks, alloc] = await Promise.all([
        axios.get(`${API}/group-blocks/${pid}?${qs}`),
        axios.get(`${API}/inventory-allocations/${pid}`),
      ]);
      setData(blocks.data);
      setRooms(alloc.data.room_types || []);
    } catch { /* */ }
  }, [pid, search, statusFilter]);
  useEffect(() => { const t = setTimeout(load, 200); return () => clearTimeout(t); }, [load]);

  const open = (row = null) => {
    if (row) {
      setEditing(row);
      setForm({ ...row, allocations: row.allocations || [] });
    } else {
      setEditing(null);
      setForm({ ...empty, allocations: rooms[0] ? [{ room_type_id: rooms[0].id, quantity: 5, rate: 0 }] : [] });
    }
    setShowForm(true);
  };

  const save = async () => {
    if (!form.name) return toast.error("Name required");
    if (form.allocations.length === 0) return toast.error("Add at least 1 allocation");
    try {
      if (editing) {
        await axios.put(`${API}/group-blocks/${editing.id}`, form);
        toast.success("Block updated");
      } else {
        const { data } = await axios.post(`${API}/group-blocks/${pid}`, form);
        toast.success(`Block created · ${data.code}`);
      }
      setShowForm(false); setEditing(null);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const cancel = async (id) => {
    if (!window.confirm("Cancel this group block?")) return;
    await axios.delete(`${API}/group-blocks/${id}`);
    toast.success("Block cancelled"); load();
  };

  const materialize = async (id) => {
    if (!window.confirm("Materialize block into individual bookings?")) return;
    try {
      const { data } = await axios.post(`${API}/group-blocks/${id}/materialize`);
      toast.success(`Created ${data.bookings_created} bookings from block`);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const addAlloc = () => setForm(f => ({ ...f, allocations: [...f.allocations, { room_type_id: rooms[0]?.id || "", quantity: 1, rate: 0 }] }));
  const updAlloc = (i, k, v) => setForm(f => { const a = [...f.allocations]; a[i] = { ...a[i], [k]: v }; return { ...f, allocations: a }; });
  const rmAlloc = (i) => setForm(f => { const a = [...f.allocations]; a.splice(i, 1); return { ...f, allocations: a }; });

  return (
    <div className="p-6 space-y-5" data-testid="group-blocks-panel">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs text-stone-400">Bookings</div>
          <h2 className="text-2xl font-bold">Group Blocks</h2>
          <p className="text-sm text-stone-500">Manage group reservations and room blocks (weddings, corporate, sports teams, tours).</p>
        </div>
        <button onClick={() => open()} className="px-4 py-2 bg-emerald-600 text-white rounded-xl text-sm font-semibold flex items-center gap-2" data-testid="group-blocks-new">
          <Plus className="w-4 h-4" /> New Group Block
        </button>
      </div>

      {/* Stat chips */}
      <div className="flex gap-3 flex-wrap">
        {[
          { k: "tentative", l: "Tentative", i: AlertTriangle, cls: "bg-amber-50 border-amber-200 text-amber-900" },
          { k: "definite",  l: "Definite",  i: CheckCircle2,  cls: "bg-emerald-50 border-emerald-200 text-emerald-900" },
          { k: "cancelled", l: "Cancelled", i: Trash2,        cls: "bg-stone-50 border-stone-200 text-stone-700" },
        ].map(s => (
          <div key={s.k} className={`flex items-center gap-3 px-4 py-3 border rounded-xl ${s.cls}`}>
            <s.i className="w-4 h-4" />
            <div>
              <div className="text-xs uppercase tracking-wider font-semibold">{s.l}</div>
              <div className="text-xl font-bold">{data.stats?.[s.k] || 0}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-2 flex-1 max-w-md bg-white border border-stone-200 rounded-xl px-3 py-2">
          <Search className="w-4 h-4 text-stone-400" />
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search by name / code / contact…" className="flex-1 outline-none text-sm bg-transparent" data-testid="group-blocks-search" />
        </div>
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} className="px-3 py-2 border rounded-xl text-sm bg-white" data-testid="group-blocks-status-filter">
          <option value="">All Statuses</option>
          <option value="tentative">Tentative</option>
          <option value="definite">Definite</option>
          <option value="cancelled">Cancelled</option>
        </select>
      </div>

      {/* Table */}
      <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
        <div className="grid grid-cols-[1fr,auto,1fr,auto,auto,auto,auto] gap-3 px-4 py-3 bg-stone-50 text-xs font-semibold text-stone-500 uppercase tracking-wider">
          <div>Group Name</div><div>Code</div><div>Dates</div><div>Rooms</div><div>Status</div><div>Ver</div><div>Actions</div>
        </div>
        {data.rows?.map(r => (
          <div key={r.id} className="grid grid-cols-[1fr,auto,1fr,auto,auto,auto,auto] gap-3 px-4 py-3 border-t border-stone-100 items-center text-sm" data-testid={`group-block-row-${r.id.slice(0,6)}`}>
            <div>
              <div className="font-semibold">{r.name}</div>
              <div className="text-xs text-stone-400">{r.contact_name || r.company || "—"} {r.contact_email && `· ${r.contact_email}`}</div>
            </div>
            <Badge className="bg-blue-50 text-blue-700 font-mono">{r.code}</Badge>
            <div className="text-xs">
              {r.from_date} → {r.to_date}
              <div className="text-stone-400">{r.nights} nights{r.cutoff_date && ` · cutoff ${r.cutoff_date}`}</div>
            </div>
            <div className="font-bold">{r.rooms_blocked || 0}</div>
            <Badge className={STATUS_BADGE[r.status] || "bg-stone-100 text-stone-600"}>{r.status}</Badge>
            <div className="text-xs text-stone-400">v{r.version}</div>
            <div className="flex gap-1">
              {r.status !== "cancelled" && !r.materialized && (
                <button onClick={() => materialize(r.id)} className="text-xs px-2 py-1 rounded bg-violet-50 text-violet-700 hover:bg-violet-100" data-testid={`group-block-materialize-${r.id.slice(0,6)}`} title="Materialize into bookings">
                  <Sparkles className="w-3 h-3 inline" /> Materialize
                </button>
              )}
              <button onClick={() => open(r)} className="text-xs px-2 py-1 rounded border border-stone-200 hover:bg-stone-50" data-testid={`group-block-edit-${r.id.slice(0,6)}`}>Edit</button>
              {r.status !== "cancelled" && (
                <button onClick={() => cancel(r.id)} className="text-rose-500" data-testid={`group-block-cancel-${r.id.slice(0,6)}`} title="Cancel block">
                  <Trash2 className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>
        ))}
        {(!data.rows || data.rows.length === 0) && (
          <div className="p-16 text-center">
            <Users className="w-10 h-10 text-stone-300 mx-auto mb-3" />
            <div className="text-stone-400 text-sm">No group blocks yet — click <b>New Group Block</b> to create one.</div>
          </div>
        )}
      </div>

      {/* Modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-6" onClick={() => setShowForm(false)}>
          <div className="bg-white rounded-2xl shadow-2xl max-w-3xl w-full max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="p-6 border-b border-stone-100 flex items-center justify-between">
              <h3 className="text-lg font-bold">{editing ? "Edit Group Block" : "New Group Block"}</h3>
              <button onClick={() => setShowForm(false)} className="text-stone-400 hover:text-stone-600 text-2xl leading-none">×</button>
            </div>
            <div className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-stone-500 uppercase">Name *</label>
                  <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="e.g. Acme Wedding 2026" className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" data-testid="group-blocks-form-name" />
                </div>
                <div>
                  <label className="text-xs font-semibold text-stone-500 uppercase">Code</label>
                  <input value={form.code} onChange={e => setForm(f => ({ ...f, code: e.target.value.toUpperCase() }))} placeholder="Auto-generated if empty" className="w-full mt-1 px-3 py-2 border rounded-lg text-sm font-mono" data-testid="group-blocks-form-code" />
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-xs font-semibold text-stone-500 uppercase">From</label>
                  <input type="date" value={form.from_date} onChange={e => setForm(f => ({ ...f, from_date: e.target.value }))} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" />
                </div>
                <div>
                  <label className="text-xs font-semibold text-stone-500 uppercase">To</label>
                  <input type="date" value={form.to_date} onChange={e => setForm(f => ({ ...f, to_date: e.target.value }))} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" />
                </div>
                <div>
                  <label className="text-xs font-semibold text-stone-500 uppercase">Cutoff</label>
                  <input type="date" value={form.cutoff_date} onChange={e => setForm(f => ({ ...f, cutoff_date: e.target.value }))} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-stone-500 uppercase">Status</label>
                  <select value={form.status} onChange={e => setForm(f => ({ ...f, status: e.target.value }))} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm">
                    <option value="tentative">Tentative</option>
                    <option value="definite">Definite</option>
                    <option value="cancelled">Cancelled</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-semibold text-stone-500 uppercase">Company</label>
                  <input value={form.company} onChange={e => setForm(f => ({ ...f, company: e.target.value }))} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" />
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3">
                <input value={form.contact_name} onChange={e => setForm(f => ({ ...f, contact_name: e.target.value }))} placeholder="Contact name" className="px-3 py-2 border rounded-lg text-sm" />
                <input value={form.contact_email} onChange={e => setForm(f => ({ ...f, contact_email: e.target.value }))} placeholder="Email" className="px-3 py-2 border rounded-lg text-sm" />
                <input value={form.contact_phone} onChange={e => setForm(f => ({ ...f, contact_phone: e.target.value }))} placeholder="Phone" className="px-3 py-2 border rounded-lg text-sm" />
              </div>

              {/* Allocations */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-xs font-semibold text-stone-500 uppercase">Room Allocations *</label>
                  <button onClick={addAlloc} className="text-xs px-2 py-1 rounded border border-emerald-300 text-emerald-700" data-testid="group-blocks-add-alloc">+ Add</button>
                </div>
                <div className="space-y-2">
                  {form.allocations.map((a, i) => (
                    <div key={i} className="grid grid-cols-[1fr,auto,auto,auto] gap-2 items-center">
                      <select value={a.room_type_id} onChange={e => updAlloc(i, "room_type_id", e.target.value)} className="px-2 py-1.5 border rounded text-sm">
                        {rooms.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
                      </select>
                      <input type="number" min="1" value={a.quantity} onChange={e => updAlloc(i, "quantity", parseInt(e.target.value) || 1)} placeholder="Qty" className="w-20 px-2 py-1.5 border rounded text-sm" />
                      <input type="number" step="0.01" value={a.rate} onChange={e => updAlloc(i, "rate", parseFloat(e.target.value) || 0)} placeholder="Rate £" className="w-28 px-2 py-1.5 border rounded text-sm" />
                      <button onClick={() => rmAlloc(i)} className="text-rose-500"><Trash2 className="w-4 h-4" /></button>
                    </div>
                  ))}
                  {form.allocations.length === 0 && <p className="text-xs text-stone-400 text-center py-4">No allocations — click <b>+ Add</b> to include a room type.</p>}
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold text-stone-500 uppercase">Notes</label>
                <textarea value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" rows={3} />
              </div>
            </div>
            <div className="p-6 border-t border-stone-100 flex justify-end gap-2">
              <button onClick={() => setShowForm(false)} className="px-4 py-2 bg-white border rounded-lg text-sm">Cancel</button>
              <button onClick={save} className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-semibold" data-testid="group-blocks-form-save">{editing ? "Save Changes" : "Create Block"}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default GroupBlocksPanel;
