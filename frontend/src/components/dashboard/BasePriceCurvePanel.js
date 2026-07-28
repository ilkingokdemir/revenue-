import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ChartLineUp, FloppyDisk, CalendarCheck, Plus, Trash,
  Lightning, Clock, ArrowsClockwise,
} from "@phosphor-icons/react";
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid,
} from "recharts";

const API = process.env.REACT_APP_BACKEND_URL;

const DOW_LABELS = [["mon", "Pzt"], ["tue", "Sal"], ["wed", "Çar"], ["thu", "Per"], ["fri", "Cum"], ["sat", "Cmt"], ["sun", "Paz"]];
const HORIZONS = [[90, "90 gün"], [180, "6 ay"], [365, "12 ay"], [540, "18 ay"]];

export default function BasePriceCurvePanel({ properties = [], activePropertyId }) {
  const [propertyId, setPropertyId] = useState(activePropertyId && activePropertyId !== "all" ? activePropertyId : properties[0]?.id || "default");
  const [cfg, setCfg] = useState(null);
  const [preview, setPreview] = useState(null);
  const [cadence, setCadence] = useState(null);
  const [horizon, setHorizon] = useState(540);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (activePropertyId && activePropertyId !== "all") setPropertyId(activePropertyId);
  }, [activePropertyId]);

  const load = useCallback(async () => {
    try {
      const [c, cad] = await Promise.all([
        axios.get(`${API}/api/base-curve/${propertyId}/config`, { withCredentials: true }),
        axios.get(`${API}/api/revenue/ai-pricing/${propertyId}/cadence`, { withCredentials: true }),
      ]);
      setCfg(c.data);
      setCadence(cad.data);
    } catch (e) {
      toast.error("Konfigürasyon yüklenemedi");
    }
  }, [propertyId]);

  const loadPreview = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/api/base-curve/${propertyId}/preview?days=${horizon}`, { withCredentials: true });
      setPreview(r.data);
    } catch (e) { /* noop */ }
  }, [propertyId, horizon]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { loadPreview(); }, [loadPreview, cfg?.updated_at]);

  const save = async () => {
    setBusy(true);
    try {
      const r = await axios.put(`${API}/api/base-curve/${propertyId}/config`, cfg, { withCredentials: true });
      setCfg(r.data);
      toast.success("Eğri kaydedildi");
      loadPreview();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Kaydedilemedi");
    } finally { setBusy(false); }
  };

  const apply = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/base-curve/${propertyId}/apply`, { days: horizon }, { withCredentials: true });
      toast.success(`${r.data.written} tarihe baz fiyat yazıldı (${r.data.skipped_protected} korunan tarih atlandı)`);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Uygulanamadı");
    } finally { setBusy(false); }
  };

  const setSeason = (i, field, value) => {
    const seasons = [...(cfg.seasons || [])];
    seasons[i] = { ...seasons[i], [field]: value };
    setCfg({ ...cfg, seasons });
  };

  if (!cfg) return <div className="p-8 text-sm text-stone-400">Yükleniyor…</div>;

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="base-curve-panel">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
            <ChartLineUp size={12} weight="fill" className="text-blue-500" />
            <span>Revenue · 18 Ay İleri Fiyatlama</span>
          </div>
          <h1 className="text-2xl font-semibold text-stone-900">Baz Fiyat Eğrisi</h1>
          <p className="text-sm text-stone-500 mt-1 max-w-2xl">
            Tek baz fiyat + haftanın günü ve sezon çarpanları ile 18 aya kadar fiyat üretin. Yakın vadede AI motoru bu bazın üzerinde optimize etmeye devam eder.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {properties.length > 1 && (
            <select value={propertyId} onChange={(e) => setPropertyId(e.target.value)}
              data-testid="base-curve-property-select"
              className="text-xs border border-stone-300 rounded-md px-2 py-2 bg-white">
              {properties.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          )}
          <select value={horizon} onChange={(e) => setHorizon(Number(e.target.value))}
            data-testid="base-curve-horizon-select"
            className="text-xs border border-stone-300 rounded-md px-2 py-2 bg-white">
            {HORIZONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          <button onClick={save} disabled={busy} data-testid="base-curve-save"
            className="px-3 py-2 text-xs rounded-md border border-stone-300 text-stone-700 hover:bg-stone-100 inline-flex items-center gap-1.5">
            <FloppyDisk size={13} /> Kaydet
          </button>
          <button onClick={apply} disabled={busy} data-testid="base-curve-apply"
            className="px-3 py-2 text-xs rounded-md bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 inline-flex items-center gap-1.5 font-medium">
            <CalendarCheck size={13} weight="fill" /> {busy ? "…" : `${horizon} Güne Uygula`}
          </button>
        </div>
      </div>

      {cadence && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
          <CadenceKpi icon={Lightning} color="amber" label="Bugünkü Autopilot Koşusu"
            value={`${cadence.runs_today} / ${cadence.target_updates_per_day}`} testId="cadence-runs" />
          <CadenceKpi icon={ArrowsClockwise} color="emerald" label="Bugün Uygulanan Fiyat"
            value={cadence.applied_today} testId="cadence-applied" />
          <CadenceKpi icon={CalendarCheck} color="blue" label="Motor Ufku"
            value={`${cadence.horizon_days} gün`} testId="cadence-horizon" />
          <CadenceKpi icon={Clock} color="violet" label="Son Koşu"
            value={cadence.last_run_at ? new Date(cadence.last_run_at).toLocaleString("tr-TR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "—"} testId="cadence-last-run" />
        </div>
      )}

      <div className="grid lg:grid-cols-3 gap-4">
        <div className="lg:col-span-1 space-y-4">
          <div className="bg-white border border-stone-200 rounded-lg p-4 space-y-3">
            <div className="text-sm font-semibold text-stone-900">Fiyat Sınırları (£)</div>
            <div className="grid grid-cols-3 gap-2">
              <NumField label="Baz" value={cfg.base_price} onChange={(v) => setCfg({ ...cfg, base_price: v })} testId="base-curve-base" />
              <NumField label="Min" value={cfg.min_price} onChange={(v) => setCfg({ ...cfg, min_price: v })} testId="base-curve-min" />
              <NumField label="Max" value={cfg.max_price} onChange={(v) => setCfg({ ...cfg, max_price: v })} testId="base-curve-max" />
            </div>
          </div>

          <div className="bg-white border border-stone-200 rounded-lg p-4 space-y-3">
            <div className="text-sm font-semibold text-stone-900">Haftanın Günü Çarpanları</div>
            <div className="grid grid-cols-4 gap-2">
              {DOW_LABELS.map(([k, l]) => (
                <NumField key={k} label={l} step="0.05" value={cfg.dow_factors?.[k] ?? 1}
                  onChange={(v) => setCfg({ ...cfg, dow_factors: { ...cfg.dow_factors, [k]: v } })}
                  testId={`base-curve-dow-${k}`} />
              ))}
            </div>
          </div>

          <div className="bg-white border border-stone-200 rounded-lg p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div className="text-sm font-semibold text-stone-900">Sezonlar</div>
              <button data-testid="base-curve-season-add"
                onClick={() => setCfg({ ...cfg, seasons: [...(cfg.seasons || []), { name: "Yeni Sezon", start: "01-01", end: "01-31", factor: 1.0 }] })}
                className="text-xs text-blue-600 hover:text-blue-700 inline-flex items-center gap-1"><Plus size={12} /> Ekle</button>
            </div>
            {(cfg.seasons || []).map((s, i) => (
              <div key={i} className="grid grid-cols-[1fr_70px_70px_56px_24px] gap-1.5 items-center" data-testid={`base-curve-season-${i}`}>
                <input value={s.name} onChange={(e) => setSeason(i, "name", e.target.value)}
                  className="px-2 py-1.5 text-xs border border-stone-300 rounded-md" />
                <input value={s.start} onChange={(e) => setSeason(i, "start", e.target.value)} placeholder="MM-DD"
                  className="px-2 py-1.5 text-xs border border-stone-300 rounded-md" />
                <input value={s.end} onChange={(e) => setSeason(i, "end", e.target.value)} placeholder="MM-DD"
                  className="px-2 py-1.5 text-xs border border-stone-300 rounded-md" />
                <input type="number" step="0.05" value={s.factor} onChange={(e) => setSeason(i, "factor", parseFloat(e.target.value) || 1)}
                  className="px-2 py-1.5 text-xs border border-stone-300 rounded-md" />
                <button onClick={() => setCfg({ ...cfg, seasons: cfg.seasons.filter((_, j) => j !== i) })}
                  className="text-stone-400 hover:text-rose-500"><Trash size={13} /></button>
              </div>
            ))}
          </div>
        </div>

        <div className="lg:col-span-2 bg-white border border-stone-200 rounded-lg p-4" data-testid="base-curve-chart">
          <div className="flex items-center justify-between mb-2">
            <div className="text-sm font-semibold text-stone-900">Fiyat Eğrisi Önizleme ({horizon} gün)</div>
            {preview && (
              <div className="text-[11px] text-stone-500">
                Min £{preview.summary.min} · Ort £{preview.summary.avg} · Max £{preview.summary.max}
              </div>
            )}
          </div>
          <div className="h-[380px]">
            {preview && (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={preview.rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="curveFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#2563EB" stopOpacity={0.25} />
                      <stop offset="100%" stopColor="#2563EB" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e7e5e4" />
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} interval={Math.floor(horizon / 10)} />
                  <YAxis tick={{ fontSize: 10 }} width={44} domain={["auto", "auto"]} />
                  <Tooltip formatter={(v) => [`£${v}`, "Fiyat"]}
                    labelFormatter={(l) => {
                      const row = preview.rows.find((r) => r.date === l);
                      return `${l}${row?.season ? ` · ${row.season}` : ""}`;
                    }} />
                  <Area type="monotone" dataKey="price" stroke="#2563EB" strokeWidth={1.5} fill="url(#curveFill)" />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
          {cfg.applied_at && (
            <div className="mt-2 text-[11px] text-stone-500" data-testid="base-curve-applied-info">
              Son uygulama: {new Date(cfg.applied_at).toLocaleString("tr-TR")} · {cfg.applied_count} tarih · {cfg.applied_by}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function NumField({ label, value, onChange, testId, step = "1" }) {
  return (
    <div>
      <label className="block text-[10px] uppercase tracking-wider text-stone-500 mb-0.5">{label}</label>
      <input type="number" step={step} value={value ?? ""} data-testid={testId}
        onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
        className="w-full px-2 py-1.5 text-xs border border-stone-300 rounded-md" />
    </div>
  );
}

function CadenceKpi({ icon: Icon, color, label, value, testId }) {
  const colors = {
    amber: "text-amber-600 bg-amber-50", emerald: "text-emerald-600 bg-emerald-50",
    blue: "text-blue-600 bg-blue-50", violet: "text-violet-600 bg-violet-50",
  };
  return (
    <div className="bg-white border border-stone-200 rounded-lg p-3.5 flex items-center gap-3" data-testid={testId}>
      <div className={`w-9 h-9 rounded-md flex items-center justify-center ${colors[color]}`}>
        <Icon size={18} weight="fill" />
      </div>
      <div>
        <div className="text-base font-bold text-stone-900 leading-tight">{value}</div>
        <div className="text-[11px] text-stone-500">{label}</div>
      </div>
    </div>
  );
}
