/**
 * Our Booking.com — Live Card
 *
 * Surfaces the fresh Booking.com scrape of OUR hotel so the user can visually
 * confirm that prices and review score are being read directly from the OTA
 * page — the foundation for genuine "Biz vs Pazar" benchmarking.
 */
import { useState, useEffect, useMemo, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ExternalLink, RefreshCw, Star, Banknote, MapPin, Link2, Save, Play, Eye,
} from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/i18n";
import useLivePolling, { LiveBadge } from "../../hooks/useLivePolling";
import { makeCurrencyFormatter } from "../../lib/currency";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const relTime = (iso) => {
  if (!iso) return "never";
  const diff = (Date.now() - new Date(iso).getTime()) / 60000;
  if (diff < 1) return "just now";
  if (diff < 60) return `${Math.floor(diff)}m ago`;
  if (diff < 1440) return `${Math.floor(diff / 60)}h ago`;
  return `${Math.floor(diff / 1440)}d ago`;
};

export default function OurBookingLiveCard({ propertyId }) {
  const { t } = useTranslation();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [urlDraft, setUrlDraft] = useState("");
  const [scraping, setScraping] = useState(false);
  const [validating, setValidating] = useState(false);
  const [validation, setValidation] = useState(null); // {ok, hotel_id, hotel_name, sample_price, currency, error}

  const load = useCallback(() => {
    setLoading(true);
    axios.get(`${API}/revenue/market-robot/${propertyId}/our-booking`)
      .then(r => { setData(r.data); setUrlDraft(r.data.booking_url || ""); })
      .finally(() => setLoading(false));
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);

  // 🏨 Branch hygiene — reset per-branch state so user never sees a previous branch's
  // URL draft, validation badge, or edit-mode dialog when switching hotels.
  useEffect(() => {
    setData(null);
    setUrlDraft("");
    setValidation(null);
    setEditing(false);
    setScraping(false);
    setValidating(false);
  }, [propertyId]);

  // ⚡ Live refresh — shared hook
  useLivePolling(load, { intervalMs: 45000, busy: scraping });

  const cur = useMemo(() => makeCurrencyFormatter(data?.currency || data?.city || ""), [data]);

  const testUrl = async () => {
    if (!urlDraft) { toast.error("URL boş"); return; }
    setValidating(true);
    setValidation(null);
    try {
      const { data: v } = await axios.post(`${API}/revenue/market-robot/validate-booking-url`, {
        booking_url: urlDraft,
        currency: data?.currency || "",
      });
      setValidation(v);
      if (v.ok) toast.success(`${v.hotel_name} · ${v.currency} ${v.sample_price}`);
      else toast.error(`Doğrulanamadı: ${v.error || "bilinmeyen"}`);
    } catch {
      toast.error("Validator error");
    }
    setValidating(false);
  };

  const save = async () => {
    try {
      const { data: res } = await axios.put(`${API}/revenue/market-robot/${propertyId}/our-booking`, { booking_url: urlDraft });
      const v = res?.validation;
      if (v && !v.ok && urlDraft) {
        toast.warning(`URL kaydedildi ama doğrulanamadı: ${v.error || "bilinmeyen"}`);
      } else {
        toast.success("Booking URL saved");
      }
      setEditing(false);
      setValidation(null);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to save URL");
    }
  };

  const triggerScrape = async () => {
    setScraping(true);
    try {
      await axios.post(`${API}/revenue/market-robot/${propertyId}/our-booking/scan`);
      toast.success("Scraping started — live prices will appear in 60-90 seconds");
      // Poll for completion (3 attempts over 2 minutes)
      for (let i = 0; i < 6; i++) {
        await new Promise(r => setTimeout(r, 20000));
        const fresh = await axios.get(`${API}/revenue/market-robot/${propertyId}/our-booking`);
        if (fresh.data?.booking_data?.snapshot_at !== data?.booking_data?.snapshot_at) {
          setData(fresh.data);
          break;
        }
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Scrape failed");
    } finally { setScraping(false); }
  };

  if (loading) {
    return <div className="bg-white border border-stone-200 rounded-2xl p-5 text-sm text-stone-400">Loading…</div>;
  }

  // "All Branches" mode or no property record — render an empty-state hint instead of crashing
  if (!data || data.all_branches_mode || propertyId === "all") {
    return (
      <div className="bg-white border border-stone-200 rounded-2xl p-5 text-sm text-stone-500" data-testid="our-booking-card-all">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-stone-100 text-stone-400 flex items-center justify-center">
            <Link2 className="w-5 h-5" />
          </div>
          <div>
            <div className="font-bold text-stone-700">Our Booking.com Live</div>
            <div className="text-xs text-stone-400 mt-0.5">
              Bu kart şube-özel — yukarıdan tek bir şube seçin (All Branches değil).
            </div>
          </div>
        </div>
      </div>
    );
  }

  const bd = data?.booking_data;
  const hasUrl = !!data?.booking_url;
  const hasData = !!bd;

  return (
    <div className="bg-gradient-to-br from-sky-50 via-indigo-50 to-white border border-indigo-200 rounded-2xl p-5 shadow-sm" data-testid="our-booking-card">
      <div className="flex items-start gap-3 mb-3">
        <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-indigo-500 to-blue-600 text-white flex items-center justify-center flex-shrink-0 shadow">
          <Link2 className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-base font-black text-stone-900">Our Booking.com Live</h3>
            {hasData && (
              <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 text-[10px] font-bold uppercase tracking-wider flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                LIVE · {relTime(bd.snapshot_at)}
              </span>
            )}
          </div>
          <p className="text-[11px] text-stone-500 mt-0.5">
            Direct scrape of <b className="text-stone-800">{data.name || "your property"}</b> for apples-to-apples Biz vs Pazar comparisons.
          </p>
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          {hasUrl && (
            <a href={data.booking_url} target="_blank" rel="noopener noreferrer"
               className="px-2.5 py-1.5 rounded-lg bg-white border border-stone-200 hover:bg-stone-50 text-stone-600 text-xs font-medium inline-flex items-center gap-1"
               data-testid="our-booking-view">
              <Eye className="w-3 h-3" /> View
            </a>
          )}
          <button onClick={() => setEditing(true)}
                  className="px-2.5 py-1.5 rounded-lg bg-white border border-stone-200 hover:bg-stone-50 text-stone-600 text-xs font-medium inline-flex items-center gap-1"
                  data-testid="our-booking-edit">
            <MapPin className="w-3 h-3" /> {hasUrl ? "Change" : "Set URL"}
          </button>
          <button onClick={triggerScrape} disabled={scraping || !hasUrl}
                  className="px-2.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-xs font-bold inline-flex items-center gap-1"
                  data-testid="our-booking-scan">
            {scraping ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
            {scraping ? "Scraping…" : "Scan Now"}
          </button>
        </div>
      </div>

      {!hasUrl && (
        <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 text-[12px] text-amber-900" data-testid="our-booking-no-url">
          No Booking.com URL set for this property. Click <b>Set URL</b> to link the hotel page so competitor overlays become real vs-OTA comparisons.
        </div>
      )}

      {hasUrl && !hasData && (
        <div className="p-3 rounded-lg bg-stone-50 border border-stone-200 text-[12px] text-stone-600">
          URL is set, but no scrape has run yet. Click <b>Scan Now</b> — next auto-scan runs every 3 hours.
        </div>
      )}

      {hasData && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="bg-white/80 backdrop-blur border border-stone-200 rounded-xl p-3" data-testid="our-booking-avg">
            <div className="flex items-center gap-1.5 text-[9px] font-bold uppercase tracking-wider text-stone-400">
              <Banknote className="w-3 h-3" /> 14-day avg
            </div>
            <div className="mt-1 text-xl font-black text-stone-900 tabular-nums">{cur.format(bd.avg_price || 0)}</div>
            <div className="text-[10px] text-stone-500">{bd.days_with_price || 0}/{bd.days_scraped || 0} days with data</div>
          </div>
          <div className="bg-white/80 backdrop-blur border border-stone-200 rounded-xl p-3">
            <div className="text-[9px] font-bold uppercase tracking-wider text-stone-400">Range</div>
            <div className="mt-1 flex items-baseline gap-1.5">
              <span className="text-sm font-black text-emerald-600 tabular-nums">{cur.format(bd.min_price || 0)}</span>
              <span className="text-stone-300">→</span>
              <span className="text-sm font-black text-rose-600 tabular-nums">{cur.format(bd.max_price || 0)}</span>
            </div>
            <div className="text-[10px] text-stone-500">Low / High across 14 days</div>
          </div>
          <div className="bg-white/80 backdrop-blur border border-stone-200 rounded-xl p-3">
            <div className="flex items-center gap-1.5 text-[9px] font-bold uppercase tracking-wider text-stone-400">
              <Star className="w-3 h-3" /> Review Score
            </div>
            <div className="mt-1 text-xl font-black text-stone-900 tabular-nums">
              {bd.review_score ? `${bd.review_score.toFixed(1)}` : "—"}
              <span className="text-xs text-stone-400 font-normal"> /10</span>
            </div>
            <div className="text-[10px] text-stone-500">Live from Booking.com</div>
          </div>
          <div className="bg-white/80 backdrop-blur border border-stone-200 rounded-xl p-3">
            <div className="text-[9px] font-bold uppercase tracking-wider text-stone-400">Next 7 days</div>
            <div className="mt-1 text-[10px] text-stone-600 space-y-0.5">
              {(bd.daily_prices || []).slice(0, 4).map((dp, i) => (
                <div key={i} className="flex justify-between">
                  <span className="text-stone-400">{dp.date.slice(5)}</span>
                  <span className={`font-bold tabular-nums ${dp.lowest_price ? "text-stone-900" : "text-stone-300"}`}>
                    {dp.lowest_price ? cur.format(dp.lowest_price) : "—"}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Edit URL dialog */}
      <Dialog open={editing} onOpenChange={setEditing}>
        <DialogContent className="max-w-lg" data-testid="our-booking-edit-dialog">
          <DialogHeader>
            <DialogTitle className="text-base font-black flex items-center gap-2">
              <ExternalLink className="w-4 h-4 text-indigo-600" />
              Our Booking.com Listing
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3 text-sm">
            <p className="text-xs text-stone-500">
              Paste the exact Booking.com URL of your hotel. Auto-scraper runs every 3 hours.
            </p>
            <div>
              <label className="text-[10px] font-bold uppercase tracking-wider text-stone-500">Booking URL</label>
              <Input value={urlDraft} onChange={(e) => { setUrlDraft(e.target.value); setValidation(null); }} autoFocus
                     className="mt-1 font-mono text-xs"
                     placeholder="https://www.booking.com/hotel/ch/your-hotel.en-gb.html"
                     data-testid="our-booking-url-input" />
              {urlDraft && !urlDraft.toLowerCase().includes("booking.com") && (
                <p className="mt-1 text-[10px] text-rose-600">URL must be a booking.com link</p>
              )}
            </div>
            {validation && (
              <div
                className={`rounded-lg border p-2.5 text-[11px] ${
                  validation.ok
                    ? "bg-emerald-50 border-emerald-200 text-emerald-800"
                    : "bg-rose-50 border-rose-200 text-rose-700"
                }`}
                data-testid="our-booking-validation"
              >
                {validation.ok ? (
                  <>
                    <div className="font-bold">✓ {validation.hotel_name}</div>
                    <div className="mt-0.5 text-emerald-600">
                      Booking ID <span className="font-mono">{validation.hotel_id}</span> · Örnek fiyat <span className="font-bold">{validation.currency} {validation.sample_price}</span>
                    </div>
                  </>
                ) : (
                  <div>✗ {validation.error || "Bilinmeyen hata"}</div>
                )}
              </div>
            )}
          </div>
          <div className="flex items-center justify-between gap-2 mt-4 pt-3 border-t">
            <Button variant="outline" onClick={testUrl} disabled={validating || !urlDraft}
                    data-testid="our-booking-test-url">
              {validating ? <RefreshCw className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Eye className="w-3.5 h-3.5 mr-1.5" />}
              {validating ? "Testing…" : "Test URL"}
            </Button>
            <div className="flex items-center gap-2">
              <Button variant="outline" onClick={() => { setEditing(false); setValidation(null); }}>Cancel</Button>
              <Button onClick={save} disabled={urlDraft && !urlDraft.toLowerCase().includes("booking.com")}
                      className="bg-indigo-600 hover:bg-indigo-700 text-white"
                      data-testid="our-booking-save">
                <Save className="w-3.5 h-3.5 mr-1.5" /> Save
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
