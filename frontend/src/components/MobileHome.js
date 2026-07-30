import React, { useEffect, useState } from "react";
import axios from "axios";
import {
  House,
  CalendarCheck,
  Broom,
  ChartLineUp,
  Bell,
  ForkKnife,
  Wrench,
  Users,
  ChartBar,
  Clock,
  MagnifyingGlass,
  CaretRight,
  Buildings,
  CheckCircle,
  DeviceMobile,
  Microphone,
  WhatsappLogo,
  Robot,
  Lock,
  Sparkle,
  DeviceTablet,
  SignIn,
  Lightning,
  MapPin,
} from "@phosphor-icons/react";
import { useTranslation } from "@/i18n";
import useCapacitor from "../hooks/useCapacitor";

/**
 * Mobile-first role-based home screen.
 *
 * Shown on phones (≤ 768 px wide) instead of the desktop layout. Each role
 * sees the 4-6 most-used cards for their job — receptionist sees today's
 * arrivals + walk-in + folio; housekeeping sees turnover + checklists; chef
 * sees recipe COGS + KDS; manager sees the dashboard + revenue alerts.
 *
 * Tapping a card switches to the desktop view of that panel — same routing
 * the sidebar uses.
 */
const ROLE_CARDS = {
  admin: ["dashboard", "arrivals", "revenue", "operations-hub", "reports", "site-feasibility"],
  manager: ["dashboard", "arrivals", "revenue", "operations-hub", "reports", "alerts"],
  receptionist: ["arrivals", "walkin", "folio-live", "self-checkin-v2", "guest-profiles", "messaging"],
  housekeeping: ["hk-turnover", "hk-route", "cleaning-checklists", "lost-found", "maintenance"],
  chef: ["pos", "kds", "menu-engineering", "recipe-cogs", "stock-management"],
  guest: ["dashboard", "guest-profiles", "messaging"],
};

const CARD_META = {
  dashboard: { icon: House, color: "from-emerald-500 to-emerald-600", label: "nav.dashboard" },
  arrivals: { icon: CalendarCheck, color: "from-sky-500 to-sky-600", label: "nav.arrivals" },
  walkin: { icon: Users, color: "from-amber-500 to-amber-600", label: "nav.walkin" },
  "self-checkin-v2": { icon: CheckCircle, color: "from-violet-500 to-violet-600", label: "nav.self_checkin_v2" },
  "folio-live": { icon: ChartBar, color: "from-rose-500 to-rose-600", label: "nav.folio_live" },
  "guest-profiles": { icon: Users, color: "from-teal-500 to-teal-600", label: "nav.guest_profiles" },
  messaging: { icon: Bell, color: "from-indigo-500 to-indigo-600", label: "nav.messaging" },
  "hk-turnover": { icon: Broom, color: "from-emerald-500 to-emerald-600", label: "nav.hk_turnover" },
  "hk-route": { icon: Clock, color: "from-sky-500 to-sky-600", label: "nav.hk_route" },
  "cleaning-checklists": { icon: CheckCircle, color: "from-violet-500 to-violet-600", label: "nav.cleaning_checklists" },
  "lost-found": { icon: MagnifyingGlass, color: "from-stone-500 to-stone-600", label: "nav.lost_found" },
  maintenance: { icon: Wrench, color: "from-amber-500 to-amber-600", label: "nav.maintenance" },
  pos: { icon: ForkKnife, color: "from-rose-500 to-rose-600", label: "nav.pos" },
  kds: { icon: ForkKnife, color: "from-orange-500 to-orange-600", label: "nav.kds" },
  "menu-engineering": { icon: ChartBar, color: "from-violet-500 to-violet-600", label: "nav.menu_engineering" },
  "recipe-cogs": { icon: ForkKnife, color: "from-emerald-500 to-emerald-600", label: "nav.recipe_cogs" },
  "stock-management": { icon: Wrench, color: "from-stone-500 to-stone-600", label: "nav.stock_management" },
  revenue: { icon: ChartLineUp, color: "from-indigo-500 to-indigo-600", label: "nav.revenue" },
  "operations-hub": { icon: Wrench, color: "from-stone-700 to-stone-900", label: "nav.operations_hub" },
  reports: { icon: ChartBar, color: "from-sky-500 to-sky-600", label: "nav.reports" },
  alerts: { icon: Bell, color: "from-rose-500 to-rose-600", label: "nav.alerts" },
  "site-feasibility": { icon: ChartLineUp, color: "from-violet-500 to-violet-600", label: "nav.site_feasibility" },
};

export default function MobileHome({ user, branding, onNavigate, kpis, catalog = [] }) {
  const { t } = useTranslation();
  const { isNative, platform, online } = useCapacitor();
  const role = (user?.role || "manager").toLowerCase();
  const cards = ROLE_CARDS[role] || ROLE_CARDS.manager;

  // Department shortcuts — admin-curated per-department task list
  const [deptItems, setDeptItems] = useState([]);
  const [badges, setBadges] = useState({});
  useEffect(() => {
    if (!user?.department) return;
    axios.get(`${process.env.REACT_APP_BACKEND_URL}/api/department-shortcuts/${user.department}`)
      .then((r) => setDeptItems(r.data.items || []))
      .catch(() => {});
    axios.get(`${process.env.REACT_APP_BACKEND_URL}/api/department-shortcuts/badges/all`)
      .then((r) => setBadges(r.data || {}))
      .catch(() => {});
  }, [user?.department]);
  const deptLabel = {
    front_desk: "Ön Büro", management: "Yönetim", housekeeping: "Housekeeping",
    food_beverage: "Y&İ", maintenance: "Teknik", spa_wellness: "Spa", concierge: "Concierge",
  }[user?.department] || "Departman";
  const catalogById = Object.fromEntries(catalog.map((c) => [c.id, c]));
  const DEPT_COLORS = ["from-sky-500 to-blue-600", "from-emerald-500 to-teal-600", "from-violet-500 to-purple-600",
    "from-amber-500 to-orange-600", "from-rose-500 to-pink-600", "from-indigo-500 to-blue-600"];

  const tNavOrFallback = (key, fallback) => {
    const out = t(key);
    return out && out !== key ? out : fallback;
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-stone-50 to-stone-100 pb-8" data-testid="mobile-home">
      {/* Header */}
      <div className="bg-stone-900 text-white px-5 pt-12 pb-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <img src="/logos/myhotelbox_icon.png" alt="MyHotelBox" className="w-8 h-8 rounded-lg object-cover" />
            <div>
              <div className="text-[10px] uppercase tracking-[0.18em] text-stone-400">
                {branding?.subtitle || "PMS & Revenue"}
              </div>
              <div className="text-base font-semibold">{branding?.app_name || "MyHotelBox"}</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {isNative && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 font-medium" data-testid="native-badge">
                {platform === "ios" ? "iOS" : "Android"}
              </span>
            )}
            <span className={`w-2 h-2 rounded-full ${online ? "bg-emerald-400" : "bg-red-500"}`} title={online ? "Online" : "Offline"} />
          </div>
        </div>
        <div className="text-2xl font-semibold leading-tight">Merhaba {user?.name?.split(" ")[0] || user?.email?.split("@")[0] || "👋"}</div>
        <div className="text-stone-400 text-sm mt-0.5 capitalize">{role}</div>
      </div>

      {/* KPI strip */}
      {kpis && (
        <div className="px-5 -mt-4 mb-3">
          <div className="bg-white rounded-xl border border-stone-200 p-3 shadow-sm grid grid-cols-3 gap-3">
            <Mini label="Bugün giriş" value={kpis.todayArrivals ?? "—"} />
            <Mini label="Çıkış" value={kpis.todayDepartures ?? "—"} />
            <Mini label="Doluluk" value={kpis.occupancy ? `${kpis.occupancy}%` : "—"} />
          </div>
        </div>
      )}

      {/* Quick search */}
      <div className="px-5 mb-4">
        <button
          onClick={() => onNavigate("__open_command_palette__")}
          className="w-full bg-white border border-stone-200 rounded-xl px-4 py-3 text-left text-sm text-stone-500 flex items-center gap-2 active:scale-[0.98] transition-transform"
          data-testid="mobile-search-btn"
        >
          <MagnifyingGlass size={16} />
          <span>Hızlı ara veya komut çalıştır…</span>
        </button>
      </div>

      {/* Department task shortcuts — managed by admin per department */}
      {deptItems.length > 0 && (
        <div className="px-5 mb-4" data-testid="mobile-dept-section">
          <div className="text-[10px] uppercase tracking-[0.18em] text-stone-500 mb-2">
            {deptLabel} görevleri
          </div>
          <div className="grid grid-cols-2 gap-3" data-testid="mobile-dept-cards">
            {deptItems.map((id, i) => {
              const c = catalogById[id];
              const meta = CARD_META[id];
              const Icon = c?.icon || meta?.icon || House;
              const label = c?.name || (meta ? tNavOrFallback(meta.label, id) : id);
              const color = meta?.color || DEPT_COLORS[i % DEPT_COLORS.length];
              return (
                <button key={`dept-${id}`} onClick={() => onNavigate(id)}
                  className={`relative overflow-hidden rounded-2xl bg-gradient-to-br ${color} text-white p-4 h-24 text-left active:scale-[0.97] transition-transform shadow-md`}
                  data-testid={`mobile-dept-card-${id}`}>
                  {badges[id] > 0 && (
                    <span className="absolute top-2.5 right-2.5 min-w-[22px] h-[22px] px-1.5 rounded-full bg-white/95 text-stone-900 text-[11px] font-black flex items-center justify-center shadow"
                      data-testid={`mobile-badge-${id}`}>
                      {badges[id]}
                    </span>
                  )}
                  <Icon size={20} weight="fill" className="mb-2 opacity-90" />
                  <div className="text-[13px] font-semibold leading-tight">{label}</div>
                  <CaretRight size={14} weight="bold" className="absolute bottom-3 right-3 opacity-80" />
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Role-based cards */}
      <div className="px-5">
        <div className="text-[10px] uppercase tracking-[0.18em] text-stone-500 mb-2">
          Sık kullanılanlar
        </div>
        <div className="grid grid-cols-2 gap-3" data-testid="mobile-role-cards">
          {cards.map((id) => {
            const meta = CARD_META[id] || { icon: House, color: "from-stone-500 to-stone-600", label: `nav.${id.replace(/-/g, "_")}` };
            const Icon = meta.icon;
            const label = tNavOrFallback(meta.label, id);
            return (
              <button
                key={id}
                onClick={() => onNavigate(id)}
                className={`relative overflow-hidden rounded-2xl bg-gradient-to-br ${meta.color} text-white p-4 h-28 text-left active:scale-[0.97] transition-transform shadow-md`}
                data-testid={`mobile-card-${id}`}
              >
                <Icon size={22} weight="fill" className="mb-3 opacity-90" />
                <div className="text-sm font-semibold leading-tight">{label}</div>
                <CaretRight size={14} weight="bold" className="absolute bottom-3 right-3 opacity-80" />
              </button>
            );
          })}
        </div>
      </div>

      {/* Mobile & Apps — consolidated app modules */}
      <div className="px-5 mt-6" data-testid="mobile-apps-section">
        <div className="flex items-center justify-between mb-2">
          <div className="text-[10px] uppercase tracking-[0.18em] text-stone-500">
            Mobil & Uygulamalar
          </div>
          <span className="text-[10px] text-emerald-600 font-medium">10 modül</span>
        </div>
        <div className="grid grid-cols-4 gap-2.5">
          {[
            { id: "mobile-companion", icon: DeviceMobile, label: "PWA", color: "bg-emerald-500" },
            { id: "guest-app", icon: MapPin, label: "Misafir app", color: "bg-sky-500" },
            { id: "kiosk-launch", icon: DeviceTablet, label: "Kiosk", color: "bg-violet-500" },
            { id: "self-checkin-v2", icon: SignIn, label: "Self check-in", color: "bg-indigo-500" },
            { id: "self-checkin-auto", icon: Lightning, label: "Oto trigger", color: "bg-amber-500" },
            { id: "voice-concierge", icon: Microphone, label: "Sesli AI", color: "bg-rose-500" },
            { id: "whatsapp-voice", icon: WhatsappLogo, label: "WhatsApp", color: "bg-emerald-600" },
            { id: "concierge-inbox", icon: Robot, label: "AI inbox", color: "bg-stone-700" },
            { id: "lock-sdk", icon: Lock, label: "Akıllı kilit", color: "bg-stone-800" },
            { id: "marketplace", icon: Sparkle, label: "Marketplace", color: "bg-fuchsia-500" },
          ].map(({ id, icon: Icon, label, color }) => (
            <button
              key={id}
              onClick={() => onNavigate(id)}
              className="flex flex-col items-center gap-1.5 active:scale-90 transition-transform"
              data-testid={`mobile-app-${id}`}
            >
              <span className={`${color} text-white w-12 h-12 rounded-2xl flex items-center justify-center shadow-md`}>
                <Icon size={22} weight="fill" />
              </span>
              <span className="text-[10px] text-stone-700 font-medium leading-tight text-center">{label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Tip footer */}
      <div className="px-5 mt-6">
        <div className="text-xs text-stone-400 text-center">
          Tüm modüllere ana menüden ulaşabilirsiniz · Sürüm 1.0
        </div>
      </div>
    </div>
  );
}

const Mini = ({ label, value }) => (
  <div className="text-center">
    <div className="text-[10px] uppercase tracking-wide text-stone-400">{label}</div>
    <div className="text-lg font-semibold text-stone-900 leading-tight">{value}</div>
  </div>
);
