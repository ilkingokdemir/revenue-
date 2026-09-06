import { useEffect } from "react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function inject(id, html) {
  if (document.getElementById(id)) return;
  const tpl = document.createElement("div"); tpl.innerHTML = html;
  const s = document.createElement("script"); s.id = id;
  const src = tpl.querySelector("script")?.getAttribute("src");
  if (src) s.src = src; else s.textContent = tpl.textContent;
  s.async = true; document.head.appendChild(s);
}

export function useAnalytics(propertyId) {
  useEffect(() => {
    if (!propertyId) return;
    let consent = "all";
    try { consent = localStorage.getItem("mhb_cookie_consent") || "all"; } catch { /* ignore */ }
    if (consent === "essential") return;
    axios.get(`${API}/site-builder/public/analytics/${propertyId}`).then(({ data }) => {
      const a = data.analytics || {};
      if (a.ga4_id) {
        inject("mhb-ga4-src", `<script src="https://www.googletagmanager.com/gtag/js?id=${a.ga4_id}"></script>`);
        inject("mhb-ga4-init", `<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag('js',new Date());gtag('config','${a.ga4_id}');</script>`);
        window.mhbTrack = (ev, params) => window.gtag && window.gtag("event", ev, params || {});
      }
      if (a.gtm_id) inject("mhb-gtm", `<script>(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],j=d.createElement(s);j.async=true;j.src='https://www.googletagmanager.com/gtm.js?id='+i;f.parentNode.insertBefore(j,f);})(window,document,'script','dataLayer','${a.gtm_id}');</script>`);
      if (a.pixel_id) inject("mhb-pixel", `<script>!function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){n.callMethod?n.callMethod.apply(n,arguments):n.queue.push(arguments)};if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}(window,document,'script','https://connect.facebook.net/en_US/fbevents.js');fbq('init','${a.pixel_id}');fbq('track','PageView');</script>`);
      document.documentElement.dataset.mhbAnalytics = [a.ga4_id && "ga4", a.gtm_id && "gtm", a.pixel_id && "pixel"].filter(Boolean).join(",");
    }).catch(() => {});
  }, [propertyId]);
}

export function trackEvent(name, params) {
  try { window.gtag && window.gtag("event", name, params || {}); window.fbq && window.fbq("trackCustom", name, params || {}); window.dataLayer && window.dataLayer.push({ event: name, ...(params || {}) }); } catch { /* ignore */ }
}
