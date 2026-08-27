import { useEffect, useRef } from "react";
import axios from "axios";

const B = process.env.REACT_APP_BACKEND_URL;

// Okunmamış yüksek öncelikli bildirimleri tarayıcı bildirimi olarak gösterir (PWA).
export function NotificationBridge() {
  const seen = useRef(new Set());
  const first = useRef(true);

  useEffect(() => {
    const tick = async () => {
      if (typeof Notification === "undefined" || Notification.permission !== "granted") return;
      try {
        const r = await axios.get(`${B}/api/notifications?unread_only=true&limit=10`);
        for (const n of r.data.notifications || []) {
          if (seen.current.has(n.id)) continue;
          seen.current.add(n.id);
          if (!first.current && (n.priority === "high" || n.category === "revenue")) {
            new Notification(n.title || "MyHotelBox", {
              body: n.message || "", tag: n.id, icon: "/favicon.ico",
            });
          }
        }
        first.current = false;
      } catch { /* oturum yoksa sessiz geç */ }
    };
    tick();
    const id = setInterval(tick, 60000);
    return () => clearInterval(id);
  }, []);

  return null;
}
