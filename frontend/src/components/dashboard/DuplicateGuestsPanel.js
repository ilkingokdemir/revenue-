/**
 * DuplicateGuestsPanel — Mews-parity feature (iter 356).
 *
 * Lists auto-detected duplicate-guest clusters (same email/phone/name+DOB)
 * and lets the operator pick a primary + merge the rest. Bookings are
 * re-pointed to the primary and duplicates deleted.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Copy, Loader2, RefreshCcw, Check, User, Merge } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export function DuplicateGuestsPanel() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [merging, setMerging] = useState(null);
  const [primaryByCluster, setPrimaryByCluster] = useState({});

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/mews-ai/duplicate-guests?limit=100`);
      setData(r.data);
      // Auto-select first (usually oldest/most complete) guest as default primary
      const defaults = {};
      (r.data.clusters || []).forEach(c => {
        defaults[c.cluster_id] = c.guests[0].id;
      });
      setPrimaryByCluster(defaults);
    } catch (e) {
      toast.error("Duplicate liste yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const merge = async (cluster) => {
    const primary = primaryByCluster[cluster.cluster_id];
    if (!primary) return toast.warning("Önce primary misafiri seçin");
    const dupes = cluster.guests.filter(g => g.id !== primary).map(g => g.id);
    if (!dupes.length) return;
    if (!window.confirm(`${dupes.length} duplicate profili ana profile birleştirilecek. Devam?`)) return;
    setMerging(cluster.cluster_id);
    try {
      const r = await axios.post(`${API}/mews-ai/merge-guests`, {
        primary_id: primary, duplicate_ids: dupes,
      });
      toast.success(`✅ Birleştirildi · ${r.data.moved_bookings} rezervasyon taşındı, ${r.data.removed_dupes} duplicate silindi`);
      await load();
    } catch (e) {
      toast.error("Birleştirme başarısız: " + (e.response?.data?.detail || e.message));
    } finally {
      setMerging(null);
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-stone-200 shadow-sm" data-testid="duplicate-guests-panel">
      <div className="p-4 border-b border-stone-100 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center shadow-md">
            <Copy className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="text-base font-black text-stone-900">Duplicate Guest Auto-Merge</h3>
            <p className="text-xs text-stone-500">
              Aynı misafirin birden fazla profilini algılar, birleştirilebilir hale getirir
            </p>
          </div>
        </div>
        <button
          onClick={load}
          disabled={loading}
          data-testid="duplicate-guests-refresh"
          className="text-xs px-3 py-1.5 bg-stone-100 hover:bg-stone-200 text-stone-700 rounded-lg font-bold inline-flex items-center gap-1.5 disabled:opacity-50"
        >
          {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCcw className="w-3 h-3" />}
          Yeniden Tara
        </button>
      </div>

      {loading && !data && (
        <div className="p-12 text-center text-stone-400 text-sm">Taranıyor...</div>
      )}

      {data && (
        <>
          <div className="p-4 bg-stone-50 border-b border-stone-100 flex items-center gap-6 text-xs">
            <span><b className="text-stone-900">{data.total_guests_scanned}</b> misafir tarandı</span>
            <span><b className="text-amber-600">{data.clusters_found}</b> potansiyel duplicate grup</span>
          </div>
          {data.clusters.length === 0 && (
            <div className="p-12 text-center">
              <Check className="w-12 h-12 text-emerald-500 mx-auto mb-2" />
              <p className="text-sm font-bold text-stone-700">Duplicate yok</p>
              <p className="text-xs text-stone-500">Tüm misafir profilleri temiz.</p>
            </div>
          )}
          <div className="divide-y divide-stone-100 max-h-[600px] overflow-y-auto">
            {data.clusters.map((c) => (
              <div key={c.cluster_id} className="p-4" data-testid="duplicate-cluster">
                <div className="flex items-center justify-between mb-2">
                  <div className="text-[11px] text-stone-500 font-bold uppercase">{c.reason}</div>
                  <button
                    onClick={() => merge(c)}
                    disabled={merging === c.cluster_id}
                    data-testid={`merge-cluster-${c.cluster_id}`}
                    className="text-[11px] px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-bold inline-flex items-center gap-1.5 disabled:opacity-50"
                  >
                    {merging === c.cluster_id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Merge className="w-3 h-3" />}
                    Birleştir ({c.size - 1})
                  </button>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {c.guests.map(g => {
                    const isPrimary = primaryByCluster[c.cluster_id] === g.id;
                    return (
                      <button
                        key={g.id}
                        onClick={() => setPrimaryByCluster(s => ({ ...s, [c.cluster_id]: g.id }))}
                        data-testid={`primary-toggle-${g.id}`}
                        className={`text-left p-2.5 rounded-lg border-2 transition-all ${isPrimary ? "border-emerald-400 bg-emerald-50" : "border-stone-200 bg-white hover:border-stone-300"}`}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <User className="w-4 h-4 text-stone-500" />
                            <span className="text-xs font-bold text-stone-900">
                              {g.first_name} {g.last_name}
                            </span>
                          </div>
                          {isPrimary && (
                            <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-500 text-white font-bold">
                              ANA
                            </span>
                          )}
                        </div>
                        <div className="text-[10px] text-stone-500 mt-1 space-y-0.5">
                          {g.email && <div>📧 {g.email}</div>}
                          {g.phone && <div>📞 {g.phone}</div>}
                          {g.created_at && <div className="text-stone-400">Oluşturulma: {g.created_at.slice(0, 10)}</div>}
                        </div>
                        {g.tags?.length > 0 && (
                          <div className="flex gap-1 mt-1.5 flex-wrap">
                            {g.tags.slice(0, 3).map(t => (
                              <span key={t} className="text-[8px] px-1.5 py-0.5 rounded bg-stone-100 text-stone-600">{t}</span>
                            ))}
                          </div>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
