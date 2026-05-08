import { useState, useEffect } from "react";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import { RefreshCw, Trophy, TrendingUp, TrendingDown, Minus, MapPin, Building2, Users, BarChart3, ArrowUpRight, ArrowDownRight } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;

const RankBadge = ({ rank, total }) => {
  const pct = rank / total;
  const color = pct <= 0.25 ? "bg-emerald-500" : pct <= 0.5 ? "bg-amber-500" : pct <= 0.75 ? "bg-orange-500" : "bg-red-500";
  return <span className={`inline-flex items-center justify-center w-8 h-8 rounded-full text-white text-sm font-bold ${color}`}>{rank}</span>;
};

const DiffArrow = ({ value }) => {
  if (value > 0) return <ArrowUpRight className="w-3.5 h-3.5 text-emerald-400" />;
  if (value < 0) return <ArrowDownRight className="w-3.5 h-3.5 text-red-400" />;
  return <Minus className="w-3.5 h-3.5 text-stone-500" />;
};

export const CompsetIntelligence = ({ propertyId }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);

  useEffect(() => {
    setLoading(true);
    axios.get(`${API}/revenue/compset-intel/${propertyId}?days=${days}`)
      .then(r => { setData(r.data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [propertyId, days]);

  if (loading) return <div className="flex items-center justify-center py-20 text-stone-400"><RefreshCw className="w-5 h-5 animate-spin mr-2" />Loading Compset Intelligence...</div>;
  if (!data) return null;

  const { kpis, sentinel_insight, key_insights, daily, tier_distribution, neighbourhoods, market_context } = data;

  // Chart dimensions
  const cW = 1100, cH = 260, pL = 55, pR = 15, pT = 25, pB = 40;
  const iW = cW - pL - pR, iH = cH - pT - pB;

  // ADR chart
  const maxADR = Math.max(...daily.map(d => Math.max(d.my_adr, d.comp_adr)), 1) * 1.08;
  const minADR = Math.min(...daily.map(d => Math.min(d.my_adr, d.comp_adr))) * 0.92;
  const adrSX = (i) => pL + (i / Math.max(daily.length - 1, 1)) * iW;
  const adrSY = (v) => pT + (1 - (v - minADR) / (maxADR - minADR)) * iH;
  const myADRLine = daily.map((d, i) => `${i === 0 ? "M" : "L"} ${adrSX(i)} ${adrSY(d.my_adr)}`).join(" ");
  const compADRLine = daily.map((d, i) => `${i === 0 ? "M" : "L"} ${adrSX(i)} ${adrSY(d.comp_adr)}`).join(" ");

  // Occupancy chart
  const occSY = (v) => pT + (1 - v / 100) * iH;
  const myOccLine = daily.map((d, i) => `${i === 0 ? "M" : "L"} ${adrSX(i)} ${occSY(d.my_occ)}`).join(" ");
  const compOccLine = daily.map((d, i) => `${i === 0 ? "M" : "L"} ${adrSX(i)} ${occSY(d.comp_occ)}`).join(" ");

  // RevPAR chart
  const maxRevPAR = Math.max(...daily.map(d => Math.max(d.my_revpar, d.comp_revpar)), 1) * 1.1;
  const rpSY = (v) => pT + (1 - v / maxRevPAR) * iH;
  const myRPLine = daily.map((d, i) => `${i === 0 ? "M" : "L"} ${adrSX(i)} ${rpSY(d.my_revpar)}`).join(" ");
  const compRPLine = daily.map((d, i) => `${i === 0 ? "M" : "L"} ${adrSX(i)} ${rpSY(d.comp_revpar)}`).join(" ");

  // Tier chart
  const maxTier = Math.max(...tier_distribution.map(t => t.count), 1);
  const tierColors = ["#8b5cf6", "#3b82f6", "#06b6d4", "#f59e0b"];

  const occDiff = kpis.my_occupancy - kpis.comp_occupancy;
  const adrDiff = kpis.my_adr - kpis.comp_adr;
  const rpDiff = kpis.my_revpar - kpis.comp_revpar;

  return (
    <div className="space-y-5" data-testid="compset-intelligence">
      {/* Header */}
      <div className="bg-stone-900 rounded-2xl p-5 text-white">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-white/10 rounded-xl flex items-center justify-center"><Trophy className="w-5 h-5 text-violet-400" /></div>
            <div>
              <h2 className="text-lg font-bold flex items-center gap-2" data-testid="compset-title">Compset Intelligence <Badge className="bg-violet-500/20 text-violet-300 text-[9px]">LIVE</Badge></h2>
              <p className="text-xs text-white/40">Your hotel vs competitive set — {days}-day analysis</p>
            </div>
          </div>
          <div className="flex items-center gap-1 bg-white/5 rounded-xl border border-white/10 p-0.5">
            {[7, 14, 30, 60, 90].map(d => (
              <button key={d} onClick={() => setDays(d)} data-testid={`compset-days-${d}`}
                className={`px-3 py-1.5 text-xs font-semibold rounded-lg ${days === d ? "bg-violet-500 text-white" : "text-white/35 hover:text-white/70"}`}>{d}d</button>
            ))}
          </div>
        </div>

        {/* Sentinel Insight */}
        <div className="bg-white/5 border border-white/10 rounded-xl p-4 mb-4" data-testid="sentinel-insight">
          <p className="text-sm text-white/80">{sentinel_insight}</p>
        </div>

        {/* Ranking Cards */}
        <div className="grid grid-cols-3 gap-3 mb-4" data-testid="ranking-cards">
          {/* Occupancy */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[9px] text-white/30 uppercase font-bold">Occupancy</span>
              <RankBadge rank={kpis.occ_rank} total={kpis.segment_size} />
            </div>
            <div className="flex items-end gap-3">
              <div>
                <p className="text-2xl font-black text-white">{kpis.my_occupancy}%</p>
                <p className="text-[10px] text-white/30">Your hotel</p>
              </div>
              <div className="text-right">
                <p className="text-lg font-bold text-stone-400">{kpis.comp_occupancy}%</p>
                <p className="text-[10px] text-white/30">Segment avg</p>
              </div>
            </div>
            <div className="mt-2 flex items-center gap-1">
              <DiffArrow value={occDiff} />
              <span className={`text-xs font-bold ${occDiff >= 0 ? "text-emerald-400" : "text-red-400"}`}>{occDiff > 0 ? "+" : ""}{occDiff} pts</span>
              <span className="text-[9px] text-white/20 ml-1">Rank {kpis.occ_rank} of {kpis.segment_size}</span>
            </div>
          </div>

          {/* ADR */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[9px] text-white/30 uppercase font-bold">ADR</span>
              <RankBadge rank={kpis.adr_rank} total={kpis.segment_size} />
            </div>
            <div className="flex items-end gap-3">
              <div>
                <p className="text-2xl font-black text-white">{cur(kpis.my_adr)}</p>
                <p className="text-[10px] text-white/30">Your hotel</p>
              </div>
              <div className="text-right">
                <p className="text-lg font-bold text-stone-400">{cur(kpis.comp_adr)}</p>
                <p className="text-[10px] text-white/30">Segment avg</p>
              </div>
            </div>
            <div className="mt-2 flex items-center gap-1">
              <DiffArrow value={adrDiff} />
              <span className={`text-xs font-bold ${adrDiff >= 0 ? "text-emerald-400" : "text-red-400"}`}>{adrDiff >= 0 ? "+" : ""}{cur(Math.abs(adrDiff))}</span>
              <span className="text-[9px] text-white/20 ml-1">Rank {kpis.adr_rank} of {kpis.segment_size}</span>
            </div>
          </div>

          {/* RevPAR */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[9px] text-white/30 uppercase font-bold">RevPAR</span>
              <RankBadge rank={kpis.revpar_rank} total={kpis.segment_size} />
            </div>
            <div className="flex items-end gap-3">
              <div>
                <p className="text-2xl font-black text-white">{cur(kpis.my_revpar)}</p>
                <p className="text-[10px] text-white/30">Your hotel</p>
              </div>
              <div className="text-right">
                <p className="text-lg font-bold text-stone-400">{cur(kpis.comp_revpar)}</p>
                <p className="text-[10px] text-white/30">Segment avg</p>
              </div>
            </div>
            <div className="mt-2 flex items-center gap-1">
              <DiffArrow value={rpDiff} />
              <span className={`text-xs font-bold ${rpDiff >= 0 ? "text-emerald-400" : "text-red-400"}`}>{rpDiff >= 0 ? "+" : ""}{cur(Math.abs(rpDiff))}</span>
              <span className="text-[9px] text-white/20 ml-1">Rank {kpis.revpar_rank} of {kpis.segment_size}</span>
            </div>
          </div>
        </div>

        {/* Key Insights Row */}
        <div className="grid grid-cols-3 gap-3" data-testid="key-insights">
          {key_insights.map((ins, i) => (
            <div key={i} className={`rounded-xl p-3 border ${ins.direction === "above" ? "bg-emerald-900/20 border-emerald-500/20" : ins.direction === "below" ? "bg-red-900/20 border-red-500/20" : "bg-stone-800 border-stone-700"}`}>
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-white">{ins.metric}</span>
                <span className={`text-sm font-black ${ins.direction === "above" ? "text-emerald-400" : ins.direction === "below" ? "text-red-400" : "text-white"}`}>{ins.diff}</span>
              </div>
              <p className="text-[10px] text-stone-400 mt-1">{ins.text}</p>
            </div>
          ))}
        </div>
      </div>

      {/* ADR Performance Chart */}
      <div className="bg-stone-900 border border-stone-700 rounded-2xl p-5" data-testid="adr-chart">
        <div className="flex items-center justify-between mb-2">
          <div>
            <p className="text-[10px] text-stone-500 uppercase">Daily Performance</p>
            <h3 className="text-sm font-bold text-white">ADR — Your Hotel vs Segment</h3>
          </div>
          <div className="flex items-center gap-4 text-[10px] text-stone-400">
            <span className="flex items-center gap-1"><span className="w-4 h-0.5 bg-violet-400 inline-block" /> Your Hotel</span>
            <span className="flex items-center gap-1"><span className="w-4 h-0.5 bg-stone-500 inline-block" /> Segment Avg</span>
          </div>
        </div>
        <div className="overflow-x-auto">
          <svg viewBox={`0 0 ${cW} ${cH}`} className="w-full" style={{ minWidth: "600px" }}>
            {[0, 0.25, 0.5, 0.75, 1].map(f => {
              const v = Math.round(minADR + f * (maxADR - minADR));
              const y = adrSY(v);
              return <g key={f}><line x1={pL} x2={cW - pR} y1={y} y2={y} stroke="#374151" strokeWidth="0.5" /><text x={pL - 8} y={y + 4} textAnchor="end" className="text-[7px]" fill="#6b7280">{cur(v)}</text></g>;
            })}
            <path d={compADRLine} fill="none" stroke="#6b7280" strokeWidth="1.5" strokeDasharray="4 3" />
            <path d={myADRLine} fill="none" stroke="#8b5cf6" strokeWidth="2.5" />
            {daily.filter((_, i) => i % Math.max(1, Math.floor(daily.length / 8)) === 0).map((d, idx) => {
              const i = daily.indexOf(d);
              return <text key={idx} x={adrSX(i)} y={cH - 10} textAnchor="middle" className="text-[7px]" fill="#6b7280">{new Date(d.date + "T00:00:00").toLocaleDateString("en", { day: "numeric", month: "short" })}</text>;
            })}
          </svg>
        </div>
      </div>

      {/* Occupancy + RevPAR side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Occupancy Chart */}
        <div className="bg-stone-900 border border-stone-700 rounded-2xl p-5" data-testid="occ-chart">
          <div className="flex items-center justify-between mb-2">
            <div>
              <p className="text-[10px] text-stone-500 uppercase">Occupancy</p>
              <h3 className="text-sm font-bold text-white">Your Hotel vs Segment</h3>
            </div>
            <div className="flex items-center gap-3 text-[9px] text-stone-400">
              <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-cyan-400 inline-block" /> You</span>
              <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-stone-500 inline-block" /> Seg</span>
            </div>
          </div>
          <div className="overflow-x-auto">
            <svg viewBox={`0 0 ${cW / 2 + 40} ${cH - 30}`} className="w-full" style={{ minWidth: "350px" }}>
              {[0, 25, 50, 75, 100].map(v => {
                const y = 15 + (1 - v / 100) * (iH - 10);
                return <g key={v}><line x1={40} x2={cW / 2 + 30} y1={y} y2={y} stroke="#374151" strokeWidth="0.5" /><text x={35} y={y + 4} textAnchor="end" className="text-[7px]" fill="#6b7280">{v}%</text></g>;
              })}
              <path d={daily.map((d, i) => `${i === 0 ? "M" : "L"} ${40 + (i / Math.max(daily.length - 1, 1)) * (cW / 2 - 15)} ${15 + (1 - d.comp_occ / 100) * (iH - 10)}`).join(" ")} fill="none" stroke="#6b7280" strokeWidth="1.5" strokeDasharray="4 3" />
              <path d={daily.map((d, i) => `${i === 0 ? "M" : "L"} ${40 + (i / Math.max(daily.length - 1, 1)) * (cW / 2 - 15)} ${15 + (1 - d.my_occ / 100) * (iH - 10)}`).join(" ")} fill="none" stroke="#06b6d4" strokeWidth="2" />
            </svg>
          </div>
        </div>

        {/* RevPAR Chart */}
        <div className="bg-stone-900 border border-stone-700 rounded-2xl p-5" data-testid="revpar-chart">
          <div className="flex items-center justify-between mb-2">
            <div>
              <p className="text-[10px] text-stone-500 uppercase">RevPAR</p>
              <h3 className="text-sm font-bold text-white">Your Hotel vs Segment</h3>
            </div>
            <div className="flex items-center gap-3 text-[9px] text-stone-400">
              <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-emerald-400 inline-block" /> You</span>
              <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-stone-500 inline-block" /> Seg</span>
            </div>
          </div>
          <div className="overflow-x-auto">
            <svg viewBox={`0 0 ${cW / 2 + 40} ${cH - 30}`} className="w-full" style={{ minWidth: "350px" }}>
              {[0, 0.25, 0.5, 0.75, 1].map(f => {
                const v = Math.round(f * maxRevPAR);
                const y = 15 + (1 - f) * (iH - 10);
                return <g key={f}><line x1={40} x2={cW / 2 + 30} y1={y} y2={y} stroke="#374151" strokeWidth="0.5" /><text x={35} y={y + 4} textAnchor="end" className="text-[7px]" fill="#6b7280">{cur(v)}</text></g>;
              })}
              <path d={daily.map((d, i) => `${i === 0 ? "M" : "L"} ${40 + (i / Math.max(daily.length - 1, 1)) * (cW / 2 - 15)} ${15 + (1 - d.comp_revpar / maxRevPAR) * (iH - 10)}`).join(" ")} fill="none" stroke="#6b7280" strokeWidth="1.5" strokeDasharray="4 3" />
              <path d={daily.map((d, i) => `${i === 0 ? "M" : "L"} ${40 + (i / Math.max(daily.length - 1, 1)) * (cW / 2 - 15)} ${15 + (1 - d.my_revpar / maxRevPAR) * (iH - 10)}`).join(" ")} fill="none" stroke="#22c55e" strokeWidth="2" />
            </svg>
          </div>
        </div>
      </div>

      {/* Daily Drill-Down Table */}
      <div className="bg-stone-900 border border-stone-700 rounded-2xl p-5" data-testid="daily-drilldown">
        <p className="text-[10px] text-stone-500 uppercase">Daily Drill-Down</p>
        <h3 className="text-sm font-bold text-white mb-3">Performance by Date</h3>
        <div className="overflow-x-auto max-h-[360px] overflow-y-auto">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-stone-900 z-10">
              <tr className="text-stone-500 border-b border-stone-700">
                <th className="text-left py-2 px-2 font-medium">Date</th>
                <th className="text-left py-2 px-1 font-medium">Day</th>
                <th className="text-right py-2 px-2 font-medium">Your Occ</th>
                <th className="text-right py-2 px-2 font-medium">Seg Occ</th>
                <th className="text-right py-2 px-2 font-medium">Your ADR</th>
                <th className="text-right py-2 px-2 font-medium">Seg ADR</th>
                <th className="text-right py-2 px-2 font-medium">Your RevPAR</th>
                <th className="text-right py-2 px-2 font-medium">Seg RevPAR</th>
              </tr>
            </thead>
            <tbody>
              {daily.map(d => {
                const occW = d.my_occ > d.comp_occ;
                const adrW = d.my_adr > d.comp_adr;
                const rpW = d.my_revpar > d.comp_revpar;
                return (
                  <tr key={d.date} className="border-b border-stone-800/50 hover:bg-stone-800/30">
                    <td className="py-1.5 px-2 text-white font-medium">{new Date(d.date + "T00:00:00").toLocaleDateString("en", { day: "numeric", month: "short" })}</td>
                    <td className="py-1.5 px-1 text-stone-400">{d.dow}</td>
                    <td className={`py-1.5 px-2 text-right font-bold ${occW ? "text-emerald-400" : "text-red-400"}`}>{d.my_occ}%</td>
                    <td className="py-1.5 px-2 text-right text-stone-400">{d.comp_occ}%</td>
                    <td className={`py-1.5 px-2 text-right font-bold ${adrW ? "text-emerald-400" : "text-red-400"}`}>{cur(d.my_adr)}</td>
                    <td className="py-1.5 px-2 text-right text-stone-400">{cur(d.comp_adr)}</td>
                    <td className={`py-1.5 px-2 text-right font-bold ${rpW ? "text-emerald-400" : "text-red-400"}`}>{cur(d.my_revpar)}</td>
                    <td className="py-1.5 px-2 text-right text-stone-400">{cur(d.comp_revpar)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Market Context + Tier Distribution + Neighbourhoods */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Market Context */}
        <div className="bg-stone-900 border border-stone-700 rounded-2xl p-5" data-testid="market-context">
          <p className="text-[10px] text-stone-500 uppercase">Market Context</p>
          <h3 className="text-sm font-bold text-white mb-4">Your Competitive Set</h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs text-stone-400 flex items-center gap-2"><Building2 className="w-3.5 h-3.5" />Segment hotels</span>
              <span className="text-sm font-bold text-white">{market_context.segment_hotels}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-stone-400 flex items-center gap-2"><Users className="w-3.5 h-3.5" />Segment rooms</span>
              <span className="text-sm font-bold text-white">{market_context.segment_rooms?.toLocaleString()}</span>
            </div>
            <div className="h-px bg-stone-700/50" />
            <div className="flex items-center justify-between">
              <span className="text-xs text-stone-400 flex items-center gap-2"><Building2 className="w-3.5 h-3.5" />Market hotels</span>
              <span className="text-sm font-bold text-white">{market_context.market_hotels}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-stone-400 flex items-center gap-2"><Users className="w-3.5 h-3.5" />Market rooms</span>
              <span className="text-sm font-bold text-white">{market_context.market_rooms?.toLocaleString()}</span>
            </div>
          </div>
        </div>

        {/* Tier Distribution */}
        <div className="bg-stone-900 border border-stone-700 rounded-2xl p-5" data-testid="tier-distribution">
          <p className="text-[10px] text-stone-500 uppercase">Segment Breakdown</p>
          <h3 className="text-sm font-bold text-white mb-4">Tier Distribution</h3>
          <div className="space-y-3">
            {tier_distribution.map((t, i) => (
              <div key={t.tier}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-white font-medium">{t.tier}</span>
                  <span className="text-xs text-stone-400">{t.count} hotels</span>
                </div>
                <div className="bg-stone-800 rounded-full h-2 overflow-hidden">
                  <div className="h-2 rounded-full transition-all" style={{ width: `${(t.count / maxTier) * 100}%`, backgroundColor: tierColors[i % tierColors.length] }} />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Neighbourhoods */}
        <div className="bg-stone-900 border border-stone-700 rounded-2xl p-5" data-testid="neighbourhoods">
          <p className="text-[10px] text-stone-500 uppercase">Geography</p>
          <h3 className="text-sm font-bold text-white mb-4">Neighbourhoods</h3>
          <div className="space-y-2 max-h-[220px] overflow-y-auto">
            {neighbourhoods.map(n => (
              <div key={n.area} className="flex items-center justify-between py-1">
                <span className="text-xs text-stone-300 flex items-center gap-1.5"><MapPin className="w-3 h-3 text-stone-500" />{n.area}</span>
                <Badge className="bg-stone-800 text-stone-300 text-[10px]">{n.hotels} hotels</Badge>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
