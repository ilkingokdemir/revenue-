import { useState, useEffect } from "react";

export const OfflineBanner = () => {
  const [offline, setOffline] = useState(!navigator.onLine);
  const [justBack, setJustBack] = useState(false);

  useEffect(() => {
    const goOffline = () => { setOffline(true); setJustBack(false); };
    const goOnline = () => {
      setOffline(false);
      setJustBack(true);
      setTimeout(() => setJustBack(false), 4000);
    };
    window.addEventListener("offline", goOffline);
    window.addEventListener("online", goOnline);
    return () => {
      window.removeEventListener("offline", goOffline);
      window.removeEventListener("online", goOnline);
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
        ? "📶 Çevrimdışı mod — son yüklenen veriler gösteriliyor, değişiklikler bağlantı gelince gönderilmeli"
        : "✓ Bağlantı geri geldi"}
    </div>
  );
};
