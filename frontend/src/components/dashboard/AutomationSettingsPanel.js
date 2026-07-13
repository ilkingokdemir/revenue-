import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  GearSix, ArrowsClockwise, CaretDown, CaretUp, Play, Lightning,
  CheckCircle, WarningCircle, Clock, Coins, Megaphone, Heart, ShieldWarning, ChartBar, Target,
} from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

const CAT_ICON = {
  revenue: Coins, marketing: Megaphone, guest: Heart, risk: ShieldWarning, reporting: ChartBar, distribution: Lightning,
};
const CAT_COLOR = {
  revenue: "text-emerald-600 bg-emerald-50 border-emerald-200",
  marketing: "text-sky-600 bg-sky-50 border-sky-200",
  guest: "text-rose-600 bg-rose-50 border-rose-200",
  risk: "text-amber-600 bg-amber-50 border-amber-200",
  reporting: "text-violet-600 bg-violet-50 border-violet-200",
  distribution: "text-cyan-600 bg-cyan-50 border-cyan-200",
};

const fmtTime = (iso) => {
  if (!iso) return "Henüz çalışmadı";
  try {
    return new Date(iso).toLocaleString("tr-TR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
  } catch { return iso; }
};
const pad = (n) => String(n).padStart(2, "0");
const DOW = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"];

function Toggle({ on, busy, onChange, testId }) {
  return (
    <button onClick={onChange} disabled={busy} data-testid={testId}
      className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors ${on ? "bg-emerald-500" : "bg-stone-300"} ${busy ? "opacity-50" : ""}`}>
      <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${on ? "translate-x-6" : "translate-x-1"}`} />
    </button>
  );
}

const SIMULATABLE = new Set(["cancel_save", "upsell_autopilot", "deposit_autopilot", "email_nudge", "review_autopilot"]);

function MotorCard({ job, onToggle, onSave, onTrigger, busyKey }) {
  const [open, setOpen] = useState(false);
  const [hour, setHour] = useState(job.cron_hour);
  const [minute, setMinute] = useState(job.cron_minute);
  const [dow, setDow] = useState(job.cron_dow === null || job.cron_dow === undefined ? "" : String(job.cron_dow));
  const [vals, setVals] = useState(() => Object.fromEntries((job.params || []).map((p) => [p.key, p.value])));
  const [sim, setSim] = useState(null);
  const [simBusy, setSimBusy] = useState(false);

  const busy = busyKey === job.job;
  const hasErr = !!job.last_run_error;
  const Icon = CAT_ICON[job.category] || Lightning;

  const save = () => onSave(job.job, {
    cron_hour: Number(hour), cron_minute: Number(minute),
    cron_dow: dow === "" ? null : Number(dow),
    params: vals,
  });

  const simulate = async () => {
    setSimBusy(true);
    try {
      const r = await axios.post(`${API}/api/automation/simulate/${job.job}`, { params: vals });
      setSim(r.data);
    } catch { toast.error("Simülasyon başarısız"); }
    finally { setSimBusy(false); }
  };

  return (
    <div data-testid={`motor-card-${job.job}`}
      className={`bg-white border rounded-xl transition-shadow hover:shadow-sm ${job.enabled ? "border-stone-200" : "border-stone-200 opacity-70"}`}>
      <div className="p-4 flex items-start gap-3">
        <div className={`h-9 w-9 rounded-lg border flex items-center justify-center shrink-0 ${CAT_COLOR[job.category]}`}>
          <Icon size={18} weight="fill" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold text-sm text-stone-900" data-testid={`motor-label-${job.job}`}>{job.label}</span>
            {job.enabled ? (
              hasErr ? (
                <span className="inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded bg-rose-100 text-rose-700"><WarningCircle size={11} weight="fill" /> HATA</span>
              ) : (
                <span className="inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700"><CheckCircle size={11} weight="fill" /> AKTİF</span>
              )
            ) : (
              <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-stone-100 text-stone-500">KAPALI</span>
            )}
          </div>
          <p className="text-xs text-stone-500 mt-0.5 leading-relaxed">{job.description}</p>
          <div className="flex items-center gap-3 mt-2 text-[11px] text-stone-400">
            <span className="inline-flex items-center gap-1"><Clock size={12} /> Zamanlama: {pad(job.cron_hour)}:{pad(job.cron_minute)}{job.cron_dow !== null && job.cron_dow !== undefined ? ` · ${DOW[job.cron_dow]}` : " · her gün"}</span>
            <span>Son çalışma: {fmtTime(job.last_run_at)}</span>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Toggle on={job.enabled} busy={busy} testId={`motor-toggle-${job.job}`}
            onChange={() => onToggle(job.job, !job.enabled)} />
          <button onClick={() => setOpen(!open)} data-testid={`motor-expand-${job.job}`}
            className="h-7 w-7 flex items-center justify-center rounded-lg border border-stone-200 text-stone-500 hover:bg-stone-50">
            {open ? <CaretUp size={13} /> : <CaretDown size={13} />}
          </button>
        </div>
      </div>

      {open && (
        <div className="border-t border-stone-100 px-4 py-4 space-y-4 bg-stone-50/50 rounded-b-xl" data-testid={`motor-settings-${job.job}`}>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <div>
              <label className="text-[11px] font-medium text-stone-500 block mb-1">Saat (UTC)</label>
              <input type="number" min="0" max="23" value={hour} onChange={(e) => setHour(e.target.value)}
                data-testid={`motor-hour-${job.job}`}
                className="w-full text-sm border border-stone-200 rounded-lg px-2.5 py-1.5 bg-white" />
            </div>
            <div>
              <label className="text-[11px] font-medium text-stone-500 block mb-1">Dakika</label>
              <input type="number" min="0" max="59" value={minute} onChange={(e) => setMinute(e.target.value)}
                data-testid={`motor-minute-${job.job}`}
                className="w-full text-sm border border-stone-200 rounded-lg px-2.5 py-1.5 bg-white" />
            </div>
            <div>
              <label className="text-[11px] font-medium text-stone-500 block mb-1">Gün</label>
              <select value={dow} onChange={(e) => setDow(e.target.value)} data-testid={`motor-dow-${job.job}`}
                className="w-full text-sm border border-stone-200 rounded-lg px-2.5 py-1.5 bg-white">
                <option value="">Her gün</option>
                {DOW.map((d, i) => <option key={i} value={i}>{d}</option>)}
              </select>
            </div>
          </div>

          {(job.params || []).length > 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {job.params.map((p) => (
                <div key={p.key}>
                  <label className="text-[11px] font-medium text-stone-500 block mb-1">
                    {p.label} <span className="text-stone-400">({p.min}–{p.max} {p.suffix})</span>
                  </label>
                  <input type="number" min={p.min} max={p.max} value={vals[p.key]}
                    onChange={(e) => setVals((v) => ({ ...v, [p.key]: e.target.value }))}
                    data-testid={`motor-param-${job.job}-${p.key}`}
                    className="w-full text-sm border border-stone-200 rounded-lg px-2.5 py-1.5 bg-white" />
                </div>
              ))}
            </div>
          )}

          {job.last_run_result && (
            <div className="text-[11px] text-stone-500 bg-white border border-stone-200 rounded-lg px-3 py-2 font-mono overflow-x-auto">
              Son sonuç: {JSON.stringify(job.last_run_result)}
            </div>
          )}
          {job.last_run_error && (
            <div className="text-[11px] text-rose-600 bg-rose-50 border border-rose-200 rounded-lg px-3 py-2">
              Son hata: {job.last_run_error}
            </div>
          )}

          {sim && (
            <div className="bg-cyan-50 border border-cyan-200 rounded-lg px-3 py-2.5 space-y-2" data-testid={`motor-sim-result-${job.job}`}>
              <div className="flex items-center gap-1.5 text-xs font-medium text-cyan-800">
                <Target size={13} weight="fill" />
                <span>Etki simülasyonu: {sim.targets}/{sim.scanned} hedeflenir</span>
                {sim.value_estimate > 0 && <span className="text-cyan-600">· ~£{Number(sim.value_estimate).toLocaleString("en-GB", { maximumFractionDigits: 0 })}</span>}
              </div>
              <p className="text-[11px] text-cyan-700 leading-relaxed">{sim.detail}</p>
              {sim.histogram && (
                <div className="flex items-end gap-1.5 pt-1">
                  {sim.histogram.map((h) => {
                    const max = Math.max(...sim.histogram.map((x) => x.count), 1);
                    return (
                      <div key={h.bucket} className="flex-1 text-center">
                        <div className="h-10 flex items-end justify-center">
                          <div className="w-full max-w-[36px] bg-cyan-400/70 rounded-t" style={{ height: `${(h.count / max) * 100}%`, minHeight: h.count > 0 ? 3 : 0 }} />
                        </div>
                        <div className="text-[9px] text-cyan-600 mt-0.5">{h.bucket}</div>
                        <div className="text-[10px] font-medium text-cyan-800">{h.count}</div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <button onClick={() => onTrigger(job.job)} disabled={busy} data-testid={`motor-trigger-${job.job}`}
                className="inline-flex items-center gap-1.5 text-xs font-medium text-stone-600 border border-stone-200 rounded-lg px-3 py-1.5 bg-white hover:border-stone-300 disabled:opacity-50">
                <Play size={13} weight="fill" /> Şimdi çalıştır
              </button>
              {SIMULATABLE.has(job.job) && (
                <button onClick={simulate} disabled={simBusy} data-testid={`motor-simulate-${job.job}`}
                  className="inline-flex items-center gap-1.5 text-xs font-medium text-cyan-700 border border-cyan-200 rounded-lg px-3 py-1.5 bg-cyan-50 hover:border-cyan-300 disabled:opacity-50">
                  <Target size={13} weight="fill" /> {simBusy ? "Hesaplanıyor…" : "Etkiyi simüle et"}
                </button>
              )}
            </div>
            <button onClick={save} disabled={busy} data-testid={`motor-save-${job.job}`}
              className="inline-flex items-center gap-1.5 text-xs font-medium text-white bg-stone-900 rounded-lg px-4 py-1.5 hover:bg-stone-800 disabled:opacity-50">
              Ayarları kaydet
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function AutomationSettingsPanel() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busyKey, setBusyKey] = useState("");

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/api/automation/settings`);
      setData(r.data);
    } catch { toast.error("Otomasyon ayarları yüklenemedi"); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const onToggle = async (job, enabled) => {
    setBusyKey(job);
    try {
      await axios.put(`${API}/api/automation/settings/${job}`, { enabled });
      toast.success(enabled ? "Motor açıldı" : "Motor kapatıldı");
      await load();
    } catch { toast.error("Güncelleme başarısız"); }
    finally { setBusyKey(""); }
  };

  const onSave = async (job, payload) => {
    setBusyKey(job);
    try {
      await axios.put(`${API}/api/automation/settings/${job}`, payload);
      toast.success("Ayarlar kaydedildi");
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Kaydetme başarısız");
    } finally { setBusyKey(""); }
  };

  const onTrigger = async (job) => {
    setBusyKey(job);
    try {
      const r = await axios.post(`${API}/api/scheduler/trigger/all/${job}`);
      toast.success(`Çalıştırıldı: ${JSON.stringify(r.data.result || {}).slice(0, 120)}`);
      await load();
    } catch { toast.error("Çalıştırma başarısız"); }
    finally { setBusyKey(""); }
  };

  if (loading) return <div className="p-8 text-stone-400 text-sm" data-testid="automation-settings-loading">Yükleniyor…</div>;
  if (!data) return <div className="p-8 text-stone-400 text-sm">Veri yok</div>;

  const jobs = data.jobs || [];
  const activeCount = jobs.filter((j) => j.enabled).length;
  const grouped = {};
  jobs.forEach((j) => { (grouped[j.category] = grouped[j.category] || []).push(j); });
  const order = ["revenue", "marketing", "guest", "risk", "distribution", "reporting"];

  return (
    <div className="space-y-6" data-testid="automation-settings-panel">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
            <GearSix size={12} weight="fill" className="text-cyan-600" />
            <span>Otomasyon Kontrol Merkezi</span>
          </div>
          <h2 className="text-xl font-semibold text-stone-900">Tüm otonom motorlar tek ekranda</h2>
          <p className="text-xs text-stone-500 mt-1">
            <span className="font-medium text-emerald-600" data-testid="active-motor-count">{activeCount}/{jobs.length} motor aktif</span> — anahtarla aç/kapat, zamanlamayı ve eşik değerlerini ayarla. Değişiklikler bir sonraki çalışmada devreye girer.
          </p>
        </div>
        <button onClick={load} data-testid="automation-settings-refresh"
          className="inline-flex items-center gap-1.5 text-xs text-stone-500 hover:text-stone-800 border border-stone-200 rounded-lg px-3 py-1.5 bg-white transition-colors">
          <ArrowsClockwise size={14} /> Yenile
        </button>
      </div>

      {order.filter((c) => grouped[c]).map((cat) => (
        <div key={cat}>
          <h3 className="text-[11px] uppercase tracking-[0.15em] text-stone-400 font-medium mb-2">
            {data.categories?.[cat] || cat}
          </h3>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {grouped[cat].map((j) => (
              <MotorCard key={j.job} job={j} onToggle={onToggle} onSave={onSave}
                onTrigger={onTrigger} busyKey={busyKey} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
