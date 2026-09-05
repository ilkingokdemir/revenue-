import { useState, useEffect } from "react";
import axios from "axios";
import { List, X } from "@phosphor-icons/react";
import { SITE_THEMES, SITE_PAGES } from "./site/siteThemes";
import { Section, AvailabilityBlock, RoomsBlock, ReviewsBlock, MapBlock, FaqBlock, ContactBlock, GalleryBlock } from "./site/SiteBlocks";
import { LanguageProvider } from "./i18n/LanguageContext";
import { CookieBanner } from "./templates/ExitIntentPopup";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const apiBase = process.env.REACT_APP_BACKEND_URL;

export function CustomDomainSite({ fallback }) {
  const [pid, setPid] = useState(null);
  const [checked, setChecked] = useState(false);
  useEffect(() => {
    axios.get(`${API}/site-builder/public/resolve-domain`, { params: { host: window.location.host } })
      .then(({ data }) => setPid(data.property_id)).catch(() => {}).finally(() => setChecked(true));
  }, []);
  if (!checked) return <div className="min-h-screen flex items-center justify-center text-stone-400 text-sm">Yükleniyor…</div>;
  if (pid) return <HotelSitePage propertyId={pid} initialPage={window.location.pathname.replace(/^\//, "") || "home"} basePath="" />;
  return fallback || null;
}

function getVisitor() {
  try {
    let v = localStorage.getItem("mhb_visitor_id");
    if (!v) { v = Math.random().toString(36).slice(2) + Date.now().toString(36); localStorage.setItem("mhb_visitor_id", v); }
    return v;
  } catch { return ""; }
}

export default function HotelSitePage({ propertyId, initialPage = "home", basePath }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(false);
  const [page, setPage] = useState(SITE_PAGES.some((p) => p.id === initialPage) ? initialPage : "home");
  const [menu, setMenu] = useState(false);
  const base = basePath ?? `/site/${propertyId}`;

  useEffect(() => {
    axios.get(`${API}/site-builder/public/site/${propertyId}`).then(({ data: d }) => setData(d)).catch(() => setErr(true));
  }, [propertyId]);

  useEffect(() => {
    if (!data) return;
    axios.post(`${API}/site-builder/public/track`, { property_id: propertyId, event: "view", visitor_id: getVisitor(), referrer: document.referrer || "" }).catch(() => {});
    if (data.site.mode === "pro" && data.site.engine_template) window.location.replace(`/book?property=${propertyId}&template=${data.site.engine_template}`);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data ? 1 : 0]);

  const trackCta = () => axios.post(`${API}/site-builder/public/track`, { property_id: propertyId, event: "cta_click", visitor_id: getVisitor(), referrer: document.referrer || "" }).catch(() => {});

  const go = (p) => {
    setPage(p); setMenu(false);
    window.history.pushState({}, "", p === "home" ? (base || "/") : `${base}/${p}`);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  useEffect(() => {
    if (!data) return;
    const c = data.site.content || {};
    const name = data.property?.name || propertyId;
    const pageLabel = SITE_PAGES.find((p) => p.id === page)?.label;
    const title = (c.seo_title || `${name}${c.headline ? " — " + c.headline : ""}`) + (page !== "home" ? ` | ${pageLabel}` : "");
    const desc = c.seo_description || c.about || `${name} için online rezervasyon.`;
    document.title = title;
    const setMeta = (attr, key, val) => {
      let el = document.head.querySelector(`meta[${attr}="${key}"]`);
      if (!el) { el = document.createElement("meta"); el.setAttribute(attr, key); document.head.appendChild(el); }
      el.setAttribute("content", val);
    };
    setMeta("name", "description", desc.slice(0, 160));
    if (c.seo_keywords) setMeta("name", "keywords", c.seo_keywords);
    setMeta("property", "og:title", title); setMeta("property", "og:description", desc.slice(0, 160)); setMeta("property", "og:type", "website");
    const cov = (data.photos || []).find((p) => p.kind === "cover");
    if (cov) setMeta("property", "og:image", `${apiBase}${cov.url}`);
    let ld = document.getElementById("hotel-jsonld");
    if (!ld) { ld = document.createElement("script"); ld.type = "application/ld+json"; ld.id = "hotel-jsonld"; document.head.appendChild(ld); }
    const graph = [{ "@type": "Hotel", name, description: desc.slice(0, 300), ...(c.address ? { address: c.address } : {}), ...(c.phone ? { telephone: c.phone } : {}), ...(cov ? { image: `${apiBase}${cov.url}` } : {}),
      ...(data.rating ? { aggregateRating: { "@type": "AggregateRating", ratingValue: data.rating.avg, reviewCount: data.rating.count, bestRating: 5 } } : {}) }];
    if (c.faqs?.length) graph.push({ "@type": "FAQPage", mainEntity: c.faqs.map((f) => ({ "@type": "Question", name: f.q, acceptedAnswer: { "@type": "Answer", text: f.a } })) });
    ld.textContent = JSON.stringify({ "@context": "https://schema.org", "@graph": graph });
  }, [data, propertyId, page]);

  if (err) return <div className="min-h-screen flex items-center justify-center text-stone-500 text-sm" data-testid="site-not-found">Bu site yayında değil.</div>;
  if (!data) return <div className="min-h-screen flex items-center justify-center text-stone-400 text-sm">Yükleniyor…</div>;

  const th = SITE_THEMES[data.site.template] || SITE_THEMES.classic;
  const c = data.site.content || {};
  const name = data.property?.name || propertyId;
  const amenities = Array.isArray(c.amenities) ? c.amenities : String(c.amenities || "").split(",").map((x) => x.trim()).filter(Boolean);
  const cover = (data.photos || []).find((p) => p.kind === "cover");
  const gallery = (data.photos || []).filter((p) => p.kind === "gallery");
  const enabledPages = SITE_PAGES.filter((p) => (c.pages_enabled || SITE_PAGES.map((x) => x.id)).includes(p.id));
  const enabledBlocks = (c.blocks || []).filter((b) => b.enabled).map((b) => b.id);
  const pageDef = SITE_PAGES.find((p) => p.id === page) || SITE_PAGES[0];
  const blocks = pageDef.blocks ? pageDef.blocks.filter((b) => enabledBlocks.includes(b) || b === pageDef.blocks[0]) : enabledBlocks;
  const currency = data.property?.currency || "GBP";
  const bookHref = `/book?property=${propertyId}`;

  const render = (id) => {
    switch (id) {
      case "hero": return (
        <div key="hero" className="relative px-6 pt-24 pb-28 text-center overflow-hidden" data-testid="site-hero"
          style={{ background: cover ? `linear-gradient(rgba(0,0,0,.35), rgba(0,0,0,.55)), url(${apiBase}${cover.url}) center/cover` : th.heroBg, color: cover ? "#fff" : th.heroText }}>
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black tracking-tight" style={{ fontFamily: th.heading }} data-testid="site-hero-title">{name}</h1>
          {c.headline && <p className="mt-4 text-base md:text-lg opacity-85 max-w-2xl mx-auto">{c.headline}</p>}
          {data.rating && data.rating.avg >= 4 && <div className="mt-4 inline-flex items-center gap-2 text-sm bg-white/15 backdrop-blur px-3 py-1 rounded-full">★ {data.rating.avg} · {data.rating.count} yorum</div>}
          <div className="mt-8 flex items-center justify-center gap-3 flex-wrap">
            <a href={bookHref} data-testid="site-book-cta" onClick={trackCta} className="inline-block px-8 py-3 text-sm font-black transition-transform hover:scale-105" style={{ background: th.accent, color: th.accentText, borderRadius: th.radius }}>Rezervasyon Yap</a>
            {enabledPages.some((p) => p.id === "rooms") && <button onClick={() => go("rooms")} className="px-6 py-3 text-sm font-bold border border-white/40 hover:bg-white/10" style={{ borderRadius: th.radius }}>Odaları Gör</button>}
          </div>
        </div>);
      case "availability": return <AvailabilityBlock key="av" th={th} propertyId={propertyId} currency={currency} />;
      case "about": return c.about ? <Section key="about" th={th} title="Hakkımızda" testId="site-about"><p className="text-base leading-relaxed max-w-3xl" data-testid="site-about-text">{c.about}</p></Section> : null;
      case "rooms": return <RoomsBlock key="rooms" th={th} rooms={data.room_types} propertyId={propertyId} onCta={trackCta} currency={currency} />;
      case "amenities": return amenities.length ? <Section key="am" th={th} title="Olanaklar" testId="site-amenities"><div className="flex flex-wrap gap-2">{amenities.map((a) => <span key={a} className="text-xs px-3 py-1.5 font-medium" style={{ background: th.card, border: `1px solid ${th.cardBorder}`, borderRadius: th.radius }}>{a}</span>)}</div></Section> : null;
      case "gallery": return <GalleryBlock key="gal" th={th} gallery={gallery} full={page === "gallery"} />;
      case "reviews": return <ReviewsBlock key="rev" th={th} reviews={data.reviews} rating={data.rating?.avg >= 4 ? data.rating : null} />;
      case "map": return <MapBlock key="map" th={th} content={c} propertyName={name} />;
      case "faq": return <FaqBlock key="faq" th={th} faqs={c.faqs} />;
      case "contact": return <ContactBlock key="ct" th={th} propertyId={propertyId} />;
      default: return null;
    }
  };

  return (
    <div className="min-h-screen" style={{ background: th.bg, color: th.text }} data-testid="hotel-site-page" data-page={page}>
      <a href="#site-main" className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[100] focus:bg-white focus:text-black focus:px-3 focus:py-2 focus:rounded-lg text-sm font-semibold">İçeriğe geç</a>
      <header className="sticky top-0 z-40 backdrop-blur-md border-b" style={{ background: `${th.nav}ee`, borderColor: th.cardBorder }} data-testid="site-nav">
        <div className="max-w-5xl mx-auto px-6 h-16 flex items-center justify-between gap-4">
          <button onClick={() => go("home")} className="font-black text-lg truncate" style={{ fontFamily: th.heading }} data-testid="site-nav-home">{name}</button>
          <nav className="hidden md:flex items-center gap-1">
            {enabledPages.map((p) => (
              <button key={p.id} onClick={() => go(p.id)} className="px-3 py-1.5 text-sm font-semibold rounded-full transition-colors" style={page === p.id ? { background: th.accent, color: th.accentText } : { color: th.muted }} data-testid={`site-nav-${p.id}`}>{p.label}</button>
            ))}
            <a href={bookHref} onClick={trackCta} className="ml-2 px-4 py-2 text-sm font-black" style={{ background: page === "home" ? th.text : th.accent, color: page === "home" ? th.bg : th.accentText, borderRadius: th.radius }} data-testid="site-nav-book">Rezervasyon</a>
          </nav>
          <button className="md:hidden p-2" onClick={() => setMenu(!menu)} aria-label="menu" data-testid="site-nav-menu">{menu ? <X size={22} /> : <List size={22} />}</button>
        </div>
        {menu && (
          <div className="md:hidden border-t px-6 py-3 flex flex-col gap-1" style={{ borderColor: th.cardBorder, background: th.nav }}>
            {enabledPages.map((p) => <button key={p.id} onClick={() => go(p.id)} className="text-left py-2 text-sm font-semibold" style={{ color: page === p.id ? th.accent : th.text }}>{p.label}</button>)}
            <a href={bookHref} onClick={trackCta} className="mt-2 text-center py-2.5 text-sm font-black" style={{ background: th.accent, color: th.accentText, borderRadius: th.radius }}>Rezervasyon Yap</a>
          </div>
        )}
      </header>

      {page !== "home" && (
        <div className="px-6 pt-12 pb-6 max-w-5xl mx-auto">
          <h1 className="text-4xl sm:text-5xl font-black" style={{ fontFamily: th.heading }} data-testid="site-page-title">{pageDef.label}</h1>
        </div>
      )}
      <main id="site-main">{blocks.map(render)}</main>
      <LanguageProvider defaultLang="tr"><CookieBanner accent={th.accent} radius={th.radius} /></LanguageProvider>

      <footer className="mt-10 border-t py-8 text-center text-xs" style={{ borderColor: th.cardBorder, color: th.muted }}>
        <div className="flex items-center justify-center gap-4 flex-wrap mb-3">
          {enabledPages.map((p) => <button key={p.id} onClick={() => go(p.id)} className="hover:underline">{p.label}</button>)}
        </div>
        <div>{c.phone && <span>{c.phone} · </span>}{c.email && <span>{c.email} · </span>}<span className="opacity-60">Powered by MyHotelBox</span></div>
      </footer>
    </div>
  );
}
