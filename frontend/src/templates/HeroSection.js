import {
  Star, MapPin, Heart, ShieldCheck, Phone,
  Sparkle, Medal, Baby, Briefcase, TreePalm, Crown, Buildings,
} from "@phosphor-icons/react";
import { SearchWidget } from "./SearchWidget";

const platformIcons = {
  "Booking.com": Buildings, "Airbnb": Heart, "Expedia": Sparkle, "Hotels.com": Medal,
};

export function HeroSection({ t, property, ratingScore, getRatingLabel, searchProps }) {
  const PlatformIcon = platformIcons[t.platform] || Buildings;

  if (t.layout === "airbnb") {
    const defaultImages = [
      "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=800",
      "https://images.unsplash.com/photo-1631049307264-da0ec9d70304?w=400",
      "https://images.unsplash.com/photo-1590490360182-c33d57733427?w=400",
      "https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?w=400",
      "https://images.unsplash.com/photo-1578683010236-d716f9a3f461?w=400",
    ];
    const galleryImgs = t.custom?.galleryImages?.length >= 5 ? t.custom.galleryImages : defaultImages;
    const mainImg = t.custom?.heroImageUrl || galleryImgs[0];
    return (
      <>
        <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-8" data-testid="hero-section">
          <div className="grid grid-cols-4 grid-rows-2 gap-2 h-[400px] rounded-2xl overflow-hidden mb-6" style={{ borderRadius: t.borderRadius }}>
            <div className="col-span-2 row-span-2 bg-slate-200 relative overflow-hidden">
              <img src={mainImg} alt="Hotel" className="w-full h-full object-cover hover:scale-105 transition-transform duration-500" />
            </div>
            {galleryImgs.slice(1, 5).map((src, i) => (
              <div key={i} className="bg-slate-200 overflow-hidden relative">
                <img src={src} alt="" className="w-full h-full object-cover hover:scale-105 transition-transform duration-500" loading="lazy" />
              </div>
            ))}
          </div>
          <div className="flex items-start justify-between pb-6 border-b border-gray-200">
            <div>
              <h1 className="text-3xl font-bold text-slate-900" style={{ fontFamily: t.fonts.heading }}>{t.custom?.hotelName || property?.name}</h1>
              <p className="text-slate-500 mt-1 flex items-center gap-1"><MapPin size={14} /> {t.custom?.address || `${property?.city || "London"}, ${property?.country || "United Kingdom"}`}</p>
              {t.custom?.tagline && <p className="text-slate-600 text-sm mt-1">{t.custom.tagline}</p>}
              <div className="flex items-center gap-3 mt-2">
                <div className="flex items-center gap-1">
                  <Star size={16} weight="fill" style={{ color: t.colors.accent }} />
                  <span className="font-bold text-slate-900">{ratingScore}</span>
                  <span className="text-slate-500 text-sm">{getRatingLabel(parseFloat(ratingScore))}</span>
                </div>
                <span className="text-slate-400">&middot;</span>
                <span className="text-sm text-slate-500">{property?.total_reviews || 0} reviews</span>
              </div>
            </div>
            <div className="flex gap-2">
              <button className="p-2 border border-gray-300 rounded-lg hover:bg-gray-50" data-testid="hero-wishlist-btn"><Heart size={20} /></button>
            </div>
          </div>
        </section>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <SearchWidget t={t} {...searchProps} />
        </div>
      </>
    );
  }

  // Standard hero (Booking.com, Expedia, Hotels.com styles)
  const heroImage = t.custom?.heroImageUrl || "https://images.pexels.com/photos/9119725/pexels-photo-9119725.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940";
  const displayName = t.custom?.hotelName || property?.name || "Book Your Stay";
  const subtitle = t.custom?.tagline || (property?.city ? `${property.city}, ${property.country}` : "Find your perfect room at the best price");
  return (
    <section className="relative bg-cover bg-center" style={{ backgroundImage: `url(${heroImage})`, minHeight: "480px" }} data-testid="hero-section">
      <div className="absolute inset-0" style={{ background: t.colors.heroOverlay }} />
      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 sm:py-24">
        <div className="text-center text-white mb-10">
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight mb-3" style={{ fontFamily: t.fonts.heading }} data-testid="hero-title">
            {displayName}
          </h1>
          <p className="text-lg sm:text-xl max-w-2xl mx-auto" style={{ opacity: 0.8 }}>
            {subtitle}
          </p>
          {t.custom?.welcomeMessage && (
            <p className="text-base max-w-xl mx-auto mt-2" style={{ opacity: 0.7 }}>{t.custom.welcomeMessage}</p>
          )}
          {property?.avg_rating > 0 && t.showRatingBadge && (
            <div className="flex items-center justify-center gap-3 mt-4">
              <div className="font-bold px-2.5 py-1 rounded-tl-lg rounded-br-lg rounded-tr-sm rounded-bl-sm text-sm" style={{ background: t.colors.ratingBg, color: t.colors.ratingText }}>
                {ratingScore}
              </div>
              <span className="font-semibold text-white">{getRatingLabel(parseFloat(ratingScore))}</span>
              <span style={{ opacity: 0.7 }}>&middot; {property.total_reviews} reviews</span>
            </div>
          )}
          {/* Platform-specific badges */}
          {t.platform === "Expedia" && (
            <div className="flex items-center justify-center gap-2 mt-3">
              <span className="text-xs px-3 py-1 rounded-full font-semibold" style={{ background: t.colors.accent, color: t.colors.primary }}>
                <Sparkle size={12} weight="fill" className="inline mr-1" />Member Price Available
              </span>
            </div>
          )}
          {t.platform === "Hotels.com" && t.id === "hotels-rewards" && (
            <div className="flex items-center justify-center gap-2 mt-3">
              <span className="text-xs px-3 py-1 rounded-full font-semibold bg-white/20 text-white">
                <Medal size={12} weight="fill" className="inline mr-1" />Collect stamps with every stay
              </span>
            </div>
          )}
          {t.id === "hotels-family" && (
            <div className="flex items-center justify-center gap-2 mt-3">
              <span className="text-xs px-3 py-1 rounded-full font-semibold bg-white/20 text-white">
                <Baby size={12} weight="fill" className="inline mr-1" />Family Friendly Property
              </span>
            </div>
          )}
          {t.id === "booking-business" && (
            <div className="flex items-center justify-center gap-2 mt-3">
              <span className="text-xs px-3 py-1 rounded-full font-semibold bg-white/20 text-white">
                <Briefcase size={12} weight="fill" className="inline mr-1" />Business Travel Ready
              </span>
            </div>
          )}
          {t.id === "booking-resort" && (
            <div className="flex items-center justify-center gap-2 mt-3">
              <span className="text-xs px-3 py-1 rounded-full font-semibold bg-white/20 text-white">
                <TreePalm size={12} weight="fill" className="inline mr-1" />Resort & Spa
              </span>
            </div>
          )}
          {t.id === "booking-boutique" && (
            <div className="flex items-center justify-center gap-2 mt-3">
              <span className="text-xs px-3 py-1 rounded-full font-semibold bg-white/20 text-white">
                <Crown size={12} weight="fill" className="inline mr-1" />Boutique Collection
              </span>
            </div>
          )}
        </div>
        <SearchWidget t={t} {...searchProps} />
      </div>
    </section>
  );
}
