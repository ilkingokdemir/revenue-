import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Lightning,
  Lightbulb,
  Thermometer,
  Television,
  BellSlash,
  Leaf,
  ArrowsClockwise,
  ClockCounterClockwise,
  Snowflake,
  SquaresFour,
} from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

const SCENES = [
  ["welcome", "Karşılama", "bg-amber-500"],
  ["eco", "Eco", "bg-emerald-500"],
  ["night", "Gece", "bg-indigo-500"],
  ["checkout", "Çıkış", "bg-stone-500"],
];
const AC_MODES = ["off", "cool", "heat", "auto"];
const AC_LABEL = { off: "Kapalı", cool: "Soğutma", heat: "Isıtma", auto: "Oto" };

export default function SmartRoomsPanel({ properties = [], activePropertyId }) {
  const [propertyId, setPropertyId] = useState(activePropertyId || properties[0]?.id || "default");

  useEffect(() => {
    if (activePropertyId && activePropertyId !== "all") setPropertyId(activePropertyId);
  }, [activePropertyId]);

  const [rooms, setRooms] = useState([]);
  const [energy, setEnergy] = useState(null);
  const [report, setReport] = useState(null);
  const [tab, setTab] = useState("rooms");
  const [log, setLog] = useState([]);
  const [loading, setLoading] = useState(false);
  const [sweeping, setSweeping] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [r, e, rep] = await Promise.all([
        axios.get(`${API}/api/smart-rooms/${propertyId}`, { withCredentials: true }),
        axios.get(`${API}/api/smart-rooms/${propertyId}/energy/summary`, { withCredentials: true }),
        axios.get(`${API}/api/smart-rooms/${propertyId}/energy/report?months=6`, { withCredentials: true }),
      ]);
      setRooms(r.data.rooms || []);
      setEnergy(e.data);
      setReport(rep.data);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Odalar yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [propertyId]);

  const loadLog = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/api/smart-rooms/${propertyId}/actions/log?limit=100`, { withCredentials: true });
      setLog(r.data.rows || []);
    } catch (e) { /* noop */ }
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (tab === "log") loadLog(); }, [tab, loadLog]);

  const control = async (roomId, device, value) => {
    try {
      const r = await axios.post(`${API}/api/smart-rooms/${propertyId}/${roomId}/control`,
        { device, value }, { withCredentials: true });
      setRooms((prev) => prev.map((x) => x.room_id === roomId ? { ...x, devices: r.data.devices, scene: null } : x));
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Kontrol hatası");
    }
  };

  const applyScene = async (roomId, scene) => {
    try {
      const r = await axios.post(`${API}/api/smart-rooms/${propertyId}/${roomId}/scene`,
        { scene }, { withCredentials: true });
      setRooms((prev) => prev.map((x) => x.room_id === roomId ? { ...x, devices: r.data.devices, scene } : x));
      toast.success(`Sahne uygulandı: ${scene}`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Sahne hatası");
    }
  };

  const ecoSweep = async () => {
    setSweeping(true);
    try {
      const r = await axios.post(`${API}/api/smart-rooms/${propertyId}/eco-sweep`, {}, { withCredentials: true });
      toast.success(`${r.data.rooms_affected} boş oda eco moda alındı (~${r.data.kwh_saved} kWh tasarruf)`);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Eco sweep hatası");
    } finally {
      setSweeping(false);
    }
  };

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="smart-rooms-panel">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
            <Lightning size={12} weight="fill" className="text-emerald-500" />
            <span>Akıllı Oda · IoT Kontrol Merkezi</span>
          </div>
          <h1 className="text-2xl font-semibold text-stone-900">Oda Otomasyonu & Enerji Tasarrufu</h1>
          <p className="text-sm text-stone-500 mt-1 max-w-2xl">
            Işık, termostat, klima, perde, DND ve TV kontrolü. Boş odaları tek tıkla eco moda alın.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {properties.length > 1 && (
            <select value={propertyId} onChange={(e) => setPropertyId(e.target.value)}
              data-testid="smart-rooms-property-select"
              className="text-xs border border-stone-300 rounded-md px-2 py-2 bg-white">
              {properties.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          )}
          <button onClick={load} data-testid="smart-rooms-refresh"
            className="px-3 py-2 text-xs rounded-md border border-stone-300 text-stone-600 hover:bg-stone-100 inline-flex items-center gap-1.5">
            <ArrowsClockwise size={13} /> Yenile
          </button>
          <button onClick={ecoSweep} disabled={sweeping} data-testid="smart-rooms-eco-sweep"
            className="px-3 py-2 text-xs rounded-md bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50 inline-flex items-center gap-1.5 font-medium">
            <Leaf size={13} weight="fill" /> {sweeping ? "Uygulanıyor…" : "Eco Sweep (Boş Odalar)"}
          </button>
        </div>
      </div>

      {energy && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
          <Kpi label="Tasarruf (30g)" value={`${energy.kwh_saved_30d} kWh`} icon={Leaf} color="emerald" testId="smart-kpi-kwh" />
          <Kpi label="Maliyet Tasarrufu" value={`£${energy.cost_saved_30d}`} icon={Lightning} color="amber" testId="smart-kpi-cost" />
          <Kpi label="Eco Modda Oda" value={energy.eco_rooms} icon={Snowflake} color="sky" testId="smart-kpi-eco" />
          <Kpi label="Bugünkü İşlem" value={energy.actions_today} icon={ClockCounterClockwise} color="violet" testId="smart-kpi-actions" />
        </div>
      )}

      {report?.months?.length > 0 && (
        <div className="bg-white border border-stone-200 rounded-xl p-4 mb-5" data-testid="energy-monthly-report">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-xs font-semibold text-stone-700 flex items-center gap-1.5">
              <Leaf size={14} className="text-emerald-500" /> Aylık Enerji Tasarrufu (Eco Sweep)
            </h3>
            <span className="text-[10px] text-stone-400">
              6 ay: <b className="text-emerald-600">{report.total_kwh} kWh</b> · <b className="text-amber-600">£{report.total_cost_saved}</b> (£{report.rate_gbp_per_kwh}/kWh)
            </span>
          </div>
          <div className="flex items-end gap-2 h-24">
            {(() => {
              const max = Math.max(...report.months.map(m => m.kwh), 1);
              return report.months.map(m => (
                <div key={m.month} className="flex-1 flex flex-col items-center gap-0.5"
                  title={`${m.month}: ${m.kwh} kWh · £${m.cost_saved} · ${m.sweeps} sweep`}>
                  <span className="text-[9px] text-stone-500 font-semibold">{m.kwh > 0 ? `£${m.cost_saved}` : ""}</span>
                  <div className="w-full bg-emerald-400 hover:bg-emerald-500 rounded-t transition-colors"
                    style={{ height: `${Math.max(4, (m.kwh / max) * 100)}%` }} />
                  <span className="text-[8px] text-stone-400">{m.month.slice(5)}</span>
                </div>
              ));
            })()}
          </div>
        </div>
      )}

      <div className="flex gap-2 mb-4 border-b border-stone-200">
        <TabBtn active={tab === "rooms"} onClick={() => setTab("rooms")} testId="smart-tab-rooms">
          <SquaresFour size={14} className="inline mr-1.5" />Oda Kontrol ({rooms.length})
        </TabBtn>
        <TabBtn active={tab === "log"} onClick={() => setTab("log")} testId="smart-tab-log">
          <ClockCounterClockwise size={14} className="inline mr-1.5" />İşlem Günlüğü
        </TabBtn>
      </div>

      {tab === "rooms" && (
        loading ? <div className="text-sm text-stone-500 py-10 text-center">Yükleniyor…</div> :
        rooms.length === 0 ? <div className="text-sm text-stone-500 py-10 text-center" data-testid="smart-rooms-empty">Bu tesiste oda bulunamadı.</div> :
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {rooms.map((r) => (
            <RoomCard key={r.room_id} room={r} onControl={control} onScene={applyScene} />
          ))}
        </div>
      )}

      {tab === "log" && (
        <div className="bg-white border border-stone-200 rounded-lg divide-y divide-stone-100" data-testid="smart-rooms-log">
          {log.length === 0 && <div className="p-6 text-sm text-stone-500 text-center">Henüz işlem yok.</div>}
          {log.map((row) => (
            <div key={row.id} className="px-4 py-2.5 flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                  row.action === "eco_sweep" ? "bg-emerald-100 text-emerald-700" :
                  row.action === "scene" ? "bg-indigo-100 text-indigo-700" : "bg-stone-100 text-stone-600"}`}>
                  {row.action}
                </span>
                <span className="text-stone-700">{row.detail}</span>
              </div>
              <div className="text-stone-400 whitespace-nowrap ml-3">
                {row.by} · {new Date(row.at).toLocaleString("tr-TR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function RoomCard({ room, onControl, onScene }) {
  const d = room.devices || {};
  const occupied = room.status === "occupied";
  return (
    <div className="bg-white border border-stone-200 rounded-lg p-4 space-y-3" data-testid={`smart-room-card-${room.room_id}`}>
      <div className="flex items-center justify-between">
        <div>
          <div className="text-sm font-semibold text-stone-900">{room.name}</div>
          <div className="text-[11px] text-stone-500">Kat {room.floor ?? "-"} · HK: {room.housekeeping || "-"}</div>
        </div>
        <div className="flex items-center gap-1.5">
          {room.scene && (
            <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-indigo-100 text-indigo-700" data-testid={`smart-room-scene-${room.room_id}`}>
              {room.scene}
            </span>
          )}
          <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${occupied ? "bg-rose-100 text-rose-700" : "bg-emerald-100 text-emerald-700"}`}>
            {occupied ? "Dolu" : "Boş"}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2">
        <Toggle icon={Lightbulb} label="Işık" on={!!d.lights} testId={`smart-light-${room.room_id}`}
          onClick={() => onControl(room.room_id, "lights", !d.lights)} />
        <Toggle icon={Television} label="TV" on={!!d.tv} testId={`smart-tv-${room.room_id}`}
          onClick={() => onControl(room.room_id, "tv", !d.tv)} />
        <Toggle icon={BellSlash} label="DND" on={!!d.dnd} testId={`smart-dnd-${room.room_id}`}
          onClick={() => onControl(room.room_id, "dnd", !d.dnd)} />
      </div>

      <div className="flex items-center justify-between gap-2 bg-stone-50 rounded-md px-3 py-2">
        <div className="flex items-center gap-1.5 text-xs text-stone-600">
          <Thermometer size={14} className="text-orange-500" />
          <button onClick={() => onControl(room.room_id, "thermostat", Math.max(16, (d.thermostat || 21) - 1))}
            data-testid={`smart-temp-down-${room.room_id}`}
            className="w-6 h-6 rounded border border-stone-300 bg-white hover:bg-stone-100 font-bold">−</button>
          <span className="font-semibold text-stone-900 w-10 text-center" data-testid={`smart-temp-${room.room_id}`}>{d.thermostat}°</span>
          <button onClick={() => onControl(room.room_id, "thermostat", Math.min(30, (d.thermostat || 21) + 1))}
            data-testid={`smart-temp-up-${room.room_id}`}
            className="w-6 h-6 rounded border border-stone-300 bg-white hover:bg-stone-100 font-bold">+</button>
        </div>
        <button
          onClick={() => onControl(room.room_id, "ac_mode", AC_MODES[(AC_MODES.indexOf(d.ac_mode || "auto") + 1) % AC_MODES.length])}
          data-testid={`smart-ac-${room.room_id}`}
          className="text-[11px] px-2 py-1 rounded border border-stone-300 bg-white hover:bg-stone-100 text-stone-600">
          Klima: {AC_LABEL[d.ac_mode] || d.ac_mode}
        </button>
        <button onClick={() => onControl(room.room_id, "curtains", d.curtains === "open" ? "closed" : "open")}
          data-testid={`smart-curtains-${room.room_id}`}
          className="text-[11px] px-2 py-1 rounded border border-stone-300 bg-white hover:bg-stone-100 text-stone-600">
          Perde: {d.curtains === "open" ? "Açık" : "Kapalı"}
        </button>
      </div>

      <div className="flex gap-1.5">
        {SCENES.map(([key, label, color]) => (
          <button key={key} onClick={() => onScene(room.room_id, key)}
            data-testid={`smart-scene-${key}-${room.room_id}`}
            className={`flex-1 py-1.5 rounded-md text-[11px] font-medium text-white ${color} hover:opacity-85 ${room.scene === key ? "ring-2 ring-offset-1 ring-stone-400" : ""}`}>
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}

function Toggle({ icon: Icon, label, on, onClick, testId }) {
  return (
    <button onClick={onClick} data-testid={testId}
      className={`py-2 rounded-md border text-xs font-medium inline-flex flex-col items-center gap-1 transition-colors ${
        on ? "bg-stone-900 text-white border-stone-900" : "bg-white text-stone-500 border-stone-200 hover:border-stone-400"}`}>
      <Icon size={16} weight={on ? "fill" : "regular"} />
      {label}
    </button>
  );
}

function Kpi({ label, value, icon: Icon, color, testId }) {
  const colors = {
    emerald: "text-emerald-600 bg-emerald-50",
    amber: "text-amber-600 bg-amber-50",
    sky: "text-sky-600 bg-sky-50",
    violet: "text-violet-600 bg-violet-50",
  };
  return (
    <div className="bg-white border border-stone-200 rounded-lg p-3.5 flex items-center gap-3" data-testid={testId}>
      <div className={`w-9 h-9 rounded-md flex items-center justify-center ${colors[color]}`}>
        <Icon size={18} weight="fill" />
      </div>
      <div>
        <div className="text-lg font-bold text-stone-900 leading-tight">{value}</div>
        <div className="text-[11px] text-stone-500">{label}</div>
      </div>
    </div>
  );
}

function TabBtn({ active, onClick, children, testId }) {
  return (
    <button onClick={onClick} data-testid={testId}
      className={`px-3 py-2 text-xs font-medium border-b-2 -mb-px transition-colors ${
        active ? "border-stone-900 text-stone-900" : "border-transparent text-stone-500 hover:text-stone-700"}`}>
      {children}
    </button>
  );
}
