import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
  AlertTriangle, RefreshCw, ShieldCheck, Building2, DoorOpen,
  Calendar, Users, ChevronRight, Sparkles, Zap,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const cur = (v, ccy = "GBP") => {
  const sym = ccy === "USD" ? "$" : ccy === "EUR" ? "€" : "£";
  return `${sym}${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

const STATUS_CLS = {
  pending:    "bg-amber-100 text-amber-800 border-amber-200",
  confirmed:  "bg-indigo-100 text-indigo-800 border-indigo-200",
  checked_in: "bg-rose-100 text-rose-800 border-rose-200",
  hold:       "bg-stone-100 text-stone-700 border-stone-200",
};

const SRC_DOT = {
  "Booking.com": "bg-[#003580]", "Airbnb": "bg-[#FF5A5F]", "Expedia": "bg-[#FFC72C]",
  "Google": "bg-[#4285F4]", "Direct": "bg-emerald-600", "Web": "bg-violet-600",
  "Agoda": "bg-[#FF3B00]", "Hotelbeds": "bg-[#00A3E4]",
};

export const CollisionsPanel = ({ user, onJumpToCalendar }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data: d } = await axios.get(`${API}/operations/collisions`);
      setData(d);
    } catch (e) {
      toast.error("Failed to scan for collisions");
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const clean = !loading && (data?.total_collisions ?? 0) === 0;

  return (
    <div className="space-y-5" data-testid="collisions-panel">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`w-12 h-12 rounded-xl flex items-center justify-center shadow-lg ${clean ? "bg-gradient-to-br from-emerald-500 to-teal-700 shadow-emerald-200" : "bg-gradient-to-br from-rose-500 via-red-600 to-rose-700 shadow-rose-200"}`}>
            {clean ? <ShieldCheck className="w-6 h-6 text-white" /> : <AlertTriangle className="w-6 h-6 text-white" />}
          </div>
          <div>
            <h1 className="text-2xl font-bold text-stone-900">Collisions</h1>
            <p className="text-sm text-stone-500">Same-room double-bookings across every property — auto-scanned live.</p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={load} data-testid="collisions-refresh-btn">
          <RefreshCw className={`w-4 h-4 mr-1.5 ${loading ? "animate-spin" : ""}`} /> Re-scan
        </Button>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <Kpi testId="col-kpi-scanned" icon={Calendar} label="Bookings scanned" value={data?.scanned_bookings ?? 0} accent="from-stone-500 to-stone-700" />
        <Kpi
          testId="col-kpi-total"
          icon={AlertTriangle}
          label="Collision pairs"
          value={data?.total_collisions ?? 0}
          accent={clean ? "from-emerald-500 to-teal-700" : "from-rose-500 to-red-700"}
          urgent={!clean}
        />
        <Kpi testId="col-kpi-rooms" icon={DoorOpen} label="Rooms affected" value={data?.affected_rooms ?? 0} accent="from-amber-500 to-orange-600" />
        <Kpi testId="col-kpi-props" icon={Building2} label="Properties affected" value={data?.affected_properties ?? 0} accent="from-indigo-500 to-violet-700" />
      </div>

      {/* Empty state */}
      {clean && (
        <div className="bg-gradient-to-br from-emerald-50 via-teal-50 to-emerald-100 border border-emerald-200 rounded-2xl p-10 text-center" data-testid="collisions-empty">
          <div className="w-20 h-20 mx-auto mb-4 rounded-full bg-gradient-to-br from-emerald-500 to-teal-700 flex items-center justify-center shadow-lg">
            <ShieldCheck className="w-10 h-10 text-white" />
          </div>
          <h2 className="text-xl font-bold text-emerald-900 mb-1">All clear</h2>
          <p className="text-sm text-emerald-700 mb-1">{data?.scanned_bookings ?? 0} active bookings scanned — no same-room double-bookings detected.</p>
          <p className="text-xs text-emerald-600 flex items-center justify-center gap-1"><Sparkles className="w-3 h-3" /> Your calendar is conflict-free</p>
        </div>
      )}

      {/* Loading state */}
      {loading && !data && (
        <div className="bg-white rounded-xl border border-stone-200 p-10 text-center text-stone-400">
          <RefreshCw className="w-8 h-8 mx-auto mb-2 animate-spin" />
          <div className="text-sm">Scanning all bookings for conflicts…</div>
        </div>
      )}

      {/* Conflict groups */}
      {!clean && (data?.groups || []).length > 0 && (
        <div className="space-y-3">
          {(data.groups || []).map((g) => (
            <div key={g.room_id} className="bg-white rounded-xl border-2 border-rose-100 overflow-hidden hover:border-rose-300 transition-colors" data-testid={`collision-group-${g.room_id}`}>
              <div className="bg-gradient-to-r from-rose-50 via-red-50 to-rose-50 px-5 py-3 flex items-center gap-3 border-b border-rose-100">
                <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-rose-500 to-red-700 flex items-center justify-center shadow">
                  <AlertTriangle className="w-4 h-4 text-white" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="font-bold text-stone-900 text-sm truncate">{g.room_name}</h3>
                    <Badge className="bg-rose-600 text-white text-[10px]">{g.collision_count} conflict{g.collision_count === 1 ? "" : "s"}</Badge>
                  </div>
                  <div className="text-[11px] text-stone-500 flex items-center gap-1.5">
                    <Building2 className="w-3 h-3" /> {g.property_name}
                    <span className="text-stone-300">·</span>
                    <Users className="w-3 h-3" /> {g.bookings.length} colliding bookings
                  </div>
                </div>
                {onJumpToCalendar && (
                  <Button size="sm" variant="outline" onClick={() => onJumpToCalendar(g.property_id)} data-testid={`collision-jump-${g.room_id}`}>
                    <Calendar className="w-3.5 h-3.5 mr-1" /> Open calendar
                    <ChevronRight className="w-3.5 h-3.5 ml-0.5" />
                  </Button>
                )}
              </div>
              <div className="divide-y divide-stone-100">
                {g.bookings.map((b) => (
                  <div key={b.id} className="px-5 py-2.5 flex items-center gap-3 hover:bg-rose-50/40">
                    <div className={`w-1 h-8 rounded-full ${SRC_DOT[b.source] || "bg-stone-500"}`}></div>
                    <div className="flex-1 min-w-0">
                      <div className="font-semibold text-sm text-stone-800 truncate">{b.guest_name}</div>
                      <div className="text-[11px] text-stone-500 truncate">
                        {b.check_in} → {b.check_out}
                        {b.nights ? ` · ${b.nights}n` : ""}
                        {b.source ? ` · ${b.source}` : ""}
                        {b.booking_ref ? ` · ${b.booking_ref}` : ""}
                      </div>
                    </div>
                    <Badge variant="outline" className={`text-[10px] ${STATUS_CLS[b.status] || "bg-stone-100 text-stone-700"}`}>{b.status}</Badge>
                    <div className="text-xs font-mono font-bold text-stone-700 w-20 text-right">{cur(b.total_price, b.currency)}</div>
                  </div>
                ))}
              </div>
              <div className="px-5 py-2.5 bg-stone-50 border-t border-stone-100 text-[11px] text-stone-600 flex items-center gap-1.5">
                <Zap className="w-3 h-3 text-amber-500" />
                Resolution: drag one of these bookings to another room on the calendar, or cancel / relocate the latest one.
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

const Kpi = ({ icon: Icon, label, value, accent, urgent, testId }) => (
  <div className="bg-white rounded-xl border border-stone-200 p-4 relative overflow-hidden" data-testid={testId}>
    <div className={`absolute top-0 right-0 w-24 h-24 rounded-full bg-gradient-to-br ${accent} opacity-10 -mr-8 -mt-8`}></div>
    <div className="flex items-center gap-2 mb-2 relative">
      <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${accent} flex items-center justify-center`}>
        <Icon className="w-4 h-4 text-white" />
      </div>
      <span className="text-[11px] font-medium text-stone-500 uppercase tracking-wider">{label}</span>
    </div>
    <div className={`text-3xl font-black ${urgent ? "text-rose-600" : "text-stone-900"}`}>{Number(value).toLocaleString()}</div>
  </div>
);

export default CollisionsPanel;
