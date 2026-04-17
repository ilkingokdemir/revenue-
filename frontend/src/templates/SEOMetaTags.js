import { useEffect } from "react";

/**
 * SEO Meta Tags — Dynamically injects meta tags for hotel booking pages.
 * Handles: title, description, Open Graph, Twitter Cards, canonical URL.
 */
export function SEOMetaTags({ property, templateSettings, rooms }) {
  useEffect(() => {
    if (!property) return;

    const hotelName = templateSettings?.hotel_name || property.name || "Hotel";
    const description = templateSettings?.seo_description ||
      templateSettings?.description ||
      `Book your stay at ${hotelName}. Best rates guaranteed when you book direct. Premium rooms from ${rooms?.length ? `£${Math.min(...rooms.map(r => r.base_price || 99))}` : "£79"}/night.`;
    const title = templateSettings?.seo_title || `${hotelName} — Book Direct | Best Rate Guarantee`;
    const image = templateSettings?.hero_image_url || templateSettings?.og_image || "";
    const url = window.location.href;
    const siteName = hotelName;
    const locale = templateSettings?.locale || "en_GB";
    const keywords = templateSettings?.seo_keywords ||
      `${hotelName}, hotel, book direct, accommodation, ${property.city || "London"}, best rate, rooms`;

    // Set document title
    document.title = title;

    // Helper to set or create meta tag
    const setMeta = (attr, key, content) => {
      if (!content) return;
      let el = document.querySelector(`meta[${attr}="${key}"]`);
      if (!el) {
        el = document.createElement("meta");
        el.setAttribute(attr, key);
        document.head.appendChild(el);
      }
      el.setAttribute("content", content);
    };

    // Standard meta tags
    setMeta("name", "description", description);
    setMeta("name", "keywords", keywords);
    setMeta("name", "author", hotelName);
    setMeta("name", "robots", "index, follow");

    // Open Graph tags
    setMeta("property", "og:title", title);
    setMeta("property", "og:description", description);
    setMeta("property", "og:type", "website");
    setMeta("property", "og:url", url);
    setMeta("property", "og:site_name", siteName);
    setMeta("property", "og:locale", locale);
    if (image) setMeta("property", "og:image", image);

    // Twitter Card tags
    setMeta("name", "twitter:card", "summary_large_image");
    setMeta("name", "twitter:title", title);
    setMeta("name", "twitter:description", description);
    if (image) setMeta("name", "twitter:image", image);

    // Canonical URL
    let canonical = document.querySelector('link[rel="canonical"]');
    if (!canonical) {
      canonical = document.createElement("link");
      canonical.setAttribute("rel", "canonical");
      document.head.appendChild(canonical);
    }
    canonical.setAttribute("href", url.split("?")[0]);

    return () => {
      // Cleanup on unmount
      document.title = "My Hotel Box";
    };
  }, [property, templateSettings, rooms]);

  return null;
}
