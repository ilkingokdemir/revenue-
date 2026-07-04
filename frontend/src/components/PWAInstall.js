/**
 * PWAInstall — floating "Add to Home Screen" button + SW registration.
 * ---------------------------------------------------------------------
 * Renders a small bottom-right chip whenever the browser fires
 * `beforeinstallprompt` (Chromium/Edge/Samsung). On iOS Safari we show a
 * short hint since Safari doesn't expose the event.
 *
 * Import once in App root:
 *   <PWAInstall />
 */
import { useEffect, useState } from "react";
import { Download, X, Apple } from "lucide-react";

export function PWAInstall() {
  const [deferredPrompt, setDeferredPrompt] = useState(null);
  const [showIosHint, setShowIosHint] = useState(false);
  const [installed, setInstalled] = useState(false);

  useEffect(() => {
    // Register service worker (production only-friendly — hot reload compatible)
    if ("serviceWorker" in navigator && !window.location.hostname.includes("localhost")) {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    }

    const isStandalone = window.matchMedia("(display-mode: standalone)").matches ||
                          window.navigator.standalone === true;
    if (isStandalone) { setInstalled(true); return; }

    const handler = (e) => { e.preventDefault(); setDeferredPrompt(e); };
    window.addEventListener("beforeinstallprompt", handler);

    // iOS detection — no beforeinstallprompt on Safari
    const ua = window.navigator.userAgent;
    const isIos = /iPad|iPhone|iPod/.test(ua) && !window.MSStream;
    const dismissed = localStorage.getItem("pwa_ios_hint_dismissed");
    if (isIos && !isStandalone && !dismissed) {
      setTimeout(() => setShowIosHint(true), 4000); // wait 4s so it doesn't fight with login
    }

    window.addEventListener("appinstalled", () => setInstalled(true));
    return () => window.removeEventListener("beforeinstallprompt", handler);
  }, []);

  if (installed) return null;

  const install = async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    if (outcome === "accepted") setInstalled(true);
    setDeferredPrompt(null);
  };

  if (deferredPrompt) {
    return (
      <div
        data-testid="pwa-install-chip"
        className="fixed bottom-4 right-4 z-[9999] bg-gradient-to-r from-indigo-600 to-fuchsia-600 text-white rounded-2xl shadow-2xl border border-white/10 pl-4 pr-2 py-2 flex items-center gap-3 max-w-xs"
      >
        <Download className="w-4 h-4 flex-shrink-0" />
        <div className="flex-1">
          <p className="text-xs font-bold leading-tight">Uygulama olarak yükle</p>
          <p className="text-[10px] text-white/70 leading-tight">Ana ekrana ekle · offline kullan</p>
        </div>
        <button
          onClick={install}
          data-testid="pwa-install-btn"
          className="text-[11px] px-3 py-1.5 rounded-xl bg-white text-indigo-700 font-black hover:bg-white/90"
        >
          Yükle
        </button>
        <button
          onClick={() => setDeferredPrompt(null)}
          className="p-1 rounded-lg hover:bg-white/10"
          aria-label="Kapat"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    );
  }

  if (showIosHint) {
    return (
      <div
        data-testid="pwa-ios-hint"
        className="fixed bottom-4 left-4 right-4 md:left-auto md:right-4 md:max-w-sm z-[9999] bg-black/90 backdrop-blur-sm text-white rounded-2xl shadow-2xl border border-white/10 p-4"
      >
        <div className="flex items-start gap-3">
          <Apple className="w-5 h-5 text-white/80 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="text-sm font-bold mb-1">Ana ekrana ekle</p>
            <p className="text-xs text-white/70 leading-relaxed">
              Safari&apos;de <b>Paylaş</b> ↗ ikonuna dokunun → <b>&quot;Ana Ekrana Ekle&quot;</b> → MyHotelBox gerçek bir app gibi açılır (offline, tam ekran).
            </p>
          </div>
          <button
            onClick={() => { localStorage.setItem("pwa_ios_hint_dismissed", "1"); setShowIosHint(false); }}
            data-testid="pwa-ios-dismiss"
            className="p-1 rounded-lg hover:bg-white/10"
            aria-label="Kapat"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>
    );
  }

  return null;
}
