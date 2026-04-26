/**
 * Operations Quick Actions
 * ------------------------
 * Two quick operational tools the front desk needs daily but live in
 * different existing panels:
 *   1. Room Move / Walk — enter booking → see eligible target rooms → move
 *   2. Lost & Found auto-match — enter lost-found item → see candidate
 *      recent guests → notify with one click.
 */
import { useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, ArrowRightLeft, PackageSearch, Search, Send, Sparkles } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function OpsQuickActionsPanel({ propertyId, hotelName = "" }) {
  const [tab, setTab] = useState("room-move");
  return (
    <div className="space-y-6" data-testid="ops-quick-actions">
      <div>
        <h2 className="text-2xl font-semibold text-stone-100">Operations Quick Actions</h2>
        <p className="text-sm text-stone-400 mt-1">{hotelName ? `${hotelName} · ` : ""}Two daily front-desk tools.</p>
      </div>
      <div className="flex gap-2">
        <TabBtn active={tab === "room-move"} onClick={() => setTab("room-move")} icon={ArrowRightLeft} testId="tab-room-move">Room Move / Walk</TabBtn>
        <TabBtn active={tab === "lost-match"} onClick={() => setTab("lost-match")} icon={PackageSearch} testId="tab-lost-match">Lost & Found Match</TabBtn>
      </div>
      {tab === "room-move" ? <RoomMoveTab propertyId={propertyId} /> : <LostFoundMatchTab propertyId={propertyId} />}
    </div>
  );
}

function TabBtn({ active, onClick, icon: Icon, testId, children }) {
  return (
    <button onClick={onClick} data-testid={testId}
      className={`px-3 py-2 rounded-lg text-sm border flex items-center gap-2 ${active
        ? "bg-cyan-500/20 border-cyan-500/40 text-cyan-200"
        : "bg-stone-800 border-stone-700 text-stone-300 hover:bg-stone-700"}`}>
      <Icon className="w-4 h-4" />{children}
    </button>
  );
}

function RoomMoveTab({ propertyId }) {
  const [bid, setBid] = useState("");
  const [opts, setOpts] = useState(null);
  const [reason, setReason] = useState("guest_request");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [moving, setMoving] = useState("");
  const fetchOpts = async () => {
    if (!bid) return;
    setLoading(true); setOpts(null);
    try {
      const { data } = await axios.get(`${API}/room-move/${bid}/options`);
      setOpts(data);
    } catch (e) { toast.error(e?.response?.data?.detail || "Lookup failed"); }
    setLoading(false);
  };
  const move = async (target) => {
    setMoving(target.room_number);
    try {
      await axios.post(`${API}/room-move`, {
        booking_id: bid, new_room_number: target.room_number,
        new_room_id: target.room_id, reason, notes,
      });
      toast.success(`Moved to ${target.room_number}`);
      fetchOpts();
    } catch (e) { toast.error(e?.response?.data?.detail || "Move failed"); }
    setMoving("");
  };
  return (
    <div className="space-y-3" data-testid="room-move-tab">
      <div className="flex flex-wrap gap-2">
        <input data-testid="room-move-bid" value={bid} onChange={(e) => setBid(e.target.value)}
          placeholder="Booking ID"
          className="flex-1 min-w-[200px] px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm" />
        <select value={reason} onChange={(e) => setReason(e.target.value)}
          className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm">
          {["upgrade", "maintenance", "noise", "guest_request", "overbook_walk", "other"].map((r) =>
            <option key={r} value={r}>{r.replaceAll("_", " ")}</option>)}
        </select>
        <input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Notes (optional)"
          className="flex-1 min-w-[200px] px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm" />
        <button data-testid="room-move-search-btn" onClick={fetchOpts}
          className="flex items-center gap-2 px-3 py-2 rounded bg-cyan-500/20 border border-cyan-500/40 text-cyan-200 text-sm">
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
          Find rooms
        </button>
      </div>
      {opts && (
        <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4">
          <div className="text-sm text-stone-400 mb-2">Currently in: <strong className="text-stone-100">{opts.current_room || "—"}</strong> · {opts.options.length} options</div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {opts.options.map((o) => (
              <button key={o.room_id || o.room_number} data-testid="room-move-target" onClick={() => move(o)} disabled={moving === o.room_number}
                className="px-3 py-2 rounded bg-stone-800 hover:bg-cyan-500/20 border border-stone-700 text-stone-200 text-sm flex items-center justify-between">
                <span>Room {o.room_number}<span className="text-stone-500 text-xs ml-1">· fl {o.floor || "?"}</span></span>
                {moving === o.room_number ? <Loader2 className="w-3 h-3 animate-spin" /> : <ArrowRightLeft className="w-3 h-3" />}
              </button>
            ))}
            {opts.options.length === 0 && <div className="text-stone-500 text-sm col-span-4">No eligible rooms.</div>}
          </div>
        </div>
      )}
    </div>
  );
}

function LostFoundMatchTab({ propertyId }) {
  const [iid, setIid] = useState("");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [notifying, setNotifying] = useState("");
  const fetchCands = async () => {
    if (!iid) return;
    setLoading(true); setData(null);
    try {
      const { data } = await axios.get(`${API}/lost-found/${iid}/match-candidates`);
      setData(data);
    } catch (e) { toast.error(e?.response?.data?.detail || "Lookup failed"); }
    setLoading(false);
  };
  const notify = async (c) => {
    setNotifying(c.booking_id);
    try {
      await axios.post(`${API}/lost-found/${iid}/notify-guest`, { booking_id: c.booking_id });
      toast.success(`Queued notification to ${c.guest_email || c.guest_name}`);
    } catch (e) { toast.error(e?.response?.data?.detail || "Notify failed"); }
    setNotifying("");
  };
  return (
    <div className="space-y-3" data-testid="lost-match-tab">
      <div className="flex gap-2 flex-wrap">
        <input data-testid="lost-match-iid" value={iid} onChange={(e) => setIid(e.target.value)}
          placeholder="Lost & Found item ID"
          className="flex-1 min-w-[200px] px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm" />
        <button data-testid="lost-match-search-btn" onClick={fetchCands}
          className="flex items-center gap-2 px-3 py-2 rounded bg-cyan-500/20 border border-cyan-500/40 text-cyan-200 text-sm">
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
          Find candidates
        </button>
      </div>
      {data && (
        <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4">
          <div className="text-sm text-stone-400 mb-2">Found {data.candidates.length} candidate(s) near {data.found_date}</div>
          <div className="space-y-2">
            {data.candidates.map((c) => (
              <div key={c.booking_id} data-testid="lost-match-candidate"
                className="flex items-center justify-between bg-stone-800/40 rounded p-2">
                <div className="flex-1">
                  <div className="text-stone-100 text-sm font-medium">{c.guest_name}</div>
                  <div className="text-xs text-stone-500">{c.guest_email || c.guest_phone || "—"} · room {c.room_number} · checkout {c.check_out}</div>
                  <div className="text-[10px] text-purple-300 mt-0.5">{c.reasons.join(" · ")}</div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-stone-400 font-mono">{c.score} pts</span>
                  <button onClick={() => notify(c)} disabled={notifying === c.booking_id}
                    className="px-2 py-1 rounded bg-cyan-500/20 border border-cyan-500/40 text-cyan-200 text-xs flex items-center gap-1">
                    {notifying === c.booking_id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Send className="w-3 h-3" />}
                    Notify
                  </button>
                </div>
              </div>
            ))}
            {data.candidates.length === 0 && (
              <div className="text-stone-500 text-sm">No matches in ±3 days. Item may need manual lookup.</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
