import { useEffect } from "react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
let cfgCache = null;
const fired = new Set();

function inject(id, html) {
  if (document.getElementById(id)) return;
  const tpl = document.createElement("div"); tpl.innerHTML = html;
  const s = document.createElement("script"); s.id = id;
  const src = tpl.querySelector("script")?.getAttribute("src");
  if (src) s.src = src; else s.textContent = tpl.textContent;
  s.async = true; document.head.appendChild(s);
}

function hasConsent() {
  try { return (localStorage.getItem("mhb_cookie_consent") || "all") !== "essential"; } catch { return true; }
}

function loadTags(a) {
  if (a.ga4_id || a.gads_id) {
    const first = a.ga4_id || a.gads_id;
    inject("mhb-gtag-src", `<script src="https://www.googletagmanager.com/gtag/js?id=${first}"></script>`);
    inject("mhb-gtag-init", `<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}window.gtag=gtag;gtag('js',new Date());${a.ga4_id ? `gtag('config','${a.ga4_id}');` : ""}${a.gads_id ? `gtag('config','${a.gads_id}');` : ""}</script>`);
  }
  if (a.gtm_id) inject("mhb-gtm", `<script>(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],j=d.createElement(s);j.async=true;j.src='https://www.googletagmanager.com/gtm.js?id='+i;f.parentNode.insertBefore(j,f);})(window,document,'script','dataLayer','${a.gtm_id}');</script>`);
  if (a.pixel_id) inject("mhb-pixel", `<script>!function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){n.callMethod?n.callMethod.apply(n,arguments):n.queue.push(arguments)};if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}(window,document,'script','https://connect.facebook.net/en_US/fbevents.js');fbq('init','${a.pixel_id}');fbq('track','PageView');</script>`);
  document.documentElement.dataset.mhbAnalytics = [a.ga4_id && "ga4", a.gtm_id && "gtm", a.pixel_id && "pixel", a.gads_id && "gads"].filter(Boolean).join(",");
}

export function useAnalytics(propertyId) {
  useEffect(() => {
    if (!propertyId) return;
    let alive = true;
    const boot = () => axios.get(`${API}/site-builder/public/analytics/${propertyId}`).then(({ data }) => {
      if (!alive) return;
      cfgCache = data.analytics || {};
      if (hasConsent()) loadTags(cfgCache);
    }).catch(() => {});
    boot();
    const onConsent = () => { if (cfgCache && hasConsent()) loadTags(cfgCache); };
    window.addEventListener("mhb-consent", onConsent);
    return () => { alive = false; window.removeEventListener("mhb-consent", onConsent); };
  }, [propertyId]);
}

const FB_MAP = { view_item_list: "ViewContent", view_item: "ViewContent", add_to_cart: "AddToCart", begin_checkout: "InitiateCheckout", add_payment_info: "AddPaymentInfo", purchase: "Purchase" };

export function trackEvent(name, params) {
  if (!hasConsent()) return;
  const p = params || {};
  try {
    if (window.gtag) window.gtag("event", name, p);
    if (window.fbq) { const std = FB_MAP[name]; if (std) window.fbq("track", std, { value: p.value, currency: p.currency, content_ids: (p.items || []).map((i) => i.item_id), content_type: "product", num_items: (p.items || []).length }); else window.fbq("trackCustom", name, p); }
    if (window.dataLayer) { if (name in FB_MAP) window.dataLayer.push({ ecommerce: null }); window.dataLayer.push({ event: name, ...(name in FB_MAP ? { ecommerce: p } : p) }); }
    if (name === "purchase" && cfgCache?.gads_id && cfgCache?.gads_label && window.gtag) {
      window.gtag("event", "conversion", { send_to: `${cfgCache.gads_id}/${cfgCache.gads_label}`, value: p.value, currency: p.currency, transaction_id: p.transaction_id });
    }
  } catch { /* ignore */ }
}

export const gaItem = (room, plan, qty, price) => ({ item_id: room?.id, item_name: room?.name, item_variant: plan?.name || plan?.id || "standard", quantity: qty || 1, price: Number(price || room?.price_per_night || room?.base_price || 0) });

export function trackPurchaseOnce(ref, params) {
  if (!ref || fired.has(ref)) return;
  fired.add(ref); trackEvent("purchase", { transaction_id: ref, ...params });
}

// ---------- Dönüşüm hunisi (birinci taraf, çerez onayından bağımsız — kişisel veri yok) ----------
function sessionId() {
  try { let s = sessionStorage.getItem("mhb_be_sid"); if (!s) { s = `s_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`; sessionStorage.setItem("mhb_be_sid", s); } return s; } catch { return `s_${Date.now()}`; }
}
function device() { const w = window.innerWidth; return w < 768 ? "mobile" : w < 1024 ? "tablet" : "desktop"; }
function utm() {
  try {
    const saved = sessionStorage.getItem("mhb_be_utm"); if (saved) return JSON.parse(saved);
    const q = new URLSearchParams(window.location.search);
    const ref = document.referrer ? new URL(document.referrer).hostname.replace(/^www\./, "") : "";
    const u = { source: q.get("utm_source") || (ref && !ref.includes(window.location.hostname) ? ref : "direct"), medium: q.get("utm_medium") || (q.get("gclid") ? "cpc" : ref ? "referral" : "none"), campaign: q.get("utm_campaign") || "" };
    sessionStorage.setItem("mhb_be_utm", JSON.stringify(u)); return u;
  } catch { return { source: "direct", medium: "none", campaign: "" }; }
}
const funnelSent = new Set();
export function trackFunnel(propertyId, step, meta) {
  if (!propertyId || !step) return;
  const key = `${propertyId}:${step}`; if (funnelSent.has(key) && step !== "room_view") return; funnelSent.add(key);
  const u = utm();
  axios.post(`${API}/booking/funnel/event`, { property_id: propertyId, session_id: sessionId(), step, device: device(), lang: (document.documentElement.lang || "").slice(0, 5), ...u, meta: meta || {} }).catch(() => {});
}
