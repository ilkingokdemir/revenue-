import { useState, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Users, RefreshCw, Plus, X, Mail, Phone, Building2, Link2,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v, c = "GBP") => {
  const sym = { GBP: "£", USD: "$", EUR: "€" }[c] || c + " ";
  return `${sym}${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

const EMPTY_GROUP = {
  property_id: "default", name: "", organiser_name: "", organiser_email: "", organiser_phone: "",
  organisation: "", billing_mode: "master_pays_room_only", booking_ids: [], notes: "",
};

const BILLING_LABEL = {
  master_pays_all: "Master pays ALL (room + extras)",
  master_pays_room_only: "Master pays ROOMS · guests pay extras",
  each_room_self_pays: "Each room self-pays",
};

export const GroupBookingsPanel = ({ user, propertyId }) => {
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(false);
  const [groupForm, setGroupForm] = useState(null);
  const [masterFor, setMasterFor] = useState(null);
  const [bookingsPool, setBookingsPool] = useState([]);
  const [attachFor, setAttachFor] = useState(null);

  const loadAll = async () => {
    setLoading(true);
    try {
      const pid = propertyId && propertyId !== "all" ? propertyId : "";
      const qs = pid ? `?property_id=${pid}` : "";
      const [g, b] = await Promise.all([
        axios.get(`${API}/groups/${qs}`),
        axios.get(`${API}/bookings${qs}`).catch(() => ({ data: [] })),
      ]);
      setGroups(g.data || []);
      setBookingsPool((b.data || []).filter(x => !x.group_id));
    } catch (e) { toast.error("Failed to load groups"); }
    finally { setLoading(false); }
  };
  useEffect(() => { loadAll(); /* eslint-disable-next-line */ }, [propertyId]);

  const saveGroup = async () => {
    if (!groupForm.name) return toast.error("Group name required");
    try {
      if (groupForm.id) await axios.put(`${API}/groups/${groupForm.id}`, groupForm);
      else await axios.post(`${API}/groups/`, groupForm);
      toast.success("Saved"); setGroupForm(null); loadAll();
    } catch (e) { toast.error(e?.response?.data?.detail || "Save failed"); }
  };
  const deleteGroup = async (id) => {
    if (!window.confirm("Delete this group? Bookings stay but are unlinked.")) return;
    try { await axios.delete(`${API}/groups/${id}`); toast.success("Deleted"); loadAll(); }
    catch (e) { toast.error("Failed"); }
  };
  const attach = async (group_id, ids) => {
    try {
      await axios.post(`${API}/groups/${group_id}/attach`, { booking_ids: ids });
      toast.success(`Linked ${ids.length} booking${ids.length === 1 ? "" : "s"}`);
      setAttachFor(null); loadAll();
    } catch (e) { toast.error("Failed"); }
  };
  const detach = async (group_id, bid) => {
    if (!window.confirm("Remove this booking from the group?")) return;
    try {
      await axios.post(`${API}/groups/${group_id}/detach`, { booking_ids: [bid] });
      loadAll();
      if (masterFor?.group?.id === group_id) openMaster(group_id);
    } catch (e) { toast.error("Failed"); }
  };
  const openMaster = async (id) => {
    try {
      const { data } = await axios.get(`${API}/groups/${id}/master-folio`);
      setMasterFor(data);
    } catch (e) { toast.error("Failed"); }
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto" data-testid="groups-panel">
      <div className="bg-gradient-to-br from-violet-50 via-purple-50 to-white border border-violet-100 rounded-2xl p-6">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-wider text-violet-700">
              <Users className="w-4 h-4" />Group Bookings · Master Folio
            </div>
            <h1 className="text-3xl font-black text-stone-900 mt-1">Groups</h1>
            <p className="text-sm text-stone-600 mt-1">
              Link multiple rooms to a single organiser for weddings, conferences &amp; tour groups.
            </p>
          </div>
          <div className="flex gap-2">
            <button onClick={loadAll} className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-stone-200 hover:border-stone-300 rounded-lg text-xs font-semibold">
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />Refresh
            </button>
            <button onClick={() => setGroupForm({ ...EMPTY_GROUP, property_id: propertyId || "default" })}
              data-testid="groups-new"
              className="flex items-center gap-1.5 px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white rounded-lg text-sm font-semibold">
              <Plus className="w-4 h-4" />New Group
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {groups.length === 0 && (
          <div className="col-span-2 p-12 bg-white border border-stone-200 rounded-xl text-center text-stone-400">
            No groups yet. Create one to link multiple bookings under one organiser.
          </div>
        )}
        {groups.map(g => (
          <div key={g.id} data-testid={`group-card-${g.id}`}
               className="bg-white border border-stone-200 rounded-xl p-5 hover:shadow-md transition-shadow">
            <div className="flex items-start justify-between mb-3">
              <div>
                <h3 className="text-lg font-bold text-stone-900">{g.name}</h3>
                <p className="text-xs text-stone-500 mt-0.5">{BILLING_LABEL[g.billing_mode] || g.billing_mode}</p>
              </div>
              <div className="flex gap-1">
                <button onClick={() => setGroupForm({ ...g })} className="p-1.5 hover:bg-stone-100 rounded text-xs text-stone-600">Edit</button>
                <button onClick={() => deleteGroup(g.id)} className="p-1.5 hover:bg-rose-50 rounded text-xs text-rose-600">Delete</button>
              </div>
            </div>
            <div className="text-xs text-stone-500 space-y-0.5 mb-3">
              {g.organiser_name && <div className="flex items-center gap-1"><Users className="w-3 h-3" />{g.organiser_name}</div>}
              {g.organiser_email && <div className="flex items-center gap-1"><Mail className="w-3 h-3" />{g.organiser_email}</div>}
              {g.organiser_phone && <div className="flex items-center gap-1"><Phone className="w-3 h-3" />{g.organiser_phone}</div>}
              {g.organisation && <div className="flex items-center gap-1"><Building2 className="w-3 h-3" />{g.organisation}</div>}
            </div>
            <div className="grid grid-cols-3 gap-2 p-3 bg-stone-50 rounded-lg mb-3">
              <Stat label="Rooms" value={g.totals?.rooms || 0} />
              <Stat label="Gross" value={cur(g.totals?.gross, g.totals?.currency)} />
              <Stat label="Balance" value={cur(g.totals?.balance, g.totals?.currency)} tone={g.totals?.balance > 0 ? "amber" : "emerald"} />
            </div>
            {g.bookings?.length > 0 ? (
              <ul className="space-y-1 mb-3">
                {g.bookings.map(b => (
                  <li key={b.id} className="flex items-center justify-between text-xs p-2 bg-stone-50 rounded">
                    <div className="flex-1 min-w-0">
                      <div className="font-semibold text-stone-800 truncate">{b.guest_name || "—"}</div>
                      <div className="text-[11px] text-stone-500">{b.room_type_name} · {b.check_in} → {b.check_out}</div>
                    </div>
                    <div className="text-right">
                      <div className="font-bold text-stone-800">{cur(b.total_price, b.currency)}</div>
                      <button onClick={() => detach(g.id, b.id)} className="text-[10px] text-rose-500 hover:underline">unlink</button>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-stone-400 text-center py-3">No bookings linked yet.</p>
            )}
            <div className="flex gap-2">
              <button onClick={() => setAttachFor(g)} data-testid={`group-attach-${g.id}`}
                className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 bg-white border border-stone-200 hover:border-violet-300 rounded-lg text-xs font-semibold">
                <Link2 className="w-3.5 h-3.5" />Link bookings
              </button>
              <button onClick={() => openMaster(g.id)} data-testid={`group-master-${g.id}`}
                className="flex-1 px-3 py-2 bg-violet-600 hover:bg-violet-700 text-white rounded-lg text-xs font-semibold">
                Master Folio
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Edit Group Modal */}
      {groupForm && (
        <Modal title={groupForm.id ? "Edit Group" : "New Group"} onClose={() => setGroupForm(null)}>
          <div className="grid grid-cols-2 gap-3">
            <F label="Group Name *"><input value={groupForm.name} onChange={e => setGroupForm({ ...groupForm, name: e.target.value })} data-testid="groups-form-name" className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" placeholder="ACME Conference 2026" /></F>
            <F label="Billing Mode">
              <select value={groupForm.billing_mode} onChange={e => setGroupForm({ ...groupForm, billing_mode: e.target.value })} data-testid="groups-form-billing" className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm">
                {Object.entries(BILLING_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </F>
            <F label="Organiser Name"><input value={groupForm.organiser_name} onChange={e => setGroupForm({ ...groupForm, organiser_name: e.target.value })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" /></F>
            <F label="Organisation"><input value={groupForm.organisation} onChange={e => setGroupForm({ ...groupForm, organisation: e.target.value })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" /></F>
            <F label="Organiser Email"><input type="email" value={groupForm.organiser_email} onChange={e => setGroupForm({ ...groupForm, organiser_email: e.target.value })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" /></F>
            <F label="Organiser Phone"><input value={groupForm.organiser_phone} onChange={e => setGroupForm({ ...groupForm, organiser_phone: e.target.value })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" /></F>
            <div className="col-span-2">
              <F label="Notes"><textarea rows={2} value={groupForm.notes} onChange={e => setGroupForm({ ...groupForm, notes: e.target.value })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" /></F>
            </div>
          </div>
          <SaveBar onCancel={() => setGroupForm(null)} onSave={saveGroup} testId="groups-form-save" />
        </Modal>
      )}

      {/* Attach modal */}
      {attachFor && (
        <Modal title={`Link bookings to "${attachFor.name}"`} onClose={() => setAttachFor(null)}>
          <p className="text-xs text-stone-500 mb-3">Pick any unassigned bookings. They'll inherit group billing rules.</p>
          <AttachPicker pool={bookingsPool} onSubmit={(ids) => attach(attachFor.id, ids)} onCancel={() => setAttachFor(null)} />
        </Modal>
      )}

      {/* Master folio modal */}
      {masterFor && (
        <Modal title={`Master Folio · ${masterFor.group?.name}`} onClose={() => setMasterFor(null)}>
          <MasterFolioView data={masterFor} />
        </Modal>
      )}
    </div>
  );
};

const Stat = ({ label, value, tone = "stone" }) => {
  const tones = { stone: "text-stone-800", amber: "text-amber-600", emerald: "text-emerald-600" };
  return (
    <div>
      <div className="text-[9px] uppercase text-stone-400 font-bold">{label}</div>
      <div className={`text-sm font-black ${tones[tone]}`}>{value}</div>
    </div>
  );
};

const AttachPicker = ({ pool, onSubmit, onCancel }) => {
  const [picked, setPicked] = useState(new Set());
  const toggle = (id) => {
    const next = new Set(picked);
    if (next.has(id)) next.delete(id); else next.add(id);
    setPicked(next);
  };
  return (
    <>
      <div className="max-h-80 overflow-y-auto space-y-1">
        {pool.length === 0 && <p className="text-xs text-stone-400 text-center py-8">No unassigned bookings.</p>}
        {pool.map(b => (
          <label key={b.id} className="flex items-center gap-2 p-2 text-sm hover:bg-stone-50 rounded cursor-pointer">
            <input type="checkbox" checked={picked.has(b.id)} onChange={() => toggle(b.id)} data-testid={`groups-pick-${b.id}`} />
            <div className="flex-1 min-w-0">
              <div className="font-semibold text-stone-800 truncate">{b.guest_name || "—"}</div>
              <div className="text-[11px] text-stone-500">{b.check_in} → {b.check_out} · {cur(b.total_price, b.currency)}</div>
            </div>
          </label>
        ))}
      </div>
      <div className="flex justify-end gap-2 mt-4">
        <button onClick={onCancel} className="px-4 py-2 text-sm">Cancel</button>
        <button onClick={() => onSubmit([...picked])} disabled={picked.size === 0} data-testid="groups-attach-submit"
          className="px-4 py-2 bg-violet-600 hover:bg-violet-700 disabled:bg-stone-300 text-white rounded-lg text-sm font-semibold">
          Link {picked.size} booking{picked.size === 1 ? "" : "s"}
        </button>
      </div>
    </>
  );
};

const MasterFolioView = ({ data }) => {
  const { billing_mode, master_charges, room_owner_charges, totals, bookings } = data;
  return (
    <div className="space-y-4 text-sm">
      <div className="grid grid-cols-3 gap-3 p-3 bg-stone-50 rounded-lg">
        <Stat label="Rooms" value={totals?.rooms || 0} />
        <Stat label="Gross" value={cur(totals?.gross, totals?.currency)} />
        <Stat label="Balance" value={cur(totals?.balance, totals?.currency)} tone={totals?.balance > 0 ? "amber" : "emerald"} />
      </div>
      <p className="text-xs p-2 bg-violet-50 border border-violet-200 rounded text-violet-700">
        <b>Billing mode:</b> {BILLING_LABEL[billing_mode]}
      </p>
      <Section title={`Master Charges (organiser pays) — ${master_charges?.length || 0}`}
               rows={master_charges} />
      <Section title={`Room-Owner Charges (individual guest pays) — ${room_owner_charges?.length || 0}`}
               rows={room_owner_charges} />
      <details className="text-xs">
        <summary className="cursor-pointer text-stone-500 font-semibold">Linked bookings ({bookings?.length || 0})</summary>
        <ul className="mt-2 space-y-1">
          {(bookings || []).map(b => (
            <li key={b.id} className="p-2 bg-stone-50 rounded flex items-center justify-between">
              <span>{b.guest_name} · {b.room_type_name}</span>
              <span className="font-bold">{cur(b.total_price, b.currency)}</span>
            </li>
          ))}
        </ul>
      </details>
    </div>
  );
};

const Section = ({ title, rows }) => (
  <div className="border border-stone-200 rounded-lg overflow-hidden">
    <div className="bg-stone-50 px-3 py-2 text-xs font-bold text-stone-700">{title}</div>
    {(!rows || rows.length === 0) ? (
      <p className="text-xs text-stone-400 text-center py-4">No charges.</p>
    ) : (
      <table className="w-full text-xs">
        <thead className="bg-white text-[10px] text-stone-400 uppercase">
          <tr><th className="p-2 text-left">Guest</th><th className="p-2 text-left">Type</th><th className="p-2 text-left">Desc</th><th className="p-2 text-right">Amount</th></tr>
        </thead>
        <tbody>
          {rows.map((c, i) => (
            <tr key={i} className="border-t border-stone-100">
              <td className="p-2">{c.guest_name}</td>
              <td className="p-2">{c.type}</td>
              <td className="p-2">{c.description || "—"}</td>
              <td className="p-2 text-right font-bold">{cur(c.amount, c.currency)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    )}
  </div>
);

const F = ({ label, children }) => (
  <div>
    <label className="block text-[10px] font-bold uppercase text-stone-500 mb-1">{label}</label>
    {children}
  </div>
);
const SaveBar = ({ onCancel, onSave, testId }) => (
  <div className="flex justify-end gap-2 mt-4">
    <button onClick={onCancel} className="px-4 py-2 text-sm">Cancel</button>
    <button onClick={onSave} data-testid={testId} className="px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white rounded-lg text-sm font-semibold">Save</button>
  </div>
);
const Modal = ({ title, onClose, children }) => (
  <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" onClick={onClose}>
    <div className="bg-white rounded-2xl p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-bold text-stone-900">{title}</h2>
        <button onClick={onClose} className="p-1 hover:bg-stone-100 rounded-lg"><X className="w-4 h-4 text-stone-500" /></button>
      </div>
      {children}
    </div>
  </div>
);

export default GroupBookingsPanel;
