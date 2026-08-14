import React, { useEffect, useState, useMemo } from "react";
import RobotImpactCard from "./RobotImpactCard";
import axios from "axios";
import DeparturesBoard from "./DeparturesBoard";
import { Pickup24Card } from "./Pickup24Card";
import {
  Sparkle,
  ArrowRight,
  Bed,
  SignIn,
  SignOut,
  Bell,
  Star,
  CurrencyCircleDollar,
  TrendUp,
  Warning,
  CheckCircle,
  ArrowsClockwise,
} from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

/**
 * TodayHub — replaces the old EnhancedDashboard splash.
 * Goal: ONE screen that answers "What should I do RIGHT NOW?"
 *
 * Layout:
 *   ┌────────────────────────────────────────────┐
 *   │  Hero: greeting + AI brief (1 line)        │
 *   │  ┌─────────────┬─────────────┬──────────┐  │
 *   │  │ Action card │ Action card │ Stats    │  │
 *   │  └─────────────┴─────────────┴──────────┘  │
 *   │  Live KPIs (8 tiles)                       │
 *   │  Smart cards: arrivals · alerts · revenue  │
 *   └────────────────────────────────────────────┘
 *
 * Pulls from:
 *   GET /api/morning-brief/{property_id}
 *   GET /api/tier1-dashboard/{property_id}?days=7  (graceful fallback)
 */
export default function TodayHub({ propertyId, pickupScope, hotelName, onNavigate }) {
  const [robotStats, setRobotStats] = useState(null);
  const [brief, setBrief] = useState(null);
  const [tier1, setTier1] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!propertyId) return;
    let abort = false;
    setLoading(true);
    Promise.allSettled([
      axios.get(`${API}/api/morning-brief/${propertyId}`),
      axios.get(`${API}/api/tier1-dashboard/${propertyId}?days=7`),
    ])
      .then(([b, t]) => {
        if (abort) return;
        if (b.status === "fulfilled") setBrief(b.value.data);
        if (t.status === "fulfilled") setTier1(t.value.data);
      })
      .finally(() => !abort && setLoading(false));
    return () => {
      abort = true;
    };
  }, [propertyId]);

  useEffect(() => {
    if (!propertyId) return;
    axios.get(`${API}/api/ai-agent/inbox/${propertyId}`)
      .then(({ data }) => setRobotStats(data))
      .catch(() => {});
  }, [propertyId]);

  const greet = useMemo(() => {
    const h = new Date().getHours();
    if (h < 6) return "İyi geceler";
    if (h < 12) return "Günaydın";
    if (h < 18) return "İyi günler";
    return "İyi akşamlar";
  }, []);

  const arrivals = brief?.today?.arrivals ?? 0;
  const departures = brief?.today?.departures ?? 0;
  const inHouse = brief?.today?.in_house ?? 0;
  const noShows = brief?.today?.no_shows ?? 0;
  const occPct = brief?.today?.occupancy_pct ?? 0;
  const revToday = brief?.today?.revenue ?? 0;
  const adr = brief?.today?.adr ?? 0;
  const revpar = brief?.today?.revpar ?? 0;

  const alerts = brief?.alerts || {};
  const totalAlerts =
    (alerts.unread_inbox || 0) +
    (alerts.unanswered_reviews || 0) +
    (alerts.open_logbook || 0);

  const heroRevenue = tier1?.hero?.incremental_revenue;
  const t1Highlights = tier1?.highlights || [];

  // Smart action cards: surface the 3 most important "do now" tasks
  const actions = useMemo(() => {
    const out = [];
    if (arrivals > 0) {
      out.push({
        id: "arrivals",
        target: "arrivals",
        icon: SignIn,
        title: `${arrivals} bugünkü giriş`,
        subtitle: "Arrivals Cockpit'i aç",
        tone: "emerald",
      });
    }
    if (departures > 0) {
      out.push({
        id: "departures",
        target: "arrivals",
        icon: SignOut,
        title: `${departures} bugünkü çıkış`,
        subtitle: "Folio'ları gözden geçir",
        tone: "sky",
      });
    }
    if ((alerts.unanswered_reviews || 0) > 0) {
      out.push({
        id: "reviews",
        target: "reviews",
        icon: Star,
        title: `${alerts.unanswered_reviews} cevapsız yorum`,
        subtitle: "AI ile yanıtla",
        tone: "amber",
      });
    }
    if ((alerts.unread_inbox || 0) > 0) {
      out.push({
        id: "inbox",
        target: "unified-inbox",
        icon: Bell,
        title: `${alerts.unread_inbox} okunmamış mesaj`,
        subtitle: "Unified Inbox'i aç",
        tone: "violet",
      });
    }
    if ((alerts.open_logbook || 0) > 0) {
      out.push({
        id: "logbook",
        target: "logbook",
        icon: Warning,
        title: `${alerts.open_logbook} açık logbook girişi`,
        subtitle: "Vardiyaya aktar",
        tone: "rose",
      });
    }
    if (out.length === 0) {
      out.push({
        id: "all-clear",
        target: "morning-brief",
        icon: CheckCircle,
        title: "Tüm görevler tamam ✓",
        subtitle: "Morning Brief'e göz at",
        tone: "emerald",
      });
    }
    return out.slice(0, 3);
  }, [arrivals, departures, alerts]);

  return (
    <div className="p-5 lg:p-7 max-w-[1480px] mx-auto" data-testid="today-hub">
      {/* HERO */}
      <div className="mb-6">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-2">
          <Sparkle size={12} className="text-blue-400" weight="fill" />
          <span>Today · {hotelName || "Property"}</span>
        </div>
        <h1 className="text-3xl sm:text-4xl lg:text-5xl font-semibold text-stone-900 leading-tight">
          {greet}.
          <span className="text-stone-400"> Bugün için</span>{" "}
          <span className="text-blue-600">{actions.length}</span>{" "}
          <span className="text-stone-400">odak alanın var.</span>
        </h1>

        {brief?.commentary && (
          <p
            className="mt-3 text-sm sm:text-base text-stone-600 max-w-3xl leading-relaxed"
            data-testid="today-hero-commentary"
          >
            {brief.commentary}
          </p>
        )}
      </div>

      {/* SMART ACTION CARDS */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-7">
        {actions.map((a) => (
          <button
            key={a.id}
            onClick={() => onNavigate && onNavigate(a.target)}
            className={`group text-left p-5 rounded-2xl border transition-all hover:-translate-y-0.5 ${toneCardClass(
              a.tone
            )}`}
            data-testid={`today-action-${a.id}`}
          >
            <div className="flex items-start gap-3">
              <div
                className={`w-10 h-10 rounded-xl flex items-center justify-center ${toneIconBg(
                  a.tone
                )}`}
              >
                <a.icon size={20} weight="bold" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-semibold text-stone-900 truncate">{a.title}</div>
                <div className="text-xs text-stone-500 mt-0.5">{a.subtitle}</div>
              </div>
              <ArrowRight
                size={16}
                className="text-stone-400 group-hover:translate-x-0.5 transition-transform"
              />
            </div>
          </button>
        ))}
      </div>

      {/* AI REPLY ROBOT WIDGET */}
      {robotStats && (
        <button
          onClick={() => onNavigate && onNavigate("ai-reply-robot")}
          data-testid="today-robot-widget"
          className="w-full mb-6 p-4 rounded-2xl bg-gradient-to-r from-violet-500/10 via-violet-500/5 to-transparent border border-violet-500/20 flex items-center gap-3 text-left hover:-translate-y-0.5 transition-transform"
        >
          <div className="w-10 h-10 rounded-full bg-violet-500/15 flex items-center justify-center text-lg">🤖</div>
          <div className="flex-1 min-w-0">
            <div className="font-semibold text-stone-900 text-sm">
              AI Yanıt Robotu —{" "}
              {robotStats.count > 0 ? (
                <span className="text-violet-600">{robotStats.count} yanıt onayınızı bekliyor</span>
              ) : (
                <span className="text-emerald-600">tüm yorum ve şikayetler yanıtlandı ✓</span>
              )}
            </div>
            <div className="text-xs text-stone-500 mt-0.5">
              {robotStats.review_count} yorum · {robotStats.complaint_count} şikayet — taslakları incele & gönder
            </div>
          </div>
          <ArrowRight size={16} className="text-violet-500" />
        </button>
      )}

      {/* INCREMENTAL REVENUE BANNER (from tier1) */}
      {heroRevenue && heroRevenue.amount > 0 && (
        <div
          className="mb-6 p-4 rounded-2xl bg-gradient-to-r from-emerald-500/10 via-emerald-500/5 to-transparent border border-emerald-500/20 flex items-center gap-3"
          data-testid="today-incremental-revenue"
        >
          <div className="w-10 h-10 rounded-full bg-emerald-500/15 flex items-center justify-center">
            <TrendUp size={18} className="text-emerald-600" weight="bold" />
          </div>
          <div className="flex-1">
            <div className="text-xs uppercase tracking-wider text-emerald-700 font-medium">
              Son 7 günde Tier-1 ek geliri
            </div>
            <div className="text-2xl font-bold text-emerald-900 mt-0.5">
              {fmtCurrency(heroRevenue.amount, heroRevenue.currency)}
            </div>
          </div>
          <button
            onClick={() => onNavigate && onNavigate("tier1-dashboard")}
            className="text-xs px-3 py-1.5 rounded-lg bg-emerald-600 text-white hover:bg-emerald-700"
            data-testid="today-tier1-link"
          >
            Detay →
          </button>
        </div>
      )}

      {/* LIVE KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3 mb-7">
        <Tile label="Doluluk" value={`${occPct}%`} icon={Bed} />
        <Tile label="In-house" value={inHouse} icon={Bed} />
        <Tile label="Giriş" value={arrivals} icon={SignIn} accent="emerald" />
        <Tile label="Çıkış" value={departures} icon={SignOut} accent="sky" />
        <Tile label="No-show" value={noShows} icon={Warning} accent={noShows ? "rose" : null} />
        <Tile
          label="Bugün gelir"
          value={fmtCurrency(revToday, brief?.currency || "GBP")}
          icon={CurrencyCircleDollar}
        />
        <Tile label="ADR" value={fmtCurrency(adr, brief?.currency || "GBP")} icon={TrendUp} />
        <Tile label="RevPAR" value={fmtCurrency(revpar, brief?.currency || "GBP")} icon={TrendUp} />
      </div>

      {/* HIGHLIGHTS + ALERTS row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Highlights from Tier-1 */}
        <div className="p-5 rounded-2xl bg-white border border-stone-200">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-stone-900">Öne çıkan KPI'lar</h3>
            <button
              onClick={() => onNavigate && onNavigate("tier1-dashboard")}
              className="text-xs text-blue-600 hover:underline"
            >
              Tümü →
            </button>
          </div>
          {t1Highlights.length === 0 && (
            <div className="text-xs text-stone-500">Henüz veri yok.</div>
          )}
          <div className="space-y-2">
            {t1Highlights.slice(0, 5).map((h, i) => (
              <div
                key={i}
                className="flex items-center gap-2 p-2 rounded-lg bg-stone-50 text-xs"
                data-testid={`today-highlight-${i}`}
              >
                <div
                  className={`w-1.5 h-1.5 rounded-full ${
                    h.kind === "alert" ? "bg-rose-500" : "bg-emerald-500"
                  }`}
                />
                <span className="text-stone-800 font-medium truncate">{h.title}</span>
                <span className="text-stone-500 ml-auto truncate">{h.value}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Alerts */}
        <div className="p-5 rounded-2xl bg-white border border-stone-200">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-stone-900">Aksiyon gerektirenler</h3>
            <span
              className={`text-xs px-2 py-0.5 rounded-full ${
                totalAlerts > 0 ? "bg-rose-100 text-rose-700" : "bg-emerald-100 text-emerald-700"
              }`}
            >
              {totalAlerts}
            </span>
          </div>
          <div className="space-y-2 text-xs">
            <AlertRow
              label="Cevapsız yorum"
              value={alerts.unanswered_reviews}
              onClick={() => onNavigate && onNavigate("reviews")}
            />
            <AlertRow
              label="Okunmamış mesaj"
              value={alerts.unread_inbox}
              onClick={() => onNavigate && onNavigate("unified-inbox")}
            />
            <AlertRow
              label="Açık logbook"
              value={alerts.open_logbook}
              onClick={() => onNavigate && onNavigate("logbook")}
            />
          </div>
        </div>

        {/* Last 7d revenue */}
        <div className="p-5 rounded-2xl bg-gradient-to-br from-blue-500/10 to-transparent border border-blue-500/20">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-stone-900">Pickup (son 7 gün)</h3>
            <ArrowsClockwise size={14} className="text-blue-500" />
          </div>
          <div className="text-3xl font-bold text-blue-900">
            {fmtCurrency(brief?.last_7d?.revenue || 0, brief?.currency || "GBP")}
          </div>
          <div className="text-xs text-stone-600 mt-1">
            {brief?.last_7d?.pickup_count || 0} rezervasyon
          </div>
          {brief?.stly && (
            <div className="mt-3 text-xs">
              <span className="text-stone-500">STLY: </span>
              <span
                className={`font-semibold ${
                  brief.stly.delta_pct >= 0 ? "text-emerald-600" : "text-rose-600"
                }`}
              >
                {brief.stly.delta_pct >= 0 ? "+" : ""}
                {brief.stly.delta_pct?.toFixed?.(1)}%
              </span>
            </div>
          )}
          <button
            onClick={() => onNavigate && onNavigate("morning-brief")}
            className="mt-4 w-full text-xs px-3 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700"
            data-testid="today-morning-brief-link"
          >
            Morning Brief'e git
          </button>
        </div>
      </div>

      {/* 24-Hour Pickup (Pulse) */}
      <div className="mt-5">
        <Pickup24Card propertyId={pickupScope || propertyId} />
      </div>

      {/* Robot Başarı Panosu — aylık kâr katkısı */}
      <div className="mt-5">
        <RobotImpactCard propertyId={propertyId} onNavigate={onNavigate} />
      </div>

      {/* Scheduled Departures Board (Mews parity) */}
      <div className="mt-5">
        <DeparturesBoard propertyId={propertyId} />
      </div>

      {loading && !brief && (
        <div className="mt-6 text-xs text-stone-400" data-testid="today-loading">
          Yükleniyor…
        </div>
      )}
    </div>
  );
}

function toneCardClass(tone) {
  const map = {
    emerald: "bg-white hover:bg-emerald-50/50 border-stone-200 hover:border-emerald-200",
    sky: "bg-white hover:bg-sky-50/50 border-stone-200 hover:border-sky-200",
    amber: "bg-white hover:bg-amber-50/50 border-stone-200 hover:border-amber-200",
    violet: "bg-white hover:bg-blue-50/50 border-stone-200 hover:border-blue-200",
    rose: "bg-white hover:bg-rose-50/50 border-stone-200 hover:border-rose-200",
  };
  return map[tone] || map.violet;
}

function toneIconBg(tone) {
  const map = {
    emerald: "bg-emerald-100 text-emerald-700",
    sky: "bg-sky-100 text-sky-700",
    amber: "bg-amber-100 text-amber-700",
    violet: "bg-blue-100 text-blue-700",
    rose: "bg-rose-100 text-rose-700",
  };
  return map[tone] || map.violet;
}

function Tile({ label, value, icon: Icon, accent }) {
  const accentMap = {
    emerald: "text-emerald-600",
    sky: "text-sky-600",
    rose: "text-rose-600",
  };
  return (
    <div
      className="p-3 rounded-xl bg-white border border-stone-200 hover:border-stone-300 transition"
      data-testid={`today-tile-${label.toLowerCase().replace(/\s+/g, "-")}`}
    >
      <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-stone-500 mb-1">
        {Icon && <Icon size={11} />}
        <span className="truncate">{label}</span>
      </div>
      <div className={`text-lg font-bold ${accent ? accentMap[accent] : "text-stone-900"}`}>
        {value}
      </div>
    </div>
  );
}

function AlertRow({ label, value, onClick }) {
  const v = value || 0;
  return (
    <button
      onClick={onClick}
      disabled={v === 0}
      className={`w-full flex items-center justify-between p-2 rounded-lg ${
        v > 0
          ? "bg-rose-50 hover:bg-rose-100 text-stone-900 cursor-pointer"
          : "bg-stone-50 text-stone-400 cursor-default"
      } transition`}
    >
      <span>{label}</span>
      <span className={`font-bold ${v > 0 ? "text-rose-700" : "text-stone-400"}`}>{v}</span>
    </button>
  );
}

function fmtCurrency(amount, currency) {
  if (amount == null) return "—";
  const sym = { GBP: "£", USD: "$", EUR: "€", TRY: "₺" }[currency] || currency || "";
  const n = Number(amount);
  if (!isFinite(n)) return "—";
  return `${sym}${n.toLocaleString("en-GB", { maximumFractionDigits: 0 })}`;
}
