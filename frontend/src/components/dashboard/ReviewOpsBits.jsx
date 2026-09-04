import { ShieldWarning, Warning, Prohibit, Gauge } from "@phosphor-icons/react";

export const RISK_META = {
  critical: { label: "CRITICAL", cls: "bg-red-600 text-white border-red-700" },
  high: { label: "HIGH", cls: "bg-orange-500 text-white border-orange-600" },
  medium: { label: "MEDIUM", cls: "bg-amber-400 text-stone-900 border-amber-500" },
  low: { label: "LOW", cls: "bg-emerald-100 text-emerald-800 border-emerald-200" },
};

export const RiskBadge = ({ analysis, size = "sm" }) => {
  if (!analysis?.risk_level) return null;
  const m = RISK_META[analysis.risk_level] || RISK_META.low;
  return (
    <span data-testid="risk-badge" className={`inline-flex items-center gap-1 rounded-full border font-bold ${size === "xs" ? "text-[10px] px-1.5 py-0.5" : "text-[11px] px-2 py-0.5"} ${m.cls}`}>
      <ShieldWarning size={11} weight="fill" /> Risk {analysis.risk_score ?? "?"} · {m.label}
    </span>
  );
};

const FLAGS = [
  ["refund_requested", "Refund"], ["compensation_requested", "Compensation"], ["safety_issue", "Safety"],
  ["legal_issue", "Legal"], ["medical_issue", "Medical"], ["discrimination", "Discrimination"],
  ["harassment", "Harassment"], ["fraud_allegation", "Fraud"],
];

export const FlagChips = ({ analysis }) => {
  if (!analysis) return null;
  const on = FLAGS.filter(([k]) => analysis[k]);
  const spam = Math.round((analysis.spam_probability || 0) * 100);
  const fake = Math.round((analysis.fake_probability || 0) * 100);
  return (
    <div className="flex flex-wrap gap-1.5" data-testid="analysis-flags">
      {on.map(([k, l]) => (
        <span key={k} className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-red-50 text-red-700 border border-red-200">{l}</span>
      ))}
      {analysis.staff_mentioned?.length > 0 && (
        <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-stone-100 text-stone-700 border border-stone-200">Staff: {analysis.staff_mentioned.join(", ")}</span>
      )}
      {spam >= 30 && (
        <span data-testid="spam-chip" className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${spam >= 80 ? "bg-red-600 text-white border-red-700" : "bg-amber-50 text-amber-800 border-amber-200"}`}>Spam {spam}%</span>
      )}
      {fake >= 50 && (
        <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-50 text-amber-800 border border-amber-200">Suspicious {fake}%</span>
      )}
      {analysis.escalation_level && analysis.escalation_level !== "none" && (
        <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-orange-50 text-orange-800 border border-orange-200">Escalate → {analysis.escalation_level}</span>
      )}
    </div>
  );
};

export const SpamNotice = ({ analysis, review }) => {
  if (!analysis?.spam_suspected) return null;
  return (
    <div data-testid="spam-notice" className="flex items-start gap-2 bg-red-50 border border-red-200 rounded-lg p-3 text-xs text-red-800">
      <Prohibit size={16} weight="fill" className="mt-0.5 shrink-0" />
      <div>
        <p className="font-bold">Possible spam ({Math.round(analysis.spam_probability * 100)}%) — DO NOT REPLY</p>
        <p>Report it on the platform instead. Reviews can't be edited or removed via API; use the platform's report flow.</p>
        {review?.external_url && <a href={review.external_url} target="_blank" rel="noreferrer" className="underline font-semibold">Open review on {review.platform}</a>}
      </div>
    </div>
  );
};

export const PrivacyAlert = ({ privacy }) => {
  if (!privacy || privacy.ok) return null;
  return (
    <div data-testid="privacy-alert" className="flex items-start gap-2 bg-red-600 text-white rounded-lg p-3 text-xs">
      <Warning size={16} weight="fill" className="mt-0.5 shrink-0" />
      <div>
        <p className="font-bold">Gizlilik ihlali — yayın engellenir</p>
        <p>{privacy.violations.map(v => `${v.type} (${v.sample})`).join(" · ")}. Metni düzenleyin: rezervasyon no, telefon, e-posta, ödeme, oda no, iç notlar ve personel bilgileri yayınlanamaz.</p>
      </div>
    </div>
  );
};

const DIMS = [["personalisation", "Personalisation"], ["relevance", "Relevance"], ["brand_voice", "Brand voice"], ["factuality", "Factuality"],
  ["originality", "Originality"], ["professionalism", "Professionalism"], ["policy_safety", "Policy safety"]];

export const QualityPanel = ({ quality, similarity, decision }) => {
  if (!quality) return null;
  const tot = quality.total ?? 0;
  const col = tot >= 90 ? "text-emerald-700" : tot >= 75 ? "text-amber-700" : "text-red-700";
  return (
    <div data-testid="quality-panel" className="bg-white border border-stone-200 rounded-lg p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold text-stone-700 inline-flex items-center gap-1"><Gauge size={14} /> Response Quality</span>
        <span className={`text-lg font-black ${col}`} data-testid="quality-total">{tot}</span>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-3 gap-y-1">
        {DIMS.map(([k, l]) => (
          <div key={k} className="flex items-center justify-between text-[10px] text-stone-500">
            <span>{l}</span><span className={`font-semibold ${quality[k] < 60 ? "text-red-600" : "text-stone-800"}`}>{quality[k]}</span>
          </div>
        ))}
        {similarity && (
          <div className="flex items-center justify-between text-[10px] text-stone-500">
            <span>Similarity</span>
            <span className={`font-semibold ${similarity.max_pct >= 70 ? "text-red-600" : "text-stone-800"}`} data-testid="similarity-pct">{similarity.max_pct}% <span className="text-stone-400">/ {similarity.compared}</span></span>
          </div>
        )}
      </div>
      {decision && (
        <div className="mt-2 pt-2 border-t border-stone-100 text-[11px]" data-testid="decision-line">
          <span className="font-semibold">Decision: </span>
          <span className={decision.action === "auto_approve" ? "text-emerald-700" : decision.action === "escalate" ? "text-red-700" : "text-amber-700"}>{decision.action.replace("_", " ")}</span>
          <span className="text-stone-400"> · {decision.mode} · {decision.reasons?.join(", ")}</span>
        </div>
      )}
    </div>
  );
};
