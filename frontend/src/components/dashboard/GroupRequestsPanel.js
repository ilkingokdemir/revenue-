/**
 * Group Requests & Allotments — admin lifecycle for B2B / corporate / wedding
 * group room block REQUESTS submitted via the public booking widget.
 *
 * Different from `GroupBookingsPanel.js` which handles master-folio billing
 * for already-confirmed groups.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Loader2, Users, Building2, Calendar, RefreshCw, Mail, Phone, FileText,
  Check, X, DollarSign, MessageSquare, Briefcase,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STATUS_META = {
  pending:   { color: "text-amber-300 bg-amber-500/15 border-amber-500/30",   label: "Pending review" },
  quoted:    { color: "text-cyan-300 bg-cyan-500/15 border-cyan-500/30",      label: "Quoted" },
  confirmed: { color: "text-emerald-300 bg-emerald-500/15 border-emerald-500/30", label: "Confirmed" },
  cancelled: { color: "text-rose-300 bg-rose-500/15 border-rose-500/30",      label: "Cancelled" },
};

const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { maximumFractionDigits: 0 })}`;

export default function GroupRequestsPanel({ propertyId, hotelName = "" }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [active, setActive] = useState(null);
  const [filter, setFilter] = useState("");
  const [draft, setDraft] = useState({ status: "", admin_notes: "", quoted_price: "" });
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/group-booking/requests/${propertyId}`);
      setItems(Array.isArray(data) ? data : []);
    } catch { toast.error("Failed to load"); }
    setLoading(false);
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setActive(null); }, [propertyId]);

  const open = (item) => {
    setActive(item);
    setDraft({
      status: item.status || "pending",
      admin_notes: item.admin_notes || "",
      quoted_price: item.quoted_price || "",
    });
  };

  const save = async (extraStatus = null) => {
    if (!active) return;
    setSaving(true);
    try {
      const payload = {
        status: extraStatus || draft.status,
        admin_notes: draft.admin_notes || "",
        quoted_price: Number(draft.quoted_price) || 0,
      };
      await axios.put(`${API}/group-booking/${active.id}`, payload);
      toast.success(extraStatus ? `Marked ${extraStatus}` : "Saved");
      load();
      setActive(prev => ({ ...(prev || {}), ...payload }));
    } catch { toast.error("Save failed"); }
    setSaving(false);
  };

  const stats = { pending: 0, quoted: 0, confirmed: 0, cancelled: 0 };
  let totalRoomsHeld = 0, totalQuoted = 0;
  items.forEach(i => {
    const s = i.status || "pending";
    stats[s] = (stats[s] || 0) + 1;
    if (s === "confirmed") totalRoomsHeld += Number(i.total_rooms || 0);
    if (s === "quoted" || s === "confirmed") totalQuoted += Number(i.quoted_price || 0);
  });
  const filtered = filter ? items.filter(i => (i.status || "pending") === filter) : items;

  return (
    <div className="p-5 space-y-5" data-testid="group-requests-panel">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-stone-100 flex items-center gap-2">
            <Briefcase className="w-5 h-5 text-orange-400" />Group Requests & Allotments
            {hotelName && <><span className="text-stone-500 mx-1">·</span><span className="text-violet-400">{hotelName}</span></>}
          </h2>
          <p className="text-xs text-stone-400">B2B / corporate / wedding requests submitted via the booking widget</p>
        </div>
        <button onClick={load} disabled={loading} data-testid="gr-refresh"
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-stone-800 hover:bg-stone-700 text-white text-xs font-bold">
          {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}Refresh
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3" data-testid="gr-stats">
        <Stat label="Total"     value={items.length}        color="text-stone-200"   onClick={() => setFilter("")}          active={filter === ""} />
        <Stat label="Pending"   value={stats.pending}       color="text-amber-300"   onClick={() => setFilter("pending")}   active={filter === "pending"} />
        <Stat label="Quoted"    value={stats.quoted}        color="text-cyan-300"    onClick={() => setFilter("quoted")}    active={filter === "quoted"} />
        <Stat label="Confirmed" value={stats.confirmed}     color="text-emerald-300" onClick={() => setFilter("confirmed")} active={filter === "confirmed"} />
        <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-3">
          <div className="text-[10px] uppercase tracking-widest text-stone-500 font-bold mb-1">Quoted volume</div>
          <div className="text-2xl font-black text-violet-300 tabular-nums">{cur(totalQuoted)}</div>
          <div className="text-[10px] text-stone-500 mt-1">{totalRoomsHeld} rooms held</div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-[420px_1fr] gap-4">
        <div className="bg-stone-900/60 border border-stone-800 rounded-2xl overflow-hidden">
          <div className="px-3 py-2 border-b border-stone-800 text-[10px] uppercase tracking-widest text-stone-500 font-bold flex items-center justify-between">
            <span>{filtered.length} request{filtered.length === 1 ? "" : "s"}</span>
            {filter && <button onClick={() => setFilter("")} className="text-cyan-400 hover:text-cyan-300 normal-case">clear filter</button>}
          </div>
          <div className="max-h-[640px] overflow-y-auto" data-testid="gr-list">
            {filtered.length === 0 && !loading && (
              <div className="p-8 text-center text-stone-500 text-sm" data-testid="gr-empty">
                <Briefcase className="w-10 h-10 mx-auto mb-2 opacity-30" />
                <p>No {filter || ""} group requests yet.</p>
              </div>
            )}
            {filtered.map(g => {
              const meta = STATUS_META[g.status || "pending"] || STATUS_META.pending;
              const isActive = active?.id === g.id;
              return (
                <button key={g.id} onClick={() => open(g)} data-testid={`gr-item-${g.id}`}
                  className={`w-full text-left p-3 border-b border-stone-800/60 transition ${isActive ? "bg-orange-500/10" : "hover:bg-stone-800/40"}`}>
                  <div className="flex items-start justify-between gap-2 mb-1.5">
                    <div className="min-w-0">
                      <p className="text-sm font-bold text-stone-100 truncate">{g.contact_name || "—"}</p>
                      <p className="text-[11px] text-stone-400 truncate">{g.company_name || g.event_type || "—"}</p>
                    </div>
                    <span className={`text-[9px] uppercase font-black tracking-widest px-1.5 py-0.5 rounded border whitespace-nowrap ${meta.color}`}>{meta.label}</span>
                  </div>
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-stone-400">
                    <span className="flex items-center gap-1"><Calendar className="w-3 h-3" />{g.check_in} → {g.check_out}</span>
                    <span className="flex items-center gap-1"><Users className="w-3 h-3" />{g.total_rooms}r · {g.total_guests}g</span>
                    {g.quoted_price > 0 && <span className="text-emerald-300 font-bold">{cur(g.quoted_price)}</span>}
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-4 min-h-[400px]">
          {!active ? (
            <div className="h-full flex items-center justify-center text-stone-500 text-sm" data-testid="gr-detail-empty">
              <div className="text-center">
                <Briefcase className="w-12 h-12 mx-auto mb-3 opacity-30" />
                <p>Select a request to review</p>
              </div>
            </div>
          ) : (
            <div className="space-y-4" data-testid={`gr-detail-${active.id}`}>
              <div className="flex items-start justify-between flex-wrap gap-3">
                <div>
                  <h3 className="text-base font-bold text-stone-100">{active.contact_name}</h3>
                  <p className="text-xs text-stone-400">{active.company_name || "Individual"} · {active.event_type || "—"}</p>
                </div>
                <span className={`text-[9px] uppercase font-black tracking-widest px-1.5 py-0.5 rounded border ${(STATUS_META[active.status || "pending"] || STATUS_META.pending).color}`}>
                  {(STATUS_META[active.status || "pending"] || STATUS_META.pending).label}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3 text-xs">
                <Field icon={Mail} label="Email" value={active.contact_email} />
                <Field icon={Phone} label="Phone" value={active.contact_phone || "—"} />
                <Field icon={Calendar} label="Check-in" value={active.check_in} />
                <Field icon={Calendar} label="Check-out" value={active.check_out} />
                <Field icon={Users} label="Rooms" value={`${active.total_rooms} room(s)`} />
                <Field icon={Users} label="Guests" value={`${active.total_guests} guest(s)`} />
                <Field icon={Building2} label="Room preferences" value={active.room_preferences || "—"} className="col-span-2" />
                <Field icon={FileText} label="Special requirements" value={active.special_requirements || "—"} className="col-span-2" />
                <Field icon={DollarSign} label="Budget range" value={active.budget_range || "—"} />
                <Field icon={Calendar} label="Submitted" value={active.created_at ? new Date(active.created_at).toLocaleString() : "—"} />
              </div>

              <div className="border-t border-stone-800 pt-4 space-y-3">
                <div>
                  <label className="block text-[10px] uppercase tracking-widest text-stone-500 font-bold mb-1">Status</label>
                  <select value={draft.status} onChange={e => setDraft({ ...draft, status: e.target.value })}
                    className="w-full bg-stone-800 border border-stone-700 text-stone-100 text-sm rounded-lg px-3 py-2"
                    data-testid="gr-status-select">
                    {Object.keys(STATUS_META).map(s => <option key={s} value={s}>{STATUS_META[s].label}</option>)}
                  </select>
                </div>

                <div>
                  <label className="text-[10px] uppercase tracking-widest text-stone-500 font-bold mb-1 flex items-center gap-1">
                    <DollarSign className="w-3 h-3" />Quoted price (total)
                  </label>
                  <input type="number" value={draft.quoted_price} onChange={e => setDraft({ ...draft, quoted_price: e.target.value })}
                    placeholder="e.g. 4800"
                    className="w-full bg-stone-800 border border-stone-700 text-stone-100 text-sm rounded-lg px-3 py-2 tabular-nums"
                    data-testid="gr-quoted-price" />
                </div>

                <div>
                  <label className="text-[10px] uppercase tracking-widest text-stone-500 font-bold mb-1 flex items-center gap-1">
                    <MessageSquare className="w-3 h-3" />Admin notes
                  </label>
                  <textarea value={draft.admin_notes} onChange={e => setDraft({ ...draft, admin_notes: e.target.value })} rows={3}
                    placeholder="Internal notes — visible to staff only"
                    className="w-full bg-stone-800 border border-stone-700 text-stone-100 text-sm rounded-lg px-3 py-2 resize-none"
                    data-testid="gr-admin-notes" />
                </div>

                <div className="flex flex-wrap gap-2">
                  <button onClick={() => save()} disabled={saving} data-testid="gr-save"
                    className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-stone-700 hover:bg-stone-600 text-white text-xs font-bold disabled:opacity-50">
                    {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}Save changes
                  </button>
                  <button onClick={() => save("quoted")} disabled={saving} data-testid="gr-quote"
                    className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-700 text-white text-xs font-bold disabled:opacity-50">
                    Send quote
                  </button>
                  <button onClick={() => save("confirmed")} disabled={saving} data-testid="gr-confirm"
                    className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold disabled:opacity-50">
                    Confirm & block
                  </button>
                  <button onClick={() => save("cancelled")} disabled={saving} data-testid="gr-cancel"
                    className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold disabled:opacity-50">
                    <X className="w-3.5 h-3.5" />Cancel
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, color, onClick, active }) {
  return (
    <button onClick={onClick} className={`text-left bg-stone-900/60 border rounded-2xl p-3 transition ${active ? "border-orange-500/60 bg-orange-500/5" : "border-stone-800 hover:border-stone-700"}`}>
      <div className="text-[10px] uppercase tracking-widest text-stone-500 font-bold mb-1">{label}</div>
      <div className={`text-2xl font-black tabular-nums ${color}`}>{value}</div>
    </button>
  );
}

function Field({ icon: Icon, label, value, className = "" }) {
  return (
    <div className={className}>
      <div className="text-[9px] uppercase tracking-widest text-stone-500 font-bold mb-0.5 flex items-center gap-1">
        <Icon className="w-2.5 h-2.5" />{label}
      </div>
      <div className="text-stone-200 break-words">{value}</div>
    </div>
  );
}
