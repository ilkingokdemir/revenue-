import { useState } from "react";
import { CheckCircle, XCircle, Coffee, ShieldCheck, Plus, Minus, Check } from "@phosphor-icons/react";
import { useLanguage } from "../i18n/LanguageContext";

export const planNightPrice = (base, plan) => {
  if (!plan) return Number(base) || 0;
  const v = Number(plan.adjustment_value) || 0;
  return plan.adjustment_type === "fixed_per_night" ? Number(base) + v : Number(base) * (1 + v / 100);
};

export const planName = (plan, lang) => (lang === "tr" && plan.name_tr) || (lang === "de" && plan.name_de) || plan.name;
export const roomNightBase = (room) => Number(room.avg_nightly ?? room.base_price) || 0;
const gbp = (v) => `£${Math.round(v)}`;

export function RatePlanRows({ t, room, plans, nights, cart, onAdd, fmt = gbp, memberPct = 0 }) {
  const { t: tr, lang } = useLanguage();
  const [qty, setQty] = useState({});
  const [beds, setBeds] = useState({});
  const ex = room.price_explanation;
  const extraBedPrice = Number(room.extra_bed_price) || 0;
  const list = plans?.length ? plans : [{ id: "", name: "Standard", adjustment_type: "pct", adjustment_value: 0, cancellation_type: room.free_cancellation ? "free" : "non_refundable", includes: room.breakfast_included ? ["breakfast"] : [] }];
  const maxQty = Math.max(1, room.available_rooms ?? 5);

  if (room.los_block) {
    return <div className="border-t border-gray-100 p-4 text-sm font-medium text-amber-700 bg-amber-50" data-testid={`los-block-${room.id}`}>{room.los_block[`message_${lang}`] || room.los_block.message_tr || room.los_block.message}</div>;
  }
  return (
    <div className="border-t border-gray-100 divide-y divide-gray-100" data-testid={`rate-plans-${room.id}`}>
      {ex && ex.vs_base_pct !== 0 && (
        <div className="px-4 py-2 text-xs flex items-center gap-1.5" style={{ color: ex.vs_base_pct < 0 ? t.colors.success : t.colors.urgency }} data-testid={`price-explain-${room.id}`}>
          {ex.vs_base_pct < 0 ? "▼" : "▲"} {ex[`headline_${lang}`] || ex.headline_en}
        </div>
      )}
      {memberPct > 0 && <div className="px-4 py-2 text-xs font-semibold flex items-center gap-1.5" style={{ color: t.colors.success }} data-testid={`member-rate-${room.id}`}>★ {tr("member.applied", { pct: memberPct })}</div>}
      {list.map((p, idx) => {
        const base = roomNightBase(room);
        const nightly = planNightPrice(base, p) * (1 - memberPct / 100);
        const q = qty[p.id] || 1;
        const b = beds[p.id] || 0;
        const total = nightly * nights * q + extraBedPrice * nights * b;
        const inCart = cart?.find((c) => c.room.id === room.id && (c.plan?.id || "") === (p.id || ""));
        const firstNightly = planNightPrice(base, list[0]);
        const saving = idx > 0 && nightly < firstNightly ? Math.round((firstNightly - nightly) / firstNightly * 100) : 0;
        return (
          <div key={p.id || idx} className="grid grid-cols-1 md:grid-cols-[1.4fr_1fr_auto] gap-3 md:gap-4 p-4 items-center transition-colors hover:bg-slate-50/60"
            style={inCart ? { background: `${t.colors.accent}08` } : undefined} data-testid={`rate-plan-${room.id}-${p.code || idx}`}>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-semibold text-slate-900 text-sm">{planName(p, lang)}</span>
                {p.badge === "popular" && <span className="text-[10px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wide text-white" style={{ background: t.colors.accent }}>{tr("plan.popular")}</span>}
                {saving > 0 && <span className="text-[10px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wide" style={{ background: `${t.colors.success}15`, color: t.colors.success }}>-{saving}%</span>}
              </div>
              <ul className="mt-1.5 space-y-0.5 text-xs">
                {p.cancellation_type === "free" ? (
                  <li className="flex items-center gap-1.5" style={{ color: t.colors.success }}><CheckCircle size={13} weight="fill" /> {p.free_cancel_hours ? tr("plan.freeCancelHours", { hours: p.free_cancel_hours }) : tr("room.freeCancellation")}</li>
                ) : (
                  <li className="flex items-center gap-1.5 text-slate-500"><XCircle size={13} weight="fill" /> {tr("plan.nonRefundable")}</li>
                )}
                {p.includes?.includes("breakfast") ? (
                  <li className="flex items-center gap-1.5" style={{ color: t.colors.success }}><Coffee size={13} weight="fill" /> {tr("room.breakfastIncluded")}</li>
                ) : (
                  <li className="flex items-center gap-1.5 text-slate-400"><Coffee size={13} /> {tr("plan.breakfastNotIncluded")}</li>
                )}
                {p.deposit_pct > 0 ? (
                  <li className="flex items-center gap-1.5 text-slate-500"><ShieldCheck size={13} /> {tr("plan.payNowPct", { pct: p.deposit_pct })}</li>
                ) : (
                  <li className="flex items-center gap-1.5 text-slate-500"><ShieldCheck size={13} /> {tr("plan.noPrepayment")}</li>
                )}
              </ul>
            </div>
            <div className="md:text-right">
              <div className="text-xs text-slate-500">{nights} {nights !== 1 ? tr("room.nights") : tr("room.night")}{q > 1 ? ` × ${q}` : ""}</div>
              <div className="text-2xl font-bold text-slate-900" data-testid={`plan-total-${room.id}-${p.code || idx}`}>{fmt(total)}</div>
              <div className="text-[11px] text-slate-500">{fmt(nightly)} {tr("room.perNight")} · {room.vat_rate ? tr("tax.vatIncl", { pct: room.vat_rate }) : tr("room.includesTaxes")}</div>
              {extraBedPrice > 0 && (
                <label className="text-[11px] text-slate-600 inline-flex items-center gap-1 mt-1">{tr("extra.bed")}
                  <select value={b} onChange={(e) => setBeds((s) => ({ ...s, [p.id]: Number(e.target.value) }))} className="border border-gray-200 rounded px-1 py-0.5 text-[11px]" data-testid={`plan-extra-bed-${room.id}-${p.code || idx}`}>{[0, 1, 2].map((n) => <option key={n} value={n}>{n}</option>)}</select>
                  <span className="text-slate-400">+{fmt(extraBedPrice)}/{tr("room.night")}</span>
                </label>
              )}
            </div>
            <div className="flex items-center gap-2 md:justify-end">
              <div className="flex items-center border border-gray-200 rounded-lg overflow-hidden" style={{ borderRadius: t.borderRadius }}>
                <button type="button" onClick={() => setQty((s) => ({ ...s, [p.id]: Math.max(1, q - 1) }))} className="w-8 h-9 flex items-center justify-center text-slate-500 hover:bg-slate-50" aria-label="-" data-testid={`plan-qty-minus-${room.id}-${p.code || idx}`}><Minus size={12} /></button>
                <span className="w-7 text-center text-sm font-semibold" data-testid={`plan-qty-${room.id}-${p.code || idx}`}>{q}</span>
                <button type="button" onClick={() => setQty((s) => ({ ...s, [p.id]: Math.min(maxQty, q + 1) }))} className="w-8 h-9 flex items-center justify-center text-slate-500 hover:bg-slate-50" aria-label="+" data-testid={`plan-qty-plus-${room.id}-${p.code || idx}`}><Plus size={12} /></button>
              </div>
              <button type="button" onClick={() => onAdd(room, p.id ? p : null, q, b)} disabled={!room.is_available}
                className="px-4 h-9 rounded-lg font-semibold text-sm text-white flex items-center gap-1.5 transition-transform hover:scale-[1.03] disabled:bg-slate-200 disabled:text-slate-400 disabled:cursor-not-allowed disabled:hover:scale-100"
                style={{ background: room.is_available ? (inCart ? t.colors.success : t.colors.accent) : undefined, borderRadius: t.borderRadius }}
                data-testid={idx === 0 ? `select-room-${room.id}` : `select-plan-${room.id}-${p.code || idx}`}>
                {!room.is_available ? tr("room.soldOut") : inCart ? <><Check size={14} weight="bold" /> {tr("plan.added")}</> : (t.custom?.bookingButtonText || tr("plan.select"))}
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
