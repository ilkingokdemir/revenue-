/**
 * AI Dynamic Pricing v2 — calls /api/dynamic-pricing/{property_id}/ai-v2/recommend
 * (GPT-5.2 reasoning over pace + competitor + event signals) and lets the
 * revenue manager review per-day suggestions, then push selected dates to the
 * rate calendar via /api/dynamic-pricing/{property_id}/ai-v2/apply.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Sparkles, Loader2, ArrowUp, ArrowDown, Check, RefreshCw, Send,
  TrendingUp, Calendar, Brain,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { maximumFractionDigits: 0 })}`;
const CONF_COLOUR = { high: "text-emerald-300 bg-emerald-500/15 border-emerald-500/30",
                      med:  "text-amber-300 bg-amber-500/15 border-amber-500/30",
                      low:  "text-stone-300 bg-stone-500/15 border-stone-500/30" };

export default function AIPricingV2Panel({ propertyId, hotelName = "" }) {
  const [days, setDays] = useState(14);
  const [roomTypes, setRoomTypes] = useState([]);
  const [roomTypeId, setRoomTypeId] = useState("");
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);
  const [selected, setSelected] = useState({});
  const [applying, setApplying] = useState(false);

  // Load room types
  useEffect(() => {
    if (!propertyId) return;
    axios.get(`${API}/room-types?property_id=${propertyId}`)
      .then(r => {
        const list = r.data || [];
        setRoomTypes(list);
        if (list.length && !roomTypeId) setRoomTypeId(list[0].id);
      })
      .catch(() => {});
  }, [propertyId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Branch hygiene
  useEffect(() => { setData(null); setSelected({}); }, [propertyId]);

  const recommend = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    setData(null);
    setSelected({});
    try {
      const { data } = await axios.post(`${API}/dynamic-pricing/${propertyId}/ai-v2/recommend`,
        { days, room_type_id: roomTypeId || undefined });
      setData(data);
      // Pre-select all by default
      const sel = {};
      (data.recommendations || []).forEach(r => { sel[r.date] = true; });
      setSelected(sel);
      if (data.fallback) toast.message("Fallback heuristic shown (no LLM)");
      else toast.success("AI v2 recommendations ready");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "AI engine error");
    }
    setLoading(false);
  }, [propertyId, days, roomTypeId]);

  const apply = async () => {
    if (!data?.recommendations?.length) return;
    const recs = data.recommendations.filter(r => selected[r.date]);
    if (!recs.length) return toast.error("Select at least one date");
    setApplying(true);
    try {
      const res = await axios.post(`${API}/dynamic-pricing/${propertyId}/ai-v2/apply`,
        { room_type_id: roomTypeId, recommendations: recs });
      toast.success(`Applied ${res.data.applied} rate(s) to calendar`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Apply failed");
    }
    setApplying(false);
  };

  const recs = data?.recommendations || [];
  const totalDelta = recs.length
    ? Math.round(recs.reduce((s, r) => s + Number(r.delta_pct || 0), 0) / recs.length * 10) / 10
    : 0;

  return (
    <div className="p-5 space-y-5" data-testid="ai-pricing-v2-panel">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-stone-100 flex items-center gap-2">
            <Brain className="w-5 h-5 text-violet-400" />
            AI Dynamic Pricing v2 (GPT-5.2)
            {hotelName && <><span className="text-stone-500 mx-1">·</span><span className="text-violet-400">{hotelName}</span></>}
          </h2>
          <p className="text-xs text-stone-400">Pace + competitors + events → reasoned rate suggestions per day</p>
        </div>
        <div className="flex items-center gap-2">
          <select value={roomTypeId} onChange={e => setRoomTypeId(e.target.value)}
            className="bg-stone-900 border border-stone-800 text-stone-100 text-xs rounded-lg px-2 py-1.5"
            data-testid="ai-v2-room-type">
            {roomTypes.length === 0 && <option>No room types</option>}
            {roomTypes.map(rt => <option key={rt.id} value={rt.id}>{rt.name} · £{rt.base_rate}</option>)}
          </select>
          <div className="flex items-center gap-1 bg-stone-900 border border-stone-800 rounded-xl p-0.5">
            {[7, 14, 21, 30].map(d => (
              <button key={d} onClick={() => setDays(d)}
                className={`px-2.5 py-1 text-xs font-bold rounded-lg ${days === d ? "bg-violet-600 text-white" : "text-stone-400 hover:text-white"}`}
                data-testid={`ai-v2-days-${d}`}>{d}d</button>
            ))}
          </div>
          <button onClick={recommend} disabled={loading || !propertyId} data-testid="ai-v2-recommend-btn"
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-gradient-to-br from-violet-600 to-fuchsia-600 hover:from-violet-700 hover:to-fuchsia-700 text-white text-xs font-bold disabled:opacity-50">
            {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
            {loading ? "Analysing…" : "Generate Recommendations"}
          </button>
        </div>
      </div>

      {/* Summary card */}
      {data && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3" data-testid="ai-v2-summary">
          <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-4">
            <div className="text-[10px] uppercase tracking-widest text-stone-500 font-bold mb-1">Avg Δ vs Base</div>
            <div className={`text-3xl font-black ${totalDelta >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
              {totalDelta >= 0 ? "+" : ""}{totalDelta}%
            </div>
            <div className="text-[10px] text-stone-500 mt-1">Across {recs.length} days</div>
          </div>
          <div className="md:col-span-2 bg-stone-900/60 border border-stone-800 rounded-2xl p-4">
            <div className="text-[10px] uppercase tracking-widest text-violet-400 font-bold mb-1 flex items-center gap-1">
              <Sparkles className="w-3 h-3" />Executive Summary
            </div>
            <p className="text-sm text-stone-200 leading-relaxed whitespace-pre-wrap">{data.summary || "—"}</p>
          </div>
        </div>
      )}

      {/* Recommendations table */}
      {recs.length > 0 && (
        <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-4" data-testid="ai-v2-recs">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-bold text-stone-100 flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-cyan-400" />Per-day suggestions
            </h3>
            <button onClick={apply} disabled={applying || !roomTypeId} data-testid="ai-v2-apply-btn"
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold disabled:opacity-50">
              {applying ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
              Apply Selected to Rate Calendar
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs" data-testid="ai-v2-table">
              <thead>
                <tr className="text-stone-400 border-b border-stone-800">
                  <th className="px-2 py-2 text-left w-10"></th>
                  <th className="px-2 py-2 text-left">Date</th>
                  <th className="px-2 py-2 text-right">Current</th>
                  <th className="px-2 py-2 text-right">Suggested</th>
                  <th className="px-2 py-2 text-right">Δ%</th>
                  <th className="px-2 py-2 text-center">Conf.</th>
                  <th className="px-2 py-2 text-left">Why</th>
                  <th className="px-2 py-2 text-right">Signals</th>
                </tr>
              </thead>
              <tbody>
                {recs.map((r) => {
                  const pct = Number(r.delta_pct || 0);
                  const sel = selected[r.date];
                  const confCls = CONF_COLOUR[r.confidence] || CONF_COLOUR.med;
                  const sig = r.signals || {};
                  return (
                    <tr key={r.date} className={`border-b border-stone-800/50 ${sel ? "bg-violet-500/5" : ""}`} data-testid={`ai-v2-row-${r.date}`}>
                      <td className="px-2 py-2">
                        <input type="checkbox" checked={!!sel}
                          onChange={() => setSelected(s => ({ ...s, [r.date]: !s[r.date] }))}
                          className="accent-violet-500"
                          data-testid={`ai-v2-check-${r.date}`} />
                      </td>
                      <td className="px-2 py-2 font-mono text-stone-200">
                        <div>{new Date(r.date).toLocaleDateString("en", { day: "2-digit", month: "short" })}</div>
                        <div className="text-[9px] text-stone-500 uppercase">{r.dow}</div>
                      </td>
                      <td className="px-2 py-2 text-right text-stone-300 tabular-nums">{cur(r.current_rate)}</td>
                      <td className="px-2 py-2 text-right font-black text-emerald-300 tabular-nums">{cur(r.suggested_rate)}</td>
                      <td className="px-2 py-2 text-right">
                        <span className={`inline-flex items-center gap-0.5 font-bold ${pct >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                          {pct >= 0 ? <ArrowUp className="w-3 h-3" /> : <ArrowDown className="w-3 h-3" />}
                          {pct >= 0 ? "+" : ""}{pct}%
                        </span>
                      </td>
                      <td className="px-2 py-2 text-center">
                        <span className={`text-[9px] font-black uppercase px-1.5 py-0.5 rounded border ${confCls}`}>
                          {r.confidence || "med"}
                        </span>
                      </td>
                      <td className="px-2 py-2 text-stone-400 max-w-[280px]">{r.reasoning}</td>
                      <td className="px-2 py-2 text-right text-[10px] text-stone-500 whitespace-nowrap">
                        occ {sig.occ_pct ?? "—"}% · stly {sig.stly_delta >= 0 ? "+" : ""}{sig.stly_delta ?? "—"}
                        {sig.comp_avg ? ` · comp £${sig.comp_avg}` : ""}
                        {sig.event ? ` · ${sig.event.name}` : ""}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {!loading && !data && (
        <div className="text-center py-16 text-stone-500" data-testid="ai-v2-empty">
          <Brain className="w-10 h-10 mx-auto mb-3 opacity-40" />
          <p className="text-sm">Click <strong>Generate Recommendations</strong> to let GPT-5.2 review pace + competitor signals.</p>
        </div>
      )}
    </div>
  );
}
