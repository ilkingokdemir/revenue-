/** Admin — Sahip Portalı (Pulse) modül kontrolü + önizleme */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Gauge, Eye, EyeSlash, FloppyDisk, ArrowSquareOut, EnvelopeSimple, PaperPlaneTilt, Robot } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const MODULES = [
  { key: "dashboard", label: "Genel Bakış (Pulse Dashboard)", desc: "Aylık gelir kartları + YoY, 90g doluluk & pickup, yıllık tablo" },
  { key: "demand_radar", label: "Talep Radarı", desc: "90 gün pazar zekâsı: talep/fiyat/arz timeline, pickup, fırsat haritası" },
  { key: "compset", label: "Rekabet Analizi (Compset)", desc: "Segment kıyası, sıralamalar, günlük drill-down" },
  { key: "reports", label: "Rapor Merkezi", desc: "Performans, YoY, rezervasyon ve kanal raporları + CSV" },
  { key: "rates", label: "Fiyatlar & İndirimler", desc: "İki yönlü fiyat panosu (mevcut modül)" },
  { key: "portfolio", label: "Portföy Panosu", desc: "Birleşik kartlar + doluluk ısı haritası + tesis YoY tabloları" },
];

export default function OwnerPulseAdminPanel({ propertyId }) {
  const pid = !propertyId || propertyId === "all" ? "default" : propertyId;
  const [modules, setModules] = useState(null);
  const [preview, setPreview] = useState(null);
  const [saving, setSaving] = useState(false);
  const [digestOn, setDigestOn] = useState(false);
  const [digestLog, setDigestLog] = useState([]);
  const [sending, setSending] = useState(false);
  const [ap, setAp] = useState({ mode: "off", occ_threshold: 35 });
  const [apStatus, setApStatus] = useState({ pending_approvals: [], recent_log: [] });
  const [apBusy, setApBusy] = useState(false);

  const loadAutopilot = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/owner-pulse/autopilot/status`);
      setApStatus(data);
      if (data.configs[pid]) setAp(data.configs[pid]);
    } catch { /* noop */ }
  }, [pid]);

  const load = useCallback(async () => {
    try {
      const [{ data: cfg }, { data: dash }, { data: log }] = await Promise.all([
        axios.get(`${API}/owner-pulse/${pid}/config`),
        axios.get(`${API}/owner-pulse/${pid}/dashboard`),
        axios.get(`${API}/owner-pulse/${pid}/digest/log`),
      ]);
      setModules(cfg.modules);
      setDigestOn(!!cfg.digest_enabled);
      setPreview(dash);
      setDigestLog(log.items || []);
    } catch { toast.error("Yüklenemedi"); }
  }, [pid]);

  useEffect(() => { load(); loadAutopilot(); }, [load, loadAutopilot]);

  const saveAutopilot = async (next) => {
    setApBusy(true);
    try {
      await axios.put(`${API}/owner-pulse/autopilot/${pid}`, next);
      setAp(next);
      toast.success(`Autopilot: ${next.mode === "off" ? "kapalı" : next.mode === "approval" ? "onaylı mod" : "tam otomatik"}`);
    } catch { toast.error("Kaydedilemedi"); }
    setApBusy(false);
  };

  const runAutopilot = async () => {
    setApBusy(true);
    try {
      const { data } = await axios.post(`${API}/owner-pulse/autopilot/run-now`);
      toast.success(`Tarama bitti: ${data.checked} tesis kontrol edildi`);
      loadAutopilot();
    } catch { toast.error("Tarama başarısız"); }
    setApBusy(false);
  };

  const decide = async (aid, decision) => {
    try {
      const { data } = await axios.post(`${API}/owner-pulse/autopilot/approvals/${aid}/decide`, { decision });
      toast.success(data.detail);
      loadAutopilot();
    } catch { toast.error("İşlem başarısız"); }
  };

  const save = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/owner-pulse/${pid}/config`, { modules, digest_enabled: digestOn });
      toast.success("Sahip portalı modülleri güncellendi");
    } catch { toast.error("Kaydedilemedi"); }
    setSaving(false);
  };

  const sendNow = async () => {
    setSending(true);
    try {
      const { data } = await axios.post(`${API}/owner-pulse/${pid}/digest/send-now`);
      toast.success(`Pulse özeti gönderildi: ${data.sent}/${data.owners} sahip`);
      const { data: log } = await axios.get(`${API}/owner-pulse/${pid}/digest/log`);
      setDigestLog(log.items || []);
    } catch (e) { toast.error(e?.response?.data?.detail || "Gönderilemedi"); }
    setSending(false);
  };

  if (!modules) return <div className="text-center py-12 text-stone-400 text-sm">Yükleniyor…</div>;
  const pc = preview?.currency || "GBP";
  const c = pc === "GBP" ? "£" : pc === "EUR" ? "€" : pc === "TRY" ? "₺" : pc === "USD" ? "$" : pc + " ";

  return (
    <div className="space-y-6 rounded-2xl bg-stone-950 border border-stone-800 p-6" data-testid="owner-pulse-admin-panel">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-2xl font-semibold text-stone-100 flex items-center gap-2"><Gauge size={22} className="text-teal-400" /> Sahip Portalı — Pulse Modülleri</h2>
          <p className="text-sm text-stone-400 mt-1">Otel sahibinin <code className="text-teal-300">/owner</code> portalında hangi analitik ekranları göreceğini buradan yönetin. Kapatılan modül sahip tarafında anında gizlenir (API de 403 döner).</p>
        </div>
        <a href="/owner" target="_blank" rel="noreferrer" data-testid="opa-open-portal"
           className="text-xs px-3 py-2 rounded-lg bg-stone-800 border border-stone-700 text-stone-200 inline-flex items-center gap-1 hover:bg-stone-700"><ArrowSquareOut size={13} /> Sahip Portalını Aç</a>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {MODULES.map((m) => (
          <button key={m.key} onClick={() => setModules({ ...modules, [m.key]: !modules[m.key] })}
            data-testid={`opa-toggle-${m.key}`}
            className={`text-left rounded-xl border p-4 transition-colors ${modules[m.key] ? "bg-teal-500/10 border-teal-500/40" : "bg-stone-900/60 border-stone-800 opacity-70"}`}>
            <div className="flex items-center justify-between">
              <span className={`text-sm font-semibold ${modules[m.key] ? "text-teal-200" : "text-stone-400"}`}>{m.label}</span>
              {modules[m.key] ? <Eye size={16} className="text-teal-300" /> : <EyeSlash size={16} className="text-stone-500" />}
            </div>
            <div className="text-[11px] text-stone-500 mt-1">{m.desc}</div>
            <div className={`text-[10px] font-bold mt-2 ${modules[m.key] ? "text-teal-300" : "text-stone-500"}`}>{modules[m.key] ? "SAHİBE AÇIK" : "GİZLİ"}</div>
          </button>
        ))}
      </div>

      <button onClick={save} disabled={saving} data-testid="opa-save-btn"
        className="px-4 py-2 rounded-lg bg-teal-500/20 border border-teal-500/40 text-teal-200 text-sm font-semibold inline-flex items-center gap-2 hover:bg-teal-500/30 disabled:opacity-50">
        <FloppyDisk size={15} /> {saving ? "Kaydediliyor…" : "Değişiklikleri Kaydet"}
      </button>

      <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4 space-y-3" data-testid="opa-digest-section">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div>
            <div className="text-sm font-semibold text-stone-200 flex items-center gap-2"><EnvelopeSimple size={16} className="text-amber-400" /> Haftalık Pulse Özeti E-postası</div>
            <div className="text-[11px] text-stone-500 mt-0.5">Her Pazartesi sahiplere otomatik gönderilir: aylık kartlar + haftanın 3 içgörüsü + portföy tablosu. (Resend anahtarı yoksa mock loglanır)</div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => setDigestOn(!digestOn)} data-testid="opa-digest-toggle"
              className={`text-xs px-3 py-1.5 rounded-lg border font-semibold ${digestOn ? "bg-amber-500/15 border-amber-500/40 text-amber-300" : "bg-stone-800 border-stone-700 text-stone-400"}`}>
              {digestOn ? "OTOMATİK AÇIK" : "OTOMATİK KAPALI"}
            </button>
            <button onClick={sendNow} disabled={sending} data-testid="opa-digest-send-now"
              className="text-xs px-3 py-1.5 rounded-lg bg-amber-500/20 border border-amber-500/40 text-amber-200 font-semibold inline-flex items-center gap-1 disabled:opacity-50">
              <PaperPlaneTilt size={13} /> {sending ? "Gönderiliyor…" : "Şimdi Gönder"}
            </button>
          </div>
        </div>
        {digestLog.length > 0 && (
          <table className="w-full text-xs" data-testid="opa-digest-log">
            <thead className="text-[9px] uppercase text-stone-500"><tr><th className="text-left py-1">Gönderim</th><th className="text-left">Sahip</th><th className="text-right">Durum</th></tr></thead>
            <tbody>
              {digestLog.slice(0, 8).map((l) => (
                <tr key={l.id} className="border-t border-stone-800/60">
                  <td className="py-1.5 text-stone-400">{(l.sent_at || "").slice(0, 16).replace("T", " ")}</td>
                  <td className="text-stone-300">{l.owner_email}</td>
                  <td className={`text-right font-semibold ${l.status === "failed" ? "text-rose-400" : "text-emerald-400"}`}>{l.status === "mock" ? "gönderildi (mock)" : l.status === "sent" ? "gönderildi" : "hata"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4 space-y-3" data-testid="opa-autopilot-section">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div>
            <div className="text-sm font-semibold text-stone-200 flex items-center gap-2"><Robot size={16} className="text-rose-400" /> Kurtarma Autopilot</div>
            <div className="text-[11px] text-stone-500 mt-0.5">30g ort. doluluk eşiğin altına düşerse sistem kurtarma promosyonunu kendisi açar (otomatik) veya onayınıza sunar (onaylı). 6 saatte bir tarar.</div>
          </div>
          <button onClick={runAutopilot} disabled={apBusy} data-testid="opa-ap-run-now"
            className="text-xs px-3 py-1.5 rounded-lg bg-rose-500/20 border border-rose-500/40 text-rose-200 font-semibold disabled:opacity-50">Şimdi Tara</button>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {[["off", "Kapalı"], ["approval", "Onaylı Mod"], ["auto", "Tam Otomatik"]].map(([m, label]) => (
            <button key={m} onClick={() => saveAutopilot({ ...ap, mode: m })} disabled={apBusy} data-testid={`opa-ap-mode-${m}`}
              className={`text-xs px-3 py-1.5 rounded-lg border font-semibold ${ap.mode === m ? "bg-rose-500/20 border-rose-500/40 text-rose-200" : "bg-stone-800 border-stone-700 text-stone-400"}`}>
              {label}
            </button>
          ))}
          <label className="flex items-center gap-1.5 text-xs text-stone-400 ml-2">Doluluk eşiği %
            <input type="number" value={ap.occ_threshold} data-testid="opa-ap-threshold"
              onChange={(e) => setAp({ ...ap, occ_threshold: parseFloat(e.target.value) || 35 })}
              onBlur={() => saveAutopilot(ap)}
              className="w-16 px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-200" />
          </label>
        </div>
        {apStatus.pending_approvals.length > 0 && (
          <div className="space-y-2" data-testid="opa-ap-approvals">
            <div className="text-[10px] uppercase text-amber-400 font-bold">Onay Bekleyenler ({apStatus.pending_approvals.length})</div>
            {apStatus.pending_approvals.map((a) => (
              <div key={a.id} className="flex items-center justify-between gap-2 rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2">
                <div className="text-xs text-stone-200">
                  <b>{a.property_name}</b> — ort. doluluk %{a.avg_occ} (eşik %{a.threshold}), {a.weak_days} zayıf gün → %15 son-dakika promosyonu
                </div>
                <div className="flex gap-1.5">
                  <button onClick={() => decide(a.id, "approve")} data-testid={`opa-ap-approve-${a.id}`} className="text-[10px] font-bold px-2 py-1 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-300">Onayla</button>
                  <button onClick={() => decide(a.id, "reject")} data-testid={`opa-ap-reject-${a.id}`} className="text-[10px] font-bold px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-400">Reddet</button>
                </div>
              </div>
            ))}
          </div>
        )}
        {apStatus.recent_log.length > 0 && (
          <div>
            <div className="text-[10px] uppercase text-stone-500 font-bold mb-1">Son Otomatik Müdahaleler</div>
            {apStatus.recent_log.slice(0, 5).map((l) => (
              <div key={l.id} className="text-[11px] text-stone-400 border-t border-stone-800/60 py-1">
                {(l.created_at || "").slice(0, 16).replace("T", " ")} · <span className="text-stone-300">{l.property_id}</span> · occ %{l.avg_occ} → {l.detail}
              </div>
            ))}
          </div>
        )}
      </div>

      {preview && (
        <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4" data-testid="opa-preview">
          <div className="text-xs uppercase tracking-wider text-stone-500 font-semibold mb-3">Sahibin Göreceği Aylık Kartlar (önizleme)</div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {preview.month_cards.map((m) => (
              <div key={m.label} className="rounded-lg border border-stone-800 bg-stone-950/60 p-3">
                <div className="flex items-center justify-between text-[10px] text-stone-500 uppercase"><span>{m.label} · {m.tag}</span>
                  {m.yoy_pct != null && <span className={m.yoy_pct >= 0 ? "text-emerald-400" : "text-rose-400"}>YoY {m.yoy_pct >= 0 ? "+" : ""}{m.yoy_pct}%</span>}
                </div>
                <div className="text-xl font-bold text-stone-100 mt-1">{c}{(m.revenue || 0).toLocaleString()}</div>
                <div className="text-[10px] text-stone-500">Occ {m.occ}% · ADR {c}{Math.round(m.adr)}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
