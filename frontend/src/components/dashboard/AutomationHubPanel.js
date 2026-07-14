import { useState, Suspense } from "react";
import { GearSix, ChartBar, Coins, Lightning } from "@phosphor-icons/react";
import {
  AutomationSettingsPanel, AutomationAnalyticsPanel, AutomationRoiPanel, AutomationRulesPanel,
} from "../../lazyPanels";

const TABS = [
  { key: "settings", label: "Ayarlar & Motorlar", icon: GearSix, legacy: ["automation-settings", "automation-hub"] },
  { key: "roi", label: "ROI", icon: Coins, legacy: ["automation-roi"] },
  { key: "analytics", label: "Analitik", icon: ChartBar, legacy: ["automation-analytics"] },
  { key: "rules", label: "Kurallar", icon: Lightning, legacy: ["automation-rules"] },
];

export default function AutomationHubPanel({ initialView = "automation-hub", propertyId, user, onNavigate }) {
  const initial = TABS.find((t) => t.legacy.includes(initialView))?.key || "settings";
  const [tab, setTab] = useState(initial);

  return (
    <div className="space-y-4" data-testid="automation-hub-panel">
      <div className="flex items-center gap-1.5 border-b border-stone-200 pb-0">
        {TABS.map((t) => {
          const Icon = t.icon;
          const active = tab === t.key;
          return (
            <button key={t.key} onClick={() => setTab(t.key)} data-testid={`automation-hub-tab-${t.key}`}
              className={`inline-flex items-center gap-1.5 text-xs font-medium px-3.5 py-2.5 border-b-2 -mb-px transition-colors ${
                active ? "border-stone-900 text-stone-900" : "border-transparent text-stone-500 hover:text-stone-800"}`}>
              <Icon size={14} weight={active ? "fill" : "regular"} /> {t.label}
            </button>
          );
        })}
      </div>
      <Suspense fallback={<div className="p-8 text-stone-400 text-sm">Yükleniyor…</div>}>
        {tab === "settings" && <AutomationSettingsPanel />}
        {tab === "roi" && <AutomationRoiPanel propertyId={propertyId} onNavigate={onNavigate} />}
        {tab === "analytics" && <AutomationAnalyticsPanel />}
        {tab === "rules" && <AutomationRulesPanel propertyId={propertyId} user={user} />}
      </Suspense>
    </div>
  );
}
