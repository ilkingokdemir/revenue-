import { useState, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { RefreshCw, Zap, TrendingUp, TrendingDown, BarChart3 } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;

export const RevenueForecasting = ({ propertyId }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    axios.get(`${API}/revenue/forecasting/${propertyId}?days=30`).then(r => { setData(r.data); setLoading(false); }).catch(() => { toast.error("Failed"); setLoading(false); });
  };
  useEffect(() => { load(); }, [propertyId]);

  if (loading || !data) return <div className="text-center py-20 text-stone-400">Loading forecast...</div>;
  const { kpis, forecast, accuracy } = data;

  const chartW = 880, chartH = 200, padL = 45, padR = 10, padT = 15, padB = 25;
  const innerW = chartW - padL - padR, innerH = chartH - padT - padB;
  const maxOcc = 100;
  const sx = (i) => padL + (i / Math.max(forecast.length - 1, 1)) * innerW;
  const sy = (v) => padT + (1 - v / maxOcc) * innerH;
  const forecastLine = forecast.map((e, i) => `${i === 0 ? "M" : "L"} ${sx(i)} ${sy(e.forecast_occ)}`).join(" ");
  const onBooksLine = forecast.map((e, i) => `${i === 0 ? "M" : "L"} ${sx(i)} ${sy(e.occupancy_on_books)}`).join(" ");
  const sdlyLine = forecast.map((e, i) => `${i === 0 ? "M" : "L"} ${sx(i)} ${sy(e.sdly_occ)}`).join(" ");

  return (
    <div className="space-y-6" data-testid="rev-forecasting">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-stone-800">Demand Forecasting</h2>
          <p className="text-sm text-stone-500">AI-powered occupancy and revenue predictions for the next 90 days.</p>
        </div>
        <div className="flex items-center gap-3">
          <Badge className="bg-violet-100 text-violet-700 text-xs">Accuracy: {accuracy}%</Badge>
          <button onClick={load} className="flex items-center gap-2 bg-violet-600 hover:bg-violet-700 text-white px-4 py-2 rounded-xl text-sm font-medium" data-testid="rev-forecast-recalc">
            <RefreshCw className="w-4 h-4" />Recalculate
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4" data-testid="rev-forecast-kpis">
        {[
          { label: "Avg Forecast Occupancy", value: `${kpis.avg_forecast_occ}%`, sub: "Next 30 days" },
          { label: "Avg Forecast ADR", value: cur(kpis.avg_forecast_adr), sub: "Predicted rate" },
          { label: "Forecast RevPAR", value: cur(kpis.forecast_revpar), sub: "Revenue per available room" },
          { label: "Total Rooms on Books", value: kpis.total_on_books, sub: "Current reservations", color: "text-emerald-600" },
        ].map(k => (
          <div key={k.label} className="bg-white border border-stone-200 rounded-2xl p-5">
            <p className="text-xs text-stone-400 font-medium">{k.label}</p>
            <p className={`text-2xl font-bold mt-1 ${k.color || "text-stone-800"}`}>{k.value}</p>
            <p className="text-[10px] text-stone-400 mt-1">{k.sub}</p>
          </div>
        ))}
      </div>

      <div className="bg-white border border-stone-200 rounded-2xl p-5" data-testid="rev-forecast-chart">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-bold text-stone-800">30-Day Occupancy Forecast</h3>
          <div className="flex items-center gap-4 text-xs text-stone-400">
            <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-violet-600 inline-block" />Forecast</span>
            <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-emerald-500 inline-block" />On Books</span>
            <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-stone-300 inline-block" />SDLY</span>
          </div>
        </div>
        <div className="overflow-x-auto">
          <svg viewBox={`0 0 ${chartW} ${chartH}`} className="w-full" style={{ minWidth: "600px" }}>
            {[0, 25, 50, 75, 100].map(v => (
              <g key={v}><line x1={padL} x2={chartW - padR} y1={sy(v)} y2={sy(v)} stroke="#f3f4f6" strokeWidth="1" />
                <text x={padL - 6} y={sy(v) + 4} textAnchor="end" fill="#9ca3af" fontSize="9">{v}%</text></g>
            ))}
            <path d={sdlyLine} fill="none" stroke="#d1d5db" strokeWidth="1.5" strokeDasharray="4 4" />
            <path d={onBooksLine} fill="none" stroke="#22c55e" strokeWidth="2" />
            <path d={forecastLine} fill="none" stroke="#7c3aed" strokeWidth="2.5" />
            {forecast.map((e, i) => i % 3 === 0 && (
              <text key={i} x={sx(i)} y={chartH - 4} textAnchor="middle" fill="#9ca3af" fontSize="8">
                {new Date(e.date + "T00:00:00").toLocaleDateString("en", { month: "short", day: "numeric" })}
              </text>
            ))}
          </svg>
        </div>
      </div>

      <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden" data-testid="rev-forecast-table">
        <div className="px-5 py-3 bg-stone-50 border-b font-bold text-stone-800 text-sm">Forecast vs SDLY Comparison</div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="border-b bg-stone-50/50">
              {["Date","Days Out","Forecast Occ","On Books","Remaining","SDLY Occ","vs SDLY","Confidence"].map(h =>
                <th key={h} className="px-3 py-2 text-xs font-semibold text-stone-500 text-center whitespace-nowrap">{h}</th>
              )}
            </tr></thead>
            <tbody>{forecast.slice(0, 14).map(r => (
              <tr key={r.date} className={`border-b border-stone-50 ${r.is_today ? "bg-violet-50/50" : ""}`}>
                <td className="px-3 py-2 font-medium text-stone-700 whitespace-nowrap">{r.dow}, {new Date(r.date + "T00:00:00").toLocaleDateString("en", { month: "short", day: "numeric" })}</td>
                <td className="px-3 py-2 text-center text-stone-500">{r.is_today ? "Today" : `${r.days_out}d`}</td>
                <td className="px-3 py-2 text-center font-semibold text-violet-700">{r.forecast_occ}%</td>
                <td className="px-3 py-2 text-center text-emerald-600 font-semibold">{r.on_books}</td>
                <td className="px-3 py-2 text-center text-stone-500">{r.remaining}</td>
                <td className="px-3 py-2 text-center text-stone-400">{r.sdly_occ}%</td>
                <td className="px-3 py-2 text-center">
                  <span className={`font-semibold ${r.vs_sdly > 0 ? "text-emerald-600" : r.vs_sdly < 0 ? "text-red-500" : "text-stone-400"}`}>
                    {r.vs_sdly > 0 ? "+" : ""}{r.vs_sdly}%
                  </span>
                </td>
                <td className="px-3 py-2 text-center"><Badge className={`text-[10px] ${r.confidence > 70 ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>{r.confidence}%</Badge></td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
