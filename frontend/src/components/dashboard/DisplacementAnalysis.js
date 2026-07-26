import { useState } from "react";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import {
  Users, TrendingUp, TrendingDown, AlertTriangle, CheckCircle, XCircle, Minus,
  Calculator, BarChart3, Calendar, DollarSign
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;

const REC_COLORS = {
  ACCEPT: { bg: "bg-emerald-500", text: "text-emerald-400", icon: CheckCircle, border: "border-emerald-500/30" },
  REJECT: { bg: "bg-red-500", text: "text-red-400", icon: XCircle, border: "border-red-500/30" },
  NEUTRAL: { bg: "bg-amber-500", text: "text-amber-400", icon: Minus, border: "border-amber-500/30" },
};

export const DisplacementAnalysis = ({ propertyId }) => {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({
    group_name: "", check_in: "", check_out: "", rooms_requested: 5, group_rate: 80,
  });

  const analyze = async () => {
    if (!form.check_in || !form.check_out) { toast.error("Enter check-in and check-out dates"); return; }
    setLoading(true);
    try {
      const { data } = await axios.post(`${API}/revenue/displacement/analyze`, { ...form, property_id: propertyId || "all" });
      setResult(data);
    } catch { toast.error("Analysis failed"); }
    setLoading(false);
  };

  const saveDecision = async (decision) => {
    if (!result) return;
    try {
      await axios.post(`${API}/revenue/displacement/save`, {
        group_name: result.group_name, recommendation: result.recommendation,
        decision, group_revenue: result.group.total_revenue, displacement_cost: result.displacement_cost,
      });
      toast.success(`Decision saved: ${decision}`);
    } catch { /* silent */ }
  };

  const rc = result ? REC_COLORS[result.recommendation] || REC_COLORS.NEUTRAL : null;
  const RecIcon = rc?.icon || Minus;

  return (
    <div className="space-y-5" data-testid="displacement-analysis">
      {/* Input Form */}
      <div className="bg-stone-900 rounded-2xl p-5 text-white">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 bg-white/10 rounded-xl flex items-center justify-center"><Calculator className="w-5 h-5 text-violet-400" /></div>
          <div>
            <h2 className="text-lg font-bold" data-testid="displacement-title">Displacement Analysis</h2>
            <p className="text-xs text-white/40">Should you accept this group booking or hold for individuals?</p>
          </div>
        </div>

        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
          <div>
            <label className="text-[9px] text-white/30 uppercase block mb-1">Group Name</label>
            <input value={form.group_name} onChange={e => setForm({...form, group_name: e.target.value})} placeholder="Tech Conference"
              className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white" />
          </div>
          <div>
            <label className="text-[9px] text-white/30 uppercase block mb-1">Check-In</label>
            <input type="date" value={form.check_in} onChange={e => setForm({...form, check_in: e.target.value})}
              className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white" />
          </div>
          <div>
            <label className="text-[9px] text-white/30 uppercase block mb-1">Check-Out</label>
            <input type="date" value={form.check_out} onChange={e => setForm({...form, check_out: e.target.value})}
              className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white" />
          </div>
          <div>
            <label className="text-[9px] text-white/30 uppercase block mb-1">Rooms</label>
            <input type="number" value={form.rooms_requested} onChange={e => setForm({...form, rooms_requested: parseInt(e.target.value) || 1})}
              className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white" />
          </div>
          <div>
            <label className="text-[9px] text-white/30 uppercase block mb-1">Group Rate/Night</label>
            <input type="number" value={form.group_rate} onChange={e => setForm({...form, group_rate: parseFloat(e.target.value) || 0})}
              className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white" />
          </div>
        </div>

        <button onClick={analyze} disabled={loading} data-testid="analyze-btn"
          className="mt-4 px-6 py-2.5 bg-violet-500 hover:bg-violet-400 text-white text-sm font-bold rounded-lg disabled:opacity-50">
          {loading ? "Analyzing..." : "Run Displacement Analysis"}
        </button>
      </div>

      {/* Results */}
      {result && (
        <>
          {/* Recommendation */}
          <div className={`bg-stone-900 border ${rc.border} rounded-2xl p-5`} data-testid="displacement-result">
            <div className="flex items-center gap-4 mb-4">
              <div className={`w-14 h-14 ${rc.bg} rounded-2xl flex items-center justify-center`}>
                <RecIcon className="w-7 h-7 text-white" />
              </div>
              <div>
                <Badge className={`${rc.bg} text-white text-sm px-3 py-1`}>{result.recommendation}</Badge>
                <p className="text-white text-sm mt-1">{result.reason}</p>
                <p className="text-stone-500 text-[10px]">Confidence: {result.confidence}%</p>
              </div>
            </div>

            {/* Comparison */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-white/5 rounded-xl p-4">
                <p className="text-[9px] text-white/30 uppercase font-bold mb-2">Group Booking</p>
                <p className="text-2xl font-black text-white">{cur(result.group.total_revenue)}</p>
                <p className="text-xs text-stone-400">{result.group.rooms} rooms x {result.group.nights} nights @ {cur(result.group.rate)}/night</p>
              </div>
              <div className="bg-white/5 rounded-xl p-4">
                <p className="text-[9px] text-white/30 uppercase font-bold mb-2">Expected Individual Revenue</p>
                <p className="text-2xl font-black text-white">{cur(result.individual.total_revenue)}</p>
                <p className="text-xs text-stone-400">~{result.individual.expected_fill_rooms} rooms @ {cur(result.individual.avg_rate)}/night ({result.individual.fill_probability}% fill)</p>
              </div>
            </div>

            {/* Net Impact */}
            <div className="bg-white/5 rounded-xl p-4 mt-3 text-center">
              <p className="text-[9px] text-white/30 uppercase">Net Displacement Cost</p>
              <p className={`text-3xl font-black ${result.displacement_cost > 0 ? "text-red-400" : "text-emerald-400"}`}>
                {result.displacement_cost > 0 ? "+" : ""}{cur(result.displacement_cost)}
              </p>
              <p className="text-xs text-stone-500">{result.displacement_cost > 0 ? "Lost revenue if you accept the group" : "Extra revenue from accepting the group"}</p>
            </div>

            {/* Blended-Rate Önerisi (FLYR Groups parity) */}
            {result.blended && (
              <div className="bg-indigo-500/10 border border-indigo-500/30 rounded-xl p-4 mt-3" data-testid="blended-rate-card">
                <p className="text-[9px] text-indigo-300 uppercase font-bold mb-2">💡 Blended-Rate Önerisi</p>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div>
                    <p className="text-[9px] text-white/30 uppercase">Önerilen min. grup fiyatı</p>
                    <p className="text-xl font-black text-indigo-300" data-testid="blended-recommended-rate">{cur(result.blended.recommended_rate)}<span className="text-xs font-normal text-stone-500">/gece</span></p>
                  </div>
                  <div>
                    <p className="text-[9px] text-white/30 uppercase">Başabaş (breakeven)</p>
                    <p className="text-lg font-bold text-white">{cur(result.blended.breakeven_rate)}</p>
                    {result.blended.lrv_floor > 0 && <p className="text-[9px] text-stone-500">LRV taban: {cur(result.blended.lrv_floor)}</p>}
                  </div>
                  <div>
                    <p className="text-[9px] text-white/30 uppercase">Doluluk etkisi</p>
                    <p className="text-lg font-bold text-white">%{result.blended.occ_before_pct} → <span className="text-emerald-400">%{result.blended.occ_after_pct}</span></p>
                    <p className="text-[9px] text-stone-500">Blended ADR: {cur(result.blended.blended_adr_after)}</p>
                  </div>
                  <div>
                    <p className="text-[9px] text-white/30 uppercase">Talep edilen fiyat</p>
                    <p className={`text-lg font-bold ${result.blended.rate_verdict === "above" ? "text-emerald-400" : result.blended.rate_verdict === "near" ? "text-amber-400" : "text-red-400"}`} data-testid="blended-verdict">
                      {cur(result.blended.requested_rate)} {result.blended.rate_verdict === "above" ? "✓ uygun" : result.blended.rate_verdict === "near" ? "≈ sınırda" : "✕ düşük"}
                    </p>
                    {result.blended.uplift_if_recommended > 0 && (
                      <p className="text-[9px] text-amber-300">Önerilen fiyatla +{cur(result.blended.uplift_if_recommended)} kazanç</p>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Decision Buttons */}
            <div className="flex gap-3 mt-4">
              <button onClick={() => saveDecision("accepted")} data-testid="decision-accept"
                className="flex-1 py-2.5 text-sm font-bold text-white bg-emerald-500 hover:bg-emerald-600 rounded-lg">Accept Group</button>
              <button onClick={() => saveDecision("rejected")} data-testid="decision-reject"
                className="flex-1 py-2.5 text-sm font-bold text-white bg-red-500 hover:bg-red-600 rounded-lg">Reject Group</button>
              <button onClick={() => saveDecision("negotiating")} data-testid="decision-negotiate"
                className="flex-1 py-2.5 text-sm font-bold text-white bg-amber-500 hover:bg-amber-600 rounded-lg">Negotiate Rate</button>
            </div>
          </div>

          {/* Risks */}
          {result.risks?.length > 0 && (
            <div className="space-y-2" data-testid="risk-factors">
              <h3 className="text-sm font-bold text-stone-800">Risk Factors</h3>
              {result.risks.map((r, i) => (
                <div key={i} className={`bg-stone-900 border rounded-xl p-3 ${r.impact === "negative" ? "border-red-500/30" : r.impact === "positive" ? "border-emerald-500/30" : "border-amber-500/30"}`}>
                  <div className="flex items-center gap-2">
                    <AlertTriangle className={`w-3.5 h-3.5 ${r.impact === "negative" ? "text-red-400" : r.impact === "positive" ? "text-emerald-400" : "text-amber-400"}`} />
                    <span className="text-xs text-white">{r.text}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
};
