/**
 * useCapacitor — bridge hook so the same React code works in browser, PWA,
 * and native (iOS/Android via Capacitor).
 *
 * All Capacitor imports are lazy + try/catch wrapped so the web bundle
 * doesn't error when the native libs aren't reachable.
 */
import { useEffect, useState, useCallback } from "react";

let _cap = null;
async function getCap() {
  if (_cap !== null) return _cap;
  try {
    const m = await import("@capacitor/core");
    _cap = m.Capacitor;
  } catch {
    _cap = false;
  }
  return _cap;
}

export function useCapacitor() {
  const [isNative, setIsNative] = useState(false);
  const [platform, setPlatform] = useState("web");
  const [online, setOnline] = useState(typeof navigator !== "undefined" ? navigator.onLine : true);

  useEffect(() => {
    let networkSub;
    let cancelled = false;

    (async () => {
      const cap = await getCap();
      if (cancelled) return;
      if (cap) {
        setIsNative(cap.isNativePlatform?.() || false);
        setPlatform(cap.getPlatform?.() || "web");
      }
      // Network status — Capacitor first, fall back to browser events.
      try {
        const Network = (await import("@capacitor/network")).Network;
        const status = await Network.getStatus();
        if (!cancelled) setOnline(status.connected);
        networkSub = await Network.addListener("networkStatusChange", (s) => {
          if (!cancelled) setOnline(s.connected);
        });
      } catch {
        const goOn = () => setOnline(true);
        const goOff = () => setOnline(false);
        window.addEventListener("online", goOn);
        window.addEventListener("offline", goOff);
        networkSub = { remove: () => {
          window.removeEventListener("online", goOn);
          window.removeEventListener("offline", goOff);
        }};
      }
    })();

    return () => {
      cancelled = true;
      try { networkSub?.remove?.(); } catch {}
    };
  }, []);

  const takePhoto = useCallback(async () => {
    try {
      const Camera = (await import("@capacitor/camera")).Camera;
      const photo = await Camera.getPhoto({
        quality: 80,
        allowEditing: false,
        resultType: "dataUrl",
        source: "PROMPT",
      });
      return photo.dataUrl || null;
    } catch (e) {
      // Web fallback — file picker
      return new Promise((resolve) => {
        const input = document.createElement("input");
        input.type = "file";
        input.accept = "image/*";
        input.capture = "environment";
        input.onchange = () => {
          const file = input.files?.[0];
          if (!file) return resolve(null);
          const reader = new FileReader();
          reader.onload = () => resolve(reader.result);
          reader.readAsDataURL(file);
        };
        input.click();
      });
    }
  }, []);

  const requestPushPermission = useCallback(async () => {
    try {
      const PN = (await import("@capacitor/push-notifications")).PushNotifications;
      const result = await PN.requestPermissions();
      if (result.receive === "granted") {
        await PN.register();
        return true;
      }
      return false;
    } catch {
      return false;
    }
  }, []);

  const setNativePref = useCallback(async (key, value) => {
    try {
      const Preferences = (await import("@capacitor/preferences")).Preferences;
      await Preferences.set({ key, value });
    } catch {
      try { localStorage.setItem(key, value); } catch {}
    }
  }, []);

  const getNativePref = useCallback(async (key) => {
    try {
      const Preferences = (await import("@capacitor/preferences")).Preferences;
      const r = await Preferences.get({ key });
      return r.value;
    } catch {
      try { return localStorage.getItem(key); } catch { return null; }
    }
  }, []);

  return { isNative, platform, online, takePhoto, requestPushPermission, setNativePref, getNativePref };
}

export default useCapacitor;
