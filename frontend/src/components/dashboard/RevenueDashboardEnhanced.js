import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { TrendingUp, TrendingDown, Zap, AlertTriangle, CheckCircle, ArrowRight, BarChart3, Clock, Target, Shield, Activity } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;

export const RevenueDashboardEnhanced = ({ propertyId, onNavigate }) => {
  const [data, setData] = useState(null);
  useEffect(() => {
    axios.get(`${API}/revenue/dashboard-enhanced/${propertyId}`).then(r => setData(r.data)).catch(() => toast.error("Failed to load dashboard"));
  }, [propertyId]);

  if (!data) return <div className="flex items-center justify-center py-20 text-stone-400"><Activity className="w-5 h-5 animate-spin mr-2" />Loading dashboard...</div>;

  const { kpis, seven_day_occupancy, demand, booking_pace, ai_confidence, readiness, opportunities, risk_alerts, recent_decisions } = data;

  return (
    <div className="space-y-6" data-testid="rev-enhanced-dashboard">
      {/* Revenue Readiness Banner */}
      <div className="bg-gradient-to-r from-stone-900 via-stone-800 to-stone-900 rounded-2xl p-6 text-white" data-testid="rev-readiness-banner">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-4">
            <div className="relative w-16 h-16">
              <svg className="w-16 h-16 transform -rotate-90" viewBox="0 0 64 64">
                <circle cx="32" cy="32" r="28" fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="6" />
                <circle cx="32" cy="32" r="28" fill="none" stroke="#22c55e" strokeWidth="6"
                  strokeDasharray={`${readiness.pct * 1.76} 176`} strokeLinecap="round" />
              </svg>
              <span className="absolute inset-0 flex items-center justify-center text-lg font-bold">{readiness.pct}%</span>
            </div>
            <div>
              <h3 className="text-xl font-bold">Revenue Readiness</h3>
              <p className="text-sm text-stone-300">{readiness.pct < 50 ? "Setup in Progress" : readiness.pct < 80 ? "Getting There" : "Well Configured"}</p>
              <p className="text-xs text-stone-400 mt-0.5">Complete setup to unlock full automation</p>
            </div>
          </div>
          <button onClick={() => onNavigate?.("wizard")} className="flex items-center gap-2 bg-emerald-500 hover:bg-emerald-600 text-white px-5 py-2.5 rounded-xl text-sm font-semibold transition-all" data-testid="rev-complete-setup-btn">
            Complete Setup <ArrowRight className="w-4 h-4" />
          </button>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {readiness.items.map(item => (
            <div key={item.key} className={`rounded-xl px-3 py-2 text-xs font-medium flex items-center gap-2 ${
              item.status === "passed" ? "bg-emerald-900/40 text-emerald-300" :
              item.status === "failed" ? "bg-red-900/40 text-red-300" :
              "bg-amber-900/30 text-amber-300"
            }`}>
              {item.status === "passed" ? <CheckCircle className="w-3.5 h-3.5" /> :
               item.status === "failed" ? <AlertTriangle className="w-3.5 h-3.5" /> :
               <Clock className="w-3.5 h-3.5" />}
              {item.label}
            </div>
          ))}
        </div>
      </div>

      {/* KPI Cards Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4" data-testid="rev-kpi-cards">
        <div className="bg-white border border-stone-200 rounded-2xl p-5">
          <p className="text-xs text-stone-400 font-medium uppercase tracking-wider">Today's Occupancy</p>
          <p className="text-3xl font-bold text-stone-800 mt-1">{kpis.today_occupancy}%</p>
          <p className="text-xs text-stone-400 mt-1">{kpis.rooms_occupied}/{kpis.total_rooms} rooms occupied</p>
        </div>
        <div className="bg-white border border-stone-200 rounded-2xl p-5">
          <p className="text-xs text-stone-400 font-medium uppercase tracking-wider">ADR</p>
          <p className="text-3xl font-bold text-stone-800 mt-1">{cur(kpis.adr)}</p>
          <p className="text-xs text-stone-400 mt-1">Average Daily Rate</p>
        </div>
        <div className="bg-white border border-stone-200 rounded-2xl p-5">
          <p className="text-xs text-stone-400 font-medium uppercase tracking-wider">RevPAR</p>
          <div className="flex items-center gap-2 mt-1">
            <p className="text-3xl font-bold text-stone-800">{cur(kpis.revpar)}</p>
            <span className={`flex items-center text-xs font-semibold ${kpis.revpar_change >= 0 ? "text-emerald-600" : "text-red-500"}`}>
              {kpis.revpar_change >= 0 ? <TrendingUp className="w-3.5 h-3.5 mr-0.5" /> : <TrendingDown className="w-3.5 h-3.5 mr-0.5" />}
              {Math.abs(kpis.revpar_change)}%
            </span>
          </div>
          <p className="text-xs text-stone-400 mt-1">Revenue per Available Room</p>
        </div>
        <div className="bg-white border border-stone-200 rounded-2xl p-5">
          <p className="text-xs text-stone-400 font-medium uppercase tracking-wider mb-2">7-Day Occupancy</p>
          <div className="flex items-end gap-1 h-12">
            {seven_day_occupancy.map(d => (
              <div key={d.date} className="flex-1 flex flex-col items-center gap-0.5">
                <div className={`w-full rounded-sm transition-all ${d.is_today ? "bg-emerald-500" : d.occupancy > 50 ? "bg-emerald-400" : d.occupancy > 0 ? "bg-stone-300" : "bg-stone-100"}`}
                  style={{ height: `${Math.max(4, d.occupancy / 100 * 40)}px` }} />
                <span className="text-[8px] text-stone-400">{d.dow}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Demand, Pace, Confidence */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4" data-testid="rev-metrics-row">
        <div className="bg-white border border-stone-200 rounded-2xl p-5">
          <div className="flex items-center justify-between mb-2">
            <h4 className="font-bold text-stone-800">Demand Index</h4>
            <Badge className={`text-[10px] ${demand.score >= 70 ? "bg-emerald-100 text-emerald-700" : demand.score >= 40 ? "bg-amber-100 text-amber-700" : "bg-red-100 text-red-700"}`}>
              {demand.label}
            </Badge>
          </div>
          <p className="text-4xl font-bold text-emerald-600 mt-2">{demand.score}</p>
          <p className="text-xs text-stone-400 mt-1">of 100</p>
          <p className="text-xs text-stone-500 mt-2">
            {demand.score >= 70 ? "Strong demand period — optimize for revenue." :
             demand.score >= 40 ? "Moderate demand — maintain competitive rates." :
             "Low demand — consider promotional pricing."}
          </p>
        </div>
        <div className="bg-white border border-stone-200 rounded-2xl p-5">
          <div className="flex items-center justify-between mb-2">
            <h4 className="font-bold text-stone-800">Booking Pace</h4>
            <span className={`flex items-center text-xs font-semibold ${booking_pace.change_pct >= 0 ? "text-emerald-600" : "text-red-500"}`}>
              {booking_pace.change_pct >= 0 ? <TrendingUp className="w-3.5 h-3.5 mr-0.5" /> : <TrendingDown className="w-3.5 h-3.5 mr-0.5" />}
              {Math.abs(booking_pace.change_pct)}%
            </span>
          </div>
          <p className="text-4xl font-bold text-stone-800 mt-2">{booking_pace.count}</p>
          <p className="text-xs text-stone-400 mt-1">check-ins next 7 days</p>
          {booking_pace.change_pct < -10 && (
            <p className="text-xs text-red-500 mt-2 font-medium">Demand is slow — consider action</p>
          )}
        </div>
        <div className="bg-white border border-stone-200 rounded-2xl p-5">
          <div className="flex items-center justify-between mb-2">
            <h4 className="font-bold text-stone-800">AI Confidence</h4>
            <Badge className={`text-[10px] ${ai_confidence.pct >= 70 ? "bg-emerald-100 text-emerald-700" : ai_confidence.pct >= 40 ? "bg-amber-100 text-amber-700" : "bg-red-100 text-red-700"}`}>
              {ai_confidence.pct}%
            </Badge>
          </div>
          <p className="text-xs text-stone-500 mt-2">
            {ai_confidence.pct < 50 ? "Limited data available. Recommendations are conservative." : "Sufficient data for reliable recommendations."}
          </p>
          <div className="mt-3 space-y-1.5 text-xs">
            <div className="flex justify-between"><span className="text-stone-400">Historical Depth</span><span className="font-medium text-stone-600">{ai_confidence.history_days} days</span></div>
            <div className="flex justify-between"><span className="text-stone-400">Booking Volume</span><span className="font-medium text-stone-600">{ai_confidence.total_bookings} bookings</span></div>
          </div>
        </div>
      </div>

      {/* Opportunities & Alerts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white border border-stone-200 rounded-2xl p-5" data-testid="rev-opportunities">
          <h4 className="font-bold text-stone-800 flex items-center gap-2 mb-3"><span className="text-emerald-500">$</span> Revenue Opportunities</h4>
          {opportunities.length === 0 ? (
            <p className="text-sm text-stone-400">No immediate opportunities detected. Revenue strategy is running smoothly.</p>
          ) : opportunities.map((o, i) => (
            <div key={i} className="bg-emerald-50 border border-emerald-100 rounded-xl p-3 mb-2">
              <p className="text-sm font-medium text-emerald-800">{o.title}</p>
              <p className="text-xs text-emerald-600 mt-0.5">{o.desc}</p>
            </div>
          ))}
        </div>
        <div className="bg-white border border-stone-200 rounded-2xl p-5" data-testid="rev-risk-alerts">
          <h4 className="font-bold text-stone-800 flex items-center gap-2 mb-3">
            <AlertTriangle className="w-4 h-4 text-red-500" /> Risk Alerts
            {risk_alerts.length > 0 && <Badge className="bg-red-500 text-white text-[10px]">{risk_alerts.length}</Badge>}
          </h4>
          {risk_alerts.length === 0 ? (
            <div className="text-center py-4">
              <CheckCircle className="w-10 h-10 text-emerald-200 mx-auto mb-2" />
              <p className="text-sm font-medium text-stone-600">All caught up!</p>
              <p className="text-xs text-stone-400">No immediate actions require your attention.</p>
            </div>
          ) : risk_alerts.map((a, i) => (
            <div key={i} className="bg-amber-50 border border-amber-100 rounded-xl p-3 mb-2">
              <p className="text-sm font-medium text-amber-800">{a.title}</p>
              <p className="text-xs text-amber-600 mt-0.5">{a.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* What System is Doing + Review Today */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white border border-stone-200 rounded-2xl p-5">
          <div className="flex items-center justify-between mb-3">
            <h4 className="font-bold text-stone-800">What the system is doing</h4>
            <Badge className="text-[10px] bg-stone-100 text-stone-500">{readiness.pct >= 50 ? "Active" : "Not Configured"}</Badge>
          </div>
          {readiness.pct < 50 ? (
            <div className="bg-stone-50 rounded-xl p-4">
              <div className="flex items-center gap-3">
                <Shield className="w-8 h-8 text-stone-300" />
                <div>
                  <p className="font-semibold text-stone-700 text-sm">Setup Required</p>
                  <p className="text-xs text-stone-400">Complete the Revenue Wizard to activate Smart Pricing.</p>
                </div>
              </div>
            </div>
          ) : (
            <p className="text-sm text-stone-500">Smart pricing is actively monitoring demand and adjusting rate recommendations.</p>
          )}
        </div>
        <div className="bg-white border border-stone-200 rounded-2xl p-5">
          <h4 className="font-bold text-stone-800 mb-3">What you should review today</h4>
          {risk_alerts.length === 0 && opportunities.length === 0 ? (
            <div className="text-center py-4">
              <CheckCircle className="w-10 h-10 text-emerald-200 mx-auto mb-2" />
              <p className="text-sm font-medium text-stone-600">All caught up!</p>
              <p className="text-xs text-stone-400">Your revenue strategy is running smoothly.</p>
            </div>
          ) : (
            <div className="space-y-2">
              {[...opportunities, ...risk_alerts].slice(0, 3).map((item, i) => (
                <div key={i} className="text-xs text-stone-600 flex items-start gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400 mt-1.5 flex-shrink-0" />
                  {item.title}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Recent Pricing Decisions */}
      <div className="bg-white border border-stone-200 rounded-2xl p-5" data-testid="rev-recent-decisions">
        <h4 className="font-bold text-stone-800 mb-3">Recent Pricing Decisions</h4>
        {recent_decisions.length === 0 ? (
          <div className="text-center py-8">
            <Clock className="w-10 h-10 text-stone-200 mx-auto mb-2" />
            <p className="text-sm font-medium text-stone-500">No pricing decisions yet</p>
            <p className="text-xs text-stone-400">Once you start reviewing Smart Pricing suggestions, your decision history will appear here.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {recent_decisions.map(d => (
              <div key={d.id} className="flex items-center justify-between text-sm border-b border-stone-50 pb-2">
                <span className="text-stone-600">{d.room_type_name} — {d.date}</span>
                <Badge className={`text-[10px] ${d.status === "accepted" ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"}`}>{d.status}</Badge>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Quick Action Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4" data-testid="rev-quick-actions">
        {[
          { id: "smart-pricing", icon: BarChart3, label: "Smart Pricing", desc: "AI-powered rate optimization", count: 0, countLabel: "pending" },
          { id: "approvals", icon: CheckCircle, label: "Approvals", desc: "Review pending suggestions", count: 0, countLabel: "to review" },
          { id: "strategy", icon: Target, label: "Playbooks", desc: "Automated pricing rules", count: 0, countLabel: "active" },
          { id: "rate-resolver", icon: Zap, label: "Rate Lookup", desc: "Check any rate instantly", count: null },
        ].map(card => (
          <button key={card.id} onClick={() => onNavigate?.(card.id)} className="bg-white border border-stone-200 rounded-2xl p-5 text-left hover:border-violet-300 hover:shadow-md transition-all group" data-testid={`rev-quick-${card.id}`}>
            <div className="flex items-center justify-between mb-2">
              <card.icon className="w-5 h-5 text-violet-400 group-hover:text-violet-600 transition-colors" />
              {card.count !== null && <span className="text-lg font-bold text-stone-800">{card.count}<span className="text-[10px] text-stone-400 ml-1">{card.countLabel}</span></span>}
            </div>
            <p className="font-semibold text-stone-800 text-sm">{card.label}</p>
            <p className="text-xs text-stone-400 mt-0.5">{card.desc}</p>
          </button>
        ))}
      </div>
    </div>
  );
};
