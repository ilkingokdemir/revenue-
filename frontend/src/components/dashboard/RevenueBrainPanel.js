import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Brain, Target, TrendUp, Warning, GraduationCap, ArrowsClockwise, Scales,
} from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;
const BAND_TR = { "0-3": "Son 3 gün", "4-7": "4-7 gün", "8-21": "1-3 hafta", "22+": "3+ hafta" };

export default function RevenueBrainPanel({ properties = [], activePropertyId }) {
  const [propertyId, setPropertyId] = useState(activePropertyId && activePropertyId !== "all" ? activePropertyId : properties[0]?.id || "default");
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [goalInput, setGoalInput] = useState("");

  useEffect(() => {
    if (activePropertyId && activePropertyId !== "all") setPropertyId(activePropertyId);
  }, [activePropertyId]);

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/api/revenue-brain/${propertyId}/status`, { withCredentials: true });
      setData(r.data);
      if (r.data.goal?.target_revenue) setGoalInput(String(r.data.goal.target_revenue));
    } catch (e) { toast.error("Beyin durumu yüklenemedi"); }
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);

  const learnNow = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/revenue-brain/${propertyId}/learn`, {}, { withCredentials: true });
      toast.success(`Öğrenme döngüsü bitti: ${r.data.measured} sonuç ölçüldü, ${r.data.weights_updated} ağırlık, ${r.data.lessons} ders`);
      load();
    } catch (e) { toast.error("Öğrenme başarısız"); } finally { setBusy(false); }
  };

  const saveGoal = async () => {
    const v = parseFloat(goalInput);
    if (!v || v <= 0) { toast.error("Geçerli bir hedef girin"); return; }
    try {
      await axios.put(`${API}/api/revenue-brain/${propertyId}/goal`, { target_revenue: v }, { withCredentials: true });
      toast.success("Aylık gelir hedefi kaydedildi");
      load();
    } catch (e) { toast.error("Hedef kaydedilemedi"); }
  };

  if (!data) return <div className="p-8 text-sm text-stone-400">Yükleniyor…</div>;
  const g = data.goal || {};

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="revenue-brain-panel">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
            <Brain size={13} weight="fill" className="text-violet-500" />
            <span>Revenue · Kapalı Öğrenme Döngüsü</span>
          </div>
          <h1 className="text-2xl font-semibold text-stone-900">Öğrenen Revenue Beyni</h1>
          <p className="text-sm text-stone-500 mt-1 max-w-2xl">
            Her fiyat kararının gerçek sonucunu ölçer, bağlam bazlı dersler çıkarır ve motoru otomatik ayarlar. Dersler AI Stratejiste de beslenir.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {properties.length > 1 && (
            <select value={propertyId} onChange={(e) => setPropertyId(e.target.value)}
              data-testid="brain-property-select"
              className="text-xs border border-stone-300 rounded-md px-2 py-2 bg-white">
              {properties.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          )}
          <button onClick={learnNow} disabled={busy} data-testid="brain-learn-now"
            className="px-3 py-2 text-xs rounded-md bg-violet-600 text-white hover:bg-violet-700 disabled:opacity-50 inline-flex items-center gap-1.5 font-medium">
            <ArrowsClockwise size={13} className={busy ? "animate-spin" : ""} /> {busy ? "Öğreniyor…" : "Şimdi Öğren"}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
        <Kpi icon={Scales} color="violet" label="Ölçülen Karar" value={data.outcomes_measured} testId="brain-kpi-outcomes" />
        <Kpi icon={TrendUp} color="emerald" label="Başarı Oranı" value={data.success_rate != null ? `%${data.success_rate}` : "—"} testId="brain-kpi-success" />
        <Kpi icon={Warning} color="amber" label="Zarar Veren Karar" value={data.hurt} testId="brain-kpi-hurt" />
        <Kpi icon={GraduationCap} color="blue" label="Aktif Öğrenilmiş Çarpan" value={data.active_weights} testId="brain-kpi-weights" />
      </div>

      {/* Hedef kartı */}
      <div className="bg-gradient-to-r from-violet-50 to-blue-50 border border-violet-200 rounded-xl p-4 mb-5" data-testid="brain-goal-card">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Target size={18} weight="fill" className="text-violet-600" />
            <div className="text-sm font-semibold text-stone-900">Aylık Gelir Hedefi ({g.month})</div>
          </div>
          <div className="flex items-center gap-2">
            <input type="number" value={goalInput} onChange={(e) => setGoalInput(e.target.value)}
              placeholder="örn. 50000" data-testid="brain-goal-input"
              className="w-32 px-2 py-1.5 text-xs border border-stone-300 rounded-md" />
            <button onClick={saveGoal} data-testid="brain-goal-save"
              className="px-3 py-1.5 text-xs rounded-md bg-stone-900 text-white hover:bg-stone-700 font-medium">Hedefi Kaydet</button>
          </div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3 text-xs">
          <div><span className="text-stone-500">Ay içi gerçekleşen:</span> <b className="text-stone-900" data-testid="brain-mtd">£{Number(g.mtd_revenue || 0).toLocaleString("tr-TR")}</b></div>
          <div><span className="text-stone-500">Ay sonu tahmini:</span> <b className="text-stone-900" data-testid="brain-projection">£{Number(g.projection || 0).toLocaleString("tr-TR")}</b></div>
          <div><span className="text-stone-500">Hedef:</span> <b className="text-stone-900">{g.target_revenue ? `£${Number(g.target_revenue).toLocaleString("tr-TR")}` : "belirlenmedi"}</b></div>
          <div><span className="text-stone-500">İlerleme:</span> <b className={g.on_track ? "text-emerald-600" : "text-amber-600"} data-testid="brain-progress">{g.progress_pct != null ? `%${g.progress_pct}${g.on_track ? " ✓ yolda" : " ⚠ geride"}` : "—"}</b></div>
        </div>
        {g.target_revenue && (
          <div className="mt-2 h-2 bg-white rounded-full overflow-hidden border border-violet-200">
            <div className="h-full bg-gradient-to-r from-violet-500 to-blue-500 transition-all" style={{ width: `${Math.min(g.progress_pct || 0, 100)}%` }} />
          </div>
        )}
        {g.recommendation && (
          <div className="mt-3 text-xs text-violet-800 bg-white/70 border border-violet-200 rounded-lg px-3 py-2" data-testid="brain-goal-recommendation">
            🧠 {g.recommendation}
          </div>
        )}
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        {/* Dersler */}
        <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="brain-lessons">
          <div className="text-sm font-semibold text-stone-900 mb-3 flex items-center gap-2">
            <GraduationCap size={16} className="text-violet-500" /> Çıkarılan Dersler
            <span className="text-[10px] text-stone-400 font-normal">— AI Stratejiste otomatik beslenir</span>
          </div>
          {data.lessons.length === 0 ? (
            <div className="text-xs text-stone-500 py-6 text-center">Henüz ders yok — "Şimdi Öğren" ile ilk döngüyü başlatın.</div>
          ) : (
            <ul className="space-y-2">
              {data.lessons.map((l) => (
                <li key={l.id} className="text-xs text-stone-700 flex gap-2 bg-violet-50/50 border border-violet-100 rounded-lg px-3 py-2">
                  <span className="text-violet-500 font-bold shrink-0">🧠</span>{l.lesson}
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Öğrenilmiş ağırlıklar */}
        <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="brain-weights">
          <div className="text-sm font-semibold text-stone-900 mb-3 flex items-center gap-2">
            <Scales size={16} className="text-blue-500" /> Öğrenilmiş Çarpanlar (motor uygular)
          </div>
          {data.weights.length === 0 ? (
            <div className="text-xs text-stone-500 py-6 text-center">Yeterli örneklem birikince (kova başına ≥4 sonuç) çarpanlar burada belirir.</div>
          ) : (
            <table className="w-full text-xs">
              <thead><tr className="text-left text-stone-400 border-b border-stone-100">
                <th className="py-1.5">Bağlam</th><th>Örneklem</th><th>Başarı</th><th className="text-right">Çarpan</th></tr></thead>
              <tbody>
                {data.weights.map((w) => {
                  const [band, dow, dir] = w.bucket_key.split("|");
                  return (
                    <tr key={w.bucket_key} className="border-b border-stone-50" data-testid={`brain-weight-${w.bucket_key}`}>
                      <td className="py-1.5 text-stone-700">{BAND_TR[band] || band} · {dow === "weekend" ? "hafta sonu" : "hafta içi"} · {dir === "up" ? "zam ↑" : "indirim ↓"}</td>
                      <td className="text-stone-500">{w.samples}</td>
                      <td className="text-stone-500">%{Math.round(w.worked_rate * 100)}</td>
                      <td className={`text-right font-bold ${w.factor < 1 ? "text-amber-600" : w.factor > 1 ? "text-emerald-600" : "text-stone-400"}`}>×{w.factor}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Son ölçümler */}
      <div className="bg-white border border-stone-200 rounded-xl p-4 mt-4" data-testid="brain-recent">
        <div className="text-sm font-semibold text-stone-900 mb-3">Son Ölçülen Kararlar</div>
        {data.recent_outcomes.length === 0 ? (
          <div className="text-xs text-stone-500 py-4 text-center">Henüz ölçüm yok.</div>
        ) : (
          <table className="w-full text-xs">
            <thead><tr className="text-left text-stone-400 border-b border-stone-100">
              <th className="py-1.5">Konaklama</th><th>Değişim</th><th>Nihai Doluluk</th><th>Baseline</th><th className="text-right">Sonuç</th></tr></thead>
            <tbody>
              {data.recent_outcomes.map((o) => (
                <tr key={o.id} className="border-b border-stone-50">
                  <td className="py-1.5 text-stone-700">{o.stay_date} <span className="text-stone-400">({o.band}, {o.dow_type === "weekend" ? "hs" : "hi"})</span></td>
                  <td className={o.direction === "up" ? "text-emerald-600" : "text-amber-600"}>{o.delta_pct > 0 ? "+" : ""}{o.delta_pct}%</td>
                  <td className="text-stone-700">%{o.final_occ}</td>
                  <td className="text-stone-500">%{o.baseline_occ}</td>
                  <td className="text-right">
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${o.verdict === "worked" ? "bg-emerald-100 text-emerald-700" : o.verdict === "hurt" ? "bg-rose-100 text-rose-700" : "bg-stone-100 text-stone-600"}`}>
                      {o.verdict === "worked" ? "İşe yaradı" : o.verdict === "hurt" ? "Zarar verdi" : "Nötr"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function Kpi({ icon: Icon, color, label, value, testId }) {
  const colors = {
    violet: "text-violet-600 bg-violet-50", emerald: "text-emerald-600 bg-emerald-50",
    amber: "text-amber-600 bg-amber-50", blue: "text-blue-600 bg-blue-50",
  };
  return (
    <div className="bg-white border border-stone-200 rounded-lg p-3.5 flex items-center gap-3" data-testid={testId}>
      <div className={`w-9 h-9 rounded-md flex items-center justify-center ${colors[color]}`}>
        <Icon size={18} weight="fill" />
      </div>
      <div>
        <div className="text-lg font-bold text-stone-900 leading-tight">{value}</div>
        <div className="text-[11px] text-stone-500">{label}</div>
      </div>
    </div>
  );
}
