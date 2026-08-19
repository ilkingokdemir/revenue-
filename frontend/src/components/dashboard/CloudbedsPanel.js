import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { CloudArrowUp, PaperPlaneTilt, DownloadSimple } from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

export default function CloudbedsPanel({ activePropertyId, properties = [] }) {
  const pid = activePropertyId && activePropertyId !== "all" ? activePropertyId : properties[0]?.id || "default";
  const [status, setStatus] = useState(null);
  const [log, setLog] = useState([]);
  const [apiKey, setApiKey] = useState("");
  const [cbPid, setCbPid] = useState("");
  const [rateId, setRateId] = useState("RMS-RATE");
  const [days, setDays] = useState(14);
  const [busy, setBusy] = useState(false);
  const [lastPush, setLastPush] = useState(null);
  const [rateMapData, setRateMapData] = useState(null);
  const [rateMap, setRateMap] = useState({});
  const [autoPush, setAutoPush] = useState(false);
  const [autoDays, setAutoDays] = useState(14);
  const [pushAvail, setPushAvail] = useState(false);
  const [preview, setPreview] = useState(null);

  const openPreview = async () => {
    setBusy(true);
    try {
      const r = await axios.get(`${API}/api/cloudbeds/push-preview/${pid}?days=${+days}`, { withCredentials: true });
      if (!r.data.table?.length) { toast.info("Önizlenecek fiyat yok — oda tipi eşlemesi ve fiyat gerekli"); return; }
      setPreview(r.data);
    } catch { toast.error("Önizleme yüklenemedi"); } finally { setBusy(false); }
  };

  const confirmPush = async () => {
    setPreview(null);
    await pushRms();
  };

  const load = useCallback(async () => {
    try {
      const [s, l, rm] = await Promise.all([
        axios.get(`${API}/api/cloudbeds/status/${pid}`, { withCredentials: true }),
        axios.get(`${API}/api/cloudbeds/log/${pid}`, { withCredentials: true }),
        axios.get(`${API}/api/cloudbeds/rate-map/${pid}`, { withCredentials: true }),
      ]);
      setStatus(s.data); setLog(l.data.log || []);
      setRateMapData(rm.data); setRateMap(rm.data.rate_map || {});
      setAutoPush(!!rm.data.auto_push); setAutoDays(rm.data.auto_push_days || 14);
    } catch { toast.error("Cloudbeds durumu yüklenemedi"); }
  }, [pid]);

  useEffect(() => { load(); }, [load]);

  const saveConfig = async () => {
    if (!apiKey.trim() && !cbPid.trim() && !rateId.trim()) { toast.error("API key, propertyID veya rateID girin"); return; }
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/cloudbeds/config/${pid}`, { api_key: apiKey, cb_property_id: cbPid, rate_id: rateId }, { withCredentials: true });
      toast.success(r.data.mode === "live" ? "Kaydedildi — CANLI mod aktif" : "Kaydedildi (API key yok — hâlâ MOCK)");
      setApiKey(""); load();
    } catch { toast.error("Kaydedilemedi"); } finally { setBusy(false); }
  };

  const testConn = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/cloudbeds/test-connection/${pid}`, {}, { withCredentials: true });
      toast.success(`Bağlantı OK — ${r.data.hotels_found} tesis bulundu`);
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Bağlantı başarısız"); } finally { setBusy(false); }
  };

  const pushRms = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/cloudbeds/push-from-rms/${pid}`, { days: +days, rate_id: rateId, include_availability: pushAvail }, { withCredentials: true });
      setLastPush(r.data);
      toast.success(r.data.mocked ? `MOCK push simüle edildi (${r.data.pushed_days} gün${r.data.availability_days ? ` + ${r.data.availability_days} gün müsaitlik` : ""})` : r.data.pushed_days > 0 ? `${r.data.pushed_days} günlük fiyat${r.data.availability_days ? ` + müsaitlik` : ""} Cloudbeds'e gönderildi` : r.data.message);
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Push başarısız"); } finally { setBusy(false); }
  };

  const pullRes = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/cloudbeds/pull-reservations/${pid}`, {}, { withCredentials: true });
      toast.success(r.data.mocked ? "MOCK — API key girilmeden rezervasyon çekilemez" : `${r.data.imported} rezervasyon içe aktarıldı`);
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Çekme başarısız"); } finally { setBusy(false); }
  };

  const runCertify = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/cloudbeds/certify/${pid}`, {}, { withCredentials: true });
      setStatus((s) => ({ ...s, certification: r.data }));
      toast.success(r.data.passed ? `Sertifikasyon GEÇTİ (${r.data.mode === "live" ? "CANLI" : "MOCK"})` : "Sertifikasyon BAŞARISIZ — kontrolleri inceleyin");
    } catch (e) { toast.error(e.response?.data?.detail || "Sertifikasyon çalıştırılamadı"); } finally { setBusy(false); }
  };

  const saveRateMap = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/cloudbeds/rate-map/${pid}`, { rate_map: rateMap }, { withCredentials: true });
      toast.success(`${r.data.mapped} oda tipi eşlemesi kaydedildi`);
      load();
    } catch { toast.error("Eşleme kaydedilemedi"); } finally { setBusy(false); }
  };

  const saveAutoPush = async (enabled) => {
    try {
      const r = await axios.post(`${API}/api/cloudbeds/auto-push/${pid}`, { enabled, days: +autoDays, push_availability: pushAvail }, { withCredentials: true });
      setAutoPush(r.data.auto_push);
      toast.success(r.data.auto_push ? "🌙 Otomatik gece push AÇIK — robot her gece fiyatları Cloudbeds'e basacak" : "Otomatik push kapatıldı");
    } catch { toast.error("Kaydedilemedi"); }
  };

  const live = status?.mode === "live";
  const cert = status?.certification;

  return (
    <div className="p-5 max-w-[1100px] mx-auto space-y-6" data-testid="cloudbeds-panel">
      <div>
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          <CloudArrowUp size={13} weight="fill" className="text-sky-500" /><span>PMS Adaptörü</span>
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">Cloudbeds Bağlantısı</h1>
        <p className="text-sm text-stone-500 mt-1">Cloudbeds kullanan otelleri platforma bağlayın: fiyat push (putRate) ve rezervasyon çekme (getReservations).</p>
      </div>

      {status && (
        <div className={`rounded-xl border p-4 flex flex-wrap items-center justify-between gap-3 ${live ? "bg-emerald-50 border-emerald-200" : "bg-amber-50 border-amber-200"}`} data-testid="cb-status-box">
          <div>
            <span className={`px-2.5 py-1 rounded-full text-[11px] font-black ${live ? "bg-emerald-600 text-white" : "bg-amber-500 text-white"}`} data-testid="cb-mode-badge">{live ? "CANLI MOD" : "MOCK MOD"}</span>
            <span className="text-sm text-stone-600 ml-3">{status.api_key_set ? "API key kayıtlı" : "API key girilmedi"} · {status.total_pushes} işlem kaydı</span>
          </div>
          {live && <button onClick={testConn} disabled={busy} data-testid="cb-test-btn" className="px-3 py-1.5 rounded-lg bg-stone-900 text-white text-[12px] font-bold disabled:opacity-50">Bağlantıyı Test Et</button>}
        </div>
      )}
      {!live && status && <p className="text-[12px] text-amber-700 -mt-3">{status.note}</p>}

      <section className="grid md:grid-cols-2 gap-4">
        <div className="bg-white border border-stone-200 rounded-xl p-4 space-y-2.5" data-testid="cb-config-form">
          <h2 className="text-base font-bold text-stone-800">Kimlikler</h2>
          <input value={apiKey} onChange={(e) => setApiKey(e.target.value)} type="password" data-testid="cb-apikey-input" className="w-full border border-stone-300 rounded-lg px-2.5 py-2 text-sm" placeholder="Cloudbeds API Key (x-api-key)" />
          <input value={cbPid} onChange={(e) => setCbPid(e.target.value)} data-testid="cb-pid-input" className="w-full border border-stone-300 rounded-lg px-2.5 py-2 text-sm" placeholder="Cloudbeds propertyID (opsiyonel)" />
          <button onClick={saveConfig} disabled={busy} data-testid="cb-save-config-btn" className="px-3 py-2 rounded-lg bg-sky-600 text-white text-sm font-bold disabled:opacity-50">Kaydet & Canlıya Geç</button>
          <p className="text-[11px] text-stone-400">Account → Apps & Marketplace → API Credentials (scope: read:hotel, read:reservation, read:rate, write:rate)</p>
        </div>

        <div className="bg-white border border-stone-200 rounded-xl p-4 space-y-2.5" data-testid="cb-push-form">
          <h2 className="text-base font-bold text-stone-800">RMS'ten Cloudbeds'e Gönder</h2>
          <div className="grid grid-cols-2 gap-2">
            <label className="text-[11px] text-stone-500 font-bold">Gün sayısı (maks 30)
              <input type="number" min={1} max={30} value={days} onChange={(e) => setDays(e.target.value)} data-testid="cb-days-input" className="block w-full border border-stone-300 rounded-lg px-2 py-2 text-sm mt-0.5" />
            </label>
            <label className="text-[11px] text-stone-500 font-bold">rateID
              <input value={rateId} onChange={(e) => setRateId(e.target.value)} data-testid="cb-rateid-input" className="block w-full border border-stone-300 rounded-lg px-2 py-2 text-sm mt-0.5" />
            </label>
          </div>
          <div className="flex gap-2 flex-wrap items-center">
            <button onClick={openPreview} disabled={busy} data-testid="cb-preview-btn" className="px-3 py-2 rounded-lg bg-indigo-600 text-white text-sm font-bold disabled:opacity-50">👁 Önizle & Gönder</button>
            <button onClick={pushRms} disabled={busy} data-testid="cb-push-btn" className="px-3 py-2 rounded-lg bg-stone-900 text-white text-sm font-bold disabled:opacity-50 flex items-center gap-1.5"><PaperPlaneTilt size={14} /> Direkt Push</button>
            <button onClick={pullRes} disabled={busy} data-testid="cb-pull-btn" className="px-3 py-2 rounded-lg border border-stone-300 text-stone-700 text-sm font-bold disabled:opacity-50 flex items-center gap-1.5"><DownloadSimple size={14} /> Rezervasyon Çek</button>
            <label className="text-[11px] font-bold text-stone-600 flex items-center gap-1.5 ml-1">
              <input type="checkbox" checked={pushAvail} onChange={(e) => setPushAvail(e.target.checked)} data-testid="cb-avail-toggle" />
              🛏 Müsaitliği de gönder
            </label>
          </div>
          {lastPush && (
            <div className="text-[12px] bg-stone-50 border border-stone-200 rounded-lg p-2" data-testid="cb-last-push">
              {lastPush.mocked ? "🟡 MOCK" : lastPush.mocked === false ? "🟢 CANLI" : "ℹ"} · {lastPush.rooms ? `${lastPush.rooms} oda tipi · ` : ""}{lastPush.pushed_days ?? 0} gün{lastPush.message ? ` · ${lastPush.message}` : ""}
              {lastPush.per_room && (
                <div className="mt-1.5 space-y-0.5">
                  {lastPush.per_room.map((r) => (
                    <div key={r.rateID} className="text-[11px] text-stone-500" data-testid={`cb-push-room-${r.rateID}`}>
                      • {r.room_type || "Varsayılan"} → rateID <b>{r.rateID}</b> · {r.days} gün{r.sample?.[0] ? ` · örn. ${r.sample[0].startDate}: £${r.sample[0].rate}` : ""}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </section>

      {/* Push Önizleme Modalı */}
      {preview && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={() => setPreview(null)} data-testid="cb-preview-modal">
          <div className="bg-white rounded-2xl max-w-3xl w-full max-h-[80vh] flex flex-col p-5" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-base font-black text-stone-800 mb-1">👁 Push Önizleme — gönderilecek fiyatlar</h3>
            <p className="text-[11px] text-stone-500 mb-3">{preview.rooms.map((r) => `${r.room_type} → ${r.rateID}`).join(" · ")} · toplam {preview.total_prices} fiyat</p>
            <div className="overflow-auto flex-1 border border-stone-200 rounded-xl">
              <table className="w-full text-[12px]">
                <thead className="bg-stone-50 sticky top-0">
                  <tr>
                    <th className="text-left px-3 py-2 font-black text-stone-600">Tarih</th>
                    {preview.rooms.map((r) => <th key={r.rateID} className="text-right px-3 py-2 font-black text-stone-600">{r.room_type}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {preview.table.map((row) => (
                    <tr key={row.date} className="border-t border-stone-100" data-testid={`cb-preview-row-${row.date}`}>
                      <td className="px-3 py-1.5 font-bold text-stone-700">{row.date}</td>
                      {preview.rooms.map((r) => {
                        const c = row.cells[r.room_type];
                        return <td key={r.rateID} className="px-3 py-1.5 text-right">{c ? <span>£{c.rate} <span className="text-stone-400">· {c.avail} oda</span></span> : "—"}</td>;
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex justify-end gap-2 mt-4">
              <button onClick={() => setPreview(null)} data-testid="cb-preview-cancel" className="px-4 py-2 rounded-lg border border-stone-300 text-stone-600 text-sm font-bold">Vazgeç</button>
              <button onClick={confirmPush} data-testid="cb-preview-confirm" className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-bold hover:bg-emerald-700">✓ Onayla ve Gönder</button>
            </div>
          </div>
        </div>
      )}

      {/* Oda Tipi Eşleme + Otomatik Push */}
      <section className="bg-white border-2 border-sky-200 rounded-xl p-4" data-testid="cb-ratemap-section">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <div>
            <h2 className="text-base font-bold text-stone-800">🗺 Oda Tipi → Cloudbeds rateID Eşleme</h2>
            <p className="text-[12px] text-stone-500 mt-0.5">Her odanın fiyatı kendi Cloudbeds rate planına basılır — Cloudbeds aldığı fiyatı Booking.com ve diğer kanallara dağıtır.</p>
          </div>
          <div className="flex items-center gap-3 text-[12px]">
            <label className="font-bold text-stone-600 flex items-center gap-1.5">
              <input type="checkbox" checked={autoPush} onChange={(e) => saveAutoPush(e.target.checked)} data-testid="cb-autopush-toggle" />
              🌙 Otomatik gece push
            </label>
            <label className="font-bold text-stone-500">gün:
              <input type="number" min={1} max={30} value={autoDays} onChange={(e) => setAutoDays(e.target.value)}
                onBlur={() => autoPush && saveAutoPush(true)} data-testid="cb-autopush-days"
                className="w-14 ml-1 border border-stone-300 rounded-lg px-1.5 py-1 text-sm font-normal" />
            </label>
          </div>
        </div>
        <div className="space-y-1.5">
          {(rateMapData?.room_types || []).map((rt) => (
            <div key={rt.id} className="flex items-center gap-3 bg-stone-50 border border-stone-200 rounded-lg px-3 py-2" data-testid={`cb-ratemap-row-${rt.id}`}>
              <span className="flex-1 text-sm font-bold text-stone-700">{rt.name}{rt.base_rate ? <span className="text-stone-400 font-normal"> · taban £{rt.base_rate}</span> : null}</span>
              <input value={rateMap[rt.id] || ""} onChange={(e) => setRateMap((m) => ({ ...m, [rt.id]: e.target.value }))}
                placeholder="Cloudbeds rateID" data-testid={`cb-ratemap-input-${rt.id}`}
                className="w-48 border border-stone-300 rounded-lg px-2 py-1.5 text-sm" />
            </div>
          ))}
        </div>
        <button onClick={saveRateMap} disabled={busy} data-testid="cb-ratemap-save-btn"
          className="mt-3 px-3 py-2 rounded-lg bg-sky-600 text-white text-sm font-bold disabled:opacity-50">Eşlemeyi Kaydet</button>
      </section>

      <section className="bg-white border border-stone-200 rounded-xl p-4" data-testid="cb-cert-section">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-bold text-stone-800">🛡 Publisher Sertifikasyonu</h2>
            <p className="text-[12px] text-stone-500 mt-0.5">Test push + geri okuma doğrulaması. CANLI modda sertifikasyon geçilmeden fiyat push'u bloklanır — HotelRunner ile aynı güvence.</p>
          </div>
          <div className="flex items-center gap-2">
            {cert && (
              <span className={`px-2.5 py-1 rounded-full text-[11px] font-black ${cert.passed ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700"}`} data-testid="cb-cert-badge">
                {cert.passed ? "SERTİFİKALI" : "BAŞARISIZ"} · {cert.mode === "live" ? "CANLI" : "MOCK"}
              </span>
            )}
            <button onClick={runCertify} disabled={busy} data-testid="cb-certify-btn" className="px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-[12px] font-bold disabled:opacity-50">Sertifikasyonu Çalıştır</button>
          </div>
        </div>
        {cert?.checks && (
          <div className="mt-3 grid sm:grid-cols-2 gap-2" data-testid="cb-cert-checks">
            {cert.checks.map((c) => {
              const warn = !c.passed && cert.mode === "mocked" && c.name === "Kimlik yapılandırması";
              return (
                <div key={c.name} className={`flex items-start gap-2 rounded-lg border p-2 text-[12px] ${c.passed ? "bg-emerald-50 border-emerald-200" : warn ? "bg-amber-50 border-amber-200" : "bg-rose-50 border-rose-200"}`}>
                  <span>{c.passed ? "✅" : warn ? "⚠️" : "❌"}</span>
                  <span><b>{c.name}</b> — {c.detail}</span>
                </div>
              );
            })}
          </div>
        )}
        {cert?.at && <p className="text-[11px] text-stone-400 mt-2">Son sertifikasyon: {String(cert.at).slice(0, 16).replace("T", " ")}</p>}
      </section>

      <section data-testid="cb-log-section">
        <h2 className="text-base font-bold text-stone-800 mb-2">İşlem Geçmişi</h2>
        {log.length === 0 ? <div className="bg-stone-50 border border-stone-200 rounded-xl p-4 text-sm text-stone-500" data-testid="cb-log-empty">Henüz işlem yok.</div> : (
          <div className="bg-white border border-stone-200 rounded-xl overflow-x-auto">
            <table className="w-full text-sm" data-testid="cb-log-table">
              <thead><tr className="text-left text-[11px] text-stone-400 border-b border-stone-100"><th className="p-2.5">Zaman</th><th className="p-2.5">Tür</th><th className="p-2.5">Mod</th><th className="p-2.5">Sonuç</th></tr></thead>
              <tbody>
                {log.map((l) => (
                  <tr key={l.id} className="border-t border-stone-100">
                    <td className="p-2.5 text-[12px]">{String(l.created_at).slice(0, 16).replace("T", " ")}</td>
                    <td className="p-2.5">{l.kind === "rate_push" ? "Fiyat Push" : "Rezervasyon"}</td>
                    <td className="p-2.5"><span className={`px-2 py-0.5 rounded-full text-[11px] font-bold ${l.mode === "live" ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>{l.mode === "live" ? "CANLI" : "MOCK"}</span></td>
                    <td className="p-2.5 text-[12px] text-stone-500 max-w-[300px] truncate">{JSON.stringify(l.result)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
