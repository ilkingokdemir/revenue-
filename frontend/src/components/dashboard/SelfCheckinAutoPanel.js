import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ToggleRight,
  Envelope,
  ChatCircle,
  Lightning,
  ArrowsClockwise,
  Play,
  CheckCircle,
  Clock,
  WarningCircle,
  GearSix,
  ListBullets,
} from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

const STATUS_PILL = {
  sent: "bg-emerald-100 text-emerald-700 border-emerald-200",
  queued: "bg-amber-100 text-amber-700 border-amber-200",
  failed: "bg-red-100 text-red-700 border-red-200",
  skipped: "bg-stone-100 text-stone-600 border-stone-200",
};

export default function SelfCheckinAutoPanel({ propertyId = "default" }) {
  const [tab, setTab] = useState("settings");
  const [settings, setSettings] = useState(null);
  const [stats, setStats] = useState(null);
  const [logs, setLogs] = useState([]);
  const [busy, setBusy] = useState(false);
  const [running, setRunning] = useState(false);

  const reload = useCallback(async () => {
    try {
      const [s, st, lg] = await Promise.all([
        axios.get(`${API}/api/self-checkin-auto/settings/${propertyId}`, { withCredentials: true }),
        axios.get(`${API}/api/self-checkin-auto/stats/${propertyId}`, { withCredentials: true }),
        axios.get(`${API}/api/self-checkin-auto/log/${propertyId}?limit=100`, { withCredentials: true }),
      ]);
      setSettings(s.data);
      setStats(st.data);
      setLogs(lg.data.items || []);
    } catch (e) {
      toast.error("Ayarlar yüklenemedi");
    }
  }, [propertyId]);

  useEffect(() => {
    reload();
  }, [reload]);

  const save = async () => {
    if (!settings) return;
    setBusy(true);
    try {
      const r = await axios.put(
        `${API}/api/self-checkin-auto/settings/${propertyId}`,
        settings,
        { withCredentials: true }
      );
      setSettings(r.data);
      toast.success("Ayarlar kaydedildi");
    } catch (e) {
      toast.error("Kaydedilemedi");
    } finally {
      setBusy(false);
    }
  };

  const runOnce = async () => {
    setRunning(true);
    try {
      const r = await axios.post(
        `${API}/api/self-checkin-auto/run-once/${propertyId}`,
        {},
        { withCredentials: true }
      );
      const d = r.data;
      if (d.skipped) {
        toast.info("Otomasyon devre dışı.");
      } else {
        toast.success(
          `İşlendi: ${d.processed} · E-posta gönderildi: ${d.email.sent}, kuyrukta: ${d.email.queued} · SMS gönderildi: ${d.sms.sent}, kuyrukta: ${d.sms.queued}`
        );
      }
      reload();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Tetikleme başarısız");
    } finally {
      setRunning(false);
    }
  };

  if (!settings) {
    return <div className="p-6 text-stone-400">Yükleniyor…</div>;
  }

  const upd = (k, v) => setSettings((s) => ({ ...s, [k]: v }));

  return (
    <div className="p-5 max-w-[1300px] mx-auto" data-testid="sca-panel">
      <div className="mb-5 flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
            <Lightning size={12} weight="fill" className="text-amber-500" />
            <span>Reservations · Self check-in automation</span>
          </div>
          <h1 className="text-2xl font-semibold text-stone-900">
            Otomatik varış öncesi self check-in
          </h1>
          <p className="text-sm text-stone-500 mt-1 max-w-2xl">
            Yaklaşan rezervasyonlara token + e-posta + SMS otomatik gönder. Resend / Twilio anahtarı yoksa
            mesajlar <span className="font-mono">queued</span> olarak işaretlenir; anahtar girer girmez gönderilir.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={runOnce}
            disabled={running}
            className="px-3 py-2 bg-stone-900 text-white rounded-md text-sm font-medium hover:bg-black disabled:opacity-50 flex items-center gap-2"
            data-testid="sca-run-once"
          >
            <Play size={14} weight="fill" />
            {running ? "Çalışıyor…" : "Şimdi tetikle"}
          </button>
          <button
            onClick={reload}
            className="px-3 py-2 bg-stone-100 text-stone-700 rounded-md text-sm hover:bg-stone-200 flex items-center gap-2"
            data-testid="sca-refresh"
          >
            <ArrowsClockwise size={14} /> Yenile
          </button>
        </div>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
        <Kpi label="E-posta gönderildi" value={stats?.email?.sent ?? 0} icon={Envelope} tone="ok" />
        <Kpi label="E-posta kuyrukta" value={stats?.email?.queued ?? 0} icon={Envelope} tone="warn" />
        <Kpi label="SMS gönderildi" value={stats?.sms?.sent ?? 0} icon={ChatCircle} tone="ok" />
        <Kpi label="SMS kuyrukta" value={stats?.sms?.queued ?? 0} icon={ChatCircle} tone="warn" />
      </div>

      {/* Tabs */}
      <div className="flex border-b border-stone-200 mb-4">
        {[
          ["settings", "Ayarlar", GearSix],
          ["templates", "Şablonlar", Envelope],
          ["log", "Hareket günlüğü", ListBullets],
        ].map(([k, l, Icon]) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            className={`px-4 py-2 text-sm border-b-2 flex items-center gap-1.5 ${
              tab === k
                ? "border-indigo-600 text-indigo-700 font-medium"
                : "border-transparent text-stone-500 hover:text-stone-800"
            }`}
            data-testid={`sca-tab-${k}`}
          >
            <Icon size={14} />
            {l}
          </button>
        ))}
      </div>

      {tab === "settings" && (
        <SettingsTab settings={settings} upd={upd} save={save} busy={busy} />
      )}
      {tab === "templates" && (
        <TemplatesTab settings={settings} upd={upd} save={save} busy={busy} />
      )}
      {tab === "log" && <LogTab logs={logs} />}
    </div>
  );
}

const Kpi = ({ label, value, icon: Icon, tone }) => (
  <div
    className={`bg-white border rounded-lg p-3 ${
      tone === "ok" ? "border-emerald-200" : tone === "warn" ? "border-amber-200" : "border-stone-200"
    }`}
  >
    <div className="flex items-center justify-between text-stone-500 mb-1">
      <span className="text-[10px] uppercase tracking-wide">{label}</span>
      {Icon && <Icon size={14} />}
    </div>
    <div className="text-lg font-semibold text-stone-900">{value}</div>
  </div>
);

const Toggle = ({ on, onChange, label, sub, testId }) => (
  <label
    className="flex items-start gap-3 p-3 border border-stone-200 rounded-md hover:bg-stone-50 cursor-pointer"
    data-testid={testId}
  >
    <input
      type="checkbox"
      checked={!!on}
      onChange={(e) => onChange(e.target.checked)}
      className="mt-1"
    />
    <div className="flex-1">
      <div className="text-sm font-medium text-stone-800">{label}</div>
      {sub && <div className="text-xs text-stone-500 mt-0.5">{sub}</div>}
    </div>
  </label>
);

const NumField = ({ label, value, onChange, suffix, testId }) => (
  <label className="block">
    <div className="text-xs text-stone-500 mb-1">{label}</div>
    <div className="flex items-center gap-2">
      <input
        type="number"
        value={value ?? ""}
        onChange={(e) => onChange(Number(e.target.value))}
        className="text-sm border border-stone-200 rounded px-3 py-1.5 w-24"
        data-testid={testId}
      />
      {suffix && <span className="text-xs text-stone-500">{suffix}</span>}
    </div>
  </label>
);

const SettingsTab = ({ settings, upd, save, busy }) => (
  <div className="bg-white border border-stone-200 rounded-lg p-5 space-y-4">
    <Toggle
      on={settings.enabled}
      onChange={(v) => upd("enabled", v)}
      label="Otomasyon açık"
      sub="Arka plan döngüsü her 5 dakikada bir yaklaşan rezervasyonları tarar."
      testId="sca-enabled"
    />
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      <Toggle
        on={settings.email_enabled}
        onChange={(v) => upd("email_enabled", v)}
        label="E-posta tetikleyici"
        sub="Resend üzerinden self-checkin-v2 linki gönderir."
        testId="sca-email-enabled"
      />
      <Toggle
        on={settings.sms_enabled}
        onChange={(v) => upd("sms_enabled", v)}
        label="SMS tetikleyici"
        sub="Twilio üzerinden kısa hatırlatma mesajı gönderir."
        testId="sca-sms-enabled"
      />
    </div>
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
      <NumField
        label="E-posta penceresi"
        value={settings.email_window_h}
        onChange={(v) => upd("email_window_h", v)}
        suffix="saat önce"
        testId="sca-email-window"
      />
      <NumField
        label="SMS penceresi"
        value={settings.sms_window_h}
        onChange={(v) => upd("sms_window_h", v)}
        suffix="saat önce"
        testId="sca-sms-window"
      />
      <NumField
        label="Token geçerlilik"
        value={settings.expiry_hours}
        onChange={(v) => upd("expiry_hours", v)}
        suffix="saat"
        testId="sca-expiry"
      />
    </div>
    <div>
      <label className="block">
        <div className="text-xs text-stone-500 mb-1">Mesaj dili</div>
        <select
          value={settings.language || "tr"}
          onChange={(e) => upd("language", e.target.value)}
          className="text-sm border border-stone-200 rounded px-3 py-1.5"
          data-testid="sca-language"
        >
          <option value="tr">Türkçe</option>
          <option value="en">English</option>
        </select>
      </label>
    </div>
    <div className="pt-3 border-t border-stone-100 flex justify-end">
      <button
        onClick={save}
        disabled={busy}
        className="px-4 py-2 bg-indigo-600 text-white rounded text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
        data-testid="sca-save"
      >
        {busy ? "Kaydediliyor…" : "Ayarları kaydet"}
      </button>
    </div>
  </div>
);

const TemplatesTab = ({ settings, upd, save, busy }) => {
  const TArea = ({ label, value, onChange, rows = 5, testId }) => (
    <label className="block">
      <div className="text-xs text-stone-500 mb-1">{label}</div>
      <textarea
        value={value || ""}
        onChange={(e) => onChange(e.target.value)}
        rows={rows}
        className="w-full text-sm border border-stone-200 rounded px-3 py-2 font-mono"
        data-testid={testId}
      />
    </label>
  );
  return (
    <div className="bg-white border border-stone-200 rounded-lg p-5 space-y-4">
      <p className="text-xs text-stone-500">
        Şablon değişkenleri: <code className="bg-stone-100 px-1 rounded">{"{guest_name}"}</code>{" "}
        <code className="bg-stone-100 px-1 rounded">{"{hotel_name}"}</code>{" "}
        <code className="bg-stone-100 px-1 rounded">{"{check_in}"}</code>{" "}
        <code className="bg-stone-100 px-1 rounded">{"{link}"}</code>{" "}
        <code className="bg-stone-100 px-1 rounded">{"{expiry}"}</code>
      </p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-stone-700">E-posta — Türkçe</h3>
          <TArea
            label="Konu (TR)"
            value={settings.subject_template_tr}
            onChange={(v) => upd("subject_template_tr", v)}
            rows={2}
            testId="sca-subject-tr"
          />
          <TArea
            label="Gövde (TR)"
            value={settings.body_template_tr}
            onChange={(v) => upd("body_template_tr", v)}
            rows={6}
            testId="sca-body-tr"
          />
          <TArea
            label="SMS (TR)"
            value={settings.sms_template_tr}
            onChange={(v) => upd("sms_template_tr", v)}
            rows={2}
            testId="sca-sms-tr"
          />
        </div>
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-stone-700">E-posta — English</h3>
          <TArea
            label="Subject (EN)"
            value={settings.subject_template_en}
            onChange={(v) => upd("subject_template_en", v)}
            rows={2}
            testId="sca-subject-en"
          />
          <TArea
            label="Body (EN)"
            value={settings.body_template_en}
            onChange={(v) => upd("body_template_en", v)}
            rows={6}
            testId="sca-body-en"
          />
          <TArea
            label="SMS (EN)"
            value={settings.sms_template_en}
            onChange={(v) => upd("sms_template_en", v)}
            rows={2}
            testId="sca-sms-en"
          />
        </div>
      </div>
      <div className="pt-3 border-t border-stone-100 flex justify-end">
        <button
          onClick={save}
          disabled={busy}
          className="px-4 py-2 bg-indigo-600 text-white rounded text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
          data-testid="sca-save-templates"
        >
          {busy ? "Kaydediliyor…" : "Şablonları kaydet"}
        </button>
      </div>
    </div>
  );
};

const LogTab = ({ logs }) => (
  <div className="bg-white border border-stone-200 rounded-lg p-3" data-testid="sca-log">
    {logs.length === 0 && (
      <p className="text-xs text-stone-400 italic p-4">Henüz tetikleme yapılmadı.</p>
    )}
    {logs.length > 0 && (
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-stone-500 border-b border-stone-200">
            <th className="py-2 pr-2">Zaman</th>
            <th className="py-2 pr-2">Misafir</th>
            <th className="py-2 pr-2">Saat</th>
            <th className="py-2 pr-2">E-posta</th>
            <th className="py-2 pr-2">SMS</th>
          </tr>
        </thead>
        <tbody>
          {logs.map((l) => (
            <tr key={l.id} className="border-b border-stone-100">
              <td className="py-1.5 pr-2 font-mono text-[11px] text-stone-500">
                {(l.created_at || "").replace("T", " ").slice(0, 16)}
              </td>
              <td className="py-1.5 pr-2">{l.guest_name || "—"}</td>
              <td className="py-1.5 pr-2">{l.hours_until ? `T-${l.hours_until}h` : "—"}</td>
              <td className="py-1.5 pr-2">
                <Pill status={l.email_status} />
              </td>
              <td className="py-1.5 pr-2">
                <Pill status={l.sms_status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    )}
  </div>
);

const Pill = ({ status }) => {
  if (!status) return <span className="text-stone-300">—</span>;
  const cls = STATUS_PILL[status] || "bg-stone-100 text-stone-600 border-stone-200";
  const Icon =
    status === "sent" ? CheckCircle : status === "queued" ? Clock : status === "failed" ? WarningCircle : ToggleRight;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium border ${cls}`}>
      <Icon size={10} weight="fill" /> {status}
    </span>
  );
};
