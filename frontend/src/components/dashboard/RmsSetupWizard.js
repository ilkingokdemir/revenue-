import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Bed, ShieldCheck, Target, Database, Robot, RocketLaunch,
  CheckCircle, Circle, Plus, Trash, ArrowRight, Lightning,
} from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STEPS = [
  { id: 0, label: "Odalar & Baz Fiyat", icon: Bed },
  { id: 1, label: "Fiyat Koruması", icon: ShieldCheck },
  { id: 2, label: "Rakip Seti", icon: Target },
  { id: 3, label: "Veri Kaynağı", icon: Database },
  { id: 4, label: "Fiyatlama Modu", icon: Robot },
  { id: 5, label: "Go-Live", icon: RocketLaunch },
];

export default function RmsSetupWizard({ activePropertyId, properties }) {
  const pid = activePropertyId && activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default");
  const [step, setStep] = useState(0);
  const [roomTypes, setRoomTypes] = useState([]);
  const [setup, setSetup] = useState({});
  const [compset, setCompset] = useState([]);
  const [golive, setGolive] = useState(null);
  const [queue, setQueue] = useState([]);
  const [busy, setBusy] = useState(false);

  const [baseRoomId, setBaseRoomId] = useState("");
  const [basePrice, setBasePrice] = useState("");
  const [offsets, setOffsets] = useState({});
  const [minRate, setMinRate] = useState("");
  const [maxRate, setMaxRate] = useState("");
  const [newComp, setNewComp] = useState("");
  const [mode, setMode] = useState("");
  const [ppd, setPpd] = useState(2);

  const load = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/rms/setup/${pid}`);
      setRoomTypes(data.room_types || []);
      setCompset(data.compset || []);
      const s = data.setup || {};
      setSetup(s);
      if (s.base_room_type_id) setBaseRoomId(s.base_room_type_id);
      else if (data.room_types?.length) setBaseRoomId(data.room_types[0].id);
      if (s.base_price) setBasePrice(String(s.base_price));
      if (s.min_rate) setMinRate(String(s.min_rate));
      if (s.max_rate) setMaxRate(String(s.max_rate));
      if (s.mode) setMode(s.mode);
      if (s.pushes_per_day) setPpd(s.pushes_per_day);
      const o = {};
      (s.offsets || []).forEach((x) => { o[x.room_type_id] = x; });
      setOffsets(o);
    } catch { toast.error("Kurulum verisi yüklenemedi"); }
  }, [pid]);

  const loadGolive = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/rms/golive/${pid}`);
      setGolive(data);
    } catch { /* silent */ }
  }, [pid]);

  const loadQueue = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/rms/copilot/queue/${pid}`);
      setQueue(data.queue || []);
    } catch { /* silent */ }
  }, [pid]);

  useEffect(() => { load(); loadGolive(); loadQueue(); }, [load, loadGolive, loadQueue]);

  const saveRooms = async () => {
    if (!baseRoomId || !parseFloat(basePrice)) { toast.error("Baz oda ve baz fiyat girin"); return; }
    setBusy(true);
    try {
      const body = {
        base_room_type_id: baseRoomId, base_price: parseFloat(basePrice),
        offsets: roomTypes.filter((r) => r.id !== baseRoomId).map((r) => ({
          room_type_id: r.id,
          mode: offsets[r.id]?.mode || "pct",
          value: parseFloat(offsets[r.id]?.value || 0),
        })),
      };
      const { data } = await axios.post(`${API}/rms/setup/${pid}/rooms`, body);
      toast.success(`${data.derived.length} oda tipi fiyatı türetildi`);
      loadGolive(); setStep(1);
    } catch (e) { toast.error(e.response?.data?.detail || "Kaydedilemedi"); }
    setBusy(false);
  };

  const saveGuardrails = async () => {
    setBusy(true);
    try {
      await axios.post(`${API}/rms/setup/${pid}/guardrails`, { min_rate: parseFloat(minRate), max_rate: parseFloat(maxRate) });
      toast.success("Fiyat koruması kaydedildi"); loadGolive(); setStep(2);
    } catch (e) { toast.error(e.response?.data?.detail || "Min > 0 ve Max > Min olmalı"); }
    setBusy(false);
  };

  const addComp = async () => {
    if (!newComp.trim()) return;
    try {
      await axios.post(`${API}/rms/setup/${pid}/compset`, { names: [newComp.trim()] });
      setNewComp(""); toast.success("Rakip eklendi");
      const { data } = await axios.get(`${API}/rms/setup/${pid}`);
      setCompset(data.compset || []); loadGolive();
    } catch { toast.error("Eklenemedi"); }
  };

  const removeComp = async (cid) => {
    try {
      await axios.delete(`${API}/compset/${pid}/${cid}`);
      setCompset(compset.filter((c) => c.id !== cid)); loadGolive();
    } catch { toast.error("Silinemedi"); }
  };

  const saveSource = async (src) => {
    try {
      await axios.post(`${API}/rms/setup/${pid}/data-source`, { source: src });
      setSetup({ ...setup, data_source: src });
      toast.success(src === "pms" ? "PMS bağlantısı: Bağlantı Kataloğu'ndan sağlayıcı seçin" : "Veri kaynağı kaydedildi");
      loadGolive(); setStep(4);
    } catch { toast.error("Kaydedilemedi"); }
  };

  const saveMode = async () => {
    if (!mode) { toast.error("Bir mod seçin"); return; }
    setBusy(true);
    try {
      await axios.post(`${API}/rms/setup/${pid}/mode`, { mode, pushes_per_day: ppd });
      toast.success(`Mod: ${mode.toUpperCase()} · günde ${ppd}× push`);
      loadGolive(); setStep(5);
    } catch { toast.error("Kaydedilemedi"); }
    setBusy(false);
  };

  const generate = async () => {
    setBusy(true);
    try {
      const { data } = await axios.post(`${API}/rms/copilot/generate/${pid}`);
      toast.success(data.auto_applied
        ? `Autopilot: ${data.count} fiyat otomatik uygulandı`
        : `${data.count} öneri kuyruğa eklendi — onayınızı bekliyor`);
      loadQueue();
    } catch (e) { toast.error(e.response?.data?.detail || "Öneri üretilemedi"); }
    setBusy(false);
  };

  const decide = async (ids, action) => {
    try {
      const { data } = await axios.post(`${API}/rms/copilot/queue/${pid}/decide`, { ids, action });
      toast.success(action === "approve" ? `${data.applied} fiyat uygulandı` : "Reddedildi");
      loadQueue();
    } catch { toast.error("İşlem başarısız"); }
  };

  const inputCls = "w-full rounded-lg border border-stone-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500";

  return (
    <div className="p-6 max-w-5xl" data-testid="rms-setup-wizard">
      <div className="mb-5">
        <h2 className="text-xl font-bold text-stone-800">RMS Hızlı Kurulum</h2>
        <p className="text-xs text-stone-500 mt-1">30 dakikada gelir yönetimini canlıya alın — RoomPriceGenie hızında, Duetto derinliğinde.</p>
      </div>

      <div className="flex gap-1.5 mb-6 flex-wrap" data-testid="rms-wizard-stepper">
        {STEPS.map((s) => (
          <button key={s.id} onClick={() => setStep(s.id)} data-testid={`rms-step-${s.id}`}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[11px] font-semibold transition-colors ${
              step === s.id ? "bg-indigo-600 text-white" : "bg-stone-100 text-stone-500 hover:bg-stone-200"}`}>
            <s.icon size={13} weight={step === s.id ? "fill" : "regular"} />
            {s.label}
          </button>
        ))}
        {golive && (
          <span data-testid="rms-golive-score-chip"
            className={`ml-auto px-3 py-1.5 rounded-full text-[11px] font-bold ${
              golive.ready ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>
            Go-Live: %{golive.score}
          </span>
        )}
      </div>

      <div className="bg-white rounded-2xl border border-stone-200 p-5 shadow-sm">
        {step === 0 && (
          <div className="space-y-4" data-testid="rms-step-rooms">
            <h3 className="text-sm font-bold text-stone-700">1 · Baz oda + fiyat farkları</h3>
            <p className="text-[11px] text-stone-500">Giriş seviyesi odanızın fiyatını belirleyin; diğer oda tipleri % veya tutar farkıyla otomatik türetilir.</p>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[10px] font-bold uppercase text-stone-500">Baz Oda Tipi</label>
                <select value={baseRoomId} onChange={(e) => setBaseRoomId(e.target.value)} className={inputCls} data-testid="rms-base-room-select">
                  {roomTypes.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
                </select>
              </div>
              <div>
                <label className="text-[10px] font-bold uppercase text-stone-500">Baz Fiyat (£)</label>
                <input type="number" value={basePrice} onChange={(e) => setBasePrice(e.target.value)} placeholder="90" className={inputCls} data-testid="rms-base-price-input" />
              </div>
            </div>
            <div className="space-y-2">
              {roomTypes.filter((r) => r.id !== baseRoomId).map((r) => (
                <div key={r.id} className="flex items-center gap-2 text-xs">
                  <span className="flex-1 truncate text-stone-700">{r.name}</span>
                  <select value={offsets[r.id]?.mode || "pct"} data-testid={`rms-offset-mode-${r.id}`}
                    onChange={(e) => setOffsets({ ...offsets, [r.id]: { ...offsets[r.id], mode: e.target.value } })}
                    className="rounded border border-stone-200 px-2 py-1 text-xs">
                    <option value="pct">%</option>
                    <option value="amount">£</option>
                  </select>
                  <input type="number" value={offsets[r.id]?.value ?? ""} placeholder="+20" data-testid={`rms-offset-value-${r.id}`}
                    onChange={(e) => setOffsets({ ...offsets, [r.id]: { ...offsets[r.id], mode: offsets[r.id]?.mode || "pct", value: e.target.value } })}
                    className="w-24 rounded border border-stone-200 px-2 py-1 text-xs" />
                  {basePrice && (
                    <span className="w-20 text-right font-mono text-stone-500">
                      £{((offsets[r.id]?.mode || "pct") === "pct"
                        ? parseFloat(basePrice || 0) * (1 + parseFloat(offsets[r.id]?.value || 0) / 100)
                        : parseFloat(basePrice || 0) + parseFloat(offsets[r.id]?.value || 0)).toFixed(0)}
                    </span>
                  )}
                </div>
              ))}
            </div>
            <button onClick={saveRooms} disabled={busy} data-testid="rms-save-rooms-btn"
              className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-xs font-bold hover:bg-indigo-700 disabled:opacity-50 flex items-center gap-1.5">
              Kaydet & Fiyatları Türet <ArrowRight size={13} />
            </button>
          </div>
        )}

        {step === 1 && (
          <div className="space-y-4" data-testid="rms-step-guardrails">
            <h3 className="text-sm font-bold text-stone-700">2 · Min/Max fiyat koruması (guardrail)</h3>
            <p className="text-[11px] text-stone-500">AI hiçbir zaman bu sınırların dışına çıkamaz — tam kontrol sizde.</p>
            <div className="grid grid-cols-2 gap-3 max-w-sm">
              <div>
                <label className="text-[10px] font-bold uppercase text-stone-500">Min Fiyat (£)</label>
                <input type="number" value={minRate} onChange={(e) => setMinRate(e.target.value)} placeholder="60" className={inputCls} data-testid="rms-min-rate-input" />
              </div>
              <div>
                <label className="text-[10px] font-bold uppercase text-stone-500">Max Fiyat (£)</label>
                <input type="number" value={maxRate} onChange={(e) => setMaxRate(e.target.value)} placeholder="300" className={inputCls} data-testid="rms-max-rate-input" />
              </div>
            </div>
            <button onClick={saveGuardrails} disabled={busy} data-testid="rms-save-guardrails-btn"
              className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-xs font-bold hover:bg-indigo-700 disabled:opacity-50 flex items-center gap-1.5">
              Kaydet <ArrowRight size={13} />
            </button>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4" data-testid="rms-step-compset">
            <h3 className="text-sm font-bold text-stone-700">3 · Rakip seti (en az 2 otel)</h3>
            <div className="flex gap-2 max-w-md">
              <input value={newComp} onChange={(e) => setNewComp(e.target.value)} onKeyDown={(e) => e.key === "Enter" && addComp()}
                placeholder="Rakip otel adı" className={inputCls} data-testid="rms-comp-input" />
              <button onClick={addComp} data-testid="rms-comp-add-btn"
                className="px-3 rounded-lg bg-stone-800 text-white hover:bg-stone-700"><Plus size={14} /></button>
            </div>
            <div className="space-y-1.5">
              {compset.map((c) => (
                <div key={c.id} className="flex items-center gap-2 text-xs bg-stone-50 rounded-lg px-3 py-2" data-testid={`rms-comp-row-${c.id}`}>
                  <Target size={13} className="text-indigo-500" />
                  <span className="flex-1">{c.name}</span>
                  <button onClick={() => removeComp(c.id)} className="text-stone-400 hover:text-red-500" data-testid={`rms-comp-del-${c.id}`}><Trash size={13} /></button>
                </div>
              ))}
              {compset.length === 0 && <p className="text-[11px] text-stone-400">Henüz rakip eklenmedi.</p>}
            </div>
            <button onClick={() => setStep(3)} data-testid="rms-compset-next-btn"
              className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-xs font-bold hover:bg-indigo-700 flex items-center gap-1.5">
              Devam <ArrowRight size={13} />
            </button>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-4" data-testid="rms-step-source">
            <h3 className="text-sm font-bold text-stone-700">4 · Veri kaynağı</h3>
            <div className="grid grid-cols-3 gap-3">
              {[
                { k: "pms", t: "PMS Bağla", d: "Cloudbeds, Mews, Apaleo… Bağlantı Kataloğu üzerinden iki yönlü senkron." },
                { k: "csv", t: "CSV / Excel", d: "Rezervasyon geçmişinizi Veri Göçü Merkezi'nden içe aktarın." },
                { k: "manual", t: "Manuel Doluluk", d: "PMS'siz çalışın — dolulukları elle girin, AI yine fiyatlar." },
              ].map((o) => (
                <button key={o.k} onClick={() => saveSource(o.k)} data-testid={`rms-source-${o.k}`}
                  className={`text-left rounded-xl border-2 p-4 transition-colors ${
                    setup.data_source === o.k ? "border-indigo-500 bg-indigo-50" : "border-stone-200 hover:border-indigo-300"}`}>
                  <div className="text-xs font-bold text-stone-800">{o.t}</div>
                  <div className="text-[10px] text-stone-500 mt-1">{o.d}</div>
                </button>
              ))}
            </div>
          </div>
        )}

        {step === 4 && (
          <div className="space-y-4" data-testid="rms-step-mode">
            <h3 className="text-sm font-bold text-stone-700">5 · Fiyatlama modu</h3>
            <div className="grid grid-cols-3 gap-3">
              {[
                { k: "autopilot", t: "Autopilot", d: "Fiyatlar guardrail içinde tam otomatik push edilir. (RoomPriceGenie tarzı)" },
                { k: "copilot", t: "Co-Pilot", d: "AI önerir, siz onaylarsınız — onay kuyruğuna düşer." },
                { k: "manual", t: "Manuel", d: "Sadece öneri görürsünüz, push yok." },
              ].map((o) => (
                <button key={o.k} onClick={() => setMode(o.k)} data-testid={`rms-mode-${o.k}`}
                  className={`text-left rounded-xl border-2 p-4 transition-colors ${
                    mode === o.k ? "border-indigo-500 bg-indigo-50" : "border-stone-200 hover:border-indigo-300"}`}>
                  <div className="text-xs font-bold text-stone-800 flex items-center gap-1.5">
                    {o.k !== "manual" && <Lightning size={13} weight="fill" className="text-amber-500" />}{o.t}
                  </div>
                  <div className="text-[10px] text-stone-500 mt-1">{o.d}</div>
                </button>
              ))}
            </div>
            <div className="max-w-sm">
              <label className="text-[10px] font-bold uppercase text-stone-500">Push sıklığı: günde {ppd}×</label>
              <input type="range" min="1" max="24" value={ppd} onChange={(e) => setPpd(parseInt(e.target.value))}
                className="w-full accent-indigo-600" data-testid="rms-ppd-slider" />
            </div>
            <button onClick={saveMode} disabled={busy} data-testid="rms-save-mode-btn"
              className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-xs font-bold hover:bg-indigo-700 disabled:opacity-50 flex items-center gap-1.5">
              Kaydet <ArrowRight size={13} />
            </button>
          </div>
        )}

        {step === 5 && (
          <div className="space-y-4" data-testid="rms-step-golive">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-stone-700">6 · Go-Live kontrol listesi</h3>
              <button onClick={loadGolive} className="text-[10px] text-indigo-600 font-semibold" data-testid="rms-golive-refresh">Yenile</button>
            </div>
            {golive && (
              <>
                <div className={`rounded-xl p-4 ${golive.ready ? "bg-emerald-50 border border-emerald-200" : "bg-amber-50 border border-amber-200"}`} data-testid="rms-golive-banner">
                  <div className="text-2xl font-black">{golive.ready ? "🚀 Canlıya hazırsınız!" : `%${golive.score} hazır`}</div>
                  <div className="text-[11px] text-stone-600 mt-1">
                    {golive.ready ? "Aşağıdan ilk fiyat önerilerinizi üretin." : "Eksik adımları tamamlayın (%80+ gerekli)."}
                  </div>
                </div>
                <div className="space-y-1.5">
                  {golive.checks.map((c) => (
                    <div key={c.key} className="flex items-center gap-2 text-xs" data-testid={`rms-check-${c.key}`}>
                      {c.ok ? <CheckCircle size={15} weight="fill" className="text-emerald-500" /> : <Circle size={15} className="text-stone-300" />}
                      <span className={c.ok ? "text-stone-700" : "text-stone-400"}>{c.label}</span>
                    </div>
                  ))}
                </div>
              </>
            )}
            <button onClick={generate} disabled={busy} data-testid="rms-generate-btn"
              className="px-4 py-2 rounded-lg bg-gradient-to-r from-emerald-600 to-teal-600 text-white text-xs font-bold hover:opacity-90 disabled:opacity-50 flex items-center gap-1.5">
              <Lightning size={13} weight="fill" /> 14 Günlük Fiyat Önerisi Üret
            </button>
            {queue.length > 0 && (
              <div className="space-y-2" data-testid="rms-copilot-queue">
                <div className="flex items-center justify-between">
                  <div className="text-[10px] font-bold uppercase text-stone-500">Co-Pilot onay kuyruğu · {queue.length} öneri</div>
                  <div className="flex gap-2">
                    <button onClick={() => decide(queue.map((q) => q.id), "approve")} data-testid="rms-approve-all-btn"
                      className="px-2.5 py-1 rounded bg-emerald-600 text-white text-[10px] font-bold hover:bg-emerald-700">Tümünü Onayla</button>
                    <button onClick={() => decide(queue.map((q) => q.id), "reject")} data-testid="rms-reject-all-btn"
                      className="px-2.5 py-1 rounded bg-stone-200 text-stone-600 text-[10px] font-bold hover:bg-stone-300">Tümünü Reddet</button>
                  </div>
                </div>
                {queue.map((q) => (
                  <div key={q.id} className="flex items-center gap-2 text-xs bg-stone-50 rounded-lg px-3 py-2" data-testid={`rms-queue-row-${q.date}`}>
                    <span className="font-mono text-stone-500 w-20">{q.date}</span>
                    <span className="flex-1 text-stone-600 truncate">{q.reason}</span>
                    <span className="font-mono text-stone-400 line-through">£{q.current_rate}</span>
                    <span className={`font-mono font-bold ${q.suggested_rate > q.current_rate ? "text-emerald-600" : "text-red-500"}`}>£{q.suggested_rate}</span>
                    <button onClick={() => decide([q.id], "approve")} className="text-emerald-600 hover:text-emerald-700 font-bold" data-testid={`rms-approve-${q.date}`}>✓</button>
                    <button onClick={() => decide([q.id], "reject")} className="text-stone-400 hover:text-red-500 font-bold" data-testid={`rms-reject-${q.date}`}>✕</button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
