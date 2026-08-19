// Plan bazlı modül kilitleri — basic / rms / cm / pro / full
const FULL_ONLY_IDS = new Set([
  "public-api", "partner-webhooks", "dev-portal", "api", "webhooks",
  "ai-agents", "marketplace", "lock-sdk",
]);
const ALWAYS_SECTIONS = new Set(["Settings & Admin"]);
const RMS_SECTIONS = new Set(["Overview", "Revenue & rates", "Reports & Analytics", "Settings & Admin"]);
const CM_SECTIONS = new Set(["Overview", "Reservations", "Direct Booking", "Channels & Distribution", "Settings & Admin"]);

export const PLAN_LABELS = {
  basic: "BASIC — Ön büro + rezervasyon + takvim (çekirdek ~30 modül)",
  rms: "RMS — Sadece Gelir Yönetimi: fiyatlama, forecast, compset, raporlar",
  cm: "CM — Sadece Channel Manager: kanallar, eşleme, booking engine",
  pro: "PRO — Basic + gelir yönetimi + kanallar + raporlar (~150 modül)",
  full: "FULL — Tüm 280+ modül + Public API + süper admin",
};

export function isModuleAllowed(item, sectionLabel, plan) {
  if (!plan || plan === "full") return true;
  if (ALWAYS_SECTIONS.has(sectionLabel)) return true;
  if (FULL_ONLY_IDS.has(item.id)) return false;
  if (plan === "pro") return true;
  if (plan === "rms") return RMS_SECTIONS.has(sectionLabel);
  if (plan === "cm") return CM_SECTIONS.has(sectionLabel);
  if (plan === "basic") return !!item.core;
  return true;
}

export function requiredPlanFor(item) {
  return FULL_ONLY_IDS.has(item.id) ? "full" : "pro";
}
