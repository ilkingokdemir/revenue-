import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { motion } from "framer-motion";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const LostFoundPanel = ({ properties, activePropertyId }) => {
  const [data, setData] = useState({ items: [], stats: {} });
  const [showCreate, setShowCreate] = useState(false);
  const [filter, setFilter] = useState("");
  const [form, setForm] = useState({ item_name: "", description: "", category: "personal", found_location: "", storage_location: "", guest_name: "", guest_room: "", guest_contact: "", found_date: "" });
  const pid = activePropertyId || "all";

  const load = useCallback(async () => {
    try { const { data: d } = await axios.get(`${API}/lost-found/${pid}${filter ? `?status=${filter}` : ""}`); setData(d); } catch { toast.error("Failed"); }
  }, [pid, filter]);
  useEffect(() => { load(); }, [load]);

  const create = async () => {
    try { await axios.post(`${API}/lost-found`, { ...form, property_id: pid }); toast.success("Item recorded"); setShowCreate(false); setForm({ item_name: "", description: "", category: "personal", found_location: "", storage_location: "", guest_name: "", guest_room: "", guest_contact: "", found_date: "" }); load(); } catch { toast.error("Failed"); }
  };

  const updateStatus = async (id, status, claimedBy) => {
    try { await axios.put(`${API}/lost-found/${id}`, { status, claimed_by: claimedBy || "" }); toast.success("Updated"); load(); } catch { toast.error("Failed"); }
  };

  const del = async (id) => { try { await axios.delete(`${API}/lost-found/${id}`); toast.success("Deleted"); load(); } catch { toast.error("Failed"); } };

  const s = data.stats || {};
  const catColors = { personal: "bg-blue-100 text-blue-700", electronics: "bg-violet-100 text-violet-700", clothing: "bg-amber-100 text-amber-700", documents: "bg-red-100 text-red-700", jewelry: "bg-emerald-100 text-emerald-700", luggage: "bg-stone-100 text-stone-700", other: "bg-stone-100 text-stone-500" };
  const statusColors = { unclaimed: "bg-amber-100 text-amber-700", claimed: "bg-emerald-100 text-emerald-700", disposed: "bg-stone-100 text-stone-500" };

  return (
    <div className="p-5" data-testid="lost-found-panel">
      <div className="flex items-center justify-between mb-6">
        <div><h2 className="text-lg font-bold text-stone-800">Lost & Found</h2><p className="text-sm text-stone-500">Track lost items, match guests, manage claims</p></div>
        <button onClick={() => setShowCreate(true)} className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium" data-testid="new-lost-item-btn">+ Log Found Item</button>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        {[{ label: "Total Items", v: s.total || 0, c: "text-stone-800" }, { label: "Unclaimed", v: s.unclaimed || 0, c: "text-amber-600" }, { label: "Claimed", v: s.claimed || 0, c: "text-emerald-600" }, { label: "Disposed", v: s.disposed || 0, c: "text-stone-500" }].map(st => (
          <div key={st.label} className="bg-white border border-stone-200 rounded-xl p-4" data-testid={`lf-stat-${st.label.toLowerCase()}`}>
            <div className="text-xs text-stone-400 uppercase font-semibold">{st.label}</div>
            <div className={`text-xl font-bold mt-1 ${st.c}`}>{st.v}</div>
          </div>
        ))}
      </div>
      <div className="flex gap-2 mb-4">
        {["", "unclaimed", "claimed", "disposed"].map(f => (
          <button key={f} onClick={() => setFilter(f)} className={`px-3 py-1.5 text-xs font-medium rounded-lg ${filter === f ? "bg-stone-800 text-white" : "text-stone-500 hover:bg-stone-100"}`} data-testid={`lf-filter-${f || "all"}`}>{f || "All"}</button>
        ))}
      </div>
      {(data.items || []).length === 0 ? <div className="text-center py-16 text-stone-400"><svg className="w-12 h-12 mx-auto mb-3 text-stone-300" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg><p className="font-medium">No items found</p></div> : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">{data.items.map(item => (
          <motion.div key={item.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }}
            className="border border-stone-200 rounded-xl p-4 bg-white hover:shadow-md transition-all" data-testid={`lf-item-${item.id}`}>
            <div className="flex items-start justify-between mb-2">
              <h4 className="font-semibold text-stone-800">{item.item_name}</h4>
              <Badge className={`text-[10px] ${statusColors[item.status] || ""}`}>{item.status}</Badge>
            </div>
            {item.description && <p className="text-xs text-stone-500 mb-2 line-clamp-2">{item.description}</p>}
            <div className="flex items-center gap-2 flex-wrap mb-2">
              <Badge className={`text-[9px] ${catColors[item.category] || catColors.other}`}>{item.category}</Badge>
              {item.found_location && <span className="text-[10px] text-stone-400">Found: {item.found_location}</span>}
            </div>
            <div className="text-[10px] text-stone-400 space-y-0.5">
              <div>Date: {item.found_date}</div>
              {item.guest_name && <div>Guest: {item.guest_name} {item.guest_room && `(Room ${item.guest_room})`}</div>}
              {item.storage_location && <div>Storage: {item.storage_location}</div>}
              <div>Found by: {item.found_by}</div>
            </div>
            <div className="flex gap-1 mt-3">
              {item.status === "unclaimed" && <>
                <button onClick={() => { const name = prompt("Claimed by (name):"); if (name) updateStatus(item.id, "claimed", name); }} className="px-2 py-1 bg-emerald-500 text-white text-[10px] rounded font-medium" data-testid={`lf-claim-${item.id}`}>Claim</button>
                <button onClick={() => updateStatus(item.id, "disposed")} className="px-2 py-1 bg-stone-200 text-stone-600 text-[10px] rounded font-medium" data-testid={`lf-dispose-${item.id}`}>Dispose</button>
              </>}
              <button onClick={() => del(item.id)} className="px-2 py-1 text-[10px] text-red-500 hover:underline ml-auto" data-testid={`lf-delete-${item.id}`}>Delete</button>
            </div>
          </motion.div>
        ))}</div>
      )}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="max-w-lg" data-testid="lf-dialog"><DialogHeader><DialogTitle>Log Found Item</DialogTitle></DialogHeader>
          <div className="space-y-3 mt-2">
            <Input value={form.item_name} onChange={e => setForm({...form, item_name: e.target.value})} placeholder="Item name (e.g. Black Wallet)" data-testid="lf-item-name" />
            <Textarea value={form.description} onChange={e => setForm({...form, description: e.target.value})} placeholder="Description" rows={2} data-testid="lf-desc" />
            <div className="grid grid-cols-2 gap-3">
              <Select value={form.category} onValueChange={v => setForm({...form, category: v})}><SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger><SelectContent>
                <SelectItem value="personal">Personal</SelectItem><SelectItem value="electronics">Electronics</SelectItem><SelectItem value="clothing">Clothing</SelectItem>
                <SelectItem value="documents">Documents</SelectItem><SelectItem value="jewelry">Jewelry</SelectItem><SelectItem value="luggage">Luggage</SelectItem><SelectItem value="other">Other</SelectItem>
              </SelectContent></Select>
              <Input type="date" value={form.found_date} onChange={e => setForm({...form, found_date: e.target.value})} data-testid="lf-date" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Input value={form.found_location} onChange={e => setForm({...form, found_location: e.target.value})} placeholder="Found location (e.g. Room 305)" data-testid="lf-location" />
              <Input value={form.storage_location} onChange={e => setForm({...form, storage_location: e.target.value})} placeholder="Storage (e.g. Reception safe)" data-testid="lf-storage" />
            </div>
            <div className="grid grid-cols-3 gap-3">
              <Input value={form.guest_name} onChange={e => setForm({...form, guest_name: e.target.value})} placeholder="Guest name" data-testid="lf-guest" />
              <Input value={form.guest_room} onChange={e => setForm({...form, guest_room: e.target.value})} placeholder="Room" data-testid="lf-room" />
              <Input value={form.guest_contact} onChange={e => setForm({...form, guest_contact: e.target.value})} placeholder="Contact" data-testid="lf-contact" />
            </div>
            <button onClick={create} className="w-full py-2.5 bg-emerald-600 text-white rounded-lg text-sm font-medium" data-testid="lf-save">Log Item</button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};
