import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Plugs, MapTrifold, GearSix, PaperPlaneTilt, RocketLaunch,
  CheckCircle, Circle, ArrowRight, Lightning,
} from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STEPS = [
  { id: 0, label: "Kanal Seçimi", icon: Plugs },
  { id: 1, label: "Oda Eşleme", icon: MapTrifold },
  { id: 2, label: "Senkron Ayarları", icon: GearSix },
  { id: 3, label: "Test Push", icon: PaperPlaneTilt },
  { id: 4, label: "Go-Live", icon: RocketLaunch },
];

export default function CmSetupWizard({ activePropertyId, properties }) {
  const pid = activePropertyId && activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default");
  const [step, setStep] = useState(0);
  const [catalog, setCatalog] = useState([]);
  const [connections, setConnections] = useState([]);
  const [roomTypes, setRoomTypes] = useState([]);
  const [mappings, setMappings] = useState({});
  const [setup, setSetup] = useState({});
  const [golive, setGolive] = useState(null);
  const [pushResults, setPushResults] = useState(null);
  const [selected, setSelected] = useState(new Set());
  const [ariScope, setAriScope] = useState("full");
  const [pushFreq, setPushFreq] = useState(30);
  const [stopSell, setStopSell] = useState(true);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/cm/setup/${pid}`);
      setCatalog(data.catalog || []);
      setConnections(data.connections || []);
      setRoomTypes(data.room_types || []);
      const s = data.setup || {};
      setSetup(s);
      setSelected(new Set((data.connections || []).filter((c) => c.connected).map((c) => c.channel_id)));
      if (s.ari_scope) setAriScope(s.ari_scope);
      if (s.push_frequency_min) setPushFreq(s.push_frequency_min);
      if (s.stop_sell_on_zero !== undefined) setStopSell(!!s.stop_sell_on_zero);
      const m = {};
      (data.mappings || []).forEach((x) => { m[`${x.internal_id}|${x.channel_id}`] = x.external_id || ""; });
      setMappings(m);
    } catch { toast.error("Kurulum verisi yüklenemedi"); }
  }, [pid]);

  const loadGolive = useCallback(async () => {
    try { const { data } = await axios.get(`${API}/cm/golive/${pid}`); setGolive(data); } catch { /* */ }
  }, [pid]);

  useEffect(() => { load(); loadGolive(); }, [load, loadGolive]);

  const saveChannels = async () => {
    if (selected.size === 0) { toast.error("En az bir kanal seçin"); return; }
    setBusy(true);
    try {
      await axios.post(`${API}/cm/setup/${pid}/channels`, { channel_ids: [...selected] });
      toast.success(`${selected.size} kanal bağlandı`);
      await load(); loadGolive(); setStep(1);
    } catch (e) { toast.error(e.response?.data?.detail || "Kaydedilemedi"); }
    setBusy(false);
  };

  const saveMapping = async () => {
    setBusy(true);
    try {
      const rows = [];
      [...selected].forEach((cid) => roomTypes.forEach((rt) => {
        const v = mappings[`${rt.id}|${cid}`];
        if (v) rows.push({ kind: "room", internal_id: rt.id, channel_id: cid, external_id: v });
      }));
      const { data } = await axios.post(`${API}/cm/setup/${pid}/mapping`, { mappings: rows });
      toast.success(`${data.saved} eşleme kaydedildi`);
      loadGolive(); setStep(2);
    } catch { toast.error("Kaydedilemedi"); }
    setBusy(false);
  };

  const saveSync = async () => {
    setBusy(true);
    try {
      await axios.post(`${API}/cm/setup/${pid}/sync-settings`, {
        ari_scope: ariScope, push_frequency_min: pushFreq, stop_sell_on_zero: stopSell,
      });
      toast.success("Senkron ayarları kaydedildi");
      loadGolive(); setStep(3);
    } catch { toast.error("Kaydedilemedi"); }
    setBusy(false);
  };

  const testPush = async () => {
    setBusy(true);
    try {
      const { data } = await axios.post(`${API}/cm/test-push/${pid}`);
      setPushResults(data.results || []);
      toast.success(`${data.results.length} kanala test push yapıldı (mock)`);
      loadGolive();
    } catch (e) { toast.error(e.response?.data?.detail || "Push başarısız"); }
    setBusy(false);
  };

  return (
    <div className="p-6 max-w-5xl" data-testid="cm-setup-wizard">
      <div className="mb-5">
        <h2 className="text-xl font-bold text-stone-800">Channel Manager Hızlı Kurulum</h2>
        <p className="text-xs text-stone-500 mt-1">Kanallarınızı bağlayın, odaları eşleyin, senkronu başlatın — eviivo tek-tık hızında.</p>
      </div>

      <div className="flex gap-1.5 mb-6 flex-wrap" data-testid="cm-wizard-stepper">
        {STEPS.map((s) => (
          <button key={s.id} onClick={() => setStep(s.id)} data-testid={`cm-step-${s.id}`}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[11px] font-semibold transition-colors ${
              step === s.id ? "bg-cyan-700 text-white" : "bg-stone-100 text-stone-500 hover:bg-stone-200"}`}>
            <s.icon size={13} weight={step === s.id ? "fill" : "regular"} />
            {s.label}
          </button>
        ))}
        {golive && (
          <span data-testid="cm-golive-score-chip"
            className={`ml-auto px-3 py-1.5 rounded-full text-[11px] font-bold ${
              golive.ready ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>
            Go-Live: %{golive.score}
          </span>
        )}
      </div>

      <div className="bg-white rounded-2xl border border-stone-200 p-5 shadow-sm">
        {step === 0 && (
          <div className="space-y-4" data-testid="cm-step-channels">
            <h3 className="text-sm font-bold text-stone-700">1 · Kanalları seçin</h3>
            <div className="grid grid-cols-4 gap-2.5">
              {catalog.map((c) => (
                <button key={c.channel_id} data-testid={`cm-channel-${c.channel_id}`}
                  onClick={() => {
                    const n = new Set(selected);
                    n.has(c.channel_id) ? n.delete(c.channel_id) : n.add(c.channel_id);
                    setSelected(n);
                  }}
                  className={`text-left rounded-xl border-2 p-3 transition-colors ${
                    selected.has(c.channel_id) ? "border-cyan-600 bg-cyan-50" : "border-stone-200 hover:border-cyan-300"}`}>
                  <div className="w-7 h-7 rounded-lg flex items-center justify-center text-white text-xs font-black mb-1.5" style={{ background: c.color }}>
                    {c.name[0]}
                  </div>
                  <div className="text-[11px] font-bold text-stone-800">{c.name}</div>
                  <div className="text-[9px] text-stone-400">Komisyon ~%{c.commission_pct}</div>
                </button>
              ))}
            </div>
            <button onClick={saveChannels} disabled={busy} data-testid="cm-save-channels-btn"
              className="px-4 py-2 rounded-lg bg-cyan-700 text-white text-xs font-bold hover:bg-cyan-800 disabled:opacity-50 flex items-center gap-1.5">
              {selected.size} Kanalı Bağla <ArrowRight size={13} />
            </button>
          </div>
        )}

        {step === 1 && (
          <div className="space-y-4" data-testid="cm-step-mapping">
            <h3 className="text-sm font-bold text-stone-700">2 · Oda eşleme (1:1 kural — Cloudbeds standardı)</h3>
            <p className="text-[11px] text-stone-500">Her oda tipinin kanal tarafındaki oda kodunu (external ID) girin.</p>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-[10px] uppercase text-stone-400 border-b border-stone-100">
                    <th className="py-2 pr-3">Oda Tipi</th>
                    {[...selected].map((cid) => <th key={cid} className="py-2 pr-3">{catalog.find((c) => c.channel_id === cid)?.name || cid}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {roomTypes.map((rt) => (
                    <tr key={rt.id} className="border-b border-stone-50">
                      <td className="py-2 pr-3 font-semibold text-stone-700">{rt.name}</td>
                      {[...selected].map((cid) => (
                        <td key={cid} className="py-1.5 pr-3">
                          <input value={mappings[`${rt.id}|${cid}`] || ""} placeholder="örn. 123456"
                            data-testid={`cm-map-${rt.id}-${cid}`}
                            onChange={(e) => setMappings({ ...mappings, [`${rt.id}|${cid}`]: e.target.value })}
                            className="w-28 rounded border border-stone-200 px-2 py-1 text-xs" />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <button onClick={saveMapping} disabled={busy} data-testid="cm-save-mapping-btn"
              className="px-4 py-2 rounded-lg bg-cyan-700 text-white text-xs font-bold hover:bg-cyan-800 disabled:opacity-50 flex items-center gap-1.5">
              Eşlemeleri Kaydet <ArrowRight size={13} />
            </button>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4" data-testid="cm-step-sync">
            <h3 className="text-sm font-bold text-stone-700">3 · Senkron ayarları (ARI kapsamı)</h3>
            <div className="grid grid-cols-2 gap-3 max-w-lg">
              {[
                { k: "full", t: "Full", d: "Müsaitlik + Fiyat + Kısıtların tamamını biz yönetelim." },
                { k: "custom", t: "Custom", d: "Sadece seçili kapsamı push edelim, gerisi sizde kalsın." },
              ].map((o) => (
                <button key={o.k} onClick={() => setAriScope(o.k)} data-testid={`cm-ari-${o.k}`}
                  className={`text-left rounded-xl border-2 p-4 ${ariScope === o.k ? "border-cyan-600 bg-cyan-50" : "border-stone-200 hover:border-cyan-300"}`}>
                  <div className="text-xs font-bold text-stone-800">{o.t}</div>
                  <div className="text-[10px] text-stone-500 mt-1">{o.d}</div>
                </button>
              ))}
            </div>
            <div className="max-w-sm">
              <label className="text-[10px] font-bold uppercase text-stone-500">Push sıklığı: {pushFreq} dk</label>
              <input type="range" min="5" max="240" step="5" value={pushFreq} onChange={(e) => setPushFreq(parseInt(e.target.value))}
                className="w-full accent-cyan-700" data-testid="cm-freq-slider" />
            </div>
            <label className="flex items-center gap-2 text-xs text-stone-700 cursor-pointer" data-testid="cm-stopsell-toggle">
              <input type="checkbox" checked={stopSell} onChange={(e) => setStopSell(e.target.checked)} className="accent-cyan-700" />
              Müsaitlik 0 olunca otomatik stop-sell gönder
            </label>
            <button onClick={saveSync} disabled={busy} data-testid="cm-save-sync-btn"
              className="px-4 py-2 rounded-lg bg-cyan-700 text-white text-xs font-bold hover:bg-cyan-800 disabled:opacity-50 flex items-center gap-1.5">
              Kaydet <ArrowRight size={13} />
            </button>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-4" data-testid="cm-step-push">
            <h3 className="text-sm font-bold text-stone-700">4 · Test push</h3>
            <p className="text-[11px] text-stone-500">Bağlı kanallara örnek ARI paketi gönderilir. Gerçek OTA API anahtarları eklenene kadar push mock'lanır.</p>
            <button onClick={testPush} disabled={busy} data-testid="cm-test-push-btn"
              className="px-4 py-2 rounded-lg bg-gradient-to-r from-cyan-700 to-blue-700 text-white text-xs font-bold hover:opacity-90 disabled:opacity-50 flex items-center gap-1.5">
              <Lightning size={13} weight="fill" /> {busy ? "Gönderiliyor..." : "Test Push Gönder"}
            </button>
            {pushResults && (
              <div className="space-y-1.5" data-testid="cm-push-results">
                {pushResults.map((r) => (
                  <div key={r.channel_id} className="flex items-center gap-2 text-xs bg-emerald-50 rounded-lg px-3 py-2">
                    <CheckCircle size={14} weight="fill" className="text-emerald-500" />
                    <span className="flex-1">{r.name}</span>
                    <span className="text-[9px] font-bold text-amber-600 uppercase">Mock</span>
                    <span className="text-[10px] font-bold text-emerald-600">BAŞARILI</span>
                  </div>
                ))}
                <button onClick={() => setStep(4)} data-testid="cm-push-next-btn"
                  className="mt-2 px-4 py-2 rounded-lg bg-cyan-700 text-white text-xs font-bold hover:bg-cyan-800 flex items-center gap-1.5">
                  Go-Live Kontrolüne Geç <ArrowRight size={13} />
                </button>
              </div>
            )}
          </div>
        )}

        {step === 4 && (
          <div className="space-y-4" data-testid="cm-step-golive">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-stone-700">5 · Go-Live kontrol listesi</h3>
              <button onClick={loadGolive} className="text-[10px] text-cyan-700 font-semibold" data-testid="cm-golive-refresh">Yenile</button>
            </div>
            {golive && (
              <>
                <div className={`rounded-xl p-4 ${golive.ready ? "bg-emerald-50 border border-emerald-200" : "bg-amber-50 border border-amber-200"}`} data-testid="cm-golive-banner">
                  <div className="text-2xl font-black">{golive.ready ? "🛰️ Kanallar canlıya hazır!" : `%${golive.score} hazır`}</div>
                  <div className="text-[11px] text-stone-600 mt-1">
                    {golive.channels_connected} kanal bağlı · Eşleme kapsamı %{golive.mapping_coverage_pct}
                  </div>
                </div>
                <div className="space-y-1.5">
                  {golive.checks.map((c) => (
                    <div key={c.key} className="flex items-center gap-2 text-xs" data-testid={`cm-check-${c.key}`}>
                      {c.ok ? <CheckCircle size={15} weight="fill" className="text-emerald-500" /> : <Circle size={15} className="text-stone-300" />}
                      <span className={c.ok ? "text-stone-700" : "text-stone-400"}>{c.label}</span>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
