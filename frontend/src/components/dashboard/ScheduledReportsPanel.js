/**
 * ScheduledReportsPanel (iter 368) — Mews parity
 * ------------------------------------------------
 * Managers subscribe to reports (daily/weekly/monthly) delivered by email.
 * Also lists recent snapshots with download links.  Email delivery is
 * currently MOCKED — snapshots are stored + downloadable.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  FileBarChart, Mail, Play, Trash2, ToggleLeft, ToggleRight,
  Download, Plus, Loader2, RefreshCw, Clock,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function ScheduledReportsPanel({ propertyId, userEmail = "" }) {
  const [catalog, setCatalog] = useState(null);
  const [subs, setSubs] = useState([]);
  const [snaps, setSnaps] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [busy, setBusy] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [c, s, sn] = await Promise.all([
        axios.get(`${API}/reports/catalog`),
        axios.get(`${API}/reports/subscriptions`),
        axios.get(`${API}/reports/snapshots?limit=15`),
      ]);
      setCatalog(c.data);
      setSubs(s.data.items || []);
      setSnaps(sn.data.items || []);
    } catch { toast.error("Rapor listesi yüklenemedi"); }
    setLoading(false);
  }, []);
  useEffect(() => { load(); }, [load]);

  const runNow = async (subId) => {
    setBusy(subId);
    try {
      const r = await axios.post(`${API}/reports/subscriptions/${subId}/run-now`);
      toast.success(`Rapor oluşturuldu (${(r.data.size_bytes / 1024).toFixed(1)} KB)`);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Başarısız"); }
    setBusy(null);
  };

  const toggleEnabled = async (sub) => {
    try {
      await axios.put(`${API}/reports/subscriptions/${sub.id}`, { enabled: !sub.enabled });
      load();
    } catch { toast.error("Güncellenemedi"); }
  };

  const remove = async (subId) => {
    if (!window.confirm("Abonelik silinsin mi? Geçmiş snapshotlar kalır.")) return;
    try {
      await axios.delete(`${API}/reports/subscriptions/${subId}`);
      toast.success("Silindi");
      load();
    } catch { toast.error("Silinemedi"); }
  };

  const downloadSnap = (snapId, reportKey) => {
    // Use axios to include auth header, then convert response to blob
    axios.get(`${API}/reports/snapshots/${snapId}/download`, { responseType: "blob" })
      .then((r) => {
        const url = URL.createObjectURL(r.data);
        const a = document.createElement("a");
        a.href = url; a.download = `${reportKey}-${snapId.slice(0, 8)}`; a.click();
        URL.revokeObjectURL(url);
      })
      .catch(() => toast.error("İndirme başarısız"));
  };

  return (
    <div className="space-y-6" data-testid="scheduled-reports-panel">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <div className="p-3 rounded-xl bg-emerald-500/20">
            <FileBarChart className="w-6 h-6 text-emerald-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-stone-100">Planlı Raporlar</h2>
            <p className="text-sm text-stone-400">Günlük / haftalık / aylık raporlar otomatik e-posta ile gelir.</p>
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={load} className="p-2 rounded-lg bg-stone-800 hover:bg-stone-700 text-stone-300" data-testid="reports-refresh">
            <RefreshCw className="w-4 h-4" />
          </button>
          <button
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-bold"
            data-testid="reports-add-btn"
          >
            <Plus className="w-4 h-4" /> Abonelik Ekle
          </button>
        </div>
      </div>

      {showAdd && catalog && (
        <AddSubscriptionForm
          catalog={catalog}
          defaultEmail={userEmail}
          propertyId={propertyId}
          onCancel={() => setShowAdd(false)}
          onCreated={() => { setShowAdd(false); load(); }}
        />
      )}

      {/* Subscriptions */}
      <div className="rounded-xl border border-stone-800 bg-stone-900/60">
        <div className="px-4 py-3 border-b border-stone-800 text-sm font-bold text-stone-100">
          Aboneliklerim ({subs.length})
        </div>
        {loading ? (
          <div className="flex items-center justify-center py-8 text-stone-500">
            <Loader2 className="w-5 h-5 animate-spin" />
          </div>
        ) : subs.length === 0 ? (
          <div className="text-center py-8 text-stone-500 text-sm" data-testid="reports-empty">
            Henüz abonelik yok. Yukarıdan bir tane ekleyin.
          </div>
        ) : (
          <div className="divide-y divide-stone-800">
            {subs.map((s) => {
              const meta = catalog?.items?.find((c) => c.key === s.report_key);
              return (
                <div key={s.id} className="flex items-center gap-3 px-4 py-3" data-testid="sub-row">
                  <button
                    onClick={() => toggleEnabled(s)}
                    className={s.enabled ? "text-emerald-400" : "text-stone-600"}
                    title={s.enabled ? "Aktif — kapat" : "Kapalı — aç"}
                    data-testid={`sub-toggle-${s.id}`}
                  >
                    {s.enabled ? <ToggleRight className="w-8 h-8" /> : <ToggleLeft className="w-8 h-8" />}
                  </button>
                  <div className="flex-1 min-w-0">
                    <div className="text-stone-100 font-semibold">{meta?.label || s.report_key}</div>
                    <div className="text-xs text-stone-500 flex items-center gap-3 flex-wrap">
                      <span className="flex items-center gap-1"><Mail className="w-3 h-3" />{s.email}</span>
                      <span className="px-1.5 py-0.5 rounded bg-stone-800 text-stone-300 text-[10px] uppercase">{s.frequency}</span>
                      <span className="flex items-center gap-1"><Clock className="w-3 h-3" />
                        Next: {new Date(s.next_run_at).toLocaleString("tr-TR", { dateStyle: "short", timeStyle: "short" })}
                      </span>
                      {s.last_run_at && <span className="text-emerald-300/70">Son: {new Date(s.last_run_at).toLocaleString("tr-TR", { dateStyle: "short", timeStyle: "short" })}</span>}
                    </div>
                  </div>
                  <button
                    onClick={() => runNow(s.id)}
                    disabled={busy === s.id}
                    className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 text-white text-xs font-bold"
                    data-testid={`sub-run-${s.id}`}
                  >
                    {busy === s.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
                    Şimdi çalıştır
                  </button>
                  <button
                    onClick={() => remove(s.id)}
                    className="p-1.5 text-stone-500 hover:text-rose-400"
                    data-testid={`sub-del-${s.id}`}
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Snapshots */}
      <div className="rounded-xl border border-stone-800 bg-stone-900/60">
        <div className="px-4 py-3 border-b border-stone-800 text-sm font-bold text-stone-100">
          Son Teslimler ({snaps.length})
        </div>
        {snaps.length === 0 ? (
          <div className="text-center py-8 text-stone-500 text-sm">
            Henüz teslim yok. Bir aboneliği "Şimdi çalıştır" ile test edin.
          </div>
        ) : (
          <div className="divide-y divide-stone-800">
            {snaps.map((sn) => {
              const meta = catalog?.items?.find((c) => c.key === sn.report_key);
              return (
                <div key={sn.id} className="flex items-center gap-3 px-4 py-3" data-testid="snap-row">
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-stone-100 font-medium">{meta?.label || sn.report_key}</div>
                    <div className="text-xs text-stone-500 flex items-center gap-2">
                      <span>{new Date(sn.created_at).toLocaleString("tr-TR")}</span>
                      <span>·</span>
                      <span>{(sn.size_bytes / 1024).toFixed(1)} KB</span>
                      <span>·</span>
                      <span className="px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-300 text-[10px] uppercase">
                        {sn.delivery_status?.replace(/_/g, " ") || "unknown"}
                      </span>
                    </div>
                  </div>
                  <button
                    onClick={() => downloadSnap(sn.id, sn.report_key)}
                    className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-stone-800 hover:bg-stone-700 text-stone-200 text-xs"
                    data-testid={`snap-dl-${sn.id}`}
                  >
                    <Download className="w-3 h-3" /> İndir
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="text-[11px] text-stone-600 border border-amber-500/30 bg-amber-500/5 rounded-lg p-3">
        <b>ℹ️ Email gönderimi şu anda MOCKED</b> — Resend / SendGrid entegrasyonu eklenene kadar raporlar
        DB'de saklanır ve buradan indirilebilir. Gerçek email için `delivery_status` alanı canlı çalışır.
      </div>
    </div>
  );
}

function AddSubscriptionForm({ catalog, defaultEmail, propertyId, onCancel, onCreated }) {
  const [reportKey, setReportKey] = useState(catalog.items[0]?.key || "");
  const [frequency, setFrequency] = useState("weekly");
  const [email, setEmail] = useState(defaultEmail);
  const [submitting, setSubmitting] = useState(false);

  const submit = async () => {
    if (!email) { toast.error("Email girin"); return; }
    setSubmitting(true);
    try {
      await axios.post(`${API}/reports/subscriptions`, {
        report_key:  reportKey,
        frequency,
        email,
        property_id: propertyId,
        filters:     { days: 30, margin_pct: 60 },
      });
      toast.success("Abonelik oluşturuldu");
      onCreated();
    } catch (e) { toast.error(e?.response?.data?.detail || "Ekleme başarısız"); }
    setSubmitting(false);
  };

  return (
    <div className="rounded-xl border border-emerald-500/40 bg-emerald-500/5 p-4 space-y-3" data-testid="add-sub-form">
      <h3 className="text-sm font-bold text-emerald-200">Yeni Abonelik</h3>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
        <select
          value={reportKey}
          onChange={(e) => setReportKey(e.target.value)}
          className="px-3 py-2 rounded-lg bg-stone-900 border border-stone-700 text-stone-100 text-sm"
          data-testid="add-sub-report"
        >
          {catalog.items.map((c) => (
            <option key={c.key} value={c.key}>{c.label}</option>
          ))}
        </select>
        <select
          value={frequency}
          onChange={(e) => setFrequency(e.target.value)}
          className="px-3 py-2 rounded-lg bg-stone-900 border border-stone-700 text-stone-100 text-sm"
          data-testid="add-sub-freq"
        >
          {catalog.frequencies.map((f) => (
            <option key={f} value={f}>{f}</option>
          ))}
        </select>
        <input
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="email@hotel.com"
          className="px-3 py-2 rounded-lg bg-stone-900 border border-stone-700 text-stone-100 text-sm"
          data-testid="add-sub-email"
        />
      </div>
      <div className="flex gap-2">
        <button
          onClick={submit}
          disabled={submitting}
          className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-sm font-bold"
          data-testid="add-sub-submit"
        >
          {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : "Oluştur"}
        </button>
        <button
          onClick={onCancel}
          className="px-3 py-2 rounded-lg bg-stone-800 hover:bg-stone-700 text-stone-200 text-sm"
        >
          İptal
        </button>
      </div>
    </div>
  );
}
