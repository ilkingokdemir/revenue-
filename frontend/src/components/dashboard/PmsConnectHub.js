import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, LineChart, Line, XAxis, YAxis, Legend } from "recharts";
import { PlugsConnected, PaperPlaneTilt, DownloadSimple, ShieldCheck } from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;
const API_BADGE = {
  open: { label: "AÇIK API", cls: "bg-emerald-100 text-emerald-700" },
  partner: { label: "PARTNER ONAYLI", cls: "bg-sky-100 text-sky-700" },
  semi: { label: "YARI AÇIK", cls: "bg-amber-100 text-amber-700" },
  closed: { label: "KAPALI API", cls: "bg-rose-100 text-rose-700" },
};
const PIE_COLORS = ["#4f46e5", "#059669", "#d97706", "#dc2626", "#0891b2", "#7c3aed", "#65a30d", "#db2777", "#78716c", "#0d9488"];

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
  const [alerts, setAlerts] = useState([]);
  const [showAlerts, setShowAlerts] = useState(false);
  const [fa, setFa] = useState(null);
  const [mapping, setMapping] = useState(null);
  const [rateOptions, setRateOptions] = useState([]);
  const [rev, setRev] = useState(null);
  const [revMonth, setRevMonth] = useState("");
  const [revView, setRevView] = useState("group");
  const [comm, setComm] = useState(null);
  const [tips, setTips] = useState(null);
  const [invite, setInvite] = useState(null);
  const [leads, setLeads] = useState(null);
  const [leadForm, setLeadForm] = useState({ hotel_name: "", contact: "", note: "" });
  const [drill, setDrill] = useState(null);
  const [drillHist, setDrillHist] = useState(null);
  const [busy, setBusy] = useState(false);

  const loadHealth = useCallback(async () => {
    try {
      const [r, a] = await Promise.all([
        axios.get(`${API}/api/pms-connect/health/${pid}`, { withCredentials: true }),
        axios.get(`${API}/api/pms-connect/alerts/${pid}`, { withCredentials: true }),
      ]);
      setHealth(r.data); setAlerts(a.data.alerts || []);
    } catch { /* sessiz */ }
  }, [pid]);

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/api/pms-connect/providers/${pid}`, { withCredentials: true });
      setData(r.data);
      const pre = localStorage.getItem("mhb_pms_connect_provider");
      if (pre) { localStorage.removeItem("mhb_pms_connect_provider"); const p = r.data.providers.find((x) => x.id === pre); if (p) { setSel(p); return; } }
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

  const resolveAlert = async (aid) => {
    try {
      await axios.post(`${API}/api/pms-connect/alerts/${aid}/resolve`, {}, { withCredentials: true });
      toast.success("Uyarı çözüldü olarak işaretlendi");
      loadHealth();
    } catch { toast.error("İşaretlenemedi"); }
  };

  const discoverRates = async () => {
    setBusy(true);
    try {
      const r = await axios.get(`${API}/api/pms-connect/${sel.id}/discover-rates/${pid}`, { withCredentials: true });
      const roots = r.data.rates.filter((x) => x.is_root && x.is_active);
      setRateOptions(r.data.rates.filter((x) => x.is_active));
      setMapping((arr) => (arr || []).map((m, i) =>
        m.channel_rate_code ? m : { ...m, channel_rate_code: (roots[i % Math.max(roots.length, 1)] || roots[0] || {}).id || "" }));
      toast.success(`${sel.name} keşfi: ${r.data.rates.length} rate, ${r.data.resource_categories.length} oda kategorisi bulundu — boş eşleştirmeler otomatik dolduruldu`);
    } catch (e) { toast.error(e.response?.data?.detail || "Keşif başarısız"); } finally { setBusy(false); }
  };

  const loadComm = async () => {
    try {
      const r = await axios.get(`${API}/api/pms-connect/commission-settings/${pid}`, { withCredentials: true });
      setComm(r.data.rows);
    } catch { toast.error("Komisyon ayarları yüklenemedi"); }
  };

  const saveComm = async () => {
    setBusy(true);
    try {
      const rates = {};
      comm.forEach((r) => { if (r.custom_pct !== null && r.custom_pct !== "") rates[r.source] = r.custom_pct; });
      const res = await axios.post(`${API}/api/pms-connect/commission-settings/${pid}`, { rates }, { withCredentials: true });
      toast.success(`${res.data.count} özel komisyon oranı kaydedildi — net gelir yeniden hesaplanıyor`);
      loadRev();
    } catch { toast.error("Kaydedilemedi"); } finally { setBusy(false); }
  };

  const loadTips = async () => {
    setBusy(true);
    try {
      const r = await axios.get(`${API}/api/pms-connect/direct-booking-tips/${pid}`, { withCredentials: true });
      setTips(r.data);
    } catch { toast.error("İpuçları yüklenemedi"); } finally { setBusy(false); }
  };

  const toggleTip = async (index, done) => {
    setTips((t) => ({ ...t, tips: t.tips.map((x) => x.index === index ? { ...x, done } : x), done_count: t.tips.filter((x) => (x.index === index ? done : x.done)).length }));
    try {
      await axios.post(`${API}/api/pms-connect/direct-booking-tips/${pid}/toggle`, { index, done }, { withCredentials: true });
      toast.success(done ? "Öneri yapıldı olarak işaretlendi" : "İşaret kaldırıldı");
    } catch { toast.error("İşaretlenemedi"); }
  };

  const loadLeads = async () => {
    try {
      const r = await axios.get(`${API}/api/pms-connect/pilot-leads/${pid}`, { withCredentials: true });
      setLeads(r.data);
    } catch { toast.error("Pilot listesi yüklenemedi"); }
  };

  const addLead = async () => {
    if (!leadForm.hotel_name.trim()) { toast.error("Otel adı girin"); return; }
    try {
      await axios.post(`${API}/api/pms-connect/pilot-leads/${pid}`, leadForm, { withCredentials: true });
      setLeadForm({ hotel_name: "", contact: "", note: "" });
      toast.success("Otel pilot listesine eklendi (durum: davet)");
      loadLeads();
    } catch { toast.error("Eklenemedi"); }
  };

  const setLeadStatus = async (leadId, status) => {
    try {
      await axios.post(`${API}/api/pms-connect/pilot-leads/${leadId}/status`, { status }, { withCredentials: true });
      setLeads((l) => ({ ...l, leads: l.leads.map((x) => x.id === leadId ? { ...x, status } : x) }));
      toast.success(`Durum güncellendi: ${status}`);
    } catch { toast.error("Güncellenemedi"); }
  };

  const saveLeadNote = async (leadId, note) => {
    try {
      await axios.post(`${API}/api/pms-connect/pilot-leads/${leadId}/note`, { note }, { withCredentials: true });
      setLeads((l) => ({ ...l, leads: l.leads.map((x) => x.id === leadId ? { ...x, note } : x) }));
      toast.success("Not kaydedildi");
    } catch { toast.error("Not kaydedilemedi"); }
  };

  const runDrill = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/pms-connect/killswitch-drill/${pid}`, {}, { withCredentials: true });
      setDrill(r.data);
      r.data.passed ? toast.success("Tatbikat BAŞARILI — acil durdurma zinciri çalışıyor") : toast.error("Tatbikat BAŞARISIZ!");
      const h = await axios.get(`${API}/api/pms-connect/killswitch-drill/${pid}/history`, { withCredentials: true });
      setDrillHist(h.data);
    } catch { toast.error("Tatbikat çalıştırılamadı"); } finally { setBusy(false); }
  };

  const loadInvite = async () => {
    setBusy(true);
    try {
      const r = await axios.get(`${API}/api/pms-connect/pilot-invite/${pid}`, { withCredentials: true });
      setInvite(r.data);
      toast.success("Pilot davet e-postası hazırlandı");
    } catch { toast.error("Davet üretilemedi"); } finally { setBusy(false); }
  };

  const loadRev = async () => {
    setBusy(true);
    try {
      const r = await axios.get(`${API}/api/pms-connect/revenue-by-channel/${pid}?months=6`, { withCredentials: true });
      setRev(r.data);
      const cur = new Date().toISOString().slice(0, 7);
      setRevMonth(r.data.months.includes(cur) ? cur : (r.data.months[r.data.months.length - 1] || ""));
    } catch { toast.error("Gelir dağılımı yüklenemedi"); } finally { setBusy(false); }
  };

  const loadFa = async () => {
    setBusy(true);
    try {
      const r = await axios.get(`${API}/api/pms-connect/forecast-accuracy/${pid}`, { withCredentials: true });
      setFa(r.data);
    } catch { toast.error("Forecast raporu yüklenemedi"); } finally { setBusy(false); }
  };

  const loadMapping = async (prov) => {
    try {
      const r = await axios.get(`${API}/api/pms-connect/${prov}/rate-mapping/${pid}`, { withCredentials: true });
      const rows = r.data.room_types.map((rt) => {
        const ex = (r.data.mappings || []).find((m) => m.room_type_id === rt.id);
        return { room_type_id: rt.id, room_type_name: rt.name, channel_rate_code: ex?.channel_rate_code || "", multiplier: ex?.multiplier ?? 1.0 };
      });
      setMapping(rows);
    } catch { setMapping([]); }
  };

  const saveMapping = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/pms-connect/${sel.id}/rate-mapping/${pid}`, { mappings: mapping }, { withCredentials: true });
      toast.success(r.data.count > 0 ? `${r.data.count} oda tipi eşleştirmesi kaydedildi — push artık oda tipi bazında` : "Eşleştirme temizlendi — push tek fiyatla devam eder");
    } catch { toast.error("Eşleştirme kaydedilemedi"); } finally { setBusy(false); }
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

  const pick = (p) => { setSel(p); setCreds({}); setLastPush(null); setKit(null); setVerify(null); setMapping(null); loadLog(p.id); loadMapping(p.id); };

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

  const [pushPreview, setPushPreview] = useState(null);

  const openPushPreview = async () => {
    setBusy(true);
    try {
      const r = await axios.get(`${API}/api/pms-connect/${sel.id}/push-preview/${pid}?days=${+days}`, { withCredentials: true });
      if (!r.data.table?.length) { toast.info(r.data.message || "Önizlenecek fiyat yok"); return; }
      setPushPreview(r.data);
    } catch (e) { toast.error(e.response?.data?.detail || "Önizleme yüklenemedi"); } finally { setBusy(false); }
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
            <h2 className="text-base font-bold text-stone-800 flex items-center gap-2">📡 Kanal Sağlık Panosu
              {alerts.length > 0 && (
                <button onClick={() => setShowAlerts((s) => !s)} data-testid="pms-alert-bell"
                  className="relative px-2 py-0.5 rounded-full bg-rose-600 text-white text-[11px] font-black animate-pulse">
                  🔔 {alerts.length} SAPMA UYARISI
                </button>
              )}
            </h2>
            <div className="flex items-center gap-2">
              <button onClick={loadFa} disabled={busy} data-testid="pms-forecast-btn" className="px-3 py-1.5 rounded-lg border border-purple-300 text-purple-700 text-[12px] font-bold disabled:opacity-50">🎯 Forecast Doğruluk</button>
              <button onClick={loadRev} disabled={busy} data-testid="pms-revenue-btn" className="px-3 py-1.5 rounded-lg border border-amber-300 text-amber-700 text-[12px] font-bold disabled:opacity-50">💰 Kanal Gelir Katkısı</button>
              <a href={`${API}/api/pms-connect/executive-pdf/${pid}`} target="_blank" rel="noreferrer" data-testid="pms-exec-pdf-btn" className="px-3 py-1.5 rounded-lg bg-stone-900 text-white text-[12px] font-bold">📄 Yönetici Özeti PDF</a>
              <button onClick={loadInvite} disabled={busy} data-testid="pms-invite-btn" className="px-3 py-1.5 rounded-lg bg-emerald-600 text-white text-[12px] font-bold disabled:opacity-50">✉ Pilot Davet</button>
              <button onClick={() => (leads ? setLeads(null) : loadLeads())} data-testid="pms-leads-btn" className="px-3 py-1.5 rounded-lg border border-sky-300 text-sky-700 text-[12px] font-bold">📋 Pilot Takip</button>
              <button onClick={runDrill} disabled={busy} data-testid="pms-drill-btn" className="px-3 py-1.5 rounded-lg border border-rose-300 text-rose-700 text-[12px] font-bold disabled:opacity-50">🛑 Kill Switch Tatbikatı</button>
              <button onClick={toggleNightPush} disabled={busy} data-testid="pms-nightpush-toggle"
                className={`px-3 py-1.5 rounded-lg text-[12px] font-bold disabled:opacity-50 ${health.auto_night_push ? "bg-emerald-600 text-white" : "border border-stone-300 text-stone-600"}`}>
                🌙 Otomatik Gece Push: {health.auto_night_push ? "AÇIK" : "KAPALI"}
              </button>
              <button onClick={runNightPushNow} disabled={busy} data-testid="pms-nightpush-run-btn" className="px-3 py-1.5 rounded-lg bg-stone-900 text-white text-[12px] font-bold disabled:opacity-50">Şimdi Çalıştır</button>
              <button onClick={loadWeekly} disabled={busy} data-testid="pms-weekly-btn" className="px-3 py-1.5 rounded-lg border border-indigo-300 text-indigo-700 text-[12px] font-bold disabled:opacity-50">📧 Haftalık Rapor</button>
              <a href={`${API}/api/pms-connect/weekly-report-pdf/${pid}`} target="_blank" rel="noreferrer" data-testid="pms-weekly-pdf-btn" className="px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-[12px] font-bold">📄 Haftalık PDF</a>
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
          {showAlerts && alerts.length > 0 && (
            <div className="mt-3 border border-rose-200 bg-rose-50 rounded-xl p-3 space-y-2" data-testid="pms-alerts-list">
              {alerts.map((a) => (
                <div key={a.id} className="flex items-start justify-between gap-2 text-[12px]">
                  <span>🚨 <b>{a.provider}</b> — fiyat sapması (maks %{a.max_drift_pct}) · {String(a.created_at).slice(0, 16).replace("T", " ")}</span>
                  <button onClick={() => resolveAlert(a.id)} data-testid={`pms-alert-resolve-${a.id}`} className="px-2 py-0.5 rounded-lg bg-white border border-rose-300 text-rose-700 text-[11px] font-bold shrink-0">Çözüldü</button>
                </div>
              ))}
            </div>
          )}
          {fa && (
            <div className="mt-3 border-t border-stone-100 pt-3" data-testid="pms-forecast-section">
              <p className="text-[12px] font-bold text-stone-700 mb-1">🎯 Canlı Veri Forecast Kıyası</p>
              <p className="text-[12px] text-stone-500 mb-2" data-testid="pms-forecast-note">{fa.note}</p>
              {fa.mae_occ_pts != null && <p className="text-sm font-black text-purple-700 mb-2">MAE: {fa.mae_occ_pts} doluluk puanı ({fa.matured_points} nokta)</p>}
              <p className="text-[12px] font-bold text-emerald-700 mb-1">Mews canlı rezervasyon katkısı (14 gün toplam: {fa.mews_total_contribution_14d} oda-gece):</p>
              <div className="overflow-x-auto">
                <table className="w-full text-[11px]" data-testid="pms-mews-impact-table">
                  <thead><tr className="text-left text-[10px] text-stone-400"><th className="p-1">Tarih</th><th className="p-1">OTB (Mews'li)</th><th className="p-1">OTB (Mews'siz)</th><th className="p-1">Mews Katkısı</th><th className="p-1">Doluluk Farkı</th></tr></thead>
                  <tbody>
                    {fa.mews_impact.filter((r) => r.mews_contribution > 0 || fa.mews_total_contribution_14d === 0).slice(0, 8).map((r) => (
                      <tr key={r.date} className="border-t border-stone-100">
                        <td className="p-1 font-bold">{r.date}</td><td className="p-1">{r.otb_with_mews}</td><td className="p-1">{r.otb_without_mews}</td>
                        <td className="p-1 font-black text-emerald-700">+{r.mews_contribution}</td>
                        <td className="p-1">%{r.occ_without_pct} → %{r.occ_with_pct}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
          {rev && (() => {
            const srcRows = (rev.by_month[revMonth] || []).slice(0, 10);
            const grpMap = {};
            srcRows.forEach((r) => {
              const g = grpMap[r.group] || { source: r.group, revenue: 0, net_revenue: 0, bookings: 0 };
              g.revenue += r.revenue; g.net_revenue += r.net_revenue; g.bookings += r.bookings;
              grpMap[r.group] = g;
            });
            const monthTot = srcRows.reduce((s, r) => s + r.revenue, 0) || 1;
            const grpRows = Object.values(grpMap).map((g) => ({ ...g, pct: Math.round(g.revenue / monthTot * 1000) / 10 })).sort((a, b) => b.revenue - a.revenue);
            const rows = revView === "group" ? grpRows : srcRows;
            const topSources = (rev.totals || []).slice(0, 5).map((t) => t.source);
            const trendData = rev.months.map((m) => {
              const mr = rev.by_month[m] || [];
              const tot = mr.reduce((s, r) => s + r.revenue, 0) || 1;
              const pt = { month: m };
              topSources.forEach((s) => {
                pt[s] = Math.round((mr.filter((r) => r.source === s).reduce((x, r) => x + r.revenue, 0) / tot) * 1000) / 10;
              });
              return pt;
            });
            const trendArrow = (s) => {
              if (trendData.length < 2) return "";
              const a = trendData[trendData.length - 2][s] || 0, b = trendData[trendData.length - 1][s] || 0;
              return b > a + 0.5 ? " ▲" : b < a - 0.5 ? " ▼" : "";
            };
            return (
              <div className="mt-3 border-t border-stone-100 pt-3" data-testid="pms-revenue-section">
                <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                  <p className="text-[12px] font-bold text-stone-700">💰 Kanal Gelir Katkısı — rezervasyon kaynağına göre</p>
                  <div className="flex items-center gap-2">
                    <button onClick={loadTips} disabled={busy} data-testid="pms-tips-btn" className="px-2.5 py-1 rounded-lg border border-emerald-300 text-emerald-700 text-[11px] font-bold disabled:opacity-50">💡 Doğrudan Teşvik</button>
                    <button onClick={() => (comm ? setComm(null) : loadComm())} data-testid="pms-comm-btn" className="px-2.5 py-1 rounded-lg border border-stone-300 text-stone-600 text-[11px] font-bold">⚙ Komisyon Ayarları</button>
                    <button onClick={() => setRevView((v) => v === "group" ? "source" : "group")} data-testid="pms-revenue-view-toggle" className="px-2.5 py-1 rounded-lg border border-stone-300 text-stone-600 text-[11px] font-bold">{revView === "group" ? "Görünüm: GRUP" : "Görünüm: KAYNAK"}</button>
                    <select value={revMonth} onChange={(e) => setRevMonth(e.target.value)} data-testid="pms-revenue-month-select" className="border border-stone-300 rounded-lg px-2 py-1 text-[12px] font-bold">
                      {rev.months.map((m) => <option key={m} value={m}>{m}</option>)}
                    </select>
                  </div>
                </div>
                {comm && (
                  <div className="mt-3 bg-stone-50 border border-stone-200 rounded-xl p-3" data-testid="pms-comm-section">
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-[12px] font-bold text-stone-700">⚙ OTA Komisyon Oranları (sözleşmenize göre düzenleyin)</p>
                      <button onClick={saveComm} disabled={busy} data-testid="pms-comm-save-btn" className="px-2.5 py-1 rounded-lg bg-indigo-600 text-white text-[11px] font-bold disabled:opacity-50">Kaydet</button>
                    </div>
                    <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-2">
                      {comm.map((r, i) => (
                        <label key={r.source} className="text-[11px] text-stone-600 font-bold flex items-center justify-between gap-2 bg-white border border-stone-200 rounded-lg px-2 py-1.5">
                          {r.source}
                          <span className="flex items-center gap-1">
                            <input type="number" step="0.5" min="0" max="50" value={r.custom_pct ?? ""} placeholder={String(r.default_pct)}
                              data-testid={`pms-comm-input-${i}`}
                              onChange={(e) => setComm((arr) => arr.map((x, j) => j === i ? { ...x, custom_pct: e.target.value === "" ? null : parseFloat(e.target.value) } : x))}
                              className="w-16 border border-stone-300 rounded px-1.5 py-0.5 text-[11px]" />%
                          </span>
                        </label>
                      ))}
                      {comm.length === 0 && <p className="text-[11px] text-stone-400">OTA kaynağı bulunamadı.</p>}
                    </div>
                    <p className="text-[10px] text-stone-400 mt-1.5">Boş bırakılan kaynak varsayılanı kullanır (Booking %15, Expedia/Hotels.com %18, Agoda %17, diğer %15).</p>
                  </div>
                )}
                {tips && (
                  <div className="mt-3 bg-emerald-50 border border-emerald-200 rounded-xl p-3" data-testid="pms-tips-section">
                    <p className="text-[12px] font-black text-emerald-800 mb-1">💡 Doğrudan Rezervasyon Teşviki — OTA komisyon kaybı: 6 ayda ₺{Math.round(tips.commission_loss_6m).toLocaleString("tr-TR")} (yıllık tahmini ₺{Math.round(tips.commission_loss_annual_est).toLocaleString("tr-TR")}) · doğrudan pay %{tips.direct_pct}</p>
                    <ul className="space-y-1">
                      {tips.tips.map((t) => (
                        <li key={t.index} className="text-[11px] text-emerald-900 flex items-start gap-2">
                          <input type="checkbox" checked={t.done} data-testid={`pms-tip-check-${t.index}`}
                            onChange={(e) => toggleTip(t.index, e.target.checked)} className="mt-0.5 accent-emerald-600" />
                          <span className={t.done ? "line-through opacity-60" : ""}>{t.text}</span>
                        </li>
                      ))}
                    </ul>
                    {tips.direct_trend && (
                      <p className="text-[11px] font-bold text-emerald-800 mt-2" data-testid="pms-direct-trend">
                        📈 Doğrudan pay (aylık): {tips.direct_trend.map((d) => `${d.month.slice(5)}: %${d.direct_pct}`).join(" → ")}
                      </p>
                    )}
                  </div>
                )}
                <div className="grid md:grid-cols-2 gap-3 items-center">
                  <div className="h-56" data-testid="pms-revenue-pie">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie data={rows} dataKey="revenue" nameKey="source" cx="50%" cy="50%" outerRadius={85} innerRadius={40} paddingAngle={2}>
                          {rows.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                        </Pie>
                        <Tooltip formatter={(v, n) => [`₺${Number(v).toLocaleString("tr-TR")}`, n]} />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="space-y-1" data-testid="pms-revenue-legend">
                    {rows.map((r, i) => (
                      <div key={r.source} className="flex items-center justify-between gap-2 text-[12px]">
                        <span className="flex items-center gap-1.5 font-bold text-stone-700">
                          <span className="w-2.5 h-2.5 rounded-full inline-block" style={{ background: PIE_COLORS[i % PIE_COLORS.length] }} />{r.source}
                        </span>
                        <span className="text-stone-500">₺{Math.round(r.revenue).toLocaleString("tr-TR")} · %{r.pct}{r.net_revenue < r.revenue - 0.5 ? ` · net ₺${Math.round(r.net_revenue).toLocaleString("tr-TR")}` : ""} · {r.bookings} rez.</span>
                      </div>
                    ))}
                    {rows.length === 0 && <p className="text-[12px] text-stone-400">Bu ayda gelirli rezervasyon yok.</p>}
                  </div>
                </div>
                <div className="mt-3" data-testid="pms-revenue-trend">
                  <p className="text-[12px] font-bold text-stone-700 mb-1">📈 Aylık Pay Trendi (ilk 5 kaynak):
                    {topSources.map((s, i) => <span key={s} className="ml-2 text-[11px]" style={{ color: PIE_COLORS[i] }}>{s}{trendArrow(s)}</span>)}
                  </p>
                  <div className="h-44">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={trendData} margin={{ top: 5, right: 10, bottom: 0, left: -20 }}>
                        <XAxis dataKey="month" tick={{ fontSize: 10 }} />
                        <YAxis tick={{ fontSize: 10 }} unit="%" />
                        <Tooltip formatter={(v, n) => [`%${v}`, n]} />
                        <Legend wrapperStyle={{ fontSize: 10 }} />
                        {topSources.map((s, i) => <Line key={s} type="monotone" dataKey={s} stroke={PIE_COLORS[i]} strokeWidth={2} dot={{ r: 2 }} />)}
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
                <p className="text-[11px] text-stone-400 mt-2" data-testid="pms-revenue-summary">6 aylık brüt: ₺{rev.total_revenue.toLocaleString("tr-TR")} · komisyon sonrası net: ₺{(rev.total_net_revenue ?? rev.total_revenue).toLocaleString("tr-TR")} · en güçlü kanal: {rev.totals[0]?.source || "—"} (%{rev.totals[0]?.pct || 0}) · {rev.commission_note || ""}</p>
              </div>
            );
          })()}
          {drill && (
            <div className={`mt-3 border rounded-xl p-3 ${drill.passed ? "bg-emerald-50 border-emerald-200" : "bg-rose-50 border-rose-200"}`} data-testid="pms-drill-section">
              <div className="flex items-center justify-between gap-2 mb-1.5">
                <p className="text-[12px] font-black text-stone-800">🛑 Kill Switch Tatbikatı: {drill.passed ? "BAŞARILI ✓" : "BAŞARISIZ ✗"}</p>
                <div className="flex gap-1.5">
                  <a href={`${API}/api/pms-connect/killswitch-drill/${pid}/report-pdf`} target="_blank" rel="noreferrer" data-testid="pms-drill-pdf-btn" className="px-2.5 py-1 rounded-lg bg-rose-600 text-white text-[11px] font-bold">📄 Güvence PDF</a>
                  <button onClick={() => { navigator.clipboard.writeText(drill.report); toast.success("Rapor panoya kopyalandı"); }} data-testid="pms-drill-copy-btn" className="px-2.5 py-1 rounded-lg bg-stone-900 text-white text-[11px] font-bold">Raporu Kopyala</button>
                </div>
              </div>
              <pre className="text-[11px] bg-white/70 border border-stone-200 rounded-lg p-2.5 max-h-48 overflow-auto whitespace-pre-wrap" data-testid="pms-drill-report">{drill.report}</pre>
              {drillHist && (
                <div className="mt-2" data-testid="pms-drill-history">
                  <p className="text-[11px] font-bold text-stone-600 mb-1">📜 Tatbikat Arşivi ({drillHist.drills.length}) · <span className="text-emerald-700">Aylık otomatik tatbikat robotu AKTİF — her ayın 1'inde çalışır, PDF'i arşivler</span></p>
                  <div className="space-y-1 max-h-36 overflow-auto">
                    {drillHist.drills.map((d) => (
                      <div key={d.id} className="flex flex-wrap items-center justify-between gap-2 bg-white/70 border border-stone-200 rounded-lg px-2 py-1 text-[11px]" data-testid={`pms-drill-hist-${d.id}`}>
                        <span>{String(d.created_at).slice(0, 16).replace("T", " ")} · <b className={d.passed ? "text-emerald-700" : "text-rose-600"}>{d.passed ? "BAŞARILI" : "BAŞARISIZ"}</b> · {d.triggered_by === "robot" ? "🤖 otomatik" : "manuel"}{d.pdf_archived ? " · 📦 PDF arşivde" : ""}</span>
                        <a href={`${API}/api/pms-connect/killswitch-drill/archive/${d.id}/pdf`} target="_blank" rel="noreferrer" data-testid={`pms-drill-hist-pdf-${d.id}`} className="px-2 py-0.5 rounded bg-stone-900 text-white font-bold">PDF</a>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
          {leads && (
            <div className="mt-3 border-t border-stone-100 pt-3" data-testid="pms-leads-section">
              <p className="text-[12px] font-bold text-stone-700 mb-2">📋 Pilot Takip Listesi ({(leads.leads || []).length} otel){leads.stale_count > 0 && <span className="ml-2 px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 text-[10px] font-black" data-testid="pms-leads-stale-badge">⏰ {leads.stale_count} otel {leads.stale_days_threshold}+ gündür bekliyor</span>}</p>
              {leads.funnel && (leads.leads || []).length > 0 && (
                <div className="flex flex-wrap items-center gap-1.5 mb-2" data-testid="pms-leads-funnel">
                  {leads.funnel.map((f, i) => (
                    <React.Fragment key={f.stage}>
                      {i > 0 && <span className="text-stone-300 text-[11px]">→</span>}
                      <div className={`px-2.5 py-1 rounded-lg border text-[11px] ${f.stage === "pilot" ? "border-emerald-300 bg-emerald-50" : "border-stone-200 bg-stone-50"}`} data-testid={`pms-funnel-${f.stage}`}>
                        <b className="capitalize">{f.stage}</b> <b className="text-stone-900">{f.reached}</b>
                        {f.conv_pct != null && <span className={`ml-1 font-black ${f.conv_pct >= 50 ? "text-emerald-600" : "text-amber-600"}`}>%{f.conv_pct}</span>}
                        {f.avg_days_in_stage != null && <span className="ml-1 text-stone-400">~{f.avg_days_in_stage}g</span>}
                      </div>
                    </React.Fragment>
                  ))}
                  {leads.lost_count > 0 && <span className="px-2 py-1 rounded-lg border border-rose-200 bg-rose-50 text-rose-600 text-[11px] font-bold" data-testid="pms-funnel-lost">✗ kaybedildi {leads.lost_count}</span>}
                </div>
              )}
              <div className="flex flex-wrap gap-2 mb-2">
                <input value={leadForm.hotel_name} onChange={(e) => setLeadForm((f) => ({ ...f, hotel_name: e.target.value }))} data-testid="pms-lead-name-input" className="flex-1 min-w-[160px] border border-stone-300 rounded-lg px-2.5 py-1.5 text-[12px]" placeholder="Otel adı" />
                <input value={leadForm.contact} onChange={(e) => setLeadForm((f) => ({ ...f, contact: e.target.value }))} data-testid="pms-lead-contact-input" className="flex-1 min-w-[160px] border border-stone-300 rounded-lg px-2.5 py-1.5 text-[12px]" placeholder="İletişim (e-posta/telefon)" />
                <input value={leadForm.note} onChange={(e) => setLeadForm((f) => ({ ...f, note: e.target.value }))} data-testid="pms-lead-note-input" className="flex-1 min-w-[160px] border border-stone-300 rounded-lg px-2.5 py-1.5 text-[12px]" placeholder="Not (opsiyonel)" />
                <button onClick={addLead} data-testid="pms-lead-add-btn" className="px-3 py-1.5 rounded-lg bg-sky-600 text-white text-[12px] font-bold">Ekle</button>
              </div>
              {(leads.leads || []).length === 0 ? <p className="text-[11px] text-stone-400" data-testid="pms-leads-empty">Henüz otel eklenmedi — davet gönderdiğiniz otelleri buradan izleyin.</p> : (
                <div className="space-y-1.5">
                  {leads.leads.map((l) => (
                    <div key={l.id} className="bg-white border border-stone-200 rounded-lg px-2.5 py-1.5 text-[12px]" data-testid={`pms-lead-row-${l.id}`}>
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span><b>{l.hotel_name}</b>{l.contact ? ` · ${l.contact}` : ""} <span className="text-stone-400 text-[10px]">({String(l.created_at).slice(0, 10)})</span>{l.stale ? <span className="ml-1.5 px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700 text-[10px] font-black" data-testid={`pms-lead-stale-${l.id}`}>⏰ {l.days_in_stage}g bekliyor</span> : l.days_in_stage > 0 ? <span className="ml-1.5 text-stone-400 text-[10px]">{l.days_in_stage}g</span> : null}</span>
                        <select value={l.status} onChange={(e) => setLeadStatus(l.id, e.target.value)} data-testid={`pms-lead-status-${l.id}`}
                          className={`border rounded-lg px-2 py-0.5 text-[11px] font-bold ${l.status === "pilot" ? "border-emerald-300 text-emerald-700" : l.status === "kaybedildi" ? "border-rose-300 text-rose-600" : "border-stone-300 text-stone-600"}`}>
                          {leads.statuses.map((s) => <option key={s} value={s}>{s}</option>)}
                        </select>
                      </div>
                      <input defaultValue={l.note || ""} onBlur={(e) => { if (e.target.value !== (l.note || "")) saveLeadNote(l.id, e.target.value); }} data-testid={`pms-lead-note-${l.id}`}
                        className="mt-1 w-full border border-stone-200 rounded px-2 py-0.5 text-[11px] text-stone-500 bg-stone-50 focus:bg-white" placeholder="Not ekle… (görüşme özeti, sonraki adım)" />
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
          {invite && (
            <div className="mt-3 border-t border-stone-100 pt-3" data-testid="pms-invite-section">
              <div className="flex flex-wrap items-center justify-between gap-2 mb-1.5">
                <p className="text-[12px] font-bold text-stone-700">✉ {invite.email_subject}</p>
                <button onClick={() => { navigator.clipboard.writeText(`${invite.email_subject}\n\n${invite.email_body}`); toast.success("Davet panoya kopyalandı"); }} data-testid="pms-invite-copy-btn" className="px-2.5 py-1 rounded-lg bg-emerald-600 text-white text-[11px] font-bold">Kopyala</button>
              </div>
              <div className="flex flex-wrap gap-2 mb-1.5 text-[11px]">
                <span className={`px-2 py-0.5 rounded-full font-black ${invite.proof.cert_passed_live ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>Mews sertifikasyon: {invite.proof.cert_passed_live ? "CANLI GEÇTİ" : "MOCK"}</span>
                <span className="px-2 py-0.5 rounded-full bg-stone-100 text-stone-600 font-bold">{invite.proof.live_pushes} canlı push</span>
                <span className="px-2 py-0.5 rounded-full bg-stone-100 text-stone-600 font-bold">Son doğrulama sapması: %{invite.proof.last_verify_drift_pct ?? "—"}</span>
              </div>
              <pre className="text-[11px] bg-stone-50 border border-stone-200 rounded-lg p-3 max-h-56 overflow-auto whitespace-pre-wrap" data-testid="pms-invite-body">{invite.email_body}</pre>
              <p className="text-[10px] text-emerald-700 font-bold mt-1">{invite.attachment_hint}</p>
            </div>
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

          {mapping && mapping.length > 0 && (
            <section className="bg-white border border-stone-200 rounded-xl p-4" data-testid="pms-mapping-section">
              <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                <div>
                  <h2 className="text-base font-bold text-stone-800">🗂 Rate Plan Eşleştirme</h2>
                  <p className="text-[12px] text-stone-500">Oda tipi ↔ {sel.name} rate kodu + fiyat çarpanı. Eşleştirme kaydedilince push oda tipi bazında ayrı ayrı basılır.</p>
                </div>
                <div className="flex items-center gap-2">
                  {sel.mode === "live" && ["mews", "apaleo"].includes(sel.id) && (
                    <button onClick={discoverRates} disabled={busy} data-testid="pms-discover-btn" className="px-3 py-1.5 rounded-lg bg-emerald-600 text-white text-[12px] font-bold disabled:opacity-50">🔎 Oda/Rate Keşfi</button>
                  )}
                  <button onClick={saveMapping} disabled={busy} data-testid="pms-mapping-save-btn" className="px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-[12px] font-bold disabled:opacity-50">Eşleştirmeyi Kaydet</button>
                </div>
              </div>
              <table className="w-full text-[12px]" data-testid="pms-mapping-table">
                <thead><tr className="text-left text-[10px] text-stone-400"><th className="p-1.5">Oda Tipi</th><th className="p-1.5">{sel.name} Rate Kodu / ID</th><th className="p-1.5 w-24">Çarpan</th></tr></thead>
                <tbody>
                  {mapping.map((m, i) => (
                    <tr key={m.room_type_id} className="border-t border-stone-100">
                      <td className="p-1.5 font-bold">{m.room_type_name}</td>
                      <td className="p-1.5">
                        <input value={m.channel_rate_code} list="pms-rate-options" data-testid={`pms-mapping-code-${i}`} onChange={(e) => setMapping((arr) => arr.map((x, j) => j === i ? { ...x, channel_rate_code: e.target.value } : x))} className="w-full border border-stone-300 rounded px-2 py-1 text-[12px]" placeholder="boş = bu oda tipi push edilmez" />
                        {rateOptions.length > 0 && (() => { const opt = rateOptions.find((o) => o.id === m.channel_rate_code); return opt ? <span className="text-[10px] text-emerald-600 font-bold">✓ {opt.name}{opt.is_root ? " (root)" : ""}</span> : null; })()}
                      </td>
                      <td className="p-1.5"><input type="number" step="0.05" value={m.multiplier} data-testid={`pms-mapping-mult-${i}`} onChange={(e) => setMapping((arr) => arr.map((x, j) => j === i ? { ...x, multiplier: parseFloat(e.target.value) || 1 } : x))} className="w-20 border border-stone-300 rounded px-2 py-1 text-[12px]" /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {rateOptions.length > 0 && (
                <datalist id="pms-rate-options">
                  {rateOptions.map((o) => <option key={o.id} value={o.id}>{`${o.name}${o.is_root ? " (root)" : ""}`}</option>)}
                </datalist>
              )}
            </section>
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
                      {verify.rows.map((r, i) => (
                        <tr key={`${r.date}-${r.rate_code || i}`} className="border-t border-stone-200/60">
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
                <button onClick={openPushPreview} disabled={busy} data-testid="pms-preview-btn" className="px-3 py-2 rounded-lg bg-indigo-600 text-white text-sm font-bold disabled:opacity-50">👁 Önizle & Gönder</button>
                <button onClick={pushRms} disabled={busy} data-testid="pms-push-btn" className="px-3 py-2 rounded-lg bg-stone-900 text-white text-sm font-bold disabled:opacity-50 flex items-center gap-1.5"><PaperPlaneTilt size={14} /> Fiyat Push</button>
                {pushPreview && (
                  <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={() => setPushPreview(null)} data-testid="pms-preview-modal">
                    <div className="bg-white rounded-2xl max-w-3xl w-full max-h-[80vh] flex flex-col p-5" onClick={(e) => e.stopPropagation()}>
                      <h3 className="text-base font-black text-stone-800 mb-1">👁 {sel.name} Push Önizleme</h3>
                      <p className="text-[11px] text-stone-500 mb-3">{pushPreview.rooms.map((r) => `${r.room_type} → ${r.rateID}`).join(" · ")} · toplam {pushPreview.total_prices} fiyat</p>
                      <div className="overflow-auto flex-1 border border-stone-200 rounded-xl">
                        <table className="w-full text-[12px]">
                          <thead className="bg-stone-50 sticky top-0"><tr>
                            <th className="text-left px-3 py-2 font-black text-stone-600">Tarih</th>
                            {pushPreview.rooms.map((r) => <th key={r.rateID} className="text-right px-3 py-2 font-black text-stone-600">{r.room_type}</th>)}
                          </tr></thead>
                          <tbody>
                            {pushPreview.table.map((row) => (
                              <tr key={row.date} className="border-t border-stone-100" data-testid={`pms-preview-row-${row.date}`}>
                                <td className="px-3 py-1.5 font-bold text-stone-700">{row.date}</td>
                                {pushPreview.rooms.map((r) => {
                                  const c = row.cells[r.room_type];
                                  return <td key={r.rateID} className="px-3 py-1.5 text-right">{c ? `£${c.rate}` : "—"}</td>;
                                })}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                      <div className="flex justify-end gap-2 mt-4">
                        <button onClick={() => setPushPreview(null)} data-testid="pms-preview-cancel" className="px-4 py-2 rounded-lg border border-stone-300 text-stone-600 text-sm font-bold">Vazgeç</button>
                        <button onClick={() => { setPushPreview(null); pushRms(); }} data-testid="pms-preview-confirm" className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-bold hover:bg-emerald-700">✓ Onayla ve Gönder</button>
                      </div>
                    </div>
                  </div>
                )}
                <button onClick={pullRes} disabled={busy} data-testid="pms-pull-btn" className="px-3 py-2 rounded-lg border border-stone-300 text-stone-700 text-sm font-bold disabled:opacity-50 flex items-center gap-1.5"><DownloadSimple size={14} /> Rezervasyon Çek</button>
              </div>
              {lastPush && (
                <div className="text-[12px] bg-stone-50 border border-stone-200 rounded-lg p-2 space-y-1" data-testid="pms-last-push">
                  <div>{lastPush.mocked ? "🟡 MOCK" : lastPush.mocked === false ? "🟢 CANLI" : "ℹ"} · {lastPush.pushed_days ?? 0} gün{lastPush.message ? ` · ${lastPush.message}` : ""}</div>
                  {lastPush.per_room_type && (
                    <div className="space-y-0.5" data-testid="pms-per-roomtype">
                      {lastPush.per_room_type.map((r, i) => (
                        <div key={`${r.room_type}-${i}`} className="text-[11px]">
                          {r.error ? "❌" : "✅"} <b>{r.room_type}</b> → {r.channel_rate_code} (×{r.multiplier ?? 1}){r.error ? ` — ${r.error}` : ` · ${r.pushed_days} gün ${r.mocked ? "MOCK" : "CANLI"}`}
                        </div>
                      ))}
                    </div>
                  )}
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

