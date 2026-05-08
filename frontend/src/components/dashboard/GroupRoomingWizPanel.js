/**
 * Group Rooming Wizard Panel
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, Users, RefreshCw, Plus, Wand2, CheckCircle2 } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function GroupRoomingWizPanel({ propertyId, hotelName = "" }) {
  const [sessions, setSessions] = useState([]);
  const [active, setActive] = useState(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ group_name: "", client_company: "", check_in: "", check_out: "", preferred_room_type: "", preferred_floor: "" });
  const [guest, setGuest] = useState({ guest_name: "", guest_email: "" });
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/group-rooming/${propertyId}/sessions`);
      setSessions(data.items || []);
      if (active) {
        const { data: s } = await axios.get(`${API}/group-rooming/sessions/${active.id}`);
        setActive(s);
      }
    } catch { toast.error("Load failed"); }
    setLoading(false);
  }, [propertyId, active]);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { (async () => {
    if (!propertyId) return;
    try {
      const { data } = await axios.get(`${API}/group-rooming/${propertyId}/sessions`);
      setSessions(data.items || []);
    } catch {}
  })(); }, [propertyId]);

  const create = async () => {
    if (!form.group_name || !form.check_in || !form.check_out) return toast.error("Required fields missing");
    try {
      const { data } = await axios.post(`${API}/group-rooming/sessions`, { property_id: propertyId, ...form });
      toast.success("Session opened");
      setActive(data.session);
      setCreating(false);
      refresh();
    } catch { toast.error("Failed"); }
  };

  const addGuest = async () => {
    if (!guest.guest_name || !active) return;
    try {
      await axios.post(`${API}/group-rooming/sessions/${active.id}/add-guest`, guest);
      setGuest({ guest_name: "", guest_email: "" });
      refresh();
    } catch { toast.error("Failed"); }
  };

  const autoAssign = async () => {
    if (!active) return;
    try {
      const { data } = await axios.post(`${API}/group-rooming/sessions/${active.id}/auto-assign`, {});
      toast.success(`${data.assignments.length} assignments · ${data.all_same_floor ? "same floor ✓" : "spans floors " + data.floors_used.join(",")}`);
      refresh();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  const finalize = async () => {
    if (!active) return;
    if (!window.confirm(`Create ${active.assignments?.length || 0} bookings? This cannot be undone.`)) return;
    try {
      const { data } = await axios.post(`${API}/group-rooming/sessions/${active.id}/finalize`, {});
      toast.success(`Created ${data.count} bookings`);
      refresh();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  return (
    <div className="space-y-6" data-testid="group-rooming-wiz-panel">
      <div>
        <h2 className="text-2xl font-semibold text-stone-100">Group Rooming Wizard</h2>
        <p className="text-sm text-stone-400 mt-1">{hotelName ? `${hotelName} · ` : ""}Build a group manifest, auto-assign rooms keeping the group together, then create all bookings in one click.</p>
      </div>

      <div className="flex gap-2">
        <button data-testid="grw-new-btn" onClick={() => setCreating(true)} className="text-sm px-3 py-2 rounded bg-cyan-500/20 border border-cyan-500/40 text-cyan-200 flex items-center gap-2"><Plus className="w-4 h-4" /> New session</button>
        <button onClick={refresh} className="text-sm px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-300 flex items-center gap-2">{loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />} Refresh</button>
      </div>

      {creating && (
        <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4 grid grid-cols-2 md:grid-cols-3 gap-2 text-xs">
          <input data-testid="grw-name-input" placeholder="Group name" value={form.group_name} onChange={(e) => setForm({ ...form, group_name: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" />
          <input placeholder="Client company" value={form.client_company} onChange={(e) => setForm({ ...form, client_company: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" />
          <input type="date" value={form.check_in} onChange={(e) => setForm({ ...form, check_in: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" />
          <input type="date" value={form.check_out} onChange={(e) => setForm({ ...form, check_out: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" />
          <input placeholder="Preferred room type" value={form.preferred_room_type} onChange={(e) => setForm({ ...form, preferred_room_type: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" />
          <input placeholder="Preferred floor" value={form.preferred_floor} onChange={(e) => setForm({ ...form, preferred_floor: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" />
          <button data-testid="grw-create-btn" onClick={create} className="col-span-2 md:col-span-3 px-2 py-2 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-200">Open session</button>
        </div>
      )}

      <div className="grid lg:grid-cols-3 gap-4">
        <div className="rounded-xl border border-stone-800 bg-stone-900/60">
          <div className="px-4 py-2 border-b border-stone-800 text-xs uppercase tracking-wider text-stone-400 flex items-center gap-2"><Users className="w-3 h-3" /> Sessions</div>
          {sessions.map((s) => (
            <button key={s.id} onClick={() => { setActive(s); setCreating(false); }} className={`w-full text-left px-3 py-2 border-t border-stone-800/60 hover:bg-stone-800/40 ${active?.id === s.id ? "bg-stone-800/60" : ""}`} data-testid="grw-session-row">
              <div className="text-sm text-stone-100">{s.group_name}</div>
              <div className="text-[10px] text-stone-400">{s.check_in} → {s.check_out} · {(s.manifest || []).length} guests · {s.status}</div>
            </button>
          ))}
          {sessions.length === 0 && <div className="px-3 py-6 text-center text-stone-500 text-xs">No sessions yet.</div>}
        </div>

        <div className="rounded-xl border border-stone-800 bg-stone-900/60 lg:col-span-2 p-4 space-y-3">
          {!active ? (
            <div className="text-center text-stone-500 py-12">Select or create a session.</div>
          ) : (
            <>
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-stone-100 font-medium">{active.group_name}</div>
                  <div className="text-xs text-stone-400">{active.check_in} → {active.check_out} · {active.client_company}</div>
                </div>
                <span className={`text-[10px] px-2 py-0.5 rounded border ${active.status === "draft" ? "bg-stone-800 border-stone-700 text-stone-300" : active.status === "finalized" ? "bg-emerald-500/20 border-emerald-500/40 text-emerald-200" : "bg-stone-800 border-stone-700 text-stone-400"}`}>{active.status}</span>
              </div>

              {active.status === "draft" && (
                <>
                  <div className="flex gap-2 text-xs">
                    <input data-testid="grw-guest-name-input" placeholder="Guest name" value={guest.guest_name} onChange={(e) => setGuest({ ...guest, guest_name: e.target.value })} className="flex-1 px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" />
                    <input placeholder="Email" value={guest.guest_email} onChange={(e) => setGuest({ ...guest, guest_email: e.target.value })} className="flex-1 px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" />
                    <button data-testid="grw-add-guest-btn" onClick={addGuest} className="px-3 py-1 rounded bg-cyan-500/20 border border-cyan-500/40 text-cyan-200 flex items-center gap-1"><Plus className="w-3 h-3" /></button>
                  </div>
                  <div className="flex gap-2">
                    <button data-testid="grw-auto-assign-btn" onClick={autoAssign} disabled={!(active.manifest || []).length} className="text-sm px-3 py-1 rounded bg-violet-500/20 border border-violet-500/40 text-violet-200 flex items-center gap-2"><Wand2 className="w-3 h-3" /> Auto-assign rooms</button>
                    <button data-testid="grw-finalize-btn" onClick={finalize} disabled={!(active.assignments || []).length} className="text-sm px-3 py-1 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 flex items-center gap-2"><CheckCircle2 className="w-3 h-3" /> Finalize → create bookings</button>
                  </div>
                </>
              )}

              <div className="text-xs uppercase tracking-wider text-stone-400">Manifest ({(active.manifest || []).length})</div>
              <table className="min-w-full text-xs">
                <thead><tr className="text-left text-[10px] text-stone-500 border-b border-stone-800"><th className="px-2 py-1">#</th><th className="px-2 py-1">Guest</th><th className="px-2 py-1">Room</th><th className="px-2 py-1">Floor</th></tr></thead>
                <tbody>
                  {(active.manifest || []).map((g, i) => {
                    const a = (active.assignments || []).find((x) => x.guest_index === g.ix);
                    return (
                      <tr key={i} className="border-t border-stone-800/60 text-stone-200" data-testid="grw-manifest-row">
                        <td className="px-2 py-1">{g.ix + 1}</td>
                        <td className="px-2 py-1"><div>{g.guest_name}</div><div className="text-[10px] text-stone-500">{g.guest_email}</div></td>
                        <td className="px-2 py-1">{a ? <span className="text-cyan-300">{a.room_number}</span> : <span className="text-stone-500">—</span>}</td>
                        <td className="px-2 py-1 text-stone-400">{a ? a.floor : ""}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
