import React, { useEffect, useState } from "react";
import { DeviceMobile, X } from "@phosphor-icons/react";

/**
 * PWA Install Banner
 * ------------------
 * Listens for the `beforeinstallprompt` event and shows a small floating button
 * inviting the user to install the app. After they accept (or dismiss), the
 * banner hides itself and remembers the choice in localStorage so it doesn't
 * spam them.
 *
 * Works on Chrome, Edge, Opera, Samsung Internet, modern Android browsers.
 * On iOS Safari, falls back to a one-line tip ("Add to Home Screen via Share menu").
 */
export default function PwaInstallButton() {
  const [deferred, setDeferred] = useState(null);
  const [show, setShow] = useState(false);
  const [iosHint, setIosHint] = useState(false);

  useEffect(() => {
    if (localStorage.getItem("pwa_install_dismissed") === "1") return;
    if (window.matchMedia && window.matchMedia("(display-mode: standalone)").matches) return; // already installed

    const isIos = /iphone|ipad|ipod/i.test(window.navigator.userAgent || "");
    const isSafari = /^((?!chrome|android).)*safari/i.test(window.navigator.userAgent || "");
    if (isIos && isSafari) {
      // iOS Safari has no install prompt; show a hint after 4s on the dashboard only
      const t = setTimeout(() => setIosHint(true), 4000);
      return () => clearTimeout(t);
    }

    const handler = (e) => {
      e.preventDefault();
      setDeferred(e);
      setShow(true);
    };
    window.addEventListener("beforeinstallprompt", handler);
    return () => window.removeEventListener("beforeinstallprompt", handler);
  }, []);

  const install = async () => {
    if (!deferred) return;
    deferred.prompt();
    const { outcome } = await deferred.userChoice;
    setShow(false);
    if (outcome !== "accepted") {
      localStorage.setItem("pwa_install_dismissed", "1");
    }
  };

  const dismiss = () => {
    setShow(false);
    setIosHint(false);
    localStorage.setItem("pwa_install_dismissed", "1");
  };

  if (show) {
    return (
      <div
        className="fixed bottom-5 right-5 z-50 max-w-sm bg-stone-900 text-white border border-stone-700 rounded-xl shadow-2xl px-4 py-3 flex items-center gap-3"
        data-testid="pwa-install-banner"
      >
        <DeviceMobile size={22} weight="fill" className="text-emerald-400 shrink-0" />
        <div className="flex-1 text-sm">
          <div className="font-semibold">Cihazınıza yükleyin</div>
          <div className="text-stone-300 text-xs">MyHotelBox&apos;u ana ekrana ekleyin — daha hızlı, tarayıcısız.</div>
        </div>
        <button
          onClick={install}
          className="px-3 py-1.5 bg-emerald-500 hover:bg-emerald-400 text-stone-900 rounded font-medium text-sm"
          data-testid="pwa-install-confirm"
        >
          Yükle
        </button>
        <button onClick={dismiss} className="text-stone-400 hover:text-white" data-testid="pwa-install-dismiss" aria-label="Kapat">
          <X size={16} />
        </button>
      </div>
    );
  }

  if (iosHint) {
    return (
      <div
        className="fixed bottom-5 right-5 z-50 max-w-xs bg-stone-900 text-white border border-stone-700 rounded-xl shadow-2xl px-4 py-3 flex items-center gap-3"
        data-testid="pwa-ios-hint"
      >
        <DeviceMobile size={20} weight="fill" className="text-sky-400 shrink-0" />
        <div className="flex-1 text-xs leading-snug">
          iOS'ta yüklemek için <b>Paylaş</b> menüsünden{" "}
          <b>Ana Ekrana Ekle</b>'yi seçin.
        </div>
        <button onClick={dismiss} className="text-stone-400 hover:text-white" aria-label="Kapat">
          <X size={14} />
        </button>
      </div>
    );
  }

  return null;
}
