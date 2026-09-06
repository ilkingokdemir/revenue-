export const SITE_THEMES = {
  classic: { bg: "#faf6f0", text: "#292524", muted: "#78716c", card: "#ffffff", cardBorder: "#f3e8d3", accent: "#b45309", accentText: "#ffffff", heroBg: "linear-gradient(135deg,#92400e,#d97706)", heroText: "#ffffff", nav: "#fffaf3", heading: "'Georgia', 'Times New Roman', serif", radius: "16px" },
  modern: { bg: "#0c0a09", text: "#f5f5f4", muted: "#a8a29e", card: "#1c1917", cardBorder: "#292524", accent: "#06b6d4", accentText: "#0c0a09", heroBg: "linear-gradient(135deg,#1c1917,#083344)", heroText: "#ffffff", nav: "#0c0a09", heading: "'Outfit', system-ui, sans-serif", radius: "6px" },
  boutique: { bg: "#ffffff", text: "#1c1917", muted: "#78716c", card: "#fafaf9", cardBorder: "#e7e5e4", accent: "#1c1917", accentText: "#ffffff", heroBg: "linear-gradient(135deg,#ffe4e6,#f5f5f4)", heroText: "#1c1917", nav: "#ffffff", heading: "'Manrope', system-ui, sans-serif", radius: "0px" },
  coastal: { bg: "#f7f3ea", text: "#0f2f3a", muted: "#5b7480", card: "#ffffff", cardBorder: "#e6ddc9", accent: "#0f4c5c", accentText: "#ffffff", heroBg: "linear-gradient(160deg,#0f4c5c,#3a8fa3 70%,#e9c46a)", heroText: "#ffffff", nav: "#f7f3ea", heading: "'Manrope', system-ui, sans-serif", radius: "20px" },
  urban: { bg: "#1c1c1e", text: "#f2f2f2", muted: "#9a9a9a", card: "#262628", cardBorder: "#333336", accent: "#f5b700", accentText: "#1c1c1e", heroBg: "linear-gradient(135deg,#111113,#2b2b2e)", heroText: "#ffffff", nav: "#1c1c1e", heading: "'Outfit', system-ui, sans-serif", radius: "10px" },
  nature: { bg: "#f4f7f1", text: "#1f2d22", muted: "#5e6f62", card: "#ffffff", cardBorder: "#dfe7dc", accent: "#2f5d3a", accentText: "#ffffff", heroBg: "linear-gradient(160deg,#1f3d27,#2f5d3a 60%,#8fb996)", heroText: "#ffffff", nav: "#f4f7f1", heading: "'Georgia', serif", radius: "14px" },
};

export const SITE_PAGES = [
  { id: "home", label: "Ana Sayfa", blocks: null },
  { id: "rooms", label: "Odalar", blocks: ["rooms", "availability"] },
  { id: "gallery", label: "Galeri", blocks: ["gallery"] },
  { id: "location", label: "Konum", blocks: ["map", "amenities"] },
  { id: "faq", label: "SSS", blocks: ["faq"] },
  { id: "contact", label: "İletişim", blocks: ["contact", "map"] },
  { id: "blog", label: "Blog & Kampanyalar", blocks: ["posts"] },
];
export const PAGE_LABELS = { tr: { home: "Ana Sayfa", rooms: "Odalar", gallery: "Galeri", location: "Konum", faq: "SSS", contact: "İletişim", blog: "Blog & Kampanyalar" },
  en: { home: "Home", rooms: "Rooms", gallery: "Gallery", location: "Location", faq: "FAQ", contact: "Contact", blog: "Blog & Offers" },
  de: { home: "Start", rooms: "Zimmer", gallery: "Galerie", location: "Lage", faq: "FAQ", contact: "Kontakt", blog: "Blog & Angebote" } };
export const UI = { tr: { book: "Rezervasyon Yap", rooms: "Odaları Gör", about: "Hakkımızda", amen: "Olanaklar", from: "gece'den", avail: "Müsaitliğe bak →", back: "← Geri", readMore: "Devamını oku", offer: "Kampanya", allRooms: "Tüm odalar", ourRooms: "Odalarımız", reviews: "Misafirlerimiz Ne Diyor", location: "Konum", faq: "Sık Sorulan Sorular", contact: "Bize Ulaşın", gallery: "Galeri", posts: "Blog & Kampanyalar", directions: "Yol tarifi al", send: "Gönder", ci: "Giriş", co: "Çıkış", guests: "Misafir", adults: "yetişkin", search: "Müsaitlik & Fiyat", noRooms: "Bu tarihlerde müsait oda bulunamadı.", nights: "gece", reserve: "Rezerve Et", sent: "Mesajınız alındı, en kısa sürede dönüş yapacağız." },
  en: { book: "Book now", rooms: "See rooms", about: "About us", amen: "Amenities", from: "per night from", avail: "Check availability →", back: "← Back", readMore: "Read more", offer: "Offer", allRooms: "All rooms", ourRooms: "Our rooms", reviews: "What our guests say", location: "Location", faq: "Frequently asked questions", contact: "Contact us", gallery: "Gallery", posts: "Blog & Offers", directions: "Get directions", send: "Send", ci: "Check-in", co: "Check-out", guests: "Guests", adults: "adults", search: "Availability & rates", noRooms: "No rooms available for these dates.", nights: "nights", reserve: "Reserve", sent: "Thanks — we received your message and will reply shortly." },
  de: { book: "Jetzt buchen", rooms: "Zimmer ansehen", about: "Über uns", amen: "Ausstattung", from: "pro Nacht ab", avail: "Verfügbarkeit prüfen →", back: "← Zurück", readMore: "Weiterlesen", offer: "Angebot", allRooms: "Alle Zimmer", ourRooms: "Unsere Zimmer", reviews: "Das sagen unsere Gäste", location: "Lage", faq: "Häufige Fragen", contact: "Kontakt", gallery: "Galerie", posts: "Blog & Angebote", directions: "Route planen", send: "Senden", ci: "Anreise", co: "Abreise", guests: "Gäste", adults: "Erwachsene", search: "Verfügbarkeit & Preise", noRooms: "Keine Zimmer für diese Daten verfügbar.", nights: "Nächte", reserve: "Reservieren", sent: "Danke — wir haben Ihre Nachricht erhalten und melden uns bald." } };

export const BLOCK_LABELS = {
  hero: "Hero (başlık + CTA)", posts: "Blog & Kampanyalar", availability: "Canlı müsaitlik arama", about: "Hakkımızda", rooms: "Odalar",
  amenities: "Olanaklar", gallery: "Galeri", reviews: "Misafir yorumları", map: "Konum / Harita", faq: "SSS", contact: "İletişim formu",
};
