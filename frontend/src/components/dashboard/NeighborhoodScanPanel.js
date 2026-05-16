/**
 * NeighborhoodScanPanel — Market Robot geo-radius scan with:
 *   • Manual scan (postcode/address + radius)
 *   • Auto-scan toggle (runs every N minutes independently from city scan)
 *   • Price data: avg/min/max market prices for the neighborhood
 *   • Charts: demand bars + price trend (same style as Demand Radar)
 *   • Parallel execution — city scan + geo scan can both run
 */
import { useState, useEffect, useCallback, useMemo } from "react";
import axios from "axios";
import {
  MapPin, Radar, Loader2, Clock, Building2, TrendingUp, Timer,
  PoundSterling, Activity, ToggleLeft, ToggleRight, Save, Zap, RefreshCw,
  Plus, Sparkles,
} from "lucide-react";
import { toast } from "sonner";
import { useTranslation } from "../../i18n";
import CompetitivePricingPanel from "./CompetitivePricingPanel";
import GapAnalyzerWidget from "./GapAnalyzerWidget";
import useLivePolling from "../../hooks/useLivePolling";
import usePriceAlerts from "../../hooks/usePriceAlerts";
import { makeCurrencyFormatter } from "../../lib/currency";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function NeighborhoodScanPanel({ propertyId }) {
  const { t } = useTranslation();
  const [location, setLocation] = useState("");
  const [radiusKm, setRadiusKm] = useState(3.2);
  const [days, setDays] = useState(30);
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const [scanning, setScanning] = useState(false);
  const [summary, setSummary] = useState(null);
  const [snapshots, setSnapshots] = useState([]);
  const [competitorSeries, setCompetitorSeries] = useState([]);
  const [ourHotelName, setOurHotelName] = useState("");
  const [lastResult, setLastResult] = useState(null);
  const [autoCfg, setAutoCfg] = useState(null);
  const [ourSummary, setOurSummary] = useState(null);
  const [saving, setSaving] = useState(false);
  const [highlightDate, setHighlightDate] = useState(null);
  // Fix Branch Location dialog
  const [fixOpen, setFixOpen] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  // Competitor visibility toggles — click a legend row to hide/show its line.
  // Key = competitor.id, value = boolean "visible" (default all visible).
  const [hiddenComps, setHiddenComps] = useState({});
  // Hovered competitor (from legend) — dims other lines, brightens this one.
  const [hoveredCompId, setHoveredCompId] = useState(null);
  // Hover index on the chart (for the vertical crosshair + date tooltip).
  const [hoverIdx, setHoverIdx] = useState(null);
  // Auto-Heal flow state
  const [healing, setHealing] = useState(false);
  const [healStatus, setHealStatus] = useState(null);
  // Auto-Heal scheduler config (persistent — saved to backend)
  const [healCfg, setHealCfg] = useState(null);
  const [healCfgSaving, setHealCfgSaving] = useState(false);
  const [fixCity, setFixCity] = useState("");
  const [fixCurrency, setFixCurrency] = useState("");
  const [fixPostcode, setFixPostcode] = useState("");
  const [fixing, setFixing] = useState(false);
  const [propInfo, setPropInfo] = useState({ city: "", currency: "" });
  // Manual competitor add (small form, no full URL validation)
  const [manualUrl, setManualUrl] = useState("");
  const [manualName, setManualName] = useState("");
  const [manualAdding, setManualAdding] = useState(false);
  // Auto-discover competitors directly from this panel — 1-click "scan & add top N"
  const [autoDiscovering, setAutoDiscovering] = useState(false);
  const [discoveryResult, setDiscoveryResult] = useState(null);  // { added, total, candidates }

  const runAutoDiscoverCompetitors = async () => {
    if (propertyId === "all") {
      toast.error("Önce yukarıdan tek bir şube seçin");
      return;
    }
    setAutoDiscovering(true);
    setDiscoveryResult(null);
    try {
      const { data } = await axios.post(
        `${API}/revenue/market-robot/${propertyId}/competitors/discover`,
        {
          // Tighter radius for "neighbors" than the geo-supply scan radius
          radius_km: Math.max(0.5, Math.min(parseFloat(radiusKm) || 2.5, 5.0)),
          max_results: 20,
          auto_add: true,
          auto_add_top: 5,
          exclude_single_room: true,
        }
      );
      const added = data?.auto_added || 0;
      const total = (data?.candidates || []).length;
      setDiscoveryResult({
        added,
        total,
        candidates: (data?.candidates || []).slice(0, 10),
      });
      if (added > 0) {
        toast.success(`✅ ${added} rakip otomatik eklendi (${total} aday bulundu) · Şimdi "Scan Now" ile fiyatlarını çek`);
      } else if (total > 0) {
        toast.warning(`${total} aday bulundu ama hepsi zaten eklenmiş veya size benziyor. Manuel olarak ekleyebilirsiniz.`);
      } else {
        toast.warning("Hiç rakip bulunamadı — yarıçapı arttırın veya manuel olarak ekleyin.");
      }
      loadAll();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Otomatik discovery başarısız");
    }
    setAutoDiscovering(false);
  };

  const addManualCompetitor = async () => {
    const url = (manualUrl || "").trim();
    if (!url) { toast.error("Booking.com URL gerekli"); return; }
    if (!/booking\.com\/hotel\//i.test(url)) {
      toast.error("Geçerli bir Booking.com /hotel/ URL'si yapıştırın");
      return;
    }
    if (propertyId === "all") {
      toast.error("Önce yukarıdan tek bir şube seçin");
      return;
    }
    setManualAdding(true);
    try {
      const { data } = await axios.post(
        `${API}/revenue/market-robot/${propertyId}/competitors`,
        { booking_url: url, name: manualName.trim() }
      );
      if (data?.error === "invalid_booking_url") {
        toast.error("Booking.com URL'si doğrulanamadı. Linki kontrol edin.");
      } else {
        toast.success(`Rakip eklendi: ${data?.name || manualName || "yeni"} — sonraki tarama bunu da çekecek`);
        setManualUrl("");
        setManualName("");
        loadAll();
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Rakip ekleme başarısız");
    }
    setManualAdding(false);
  };

  // Hydrate location fields whenever the branch (propertyId) or backend cfg changes.
  // Bug before: `!location` guarded this, so once any branch set location, subsequent
  // branch switches kept the old value — broke every scan/scrape for the new branch.
  useEffect(() => {
    if (autoCfg) {
      setLocation(autoCfg.location || "");
      setRadiusKm(autoCfg.radius_km || 3.2);
      setLatitude(autoCfg.latitude || "");
      setLongitude(autoCfg.longitude || "");
    } else {
      // No cfg for this branch yet → clear stale values carried over from a previous branch
      setLocation("");
      setLatitude("");
      setLongitude("");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [propertyId, autoCfg?.location, autoCfg?.radius_km, autoCfg?.latitude, autoCfg?.longitude]);

  // Clear all branch-scoped state the instant the branch switches, before new data arrives.
  // Without this the user sees the previous branch's snapshots/competitors/summary for a
  // second or two — looked like "wrong data" for their newly-selected branch.
  useEffect(() => {
    setSummary(null);
    setSnapshots([]);
    setCompetitorSeries([]);
    setOurHotelName("");
    setOurSummary(null);
    setLastResult(null);
    setHiddenComps({});
    setHealStatus(null);
    setHighlightDate(null);
    setHoverIdx(null);
    setHoveredCompId(null);
  }, [propertyId]);

  const loadAll = useCallback(async () => {
    try {
      const [{ data: supply }, { data: cfg }, { data: ob }, { data: hcfg }] = await Promise.all([
        axios.get(`${API}/revenue/market-robot/${propertyId}/geo-supply?days=${days}`),
        axios.get(`${API}/revenue/market-robot/${propertyId}/geo-config`),
        axios.get(`${API}/revenue/market-robot/${propertyId}/our-booking`).catch(() => ({ data: {} })),
        axios.get(`${API}/revenue/market-robot/${propertyId}/competitors/auto-heal/config`).catch(() => ({ data: null })),
      ]);
      const sum = supply.summary || {};
      if (supply.property_currency) sum.property_currency = supply.property_currency;
      setSummary(sum);
      setSnapshots(supply.snapshots || []);
      setOurSummary(supply.our_summary || null);
      setCompetitorSeries(supply.competitor_series || []);
      setOurHotelName(supply.our_hotel_name || "");
      setAutoCfg(cfg);
      setHealCfg(hcfg);
      setPropInfo({ city: ob?.city || "", currency: ob?.currency || supply.property_currency || "" });
    } catch { /* noop */ }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [propertyId, days]);

  useEffect(() => { loadAll(); }, [loadAll]);

  // ⚡ Live updates — see hooks/useLivePolling.js
  useLivePolling(loadAll, { intervalMs: 30000, busy: refreshing });

  // 🔔 Price alerts — toast the revenue manager on significant market moves
  usePriceAlerts({
    propertyId,
    scope: "neighborhood",
    marketAvgPrice: summary?.avg_price,
    ourAvgRate: ourSummary?.avg_rate,
    currency: summary?.property_currency || "GBP",
    enabled: propertyId !== "all",
  });

  // Prefill the Fix dialog when opened — from property record or current scan location
  useEffect(() => {
    if (fixOpen) {
      setFixCity(propInfo.city || "");
      setFixCurrency(propInfo.currency || "");
      setFixPostcode(location || "");
    }
  }, [fixOpen, propInfo, location]);

  const applyLocationFix = async () => {
    if (!fixCity.trim() || !fixCurrency.trim()) {
      toast.error("City and currency are required");
      return;
    }
    setFixing(true);
    try {
      const { data } = await axios.post(`${API}/revenue/market-robot/${propertyId}/fix-property-location`, {
        city: fixCity.trim(),
        currency: fixCurrency.trim().toUpperCase(),
        postcode: fixPostcode.trim(),
        clear_stale_snapshots: true,
      });
      toast.success(data.message || "Fixed");
      setFixOpen(false);
      loadAll();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Fix failed");
    }
    setFixing(false);
  };

  const refreshNeighborhood = async () => {
    if (!window.confirm("Eski/hatalı scrap kayıtlarını silip yeni tarama başlatmak ister misiniz? (Grafik 1-2 dakika içinde yenilenecek.)")) return;
    setRefreshing(true);
    try {
      const { data } = await axios.post(`${API}/revenue/market-robot/${propertyId}/neighborhood/refresh`, {
        location: location.trim(),
        radius_km: Number(radiusKm),
        days_ahead: Number(days),
      });
      toast.success(data.message || `Cleaned ${data.stale_snapshots_cleared || 0} rows, scan queued`);
      // Poll for fresh data every 15s, up to 3 minutes
      const started = Date.now();
      const poll = async () => {
        try {
          await loadAll();
          if (Date.now() - started > 3 * 60 * 1000) {
            setRefreshing(false);
            return;
          }
          setTimeout(poll, 15000);
        } catch {
          setRefreshing(false);
        }
      };
      setTimeout(poll, 10000);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Refresh failed");
      setRefreshing(false);
    }
  };

  const runScan = async () => {
    if (!location.trim() && !(latitude && longitude)) { toast.error("Enter a postcode/address OR coordinates"); return; }
    setScanning(true);
    try {
      const payload = { location: location.trim(), radius_km: Number(radiusKm), days_ahead: Number(days) };
      if (latitude && longitude) { payload.latitude = Number(latitude); payload.longitude = Number(longitude); }
      const { data } = await axios.post(`${API}/revenue/market-robot/${propertyId}/scan-geo`, payload);
      if (data.status === "busy") { toast.error(data.error || "Another geo scan in progress"); }
      else {
        setLastResult(data);
        toast.success(`Scanned ${data.dates_scanned} dates · ${data.location}`);
        loadAll();
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Scan failed");
    }
    setScanning(false);
  };

  // Reset wizard: clears all competitors + auto-geocodes property + re-discovers
  // proper neighbors. Used when the auto-discovery picked the wrong area
  // (e.g. Kensington shown for an Aldgate property).
  const [resetting, setResetting] = useState(false);
  const resetNeighbors = async () => {
    if (!window.confirm(
      "Tüm mevcut rakipleri sileceğim, property'yi otomatik geocode'layacağım ve " +
      "gerçek komşuları yeniden bulacağım. Bu işlem 30-60 saniye sürebilir. Devam?"
    )) return;
    setResetting(true);
    try {
      // Step 1: clear bad competitors
      const clr = await axios.delete(`${API}/revenue/market-robot/${propertyId}/competitors/clear`);
      toast.info(`1/3: ${clr.data.deleted} eski rakip silindi`);

      // Step 2: force auto-geocode (in case property has no lat/lon or wrong ones)
      const geo = await axios.post(`${API}/revenue/market-robot/${propertyId}/auto-geocode`, { force: true });
      if (geo.data.ok) {
        toast.info(`2/3: Geocode tamam → ${geo.data.geocoded_from || "ok"}`);
      } else {
        toast.warning(`2/3: Geocode atlandı (${geo.data.error || "no_match"})`);
      }

      // Step 3: re-discover with proper neighborhood radius + auto-add top 5
      const disc = await axios.post(`${API}/revenue/market-robot/${propertyId}/competitors/discover`,
        { radius_km: 2.0, max_results: 15, auto_add: true, auto_add_top: 5 });
      const added = disc.data.auto_added || 0;
      toast.success(`3/3: ${disc.data.total} komşu bulundu, ${added} otomatik rakip olarak eklendi.`);
      loadAll();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Sıfırlama başarısız");
    }
    setResetting(false);
  };

  const saveAutoCfg = async () => {
    setSaving(true);
    try {
      const payload = {
        enabled: autoCfg?.enabled || false,
        location: location.trim(),
        radius_km: Number(radiusKm),
        days_ahead: Number(days),
        scan_interval_minutes: Number(autoCfg?.scan_interval_minutes || 120),
        latitude: latitude ? Number(latitude) : null,
        longitude: longitude ? Number(longitude) : null,
      };
      const { data } = await axios.put(`${API}/revenue/market-robot/${propertyId}/geo-config`, payload);
      setAutoCfg(data);
      toast.success("Auto-scan settings saved");
    } catch (e) {
      toast.error("Save failed");
    }
    setSaving(false);
  };

  const toggleAuto = async () => {
    if (!location.trim() && !(latitude && longitude)) { toast.error("Set a location first, then save before enabling"); return; }
    const next = !(autoCfg?.enabled);
    setAutoCfg({ ...(autoCfg || {}), enabled: next });
    try {
      await axios.put(`${API}/revenue/market-robot/${propertyId}/geo-config`, {
        ...(autoCfg || {}),
        enabled: next,
        location: location.trim(),
        radius_km: Number(radiusKm),
        days_ahead: Number(days),
        scan_interval_minutes: Number(autoCfg?.scan_interval_minutes || 120),
        latitude: latitude ? Number(latitude) : null,
        longitude: longitude ? Number(longitude) : null,
      });
      toast.success(next ? "Auto-scan enabled" : "Auto-scan paused");
    } catch { toast.error("Toggle failed"); }
  };

  // Persist Auto-Heal scheduler config. If `overrides` is provided, merge into current cfg.
  const saveHealCfg = async (overrides = {}) => {
    const base = healCfg || { enabled: false, interval_minutes: 60, threshold: 50, days_ahead: 30 };
    const payload = {
      enabled: overrides.enabled != null ? overrides.enabled : base.enabled,
      interval_minutes: overrides.interval_minutes != null ? overrides.interval_minutes : (base.interval_minutes || 60),
      threshold: overrides.threshold != null ? overrides.threshold : (base.threshold || 50),
      days_ahead: overrides.days_ahead != null ? overrides.days_ahead : (base.days_ahead || Number(days) || 30),
    };
    setHealCfgSaving(true);
    // Optimistic UI — flip immediately, rollback on failure
    setHealCfg({ ...(base || {}), ...payload });
    try {
      const { data } = await axios.put(
        `${API}/revenue/market-robot/${propertyId}/competitors/auto-heal/config`, payload,
      );
      setHealCfg(data);
      toast.success(
        payload.enabled
          ? `Auto-Heal açık — her ${payload.interval_minutes} dk arka planda çalışır`
          : "Auto-Heal kapatıldı"
      );
    } catch (e) {
      toast.error("Save failed — değişiklik geri alındı");
      setHealCfg(base);
    }
    setHealCfgSaving(false);
  };

  // ⚡ Auto-Heal — re-validates + re-scrapes competitors with hit_rate below threshold
  // (default 50). Background task; polls status for 3 min and refreshes the chart when done.
  const autoHealCompetitors = async () => {
    if (healing) return;
    setHealing(true);
    try {
      const { data } = await axios.post(
        `${API}/revenue/market-robot/${propertyId}/competitors/auto-heal`,
        { days_ahead: Number(days), threshold: 50 },
      );
      if (data.status === "skipped" || data.queued === 0) {
        toast.success(data.message || "Tüm rakipler zaten sağlıklı ✓");
        setHealing(false);
        return;
      }
      toast.success(data.message || `Auto-Heal: ${data.queued} rakip için başlatıldı`);
      setHealStatus({ status: "running", total: data.queued, healed: 0, failed: 0, done: 0 });
      // Poll every 8s up to 4 min
      const started = Date.now();
      const poll = async () => {
        try {
          const { data: st } = await axios.get(
            `${API}/revenue/market-robot/${propertyId}/competitors/auto-heal/status`,
          );
          setHealStatus(st);
          if (st?.status === "done") {
            toast.success(`Auto-Heal tamamlandı: ${st.healed || 0} iyileştirildi · ${st.failed || 0} başarısız`);
            setHealing(false);
            loadAll();
            return;
          }
          if (Date.now() - started > 4 * 60 * 1000) {
            setHealing(false);
            return;
          }
          setTimeout(poll, 8000);
        } catch {
          setHealing(false);
        }
      };
      setTimeout(poll, 5000);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Auto-Heal failed");
      setHealing(false);
    }
  };

  // Stable palette for competitor lines — vivid, high-contrast, colour-blind aware.
  // Picked with the "biz + market avg" hero colours (violet/amber) in mind so competitors
  // pop without clashing.
  const COMP_PALETTE = useMemo(() => [
    "#3b82f6", // blue-500
    "#f97316", // orange-500
    "#10b981", // emerald-500
    "#ec4899", // pink-500
    "#eab308", // yellow-500
    "#ef4444", // red-500
    "#14b8a6", // teal-500
    "#8b5cf6", // violet-500 (reserved for later competitors, our-line is lighter violet)
  ], []);

  // Chart derivation
  const chart = useMemo(() => {
    if (!snapshots.length) return null;
    const pad = { l: 55, r: 10, t: 28, b: 32 };
    const W = 1000, H = 380;
    const iW = W - pad.l - pad.r, iH = H - pad.t - pad.b;
    const n = snapshots.length;
    const sx = (i) => pad.l + (i / Math.max(n - 1, 1)) * iW;
    // Price axis: include our rate AND every competitor series in min/max so all lines fit
    const mktPrices = snapshots.map(s => s.avg_price || 0).filter(v => v > 0);
    const ourPrices = snapshots.map(s => s.our_avg_rate || 0).filter(v => v > 0);
    const compPrices = competitorSeries.flatMap(c => Object.values(c.prices_by_date || {})).filter(v => v > 0);
    const allPrices = [...mktPrices, ...ourPrices, ...compPrices];
    const pMin = allPrices.length ? Math.min(...allPrices) * 0.92 : 0;
    const pMax = allPrices.length ? Math.max(...allPrices) * 1.06 : 1;
    const syP = (v) => pad.t + iH - ((v - pMin) / Math.max(pMax - pMin, 1)) * iH;
    const syD = (v) => pad.t + iH - (v / 100) * iH;
    // Smooth path with Catmull-Rom → cubic bezier conversion (gentle curves, much easier to read)
    const smoothPath = (pts) => {
      if (!pts.length) return "";
      if (pts.length === 1) return `M ${pts[0].x} ${pts[0].y}`;
      let d = `M ${pts[0].x} ${pts[0].y}`;
      for (let i = 0; i < pts.length - 1; i++) {
        const p0 = pts[i - 1] || pts[i];
        const p1 = pts[i];
        const p2 = pts[i + 1];
        const p3 = pts[i + 2] || p2;
        const t = 0.18; // tension — low = rounder, high = straighter
        const cp1x = p1.x + (p2.x - p0.x) * t;
        const cp1y = p1.y + (p2.y - p0.y) * t;
        const cp2x = p2.x - (p3.x - p1.x) * t;
        const cp2y = p2.y - (p3.y - p1.y) * t;
        d += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${p2.x} ${p2.y}`;
      }
      return d;
    };
    // Market (avg of neighbourhood) — dashed amber, smoothed
    const mktPts = snapshots.map((s, i) => ({ x: sx(i), y: syP(s.avg_price || 0), v: s.avg_price || 0 }));
    const linePath = smoothPath(mktPts);
    // Our rate line (only dates with valid our_avg_rate) — solid thick violet, smoothed
    const ourLinePoints = snapshots.map((s, i) => ({ x: sx(i), y: syP(s.our_avg_rate || 0), v: s.our_avg_rate || 0 })).filter(p => p.v > 0);
    const ourLinePath = smoothPath(ourLinePoints);
    // One polyline per competitor — thin coloured lines, smoothed
    const compLines = competitorSeries.map((c, idx) => {
      const colour = COMP_PALETTE[idx % COMP_PALETTE.length];
      const pts = snapshots.map((s, i) => {
        const v = c.prices_by_date?.[s.date];
        return v ? { x: sx(i), y: syP(v), v } : null;
      }).filter(Boolean);
      return {
        id: c.id,
        name: c.name,
        colour,
        path: smoothPath(pts),
        points: pts,
        avg: c.avg_price,
        days: c.days_covered,
        attempted: c.attempted_days,
        hitRate: c.hit_rate,
        lastScraped: c.last_scraped,
        validationOk: c.validation_ok,
      };
    });
    return { pad, W, H, iW, iH, sx, syP, syD, linePath, ourLinePath, ourLinePoints, compLines, pMin, pMax };
  }, [snapshots, competitorSeries, COMP_PALETTE]);

  const miles = (radiusKm * 0.621371).toFixed(1);

  // Currency derived from scan location with priority: property-configured currency > scan city > fallback £
  const currency = useMemo(() => {
    const hint = (summary && summary.property_currency) || (summary && summary.scan_city) || (summary && summary.last_location) || location || "";
    return makeCurrencyFormatter(hint);
  }, [summary, location]);
  const cur = currency.format;
  const curShort = currency.short;

  // TOP 3 biggest absolute % changes vs previous day
  const top3Changes = useMemo(() => {
    const deltas = [];
    for (let i = 1; i < snapshots.length; i++) {
      const p = snapshots[i - 1].avg_price;
      const c = snapshots[i].avg_price;
      if (p > 0 && c > 0) {
        const pct = ((c - p) / p) * 100;
        deltas.push({ date: snapshots[i].date, pct, price: c, prevPrice: p });
      }
    }
    return deltas.sort((a, b) => Math.abs(b.pct) - Math.abs(a.pct)).slice(0, 3);
  }, [snapshots]);

  const scrollToDate = (date) => {
    setHighlightDate(date);
    const row = document.querySelector(`[data-row-date="${date}"]`);
    if (row) row.scrollIntoView({ behavior: "smooth", block: "center" });
    setTimeout(() => setHighlightDate(null), 2500);
  };

  return (
    <div className="space-y-5" data-testid="neighborhood-scan-panel">
      {/* Hero */}
      <div className="relative overflow-hidden rounded-2xl border border-emerald-500/30 bg-gradient-to-br from-emerald-950/70 via-teal-950/40 to-stone-900 p-6">
        <div className="absolute -top-10 -right-10 w-48 h-48 rounded-full bg-emerald-500/20 blur-3xl pointer-events-none" />
        <div className="relative flex items-start justify-between gap-4">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-xl bg-emerald-500/20 flex items-center justify-center shrink-0">
              <MapPin className="w-6 h-6 text-emerald-400" />
            </div>
            <div>
              <h2 className="text-xl font-black text-emerald-300 flex items-center gap-2">
                {t("ns.hero.title")}
                <span className="inline-flex items-center gap-1 text-[9px] font-bold uppercase tracking-wider text-emerald-400/80 bg-emerald-500/10 border border-emerald-500/30 rounded-full px-1.5 py-0.5" title="Chart auto-updates every 30s">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  Live · 30s
                </span>
                {summary?.data_freshness_seconds !== null && summary?.data_freshness_seconds !== undefined && (
                  <span className="text-[10px] font-semibold text-stone-400 bg-stone-800/60 border border-stone-700 rounded-full px-2 py-0.5"
                    title={`Last scrape: ${summary.last_scan || "—"}`}>
                    {(() => {
                      const s = Number(summary.data_freshness_seconds || 0);
                      if (s < 60) return t("ns.hero.updated_sec", { n: s });
                      if (s < 3600) return t("ns.hero.updated_min", { n: Math.round(s / 60) });
                      if (s < 86400) return t("ns.hero.updated_hr", { n: Math.round(s / 3600) });
                      return t("ns.hero.updated_day", { n: Math.round(s / 86400) });
                    })()}
                  </span>
                )}
                {ourSummary?.booking_cover_pct !== undefined && (
                  <span
                    className={`text-[10px] font-semibold rounded-full px-2 py-0.5 border ${
                      ourSummary.booking_cover_pct >= 70
                        ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
                        : ourSummary.booking_cover_pct >= 30
                        ? "bg-amber-500/10 border-amber-500/30 text-amber-300"
                        : "bg-rose-500/10 border-rose-500/30 text-rose-300"
                    }`}
                    title={`${ourSummary.booking_cover_days}/${snapshots.length} gün için Booking.com canlı fiyatımız var. Geri kalan günler internal rate'den hesaplanıyor.`}>
                    {t("ns.hero.biz_booking_live", { name: ourHotelName || t("ns.chart.legend.us"), pct: ourSummary.booking_cover_pct.toFixed(0) })}
                  </span>
                )}
              </h2>
              <p className="text-xs text-stone-400 mt-1">
                {(() => {
                  const txt = t("ns.hero.subtitle", {
                    miles: `__M__${miles}__M__`,
                    parallel: `__P__`,
                    live: `__L__`,
                  });
                  // Replace markers with styled spans
                  const parts = [];
                  let rest = txt;
                  const pushSpan = (cls, content, key) => parts.push(<span key={key} className={cls}>{content}</span>);
                  // Simple sequential replace — tokens appear in order
                  const re = /__M__(.+?)__M__|__P__|__L__/g;
                  let m; let idx = 0; let lastIdx = 0;
                  while ((m = re.exec(rest)) !== null) {
                    if (m.index > lastIdx) parts.push(rest.slice(lastIdx, m.index));
                    if (m[0].startsWith("__M__")) pushSpan("text-emerald-300 font-semibold", `${m[1]} miles`, `tk-m-${idx}`);
                    else if (m[0] === "__P__") pushSpan("text-amber-300 font-semibold", t("ns.hero.parallel"), `tk-p-${idx}`);
                    else if (m[0] === "__L__") pushSpan("text-emerald-300 font-semibold", t("ns.hero.live"), `tk-l-${idx}`);
                    lastIdx = m.index + m[0].length;
                    idx += 1;
                  }
                  if (lastIdx < rest.length) parts.push(rest.slice(lastIdx));
                  return parts;
                })()}
              </p>
            </div>
          </div>
          {autoCfg && (
            <div className="flex items-center gap-2 flex-wrap justify-end">
              <button onClick={refreshNeighborhood} disabled={refreshing}
                className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-[11px] font-bold transition-all bg-rose-500/15 text-rose-300 hover:bg-rose-500/25 border border-rose-500/30 disabled:opacity-50"
                data-testid="refresh-neighborhood-btn"
                title={t("ns.btn.clear_stale")}>
                {refreshing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Radar className="w-4 h-4" />}
                {refreshing ? t("ns.btn.clear_stale_loading") : t("ns.btn.clear_stale")}
              </button>
              <button onClick={() => setFixOpen(true)}
                className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-[11px] font-bold transition-all bg-amber-500/15 text-amber-300 hover:bg-amber-500/25 border border-amber-500/30"
                data-testid="fix-location-btn"
                title={t("ns.btn.fix_location")}>
                <MapPin className="w-4 h-4" />
                {t("ns.btn.fix_location")}
              </button>
              <button onClick={toggleAuto}
                className={`flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-bold transition-all ${autoCfg.enabled ? "bg-emerald-500 text-black shadow-lg shadow-emerald-500/30" : "bg-stone-800 text-stone-400 hover:bg-stone-700"}`}
                data-testid="geo-auto-toggle">
                {autoCfg.enabled ? <ToggleRight className="w-5 h-5" /> : <ToggleLeft className="w-5 h-5" />}
                {t("ns.btn.auto_scan")} {autoCfg.enabled ? "ON" : "OFF"}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Config form */}
      <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-5 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-[10px] font-bold uppercase text-stone-400 mb-1.5 tracking-wider">Location (Postcode / Address)</label>
            <input value={location} onChange={e => setLocation(e.target.value)} placeholder="e.g. E1 6AN"
              className="w-full px-3 py-2.5 text-sm bg-stone-950 border border-stone-700 rounded-lg text-stone-100 placeholder-stone-500 focus:outline-none focus:ring-2 focus:ring-emerald-500" data-testid="geo-location" />
          </div>
          <div>
            <label className="block text-[10px] font-bold uppercase text-stone-400 mb-1.5 tracking-wider">Radius · <span className="text-emerald-400">{radiusKm} km ({miles} mi)</span></label>
            <input type="range" min="0.5" max="10" step="0.1" value={radiusKm} onChange={e => setRadiusKm(e.target.value)} className="w-full accent-emerald-500" data-testid="geo-radius" />
            <div className="flex justify-between text-[9px] text-stone-500 mt-0.5"><span>0.5km</span><span>5km</span><span>10km</span></div>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div>
            <label className="block text-[10px] font-bold uppercase text-stone-400 mb-1.5 tracking-wider">Days Ahead</label>
            <select value={days} onChange={e => setDays(e.target.value)} className="w-full px-3 py-2.5 text-sm bg-stone-950 border border-stone-700 rounded-lg text-stone-100" data-testid="geo-days">
              {[7,15,30,60,90].map(d => <option key={d} value={d}>{d} days</option>)}
            </select>
          </div>
          <div>
            <label className="block text-[10px] font-bold uppercase text-stone-400 mb-1.5 tracking-wider">Auto Interval (min)</label>
            <select value={autoCfg?.scan_interval_minutes || 120} onChange={e => setAutoCfg(c => ({ ...(c || {}), scan_interval_minutes: Number(e.target.value) }))} className="w-full px-3 py-2.5 text-sm bg-stone-950 border border-stone-700 rounded-lg text-stone-100" data-testid="geo-interval">
              {[30,60,120,240,480,1440].map(m => <option key={m} value={m}>{m >= 60 ? (m/60)+"h" : m+"m"}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-[10px] font-bold uppercase text-stone-400 mb-1.5 tracking-wider">Latitude</label>
            <input value={latitude} onChange={e => setLatitude(e.target.value)} placeholder="51.5074" className="w-full px-3 py-2.5 text-sm bg-stone-950 border border-stone-700 rounded-lg text-stone-100" />
          </div>
          <div>
            <label className="block text-[10px] font-bold uppercase text-stone-400 mb-1.5 tracking-wider">Longitude</label>
            <input value={longitude} onChange={e => setLongitude(e.target.value)} placeholder="-0.1278" className="w-full px-3 py-2.5 text-sm bg-stone-950 border border-stone-700 rounded-lg text-stone-100" />
          </div>
        </div>

        <div className="flex gap-2">
          <button onClick={runScan} disabled={scanning}
            className="flex-1 py-3 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-black font-black rounded-xl flex items-center justify-center gap-2 disabled:opacity-60 shadow-lg shadow-emerald-500/30"
            data-testid="geo-scan-btn">
            {scanning ? <Loader2 className="w-5 h-5 animate-spin" /> : <Radar className="w-5 h-5" />}
            {scanning ? "Scanning Booking.com…" : `Scan Now (${miles} mi)`}
          </button>
          <button onClick={saveAutoCfg} disabled={saving}
            className="px-5 py-3 bg-stone-800 hover:bg-stone-700 text-stone-100 font-bold rounded-xl flex items-center gap-2 disabled:opacity-60 border border-stone-700"
            data-testid="geo-save-cfg">
            {saving ? <Loader2 className="w-5 h-5 animate-spin" /> : <Save className="w-5 h-5" />}
            Save
          </button>
        </div>
        {autoCfg?.last_scan && (
          <p className="text-[11px] text-stone-500 flex items-center gap-1.5"><Timer className="w-3 h-3" /> Last auto-scan: <span className="text-emerald-300 font-semibold">{new Date(autoCfg.last_scan).toLocaleString()}</span> · Total: <span className="text-emerald-300 font-semibold">{autoCfg.total_scans || 0}</span></p>
        )}
      </div>

      {/* Competitor discovery — auto + manual, two-tier flow */}
      {propertyId !== "all" && (
        <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-5 space-y-4" data-testid="competitor-discovery-section">
          <div className="flex items-start justify-between gap-3 flex-wrap">
            <div className="min-w-0 flex-1">
              <h4 className="text-sm font-bold text-stone-100 flex items-center gap-2">
                <Building2 className="w-4 h-4 text-cyan-400" />
                Rakipler · Competitors
              </h4>
              <p className="text-[11px] text-stone-500 mt-0.5">
                Önce <strong className="text-cyan-300">otomatik</strong> Booking.com taraması yapın — yetmezse <strong className="text-emerald-300">manuel</strong> ekleyin. Bir sonraki "Scan Now" taramasında bu rakiplerin fiyatları çekilir.
              </p>
            </div>
            <button
              onClick={runAutoDiscoverCompetitors}
              disabled={autoDiscovering}
              className="shrink-0 px-4 py-2 bg-gradient-to-r from-cyan-500 to-blue-500 hover:brightness-110 text-black font-black rounded-xl text-sm flex items-center gap-2 disabled:opacity-50 shadow-lg shadow-cyan-500/30"
              data-testid="auto-discover-competitors-btn"
              title="Booking.com'da yakın komşuları bul ve top 5'i otomatik rakip olarak ekle"
            >
              {autoDiscovering ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
              {autoDiscovering ? "Tarıyor..." : "🤖 Otomatik Rakip Bul & Ekle"}
            </button>
          </div>

          {/* Auto-discovery result summary */}
          {discoveryResult && (
            <div className="bg-cyan-500/5 border border-cyan-500/20 rounded-xl p-3" data-testid="discovery-result">
              <p className="text-xs text-cyan-200">
                <strong>{discoveryResult.added}</strong> rakip otomatik eklendi ·
                <strong className="ml-1">{discoveryResult.total}</strong> aday Booking.com'dan bulundu.
                {discoveryResult.candidates.length > 0 && (
                  <span className="text-stone-400"> Önizleme: {discoveryResult.candidates.slice(0, 5).map(c => c.name).join(", ")}{discoveryResult.candidates.length > 5 ? "…" : ""}</span>
                )}
              </p>
            </div>
          )}

          {/* Manual add — fallback for missing ones */}
          <div className="pt-3 border-t border-stone-800" data-testid="manual-competitor-add">
            <div className="flex items-center gap-2 mb-2 flex-wrap">
              <Plus className="w-4 h-4 text-emerald-400" />
              <h5 className="text-xs font-bold text-stone-200 uppercase tracking-wider">Manuel Ekle · Manual Add</h5>
              <span className="text-[10px] text-stone-500 italic">Otomatik bulamadıklarını sen ekle</span>
            </div>
            <div className="flex flex-wrap gap-2">
              <input
                value={manualName}
                onChange={e => setManualName(e.target.value)}
                placeholder="Otel adı (opsiyonel)"
                className="w-full sm:w-48 px-3 py-2 text-sm bg-stone-950 border border-stone-700 rounded-lg text-stone-100 placeholder-stone-500 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                data-testid="manual-comp-name"
                disabled={manualAdding}
              />
              <input
                value={manualUrl}
                onChange={e => setManualUrl(e.target.value)}
                placeholder="https://www.booking.com/hotel/gb/the-barkston.html"
                className="flex-1 min-w-[260px] px-3 py-2 text-sm font-mono bg-stone-950 border border-stone-700 rounded-lg text-stone-100 placeholder-stone-500 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                data-testid="manual-comp-url"
                disabled={manualAdding}
                onKeyDown={e => { if (e.key === "Enter") addManualCompetitor(); }}
              />
              <button
                onClick={addManualCompetitor}
                disabled={manualAdding || !manualUrl}
                className="px-4 py-2 bg-emerald-500 hover:bg-emerald-400 text-black font-bold rounded-lg text-sm flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                data-testid="manual-comp-add-btn"
              >
                {manualAdding ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                {manualAdding ? "Ekleniyor..." : "+ Manuel Ekle"}
              </button>
            </div>
            <p className="text-[10px] text-stone-500 mt-2">
              ✓ Tek-odalı / studio mülkler otomatik filtrelenir. ✓ URL Booking.com'da doğrulanır. ✓ Bir sonraki tarama bu rakibi de çeker.
            </p>
          </div>
        </div>
      )}

      {/* Last scan result */}
      {lastResult && (
        <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-xl p-4" data-testid="geo-last-result">
          <div className="flex items-center gap-2 text-emerald-300 font-bold text-sm">
            <TrendingUp className="w-4 h-4" /> Scan completed
          </div>
          <p className="text-xs text-stone-300 mt-1">
            <span className="text-emerald-400 font-semibold">{lastResult.dates_scanned}</span> dates · {lastResult.location}
          </p>
        </div>
      )}

      {/* Summary cards */}
      {summary && summary.total_snapshots > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3" data-testid="geo-summary">
          <KPI label={t("ns.kpi.snapshots")} value={summary.total_snapshots} tone="slate" icon={Activity} />
          <KPI label={t("ns.kpi.avg_unavail")} value={`${summary.avg_unavailable_pct}%`} tone="amber" icon={Building2} />
          <KPI label={t("ns.kpi.market_avg")} value={cur(summary.avg_price)} tone="emerald" icon={PoundSterling} testId="geo-avg-price" />
          <KPI label={t("ns.kpi.market_low")} value={cur(summary.min_price)} tone="emerald" />
          <KPI label={t("ns.kpi.market_high")} value={cur(summary.max_price)} tone="rose" />
        </div>
      )}

      {/* Head-to-head: Us vs Market */}
      {ourSummary && summary && summary.avg_price > 0 && (
        <div className="bg-gradient-to-r from-cyan-500/10 via-violet-500/10 to-stone-900/60 border border-cyan-500/30 rounded-2xl p-5" data-testid="us-vs-market">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-cyan-500/20 flex items-center justify-center">
                <Activity className="w-5 h-5 text-cyan-400" />
              </div>
              <div>
                <h3 className="text-sm font-black text-cyan-200">{t("ns.vs.title", { name: ourHotelName || t("ns.chart.legend.us"), days })}</h3>
                <p className="text-[11px] text-stone-400 mt-0.5">{t("ns.vs.subtitle", { name: ourHotelName || t("ns.chart.legend.us") })}</p>
              </div>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 flex-1 md:max-w-3xl">
              <CompareCard
                label={t("ns.vs.avg_price")}
                us={cur(ourSummary.avg_rate)}
                them={cur(summary.avg_price)}
                delta={((ourSummary.avg_rate - summary.avg_price) / summary.avg_price) * 100}
                kind="price"
              />
              <CompareCard
                label={t("ns.vs.occupancy")}
                us={`${ourSummary.avg_occupancy_pct}%`}
                them={`${summary.avg_unavailable_pct}%`}
                delta={ourSummary.avg_occupancy_pct - summary.avg_unavailable_pct}
                kind="occupancy"
              />
              <CompareCard
                label={t("ns.vs.rooms")}
                us={ourSummary.total_rooms}
                them={Math.round(summary.max_price > 0 ? snapshots.reduce((a,s) => a + (s.total_properties || 0), 0) / Math.max(snapshots.length, 1) : 0)}
                kind="count"
                hint={t("ns.vs.rooms_hint")}
              />
              <div className="bg-stone-950/60 border border-stone-800 rounded-lg p-2.5">
                <p className="text-[9px] font-bold uppercase tracking-widest text-stone-400">{t("ns.vs.position")}</p>
                <p className="text-xs font-black text-cyan-300 mt-1"
                   dangerouslySetInnerHTML={{
                     __html: ourSummary.avg_rate > summary.avg_price
                       ? t("ns.vs.above_market", {
                           pct: `<span class="text-rose-300">${(((ourSummary.avg_rate - summary.avg_price) / summary.avg_price) * 100).toFixed(1)}</span>`,
                         })
                       : t("ns.vs.below_market", {
                           pct: `<span class="text-emerald-300">${(((summary.avg_price - ourSummary.avg_rate) / summary.avg_price) * 100).toFixed(1)}</span>`,
                         })
                   }} />
                <p className="text-[9px] text-stone-500 mt-0.5">
                  {ourSummary.avg_occupancy_pct > summary.avg_unavailable_pct ? t("ns.vs.high_occ") : t("ns.vs.low_occ")}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Scrape Health Card — per-competitor data quality at a glance */}
      {competitorSeries.length > 0 && snapshots.length > 0 && propertyId !== "all" && (
        <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-5" data-testid="scrape-health-card">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-cyan-400" />
              <h3 className="text-sm font-bold text-stone-100">{t("ns.health.title")}</h3>
              <span className="text-[10px] text-stone-500">{t("ns.health.subtitle", { n: competitorSeries.length, days })}</span>
            </div>
            <div className="flex items-center gap-2 text-[10px]">
              {(() => {
                const healthy = competitorSeries.filter(c => (c.hit_rate || 0) >= 85).length;
                const warn = competitorSeries.filter(c => (c.hit_rate || 0) >= 50 && (c.hit_rate || 0) < 85).length;
                const bad = competitorSeries.filter(c => (c.hit_rate || 0) < 50).length;
                return (
                  <>
                    {healthy > 0 && <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 font-bold">{healthy} OK</span>}
                    {warn > 0 && <span className="px-2 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-300 font-bold">{warn} Warn</span>}
                    {bad > 0 && <span className="px-2 py-0.5 rounded-full bg-rose-500/10 border border-rose-500/30 text-rose-300 font-bold">{bad} Low</span>}
                    {/* Auto-Heal button — heals under-performers (hit<50%) silently in background */}
                    {(() => {
                      const needy = competitorSeries.filter(c => (c.hit_rate || 0) < 50).length;
                      if (needy === 0 && !healing) return null;
                      return (
                        <button
                          onClick={autoHealCompetitors}
                          disabled={healing}
                          data-testid="scrape-health-auto-heal-btn"
                          className={`ml-1 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-black border transition-all ${
                            healing
                              ? "bg-cyan-500/10 border-cyan-500/30 text-cyan-300 cursor-wait"
                              : "bg-gradient-to-r from-cyan-500 to-violet-500 text-black border-transparent hover:brightness-110 shadow-md shadow-cyan-500/20"
                          }`}
                          title={t("ns.health.heal_title", { n: needy })}
                        >
                          {healing ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
                          {healing
                            ? (healStatus?.total
                                ? t("ns.health.heal_loading", { done: healStatus.done || 0, total: healStatus.total })
                                : t("ns.health.heal_loading", { done: 0, total: "…" }))
                            : t("ns.health.heal_button", { n: needy })}
                        </button>
                      );
                    })()}
                    {/* Auto-Heal scheduler toggle — persistent; runs in background on interval. */}
                    <button
                      onClick={() => saveHealCfg({ enabled: !(healCfg?.enabled) })}
                      disabled={healCfgSaving}
                      data-testid="auto-heal-scheduler-toggle"
                      className={`ml-1 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[10px] font-bold border transition-all ${
                        healCfg?.enabled
                          ? "bg-emerald-500/15 border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/25"
                          : "bg-stone-800 border-stone-700 text-stone-400 hover:border-stone-600"
                      } disabled:opacity-50`}
                      title={healCfg?.enabled
                        ? t("ns.health.auto_on_title", { n: healCfg.interval_minutes || 60 })
                        : t("ns.health.auto_off_title")}
                    >                      {healCfg?.enabled ? <ToggleRight className="w-3.5 h-3.5" /> : <ToggleLeft className="w-3.5 h-3.5" />}
                      <span className="tabular-nums">{healCfg?.enabled ? t("ns.health.auto_on") : t("ns.health.auto_off")}</span>
                    </button>
                    {healCfg?.enabled && (
                      <select
                        value={healCfg.interval_minutes || 60}
                        onChange={(e) => saveHealCfg({ interval_minutes: Number(e.target.value) })}
                        disabled={healCfgSaving}
                        data-testid="auto-heal-interval-select"
                        className="ml-0 px-1.5 py-1 text-[10px] font-bold bg-stone-950 border border-stone-700 rounded-lg text-stone-200 cursor-pointer hover:border-stone-500"
                        title="Otomatik iyileştirme sıklığı"
                      >
                        <option value={30}>30m</option>
                        <option value={60}>1h</option>
                        <option value={120}>2h</option>
                        <option value={240}>4h</option>
                        <option value={480}>8h</option>
                        <option value={1440}>24h</option>
                      </select>
                    )}
                    {/* Wrong neighborhood? Reset & re-discover */}
                    <button
                      onClick={resetNeighbors}
                      disabled={resetting}
                      data-testid="neighborhood-reset-btn"
                      title="Yanlış komşular? Tümünü sil + auto-geocode + gerçek komşuları yeniden bul."
                      className={`ml-1 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[10px] font-bold border transition-all ${
                        resetting
                          ? "bg-orange-500/10 border-orange-500/30 text-orange-300 cursor-wait"
                          : "bg-stone-800 border-stone-600 text-orange-300 hover:bg-orange-500/15 hover:border-orange-400"
                      }`}
                    >
                      {resetting ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                      {resetting ? "Sıfırlanıyor..." : "Komşuları Sıfırla"}
                    </button>
                  </>
                );
              })()}
            </div>
          </div>
          {/* Auto-Heal live progress bar — visible while healing */}
          {healing && healStatus?.total > 0 && (
            <div className="mb-3 rounded-lg bg-cyan-500/5 border border-cyan-500/20 px-3 py-2"
                 data-testid="auto-heal-progress">
              <div className="flex items-center justify-between text-[10px] mb-1">
                <span className="text-cyan-300 font-bold flex items-center gap-1">
                  <Zap className="w-3 h-3" /> {t("ns.health.progress_bg")}
                </span>
                <span className="text-stone-400 tabular-nums">
                  {healStatus.done || 0} / {healStatus.total}
                  {healStatus.healed > 0 && <> · <span className="text-emerald-300">{healStatus.healed} ✓</span></>}
                  {healStatus.failed > 0 && <> · <span className="text-rose-300">{healStatus.failed} ✗</span></>}
                </span>
              </div>
              <div className="w-full h-1 bg-stone-800 rounded-full overflow-hidden">
                <div className="h-full bg-gradient-to-r from-cyan-400 to-violet-400 transition-all"
                     style={{ width: `${Math.min(100, ((healStatus.done || 0) / Math.max(healStatus.total, 1)) * 100)}%` }} />
              </div>
            </div>
          )}
          {/* Auto-Heal scheduler status line — visible when auto mode is ON and no active healing */}
          {healCfg?.enabled && !healing && (
            <div className="mb-3 flex items-center justify-between gap-2 text-[10px] rounded-lg bg-emerald-500/5 border border-emerald-500/20 px-3 py-2"
                 data-testid="auto-heal-scheduler-status">
              <span className="text-emerald-300 font-bold flex items-center gap-1.5">
                <Zap className="w-3 h-3" /> {t("ns.health.scheduler_running", { interval: healCfg.interval_minutes, threshold: healCfg.threshold })}
              </span>
              <span className="text-stone-400 tabular-nums">
                {healCfg.last_run ? (() => {
                  const diff = Math.max(0, (Date.now() - new Date(healCfg.last_run).getTime()) / 60000);
                  const remaining = Math.max(0, (healCfg.interval_minutes || 60) - diff);
                  return remaining > 60
                    ? t("ns.health.last_next_h", { last: Math.round(diff / 60), next: Math.round(remaining / 60) })
                    : t("ns.health.last_next_m", { last: Math.round(diff), next: Math.round(remaining) });
                })() : t("ns.health.never_ran")}
                {healCfg.total_runs ? t("ns.health.runs_count", { n: healCfg.total_runs }) : ""}
              </span>
            </div>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-2">
            {competitorSeries.map((c, idx) => {
              const colour = COMP_PALETTE[idx % COMP_PALETTE.length];
              const hit = Number(c.hit_rate || 0);
              const tone = hit >= 85 ? "emerald" : hit >= 50 ? "amber" : "rose";
              const toneClasses = {
                emerald: { ring: "border-emerald-500/30", bar: "bg-emerald-400", text: "text-emerald-300", pct: "text-emerald-200" },
                amber:   { ring: "border-amber-500/30",   bar: "bg-amber-400",   text: "text-amber-300",   pct: "text-amber-200" },
                rose:    { ring: "border-rose-500/30",    bar: "bg-rose-400",    text: "text-rose-300",    pct: "text-rose-200" },
              }[tone];
              // last_scraped → relative time
              const relAgo = (() => {
                if (!c.last_scraped) return "—";
                const d = new Date(c.last_scraped);
                const diff = Math.max(0, (Date.now() - d.getTime()) / 1000);
                if (diff < 60) return `${Math.round(diff)}s`;
                if (diff < 3600) return `${Math.round(diff / 60)}m`;
                if (diff < 86400) return `${Math.round(diff / 3600)}h`;
                return `${Math.round(diff / 86400)}d`;
              })();
              const coverPct = c.attempted_days > 0 ? Math.round((c.days_covered / c.attempted_days) * 100) : 0;
              return (
                <div key={c.id}
                     className={`rounded-xl bg-stone-950/60 border ${toneClasses.ring} p-3`}
                     data-testid={`scrape-health-${c.id}`}>
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2 min-w-0 flex-1">
                      <span className="w-2.5 h-2.5 rounded-sm flex-shrink-0" style={{ background: colour }} />
                      <span className="text-[12px] font-bold text-stone-100 truncate" title={c.name}>{c.name}</span>
                    </div>
                    <span className={`text-[10px] font-black tabular-nums ${toneClasses.text}`} title={`Hit rate: ${hit}%`}>
                      {hit}%
                    </span>
                  </div>
                  {/* Coverage bar */}
                  <div className="w-full h-1.5 bg-stone-800 rounded-full overflow-hidden mb-2">
                    <div className={`h-full ${toneClasses.bar} transition-all`} style={{ width: `${coverPct}%` }} />
                  </div>
                  <div className="flex items-center justify-between text-[10px]">
                    <span className="text-stone-400">
                      <span className={`font-bold tabular-nums ${toneClasses.pct}`}>{c.days_covered || 0}</span>
                      <span className="text-stone-500">/{c.attempted_days || 0} gün</span>
                    </span>
                    <span className="text-stone-500" title={c.last_scraped || ""}>
                      <Clock className="inline w-2.5 h-2.5 mr-0.5 -mt-0.5" />
                      {relAgo}
                    </span>
                    {c.avg_price != null && (
                      <span className="font-bold tabular-nums" style={{ color: colour }}>
                        {curShort(c.avg_price)}
                      </span>
                    )}
                  </div>
                  {c.validation_ok === false && (
                    <div className="mt-2 text-[9px] font-bold text-rose-300 bg-rose-500/10 border border-rose-500/30 rounded-md px-2 py-0.5">
                      ⚠ URL validation failed
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Chart — Avg Price + Demand with per-competitor lines + LEFT LEGEND */}
      {chart && snapshots.length > 2 && (
        <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-5" data-testid="geo-chart">
          <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-emerald-400" />
              <h3 className="text-sm font-bold text-stone-100">{t("ns.chart.title")}</h3>
              <span className="text-[10px] text-stone-500">({snapshots.length} gün)</span>
            </div>
            {/* Range picker pills */}
            <div className="flex items-center gap-1 bg-stone-950 border border-stone-700 rounded-lg p-0.5" data-testid="geo-chart-range-picker">
              {[7, 15, 30, 60, 90].map(d => (
                <button
                  key={d}
                  onClick={() => setDays(d)}
                  className={`px-2.5 py-1 text-[10px] font-bold rounded-md transition-colors ${
                    Number(days) === d
                      ? "bg-emerald-500 text-black shadow-sm"
                      : "text-stone-400 hover:text-stone-100 hover:bg-stone-800"
                  }`}
                  data-testid={`range-${d}d`}
                >
                  {d}d
                </button>
              ))}
            </div>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-[10px] text-stone-400" data-testid="geo-chart-legend">
              <span className="flex items-center gap-1.5" title={t("ns.chart.legend.demand")}><span className="w-2 h-3 rounded-sm bg-emerald-500/70" /> {t("ns.chart.legend.demand")}</span>
              <span className="flex items-center gap-1.5" title={t("ns.chart.legend.market")}><span className="w-5 h-[2px]" style={{ background: "repeating-linear-gradient(90deg,#f59e0b 0,#f59e0b 4px,transparent 4px,transparent 7px)" }} /> {t("ns.chart.legend.market")}</span>
              {ourHotelName && (
                <span className="flex items-center gap-1.5" title={ourHotelName}><span className="w-5 h-[3px] rounded-full bg-violet-400" /> <span className="truncate max-w-[120px] inline-block">{ourHotelName}</span></span>
              )}
              <span className="text-stone-500/70 border-l border-stone-700 pl-3 italic">{t("ns.chart.legend.hint")}</span>
            </div>
          </div>

          {/* Two-column layout: left=hotel legend w/ avg prices, right=chart */}
          <div className="flex flex-col lg:flex-row gap-4">
            {/* Left legend — hotels list */}
            <div className="lg:w-52 flex-shrink-0 space-y-1.5 lg:max-h-[320px] lg:overflow-y-auto lg:pr-2" data-testid="geo-chart-hotel-legend">
              <div className="text-[9px] font-bold uppercase tracking-widest text-stone-500 mb-1">{t("ns.chart.hotels")}</div>
              {/* Our hotel — hero row */}
              {ourHotelName && (
                <div className="flex items-center justify-between gap-2 rounded-lg bg-violet-500/10 border border-violet-500/30 px-2.5 py-1.5" data-testid="geo-legend-ours">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="w-3 h-3 rounded-sm bg-violet-400 flex-shrink-0" />
                    <span className="text-[11px] font-black text-violet-200 truncate" title={ourHotelName}>{ourHotelName}</span>
                  </div>
                  {ourSummary?.avg_rate && (
                    <span className="text-[10px] font-bold text-violet-300 tabular-nums flex-shrink-0">
                      {curShort(ourSummary.avg_rate)}
                    </span>
                  )}
                </div>
              )}
              {/* Market avg row */}
              <div className="flex items-center justify-between gap-2 rounded-lg bg-amber-500/5 border border-amber-500/20 px-2.5 py-1.5" data-testid="geo-legend-market">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="w-3 h-[2px] bg-amber-400 flex-shrink-0" />
                  <span className="text-[11px] font-black text-amber-300 truncate">{t("ns.chart.legend.market")}</span>
                </div>
                {summary?.avg_price && (
                  <span className="text-[10px] font-bold text-amber-300 tabular-nums flex-shrink-0">
                    {curShort(summary.avg_price)}
                  </span>
                )}
              </div>
              <div className="h-px bg-stone-800 my-2" />
              <div className="text-[9px] font-bold uppercase tracking-widest text-stone-500 mb-1">{t("ns.chart.competitors", { n: competitorSeries.length })}</div>
              {/* Competitor rows — clickable to hide/show */}
              {competitorSeries.length === 0 && (
                <div className="text-[10px] text-stone-500 italic px-2.5 py-1.5">{t("ns.chart.no_comps")}</div>
              )}
              {chart.compLines.map((c) => {
                const hidden = !!hiddenComps[c.id];
                return (
                  <button
                    key={`leg-${c.id}`}
                    onClick={() => setHiddenComps(p => ({ ...p, [c.id]: !hidden }))}
                    onMouseEnter={() => !hidden && setHoveredCompId(c.id)}
                    onMouseLeave={() => setHoveredCompId(null)}
                    className={`w-full flex items-center justify-between gap-2 rounded-lg border px-2.5 py-1.5 transition-all ${
                      hidden
                        ? "bg-stone-900/20 border-stone-900 opacity-50 hover:opacity-80"
                        : hoveredCompId === c.id
                        ? "bg-stone-800/80 border-stone-500 ring-1 ring-stone-500"
                        : "bg-stone-900/60 border-stone-800 hover:border-stone-600"
                    }`}
                    data-testid={`geo-legend-comp-${c.id}`}
                    title={hidden ? "Grafikte göster" : "Fareyi üstüne tut → vurgula · Tıkla → gizle"}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="w-3 h-[2px] flex-shrink-0 rounded" style={{ background: hidden ? "#44403c" : c.colour }} />
                      <span className={`text-[11px] font-semibold truncate ${hidden ? "line-through text-stone-500" : "text-stone-200"}`} title={c.name}>{c.name}</span>
                    </div>
                    {c.avg != null ? (
                      <span className="text-[10px] font-bold tabular-nums flex-shrink-0" style={{ color: hidden ? "#57534e" : c.colour }}>
                        {curShort(c.avg)}
                      </span>
                    ) : (
                      <span className="text-[9px] text-stone-600 flex-shrink-0">— no data</span>
                    )}
                  </button>
                );
              })}
              {competitorSeries.length > 0 && (
                <div className="text-[9px] text-stone-500 italic px-2 pt-2 text-center leading-snug"
                     dangerouslySetInnerHTML={{ __html: "💡 " + t("ns.chart.tip") }} />
              )}
            </div>

            <div className="flex-1 relative overflow-x-auto">
            {/* Y-axis left (demand %) */}
            <div className="absolute left-0 top-0 bottom-0 w-12 pointer-events-none z-10">
              {[100,75,50,25,0].map(v => (
                <div key={v} className="absolute right-1 text-[11px] font-bold text-stone-200 tabular-nums"
                  style={{ top: `calc(${((100-v)/100)*(chart.H-chart.pad.t-chart.pad.b)/chart.H*100}% + ${chart.pad.t/chart.H*100}% - 7px)`, lineHeight: 1 }}>{v}%</div>
              ))}
            </div>
            {/* Y-axis right (price £) */}
            <div className="absolute right-0 top-0 bottom-0 w-14 pointer-events-none z-10">
              {[1,0.75,0.5,0.25,0].map(f => {
                const val = Math.round(chart.pMin + f * (chart.pMax - chart.pMin));
                return <div key={f} className="absolute left-1 text-[11px] font-bold text-amber-300 tabular-nums"
                  style={{ top: `calc(${((1-f)*chart.iH + chart.pad.t)/chart.H*100}% - 7px)`, lineHeight: 1 }}>{cur(val)}</div>;
              })}
            </div>

            <svg viewBox={`0 0 ${chart.W} ${chart.H}`} className="w-full" style={{ minWidth: `${Math.max(600, snapshots.length * 18)}px` }}
                 onMouseLeave={() => setHoverIdx(null)}
                 onMouseMove={(e) => {
                   const svg = e.currentTarget;
                   const rect = svg.getBoundingClientRect();
                   const xPx = e.clientX - rect.left;
                   // map pixel → viewBox x
                   const vbx = (xPx / rect.width) * chart.W;
                   const ratio = Math.max(0, Math.min(1, (vbx - chart.pad.l) / chart.iW));
                   const idx = Math.round(ratio * (snapshots.length - 1));
                   setHoverIdx(idx);
                 }}>
              {/* Weekend vertical bands — soft, subtle, for temporal anchoring */}
              {snapshots.map((s, i) => {
                if (!s?.date) return null;
                const dow = new Date(s.date + "T00:00:00").getDay(); // 0=Sun, 6=Sat
                if (dow !== 0 && dow !== 6) return null;
                const bandW = chart.iW / Math.max(snapshots.length - 1, 1);
                return <rect key={`wk-${i}`} x={chart.sx(i) - bandW / 2} y={chart.pad.t}
                             width={bandW} height={chart.iH} fill="#1c1917" opacity="0.5" />;
              })}
              {/* Grid */}
              {[0,25,50,75,100].map(v => (
                <line key={v} x1={chart.pad.l} x2={chart.W - chart.pad.r} y1={chart.syD(v)} y2={chart.syD(v)} stroke="#374151" strokeWidth="0.5" />
              ))}
              {/* Demand bars — very subtle behind the price lines so they never fight for attention */}
              {snapshots.map((s, i) => {
                const h = (s.unavailable_pct / 100) * chart.iH;
                const x = chart.sx(i) - 2.5;
                const y = chart.pad.t + chart.iH - h;
                const hot = s.unavailable_pct >= 80;
                return (
                  <rect key={`bar-${i}`} x={x} y={y} width={5} height={h} rx={1.5}
                    fill={hot ? "#ef4444" : s.unavailable_pct >= 60 ? "#14b8a6" : "#10b981"} opacity="0.22" />
                );
              })}
              {/* === MARKET AVERAGE (dashed amber, smoothed) — dim when user is hovering a competitor === */}
              <path d={chart.linePath} fill="none" stroke="#f59e0b" strokeWidth="2"
                    strokeDasharray="6 3"
                    opacity={hoveredCompId ? 0.25 : 0.9} strokeLinecap="round" />
              {/* === OUR HOTEL price line (solid thicker violet — hero line) === */}
              {chart.ourLinePath && (
                <path d={chart.ourLinePath} fill="none" stroke="#a78bfa" strokeWidth="3"
                      opacity={hoveredCompId ? 0.25 : 1} strokeLinecap="round" strokeLinejoin="round" />
              )}
              {/* === COMPETITOR LINES — dimmed/highlighted based on legend hover === */}
              {chart.compLines.map((c) => {
                if (!c.path || hiddenComps[c.id]) return null;
                const isHovered = hoveredCompId === c.id;
                const isDimmed = hoveredCompId && !isHovered;
                return (
                  <g key={`comp-${c.id}`} style={{ transition: "opacity 0.15s" }}>
                    <path d={c.path} fill="none" stroke={c.colour}
                          strokeWidth={isHovered ? 2.8 : 1.6}
                          opacity={isDimmed ? 0.12 : (isHovered ? 1 : 0.7)}
                          strokeLinecap="round" strokeLinejoin="round" />
                    {isHovered && c.points.map((p, i) => (
                      <circle key={i} cx={p.x} cy={p.y} r="2.4" fill={c.colour} stroke="#0a0a0a" strokeWidth="0.6" />
                    ))}
                  </g>
                );
              })}
              {/* === HOVER CROSSHAIR + TOOLTIP === */}
              {hoverIdx !== null && snapshots[hoverIdx] && (() => {
                const s = snapshots[hoverIdx];
                const hx = chart.sx(hoverIdx);
                const dt = new Date(s.date + "T00:00:00");
                const dowLabel = dt.toLocaleDateString("en", { weekday: "short" });
                // Build tooltip rows: Our + Market + visible comps, sorted by price desc.
                // Each non-market row gets Δ vs Pazar (absolute + %) so the revenue manager
                // can spot at a glance who's over/under priced on this date.
                const market = s.avg_price || 0;
                const rows = [];
                if (s.our_avg_rate > 0) rows.push({ label: ourHotelName || t("ns.chart.legend.us"), price: s.our_avg_rate, colour: "#a78bfa", hero: true, isMarket: false });
                if (market > 0) rows.push({ label: t("ns.chart.legend.market"), price: market, colour: "#f59e0b", dashed: true, isMarket: true });
                chart.compLines.forEach((c) => {
                  if (hiddenComps[c.id]) return;
                  const v = competitorSeries.find(cs => cs.id === c.id)?.prices_by_date?.[s.date];
                  if (v) rows.push({ label: c.name, price: v, colour: c.colour, isMarket: false });
                });
                rows.sort((a, b) => b.price - a.price);
                const tipW = 235, rowH = 14, tipH = 28 + rows.length * rowH;
                const flipLeft = hx + tipW + 12 > chart.W - chart.pad.r;
                const tipX = flipLeft ? hx - tipW - 10 : hx + 10;
                const tipY = Math.max(chart.pad.t + 4, Math.min(chart.pad.t + 20, chart.H - tipH - 4));
                return (
                  <g key={`hover-${hoverIdx}`} style={{ pointerEvents: "none" }}>
                    {/* crosshair */}
                    <line x1={hx} x2={hx} y1={chart.pad.t} y2={chart.pad.t + chart.iH}
                          stroke="#a8a29e" strokeWidth="0.8" strokeDasharray="2 3" opacity="0.75" />
                    {/* tooltip card */}
                    <rect x={tipX} y={tipY} width={tipW} height={tipH} rx="6"
                          fill="#0a0a0a" stroke="#44403c" strokeWidth="1" opacity="0.96" />
                    <text x={tipX + 8} y={tipY + 14} fontSize="10" fontWeight="800" fill="#fafaf9">
                      {dt.toLocaleDateString("en", { day: "2-digit", month: "short" })} <tspan fill="#a8a29e" fontWeight="600">·{dowLabel}</tspan>
                    </text>
                    <text x={tipX + tipW - 8} y={tipY + 14} fontSize="9" fontWeight="700" fill="#fbbf24" textAnchor="end">
                      {t("ns.chart.demand_label", { pct: Math.round(s.unavailable_pct || 0) })}
                    </text>
                    {rows.map((r, ri) => {
                      // Δ vs market: positive = above market (rose), negative = below (emerald).
                      // Market row itself gets no delta — it's the baseline.
                      const showDelta = !r.isMarket && market > 0;
                      const delta = showDelta ? r.price - market : 0;
                      const deltaPct = showDelta ? (delta / market) * 100 : 0;
                      const above = delta > 0;
                      const deltaColour = Math.abs(delta) < 0.5 ? "#a8a29e" : (above ? "#fb7185" : "#6ee7b7");
                      const deltaStr = showDelta
                        ? `${above ? "+" : ""}${curShort(delta)} ${above ? "+" : ""}${deltaPct.toFixed(1)}%`
                        : t("ns.chart.baseline");
                      return (
                        <g key={ri}>
                          <circle cx={tipX + 10} cy={tipY + 26 + ri * rowH + 2} r="3" fill={r.colour} />
                          <text x={tipX + 19} y={tipY + 30 + ri * rowH} fontSize="9.5"
                                fontWeight={r.hero ? "800" : "600"} fill={r.hero ? "#ddd6fe" : "#e7e5e4"}>
                            {r.label.length > 17 ? r.label.slice(0, 16) + "…" : r.label}
                          </text>
                          <text x={tipX + tipW - 78} y={tipY + 30 + ri * rowH} fontSize="9.5"
                                fontWeight="800" fill={r.colour} textAnchor="end">
                            {curShort(r.price)}
                          </text>
                          <text x={tipX + tipW - 8} y={tipY + 30 + ri * rowH} fontSize="8.5"
                                fontWeight="700" fill={r.isMarket ? "#a8a29e" : deltaColour} textAnchor="end"
                                fontStyle={r.isMarket ? "italic" : "normal"}>
                            {deltaStr}
                          </text>
                        </g>
                      );
                    })}
                  </g>
                );
              })()}
              {/* Date labels */}
              {snapshots.map((s, i) => {
                if (!s?.date) return null;
                const dt = new Date(s.date + "T00:00:00");
                const prev = i > 0 ? new Date(snapshots[i-1].date + "T00:00:00") : null;
                const isMonthStart = !prev || prev.getMonth() !== dt.getMonth();
                const step = snapshots.length > 30 ? 3 : 1;
                if (i % step !== 0 && !isMonthStart) return null;
                return (
                  <g key={`xd${i}`}>
                    <text x={chart.sx(i)} y={chart.H - 12} textAnchor="middle" fontSize="7" fill={isMonthStart ? "#ffffff" : "#9ca3af"} fontWeight={isMonthStart ? "700" : "500"}>{dt.getDate()}</text>
                    {isMonthStart && <text x={chart.sx(i)} y={chart.H - 2} textAnchor="middle" fontSize="8" fill="#10b981" fontWeight="800">{dt.toLocaleDateString("en",{month:"short"})}</text>}
                  </g>
                );
              })}
            </svg>
          </div>
          </div>
        </div>
      )}
      {propertyId && propertyId !== "all" && snapshots.length > 0 && (
        <GapAnalyzerWidget snapshots={snapshots} propertyId={propertyId} cityHint={(summary && summary.last_location) || location} />
      )}

      {/* Competitive Pricing Rule */}
      {propertyId && propertyId !== "all" && snapshots.length > 0 && (
        <CompetitivePricingPanel propertyId={propertyId} />
      )}
      {propertyId === "all" && snapshots.length > 0 && (
        <div className="bg-violet-500/5 border border-violet-500/30 rounded-2xl p-4 flex items-start gap-3" data-testid="cp-all-branches-hint">
          <div className="w-9 h-9 rounded-lg bg-violet-500/20 flex items-center justify-center flex-shrink-0">
            <PoundSterling className="w-4 h-4 text-violet-400" />
          </div>
          <div>
            <h4 className="text-sm font-black text-violet-300">{t("ns.rule.title")}</h4>
            <p className="text-xs text-stone-400 mt-1">{t("ns.rule.all_branches_hint")}</p>
          </div>
        </div>
      )}

      {/* Snapshots table */}
      {snapshots.length > 0 && (
        <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-5" data-testid="geo-snapshots">
          <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
            <div className="flex items-center gap-2">
              <Building2 className="w-4 h-4 text-emerald-400" />
              <h3 className="text-sm font-bold text-stone-100">{t("ns.supply.title", { days })}</h3>
            </div>
            {top3Changes.length > 0 && (
              <div className="flex flex-wrap items-center gap-2" data-testid="top3-changes">
                <span className="text-[10px] text-stone-400 uppercase tracking-widest font-bold flex items-center gap-1">
                  <span className="text-amber-400">🔥</span> {t("ns.supply.top3")}
                </span>
                {top3Changes.map((t, i) => {
                  const up = t.pct > 0;
                  return (
                    <button
                      key={t.date}
                      onClick={() => scrollToDate(t.date)}
                      data-testid={`top3-pill-${i}`}
                      className={`group flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold transition-all border ${
                        up
                          ? "bg-rose-500/15 border-rose-500/40 text-rose-200 hover:bg-rose-500/25 hover:border-rose-400"
                          : "bg-emerald-500/15 border-emerald-500/40 text-emerald-200 hover:bg-emerald-500/25 hover:border-emerald-400"
                      }`}
                      title={`£${Math.round(t.prevPrice)} → £${Math.round(t.price)}`}
                    >
                      <span className="text-stone-300 tabular-nums">{t.date.slice(5)}</span>
                      <span>{up ? "▲" : "▼"}{Math.abs(t.pct).toFixed(1)}%</span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
          <div className="overflow-x-auto rounded-xl border border-stone-800">
            <table className="w-full text-xs">
              <thead className="bg-stone-950/80">
                <tr className="text-[11px] text-stone-100 border-b-2 border-emerald-500/40">
                  <th className="text-left py-3 pl-3 pr-2 font-bold tracking-wide">
                    <div className="flex flex-col leading-tight">
                      <span className="text-emerald-300 uppercase text-[10px] tracking-widest">Tarih</span>
                      <span className="text-[9px] text-stone-400 font-normal normal-case">Check-in günü</span>
                    </div>
                  </th>
                  <th className="text-right px-2 font-bold">
                    <div className="flex flex-col leading-tight items-end">
                      <span className="text-emerald-300 uppercase text-[10px] tracking-widest">Bölge</span>
                      <span className="text-[9px] text-stone-400 font-normal normal-case">Tarama lokasyonu</span>
                    </div>
                  </th>
                  <th className="text-right px-2 font-bold">
                    <div className="flex flex-col leading-tight items-end">
                      <span className="text-emerald-300 uppercase text-[10px] tracking-widest">Otel · Kaynak</span>
                      <span className="text-[9px] text-stone-400 font-normal normal-case">Toplam rakip · veri kaynağı</span>
                    </div>
                  </th>
                  <th className="text-right px-2 font-bold">
                    <div className="flex flex-col leading-tight items-end">
                      <span className="text-emerald-300 uppercase text-[10px] tracking-widest">Doluluk %</span>
                      <span className="text-[9px] text-stone-400 font-normal normal-case">Rezerve olan oran</span>
                    </div>
                  </th>
                  <th className="text-right px-2 font-bold">
                    <div className="flex flex-col leading-tight items-end">
                      <span className="text-amber-300 uppercase text-[10px] tracking-widest">Ort. Fiyat</span>
                      <span className="text-[9px] text-stone-400 font-normal normal-case">Rakip ortalaması</span>
                    </div>
                  </th>
                  <th className="text-right px-2 font-bold">
                    <div className="flex flex-col leading-tight items-end">
                      <span className="text-violet-300 uppercase text-[10px] tracking-widest">Δ Değişim</span>
                      <span className="text-[9px] text-stone-400 font-normal normal-case">Bir önceki güne göre</span>
                    </div>
                  </th>
                  <th className="text-right px-2 font-bold">
                    <div className="flex flex-col leading-tight items-end">
                      <span className="text-emerald-300 uppercase text-[10px] tracking-widest">Min {currency.info.symbol.trim()}</span>
                      <span className="text-[9px] text-stone-400 font-normal normal-case">En ucuz oda</span>
                    </div>
                  </th>
                  <th className="text-right pr-3 pl-2 font-bold">
                    <div className="flex flex-col leading-tight items-end">
                      <span className="text-rose-300 uppercase text-[10px] tracking-widest">Max {currency.info.symbol.trim()}</span>
                      <span className="text-[9px] text-stone-400 font-normal normal-case">En pahalı oda</span>
                    </div>
                  </th>
                </tr>
              </thead>
              <tbody>
                {snapshots.map((s, idx) => {
                  const hot = (s.unavailable_pct || 0) >= 80;
                  const prev = idx > 0 ? snapshots[idx - 1] : null;
                  const prevPrice = prev && prev.avg_price > 0 ? prev.avg_price : null;
                  const delta = prevPrice && s.avg_price > 0
                    ? ((s.avg_price - prevPrice) / prevPrice) * 100 : null;
                  const up = delta !== null && delta > 0;
                  return (
                    <tr key={s.date}
                      data-row-date={s.date}
                      className={`border-b border-stone-800/40 transition-all duration-500 ${
                        highlightDate === s.date
                          ? "bg-amber-400/20 ring-2 ring-amber-400 ring-inset"
                          : "hover:bg-emerald-500/5"
                      }`}>
                      <td className="py-2.5 pl-3 pr-2 text-stone-100 font-semibold tabular-nums">{s.date}</td>
                      <td className="text-right px-2 text-stone-400 truncate max-w-[120px]">{s.location}</td>
                      <td className="text-right px-2 tabular-nums">
                        <div className="flex items-center justify-end gap-1.5">
                          <span className="text-stone-100 font-semibold">{s.total_properties || "—"}</span>
                          <SourceBadge source={s.total_source} />
                        </div>
                      </td>
                      <td className="text-right px-2 tabular-nums">
                        <span className={`inline-block px-2 py-0.5 rounded font-bold ${hot ? "bg-rose-500/20 text-rose-200" : (s.unavailable_pct||0) >= 60 ? "bg-amber-500/20 text-amber-200" : "bg-emerald-500/15 text-emerald-200"}`}>
                          {s.unavailable_pct}%
                        </span>
                      </td>
                      <td className="text-right px-2 text-amber-300 font-bold tabular-nums">{s.avg_price ? cur(s.avg_price) : "—"}</td>
                      <td className="text-right px-2 tabular-nums">
                        {delta === null ? <span className="text-stone-600">—</span> : (
                          <span className={`font-bold ${Math.abs(delta) < 2 ? "text-stone-400" : up ? "text-rose-300" : "text-emerald-300"}`}>
                            {up ? "▲" : delta < 0 ? "▼" : ""}{delta.toFixed(1)}%
                          </span>
                        )}
                      </td>
                      <td className="text-right px-2 text-stone-300 tabular-nums">{s.min_price ? cur(s.min_price) : "—"}</td>
                      <td className="text-right pr-3 pl-2 text-stone-300 tabular-nums">{s.max_price ? cur(s.max_price) : "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {snapshots.length === 0 && !lastResult && (
        <div className="text-center py-10 bg-stone-900/40 border border-dashed border-stone-700 rounded-xl">
          <Clock className="w-10 h-10 text-stone-600 mx-auto mb-2" />
          <p className="text-sm text-stone-400">No neighborhood scans yet</p>
          <p className="text-xs text-stone-500 mt-1">Enter a postcode above and hit Scan to see supply & price data around your target area.</p>
        </div>
      )}

      {/* Fix Branch Location dialog */}
      {fixOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" data-testid="fix-location-dialog">
          <div className="bg-stone-950 border border-amber-500/40 rounded-2xl max-w-md w-full p-5 space-y-4 shadow-2xl">
            <div>
              <h3 className="text-base font-black text-amber-300 flex items-center gap-2">
                <MapPin className="w-4 h-4" /> Fix Branch Location
              </h3>
              <p className="text-[11px] text-stone-400 mt-1 leading-relaxed">
                Bu şubenin <b>şehir</b>, <b>currency</b> ve <b>postkod</b> ayarlarını düzeltir.
                Önceki (yanlış currency ile kaydedilmiş) scrap verileri temizlenir —
                bir sonraki tarama doğru currency ile çalışır.
              </p>
              <p className="text-[10px] text-stone-500 mt-1">
                Şu anki property kaydı: <span className="font-mono text-stone-300">{propInfo.city || "—"}</span> · <span className="font-mono text-stone-300">{propInfo.currency || "—"}</span>
              </p>
            </div>
            <div className="space-y-2.5">
              <div>
                <label className="block text-[10px] font-bold uppercase text-stone-400 mb-1 tracking-wider">City</label>
                <input value={fixCity} onChange={e => setFixCity(e.target.value)} placeholder="e.g. London"
                  className="w-full px-3 py-2 text-sm bg-stone-900 border border-stone-700 rounded-lg text-stone-100"
                  data-testid="fix-city-input" />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-[10px] font-bold uppercase text-stone-400 mb-1 tracking-wider">Currency (ISO)</label>
                  <select value={fixCurrency} onChange={e => setFixCurrency(e.target.value)}
                    className="w-full px-3 py-2 text-sm bg-stone-900 border border-stone-700 rounded-lg text-stone-100"
                    data-testid="fix-currency-input">
                    <option value="">—</option>
                    {["GBP","EUR","USD","CHF","TRY","JPY","CAD","AUD","SEK","DKK","NOK","AED"].map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-[10px] font-bold uppercase text-stone-400 mb-1 tracking-wider">Postcode <span className="opacity-50 font-normal">(optional)</span></label>
                  <input value={fixPostcode} onChange={e => setFixPostcode(e.target.value)} placeholder="e.g. E1 6AN"
                    className="w-full px-3 py-2 text-sm bg-stone-900 border border-stone-700 rounded-lg text-stone-100"
                    data-testid="fix-postcode-input" />
                </div>
              </div>
            </div>
            <div className="flex items-center justify-end gap-2 pt-2 border-t border-stone-800">
              <button onClick={() => setFixOpen(false)}
                className="px-3 py-1.5 text-xs rounded-lg text-stone-400 hover:bg-stone-900" data-testid="fix-cancel-btn">
                Cancel
              </button>
              <button onClick={applyLocationFix} disabled={fixing || !fixCity.trim() || !fixCurrency.trim()}
                className="px-4 py-1.5 text-xs font-bold rounded-lg bg-amber-500 hover:bg-amber-400 text-black disabled:opacity-50 flex items-center gap-1.5"
                data-testid="fix-apply-btn">
                {fixing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                {fixing ? "Fixing…" : "Fix & Clear Stale"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function CompareCard({ label, us, them, delta, kind, hint }) {
  const isPrice = kind === "price";
  const isOcc = kind === "occupancy";
  const goodWhenAbove = isOcc;   // higher occupancy = better ; lower price vs market = better
  const isAbove = delta > 0;
  const positiveOutcome = isAbove === goodWhenAbove;
  const deltaColor = Math.abs(delta) < 1
    ? "text-stone-400"
    : positiveOutcome ? "text-emerald-300" : "text-rose-300";
  return (
    <div className="bg-stone-950/60 border border-stone-800 rounded-lg p-2.5">
      <p className="text-[9px] font-bold uppercase tracking-widest text-stone-400">{label}</p>
      <div className="flex items-baseline gap-2 mt-1">
        <span className="text-base font-black text-cyan-300 tabular-nums">{us}</span>
        <span className="text-[9px] text-stone-500">biz</span>
      </div>
      <div className="flex items-baseline gap-2">
        <span className="text-xs font-bold text-amber-300 tabular-nums">{them}</span>
        <span className="text-[9px] text-stone-500">pazar</span>
      </div>
      {kind !== "count" && (
        <p className={`text-[10px] font-bold mt-0.5 ${deltaColor}`}>
          {isAbove ? "▲" : "▼"} {Math.abs(delta).toFixed(1)}{isPrice ? "%" : " puan"}
        </p>
      )}
      {hint && <p className="text-[9px] text-stone-500 mt-0.5">{hint}</p>}
    </div>
  );
}

function KPI({ label, value, tone, icon: Icon, testId }) {
  const tones = {
    emerald: "border-emerald-500/30 text-emerald-300",
    amber: "border-amber-500/30 text-amber-300",
    rose: "border-rose-500/30 text-rose-300",
    slate: "border-stone-700 text-stone-200",
  };
  return (
    <div className={`bg-stone-900/60 border ${tones[tone] || tones.slate} rounded-xl p-3 relative overflow-hidden`} data-testid={testId}>
      {Icon && <Icon className="absolute -right-2 -bottom-2 w-10 h-10 opacity-10" />}
      <p className="text-[9px] font-bold uppercase tracking-widest opacity-70">{label}</p>
      <p className="text-xl font-black tabular-nums mt-1">{value}</p>
    </div>
  );
}

function SourceBadge({ source }) {
  const map = {
    "booking-cards":  { label: "Booking",  tip: "Booking.com property-card sayımı (en güvenilir)",          cls: "bg-blue-500/15 text-blue-200 border-blue-500/40" },
    "booking-pager":  { label: "Booking",  tip: "Booking.com 'Showing X of Y' sayfalama sayımı",             cls: "bg-blue-500/15 text-blue-200 border-blue-500/40" },
    "booking-header": { label: "Booking*", tip: "Booking.com toplam başlık — geo filtresiz (tahmini üst sınır)", cls: "bg-blue-500/10 text-blue-300/70 border-blue-500/30" },
    "google-places":  { label: "Google",   tip: "Google Places Nearby Search (type=lodging)",                cls: "bg-amber-500/15 text-amber-200 border-amber-500/40" },
    "osm":            { label: "OSM",      tip: "OpenStreetMap Overpass — açık kaynak, ücretsiz",           cls: "bg-emerald-500/15 text-emerald-200 border-emerald-500/40" },
    "heuristic":      { label: "Tahmini",  tip: "Yarıçap × yoğunluk heuristic (veri kaynağı yanıt vermedi)", cls: "bg-stone-600/20 text-stone-300 border-stone-600/40" },
    "city-baseline":  { label: "Şehir",    tip: "Şehir geneli sabit baseline",                              cls: "bg-violet-500/15 text-violet-200 border-violet-500/40" },
    "aggregated":     { label: "Toplam",   tip: "Tüm şubelerin ortalaması",                                 cls: "bg-teal-500/15 text-teal-200 border-teal-500/40" },
  };
  const info = map[source] || { label: "—", tip: "Kaynak bilinmiyor", cls: "bg-stone-700/40 text-stone-400 border-stone-700" };
  return (
    <span
      className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[9px] font-bold border ${info.cls}`}
      title={info.tip}
      data-testid={`src-badge-${source || "unknown"}`}
    >
      {info.label}
    </span>
  );
}
