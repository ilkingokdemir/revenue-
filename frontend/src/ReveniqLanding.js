import { useState } from "react";
import { motion } from "framer-motion";
import { Toaster } from "sonner";
import {
  ArrowRight, ArrowUpRight, CheckCircle2, Sparkles, TrendingUp,
  LineChart, Radar, Zap, Target, CalendarRange, Sunrise, Menu, X,
  Building2, ShieldCheck, Gauge, SearchX,
} from "lucide-react";
import { DemoForm, FaqItem, fadeUp, goLogin, scrollTo } from "./landing/shared";

const NAV_LINKS = [
  { label: "Features", href: "#features" },
  { label: "How it works", href: "#how" },
  { label: "Pricing", href: "#pricing" },
  { label: "FAQ", href: "#faq" },
];

const TESTIMONIALS = [
  {
    quote: "ReveniQ quietly lifted our RevPAR by double digits in the first season. The morning brief tells me exactly what changed overnight and why — I stopped exporting spreadsheets entirely.",
    name: "Selin Aydın", role: "Revenue Manager", hotel: "Aurora Palace İstanbul · 142 rooms", accent: "from-blue-500 to-cyan-400",
  },
  {
    quote: "The intraday repricing caught a weekend spike at 11am and had us repriced before lunch. That single event paid for the platform for the year.",
    name: "Marco Bianchi", role: "Director of Revenue", hotel: "Harborline Suites · 86 rooms", accent: "from-emerald-500 to-lime-400",
  },
  {
    quote: "I'm not a revenue manager — I'm an owner. Autopilot with guardrails means I set a floor and a ceiling and ReveniQ handles the rest. My rates finally move with the market.",
    name: "Deniz Kaya", role: "Owner", hotel: "Villa Lumen Kaş · 24 rooms", accent: "from-amber-500 to-orange-400",
  },
];

const FAQS = [
  { q: "Is the AI really automatic?", a: "You choose the level of control. Run it in advisory mode where it suggests prices for approval, or full autopilot with guardrails — floor and ceiling rates, maximum daily change, and instant rollback." },
  { q: "Which PMS does it work with?", a: "ReveniQ works natively with MyHotelBox — same data, zero integration effort. Connections to other property management systems are handled during onboarding via our API." },
  { q: "How does the competitor rate radar work?", a: "You define your compset once. ReveniQ scans competitor rates around the clock and flags the dates where you're meaningfully under- or over-priced versus the market median, with a suggested target rate." },
  { q: "What is unconstrained demand and why should I care?", a: "Every request you turn away — sold out, price too high, wrong room type — is demand you never see in your PMS. ReveniQ logs these denials and regrets to reveal your true demand, so you price to what the market wanted, not just what you sold." },
  { q: "How fast will I see results?", a: "The forecast models start learning from your historical data on day one. Most properties see the first meaningful pricing decisions within a week and measurable RevPAR impact within the first full month." },
];

function ForecastMockup() {
  return (
    <div className="relative" data-testid="rq-hero-mockup">
      <div className="absolute -inset-6 bg-gradient-to-br from-[#1D4ED8]/40 via-[#06B6D4]/25 to-[#10B981]/30 rounded-[32px] rotate-2 blur-md" aria-hidden="true" />
      <div className="relative bg-[#111827] rounded-2xl border border-white/10 shadow-[0_24px_80px_rgba(6,182,212,0.25)] overflow-hidden">
        <div className="flex items-center gap-1.5 px-4 py-3 border-b border-white/10">
          <span className="w-2.5 h-2.5 rounded-full bg-[#FF5F57]" />
          <span className="w-2.5 h-2.5 rounded-full bg-[#FEBC2E]" />
          <span className="w-2.5 h-2.5 rounded-full bg-[#28C840]" />
          <span className="ml-3 text-[10px] text-stone-400 font-mono">reveniq · demand forecast</span>
        </div>
        <div className="p-5 space-y-4">
          <div className="grid grid-cols-3 gap-3">
            {[["RevPAR", "€160", "+12.4%", "text-cyan-300"], ["Forecast occ.", "91%", "next 30d", "text-emerald-300"], ["Repriced today", "42", "rates", "text-amber-300"]].map(([l, v, d, c]) => (
              <div key={l} className="bg-white/[0.05] border border-white/10 rounded-xl p-3">
                <div className="text-[9px] uppercase tracking-widest text-stone-400 font-bold">{l}</div>
                <div className={`text-xl font-extrabold tabular-nums mt-0.5 ${c}`}>{v}</div>
                <div className="text-[10px] text-emerald-400 font-bold">{d}</div>
              </div>
            ))}
          </div>
          <div className="bg-white/[0.05] border border-white/10 rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] uppercase tracking-widest text-stone-400 font-bold">30-day forecast · confidence band</span>
              <span className="text-[10px] text-cyan-300 font-bold flex items-center gap-1"><Sparkles size={10} /> 94% accuracy</span>
            </div>
            <svg viewBox="0 0 320 110" className="w-full h-28">
              <defs>
                <linearGradient id="rqLine" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stopColor="#3B82F6" />
                  <stop offset="55%" stopColor="#06B6D4" />
                  <stop offset="100%" stopColor="#10B981" />
                </linearGradient>
                <linearGradient id="rqBand" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stopColor="#1D4ED8" />
                  <stop offset="100%" stopColor="#06B6D4" />
                </linearGradient>
              </defs>
              <polygon points="0,70 40,62 80,66 120,50 160,42 200,48 240,30 280,24 320,30 320,58 280,50 240,58 200,74 160,68 120,76 80,88 40,84 0,92"
                fill="url(#rqBand)" opacity="0.2" />
              <polyline points="0,81 40,73 80,77 120,63 160,55 200,61 240,44 280,37 320,44"
                fill="none" stroke="url(#rqLine)" strokeWidth="3" strokeLinecap="round" />
              <polyline points="0,86 40,80 80,84 120,72 160,66 200,70 240,58 280,52 320,56"
                fill="none" stroke="#78716C" strokeWidth="1.5" strokeDasharray="4 4" />
              <circle cx="240" cy="44" r="5" fill="#06B6D4" />
              <circle cx="240" cy="44" r="9" fill="#06B6D4" opacity="0.25" />
            </svg>
            <div className="flex items-center gap-4 text-[9px] text-stone-400 font-bold uppercase tracking-widest">
              <span className="flex items-center gap-1.5"><span className="w-3 h-0.5 bg-gradient-to-r from-blue-500 to-emerald-400 inline-block rounded" /> AI forecast</span>
              <span className="flex items-center gap-1.5"><span className="w-3 h-0.5 bg-stone-500 inline-block rounded" /> Same time last year</span>
            </div>
          </div>
          <div className="flex items-center gap-2 bg-gradient-to-r from-emerald-500/15 to-cyan-500/10 border border-emerald-500/30 rounded-xl px-3 py-2.5">
            <Zap size={13} className="text-emerald-400 shrink-0" />
            <span className="text-[11px] text-emerald-200">Pickup spike on Sat 14 — repriced +€18, comp median leaves €22 headroom</span>
          </div>
        </div>
      </div>
    </div>
  );
}

const FEATURES = [
  { icon: LineChart, title: "Demand forecasting", desc: "24-month forecast with confidence bands, version control and approval workflow. Know your busy dates before the market does.", c: "bg-blue-500/15 border-blue-400/30 text-blue-400", hover: "hover:border-blue-400/60" },
  { icon: Gauge, title: "AI dynamic pricing", desc: "Prices recalculated continuously with explainable logic — every change tells you why. Advisory mode or full autopilot with guardrails.", c: "bg-cyan-500/15 border-cyan-400/30 text-cyan-400", hover: "hover:border-cyan-400/60" },
  { icon: Zap, title: "Intraday repricing", desc: "Hourly pickup-spike detection reprices within the day, not just overnight. Catch the surge while it's still worth money.", c: "bg-amber-500/15 border-amber-400/30 text-amber-400", hover: "hover:border-amber-400/60" },
  { icon: Radar, title: "Competitor rate radar", desc: "24/7 compset scanning with under/over-priced alerts and target rates versus the market median.", c: "bg-emerald-500/15 border-emerald-400/30 text-emerald-400", hover: "hover:border-emerald-400/60" },
  { icon: Target, title: "Restriction advisor", desc: "AI-suggested MLOS and closed-to-arrival restrictions that protect your shoulder nights around peak dates.", c: "bg-rose-500/15 border-rose-400/30 text-rose-400", hover: "hover:border-rose-400/60" },
  { icon: CalendarRange, title: "Gap-filler campaigns", desc: "Low-occupancy windows detected automatically, promo codes generated, campaigns drafted — with ROI tracked per campaign.", c: "bg-orange-500/15 border-orange-400/30 text-orange-400", hover: "hover:border-orange-400/60" },
  { icon: SearchX, title: "Lost demand tracking", desc: "Denials and regrets logged to reveal unconstrained demand — price to what the market wanted, not just what you sold.", c: "bg-sky-500/15 border-sky-400/30 text-sky-400", hover: "hover:border-sky-400/60" },
  { icon: Sunrise, title: "Morning brief", desc: "Your 8 AM heads-up: pickup, parity issues, overnight AI actions and the dates that need a human eye. Coffee-length reading.", c: "bg-lime-500/15 border-lime-400/30 text-lime-400", hover: "hover:border-lime-400/60" },
];

const STEPS = [
  { n: "01", title: "Connect your data", desc: "Native with MyHotelBox — one click. Other PMS via API during onboarding. Historical bookings, rates and compset flow in automatically.", g: "from-blue-400 to-cyan-300" },
  { n: "02", title: "The AI learns your market", desc: "Forecast models train on your seasonality, pickup curves and competitor behaviour. You review the first suggestions in advisory mode.", g: "from-cyan-300 to-emerald-300" },
  { n: "03", title: "Approve — or let it fly", desc: "Set guardrails (floor, ceiling, max daily change) and switch on autopilot. Every decision stays explainable and reversible.", g: "from-emerald-300 to-lime-300" },
];

export default function ReveniqLanding() {
  const [mobileNav, setMobileNav] = useState(false);
  return (
    <div className="min-h-screen bg-[#0A0F1C] text-white antialiased" data-testid="reveniq-page">
      <Toaster position="top-right" richColors />

      {/* Nav */}
      <header className="sticky top-0 z-50 backdrop-blur-xl bg-[#0A0F1C]/80 border-b border-white/10">
        <div className="max-w-7xl mx-auto px-5 sm:px-8 h-16 flex items-center justify-between">
          <a href="/reveniq" className="flex items-center gap-2.5" data-testid="rq-logo">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#1D4ED8] via-[#06B6D4] to-[#10B981] flex items-center justify-center">
              <TrendingUp size={16} className="text-white" />
            </div>
            <span className="font-extrabold tracking-tight text-lg">Reveni<span className="bg-gradient-to-r from-blue-400 to-cyan-300 bg-clip-text text-transparent">Q</span></span>
          </a>
          <nav className="hidden md:flex items-center gap-7">
            {NAV_LINKS.map((l) => (
              <button key={l.href} onClick={() => scrollTo(l.href)} data-testid={`rq-nav-link-${l.label.toLowerCase().replace(/\s/g, "-")}`}
                className="text-sm font-medium text-stone-400 hover:text-white transition-colors">{l.label}</button>
            ))}
            <a href="/" data-testid="rq-nav-link-myhotelbox"
              className="text-sm font-bold text-cyan-400 hover:text-cyan-300 transition-colors flex items-center gap-1">
              MyHotelBox <ArrowUpRight size={13} />
            </a>
          </nav>
          <div className="hidden md:flex items-center gap-3">
            <button onClick={goLogin} data-testid="rq-signin-btn"
              className="px-4 py-2 rounded-lg text-sm font-bold text-stone-300 border border-white/20 hover:border-cyan-400/60 hover:text-cyan-300 transition-colors">Sign In</button>
            <button onClick={() => scrollTo("#demo")} data-testid="rq-nav-demo-btn"
              className="px-4 py-2 rounded-lg text-sm font-bold bg-gradient-to-r from-[#1D4ED8] to-[#06B6D4] hover:from-[#1E40AF] hover:to-[#0891B2] text-white transition-colors shadow-[0_4px_16px_rgba(6,182,212,0.35)]">Request Demo</button>
          </div>
          <button className="md:hidden p-2" onClick={() => setMobileNav(!mobileNav)} data-testid="rq-mobile-menu-btn">
            {mobileNav ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
        {mobileNav && (
          <div className="md:hidden border-t border-white/10 bg-[#0A0F1C] px-5 py-4 space-y-3" data-testid="rq-mobile-menu">
            {NAV_LINKS.map((l) => (
              <button key={l.href} onClick={() => { setMobileNav(false); scrollTo(l.href); }} className="block text-sm font-medium text-stone-300">{l.label}</button>
            ))}
            <a href="/" className="block text-sm font-bold text-cyan-400">MyHotelBox ↗</a>
            <div className="flex gap-3 pt-2">
              <button onClick={goLogin} className="flex-1 px-4 py-2 rounded-lg text-sm font-bold border border-white/20">Sign In</button>
              <button onClick={() => { setMobileNav(false); scrollTo("#demo"); }} className="flex-1 px-4 py-2 rounded-lg text-sm font-bold bg-[#1D4ED8] text-white">Request Demo</button>
            </div>
          </div>
        )}
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="absolute top-[-140px] left-[-100px] w-[480px] h-[480px] rounded-full bg-[#1D4ED8]/25 blur-3xl" aria-hidden="true" />
        <div className="absolute top-[80px] right-[-140px] w-[520px] h-[520px] rounded-full bg-[#06B6D4]/20 blur-3xl" aria-hidden="true" />
        <div className="absolute bottom-[-160px] left-[35%] w-[400px] h-[400px] rounded-full bg-[#10B981]/15 blur-3xl" aria-hidden="true" />
        <div className="relative max-w-7xl mx-auto px-5 sm:px-8 pt-16 pb-20 lg:pt-24 lg:pb-28 grid lg:grid-cols-12 gap-12 items-center">
          <motion.div className="lg:col-span-6" initial={{ opacity: 0, y: 28 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}>
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-gradient-to-r from-[#1D4ED8]/20 to-[#06B6D4]/15 border border-cyan-400/40 text-cyan-300 text-xs font-bold mb-6" data-testid="rq-hero-badge">
              <Sparkles size={12} /> AI Revenue Management for hotels
            </div>
            <h1 className="text-5xl lg:text-6xl font-extrabold tracking-tighter leading-[1.05]">
              Revenue management<br />
              <span className="bg-gradient-to-r from-blue-400 via-cyan-300 to-emerald-300 bg-clip-text text-transparent">that never sleeps.</span>
            </h1>
            <p className="mt-6 text-lg text-stone-300 leading-relaxed max-w-xl">
              ReveniQ forecasts your demand, watches your competitors and reprices your rooms around the clock — with 15 automation engines, explainable decisions and guardrails you control.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-4">
              <button onClick={() => scrollTo("#demo")} data-testid="rq-hero-demo-btn"
                className="px-7 py-3.5 rounded-lg bg-gradient-to-r from-[#1D4ED8] to-[#06B6D4] hover:from-[#1E40AF] hover:to-[#0891B2] text-white font-bold transition-colors flex items-center gap-2 shadow-[0_8px_28px_rgba(6,182,212,0.4)]">
                Request a demo <ArrowRight size={16} />
              </button>
              <button onClick={() => scrollTo("#features")} data-testid="rq-hero-explore-btn"
                className="px-7 py-3.5 rounded-lg border-2 border-white/25 hover:border-emerald-400/70 hover:text-emerald-300 text-white font-bold transition-colors">
                See the engines
              </button>
            </div>
            <div className="mt-10 flex flex-wrap gap-x-8 gap-y-3">
              {[["+12.4%", "avg. RevPAR lift", "text-emerald-300"], ["94%", "forecast accuracy", "text-cyan-300"], ["38k", "price decisions / week", "text-amber-300"]].map(([v, l, c]) => (
                <div key={l} data-testid={`rq-hero-stat-${l.replace(/[.\s/%]/g, "-")}`}>
                  <div className={`text-2xl font-extrabold tabular-nums ${c}`}>{v}</div>
                  <div className="text-xs text-stone-400 font-medium">{l}</div>
                </div>
              ))}
            </div>
          </motion.div>
          <motion.div className="lg:col-span-6" initial={{ opacity: 0, y: 40 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, delay: 0.15, ease: [0.22, 1, 0.36, 1] }}>
            <ForecastMockup />
          </motion.div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="relative border-t border-white/10 bg-[#0D1424] py-24 overflow-hidden">
        <div className="absolute top-[10%] right-[-120px] w-[400px] h-[400px] rounded-full bg-[#06B6D4]/10 blur-3xl" aria-hidden="true" />
        <div className="relative max-w-7xl mx-auto px-5 sm:px-8">
          <motion.div {...fadeUp} className="max-w-2xl mb-14">
            <div className="text-xs font-bold uppercase tracking-[0.2em] text-cyan-400 mb-3">The engines</div>
            <h2 className="text-3xl lg:text-4xl font-bold tracking-tight">Fifteen automation engines. <span className="bg-gradient-to-r from-cyan-300 to-emerald-300 bg-clip-text text-transparent">One quiet revenue team.</span></h2>
            <p className="mt-4 text-stone-400 leading-relaxed">Every engine runs on schedule, explains its decisions and respects your guardrails. Here are the ones revenue managers ask about first.</p>
          </motion.div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-5">
            {FEATURES.map((f, i) => (
              <motion.div key={f.title} {...fadeUp} transition={{ ...fadeUp.transition, delay: (i % 4) * 0.06 }}
                className={`bg-white/[0.04] border border-white/10 rounded-2xl p-6 hover:-translate-y-1 ${f.hover} transition-[transform,border-color] duration-300`}
                data-testid={`rq-feature-${i}`}>
                <div className={`w-10 h-10 rounded-lg border flex items-center justify-center mb-4 ${f.c}`}>
                  <f.icon size={18} />
                </div>
                <h3 className="text-base font-semibold tracking-tight">{f.title}</h3>
                <p className="mt-2 text-sm text-stone-400 leading-relaxed">{f.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="max-w-7xl mx-auto px-5 sm:px-8 py-24">
        <motion.div {...fadeUp} className="max-w-2xl mb-14">
          <div className="text-xs font-bold uppercase tracking-[0.2em] text-emerald-400 mb-3">How it works</div>
          <h2 className="text-3xl lg:text-4xl font-bold tracking-tight">Live in days. Trusted in weeks.</h2>
        </motion.div>
        <div className="grid md:grid-cols-3 gap-6">
          {STEPS.map((s, i) => (
            <motion.div key={s.n} {...fadeUp} transition={{ ...fadeUp.transition, delay: i * 0.08 }}
              className="relative bg-white/[0.03] border border-white/10 rounded-2xl p-7" data-testid={`rq-step-${i}`}>
              <div className={`text-5xl font-black leading-none font-mono bg-gradient-to-r ${s.g} bg-clip-text text-transparent`}>{s.n}</div>
              <h3 className="mt-4 text-lg font-semibold">{s.title}</h3>
              <p className="mt-2 text-sm text-stone-400 leading-relaxed">{s.desc}</p>
            </motion.div>
          ))}
        </div>
        <motion.div {...fadeUp} className="mt-10 flex items-center gap-3 bg-gradient-to-r from-[#1D4ED8]/15 to-[#06B6D4]/10 border border-cyan-400/25 rounded-2xl px-6 py-5">
          <Building2 size={18} className="text-cyan-400 shrink-0" />
          <p className="text-sm text-stone-300">
            Running your operations on <a href="/" className="font-bold text-cyan-400 hover:text-cyan-300 transition-colors" data-testid="rq-crosssell-mhb-link">MyHotelBox</a>? ReveniQ shares the same data — it switches on in one click, no integration project.
          </p>
        </motion.div>
      </section>

      {/* Testimonials */}
      <section className="border-y border-white/10 bg-[#0D1424] py-24">
        <div className="max-w-7xl mx-auto px-5 sm:px-8">
          <motion.div {...fadeUp} className="max-w-2xl mb-14">
            <div className="text-xs font-bold uppercase tracking-[0.2em] text-amber-400 mb-3">From revenue teams</div>
            <h2 className="text-3xl lg:text-4xl font-bold tracking-tight">The numbers speak. So do the people.</h2>
          </motion.div>
          <div className="grid md:grid-cols-3 gap-6">
            {TESTIMONIALS.map((t, i) => (
              <motion.div key={t.name} {...fadeUp} transition={{ ...fadeUp.transition, delay: i * 0.08 }}
                className={`bg-white/[0.04] rounded-2xl border border-white/10 p-7 ${i === 1 ? "md:mt-10" : ""}`}
                data-testid={`rq-testimonial-${i}`}>
                <div className="text-4xl font-black bg-gradient-to-r from-blue-400 to-cyan-300 bg-clip-text text-transparent leading-none">"</div>
                <p className="text-sm text-stone-300 leading-relaxed mt-2">{t.quote}</p>
                <div className="mt-6 pt-5 border-t border-white/10 flex items-center gap-3">
                  <div className={`w-9 h-9 rounded-full bg-gradient-to-br ${t.accent} flex items-center justify-center text-white text-xs font-black`}>
                    {t.name.split(" ").map((w) => w[0]).join("")}
                  </div>
                  <div>
                    <div className="font-bold text-sm">{t.name}</div>
                    <div className="text-xs text-stone-400">{t.role} · {t.hotel}</div>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="relative max-w-7xl mx-auto px-5 sm:px-8 py-24 overflow-visible">
        <motion.div {...fadeUp} className="max-w-2xl mb-14">
          <div className="text-xs font-bold uppercase tracking-[0.2em] text-cyan-400 mb-3">Pricing</div>
          <h2 className="text-3xl lg:text-4xl font-bold tracking-tight">Pays for itself. <span className="bg-gradient-to-r from-emerald-300 to-lime-300 bg-clip-text text-transparent">Usually in the first month.</span></h2>
          <p className="mt-4 text-stone-400">Per room, per month. Every plan includes model training on your historical data and guardrail setup.</p>
        </motion.div>
        <div className="grid md:grid-cols-3 gap-6 items-start">
          {[
            {
              name: "Essentials", price: "€3", note: "per room / month", accent: "text-emerald-300",
              desc: "Forecasting and pricing advisory for smaller properties.",
              items: ["Demand forecast with confidence bands", "AI price suggestions (advisory mode)", "Morning brief", "Pace & pickup reports"],
              cta: "Start with Essentials", highlight: false,
            },
            {
              name: "Pro", price: "€5", note: "per room / month", accent: "text-white",
              desc: "Full autopilot with every engine switched on.",
              items: ["Everything in Essentials", "Autopilot pricing with guardrails", "Intraday repricing & pickup spikes", "Competitor rate radar 24/7", "Restriction advisor (MLOS/CTA)", "Gap-filler campaigns & lost demand"],
              cta: "Choose Pro", highlight: true,
            },
            {
              name: "Enterprise", price: "Custom", note: "chains & groups", accent: "text-amber-300",
              desc: "Multi-property revenue strategy at scale.",
              items: ["Everything in Pro", "Chain benchmarking & rollups", "Budget vs forecast vs actual", "Custom model tuning & API access", "Dedicated revenue scientist"],
              cta: "Contact Sales", highlight: false,
            },
          ].map((p, i) => (
            <motion.div key={p.name} {...fadeUp} transition={{ ...fadeUp.transition, delay: i * 0.08 }}
              className={`rounded-2xl p-7 border transition-transform duration-300 hover:-translate-y-1 ${p.highlight ? "bg-gradient-to-br from-[#1D4ED8] to-[#0E7490] border-cyan-400/50 shadow-[0_24px_60px_rgba(6,182,212,0.35)] md:-mt-4" : "bg-white/[0.04] border-white/10"}`}
              data-testid={`rq-pricing-${p.name.toLowerCase()}`}>
              {p.highlight && (
                <div className="inline-block px-3 py-1 rounded-full bg-white text-[#1D4ED8] text-[10px] font-bold uppercase tracking-widest mb-4">Most popular</div>
              )}
              <h3 className="text-lg font-bold">{p.name}</h3>
              <div className="mt-3 flex items-baseline gap-2">
                <span className={`text-4xl font-extrabold tabular-nums ${p.highlight ? "text-white" : p.accent}`}>{p.price}</span>
                <span className={`text-xs font-medium ${p.highlight ? "text-cyan-100" : "text-stone-400"}`}>{p.note}</span>
              </div>
              <p className={`mt-2 text-sm ${p.highlight ? "text-cyan-50" : "text-stone-400"}`}>{p.desc}</p>
              <ul className="mt-6 space-y-2.5">
                {p.items.map((it) => (
                  <li key={it} className={`flex items-start gap-2.5 text-sm ${p.highlight ? "text-white" : "text-stone-300"}`}>
                    <CheckCircle2 size={15} className={`mt-0.5 shrink-0 ${p.highlight ? "text-lime-300" : "text-emerald-400"}`} /> {it}
                  </li>
                ))}
              </ul>
              <button onClick={() => scrollTo("#demo")} data-testid={`rq-pricing-cta-${p.name.toLowerCase()}`}
                className={`mt-7 w-full py-3 rounded-lg text-sm font-bold transition-colors ${p.highlight ? "bg-white text-[#1D4ED8] hover:bg-cyan-50" : "border-2 border-white/25 hover:border-cyan-400/70 hover:text-cyan-300 text-white"}`}>
                {p.cta}
              </button>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Demo form */}
      <section id="demo" className="relative border-t border-white/10 bg-[#0D1424] overflow-hidden">
        <div className="absolute top-[-100px] left-[10%] w-[380px] h-[380px] rounded-full bg-[#10B981]/12 blur-3xl" aria-hidden="true" />
        <div className="absolute bottom-[-120px] right-[5%] w-[420px] h-[420px] rounded-full bg-[#1D4ED8]/18 blur-3xl" aria-hidden="true" />
        <div className="relative max-w-7xl mx-auto px-5 sm:px-8 py-24 grid lg:grid-cols-12 gap-12">
          <motion.div {...fadeUp} className="lg:col-span-5">
            <div className="text-xs font-bold uppercase tracking-[0.2em] text-emerald-400 mb-3">Get started</div>
            <h2 className="text-3xl lg:text-4xl font-bold tracking-tight">See ReveniQ <span className="bg-gradient-to-r from-blue-400 to-cyan-300 bg-clip-text text-transparent">price your hotel</span></h2>
            <p className="mt-4 text-stone-400 leading-relaxed">Tell us about your property and we'll run a live demo against your market — your compset, your seasonality, your OTA mix.</p>
            <ul className="mt-8 space-y-3">
              {["30-minute demo with a revenue specialist", "Sample forecast built from your market data", "ROI estimate for your exact room count"].map((t) => (
                <li key={t} className="flex items-center gap-3 text-sm text-stone-300">
                  <CheckCircle2 size={16} className="text-emerald-400 shrink-0" /> {t}
                </li>
              ))}
            </ul>
          </motion.div>
          <motion.div {...fadeUp} className="lg:col-span-7">
            <DemoForm product="rms" dark />
          </motion.div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="max-w-4xl mx-auto px-5 sm:px-8 py-24">
        <motion.div {...fadeUp}>
          <div className="text-xs font-bold uppercase tracking-[0.2em] text-amber-400 mb-3">FAQ</div>
          <h2 className="text-3xl font-bold tracking-tight mb-6">Questions revenue teams ask us</h2>
          {FAQS.map((f, i) => <FaqItem key={f.q} q={f.q} a={f.a} idx={i} dark />)}
        </motion.div>
      </section>

      {/* Footer */}
      <footer className="relative border-t border-white/10 bg-[#070B14] overflow-hidden">
        <div className="absolute top-[-140px] left-[25%] w-[460px] h-[460px] rounded-full bg-[#06B6D4]/15 blur-3xl" aria-hidden="true" />
        <div className="relative max-w-7xl mx-auto px-5 sm:px-8 py-20">
          <div className="grid lg:grid-cols-12 gap-12">
            <div className="lg:col-span-7">
              <h2 className="text-4xl lg:text-5xl font-extrabold tracking-tighter leading-tight">Your rates should<br /><span className="bg-gradient-to-r from-blue-400 via-cyan-300 to-emerald-300 bg-clip-text text-transparent">work the night shift.</span></h2>
              <button onClick={() => scrollTo("#demo")} data-testid="rq-footer-demo-btn"
                className="mt-8 px-7 py-3.5 rounded-lg bg-gradient-to-r from-[#1D4ED8] to-[#06B6D4] hover:from-[#1E40AF] hover:to-[#0891B2] text-white font-bold transition-colors inline-flex items-center gap-2 shadow-[0_8px_28px_rgba(6,182,212,0.35)]">
                Request a demo <ArrowRight size={16} />
              </button>
            </div>
            <div className="lg:col-span-5 grid grid-cols-2 gap-8 text-sm">
              <div>
                <div className="text-xs font-bold uppercase tracking-[0.2em] text-stone-400 mb-4">Product</div>
                <ul className="space-y-2.5 text-[#9CA3AF]">
                  <li><button onClick={() => scrollTo("#features")} className="hover:text-white transition-colors">Features</button></li>
                  <li><button onClick={() => scrollTo("#pricing")} className="hover:text-white transition-colors">Pricing</button></li>
                  <li><button onClick={() => scrollTo("#faq")} className="hover:text-white transition-colors">FAQ</button></li>
                  <li><a href="/" className="hover:text-white transition-colors font-bold text-cyan-400" data-testid="rq-footer-mhb-link">MyHotelBox — Hotel PMS ↗</a></li>
                </ul>
              </div>
              <div>
                <div className="text-xs font-bold uppercase tracking-[0.2em] text-stone-400 mb-4">Company</div>
                <ul className="space-y-2.5 text-[#9CA3AF]">
                  <li><button onClick={goLogin} className="hover:text-white transition-colors" data-testid="rq-footer-signin-btn">Sign In</button></li>
                  <li><button onClick={() => scrollTo("#demo")} className="hover:text-white transition-colors">Contact Sales</button></li>
                </ul>
              </div>
            </div>
          </div>
          <div className="mt-16 pt-8 border-t border-white/10 flex flex-wrap items-center justify-between gap-4 text-xs text-[#9CA3AF]">
            <span>© {new Date().getFullYear()} ReveniQ. All rights reserved.</span>
            <span className="flex items-center gap-2"><ShieldCheck size={13} className="text-emerald-400" /> Explainable AI · Guardrails always on</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
