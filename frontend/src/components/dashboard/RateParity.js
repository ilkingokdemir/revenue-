import { useState, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Shield, RefreshCw, CheckCircle, AlertTriangle, XCircle, ArrowUpRight, ArrowDownRight, Minus, Search } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;

const STATUS_STYLES = {
  parity: { bg: "bg-emerald-50", border: "border-emerald-200", text: "text-emerald-700", icon: CheckCircle, label: "In Parity" },
  minor: { bg: "bg-amber-50", border: "border-amber-200", text: "text-amber-700", icon: AlertTriangle, label: "Minor" },
  violation: { bg: "bg-red-50", border: "border-red-200", text: "text-red-600", icon: XCircle, label: "Violation" },
};

const CHANNEL_COLORS = {
  booking: { bg: "bg-[#003580]", text: "text-white" },
  expedia: { bg: "bg-[#FFCC00]", text: "text-stone-800" },
  hotels_com: { bg: "bg-[#D32F2F]", text: "text-white" },
  agoda: { bg: "bg-[#5C2D91]", text: "text-white" },
  google: { bg: "bg-[#4285F4]", text: "text-white" },
  direct: { bg: "bg-emerald-600", text: "text-white" },
};

export const RateParity = ({ propertyId, hotelName = "" }) => {
  const shortName = hotelName && hotelName.length > 20
    ? (hotelName.split(" ")[0] || "Us")
    : (hotelName || "Us");
  const [data, setData] = useState(null);
  const [scanning, setScanning] = useState(false);

  const load = () => {
    axios.get(`${API}/revenue/market-robot/${propertyId}/parity`).then(r => setData(r.data)).catch(() => {});
  };
  useEffect(() => { load(); }, [propertyId]);

  const scan = async () => {
    setScanning(true);
    try {
      const { data: r } = await axios.post(`${API}/revenue/market-robot/${propertyId}/parity/scan`, { days: 14 });
      toast.success(r.message);
      load();
    } catch { toast.error("Parity scan failed"); }
    setScanning(false);
  };

  const channels = data?.channels || [];
  const parity = data?.parity_data || [];
  const s = data?.summary || {};

  return (
    <div className="space-y-6" data-testid="rate-parity">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-xl flex items-center justify-center">
            <Shield className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="font-bold text-stone-800">Rate Parity Monitor</h3>
            <p className="text-xs text-stone-400">Compare your rates across all OTA channels</p>
          </div>
        </div>
        <button onClick={scan} disabled={scanning}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-5 py-2.5 rounded-xl text-sm font-semibold disabled:opacity-50" data-testid="parity-scan">
          {scanning ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
          {scanning ? "Scanning OTAs..." : "Scan All Channels"}
        </button>
      </div>

      {/* Parity Score */}
      {parity.length > 0 && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4" data-testid="parity-kpis">
            <div className={`rounded-2xl p-5 text-center border ${s.parity_score >= 90 ? "bg-emerald-50 border-emerald-200" : s.parity_score >= 70 ? "bg-amber-50 border-amber-200" : "bg-red-50 border-red-200"}`}>
              <p className="text-[10px] text-stone-500 uppercase tracking-wider font-medium">Parity Score</p>
              <p className={`text-3xl font-bold mt-1 ${s.parity_score >= 90 ? "text-emerald-600" : s.parity_score >= 70 ? "text-amber-600" : "text-red-600"}`}>{s.parity_score}%</p>
            </div>
            <div className="bg-emerald-50 border border-emerald-100 rounded-2xl p-5 text-center">
              <p className="text-[10px] text-emerald-600 uppercase tracking-wider font-medium">In Parity</p>
              <p className="text-2xl font-bold text-emerald-600 mt-1">{s.in_parity}</p>
            </div>
            <div className="bg-amber-50 border border-amber-100 rounded-2xl p-5 text-center">
              <p className="text-[10px] text-amber-600 uppercase tracking-wider font-medium">Minor Issues</p>
              <p className="text-2xl font-bold text-amber-600 mt-1">{s.minor_issues}</p>
            </div>
            <div className="bg-red-50 border border-red-100 rounded-2xl p-5 text-center">
              <p className="text-[10px] text-red-500 uppercase tracking-wider font-medium">Violations</p>
              <p className="text-2xl font-bold text-red-500 mt-1">{s.violations}</p>
            </div>
            <div className="bg-white border border-stone-200 rounded-2xl p-5 text-center">
              <p className="text-[10px] text-stone-400 uppercase tracking-wider font-medium">Dates Checked</p>
              <p className="text-2xl font-bold text-stone-700 mt-1">{s.total_dates}</p>
            </div>
          </div>

          {/* Channel Legend */}
          <div className="flex items-center gap-2 flex-wrap">
            {channels.map(ch => (
              <span key={ch.id} className={`text-[10px] font-bold px-2.5 py-1 rounded-lg ${CHANNEL_COLORS[ch.id]?.bg || "bg-stone-200"} ${CHANNEL_COLORS[ch.id]?.text || "text-stone-600"}`}>
                {ch.name}
              </span>
            ))}
          </div>

          {/* Parity Grid */}
          <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden" data-testid="parity-grid">
            <div className="px-5 py-3 bg-stone-50 border-b flex items-center justify-between">
              <span className="font-bold text-stone-800 text-sm">Rate Parity by Date & Channel</span>
              <div className="flex items-center gap-3 text-[10px]">
                <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-emerald-100 border border-emerald-200" />In Parity</span>
                <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-amber-100 border border-amber-200" />Minor (1-5%)</span>
                <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-red-100 border border-red-200" />Violation (5%+)</span>
              </div>
            </div>
            <div className="overflow-x-auto max-h-[500px] overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-white z-10">
                  <tr className="border-b">
                    <th className="px-3 py-2 text-xs font-semibold text-stone-500 text-left sticky left-0 bg-white">Date</th>
                    <th className="px-3 py-2 text-xs font-semibold text-stone-500 text-center">{shortName} Rate</th>
                    {channels.filter(c => c.id !== "direct").map(ch => (
                      <th key={ch.id} className="px-3 py-2 text-center">
                        <span className={`text-[9px] font-bold px-2 py-0.5 rounded ${CHANNEL_COLORS[ch.id]?.bg || "bg-stone-200"} ${CHANNEL_COLORS[ch.id]?.text || ""}`}>{ch.name}</span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {parity.map(p => (
                    <tr key={p.date} className="border-b border-stone-50">
                      <td className="px-3 py-2 font-medium text-stone-700 text-xs whitespace-nowrap sticky left-0 bg-white">
                        {new Date(p.date + "T00:00:00").toLocaleDateString("en", { weekday: "short", month: "short", day: "numeric" })}
                      </td>
                      <td className="px-3 py-2 text-center font-bold text-stone-800">{cur(p.our_price)}</td>
                      {channels.filter(c => c.id !== "direct").map(ch => {
                        const cd = p.channels?.[ch.id];
                        if (!cd) return <td key={ch.id} className="px-3 py-2 text-center text-stone-300">—</td>;
                        const st = STATUS_STYLES[cd.status] || STATUS_STYLES.parity;
                        const Icon = st.icon;
                        return (
                          <td key={ch.id} className={`px-3 py-2 text-center ${st.bg}`}>
                            <div className="font-bold text-stone-800 text-sm">{cur(cd.price)}</div>
                            <div className={`flex items-center justify-center gap-0.5 text-[10px] font-semibold mt-0.5 ${st.text}`}>
                              <Icon className="w-3 h-3" />
                              {cd.diff_pct > 0 ? "+" : ""}{cd.diff_pct}%
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
        </>
      )}

      {parity.length === 0 && !scanning && (
        <div className="bg-white border border-stone-200 rounded-2xl p-12 text-center">
          <Shield className="w-14 h-14 text-stone-200 mx-auto mb-3" />
          <h3 className="font-bold text-stone-600 text-lg mb-1">No Parity Data Yet</h3>
          <p className="text-sm text-stone-400 mb-4">Click "Scan All Channels" to check your hotel's rate consistency across Booking.com, Expedia, Hotels.com, Agoda, and Google Hotels.</p>
          <button onClick={scan} className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2.5 rounded-xl text-sm font-semibold" data-testid="parity-scan-empty">
            Start Parity Check
          </button>
        </div>
      )}
    </div>
  );
};
