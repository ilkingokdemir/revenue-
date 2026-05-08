/**
 * Web Push Notifications Panel
 * - Registers this browser into the property push channel
 * - Sends targeted pushes (role / tag / all)
 * - Polls for pending simulated pushes (until VAPID is wired) and surfaces
 *   them as in-app toasts.
 */
import { useEffect, useState, useCallback, useRef } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, Bell, BellRing, Send, RefreshCw, BellOff } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function fakeEndpoint() {
  // VAPID-less stand-in. Real service workers replace this with the browser endpoint.
  let id = localStorage.getItem("__hk_push_endpoint");
  if (!id) {
    id = `hk-stub://${Math.random().toString(36).slice(2, 10)}-${Date.now()}`;
    localStorage.setItem("__hk_push_endpoint", id);
  }
  return id;
}

export default function WebPushPanel({ propertyId, hotelName = "", currentUser }) {
  const [subs, setSubs] = useState({ items: [], by_role: {} });
  const [log, setLog] = useState([]);
  const [loading, setLoading] = useState(false);
  const [subscribed, setSubscribed] = useState(false);
  const [form, setForm] = useState({ title: "", body: "", url: "/", category: "ops", target_role: "", target_tag: "" });
  const pollRef = useRef(null);

  const refresh = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const [{ data: s }, { data: l }] = await Promise.all([
        axios.get(`${API}/push/${propertyId}/subscriptions`),
        axios.get(`${API}/push/${propertyId}/log?days=7`),
      ]);
      setSubs(s);
      setLog(l.items || []);
    } catch { toast.error("Load failed"); }
    setLoading(false);
  }, [propertyId]);

  // Check if this browser is already subscribed
  useEffect(() => {
    setSubscribed(!!localStorage.getItem("__hk_push_subscribed"));
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  // Poll pending pushes for this user — render as toast
  useEffect(() => {
    if (!subscribed || !propertyId) return;
    const tick = async () => {
      try {
        const { data } = await axios.get(`${API}/push/${propertyId}/pending`, {
          params: { user_id: currentUser?.id || "", user_role: currentUser?.role || "staff" },
        });
        (data.items || []).forEach((p) => {
          toast(p.title, { description: p.body, duration: 6000 });
        });
      } catch { /* swallow */ }
    };
    pollRef.current = setInterval(tick, 15000);
    tick();
    return () => clearInterval(pollRef.current);
  }, [subscribed, propertyId, currentUser]);

  const subscribe = async () => {
    try {
      await axios.post(`${API}/push/subscribe`, {
        property_id: propertyId, endpoint: fakeEndpoint(),
        user_id: currentUser?.id || "", user_role: currentUser?.role || "staff",
        user_agent: navigator.userAgent.slice(0, 80), tags: ["frontdesk"],
      });
      localStorage.setItem("__hk_push_subscribed", "1");
      setSubscribed(true);
      toast.success("This browser is now subscribed");
      refresh();
    } catch { toast.error("Subscribe failed"); }
  };

  const unsubscribe = async () => {
    try {
      await axios.post(`${API}/push/unsubscribe`, { endpoint: fakeEndpoint() });
      localStorage.removeItem("__hk_push_subscribed");
      setSubscribed(false);
      toast.success("Unsubscribed");
      refresh();
    } catch { toast.error("Failed"); }
  };

  const send = async () => {
    if (!form.title || !form.body) return toast.error("Title + body required");
    try {
      const { data } = await axios.post(`${API}/push/${propertyId}/send`, form);
      toast.success(`Dispatched to ${data.subscribers_targeted} subscriber(s)`);
      setForm({ ...form, title: "", body: "" });
      refresh();
    } catch { toast.error("Send failed"); }
  };

  return (
    <div className="space-y-6" data-testid="web-push-panel">
      <div>
        <h2 className="text-2xl font-semibold text-stone-100">Web Push Notifications</h2>
        <p className="text-sm text-stone-400 mt-1">{hotelName ? `${hotelName} · ` : ""}PWA browser push for staff and guests. Works without VAPID via in-app toast fallback; flip to real VAPID anytime in property settings.</p>
      </div>

      <div className="grid md:grid-cols-3 gap-4">
        <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4 space-y-2">
          <div className="text-xs uppercase tracking-wider text-stone-400">This browser</div>
          {subscribed ? (
            <>
              <div className="flex items-center gap-2 text-emerald-300"><BellRing className="w-4 h-4" /> Subscribed</div>
              <button data-testid="push-unsub-btn" onClick={unsubscribe} className="text-xs px-3 py-1 rounded bg-stone-800 border border-stone-700 text-stone-300 flex items-center gap-1">
                <BellOff className="w-3 h-3" /> Unsubscribe
              </button>
            </>
          ) : (
            <>
              <div className="flex items-center gap-2 text-stone-400"><Bell className="w-4 h-4" /> Not subscribed</div>
              <button data-testid="push-sub-btn" onClick={subscribe} className="text-xs px-3 py-1 rounded bg-cyan-500/20 border border-cyan-500/40 text-cyan-200 flex items-center gap-1">
                <Bell className="w-3 h-3" /> Subscribe this browser
              </button>
            </>
          )}
        </div>

        <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4">
          <div className="text-xs uppercase tracking-wider text-stone-400 mb-2">Active subscribers</div>
          <div className="text-3xl font-semibold text-stone-100">{subs.count}</div>
          <div className="mt-2 flex flex-wrap gap-1 text-[10px]">
            {Object.entries(subs.by_role).map(([k, v]) => (
              <span key={k} className="px-2 py-0.5 rounded border border-stone-700 bg-stone-800 text-stone-300">{k}: {v}</span>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4">
          <div className="text-xs uppercase tracking-wider text-stone-400 mb-2">Sent (7d)</div>
          <div className="text-3xl font-semibold text-stone-100">{log.length}</div>
          <button data-testid="push-refresh-btn" onClick={refresh} className="mt-2 text-xs px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-300 flex items-center gap-1">
            {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />} Refresh
          </button>
        </div>
      </div>

      <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4 space-y-2">
        <div className="text-xs uppercase tracking-wider text-stone-400">Compose push</div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          <input data-testid="push-title-input" placeholder="Title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm" />
          <input placeholder="URL (deep link, optional)" value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm" />
        </div>
        <textarea data-testid="push-body-input" rows={2} placeholder="Body" value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} className="w-full px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm" />
        <div className="flex flex-wrap gap-2">
          <select value={form.target_role} onChange={(e) => setForm({ ...form, target_role: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-xs">
            <option value="">All roles</option>
            {["admin", "manager", "receptionist", "housekeeping", "maintenance"].map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
          <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-xs">
            {["ops", "guest", "alert", "marketing"].map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <input placeholder="Target tag (optional)" value={form.target_tag} onChange={(e) => setForm({ ...form, target_tag: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-xs" />
          <button data-testid="push-send-btn" onClick={send} className="ml-auto px-3 py-1 rounded bg-cyan-500/20 border border-cyan-500/40 text-cyan-200 text-xs flex items-center gap-1">
            <Send className="w-3 h-3" /> Dispatch
          </button>
        </div>
      </div>

      <div className="rounded-xl border border-stone-800 bg-stone-900/60 overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="text-left text-[10px] uppercase tracking-wider text-stone-500 border-b border-stone-800">
            <tr><th className="px-3 py-2">Sent</th><th className="px-3 py-2">Title</th><th className="px-3 py-2">Body</th><th className="px-3 py-2">Target</th><th className="px-3 py-2 text-right">#Subs</th><th className="px-3 py-2">Mode</th></tr>
          </thead>
          <tbody>
            {log.map((l) => (
              <tr key={l.id} className="border-t border-stone-800/60 text-stone-200" data-testid="push-log-row">
                <td className="px-3 py-2 text-stone-400 text-xs">{(l.sent_at || "").slice(0, 16)}</td>
                <td className="px-3 py-2 text-stone-100">{l.title}</td>
                <td className="px-3 py-2 text-stone-400 text-xs truncate max-w-xs">{l.body}</td>
                <td className="px-3 py-2 text-stone-400 text-xs">{l.target_role || "all"}{l.target_tag ? ` / ${l.target_tag}` : ""}</td>
                <td className="px-3 py-2 text-right">{l.subscriber_count}</td>
                <td className="px-3 py-2"><span className={`text-[10px] px-2 py-0.5 rounded border ${l.delivery_mode === "real_vapid" ? "bg-emerald-500/20 border-emerald-500/40 text-emerald-200" : "bg-amber-500/20 border-amber-500/40 text-amber-200"}`}>{l.delivery_mode}</span></td>
              </tr>
            ))}
            {log.length === 0 && <tr><td colSpan={6} className="px-3 py-6 text-center text-stone-500">No pushes sent yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
