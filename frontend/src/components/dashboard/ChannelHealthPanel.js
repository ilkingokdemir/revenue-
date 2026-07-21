import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  HeartStraight, ArrowsClockwise, Wrench, WarningCircle, CheckCircle,
  CloudSlash, Clock, ArrowCounterClockwise, BellRinging, PaperPlaneTilt, ClockCounterClockwise,
} from "@phosphor-icons/react";
import ChannelPushHistory from "./ChannelPushHistory";

const API = process.env.REACT_APP_BACKEND_URL;

const STATUS_META = {
  healthy: { label: "SAĞLIKLI", cls: "bg-emerald-100 text-emerald-700 border-emerald-200", dot: "bg-emerald-500" },
  warning: { label: "UYARI", cls: "bg-amber-100 text-amber-700 border-amber-200", dot: "bg-amber-500" },
  critical: { label: "KRİTİK", cls: "bg-rose-100 text-rose-700 border-rose-200", dot: "bg-rose-500" },
  no_data: { label: "VERİ YOK", cls: "bg-stone-100 text-stone-500 border-stone-200", dot: "bg-stone-300" },
};

const fmtTime = (iso) => {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleString("tr-TR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }); }
  catch { return iso; }
};

export default function ChannelHealthPanel({ propertyId }) {
  const [tab, setTab] = useState("health");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [webhook, setWebhook] = useState("");
  const [webhookInfo, setWebhookInfo] = useState(null);

  const load = useCallback(async () => {
    try {
      const [r, w] = await Promise.all([
        axios.get(`${API}/api/channel-health/${propertyId}`),
        axios.get(`${API}/api/channel-health/webhook-config/get`),
      ]);
      setData(r.data);
      setWebhook(w.data.webhook_url || "");
      setWebhookInfo(w.data);
    } catch { toast.error("Kanal sağlık verisi yüklenemedi"); }
    finally { setLoading(false); }
  }, [propertyId]);
  useEffect(() => { load(); }, [load]);

  const saveWebhook = async () => {
    setBusy("webhook");
    try {
      await axios.put(`${API}/api/channel-health/webhook-config`, { webhook_url: webhook });
      toast.success(webhook ? "Webhook kaydedildi" : "Webhook kaldırıldı");
    } catch { toast.error("Kaydetme başarısız"); }
    finally { setBusy(""); }
  };

  const testWebhook = async () => {
    setBusy("webhook-test");
    try {
      const r = await axios.post(`${API}/api/channel-health/webhook-test`);
      toast.success(`Test uyarısı gönderildi (uygulama içi bildirim${r.data.webhook_configured ? " + webhook" : ""})`);
      await load();
    } catch { toast.error("Test başarısız"); }
    finally { setBusy(""); }
  };

  const heal = async () => {
    setBusy("heal");
    try {
      const r = await axios.post(`${API}/api/channel-health/heal`, { property_id: propertyId });
      toast.success(`İyileştirme: ${r.data.requeued} görev yeniden kuyruğa alındı, ${r.data.alerts_resolved} uyarı kapandı`);
      await load();
    } catch { toast.error("İyileştirme başarısız"); }
    finally { setBusy(""); }
  };

  const retryTask = async (id) => {
    setBusy(id);
    try {
      await axios.post(`${API}/api/sync-queue/${id}/retry`);
      toast.success("Görev yeniden kuyruğa alındı");
      await load();
    } catch { toast.error("Yeniden deneme başarısız"); }
    finally { setBusy(""); }
  };

  if (loading) return <div className="p-8 text-stone-400 text-sm" data-testid="channel-health-loading">Yükleniyor…</div>;
  if (!data) return <div className="p-8 text-stone-400 text-sm">Veri yok</div>;

  const s = data.summary;

  return (
    <div className="space-y-6" data-testid="channel-health-panel">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
            <HeartStraight size={12} weight="fill" className="text-rose-500" />
            <span>Kanal Sağlık Merkezi</span>
          </div>
          <h2 className="text-xl font-semibold text-stone-900">OTA senkron sağlığı & otomatik iyileştirme</h2>
          <p className="text-xs text-stone-500 mt-1">
            <span className="font-medium text-emerald-600">{s.healthy} sağlıklı</span>
            {s.warning > 0 && <span className="font-medium text-amber-600"> · {s.warning} uyarı</span>}
            {s.critical > 0 && <span className="font-medium text-rose-600"> · {s.critical} kritik</span>}
            {s.no_data > 0 && <span className="text-stone-400"> · {s.no_data} veri yok</span>}
            {" "}— Watchdog her gün dead-letter görevleri otomatik yeniden dener ve {data.stale_hours} saatten eski senkronları raporlar.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={heal} disabled={busy === "heal"} data-testid="channel-heal-btn"
            className="inline-flex items-center gap-1.5 text-xs font-medium text-white bg-stone-900 rounded-lg px-4 py-2 hover:bg-stone-800 disabled:opacity-50">
            <Wrench size={14} weight="fill" /> {busy === "heal" ? "İyileştiriliyor…" : "Şimdi iyileştir"}
          </button>
          <button onClick={load} data-testid="channel-health-refresh"
            className="inline-flex items-center gap-1.5 text-xs text-stone-500 hover:text-stone-800 border border-stone-200 rounded-lg px-3 py-2 bg-white transition-colors">
            <ArrowsClockwise size={14} /> Yenile
          </button>
        </div>
      </div>

      <div className="flex items-center gap-1.5 border-b border-stone-200">
        <button onClick={() => setTab("health")} data-testid="channel-tab-health"
          className={`inline-flex items-center gap-1.5 text-xs font-medium px-3.5 py-2.5 border-b-2 -mb-px transition-colors ${tab === "health" ? "border-stone-900 text-stone-900" : "border-transparent text-stone-500 hover:text-stone-800"}`}>
          <HeartStraight size={14} weight={tab === "health" ? "fill" : "regular"} /> Sağlık & Uyarılar
        </button>
        <button onClick={() => setTab("history")} data-testid="channel-tab-history"
          className={`inline-flex items-center gap-1.5 text-xs font-medium px-3.5 py-2.5 border-b-2 -mb-px transition-colors ${tab === "history" ? "border-stone-900 text-stone-900" : "border-transparent text-stone-500 hover:text-stone-800"}`}>
          <ClockCounterClockwise size={14} weight={tab === "history" ? "fill" : "regular"} /> Push Geçmişi
        </button>
      </div>

      {tab === "history" ? (
        <ChannelPushHistory propertyId={propertyId} />
      ) : (
      <>
      {data.alerts.length > 0 && (
        <div className="bg-rose-50 border border-rose-200 rounded-xl p-4 space-y-2" data-testid="channel-alerts">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-rose-700">
            <WarningCircle size={14} weight="fill" /> Açık uyarılar ({data.alerts.length})
          </div>
          {data.alerts.map((a, i) => (
            <div key={i} className="text-xs text-rose-700 flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-rose-500 shrink-0" />
              {a.message} <span className="text-rose-400">· {fmtTime(a.updated_at)}</span>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {data.channels.map((c) => {
          const m = STATUS_META[c.status];
          return (
            <div key={c.channel} data-testid={`channel-card-${c.channel}`}
              className="bg-white border border-stone-200 rounded-xl p-4">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-sm text-stone-900">{c.label}</span>
                <span className={`inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded border ${m.cls}`}>
                  <span className={`h-1.5 w-1.5 rounded-full ${m.dot}`} /> {m.label}
                </span>
              </div>
              <div className="mt-3 space-y-1.5 text-[11px] text-stone-500">
                <div className="flex justify-between">
                  <span>Başarı (24s)</span>
                  <span className="font-medium text-stone-800">
                    {c.success_rate !== null ? `%${c.success_rate}` : "—"}
                    {c.total_24h > 0 && <span className="text-stone-400"> ({c.succeeded_24h}/{c.total_24h})</span>}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Bekleyen</span>
                  <span className={`font-medium ${c.pending > 20 ? "text-amber-600" : "text-stone-800"}`}>{c.pending}</span>
                </div>
                <div className="flex justify-between">
                  <span>Dead-letter</span>
                  <span className={`font-medium ${c.dead_letter > 0 ? "text-rose-600" : "text-stone-800"}`}>{c.dead_letter}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="inline-flex items-center gap-1"><Clock size={11} /> Son başarı</span>
                  <span className="font-medium text-stone-700">{fmtTime(c.last_success)}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="alert-webhook-config">
        <div className="flex items-center gap-2 mb-1">
          <BellRinging size={15} weight="fill" className="text-cyan-600" />
          <h3 className="text-sm font-semibold text-stone-900">Anlık uyarı ayarları</h3>
        </div>
        <p className="text-[11px] text-stone-500 mb-3">
          Kritik kanal uyarıları anında uygulama içi bildirim merkezine düşer. İsteğe bağlı: Slack uyumlu webhook URL'i girin (Slack Incoming Webhook, Mattermost, Discord /slack uçları desteklenir).
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <input type="url" value={webhook} onChange={(e) => setWebhook(e.target.value)}
            placeholder="https://hooks.slack.com/services/…"
            data-testid="webhook-url-input"
            className="flex-1 min-w-[260px] text-sm border border-stone-200 rounded-lg px-3 py-2 bg-white" />
          <button onClick={saveWebhook} disabled={busy === "webhook"} data-testid="webhook-save-btn"
            className="text-xs font-medium text-white bg-stone-900 rounded-lg px-4 py-2 hover:bg-stone-800 disabled:opacity-50">
            Kaydet
          </button>
          <button onClick={testWebhook} disabled={busy === "webhook-test"} data-testid="webhook-test-btn"
            className="inline-flex items-center gap-1.5 text-xs font-medium text-cyan-700 border border-cyan-200 rounded-lg px-3 py-2 bg-cyan-50 hover:border-cyan-300 disabled:opacity-50">
            <PaperPlaneTilt size={13} weight="fill" /> Test uyarısı gönder
          </button>
        </div>
        {webhookInfo?.last_delivery_at && (
          <p className="text-[11px] text-stone-400 mt-2">
            Son webhook teslimi: {fmtTime(webhookInfo.last_delivery_at)} — durum: <span className={String(webhookInfo.last_delivery_status).startsWith("2") ? "text-emerald-600" : "text-rose-600"}>{String(webhookInfo.last_delivery_status)}</span>
          </p>
        )}
      </div>

      <div className="bg-white border border-stone-200 rounded-xl overflow-hidden" data-testid="dead-letter-table">
        <div className="px-4 py-3 border-b border-stone-100 flex items-center gap-2">
          <CloudSlash size={15} className="text-stone-400" />
          <h3 className="text-sm font-semibold text-stone-900">Dead-letter kuyruğu ({data.dead_letters.length})</h3>
        </div>
        {data.dead_letters.length === 0 ? (
          <div className="px-4 py-5 text-xs text-emerald-600 flex items-center gap-1.5">
            <CheckCircle size={14} weight="fill" /> Kalıcı başarısız görev yok — tüm senkronlar sağlıklı
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[11px] uppercase tracking-wide text-stone-400 border-b border-stone-100">
                <th className="text-left px-4 py-2 font-medium">Kanal</th>
                <th className="text-left px-2 py-2 font-medium">Tür</th>
                <th className="text-left px-2 py-2 font-medium">Hata</th>
                <th className="text-right px-2 py-2 font-medium">Deneme</th>
                <th className="text-right px-4 py-2 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {data.dead_letters.map((t) => (
                <tr key={t.id} className="border-b border-stone-50 last:border-0">
                  <td className="px-4 py-2 font-medium text-stone-800">{t.channel_id || "—"}</td>
                  <td className="px-2 py-2 text-stone-600 text-xs">{t.kind}</td>
                  <td className="px-2 py-2 text-rose-600 text-xs">{t.error || "—"}</td>
                  <td className="px-2 py-2 text-right text-stone-600">{t.attempts}</td>
                  <td className="px-4 py-2 text-right">
                    <button onClick={() => retryTask(t.id)} disabled={busy === t.id}
                      data-testid={`retry-task-${t.id}`}
                      className="inline-flex items-center gap-1 text-[11px] font-medium text-stone-600 border border-stone-200 rounded-lg px-2.5 py-1 bg-white hover:border-stone-300 disabled:opacity-50">
                      <ArrowCounterClockwise size={12} /> Yeniden dene
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      </>
      )}
    </div>
  );
}
