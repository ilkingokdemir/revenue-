import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { CalendarBlank, LinkSimple, Copy, Trash, ArrowsClockwise, Plus, WarningCircle, CheckCircle } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function IcalSyncPanel({ activePropertyId, properties }) {
  const pid = activePropertyId && activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default");
  const [sources, setSources] = useState([]);
  const [rooms, setRooms] = useState([]);
  const [roomTypes, setRoomTypes] = useState([]);
  const [token, setToken] = useState("");
  const [form, setForm] = useState({ room_id: "", channel_name: "Airbnb", url: "" });
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/ical/${pid}`);
      setSources(data.sources || []);
      setRooms(data.rooms || []);
      setRoomTypes(data.room_types || []);
      setToken(data.export_token || "");
      if (!form.room_id && data.rooms?.length) setForm((f) => ({ ...f, room_id: data.rooms[0].id }));
    } catch { toast.error("Yüklenemedi"); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pid]);

  useEffect(() => { load(); }, [load]);

  const exportBase = `${process.env.REACT_APP_BACKEND_URL}/api/ical/export/${pid}.ics?token=${token}`;

  const copy = async (text) => {
    try { await navigator.clipboard.writeText(text); toast.success("Kopyalandı"); }
    catch { toast.error("Pano erişimi engellendi — linki elle kopyalayın"); }
  };

  const addSource = async () => {
    if (!form.url.trim()) { toast.error("iCal URL girin"); return; }
    setBusy(true);
    try {
      const { data } = await axios.post(`${API}/ical/${pid}/sources`, form);
      const fs = data.first_sync;
      toast.success(fs.status === "ok" ? `Bağlandı — ${fs.blocks} blok içe aktarıldı` : `Kaynak eklendi, ilk senkron hatası: ${fs.error}`);
      setForm({ ...form, url: "" });
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Eklenemedi"); }
    setBusy(false);
  };

  const syncAll = async () => {
    setBusy(true);
    try {
      const { data } = await axios.post(`${API}/ical/${pid}/sync`);
      const ok = data.results.filter((r) => r.status === "ok").length;
      toast.success(`${ok}/${data.results.length} kaynak senkronlandı`);
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Senkron başarısız"); }
    setBusy(false);
  };

  const remove = async (sid) => {
    try {
      const { data } = await axios.delete(`${API}/ical/${pid}/sources/${sid}`);
      toast.success(`Kaynak silindi (${data.blocks_removed} blok kaldırıldı)`);
      load();
    } catch { toast.error("Silinemedi"); }
  };

  const inputCls = "w-full rounded-lg border border-stone-200 px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-cyan-600";

  return (
    <div className="p-6 max-w-4xl" data-testid="ical-sync-panel">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-stone-800">iCal Senkronu</h2>
          <p className="text-xs text-stone-500 mt-1">API'siz kanallar için takvim senkronu — Airbnb/Vrbo iCal URL'sini yapıştırın, dolu tarihler anında takvim bloğu olur. 4 saatte bir otomatik yenilenir.</p>
        </div>
        <button onClick={syncAll} disabled={busy} data-testid="ical-sync-all-btn"
          className="px-4 py-2 rounded-lg bg-stone-900 text-white text-xs font-bold hover:bg-stone-700 disabled:opacity-50 flex items-center gap-1.5">
          <ArrowsClockwise size={13} /> Şimdi Senkronla
        </button>
      </div>

      {/* DIŞA AKTAR */}
      <div className="bg-white rounded-2xl border border-stone-200 p-5 shadow-sm mb-5" data-testid="ical-export-card">
        <div className="flex items-center gap-2 mb-2">
          <LinkSimple size={16} weight="bold" className="text-cyan-700" />
          <h3 className="text-sm font-bold text-stone-800">Dışa aktarma (takvimimizi kanala verin)</h3>
        </div>
        <p className="text-[11px] text-stone-500 mb-3">Bu URL'yi Airbnb → Takvim → "Başka takvimi içe aktar" alanına yapıştırın; rezervasyonlarımız orada dolu görünür.</p>
        <div className="flex items-center gap-1.5 mb-2">
          <input readOnly value={exportBase} data-testid="ical-export-url"
            className="flex-1 min-w-0 rounded bg-stone-50 border border-stone-200 px-2 py-1.5 text-[10px] font-mono text-stone-600 truncate" />
          <button onClick={() => copy(exportBase)} data-testid="ical-export-copy-btn"
            className="p-2 rounded bg-stone-100 hover:bg-stone-200 text-stone-600"><Copy size={13} /></button>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {roomTypes.map((rt) => (
            <button key={rt.id} onClick={() => copy(`${exportBase}&room_type_id=${rt.id}`)}
              data-testid={`ical-export-rt-${rt.id}`}
              className="text-[10px] px-2 py-1 rounded-full bg-cyan-50 text-cyan-800 border border-cyan-200 hover:bg-cyan-100">
              {rt.name} feed'i kopyala
            </button>
          ))}
        </div>
      </div>

      {/* İÇE AKTAR */}
      <div className="bg-white rounded-2xl border border-stone-200 p-5 shadow-sm mb-5" data-testid="ical-import-card">
        <div className="flex items-center gap-2 mb-3">
          <CalendarBlank size={16} weight="bold" className="text-cyan-700" />
          <h3 className="text-sm font-bold text-stone-800">İçe aktarma (Airbnb takvimini bağla)</h3>
        </div>
        <div className="grid sm:grid-cols-3 gap-2">
          <select value={form.room_id} onChange={(e) => setForm({ ...form, room_id: e.target.value })}
            className={inputCls} data-testid="ical-room-select">
            {rooms.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
          </select>
          <input value={form.channel_name} onChange={(e) => setForm({ ...form, channel_name: e.target.value })}
            placeholder="Kanal adı (Airbnb, Vrbo...)" className={inputCls} data-testid="ical-channel-input" />
          <input value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })}
            placeholder="https://www.airbnb.com/calendar/ical/....ics" className={inputCls} data-testid="ical-url-input" />
        </div>
        <button onClick={addSource} disabled={busy} data-testid="ical-add-source-btn"
          className="mt-3 px-4 py-2 rounded-lg bg-cyan-700 text-white text-xs font-bold hover:bg-cyan-800 disabled:opacity-50 flex items-center gap-1.5">
          <Plus size={13} weight="bold" /> Bağla ve Senkronla
        </button>
      </div>

      {/* KAYNAKLAR */}
      <div className="space-y-2" data-testid="ical-sources-list">
        {sources.length === 0 && <p className="text-[11px] text-stone-400">Henüz iCal kaynağı bağlanmadı.</p>}
        {sources.map((s) => (
          <div key={s.id} className="bg-white rounded-xl border border-stone-200 px-4 py-3 flex items-center gap-3" data-testid={`ical-source-${s.id}`}>
            {s.last_status === "ok"
              ? <CheckCircle size={16} weight="fill" className="text-emerald-500 flex-shrink-0" />
              : <WarningCircle size={16} weight="fill" className={`flex-shrink-0 ${s.last_status === "error" ? "text-red-500" : "text-amber-400"}`} />}
            <div className="flex-1 min-w-0">
              <div className="text-xs font-bold text-stone-800">{s.channel_name} → {s.room_name}</div>
              <div className="text-[10px] text-stone-400 font-mono truncate">{s.url}</div>
              {s.last_status === "error" && <div className="text-[10px] text-red-500 truncate">{s.last_error}</div>}
            </div>
            <div className="text-right flex-shrink-0">
              <div className="text-[10px] font-bold text-stone-600" data-testid={`ical-blocks-${s.id}`}>{s.blocks_count || 0} blok</div>
              <div className="text-[9px] text-stone-400">{s.last_sync ? s.last_sync.slice(0, 16).replace("T", " ") : "senkron bekliyor"}</div>
            </div>
            <button onClick={() => remove(s.id)} data-testid={`ical-delete-${s.id}`}
              className="p-1.5 rounded text-stone-400 hover:text-red-500 hover:bg-red-50"><Trash size={14} /></button>
          </div>
        ))}
      </div>
    </div>
  );
}
