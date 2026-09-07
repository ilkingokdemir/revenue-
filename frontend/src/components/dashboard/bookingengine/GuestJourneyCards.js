import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Gift, Mail, Play, Trash2 } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cfg = { withCredentials: true };
const inputCls = "w-full border border-stone-300 rounded-lg px-2.5 py-1.5 text-sm";

export const EventPackagesCard = ({ propertyId }) => {
  const [items, setItems] = useState([]);
  const [f, setF] = useState({ name_tr: "", name_en: "", name_de: "", price_per_night: 25, includes: "breakfast, late_checkout" });
  const load = useCallback(() => axios.get(`${API}/arrival-reminder/event-packages/${propertyId}`, cfg).then((r) => setItems(r.data)).catch(() => {}), [propertyId]);
  useEffect(() => { load(); }, [load]);

  const create = async (useDefault) => {
    try {
      const body = useDefault ? { use_default: true } : { ...f, price_per_night: parseFloat(f.price_per_night) || 0, includes: f.includes.split(",").map((x) => x.trim()).filter(Boolean) };
      await axios.post(`${API}/arrival-reminder/event-packages/${propertyId}`, body, cfg);
      toast.success("Paket eklendi — widget etkinlik kartlarında 'Paketli rezerve et' görünür");
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Eklenemedi"); }
  };
  const toggle = async (p) => { await axios.put(`${API}/arrival-reminder/event-packages/${propertyId}/${p.id}`, { enabled: !p.enabled }, cfg); load(); };
  const remove = async (p) => { if (!window.confirm("Paket silinsin mi?")) return; await axios.delete(`${API}/arrival-reminder/event-packages/${propertyId}/${p.id}`, cfg); load(); };

  return (
    <div className="border border-amber-200 bg-amber-50/30 rounded-xl p-4 space-y-3" data-testid="event-packages-card">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-sm font-semibold text-amber-900"><Gift size={16} /> Etkinlik Paketleri ({items.length})</div>
        <button onClick={() => create(true)} className="text-xs px-3 py-1.5 rounded-lg bg-amber-600 text-white hover:bg-amber-700" data-testid="event-package-add-default">+ Varsayılan paketi ekle (+£25/gece)</button>
      </div>
      <p className="text-xs text-stone-500">Widget'taki etkinlik kartlarında ilk aktif paket "Paketli rezerve et" butonu olarak satılır; paket ücreti gece × oda olarak toplama eklenir ve rezervasyona yazılır.</p>
      <div className="space-y-1.5">
        {items.map((p) => (
          <div key={p.id} className={`flex flex-wrap items-center justify-between gap-2 text-sm bg-white border rounded-lg px-3 py-2 ${p.enabled ? "border-stone-200" : "border-stone-100 opacity-50"}`} data-testid={`event-package-row-${p.id}`}>
            <div><b>{p.name_tr}</b> <span className="text-stone-400">/ {p.name_en}</span> · <b className="text-amber-700">+£{Number(p.price_per_night).toFixed(0)}/gece</b> <span className="text-xs text-stone-400">· {(p.includes || []).join(", ")}</span></div>
            <div className="flex gap-1.5">
              <button onClick={() => toggle(p)} className="text-xs px-2 py-1 rounded-lg border border-stone-200 hover:bg-stone-50" data-testid={`event-package-toggle-${p.id}`}>{p.enabled ? "Pasifleştir" : "Aktifleştir"}</button>
              <button onClick={() => remove(p)} className="p-1.5 rounded-lg border border-stone-200 hover:bg-red-50 text-red-500" data-testid={`event-package-delete-${p.id}`}><Trash2 size={13} /></button>
            </div>
          </div>
        ))}
        {items.length === 0 && <div className="text-xs text-stone-400">Henüz paket yok.</div>}
      </div>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-2 items-end" data-testid="event-package-form">
        <input className={inputCls} placeholder="Ad (TR)" value={f.name_tr} onChange={(e) => setF({ ...f, name_tr: e.target.value })} data-testid="event-package-name-tr" />
        <input className={inputCls} placeholder="Name (EN)" value={f.name_en} onChange={(e) => setF({ ...f, name_en: e.target.value })} data-testid="event-package-name-en" />
        <input className={inputCls} placeholder="Name (DE)" value={f.name_de} onChange={(e) => setF({ ...f, name_de: e.target.value })} />
        <input className={inputCls} type="number" step="0.5" placeholder="£/gece" value={f.price_per_night} onChange={(e) => setF({ ...f, price_per_night: e.target.value })} data-testid="event-package-price" />
        <button onClick={() => create(false)} className="text-xs px-3 py-2 rounded-lg bg-stone-900 text-white" data-testid="event-package-submit">Özel paket ekle</button>
      </div>
    </div>
  );
};

export const ArrivalReminderCard = ({ propertyId }) => {
  const [log, setLog] = useState([]);
  const [running, setRunning] = useState(false);
  const [preview, setPreview] = useState(null);
  const [stats, setStats] = useState(null);
  const load = useCallback(() => {
    axios.get(`${API}/arrival-reminder/log/${propertyId}`, cfg).then((r) => setLog(r.data)).catch(() => {});
    axios.get(`${API}/arrival-reminder/stats/${propertyId}`, cfg).then((r) => setStats(r.data)).catch(() => {});
  }, [propertyId]);
  useEffect(() => { load(); }, [load]);

  const run = async () => {
    setRunning(true);
    try {
      const { data } = await axios.post(`${API}/arrival-reminder/run/${propertyId}`, {}, cfg);
      toast.success(`${data.candidates} aday · ${data.sent} gönderildi · ${data.mocked} MOCK (${data.targets.join(", ")} girişleri)`);
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Çalıştırılamadı"); }
    setRunning(false);
  };
  const showPreview = async (lang) => {
    const { data } = await axios.get(`${API}/arrival-reminder/preview/${propertyId}?lang=${lang}`, cfg);
    setPreview(data);
  };

  return (
    <div className="border border-sky-200 bg-sky-50/30 rounded-xl p-4 space-y-3" data-testid="arrival-reminder-card">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-sm font-semibold text-sky-900"><Mail size={16} /> Ön Varış E-postası (T-2 · TR/EN/DE)</div>
        <div className="flex gap-1.5">
          {["tr", "en", "de"].map((l) => <button key={l} onClick={() => showPreview(l)} className="text-xs px-2 py-1.5 rounded-lg border border-stone-200 bg-white hover:bg-stone-50 uppercase" data-testid={`arrival-preview-${l}`}>{l}</button>)}
          <button onClick={run} disabled={running} className="text-xs px-3 py-1.5 rounded-lg bg-sky-700 text-white hover:bg-sky-800 disabled:opacity-50 inline-flex items-center gap-1" data-testid="arrival-run-now"><Play size={12} /> Şimdi çalıştır</button>
        </div>
      </div>
      <p className="text-xs text-stone-500">Robot her gün 10:00'da girişe 2 gün kalan misafirlere kendi dilinde check-in saati, adres + yol tarifi ve <b>kişiselleştirilmiş</b> ek hizmet tekliflerini (tek tık ekle) e-posta + WhatsApp ile gönderir. Zaten eklenen/kahvaltı dahil ekstralar gizlenir, geçmiş favoriler ⭐ öne çıkar. Resend/Twilio anahtarı yokken MOCK.</p>
      {stats && (
        <div className="grid grid-cols-3 md:grid-cols-6 gap-1.5" data-testid="arrival-stats">
          {[["Hatırlatma", stats.reminders, "arrival-stat-reminders"], ["WhatsApp", stats.whatsapp, "arrival-stat-wa"], ["Teklif", stats.offers, "arrival-stat-offers"], ["Tek tık eklenen", stats.claimed, "arrival-stat-claimed"], ["Dönüşüm", `%${stats.conversion_pct}`, "arrival-stat-conv"], ["Ekstra gelir", stats.revenue, "arrival-stat-rev"]].map(([l, v, tid]) => (
            <div key={l} className="bg-white border border-stone-100 rounded-lg px-2 py-1.5"><div className="text-[9px] uppercase font-bold text-stone-400">{l}</div><div className="text-sm font-bold text-stone-900" data-testid={tid}>{v}</div></div>
          ))}
          {stats.by_label?.length > 0 && <div className="col-span-3 md:col-span-6 text-[10px] text-stone-500">{stats.by_label.map((b) => `${b.label}: ${b.claimed}/${b.offered}`).join(" · ")}</div>}
        </div>
      )}
      {preview && (
        <div className="bg-white border border-stone-200 rounded-lg p-3" data-testid="arrival-preview-panel">
          <div className="text-xs font-semibold text-stone-700 mb-2">Konu: {preview.subject}</div>
          <iframe title="preview" srcDoc={preview.html} className="w-full h-72 border-0 rounded" />
        </div>
      )}
      <div className="space-y-1 max-h-48 overflow-y-auto">
        {log.map((l) => (
          <div key={l.id} className="flex flex-wrap justify-between gap-2 text-xs bg-white border border-stone-100 rounded-lg px-3 py-1.5" data-testid={`arrival-log-${l.id}`}>
            <span><b>{l.guest_name}</b> · {l.to} · giriş {l.check_in} · <span className="uppercase">{l.lang}</span>{l.channels?.includes("whatsapp") && <span className="ml-1 px-1 rounded bg-emerald-100 text-emerald-700 font-bold">WA</span>}{l.favorites > 0 && <span className="ml-1">⭐{l.favorites}</span>}</span>
            <span className={l.status === "sent" ? "text-emerald-600" : "text-amber-600"}>{l.status === "sent" ? "gönderildi" : l.status === "mocked" ? "MOCK" : l.status}</span>
          </div>
        ))}
        {log.length === 0 && <div className="text-xs text-stone-400">Henüz gönderim yok.</div>}
      </div>
    </div>
  );
};
