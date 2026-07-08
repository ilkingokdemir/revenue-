import { useState, lazy, Suspense } from "react";
import { Broom, Sparkle, MapTrifold, CheckSquare, Camera, QrCode, TShirt, Gear, CalendarCheck } from "@phosphor-icons/react";

// Lazy-load each sub-panel to keep the hub light
const HousekeepingPanel = lazy(() => import("./HousekeepingPanel").then(m => ({ default: m.HousekeepingPanel })));
const HkTurnoverPanel = lazy(() => import("./HkTurnoverPanel"));
const PredictiveHkPanel = lazy(() => import("./PredictiveHkPanel"));
const HousekeepingRoutePanel = lazy(() => import("./HousekeepingRoutePanel"));
const CleaningChecklistsPanel = lazy(() => import("./CleaningChecklistsPanel"));
const ImageAIPanel = lazy(() => import("./ImageAIPanel"));
const RoomQRPanel = lazy(() => import("./RoomQRPanel"));
const LaundryManagement = lazy(() => import("./LaundryManagement").then(m => ({ default: m.LaundryManagement })));
const LaundrySettingsPanel = lazy(() => import("./LaundrySettingsPanel"));

const TABS = [
  { id: "rooms", label: "Oda Durumu", icon: Broom },
  { id: "turnover", label: "Devir / Board", icon: Sparkle },
  { id: "predictive", label: "Tahminsel Plan", icon: CalendarCheck },
  { id: "route", label: "Temizlik Rotası", icon: MapTrifold },
  { id: "checklists", label: "Kontrol Listeleri", icon: CheckSquare },
  { id: "ai-score", label: "AI Temizlik Skoru", icon: Camera },
  { id: "qr", label: "Oda QR'ları", icon: QrCode },
  { id: "laundry", label: "Çamaşırhane", icon: TShirt },
  { id: "laundry-cfg", label: "Çamaşır Ayarları", icon: Gear },
];

const Skeleton = () => (
  <div className="p-8 text-stone-400 text-sm" data-testid="hk-hub-skeleton">Yükleniyor…</div>
);

export default function HousekeepingHubPanel({ properties, activePropertyId, user, permissions, initialTab = "rooms" }) {
  const [tab, setTab] = useState(initialTab);
  const propertyId =
    activePropertyId && activePropertyId !== "all"
      ? activePropertyId
      : (properties?.[0]?.id || "default");
  const hotelName = properties?.find(p => p.id === activePropertyId)?.name || "";

  return (
    <div className="bg-stone-50 min-h-screen -m-6" data-testid="hk-hub-panel">
      <div className="px-6 pt-6 pb-3 bg-white border-b border-stone-200">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          <Broom size={12} weight="fill" className="text-cyan-500" />
          <span>Housekeeping</span>
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">Temizlik & Oda Hizmetleri</h1>
        <p className="text-sm text-stone-500 mt-1 max-w-2xl">
          Oda durumu, devir, rota, kontrol listeleri, AI skor, QR kodları ve çamaşırhane — tek modül altında.
        </p>

        <div className="mt-4 flex gap-1 overflow-x-auto -mb-px">
          {TABS.map(t => {
            const Icon = t.icon;
            const active = tab === t.id;
            return (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                data-testid={`hk-hub-tab-${t.id}`}
                className={`whitespace-nowrap px-3.5 py-2 text-xs font-medium transition-all border-b-2 -mb-px inline-flex items-center gap-1.5 ${
                  active
                    ? "border-cyan-500 text-cyan-700"
                    : "border-transparent text-stone-500 hover:text-stone-800"
                }`}
              >
                <Icon size={14} />
                {t.label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="p-6">
        <Suspense fallback={<Skeleton />}>
          {tab === "rooms" && (
            <HousekeepingPanel properties={properties} activePropertyId={activePropertyId} />
          )}
          {tab === "turnover" && <HkTurnoverPanel propertyId={propertyId} />}
          {tab === "predictive" && <PredictiveHkPanel propertyId={propertyId} />}
          {tab === "route" && <HousekeepingRoutePanel propertyId={propertyId} hotelName={hotelName} />}
          {tab === "checklists" && <CleaningChecklistsPanel propertyId={propertyId} hotelName={hotelName} />}
          {tab === "ai-score" && <ImageAIPanel propertyId={propertyId} />}
          {tab === "qr" && <RoomQRPanel propertyId={propertyId} hotelName={hotelName} />}
          {tab === "laundry" && (
            <LaundryManagement propertyId={activePropertyId} user={user} permissions={permissions} />
          )}
          {tab === "laundry-cfg" && <LaundrySettingsPanel activePropertyId={activePropertyId} />}
        </Suspense>
      </div>
    </div>
  );
}
