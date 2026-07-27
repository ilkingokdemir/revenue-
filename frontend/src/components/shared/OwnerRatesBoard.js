import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { Tag, Plus, Trash, PencilSimple, Lightning, ArrowsClockwise } from "@phosphor-icons/react";

/**
 * İki yönlü fiyat panosu — admin ve sahip portalı aynı bileşeni kullanır.
 * props.api: { getBoard(days), setRate({date,rate,mode}), getLayers(),
 *              addLayer({name,pct}), toggleLayer(id,active), deleteLayer(id) }
 */
export default function OwnerRatesBoard({ api, title = "Fiyat Panosu" }) {
  const [board, setBoard] = useState(null);
  const [editing, setEditing] = useState(null); // {date, mode}
  const [editVal, setEditVal] = useState("");
  const [newName, setNewName] = useState("");
  const [newPct, setNewPct] = useState("");

  const load = useCallback(async () => {
    try { setBoard(await api.getBoard(14)); }
    catch { toast.error("Fiyat panosu yüklenemedi"); }
  }, [api]);
  useEffect(() => { load(); }, [load]);

  const startEdit = (d, mode) => {
    setEditing({ date: d.date, mode });
    setEditVal(mode === "gross" ? d.live_pms_rate : d.current_sell_rate);
  };

  const saveEdit = async () => {
    if (!editing || !editVal) return;
    try {
      const r = await api.setRate({ date: editing.date, rate: parseFloat(editVal), mode: editing.mode });
      toast.success(`${editing.date}: PMS £${r.live_pms_rate} → müşteri £${r.current_sell_rate}` +
        (r.guard_clamped ? ` (${r.guard_reason} korumasına ayarlandı)` : ""));
      setEditing(null);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Kaydedilemedi"); }
  };

  const addLayer = async () => {
    if (!newName || !newPct) { toast.error("Ad ve yüzde girin"); return; }
    try {
      await api.addLayer({ name: newName, pct: parseFloat(newPct) });
      setNewName(""); setNewPct("");
      toast.success("İndirim eklendi");
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Eklenemedi"); }
  };

  if (!board) return <div className="text-center py-10 text-sm text-stone-400" data-testid="rates-board-loading">Yükleniyor…</div>;

  return (
    <div className="space-y-4" data-testid="owner-rates-board">
      {/* İndirim katmanları */}
      <div className="bg-white border border-stone-200 rounded-2xl p-4">
        <div className="flex flex-wrap items-center gap-2 mb-3">
          <h3 className="text-sm font-bold text-stone-800 flex items-center gap-2 mr-2">
            <Tag size={15} className="text-[#F97316]" /> İndirimler & Promosyonlar
          </h3>
          <span className="text-[10px] font-black text-white bg-[#F97316] rounded-full px-2 py-0.5">toplam -%{board.total_discount_pct}</span>
          <button onClick={load} className="ml-auto p-1.5 rounded-lg text-stone-400 hover:text-stone-700 transition-colors" data-testid="rates-board-refresh">
            <ArrowsClockwise size={14} />
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          {(board.active_layers || []).map((l) => (
            <span key={l.id} className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-amber-50 border border-amber-200 text-xs font-bold text-amber-800" data-testid={`board-layer-${l.id}`}>
              {l.name} −%{l.pct}
              <button onClick={async () => { try { await api.toggleLayer(l.id, false); toast.success("Pasife alındı"); load(); } catch { toast.error("Olmadı"); } }}
                className="text-amber-400 hover:text-rose-500 transition-colors" title="Pasife al" data-testid={`board-layer-off-${l.id}`}>✕</button>
              <button onClick={async () => { try { await api.deleteLayer(l.id); toast.success("Silindi"); load(); } catch { toast.error("Olmadı"); } }}
                className="text-amber-400 hover:text-rose-600 transition-colors" title="Sil" data-testid={`board-layer-del-${l.id}`}><Trash size={11} /></button>
            </span>
          ))}
          {(board.active_layers || []).length === 0 && <span className="text-xs text-stone-400">Aktif indirim yok</span>}
          <span className="inline-flex items-center gap-1.5">
            <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="yeni indirim adı"
              className="w-36 rounded-lg border border-stone-200 px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-[#F97316]/40" data-testid="board-new-layer-name" />
            <input type="number" min="1" max="89" value={newPct} onChange={(e) => setNewPct(e.target.value)} placeholder="%"
              className="w-14 rounded-lg border border-stone-200 px-2 py-1.5 text-xs text-right" data-testid="board-new-layer-pct" />
            <button onClick={addLayer} className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-[#F97316] hover:bg-[#EA580C] text-white text-xs font-bold transition-colors" data-testid="board-add-layer-btn">
              <Plus size={11} weight="bold" /> Ekle
            </button>
          </span>
        </div>
      </div>

      {/* Fiyat tablosu */}
      <div className="bg-white border border-stone-200 rounded-2xl p-4 overflow-x-auto">
        <h3 className="text-sm font-bold text-stone-800 mb-3">{title} — önümüzdeki 14 gün <span className="text-[10px] font-normal text-stone-400">(fiyata tıklayıp değiştirin)</span></h3>
        <table className="w-full text-xs" data-testid="rates-board-table">
          <thead>
            <tr className="text-left text-[10px] uppercase tracking-widest text-stone-400">
              <th className="py-2 pr-3">Tarih</th>
              <th className="py-2 pr-3">Doluluk</th>
              <th className="py-2 pr-3">Boş oda</th>
              <th className="py-2 pr-3">Min</th>
              <th className="py-2 pr-3 text-blue-700">Live PMS Rate (brüt)</th>
              <th className="py-2 pr-3 text-emerald-700">Current Sell Rate (müşteri)</th>
              <th className="py-2">Kaynak</th>
            </tr>
          </thead>
          <tbody>
            {board.days.map((d) => (
              <tr key={d.date} className={`border-t border-stone-100 ${d.is_event_day ? "bg-violet-50/60" : ""}`} data-testid={`board-row-${d.date}`}>
                <td className="py-2 pr-3 font-bold text-stone-700 whitespace-nowrap">
                  {d.date.slice(5)}{d.is_event_day && <Lightning size={11} weight="fill" className="inline ml-1 text-violet-500" />}
                </td>
                <td className="py-2 pr-3">
                  <span className={`font-black tabular-nums ${d.occ_pct >= 80 ? "text-emerald-600" : d.occ_pct >= 50 ? "text-amber-600" : "text-rose-500"}`}>%{d.occ_pct}</span>
                </td>
                <td className="py-2 pr-3 tabular-nums text-stone-500">{d.available}</td>
                <td className="py-2 pr-3 tabular-nums text-stone-400">{d.min_rate ? `£${d.min_rate}` : "—"}</td>
                {["gross", "net"].map((mode) => {
                  const val = mode === "gross" ? d.live_pms_rate : d.current_sell_rate;
                  const isEd = editing?.date === d.date && editing?.mode === mode;
                  return (
                    <td key={mode} className="py-2 pr-3">
                      {isEd ? (
                        <span className="inline-flex items-center gap-1">
                          <input autoFocus type="number" value={editVal} onChange={(e) => setEditVal(e.target.value)}
                            onKeyDown={(e) => { if (e.key === "Enter") saveEdit(); if (e.key === "Escape") setEditing(null); }}
                            className="w-20 rounded border border-blue-300 px-1.5 py-1 text-xs tabular-nums" data-testid={`board-edit-input-${d.date}`} />
                          <button onClick={saveEdit} className="px-2 py-1 rounded bg-[#1D4ED8] text-white text-[10px] font-bold" data-testid={`board-edit-save-${d.date}`}>✓</button>
                        </span>
                      ) : (
                        <button onClick={() => startEdit(d, mode)} data-testid={`board-${mode}-${d.date}`}
                          className={`group inline-flex items-center gap-1 font-black tabular-nums px-1.5 py-0.5 rounded hover:bg-blue-50 transition-colors ${mode === "gross" ? "text-[#1D4ED8]" : "text-emerald-600"}`}>
                          £{val}
                          <PencilSimple size={10} className="opacity-0 group-hover:opacity-60" />
                        </button>
                      )}
                    </td>
                  );
                })}
                <td className="py-2">
                  <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full uppercase ${
                    d.source === "owner-manual" ? "bg-amber-100 text-amber-700"
                    : d.source === "admin-manual" ? "bg-blue-100 text-blue-700"
                    : d.source?.includes("ai") ? "bg-emerald-100 text-emerald-700" : "bg-stone-100 text-stone-500"}`}>
                    {d.source === "owner-manual" ? "SAHİP" : d.source === "admin-manual" ? "ADMİN" : d.source === "base" ? "BAZ" : d.source}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
