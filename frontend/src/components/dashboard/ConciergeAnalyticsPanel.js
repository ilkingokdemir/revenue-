import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import {
  Robot, ChatText, Users, ArrowsClockwise, Lightning, Clock,
} from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export function ConciergeAnalyticsPanel({ properties, activePropertyId: propActivePropertyId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const propertyId = (propActivePropertyId && propActivePropertyId !== "all") ? propActivePropertyId : (properties?.[0]?.id || "aldgate-flats");

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const { data: d } = await axios.get(`${API}/concierge/analytics/${propertyId}`);
      setData(d);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [propertyId]);

  useEffect(() => { fetch(); }, [fetch]);

  if (loading) return (
    <div className="p-5 flex justify-center py-20">
      <ArrowsClockwise size={24} className="animate-spin text-stone-400" />
    </div>
  );

  return (
    <div className="p-5" data-testid="concierge-analytics-panel">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-lg font-semibold text-stone-900 flex items-center gap-2">
            <Robot size={20} weight="fill" className="text-purple-600" /> AI Concierge Analytics
          </h2>
          <p className="text-sm text-stone-500">Chat interactions and guest inquiries</p>
        </div>
        <button onClick={fetch} className="text-xs bg-stone-100 text-stone-600 px-3 py-1.5 rounded-lg hover:bg-stone-200 flex items-center gap-1">
          <ArrowsClockwise size={12} /> Refresh
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        {[
          { icon: ChatText, label: "Total Sessions", value: data?.total_sessions || 0, color: "text-blue-600" },
          { icon: Lightning, label: "Total Messages", value: data?.total_messages || 0, color: "text-amber-600" },
          { icon: Users, label: "Guest Questions", value: data?.user_messages || 0, color: "text-emerald-600" },
          { icon: Robot, label: "AI Responses", value: data?.ai_messages || 0, color: "text-purple-600" },
        ].map(s => (
          <div key={s.label} className="bg-white border border-stone-200 rounded-xl p-4">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] text-stone-400 uppercase tracking-wider font-semibold">{s.label}</span>
              <s.icon size={14} className={s.color} weight="fill" />
            </div>
            <span className="text-2xl font-bold text-stone-900">{s.value}</span>
          </div>
        ))}
      </div>

      {/* Recent Sessions */}
      <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-stone-200 bg-stone-50">
          <h3 className="text-sm font-semibold text-stone-700">Recent Chat Sessions</h3>
        </div>
        {!data?.recent_sessions?.length ? (
          <div className="py-10 text-center">
            <Robot size={32} className="mx-auto mb-2 text-stone-300" />
            <p className="text-sm text-stone-400">No chat sessions yet</p>
            <p className="text-xs text-stone-300 mt-1">Guests can chat via the booking engine</p>
          </div>
        ) : (
          <div className="divide-y divide-stone-50">
            {data.recent_sessions.map((s, i) => (
              <div key={s.session_id} className="px-4 py-3 flex items-center gap-3 hover:bg-stone-50 transition-colors" data-testid={`session-${i}`}>
                <div className="w-8 h-8 rounded-full bg-purple-100 flex items-center justify-center flex-shrink-0">
                  <ChatText size={14} className="text-purple-600" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-stone-800 truncate">"{s.first_message}"</p>
                  <div className="flex items-center gap-3 mt-0.5 text-[11px] text-stone-400">
                    <span className="flex items-center gap-1"><Lightning size={10} /> {s.messages} messages</span>
                    <span className="flex items-center gap-1"><Clock size={10} /> {new Date(s.last_active).toLocaleDateString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
