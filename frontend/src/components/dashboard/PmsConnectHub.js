import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { PlugsConnected, PaperPlaneTilt, DownloadSimple, ShieldCheck } from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;
const API_BADGE = {
  open: { label: "AÇIK API", cls: "bg-emerald-100 text-emerald-700" },
  partner: { label: "PARTNER ONAYLI", cls: "bg-sky-100 text-sky-700" },
  semi: { label: "YARI AÇIK", cls: "bg-amber-100 text-amber-700" },
  closed: { label: "KAPALI API", cls: "bg-rose-100 text-rose-700" },
};

export default function PmsConnectHub({ activePropertyId, properties = [] }) {
  const pid = activePropertyId && activePropertyId !== "all" ? activePropertyId : properties[0]?.id || "default";
  const [data, setData] = useState(null);
  const [health, setHealth] = useState(null);
  const [sel, setSel] = useState(null);
  const [creds, setCreds] = useState({});
  const [days, setDays] = useState(14);
  const [log, setLog] = useState([]);
  const [lastPush, setLastPush] = useState(null);
  const [kit, setKit] = useState(null);
  const [verify, setVerify] = useState(null);
  const [weekly, setWeekly] = useState(null);
  const [busy, setBusy] = useState(false);

  const loadHealth = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/api/pms-connect/health/${pid}`, { withCredentials: true });
      setHealth(r.data);
    } catch { /* sessiz */ }
  }, [pid]);

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/api/pms-connect/providers/${pid}`, { withCredentials: true });
      setData(r.data);
      if (sel) setSel(r.data.providers.find((p) => p.id === sel.id) || null);
    } catch { toast.error("PMS bağlantı merkezi yüklenemedi"); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pid]);

  useEffect(() => { load(); loadHealth(); }, [load, loadHealth]);

  const toggleNightPush = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/pms-connect/night-push/${pid}`, { enabled: !health?.auto_night_push }, { withCredentials: true });
      toast.success(r.data.auto_night_push ? "Otomatik gece push AÇIK — sabah raporu sonrası sertifikalı kanallara basılacak" : "Otomatik gece push kapatıldı");
      loadHealth();
    } catch { toast.error("Ayar kaydedilemedi"); } finally { setBusy(false); }
  };

  const runNightPushNow = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/pms-connect/night-push/${pid}/run`, {}, { withCredentials: true });
      const done = r.data.results.filter((x) => !x.skipped && !x.error).length;
      toast.success(`Gece push çalıştı — ${done} kanala basıldı, ${r.data.results.length - done} atlandı`);
      loadHealth(); load();
    } catch (e) { toast.error(e.response?.data?.detail || "Gece push çalıştırılamadı"); } finally { setBusy(false); }
  };

  const runVerify = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/pms-connect/${sel.id}/verify-push/${pid}`, {}, { withCredentials: true });
      setVerify(r.data);
      if (r.data.ok) toast.success(r.data.message);
      else toast.error(r.data.message);
    } catch (e) { toast.error(e.response?.data?.detail || "Doğrulama çalıştırılamadı"); } finally { setBusy(false); }
  };

  const importOtb = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/pms-connect/mews/import-to-otb/${pid}`, {}, { withCredentials: true });
      toast.success(`${r.data.imported} rezervasyon OTB'ye aktarıldı (${r.data.cancelled} iptal) — önümüzdeki 14 günde ${r.data.otb_contribution_next14} aktif konaklama`);
    } catch (e) { toast.error(e.response?.data?.detail || "İçe aktarım başarısız"); } finally { setBusy(false); }
  };

  const loadWeekly = async () => {
    setBusy(true);
    try {
      const r = await axios.get(`${API}/api/pms-connect/weekly-report/${pid}`, { withCredentials: true });
      setWeekly(r.data);
      toast.success("Haftalık rapor hazırlandı");
    } catch { toast.error("Rapor üretilemedi"); } finally { setBusy(false); }
  };

  const loadKit = async () => {
    setBusy(true);
    try {
      const r = await axios.get(`${API}/api/pms-connect/${sel.id}/partner-kit/${pid}`, { withCredentials: true });
      setKit(r.data);
      toast.success("Başvuru kiti hazırlandı");
    } catch { toast.error("Kit üretilemedi"); } finally { setBusy(false); }
  };

  const mewsDemoConnect = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/pms-connect/mews/demo-connect/${pid}`, {}, { withCredentials: true });
      toast.success(r.data.rate_id ? `Mews demo bağlandı — ${r.data.enterprise} · rate: ${r.data.rate_name}` : r.data.note);
      await load(); loadHealth();
      const r2 = await axios.get(`${API}/api/pms-connect/providers/${pid}`, { withCredentials: true });
      setSel(r2.data.providers.find((p) => p.id === "mews"));
    } catch (e) { toast.error(e.response?.data?.detail || "Mews demo bağlantısı başarısız"); } finally { setBusy(false); }
  };

  const loadLog = useCallback(async (prov) => {
    try {
      const r = await axios.get(`${API}/api/pms-connect/${prov}/log/${pid}`, { withCredentials: true });
      setLog(r.data.log || []);
    } catch { setLog([]); }
  }, [pid]);

  const pick = (p) => { setSel(p); setCreds({}); setLastPush(null); setKit(null); loadLog(p.id); };

  const saveCreds = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/pms-connect/${sel.id}/config/${pid}`, creds, { withCredentials: true });
      toast.success(r.data.mode === "live" ? `${sel.name} kimlikleri kaydedildi — CANLI mod` : "Kaydedildi (eksik alan — hâlâ MOCK)");
      setCreds({}); await load();
      const r2 = await axios.get(`${API}/api/pms-connect/providers/${pid}`, { withCredentials: true });
      setSel(r2.data.providers.find((p) => p.id === sel.id));
    } catch { toast.error("Kaydedilemedi"); } finally { setBusy(false); }
  };

  const testConn = async () => {
    setBusy(true);
    try {
      await axios.post(`${API}/api/pms-connect/${sel.id}/test-connection/${pid}`, {}, { withCredentials: true });
      toast.success(`${sel.name} bağlantısı OK`);
    } catch (e) { toast.error(e.response?.data?.detail || "Bağlantı başarısız"); } finally { setBusy(false); }
  };

  const pushRms = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/pms-connect/${sel.id}/push-from-rms/${pid}`, { days: +days }, { withCredentials: true });
      setLastPush(r.data);
      toast.success(r.data.mocked ? `MOCK push simüle edildi (${r.data.pushed_days} gün)` : r.data.pushed_days > 0 ? `${r.data.pushed_days} günlük fiyat ${sel.name}'e gönderildi` : r.data.message);
      loadLog(sel.id); load();
    } catch (e) { toast.error(e.response?.data?.detail || "Push başarısız"); } finally { setBusy(false); }
  };

  const pullRes = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/pms-connect/${sel.id}/pull-reservations/${pid}`, {}, { withCredentials: true });
      toast.success(r.data.mocked ? "MOCK — kimlik girilmeden rezervasyon çekilemez" : `${r.data.imported} rezervasyon içe aktarıldı`);
      loadLog(sel.id);
    } catch (e) { toast.error(e.response?.data?.detail || "Çekme başarısız"); } finally { setBusy(false); }
  };

  const runCertify = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/pms-connect/${sel.id}/certify/${pid}`, {}, { withCredentials: true });
      setSel((s) => ({ ...s, certification: r.data }));
      toast.success(r.data.passed ? `Sertifikasyon GEÇTİ (${r.data.mode === "live" ? "CANLI" : "MOCK"})` : "Sertifikasyon BAŞARISIZ");
      loadLog(sel.id); load();
    } catch (e) { toast.error(e.response?.data?.detail || "Sertifikasyon çalıştırılamadı"); } finally { setBusy(false); }
  };

  const cert = sel?.certification;

  return (
    <div className="p-5 max-w-[1200px] mx-auto space-y-6" data-testid="pms-connect-panel">
      <div>
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          <PlugsConnected size={13} weight="fill" className="text-indigo-500" /><span>Agnostic Middleware</span>
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">PMS & Kanal Bağlantı Merkezi</h1>
        <p className="text-sm text-stone-500 mt-1">RMS fiyatları standart formatta üretilir; her adaptör kendi diline çevirip (JSON / OTA XML) PMS'e basar — onlar da Booking.com, Expedia ve diğer OTA'lara dağıtır.</p>
      </div>

      {health && (
        <section className="bg-white border border-stone-200 rounded-xl p-4" data-testid="pms-health-board">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
            <h2 className="text-base font-bold text-stone-800">📡 Kanal Sağlık Panosu</h2>
            <div className="flex items-center gap-2">
              <button onClick={toggleNightPush} disabled={busy} data-testid="pms-nightpush-toggle"
                className={`px-3 py-1.5 rounded-lg text-[12px] font-bold disabled:opacity-50 ${health.auto_night_push ? "bg-emerald-600 text-white" : "border border-stone-300 text-stone-600"}`}>
                🌙 Otomatik Gece Push: {health.auto_night_push ? "AÇIK" : "KAPALI"}
              </button>
              <button onClick={runNightPushNow} disabled={busy} data-testid="pms-nightpush-run-btn" className="px-3 py-1.5 rounded-lg bg-stone-900 text-white text-[12px] font-bold disabled:opacity-50">Şimdi Çalıştır</button>
              <button onClick={loadWeekly} disabled={busy} data-testid="pms-weekly-btn" className="px-3 py-1.5 rounded-lg border border-indigo-300 text-indigo-700 text-[12px] font-bold disabled:opacity-50">📧 Haftalık Rapor</button>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="pms-health-table">
              <thead><tr className="text-left text-[11px] text-stone-400 border-b border-stone-100">
                <th className="p-2">Kanal</th><th className="p-2">Mod</th><th className="p-2">Sertifika</th><th className="p-2">Son Push</th><th className="p-2">Toplam</th><th className="p-2">Hata Oranı</th>
              </tr></thead>
              <tbody>
                {health.channels.map((ch) => (
                  <tr key={ch.id} className="border-t border-stone-100" data-testid={`pms-health-row-${ch.id}`}>
                    <td className="p-2 font-bold">{ch.name}</td>
                    <td className="p-2"><span className={`px-2 py-0.5 rounded-full text-[10px] font-black ${ch.mode === "live" ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>{ch.mode === "live" ? "CANLI" : "MOCK"}</span></td>
                    <td className="p-2">{ch.certified ? <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 text-[10px] font-black">SERTİFİKALI{ch.cert_mode === "live" ? " · CANLI" : ""}</span> : <span className="text-[11px] text-stone-400">—</span>}</td>
                    <td className="p-2 text-[11px] text-stone-500">{ch.last_push_at ? String(ch.last_push_at).slice(0, 16).replace("T", " ") : "hiç"}</td>
                    <td className="p-2 text-[12px]">{ch.total_pushes}</td>
                    <td className="p-2 text-[12px]">{ch.error_rate_pct > 0 ? <span className="text-rose-600 font-bold">%{ch.error_rate_pct}</span> : "%0"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {health.last_night_push && (
            <p className="text-[11px] text-stone-400 mt-2" data-testid="pms-last-nightpush">Son gece push: {String(health.last_night_push.ran_at).slice(0, 16).replace("T", " ")} — {health.last_night_push.results.filter((x) => !x.skipped && !x.error).length} kanala basıldı</p>
          )}
          {weekly && (
            <div className="mt-3 border-t border-stone-100 pt-3" data-testid="pms-weekly-section">
              <div className="flex items-center justify-between gap-2 mb-1.5">
                <p className="text-[12px] font-bold text-stone-700">{weekly.email_subject}</p>
                <button onClick={() => { navigator.clipboard.writeText(weekly.email_body); toast.success("Rapor panoya kopyalandı"); }} data-testid="pms-weekly-copy-btn" className="px-2.5 py-1 rounded-lg bg-indigo-600 text-white text-[11px] font-bold">Kopyala</button>
              </div>
              <pre className="text-[11px] bg-stone-50 border border-stone-200 rounded-lg p-3 max-h-56 overflow-auto whitespace-pre-wrap" data-testid="pms-weekly-body">{weekly.email_body}</pre>
            </div>
          )}
        </section>
      )}

      <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-3" data-testid="pms-provider-grid">
        {(data?.providers || []).map((p) => (
          <button key={p.id} onClick={() => pick(p)} data-testid={`pms-card-${p.id}`}
            className={`text-left rounded-xl border p-3.5 transition-colors ${sel?.id === p.id ? "border-indigo-400 bg-indigo-50" : "border-stone-200 bg-white hover:border-stone-300"}`}>
            <div className="flex items-center justify-between gap-1">
              <span className="font-black text-stone-900 text-sm">{p.name}</span>
              <span className={`px-1.5 py-0.5 rounded-full text-[9px] font-black ${p.mode === "live" ? "bg-emerald-600 text-white" : "bg-amber-400 text-white"}`}>{p.mode === "live" ? "CANLI" : "MOCK"}</span>
            </div>
            <div className="text-[10px] text-stone-500 mt-1">{p.region}</div>
            <div className="flex flex-wrap gap-1 mt-2">
              <span className={`px-1.5 py-0.5 rounded-full text-[9px] font-black ${API_BADGE[p.api_type].cls}`}>{API_BADGE[p.api_type].label}</span>
              {p.certification && <span className={`px-1.5 py-0.5 rounded-full text-[9px] font-black ${p.certification.passed ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700"}`}>{p.certification.passed ? "SERTİFİKALI" : "SERT. BAŞARISIZ"}</span>}
            </div>
            <div className="text-[10px] text-stone-400 mt-1.5">{p.total_pushes} işlem · {p.format === "ota_xml" ? "OTA XML" : "JSON"}</div>
          </button>
        ))}
      </div>

      {sel && (
        <div className="space-y-4" data-testid="pms-detail">
          <div className="bg-stone-50 border border-stone-200 rounded-xl p-3 text-[12px] text-stone-600" data-testid="pms-provider-note">{sel.note}</div>

          <div className="flex flex-wrap gap-2">
            <button onClick={loadKit} disabled={busy} data-testid="pms-kit-btn" className="px-3 py-2 rounded-lg border border-indigo-300 text-indigo-700 text-sm font-bold disabled:opacity-50">📨 Partner Başvuru Kiti</button>
            <button onClick={runVerify} disabled={busy} data-testid="pms-verify-btn" className="px-3 py-2 rounded-lg border border-emerald-300 text-emerald-700 text-sm font-bold disabled:opacity-50">🔍 Push Doğrula (Geri Okuma)</button>
            {sel.id === "mews" && <button onClick={mewsDemoConnect} disabled={busy} data-testid="pms-mews-demo-btn" className="px-3 py-2 rounded-lg bg-emerald-600 text-white text-sm font-bold disabled:opacity-50">⚡ Mews Demo'ya Bağlan (Canlı Test)</button>}
            {sel.id === "mews" && sel.mode === "live" && <button onClick={importOtb} disabled={busy} data-testid="pms-import-otb-btn" className="px-3 py-2 rounded-lg bg-stone-900 text-white text-sm font-bold disabled:opacity-50">📥 Rezervasyonları OTB'ye Aktar</button>}
          </div>

          {sel.id === "apaleo" && sel.mode === "mocked" && (
            <div className="bg-sky-50 border border-sky-200 rounded-xl p-3 text-[12px] text-sky-900 space-y-1" data-testid="pms-apaleo-guide">
              <p className="font-bold">⚡ Apaleo Sandbox Hızlı Kurulum (5 dk, ücretsiz):</p>
              <p>1. <b>apaleo.dev</b> → "Get started" ile geliştirici hesabı açın (e-posta doğrulaması gerekir — bu adımı sizin yapmanız gerekiyor).</p>
              <p>2. Apaleo panelinde: Apps → "Create OAuth simple client" → scope: <code>rateplans.manage, rates.manage, reservations.read</code></p>
              <p>3. Client ID + Client Secret'ı yukarıdaki forma girin, Property ID ve Rate Plan ID'yi (Settings → Rate plans) ekleyin.</p>
              <p>4. Kaydet → Bağlantıyı Test Et → Sertifikasyonu Çalıştır → canlı push otomatik açılır (Mews ile aynı akış).</p>
            </div>
          )}

          {verify && (
            <section className={`border rounded-xl p-4 ${verify.ok ? "bg-emerald-50 border-emerald-200" : "bg-rose-50 border-rose-200"}`} data-testid="pms-verify-section">
              <div className="flex items-center justify-between gap-2 mb-2">
                <p className="text-sm font-bold text-stone-800">{verify.ok ? "✅" : "🚨"} {verify.message}</p>
                {verify.mocked && <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 text-[10px] font-black">MOCK GERİ OKUMA</span>}
              </div>
              {verify.rows && (
                <div className="overflow-x-auto">
                  <table className="w-full text-[12px]" data-testid="pms-verify-table">
                    <thead><tr className="text-left text-[10px] text-stone-400"><th className="p-1.5">Tarih</th><th className="p-1.5">Basılan</th><th className="p-1.5">Kanaldaki</th><th className="p-1.5">Sapma</th><th className="p-1.5">Durum</th></tr></thead>
                    <tbody>
                      {verify.rows.map((r) => (
                        <tr key={r.date} className="border-t border-stone-200/60">
                          <td className="p-1.5 font-bold">{r.date}</td>
                          <td className="p-1.5">₺{r.pushed}</td>
                          <td className="p-1.5">{r.channel != null ? `₺${r.channel}` : "—"}</td>
                          <td className="p-1.5">{r.drift_pct != null ? `%${r.drift_pct}` : "—"}</td>
                          <td className="p-1.5">{r.ok ? "✅" : "❌ SAPMA"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          )}

          {kit && (
            <section className="bg-white border border-indigo-200 rounded-xl p-4 space-y-2" data-testid="pms-kit-section">
              <div className="flex items-center justify-between gap-2">
                <h3 className="text-sm font-bold text-stone-800">{sel.name} Başvuru E-postası</h3>
                <button onClick={() => { navigator.clipboard.writeText(`${kit.email_subject}\n\n${kit.email_body}`); toast.success("E-posta panoya kopyalandı"); }} data-testid="pms-kit-copy-btn" className="px-2.5 py-1 rounded-lg bg-indigo-600 text-white text-[11px] font-bold">Kopyala</button>
              </div>
              <p className="text-[12px] font-bold text-stone-700" data-testid="pms-kit-subject">Konu: {kit.email_subject}</p>
              <pre className="text-[11px] bg-stone-50 border border-stone-200 rounded-lg p-3 max-h-64 overflow-auto whitespace-pre-wrap" data-testid="pms-kit-body">{kit.email_body}</pre>
              <details><summary className="text-[12px] font-bold text-stone-500 cursor-pointer">Teknik yeterlilik özeti (JSON)</summary>
                <pre className="text-[10px] bg-stone-900 text-emerald-300 rounded p-2 mt-1 max-h-40 overflow-auto">{JSON.stringify(kit.tech_summary, null, 1)}</pre>
              </details>
            </section>
          )}

          <section className="grid md:grid-cols-2 gap-4">
            <div className="bg-white border border-stone-200 rounded-xl p-4 space-y-2.5" data-testid="pms-config-form">
              <h2 className="text-base font-bold text-stone-800">{sel.name} Kimlikleri</h2>
              {sel.auth_fields.map((f) => (
                <input key={f.key} type={f.secret ? "password" : "text"} value={creds[f.key] || ""}
                  onChange={(e) => setCreds((c) => ({ ...c, [f.key]: e.target.value }))}
                  data-testid={`pms-cred-${f.key}`}
                  className="w-full border border-stone-300 rounded-lg px-2.5 py-2 text-sm"
                  placeholder={`${f.label}${sel.configured_fields.includes(f.key) ? " ✓ (kayıtlı)" : ""}`} />
              ))}
              <div className="flex gap-2">
                <button onClick={saveCreds} disabled={busy} data-testid="pms-save-btn" className="px-3 py-2 rounded-lg bg-indigo-600 text-white text-sm font-bold disabled:opacity-50">Kaydet</button>
                {sel.mode === "live" && <button onClick={testConn} disabled={busy} data-testid="pms-test-btn" className="px-3 py-2 rounded-lg bg-stone-900 text-white text-sm font-bold disabled:opacity-50">Bağlantıyı Test Et</button>}
              </div>
            </div>

            <div className="bg-white border border-stone-200 rounded-xl p-4 space-y-2.5" data-testid="pms-push-form">
              <h2 className="text-base font-bold text-stone-800">RMS'ten {sel.name}'e Gönder</h2>
              <label className="text-[11px] text-stone-500 font-bold">Gün sayısı
                <input type="number" min={1} max={90} value={days} onChange={(e) => setDays(e.target.value)} data-testid="pms-days-input" className="block w-28 border border-stone-300 rounded-lg px-2 py-2 text-sm mt-0.5" />
              </label>
              <div className="flex gap-2">
                <button onClick={pushRms} disabled={busy} data-testid="pms-push-btn" className="px-3 py-2 rounded-lg bg-stone-900 text-white text-sm font-bold disabled:opacity-50 flex items-center gap-1.5"><PaperPlaneTilt size={14} /> Fiyat Push</button>
                <button onClick={pullRes} disabled={busy} data-testid="pms-pull-btn" className="px-3 py-2 rounded-lg border border-stone-300 text-stone-700 text-sm font-bold disabled:opacity-50 flex items-center gap-1.5"><DownloadSimple size={14} /> Rezervasyon Çek</button>
              </div>
              {lastPush && (
                <div className="text-[12px] bg-stone-50 border border-stone-200 rounded-lg p-2 space-y-1" data-testid="pms-last-push">
                  <div>{lastPush.mocked ? "🟡 MOCK" : lastPush.mocked === false ? "🟢 CANLI" : "ℹ"} · {lastPush.pushed_days ?? 0} gün{lastPush.message ? ` · ${lastPush.message}` : ""}</div>
                  {lastPush.translated_preview && (
                    <details><summary className="cursor-pointer font-bold text-stone-500">Çevrilmiş payload önizleme ({sel.format === "ota_xml" ? "OTA XML" : "JSON"})</summary>
                      <pre className="text-[10px] bg-stone-900 text-emerald-300 rounded p-2 mt-1 max-h-40 overflow-auto whitespace-pre-wrap" data-testid="pms-translated-preview">{JSON.stringify(lastPush.translated_preview, null, 1).slice(0, 1200)}</pre>
                    </details>
                  )}
                </div>
              )}
            </div>
          </section>

          <section className="bg-white border border-stone-200 rounded-xl p-4" data-testid="pms-cert-section">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-bold text-stone-800 flex items-center gap-1.5"><ShieldCheck size={17} className="text-indigo-600" /> Publisher Sertifikasyonu</h2>
                <p className="text-[12px] text-stone-500 mt-0.5">Test push + geri okuma + format çevirisi doğrulaması. CANLI modda sertifikasyon geçilmeden push bloklanır.</p>
              </div>
              <div className="flex items-center gap-2">
                {cert && (
                  <span className={`px-2.5 py-1 rounded-full text-[11px] font-black ${cert.passed ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700"}`} data-testid="pms-cert-badge">
                    {cert.passed ? "SERTİFİKALI" : "BAŞARISIZ"} · {cert.mode === "live" ? "CANLI" : "MOCK"}
                  </span>
                )}
                <button onClick={runCertify} disabled={busy} data-testid="pms-certify-btn" className="px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-[12px] font-bold disabled:opacity-50">Sertifikasyonu Çalıştır</button>
              </div>
            </div>
            {cert?.checks && (
              <div className="mt-3 grid sm:grid-cols-2 gap-2" data-testid="pms-cert-checks">
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
          </section>

          <section data-testid="pms-log-section">
            <h2 className="text-base font-bold text-stone-800 mb-2">{sel.name} İşlem Geçmişi</h2>
            {log.length === 0 ? <div className="bg-stone-50 border border-stone-200 rounded-xl p-4 text-sm text-stone-500" data-testid="pms-log-empty">Henüz işlem yok.</div> : (
              <div className="bg-white border border-stone-200 rounded-xl overflow-x-auto">
                <table className="w-full text-sm" data-testid="pms-log-table">
                  <thead><tr className="text-left text-[11px] text-stone-400 border-b border-stone-100"><th className="p-2.5">Zaman</th><th className="p-2.5">Tür</th><th className="p-2.5">Mod</th><th className="p-2.5">Sonuç</th></tr></thead>
                  <tbody>
                    {log.map((l) => (
                      <tr key={l.id} className="border-t border-stone-100">
                        <td className="p-2.5 text-[12px]">{String(l.created_at).slice(0, 16).replace("T", " ")}</td>
                        <td className="p-2.5">{l.kind === "rate_push" ? (l.cert_test ? "Sertifikasyon Push" : "Fiyat Push") : "Rezervasyon"}</td>
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
      )}
    </div>
  );
}
