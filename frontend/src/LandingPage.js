import { useState } from "react";
import axios from "axios";
import { motion } from "framer-motion";
import { Toaster, toast } from "sonner";
import {
  ArrowRight, ArrowUpRight, CheckCircle2, ChevronDown, Sparkles,
  CalendarCheck, TrendingUp, Globe2, MessageSquareText, BedDouble,
  BarChart3, CreditCard, Zap, ShieldCheck, Building2, Menu, X,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const fadeUp = {
  initial: { opacity: 0, y: 24 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-60px" },
  transition: { duration: 0.55, ease: [0.22, 1, 0.36, 1] },
};

const NAV_LINKS = [
  { label: "Product", href: "#product" },
  { label: "Revenue AI", href: "#revenue" },
  { label: "Pricing", href: "#pricing" },
  { label: "FAQ", href: "#faq" },
];

const TRUST_NAMES = [
  "Aurora Palace İstanbul", "The Meridian Bodrum", "Casa Verde Antalya",
  "Harborline Suites", "Stonebridge Boutique", "Villa Lumen Kaş",
  "Grand Anatolia Resort", "The Olive & Fig Hotel", "Blue Slate Residences",
];

const TESTIMONIALS = [
  {
    quote: "We replaced four separate tools with one platform. Our front desk closes night audit in minutes and the AI pricing quietly lifted our RevPAR by double digits in the first season.",
    name: "Selin Aydın", role: "General Manager", hotel: "Aurora Palace İstanbul · 142 rooms",
  },
  {
    quote: "The morning brief is the first thing I read every day. Pickup, parity issues, gap dates — it tells me exactly where to look before my coffee is done.",
    name: "Marco Bianchi", role: "Revenue Manager", hotel: "Harborline Suites · 86 rooms",
  },
  {
    quote: "Guests check in from their phone, housekeeping gets tasks automatically, and I finally see clean P&L numbers per outlet. It feels like hiring three extra people.",
    name: "Deniz Kaya", role: "Owner", hotel: "Villa Lumen Kaş · 24 rooms",
  },
];

const FAQS = [
  { q: "How long does onboarding take?", a: "Most independent hotels go live in under two weeks. We migrate your reservations, rate plans and OTA connections, and your team gets guided training inside the product with the built-in academy." },
  { q: "Does it connect to Booking.com, Expedia and other OTAs?", a: "Yes. The channel manager keeps availability, rates and restrictions in sync in real time across all major OTAs, with parity monitoring that alerts you when a channel undercuts your direct price." },
  { q: "Is the AI revenue management really automatic?", a: "You choose the level of control. Run it in advisory mode where it suggests prices for approval, or full autopilot with guardrails — floor and ceiling rates, max daily change, and instant rollback." },
  { q: "Can I use only the PMS without the revenue tools?", a: "Absolutely. Start with the Starter plan for core operations, and switch on ReveniQ revenue intelligence whenever you're ready — your data is already in place." },
  { q: "What about my existing payment provider?", a: "Built-in payments support cards, payment links, terminals and OTA virtual cards. If you prefer your current provider, we integrate with it during onboarding." },
];

function MiniBar({ h, c }) {
  return <div className={`w-full rounded-sm ${c}`} style={{ height: `${h}%` }} />;
}

function DashboardMockup() {
  const bars = [42, 58, 50, 66, 74, 62, 82, 90, 78, 88, 96, 84];
  return (
    <div className="relative" data-testid="hero-dashboard-mockup">
      <div className="absolute -inset-6 bg-[#1D4ED8]/8 rounded-[32px] rotate-2" aria-hidden="true" />
      <div className="relative bg-[#0A0F1C] rounded-2xl border border-white/10 shadow-[0_24px_80px_rgba(10,15,28,0.35)] overflow-hidden">
        <div className="flex items-center gap-1.5 px-4 py-3 border-b border-white/10">
          <span className="w-2.5 h-2.5 rounded-full bg-[#E07A5F]" />
          <span className="w-2.5 h-2.5 rounded-full bg-[#E5C05F]" />
          <span className="w-2.5 h-2.5 rounded-full bg-[#849B89]" />
          <span className="ml-3 text-[10px] text-stone-400 font-mono">reveniq · live dashboard</span>
        </div>
        <div className="p-5 space-y-4">
          <div className="grid grid-cols-3 gap-3">
            {[["Occupancy", "87%", "+6 pts"], ["ADR", "€184", "+€11"], ["RevPAR", "€160", "+12.4%"]].map(([l, v, d]) => (
              <div key={l} className="bg-white/[0.04] border border-white/10 rounded-xl p-3">
                <div className="text-[9px] uppercase tracking-widest text-stone-400 font-bold">{l}</div>
                <div className="text-xl font-extrabold text-white tabular-nums mt-0.5">{v}</div>
                <div className="text-[10px] text-emerald-400 font-bold">{d}</div>
              </div>
            ))}
          </div>
          <div className="bg-white/[0.04] border border-white/10 rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <span className="text-[10px] uppercase tracking-widest text-stone-400 font-bold">Next 12 days · AI price</span>
              <span className="text-[10px] text-blue-300 font-bold flex items-center gap-1"><Sparkles size={10} /> autopilot on</span>
            </div>
            <div className="flex items-end gap-1.5 h-24">
              {bars.map((h, i) => (
                <MiniBar key={i} h={h} c={i >= 7 ? "bg-blue-500" : "bg-stone-600"} />
              ))}
            </div>
          </div>
          <div className="flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/25 rounded-xl px-3 py-2.5">
            <Zap size={13} className="text-emerald-400 shrink-0" />
            <span className="text-[11px] text-emerald-200">Weekend spike detected — 14 rates repriced, est. +€2,340 revenue</span>
          </div>
        </div>
      </div>
    </div>
  );
}

const FEATURES = [
  {
    span: "md:col-span-7", icon: CalendarCheck, label: "Property Management",
    title: "Front desk, reservations & housekeeping in one calm screen",
    desc: "Drag-and-drop room calendar, group bookings, digital check-in kiosk, housekeeping auto-dispatch and a night audit that runs itself. Your team stops juggling tabs.",
    img: "https://images.unsplash.com/photo-1759038085950-1234ca8f5fed?crop=entropy&cs=srgb&fm=jpg&q=85&w=1200",
    testid: "feature-pms",
  },
  {
    span: "md:col-span-5", dark: true, icon: TrendingUp, label: "ReveniQ · Revenue AI",
    title: "Prices that move before the market does",
    desc: "15 automation engines: demand forecasting with confidence bands, intraday repricing, competitor rate radar, gap-filler campaigns and restriction advisor — all explainable, all with guardrails.",
    testid: "feature-revenue",
  },
  {
    span: "md:col-span-4", icon: Globe2, label: "Distribution",
    title: "Direct bookings & OTA sync",
    desc: "Commission-free booking engine with promo codes, plus real-time channel manager and rate-parity monitoring across every OTA.",
    testid: "feature-booking",
  },
  {
    span: "md:col-span-4", icon: MessageSquareText, label: "Guest Experience",
    title: "One inbox for every guest",
    desc: "WhatsApp, email and SMS unified with AI-drafted replies, pre-arrival journeys, upsell offers and post-stay review autopilot.",
    img: "https://images.unsplash.com/photo-1713865470192-efd903813197?crop=entropy&cs=srgb&fm=jpg&q=85&w=800",
    testid: "feature-guest",
  },
  {
    span: "md:col-span-4", icon: BarChart3, label: "Finance & Reports",
    title: "Numbers your accountant will love",
    desc: "P&L per outlet, budget vs forecast vs actual, OTA commission reconciliation, city ledger and scheduled reports to your inbox.",
    testid: "feature-finance",
  },
];

const CHIPS = [
  [BedDouble, "Housekeeping mobile app"], [CreditCard, "Payments & terminals"],
  [Building2, "Multi-property & chains"], [ShieldCheck, "Role-based access"],
  [Zap, "POS · F&B · spa & events"], [Sparkles, "AI morning brief"],
];

function DemoForm() {
  const [form, setForm] = useState({ name: "", email: "", hotel_name: "", room_count: "", message: "" });
  const [sending, setSending] = useState(false);
  const [done, setDone] = useState(false);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    if (!form.name || !form.email || !form.hotel_name) {
      toast.error("Please fill in your name, email and hotel name");
      return;
    }
    setSending(true);
    try {
      await axios.post(`${API}/public/demo-requests`, form);
      setDone(true);
      toast.success("Thanks! Our team will reach out within one business day.");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Something went wrong — please try again");
    } finally {
      setSending(false);
    }
  };

  if (done) {
    return (
      <div className="bg-white rounded-2xl border border-black/5 p-10 text-center shadow-[0_8px_32px_rgba(29,78,216,0.08)]" data-testid="demo-form-success">
        <CheckCircle2 size={40} className="mx-auto text-emerald-500 mb-4" />
        <h3 className="text-xl font-bold text-stone-900">Request received</h3>
        <p className="text-sm text-stone-500 mt-2">We'll email {form.email} to schedule your personalised demo.</p>
      </div>
    );
  }

  const inputCls = "w-full rounded-lg border border-stone-200 bg-[#FDFCFB] px-3.5 py-2.5 text-sm text-stone-900 placeholder:text-stone-400 focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]/40 focus:border-[#1D4ED8] transition-colors";
  return (
    <form onSubmit={submit} className="bg-white rounded-2xl border border-black/5 p-6 sm:p-8 shadow-[0_8px_32px_rgba(29,78,216,0.08)] space-y-4" data-testid="demo-request-form">
      <div className="grid sm:grid-cols-2 gap-4">
        <div>
          <label className="text-xs font-bold uppercase tracking-[0.15em] text-stone-500">Full name *</label>
          <input value={form.name} onChange={set("name")} placeholder="Jane Smith" className={`${inputCls} mt-1.5`} data-testid="demo-form-name" />
        </div>
        <div>
          <label className="text-xs font-bold uppercase tracking-[0.15em] text-stone-500">Work email *</label>
          <input type="email" value={form.email} onChange={set("email")} placeholder="jane@yourhotel.com" className={`${inputCls} mt-1.5`} data-testid="demo-form-email" />
        </div>
        <div>
          <label className="text-xs font-bold uppercase tracking-[0.15em] text-stone-500">Hotel name *</label>
          <input value={form.hotel_name} onChange={set("hotel_name")} placeholder="The Grand Hotel" className={`${inputCls} mt-1.5`} data-testid="demo-form-hotel" />
        </div>
        <div>
          <label className="text-xs font-bold uppercase tracking-[0.15em] text-stone-500">Rooms</label>
          <select value={form.room_count} onChange={set("room_count")} className={`${inputCls} mt-1.5`} data-testid="demo-form-rooms">
            <option value="">Select…</option>
            <option value="1-20">1 – 20</option>
            <option value="21-50">21 – 50</option>
            <option value="51-120">51 – 120</option>
            <option value="121-300">121 – 300</option>
            <option value="300+">300+</option>
          </select>
        </div>
      </div>
      <div>
        <label className="text-xs font-bold uppercase tracking-[0.15em] text-stone-500">Anything specific you'd like to see?</label>
        <textarea value={form.message} onChange={set("message")} rows={3} placeholder="e.g. AI pricing, channel manager, group bookings…" className={`${inputCls} mt-1.5 resize-none`} data-testid="demo-form-message" />
      </div>
      <button type="submit" disabled={sending} data-testid="demo-form-submit"
        className="w-full sm:w-auto px-8 py-3 rounded-lg bg-[#1D4ED8] hover:bg-[#1E40AF] text-white text-sm font-bold transition-colors disabled:opacity-60 flex items-center justify-center gap-2">
        {sending ? "Sending…" : "Request my demo"} <ArrowRight size={15} />
      </button>
      <p className="text-[11px] text-stone-400">No credit card required · 30-minute personalised walkthrough · Replies within one business day</p>
    </form>
  );
}

function FaqItem({ q, a, idx }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-b border-stone-200">
      <button onClick={() => setOpen(!open)} data-testid={`faq-item-${idx}`}
        className="w-full flex items-center justify-between gap-4 py-5 text-left group">
        <span className="text-base font-semibold text-stone-900 group-hover:text-[#1D4ED8] transition-colors">{q}</span>
        <ChevronDown size={18} className={`shrink-0 text-stone-400 transition-transform duration-200 ${open ? "rotate-180" : ""}`} />
      </button>
      {open && <p className="pb-5 text-sm text-stone-600 leading-relaxed max-w-3xl">{a}</p>}
    </div>
  );
}

const goLogin = () => { window.location.href = "/login"; };
const scrollTo = (id) => document.querySelector(id)?.scrollIntoView({ behavior: "smooth" });

export default function LandingPage() {
  const [mobileNav, setMobileNav] = useState(false);
  return (
    <div className="min-h-screen bg-[#FDFCFB] text-stone-900 antialiased" data-testid="landing-page">
      <Toaster position="top-right" richColors />

      {/* Nav */}
      <header className="sticky top-0 z-50 backdrop-blur-xl bg-[#FDFCFB]/80 border-b border-black/5">
        <div className="max-w-7xl mx-auto px-5 sm:px-8 h-16 flex items-center justify-between">
          <a href="/" className="flex items-center gap-2.5" data-testid="landing-logo">
            <div className="w-8 h-8 rounded-lg bg-[#0A0F1C] flex items-center justify-center">
              <Building2 size={16} className="text-white" />
            </div>
            <span className="font-extrabold tracking-tight text-lg">MyHotelBox <span className="text-[#1D4ED8]">&amp; ReveniQ</span></span>
          </a>
          <nav className="hidden md:flex items-center gap-7">
            {NAV_LINKS.map((l) => (
              <button key={l.href} onClick={() => scrollTo(l.href)} data-testid={`nav-link-${l.label.toLowerCase().replace(/\s/g, "-")}`}
                className="text-sm font-medium text-stone-600 hover:text-stone-900 transition-colors">{l.label}</button>
            ))}
          </nav>
          <div className="hidden md:flex items-center gap-3">
            <button onClick={goLogin} data-testid="landing-signin-btn"
              className="px-4 py-2 rounded-lg text-sm font-bold text-stone-700 border border-stone-300 hover:border-stone-500 transition-colors">Sign In</button>
            <button onClick={() => scrollTo("#demo")} data-testid="landing-nav-demo-btn"
              className="px-4 py-2 rounded-lg text-sm font-bold bg-[#1D4ED8] hover:bg-[#1E40AF] text-white transition-colors">Request Demo</button>
          </div>
          <button className="md:hidden p-2" onClick={() => setMobileNav(!mobileNav)} data-testid="landing-mobile-menu-btn">
            {mobileNav ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
        {mobileNav && (
          <div className="md:hidden border-t border-black/5 bg-[#FDFCFB] px-5 py-4 space-y-3" data-testid="landing-mobile-menu">
            {NAV_LINKS.map((l) => (
              <button key={l.href} onClick={() => { setMobileNav(false); scrollTo(l.href); }} className="block text-sm font-medium text-stone-700">{l.label}</button>
            ))}
            <div className="flex gap-3 pt-2">
              <button onClick={goLogin} className="flex-1 px-4 py-2 rounded-lg text-sm font-bold border border-stone-300">Sign In</button>
              <button onClick={() => { setMobileNav(false); scrollTo("#demo"); }} className="flex-1 px-4 py-2 rounded-lg text-sm font-bold bg-[#1D4ED8] text-white">Request Demo</button>
            </div>
          </div>
        )}
      </header>

      {/* Hero */}
      <section className="max-w-7xl mx-auto px-5 sm:px-8 pt-16 pb-20 lg:pt-24 lg:pb-28 grid lg:grid-cols-12 gap-12 items-center">
        <motion.div className="lg:col-span-6" initial={{ opacity: 0, y: 28 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}>
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-[#1D4ED8]/8 border border-[#1D4ED8]/20 text-[#1D4ED8] text-xs font-bold mb-6" data-testid="hero-badge">
            <Sparkles size={12} /> PMS + AI Revenue Management, finally together
          </div>
          <h1 className="text-5xl lg:text-6xl font-extrabold tracking-tighter leading-[1.05]">
            Run your hotel.<br />
            <span className="text-[#1D4ED8]">The revenue runs itself.</span>
          </h1>
          <p className="mt-6 text-lg text-stone-600 leading-relaxed max-w-xl">
            MyHotelBox handles front desk, housekeeping, bookings and payments. ReveniQ's AI reprices your rooms around the clock — forecasting demand, watching competitors, and filling the gaps you didn't know you had.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-4">
            <button onClick={() => scrollTo("#demo")} data-testid="hero-request-demo-btn"
              className="px-7 py-3.5 rounded-lg bg-[#1D4ED8] hover:bg-[#1E40AF] text-white font-bold transition-colors flex items-center gap-2">
              Request a demo <ArrowRight size={16} />
            </button>
            <button onClick={() => scrollTo("#product")} data-testid="hero-explore-btn"
              className="px-7 py-3.5 rounded-lg border border-stone-300 hover:border-stone-500 text-stone-800 font-bold transition-colors">
              Explore the platform
            </button>
          </div>
          <div className="mt-10 flex flex-wrap gap-x-8 gap-y-3">
            {[["+12.4%", "avg. RevPAR lift"], ["15", "automation engines"], ["2 wks", "typical go-live"]].map(([v, l]) => (
              <div key={l} data-testid={`hero-stat-${l.replace(/[.\s]/g, "-")}`}>
                <div className="text-2xl font-extrabold tabular-nums text-stone-900">{v}</div>
                <div className="text-xs text-stone-500 font-medium">{l}</div>
              </div>
            ))}
          </div>
        </motion.div>
        <motion.div className="lg:col-span-6" initial={{ opacity: 0, y: 40 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, delay: 0.15, ease: [0.22, 1, 0.36, 1] }}>
          <DashboardMockup />
        </motion.div>
      </section>

      {/* Trust marquee */}
      <section className="border-y border-black/5 bg-[#F5F4F0] py-6 overflow-hidden" data-testid="trust-bar">
        <div className="landing-marquee flex items-center gap-12 whitespace-nowrap">
          {[...TRUST_NAMES, ...TRUST_NAMES].map((n, i) => (
            <span key={i} className="text-sm font-bold tracking-wide text-stone-400 uppercase">{n}</span>
          ))}
        </div>
      </section>

      {/* Features bento */}
      <section id="product" className="max-w-7xl mx-auto px-5 sm:px-8 py-24">
        <motion.div {...fadeUp} className="max-w-2xl mb-14">
          <div className="text-xs font-bold uppercase tracking-[0.2em] text-[#1D4ED8] mb-3">The platform</div>
          <h2 className="text-3xl lg:text-4xl font-bold tracking-tight">Everything a modern hotel needs. Nothing it doesn't.</h2>
          <p className="mt-4 text-stone-600 leading-relaxed">One login for operations, distribution, guest experience and finance — built to replace the patchwork of tools your team fights with today.</p>
        </motion.div>
        <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
          {FEATURES.map((f, i) => (
            <motion.div key={f.testid} {...fadeUp} transition={{ ...fadeUp.transition, delay: i * 0.06 }}
              className={`${f.span} rounded-2xl border overflow-hidden group hover:-translate-y-1 transition-transform duration-300 ${f.dark ? "bg-[#0A0F1C] border-white/10 text-white" : "bg-white border-black/5 shadow-[0_8px_32px_rgba(29,78,216,0.05)]"}`}
              data-testid={f.testid}>
              <div className="p-7">
                <div className={`inline-flex items-center gap-2 text-xs font-bold uppercase tracking-[0.18em] mb-4 ${f.dark ? "text-blue-300" : "text-[#1D4ED8]"}`}>
                  <f.icon size={14} /> {f.label}
                </div>
                <h3 className={`text-xl lg:text-2xl font-semibold tracking-tight ${f.dark ? "text-white" : "text-stone-900"}`}>{f.title}</h3>
                <p className={`mt-3 text-sm leading-relaxed ${f.dark ? "text-stone-300" : "text-stone-600"}`}>{f.desc}</p>
                {f.dark && (
                  <div className="mt-6 grid grid-cols-2 gap-3">
                    {[["Forecast accuracy", "94%"], ["Prices/day", "1,400+"], ["Comp radar", "24/7"], ["Guardrails", "Always"]].map(([l, v]) => (
                      <div key={l} className="bg-white/[0.05] border border-white/10 rounded-lg px-3 py-2.5">
                        <div className="text-lg font-extrabold text-white">{v}</div>
                        <div className="text-[10px] text-stone-400 uppercase tracking-widest font-bold">{l}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              {f.img && (
                <div className="h-48 overflow-hidden">
                  <img src={f.img} alt={f.label} loading="lazy" className="w-full h-full object-cover group-hover:scale-[1.03] transition-transform duration-500" />
                </div>
              )}
            </motion.div>
          ))}
        </div>
        <motion.div {...fadeUp} className="mt-8 flex flex-wrap gap-3">
          {CHIPS.map(([Icon, label]) => (
            <span key={label} className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-[#F5F4F0] border border-black/5 text-sm font-medium text-stone-700">
              <Icon size={14} className="text-[#1D4ED8]" /> {label}
            </span>
          ))}
        </motion.div>
      </section>

      {/* Revenue dark section */}
      <section id="revenue" className="bg-[#0A0F1C] text-white py-24">
        <div className="max-w-7xl mx-auto px-5 sm:px-8 grid lg:grid-cols-12 gap-12 items-center">
          <motion.div {...fadeUp} className="lg:col-span-5">
            <div className="text-xs font-bold uppercase tracking-[0.2em] text-blue-300 mb-3">ReveniQ · Revenue Intelligence</div>
            <h2 className="text-3xl lg:text-4xl font-bold tracking-tight">Your best revenue manager never sleeps</h2>
            <p className="mt-4 text-stone-300 leading-relaxed">Every night it forecasts. Every hour it scans pickup and competitor rates. Every morning it hands you a brief with exactly what changed and why — then acts on it, within the limits you set.</p>
            <ul className="mt-8 space-y-4">
              {[
                "Demand forecast with confidence bands & version approvals",
                "Intraday repricing on pickup spikes — not just nightly runs",
                "Competitor rate radar with under/over-priced alerts",
                "AI gap-filler campaigns with promo codes & ROI tracking",
                "Lost-demand tracking to reveal unconstrained demand",
              ].map((t) => (
                <li key={t} className="flex items-start gap-3 text-sm text-stone-200">
                  <CheckCircle2 size={16} className="text-emerald-400 mt-0.5 shrink-0" /> {t}
                </li>
              ))}
            </ul>
            <button onClick={() => scrollTo("#demo")} data-testid="revenue-cta-btn"
              className="mt-9 px-6 py-3 rounded-lg bg-[#1D4ED8] hover:bg-[#1E40AF] text-white text-sm font-bold transition-colors inline-flex items-center gap-2">
              See it price your hotel <ArrowUpRight size={15} />
            </button>
          </motion.div>
          <motion.div {...fadeUp} className="lg:col-span-7">
            <div className="rounded-2xl overflow-hidden border border-white/10">
              <img src="https://images.unsplash.com/photo-1692153142524-60285a93c249?crop=entropy&cs=srgb&fm=jpg&q=85&w=1400" alt="Luxury hotel lobby" loading="lazy" className="w-full h-[420px] object-cover" />
            </div>
            <div className="grid grid-cols-3 gap-4 -mt-10 px-6 relative">
              {[["€2.4M", "revenue optimised monthly"], ["38k", "price decisions / week"], ["0", "spreadsheets needed"]].map(([v, l]) => (
                <div key={l} className="bg-[#111827] border border-white/10 rounded-xl p-4 text-center shadow-xl">
                  <div className="text-xl lg:text-2xl font-extrabold tabular-nums">{v}</div>
                  <div className="text-[10px] text-stone-400 mt-1 uppercase tracking-widest font-bold leading-tight">{l}</div>
                </div>
              ))}
            </div>
          </motion.div>
        </div>
      </section>

      {/* Testimonials */}
      <section className="max-w-7xl mx-auto px-5 sm:px-8 py-24">
        <motion.div {...fadeUp} className="max-w-2xl mb-14">
          <div className="text-xs font-bold uppercase tracking-[0.2em] text-[#1D4ED8] mb-3">From hoteliers</div>
          <h2 className="text-3xl lg:text-4xl font-bold tracking-tight">Trusted at the front desk and in the boardroom</h2>
        </motion.div>
        <div className="grid md:grid-cols-3 gap-6">
          {TESTIMONIALS.map((t, i) => (
            <motion.div key={t.name} {...fadeUp} transition={{ ...fadeUp.transition, delay: i * 0.08 }}
              className={`bg-white rounded-2xl border border-black/5 p-7 shadow-[0_8px_32px_rgba(29,78,216,0.05)] ${i === 1 ? "md:mt-10" : ""}`}
              data-testid={`testimonial-${i}`}>
              <div className="text-4xl font-black text-[#1D4ED8]/20 leading-none">"</div>
              <p className="text-sm text-stone-700 leading-relaxed mt-2">{t.quote}</p>
              <div className="mt-6 pt-5 border-t border-stone-100">
                <div className="font-bold text-sm text-stone-900">{t.name}</div>
                <div className="text-xs text-stone-500">{t.role} · {t.hotel}</div>
              </div>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="bg-[#F5F4F0] border-y border-black/5 py-24">
        <div className="max-w-7xl mx-auto px-5 sm:px-8">
          <motion.div {...fadeUp} className="max-w-2xl mb-14">
            <div className="text-xs font-bold uppercase tracking-[0.2em] text-[#1D4ED8] mb-3">Pricing</div>
            <h2 className="text-3xl lg:text-4xl font-bold tracking-tight">Simple per-room pricing. No surprises.</h2>
            <p className="mt-4 text-stone-600">Pay per room, per month. Every plan includes onboarding, data migration and unlimited users.</p>
          </motion.div>
          <div className="grid md:grid-cols-3 gap-6 items-start">
            {[
              {
                name: "Starter", price: "€4", note: "per room / month",
                desc: "Core operations for independent hotels.",
                items: ["PMS: calendar, front desk & housekeeping", "Direct booking engine", "Payments & invoicing", "Guest messaging inbox", "Standard reports"],
                cta: "Start with Starter", highlight: false,
              },
              {
                name: "Professional", price: "€7", note: "per room / month",
                desc: "Operations + full AI revenue intelligence.",
                items: ["Everything in Starter", "ReveniQ AI pricing & forecasting", "Channel manager & parity radar", "Competitor rate radar", "Gap-filler campaigns & morning brief", "POS, F&B and events"],
                cta: "Choose Professional", highlight: true,
              },
              {
                name: "Enterprise", price: "Custom", note: "chains & groups",
                desc: "Multi-property, custom SLAs and integrations.",
                items: ["Everything in Professional", "Multi-property & chain benchmarking", "Owner & agency portals", "Custom integrations & API access", "Dedicated success manager"],
                cta: "Contact Sales", highlight: false,
              },
            ].map((p, i) => (
              <motion.div key={p.name} {...fadeUp} transition={{ ...fadeUp.transition, delay: i * 0.08 }}
                className={`rounded-2xl p-7 border transition-transform duration-300 hover:-translate-y-1 ${p.highlight ? "bg-[#0A0F1C] text-white border-white/10 shadow-[0_24px_60px_rgba(10,15,28,0.3)] md:-mt-4" : "bg-white border-black/5"}`}
                data-testid={`pricing-${p.name.toLowerCase()}`}>
                {p.highlight && (
                  <div className="inline-block px-3 py-1 rounded-full bg-[#1D4ED8] text-white text-[10px] font-bold uppercase tracking-widest mb-4">Most popular</div>
                )}
                <h3 className={`text-lg font-bold ${p.highlight ? "text-white" : "text-stone-900"}`}>{p.name}</h3>
                <div className="mt-3 flex items-baseline gap-2">
                  <span className={`text-4xl font-extrabold tabular-nums ${p.highlight ? "text-white" : "text-stone-900"}`}>{p.price}</span>
                  <span className={`text-xs font-medium ${p.highlight ? "text-stone-400" : "text-stone-500"}`}>{p.note}</span>
                </div>
                <p className={`mt-2 text-sm ${p.highlight ? "text-stone-300" : "text-stone-600"}`}>{p.desc}</p>
                <ul className="mt-6 space-y-2.5">
                  {p.items.map((it) => (
                    <li key={it} className={`flex items-start gap-2.5 text-sm ${p.highlight ? "text-stone-200" : "text-stone-700"}`}>
                      <CheckCircle2 size={15} className={`mt-0.5 shrink-0 ${p.highlight ? "text-emerald-400" : "text-[#1D4ED8]"}`} /> {it}
                    </li>
                  ))}
                </ul>
                <button onClick={() => scrollTo("#demo")} data-testid={`pricing-cta-${p.name.toLowerCase()}`}
                  className={`mt-7 w-full py-3 rounded-lg text-sm font-bold transition-colors ${p.highlight ? "bg-[#1D4ED8] hover:bg-[#1E40AF] text-white" : "border border-stone-300 hover:border-stone-500 text-stone-800"}`}>
                  {p.cta}
                </button>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Demo form */}
      <section id="demo" className="max-w-7xl mx-auto px-5 sm:px-8 py-24 grid lg:grid-cols-12 gap-12">
        <motion.div {...fadeUp} className="lg:col-span-5">
          <div className="text-xs font-bold uppercase tracking-[0.2em] text-[#1D4ED8] mb-3">Get started</div>
          <h2 className="text-3xl lg:text-4xl font-bold tracking-tight">See your hotel inside the platform</h2>
          <p className="mt-4 text-stone-600 leading-relaxed">Tell us about your property and we'll prepare a walkthrough with your room types, your market and your OTA mix — not a generic slideshow.</p>
          <ul className="mt-8 space-y-3">
            {["30-minute personalised demo", "Migration & onboarding plan included", "Pricing quote for your exact room count"].map((t) => (
              <li key={t} className="flex items-center gap-3 text-sm text-stone-700">
                <CheckCircle2 size={16} className="text-emerald-500 shrink-0" /> {t}
              </li>
            ))}
          </ul>
        </motion.div>
        <motion.div {...fadeUp} className="lg:col-span-7">
          <DemoForm />
        </motion.div>
      </section>

      {/* FAQ */}
      <section id="faq" className="max-w-4xl mx-auto px-5 sm:px-8 pb-24">
        <motion.div {...fadeUp}>
          <div className="text-xs font-bold uppercase tracking-[0.2em] text-[#1D4ED8] mb-3">FAQ</div>
          <h2 className="text-3xl font-bold tracking-tight mb-6">Questions hoteliers ask us</h2>
          {FAQS.map((f, i) => <FaqItem key={f.q} q={f.q} a={f.a} idx={i} />)}
        </motion.div>
      </section>

      {/* Footer */}
      <footer className="bg-[#0A0F1C] text-white">
        <div className="max-w-7xl mx-auto px-5 sm:px-8 py-20">
          <div className="grid lg:grid-cols-12 gap-12">
            <div className="lg:col-span-7">
              <h2 className="text-4xl lg:text-5xl font-extrabold tracking-tighter leading-tight">Ready to run<br />a smarter hotel?</h2>
              <button onClick={() => scrollTo("#demo")} data-testid="footer-demo-btn"
                className="mt-8 px-7 py-3.5 rounded-lg bg-[#1D4ED8] hover:bg-[#1E40AF] text-white font-bold transition-colors inline-flex items-center gap-2">
                Request a demo <ArrowRight size={16} />
              </button>
            </div>
            <div className="lg:col-span-5 grid grid-cols-2 gap-8 text-sm">
              <div>
                <div className="text-xs font-bold uppercase tracking-[0.2em] text-stone-400 mb-4">Product</div>
                <ul className="space-y-2.5 text-[#9CA3AF]">
                  <li><button onClick={() => scrollTo("#product")} className="hover:text-white transition-colors">Property Management</button></li>
                  <li><button onClick={() => scrollTo("#revenue")} className="hover:text-white transition-colors">Revenue AI</button></li>
                  <li><button onClick={() => scrollTo("#pricing")} className="hover:text-white transition-colors">Pricing</button></li>
                  <li><button onClick={() => scrollTo("#faq")} className="hover:text-white transition-colors">FAQ</button></li>
                </ul>
              </div>
              <div>
                <div className="text-xs font-bold uppercase tracking-[0.2em] text-stone-400 mb-4">Company</div>
                <ul className="space-y-2.5 text-[#9CA3AF]">
                  <li><button onClick={goLogin} className="hover:text-white transition-colors" data-testid="footer-signin-btn">Sign In</button></li>
                  <li><button onClick={() => scrollTo("#demo")} className="hover:text-white transition-colors">Contact Sales</button></li>
                </ul>
              </div>
            </div>
          </div>
          <div className="mt-16 pt-8 border-t border-white/10 flex flex-wrap items-center justify-between gap-4 text-xs text-[#9CA3AF]">
            <span>© {new Date().getFullYear()} MyHotelBox &amp; ReveniQ. All rights reserved.</span>
            <span className="flex items-center gap-2"><ShieldCheck size={13} /> PCI-DSS compliant payments · GDPR ready</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
