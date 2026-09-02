import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { TrendUp, ArrowsClockwise, HourglassMedium } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/ramp-ladder`;

export default function RampLadderPanel({ propertyId = "default" }) {
  const [data, setData] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [saving, setSaving] = useState(false);
  const pid = propertyId === "all" ? "default" : propertyId;

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/${pid}`);
      setData(r.data);
    } catch { toast.error("Zam merdiveni verisi yüklenemedi"); }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  async function scan() {
    setScanning(true);
    try {
      const r = await axios.post(`${API}/${pid}/scan`);
      const n = (r.data.actions || []).length;
      const waiting = (r.data.skips || []).filter((s) => s.reason === "awaiting_guest_approval").length;
      toast.success(`Tarama bitti: ${n} zam kademesi, ${waiting} gece misafir onayı bekliyor`);
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
        occ_threshold: parseFloat(f.occth.value),
        step_pct: parseFloat(f.step.value),
        max_steps: parseInt(f.maxsteps.value, 10),
        cadence_hours: parseInt(f.cadence.value, 10),
        forecast_boost: f.fcboost.checked,
        event_premium: f.evprem.checked,
        event_min_score: parseInt(f.evscore.value, 10) || 60,
      });
      toast.success("Zam merdiveni ayarları kaydedildi"); load();
    } catch { toast.error("Kaydedilemedi"); }
    setSaving(false);
  }

  if (!data) return <div className="p-8 text-center text-stone-400">Yükleniyor…</div>;
  const { config: c, summary: s, steps, awaiting } = data;

  return (
    <div className="p-5 max-w-[1100px] mx-auto space-y-4" data-testid="ramp-ladder-panel">
      <div className="bg-gradient-to-br from-stone-900 via-amber-950 to-orange-950 rounded-2xl p-6 text-white">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-amber-300">
              <TrendUp size={14} /> Guest-Approved Ramp
            </div>
            <h1 className="text-2xl font-bold mt-1">Misafir-Onaylı Zam Merdiveni</h1>
            <p className="text-sm text-stone-300 mt-1">
              İlk zam talep kanıtıyla (doluluk ≥ %{c.occ_threshold}). İkinci ve sonraki basamaklar için
              <b> YENİ REZERVASYON şarttır</b> — kimsenin ödemediği fiyata tırmanış matematiksel kapalı.
              Pencere D{c.window_start}–D{c.window_end}, tavan korumalı, kira-çit kilidiyle yazar.
            </p>
          </div>
          <button onClick={scan} disabled={scanning} data-testid="ramp-scan-btn"
            className="px-4 py-2 rounded-full bg-amber-500 hover:bg-amber-400 text-stone-900 text-sm font-semibold flex items-center gap-2 disabled:opacity-50">
            <ArrowsClockwise size={16} className={scanning ? "animate-spin" : ""} /> Şimdi Tara
          </button>
        </div>
        <div className="grid grid-cols-4 gap-3 mt-5">
          <div className="bg-white/10 rounded-xl p-3" data-testid="ramp-stat-total">
            <div className="text-2xl font-bold">{s.total_steps}</div>
            <div className="text-xs text-stone-300">Toplam kademe</div>
          </div>
          <div className="bg-white/10 rounded-xl p-3" data-testid="ramp-stat-approved">
            <div className="text-2xl font-bold text-emerald-300">{s.guest_approved_steps}</div>
            <div className="text-xs text-stone-300">Misafir-onaylı kademe</div>
          </div>
          <div className="bg-white/10 rounded-xl p-3" data-testid="ramp-stat-reversals">
            <div className="text-2xl font-bold text-rose-300">{s.reversals || 0}</div>
            <div className="text-xs text-stone-300">Yön dönüşü (talep söndü)</div>
          </div>
          <div className="bg-white/10 rounded-xl p-3" data-testid="ramp-stat-awaiting">
            <div className="text-2xl font-bold text-amber-300">{s.awaiting_approval}</div>
            <div className="text-xs text-stone-300">Onay bekleyen gece</div>
          </div>
        </div>
        {data.rules?.asymmetric_time && (
          <div className="mt-3 text-[11px] text-stone-400 italic" data-testid="ramp-asymmetric-rule">
            ⚖️ Asimetrik zaman kuralı: {data.rules.asymmetric_time}
          </div>
        )}
      </div>

      <form onSubmit={saveCfg} className="bg-white rounded-2xl border border-stone-200 p-5 grid grid-cols-2 md:grid-cols-5 gap-4 items-end" data-testid="ramp-config-form">
        <label className="flex items-center gap-2 text-sm font-medium col-span-2 md:col-span-1">
          <input type="checkbox" name="enabled" defaultChecked={c.enabled} className="w-4 h-4 accent-amber-600" data-testid="ramp-enabled-toggle" />
          Zam merdiveni aktif
        </label>
        <label className="text-xs text-stone-500">Doluluk eşiği (%)
          <input name="occth" type="number" min="30" max="95" defaultValue={c.occ_threshold} className="mt-1 w-full border rounded-lg px-2 py-1.5 text-sm" data-testid="ramp-occth-input" />
        </label>
        <label className="text-xs text-stone-500">Kademe boyu (%)
          <input name="step" type="number" min="1" max="15" step="0.5" defaultValue={c.step_pct} className="mt-1 w-full border rounded-lg px-2 py-1.5 text-sm" data-testid="ramp-step-input" />
        </label>
        <label className="text-xs text-stone-500">Maks kademe
          <input name="maxsteps" type="number" min="1" max="6" defaultValue={c.max_steps} className="mt-1 w-full border rounded-lg px-2 py-1.5 text-sm" data-testid="ramp-maxsteps-input" />
        </label>
        <label className="text-xs text-stone-500">Kademe ritmi (saat)
          <input name="cadence" type="number" min="1" max="48" defaultValue={c.cadence_hours} className="mt-1 w-full border rounded-lg px-2 py-1.5 text-sm" data-testid="ramp-cadence-input" />
        </label>
        <label className="flex items-center gap-2 text-sm font-medium col-span-2 md:col-span-4" title="LightGBM pickup tahmini: 14+ gün kala nihai doluluk ≥%90 ise yeni rezervasyon beklemeden sönümlü (yarım) kademe; <%50 tahminde zam freni">
          <input type="checkbox" name="fcboost" defaultChecked={c.forecast_boost !== false} className="w-4 h-4 accent-indigo-600" data-testid="ramp-forecast-toggle" />
          ML tahmin anahtarı (FORECAST_HOT sönümlü kademe · FORECAST_COLD zam freni)
        </label>
        <label className="flex items-center gap-2 text-sm font-medium col-span-2 md:col-span-3" title="Şehirdeki büyük etkinlik gecelerinde doluluk kanıtı beklemeden sönümlü (yarım) ilk kademe atılır; etkinlik sürdüğü sürece geri alınmaz">
          <input type="checkbox" name="evprem" defaultChecked={c.event_premium !== false} className="w-4 h-4 accent-amber-600" data-testid="ramp-event-toggle" />
          Etkinlik primi (EVENT_PREMIUM sönümlü kademe)
        </label>
        <label className="text-xs font-medium col-span-2 md:col-span-1">Min. talep skoru
          <input name="evscore" type="number" min="10" max="100" defaultValue={c.event_min_score ?? 60} className="mt-1 w-full border rounded-lg px-2 py-1.5 text-sm" data-testid="ramp-event-score" />
        </label>
        <button type="submit" disabled={saving} className="col-span-2 md:col-span-1 md:w-40 px-4 py-2 rounded-full bg-stone-900 text-white text-sm font-semibold disabled:opacity-50" data-testid="ramp-save-config-btn">
          {saving ? "Kaydediliyor…" : "Ayarları Kaydet"}
        </button>
      </form>

      {awaiting?.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4" data-testid="ramp-awaiting-list">
          <div className="flex items-center gap-2 text-sm font-semibold text-amber-800 mb-2">
            <HourglassMedium size={16} /> Misafir onayı bekleyen geceler (yeni rezervasyon gelmeden tırmanış KAPALI)
          </div>
          <div className="flex flex-wrap gap-2">
            {awaiting.map((a, i) => (
              <span key={i} className="px-2.5 py-1 rounded-full bg-white border border-amber-300 text-xs">
                {a.stay_date} · kademe {a.step_no} · {a.bookings_at_last_step} rezervasyonda bekliyor
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="bg-white rounded-2xl border border-stone-200 p-5">
        <h2 className="text-lg font-semibold mb-3">Zam Günlüğü</h2>
        {steps.length === 0 ? (
          <p className="text-sm text-stone-400" data-testid="ramp-empty-log">Henüz zam kademesi yok. Merdiveni aktif edin; doluluk eşiği aşan geceler kanıtla yükselir.</p>
        ) : (
          <table className="w-full text-sm" data-testid="ramp-steps-table">
            <thead><tr className="text-left text-xs text-stone-500 border-b">
              <th className="py-2">Zaman</th><th>Gece</th><th>Oda tipi</th><th>Kademe</th><th>Fiyat</th><th>Doluluk</th><th>Kanıt</th>
            </tr></thead>
            <tbody>
              {steps.slice(0, 40).map((st) => (
                <tr key={st.id} className="border-b border-stone-100">
                  <td className="py-2 text-xs text-stone-400">{st.created_at?.slice(0, 16).replace("T", " ")}</td>
                  <td>{st.stay_date}</td>
                  <td>{st.room_type}</td>
                  <td>{st.from_step}→{st.step_no}</td>
                  <td className={`font-semibold ${st.direction === "down" ? "text-rose-600" : "text-emerald-700"}`}>
                    {st.direction === "down" ? "▼" : "▲"} {st.rate}
                  </td>
                  <td>%{st.occ}</td>
                  <td>{st.reason === "demand_faded_reversal"
                    ? <span className="text-rose-600 text-xs font-semibold">↩ Talep söndü (yön dönüşü)</span>
                    : st.reason === "DEMAND_STRONG"
                    ? <span className="text-sky-600 text-xs font-semibold">📈 Piyasa sıkılaştı (sönümlü)</span>
                    : st.reason === "FORECAST_HOT"
                    ? <span className="text-indigo-600 text-xs font-semibold" title={`ML nihai doluluk tahmini %${st.forecast_signal?.occ ?? "?"}`}>🤖 ML tahmin sıcak (sönümlü)</span>
                    : st.reason === "EVENT_PREMIUM"
                    ? <span className="text-amber-700 text-xs font-semibold" title={st.event?.name || ""}>🎪 Etkinlik primi (sönümlü)</span>
                    : st.guest_approved
                    ? <span className="text-emerald-600 text-xs font-semibold">✓ Yeni rezervasyon (misafir onayı)</span>
                    : <span className="text-stone-500 text-xs">Talep kanıtı (doluluk)</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
