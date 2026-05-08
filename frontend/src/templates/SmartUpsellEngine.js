import { useState, useEffect } from "react";
import {
  Clock, CoffeeBean, Car, Champagne, FlowerLotus, ArrowUp,
  CarSimple, PawPrint, Heart, CheckCircle, Sparkle,
} from "@phosphor-icons/react";
import { useLanguage } from "../i18n/LanguageContext";

const ICONS = {
  "clock": Clock, "clock-afternoon": Clock, "coffee": CoffeeBean,
  "car": Car, "champagne": Champagne, "flower-lotus": FlowerLotus,
  "arrow-up": ArrowUp, "car-simple": CarSimple, "paw-print": PawPrint,
  "heart": Heart,
};

const PRICE_LABELS = {
  per_stay: "per stay",
  per_night: "per night",
  per_person: "per person",
  per_person_per_night: "per person/night",
};

export function SmartUpsellEngine({ t, upsells, selectedUpsells, onToggle, nights, adults }) {
  const { t: tr } = useLanguage();
  const [showAll, setShowAll] = useState(false);

  if (!upsells || upsells.length === 0) return null;

  // Show top 3 by default, expand to show all
  const visible = showAll ? upsells : upsells.slice(0, 3);
  const hasMore = upsells.length > 3;

  const getPrice = (item) => {
    if (item.price_type === "per_night") return item.price * nights;
    if (item.price_type === "per_person") return item.price * adults;
    if (item.price_type === "per_person_per_night") return item.price * adults * nights;
    return item.price;
  };

  return (
    <div className="bg-gradient-to-br from-amber-50 to-orange-50 rounded-xl border border-amber-200 p-5"
      style={{ borderRadius: t.borderRadius }} data-testid="upsell-engine">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-8 h-8 rounded-full bg-amber-100 flex items-center justify-center">
          <Sparkle size={16} weight="fill" className="text-amber-600" />
        </div>
        <div>
          <h3 className="font-semibold text-slate-900 text-base" style={{ fontFamily: t.fonts.heading }}>
            {tr("addons.title")}
          </h3>
          <p className="text-xs text-slate-500">Recommended for your stay</p>
        </div>
      </div>

      <div className="space-y-2">
        {visible.map((item) => {
          const isSelected = selectedUpsells.find(u => u.id === item.id);
          const Icon = ICONS[item.icon] || Sparkle;
          const totalPrice = getPrice(item);
          return (
            <button
              key={item.id}
              onClick={() => onToggle(item)}
              className="w-full flex items-center gap-3 p-3 rounded-lg border-2 text-left transition-all hover:shadow-sm"
              style={{
                borderColor: isSelected ? t.colors.accent : "#e5e7eb",
                background: isSelected ? `${t.colors.accent}08` : "white",
                borderRadius: t.borderRadius,
              }}
              data-testid={`upsell-${item.id}`}
            >
              <div className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                style={{ background: isSelected ? `${t.colors.accent}15` : "#f8fafc" }}>
                <Icon size={20} weight="fill"
                  style={{ color: isSelected ? t.colors.accent : "#64748b" }} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-slate-800">{item.name}</span>
                  {isSelected && <CheckCircle size={14} weight="fill" style={{ color: t.colors.accent }} />}
                </div>
                <span className="text-xs text-slate-500 block truncate">{item.description}</span>
              </div>
              <div className="text-right flex-shrink-0">
                <span className="text-sm font-bold text-slate-900">&pound;{totalPrice.toFixed(0)}</span>
                <span className="text-[10px] text-slate-400 block">
                  {item.price_type !== "per_stay" ? `£${item.price} ${PRICE_LABELS[item.price_type]}` : "total"}
                </span>
              </div>
            </button>
          );
        })}
      </div>

      {hasMore && (
        <button
          onClick={() => setShowAll(!showAll)}
          className="w-full text-center text-sm font-medium mt-3 py-2 hover:underline"
          style={{ color: t.colors.accent }}
          data-testid="show-more-upsells"
        >
          {showAll ? "Show less" : `Show ${upsells.length - 3} more options`}
        </button>
      )}

      {selectedUpsells.length > 0 && (
        <div className="mt-3 pt-3 border-t border-amber-200 flex items-center justify-between">
          <span className="text-xs text-slate-500">{selectedUpsells.length} extras selected</span>
          <span className="text-sm font-bold text-slate-900">
            +&pound;{selectedUpsells.reduce((sum, u) => sum + getPrice(u), 0).toFixed(0)}
          </span>
        </div>
      )}
    </div>
  );
}
