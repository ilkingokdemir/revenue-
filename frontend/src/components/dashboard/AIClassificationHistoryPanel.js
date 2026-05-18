/**
 * AIClassificationHistoryPanel
 * ─────────────────────────────────────────────────────────────────────────
 * iter 322 — AI-driven `property_type` değişikliklerinin denetimi ve geri
 * alınması için admin paneli.
 *
 * Backend:
 *   GET  /api/revenue/market-robot/ai-classification-history?days=30&limit=100
 *   POST /api/revenue/market-robot/{property_id}/ai-classification-rollback
 *        body: {} (auto-rollback to previous_type) or {target_type: "<x>"}
 *
 * Her satırda mevcut tip, önceki tip, AI güven skoru, gerekçe, tarih ve
 * rollback butonu gösterilir. Rollback dialog'unda admin ya kayıtlı önceki
 * değere döner ya da manuel olarak istediği değeri seçer.
 */
import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, Undo2, Brain, RefreshCw } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const VALID_TYPES = ["hotel", "apartment", "serviced_apartment", "aparthotel",
                     "guesthouse", "bnb", "hostel"];

export default function AIClassificationHistoryPanel() {
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState([]);
  const [days, setDays] = useState(30);
  const [rollbackTarget, setRollbackTarget] = useState(null);  // {property_id, name, current, suggested}
  const [rollbackType, setRollbackType] = useState("");
  const [rollingBack, setRollingBack] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(
        `${API}/revenue/market-robot/ai-classification-history?days=${days}&limit=100`,
      );
      setItems(data?.items || []);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "History yüklenemedi");
    }
    setLoading(false);
  }, [days]);

  useEffect(() => { load(); }, [load]);

  const openRollback = (item) => {
    setRollbackTarget(item);
    setRollbackType(item.previous_type || "hotel");
  };

  const doRollback = async () => {
    if (!rollbackTarget) return;
    setRollingBack(true);
    try {
      const body = rollbackTarget.rollback_available && rollbackType === rollbackTarget.previous_type
        ? {}
        : { target_type: rollbackType };
      const { data } = await axios.post(
        `${API}/revenue/market-robot/${rollbackTarget.property_id}/ai-classification-rollback`,
        body,
      );
      if (data?.no_op) {
        toast.warning(data.message || "Hedef değer mevcutla aynı");
      } else {
        toast.success(`${rollbackTarget.name}: ${data.previous_type} → ${data.current_type}`);
        setRollbackTarget(null);
        await load();
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Rollback başarısız");
    }
    setRollingBack(false);
  };

  return (
    <div className="space-y-4" data-testid="ai-classification-history-panel">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h3 className="text-lg font-bold text-stone-100 flex items-center gap-2">
            <Brain className="w-5 h-5 text-violet-400" />
            AI Sınıflandırma Geçmişi · Audit & Rollback
          </h3>
          <p className="text-xs text-stone-500 mt-0.5">
            GPT-4o-mini'nin <code className="bg-stone-950 px-1 rounded text-violet-300">property_type</code> alanında yaptığı tüm değişiklikler.
            Tek tıkla geri alabilirsiniz.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={days}
            onChange={e => setDays(Number(e.target.value))}
            data-testid="history-days-select"
            className="bg-stone-900 border border-stone-700 rounded px-2 py-1.5 text-xs text-stone-200"
            disabled={loading}
          >
            <option value={7}>Son 7 gün</option>
            <option value={30}>Son 30 gün</option>
            <option value={90}>Son 90 gün</option>
            <option value={0}>Tüm zamanlar</option>
          </select>
          <button
            onClick={load}
            disabled={loading}
            data-testid="history-refresh-btn"
            className="px-3 py-1.5 bg-stone-800 hover:bg-stone-700 text-stone-200 text-xs font-bold rounded flex items-center gap-1.5 disabled:opacity-50"
          >
            {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
            Yenile
          </button>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-12 text-stone-500">
          <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2" />
          Yükleniyor…
        </div>
      ) : items.length === 0 ? (
        <div className="text-center py-12 text-stone-500 bg-stone-900/40 border border-stone-800 rounded-2xl">
          <Brain className="w-8 h-8 mx-auto mb-2 opacity-40" />
          <p>Bu dönemde AI sınıflandırma kaydı yok.</p>
          <p className="text-[11px] mt-2">Market Robot panelinden "🧠 AI Tip Sınıflandır" çalıştırın.</p>
        </div>
      ) : (
        <div className="overflow-x-auto" data-testid="history-table">
          <table className="w-full text-sm">
            <thead className="text-[11px] uppercase tracking-wider text-stone-500 border-b border-stone-800">
              <tr>
                <th className="text-left py-2 px-3 font-bold">Property</th>
                <th className="text-left py-2 px-3 font-bold">Önceki</th>
                <th className="text-left py-2 px-3 font-bold">Şimdiki</th>
                <th className="text-left py-2 px-3 font-bold">Güven</th>
                <th className="text-left py-2 px-3 font-bold">Gerekçe</th>
                <th className="text-left py-2 px-3 font-bold">Ne zaman</th>
                <th className="text-left py-2 px-3 font-bold">Kim</th>
                <th className="text-right py-2 px-3 font-bold">Aksiyon</th>
              </tr>
            </thead>
            <tbody>
              {items.map((it) => {
                const confColor = (it.confidence || 0) >= 0.9 ? "text-emerald-300"
                  : (it.confidence || 0) >= 0.7 ? "text-cyan-300" : "text-amber-300";
                const isManual = (it.classified_by || "").startsWith("manual-rollback");
                return (
                  <tr key={`${it.property_id}-${it.classified_at}`}
                      className="border-b border-stone-900 hover:bg-stone-900/30 transition"
                      data-testid={`history-row-${it.property_id}`}>
                    <td className="py-2.5 px-3">
                      <div className="font-bold text-stone-100">{it.name}</div>
                      <div className="text-[10px] text-stone-500 font-mono">{it.property_id}</div>
                    </td>
                    <td className="py-2.5 px-3">
                      {it.previous_type ? (
                        <span className="text-[11px] px-2 py-0.5 rounded bg-stone-800 text-stone-300 font-mono">{it.previous_type}</span>
                      ) : <span className="text-[10px] text-stone-600">—</span>}
                    </td>
                    <td className="py-2.5 px-3">
                      <span className="text-[11px] px-2 py-0.5 rounded bg-violet-500/15 text-violet-300 font-mono">{it.current_type || "?"}</span>
                    </td>
                    <td className={`py-2.5 px-3 font-bold ${confColor}`}>
                      {it.confidence ? `${Math.round(it.confidence * 100)}%` : "—"}
                    </td>
                    <td className="py-2.5 px-3 text-stone-400 text-xs max-w-md">
                      <span className="line-clamp-2">{it.reason || "—"}</span>
                    </td>
                    <td className="py-2.5 px-3 text-[10px] text-stone-500 whitespace-nowrap">
                      {it.classified_at ? new Date(it.classified_at).toLocaleString() : "—"}
                    </td>
                    <td className="py-2.5 px-3 text-[10px] text-stone-500 whitespace-nowrap">
                      {isManual ? (
                        <span className="text-amber-300">manuel</span>
                      ) : (
                        <span className="text-violet-400">AI</span>
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      <button
                        onClick={() => openRollback(it)}
                        className="px-2.5 py-1 bg-stone-800 hover:bg-amber-500/20 text-amber-300 text-[10px] font-bold rounded border border-amber-500/30 flex items-center gap-1 ml-auto"
                        data-testid={`history-rollback-btn-${it.property_id}`}
                        title={it.rollback_available ? `Geri al → ${it.previous_type}` : "Manuel değer seç"}
                      >
                        <Undo2 className="w-3 h-3" />
                        Geri Al
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Rollback modal */}
      {rollbackTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" data-testid="rollback-modal">
          <div className="bg-stone-900 border border-stone-700 rounded-2xl p-6 max-w-md w-full">
            <h4 className="text-lg font-bold text-stone-100 mb-1">Property Type Geri Al</h4>
            <p className="text-sm text-stone-400 mb-4">
              <strong className="text-stone-200">{rollbackTarget.name}</strong> için yeni property_type seç:
            </p>
            <div className="space-y-2 mb-4">
              <div className="flex items-center gap-2 text-xs">
                <span className="text-stone-500">Şimdiki:</span>
                <span className="px-2 py-0.5 rounded bg-violet-500/15 text-violet-300 font-mono font-bold">{rollbackTarget.current_type}</span>
              </div>
              {rollbackTarget.previous_type && (
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-stone-500">Kayıtlı önceki:</span>
                  <span className="px-2 py-0.5 rounded bg-stone-800 text-stone-300 font-mono font-bold">{rollbackTarget.previous_type}</span>
                </div>
              )}
            </div>
            <label className="block">
              <span className="text-[11px] uppercase tracking-wider text-stone-400 font-bold">Hedef tip</span>
              <select
                value={rollbackType}
                onChange={e => setRollbackType(e.target.value)}
                data-testid="rollback-type-select"
                className="w-full mt-1 bg-stone-950 border border-stone-700 rounded px-3 py-2 text-sm text-stone-100"
              >
                {VALID_TYPES.map(t => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </label>
            <div className="flex justify-end gap-2 mt-6">
              <button
                onClick={() => setRollbackTarget(null)}
                disabled={rollingBack}
                data-testid="rollback-cancel-btn"
                className="px-4 py-2 bg-stone-800 hover:bg-stone-700 text-stone-300 text-sm font-bold rounded"
              >İptal</button>
              <button
                onClick={doRollback}
                disabled={rollingBack || !rollbackType}
                data-testid="rollback-confirm-btn"
                className="px-4 py-2 bg-amber-500 hover:bg-amber-400 text-black text-sm font-black rounded flex items-center gap-2 disabled:opacity-50"
              >
                {rollingBack ? <Loader2 className="w-4 h-4 animate-spin" /> : <Undo2 className="w-4 h-4" />}
                Uygula
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
