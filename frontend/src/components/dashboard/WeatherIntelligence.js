import { useState, useEffect } from "react";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import { RefreshCw, Sun, Cloud, CloudRain, Snowflake, CloudLightning, CloudDrizzle, CloudFog, Thermometer, Wind, Droplets, TrendingUp, Zap, Calendar } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;

const WEATHER_ICONS = {
  sun: Sun, "cloud-sun": Cloud, cloud: Cloud, "cloud-fog": CloudFog,
  "cloud-drizzle": CloudDrizzle, "cloud-rain": CloudRain, "cloud-rain-heavy": CloudRain,
  snowflake: Snowflake, "cloud-lightning": CloudLightning,
};

const scoreColor = (s) => s >= 70 ? "text-emerald-400" : s >= 40 ? "text-amber-400" : "text-red-400";
const scoreBg = (s) => s >= 70 ? "bg-emerald-500" : s >= 40 ? "bg-amber-500" : "bg-red-500";
const impactColor = (i) => i === "high" ? "bg-red-500/20 text-red-400 border-red-500/30" : "bg-amber-500/20 text-amber-400 border-amber-500/30";

export const WeatherIntelligence = ({ propertyId }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    axios.get(`${API}/revenue/weather/${propertyId}?days=14`)
      .then(r => { setData(r.data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [propertyId]);

  if (loading) return <div className="flex items-center justify-center py-20 text-stone-400"><RefreshCw className="w-5 h-5 animate-spin mr-2" />Loading Weather Intelligence...</div>;
  if (!data || !data.daily?.length) return <div className="text-center py-20 text-stone-400">No weather data available</div>;

  const { city, summary, opportunities, daily } = data;

  // Chart dimensions
  const cW = 1100, cH = 200, pL = 40, pR = 10, pT = 20, pB = 40;
  const iW = cW - pL - pR, iH = cH - pT - pB;
  const maxT = Math.max(...daily.map(d => d.temp_max)) + 3;
  const minT = Math.min(...daily.map(d => d.temp_min)) - 3;
  const sx = (i) => pL + (i / Math.max(daily.length - 1, 1)) * iW;
  const sy = (v) => pT + (1 - (v - minT) / (maxT - minT)) * iH;
  const maxLine = daily.map((d, i) => `${i === 0 ? "M" : "L"} ${sx(i)} ${sy(d.temp_max)}`).join(" ");
  const minLine = daily.map((d, i) => `${i === 0 ? "M" : "L"} ${sx(i)} ${sy(d.temp_min)}`).join(" ");

  return (
    <div className="space-y-5" data-testid="weather-intelligence">
      {/* Header */}
      <div className="bg-gradient-to-r from-sky-900 via-blue-900 to-indigo-900 rounded-2xl p-5 text-white">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-white/10 rounded-xl flex items-center justify-center"><Sun className="w-5 h-5 text-amber-400" /></div>
            <div>
              <h2 className="text-lg font-bold" data-testid="weather-title">Weather Intelligence</h2>
              <p className="text-xs text-white/40">{city} — {data.days}-day forecast with pricing insights</p>
            </div>
          </div>
        </div>

        {/* Summary KPIs */}
        <div className="grid grid-cols-5 gap-3">
          <div className="bg-white/5 rounded-xl p-3 text-center">
            <Thermometer className="w-4 h-4 mx-auto mb-1 text-amber-400" />
            <p className="text-xl font-bold">{summary.avg_temp}°C</p>
            <p className="text-[8px] text-white/30 uppercase">Avg Temp</p>
          </div>
          <div className="bg-white/5 rounded-xl p-3 text-center">
            <Sun className="w-4 h-4 mx-auto mb-1 text-amber-400" />
            <p className="text-xl font-bold text-emerald-400">{summary.sunny_days}</p>
            <p className="text-[8px] text-white/30 uppercase">Sunny Days</p>
          </div>
          <div className="bg-white/5 rounded-xl p-3 text-center">
            <CloudRain className="w-4 h-4 mx-auto mb-1 text-blue-400" />
            <p className="text-xl font-bold text-blue-400">{summary.rainy_days}</p>
            <p className="text-[8px] text-white/30 uppercase">Rainy Days</p>
          </div>
          <div className="bg-white/5 rounded-xl p-3 text-center">
            <TrendingUp className="w-4 h-4 mx-auto mb-1 text-emerald-400" />
            <p className="text-lg font-bold text-emerald-400">{summary.best_day?.date ? new Date(summary.best_day.date + "T00:00:00").toLocaleDateString("en", { day: "numeric", month: "short" }) : "—"}</p>
            <p className="text-[8px] text-white/30 uppercase">Best Day ({summary.best_day?.score})</p>
          </div>
          <div className="bg-white/5 rounded-xl p-3 text-center">
            <Zap className="w-4 h-4 mx-auto mb-1 text-red-400" />
            <p className="text-xl font-bold text-amber-400">{opportunities.length}</p>
            <p className="text-[8px] text-white/30 uppercase">Opportunities</p>
          </div>
        </div>
      </div>

      {/* Pricing Opportunities */}
      {opportunities.length > 0 && (
        <div className="space-y-3" data-testid="weather-opportunities">
          <h3 className="text-sm font-bold text-stone-800">Pricing Opportunities</h3>
          {opportunities.map((opp, i) => (
            <div key={i} className={`bg-stone-900 border rounded-xl p-4 ${impactColor(opp.impact)}`}>
              <div className="flex items-center gap-2 mb-1">
                <Badge className={`text-[9px] ${opp.impact === "high" ? "bg-red-500 text-white" : "bg-amber-500 text-white"}`}>{opp.impact}</Badge>
                <span className="text-xs text-stone-400">{new Date(opp.date + "T00:00:00").toLocaleDateString("en", { weekday: "short", day: "numeric", month: "short" })}</span>
                <span className={`text-xs font-bold ${scoreColor(opp.weather_score)}`}>Score: {opp.weather_score}</span>
              </div>
              <p className="text-sm font-bold text-white">{opp.title}</p>
              <p className="text-xs text-stone-400 mt-1">{opp.suggestion}</p>
            </div>
          ))}
        </div>
      )}

      {/* Temperature Chart */}
      <div className="bg-stone-900 border border-stone-700 rounded-2xl p-5" data-testid="temp-chart">
        <div className="flex items-center justify-between mb-2">
          <div>
            <p className="text-[10px] text-stone-500 uppercase">{data.days}-Day Forecast</p>
            <h3 className="text-sm font-bold text-white">Temperature Range</h3>
          </div>
          <div className="flex items-center gap-3 text-[10px] text-stone-400">
            <span className="flex items-center gap-1"><span className="w-4 h-0.5 bg-red-400 inline-block" /> Max</span>
            <span className="flex items-center gap-1"><span className="w-4 h-0.5 bg-blue-400 inline-block" /> Min</span>
          </div>
        </div>
        <div className="overflow-x-auto">
          <svg viewBox={`0 0 ${cW} ${cH}`} className="w-full" style={{ minWidth: "600px" }}>
            {/* Grid */}
            {[0, 0.25, 0.5, 0.75, 1].map(f => {
              const v = Math.round(minT + f * (maxT - minT));
              const y = sy(v);
              return <g key={f}><line x1={pL} x2={cW - pR} y1={y} y2={y} stroke="#374151" strokeWidth="0.5" /><text x={pL - 5} y={y + 4} textAnchor="end" className="text-[7px]" fill="#6b7280">{v}°</text></g>;
            })}
            {/* Fill area between max and min */}
            <path d={`${maxLine} ${daily.map((d, i) => `L ${sx(daily.length - 1 - i)} ${sy(daily[daily.length - 1 - i].temp_min)}`).join(" ")} Z`} fill="url(#tempGrad)" opacity="0.2" />
            <defs><linearGradient id="tempGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#ef4444" /><stop offset="100%" stopColor="#3b82f6" /></linearGradient></defs>
            {/* Lines */}
            <path d={maxLine} fill="none" stroke="#ef4444" strokeWidth="2" />
            <path d={minLine} fill="none" stroke="#3b82f6" strokeWidth="2" />
            {/* Date labels */}
            {daily.map((d, i) => (
              <text key={i} x={sx(i)} y={cH - 8} textAnchor="middle" className="text-[7px]" fill="#6b7280">{d.dow} {d.day}</text>
            ))}
            {/* Weather icons as dots with score color */}
            {daily.map((d, i) => (
              <circle key={`dot-${i}`} cx={sx(i)} cy={sy(d.temp_max)} r="3" fill={d.weather_score >= 70 ? "#22c55e" : d.weather_score >= 40 ? "#f59e0b" : "#ef4444"} />
            ))}
          </svg>
        </div>
      </div>

      {/* Daily Forecast Table */}
      <div className="bg-stone-900 border border-stone-700 rounded-2xl p-5" data-testid="weather-daily">
        <h3 className="text-sm font-bold text-white mb-3">Daily Forecast & Demand Correlation</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-stone-500 border-b border-stone-700">
                <th className="text-left py-2 px-2 font-medium">Date</th>
                <th className="text-left py-2 px-1 font-medium">Weather</th>
                <th className="text-right py-2 px-2 font-medium">Max°C</th>
                <th className="text-right py-2 px-2 font-medium">Min°C</th>
                <th className="text-right py-2 px-2 font-medium">Rain%</th>
                <th className="text-right py-2 px-2 font-medium">Wind</th>
                <th className="text-right py-2 px-2 font-medium">UV</th>
                <th className="text-right py-2 px-2 font-medium">Sun hrs</th>
                <th className="text-center py-2 px-2 font-medium">Score</th>
                <th className="text-right py-2 px-2 font-medium">Demand</th>
                <th className="text-right py-2 px-2 font-medium">Rate</th>
                <th className="text-left py-2 px-2 font-medium">Event</th>
              </tr>
            </thead>
            <tbody>
              {daily.map(d => {
                const Icon = WEATHER_ICONS[d.icon] || Cloud;
                return (
                  <tr key={d.date} className={`border-b border-stone-800/50 hover:bg-stone-800/30 ${d.is_weekend ? "bg-stone-800/20" : ""}`}>
                    <td className="py-1.5 px-2 font-medium text-white">{new Date(d.date + "T00:00:00").toLocaleDateString("en", { day: "numeric", month: "short" })}</td>
                    <td className="py-1.5 px-1"><span className="flex items-center gap-1"><Icon className="w-3.5 h-3.5 text-stone-400" /><span className="text-stone-300 truncate max-w-[100px]">{d.description}</span></span></td>
                    <td className="py-1.5 px-2 text-right font-bold text-red-400">{d.temp_max}°</td>
                    <td className="py-1.5 px-2 text-right text-blue-400">{d.temp_min}°</td>
                    <td className={`py-1.5 px-2 text-right ${d.precip_prob >= 50 ? "text-blue-400 font-bold" : "text-stone-400"}`}>{d.precip_prob}%</td>
                    <td className="py-1.5 px-2 text-right text-stone-400">{d.wind_max}km/h</td>
                    <td className="py-1.5 px-2 text-right text-stone-400">{d.uv_index}</td>
                    <td className="py-1.5 px-2 text-right text-amber-400">{d.sunshine_hrs}h</td>
                    <td className="py-1.5 px-2 text-center">
                      <div className="flex items-center justify-center gap-1">
                        <div className="w-8 h-2 bg-stone-800 rounded-full overflow-hidden"><div className={`h-full rounded-full ${scoreBg(d.weather_score)}`} style={{ width: `${d.weather_score}%` }} /></div>
                        <span className={`text-[10px] font-bold ${scoreColor(d.weather_score)}`}>{d.weather_score}</span>
                      </div>
                    </td>
                    <td className="py-1.5 px-2 text-right text-stone-400">{d.demand !== null ? `${d.demand}%` : "—"}</td>
                    <td className="py-1.5 px-2 text-right text-white font-bold">{cur(d.our_rate)}</td>
                    <td className="py-1.5 px-2 text-left">{d.event && <Badge className="bg-red-500/20 text-red-400 text-[8px]">{d.event}</Badge>}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
