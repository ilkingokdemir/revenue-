/**
 * Tier-1 Master Operations Dashboard
 * One-glance KPI roll-up from every keyless feature in Batches 1-10.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Loader2, RefreshCw, ShieldCheck, Bell, Database, Code, Star, FlaskConical,
  Mail, Tag, Crown, Clock, Package, RefreshCcw, TrendingUp, Cake,
  CheckCircle, AlertTriangle, PoundSterling, Users, CalendarDays, Trophy,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const fmtMoney = (n) => `£${Number(n || 0).toFixed(0)}`;

export default function Tier1DashboardPanel({ propertyId, hotelName = "" }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [days, setDays] = useState(30);

  const refresh = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/tier1-dashboard/${propertyId}?days=${days}`);
      setData(data);
    } catch { toast.error("Load failed"); }
    setLoading(false);
  }, [propertyId, days]);

  useEffect(() => { refresh(); }, [refresh]);

  if (!data) {
    return <div className="flex items-center justify-center py-20" data-testid="tier1-dashboard-panel"><Loader2 className="w-6 h-6 animate-spin text-stone-400" /></div>;
  }

  const k = data.kpis;
  const totalNewRevenue = (k.late_checkout?.revenue || 0)
                          + (k.stay_ext?.extra_revenue || 0)
                          + (k.cancel_insurance?.fee_revenue || 0);

  return (
    <div className="space-y-6" data-testid="tier1-dashboard-panel">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold text-stone-100">Tier-1 Operations Dashboard</h2>
          <p className="text-sm text-stone-400 mt-1">{hotelName ? `${hotelName} · ` : ""}Live roll-up from every keyless feature — last {data.window_days} days.</p>
        </div>
        <div className="flex gap-2">
          <select value={days} onChange={(e) => setDays(parseInt(e.target.value, 10))} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-xs">
            {[7, 14, 30, 60, 90].map((d) => <option key={d} value={d}>{`${d} days`}</option>)}
          </select>
          <button data-testid="t1-refresh-btn" onClick={refresh} className="text-sm px-3 py-1 rounded bg-stone-800 border border-stone-700 text-stone-300 flex items-center gap-2">
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />} Refresh
          </button>
        </div>
      </div>

      {/* HERO STAT */}
      <div className="rounded-xl border border-emerald-500/40 bg-emerald-500/10 p-6">
        <div className="text-xs uppercase tracking-wider text-emerald-200 mb-2">Incremental revenue captured</div>
        <div className="text-4xl font-bold text-emerald-200 flex items-center gap-3">
          <Trophy className="w-8 h-8" /> {fmtMoney(totalNewRevenue)}
          <span className="text-sm text-emerald-300/80 font-normal">from late-checkout + extensions + insurance</span>
        </div>
      </div>

      {/* HIGHLIGHTS */}
      {data.highlights?.length > 0 && (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
          {data.highlights.map((h, i) => (
            <div key={i} className={`p-3 rounded-lg border ${h.kind === "win" ? "bg-emerald-500/10 border-emerald-500/40" : "bg-amber-500/10 border-amber-500/40"}`} data-testid="t1-highlight">
              <div className={`flex items-center gap-2 text-[10px] uppercase tracking-wider ${h.kind === "win" ? "text-emerald-300" : "text-amber-300"}`}>
                {h.kind === "win" ? <CheckCircle className="w-3 h-3" /> : <AlertTriangle className="w-3 h-3" />} {h.label}
              </div>
              <div className={`mt-1 text-lg font-semibold ${h.kind === "win" ? "text-emerald-200" : "text-amber-200"}`}>{h.value}</div>
            </div>
          ))}
        </div>
      )}

      {/* SECTIONS */}
      <Section title="Revenue captures">
        <KpiCard icon={Clock} label="Late-checkout revenue" main={fmtMoney(k.late_checkout.revenue)} sub={`${k.late_checkout.accepted}/${k.late_checkout.offers} accepted`} good />
        <KpiCard icon={CalendarDays} label="Stay-extension revenue" main={fmtMoney(k.stay_ext.extra_revenue)} sub={`+${k.stay_ext.extra_nights} nights`} good />
        <KpiCard icon={ShieldCheck} label="Insurance net P&L" main={fmtMoney(k.cancel_insurance.net_pl)} sub={`${k.cancel_insurance.policies} sold · ${k.cancel_insurance.claimed} claimed`} good />
        <KpiCard icon={Tag} label="Long-stay discount given" main={fmtMoney(k.long_stay.discount_total)} sub={`${k.long_stay.applied} bookings`} />
      </Section>

      <Section title="Guest experience">
        <KpiCard icon={Star} label="Mid-stay avg score" main={k.mid_stay.avg_score || "—"} sub={`${k.mid_stay.responses} responses · ${k.mid_stay.low_scores} low`} alert={k.mid_stay.low_scores > 0} />
        <KpiCard icon={Tag} label="SR vouchers" main={k.sr_voucher.issued} sub={`${k.sr_voucher.redeemed} redeemed (${k.sr_voucher.redeem_rate_pct}%)`} />
        <KpiCard icon={Cake} label="Birthday vouchers" main={k.sr_voucher.birthday_issued} sub="auto-issued in window" />
        <KpiCard icon={Crown} label="Loyalty upgrades" main={k.loyalty.upgrades} sub={`${k.loyalty.downgrades} downgrades`} good={k.loyalty.upgrades > 0} />
        <KpiCard icon={RefreshCcw} label="Re-booking CTA" main={`${k.rebook.click_rate_pct}%`} sub={`${k.rebook.clicked}/${k.rebook.sent} clicks`} />
        <KpiCard icon={Users} label="Group rooming" main={k.group_rooming.finalized_sessions} sub="finalized sessions" />
      </Section>

      <Section title="Operations & risk">
        <KpiCard icon={ShieldCheck} label="Pre-auth held" main={fmtMoney(k.preauth.currently_held)} sub={`${k.preauth.total_holds} total · ${fmtMoney(k.preauth.captured)} captured`} />
        <KpiCard icon={Trophy} label="Chargeback win rate" main={k.chargeback.cases > 0 ? `${k.chargeback.win_rate_pct}%` : "—"} sub={`${k.chargeback.cases} cases · ${fmtMoney(k.chargeback.amount_at_risk)} at risk`} good={k.chargeback.win_rate_pct >= 50} />
        <KpiCard icon={Package} label="Low-stock alerts" main={k.low_stock.open_alerts} sub="open" alert={k.low_stock.open_alerts > 0} />
        <KpiCard icon={Clock} label="CI slot reservations" main={k.ci_slots.reservations} sub={`${k.ci_slots.early_paid} early-paid`} />
      </Section>

      <Section title="Distribution & integrations">
        <KpiCard icon={Database} label="PMS-CRS drift" main={k.pms_crs.drift} sub={`${k.pms_crs.pms_bookings} PMS / ${k.pms_crs.crs_records} CRS`} alert={Math.abs(k.pms_crs.drift) > 0} />
        <KpiCard icon={Code} label="API calls" main={k.public_api.calls_in_window} sub={`${k.public_api.active_keys} active keys`} />
        <KpiCard icon={Bell} label="Web push" main={k.web_push.pushes_sent} sub={`${k.web_push.active_subscribers} subscribers`} />
        <KpiCard icon={Mail} label="Pre-arrival drip" main={k.pre_arrival.dispatches} sub={`${k.pre_arrival.sent} sent`} />
        <KpiCard icon={FlaskConical} label="A/B experiments" main={k.ab_test.active_experiments} sub={`${k.ab_test.events_in_window} events`} />
        <KpiCard icon={PoundSterling} label="Folio settlements" main={k.folio_split.settlements_in_window} sub="split-billing" />
      </Section>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wider text-stone-400 mb-2">{title}</div>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">{children}</div>
    </div>
  );
}

function KpiCard({ icon: Icon, label, main, sub, good = false, alert = false }) {
  const cls = alert ? "bg-amber-500/10 border-amber-500/40" :
              good ? "bg-emerald-500/10 border-emerald-500/40" :
              "bg-stone-800/60 border-stone-800";
  const main_cls = alert ? "text-amber-200" : good ? "text-emerald-200" : "text-stone-100";
  return (
    <div className={`p-3 rounded-lg border ${cls}`} data-testid="t1-kpi-card">
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-wider text-stone-400">
        {Icon && <Icon className="w-3 h-3" />} {label}
      </div>
      <div className={`text-xl font-semibold mt-1 ${main_cls}`}>{main}</div>
      {sub && <div className="text-[10px] text-stone-500 mt-0.5">{sub}</div>}
    </div>
  );
}
