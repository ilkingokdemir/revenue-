import { useState, useEffect } from "react";
import { getQueueCount } from "../lib/offlineQueue";

export const OfflineBanner = () => {
  const [offline, setOffline] = useState(!navigator.onLine);
  const [justBack, setJustBack] = useState(false);
  const [queued, setQueued] = useState(getQueueCount());

  useEffect(() => {
    const goOffline = () => { setOffline(true); setJustBack(false); };
    const goOnline = () => {
      setOffline(false);
      setJustBack(true);
      setTimeout(() => setJustBack(false), 4000);
    };
    const onQueue = (e) => setQueued(e.detail?.count ?? getQueueCount());
    window.addEventListener("offline", goOffline);
    window.addEventListener("online", goOnline);
    window.addEventListener("offline-queue-changed", onQueue);
    return () => {
      window.removeEventListener("offline", goOffline);
      window.removeEventListener("online", goOnline);
      window.removeEventListener("offline-queue-changed", onQueue);
    };
  }, []);

  if (!offline && !justBack) return null;
  return (
    <div
      data-testid="offline-banner"
      className={`fixed top-0 left-0 right-0 z-[100] text-center text-xs font-medium py-1.5 transition-colors ${
        offline ? "bg-amber-500 text-amber-950" : "bg-emerald-500 text-white"
      }`}
    >
      {offline
        ? `📶 Çevrimdışı mod — son yüklenen veriler gösteriliyor${queued > 0 ? ` · ${queued} işlem kuyrukta` : ""}`
        : "✓ Bağlantı geri geldi"}
    </div>
  );
};
