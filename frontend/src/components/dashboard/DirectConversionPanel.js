/**
 * DirectConversionPanel (iter 375) — Direct Booking Conversion Engine
 *
 * OTA misafirlerini checkout sonrası kuponla direct booking'e çevirme motoru.
 * Tabs: Funnel & İstatistik · Gönderilen Teklifler · Ayarlar
 */
import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Target, Mail, Ticket, RefreshCw, Settings, Save, Send, TrendingUp,
  CheckCircle2, Clock, XCircle, Percent,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function DirectConversionPanel() {
  const [tab, setTab] = useState("stats");
  return (
    <div className="p-6 max-w-[1400px] mx-auto" data-testid="direct-conversion-panel">
      <div className="mb-5">
        <div className="text-xs uppercase tracking-widest text-stone-500 mb-1 flex items-center gap-1.5">
          <Target className="w-3 h-3 text-emerald-500" /> Komisyon Tasarrufu
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">Direct Booking Conversion Engine</h1>
        <p className="text-sm text-stone-500 mt-1 max-w-2xl">
          OTA misafiri checkout olduğunda otomatik kupon e-postası gönder — bir sonraki
          konaklamayı direkt kanaldan alarak %15-18 OTA komisyonundan kurtulun.
        </p>
      </div>

      <div className="flex gap-2 mb-5 border-b border-stone-200">
        <TabBtn active={tab === "stats"} onClick={() => setTab("stats")} testId="dcv-tab-stats">
          <TrendingUp className="w-4 h-4 inline mr-1.5" /> Funnel & İstatistik
        </TabBtn>
        <TabBtn active={tab === "offers"} onClick={() => setTab("offers")} testId="dcv-tab-offers">
          <Ticket className="w-4 h-4 inline mr-1.5" /> Gönderilen Teklifler
        </TabBtn>
        <TabBtn active={tab === "settings"} onClick={() => setTab("settings")} testId="dcv-tab-settings">
          <Settings className="w-4 h-4 inline mr-1.5" /> Ayarlar
        </TabBtn>
        <TabBtn active={tab === "abandoned"} onClick={() => setTab("abandoned")} testId="dcv-tab-abandoned">
          <Clock className="w-4 h-4 inline mr-1.5" /> Terk Edilmiş Kurtarma
        </TabBtn>
      </div>

      {tab === "stats" && <StatsTab />}
      {tab === "offers" && <OffersTab />}
      {tab === "settings" && <SettingsTab />}
      {tab === "abandoned" && <AbandonedTab />}
    </div>
  );
}

const TabBtn = ({ active, onClick, children, testId }) => (
  <button onClick={onClick} data-testid={testId}
    className={`px-4 py-2.5 text-sm font-semibold transition -mb-px border-b-2 ${
      active ? "border-emerald-600 text-emerald-700" : "border-transparent text-stone-500 hover:text-stone-700"
    }`}>{children}</button>
);

const fmt = (n) => (typeof n === "number" ? n.toLocaleString("tr-TR", { maximumFractionDigits: 0 }) : "-");

/* ═══════════ STATS TAB ═══════════ */
const StatsTab = () => {
  const [data, setData] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [reminding, setReminding] = useState(false);
  const runReminders = async () => {
    setReminding(true);
    try {
      const r = await axios.post(`${API}/review-collection/coupon-reminders/all`);
      toast.success(`${r.data.candidates} aday · ${r.data.sent} gönderildi · ${r.data.mocked} MOCK`);
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Çalıştırılamadı"); }
    finally { setReminding(false); }
  };

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/direct-conversion/stats`);
      setData(r.data);
    } catch (e) {
      toast.error("Yüklenemedi: " + (e.response?.data?.detail || e.message));
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  const runScan = async () => {
    setScanning(true);
    try {
      const r = await axios.post(`${API}/direct-conversion/scan`);
      toast.success(`${r.data.scanned} booking tarandı, ${r.data.offers_created} yeni kupon gönderildi`);
      load();
    } catch (e) {
      toast.error("Tarama başarısız: " + (e.response?.data?.detail || e.message));
    }
    setScanning(false);
  };

  if (!data) return <div className="text-sm text-stone-400" data-testid="dcv-loading">Yükleniyor…</div>;

  return (
    <div data-testid="dcv-stats-tab">
      <div className="flex justify-end mb-4">
        <button onClick={runScan} disabled={scanning} data-testid="dcv-scan-btn"
          className="flex items-center gap-2 px-4 py-2 bg-emerald-700 text-white text-sm font-semibold rounded-lg hover:bg-emerald-800 disabled:opacity-50 transition-colors">
          <RefreshCw className={`w-4 h-4 ${scanning ? "animate-spin" : ""}`} />
          Checkout'ları Tara & Kupon Gönder
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <KPI icon={Send} label="Gönderilen Kupon" value={fmt(data.sent)} testId="dcv-kpi-sent" />
        <KPI icon={CheckCircle2} label="Redeem Edilen" value={fmt(data.redeemed)} accent="text-emerald-600" testId="dcv-kpi-redeemed" />
        <KPI icon={Percent} label="Dönüşüm Oranı" value={`%${data.conversion_rate_pct}`} accent="text-emerald-600" testId="dcv-kpi-rate" />
        <KPI icon={TrendingUp} label="Komisyon Tasarrufu" value={`£${fmt(data.commission_saved)}`} accent="text-emerald-700" testId="dcv-kpi-saved" />
      </div>

      {data.review_coupons && (
        <div className="bg-white border border-blue-200 rounded-xl p-4" data-testid="dcv-review-coupons">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
            <h3 className="text-sm font-semibold text-blue-900">🎁 Yorum Teşekkür Kuponları (THANKS-kodları)</h3>
            <span className="text-[11px] text-stone-500">Yorum bırakan misafire otomatik %10 · tek kullanım · 1 yıl</span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
            <div className="bg-stone-50 rounded-lg p-3"><div className="text-[11px] text-stone-500">Verilen</div><div className="text-xl font-bold" data-testid="dcv-rc-issued">{data.review_coupons.issued}</div></div>
            <div className="bg-stone-50 rounded-lg p-3"><div className="text-[11px] text-stone-500">Kullanılan</div><div className="text-xl font-bold text-emerald-700" data-testid="dcv-rc-used">{data.review_coupons.used}</div></div>
            <div className="bg-stone-50 rounded-lg p-3"><div className="text-[11px] text-stone-500">Kullanım oranı</div><div className="text-xl font-bold" data-testid="dcv-rc-pct">{data.review_coupons.usage_pct}%</div></div>
            <div className="bg-stone-50 rounded-lg p-3"><div className="text-[11px] text-stone-500">Süresi dolan</div><div className="text-xl font-bold text-stone-500">{data.review_coupons.expired}</div></div>
            <div className="bg-emerald-50 rounded-lg p-3 border border-emerald-200"><div className="text-[11px] text-stone-500">Getirdiği gelir</div><div className="text-xl font-bold text-emerald-700" data-testid="dcv-rc-revenue">£{fmt(data.review_coupons.revenue)}</div></div>
            <div className="bg-amber-50 rounded-lg p-3 border border-amber-200">
              <div className="text-[11px] text-stone-500">Hatırlatma (30 gün kala)</div>
              <div className="text-xl font-bold text-amber-800" data-testid="dcv-rc-reminded">{data.review_coupons.reminded ?? 0}</div>
              <div className="text-[10px] text-stone-500">gönderildi · {data.review_coupons.expiring_30d ?? 0} kupon 30 günde dolacak</div>
              <button onClick={runReminders} disabled={reminding} data-testid="dcv-rc-remind-btn"
                className="mt-1.5 text-[11px] px-2 py-1 rounded bg-amber-600 text-white hover:bg-amber-700 disabled:opacity-50">
                {reminding ? "Gönderiliyor…" : "Şimdi çalıştır"}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-4">
        <div className="bg-white border border-stone-200 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-stone-800 mb-3">Funnel</h3>
          <FunnelRow label="Gönderildi" value={data.sent} max={data.sent} color="bg-stone-400" />
          <FunnelRow label="Aktif (bekliyor)" value={data.active} max={data.sent} color="bg-amber-400" />
          <FunnelRow label="Redeem edildi" value={data.redeemed} max={data.sent} color="bg-emerald-500" />
          <FunnelRow label="Süresi doldu" value={data.expired} max={data.sent} color="bg-stone-300" />
          <div className="mt-4 pt-3 border-t border-stone-100 text-xs text-stone-500 flex justify-between">
            <span>Potansiyel tasarruf (aktif kuponlar)</span>
            <span className="font-semibold text-stone-700">£{fmt(data.potential_saving)}</span>
          </div>
          <div className="mt-1 text-xs text-stone-500 flex justify-between">
            <span>Direct kanala çevrilen ciro</span>
            <span className="font-semibold text-emerald-700">£{fmt(data.direct_revenue)}</span>
          </div>
        </div>

        <div className="bg-white border border-stone-200 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-stone-800 mb-3">Kanal Bazında</h3>
          {(data.by_channel || []).length === 0 && (
            <p className="text-sm text-stone-400">Henüz kupon gönderilmedi. "Checkout'ları Tara" ile başlayın.</p>
          )}
          {(data.by_channel || []).map((c) => (
            <div key={c.channel} className="flex items-center justify-between py-2 border-b border-stone-100 last:border-0 text-sm">
              <span className="font-medium text-stone-700 capitalize">{c.channel.replace("_", ".")}</span>
              <span className="text-stone-500">{c.sent} gönderildi · <span className="text-emerald-600 font-semibold">{c.redeemed} dönüşüm</span></span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

const KPI = ({ icon: Icon, label, value, accent = "text-stone-900", testId }) => (
  <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid={testId}>
    <div className="flex items-center gap-1.5 text-xs text-stone-500 mb-1.5">
      <Icon className="w-3.5 h-3.5" /> {label}
    </div>
    <div className={`text-2xl font-semibold ${accent}`}>{value}</div>
  </div>
);

const FunnelRow = ({ label, value, max, color }) => (
  <div className="mb-2.5">
    <div className="flex justify-between text-xs text-stone-600 mb-1">
      <span>{label}</span><span className="font-semibold">{fmt(value)}</span>
    </div>
    <div className="h-2 bg-stone-100 rounded-full overflow-hidden">
      <div className={`h-full ${color} rounded-full transition-all`}
        style={{ width: max ? `${Math.max(2, (value / max) * 100)}%` : "0%" }} />
    </div>
  </div>
);

/* ═══════════ OFFERS TAB ═══════════ */
const STATUS_BADGE = {
  sent:     { label: "Aktif", cls: "bg-amber-50 text-amber-700 border-amber-200", Icon: Clock },
  redeemed: { label: "Redeem", cls: "bg-emerald-50 text-emerald-700 border-emerald-200", Icon: CheckCircle2 },
  expired:  { label: "Süresi doldu", cls: "bg-stone-100 text-stone-500 border-stone-200", Icon: XCircle },
};

const OffersTab = () => {
  const [items, setItems] = useState(null);

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/direct-conversion/offers`);
      setItems(r.data.items || []);
    } catch (e) {
      toast.error("Yüklenemedi: " + (e.response?.data?.detail || e.message));
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  if (!items) return <div className="text-sm text-stone-400">Yükleniyor…</div>;
  if (items.length === 0) return (
    <div className="text-center py-16 text-stone-400 text-sm" data-testid="dcv-offers-empty">
      <Mail className="w-8 h-8 mx-auto mb-2 opacity-40" />
      Henüz gönderilmiş kupon yok. Funnel sekmesinden "Checkout'ları Tara" çalıştırın.
    </div>
  );

  return (
    <div className="bg-white border border-stone-200 rounded-xl overflow-hidden" data-testid="dcv-offers-table">
      <table className="w-full text-sm">
        <thead className="bg-stone-50 text-xs uppercase tracking-wide text-stone-500">
          <tr>
            <th className="text-left px-4 py-3">Misafir</th>
            <th className="text-left px-4 py-3">Kanal</th>
            <th className="text-left px-4 py-3">Kupon</th>
            <th className="text-right px-4 py-3">İndirim</th>
            <th className="text-right px-4 py-3">Tahmini Tasarruf</th>
            <th className="text-left px-4 py-3">Geçerlilik</th>
            <th className="text-left px-4 py-3">Durum</th>
            <th className="text-left px-4 py-3">E-posta</th>
          </tr>
        </thead>
        <tbody>
          {items.map((o) => {
            const badge = STATUS_BADGE[o.status] || STATUS_BADGE.sent;
            return (
              <tr key={o.id} className="border-t border-stone-100 hover:bg-stone-50/60">
                <td className="px-4 py-3">
                  <div className="font-medium text-stone-800">{o.guest_name}</div>
                  <div className="text-xs text-stone-400">{o.guest_email}</div>
                </td>
                <td className="px-4 py-3 capitalize text-stone-600">{(o.channel || "").replace("_", ".")}</td>
                <td className="px-4 py-3 font-mono text-xs font-semibold text-emerald-700">{o.coupon_code}</td>
                <td className="px-4 py-3 text-right font-semibold">%{o.discount_pct}</td>
                <td className="px-4 py-3 text-right text-stone-600">£{fmt(o.commission_saved_estimate)}</td>
                <td className="px-4 py-3 text-xs text-stone-500">{(o.valid_until || "").slice(0, 10)}</td>
                <td className="px-4 py-3">
                  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${badge.cls}`}>
                    <badge.Icon className="w-3 h-3" /> {badge.label}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs text-stone-500">{o.email_status}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

/* ═══════════ SETTINGS TAB ═══════════ */
const SettingsTab = () => {
  const [s, setS] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    axios.get(`${API}/direct-conversion/settings`)
      .then((r) => setS(r.data))
      .catch((e) => toast.error("Ayarlar yüklenemedi: " + (e.response?.data?.detail || e.message)));
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      const r = await axios.put(`${API}/direct-conversion/settings`, {
        enabled: s.enabled,
        discount_pct: Number(s.discount_pct),
        validity_days: Number(s.validity_days),
        min_booking_value: Number(s.min_booking_value || 0),
      });
      setS(r.data);
      toast.success("Ayarlar kaydedildi");
    } catch (e) {
      toast.error("Kaydedilemedi: " + (e.response?.data?.detail || e.message));
    }
    setSaving(false);
  };

  if (!s) return <div className="text-sm text-stone-400">Yükleniyor…</div>;

  return (
    <div className="max-w-lg bg-white border border-stone-200 rounded-xl p-6" data-testid="dcv-settings-form">
      <label className="flex items-center justify-between mb-5 cursor-pointer">
        <div>
          <div className="text-sm font-semibold text-stone-800">Engine Aktif</div>
          <div className="text-xs text-stone-500">Checkout'ta otomatik kupon e-postası gönder</div>
        </div>
        <input type="checkbox" checked={!!s.enabled} data-testid="dcv-enabled-toggle"
          onChange={(e) => setS({ ...s, enabled: e.target.checked })}
          className="w-5 h-5 accent-emerald-600" />
      </label>

      <Field label="İndirim Oranı (%)" hint="1-50 arası">
        <input type="number" min={1} max={50} value={s.discount_pct} data-testid="dcv-discount-input"
          onChange={(e) => setS({ ...s, discount_pct: e.target.value })}
          className="w-full border border-stone-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500" />
      </Field>
      <Field label="Kupon Geçerlilik Süresi (gün)" hint="7-365 arası">
        <input type="number" min={7} max={365} value={s.validity_days} data-testid="dcv-validity-input"
          onChange={(e) => setS({ ...s, validity_days: e.target.value })}
          className="w-full border border-stone-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500" />
      </Field>
      <Field label="Minimum Booking Değeri (£)" hint="Bu tutarın altındaki konaklamalara kupon gönderilmez">
        <input type="number" min={0} value={s.min_booking_value} data-testid="dcv-minvalue-input"
          onChange={(e) => setS({ ...s, min_booking_value: e.target.value })}
          className="w-full border border-stone-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500" />
      </Field>

      <button onClick={save} disabled={saving} data-testid="dcv-save-settings-btn"
        className="mt-2 flex items-center gap-2 px-4 py-2 bg-emerald-700 text-white text-sm font-semibold rounded-lg hover:bg-emerald-800 disabled:opacity-50 transition-colors">
        <Save className="w-4 h-4" /> Kaydet
      </button>
    </div>
  );
};

const Field = ({ label, hint, children }) => (
  <div className="mb-4">
    <label className="block text-sm font-medium text-stone-700 mb-1">{label}</label>
    {children}
    {hint && <p className="text-xs text-stone-400 mt-1">{hint}</p>}
  </div>
);

/* ═══════════ ABANDONED RECOVERY TAB (iter 393) ═══════════ */
const AbandonedTab = () => {
  const [data, setData] = useState(null);
  const [running, setRunning] = useState(false);

  const load = useCallback(() => {
    axios.get(`${API}/booking-widget/abandoned/stats/all?days=30`)
      .then((r) => setData(r.data)).catch(() => toast.error("İstatistik yüklenemedi"));
  }, []);
  useEffect(() => { load(); }, [load]);

  const runNow = async () => {
    setRunning(true);
    try {
      const { data: r } = await axios.post(`${API}/booking-widget/abandoned/run-recovery`, {});
      toast.success(`${r.emails_sent} kurtarma e-postası gönderildi (${r.eligible} uygun sepet)`);
      load();
    } catch (e) {
      toast.error("Kurtarma çalıştırılamadı");
    } finally { setRunning(false); }
  };

  if (!data) return <div className="p-8 text-stone-400 text-sm" data-testid="dcv-abandoned-loading">Yükleniyor…</div>;

  return (
    <div className="space-y-5" data-testid="dcv-abandoned-tab">
      <div className="flex items-start justify-between gap-4">
        <p className="text-sm text-stone-500 max-w-xl">
          Widget'ta e-postasını girip rezervasyonu tamamlamayan misafirlere 1 saat sonra
          %5 kuponlu hatırlatma e-postası gider. Saatlik otomatik tarama aktiftir (Scheduler → abandoned_recovery).
        </p>
        <button onClick={runNow} disabled={running} data-testid="dcv-run-recovery-btn"
          className="flex items-center gap-2 px-4 py-2 bg-emerald-700 text-white text-sm font-semibold rounded-lg hover:bg-emerald-800 disabled:opacity-50 transition-colors shrink-0">
          <Send className="w-4 h-4" /> {running ? "Çalışıyor…" : "Şimdi Tara & Gönder"}
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[["Yakalanan (30g)", data.total_captured], ["E-posta Gönderilen", data.emailed],
          ["Kurtarılan", data.recovered], ["Kurtarma Oranı", `${data.recovery_rate}%`]].map(([l, v]) => (
          <div key={l} className="bg-white border border-stone-200 rounded-xl p-4">
            <div className="text-2xl font-semibold text-stone-900">{v}</div>
            <div className="text-xs text-stone-500 mt-1">{l}</div>
          </div>
        ))}
      </div>

      <div className="bg-white border border-stone-200 rounded-xl overflow-x-auto">
        <table className="w-full text-xs" data-testid="dcv-abandoned-table">
          <thead>
            <tr className="border-b border-stone-200 text-left text-[10px] uppercase tracking-wide text-stone-500">
              <th className="px-3 py-2.5">Misafir</th><th className="px-3 py-2.5">Tarihler</th>
              <th className="px-3 py-2.5">Tutar</th><th className="px-3 py-2.5">Kupon</th>
              <th className="px-3 py-2.5">Durum</th>
            </tr>
          </thead>
          <tbody>
            {(data.recent || []).map((c) => (
              <tr key={c.session_id} className="border-b border-stone-100">
                <td className="px-3 py-2 text-stone-800">{c.guest_email}</td>
                <td className="px-3 py-2 text-stone-600">{c.check_in} → {c.check_out}</td>
                <td className="px-3 py-2 text-stone-600">{c.rate ? `£${fmt(c.rate)}` : "—"}</td>
                <td className="px-3 py-2 font-mono text-[11px] text-cyan-700">{c.coupon_code || "—"}</td>
                <td className="px-3 py-2">
                  {c.recovered ? <span className="text-emerald-600 font-medium">kurtarıldı ✓</span>
                    : c.status === "converted" ? <span className="text-emerald-600">tamamlandı</span>
                    : c.email_sent ? <span className="text-amber-600">e-posta gönderildi</span>
                    : <span className="text-stone-400">bekliyor</span>}
                </td>
              </tr>
            ))}
            {(data.recent || []).length === 0 && (
              <tr><td colSpan={5} className="px-3 py-6 text-center text-stone-400">Henüz terk edilmiş sepet yok</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
