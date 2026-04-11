import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import {
  Bed, Users, CalendarBlank, CurrencyGbp, ChatText, Star,
  ArrowsClockwise, Envelope, Lightning, CaretRight,
  WhatsappLogo, TelegramLogo, DeviceMobile, Globe, ChatCircleDots,
  WarningCircle, ArrowUp, ArrowDown, Clock, SignIn, SignOut,
  PaperPlaneTilt, Robot,
} from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const CHANNEL_COLORS = {
  whatsapp: { icon: WhatsappLogo, color: "text-green-600" },
  email: { icon: Envelope, color: "text-blue-600" },
  sms: { icon: DeviceMobile, color: "text-purple-600" },
  telegram: { icon: TelegramLogo, color: "text-sky-600" },
  "booking.com": { icon: Globe, color: "text-blue-800" },
  website_chat: { icon: ChatCircleDots, color: "text-blue-600" },
  internal: { icon: ChatText, color: "text-stone-600" },
};

function StatCard({ icon: Icon, iconColor, iconBg, label, value, sub, onClick, testId }) {
  return (
    <div onClick={onClick}
      className={`bg-white border border-stone-200 rounded-xl p-4 transition-all ${onClick ? "cursor-pointer hover:border-stone-300 hover:shadow-sm" : ""}`}
      data-testid={testId}>
      <div className="flex items-center justify-between mb-2">
        <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${iconBg}`}>
          <Icon size={18} className={iconColor} weight="fill" />
        </div>
        {onClick && <CaretRight size={12} className="text-stone-300" />}
      </div>
      <div className="text-2xl font-bold text-stone-900">{value}</div>
      <div className="text-[11px] text-stone-400 mt-0.5">{label}</div>
      {sub && <div className="text-[10px] text-stone-400 mt-0.5">{sub}</div>}
    </div>
  );
}

export function DashboardHome({ properties, activePropertyId: propActivePropertyId, onNavigate }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const propertyId = (propActivePropertyId && propActivePropertyId !== "all") ? propActivePropertyId : (properties?.[0]?.id || "aldgate-flats");

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const { data: d } = await axios.get(`${API}/dashboard/overview/${propertyId}`);
      setData(d);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [propertyId]);

  useEffect(() => { fetch(); }, [fetch]);

  if (loading) {
    return (
      <div className="p-6 flex justify-center py-20">
        <ArrowsClockwise size={28} className="animate-spin text-stone-300" />
      </div>
    );
  }

  if (!data) return null;

  const now = new Date();
  const greeting = now.getHours() < 12 ? "Good morning" : now.getHours() < 18 ? "Good afternoon" : "Good evening";
  const dateStr = now.toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" });

  return (
    <div className="p-6" data-testid="dashboard-home">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-xl font-bold text-stone-900" data-testid="dashboard-greeting">{greeting}</h1>
        <p className="text-sm text-stone-400 mt-0.5">{dateStr}</p>
      </div>

      {/* Today's Snapshot */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
        <StatCard icon={SignIn} iconColor="text-emerald-600" iconBg="bg-emerald-50"
          label="Arriving Today" value={data.bookings.today_checkins}
          sub={`${data.bookings.tomorrow_checkins} tomorrow`} testId="stat-checkins" />
        <StatCard icon={SignOut} iconColor="text-amber-600" iconBg="bg-amber-50"
          label="Departing Today" value={data.bookings.today_checkouts} testId="stat-checkouts" />
        <StatCard icon={Users} iconColor="text-blue-600" iconBg="bg-blue-50"
          label="In-House Guests" value={data.bookings.current_guests}
          sub={data.bookings.total_rooms > 0 ? `${data.bookings.occupancy}% occupancy` : ""} testId="stat-guests" />
        <StatCard icon={CurrencyGbp} iconColor="text-emerald-600" iconBg="bg-emerald-50"
          label="Revenue (Month)" value={`£${Math.round(data.revenue.month_total).toLocaleString()}`}
          sub={`${data.revenue.month_bookings} bookings`} testId="stat-revenue" />
        <StatCard icon={ChatText} iconColor="text-purple-600" iconBg="bg-purple-50"
          label="Unread Messages" value={data.messaging.unread}
          sub={`${data.messaging.open} open conversations`}
          onClick={() => onNavigate?.("messaging")} testId="stat-messages" />
        <StatCard icon={Star} iconColor="text-amber-500" iconBg="bg-amber-50"
          label="Avg Rating" value={data.reviews.avg_rating || "—"}
          sub={`${data.reviews.total} reviews`}
          onClick={() => onNavigate?.("reviews")} testId="stat-rating" />
      </div>

      {/* Quick Actions */}
      <div className="flex items-center gap-2 mb-6">
        <span className="text-xs font-semibold text-stone-400 uppercase tracking-wider mr-2">Quick Actions</span>
        {[
          { label: "Inbox", icon: ChatText, view: "messaging", color: "bg-purple-50 text-purple-700 hover:bg-purple-100" },
          { label: "Run Automation", icon: Lightning, view: "automation", color: "bg-amber-50 text-amber-700 hover:bg-amber-100" },
          { label: "Reviews", icon: Star, view: "reviews", color: "bg-emerald-50 text-emerald-700 hover:bg-emerald-100" },
          { label: "Bookings", icon: Bed, view: "booking", color: "bg-blue-50 text-blue-700 hover:bg-blue-100" },
        ].map(a => (
          <button key={a.label} onClick={() => onNavigate?.(a.view)}
            className={`text-xs px-3 py-2 rounded-lg flex items-center gap-1.5 font-medium transition-colors ${a.color}`}
            data-testid={`quick-${a.label.toLowerCase().replace(/\s/g, '-')}`}>
            <a.icon size={13} weight="fill" /> {a.label}
          </button>
        ))}
      </div>

      {/* Three Column Activity Feed */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

        {/* Recent Bookings */}
        <div className="bg-white border border-stone-200 rounded-xl overflow-hidden" data-testid="recent-bookings-card">
          <div className="px-4 py-3 border-b border-stone-100 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-stone-800 flex items-center gap-1.5">
              <Bed size={14} className="text-blue-600" weight="fill" /> Recent Bookings
            </h3>
            <button onClick={() => onNavigate?.("booking")} className="text-[10px] text-blue-600 hover:text-blue-700 font-medium flex items-center gap-0.5">
              View all <CaretRight size={10} />
            </button>
          </div>
          {data.recent.bookings.length === 0 ? (
            <div className="py-8 text-center text-xs text-stone-400">No recent bookings</div>
          ) : (
            <div className="divide-y divide-stone-50">
              {data.recent.bookings.map((b, i) => (
                <div key={i} className="px-4 py-3 hover:bg-stone-50 transition-colors" data-testid={`recent-booking-${i}`}>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-stone-800">{b.guest_name}</span>
                    <span className="text-xs font-bold text-emerald-600">£{b.total_price}</span>
                  </div>
                  <div className="flex items-center gap-2 mt-1 text-[10px] text-stone-400">
                    <span>#{b.booking_ref}</span>
                    <span>{b.check_in} — {b.check_out}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Unread Messages */}
        <div className="bg-white border border-stone-200 rounded-xl overflow-hidden" data-testid="recent-messages-card">
          <div className="px-4 py-3 border-b border-stone-100 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-stone-800 flex items-center gap-1.5">
              <ChatText size={14} className="text-purple-600" weight="fill" /> Unread Messages
            </h3>
            <button onClick={() => onNavigate?.("messaging")} className="text-[10px] text-purple-600 hover:text-purple-700 font-medium flex items-center gap-0.5">
              Open inbox <CaretRight size={10} />
            </button>
          </div>
          {data.recent.messages.length === 0 ? (
            <div className="py-8 text-center text-xs text-stone-400">All caught up!</div>
          ) : (
            <div className="divide-y divide-stone-50">
              {data.recent.messages.map((m, i) => {
                const chCfg = CHANNEL_COLORS[m.channel] || CHANNEL_COLORS.internal;
                const ChIcon = chCfg.icon;
                return (
                  <div key={i} className="px-4 py-3 hover:bg-stone-50 transition-colors cursor-pointer"
                    onClick={() => onNavigate?.("messaging")} data-testid={`recent-msg-${i}`}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <ChIcon size={12} className={chCfg.color} weight="fill" />
                        <span className="text-xs font-semibold text-stone-800">{m.guest_name}</span>
                      </div>
                      {m.priority === "urgent" && <WarningCircle size={12} className="text-red-500" weight="fill" />}
                      {m.priority === "high" && <WarningCircle size={12} className="text-orange-500" weight="fill" />}
                    </div>
                    <p className="text-[11px] text-stone-500 truncate mt-1">{m.last_message_preview}</p>
                    <span className="text-[9px] text-stone-300 mt-0.5 block">
                      {new Date(m.last_message_at).toLocaleDateString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Recent Reviews */}
        <div className="bg-white border border-stone-200 rounded-xl overflow-hidden" data-testid="recent-reviews-card">
          <div className="px-4 py-3 border-b border-stone-100 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-stone-800 flex items-center gap-1.5">
              <Star size={14} className="text-amber-500" weight="fill" /> Recent Reviews
            </h3>
            <button onClick={() => onNavigate?.("reviews")} className="text-[10px] text-amber-600 hover:text-amber-700 font-medium flex items-center gap-0.5">
              View all <CaretRight size={10} />
            </button>
          </div>
          {data.recent.reviews.length === 0 ? (
            <div className="py-8 text-center text-xs text-stone-400">No reviews yet</div>
          ) : (
            <div className="divide-y divide-stone-50">
              {data.recent.reviews.map((r, i) => (
                <div key={i} className="px-4 py-3 hover:bg-stone-50 transition-colors" data-testid={`recent-review-${i}`}>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-stone-800">{r.guest_name || "Guest"}</span>
                    <div className="flex items-center gap-0.5">
                      {Array.from({ length: 5 }).map((_, si) => (
                        <Star key={si} size={10} weight="fill" className={si < (r.rating || 0) ? "text-amber-400" : "text-stone-200"} />
                      ))}
                    </div>
                  </div>
                  <p className="text-[11px] text-stone-500 truncate mt-1">{r.review_text || "No text"}</p>
                  <div className="flex items-center gap-2 mt-1 text-[9px] text-stone-300">
                    <span>{r.platform}</span>
                    {r.status === "pending" && <span className="text-amber-600 font-medium">Pending</span>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Bottom Row - Automation + Revenue Summary */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4">
        {/* Automation Status */}
        <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="automation-status-card">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-stone-800 flex items-center gap-1.5">
              <Lightning size={14} className="text-amber-500" weight="fill" /> Automation Today
            </h3>
            <button onClick={() => onNavigate?.("automation")} className="text-[10px] text-amber-600 hover:text-amber-700 font-medium flex items-center gap-0.5">
              Manage <CaretRight size={10} />
            </button>
          </div>
          <div className="flex items-center gap-6">
            <div>
              <div className="text-2xl font-bold text-stone-900">{data.automation.sent_today}</div>
              <div className="text-[10px] text-stone-400">Messages sent</div>
            </div>
            {data.automation.failed_today > 0 && (
              <div>
                <div className="text-2xl font-bold text-red-500">{data.automation.failed_today}</div>
                <div className="text-[10px] text-red-400">Failed (check config)</div>
              </div>
            )}
            <div className="ml-auto text-right">
              <div className="text-[11px] text-stone-400">Tomorrow</div>
              <div className="text-sm font-bold text-blue-600">{data.bookings.tomorrow_checkins} check-ins</div>
              <div className="text-[10px] text-stone-400">Pre-arrival messages will fire</div>
            </div>
          </div>
        </div>

        {/* Revenue */}
        <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="revenue-summary-card">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-stone-800 flex items-center gap-1.5">
              <CurrencyGbp size={14} className="text-emerald-600" weight="fill" /> Revenue
            </h3>
          </div>
          <div className="flex items-center gap-8">
            <div>
              <div className="text-[10px] text-stone-400 uppercase tracking-wider font-semibold">This Week</div>
              <div className="text-2xl font-bold text-stone-900">£{Math.round(data.revenue.week_total).toLocaleString()}</div>
              <div className="text-[10px] text-stone-400">{data.revenue.week_bookings} bookings</div>
            </div>
            <div className="h-10 w-px bg-stone-200" />
            <div>
              <div className="text-[10px] text-stone-400 uppercase tracking-wider font-semibold">This Month</div>
              <div className="text-2xl font-bold text-stone-900">£{Math.round(data.revenue.month_total).toLocaleString()}</div>
              <div className="text-[10px] text-stone-400">{data.revenue.month_bookings} bookings</div>
            </div>
            <div className="h-10 w-px bg-stone-200" />
            <div>
              <div className="text-[10px] text-stone-400 uppercase tracking-wider font-semibold">Total Bookings</div>
              <div className="text-2xl font-bold text-stone-900">{data.bookings.total}</div>
              <div className="text-[10px] text-stone-400">all time</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
