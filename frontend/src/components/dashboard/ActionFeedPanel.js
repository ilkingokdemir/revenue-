/**
 * ActionFeedPanel — Global right-side drawer surfacing ALL pricing/market events
 * from the Market Robot in one chronological stream. Mounted at the dashboard
 * shell so it's visible everywhere; the revenue manager opens it in the morning
 * and sees "what happened overnight" in 30 seconds.
 *
 * Uses the same useLivePolling hook as every other chart, so the feed stays
 * fresh without manual refresh. Unread count pulses on the trigger button.
 */
import { useState, useCallback, useMemo } from "react";
import axios from "axios";
import { Bell, X, TrendingUp, TrendingDown, Zap, AlertTriangle, UserCog, Radio, ChevronRight } from "lucide-react";
import useLivePolling from "../../hooks/useLivePolling";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const SEEN_KEY = (pid) => `action-feed-last-seen-${pid}`;

const TYPE_STYLES = {
  auto_pricing:     { Icon: Zap,             color: "violet",   label: "Auto-Pricing" },
  competitor_move:  { Icon: TrendingUp,      color: "cyan",     label: "Competitor" },
  manual_override:  { Icon: UserCog,         color: "amber",    label: "Manual" },
  scanner_error:    { Icon: AlertTriangle,   color: "rose",     label: "Scanner" },
};
const SEV_BORDER = {
  alert: "border-rose-500/50",
  warn:  "border-amber-400/50",
  info:  "border-stone-700",
};

function formatRelative(iso) {
  if (!iso) return "";
  const diffMs = Date.now() - new Date(iso).getTime();
  const m = Math.round(diffMs / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.round(h / 24)}d ago`;
}

export default function ActionFeedPanel({ propertyId }) {
  const [open, setOpen] = useState(false);
  const [events, setEvents] = useState([]);
  const [lastSeen, setLastSeen] = useState(() => {
    try { return window.localStorage.getItem(SEEN_KEY(propertyId)) || ""; } catch { return ""; }
  });

  const load = useCallback(async () => {
    if (!propertyId || propertyId === "all") { setEvents([]); return; }
    try {
      const { data } = await axios.get(`${API}/revenue/market-robot/${propertyId}/action-feed?limit=40`);
      setEvents(data.events || []);
    } catch { /* silent */ }
  }, [propertyId]);

  useLivePolling(load, { intervalMs: 30000, enabled: !!propertyId && propertyId !== "all" });

  const unreadCount = useMemo(() => {
    if (!events.length) return 0;
    if (!lastSeen) return Math.min(events.length, 9);
    return events.filter(e => (e.timestamp || "") > lastSeen).length;
  }, [events, lastSeen]);

  const markAllRead = () => {
    const latest = events[0]?.timestamp || new Date().toISOString();
    setLastSeen(latest);
    try { window.localStorage.setItem(SEEN_KEY(propertyId), latest); } catch { /* noop */ }
  };

  const handleOpen = () => {
    setOpen(true);
    load();
    // Schedule mark-read slightly later so user sees the green dots highlight fresh items
    setTimeout(markAllRead, 1500);
  };

  if (!propertyId || propertyId === "all") return null;

  return (
    <>
      {/* Floating trigger button (bottom-right, offset from ReportIssueFAB) */}
      <button
        onClick={handleOpen}
        className="fixed bottom-5 right-5 z-40 w-12 h-12 rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 hover:from-indigo-400 hover:to-violet-500 text-white shadow-xl shadow-indigo-900/30 flex items-center justify-center transition-transform hover:scale-105"
        data-testid="action-feed-trigger"
        title="Revenue Action Feed — son pazar & otomatik fiyat hareketleri"
        style={{ bottom: "5rem" }}
      >
        <Bell className="w-5 h-5" />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 rounded-full bg-rose-500 text-white text-[10px] font-bold flex items-center justify-center animate-pulse" data-testid="action-feed-unread">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {/* Drawer */}
      {open && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm transition-opacity"
            onClick={() => setOpen(false)}
            data-testid="action-feed-backdrop"
          />
          <div
            className="fixed top-0 right-0 bottom-0 z-50 w-full sm:w-[420px] bg-stone-950 text-stone-100 border-l border-stone-800 shadow-2xl overflow-hidden flex flex-col"
            data-testid="action-feed-drawer"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-stone-800 bg-gradient-to-r from-indigo-600/15 to-violet-600/15">
              <div className="flex items-center gap-2">
                <Radio className="w-4 h-4 text-indigo-300" />
                <h2 className="font-black text-sm uppercase tracking-wide text-indigo-200">Action Feed</h2>
                <span className="inline-flex items-center gap-1 text-[9px] font-bold uppercase tracking-wider rounded-full border border-emerald-500/30 bg-emerald-500/10 text-emerald-400 px-1.5 py-0.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  Live · 30s
                </span>
              </div>
              <button onClick={() => setOpen(false)} className="text-stone-400 hover:text-white" data-testid="action-feed-close">
                <X className="w-5 h-5" />
              </button>
            </div>
            <p className="text-[11px] text-stone-400 px-5 py-2 border-b border-stone-900">
              Market Robot auto-pricing, rakip fiyat hareketleri, ve manuel değişiklikler — hepsi burada. Sağ altta kalırsanız bildirim gelir.
            </p>

            {/* Events list */}
            <div className="flex-1 overflow-y-auto" data-testid="action-feed-list">
              {events.length === 0 && (
                <div className="p-8 text-center text-xs text-stone-500">
                  <Bell className="w-8 h-8 mx-auto mb-2 text-stone-700" />
                  <div>Henüz olay yok.</div>
                  <div className="mt-1 opacity-70">Scanner çalışır çalışmaz ilk hareketler burada görünecek.</div>
                </div>
              )}
              {events.map(ev => {
                const def = TYPE_STYLES[ev.type] || TYPE_STYLES.auto_pricing;
                const isFresh = !lastSeen || (ev.timestamp || "") > lastSeen;
                const Icon = def.Icon;
                return (
                  <div
                    key={ev.id}
                    className={`px-4 py-3 border-b border-stone-900 border-l-2 ${SEV_BORDER[ev.severity] || "border-stone-700"} ${isFresh ? "bg-indigo-500/5" : ""} hover:bg-stone-900/50 transition-colors`}
                    data-testid="action-feed-event"
                  >
                    <div className="flex items-start gap-3">
                      <div className={`w-8 h-8 rounded-lg flex-shrink-0 flex items-center justify-center bg-${def.color}-500/15 text-${def.color}-300`}>
                        <Icon className="w-4 h-4" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className={`text-[9px] font-bold uppercase tracking-wider text-${def.color}-400`}>{def.label}</span>
                          {isFresh && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />}
                          <span className="text-[10px] text-stone-500 ml-auto">{formatRelative(ev.timestamp)}</span>
                        </div>
                        <div className="text-sm font-semibold text-stone-100 mt-0.5 leading-snug">{ev.title}</div>
                        {ev.detail && <div className="text-[11px] text-stone-400 mt-1 leading-relaxed">{ev.detail}</div>}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Footer */}
            {events.length > 0 && (
              <div className="px-5 py-3 border-t border-stone-800 bg-stone-950 flex items-center justify-between text-[11px] text-stone-500">
                <span>{events.length} event{events.length > 1 ? "s" : ""} · last 48h</span>
                <button onClick={markAllRead} className="flex items-center gap-1 text-indigo-400 hover:text-indigo-300 font-semibold">
                  Mark all read <ChevronRight className="w-3 h-3" />
                </button>
              </div>
            )}
          </div>
        </>
      )}
    </>
  );
}
