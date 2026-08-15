import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Broadcast, PaperPlaneTilt, DownloadSimple } from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

export default function HotelRunnerPanel({ activePropertyId, properties = [] }) {
  const pid = activePropertyId && activePropertyId !== "all" ? activePropertyId : properties[0]?.id || "default";
  const [status, setStatus] = useState(null);
  const [log, setLog] = useState([]);
  const [hrId, setHrId] = useState("");
  const [token, setToken] = useState("");
  const [days, setDays] = useState(14);
  const [invCode, setInvCode] = useState("RMS-DEFAULT");
  const [busy, setBusy] = useState(false);
  const [lastPush, setLastPush] = useState(null);

  const load = useCallback(async () => {
    try {
      const [s, l] = await Promise.all([
        axios.get(`${API}/api/hotelrunner/status/${pid}`, { withCredentials: true }),
        axios.get(`${API}/api/hotelrunner/log/${pid}`, { withCredentials: true }),
      ]);
      setStatus(s.data); setLog(l.data.log || []);
    } catch { toast.error("HotelRunner durumu yüklenemedi"); }
  }, [pid]);

  useEffect(() => { load(); }, [load]);

  const saveConfig = async () => {
    if (!hrId.trim() && !token.trim()) { toast.error("HR_ID veya TOKEN girin"); return; }
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/hotelrunner/config/${pid}`, { hr_id: hrId, token }, { withCredentials: true });
      toast.success(r.data.mode === "live" ? "Kimlikler kaydedildi — CANLI mod aktif" : "Kaydedildi (eksik kimlik — hâlâ MOCK)");
      setHrId(""); setToken(""); load();
    } catch { toast.error("Kaydedilemedi"); } finally { setBusy(false); }
  };

  const testConn = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/hotelrunner/test-connection/${pid}`, {}, { withCredentials: true });
      toast.success(`Bağlantı OK — ${r.data.rooms_found} oda bulundu`);
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Bağlantı başarısız"); } finally { setBusy(false); }
  };

  const pushRms = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/hotelrunner/push-from-rms/${pid}`, { days: +days, inv_code: invCode }, { withCredentials: true });
      setLastPush(r.data);
      toast.success(r.data.mocked ? `MOCK push simüle edildi (${r.data.pushed_days} gün)` : `${r.data.pushed_days} günlük ARI kanala gönderildi`);
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Push başarısız"); } finally { setBusy(false); }
  };

  const pullRes = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/hotelrunner/pull-reservations/${pid}`, {}, { withCredentials: true });
      toast.success(r.data.mocked ? "MOCK — kimlik girilmeden rezervasyon çekilemez" : `${r.data.imported} rezervasyon içe aktarıldı`);
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Çekme başarısız"); } finally { setBusy(false); }
  };

  const live = status?.mode === "live";

  return (
    <div className="p-5 max-w-[1100px] mx-auto space-y-6" data-testid="hotelrunner-panel">
      <div>
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          <Broadcast size={13} weight="fill" className="text-orange-500" /><span>Canlı Kanal Bağlantısı</span>
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">HotelRunner ARI Push</h1>
        <p className="text-sm text-stone-500 mt-1">RMS fiyat ve müsaitliğini HotelRunner üzerinden gerçek OTA kanallarına gönderin, rezervasyonları çekin.</p>
      </div>

      {status && (
        <div className={`rounded-xl border p-4 flex flex-wrap items-center justify-between gap-3 ${live ? "bg-emerald-50 border-emerald-200" : "bg-amber-50 border-amber-200"}`} data-testid="hr-status-box">
          <div>
            <span className={`px-2.5 py-1 rounded-full text-[11px] font-black ${live ? "bg-emerald-600 text-white" : "bg-amber-500 text-white"}`} data-testid="hr-mode-badge">{live ? "CANLI MOD" : "MOCK MOD"}</span>
            <span className="text-sm text-stone-600 ml-3">{status.hr_id_masked ? `HR_ID: ${status.hr_id_masked}` : "Kimlik girilmedi"} · {status.total_pushes} push kaydı</span>
          </div>
          {live && <button onClick={testConn} disabled={busy} data-testid="hr-test-btn" className="px-3 py-1.5 rounded-lg bg-stone-900 text-white text-[12px] font-bold disabled:opacity-50">Bağlantıyı Test Et</button>}
        </div>
      )}
      {!live && status && <p className="text-[12px] text-amber-700 -mt-3">{status.note}</p>}

      <section className="grid md:grid-cols-2 gap-4">
        <div className="bg-white border border-stone-200 rounded-xl p-4 space-y-2.5" data-testid="hr-config-form">
          <h2 className="text-base font-bold text-stone-800">Kimlikler</h2>
          <input value={hrId} onChange={(e) => setHrId(e.target.value)} data-testid="hr-id-input" className="w-full border border-stone-300 rounded-lg px-2.5 py-2 text-sm" placeholder="HR_ID (tesisin HotelRunner ID'si)" />
          <input value={token} onChange={(e) => setToken(e.target.value)} type="password" data-testid="hr-token-input" className="w-full border border-stone-300 rounded-lg px-2.5 py-2 text-sm" placeholder="API TOKEN" />
          <button onClick={saveConfig} disabled={busy} data-testid="hr-save-config-btn" className="px-3 py-2 rounded-lg bg-orange-600 text-white text-sm font-bold disabled:opacity-50">Kaydet & Canlıya Geç</button>
          <p className="text-[11px] text-stone-400">Partner panel: partner.hotelrunner.com → My Property → HotelRunner Apps/API key</p>
        </div>

        <div className="bg-white border border-stone-200 rounded-xl p-4 space-y-2.5" data-testid="hr-push-form">
          <h2 className="text-base font-bold text-stone-800">RMS'ten Kanala Gönder</h2>
          <div className="grid grid-cols-2 gap-2">
            <label className="text-[11px] text-stone-500 font-bold">Gün sayısı
              <input type="number" min={1} max={90} value={days} onChange={(e) => setDays(e.target.value)} data-testid="hr-days-input" className="block w-full border border-stone-300 rounded-lg px-2 py-2 text-sm mt-0.5" />
            </label>
            <label className="text-[11px] text-stone-500 font-bold">inv_code
              <input value={invCode} onChange={(e) => setInvCode(e.target.value)} data-testid="hr-invcode-input" className="block w-full border border-stone-300 rounded-lg px-2 py-2 text-sm mt-0.5" />
            </label>
          </div>
          <div className="flex gap-2">
            <button onClick={pushRms} disabled={busy} data-testid="hr-push-btn" className="px-3 py-2 rounded-lg bg-stone-900 text-white text-sm font-bold disabled:opacity-50 flex items-center gap-1.5"><PaperPlaneTilt size={14} /> ARI Push</button>
            <button onClick={pullRes} disabled={busy} data-testid="hr-pull-btn" className="px-3 py-2 rounded-lg border border-stone-300 text-stone-700 text-sm font-bold disabled:opacity-50 flex items-center gap-1.5"><DownloadSimple size={14} /> Rezervasyon Çek</button>
          </div>
          {lastPush && (
            <div className="text-[12px] bg-stone-50 border border-stone-200 rounded-lg p-2" data-testid="hr-last-push">
              {lastPush.mocked ? "🟡 MOCK" : "🟢 CANLI"} · {lastPush.pushed_days} gün · örnek: {lastPush.sample?.map((s) => `${s.date}: ${s.availability} oda${s.price ? ` ₺${s.price}` : ""}`).join(" · ")}
            </div>
          )}
        </div>
      </section>

      <section data-testid="hr-log-section">
        <h2 className="text-base font-bold text-stone-800 mb-2">Push Geçmişi</h2>
        {log.length === 0 ? <div className="bg-stone-50 border border-stone-200 rounded-xl p-4 text-sm text-stone-500" data-testid="hr-log-empty">Henüz push yok.</div> : (
          <div className="bg-white border border-stone-200 rounded-xl overflow-x-auto">
            <table className="w-full text-sm" data-testid="hr-log-table">
              <thead><tr className="text-left text-[11px] text-stone-400 border-b border-stone-100"><th className="p-2.5">Zaman</th><th className="p-2.5">Tür</th><th className="p-2.5">Mod</th><th className="p-2.5">Sonuç</th></tr></thead>
              <tbody>
                {log.map((l) => (
                  <tr key={l.id} className="border-t border-stone-100">
                    <td className="p-2.5 text-[12px]">{String(l.created_at).slice(0, 16).replace("T", " ")}</td>
                    <td className="p-2.5">{l.kind === "ari_push" ? "ARI Push" : "Rezervasyon"}</td>
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
