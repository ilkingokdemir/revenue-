// Offline action queue (iter 388) — queues whitelisted write requests while
// offline and replays them automatically when connection returns.
import axios from "axios";
import { toast } from "sonner";

const QUEUE_KEY = "offline_action_queue_v1";

// Only queue safe-to-replay operational writes (idempotent-ish updates)
const QUEUE_PATTERNS = [
  /\/api\/housekeeping\/tasks\/[^/]+$/,          // PUT task update (status vb.)
  /\/api\/housekeeping\/rooms\/[^/]+\/status$/,  // PUT room status
  /\/api\/housekeeping\/maintenance(\/[^/]+)?$/, // POST/PUT maintenance
  /\/api\/maintenance\/issues\/[^/]+$/,          // PUT issue update
];

const readQueue = () => {
  try { return JSON.parse(localStorage.getItem(QUEUE_KEY) || "[]"); } catch { return []; }
};
const writeQueue = (q) => {
  localStorage.setItem(QUEUE_KEY, JSON.stringify(q));
  window.dispatchEvent(new CustomEvent("offline-queue-changed", { detail: { count: q.length } }));
};

export const getQueueCount = () => readQueue().length;

const isQueueable = (config) => {
  const method = (config.method || "").toLowerCase();
  if (!["post", "put", "patch"].includes(method)) return false;
  const url = config.url || "";
  return QUEUE_PATTERNS.some((p) => p.test(url));
};

const isNetworkError = (error) => !error.response;

let flushing = false;

export async function flushQueue() {
  if (flushing) return;
  const q = readQueue();
  if (q.length === 0) return;
  flushing = true;
  let ok = 0, dropped = 0;
  const remaining = [];
  for (const item of q) {
    try {
      await axios.request({ method: item.method, url: item.url, data: item.data,
        headers: { "X-Offline-Replay": "1" } });
      ok += 1;
    } catch (e) {
      if (e.response && e.response.status >= 400 && e.response.status < 500) {
        dropped += 1; // server rejected — don't retry forever
      } else {
        remaining.push(item); // still offline / 5xx — keep
      }
    }
  }
  writeQueue(remaining);
  flushing = false;
  if (ok > 0) toast.success(`🔄 ${ok} bekleyen işlem senkronize edildi`);
  if (dropped > 0) toast.error(`${dropped} işlem sunucu tarafından reddedildi`);
}

export function installOfflineQueue() {
  axios.interceptors.response.use(
    (r) => r,
    (error) => {
      const cfg = error.config || {};
      if (isNetworkError(error) && isQueueable(cfg) && !cfg.headers?.["X-Offline-Replay"]) {
        const q = readQueue();
        q.push({ method: cfg.method, url: cfg.url,
                 data: typeof cfg.data === "string" ? JSON.parse(cfg.data || "{}") : (cfg.data || {}),
                 queued_at: new Date().toISOString() });
        writeQueue(q);
        toast.info("📶 Çevrimdışı — işlem kuyruğa alındı, bağlantı gelince gönderilecek");
        // synthetic response so UI flows don't crash
        return Promise.resolve({ data: { queued: true, offline: true }, status: 202,
                                 statusText: "Queued (offline)", headers: {}, config: cfg });
      }
      return Promise.reject(error);
    }
  );
  window.addEventListener("online", () => setTimeout(flushQueue, 1500));
  if (navigator.onLine) setTimeout(flushQueue, 3000); // flush leftovers on boot
  window.__offlineQueue = { flushQueue, getQueueCount, axios }; // debug/test hook
}
