/**
 * SiteMinderPanel (iter 375) — Middleware Translator Adapter
 *
 * SiteMinder kanal kodu eşlemeleri + çeviri log görünümü + test webhook.
 */
import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Plug, ArrowLeftRight, ScrollText, Save, RefreshCw, Send, CheckCircle2,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const INTERNAL_CHANNELS = ["booking_com", "expedia", "airbnb", "agoda", "trip_com", "direct"];

export default function SiteMinderPanel({ activePropertyId }) {
  const [tab, setTab] = useState("mappings");
  return (
    <div className="p-6 max-w-[1200px] mx-auto" data-testid="siteminder-panel">
      <div className="mb-5">
        <div className="text-xs uppercase tracking-widest text-stone-500 mb-1 flex items-center gap-1.5">
          <Plug className="w-3 h-3 text-emerald-500" /> Middleware
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">SiteMinder Translator Adapter</h1>
        <p className="text-sm text-stone-500 mt-1 max-w-2xl">
          SiteMinder 450+ OTA'yı tek webhook'ta toplar. Bu adaptör gelen JSON/XML rezervasyonları
          iç kanal formatına çevirir ve otomatik oda atama pipeline'ına besler.
        </p>
        <div className="mt-2 text-xs font-mono bg-stone-100 border border-stone-200 rounded px-3 py-1.5 inline-block text-stone-600">
          POST {API}/siteminder/webhook
        </div>
      </div>

      <div className="flex gap-2 mb-5 border-b border-stone-200">
        <TabBtn active={tab === "mappings"} onClick={() => setTab("mappings")} testId="sm-tab-mappings">
          <ArrowLeftRight className="w-4 h-4 inline mr-1.5" /> Kanal Eşlemeleri
        </TabBtn>
        <TabBtn active={tab === "log"} onClick={() => setTab("log")} testId="sm-tab-log">
          <ScrollText className="w-4 h-4 inline mr-1.5" /> Çeviri Logu
        </TabBtn>
      </div>

      {tab === "mappings" && <MappingsTab activePropertyId={activePropertyId} />}
      {tab === "log" && <LogTab />}
    </div>
  );
}

const TabBtn = ({ active, onClick, children, testId }) => (
  <button onClick={onClick} data-testid={testId}
    className={`px-4 py-2.5 text-sm font-semibold transition -mb-px border-b-2 ${
      active ? "border-emerald-600 text-emerald-700" : "border-transparent text-stone-500 hover:text-stone-700"
    }`}>{children}</button>
);

/* ═══════════ MAPPINGS TAB ═══════════ */
const MappingsTab = ({ activePropertyId }) => {
  const [items, setItems] = useState(null);
  const [newCode, setNewCode] = useState("");
  const [newChannel, setNewChannel] = useState("booking_com");
  const [testing, setTesting] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/siteminder/mappings`);
      setItems(r.data.items || []);
    } catch (e) {
      toast.error("Yüklenemedi: " + (e.response?.data?.detail || e.message));
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  const saveMapping = async () => {
    if (!newCode.trim()) return toast.error("Kanal kodu girin");
    try {
      await axios.put(`${API}/siteminder/mappings`, { code: newCode.trim(), channel: newChannel });
      toast.success(`Eşleme kaydedildi: ${newCode.toUpperCase()} → ${newChannel}`);
      setNewCode("");
      load();
    } catch (e) {
      toast.error("Kaydedilemedi: " + (e.response?.data?.detail || e.message));
    }
  };

  const sendTest = async () => {
    setTesting(true);
    try {
      const r = await axios.post(`${API}/siteminder/webhook`, {
        event: "reservation",
        reservation_id: "SM-TEST-" + Date.now().toString().slice(-6),
        channel_code: "BDC",
        property_id: activePropertyId && activePropertyId !== "all" ? activePropertyId : "default",
        guest_name: "SiteMinder Test Misafiri",
        guest_email: "sm-test@example.com",
        check_in: new Date(Date.now() + 7 * 864e5).toISOString().slice(0, 10),
        check_out: new Date(Date.now() + 9 * 864e5).toISOString().slice(0, 10),
        total_price: 240,
        currency: "GBP",
      });
      toast.success(`Test OK — booking ${r.data.action}, oda: ${r.data.room_number || "atanamadı"}`);
    } catch (e) {
      toast.error("Test başarısız: " + (e.response?.data?.detail || e.message));
    }
    setTesting(false);
  };

  if (!items) return <div className="text-sm text-stone-400">Yükleniyor…</div>;

  return (
    <div data-testid="sm-mappings-tab">
      <div className="flex flex-wrap items-end gap-3 mb-5 bg-white border border-stone-200 rounded-xl p-4">
        <div>
          <label className="block text-xs font-medium text-stone-500 mb-1">SiteMinder Kodu</label>
          <input value={newCode} onChange={(e) => setNewCode(e.target.value)} placeholder="örn. HRS"
            data-testid="sm-new-code-input"
            className="border border-stone-300 rounded-lg px-3 py-2 text-sm w-36 focus:outline-none focus:ring-2 focus:ring-emerald-500" />
        </div>
        <div>
          <label className="block text-xs font-medium text-stone-500 mb-1">İç Kanal</label>
          <select value={newChannel} onChange={(e) => setNewChannel(e.target.value)}
            data-testid="sm-new-channel-select"
            className="border border-stone-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500">
            {INTERNAL_CHANNELS.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <button onClick={saveMapping} data-testid="sm-save-mapping-btn"
          className="flex items-center gap-2 px-4 py-2 bg-emerald-700 text-white text-sm font-semibold rounded-lg hover:bg-emerald-800 transition-colors">
          <Save className="w-4 h-4" /> Eşleme Ekle
        </button>
        <button onClick={sendTest} disabled={testing} data-testid="sm-test-webhook-btn"
          className="flex items-center gap-2 px-4 py-2 border border-stone-300 text-stone-700 text-sm font-semibold rounded-lg hover:bg-stone-50 disabled:opacity-50 transition-colors ml-auto">
          <Send className={`w-4 h-4 ${testing ? "animate-pulse" : ""}`} /> Test Webhook Gönder
        </button>
      </div>

      <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-stone-50 text-xs uppercase tracking-wide text-stone-500">
            <tr>
              <th className="text-left px-4 py-3">SiteMinder Kodu</th>
              <th className="text-left px-4 py-3">İç Kanal</th>
              <th className="text-left px-4 py-3">Tip</th>
            </tr>
          </thead>
          <tbody>
            {items.map((m) => (
              <tr key={m.code} className="border-t border-stone-100">
                <td className="px-4 py-2.5 font-mono text-xs font-semibold text-stone-700">{m.code}</td>
                <td className="px-4 py-2.5 text-stone-600">{m.channel}</td>
                <td className="px-4 py-2.5">
                  <span className={`text-xs px-2 py-0.5 rounded-full border ${
                    m.default ? "bg-stone-50 text-stone-500 border-stone-200" : "bg-emerald-50 text-emerald-700 border-emerald-200"
                  }`}>{m.default ? "varsayılan" : "override"}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

/* ═══════════ LOG TAB ═══════════ */
const LogTab = () => {
  const [items, setItems] = useState(null);

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/siteminder/log`);
      setItems(r.data.items || []);
    } catch (e) {
      toast.error("Yüklenemedi: " + (e.response?.data?.detail || e.message));
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  if (!items) return <div className="text-sm text-stone-400">Yükleniyor…</div>;

  return (
    <div data-testid="sm-log-tab">
      <div className="flex justify-end mb-3">
        <button onClick={load} data-testid="sm-log-refresh-btn"
          className="flex items-center gap-1.5 text-xs text-stone-500 hover:text-stone-700">
          <RefreshCw className="w-3.5 h-3.5" /> Yenile
        </button>
      </div>
      {items.length === 0 ? (
        <div className="text-center py-16 text-stone-400 text-sm">Henüz çeviri olayı yok.</div>
      ) : (
        <div className="space-y-2">
          {items.map((l) => (
            <div key={l.id} className="bg-white border border-stone-200 rounded-lg px-4 py-3 flex items-center gap-4 text-sm">
              <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
              <div className="font-mono text-xs text-stone-500">{l.channel_code}</div>
              <ArrowLeftRight className="w-3 h-3 text-stone-300" />
              <div className="font-semibold text-stone-700">{l.resolved_channel}</div>
              <div className="text-stone-400 text-xs">{l.event} · {l.format} · ref {l.reservation_id}</div>
              <div className="ml-auto text-xs text-stone-400">{(l.received_at || "").slice(0, 19).replace("T", " ")}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
