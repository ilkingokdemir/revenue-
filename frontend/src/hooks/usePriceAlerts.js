/**
 * usePriceAlerts — Emits Sonner toasts when live-polled market data shifts
 * meaningfully, so the revenue manager never misses a sudden market move
 * even if they're not staring at the chart.
 *
 * Trigger conditions (conservative by design — this is an attention system,
 * not a stream of noise):
 *   1. Market avg drops OR rises ≥10% vs the reading we stored on mount
 *      (debounced so it fires at most once per direction per mount).
 *   2. Market avg crosses OUR avg rate from above (i.e. we just became the
 *      most expensive option) — a "price war" warning.
 *
 * The alerts are scoped by `propertyId + scope` so each branch + chart gets
 * an independent history. Ideas deliberately left out:
 *   - Competitor-specific alerts (they live in the MarketRobot panel already).
 *   - Push notifications (out of scope — we have Sonner toasts).
 *
 * Usage:
 *   usePriceAlerts({
 *     propertyId,
 *     scope: "neighborhood",          // free-text id, unique per mount
 *     marketAvgPrice: summary?.avg_price,
 *     ourAvgRate:     ourSummary?.avg_rate,
 *     currency:       summary?.property_currency || "GBP",
 *   });
 */
import { useEffect, useRef } from "react";
import { toast } from "sonner";

const DEFAULT_THRESHOLD = 0.10;  // 10%

export default function usePriceAlerts({
  propertyId,
  scope = "default",
  marketAvgPrice,
  ourAvgRate,
  currency = "GBP",
  threshold = DEFAULT_THRESHOLD,
  enabled = true,
}) {
  const baselineRef  = useRef(null);  // { marketAvg, ourAvg } on first successful read
  const lastDirRef   = useRef(null);  // "up" | "down" — last direction toasted, debounces
  const warRef       = useRef(false); // whether we've already warned about price war

  useEffect(() => {
    if (!enabled) return;
    if (typeof marketAvgPrice !== "number" || marketAvgPrice <= 0) return;

    // Establish baseline on first good read
    if (baselineRef.current === null) {
      baselineRef.current = { marketAvg: marketAvgPrice, ourAvg: ourAvgRate || null };
      return;
    }
    const base = baselineRef.current;
    const pct  = (marketAvgPrice - base.marketAvg) / base.marketAvg;
    const dir  = pct >= threshold ? "up" : pct <= -threshold ? "down" : null;

    if (dir && dir !== lastDirRef.current) {
      lastDirRef.current = dir;
      const pctDisp = Math.round(Math.abs(pct) * 100);
      if (dir === "up") {
        toast.info(`📈 Pazar ortalaması %${pctDisp} yükseldi (${currency} ${base.marketAvg.toFixed(0)} → ${currency} ${marketAvgPrice.toFixed(0)})`, {
          id: `price-alert-up-${propertyId}-${scope}`,
          duration: 7000,
        });
      } else {
        toast.warning(`📉 Pazar ortalaması %${pctDisp} düştü (${currency} ${base.marketAvg.toFixed(0)} → ${currency} ${marketAvgPrice.toFixed(0)}) — fiyatları gözden geçirin`, {
          id: `price-alert-down-${propertyId}-${scope}`,
          duration: 9000,
        });
      }
      // Re-anchor baseline so the next ±10% move is measured from HERE
      baselineRef.current = { marketAvg: marketAvgPrice, ourAvg: ourAvgRate || null };
    }

    // Price-war check: our rate just overtook the market
    if (typeof ourAvgRate === "number" && ourAvgRate > 0) {
      if (!warRef.current && ourAvgRate > marketAvgPrice * 1.05) {
        warRef.current = true;
        toast.warning(
          `⚠️ Biz pazar ortalamasının %${Math.round(((ourAvgRate - marketAvgPrice) / marketAvgPrice) * 100)} üstündeyiz (${currency} ${ourAvgRate.toFixed(0)} vs ${currency} ${marketAvgPrice.toFixed(0)}). Rezervasyon kaçırma riski.`,
          { id: `price-war-${propertyId}-${scope}`, duration: 12000 },
        );
      } else if (warRef.current && ourAvgRate < marketAvgPrice * 1.02) {
        warRef.current = false;
      }
    }
  }, [marketAvgPrice, ourAvgRate, currency, propertyId, scope, threshold, enabled]);
}
