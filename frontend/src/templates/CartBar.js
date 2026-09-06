import { ShoppingCart, X, ArrowRight } from "@phosphor-icons/react";
import { useLanguage } from "../i18n/LanguageContext";
import { planNightPrice, planName, roomNightBase } from "./RatePlanRows";

export function CartBar({ t, cart, nights, onRemove, onContinue, fmt = (v) => `£${Math.round(v)}`, memberPct = 0 }) {
  const { t: tr, lang } = useLanguage();
  if (!cart?.length) return null;
  const roomsTotal = cart.reduce((s, c) => s + c.qty, 0);
  const total = cart.reduce((s, c) => s + planNightPrice(roomNightBase(c.room), c.plan) * (1 - memberPct / 100) * nights * c.qty + (Number(c.room.extra_bed_price) || 0) * nights * (c.extraBeds || 0), 0);
  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 animate-in slide-in-from-bottom-4" data-testid="cart-bar">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-4">
        <div className="bg-white/95 backdrop-blur-md border border-gray-200 shadow-2xl p-3 sm:p-4 flex flex-col sm:flex-row sm:items-center gap-3" style={{ borderRadius: t.borderRadius }}>
          <div className="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 text-white" style={{ background: t.colors.accent }}>
            <ShoppingCart size={18} weight="fill" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-xs text-slate-500 font-medium">{tr("cart.yourStay", { rooms: roomsTotal, nights })}</div>
            <div className="flex flex-wrap gap-1.5 mt-1">
              {cart.map((c, i) => (
                <span key={i} className="inline-flex items-center gap-1 text-xs bg-slate-100 text-slate-700 rounded-full pl-2.5 pr-1 py-0.5" data-testid={`cart-item-${i}`}>
                  {c.qty}× {c.room.name}{c.plan ? ` · ${planName(c.plan, lang)}` : ""}{c.extraBeds ? ` · +${c.extraBeds} ${tr("extra.bed")}` : ""}
                  <button type="button" onClick={() => onRemove(i)} className="w-5 h-5 rounded-full hover:bg-slate-200 flex items-center justify-center text-slate-500" aria-label="remove" data-testid={`cart-remove-${i}`}><X size={11} /></button>
                </span>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-4 sm:justify-end">
            <div className="text-right">
              <div className="text-[11px] text-slate-500">{tr("summary.total")}</div>
              <div className="text-xl font-bold text-slate-900" data-testid="cart-total">{fmt(total)}</div>
            </div>
            <button type="button" onClick={onContinue} className="px-5 py-3 rounded-lg font-bold text-sm text-white flex items-center gap-2 shadow-lg transition-transform hover:scale-[1.03]"
              style={{ background: t.colors.accent, borderRadius: t.borderRadius }} data-testid="cart-continue-btn">
              {tr("cart.continue")} <ArrowRight size={16} weight="bold" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
