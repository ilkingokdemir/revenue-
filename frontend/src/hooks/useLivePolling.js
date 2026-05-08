/**
 * useLivePolling — Dashboard-wide live refresh primitive.
 *
 * Applies the same visibility-aware polling contract used by NeighborhoodScanPanel
 * to every chart/analytics card in the app:
 *   • Re-runs the loader every `intervalMs` ms while the tab is VISIBLE.
 *   • Force-refreshes instantly when the tab regains focus / becomes visible,
 *     so swapping between apps never leaves a stale chart on screen.
 *   • Skips a tick while `busy` is true (e.g. a user-initiated scrape is in
 *     flight) to avoid UI flicker.
 *   • Respects `enabled=false` so parents can pause polling (onboarding modals,
 *     hidden tabs, "all branches" sentinel pages).
 *
 * Usage:
 *   const load = useCallback(async () => { ... }, [propertyId]);
 *   useLivePolling(load, { intervalMs: 45000 });
 */
import { useEffect, useRef } from "react";

export function useLivePolling(loader, { intervalMs = 45000, enabled = true, busy = false } = {}) {
  const busyRef = useRef(busy);
  const loaderRef = useRef(loader);

  // Keep refs in sync without re-registering the interval every render.
  useEffect(() => { busyRef.current = busy; }, [busy]);
  useEffect(() => { loaderRef.current = loader; }, [loader]);

  useEffect(() => {
    if (!enabled) return undefined;
    let cancelled = false;
    let timer = null;

    const safeLoad = async () => {
      if (cancelled) return;
      if (busyRef.current) return;
      if (document.visibilityState !== "visible") return;
      try { await loaderRef.current(); } catch { /* silent — network flakes ok */ }
    };

    const tick = async () => {
      await safeLoad();
      if (!cancelled) timer = setTimeout(tick, intervalMs);
    };

    timer = setTimeout(tick, intervalMs);

    const onFocus = () => { safeLoad(); };
    const onVisible = () => { if (document.visibilityState === "visible") safeLoad(); };
    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onVisible);

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [intervalMs, enabled]);
}

/**
 * LiveBadge — tiny visual indicator users glance at to know "yeah this is live".
 * Pulsing coloured dot + interval label. Drop-in next to any chart title.
 *
 * Example:  <h2>Revenue Forecast <LiveBadge seconds={60} /></h2>
 */
export function LiveBadge({ seconds = 45, color = "emerald", title }) {
  const palette = {
    emerald: "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
    cyan:    "text-cyan-400 bg-cyan-500/10 border-cyan-500/30",
    amber:   "text-amber-400 bg-amber-500/10 border-amber-500/30",
    rose:    "text-rose-400 bg-rose-500/10 border-rose-500/30",
    violet:  "text-violet-400 bg-violet-500/10 border-violet-500/30",
  }[color] || "text-emerald-400 bg-emerald-500/10 border-emerald-500/30";
  const dotColor = {
    emerald: "bg-emerald-400",
    cyan:    "bg-cyan-400",
    amber:   "bg-amber-400",
    rose:    "bg-rose-400",
    violet:  "bg-violet-400",
  }[color] || "bg-emerald-400";
  return (
    <span
      className={`inline-flex items-center gap-1 text-[9px] font-bold uppercase tracking-wider rounded-full border px-1.5 py-0.5 ${palette}`}
      title={title || `Chart auto-updates every ${seconds}s`}
      data-testid="live-badge"
    >
      <span className={`w-1.5 h-1.5 rounded-full ${dotColor} animate-pulse`} />
      Live · {seconds}s
    </span>
  );
}

export default useLivePolling;
