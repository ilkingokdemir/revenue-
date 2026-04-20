/**
 * Channel Manager MVP (Iter 160) — 3 new panels
 *   - ChannelRestrictionsPanel: MinLOS/MaxLOS/CTA/CTD/StopSell per channel × date
 *   - ChannelInboundPanel:      Manual + iCal inbound reservation pipeline
 *   - ChannelParityPanel:       Rate-parity violation detector
 */
import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Lock, Unlock, Plus, Trash2, RefreshCw, Link2, CheckCircle, AlertTriangle, XCircle, CalendarDays, Activity } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v, c = "GBP") => `${c === "GBP" ? "£" : c === "USD" ? "$" : c === "EUR" ? "€" : ""}${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

/* ═══════════ 15. CHANNEL RESTRICTIONS GRID ═══════════ */
export const ChannelRestrictionsPanel = ({ activePropertyId }) => {
  const pid = activePropertyId || "aldgate-flats";
  const [data, setData] = useState(null);
  const [fromDate, setFromDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [toDate, setToDate] = useState(() => { const d = new Date(); d.setDate(d.getDate() + 30); return d.toISOString().slice(0, 10); });
  const [bulk, setBulk] = useState({ channel_ids: [], min_los: null, max_los: null, closed_to_arrival: null, closed_to_departure: null, stop_sell: null });

  const load = useCallback(async () => {
    try { const { data } = await axios.get(`${API}/channel-restrictions/${pid}?from_date=${fromDate}&to_date=${toDate}`); setData(data); }
    catch { /* */ }
  }, [pid, fromDate, toDate]);
  useEffect(() => { load(); }, [load]);

  const applyBulk = async () => {
    if (!bulk.channel_ids.length) return toast.error("Pick at least one channel");
    const body = { from_date: fromDate, to_date: toDate, channel_ids: bulk.channel_ids };
    ["min_los", "max_los", "closed_to_arrival", "closed_to_departure", "stop_sell"].forEach(k => {
      if (bulk[k] !== null && bulk[k] !== "") body[k] = bulk[k];
    });
    try {
      const { data: r } = await axios.put(`${API}/channel-restrictions/${pid}/bulk`, body);
      toast.success(`Applied to ${r.upserted} date×channel cells`);
      setBulk({ channel_ids: [], min_los: null, max_los: null, closed_to_arrival: null, closed_to_departure: null, stop_sell: null });
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const toggleChannel = (id) => {
    setBulk(b => ({ ...b, channel_ids: b.channel_ids.includes(id) ? b.channel_ids.filter(x => x !== id) : [...b.channel_ids, id] }));
  };

  const clearRange = async () => {
    if (!window.confirm(`Clear all restrictions ${fromDate} → ${toDate}?`)) return;
    try { const { data: r } = await axios.post(`${API}/channel-restrictions/${pid}/clear-range`, { from_date: fromDate, to_date: toDate, channel_ids: bulk.channel_ids.length ? bulk.channel_ids : undefined }); toast.success(`Deleted ${r.deleted}`); load(); }
    catch { toast.error("Failed"); }
  };

  if (!data) return <div className="p-8 text-center" data-testid="cr-loading">Loading…</div>;
  return (
    <div data-testid="channel-restrictions-panel" className="space-y-4">
      <div className="bg-gradient-to-br from-amber-600 to-orange-700 text-white rounded-2xl p-6">
        <div className="flex items-center gap-2 mb-1"><Lock className="w-4 h-4" /><span className="text-[11px] font-bold uppercase tracking-wider opacity-80">Channel Restrictions · MinLOS · MaxLOS · CTA · CTD · StopSell</span></div>
        <h2 className="text-2xl font-bold">{data.count} active restrictions</h2>
        <p className="text-sm opacity-80 mt-1">Pushed to OTAs with rates. Revenue managers use these for yield strategies (min 3 nights for weekends, close arrivals on check-out days, stop-sell for overbooked dates).</p>
      </div>

      <div className="bg-white border rounded-2xl p-6">
        <div className="grid grid-cols-4 gap-3 mb-4">
          <div><label className="text-[10px] font-bold uppercase text-stone-500">From</label><input type="date" value={fromDate} onChange={e => setFromDate(e.target.value)} data-testid="cr-from" className="w-full border rounded px-3 py-2 text-sm" /></div>
          <div><label className="text-[10px] font-bold uppercase text-stone-500">To</label><input type="date" value={toDate} onChange={e => setToDate(e.target.value)} data-testid="cr-to" className="w-full border rounded px-3 py-2 text-sm" /></div>
          <div className="col-span-2 flex items-end gap-2">
            <button onClick={load} data-testid="cr-refresh" className="px-4 py-2 bg-stone-100 rounded-lg text-sm flex items-center gap-1"><RefreshCw className="w-4 h-4" />Refresh</button>
            <button onClick={clearRange} className="px-4 py-2 bg-rose-50 text-rose-700 border border-rose-200 rounded-lg text-sm">Clear range</button>
          </div>
        </div>

        <div className="border-t border-stone-100 pt-4">
          <h3 className="font-bold text-sm mb-2">Bulk Apply</h3>
          <div className="flex flex-wrap gap-2 mb-3">
            {(data.channels || []).map(c => (
              <button key={c.channel_id} type="button" onClick={() => toggleChannel(c.channel_id)}
                data-testid={`cr-ch-${c.channel_id}`}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold border-2 ${bulk.channel_ids.includes(c.channel_id) ? "bg-amber-50 border-amber-500 text-amber-800" : "border-stone-200 text-stone-500"}`}>
                {c.name}
              </button>
            ))}
          </div>
          <div className="grid grid-cols-5 gap-2">
            <div><label className="text-[10px] font-bold text-stone-500">MinLOS</label><input type="number" min={0} value={bulk.min_los ?? ""} onChange={e => setBulk({ ...bulk, min_los: e.target.value === "" ? null : parseInt(e.target.value) })} data-testid="cr-minlos" className="w-full border rounded px-2 py-1.5 text-sm" placeholder="—" /></div>
            <div><label className="text-[10px] font-bold text-stone-500">MaxLOS</label><input type="number" min={0} value={bulk.max_los ?? ""} onChange={e => setBulk({ ...bulk, max_los: e.target.value === "" ? null : parseInt(e.target.value) })} className="w-full border rounded px-2 py-1.5 text-sm" placeholder="—" /></div>
            <div><label className="text-[10px] font-bold text-stone-500">CTA</label><select value={bulk.closed_to_arrival === null ? "" : bulk.closed_to_arrival ? "1" : "0"} onChange={e => setBulk({ ...bulk, closed_to_arrival: e.target.value === "" ? null : e.target.value === "1" })} data-testid="cr-cta" className="w-full border rounded px-2 py-1.5 text-sm"><option value="">—</option><option value="1">Closed</option><option value="0">Open</option></select></div>
            <div><label className="text-[10px] font-bold text-stone-500">CTD</label><select value={bulk.closed_to_departure === null ? "" : bulk.closed_to_departure ? "1" : "0"} onChange={e => setBulk({ ...bulk, closed_to_departure: e.target.value === "" ? null : e.target.value === "1" })} className="w-full border rounded px-2 py-1.5 text-sm"><option value="">—</option><option value="1">Closed</option><option value="0">Open</option></select></div>
            <div><label className="text-[10px] font-bold text-stone-500">Stop Sell</label><select value={bulk.stop_sell === null ? "" : bulk.stop_sell ? "1" : "0"} onChange={e => setBulk({ ...bulk, stop_sell: e.target.value === "" ? null : e.target.value === "1" })} data-testid="cr-stopsell" className="w-full border rounded px-2 py-1.5 text-sm"><option value="">—</option><option value="1">Stop</option><option value="0">Open</option></select></div>
          </div>
          <button onClick={applyBulk} data-testid="cr-apply" className="mt-3 px-5 py-2 bg-amber-600 text-white rounded-lg text-sm font-bold">Apply to selected channels</button>
        </div>
      </div>

      {/* Grid */}
      <div className="bg-white border rounded-2xl p-6 overflow-auto">
        <h3 className="font-bold mb-3">Restriction Grid</h3>
        <table className="min-w-max text-[10px]">
          <thead className="sticky top-0 bg-white"><tr><th className="p-1 text-left pr-3">Channel</th>{(data.dates || []).map(d => <th key={d} className="p-1 font-mono min-w-[60px]">{d.slice(5)}</th>)}</tr></thead>
          <tbody>
            {(data.channels || []).map(c => (
              <tr key={c.channel_id} className="border-t border-stone-100" data-testid={`cr-row-${c.channel_id}`}>
                <td className="p-1 pr-3 text-left font-semibold whitespace-nowrap">{c.name}</td>
                {(data.dates || []).map(d => {
                  const r = data.index?.[c.channel_id]?.[d];
                  if (!r) return <td key={d} className="p-1 text-center text-stone-300">·</td>;
                  return (
                    <td key={d} className="p-1 text-center" data-testid={`cr-cell-${c.channel_id}-${d}`}>
                      <div className="flex flex-wrap gap-0.5 justify-center">
                        {r.min_los && <span className="bg-sky-100 text-sky-700 px-1 rounded" title="MinLOS">≥{r.min_los}</span>}
                        {r.max_los && <span className="bg-indigo-100 text-indigo-700 px-1 rounded" title="MaxLOS">≤{r.max_los}</span>}
                        {r.closed_to_arrival && <span className="bg-amber-100 text-amber-700 px-1 rounded" title="Closed To Arrival">CTA</span>}
                        {r.closed_to_departure && <span className="bg-orange-100 text-orange-700 px-1 rounded" title="Closed To Departure">CTD</span>}
                        {r.stop_sell && <span className="bg-rose-500 text-white px-1 rounded font-bold" title="Stop Sell">SS</span>}
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

/* ═══════════ 16. CHANNEL INBOUND RESERVATIONS ═══════════ */
export const ChannelInboundPanel = ({ activePropertyId }) => {
  const pid = activePropertyId || "aldgate-flats";
  const [tab, setTab] = useState("pending");
  const [rows, setRows] = useState([]);
  const [counts, setCounts] = useState({});
  const [sources, setSources] = useState([]);
  const [showManual, setShowManual] = useState(false);
  const [manual, setManual] = useState({ channel: "Airbnb", channel_booking_ref: "", guest_name: "", guest_email: "", check_in: "", check_out: "", total_price: 0, currency: "GBP", notes: "" });
  const [newSrc, setNewSrc] = useState({ channel: "Airbnb", url: "", label: "" });

  const load = useCallback(async () => {
    try {
      const [{ data: inb }, { data: src }] = await Promise.all([
        axios.get(`${API}/channel-inbound/${pid}${tab === "pending" ? "?status=pending_review" : tab === "confirmed" ? "?status=confirmed" : ""}`),
        axios.get(`${API}/channel-inbound/ical/sources/${pid}`),
      ]);
      setRows(inb.rows || []);
      setCounts({ pending: inb.pending_count, confirmed: inb.confirmed_count });
      setSources(src);
    } catch { /* */ }
  }, [pid, tab]);
  useEffect(() => { load(); }, [load]);

  const submitManual = async () => {
    try { await axios.post(`${API}/channel-inbound/manual`, { ...manual, property_id: pid }); toast.success("Staged as pending review"); setShowManual(false); setManual({ ...manual, channel_booking_ref: "", guest_name: "", guest_email: "", check_in: "", check_out: "", total_price: 0 }); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };
  const confirmRow = async (id) => {
    try { await axios.post(`${API}/channel-inbound/${id}/confirm`); toast.success("Confirmed → booking created"); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };
  const rejectRow = async (id) => {
    const reason = prompt("Reject reason?"); if (!reason) return;
    try { await axios.post(`${API}/channel-inbound/${id}/reject`, { reason }); load(); }
    catch { toast.error("Failed"); }
  };
  const addSource = async () => {
    if (!newSrc.url) return toast.error("URL required");
    try { await axios.post(`${API}/channel-inbound/ical/sources`, { ...newSrc, property_id: pid }); toast.success("iCal source added"); setNewSrc({ channel: "Airbnb", url: "", label: "" }); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };
  const pullSource = async (id) => {
    try { const { data } = await axios.post(`${API}/channel-inbound/ical/fetch/${id}`); toast.success(`${data.source}: ${data.fetched} events, ${data.new_staged} new`); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };
  const delSource = async (id) => {
    if (!window.confirm("Remove this iCal source?")) return;
    try { await axios.delete(`${API}/channel-inbound/ical/sources/${id}`); load(); }
    catch { /* */ }
  };

  return (
    <div data-testid="channel-inbound-panel" className="space-y-4">
      <div className="bg-gradient-to-br from-sky-600 to-blue-700 text-white rounded-2xl p-6 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1"><Link2 className="w-4 h-4" /><span className="text-[11px] font-bold uppercase tracking-wider opacity-80">Inbound Reservations · OTA → PMS</span></div>
          <h2 className="text-2xl font-bold">{counts.pending || 0} pending · {counts.confirmed || 0} confirmed</h2>
          <p className="text-sm opacity-80 mt-1">Reservations from OTAs land here first for review, then promote to real bookings.</p>
        </div>
        <button onClick={() => setShowManual(true)} data-testid="ci-new-manual" className="px-4 py-2 bg-white/20 hover:bg-white/30 rounded-lg text-sm font-bold flex items-center gap-2"><Plus className="w-4 h-4" />Manual Entry</button>
      </div>

      <div className="flex gap-2 border-b border-stone-200">
        {["pending", "confirmed", "all", "sources"].map(t => (
          <button key={t} onClick={() => setTab(t)} data-testid={`ci-tab-${t}`}
            className={`px-4 py-2 text-sm font-bold ${tab === t ? "border-b-2 border-sky-600 text-sky-700" : "text-stone-500"}`}>
            {t === "sources" ? "iCal Sources" : t[0].toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {showManual && (
        <div className="bg-white border-2 border-sky-300 rounded-2xl p-6" data-testid="ci-manual-form">
          <h3 className="font-bold mb-3">Manual OTA Reservation Entry</h3>
          <div className="grid grid-cols-3 gap-3">
            <select value={manual.channel} onChange={e => setManual({ ...manual, channel: e.target.value })} data-testid="ci-manual-channel" className="border rounded px-3 py-2 text-sm">
              <option>Airbnb</option><option>Booking.com</option><option>Expedia</option><option>Agoda</option><option>Hotels.com</option><option>Trip.com</option><option>Vrbo</option>
            </select>
            <input placeholder="Channel booking ref" value={manual.channel_booking_ref} onChange={e => setManual({ ...manual, channel_booking_ref: e.target.value })} data-testid="ci-manual-ref" className="border rounded px-3 py-2 text-sm" />
            <input placeholder="Guest name" value={manual.guest_name} onChange={e => setManual({ ...manual, guest_name: e.target.value })} data-testid="ci-manual-name" className="border rounded px-3 py-2 text-sm" />
            <input placeholder="Guest email" value={manual.guest_email} onChange={e => setManual({ ...manual, guest_email: e.target.value })} className="border rounded px-3 py-2 text-sm" />
            <input type="date" placeholder="Check-in" value={manual.check_in} onChange={e => setManual({ ...manual, check_in: e.target.value })} className="border rounded px-3 py-2 text-sm" />
            <input type="date" placeholder="Check-out" value={manual.check_out} onChange={e => setManual({ ...manual, check_out: e.target.value })} className="border rounded px-3 py-2 text-sm" />
            <input type="number" placeholder="Total price" value={manual.total_price || ""} onChange={e => setManual({ ...manual, total_price: parseFloat(e.target.value) })} data-testid="ci-manual-price" className="border rounded px-3 py-2 text-sm" />
          </div>
          <div className="flex justify-end gap-2 mt-3">
            <button onClick={() => setShowManual(false)} className="px-4 py-2 text-sm">Cancel</button>
            <button onClick={submitManual} data-testid="ci-manual-submit" className="px-4 py-2 bg-sky-600 text-white rounded-lg text-sm font-bold">Stage for Review</button>
          </div>
        </div>
      )}

      {tab !== "sources" ? (
        <div className="bg-white border rounded-2xl p-4">
          <div className="divide-y divide-stone-100">
            {rows.map(r => (
              <div key={r.id} className="py-3 flex items-center gap-3" data-testid={`ci-row-${r.id}`}>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <Badge className="text-[10px]">{r.channel}</Badge>
                    <span className="font-mono text-[10px] text-stone-400">{r.channel_booking_ref || String(r.uid || "").slice(0, 16)}</span>
                    <span className="font-semibold text-sm">{r.guest_name}</span>
                  </div>
                  <div className="text-xs text-stone-400">{r.check_in} → {r.check_out} · {r.total_price ? cur(r.total_price, r.currency) : "—"}</div>
                </div>
                {r.status === "pending_review" && (
                  <>
                    <button onClick={() => confirmRow(r.id)} data-testid={`ci-confirm-${r.id}`} className="px-3 py-1.5 bg-emerald-600 text-white rounded-lg text-xs font-bold flex items-center gap-1"><CheckCircle className="w-3.5 h-3.5" />Confirm</button>
                    <button onClick={() => rejectRow(r.id)} className="px-3 py-1.5 bg-rose-100 text-rose-700 rounded-lg text-xs font-bold">Reject</button>
                  </>
                )}
                {r.status === "confirmed" && <Badge className="bg-emerald-100 text-emerald-700"><CheckCircle className="w-3 h-3 inline mr-1" />Confirmed</Badge>}
                {r.status === "rejected" && <Badge className="bg-rose-100 text-rose-700"><XCircle className="w-3 h-3 inline mr-1" />Rejected</Badge>}
              </div>
            ))}
            {rows.length === 0 && <p className="text-center text-sm text-stone-400 py-6">No {tab} reservations</p>}
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="bg-white border-2 border-sky-300 rounded-2xl p-4" data-testid="ci-source-form">
            <h3 className="font-bold mb-2">Add iCal Source</h3>
            <div className="grid grid-cols-4 gap-2">
              <select value={newSrc.channel} onChange={e => setNewSrc({ ...newSrc, channel: e.target.value })} className="border rounded px-3 py-2 text-sm"><option>Airbnb</option><option>Vrbo</option><option>Booking.com</option></select>
              <input placeholder="Label" value={newSrc.label} onChange={e => setNewSrc({ ...newSrc, label: e.target.value })} className="border rounded px-3 py-2 text-sm" />
              <input placeholder="https://..." value={newSrc.url} onChange={e => setNewSrc({ ...newSrc, url: e.target.value })} data-testid="ci-source-url" className="col-span-1 border rounded px-3 py-2 text-sm" />
              <button onClick={addSource} data-testid="ci-source-add" className="px-4 py-2 bg-sky-600 text-white rounded-lg text-sm font-bold">Add</button>
            </div>
          </div>
          <div className="bg-white border rounded-2xl p-4">
            <h3 className="font-bold mb-3">Sources ({sources.length})</h3>
            <div className="divide-y divide-stone-100">
              {sources.map(s => (
                <div key={s.id} className="py-3 flex items-center gap-3" data-testid={`ci-src-${s.id}`}>
                  <Badge className="text-[10px]">{s.channel}</Badge>
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-sm">{s.label || s.url.slice(0, 50)}</div>
                    <div className="text-xs text-stone-400 font-mono truncate">{s.url}</div>
                  </div>
                  <div className="text-xs text-stone-500">{s.last_pull_at ? `Last: ${new Date(s.last_pull_at).toLocaleString()}` : "Never pulled"}</div>
                  <button onClick={() => pullSource(s.id)} data-testid={`ci-pull-${s.id}`} className="px-3 py-1.5 bg-sky-600 text-white rounded-lg text-xs font-bold flex items-center gap-1"><RefreshCw className="w-3 h-3" />Pull</button>
                  <button onClick={() => delSource(s.id)} className="text-rose-600"><Trash2 className="w-4 h-4" /></button>
                </div>
              ))}
              {sources.length === 0 && <p className="text-center text-sm text-stone-400 py-6">No iCal sources yet. Airbnb hosts: "Manage Listing → Availability → Export Calendar (.ics)"</p>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

/* ═══════════ 17. CHANNEL PARITY MONITOR ═══════════ */
export const ChannelParityPanel = ({ activePropertyId }) => {
  const pid = activePropertyId || "aldgate-flats";
  const [data, setData] = useState(null);
  const [days, setDays] = useState(14);
  const [tolerance, setTolerance] = useState(5);

  const load = useCallback(async () => {
    try { const { data } = await axios.get(`${API}/channel-parity/${pid}?days=${days}&tolerance_pct=${tolerance}`); setData(data); }
    catch { /* */ }
  }, [pid, days, tolerance]);
  useEffect(() => { load(); }, [load]);

  if (!data) return <div className="p-8 text-center" data-testid="cp-loading">Loading…</div>;
  const s = data.summary || {};
  const gradeColor = s.overall_parity_pct >= 95 ? "from-emerald-500 to-green-600" : s.overall_parity_pct >= 80 ? "from-amber-500 to-orange-600" : "from-rose-600 to-red-700";

  return (
    <div data-testid="channel-parity-panel" className="space-y-4">
      <div className={`bg-gradient-to-br ${gradeColor} text-white rounded-2xl p-6`}>
        <div className="flex items-center gap-2 mb-2"><Activity className="w-4 h-4" /><span className="text-[11px] font-bold uppercase tracking-wider opacity-80">Channel Parity Monitor</span></div>
        <div className="flex items-end justify-between">
          <div>
            <div className="text-6xl font-black" data-testid="cp-score">{s.overall_parity_pct}%</div>
            <p className="text-sm opacity-80 mt-1">{s.total_violations} violations across {s.channels_with_violations}/{s.total_channels} channels (±{tolerance}% tolerance)</p>
          </div>
          <div className="flex gap-2">
            <input type="number" min={1} max={60} value={days} onChange={e => setDays(parseInt(e.target.value) || 14)} data-testid="cp-days" className="w-20 bg-white/20 text-white rounded px-2 py-1 text-sm font-mono" />
            <span className="text-xs self-center opacity-80">days</span>
            <input type="number" min={0.5} max={20} step={0.5} value={tolerance} onChange={e => setTolerance(parseFloat(e.target.value) || 5)} data-testid="cp-tolerance" className="w-20 bg-white/20 text-white rounded px-2 py-1 text-sm font-mono" />
            <span className="text-xs self-center opacity-80">% tol</span>
          </div>
        </div>
      </div>

      <div className="bg-white border rounded-2xl p-6">
        <h3 className="font-bold mb-3">Parity by Channel</h3>
        <div className="space-y-2">
          {(data.by_channel || []).map(c => (
            <div key={c.channel_id} className="flex items-center gap-3" data-testid={`cp-ch-${c.channel_id}`}>
              <div className="w-32 text-sm font-semibold truncate">{c.channel_name}</div>
              <div className="flex-1 bg-stone-100 rounded-full h-2 overflow-hidden">
                <div className={`h-full ${c.parity_pct >= 95 ? "bg-emerald-500" : c.parity_pct >= 80 ? "bg-amber-500" : "bg-rose-500"}`} style={{ width: `${c.parity_pct}%` }} />
              </div>
              <div className="w-16 text-right text-sm font-mono font-bold">{c.parity_pct}%</div>
              <div className="w-20 text-right text-xs text-stone-400">{c.rule} {c.markup_pct ? `${c.markup_pct > 0 ? "+" : ""}${c.markup_pct}%` : ""}</div>
              <Badge className={c.violation_count > 0 ? "bg-rose-100 text-rose-700" : "bg-stone-100 text-stone-500"}>{c.violation_count} violations</Badge>
            </div>
          ))}
          {(data.by_channel || []).length === 0 && <p className="text-center text-sm text-stone-400 py-6">No channels connected</p>}
        </div>
      </div>

      <div className="bg-white border rounded-2xl p-6">
        <h3 className="font-bold mb-3">Violations ({s.total_violations})</h3>
        {(data.violations || []).length === 0 ? (
          <div className="text-center py-8 text-emerald-600"><CheckCircle className="w-12 h-12 mx-auto mb-2" /><p className="font-bold">All channels in parity</p></div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-stone-50"><tr className="text-left"><th className="p-2">Date</th><th className="p-2">Channel</th><th className="p-2 text-right">Direct</th><th className="p-2 text-right">Channel</th><th className="p-2 text-right">Δ</th><th className="p-2">Severity</th></tr></thead>
              <tbody>
                {(data.violations || []).slice(0, 100).map((v, i) => (
                  <tr key={i} className="border-b border-stone-100" data-testid={`cp-v-${v.channel_id}-${v.date}`}>
                    <td className="p-2 font-mono">{v.date}</td>
                    <td className="p-2 font-semibold">{v.channel_name}</td>
                    <td className="p-2 text-right font-mono">{cur(v.direct_rate)}</td>
                    <td className="p-2 text-right font-mono">{cur(v.channel_rate)}</td>
                    <td className={`p-2 text-right font-mono font-bold ${v.delta_pct > 0 ? "text-sky-600" : "text-rose-600"}`}>{v.delta_pct > 0 ? "+" : ""}{v.delta_pct}%</td>
                    <td className="p-2"><Badge className={v.severity === "high" ? "bg-rose-500 text-white" : "bg-amber-200 text-amber-900"}>{v.severity}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

/* ═══════════ 18. OTA HEALTH DASHBOARD — composite board-ready tile ═══════════ */
export const OtaHealthPanel = ({ activePropertyId }) => {
  const pid = activePropertyId || "aldgate-flats";
  const [data, setData] = useState(null);

  const load = useCallback(async () => {
    try { const { data } = await axios.get(`${API}/ota-health/${pid}`); setData(data); }
    catch { /* */ }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  if (!data) return <div className="p-8 text-center" data-testid="oh-loading">Loading…</div>;
  const gradeColor = {
    "A+": "from-emerald-500 to-green-600",
    "A": "from-emerald-500 to-green-600",
    "B": "from-sky-500 to-blue-600",
    "C": "from-amber-500 to-orange-600",
    "D": "from-rose-500 to-red-600",
    "F": "from-rose-700 to-red-800",
  }[data.grade] || "from-stone-500 to-stone-600";

  const tintBg = { sky: "bg-sky-500", fuchsia: "bg-fuchsia-500", emerald: "bg-emerald-500", violet: "bg-violet-500" };
  const tintBorder = {
    sky: "border-sky-200 bg-sky-50",
    fuchsia: "border-fuchsia-200 bg-fuchsia-50",
    emerald: "border-emerald-200 bg-emerald-50",
    violet: "border-violet-200 bg-violet-50",
  };

  return (
    <div data-testid="ota-health-panel" className="space-y-4">
      <div className={`bg-gradient-to-br ${gradeColor} text-white rounded-2xl p-8`}>
        <div className="flex items-center gap-2 mb-2"><Activity className="w-4 h-4" /><span className="text-[11px] font-bold uppercase tracking-wider opacity-80">OTA Health · Board-ready composite</span></div>
        <div className="flex items-end gap-8">
          <div>
            <div className="text-[10px] font-bold uppercase opacity-70">Grade</div>
            <div className="text-7xl font-black leading-none tracking-tighter" data-testid="oh-grade">{data.grade}</div>
          </div>
          <div>
            <div className="text-[10px] font-bold uppercase opacity-70">Score</div>
            <div className="text-5xl font-bold" data-testid="oh-score">{data.overall_score}<span className="text-2xl opacity-70">/100</span></div>
          </div>
          <div className="ml-auto text-right opacity-80">
            <div className="text-xs">Last 30d revenue</div>
            <div className="text-2xl font-mono font-bold">{cur(data.total_revenue_30d)}</div>
            <div className="text-[10px]">{data.channel_mix?.length || 0} active channels</div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {(data.metrics || []).map(m => (
          <div key={m.key} className={`border-2 rounded-2xl p-5 ${tintBorder[m.color]}`} data-testid={`oh-metric-${m.key}`}>
            <div className="flex items-center justify-between mb-3">
              <div className="text-sm font-bold text-stone-800">{m.label}</div>
              <div className="text-2xl font-black">{m.score}<span className="text-xs text-stone-400">/100</span></div>
            </div>
            <div className="w-full bg-white/60 rounded-full h-2 overflow-hidden mb-3">
              <div className={`h-full ${tintBg[m.color]}`} style={{ width: `${m.score}%` }} />
            </div>
            <div className="flex items-end justify-between">
              <div>
                <div className="text-[10px] font-bold uppercase text-stone-500">Current</div>
                <div className="text-xl font-bold">{m.value}{m.unit}</div>
              </div>
              <div className="text-right">
                <div className="text-[10px] font-bold uppercase text-stone-400">Target</div>
                <div className="text-sm text-stone-600">{m.target}{m.unit}</div>
              </div>
            </div>
            <p className="text-xs text-stone-500 mt-3">{m.summary}</p>
          </div>
        ))}
      </div>

      <div className="bg-white border rounded-2xl p-6">
        <h3 className="font-bold mb-3">Channel Revenue Share — Last 30 days</h3>
        <div className="space-y-2">
          {(data.channel_mix || []).map(c => (
            <div key={c.channel} className="flex items-center gap-3" data-testid={`oh-ch-${c.channel.replace(/[^a-z0-9]/gi, '').toLowerCase()}`}>
              <div className="w-32 text-sm font-semibold truncate">{c.channel}</div>
              <div className="flex-1 bg-stone-100 rounded-full h-2 overflow-hidden">
                <div className="h-full bg-gradient-to-r from-sky-500 to-indigo-600" style={{ width: `${c.share_pct}%` }} />
              </div>
              <div className="w-24 text-right font-mono font-bold">{cur(c.revenue)}</div>
              <div className="w-14 text-right text-xs text-stone-500">{c.share_pct}%</div>
            </div>
          ))}
          {(data.channel_mix || []).length === 0 && <p className="text-center text-sm text-stone-400 py-4">No bookings in last 30 days</p>}
        </div>
      </div>
    </div>
  );
};


/* ═══════════ 19. CHANNEL MAPPINGS MATRIX ═══════════ */
export const ChannelMappingsPanel = ({ activePropertyId }) => {
  const pid = activePropertyId || "aldgate-flats";
  const [data, setData] = useState(null);
  const [tab, setTab] = useState("room");

  const load = useCallback(async () => {
    try { const { data } = await axios.get(`${API}/channel-mappings/${pid}`); setData(data); }
    catch { /* */ }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  const saveCell = async (kind, internalId, channelId, externalId, externalLabel) => {
    try {
      await axios.put(`${API}/channel-mappings/${pid}/upsert`, {
        kind, internal_id: internalId, channel_id: channelId,
        external_id: externalId, external_label: externalLabel || "",
      });
      if (externalId) toast.success("Saved"); else toast.success("Cleared");
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  if (!data) return <div className="p-8 text-center" data-testid="cm-loading">Loading…</div>;
  const items = tab === "room" ? data.room_types : data.rate_plans;
  const s = data.stats || {};

  return (
    <div data-testid="channel-mappings-panel" className="space-y-4">
      <div className="bg-gradient-to-br from-indigo-700 to-purple-800 text-white rounded-2xl p-6">
        <div className="flex items-center gap-2 mb-1"><Link2 className="w-4 h-4" /><span className="text-[11px] font-bold uppercase tracking-wider opacity-80">Channel Mappings · Internal ↔ OTA IDs</span></div>
        <div className="flex items-end justify-between">
          <div>
            <h2 className="text-2xl font-bold" data-testid="cm-coverage">{s.coverage_pct}% coverage</h2>
            <p className="text-sm opacity-80">{s.total_mapped}/{s.total_mappings_expected} cells mapped · rates can only push where mappings exist</p>
          </div>
        </div>
      </div>

      <div className="flex gap-2 border-b border-stone-200">
        {["room", "rate_plan"].map(t => (
          <button key={t} onClick={() => setTab(t)} data-testid={`cm-tab-${t}`}
            className={`px-4 py-2 text-sm font-bold ${tab === t ? "border-b-2 border-indigo-600 text-indigo-700" : "text-stone-500"}`}>
            {t === "room" ? "Room Types" : "Rate Plans"}
          </button>
        ))}
      </div>

      <div className="bg-white border rounded-2xl p-4 overflow-auto">
        {items.length === 0 ? (
          <p className="text-center text-sm text-stone-400 py-8">No {tab === "room" ? "room types" : "rate plans"} defined yet. Create some first in Room Types / Rate Plans.</p>
        ) : (
          <table className="min-w-max text-xs">
            <thead className="sticky top-0 bg-white">
              <tr className="text-left">
                <th className="p-2 pr-6 whitespace-nowrap">Internal {tab === "room" ? "Room Type" : "Rate Plan"}</th>
                {(data.channels || []).map(c => (
                  <th key={c.channel_id} className="p-2 text-center min-w-[180px]" data-testid={`cm-ch-${c.channel_id}`}>
                    {c.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map(item => (
                <tr key={item.id} className="border-t border-stone-100" data-testid={`cm-row-${item.id}`}>
                  <td className="p-2 pr-6 font-semibold whitespace-nowrap">{item.name || item.id}<div className="text-[10px] text-stone-400 font-mono">{item.id}</div></td>
                  {(data.channels || []).map(c => {
                    const cur = data.index?.[tab]?.[item.id]?.[c.channel_id];
                    return (
                      <td key={c.channel_id} className="p-1" data-testid={`cm-cell-${item.id}-${c.channel_id}`}>
                        <input
                          defaultValue={cur?.external_id || ""}
                          placeholder="—"
                          onBlur={e => {
                            const val = e.target.value.trim();
                            if ((cur?.external_id || "") !== val) saveCell(tab, item.id, c.channel_id, val, cur?.external_label || "");
                          }}
                          className={`w-full border rounded px-2 py-1.5 text-[11px] font-mono ${cur?.external_id ? "border-emerald-200 bg-emerald-50" : "border-stone-200"}`}
                        />
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="bg-stone-50 border border-stone-200 rounded-xl p-4 text-xs text-stone-600">
        <strong>How it works:</strong> enter the OTA's own room/rate ID into each cell. When pushing rates, the payload is translated per channel using these mappings. Empty cell = that room/rate is not distributed to that channel. Green cell = mapping is live.
      </div>
    </div>
  );
};

/* ═══════════ 20. SYNC QUEUE WITH BACKOFF ═══════════ */
export const SyncQueuePanel = ({ activePropertyId }) => {
  const pid = activePropertyId || "aldgate-flats";
  const [data, setData] = useState(null);
  const [filter, setFilter] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try { const { data } = await axios.get(`${API}/sync-queue/${pid}${filter ? `?status=${filter}` : ""}`); setData(data); }
    catch { /* */ }
  }, [pid, filter]);
  useEffect(() => { load(); }, [load]);

  const runTick = async () => {
    setBusy(true);
    try { const { data } = await axios.post(`${API}/sync-queue/run-tick`); toast.success(`Tick: ${data.succeeded} ok, ${data.rescheduled} retry, ${data.dead_lettered} dead`); load(); }
    catch { toast.error("Failed"); }
    finally { setBusy(false); }
  };
  const retry = async (id) => {
    try { await axios.post(`${API}/sync-queue/${id}/retry`); load(); toast.success("Re-queued"); }
    catch { /* */ }
  };
  const clearDead = async () => {
    if (!window.confirm("Clear all dead-letter items?")) return;
    try { const { data } = await axios.post(`${API}/sync-queue/${pid}/clear-dead-letter`); toast.success(`Deleted ${data.deleted}`); load(); }
    catch { /* */ }
  };

  if (!data) return <div className="p-8 text-center" data-testid="sq-loading">Loading…</div>;
  const c = data.counts || {};

  return (
    <div data-testid="sync-queue-panel" className="space-y-4">
      <div className="bg-gradient-to-br from-cyan-600 to-sky-700 text-white rounded-2xl p-6 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1"><RefreshCw className="w-4 h-4" /><span className="text-[11px] font-bold uppercase tracking-wider opacity-80">Sync Queue · Exponential Backoff</span></div>
          <h2 className="text-2xl font-bold">{c.pending || 0} pending · {c.succeeded || 0} succeeded · {c.dead_letter || 0} dead-letter</h2>
          <p className="text-sm opacity-80 mt-1">Failed OTA pushes retry with backoff: 1min → 5min → 15min → 1h → 4h. After 6 attempts they land in dead-letter for manual review.</p>
        </div>
        <div className="flex flex-col gap-2">
          <button onClick={runTick} disabled={busy} data-testid="sq-run-tick" className="px-4 py-2 bg-white/20 hover:bg-white/30 rounded-lg text-sm font-bold flex items-center gap-2"><RefreshCw className="w-4 h-4" />{busy ? "Running…" : "Run Tick"}</button>
          {c.dead_letter > 0 && <button onClick={clearDead} data-testid="sq-clear-dead" className="px-4 py-2 bg-rose-500 hover:bg-rose-600 rounded-lg text-sm font-bold">Clear dead</button>}
        </div>
      </div>

      <div className="grid grid-cols-5 gap-2">
        {[
          { k: "", label: "All", v: data.total, color: "bg-stone-600" },
          { k: "pending", label: "Pending", v: c.pending || 0, color: "bg-amber-500" },
          { k: "processing", label: "Processing", v: c.processing || 0, color: "bg-sky-500" },
          { k: "succeeded", label: "Succeeded", v: c.succeeded || 0, color: "bg-emerald-500" },
          { k: "dead_letter", label: "Dead letter", v: c.dead_letter || 0, color: "bg-rose-600" },
        ].map(b => (
          <button key={b.k} onClick={() => setFilter(b.k)}
            data-testid={`sq-filter-${b.k || 'all'}`}
            className={`rounded-xl p-3 text-white ${b.color} ${filter === b.k ? "ring-2 ring-offset-2 ring-stone-400" : "opacity-75"} transition hover:opacity-100`}>
            <div className="text-[10px] font-bold uppercase opacity-80">{b.label}</div>
            <div className="text-2xl font-bold">{b.v}</div>
          </button>
        ))}
      </div>

      <div className="bg-white border rounded-2xl p-4 overflow-auto">
        <table className="w-full text-xs">
          <thead className="bg-stone-50"><tr className="text-left">
            <th className="p-2">Status</th>
            <th className="p-2">Channel</th>
            <th className="p-2">Kind</th>
            <th className="p-2">Payload</th>
            <th className="p-2 text-center">Attempts</th>
            <th className="p-2">Next retry</th>
            <th className="p-2">Error</th>
            <th className="p-2"></th>
          </tr></thead>
          <tbody>
            {(data.rows || []).map(r => (
              <tr key={r.id} className="border-t border-stone-100" data-testid={`sq-row-${r.id}`}>
                <td className="p-2">
                  <Badge className={
                    r.status === "succeeded" ? "bg-emerald-100 text-emerald-700" :
                    r.status === "pending" ? "bg-amber-100 text-amber-700" :
                    r.status === "processing" ? "bg-sky-100 text-sky-700" :
                    r.status === "dead_letter" ? "bg-rose-500 text-white" : "bg-stone-100 text-stone-600"
                  }>{r.status}</Badge>
                </td>
                <td className="p-2 font-mono text-[10px]">{r.channel_id}</td>
                <td className="p-2"><Badge className="text-[10px]">{r.kind}</Badge></td>
                <td className="p-2 font-mono text-[10px] text-stone-500 max-w-[200px] truncate">{JSON.stringify(r.payload)}</td>
                <td className="p-2 text-center font-mono">{r.attempts}/{r.max_attempts}</td>
                <td className="p-2 text-[10px] text-stone-400">{r.next_retry_at ? new Date(r.next_retry_at).toLocaleString() : "—"}</td>
                <td className="p-2 text-[10px] text-rose-600 max-w-[150px] truncate">{r.error || ""}</td>
                <td className="p-2">
                  {(r.status === "failed" || r.status === "dead_letter") && (
                    <button onClick={() => retry(r.id)} data-testid={`sq-retry-${r.id}`} className="text-xs text-sky-600 hover:underline">Retry</button>
                  )}
                </td>
              </tr>
            ))}
            {(data.rows || []).length === 0 && <tr><td colSpan={8} className="p-6 text-center text-stone-400">No items</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
};

