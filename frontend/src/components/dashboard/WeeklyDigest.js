import { useState, useEffect } from "react";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import { RefreshCw, Sparkles, BarChart3, Calendar, TrendingUp, AlertTriangle, CheckCircle, Target } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const WeeklyDigest = ({ propertyId }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  const pid = propertyId || "all";

  useEffect(() => {
    setLoading(true);
    axios.get(`${API}/revenue/weekly-digest/${pid}`)
      .then(r => { setData(r.data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [pid]);

  const generate = async () => {
    setGenerating(true);
    try {
      const { data: d } = await axios.post(`${API}/revenue/weekly-digest/${pid}/generate`);
      setData(d);
    } catch { /* silent */ }
    setGenerating(false);
  };

  if (loading) return <div className="flex items-center justify-center py-20 text-stone-400"><RefreshCw className="w-5 h-5 animate-spin mr-2" />Loading...</div>;

  const m = data?.metrics || {};
  const hasDigest = data?.digest_text;

  return (
    <div className="space-y-5" data-testid="weekly-digest">
      <div className="bg-gradient-to-r from-violet-900 via-indigo-900 to-blue-900 rounded-2xl p-5 text-white">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-white/10 rounded-xl flex items-center justify-center"><Sparkles className="w-5 h-5 text-amber-400" /></div>
            <div>
              <h2 className="text-lg font-bold" data-testid="digest-title">AI Weekly Revenue Digest</h2>
              <p className="text-xs text-white/40">{data?.week_start || ""} — {data?.week_end || ""}</p>
            </div>
          </div>
          <button onClick={generate} disabled={generating} data-testid="generate-digest-btn"
            className={`px-4 py-2 text-xs font-bold rounded-lg ${generating ? "bg-white/10 text-white/50" : "bg-amber-500 hover:bg-amber-400 text-white"}`}>
            {generating ? "Generating..." : hasDigest ? "Regenerate" : "Generate Digest"}
          </button>
        </div>

        {hasDigest && (
          <div className="grid grid-cols-5 gap-2 mb-4">
            <div className="bg-white/5 rounded-xl p-2.5 text-center"><p className="text-lg font-bold">{m.new_bookings}</p><p className="text-[7px] text-white/30 uppercase">Bookings</p></div>
            <div className="bg-white/5 rounded-xl p-2.5 text-center"><p className="text-lg font-bold">£{m.revenue}</p><p className="text-[7px] text-white/30 uppercase">Revenue</p></div>
            <div className="bg-white/5 rounded-xl p-2.5 text-center"><p className="text-lg font-bold">{m.avg_occupancy}%</p><p className="text-[7px] text-white/30 uppercase">Occupancy</p></div>
            <div className="bg-white/5 rounded-xl p-2.5 text-center"><p className="text-lg font-bold">£{m.adr}</p><p className="text-[7px] text-white/30 uppercase">ADR</p></div>
            <div className="bg-white/5 rounded-xl p-2.5 text-center"><p className="text-lg font-bold">{m.room_nights}</p><p className="text-[7px] text-white/30 uppercase">Room Nights</p></div>
          </div>
        )}
      </div>

      {hasDigest && (
        <div className="bg-white border border-stone-200 rounded-2xl p-6" data-testid="digest-content">
          <div className="prose prose-sm max-w-none text-stone-700 whitespace-pre-wrap leading-relaxed"
            dangerouslySetInnerHTML={{ __html: data.digest_text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br/>') }} />
          <p className="text-[10px] text-stone-400 mt-4 border-t border-stone-100 pt-3">Generated {new Date(data.generated_at).toLocaleString("en-GB")} by GPT-5.2</p>
        </div>
      )}

      {!hasDigest && !generating && (
        <div className="bg-white border border-stone-200 rounded-2xl p-12 text-center">
          <Sparkles className="w-10 h-10 text-stone-300 mx-auto mb-3" />
          <p className="text-sm font-bold text-stone-700">No digest generated yet</p>
          <p className="text-xs text-stone-400 mt-1">Click "Generate Digest" to create your AI-powered weekly revenue summary</p>
        </div>
      )}
    </div>
  );
};
