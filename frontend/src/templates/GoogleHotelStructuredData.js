import { useEffect } from "react";

/**
 * GoogleHotelStructuredData
 * Injects JSON-LD structured data for Google Hotel Search integration.
 * This helps the property appear in Google Maps with "Official Site" pricing.
 */
export function GoogleHotelStructuredData({ property, rooms, reviews, templateSettings }) {
  useEffect(() => {
    if (!property) return;

    const hotelName = templateSettings?.hotel_name || property.name || "Hotel";
    const address = templateSettings?.address || `${property.city || "London"}, ${property.country || "United Kingdom"}`;
    const heroImage = templateSettings?.hero_image_url || "";
    const lowestPrice = rooms?.length > 0 ? Math.min(...rooms.map(r => r.base_price)) : 0;
    const avgRating = property.avg_rating || 0;
    const totalReviews = property.total_reviews || 0;

    const schema = {
      "@context": "https://schema.org",
      "@type": "Hotel",
      "name": hotelName,
      "description": templateSettings?.description || `Book your stay at ${hotelName}`,
      "address": {
        "@type": "PostalAddress",
        "addressLocality": property.city || "London",
        "addressCountry": property.country || "United Kingdom",
        "streetAddress": address,
      },
      "telephone": templateSettings?.contact_phone || "",
      "email": templateSettings?.contact_email || "",
      "url": window.location.href,
      ...(heroImage && { "image": heroImage }),
      ...(avgRating > 0 && {
        "aggregateRating": {
          "@type": "AggregateRating",
          "ratingValue": (avgRating * 2).toFixed(1),
          "bestRating": "10",
          "reviewCount": totalReviews,
        }
      }),
      ...(lowestPrice > 0 && {
        "priceRange": `£${lowestPrice}+`,
        "offers": {
          "@type": "AggregateOffer",
          "lowPrice": lowestPrice,
          "priceCurrency": "GBP",
          "offerCount": rooms?.length || 0,
        }
      }),
      "checkinTime": property.policies?.check_in_from || "15:00",
      "checkoutTime": property.policies?.check_out_until || "11:00",
      ...(property.facilities?.length > 0 && {
        "amenityFeature": property.facilities.map(f => ({
          "@type": "LocationFeatureSpecification",
          "name": f,
          "value": true,
        }))
      }),
    };

    // Inject or update script tag
    const scriptId = "hotel-structured-data";
    let script = document.getElementById(scriptId);
    if (!script) {
      script = document.createElement("script");
      script.id = scriptId;
      script.type = "application/ld+json";
      document.head.appendChild(script);
    }
    script.textContent = JSON.stringify(schema);

    return () => {
      const el = document.getElementById(scriptId);
      if (el) el.remove();
    };
  }, [property, rooms, reviews, templateSettings]);

  return null; // This component renders nothing visible
}
