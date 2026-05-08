import { ShieldCheck, ArrowDown } from "@phosphor-icons/react";
import { useLanguage } from "../i18n/LanguageContext";

export function PriceComparisonWidget({ t, roomPrice, settings }) {
  const { t: tr } = useLanguage();

  if (!settings?.show_price_comparison) return null;

  const markupPercent = settings.ota_markup_percent || 18;
  const otaPrice = Math.round(roomPrice * (1 + markupPercent / 100));
  const savings = otaPrice - roomPrice;

  return (
    <div className="bg-gradient-to-r from-emerald-50 to-teal-50 border border-emerald-200 rounded-xl p-4 mb-6"
      style={{ borderRadius: t.borderRadius }} data-testid="price-comparison-widget">
      <div className="flex items-center gap-2 mb-3">
        <ShieldCheck size={18} weight="fill" className="text-emerald-600" />
        <span className="font-semibold text-emerald-800 text-sm">
          {(settings.direct_saving_label || "Book direct & save {percent}%").replace("{percent}", markupPercent)}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-2">
        {/* OTA prices */}
        <div className="bg-white/60 rounded-lg p-2.5 text-center border border-gray-200">
          <span className="text-[10px] text-slate-500 block mb-1">{settings.booking_com_label || "Booking.com"}</span>
          <span className="text-sm font-bold text-slate-400 line-through">&pound;{otaPrice}</span>
        </div>
        <div className="bg-white/60 rounded-lg p-2.5 text-center border border-gray-200">
          <span className="text-[10px] text-slate-500 block mb-1">{settings.expedia_label || "Expedia"}</span>
          <span className="text-sm font-bold text-slate-400 line-through">&pound;{Math.round(otaPrice * 0.97)}</span>
        </div>
        {/* Direct price */}
        <div className="bg-emerald-600 rounded-lg p-2.5 text-center text-white relative overflow-hidden">
          <span className="text-[10px] opacity-80 block mb-1">Direct Price</span>
          <span className="text-sm font-bold">&pound;{roomPrice}</span>
          <div className="absolute -top-1 -right-1 bg-yellow-400 text-[8px] font-bold text-slate-900 px-1.5 py-0.5 rounded-bl-lg">
            <ArrowDown size={8} weight="bold" className="inline" /> SAVE
          </div>
        </div>
      </div>
      <p className="text-[11px] text-emerald-700 mt-2 text-center font-medium">
        You save &pound;{savings} per night by booking directly with us
      </p>
    </div>
  );
}
