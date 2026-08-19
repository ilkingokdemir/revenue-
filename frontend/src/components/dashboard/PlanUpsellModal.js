import { PLAN_LABELS } from "../../navigation/planGate";
import { LockKey, Crown, X } from "@phosphor-icons/react";

export const PlanUpsellModal = ({ upsell, currentPlan, isAdmin, onClose, onUpgrade }) => {
  if (!upsell) return null;
  const req = upsell.required || "pro";
  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/60 p-4" data-testid="plan-upsell-modal" onClick={onClose}>
      <div className="w-full max-w-md rounded-2xl bg-white shadow-2xl overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="bg-gradient-to-r from-indigo-600 to-violet-600 px-5 py-4 flex items-center gap-3">
          <LockKey size={22} weight="fill" className="text-amber-300" />
          <div className="flex-1">
            <div className="text-sm font-bold text-white">"{upsell.name}" kilitli</div>
            <div className="text-[11px] text-indigo-100">Bu modül {req.toUpperCase()} planda yer alıyor</div>
          </div>
          <button onClick={onClose} className="text-indigo-200 hover:text-white" data-testid="plan-upsell-close">
            <X size={18} />
          </button>
        </div>
        <div className="p-5 space-y-2">
          {["basic", "rms", "pro", "full"].map((p) => (
            <div key={p} data-testid={`plan-upsell-row-${p}`}
              className={`rounded-lg border px-3 py-2 text-[11px] flex items-center gap-2 ${
                p === currentPlan ? "border-stone-300 bg-stone-50 text-stone-500"
                : p === req || (req === "pro" && p === "full") ? "border-indigo-300 bg-indigo-50 text-indigo-800 font-medium"
                : "border-stone-100 text-stone-400"}`}>
              {(p === req) && <Crown size={13} weight="fill" className="text-amber-500 flex-shrink-0" />}
              <span className="flex-1">{PLAN_LABELS[p]}</span>
              {p === currentPlan && <span className="text-[9px] font-bold uppercase text-stone-400">Mevcut</span>}
            </div>
          ))}
          <div className="pt-2 flex gap-2">
            <button onClick={onClose} data-testid="plan-upsell-later"
              className="flex-1 py-2 rounded-lg border border-stone-200 text-xs font-semibold text-stone-600 hover:bg-stone-50">
              Daha sonra
            </button>
            {isAdmin ? (
              <button onClick={onUpgrade} data-testid="plan-upsell-upgrade-btn"
                className="flex-1 py-2 rounded-lg bg-gradient-to-r from-indigo-600 to-violet-600 text-xs font-bold text-white hover:opacity-90">
                Planı Yükselt →
              </button>
            ) : (
              <div className="flex-1 py-2 text-center text-[10px] text-stone-500">
                Yükseltme için yöneticinize başvurun
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default PlanUpsellModal;
