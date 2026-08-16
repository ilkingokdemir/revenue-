import { useState, useEffect, useCallback, useMemo } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import {
  Brain, Zap, TrendingUp, TrendingDown, CheckCircle2, X,
  Sparkles, Clock, AlertTriangle, RefreshCw, Activity, Settings2,
} from "lucide-react";
import { makeCurrencyFormatter } from "../../lib/currency";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const authHeaders = () => ({ Authorization: `Bearer ${localStorage.getItem("access_token")}` });

const StatusBadge = ({ status }) => {
  const map = {
    pending: { c: "bg-amber-50 text-amber-700 border-amber-200", l: "Bekliyor" },
    accepted: { c: "bg-emerald-50 text-emerald-700 border-emerald-200", l: "Kabul" },
    rejected: { c: "bg-rose-50 text-rose-700 border-rose-200", l: "Red" },
    "auto-applied": { c: "bg-violet-50 text-violet-700 border-violet-200", l: "Auto" },
  };
  const m = map[status] || map.pending;
  return <span className={`text-[10px] px-1.5 py-0.5 rounded border ${m.c} font-semibold`}>{m.l}</span>;
};

const DemandBadge = ({ bucket }) => {
  const map = {
    high: "bg-rose-500/10 text-rose-700 border-rose-300",
    medium: "bg-amber-500/10 text-amber-700 border-amber-300",
    low: "bg-sky-500/10 text-sky-700 border-sky-300",
  };
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded border font-mono uppercase ${map[bucket] || map.low}`}>
      {bucket}
    </span>
  );
};

const AIPricingEnginePanel = ({ propertyId }) => {
  const [cfg, setCfg] = useState(null);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [useLLM, setUseLLM] = useState(true);
  const [days, setDays] = useState(30);
  const [filter, setFilter] = useState("all"); // all | auto | review | pending | accepted
  const [rejecting, setRejecting] = useState(null); // {date, room_type_id} when modal open
  const [rejectReason, setRejectReason] = useState("");
  const [rejectTag, setRejectTag] = useState("");
  const [signals, setSignals] = useState(null);
  const [sigCfg, setSigCfg] = useState(null);
  const [showSigCfg, setShowSigCfg] = useState(false);
  const [impact, setImpact] = useState(null);
  const [showImpact, setShowImpact] = useState(false);
  const [savingCfg, setSavingCfg] = useState(false);

  const curFormatter = useMemo(
    () => makeCurrencyFormatter(data?.currency || "GBP"),
    [data?.currency]
  );
  const cur = (v, decimals = 0) => curFormatter.format(v, decimals);

  const loadCfg = useCallback(async () => {
    if (!propertyId || propertyId === "all") return;
    try {
      const r = await axios.get(`${API}/revenue/ai-pricing/${propertyId}/config`, { headers: authHeaders() });
      setCfg(r.data);
      setDays(r.data?.days_horizon || 30);
      setUseLLM(!!r.data?.use_llm);
    } catch (e) {
      console.error("ai-pricing config load", e);
    }
  }, [propertyId]);

  const loadSuggestions = useCallback(async () => {
    if (!propertyId || propertyId === "all") return;
    setLoading(true);
    try {
      const r = await axios.get(
        `${API}/revenue/ai-pricing/${propertyId}/suggestions`,
        { params: { days, use_llm: useLLM }, headers: authHeaders() }
      );
      setData(r.data);
    } catch (e) {
      console.error("ai-pricing suggestions", e);
      toast.error("Öneriler yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [propertyId, days, useLLM]);

  useEffect(() => { loadCfg(); }, [loadCfg]);
  useEffect(() => { loadSuggestions(); }, [loadSuggestions]);
  useEffect(() => {
    if (!propertyId || propertyId === "all") return;
    axios.get(`${API}/demand-signals/${propertyId}?days=14`, { headers: authHeaders() })
      .then((r) => setSignals(r.data)).catch(() => {});
  }, [propertyId]);

  const saveCfg = async (patch) => {
    if (!cfg) return;
    setSavingCfg(true);
    try {
      const r = await axios.put(
        `${API}/revenue/ai-pricing/${propertyId}/config`,
        { ...cfg, ...patch },
        { headers: authHeaders() }
      );
      setCfg(r.data);
      toast.success("Yapılandırma kaydedildi");
    } catch (e) {
      toast.error("Yapılandırma kaydedilemedi");
    } finally {
      setSavingCfg(false);
    }
  };

  const acceptAll = async () => {
    if (!data?.suggestions) return;
    const items = data.suggestions.filter(s => s.auto_apply_eligible && s.status === "pending");
    if (items.length === 0) {
      toast.info("Eşik içinde bekleyen öneri yok");
      return;
    }
    try {
      const r = await axios.post(
        `${API}/revenue/ai-pricing/${propertyId}/accept`,
        { items },
        { headers: authHeaders() }
      );
      toast.success(`${r.data.accepted} öneri uygulandı`);
      loadSuggestions();
    } catch (e) {
      toast.error("Toplu uygulama başarısız");
    }
  };

  const acceptOne = async (item) => {
    try {
      await axios.post(
        `${API}/revenue/ai-pricing/${propertyId}/accept`,
        { items: [item] },
        { headers: authHeaders() }
      );
      toast.success(`${item.date} → ${cur(item.suggested_rate)} uygulandı`);
      loadSuggestions();
    } catch (e) {
      toast.error("Uygulanamadı");
    }
  };

  const runAutoApplyNow = async () => {
    setRunning(true);
    try {
      const r = await axios.post(
        `${API}/revenue/ai-pricing/${propertyId}/run-auto-apply`,
        {},
        { headers: authHeaders() }
      );
      if (r.data?.skipped_reason) {
        toast.info(`Atlandı: ${r.data.skipped_reason}`);
      } else {
        toast.success(`${r.data.applied} öneri otomatik uygulandı`);
      }
      loadSuggestions();
    } catch (e) {
      toast.error("Auto-apply başarısız");
    } finally {
      setRunning(false);
    }
  };

  const openImpact = async () => {
    if (!showImpact && !impact) {
      try {
        const r = await axios.get(`${API}/demand-signals/${propertyId}/impact-report?weeks=4`, { headers: authHeaders() });
        setImpact(r.data);
      } catch { toast.error("Etki raporu yüklenemedi"); return; }
    }
    setShowImpact((s) => !s);
  };

  const openSigCfg = async () => {
    if (!showSigCfg && !sigCfg) {
      try {
        const r = await axios.get(`${API}/demand-signals/${propertyId}/config`, { headers: authHeaders() });
        setSigCfg(r.data);
      } catch { toast.error("Sinyal ayarları yüklenemedi"); return; }
    }
    setShowSigCfg((s) => !s);
  };

  const saveSigCfg = async () => {
    try {
      const r = await axios.put(`${API}/demand-signals/${propertyId}/config`, sigCfg, { headers: authHeaders() });
      setSigCfg(r.data);
      toast.success("Sinyal ağırlıkları kaydedildi — takvim yeniden hesaplandı");
      const s = await axios.get(`${API}/demand-signals/${propertyId}?days=14`, { headers: authHeaders() });
      setSignals(s.data);
    } catch { toast.error("Kaydedilemedi"); }
  };

  const confirmReject = async () => {
    if (!rejecting) return;
    try {
      await axios.post(
        `${API}/revenue/ai-pricing/${propertyId}/reject`,
        { ...rejecting, reason: rejectReason || "Manuel reddedildi", reason_tag: rejectTag || undefined },
        { headers: authHeaders() }
      );
      toast.success("Öneri reddedildi");
      setRejecting(null);
      setRejectReason("");
      setRejectTag("");
      loadSuggestions();
    } catch (e) {
      toast.error("Reddedilemedi");
    }
  };

  const filtered = useMemo(() => {
    const list = data?.suggestions || [];
    if (filter === "auto") return list.filter(s => s.auto_apply_eligible);
    if (filter === "review") return list.filter(s => !s.auto_apply_eligible);
    if (filter === "pending") return list.filter(s => s.status === "pending");
    if (filter === "accepted") return list.filter(s => ["accepted", "auto-applied"].includes(s.status));
    return list;
  }, [data, filter]);

  if (!propertyId || propertyId === "all") {
    return (
      <div className="bg-white border border-stone-200 rounded-2xl p-6" data-testid="ai-pricing-panel-empty">
        <div className="flex items-center gap-3">
          <Brain className="w-6 h-6 text-violet-600" />
          <p className="text-stone-600">AI Pricing motoru için lütfen bir otel seçin.</p>
        </div>
      </div>
    );
  }

  const sum = data?.summary || {};

  return (
    <div className="space-y-6" data-testid="ai-pricing-panel">
      {/* HEADER */}
      <div className="relative overflow-hidden rounded-2xl border border-violet-200 bg-gradient-to-br from-violet-600 via-indigo-600 to-cyan-600 p-6 text-white">
        <div className="absolute -top-12 -right-12 w-48 h-48 bg-white/10 rounded-full blur-3xl"></div>
        <div className="relative flex items-start justify-between gap-4 flex-wrap">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Brain className="w-5 h-5" />
              <span className="text-xs uppercase tracking-widest font-bold opacity-80">RMS Pro · AI Pricing Engine</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/20 font-mono">Hybrid</span>
            </div>
            <h2 className="text-2xl font-bold">Akıllı Günlük Fiyat Önerileri</h2>
            <p className="text-sm opacity-85 mt-1">
              Rakip ortalaması + doluluk + lead-time → otomatik kabul/red akışı
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              data-testid="ai-pricing-refresh"
              onClick={loadSuggestions}
              disabled={loading}
              className="px-3 py-2 bg-white/15 hover:bg-white/25 rounded-lg text-sm font-medium flex items-center gap-2 transition"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
              Yenile
            </button>
            <button
              data-testid="ai-pricing-run-auto"
              onClick={runAutoApplyNow}
              disabled={running || !cfg?.auto_apply}
              className="px-4 py-2 bg-white text-violet-700 hover:bg-violet-50 rounded-lg text-sm font-bold flex items-center gap-2 transition disabled:opacity-50 disabled:cursor-not-allowed"
              title={!cfg?.auto_apply ? "Auto-apply önce yapılandırmadan açılmalı" : "Eşik içindeki tüm önerileri sessizce uygula"}
            >
              <Zap className="w-4 h-4" />
              {running ? "Çalışıyor…" : "Auto-Apply Şimdi"}
            </button>
          </div>
        </div>
      </div>

      {/* CONFIG STRIP */}
      <div className="bg-white border border-stone-200 rounded-2xl p-5" data-testid="ai-pricing-config">
        <div className="flex items-center gap-2 mb-4">
          <Settings2 className="w-4 h-4 text-stone-600" />
          <h3 className="font-bold text-stone-800">Motor Ayarları</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="flex flex-col gap-2 p-3 rounded-lg bg-stone-50 border border-stone-200">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-stone-700">Motor Açık</span>
              <Switch
                data-testid="ai-pricing-cfg-enabled"
                checked={!!cfg?.enabled}
                onCheckedChange={(v) => saveCfg({ enabled: v })}
                disabled={savingCfg}
              />
            </div>
            <p className="text-[10px] text-stone-500">Tüm öneri üretimi {cfg?.enabled ? "aktif" : "pasif"}</p>
          </div>
          <div className="flex flex-col gap-2 p-3 rounded-lg bg-stone-50 border border-stone-200">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-stone-700">Auto-Apply</span>
              <Switch
                data-testid="ai-pricing-cfg-autoapply"
                checked={!!cfg?.auto_apply}
                onCheckedChange={(v) => saveCfg({ auto_apply: v })}
                disabled={savingCfg}
              />
            </div>
            <p className="text-[10px] text-stone-500">Eşik içindeki öneriler sessizce uygulanır</p>
          </div>
          <div className="flex flex-col gap-2 p-3 rounded-lg bg-stone-50 border border-stone-200">
            <span className="text-xs font-semibold text-stone-700">Eşik (±%)</span>
            <Input
              data-testid="ai-pricing-cfg-threshold"
              type="number"
              min={0.5}
              max={25}
              step={0.5}
              value={cfg?.auto_apply_threshold_pct || 5}
              onChange={(e) => setCfg({ ...cfg, auto_apply_threshold_pct: parseFloat(e.target.value) || 5 })}
              onBlur={(e) => saveCfg({ auto_apply_threshold_pct: parseFloat(e.target.value) || 5 })}
              className="h-8 text-xs"
            />
            <p className="text-[10px] text-stone-500">|Δ| ≤ {cfg?.auto_apply_threshold_pct || 5}% otomatik</p>
          </div>
          <div className="flex flex-col gap-2 p-3 rounded-lg bg-stone-50 border border-stone-200">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-stone-700">LLM Gerekçesi</span>
              <Switch
                data-testid="ai-pricing-cfg-llm"
                checked={useLLM}
                onCheckedChange={(v) => { setUseLLM(v); saveCfg({ use_llm: v }); }}
                disabled={savingCfg}
              />
            </div>
            <p className="text-[10px] text-stone-500">GPT-4o-mini ile günlük TR açıklama</p>
          </div>
          <div className="flex flex-col gap-2 p-3 rounded-lg bg-stone-50 border border-stone-200">
            <span className="text-xs font-semibold text-stone-700">Anomali Modu</span>
            <select value={cfg?.anomaly_mode || "human"} data-testid="ai-pricing-cfg-anomaly"
              onChange={(e) => { setCfg({ ...cfg, anomaly_mode: e.target.value }); saveCfg({ anomaly_mode: e.target.value }); }}
              className="h-8 text-xs border border-stone-300 rounded-md px-2 bg-white">
              <option value="human">İnsan onayı (dondur + sor)</option>
              <option value="auto">Otomatik (bildir + devam)</option>
            </select>
            <p className="text-[10px] text-stone-500">Rakip verisi saçmalarsa / OTB sıçrarsa</p>
          </div>
        </div>
      </div>

      {/* ROLLBACK + FREEZE */}
      <div className="flex justify-end">
        <button onClick={async () => {
          try {
            const r = await axios.post(`${API}/revenue/ai-pricing/${propertyId}/rollback-last`, {}, { headers: authHeaders() });
            if (r.data.ok) toast.success(`${r.data.reverted} fiyat geri alındı (${(r.data.run_at || "").slice(0, 16)} koşusu)`);
            else toast.info(r.data.reason || "Geri alınacak koşu yok");
          } catch { toast.error("Geri alma başarısız"); }
        }} data-testid="ai-pricing-rollback-btn"
          className="px-3 py-1.5 text-xs font-bold rounded-lg border border-rose-300 text-rose-700 hover:bg-rose-50">
          ↩ Son Koşuyu Geri Al
        </button>
      </div>

      {/* FREEZE BANNER */}
      {cfg?.freeze?.active && (
        <div className="bg-amber-50 border border-amber-300 rounded-xl p-4 flex flex-wrap items-center gap-3" data-testid="ai-pricing-freeze-banner">
          <div className="flex-1 min-w-[250px]">
            <div className="text-sm font-bold text-amber-800">⚠ Fiyat oto-uygulama DONDURULDU — insan onayı bekleniyor</div>
            <div className="text-xs text-amber-700 mt-0.5">{cfg.freeze.reason}</div>
          </div>
          <button onClick={async () => {
            try {
              await axios.post(`${API}/revenue/ai-pricing/${propertyId}/unfreeze`, {}, { headers: authHeaders() });
              toast.success("Dondurma kaldırıldı — robot devam ediyor");
              loadCfg();
            } catch { toast.error("Kaldırılamadı"); }
          }} data-testid="ai-pricing-unfreeze-btn"
            className="px-4 py-2 text-xs font-bold rounded-lg bg-amber-600 text-white hover:bg-amber-700">
            Dondurmayı Kaldır
          </button>
        </div>
      )}

      {/* HAVA + TATİL SİNYAL ŞERİDİ */}
      {signals && (signals.rows || []).length > 0 && (
        <div className="bg-white border border-stone-200 rounded-xl p-3" data-testid="ai-pricing-signals-strip">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[11px] font-bold text-stone-600">🌤 Hava + Resmi Tatil Sinyalleri (14 gün{signals.geo?.resolved_name ? ` · ${signals.geo.resolved_name}` : ""}) — fiyat motoruna çarpan olarak girer</span>
            <div className="flex items-center gap-1.5">
              <button onClick={openImpact} data-testid="ai-pricing-signal-impact-btn" className="px-2 py-0.5 rounded-lg border border-stone-300 text-stone-500 text-[10px] font-bold hover:border-stone-400">📊 Etki Raporu</button>
              <button onClick={openSigCfg} data-testid="ai-pricing-signal-cfg-btn" className="px-2 py-0.5 rounded-lg border border-stone-300 text-stone-500 text-[10px] font-bold hover:border-stone-400">⚙ Ağırlıklar</button>
            </div>
          </div>
          {showImpact && impact && (
            <div className="mb-2 bg-stone-50 border border-stone-200 rounded-lg p-2" data-testid="ai-pricing-signal-impact">
              <div className="text-[11px] font-black text-stone-700 mb-1">
                📊 Sinyal Etki Raporu (son 4 hafta) — toplam tahmini katkı:{" "}
                <span className={impact.total_est_impact >= 0 ? "text-emerald-700" : "text-rose-600"} data-testid="ai-pricing-impact-total">
                  {impact.total_est_impact >= 0 ? "+" : ""}{impact.total_est_impact} {impact.currency}
                </span>{" "}
                <span className="text-stone-400 font-normal">({impact.total_signal_days} sinyalli gün)</span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5">
                {impact.weeks.map((wk) => (
                  <div key={wk.week} className="bg-white border border-stone-200 rounded-lg px-2 py-1" data-testid={`ai-pricing-impact-${wk.week}`}>
                    <div className="text-[9px] text-stone-400">{wk.week} · {wk.signal_days} gün · {wk.room_nights} og</div>
                    <div className={`text-[12px] font-black ${wk.est_impact > 0 ? "text-emerald-700" : wk.est_impact < 0 ? "text-rose-600" : "text-stone-400"}`}>
                      {wk.est_impact > 0 ? "+" : ""}{wk.est_impact} {impact.currency}
                    </div>
                  </div>
                ))}
              </div>
              <p className="text-[9px] text-stone-400 mt-1">{impact.note}</p>
            </div>
          )}
          {showSigCfg && sigCfg && (
            <div className="flex flex-wrap items-end gap-2 mb-2 bg-stone-50 border border-stone-200 rounded-lg p-2" data-testid="ai-pricing-signal-cfg">
              {[["holiday_pct", "Tatil +%"], ["eve_pct", "Arife +%"], ["sunny_weekend_pct", "Güneşli h.sonu +%"], ["bad_weather_pct", "Şiddetli hava −%"]].map(([k, label]) => (
                <label key={k} className="text-[10px] text-stone-500 font-bold">
                  {label}
                  <input type="number" min="0" max="15" step="0.5" value={sigCfg[k]} data-testid={`ai-pricing-sigcfg-${k}`}
                    onChange={(e) => setSigCfg((c) => ({ ...c, [k]: e.target.value }))}
                    className="block w-20 mt-0.5 border border-stone-300 rounded-lg px-2 py-1 text-[12px] font-normal" />
                </label>
              ))}
              <label className="text-[10px] text-stone-500 font-bold flex items-center gap-1 pb-1.5">
                <input type="checkbox" checked={!!sigCfg.enabled} data-testid="ai-pricing-sigcfg-enabled"
                  onChange={(e) => setSigCfg((c) => ({ ...c, enabled: e.target.checked }))} /> Aktif
              </label>
              <button onClick={saveSigCfg} data-testid="ai-pricing-sigcfg-save" className="px-3 py-1.5 rounded-lg bg-stone-900 text-white text-[11px] font-bold">Kaydet</button>
            </div>
          )}
          <div className="flex gap-1 overflow-x-auto pb-1">
            {signals.rows.map((s) => (
              <div key={s.date} title={(s.reasons || []).join(" · ") || "Nötr"} data-testid={`ai-pricing-signal-${s.date}`}
                className={`shrink-0 w-[72px] rounded-lg border px-1.5 py-1 text-center ${s.multiplier > 1 ? "border-emerald-200 bg-emerald-50" : s.multiplier < 1 ? "border-rose-200 bg-rose-50" : "border-stone-100 bg-stone-50"}`}>
                <div className="text-[9px] text-stone-500">{s.date.slice(5)}</div>
                <div className="text-[11px]">{s.holiday ? "🎌" : s.weather && (s.weather.precip || 0) >= 15 ? "🌧" : s.weather && (s.weather.tmax || 0) >= 22 ? "☀️" : "·"}</div>
                <div className={`text-[10px] font-black ${s.multiplier > 1 ? "text-emerald-700" : s.multiplier < 1 ? "text-rose-600" : "text-stone-400"}`}>
                  {s.multiplier === 1 ? "—" : `×${s.multiplier}`}
                </div>
              </div>
            ))}
          </div>
          <p className="text-[9px] text-stone-400 mt-1">{signals.note}</p>
        </div>
      )}

      {/* STATS GRID */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3" data-testid="ai-pricing-stats">
        <StatCard label="Toplam Öneri" value={sum.total || 0} icon={<Sparkles className="w-4 h-4" />} tone="violet" />
        <StatCard label="Auto Uygun" value={sum.auto_eligible || 0} icon={<Zap className="w-4 h-4" />} tone="emerald" />
        <StatCard label="Manuel İnceleme" value={sum.outside_threshold || 0} icon={<AlertTriangle className="w-4 h-4" />} tone="amber" />
        <StatCard label="Ort. Δ %" value={`${sum.avg_delta_pct >= 0 ? "+" : ""}${sum.avg_delta_pct || 0}%`} icon={sum.avg_delta_pct >= 0 ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />} tone={sum.avg_delta_pct >= 0 ? "emerald" : "rose"} />
        <StatCard label="Tahmini Uplift" value={cur(sum.uplift_estimate || 0)} icon={<Activity className="w-4 h-4" />} tone="cyan" />
      </div>

      {/* FILTER PILLS */}
      <div className="flex items-center gap-2 flex-wrap" data-testid="ai-pricing-filters">
        {[
          { id: "all", label: `Tümü (${sum.total || 0})` },
          { id: "auto", label: `Auto Uygun (${sum.auto_eligible || 0})` },
          { id: "review", label: `İncelene (${sum.outside_threshold || 0})` },
          { id: "pending", label: `Bekliyor (${sum.pending || 0})` },
          { id: "accepted", label: `Uygulanan (${(sum.accepted || 0) + (sum.auto_applied || 0)})` },
        ].map(f => (
          <button
            key={f.id}
            data-testid={`ai-pricing-filter-${f.id}`}
            onClick={() => setFilter(f.id)}
            className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition ${
              filter === f.id
                ? "bg-violet-600 text-white border-violet-600"
                : "bg-white text-stone-600 border-stone-200 hover:border-stone-300"
            }`}
          >
            {f.label}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-2">
          <span className="text-xs text-stone-500">Pencere:</span>
          {[7, 14, 30, 60, 90].map(d => (
            <button
              key={d}
              data-testid={`ai-pricing-days-${d}`}
              onClick={() => setDays(d)}
              className={`px-2 py-1 rounded text-[11px] font-mono ${
                days === d
                  ? "bg-stone-900 text-white"
                  : "bg-stone-100 text-stone-600 hover:bg-stone-200"
              }`}
            >
              {d}g
            </button>
          ))}
          <button
            data-testid="ai-pricing-accept-all"
            onClick={acceptAll}
            disabled={!sum.auto_eligible}
            className="ml-2 px-3 py-1.5 rounded-lg text-xs font-bold bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            <CheckCircle2 className="w-3 h-3 inline-block mr-1" />
            Tüm Auto-Uygunları Kabul Et
          </button>
        </div>
      </div>

      {/* SUGGESTION TABLE */}
      <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden" data-testid="ai-pricing-table">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-stone-50 border-b border-stone-200">
              <tr className="text-left text-[11px] uppercase tracking-wider text-stone-600">
                <th className="px-3 py-2.5">Tarih</th>
                <th className="px-3 py-2.5">Lead</th>
                <th className="px-3 py-2.5">Talep</th>
                <th className="px-3 py-2.5">Doluluk</th>
                <th className="px-3 py-2.5">Pazar Ort</th>
                <th className="px-3 py-2.5">Mevcut</th>
                <th className="px-3 py-2.5">Öneri</th>
                <th className="px-3 py-2.5">NET Kâr</th>
                <th className="px-3 py-2.5">Δ%</th>
                <th className="px-3 py-2.5">Gerekçe</th>
                <th className="px-3 py-2.5">Durum</th>
                <th className="px-3 py-2.5"></th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={12} className="px-3 py-10 text-center text-stone-400">
                  <RefreshCw className="w-5 h-5 animate-spin inline-block mr-2" />
                  Hesaplanıyor…
                </td></tr>
              )}
              {!loading && filtered.length === 0 && (
                <tr><td colSpan={12} className="px-3 py-10 text-center text-stone-400">
                  <Brain className="w-6 h-6 inline-block mb-2 opacity-50" /><br />
                  Bu filtreye uygun öneri yok. Önce Neighborhood scan'i çalıştırın.
                </td></tr>
              )}
              {!loading && filtered.map((s, i) => {
                const positive = s.delta_vs_current_pct > 0;
                const dlt = `${positive ? "+" : ""}${s.delta_vs_current_pct?.toFixed(1)}%`;
                const dltColor =
                  Math.abs(s.delta_vs_current_pct) <= (cfg?.auto_apply_threshold_pct || 5)
                    ? "text-emerald-700 bg-emerald-50 border-emerald-200"
                    : positive
                      ? "text-amber-700 bg-amber-50 border-amber-200"
                      : "text-rose-700 bg-rose-50 border-rose-200";
                return (
                  <tr key={s.id} data-testid={`ai-pricing-row-${i}`} className={`border-b border-stone-100 hover:bg-stone-50/50 ${(s.confidence ?? 1) < 0.5 ? "opacity-45 grayscale" : ""}`} title={(s.confidence ?? 1) < 0.5 ? `Düşük güven (%${Math.round((s.confidence || 0) * 100)}) — ${(s.evidence || []).join(" · ")}` : (s.evidence || []).join(" · ")}>
                    <td className="px-3 py-2 font-mono text-xs text-stone-800">{s.date}</td>
                    <td className="px-3 py-2 text-xs text-stone-600">
                      <span className="font-mono">{s.days_out}g</span>
                    </td>
                    <td className="px-3 py-2">
                      <DemandBadge bucket={s.demand_bucket} />
                      {s.str_mult > 1 && (
                        <span className="ml-1 text-[9px] px-1 py-0.5 rounded bg-rose-50 text-rose-600 border border-rose-200 font-bold" data-testid={`ai-pricing-str-badge-${i}`} title={`STR baskısı: doluluk %${s.str_unavailable_pct} · medyan £${s.str_median}`}>
                          STR×{s.str_mult}
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-xs text-stone-700 font-mono">{s.occupancy_pct}%</td>
                    <td className="px-3 py-2 text-xs text-stone-700 font-mono">{cur(s.market_avg)}</td>
                    <td className="px-3 py-2 text-xs text-stone-700 font-mono">{cur(s.current_rate)}</td>
                    <td className="px-3 py-2 text-xs text-violet-700 font-bold font-mono">
                      {cur(s.suggested_rate)}
                      {s.confidence != null && (
                        <span className={`ml-1 text-[9px] px-1 py-0.5 rounded border font-bold ${s.confidence >= 0.7 ? "bg-emerald-50 text-emerald-600 border-emerald-200" : s.confidence >= 0.5 ? "bg-amber-50 text-amber-600 border-amber-200" : "bg-stone-100 text-stone-500 border-stone-200"}`} data-testid={`ai-pricing-conf-${i}`} title={(s.evidence || []).join(" · ")}>
                          G%{Math.round(s.confidence * 100)}
                        </span>
                      )}
                      {s.event_boost_pct > 0 && (
                        <span className="ml-1 text-[9px] px-1 py-0.5 rounded bg-violet-50 text-violet-600 border border-violet-200 font-bold" data-testid={`ai-pricing-event-${i}`} title={`Etkinlik boost'u: +%${s.event_boost_pct}`}>🎫+%{s.event_boost_pct}</span>
                      )}
                      {s.clamped && <span className="ml-1 text-[9px] text-stone-400">clamped</span>}
                    </td>
                    <td className="px-3 py-2 text-xs font-mono" data-testid={`ai-pricing-net-${i}`}>
                      {s.net_new_rate != null ? (
                        <span title={s.net_note || "Komisyon + CPOR düşülmüş net oda kârı"}>
                          <span className="text-stone-400">{cur(s.net_current_rate)}→</span>
                          <span className={`font-bold ${(s.net_delta_pct || 0) >= 0 ? "text-emerald-700" : "text-rose-700"}`}>{cur(s.net_new_rate)}</span>
                          <span className={`ml-1 text-[9px] ${(s.net_delta_pct || 0) >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
                            {(s.net_delta_pct || 0) > 0 ? "+" : ""}{s.net_delta_pct}%
                          </span>
                        </span>
                      ) : <span className="text-stone-300">—</span>}
                    </td>
                    <td className="px-3 py-2">
                      <span className={`text-[10px] px-1.5 py-0.5 rounded border font-mono font-bold ${dltColor}`}>{dlt}</span>
                    </td>
                    <td className="px-3 py-2 text-[11px] text-stone-600 max-w-[280px]">
                      {s.rationale || (
                        <span className="text-stone-400 italic">
                          {`ref ${cur(s.ref_price)} × lead ${s.lead_time_mult} × occ ${s.occupancy_mult}${s.str_mult > 1 ? ` × STR ${s.str_mult}` : ""}`}
                        </span>
                      )}
                      {Array.isArray(s.waterfall) && s.waterfall.length > 1 && (
                        <div className="flex flex-wrap gap-0.5 mt-1" data-testid={`ai-pricing-waterfall-${i}`}>
                          {s.waterfall.map((w, wi) => (
                            <span key={wi} className={`text-[9px] px-1 py-0.5 rounded border font-bold ${wi === 0 ? "bg-stone-100 text-stone-600 border-stone-200" : w.delta >= 0 ? "bg-emerald-50 text-emerald-600 border-emerald-200" : "bg-rose-50 text-rose-600 border-rose-200"}`} title={`${w.label} — ara toplam: ${w.running}`}>
                              {wi === 0 ? `${w.label} ${w.delta}` : `${w.label} ${w.delta >= 0 ? "+" : ""}${w.delta}`}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-2"><StatusBadge status={s.status} /></td>
                    <td className="px-3 py-2 whitespace-nowrap">
                      {s.status === "pending" && (
                        <div className="flex gap-1">
                          <button
                            data-testid={`ai-pricing-accept-${i}`}
                            onClick={() => acceptOne(s)}
                            className="px-2 py-1 rounded text-[10px] font-bold bg-emerald-600 hover:bg-emerald-700 text-white"
                            title="Kabul et — rate_overrides'a yaz"
                          >
                            <CheckCircle2 className="w-3 h-3 inline-block mr-0.5" />
                            Kabul
                          </button>
                          <button
                            data-testid={`ai-pricing-reject-${i}`}
                            onClick={() => setRejecting({ date: s.date, room_type_id: s.room_type_id })}
                            className="px-2 py-1 rounded text-[10px] font-bold bg-rose-50 text-rose-700 border border-rose-200 hover:bg-rose-100"
                            title="Reddet"
                          >
                            <X className="w-3 h-3 inline-block" />
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="px-4 py-2.5 bg-stone-50 border-t border-stone-200 flex items-center justify-between text-[11px] text-stone-500">
          <div className="flex items-center gap-3">
            <Clock className="w-3 h-3" />
            <span>
              Son çalıştırma: {cfg?.last_run_at ? new Date(cfg.last_run_at).toLocaleString("tr-TR") : "—"}
            </span>
            {cfg?.last_auto_applied != null && (
              <span>· Son auto-apply: {cfg.last_auto_applied}</span>
            )}
          </div>
          <span className="font-mono">{filtered.length} satır</span>
        </div>
      </div>

      {/* REJECT MODAL */}
      {rejecting && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" data-testid="ai-pricing-reject-modal">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6">
            <h3 className="text-lg font-bold text-stone-900 mb-2">Öneriyi Reddet</h3>
            <p className="text-sm text-stone-600 mb-4">
              <span className="font-mono">{rejecting.date}</span> önerisini reddetmek istediğine emin misin?
            </p>
            <label className="block text-xs font-semibold text-stone-700 mb-1.5">Red nedeni (etiket seç — modelin kör nokta haritası)</label>
            <div className="flex flex-wrap gap-1.5 mb-3" data-testid="ai-pricing-reject-tags">
              {[["too_aggressive", "Çok agresif artış"], ["too_low", "Gereksiz indirim"], ["event_unknown", "Motor etkinliği bilmiyor"], ["segment_mismatch", "Segment/kanal uyumsuz"], ["data_wrong", "Veri hatalı"], ["strategy_conflict", "Stratejiye aykırı"], ["other", "Diğer"]].map(([tag, label]) => (
                <button key={tag} type="button" onClick={() => setRejectTag(rejectTag === tag ? "" : tag)} data-testid={`ai-pricing-reject-tag-${tag}`}
                  className={`px-2.5 py-1 rounded-full text-[11px] font-bold border transition-colors ${rejectTag === tag ? "bg-rose-600 text-white border-rose-600" : "border-stone-300 text-stone-600 hover:border-rose-300"}`}>
                  {label}
                </button>
              ))}
            </div>
            <label className="block text-xs font-semibold text-stone-700 mb-1.5">Sebep (opsiyonel)</label>
            <Input
              data-testid="ai-pricing-reject-reason"
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="örn. özel event, manuel set ettim, vs."
              className="mb-4"
            />
            <div className="flex justify-end gap-2">
              <button
                data-testid="ai-pricing-reject-cancel"
                onClick={() => { setRejecting(null); setRejectReason(""); setRejectTag(""); }}
                className="px-3 py-1.5 rounded text-sm font-medium text-stone-600 hover:bg-stone-100"
              >
                İptal
              </button>
              <button
                data-testid="ai-pricing-reject-confirm"
                onClick={confirmReject}
                className="px-3 py-1.5 rounded text-sm font-bold bg-rose-600 hover:bg-rose-700 text-white"
              >
                Reddet
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const StatCard = ({ label, value, icon, tone = "violet" }) => {
  const tones = {
    violet: "from-violet-50 to-indigo-50 text-violet-700 border-violet-200",
    emerald: "from-emerald-50 to-green-50 text-emerald-700 border-emerald-200",
    amber: "from-amber-50 to-orange-50 text-amber-700 border-amber-200",
    rose: "from-rose-50 to-pink-50 text-rose-700 border-rose-200",
    cyan: "from-cyan-50 to-sky-50 text-cyan-700 border-cyan-200",
  };
  return (
    <div className={`rounded-xl border bg-gradient-to-br p-3 ${tones[tone] || tones.violet}`}>
      <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider font-semibold opacity-80">
        {icon}{label}
      </div>
      <div className="text-xl font-bold mt-1 tabular-nums">{value}</div>
    </div>
  );
};

export default AIPricingEnginePanel;
