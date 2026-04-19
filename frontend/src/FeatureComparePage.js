import { useState, useEffect } from "react";
import {
  Check, Minus, Sparkles, Zap, ArrowRight, Shield, Globe, Users,
  MessageSquare, Wallet, Tags, Bot, Building2, X,
} from "lucide-react";

// MyHotelBox vs top competitors. Marks are based on the current public
// feature documentation of each platform as of April 2026. "partial" means
// the competitor has the feature but behind an add-on or in a limited form.
// Update freely — keep claims factual.
const competitors = ["myhotelbox", "mews", "cloudbeds", "eviivo"];
const labels = {
  myhotelbox: "MyHotelBox",
  mews: "Mews",
  cloudbeds: "Cloudbeds",
  eviivo: "Eviivo",
};

const MATRIX = [
  {
    group: "Front Office",
    icon: Building2,
    rows: [
      ["Gantt calendar · drag-to-move · collision detect", "full", "full", "full", "full"],
      ["Today-line, payment-status dots, OOS stripes", "full", "partial", "full", "partial"],
      ["Overbooking real-time alert banner", "full", "partial", "full", "none"],
      ["Self-Service Kiosk (/checkin-kiosk)", "full", "full", "partial", "none"],
      ["Duplicate / Copy booking one-click", "full", "full", "full", "partial"],
      ["Registration Card PDF (legal EU/UK/TR)", "full", "full", "full", "full"],
    ],
  },
  {
    group: "Billing & Finance",
    icon: Wallet,
    rows: [
      ["Split Folios · Set Payer per sub-folio", "full", "full", "partial", "none"],
      ["City Ledger (Corporate AR · 30/60/90 aging)", "full", "full", "full", "partial"],
      ["Multi-currency folios with live FX", "full", "full", "partial", "none"],
      ["41 ISO currencies out of the box", "full", "partial", "partial", "none"],
      ["Multi-currency invoice line items", "full", "partial", "none", "none"],
      ["Tax Configuration (VAT + city tax + resort fee)", "full", "full", "full", "full"],
      ["Deposit Policies with rule evaluator", "full", "full", "partial", "full"],
      ["Profit OS (ContributionPAR, net of OTA commission)", "full", "partial", "none", "none"],
      ["Bank reconciliation + Payroll + Expenses", "full", "full", "partial", "partial"],
    ],
  },
  {
    group: "Commercial / Revenue",
    icon: Tags,
    rows: [
      ["Rate Products (BAR · NR · AP · Corporate · Package)", "full", "full", "full", "full"],
      ["Derived rates (parent ± %, auto-recalc)", "full", "full", "partial", "partial"],
      ["OTA channel-code mapping UI", "full", "full", "full", "partial"],
      ["Promo codes + booking-engine /validate hook", "full", "full", "full", "partial"],
      ["Group bookings with 3 billing modes", "full", "full", "partial", "partial"],
      ["AI Revenue Copilot (Claude Sonnet)", "full", "partial", "none", "none"],
      ["Demand Radar + Compset + Price Alerts", "full", "partial", "partial", "none"],
    ],
  },
  {
    group: "Guest Comms",
    icon: MessageSquare,
    rows: [
      ["Unified Inbox (WhatsApp · SMS · Email · BDC · Airbnb)", "full", "partial", "partial", "partial"],
      ["AI auto-respond (GPT-5.2)", "full", "partial", "none", "none"],
      ["Manual click-to-send (no surprise emails)", "full", "partial", "none", "none"],
      ["Pre-arrival digital check-in + upsell", "full", "full", "full", "full"],
    ],
  },
  {
    group: "Compliance & Ops",
    icon: Shield,
    rows: [
      ["RBAC v2 — 313 permissions, audit trail", "full", "partial", "partial", "none"],
      ["GDPR Art. 17 + 20 (erasure + export)", "full", "partial", "partial", "none"],
      ["Housekeeping auto-dispatch on checkout", "full", "full", "full", "partial"],
      ["Lost & Found · Maintenance tickets", "full", "full", "full", "partial"],
      ["Shift Scheduler + Payroll rate matrix", "full", "partial", "none", "none"],
    ],
  },
  {
    group: "AI & Intelligence",
    icon: Bot,
    rows: [
      ["AI Weekly Digest (natural-language P&L)", "full", "none", "none", "none"],
      ["Smart Scanner (ID OCR on mobile)", "full", "partial", "none", "none"],
      ["Event Intelligence (auto-pricing on concerts)", "full", "none", "none", "none"],
      ["Concierge Analytics (intent mining)", "full", "none", "none", "none"],
    ],
  },
];

const CellMark = ({ mark }) => {
  if (mark === "full")
    return (
      <div className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-emerald-400/10 border border-emerald-400/30">
        <Check className="w-4 h-4 text-emerald-400" strokeWidth={3} />
      </div>
    );
  if (mark === "partial")
    return (
      <div className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-amber-400/10 border border-amber-400/30" title="Partial / add-on">
        <Minus className="w-4 h-4 text-amber-400" strokeWidth={3} />
      </div>
    );
  return (
    <div className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-white/5 border border-white/10" title="Not available">
      <X className="w-3.5 h-3.5 text-stone-500" strokeWidth={3} />
    </div>
  );
};

// Count our advantage per group (rows where myhotelbox=full but ≥1 competitor <full)
const advantageFor = (rows) =>
  rows.filter(([, us, ...rest]) => us === "full" && rest.some((m) => m !== "full")).length;

export default function FeatureComparePage() {
  const [activeGroup, setActiveGroup] = useState(null);

  useEffect(() => {
    const prevTitle = document.title;
    document.title = "Feature scorecard vs Mews · Cloudbeds · Eviivo — MyHotelBox";
    const ogImg = `${process.env.REACT_APP_BACKEND_URL}/api/og/compare.png`;
    const tags = [
      ["property", "og:title", "Feature scorecard vs the top PMS platforms"],
      ["property", "og:description", "Independent audit of MyHotelBox vs Mews, Cloudbeds, and Eviivo. Every production feature mapped side-by-side."],
      ["property", "og:image", ogImg],
      ["name", "twitter:title", "Feature scorecard vs the top PMS platforms"],
      ["name", "twitter:image", ogImg],
      ["name", "description", "MyHotelBox feature comparison — independent audit vs Mews, Cloudbeds, Eviivo."],
    ];
    tags.forEach(([attr, val, content]) => {
      let el = document.querySelector(`meta[${attr}="${val}"]`);
      if (!el) {
        el = document.createElement("meta");
        el.setAttribute(attr, val);
        document.head.appendChild(el);
      }
      el.setAttribute("content", content);
    });
    return () => { document.title = prevTitle; };
  }, []);

  const totals = competitors.reduce((acc, c, idx) => {
    let full = 0, partial = 0, none = 0;
    MATRIX.forEach(({ rows }) => rows.forEach((r) => {
      const v = r[1 + idx];
      if (v === "full") full++;
      else if (v === "partial") partial++;
      else none++;
    }));
    acc[c] = { full, partial, none, score: full * 2 + partial };
    return acc;
  }, {});
  const topScore = Math.max(...Object.values(totals).map((t) => t.score));

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-stone-100 selection:bg-fuchsia-500/40">
      {/* grain + glow */}
      <div className="pointer-events-none fixed inset-0 opacity-[0.15]" style={{
        backgroundImage:
          "radial-gradient(600px circle at 30% 10%, rgba(217, 70, 239, 0.25), transparent 50%), radial-gradient(500px circle at 80% 30%, rgba(99, 102, 241, 0.25), transparent 50%)",
      }} />
      <div className="pointer-events-none fixed inset-0 opacity-[0.04]" style={{
        backgroundImage:
          "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='4' height='4'><circle cx='2' cy='2' r='1' fill='white'/></svg>\")",
      }} />

      {/* HERO */}
      <header className="relative max-w-7xl mx-auto px-6 pt-20 pb-12">
        <div className="inline-flex items-center gap-2 text-[11px] font-bold uppercase tracking-[0.2em] text-fuchsia-400 mb-6">
          <Sparkles className="w-3.5 h-3.5" />Independent Feature Audit · Q2 2026
        </div>
        <h1 className="text-5xl md:text-7xl font-black leading-[0.95] tracking-tight">
          Every feature that <span className="text-fuchsia-400">actually matters</span>,<br />
          side by side.
        </h1>
        <p className="mt-6 text-lg text-stone-400 max-w-2xl">
          We audited the public documentation of the four leading independent-hotel PMS platforms
          and mapped every production feature. Here's the honest picture.
        </p>

        {/* Score cards */}
        <div className="mt-10 grid grid-cols-2 md:grid-cols-4 gap-3">
          {competitors.map((c) => {
            const t = totals[c];
            const isTop = t.score === topScore;
            return (
              <div key={c} data-testid={`compare-score-${c}`}
                className={`relative rounded-2xl p-5 border backdrop-blur-xl ${
                  isTop
                    ? "bg-gradient-to-br from-fuchsia-500/20 via-indigo-500/10 to-transparent border-fuchsia-400/40"
                    : "bg-white/[0.02] border-white/10"
                }`}>
                {isTop && (
                  <div className="absolute -top-2.5 left-5 inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] font-bold tracking-widest uppercase bg-fuchsia-500 text-white">
                    <Zap className="w-3 h-3" />Leader
                  </div>
                )}
                <div className="text-xs text-stone-400 font-semibold uppercase tracking-wider">{labels[c]}</div>
                <div className={`mt-1 text-4xl font-black ${isTop ? "text-fuchsia-300" : "text-stone-200"}`}>
                  {t.score}
                </div>
                <div className="mt-2 flex gap-3 text-[11px] text-stone-400">
                  <span><span className="text-emerald-400 font-bold">{t.full}</span> full</span>
                  <span><span className="text-amber-400 font-bold">{t.partial}</span> partial</span>
                  <span><span className="text-stone-500 font-bold">{t.none}</span> none</span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Legend */}
        <div className="mt-8 flex flex-wrap items-center gap-5 text-xs text-stone-400">
          <span className="flex items-center gap-2"><CellMark mark="full" />Full native support</span>
          <span className="flex items-center gap-2"><CellMark mark="partial" />Partial / add-on</span>
          <span className="flex items-center gap-2"><CellMark mark="none" />Not available</span>
          <span className="ml-auto text-stone-500 font-mono text-[11px]">
            Score = 2×full + 1×partial · 0×none
          </span>
        </div>
      </header>

      {/* MATRIX */}
      <main className="relative max-w-7xl mx-auto px-6 pb-32 space-y-10">
        {MATRIX.map((section) => {
          const adv = advantageFor(section.rows);
          return (
            <section key={section.group} data-testid={`compare-section-${section.group}`}
              className="rounded-3xl border border-white/10 bg-white/[0.02] backdrop-blur-xl overflow-hidden">
              <button
                onClick={() => setActiveGroup(activeGroup === section.group ? null : section.group)}
                className="w-full flex items-center justify-between px-6 py-5 hover:bg-white/[0.02] transition-colors">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-xl bg-fuchsia-500/10 border border-fuchsia-500/20">
                    <section.icon className="w-5 h-5 text-fuchsia-400" />
                  </div>
                  <div className="text-left">
                    <h2 className="text-xl font-bold text-stone-100">{section.group}</h2>
                    <p className="text-xs text-stone-500 mt-0.5">{section.rows.length} features</p>
                  </div>
                </div>
                {adv > 0 && (
                  <div className="flex items-center gap-2 text-xs text-fuchsia-300 font-bold">
                    <span className="px-2 py-1 rounded-full bg-fuchsia-500/10 border border-fuchsia-500/30">
                      {adv} rows where we lead
                    </span>
                    <ArrowRight className={`w-4 h-4 transition-transform ${activeGroup === section.group ? "rotate-90" : ""}`} />
                  </div>
                )}
              </button>

              {(activeGroup === null || activeGroup === section.group) && (
                <div className="border-t border-white/10">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-[10px] uppercase tracking-wider text-stone-500 border-b border-white/5">
                        <th className="p-4 text-left font-bold w-[44%]">Feature</th>
                        {competitors.map((c) => (
                          <th key={c} className={`p-4 text-center font-bold ${c === "myhotelbox" ? "text-fuchsia-400" : "text-stone-400"}`}>
                            {labels[c]}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {section.rows.map((row, i) => {
                        const [feature, us, ...rest] = row;
                        const weLead = us === "full" && rest.some((m) => m !== "full");
                        return (
                          <tr key={i}
                            className={`border-b border-white/5 last:border-0 transition-colors ${
                              weLead ? "hover:bg-fuchsia-500/[0.03]" : "hover:bg-white/[0.02]"
                            }`}>
                            <td className="p-4 text-stone-300">
                              {feature}
                              {weLead && (
                                <span className="ml-2 text-[10px] text-fuchsia-400 font-bold uppercase tracking-wider">· lead</span>
                              )}
                            </td>
                            {row.slice(1).map((mark, idx) => (
                              <td key={idx} className="p-4 text-center">
                                <CellMark mark={mark} />
                              </td>
                            ))}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          );
        })}

        {/* CTA */}
        <div className="relative mt-20 rounded-3xl p-10 md:p-16 border border-fuchsia-500/30 bg-gradient-to-br from-fuchsia-500/15 via-indigo-500/10 to-transparent overflow-hidden">
          <div className="absolute -top-20 -right-20 w-96 h-96 rounded-full bg-fuchsia-500/20 blur-3xl" />
          <div className="relative">
            <h3 className="text-3xl md:text-5xl font-black tracking-tight">
              Switching PMS? <span className="text-fuchsia-300">We'll migrate you in a weekend.</span>
            </h3>
            <p className="mt-4 text-stone-300 text-lg max-w-2xl">
              Every row above is live in the product today. We don't promise roadmaps —
              we ship. Book a 20-minute live demo and see for yourself.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <a href="/book" data-testid="compare-cta-book"
                className="inline-flex items-center gap-2 px-6 py-3.5 rounded-xl bg-fuchsia-500 hover:bg-fuchsia-400 text-white font-bold text-sm transition-all hover:-translate-y-0.5 shadow-[0_10px_40px_-10px_rgba(217,70,239,0.6)]">
                Book a live demo <ArrowRight className="w-4 h-4" />
              </a>
              <a href="/" data-testid="compare-cta-signin"
                className="inline-flex items-center gap-2 px-6 py-3.5 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-stone-200 font-bold text-sm transition-all">
                Sign in to dashboard
              </a>
            </div>
            <div className="mt-8 flex flex-wrap items-center gap-6 text-[11px] text-stone-400 uppercase tracking-wider font-semibold">
              <span className="flex items-center gap-1.5"><Globe className="w-3.5 h-3.5" />41 currencies</span>
              <span className="flex items-center gap-1.5"><Users className="w-3.5 h-3.5" />Group bookings</span>
              <span className="flex items-center gap-1.5"><Shield className="w-3.5 h-3.5" />GDPR ready</span>
              <span className="flex items-center gap-1.5"><Bot className="w-3.5 h-3.5" />AI Revenue Copilot</span>
            </div>
          </div>
        </div>

        <p className="text-center text-xs text-stone-600 pt-10">
          Based on publicly-available product documentation of each platform. Last audit: April 2026.
          Questions? <a href="mailto:hello@myhotelbox.com" className="text-stone-400 hover:text-fuchsia-400 underline">hello@myhotelbox.com</a>
        </p>
      </main>
    </div>
  );
}
