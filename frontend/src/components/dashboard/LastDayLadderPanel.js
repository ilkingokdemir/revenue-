import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Ladder, ArrowsClockwise, ShieldCheck } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/lastday-ladder`;

export default function LastDayLadderPanel({ propertyId = "default" }) {
  const [data, setData] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [saving, setSaving] = useState(false);
  const pid = propertyId === "all" ? "default" : propertyId;

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/${pid}`);
      setData(r.data);
    } catch { toast.error("Merdiven verisi yüklenemedi"); }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  async function scan() {
    setScanning(true);
    try {
      const r = await axios.post(`${API}/${pid}/scan`);
      const n = (r.data.actions || []).length;
      const sk = (r.data.skips || []).length;
      toast.success(`Tarama bitti: ${n} kademe, ${sk} atlanan gece`);
      load();
    } catch { toast.error("Tarama başarısız"); }
    setScanning(false);
  }

  async function saveCfg(e) {
    e.preventDefault();
    const f = e.target;
    setSaving(true);
    try {
      await axios.put(`${API}/${pid}/config`, {
        enabled: f.enabled.checked,
        window_days: parseInt(f.window.value, 10),
        cadence_hours: parseInt(f.cadence.value, 10),
        step_pct: parseFloat(f.step.value),
        max_steps: parseInt(f.maxsteps.value, 10),
      });
      toast.success("Merdiven ayarları kaydedildi"); load();
    } catch { toast.error("Kaydedilemedi"); }
    setSaving(false);
  }

  if (!data) return <div className="p-8 text-center text-stone-400">Yükleniyor…</div>;
  const { config: c, summary: s, steps, owned_dates } = data;

  return (
    <div className="p-5 max-w-[1100px] mx-auto space-y-4" data-testid="lastday-ladder-panel">
      <div className="bg-gradient-to-br from-stone-900 via-emerald-950 to-teal-900 rounded-2xl p-6 text-white">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-emerald-300">
              <Ladder size={14} /> Last-Minute Ladder
            </div>
            <h1 className="text-2xl font-bold mt-1">Son-Gün Merdiveni (D0–D{c.window_days})</h1>
            <p className="text-sm text-stone-300 mt-1">
              Satılmamış odalar {c.cadence_hours} saatte bir ~%{c.step_pct} kademeli iner; oda satılınca yön DÖNER.
              Taban tanımlı değilse fail-closed: dokunmaz. Pin'lere saygılı — tek yazıcı kuralı.
            </p>
          </div>
          <button onClick={scan} disabled={scanning} data-testid="ladder-scan-btn"
            className="px-4 py-2 rounded-full bg-emerald-500 hover:bg-emerald-400 text-stone-900 text-sm font-semibold flex items-center gap-2 disabled:opacity-50">
            <ArrowsClockwise size={16} className={scanning ? "animate-spin" : ""} /> Şimdi Tara
          </button>
        </div>
        <div className="grid grid-cols-3 gap-3 mt-5">
          <div className="bg-white/10 rounded-xl p-3" data-testid="ladder-stat-24h">
            <div className="text-2xl font-bold">{s.steps_24h}</div>
            <div className="text-xs text-stone-300">Kademe (24 saat)</div>
          </div>
          <div className="bg-white/10 rounded-xl p-3" data-testid="ladder-stat-reversals">
            <div className="text-2xl font-bold text-emerald-300">{s.reversals}</div>
            <div className="text-xs text-stone-300">Satışla geri çıkış</div>
          </div>
          <div className="bg-white/10 rounded-xl p-3" data-testid="ladder-stat-active">
            <div className="text-2xl font-bold">{s.active_ladders}</div>
            <div className="text-xs text-stone-300">Aktif merdiven (sahipli gece)</div>
          </div>
        </div>
        {owned_dates?.length > 0 && (
          <div className="mt-3 text-xs text-emerald-200 flex items-center gap-1">
            <ShieldCheck size={14} /> Tek yazıcı — sahipli geceler: {owned_dates.join(", ")}
          </div>
        )}
        {data.rules?.asymmetric_time && (
          <div className="mt-3 text-[11px] text-stone-400 italic" data-testid="ladder-asymmetric-rule">
            ⚖️ Asimetrik zaman kuralı: {data.rules.asymmetric_time}
          </div>
        )}
      </div>

      <form onSubmit={saveCfg} className="bg-white rounded-2xl border border-stone-200 p-5 grid grid-cols-2 md:grid-cols-5 gap-4 items-end" data-testid="ladder-config-form">
        <label className="flex items-center gap-2 text-sm font-medium col-span-2 md:col-span-1">
          <input type="checkbox" name="enabled" defaultChecked={c.enabled} className="w-4 h-4 accent-emerald-600" data-testid="ladder-enabled-toggle" />
          Merdiven aktif
        </label>
        <label className="text-xs text-stone-500">Pencere (gün, 0-3)
          <input name="window" type="number" min="0" max="3" defaultValue={c.window_days} className="mt-1 w-full border rounded-lg px-2 py-1.5 text-sm" data-testid="ladder-window-input" />
        </label>
        <label className="text-xs text-stone-500">Kademe ritmi (saat)
          <input name="cadence" type="number" min="1" max="12" defaultValue={c.cadence_hours} className="mt-1 w-full border rounded-lg px-2 py-1.5 text-sm" data-testid="ladder-cadence-input" />
        </label>
        <label className="text-xs text-stone-500">Kademe boyu (%)
          <input name="step" type="number" min="1" max="20" step="0.5" defaultValue={c.step_pct} className="mt-1 w-full border rounded-lg px-2 py-1.5 text-sm" data-testid="ladder-step-input" />
        </label>
        <label className="text-xs text-stone-500">Maks kademe
          <input name="maxsteps" type="number" min="1" max="6" defaultValue={c.max_steps} className="mt-1 w-full border rounded-lg px-2 py-1.5 text-sm" data-testid="ladder-maxsteps-input" />
        </label>
        <button type="submit" disabled={saving} className="col-span-2 md:col-span-5 md:w-40 px-4 py-2 rounded-full bg-stone-900 text-white text-sm font-semibold disabled:opacity-50" data-testid="ladder-save-config-btn">
          {saving ? "Kaydediliyor…" : "Ayarları Kaydet"}
        </button>
      </form>

      <div className="bg-white rounded-2xl border border-stone-200 p-5">
        <h2 className="text-lg font-semibold mb-3">Kademe Günlüğü</h2>
        {steps.length === 0 ? (
          <p className="text-sm text-stone-400" data-testid="ladder-empty-log">Henüz kademe yok. Merdiveni aktif edin ve D0–D1 penceresinde boş oda olduğunda otomatik çalışır.</p>
        ) : (
          <table className="w-full text-sm" data-testid="ladder-steps-table">
            <thead><tr className="text-left text-xs text-stone-500 border-b">
              <th className="py-2">Zaman</th><th>Gece</th><th>Oda tipi</th><th>Yön</th><th>Kademe</th><th>Fiyat</th><th>Boş</th><th>Neden</th>
            </tr></thead>
            <tbody>
              {steps.slice(0, 40).map((st) => (
                <tr key={st.id} className="border-b border-stone-100">
                  <td className="py-2 text-xs text-stone-400">{st.created_at?.slice(0, 16).replace("T", " ")}</td>
                  <td>{st.stay_date}</td>
                  <td>{st.room_type}</td>
                  <td>{st.direction === "down"
                    ? <span className="text-rose-600 font-semibold">▼ İndirim</span>
                    : <span className="text-emerald-600 font-semibold">▲ Geri çıkış</span>}</td>
                  <td>{st.from_step}→{st.step_no}</td>
                  <td className="font-semibold">{st.rate}</td>
                  <td>{st.unsold}</td>
                  <td className="text-xs text-stone-500">{st.reason === "sale_reversal" ? "Satış geldi" : "Boş oda"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
