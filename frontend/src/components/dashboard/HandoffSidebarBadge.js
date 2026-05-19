import { useEffect, useState } from "react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const auth = () => ({ Authorization: `Bearer ${localStorage.getItem("access_token")}` });

// Tiny "ding" sound — same as LiveChatInboxPanel, kept independent so sidebar
// can alert even when the user is NOT on the live-chat-inbox page.
let _ctx = null;
const ding = () => {
  try {
    if (!_ctx) _ctx = new (window.AudioContext || window.webkitAudioContext)();
    const now = _ctx.currentTime;
    [1046.5, 1318.5].forEach((f, i) => {
      const o = _ctx.createOscillator();
      const g = _ctx.createGain();
      o.type = "sine"; o.frequency.value = f;
      g.gain.setValueAtTime(0.0001, now + i * 0.12);
      g.gain.exponentialRampToValueAtTime(0.22, now + i * 0.12 + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, now + i * 0.12 + 0.35);
      o.connect(g); g.connect(_ctx.destination);
      o.start(now + i * 0.12); o.stop(now + i * 0.12 + 0.4);
    });
  } catch (e) { /* silent */ }
};

/**
 * Background poller for the sidebar — shows an unread badge next to the
 * "Live Chat Inbox" nav link. Fires a ding + Notification if a NEW handoff
 * arrives while the user is on any other page.
 *
 * Usage: <HandoffSidebarBadge propertyId="aldgate-flats" />
 */
const HandoffSidebarBadge = ({ propertyId }) => {
  const [count, setCount] = useState(0);
  const [snap, setSnap] = useState({ ids: new Set(), unread: 0 });

  useEffect(() => {
    if (!propertyId || propertyId === "all") { setCount(0); return; }
    let alive = true;
    const tick = async () => {
      try {
        const r = await axios.get(`${API}/chatbot/${propertyId}/handoff/sessions`, {
          params: { status: "active" }, headers: auth(),
        });
        if (!alive) return;
        const items = r.data.items || [];
        const ids = new Set(items.map(s => s.session_id));
        const unread = items.reduce((a, s) => a + (s.unread_count || 0), 0);
        const newSession = [...ids].find(id => !snap.ids.has(id));
        const unreadIncreased = unread > snap.unread;
        if (snap.ids.size > 0 && (newSession || unreadIncreased)) {
          ding();
          if (typeof Notification !== "undefined" && Notification.permission === "granted") {
            try {
              const n = new Notification("🔔 Live Chat", {
                body: newSession ? "Yeni canlı destek talebi" : `${unread} okunmamış mesaj`,
                tag: "handoff-bg", icon: "/favicon.ico",
              });
              n.onclick = () => { window.focus(); n.close(); };
            } catch (_) { /* ignore */ }
          }
        }
        setSnap({ ids, unread });
        setCount(unread);
      } catch (e) { /* silent */ }
    };
    tick();
    const t = setInterval(tick, 15000); // 15s background poll
    return () => { alive = false; clearInterval(t); };
  }, [propertyId, snap]);

  if (count <= 0) return null;
  return (
    <span
      data-testid="handoff-sidebar-badge"
      className="ml-auto inline-flex items-center justify-center min-w-[18px] h-[18px] px-1.5 rounded-full bg-rose-500 text-white text-[10px] font-bold animate-pulse"
      title={`${count} okunmamış canlı destek mesajı`}
    >
      {count > 99 ? "99+" : count}
    </span>
  );
};

export default HandoffSidebarBadge;
export { HandoffSidebarBadge };
