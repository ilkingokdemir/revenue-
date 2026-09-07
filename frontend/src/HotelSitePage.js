import { useState, useEffect } from "react";
import axios from "axios";
import { List, X } from "@phosphor-icons/react";
import { SITE_THEMES, SITE_PAGES, PAGE_LABELS, UI } from "./site/siteThemes";
import { Section, AvailabilityBlock, RoomsBlock, ReviewsBlock, MapBlock, FaqBlock, ContactBlock, GalleryBlock, PostsBlock, RoomDetailPage } from "./site/SiteBlocks";
import { useAnalytics } from "./site/analytics";
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
  if (pid) { const [pg, sub] = window.location.pathname.replace(/^\//, "").split("/"); return <HotelSitePage propertyId={pid} initialPage={pg || "home"} initialSub={sub || ""} basePath="" />; }
  return fallback || null;
}

function getVisitor() {
  try {
    let v = localStorage.getItem("mhb_visitor_id");
    if (!v) { v = Math.random().toString(36).slice(2) + Date.now().toString(36); localStorage.setItem("mhb_visitor_id", v); }
    return v;
  } catch { return ""; }
}

export default function HotelSitePage({ propertyId, initialPage = "home", initialSub = "", basePath }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(false);
  const [page, setPage] = useState(SITE_PAGES.some((p) => p.id === initialPage) ? initialPage : "home");
  const [sub, setSub] = useState(initialSub);
  const [lang, setLang] = useState(() => { const q = new URLSearchParams(window.location.search).get("lang"); return ["tr", "en", "de"].includes(q) ? q : "tr"; });
  const [menu, setMenu] = useState(false);
  const base = basePath ?? `/site/${propertyId}`;
  useAnalytics(propertyId);

  useEffect(() => {
    axios.get(`${API}/site-builder/public/site/${propertyId}`).then(({ data: d }) => setData(d)).catch(() => setErr(true));
  }, [propertyId]);

  useEffect(() => {
    if (!data) return;
    axios.post(`${API}/site-builder/public/track`, { property_id: propertyId, event: "view", page: page === "blog" && sub ? `blog/${sub}` : page, variant: new URLSearchParams(window.location.search).get("v") || "", visitor_id: getVisitor(), referrer: document.referrer || "" }).catch(() => {});
    if (data.site.mode === "pro" && data.site.engine_template) window.location.replace(`/book?property=${propertyId}&template=${data.site.engine_template}`);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data ? 1 : 0]);

  const trackCta = () => axios.post(`${API}/site-builder/public/track`, { property_id: propertyId, event: "cta_click", visitor_id: getVisitor(), referrer: document.referrer || "" }).catch(() => {});

  const go = (p, subId = "") => {
    setPage(p); setSub(subId); setMenu(false);
    if (p === "blog" && subId) axios.post(`${API}/site-builder/public/track`, { property_id: propertyId, event: "view", page: `blog/${subId}`, variant: new URLSearchParams(window.location.search).get("v") || "", visitor_id: getVisitor(), referrer: document.referrer || "" }).catch(() => {});
    const q = lang !== "tr" ? `?lang=${lang}` : "";
    window.history.pushState({}, "", (p === "home" ? (base || "/") : `${base}/${p}${subId ? `/${subId}` : ""}`) + q);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  useEffect(() => {
    if (!data) return;
    const c0 = data.site.content || {};
    const c = { ...c0, ...((c0.translations || {})[lang] || {}) };
    const name = data.property?.name || propertyId;
    const pageLabel = PAGE_LABELS[lang]?.[page] || SITE_PAGES.find((p) => p.id === page)?.label;
    const title = (c.seo_title || `${name}${c.headline ? " — " + c.headline : ""}`) + (page !== "home" ? ` | ${pageLabel}` : "");
    const desc = c.seo_description || c.about || `${name} için online rezervasyon.`;
    document.title = title;
    document.documentElement.lang = lang;
    document.head.querySelectorAll("link[data-mhb-hreflang]").forEach((l) => l.remove());
    const langs = ["tr", ...["en", "de"].filter((lg) => (c0.translations || {})[lg])];
    const path = window.location.pathname;
    langs.concat(["x-default"]).forEach((lg) => { const l = document.createElement("link"); l.rel = "alternate"; l.hreflang = lg; l.href = `${window.location.origin}${path}${lg === "tr" || lg === "x-default" ? "" : `?lang=${lg}`}`; l.dataset.mhbHreflang = "1"; document.head.appendChild(l); });
    let sm = document.getElementById("mhb-sitemap"); if (!sm) { sm = document.createElement("link"); sm.id = "mhb-sitemap"; sm.rel = "sitemap"; sm.type = "application/xml"; document.head.appendChild(sm); }
    sm.href = `${apiBase}/api/site-builder/public/sitemap/${propertyId}.xml`;
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
  }, [data, propertyId, page, lang]);

  if (err) return <div className="min-h-screen flex items-center justify-center text-stone-500 text-sm" data-testid="site-not-found">Bu site yayında değil.</div>;
  if (!data) return <div className="min-h-screen flex items-center justify-center text-stone-400 text-sm">Yükleniyor…</div>;

  const th0 = SITE_THEMES[data.site.template] || SITE_THEMES.classic;
  const c0 = data.site.content || {};
  const th = { ...th0, ...(c0.brand?.accent ? { accent: c0.brand.accent } : {}), ...(c0.brand?.radius ? { radius: c0.brand.radius } : {}) };
  const c = { ...c0, ...((c0.translations || {})[lang] || {}) };
  const ui = UI[lang] || UI.tr;
  const availableLangs = ["tr", ...["en", "de"].filter((lg) => (c0.translations || {})[lg])];
  const name = data.property?.name || propertyId;
  const amenities = Array.isArray(c.amenities) ? c.amenities : String(c.amenities || "").split(",").map((x) => x.trim()).filter(Boolean);
  const cover = (data.photos || []).find((p) => p.kind === "cover");
  const gallery = (data.photos || []).filter((p) => p.kind === "gallery");
  const enabledPages = SITE_PAGES.filter((p) => (c.pages_enabled || SITE_PAGES.map((x) => x.id)).includes(p.id) && (p.id !== "blog" || (c.posts || []).some((x) => x.published !== false))).map((p) => ({ ...p, label: PAGE_LABELS[lang]?.[p.id] || p.label }));
  const enabledBlocks = (c.blocks || []).filter((b) => b.enabled).map((b) => b.id);
  const pageDef = SITE_PAGES.find((p) => p.id === page) || SITE_PAGES[0];
  const blocks = pageDef.blocks ? pageDef.blocks.filter((b) => enabledBlocks.includes(b) || b === pageDef.blocks[0]) : enabledBlocks;
  const currency = data.property?.currency || "GBP";
  const bookHref = `/book?property=${propertyId}`;

  const render = (id) => {
    switch (id) {
      case "posts": return <PostsBlock key="posts" th={th} posts={c.posts} ui={ui} onOpen={(slug) => go("blog", slug || "")} single={sub ? (c.posts || []).find((x) => x.slug === sub) : null} propertyId={propertyId} />;
      case "hero": return (
        <div key="hero" className="relative px-6 pt-24 pb-28 text-center overflow-hidden" data-testid="site-hero"
          style={{ background: cover ? `linear-gradient(rgba(0,0,0,.35), rgba(0,0,0,.55)), url(${apiBase}${cover.url}) center/cover` : th.heroBg, color: cover ? "#fff" : th.heroText }}>
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black tracking-tight" style={{ fontFamily: th.heading }} data-testid="site-hero-title">{name}</h1>
          {c.headline && <p className="mt-4 text-base md:text-lg opacity-85 max-w-2xl mx-auto" data-testid="site-hero-headline">{c.headline}</p>}
          {data.rating && data.rating.avg >= 4 && <div className="mt-4 inline-flex items-center gap-2 text-sm bg-white/15 backdrop-blur px-3 py-1 rounded-full">★ {data.rating.avg} · {data.rating.count} yorum</div>}
          <div className="mt-8 flex items-center justify-center gap-3 flex-wrap">
            <a href={bookHref} data-testid="site-book-cta" onClick={trackCta} className="inline-block px-8 py-3 text-sm font-black transition-transform hover:scale-105" style={{ background: th.accent, color: th.accentText, borderRadius: th.radius }}>{ui.book}</a>
            {enabledPages.some((p) => p.id === "rooms") && <button onClick={() => go("rooms")} className="px-6 py-3 text-sm font-bold border border-white/40 hover:bg-white/10" style={{ borderRadius: th.radius }}>{ui.rooms}</button>}
          </div>
        </div>);
      case "availability": return <AvailabilityBlock key="av" th={th} propertyId={propertyId} currency={currency} ui={ui} />;
      case "about": return c.about ? <Section key="about" th={th} title={ui.about} testId="site-about"><p className="text-base leading-relaxed max-w-3xl" data-testid="site-about-text">{c.about}</p></Section> : null;
      case "rooms": return <RoomsBlock key="rooms" th={th} rooms={data.room_types} propertyId={propertyId} onCta={trackCta} currency={currency} onDetail={(id) => go("rooms", id)} ui={ui} />;
      case "amenities": return amenities.length ? <Section key="am" th={th} title={ui.amen} testId="site-amenities"><div className="flex flex-wrap gap-2">{amenities.map((a) => <span key={a} className="text-xs px-3 py-1.5 font-medium" style={{ background: th.card, border: `1px solid ${th.cardBorder}`, borderRadius: th.radius }}>{a}</span>)}</div></Section> : null;
      case "gallery": return <GalleryBlock key="gal" th={th} gallery={gallery} full={page === "gallery"} ui={ui} />;
      case "reviews": return <ReviewsBlock key="rev" th={th} reviews={data.reviews} rating={data.rating?.avg >= 4 ? data.rating : null} ui={ui} />;
      case "map": return <MapBlock key="map" th={th} content={c} propertyName={name} ui={ui} />;
      case "faq": return <FaqBlock key="faq" th={th} faqs={c.faqs} ui={ui} />;
      case "contact": return <ContactBlock key="ct" th={th} propertyId={propertyId} ui={ui} />;
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
            {availableLangs.length > 1 && (
              <select value={lang} onChange={(e) => { setLang(e.target.value); const q = e.target.value !== "tr" ? `?lang=${e.target.value}` : ""; window.history.replaceState({}, "", window.location.pathname + q); }} className="ml-2 text-xs font-bold bg-transparent border rounded-full px-2 py-1" style={{ borderColor: th.cardBorder, color: th.text }} aria-label="language" data-testid="site-lang-select">
                {availableLangs.map((lg) => <option key={lg} value={lg}>{lg.toUpperCase()}</option>)}
              </select>
            )}
            <a href={bookHref} onClick={trackCta} className="ml-2 px-4 py-2 text-sm font-black" style={{ background: page === "home" ? th.text : th.accent, color: page === "home" ? th.bg : th.accentText, borderRadius: th.radius }} data-testid="site-nav-book">{ui.book}</a>
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

      {page !== "home" && !(page === "rooms" && sub) && !(page === "blog" && sub) && (
        <div className="px-6 pt-12 pb-6 max-w-5xl mx-auto">
          <h1 className="text-4xl sm:text-5xl font-black" style={{ fontFamily: th.heading }} data-testid="site-page-title">{PAGE_LABELS[lang]?.[pageDef.id] || pageDef.label}</h1>
        </div>
      )}
      <main id="site-main">
        {page === "rooms" && sub ? <RoomDetailPage th={th} room={(data.room_types || []).find((r) => r.id === sub)} propertyId={propertyId} ui={ui} onBack={() => go("rooms")} currency={currency} /> : blocks.map(render)}
      </main>
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
