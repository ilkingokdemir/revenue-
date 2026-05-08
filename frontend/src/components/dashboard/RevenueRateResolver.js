import { useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Search, ArrowRight, Layers } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export const RevenueRateResolver = ({ propertyId, roomTypes }) => {
  const [date, setDate] = useState(new Date().toISOString().split("T")[0]);
  const [roomCategory, setRoomCategory] = useState("");
  const [ratePlan, setRatePlan] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const resolve = async () => {
    setLoading(true);
    try {
      const { data } = await axios.post(`${API}/revenue/rate-resolver`, {
        property_id: propertyId, date, room_category: roomCategory, rate_plan: ratePlan
      });
      setResult(data);
    } catch { toast.error("Failed to resolve rate"); }
    setLoading(false);
  };

  return (
    <div className="space-y-6" data-testid="rev-rate-resolver">
      <div>
        <h2 className="text-lg font-bold text-stone-800">Rate Resolver (SSOT)</h2>
        <p className="text-sm text-stone-500">View resolved rates with precedence breakdown</p>
      </div>

      {/* Filters */}
      <div className="bg-white border border-stone-200 rounded-2xl p-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          <div>
            <label className="text-sm font-semibold text-stone-700 block mb-2">Date</label>
            <Input type="date" value={date} onChange={e => setDate(e.target.value)} className="h-10" data-testid="rev-resolver-date" />
          </div>
          <div>
            <label className="text-sm font-semibold text-stone-700 block mb-2">Room Category</label>
            <Select value={roomCategory} onValueChange={setRoomCategory}>
              <SelectTrigger className="h-10" data-testid="rev-resolver-room"><SelectValue placeholder="Select category" /></SelectTrigger>
              <SelectContent>
                {(roomTypes || []).map(r => <SelectItem key={r.id} value={r.id}>{r.name}</SelectItem>)}
                {(!roomTypes || roomTypes.length === 0) && <SelectItem value="default">Standard</SelectItem>}
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="text-sm font-semibold text-stone-700 block mb-2">Rate Plan</label>
            <Select value={ratePlan} onValueChange={setRatePlan}>
              <SelectTrigger className="h-10"><SelectValue placeholder="Select rate plan" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="base">Base Rate</SelectItem>
                <SelectItem value="rack">Rack Rate</SelectItem>
                <SelectItem value="promo">Promotional</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <button onClick={resolve} disabled={loading}
          className="flex items-center gap-2 bg-emerald-500 hover:bg-emerald-600 text-white px-5 py-2.5 rounded-xl text-sm font-semibold disabled:opacity-50" data-testid="rev-resolve-btn">
          <Search className="w-4 h-4" />{loading ? "Resolving..." : "Resolve Rate"}
        </button>
      </div>

      {/* Result */}
      {result && (
        <div className="bg-white border border-stone-200 rounded-2xl p-6" data-testid="rev-resolver-result">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h3 className="font-bold text-stone-800">Resolved Rate</h3>
              <p className="text-xs text-stone-400 mt-0.5">{result.room_type} — {result.date}</p>
            </div>
            <div className="text-right">
              <p className="text-3xl font-bold text-violet-700">{cur(result.resolved_rate)}</p>
              <p className="text-xs text-stone-400">Guardrails: {cur(result.guardrails.min)} – {cur(result.guardrails.max)}</p>
            </div>
          </div>

          {/* Precedence Breakdown */}
          <h4 className="font-semibold text-stone-700 text-sm mb-3 flex items-center gap-2">
            <Layers className="w-4 h-4 text-violet-500" /> Precedence Breakdown
          </h4>
          <div className="space-y-2">
            {result.layers.map((layer, i) => (
              <div key={i} className="flex items-center gap-3">
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold ${
                  i === 0 ? "bg-stone-100 text-stone-500" : i === result.layers.length - 1 ? "bg-violet-100 text-violet-700" : "bg-blue-50 text-blue-600"
                }`}>{i + 1}</div>
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-stone-700">{layer.name}</span>
                    <span className="text-sm font-bold text-stone-800">{cur(layer.value)}</span>
                  </div>
                  <span className="text-xs text-stone-400">{layer.adjustment}</span>
                </div>
                {i < result.layers.length - 1 && <ArrowRight className="w-4 h-4 text-stone-300" />}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
