import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { UserMinus, Plus, Trash, Lightbulb } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/lost-demand`;
const CHANNELS = { phone: "Telefon", walk_in: "Walk-in", email: "E-posta", widget: "Web sitesi", ota: "OTA", agency: "Acenta", other: "Diğer" };
const REASON_COLORS = { price_too_high: "bg-rose-400", no_availability: "bg-amber-400", room_type_unavailable: "bg-orange-400", restrictions: "bg-violet-400", dates_changed: "bg-sky-400", other: "bg-stone-400" };

export default function LostDemandPanel({ propertyId = "all" }) {
  const [data, setData] = useState(null);
  const [insights, setInsights] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [tab, setTab] = useState("log");

  const load = useCallback(async () => {
    try {
      const [r, i] = await Promise.all([
        axios.get(`${API}/${propertyId}?days=30`),
        axios.get(`${API}/${propertyId}/insights`),
      ]);
      setData(r.data); setInsights(i.data);
    } catch { toast.error("Kayıp talep verisi yüklenemedi"); }
  }, [propertyId]);
  useEffect(() => { load(); }, [load]);

  async function remove(e) {
    try { await axios.delete(`${API}/${e.property_id}/${e.id}`); toast.success("Silindi"); load(); }
    catch { toast.error("Silinemedi"); }
  }

  if (!data) return <div className="p-8 text-center text-stone-400">Yükleniyor…</div>;
  const s = data.summary;
  const RL = data.reason_labels || {};
  const maxRn = Math.max(...Object.values(s.by_reason || {}).map(b => b.room_nights), 1);

  return (
    <div className="p-5 max-w-[1150px] mx-auto space-y-4" data-testid="lost-demand-panel">
      <div className="bg-gradient-to-br from-stone-900 via-slate-900 to-rose-950 rounded-2xl p-6 text-white">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-rose-300">
              <UserMinus size={14} /> Denials & Regrets
            </div>
            <h1 className="text-2xl font-bold mt-1">Kayıp Talep Takibi</h1>
            <p className="text-sm text-stone-300 mt-1">Reddedilen/kaçan talepleri kaydedin — kısıtsız talep verisi fiyat ve kapasite kararlarınızı besler. Web sitesinde müsaitlik bulunamayan aramalar otomatik düşer.</p>
          </div>
          <button onClick={() => setShowForm(v => !v)} data-testid="ld-new-btn"
            className="px-4 py-2 bg-rose-400 hover:bg-rose-300 text-stone-900 rounded-lg text-sm font-bold inline-flex items-center gap-2">
            <Plus size={16} /> Kayıp Talep Ekle
          </button>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-5">
          <Stat label="Kayıt (30 gün)" value={s.entries} testid="ld-stat-entries" />
          <Stat label="Kayıp oda-gece" value={s.lost_room_nights} testid="ld-stat-rn" />
          <Stat label="Tahmini kayıp gelir" value={`£${s.est_lost_revenue.toLocaleString("tr-TR")}`} testid="ld-stat-rev" />
          <Stat label="En sık sebep" value={s.top_reason_label || "—"} small testid="ld-stat-reason" />
        </div>
      </div>

      {showForm && <LogForm propertyId={propertyId} labels={RL} onDone={() => { setShowForm(false); load(); }} />}

      {Object.keys(s.by_reason || {}).length > 0 && (
        <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="ld-reason-breakdown">
          <div className="text-xs font-bold text-stone-500 uppercase mb-2">Sebep dağılımı (oda-gece)</div>
          <div className="space-y-1.5">
            {Object.entries(s.by_reason).sort((a, b) => b[1].room_nights - a[1].room_nights).map(([k, v]) => (
              <div key={k} className="flex items-center gap-2 text-xs">
                <span className="w-44 text-stone-600">{RL[k] || k}</span>
                <div className="flex-1 h-2.5 bg-stone-100 rounded-full overflow-hidden">
                  <div className={`h-full rounded-full ${REASON_COLORS[k] || "bg-stone-400"}`} style={{ width: `${(v.room_nights / maxRn) * 100}%` }} />
                </div>
                <span className="w-24 text-right text-stone-500">{v.room_nights} og · £{v.revenue.toLocaleString("tr-TR")}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="flex gap-1.5">
        {[["log", "Kayıtlar"], ["insights", "Kısıtsız Talep İçgörüleri"]].map(([id, label]) => (
          <button key={id} onClick={() => setTab(id)} data-testid={`ld-tab-${id}`}
            className={`px-3 py-1 text-xs rounded-full border ${tab === id ? "bg-stone-900 text-white border-stone-900" : "bg-white text-stone-600 border-stone-200 hover:bg-stone-50"}`}>
            {label}
          </button>
        ))}
      </div>

      {tab === "insights" ? (
        <div className="space-y-2" data-testid="ld-insights">
          {(insights?.dates || []).map(d => (
            <div key={d.date} className="bg-white border border-stone-200 rounded-xl p-3 flex items-center gap-4 flex-wrap" data-testid={`ld-insight-${d.date}`}>
              <span className="font-mono text-sm font-bold text-stone-800">{d.date}</span>
              <span className="text-xs text-stone-500">OTB {d.otb_rooms} + kayıp <b className="text-rose-600">{d.lost_rooms}</b> = kısıtsız <b>{d.unconstrained_demand}</b>/{d.capacity} oda</span>
              {d.price_driven > 0 && <span className="text-[10px] px-2 py-0.5 bg-rose-50 text-rose-600 rounded-full font-semibold">{d.price_driven} fiyat kaynaklı</span>}
              {d.availability_driven > 0 && <span className="text-[10px] px-2 py-0.5 bg-amber-50 text-amber-700 rounded-full font-semibold">{d.availability_driven} müsaitlik kaynaklı</span>}
              <span className="flex items-center gap-1.5 text-xs text-stone-600 basis-full md:basis-auto md:flex-1">
                <Lightbulb size={13} className="text-amber-500 flex-shrink-0" />{d.recommendation}
              </span>
            </div>
          ))}
          {(!insights?.dates || insights.dates.length === 0) && (
            <div className="bg-white border border-stone-200 rounded-xl px-4 py-10 text-center text-stone-400 text-sm">Gelecek tarihli kayıp talep verisi yok.</div>
          )}
        </div>
      ) : (
        <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead><tr className="text-[11px] uppercase text-stone-400 border-b border-stone-100">
              <th className="text-left px-4 py-2">Tarih</th><th className="text-left px-2 py-2">Konaklama</th>
              <th className="text-center px-2 py-2">Oda</th><th className="text-left px-2 py-2">Kanal</th>
              <th className="text-left px-2 py-2">Sebep</th><th className="text-right px-2 py-2">Kayıp gelir</th>
              <th className="px-2 py-2"></th>
            </tr></thead>
            <tbody>
              {data.entries.map(e => (
                <tr key={e.id} className="border-b border-stone-50" data-testid={`ld-entry-${e.id}`}>
                  <td className="px-4 py-2 text-xs text-stone-500">{new Date(e.created_at).toLocaleDateString("tr-TR")}{e.source === "widget_auto" && <span className="ml-1 text-[9px] px-1 py-0.5 bg-sky-50 text-sky-600 rounded font-semibold">oto</span>}</td>
                  <td className="px-2 py-2 font-mono text-xs">{e.check_in} → {e.check_out}</td>
                  <td className="px-2 py-2 text-center">{e.rooms}</td>
                  <td className="px-2 py-2 text-xs text-stone-500">{CHANNELS[e.channel] || e.channel}</td>
                  <td className="px-2 py-2"><span className="text-[10px] px-2 py-0.5 rounded-full font-semibold bg-stone-100 text-stone-600">{RL[e.reason] || e.reason}</span></td>
                  <td className="px-2 py-2 text-right font-mono">{e.est_lost_revenue > 0 ? `£${e.est_lost_revenue.toLocaleString("tr-TR")}` : "—"}</td>
                  <td className="px-2 py-2 text-right"><button onClick={() => remove(e)} className="p-1 text-stone-300 hover:text-rose-600" data-testid={`ld-delete-${e.id}`}><Trash size={13} /></button></td>
                </tr>
              ))}
              {data.entries.length === 0 && (
                <tr><td colSpan={7} className="px-4 py-10 text-center text-stone-400 text-sm">Son 30 günde kayıp talep kaydı yok.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function LogForm({ propertyId, labels, onDone }) {
  const [saving, setSaving] = useState(false);
  async function submit(e) {
    e.preventDefault();
    const f = e.target;
    if (propertyId === "all" && !f.pid.value.trim()) { toast.error("Tesis ID girin"); return; }
    setSaving(true);
    try {
      await axios.post(`${API}/${propertyId === "all" ? f.pid.value.trim() : propertyId}/log`, {
        check_in: f.ci.value, check_out: f.co.value,
        rooms: parseInt(f.rooms.value || "1", 10), channel: f.channel.value,
        reason: f.reason.value, quoted_rate: parseFloat(f.rate.value || "0"),
        note: f.note.value,
      });
      toast.success("Kayıp talep kaydedildi"); onDone();
    } catch (err) { toast.error(err.response?.data?.detail || "Kaydedilemedi"); }
    setSaving(false);
  }
  const inp = "border border-stone-200 rounded-lg px-2.5 py-1.5 text-sm w-full";
  const lbl = "text-[10px] uppercase tracking-wider text-stone-400";
  return (
    <form onSubmit={submit} className="bg-white border border-rose-200 rounded-xl p-4 grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="ld-form">
      {propertyId === "all" && (
        <div><div className={lbl}>Tesis ID</div><input name="pid" className={inp} placeholder="default" data-testid="ld-form-pid" /></div>
      )}
      <div><div className={lbl}>Giriş</div><input name="ci" type="date" required className={inp} data-testid="ld-form-ci" /></div>
      <div><div className={lbl}>Çıkış</div><input name="co" type="date" required className={inp} data-testid="ld-form-co" /></div>
      <div><div className={lbl}>Oda sayısı</div><input name="rooms" type="number" min="1" defaultValue="1" className={inp} data-testid="ld-form-rooms" /></div>
      <div><div className={lbl}>Kanal</div>
        <select name="channel" className={inp} data-testid="ld-form-channel">
          {Object.entries(CHANNELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select></div>
      <div><div className={lbl}>Sebep</div>
        <select name="reason" className={inp} data-testid="ld-form-reason">
          {Object.entries(labels).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select></div>
      <div><div className={lbl}>Teklif edilen fiyat (gece)</div><input name="rate" type="number" step="0.01" min="0" className={inp} placeholder="120" data-testid="ld-form-rate" /></div>
      <div className="col-span-2"><div className={lbl}>Not</div><input name="note" className={inp} placeholder="opsiyonel" data-testid="ld-form-note" /></div>
      <div className="flex items-end">
        <button type="submit" disabled={saving} data-testid="ld-form-save"
          className="px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white rounded-lg text-sm font-bold disabled:opacity-60">
          {saving ? "Kaydediliyor…" : "Kaydet"}
        </button>
      </div>
    </form>
  );
}

function Stat({ label, value, small, testid }) {
  return (
    <div className="bg-white/10 rounded-xl p-3" data-testid={testid}>
      <div className="text-[10px] uppercase tracking-wider text-stone-300">{label}</div>
      <div className={`${small ? "text-sm" : "text-xl"} font-bold mt-0.5`}>{value}</div>
    </div>
  );
}
