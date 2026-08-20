import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";

const API = process.env.REACT_APP_BACKEND_URL;
const OPTS = [
  ["balanced", "⚖️ Dengeli"], ["high_season", "🔥 Yoğun Sezon"],
  ["low_occupancy", "🌙 Düşük Doluluk"], ["group_heavy", "👥 Grup Ağırlıklı"],
];
const label = (k) => (OPTS.find((o) => o[0] === k) || ["", k])[1];
const fmt = (v, c) => `${c === "CHF" ? "CHF" : c === "GBP" ? "£" : c === "EUR" ? "€" : c} ${Math.round(v).toLocaleString("tr-TR")}`;

export const ScenarioComparePanel = ({ propertyId, onClose }) => {
  const [a, setA] = useState("high_season");
  const [b, setB] = useState("low_occupancy");
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [applyInfo, setApplyInfo] = useState(null);
  const [history, setHistory] = useState([]);

  const loadHistory = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/api/demo-seeder/apply-scenario/${propertyId}/history`);
      setHistory(r.data.batches || []);
    } catch { /* ignore */ }
  }, [propertyId]);
  useEffect(() => { loadHistory(); }, [loadHistory]);

  const revertBatch = async (batchId) => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/demo-seeder/apply-scenario/${propertyId}/revert`, { batch_id: batchId });
      toast.success(`${r.data.restored} fiyat geri alındı — önceki durumuna döndü ↩️`);
      loadHistory();
    } catch (e) { toast.error(e.response?.data?.detail || "Geri alınamadı"); }
    finally { setBusy(false); }
  };

  const winner = data ? (data.a.total_rev >= data.b.total_rev ? data.a.scenario : data.b.scenario) : null;

  const applyWinner = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/demo-seeder/apply-scenario/${propertyId}`, { scenario: winner });
      setApplyInfo(r.data);
      toast.info(`${r.data.suggestions} fiyat önerisi hazırlandı — onayınızı bekliyor`);
    } catch (e) { toast.error(e.response?.data?.detail || "Öneri oluşturulamadı"); }
    finally { setBusy(false); }
  };

  const confirmApply = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/demo-seeder/apply-scenario/${propertyId}/confirm`, { batch_id: applyInfo.batch_id });
      toast.success(`${r.data.applied} günlük fiyat RMS'e uygulandı ✅ (${label(r.data.scenario)})`);
      setApplyInfo(null);
      loadHistory();
    } catch (e) { toast.error(e.response?.data?.detail || "Uygulanamadı"); }
    finally { setBusy(false); }
  };

  const run = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/demo-seeder/compare/${propertyId}?a=${a}&b=${b}`);
      setData(r.data);
    } catch (e) { toast.error(e.response?.data?.detail || "Karşılaştırılamadı"); }
    finally { setBusy(false); }
  };

  const maxRev = data ? Math.max(1, ...data.a.daily_rev, ...data.b.daily_rev) : 1;

  return (
    <div className="fixed inset-0 z-[85] flex items-center justify-center bg-black/60 p-4" data-testid="scenario-compare-modal" onClick={onClose}>
      <div className="w-full max-w-3xl bg-white rounded-2xl shadow-2xl p-5 max-h-[90vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2 mb-3">
          <h2 className="flex-1 text-base font-black text-stone-900">⚖️ Senaryo Karşılaştırma — 30 günlük simülasyon</h2>
          <button onClick={onClose} data-testid="scenario-compare-close" className="text-stone-400 hover:text-stone-700 text-lg font-bold">✕</button>
        </div>
        <div className="flex flex-wrap items-center gap-2 mb-4">
          <select value={a} onChange={(e) => setA(e.target.value)} data-testid="scenario-a-select"
            className="border border-indigo-300 bg-indigo-50 rounded-lg px-2.5 py-2 text-xs font-bold text-indigo-800">
            {OPTS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
          <span className="text-xs font-black text-stone-400">vs</span>
          <select value={b} onChange={(e) => setB(e.target.value)} data-testid="scenario-b-select"
            className="border border-amber-300 bg-amber-50 rounded-lg px-2.5 py-2 text-xs font-bold text-amber-800">
            {OPTS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
          <button onClick={run} disabled={busy || a === b} data-testid="scenario-compare-run"
            className="px-4 py-2 rounded-lg bg-stone-900 text-white text-xs font-black disabled:opacity-40">
            {busy ? "Hesaplanıyor..." : "Karşılaştır →"}
          </button>
          {a === b && <span className="text-[10px] text-rose-500 font-bold">Farklı iki senaryo seçin</span>}
          <span className="text-[10px] text-stone-400">Veritabanına yazılmaz — anlık simülasyon</span>
        </div>

        {data && (
          <div className="space-y-4" data-testid="scenario-compare-result">
            <div className="flex flex-wrap items-center gap-2 bg-emerald-50 border border-emerald-200 rounded-xl px-3 py-2">
              <span className="text-sm">🏆</span>
              <span className="flex-1 min-w-[180px] text-xs font-bold text-emerald-800">
                Kazanan: <b>{label(winner)}</b> — {fmt(Math.abs(data.a.total_rev - data.b.total_rev), data.currency)} daha fazla gelir
              </span>
              {!applyInfo ? (
                <button onClick={applyWinner} disabled={busy} data-testid="scenario-apply-btn"
                  className="px-3 py-1.5 rounded-lg bg-emerald-600 text-white text-xs font-black hover:bg-emerald-700 disabled:opacity-50">
                  Kazananı RMS'e Aktar →
                </button>
              ) : (
                <div className="flex items-center gap-2" data-testid="scenario-apply-preview">
                  <span className="text-[11px] text-stone-600">
                    {applyInfo.suggestions} öneri · {applyInfo.days} gün · {applyInfo.rooms} oda tipi · ort. değişim <b className={applyInfo.avg_change_pct >= 0 ? "text-emerald-700" : "text-rose-600"}>%{applyInfo.avg_change_pct}</b>
                  </span>
                  <button onClick={confirmApply} disabled={busy} data-testid="scenario-confirm-btn"
                    className="px-3 py-1.5 rounded-lg bg-stone-900 text-white text-xs font-black disabled:opacity-50">Onayla ve Fiyatlara Uygula ✓</button>
                  <button onClick={() => setApplyInfo(null)} data-testid="scenario-apply-cancel"
                    className="px-2 py-1.5 rounded-lg text-[11px] font-bold text-stone-500 hover:bg-stone-100">Vazgeç</button>
                </div>
              )}
            </div>

            <div className="grid grid-cols-3 gap-2">
              {[["Toplam Gelir (30g)", fmt(data.a.total_rev, data.currency), fmt(data.b.total_rev, data.currency),
                 data.a.total_rev - data.b.total_rev, (v) => fmt(Math.abs(v), data.currency)],
                ["Ort. Doluluk", `%${data.a.avg_occ_pct}`, `%${data.b.avg_occ_pct}`,
                 data.a.avg_occ_pct - data.b.avg_occ_pct, (v) => `%${Math.abs(v).toFixed(1)}`],
                ["ADR", fmt(data.a.adr, data.currency), fmt(data.b.adr, data.currency),
                 data.a.adr - data.b.adr, (v) => fmt(Math.abs(v), data.currency)]].map(([l, va, vb, delta, df]) => (
                <div key={l} className="bg-stone-50 border border-stone-200 rounded-xl p-3">
                  <div className="text-[10px] font-bold text-stone-500 uppercase mb-1">{l}</div>
                  <div className="text-xs"><span className="font-black text-indigo-700">{va}</span>
                    <span className="text-stone-400 mx-1">vs</span>
                    <span className="font-black text-amber-700">{vb}</span></div>
                  <div className={`text-[10px] font-black mt-0.5 ${delta >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
                    {delta >= 0 ? "▲" : "▼"} {df(delta)} fark
                  </div>
                </div>
              ))}
            </div>

            <div className="bg-stone-50 border border-stone-200 rounded-xl p-3">
              <div className="text-[11px] font-black text-stone-600 uppercase mb-2">Günlük Gelir — {label(a)} vs {label(b)}</div>
              <div className="flex items-end gap-[2px] h-32">
                {data.days.map((d, i) => (
                  <div key={d} className="flex-1 h-full flex items-end gap-[1px]" title={`${d}: ${fmt(data.a.daily_rev[i], data.currency)} vs ${fmt(data.b.daily_rev[i], data.currency)}`}>
                    <div className="flex-1 bg-indigo-500 rounded-t-sm" style={{ height: `${(data.a.daily_rev[i] / maxRev) * 100}%`, minHeight: data.a.daily_rev[i] ? 2 : 0 }} />
                    <div className="flex-1 bg-amber-400 rounded-t-sm" style={{ height: `${(data.b.daily_rev[i] / maxRev) * 100}%`, minHeight: data.b.daily_rev[i] ? 2 : 0 }} />
                  </div>
                ))}
              </div>
              <div className="flex justify-between text-[9px] text-stone-400 mt-1">
                <span>{data.days[0]}</span><span>{data.days[14]}</span><span>{data.days[29]}</span>
              </div>
            </div>

            <div className="bg-stone-50 border border-stone-200 rounded-xl p-3">
              <div className="text-[11px] font-black text-stone-600 uppercase mb-2">Günlük Doluluk %</div>
              <svg viewBox="0 0 300 60" className="w-full h-20" preserveAspectRatio="none">
                <polyline fill="none" stroke="#6366f1" strokeWidth="1.6"
                  points={data.a.daily_occ_pct.map((v, i) => `${(i / 29) * 300},${60 - (v / 100) * 58}`).join(" ")} />
                <polyline fill="none" stroke="#f59e0b" strokeWidth="1.6"
                  points={data.b.daily_occ_pct.map((v, i) => `${(i / 29) * 300},${60 - (v / 100) * 58}`).join(" ")} />
              </svg>
              <div className="flex gap-3 text-[10px] text-stone-500">
                <span><span className="inline-block w-2 h-2 bg-indigo-500 rounded-sm mr-1" />{label(a)}</span>
                <span><span className="inline-block w-2 h-2 bg-amber-400 rounded-sm mr-1" />{label(b)}</span>
              </div>
            </div>
          </div>
        )}

        {/* Öneri Geçmişi */}
        {history.length > 0 && (
          <div className="mt-4 bg-stone-50 border border-stone-200 rounded-xl p-3" data-testid="scenario-history">
            <div className="text-[11px] font-black text-stone-600 uppercase mb-2">📜 Öneri Geçmişi — kim, ne zaman, ne oldu</div>
            <div className="space-y-1.5 max-h-48 overflow-auto">
              {history.map((h) => (
                <div key={h.id} className="flex flex-wrap items-center gap-2 bg-white border border-stone-200 rounded-lg px-2.5 py-1.5" data-testid={`scenario-history-row-${h.id}`}>
                  <span className="text-xs font-bold text-stone-800">{label(h.scenario)}</span>
                  <span className="text-[10px] text-stone-500">{h.item_count} fiyat</span>
                  <span className="flex-1 text-[10px] text-stone-400 min-w-[160px]">
                    {h.status === "applied" && `✓ ${h.applied_by || "?"} onayladı · ${new Date(h.applied_at).toLocaleString("tr-TR")}`}
                    {h.status === "reverted" && `↩ ${h.reverted_by || "?"} geri aldı · ${new Date(h.reverted_at).toLocaleString("tr-TR")}`}
                    {h.status === "pending" && `⏳ ${h.created_by || "?"} oluşturdu · ${new Date(h.created_at).toLocaleString("tr-TR")}`}
                  </span>
                  <span className={`px-2 py-0.5 rounded-full text-[9px] font-black border ${
                    h.status === "applied" ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                    : h.status === "reverted" ? "bg-stone-100 text-stone-500 border-stone-300"
                    : "bg-amber-50 text-amber-700 border-amber-200"}`}>
                    {h.status === "applied" ? "UYGULANDI" : h.status === "reverted" ? "GERİ ALINDI" : "BEKLİYOR"}
                  </span>
                  {h.status === "applied" && (
                    <button onClick={() => revertBatch(h.id)} disabled={busy} data-testid={`scenario-revert-${h.id}`}
                      className="px-2 py-1 rounded-lg border border-rose-300 text-[10px] font-bold text-rose-600 hover:bg-rose-50 disabled:opacity-50">
                      ↩ Geri Al
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ScenarioComparePanel;
