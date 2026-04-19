import { useState, useEffect, useCallback, useMemo } from "react";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import {
  TrendingUp, DollarSign, Percent, Receipt, Wallet, BarChart3,
  RefreshCw, Download, Sparkles, ChevronDown, Bed, Globe,
  ArrowUpRight, ArrowDownRight, Target, Brain, Zap, AlertTriangle,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const fmt = (v) => `£${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const pct = (v) => `${Number(v || 0).toFixed(1)}%`;

// Distinct brand-ish colors for channel bars
const CHANNEL_COLOR = {
  "Booking.com": "#003580",
  "Airbnb":      "#FF5A5F",
  "Expedia":     "#FFC72C",
  "Google":      "#4285F4",
  "Agoda":       "#FF3B00",
  "Hotelbeds":   "#00A3E4",
  "Direct":      "#10b981",
  "Web":         "#8b5cf6",
  "Website":     "#8b5cf6",
  "Affiliate":   "#f97316",
  "Phone":       "#14b8a6",
  "Walk-in":     "#84cc16",
  "Stripe":      "#635BFF",
  "PayAtHotel":  "#64748b",
  "Hotels.com":  "#EF4444",
  "Turkish_Payment": "#e11d48",
};
const colorFor = (src) => CHANNEL_COLOR[src] || "#78716c";

export const ProfitOSPanel = ({ user, propertyId }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState("30");
  const [advisor, setAdvisor] = useState(null);
  const [advisorLoading, setAdvisorLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const today = new Date();
      const start = new Date(today);
      start.setDate(today.getDate() - (parseInt(days, 10) - 1));
      const p = new URLSearchParams();
      if (propertyId && propertyId !== "all") p.set("property_id", propertyId);
      p.set("start", start.toISOString().slice(0, 10));
      p.set("end", today.toISOString().slice(0, 10));
      const { data: d } = await axios.get(`${API}/revenue/profit-os?${p}`);
      setData(d);
    } catch {
      toast.error("Failed to load Profit OS");
    }
    setLoading(false);
  }, [days, propertyId]);

  useEffect(() => { load(); }, [load]);

  const runAdvisor = async () => {
    if (!data) return;
    setAdvisorLoading(true);
    setAdvisor(null);
    try {
      const { data: res } = await axios.post(`${API}/revenue/profit-os/advisor`, data, { timeout: 90000 });
      setAdvisor(res);
      toast.success(`AI advisor generated ${res.recommendations?.length || 0} recommendations`);
    } catch (e) {
      toast.error("AI advisor is busy — please retry in a moment");
    }
    setAdvisorLoading(false);
  };

  const onExport = () => {
    if (!data) return;
    const rows = [
      ["Metric", "Value"],
      ["Gross Revenue", data.kpis.gross_revenue],
      ["Commission", data.kpis.total_commission],
      ["Payment Fees", data.kpis.total_payment_fees],
      ["Net Revenue", data.kpis.net_revenue],
      ["Net Margin %", data.kpis.net_margin_pct],
      ["CPAR", data.kpis.cpar],
      ["RevPAR", data.kpis.revpar],
      ["ADR", data.kpis.adr],
      ["Occupancy %", data.kpis.occupancy_pct],
      [""],
      ["Channel", "Bookings", "Gross", "Commission", "Fees", "Net", "Margin %", "Contribution %"],
      ...data.by_channel.map((c) => [c.source, c.bookings, c.gross.toFixed(2), c.commission.toFixed(2), c.fee.toFixed(2), c.net.toFixed(2), c.net_margin_pct.toFixed(1), c.contribution_pct.toFixed(1)]),
    ];
    const csv = rows.map((r) => r.map((v) => `"${v}"`).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `profit-os-${data.window.start}-to-${data.window.end}.csv`;
    a.click(); URL.revokeObjectURL(url);
    toast.success("Profit OS report exported");
  };

  const maxNet = useMemo(() => Math.max(1, ...(data?.by_channel || []).map((c) => c.net)), [data]);
  const maxTrendGross = useMemo(() => Math.max(1, ...(data?.trend || []).map((t) => t.gross)), [data]);

  return (
    <div className="space-y-5" data-testid="profit-os-panel">
      {/* Hero Header */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-emerald-600 via-teal-700 to-emerald-900 p-6 shadow-xl">
        <div className="absolute top-0 right-0 w-96 h-96 rounded-full bg-white/5 -mr-32 -mt-32 blur-3xl"></div>
        <div className="absolute bottom-0 left-0 w-72 h-72 rounded-full bg-emerald-300/10 -ml-20 -mb-20 blur-3xl"></div>
        <div className="relative flex items-start justify-between">
          <div>
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-white/15 backdrop-blur rounded-full text-[10px] font-bold uppercase tracking-wider text-emerald-100 mb-3">
              <Sparkles className="w-3 h-3" /> REVENUE · PROFIT OS · CPAR
            </div>
            <h1 className="text-3xl font-black text-white leading-tight">What your revenue<br /><span className="text-emerald-200">actually earns.</span></h1>
            <p className="text-sm text-emerald-100 mt-2 max-w-xl">ContributionPAR strips OTA commissions and payment processing fees from gross revenue so you see the real dollar that reaches the P&amp;L — per channel, per room type, per day.</p>
          </div>
          <div className="flex items-center gap-2">
            <Select value={days} onValueChange={setDays}>
              <SelectTrigger className="w-32 bg-white/15 backdrop-blur border-white/20 text-white hover:bg-white/20" data-testid="profit-os-window"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="7">Last 7 days</SelectItem>
                <SelectItem value="30">Last 30 days</SelectItem>
                <SelectItem value="60">Last 60 days</SelectItem>
                <SelectItem value="90">Last 90 days</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="secondary" size="sm" onClick={load} className="bg-white/15 border-white/20 text-white hover:bg-white/25" data-testid="profit-os-refresh">
              <RefreshCw className={`w-4 h-4 mr-1.5 ${loading ? "animate-spin" : ""}`} /> Refresh
            </Button>
            <Button variant="secondary" size="sm" onClick={onExport} disabled={!data} className="bg-white/15 border-white/20 text-white hover:bg-white/25" data-testid="profit-os-export">
              <Download className="w-4 h-4 mr-1.5" /> Export CSV
            </Button>
          </div>
        </div>
      </div>

      {loading && !data && (
        <div className="bg-white rounded-xl border border-stone-200 p-10 text-center text-stone-400">
          <RefreshCw className="w-8 h-8 mx-auto mb-2 animate-spin" /> Calculating contribution margins…
        </div>
      )}

      {data && (
        <>
          {/* KPI Row 1 — Revenue waterfall */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <KpiCard testId="po-gross" label="Gross Revenue" value={fmt(data.kpis.gross_revenue)} sub={`${data.kpis.bookings_count} bookings · ADR ${fmt(data.kpis.adr)}`} icon={DollarSign} accent="from-sky-500 to-blue-700" />
            <KpiCard testId="po-commission" label="Commission" value={fmt(data.kpis.total_commission)} sub={`${pct(data.kpis.commission_pct)} of gross`} icon={Percent} accent="from-amber-500 to-orange-600" negative />
            <KpiCard testId="po-fees" label="Payment Fees" value={fmt(data.kpis.total_payment_fees)} sub="Stripe 2.9% + 30p" icon={Receipt} accent="from-rose-500 to-red-700" negative />
            <KpiCard testId="po-net" label="Net Revenue" value={fmt(data.kpis.net_revenue)} sub={`${pct(data.kpis.net_margin_pct)} margin`} icon={Wallet} accent="from-emerald-500 to-teal-700" big />
          </div>

          {/* KPI Row 2 — Operational metrics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <KpiCard testId="po-cpar" label="CPAR" value={fmt(data.kpis.cpar)} sub="Net per available room" icon={Target} accent="from-emerald-500 to-teal-700" hero />
            <KpiCard testId="po-revpar" label="RevPAR" value={fmt(data.kpis.revpar)} sub="Gross per available room" icon={BarChart3} accent="from-indigo-500 to-violet-700" />
            <KpiCard testId="po-adr" label="ADR" value={fmt(data.kpis.adr)} sub={`${data.kpis.occupied_nights} occupied nights`} icon={TrendingUp} accent="from-stone-500 to-stone-700" />
            <KpiCard testId="po-occ" label="Occupancy" value={pct(data.kpis.occupancy_pct)} sub={`${data.scope.total_rooms} rooms × ${data.window.nights} nights`} icon={Bed} accent="from-amber-500 to-orange-600" />
          </div>

          {/* AI Revenue Advisor */}
          <div className="bg-gradient-to-br from-violet-950 via-indigo-900 to-violet-900 rounded-2xl p-5 shadow-xl relative overflow-hidden" data-testid="po-advisor">
            <div className="absolute top-0 right-0 w-64 h-64 rounded-full bg-violet-500/20 -mr-20 -mt-20 blur-3xl"></div>
            <div className="absolute bottom-0 left-0 w-48 h-48 rounded-full bg-indigo-400/10 -ml-16 -mb-16 blur-3xl"></div>
            <div className="relative">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-violet-400 to-indigo-600 flex items-center justify-center shadow-lg shadow-violet-500/40">
                    <Brain className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <div className="inline-flex items-center gap-1.5 px-2 py-0.5 bg-white/10 backdrop-blur rounded-full text-[9px] font-bold uppercase tracking-wider text-violet-200 mb-1">
                      <Sparkles className="w-2.5 h-2.5" /> AI REVENUE ADVISOR · CLAUDE 4.5
                    </div>
                    <h3 className="font-black text-white text-lg">What would a revenue consultant do?</h3>
                  </div>
                </div>
                <Button
                  size="sm"
                  onClick={runAdvisor}
                  disabled={advisorLoading || !data}
                  className="bg-gradient-to-r from-violet-500 to-indigo-600 text-white border-0 hover:from-violet-400 hover:to-indigo-500 shadow-lg shadow-violet-500/30"
                  data-testid="po-advisor-run"
                >
                  {advisorLoading ? <><RefreshCw className="w-4 h-4 mr-1.5 animate-spin" /> Analyzing…</> : <><Zap className="w-4 h-4 mr-1.5" /> Generate recommendations</>}
                </Button>
              </div>

              {!advisor && !advisorLoading && (
                <p className="text-sm text-violet-200/80" data-testid="po-advisor-hint">
                  Click <span className="font-semibold text-white">Generate recommendations</span> to have Claude 4.5 analyze this CPAR snapshot and surface the 3 highest-leverage revenue moves for this week — quantified in £/month.
                </p>
              )}

              {advisorLoading && (
                <div className="bg-white/5 backdrop-blur rounded-xl p-8 text-center text-violet-200">
                  <Brain className="w-8 h-8 mx-auto mb-2 animate-pulse" />
                  <div className="text-sm">Analyzing {data?.by_channel?.length || 0} channels and {data?.by_room_type?.length || 0} room types…</div>
                </div>
              )}

              {advisor && (
                <div className="space-y-3" data-testid="po-advisor-result">
                  <div className="bg-white/10 backdrop-blur rounded-xl p-3 border border-violet-400/30">
                    <div className="flex items-start gap-2">
                      <Sparkles className="w-4 h-4 text-amber-300 flex-shrink-0 mt-0.5" />
                      <p className="text-sm text-white font-medium italic leading-relaxed">{advisor.headline}</p>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    {advisor.recommendations.map((r, i) => {
                      const sev = (r.severity || "medium").toLowerCase();
                      const sevCls = sev === "high" ? "bg-rose-500/20 text-rose-200 border-rose-400/40" : sev === "low" ? "bg-stone-500/20 text-stone-200 border-stone-400/40" : "bg-amber-500/20 text-amber-200 border-amber-400/40";
                      return (
                        <div key={i} className="bg-white/10 backdrop-blur rounded-xl p-4 border border-violet-400/20 hover:border-violet-300/40 transition-all" data-testid={`po-advisor-rec-${i}`}>
                          <div className="flex items-center justify-between mb-2">
                            <Badge className={`text-[9px] uppercase tracking-wider border ${sevCls}`}>{sev}</Badge>
                            <div className="text-right">
                              <div className="text-[9px] uppercase tracking-wider text-violet-300">Projected</div>
                              <div className="text-lg font-black text-emerald-300 leading-none flex items-center gap-0.5">
                                <ArrowUpRight className="w-4 h-4" />
                                £{Math.round(r.impact_gbp_per_month).toLocaleString()}
                                <span className="text-[9px] text-violet-300 font-normal ml-0.5">/mo</span>
                              </div>
                            </div>
                          </div>
                          <h4 className="font-bold text-white text-sm leading-snug mb-1">{r.title}</h4>
                          <Badge variant="outline" className="text-[10px] bg-white/5 text-violet-100 border-violet-300/30 mb-2">
                            <Target className="w-2.5 h-2.5 mr-1" /> {r.channel_or_room}
                          </Badge>
                          <p className="text-[11px] text-violet-100/90 leading-relaxed mb-2">{r.rationale}</p>
                          <div className="bg-violet-950/50 rounded-lg p-2 border-l-2 border-emerald-400">
                            <div className="text-[9px] uppercase tracking-wider text-emerald-300 font-bold mb-0.5 flex items-center gap-1">
                              <Zap className="w-2.5 h-2.5" /> Next step
                            </div>
                            <p className="text-[11px] text-white leading-relaxed">{r.action}</p>
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {advisor.risk_flag && (
                    <div className="bg-rose-500/15 backdrop-blur rounded-xl p-3 border border-rose-400/40 flex items-start gap-2">
                      <AlertTriangle className="w-4 h-4 text-rose-300 flex-shrink-0 mt-0.5" />
                      <div>
                        <div className="text-[10px] uppercase tracking-wider text-rose-300 font-bold mb-0.5">Risk flag</div>
                        <p className="text-xs text-rose-100">{advisor.risk_flag}</p>
                      </div>
                    </div>
                  )}

                  <div className="flex items-center gap-2 text-[10px] text-violet-300">
                    <Brain className="w-3 h-3" />
                    Generated by {advisor.model} · {new Date(advisor.generated_at).toLocaleString()}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Channel breakdown */}
          <div className="bg-white rounded-xl border border-stone-200 overflow-hidden" data-testid="po-channels">
            <div className="px-5 py-3 border-b border-stone-100 flex items-center gap-2">
              <Globe className="w-4 h-4 text-emerald-600" />
              <h3 className="font-bold text-stone-800">Channel profitability</h3>
              <span className="ml-auto text-xs text-stone-400">{data.by_channel.length} active channels · sorted by net contribution</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-stone-50 border-b border-stone-200">
                  <tr>
                    <th className="px-4 py-2.5 text-left text-[11px] font-semibold text-stone-600 uppercase tracking-wider">Channel</th>
                    <th className="px-4 py-2.5 text-right text-[11px] font-semibold text-stone-600 uppercase tracking-wider">Bookings</th>
                    <th className="px-4 py-2.5 text-right text-[11px] font-semibold text-stone-600 uppercase tracking-wider">Gross</th>
                    <th className="px-4 py-2.5 text-right text-[11px] font-semibold text-stone-600 uppercase tracking-wider">Commission</th>
                    <th className="px-4 py-2.5 text-right text-[11px] font-semibold text-stone-600 uppercase tracking-wider">Fees</th>
                    <th className="px-4 py-2.5 text-right text-[11px] font-semibold text-stone-600 uppercase tracking-wider">Net</th>
                    <th className="px-4 py-2.5 text-right text-[11px] font-semibold text-stone-600 uppercase tracking-wider">Margin</th>
                    <th className="px-4 py-2.5 text-left text-[11px] font-semibold text-stone-600 uppercase tracking-wider w-48">Contribution</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100">
                  {data.by_channel.map((c) => {
                    const barPct = Math.max(1, (c.net / maxNet) * 100);
                    return (
                      <tr key={c.source} className="hover:bg-emerald-50/40" data-testid={`po-channel-${c.source}`}>
                        <td className="px-4 py-2.5">
                          <div className="flex items-center gap-2">
                            <span className="w-2.5 h-6 rounded-sm" style={{ background: colorFor(c.source) }}></span>
                            <span className="font-semibold text-stone-800">{c.source}</span>
                          </div>
                        </td>
                        <td className="px-4 py-2.5 text-right text-stone-600 tabular-nums">{c.bookings}</td>
                        <td className="px-4 py-2.5 text-right font-mono text-stone-800 tabular-nums">{fmt(c.gross)}</td>
                        <td className="px-4 py-2.5 text-right font-mono tabular-nums">
                          <span className="text-amber-700">-{fmt(c.commission)}</span>
                          <span className="text-[10px] text-stone-400 ml-1">({pct(c.commission_pct)})</span>
                        </td>
                        <td className="px-4 py-2.5 text-right font-mono text-rose-600 tabular-nums">{c.fee > 0 ? `-${fmt(c.fee)}` : "—"}</td>
                        <td className="px-4 py-2.5 text-right font-mono font-bold text-emerald-700 tabular-nums">{fmt(c.net)}</td>
                        <td className="px-4 py-2.5 text-right">
                          <Badge className={`text-[10px] ${c.net_margin_pct > 85 ? "bg-emerald-100 text-emerald-800" : c.net_margin_pct > 75 ? "bg-amber-100 text-amber-800" : "bg-rose-100 text-rose-800"}`}>
                            {pct(c.net_margin_pct)}
                          </Badge>
                        </td>
                        <td className="px-4 py-2.5">
                          <div className="flex items-center gap-2">
                            <div className="flex-1 h-2 bg-stone-100 rounded-full overflow-hidden">
                              <div className="h-full rounded-full transition-all" style={{ width: `${barPct}%`, background: `linear-gradient(to right, ${colorFor(c.source)}, ${colorFor(c.source)}dd)` }}></div>
                            </div>
                            <span className="text-xs font-bold text-stone-600 w-10 text-right tabular-nums">{pct(c.contribution_pct)}</span>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Room type breakdown + Daily trend */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="bg-white rounded-xl border border-stone-200 overflow-hidden" data-testid="po-room-types">
              <div className="px-5 py-3 border-b border-stone-100 flex items-center gap-2">
                <Bed className="w-4 h-4 text-emerald-600" />
                <h3 className="font-bold text-stone-800">Room type · CPAR ranking</h3>
              </div>
              <div className="divide-y divide-stone-100 max-h-96 overflow-auto">
                {data.by_room_type.length === 0 && (
                  <div className="p-6 text-center text-sm text-stone-400">No room-type data</div>
                )}
                {data.by_room_type.map((r) => {
                  const maxCpar = Math.max(1, ...data.by_room_type.map((x) => x.cpar));
                  const barPct = Math.max(2, (r.cpar / maxCpar) * 100);
                  return (
                    <div key={r.room_type_id} className="px-5 py-3" data-testid={`po-rt-${r.room_type_id}`}>
                      <div className="flex items-center justify-between mb-1.5">
                        <div>
                          <div className="font-semibold text-sm text-stone-800">{r.room_type_name}</div>
                          <div className="text-[10px] text-stone-500">{r.bookings} bookings · {r.nights} nights · ADR {fmt(r.adr)}</div>
                        </div>
                        <div className="text-right">
                          <div className="text-lg font-black text-emerald-700 tabular-nums">{fmt(r.cpar)}</div>
                          <div className="text-[10px] text-stone-400">CPAR</div>
                        </div>
                      </div>
                      <div className="h-2 bg-stone-100 rounded-full overflow-hidden">
                        <div className="h-full bg-gradient-to-r from-emerald-500 to-teal-600 rounded-full" style={{ width: `${barPct}%` }}></div>
                      </div>
                      <div className="flex items-center gap-3 text-[10px] text-stone-500 mt-1.5">
                        <span>Gross {fmt(r.gross)}</span>
                        <span>·</span>
                        <span>Net {fmt(r.net)}</span>
                        <span>·</span>
                        <span className="text-emerald-700 font-semibold">{pct(r.net_margin_pct)} margin</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="bg-white rounded-xl border border-stone-200 overflow-hidden" data-testid="po-trend">
              <div className="px-5 py-3 border-b border-stone-100 flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-emerald-600" />
                <h3 className="font-bold text-stone-800">Daily gross vs net</h3>
                <span className="ml-auto text-xs text-stone-400">{data.window.start} → {data.window.end}</span>
              </div>
              <div className="p-4">
                <div className="flex items-end gap-0.5 h-48">
                  {data.trend.map((t) => {
                    const grossH = (t.gross / maxTrendGross) * 100;
                    const netH = (t.net / maxTrendGross) * 100;
                    return (
                      <div key={t.date} className="flex-1 relative group flex flex-col justify-end" title={`${t.date}\nGross: ${fmt(t.gross)} · Net: ${fmt(t.net)} · ${t.bookings} bookings`}>
                        <div className="absolute inset-x-0 bottom-0 flex justify-center">
                          <div className="w-full bg-sky-200 rounded-t-sm" style={{ height: `${grossH}%` }}></div>
                        </div>
                        <div className="absolute inset-x-0 bottom-0 flex justify-center">
                          <div className="w-full bg-gradient-to-t from-emerald-600 to-emerald-400 rounded-t-sm" style={{ height: `${netH}%` }}></div>
                        </div>
                      </div>
                    );
                  })}
                </div>
                <div className="flex items-center justify-between mt-3 text-[10px] text-stone-500">
                  <span>{data.trend[0]?.date.slice(5) || ""}</span>
                  <span className="flex items-center gap-3">
                    <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-sky-200"></span> Gross</span>
                    <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-emerald-500"></span> Net</span>
                  </span>
                  <span>{data.trend[data.trend.length - 1]?.date.slice(5) || ""}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Cost model assumptions */}
          <div className="bg-stone-50 border border-stone-200 rounded-xl p-4" data-testid="po-cost-model">
            <div className="flex items-center gap-2 mb-2">
              <Sparkles className="w-4 h-4 text-stone-600" />
              <h4 className="font-semibold text-sm text-stone-700">Cost-model assumptions</h4>
              <span className="text-[10px] text-stone-400 ml-auto">Industry defaults — override per-property coming in v2</span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(data.cost_model.commission_rates)
                .sort((a, b) => b[1] - a[1])
                .map(([src, rate]) => (
                  <Badge key={src} variant="outline" className="text-[10px] bg-white" style={{ borderColor: colorFor(src) + "60", color: colorFor(src) }}>
                    {src}: {(rate * 100).toFixed(0)}%
                  </Badge>
                ))}
              <Badge variant="outline" className="text-[10px] bg-white border-rose-300 text-rose-700">
                + Card fee: {(data.cost_model.payment_fee_pct * 100).toFixed(1)}% + £{data.cost_model.payment_fee_fixed.toFixed(2)}
              </Badge>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

const KpiCard = ({ icon: Icon, label, value, sub, accent, big, hero, negative, testId }) => (
  <div className={`bg-white rounded-xl border ${hero ? "border-emerald-400 ring-2 ring-emerald-100" : "border-stone-200"} p-4 relative overflow-hidden`} data-testid={testId}>
    <div className={`absolute top-0 right-0 w-24 h-24 rounded-full bg-gradient-to-br ${accent} opacity-10 -mr-8 -mt-8`}></div>
    <div className="flex items-center gap-2 mb-2 relative">
      <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${accent} flex items-center justify-center`}>
        <Icon className="w-4 h-4 text-white" />
      </div>
      <span className="text-[11px] font-medium text-stone-500 uppercase tracking-wider">{label}</span>
    </div>
    <div className={`${big || hero ? "text-3xl" : "text-2xl"} font-black ${hero ? "text-emerald-700" : "text-stone-900"}`}>
      {negative && "-"}{value}
    </div>
    {sub && <div className="text-[11px] text-stone-500 mt-0.5 flex items-center gap-1">{hero ? <ArrowUpRight className="w-3 h-3 text-emerald-500" /> : null}{sub}</div>}
  </div>
);

export default ProfitOSPanel;
