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

  const load = useCallback(async () => {
    try {
      const [s, l] = await Promise.all([
        axios.get(`${API}/api/cloudbeds/status/${pid}`, { withCredentials: true }),
        axios.get(`${API}/api/cloudbeds/log/${pid}`, { withCredentials: true }),
      ]);
      setStatus(s.data); setLog(l.data.log || []);
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
      const r = await axios.post(`${API}/api/cloudbeds/push-from-rms/${pid}`, { days: +days, rate_id: rateId }, { withCredentials: true });
      setLastPush(r.data);
      toast.success(r.data.mocked ? `MOCK push simüle edildi (${r.data.pushed_days} gün)` : r.data.pushed_days > 0 ? `${r.data.pushed_days} günlük fiyat Cloudbeds'e gönderildi` : r.data.message);
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

  const live = status?.mode === "live";

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
          <div className="flex gap-2">
            <button onClick={pushRms} disabled={busy} data-testid="cb-push-btn" className="px-3 py-2 rounded-lg bg-stone-900 text-white text-sm font-bold disabled:opacity-50 flex items-center gap-1.5"><PaperPlaneTilt size={14} /> Fiyat Push</button>
            <button onClick={pullRes} disabled={busy} data-testid="cb-pull-btn" className="px-3 py-2 rounded-lg border border-stone-300 text-stone-700 text-sm font-bold disabled:opacity-50 flex items-center gap-1.5"><DownloadSimple size={14} /> Rezervasyon Çek</button>
          </div>
          {lastPush && (
            <div className="text-[12px] bg-stone-50 border border-stone-200 rounded-lg p-2" data-testid="cb-last-push">
              {lastPush.mocked ? "🟡 MOCK" : lastPush.mocked === false ? "🟢 CANLI" : "ℹ"} · {lastPush.pushed_days ?? 0} gün{lastPush.sample ? ` · örnek: ${lastPush.sample.map((s) => `${s.startDate}: ₺${s.rate}`).join(" · ")}` : ""}{lastPush.message ? ` · ${lastPush.message}` : ""}
            </div>
          )}
        </div>
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
