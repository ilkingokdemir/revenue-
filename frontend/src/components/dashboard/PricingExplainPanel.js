import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Sparkle,
  ArrowsClockwise,
  TrendUp,
  TrendDown,
  CheckCircle,
  XCircle,
  PencilSimple,
  Brain,
  Warning,
  Lightning,
  Plus,
  Trash,
} from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

export default function PricingExplainPanel({ propertyId }) {
  const [stats, setStats] = useState(null);
  const [history, setHistory] = useState([]);
  const [tab, setTab] = useState("new"); // new | history
  const [loading, setLoading] = useState(false);

  const reload = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const [s, h] = await Promise.all([
        axios.get(`${API}/api/pricing/explain/dashboard/${propertyId}`, { withCredentials: true }),
        axios.get(`${API}/api/pricing/explain/history/${propertyId}?limit=50`, { withCredentials: true }),
      ]);
      setStats(s.data);
      setHistory(h.data.items || []);
    } catch (e) {
      toast.error("Veri yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [propertyId]);

  useEffect(() => { reload(); }, [reload]);

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="pricing-explain-panel">
      <div className="mb-5">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          <Brain size={12} weight="fill" className="text-violet-500" />
          <span>Revenue Management · AI Açıklayıcı</span>
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">Fiyat Önerisi Açıklayıcı</h1>
        <p className="text-sm text-stone-500 mt-1 max-w-2xl">
          AI bir fiyat önerdi. <b>Neden?</b> 5 sn'de doğal dilde cevap, sürücü kırılımı, alternatif senaryolar.
        </p>
      </div>

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-6 gap-3 mb-5" data-testid="pe-stats">
          <Kpi label="Toplam Açıklama" value={stats.total} color="stone" />
          <Kpi label="Bekleyen" value={stats.pending} color="amber" />
          <Kpi label="Onay Oranı" value={`%${stats.accept_rate_pct}`} color="emerald" />
          <Kpi label="Override" value={stats.overridden} color="violet" />
          <Kpi label="Ort. Güven" value={`%${stats.avg_confidence}`} color="cyan" />
          <Kpi label="Ort. |Δ|" value={`%${stats.avg_abs_delta_pct}`} color="sky" />
        </div>
      )}

      <div className="flex items-center gap-2 mb-4">
        <button
          onClick={() => setTab("new")}
          data-testid="pe-tab-new"
          className={`px-3 py-1.5 text-xs rounded-md ${tab === "new" ? "bg-violet-600 text-white" : "bg-stone-100 text-stone-600 hover:bg-stone-200"}`}
        >
          + Yeni Açıklama
        </button>
        <button
          onClick={() => setTab("history")}
          data-testid="pe-tab-history"
          className={`px-3 py-1.5 text-xs rounded-md ${tab === "history" ? "bg-violet-600 text-white" : "bg-stone-100 text-stone-600 hover:bg-stone-200"}`}
        >
          Geçmiş ({history.length})
        </button>
        <button onClick={reload} className="ml-auto px-3 py-1.5 text-xs rounded-md border border-stone-200 text-stone-600 hover:bg-stone-50 inline-flex items-center gap-1.5">
          <ArrowsClockwise size={12} /> Yenile
        </button>
      </div>

      {tab === "new" && <ExplainForm propertyId={propertyId} onCreated={() => { reload(); setTab("history"); }} />}
      {tab === "history" && (
        <HistoryList items={history} loading={loading} onChanged={reload} />
      )}
    </div>
  );
}

function Kpi({ label, value, color }) {
  const bg = {
    stone: "bg-stone-100 text-stone-700",
    amber: "bg-amber-50 text-amber-700",
    emerald: "bg-emerald-50 text-emerald-700",
    violet: "bg-violet-50 text-violet-700",
    cyan: "bg-cyan-50 text-cyan-700",
    sky: "bg-sky-50 text-sky-700",
  }[color];
  return (
    <div className={`${bg} border border-stone-100 rounded-lg p-3`}>
      <div className="text-[10px] uppercase tracking-wider opacity-70">{label}</div>
      <div className="text-xl font-semibold mt-1">{value}</div>
    </div>
  );
}

function ExplainForm({ propertyId, onCreated }) {
  const [form, setForm] = useState({
    room_type: "Standard",
    target_date: new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 10),
    current_rate: 1500,
    proposed_rate: 1750,
    occupancy_pct: 78,
    pace_lead_30d: 0.12,
    demand_signals_text: "Hafta sonu, arama hacmi ↑",
    events_text: "Konser - 22:00 Stadyum",
    notes: "",
  });
  const [comp, setComp] = useState([{ name: "Rakip A", rate: 1700 }, { name: "Rakip B", rate: 1820 }]);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  const submit = async () => {
    setBusy(true);
    setResult(null);
    try {
      const payload = {
        property_id: propertyId,
        room_type: form.room_type,
        target_date: form.target_date,
        current_rate: parseFloat(form.current_rate),
        proposed_rate: parseFloat(form.proposed_rate),
        occupancy_pct: parseFloat(form.occupancy_pct),
        pace_lead_30d: form.pace_lead_30d ? parseFloat(form.pace_lead_30d) : null,
        demand_signals: form.demand_signals_text.split(",").map((s) => s.trim()).filter(Boolean),
        events: form.events_text.split(",").map((s) => s.trim()).filter(Boolean),
        comp_set: comp.filter((c) => c.name && c.rate).map((c) => ({ name: c.name, rate: parseFloat(c.rate) })),
        notes: form.notes || null,
      };
      const r = await axios.post(`${API}/api/pricing/explain`, payload, { withCredentials: true });
      setResult(r.data);
      toast.success("AI açıklamayı oluşturdu");
      onCreated?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Hata");
    } finally {
      setBusy(false);
    }
  };

  if (result) {
    return <ResultCard exp={result} onClose={() => setResult(null)} />;
  }

  return (
    <div className="bg-white border border-stone-200 rounded-xl p-5 space-y-4" data-testid="pe-form">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Field label="Oda Tipi">
          <input value={form.room_type} onChange={(e) => setForm({ ...form, room_type: e.target.value })}
            data-testid="pe-room-type" className="w-full px-2 py-1.5 text-sm border border-stone-200 rounded" />
        </Field>
        <Field label="Tarih">
          <input type="date" value={form.target_date} onChange={(e) => setForm({ ...form, target_date: e.target.value })}
            data-testid="pe-target-date" className="w-full px-2 py-1.5 text-sm border border-stone-200 rounded" />
        </Field>
        <Field label="Mevcut Fiyat">
          <input type="number" value={form.current_rate} onChange={(e) => setForm({ ...form, current_rate: e.target.value })}
            data-testid="pe-current-rate" className="w-full px-2 py-1.5 text-sm border border-stone-200 rounded" />
        </Field>
        <Field label="Önerilen Fiyat">
          <input type="number" value={form.proposed_rate} onChange={(e) => setForm({ ...form, proposed_rate: e.target.value })}
            data-testid="pe-proposed-rate" className="w-full px-2 py-1.5 text-sm border border-stone-200 rounded" />
        </Field>
        <Field label="Doluluk %">
          <input type="number" min="0" max="100" value={form.occupancy_pct} onChange={(e) => setForm({ ...form, occupancy_pct: e.target.value })}
            data-testid="pe-occupancy" className="w-full px-2 py-1.5 text-sm border border-stone-200 rounded" />
        </Field>
        <Field label="Pace 30g (oran)">
          <input type="number" step="0.01" value={form.pace_lead_30d} onChange={(e) => setForm({ ...form, pace_lead_30d: e.target.value })}
            data-testid="pe-pace" className="w-full px-2 py-1.5 text-sm border border-stone-200 rounded" />
        </Field>
        <Field label="Talep Sinyalleri (virgülle)">
          <input value={form.demand_signals_text} onChange={(e) => setForm({ ...form, demand_signals_text: e.target.value })}
            data-testid="pe-demand" className="w-full px-2 py-1.5 text-sm border border-stone-200 rounded" />
        </Field>
        <Field label="Etkinlikler (virgülle)">
          <input value={form.events_text} onChange={(e) => setForm({ ...form, events_text: e.target.value })}
            data-testid="pe-events" className="w-full px-2 py-1.5 text-sm border border-stone-200 rounded" />
        </Field>
      </div>

      <div>
        <div className="flex items-center justify-between mb-2">
          <div className="text-xs font-semibold text-stone-700">Comp Set</div>
          <button
            onClick={() => setComp([...comp, { name: "", rate: "" }])}
            data-testid="pe-add-comp"
            className="text-xs px-2 py-1 rounded bg-stone-100 hover:bg-stone-200 inline-flex items-center gap-1"
          >
            <Plus size={10} /> Ekle
          </button>
        </div>
        <div className="space-y-1.5">
          {comp.map((c, i) => (
            <div key={i} className="flex items-center gap-2">
              <input
                placeholder="Otel adı"
                value={c.name}
                onChange={(e) => setComp(comp.map((x, idx) => idx === i ? { ...x, name: e.target.value } : x))}
                data-testid={`pe-comp-name-${i}`}
                className="flex-1 px-2 py-1 text-sm border border-stone-200 rounded"
              />
              <input
                placeholder="Fiyat"
                type="number"
                value={c.rate}
                onChange={(e) => setComp(comp.map((x, idx) => idx === i ? { ...x, rate: e.target.value } : x))}
                data-testid={`pe-comp-rate-${i}`}
                className="w-28 px-2 py-1 text-sm border border-stone-200 rounded"
              />
              <button onClick={() => setComp(comp.filter((_, idx) => idx !== i))} className="w-7 h-7 rounded bg-rose-50 text-rose-500 inline-flex items-center justify-center">
                <Trash size={12} />
              </button>
            </div>
          ))}
        </div>
      </div>

      <Field label="Not (opsiyonel)">
        <textarea
          value={form.notes}
          onChange={(e) => setForm({ ...form, notes: e.target.value })}
          rows={2}
          data-testid="pe-notes"
          className="w-full px-2 py-1.5 text-sm border border-stone-200 rounded"
        />
      </Field>

      <button
        onClick={submit}
        disabled={busy}
        data-testid="pe-submit"
        className="w-full py-3 rounded-md bg-violet-600 text-white font-semibold hover:bg-violet-700 disabled:opacity-50 inline-flex items-center justify-center gap-2"
      >
        <Sparkle size={14} weight="fill" />
        {busy ? "AI Düşünüyor…" : "AI ile Açıkla"}
      </button>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <label className="block">
      <div className="text-[10px] uppercase tracking-wider text-stone-500 mb-1">{label}</div>
      {children}
    </label>
  );
}

function ResultCard({ exp, onClose }) {
  return (
    <div className="bg-white border border-violet-200 rounded-xl p-5 space-y-4" data-testid="pe-result">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[10px] uppercase tracking-wider text-violet-600 mb-1">AI Açıklaması</div>
          <div className="text-xl font-semibold text-stone-900">
            {exp.room_type} · {exp.target_date} · {exp.current_rate} → <span className="text-violet-600">{exp.proposed_rate}</span>
            <span className={`ml-2 text-sm ${exp.delta_pct >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
              ({exp.delta_pct >= 0 ? "+" : ""}{exp.delta_pct}%)
            </span>
          </div>
        </div>
        <ConfidenceRing value={exp.confidence} />
      </div>

      <div className="bg-violet-50 border border-violet-100 rounded-lg p-3 text-sm text-stone-800 leading-relaxed">
        {exp.narrative || "—"}
      </div>

      {exp.key_drivers?.length > 0 && (
        <div>
          <div className="text-[10px] uppercase tracking-wider text-stone-500 mb-2">Sürücüler</div>
          <div className="space-y-1.5">
            {exp.key_drivers.map((d, i) => <DriverBar key={i} driver={d} />)}
          </div>
        </div>
      )}

      {exp.risks?.length > 0 && (
        <div>
          <div className="text-[10px] uppercase tracking-wider text-stone-500 mb-2">Riskler</div>
          <div className="space-y-1">
            {exp.risks.map((r, i) => (
              <div key={i} className="flex items-start gap-2 text-xs text-amber-800 bg-amber-50 border border-amber-100 rounded px-2 py-1">
                <Warning size={12} className="mt-0.5" /> {r}
              </div>
            ))}
          </div>
        </div>
      )}

      {exp.alternative_rates?.length > 0 && (
        <div>
          <div className="text-[10px] uppercase tracking-wider text-stone-500 mb-2">Alternatif Senaryolar</div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {exp.alternative_rates.map((a, i) => (
              <div key={i} className="border border-stone-200 rounded-lg p-3" data-testid={`pe-alt-${i}`}>
                <div className="text-lg font-bold text-stone-900">{a.rate}</div>
                <div className="text-xs text-stone-600">{a.scenario}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {exp.id && !exp.decision && (
        <DecisionRow expId={exp.id} proposedRate={exp.proposed_rate} currentRate={exp.current_rate} onDone={onClose} />
      )}
      {exp.decision && (
        <div className="text-center text-sm text-stone-500">
          Karar verildi: <b>{exp.decision}</b> @ <b>{exp.decision_rate}</b>
        </div>
      )}
    </div>
  );
}

function ConfidenceRing({ value }) {
  const v = Math.max(0, Math.min(100, value || 0));
  const color = v >= 75 ? "#10b981" : v >= 50 ? "#f59e0b" : "#ef4444";
  return (
    <div className="relative w-16 h-16 shrink-0">
      <svg viewBox="0 0 36 36" className="w-full h-full -rotate-90">
        <circle cx="18" cy="18" r="15.9" fill="none" stroke="#e7e5e4" strokeWidth="2.5" />
        <circle cx="18" cy="18" r="15.9" fill="none" stroke={color} strokeWidth="2.5"
          strokeDasharray={`${v}, 100`} strokeLinecap="round" />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <div className="text-sm font-bold text-stone-900">{v}</div>
        <div className="text-[8px] text-stone-500 uppercase tracking-wider">güven</div>
      </div>
    </div>
  );
}

function DriverBar({ driver }) {
  const { label, weight, direction } = driver;
  const w = Math.max(0, Math.min(100, weight));
  const Icon = direction === "up" ? TrendUp : direction === "down" ? TrendDown : Lightning;
  const color = direction === "up" ? "bg-emerald-500" : direction === "down" ? "bg-rose-500" : "bg-stone-400";
  const text = direction === "up" ? "text-emerald-700" : direction === "down" ? "text-rose-700" : "text-stone-700";
  return (
    <div className="flex items-center gap-3" data-testid="pe-driver">
      <div className={`w-7 h-7 rounded ${color} bg-opacity-15 inline-flex items-center justify-center`}>
        <Icon size={12} className={text} weight="bold" />
      </div>
      <div className="flex-1">
        <div className="flex items-center justify-between text-xs mb-0.5">
          <span className="text-stone-700">{label}</span>
          <span className={`font-mono ${text}`}>%{w}</span>
        </div>
        <div className="h-1.5 bg-stone-100 rounded overflow-hidden">
          <div className={`h-full ${color}`} style={{ width: `${w}%` }} />
        </div>
      </div>
    </div>
  );
}

function DecisionRow({ expId, proposedRate, currentRate, onDone }) {
  const [overrideRate, setOverrideRate] = useState(proposedRate);
  const [busy, setBusy] = useState(false);
  const [showOverride, setShowOverride] = useState(false);

  const send = async (decision, finalRate = null) => {
    setBusy(true);
    try {
      await axios.post(`${API}/api/pricing/explain/${expId}/decision`, {
        decision,
        final_rate: finalRate,
      }, { withCredentials: true });
      const labels = { accept: "Kabul edildi", reject: "Reddedildi", override: "Override uygulandı" };
      toast.success(labels[decision]);
      onDone?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Hata");
    } finally {
      setBusy(false);
    }
  };

  if (showOverride) {
    return (
      <div className="border-t border-stone-100 pt-4 flex items-center gap-2">
        <input
          type="number"
          value={overrideRate}
          onChange={(e) => setOverrideRate(e.target.value)}
          data-testid="pe-override-rate"
          className="w-32 px-2 py-1.5 text-sm border border-stone-200 rounded"
        />
        <button
          onClick={() => send("override", parseFloat(overrideRate))}
          disabled={busy}
          data-testid="pe-confirm-override"
          className="px-3 py-1.5 text-sm bg-violet-600 text-white rounded font-semibold hover:bg-violet-700 disabled:opacity-50"
        >
          Override Uygula
        </button>
        <button onClick={() => setShowOverride(false)} className="px-3 py-1.5 text-sm bg-stone-100 text-stone-600 rounded">
          İptal
        </button>
      </div>
    );
  }

  return (
    <div className="border-t border-stone-100 pt-4 grid grid-cols-3 gap-2">
      <button
        onClick={() => send("accept", proposedRate)}
        disabled={busy}
        data-testid="pe-accept"
        className="py-2 rounded-md bg-emerald-500 text-white text-sm font-semibold hover:bg-emerald-600 disabled:opacity-50 inline-flex items-center justify-center gap-1.5"
      >
        <CheckCircle size={14} weight="fill" /> Kabul ({proposedRate})
      </button>
      <button
        onClick={() => send("reject", currentRate)}
        disabled={busy}
        data-testid="pe-reject"
        className="py-2 rounded-md bg-rose-500 text-white text-sm font-semibold hover:bg-rose-600 disabled:opacity-50 inline-flex items-center justify-center gap-1.5"
      >
        <XCircle size={14} weight="fill" /> Reddet ({currentRate})
      </button>
      <button
        onClick={() => setShowOverride(true)}
        disabled={busy}
        data-testid="pe-show-override"
        className="py-2 rounded-md bg-violet-100 text-violet-700 text-sm font-semibold hover:bg-violet-200 disabled:opacity-50 inline-flex items-center justify-center gap-1.5"
      >
        <PencilSimple size={14} weight="fill" /> Override
      </button>
    </div>
  );
}

function HistoryList({ items, loading, onChanged }) {
  const [openId, setOpenId] = useState(null);
  if (loading) return <div className="text-sm text-stone-400">Yükleniyor…</div>;
  if (!items.length) {
    return (
      <div className="text-center py-12 text-stone-400 text-sm" data-testid="pe-empty">
        Henüz açıklama yok. "Yeni Açıklama" sekmesinden başlayın.
      </div>
    );
  }
  return (
    <div className="space-y-2" data-testid="pe-history">
      {items.map((e) => (
        <div key={e.id} className="bg-white border border-stone-200 rounded-lg" data-testid={`pe-row-${e.id}`}>
          <button
            onClick={() => setOpenId(openId === e.id ? null : e.id)}
            className="w-full p-3 text-left flex items-center gap-3"
          >
            <div className="flex-1 min-w-0">
              <div className="text-sm font-semibold text-stone-900 truncate">
                {e.room_type} · {e.target_date} · {e.current_rate} → {e.proposed_rate}
                <span className={`ml-2 text-xs ${e.delta_pct >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
                  ({e.delta_pct >= 0 ? "+" : ""}{e.delta_pct}%)
                </span>
              </div>
              <div className="text-[10px] text-stone-400">{e.created_at?.slice(0, 16).replace("T", " ")} · güven %{e.confidence}</div>
            </div>
            <div>
              {e.decision === "accept" && <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 font-bold">KABUL</span>}
              {e.decision === "reject" && <span className="text-[10px] px-1.5 py-0.5 rounded bg-rose-100 text-rose-700 font-bold">RED</span>}
              {e.decision === "override" && <span className="text-[10px] px-1.5 py-0.5 rounded bg-violet-100 text-violet-700 font-bold">OVERRIDE</span>}
              {!e.decision && <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 font-bold">BEKLEME</span>}
            </div>
          </button>
          {openId === e.id && (
            <div className="border-t border-stone-100 p-3">
              <ResultCard exp={e} onClose={onChanged} />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
