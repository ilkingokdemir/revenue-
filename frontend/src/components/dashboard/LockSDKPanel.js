import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Lock,
  Key,
  ArrowsClockwise,
  Lightning,
  ShieldCheck,
  BatteryHigh,
  WifiSlash,
  WarningCircle,
  CheckCircle,
  Plus,
  Trash,
  Pulse,
} from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

export default function LockSDKPanel({ propertyId = "default" }) {
  const [tab, setTab] = useState("health");
  const [test, setTest] = useState(null);
  const [health, setHealth] = useState(null);
  const [audit, setAudit] = useState([]);
  const [busy, setBusy] = useState(false);
  const [encodeForm, setEncodeForm] = useState({
    booking_ref: "",
    room_number: "",
    guest_name: "",
    valid_from: new Date().toISOString().slice(0, 10),
    valid_until: new Date(Date.now() + 86400000).toISOString().slice(0, 10),
    mobile_key: false,
  });
  const [simEv, setSimEv] = useState({ room_number: "", event_type: "entry", actor: "guest" });

  const reload = useCallback(async () => {
    try {
      const [t, h, a] = await Promise.all([
        axios.get(`${API}/api/lock-sdk/test/${propertyId}`, { withCredentials: true }),
        axios.get(`${API}/api/lock-sdk/health/${propertyId}`, { withCredentials: true }),
        axios.get(`${API}/api/lock-sdk/audit/${propertyId}?limit=100`, { withCredentials: true }),
      ]);
      setTest(t.data);
      setHealth(h.data);
      setAudit(a.data.items || []);
    } catch (e) {
      toast.error("Lock SDK verisi yüklenemedi");
    }
  }, [propertyId]);

  useEffect(() => {
    reload();
  }, [reload]);

  const encode = async () => {
    if (!encodeForm.booking_ref || !encodeForm.room_number) {
      toast.error("Booking ref ve oda numarası gerekli");
      return;
    }
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/lock-sdk/encode-card/${propertyId}`, encodeForm, {
        withCredentials: true,
      });
      const p = r.data.card_payload || {};
      toast.success(
        encodeForm.mobile_key
          ? `Mobile key oluşturuldu (BLE token ${p.ble_token?.slice(0, 8)}…)`
          : `Kart kodlandı: ${p.card_id}`
      );
      reload();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Kodlama başarısız");
    } finally {
      setBusy(false);
    }
  };

  const simulate = async () => {
    if (!simEv.room_number) return toast.error("Oda numarası girin");
    try {
      await axios.post(`${API}/api/lock-sdk/simulate-event/${propertyId}`, simEv, { withCredentials: true });
      toast.success("Simülasyon olayı eklendi");
      reload();
    } catch (e) {
      toast.error("Eklenemedi");
    }
  };

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="lock-sdk-panel">
      <div className="mb-5 flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
            <Lock size={12} weight="fill" className="text-violet-500" />
            <span>Operations · Hardware Lock SDK</span>
          </div>
          <h1 className="text-2xl font-semibold text-stone-900">Donanım kilit SDK</h1>
          <p className="text-sm text-stone-500 mt-1 max-w-2xl">
            Salto, ASSA ABLOY, Onity, dormakaba, TTLock, Nuki ve August/Yale entegrasyonu.
            Anahtar/kart kodla, mobil anahtar üret, denetim günlüğünü izle. Gerçek SDK olmadığında
            yerleşik simülatör devreye girer.
          </p>
        </div>
        <button onClick={reload} className="px-3 py-2 bg-stone-100 text-stone-700 rounded-md text-sm hover:bg-stone-200 flex items-center gap-2" data-testid="lock-refresh">
          <ArrowsClockwise size={14} /> Yenile
        </button>
      </div>

      {test && (
        <div className={`mb-4 p-3 border rounded-md text-sm flex items-center gap-2 ${
          test.use_simulator ? "bg-amber-50 border-amber-200 text-amber-800" : "bg-emerald-50 border-emerald-200 text-emerald-800"
        }`} data-testid="lock-status-banner">
          {test.use_simulator ? <Pulse size={14} weight="fill" /> : <ShieldCheck size={14} weight="fill" />}
          <span><b>Provider:</b> {test.provider} — {test.message}</span>
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-5" data-testid="lock-kpis">
        <Kpi label="Toplam kilit" value={health?.total_locks ?? 0} icon={Lock} />
        <Kpi label="Online" value={health?.online ?? 0} icon={ShieldCheck} tone="ok" />
        <Kpi label="Offline" value={health?.offline ?? 0} icon={WifiSlash} tone={health?.offline ? "bad" : "neutral"} />
        <Kpi label="Pil düşük" value={health?.battery_low ?? 0} icon={BatteryHigh} tone={health?.battery_low ? "warn" : "neutral"} />
        <Kpi label="Uptime %" value={`${health?.uptime_pct ?? 0}%`} icon={Pulse} tone="ok" />
      </div>

      <div className="flex border-b border-stone-200 mb-4">
        {[["health", "Kilit sağlığı"], ["encode", "Kart/anahtar kodla"], ["audit", "Denetim günlüğü"], ["sim", "Simülasyon"]].map(([k, l]) => (
          <button key={k} onClick={() => setTab(k)} data-testid={`lock-tab-${k}`}
            className={`px-4 py-2 text-sm border-b-2 ${tab === k ? "border-indigo-600 text-indigo-700 font-medium" : "border-transparent text-stone-500 hover:text-stone-800"}`}>
            {l}
          </button>
        ))}
      </div>

      {tab === "health" && (
        <div className="bg-white border border-stone-200 rounded-lg p-3 max-h-[420px] overflow-auto" data-testid="lock-fleet">
          <table className="w-full text-sm">
            <thead><tr className="text-left text-xs text-stone-500 border-b border-stone-200">
              <th className="py-2 pr-2">Oda</th><th className="py-2 pr-2">Durum</th><th className="py-2 pr-2">Pil</th><th className="py-2 pr-2">İletişim</th><th className="py-2 pr-2">Son görülme</th>
            </tr></thead>
            <tbody>
              {(health?.fleet || []).map((f) => (
                <tr key={f.room} className="border-b border-stone-100">
                  <td className="py-1.5 pr-2 font-mono">{f.room}</td>
                  <td className="py-1.5 pr-2">
                    {f.online ? <span className="text-emerald-700 inline-flex items-center gap-1 text-xs"><CheckCircle size={12} weight="fill" /> Online</span>
                              : <span className="text-red-700 inline-flex items-center gap-1 text-xs"><WifiSlash size={12} weight="fill" /> Offline</span>}
                  </td>
                  <td className="py-1.5 pr-2"><span className={f.battery_pct < 30 ? "text-amber-700 font-mono" : "font-mono text-stone-700"}>{f.battery_pct}%</span></td>
                  <td className="py-1.5 pr-2 font-mono">{f.comms_quality}/100</td>
                  <td className="py-1.5 pr-2 font-mono text-[11px] text-stone-500">{(f.last_seen || "").replace("T", " ").slice(0, 16)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "encode" && (
        <div className="bg-white border border-stone-200 rounded-lg p-5 space-y-3 max-w-2xl" data-testid="lock-encode-form">
          <div className="grid grid-cols-2 gap-3">
            <Field label="Booking ref" v={encodeForm.booking_ref} setV={(v) => setEncodeForm({ ...encodeForm, booking_ref: v })} testId="encode-booking" />
            <Field label="Oda no" v={encodeForm.room_number} setV={(v) => setEncodeForm({ ...encodeForm, room_number: v })} testId="encode-room" />
            <Field label="Misafir adı" v={encodeForm.guest_name} setV={(v) => setEncodeForm({ ...encodeForm, guest_name: v })} testId="encode-guest" />
            <div className="flex items-center gap-2 pt-5">
              <label className="flex items-center gap-2 text-sm" data-testid="encode-mobile">
                <input type="checkbox" checked={encodeForm.mobile_key} onChange={(e) => setEncodeForm({ ...encodeForm, mobile_key: e.target.checked })} />
                Mobil anahtar (BLE)
              </label>
            </div>
            <Field label="Geçerlilik başlangıç" v={encodeForm.valid_from} setV={(v) => setEncodeForm({ ...encodeForm, valid_from: v })} type="date" testId="encode-from" />
            <Field label="Geçerlilik bitiş" v={encodeForm.valid_until} setV={(v) => setEncodeForm({ ...encodeForm, valid_until: v })} type="date" testId="encode-to" />
          </div>
          <button onClick={encode} disabled={busy} data-testid="encode-submit"
            className="px-4 py-2 bg-indigo-600 text-white rounded text-sm hover:bg-indigo-700 disabled:opacity-50 flex items-center gap-2">
            <Key size={14} weight="fill" /> {busy ? "Kodlanıyor…" : "Kart/anahtar oluştur"}
          </button>
        </div>
      )}

      {tab === "audit" && (
        <div className="bg-white border border-stone-200 rounded-lg p-3" data-testid="lock-audit">
          <table className="w-full text-sm">
            <thead><tr className="text-left text-xs text-stone-500 border-b border-stone-200">
              <th className="py-2 pr-2">Zaman</th><th className="py-2 pr-2">Olay</th><th className="py-2 pr-2">Oda</th><th className="py-2 pr-2">Aktör</th><th className="py-2 pr-2">Kaynak</th>
            </tr></thead>
            <tbody>
              {audit.map((e) => (
                <tr key={e.id} className="border-b border-stone-100">
                  <td className="py-1.5 pr-2 font-mono text-[11px]">{(e.timestamp || "").replace("T", " ").slice(0, 19)}</td>
                  <td className="py-1.5 pr-2"><EventPill t={e.event_type} /></td>
                  <td className="py-1.5 pr-2 font-mono">{e.room_number || "—"}</td>
                  <td className="py-1.5 pr-2">{e.actor || "—"}</td>
                  <td className="py-1.5 pr-2 text-xs text-stone-500">{e.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "sim" && (
        <div className="bg-white border border-stone-200 rounded-lg p-5 space-y-3 max-w-xl" data-testid="lock-sim">
          <p className="text-xs text-stone-500">Simülasyon olayları gerçek bir kapı açılışı/reddi varmış gibi günlüğe yazılır.</p>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Oda" v={simEv.room_number} setV={(v) => setSimEv({ ...simEv, room_number: v })} testId="sim-room" />
            <div>
              <label className="text-xs text-stone-500 mb-1 block">Olay türü</label>
              <select value={simEv.event_type} onChange={(e) => setSimEv({ ...simEv, event_type: e.target.value })} className="w-full text-sm border border-stone-200 rounded px-3 py-1.5" data-testid="sim-type">
                <option value="entry">entry</option>
                <option value="denied">denied</option>
                <option value="battery_low">battery_low</option>
                <option value="offline">offline</option>
                <option value="online">online</option>
              </select>
            </div>
          </div>
          <button onClick={simulate} className="px-4 py-2 bg-amber-500 text-white rounded text-sm hover:bg-amber-600" data-testid="sim-submit">
            <Lightning size={14} className="inline mr-1" /> Olayı tetikle
          </button>
        </div>
      )}
    </div>
  );
}

const Kpi = ({ label, value, icon: Icon, tone }) => (
  <div className={`bg-white border rounded-lg p-3 ${
    tone === "ok" ? "border-emerald-200" : tone === "bad" ? "border-red-200" : tone === "warn" ? "border-amber-200" : "border-stone-200"
  }`}>
    <div className="flex items-center justify-between text-stone-500 mb-1">
      <span className="text-[10px] uppercase tracking-wide">{label}</span>{Icon && <Icon size={14} />}
    </div>
    <div className="text-lg font-semibold text-stone-900">{value}</div>
  </div>
);

const Field = ({ label, v, setV, type = "text", testId }) => (
  <div>
    <label className="text-xs text-stone-500 mb-1 block">{label}</label>
    <input type={type} value={v} onChange={(e) => setV(e.target.value)}
      className="w-full text-sm border border-stone-200 rounded px-3 py-1.5" data-testid={testId} />
  </div>
);

const EventPill = ({ t }) => {
  const map = {
    entry: "bg-emerald-100 text-emerald-700",
    denied: "bg-red-100 text-red-700",
    battery_low: "bg-amber-100 text-amber-700",
    offline: "bg-stone-200 text-stone-700",
    online: "bg-sky-100 text-sky-700",
    encode: "bg-violet-100 text-violet-700",
    revoke: "bg-rose-100 text-rose-700",
  };
  return <span className={`text-[10px] px-2 py-0.5 rounded font-medium ${map[t] || "bg-stone-100 text-stone-700"}`}>{t}</span>;
};
