import { useState } from "react";
import { motion } from "framer-motion";
import { Toaster } from "sonner";
import {
  ArrowRight, ArrowUpRight, CheckCircle2, Sparkles,
  CalendarCheck, TrendingUp, Globe2, MessageSquareText, BedDouble,
  BarChart3, CreditCard, Zap, ShieldCheck, Building2, Menu, X, ClipboardCheck,
} from "lucide-react";
import { DemoForm, FaqItem, fadeUp, goLogin, scrollTo } from "./landing/shared";

const NAV_LINKS = [
  { label: "Product", href: "#product" },
  { label: "Guest Experience", href: "#guests" },
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
    quote: "We replaced four separate tools with one platform. Our front desk closes night audit in minutes and check-in queues simply disappeared once guests started arriving pre-registered.",
    name: "Selin Aydın", role: "General Manager", hotel: "Aurora Palace İstanbul · 142 rooms",
  },
  {
    quote: "Housekeeping gets tasks the moment a guest checks out, maintenance issues are logged from the room's QR code, and I can see the whole house on one screen.",
    name: "Marco Bianchi", role: "Operations Manager", hotel: "Harborline Suites · 86 rooms",
  },
  {
    quote: "Guests check in from their phone, order room service by QR, and I finally see clean P&L numbers per outlet. It feels like hiring three extra people.",
    name: "Deniz Kaya", role: "Owner", hotel: "Villa Lumen Kaş · 24 rooms",
  },
];

const FAQS = [
  { q: "How long does onboarding take?", a: "Most independent hotels go live in under two weeks. We migrate your reservations, rate plans and OTA connections, and your team gets guided training inside the product with the built-in academy." },
  { q: "Does it connect to Booking.com, Expedia and other OTAs?", a: "Yes. The channel manager keeps availability, rates and restrictions in sync in real time across all major OTAs, with parity monitoring that alerts you when a channel undercuts your direct price." },
  { q: "Can guests really check in without the front desk?", a: "Yes — guests receive a pre-arrival link to register, upload documents, pay and get a digital room key. The kiosk mode covers walk-ins. Your team only steps in for exceptions." },
  { q: "What about revenue management?", a: "MyHotelBox pairs natively with ReveniQ, our AI revenue platform. It shares the same data, so forecasting, dynamic pricing and competitor tracking switch on instantly — no extra integration project." },
  { q: "What about my existing payment provider?", a: "Built-in payments support cards, payment links, terminals and OTA virtual cards. If you prefer your current provider, we integrate with it during onboarding." },
];

function FrontDeskMockup() {
  const rows = [
    ["101 · Deluxe", "S. Carter", "Arriving 14:00", "bg-blue-500/15 text-blue-300"],
    ["204 · Suite", "J. Meyer", "In-house · 2n", "bg-emerald-500/15 text-emerald-300"],
    ["118 · Twin", "A. Rossi", "Checkout 11:00", "bg-amber-500/15 text-amber-300"],
    ["302 · Deluxe", "L. Novak", "Cleaning", "bg-stone-500/20 text-stone-300"],
  ];
  return (
    <div className="relative" data-testid="hero-dashboard-mockup">
      <div className="absolute -inset-6 bg-[#849B89]/15 rounded-[32px] -rotate-2" aria-hidden="true" />
      <div className="relative bg-[#0A0F1C] rounded-2xl border border-white/10 shadow-[0_24px_80px_rgba(10,15,28,0.35)] overflow-hidden">
        <div className="flex items-center gap-1.5 px-4 py-3 border-b border-white/10">
          <span className="w-2.5 h-2.5 rounded-full bg-[#E07A5F]" />
          <span className="w-2.5 h-2.5 rounded-full bg-[#E5C05F]" />
          <span className="w-2.5 h-2.5 rounded-full bg-[#849B89]" />
          <span className="ml-3 text-[10px] text-stone-400 font-mono">myhotelbox · front desk</span>
        </div>
        <div className="p-5 space-y-4">
          <div className="grid grid-cols-3 gap-3">
            {[["Arrivals", "18", "6 pre-registered"], ["In-house", "112", "87% occupancy"], ["Departures", "14", "3 late checkout"]].map(([l, v, d]) => (
              <div key={l} className="bg-white/[0.04] border border-white/10 rounded-xl p-3">
                <div className="text-[9px] uppercase tracking-widest text-stone-400 font-bold">{l}</div>
                <div className="text-xl font-extrabold text-white tabular-nums mt-0.5">{v}</div>
                <div className="text-[10px] text-emerald-400 font-bold">{d}</div>
              </div>
            ))}
          </div>
          <div className="bg-white/[0.04] border border-white/10 rounded-xl p-4 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-[10px] uppercase tracking-widest text-stone-400 font-bold">Today's board</span>
              <span className="text-[10px] text-blue-300 font-bold flex items-center gap-1"><Sparkles size={10} /> auto-assigned</span>
            </div>
            {rows.map(([room, guest, status, badge]) => (
              <div key={room} className="flex items-center justify-between bg-white/[0.03] rounded-lg px-3 py-2">
                <div>
                  <div className="text-[11px] font-bold text-white">{room}</div>
                  <div className="text-[10px] text-stone-400">{guest}</div>
                </div>
                <span className={`text-[9px] font-bold px-2 py-1 rounded-full ${badge}`}>{status}</span>
              </div>
            ))}
          </div>
          <div className="flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/25 rounded-xl px-3 py-2.5">
            <ClipboardCheck size={13} className="text-emerald-400 shrink-0" />
            <span className="text-[11px] text-emerald-200">Housekeeping: 12 rooms cleaned, 4 in progress — night audit ready</span>
          </div>
        </div>
      </div>
    </div>
  );
}

const FEATURES = [
  {
    span: "md:col-span-7", icon: CalendarCheck, label: "Front Desk & Reservations",
    title: "Front desk, reservations & housekeeping in one calm screen",
    desc: "Drag-and-drop room calendar, group bookings, digital check-in kiosk, housekeeping auto-dispatch and a night audit that runs itself. Your team stops juggling tabs.",
    img: "https://images.unsplash.com/photo-1759038085950-1234ca8f5fed?crop=entropy&cs=srgb&fm=jpg&q=85&w=1200",
    testid: "feature-pms",
  },
  {
    span: "md:col-span-5", icon: Globe2, label: "Distribution",
    title: "Direct bookings & OTA sync",
    desc: "Commission-free booking engine with promo codes, plus a real-time channel manager that keeps availability, rates and restrictions aligned across every OTA — with parity alerts when a channel undercuts you.",
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
    span: "md:col-span-4", icon: BedDouble, label: "Housekeeping & Maintenance",
    title: "The house runs itself",
    desc: "Mobile housekeeping app, auto-dispatch on checkout, lost & found, minibar posting and QR maintenance reporting straight from the room.",
    img: "https://images.unsplash.com/photo-1549638441-b787d2e11f14?crop=entropy&cs=srgb&fm=jpg&q=85&w=800",
    testid: "feature-housekeeping",
  },
  {
    span: "md:col-span-4", icon: BarChart3, label: "Finance & Reports",
    title: "Numbers your accountant will love",
    desc: "P&L per outlet, OTA commission reconciliation, city ledger, invoicing and scheduled reports delivered to your inbox.",
    testid: "feature-finance",
  },
];

const CHIPS = [
  [BedDouble, "Housekeeping mobile app"], [CreditCard, "Payments & terminals"],
  [Building2, "Multi-property & chains"], [ShieldCheck, "Role-based access"],
  [Zap, "POS · F&B · spa & events"], [Sparkles, "AI guest messaging"],
];

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
            <span className="font-extrabold tracking-tight text-lg">MyHotelBox</span>
          </a>
          <nav className="hidden md:flex items-center gap-7">
            {NAV_LINKS.map((l) => (
              <button key={l.href} onClick={() => scrollTo(l.href)} data-testid={`nav-link-${l.label.toLowerCase().replace(/\s/g, "-")}`}
                className="text-sm font-medium text-stone-600 hover:text-stone-900 transition-colors">{l.label}</button>
            ))}
            <a href="/reveniq" data-testid="nav-link-reveniq"
              className="text-sm font-bold text-[#1D4ED8] hover:text-[#1E40AF] transition-colors flex items-center gap-1">
              ReveniQ <ArrowUpRight size={13} />
            </a>
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
            <a href="/reveniq" className="block text-sm font-bold text-[#1D4ED8]">ReveniQ ↗</a>
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
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-[#849B89]/15 border border-[#849B89]/30 text-[#3E5245] text-xs font-bold mb-6" data-testid="hero-badge">
            <Sparkles size={12} /> The hotel property management system
          </div>
          <h1 className="text-5xl lg:text-6xl font-extrabold tracking-tighter leading-[1.05]">
            The calm way<br />
            <span className="text-[#1D4ED8]">to run your hotel.</span>
          </h1>
          <p className="mt-6 text-lg text-stone-600 leading-relaxed max-w-xl">
            MyHotelBox brings front desk, housekeeping, bookings, guest messaging and payments into one quiet, reliable screen — so your team spends their day with guests, not with software.
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
            {[["2 wks", "typical go-live"], ["-40%", "front desk admin time"], ["24/7", "guest self-service"]].map(([v, l]) => (
              <div key={l} data-testid={`hero-stat-${l.replace(/[.\s%]/g, "-")}`}>
                <div className="text-2xl font-extrabold tabular-nums text-stone-900">{v}</div>
                <div className="text-xs text-stone-500 font-medium">{l}</div>
              </div>
            ))}
          </div>
        </motion.div>
        <motion.div className="lg:col-span-6" initial={{ opacity: 0, y: 40 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, delay: 0.15, ease: [0.22, 1, 0.36, 1] }}>
          <FrontDeskMockup />
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
        <div className="grid grid-cols-1 md:grid-cols-12 gap-6" id="guests">
          {FEATURES.map((f, i) => (
            <motion.div key={f.testid} {...fadeUp} transition={{ ...fadeUp.transition, delay: i * 0.06 }}
              className={`${f.span} rounded-2xl border overflow-hidden group hover:-translate-y-1 transition-transform duration-300 bg-white border-black/5 shadow-[0_8px_32px_rgba(29,78,216,0.05)]`}
              data-testid={f.testid}>
              <div className="p-7">
                <div className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-[0.18em] mb-4 text-[#1D4ED8]">
                  <f.icon size={14} /> {f.label}
                </div>
                <h3 className="text-xl lg:text-2xl font-semibold tracking-tight text-stone-900">{f.title}</h3>
                <p className="mt-3 text-sm leading-relaxed text-stone-600">{f.desc}</p>
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

      {/* ReveniQ cross-sell */}
      <section className="bg-[#0A0F1C] text-white py-20" data-testid="reveniq-crosssell">
        <div className="max-w-7xl mx-auto px-5 sm:px-8 grid lg:grid-cols-12 gap-10 items-center">
          <motion.div {...fadeUp} className="lg:col-span-7">
            <div className="text-xs font-bold uppercase tracking-[0.2em] text-blue-300 mb-3 flex items-center gap-2">
              <TrendingUp size={14} /> Works hand-in-hand with ReveniQ
            </div>
            <h2 className="text-3xl lg:text-4xl font-bold tracking-tight">Need your prices to run themselves too?</h2>
            <p className="mt-4 text-stone-300 leading-relaxed max-w-2xl">
              ReveniQ is our dedicated AI revenue management platform — demand forecasting, dynamic pricing, competitor rate radar and gap-filler campaigns. It shares the same data as MyHotelBox, so it switches on in a day, not a quarter.
            </p>
            <a href="/reveniq" data-testid="crosssell-reveniq-btn"
              className="mt-8 inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-[#1D4ED8] hover:bg-[#1E40AF] text-white text-sm font-bold transition-colors">
              Discover ReveniQ <ArrowUpRight size={15} />
            </a>
          </motion.div>
          <motion.div {...fadeUp} className="lg:col-span-5 grid grid-cols-2 gap-4">
            {[["+12.4%", "avg. RevPAR lift"], ["94%", "forecast accuracy"], ["38k", "price decisions / week"], ["24/7", "competitor radar"]].map(([v, l]) => (
              <div key={l} className="bg-white/[0.05] border border-white/10 rounded-xl p-5">
                <div className="text-2xl font-extrabold tabular-nums">{v}</div>
                <div className="text-[10px] text-stone-400 mt-1 uppercase tracking-widest font-bold leading-tight">{l}</div>
              </div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* Testimonials */}
      <section className="max-w-7xl mx-auto px-5 sm:px-8 py-24">
        <motion.div {...fadeUp} className="max-w-2xl mb-14">
          <div className="text-xs font-bold uppercase tracking-[0.2em] text-[#1D4ED8] mb-3">From hoteliers</div>
          <h2 className="text-3xl lg:text-4xl font-bold tracking-tight">Trusted at the front desk and in the back office</h2>
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
            <p className="mt-4 text-stone-600">Pay per room, per month. Every plan includes onboarding, data migration and unlimited users. Add <a href="/reveniq" className="text-[#1D4ED8] font-bold hover:underline">ReveniQ revenue AI</a> to any plan.</p>
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
                desc: "Full operations, distribution and guest experience.",
                items: ["Everything in Starter", "Channel manager & parity alerts", "Digital check-in, kiosk & room keys", "Upsells, surveys & review autopilot", "POS, F&B and events", "P&L, budgets & scheduled reports"],
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
          <h2 className="text-3xl lg:text-4xl font-bold tracking-tight">See your hotel inside MyHotelBox</h2>
          <p className="mt-4 text-stone-600 leading-relaxed">Tell us about your property and we'll prepare a walkthrough with your room types, your outlets and your OTA mix — not a generic slideshow.</p>
          <ul className="mt-8 space-y-3">
            {["30-minute personalised demo", "Migration & onboarding plan included", "Pricing quote for your exact room count"].map((t) => (
              <li key={t} className="flex items-center gap-3 text-sm text-stone-700">
                <CheckCircle2 size={16} className="text-emerald-500 shrink-0" /> {t}
              </li>
            ))}
          </ul>
        </motion.div>
        <motion.div {...fadeUp} className="lg:col-span-7">
          <DemoForm product="pms" />
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
              <h2 className="text-4xl lg:text-5xl font-extrabold tracking-tighter leading-tight">Ready to run<br />a calmer hotel?</h2>
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
                  <li><button onClick={() => scrollTo("#pricing")} className="hover:text-white transition-colors">Pricing</button></li>
                  <li><button onClick={() => scrollTo("#faq")} className="hover:text-white transition-colors">FAQ</button></li>
                  <li><a href="/reveniq" className="hover:text-white transition-colors font-bold text-blue-300" data-testid="footer-reveniq-link">ReveniQ — Revenue AI ↗</a></li>
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
            <span>© {new Date().getFullYear()} MyHotelBox. All rights reserved.</span>
            <span className="flex items-center gap-2"><ShieldCheck size={13} /> PCI-DSS compliant payments · GDPR ready</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
