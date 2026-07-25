import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowsLeftRight, WarningOctagon, CheckCircle, Broadcast,
} from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

const fmtTime = (iso) => {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleString("tr-TR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }); }
  catch { return iso; }
};

export default function TwoWaySyncTab({ propertyId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/api/two-way-sync/${propertyId}`);
      setData(r.data);
    } catch { toast.error("İki yönlü sync verisi yüklenemedi"); }
    finally { setLoading(false); }
  }, [propertyId]);
  useEffect(() => { load(); }, [load]);

  const simulate = async (forceConflict) => {
    setBusy(forceConflict ? "sim-conflict" : "sim");
    try {
      const r = await axios.post(`${API}/api/two-way-sync/simulate`, {
        property_id: propertyId, force_conflict: forceConflict,
      });
      const rip = r.data.ripple || {};
      toast.success(`Simülasyon tamam: ${rip.tasks_succeeded || 0}/${rip.tasks_total || 0} ripple push${r.data.conflict ? " — ÇAKIŞMA tespit edildi!" : ""}`);
      await load();
    } catch { toast.error("Simülasyon başarısız"); }
    finally { setBusy(""); }
  };

  const resolve = async (id) => {
    setBusy(id);
    try {
      await axios.post(`${API}/api/two-way-sync/conflicts/${id}/resolve`, {});
      toast.success("Çakışma çözüldü olarak işaretlendi");
      await load();
    } catch { toast.error("İşlem başarısız"); }
    finally { setBusy(""); }
  };

  if (loading) return <div className="p-8 text-stone-400 text-sm" data-testid="two-way-loading">Yükleniyor…</div>;
  if (!data) return <div className="p-8 text-stone-400 text-sm">Veri yok</div>;

  const s = data.summary;
  const openConflicts = data.conflicts.filter((c) => c.status === "open");

  return (
    <div className="space-y-5" data-testid="two-way-sync-tab">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-stone-500 max-w-2xl">
          Bir OTA'dan rezervasyon geldiğinde müsaitlik değişikliği <span className="font-medium text-stone-700">diğer tüm kanallara anında push'lanır</span> (ripple sync) ve aynı odaya çakışan rezervasyonlar <span className="font-medium text-rose-600">overbooking koruması</span> ile yakalanır.
        </p>
        <div className="flex gap-2">
          <button onClick={() => simulate(false)} disabled={!!busy} data-testid="simulate-inbound-btn"
            className="inline-flex items-center gap-1.5 text-xs font-medium text-white bg-stone-900 rounded-lg px-3.5 py-2 hover:bg-stone-800 disabled:opacity-50">
            <Broadcast size={14} weight="fill" /> {busy === "sim" ? "Çalışıyor…" : "Gelen rezervasyon simüle et"}
          </button>
          <button onClick={() => simulate(true)} disabled={!!busy} data-testid="simulate-conflict-btn"
            className="inline-flex items-center gap-1.5 text-xs font-medium text-rose-700 bg-rose-50 border border-rose-200 rounded-lg px-3.5 py-2 hover:bg-rose-100 disabled:opacity-50">
            <WarningOctagon size={14} weight="fill" /> {busy === "sim-conflict" ? "Çalışıyor…" : "Çakışma senaryosu"}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-5 gap-3">
        <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="kpi-ripple-24h">
          <div className="text-2xl font-bold text-stone-900">{s.ripple_24h}</div>
          <div className="text-[11px] text-stone-500 mt-1">Ripple olayı (24 saat)</div>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="kpi-ripple-total">
          <div className="text-2xl font-bold text-stone-900">{s.ripple_total}</div>
          <div className="text-[11px] text-stone-500 mt-1">Toplam ripple olayı</div>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="kpi-conflicts-open">
          <div className={`text-2xl font-bold ${s.conflicts_open > 0 ? "text-rose-600" : "text-emerald-600"}`}>{s.conflicts_open}</div>
          <div className="text-[11px] text-stone-500 mt-1">Açık çakışma (overbooking)</div>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="kpi-auto-moves">
          <div className="text-2xl font-bold text-indigo-600">{s.auto_moves_total || 0}</div>
          <div className="text-[11px] text-stone-500 mt-1">Otomatik taşıma (aynı tip oda) {s.auto_move_enabled === false && <span className="text-rose-500 font-semibold">· KAPALI</span>}</div>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="kpi-channels">
          <div className="text-2xl font-bold text-stone-900">{s.channels.length}</div>
          <div className="text-[11px] text-stone-500 mt-1">Kapsanan kanal: {s.channels.join(", ") || "—"}</div>
        </div>
      </div>

      {openConflicts.length > 0 && (
        <div className="bg-rose-50 border border-rose-200 rounded-xl p-4 space-y-3" data-testid="conflicts-list">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-rose-700">
            <WarningOctagon size={14} weight="fill" /> Açık overbooking çakışmaları ({openConflicts.length})
          </div>
          {openConflicts.map((c) => (
            <div key={c.id} className="bg-white border border-rose-200 rounded-lg p-3 flex items-center justify-between gap-3" data-testid={`conflict-${c.id}`}>
              <div className="text-xs">
                <span className="font-semibold text-stone-900">Oda {c.room_number}</span>
                <span className="text-stone-500"> — </span>
                <span className="text-stone-700">{c.booking_a.guest_name} <span className="text-stone-400">({c.booking_a.channel}, {c.booking_a.check_in} → {c.booking_a.check_out})</span></span>
                <span className="text-rose-600 font-medium"> ⇄ </span>
                <span className="text-stone-700">{c.booking_b.guest_name} <span className="text-stone-400">({c.booking_b.channel}, {c.booking_b.check_in} → {c.booking_b.check_out})</span></span>
              </div>
              <button onClick={() => resolve(c.id)} disabled={busy === c.id} data-testid={`resolve-conflict-${c.id}`}
                className="shrink-0 inline-flex items-center gap-1 text-[11px] font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-2.5 py-1.5 hover:bg-emerald-100 disabled:opacity-50">
                <CheckCircle size={12} weight="fill" /> Çözüldü işaretle
              </button>
            </div>
          ))}
        </div>
      )}

      {(data.auto_relocations || []).length > 0 && (
        <div className="bg-white border border-indigo-200 rounded-xl overflow-hidden" data-testid="auto-relocations-list">
          <div className="px-4 py-3 border-b border-indigo-100 bg-indigo-50/50 flex items-center gap-1.5">
            <CheckCircle size={14} weight="fill" className="text-indigo-600" />
            <h3 className="text-sm font-semibold text-stone-900">Otomatik taşımalar — aynı oda tipi kuralı ({data.auto_relocations.length})</h3>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[11px] uppercase tracking-wide text-stone-400 border-b border-stone-100">
                <th className="text-left px-4 py-2 font-medium">Zaman</th>
                <th className="text-left px-2 py-2 font-medium">Misafir</th>
                <th className="text-left px-2 py-2 font-medium">Kanal</th>
                <th className="text-left px-2 py-2 font-medium">Tarih</th>
                <th className="text-left px-4 py-2 font-medium">Taşıma</th>
              </tr>
            </thead>
            <tbody>
              {data.auto_relocations.map((r) => (
                <tr key={r.id} className="border-b border-stone-50 last:border-0" data-testid={`auto-move-${r.id}`}>
                  <td className="px-4 py-2 text-xs text-stone-500">{fmtTime(r.created_at)}</td>
                  <td className="px-2 py-2 text-xs font-medium text-stone-800">{r.guest_name}</td>
                  <td className="px-2 py-2 text-xs text-stone-600">{r.channel || "—"}</td>
                  <td className="px-2 py-2 text-xs text-stone-600">{r.check_in} → {r.check_out}</td>
                  <td className="px-4 py-2 text-xs">
                    <span className="text-rose-600 line-through">{r.from_room}</span>
                    <span className="text-stone-400 mx-1.5">→</span>
                    <span className="font-bold text-emerald-700">{r.to_room}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="bg-white border border-stone-200 rounded-xl overflow-hidden" data-testid="ripple-timeline">
        <div className="px-4 py-3 border-b border-stone-100 flex items-center gap-1.5">
          <ArrowsLeftRight size={14} className="text-indigo-600" />
          <h3 className="text-sm font-semibold text-stone-900">Ripple olayları ({data.ripple_events.length})</h3>
        </div>
        {data.ripple_events.length === 0 ? (
          <div className="px-4 py-6 text-xs text-stone-400">Henüz ripple olayı yok — "Gelen rezervasyon simüle et" ile akışı test edebilirsiniz.</div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[11px] uppercase tracking-wide text-stone-400 border-b border-stone-100">
                <th className="text-left px-4 py-2 font-medium">Zaman</th>
                <th className="text-left px-2 py-2 font-medium">Olay</th>
                <th className="text-left px-2 py-2 font-medium">Kaynak kanal</th>
                <th className="text-left px-2 py-2 font-medium">Misafir</th>
                <th className="text-left px-2 py-2 font-medium">Tarih</th>
                <th className="text-right px-2 py-2 font-medium">Push (başarılı/toplam)</th>
                <th className="text-left px-4 py-2 font-medium">Hedef kanallar</th>
              </tr>
            </thead>
            <tbody>
              {data.ripple_events.map((e) => (
                <tr key={e.id} className="border-b border-stone-50 last:border-0" data-testid={`ripple-${e.id}`}>
                  <td className="px-4 py-2 text-xs text-stone-500">{fmtTime(e.created_at)}</td>
                  <td className="px-2 py-2">
                    <span className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full ${e.event_type === "cancellation" ? "bg-amber-100 text-amber-700" : "bg-indigo-100 text-indigo-700"}`}>
                      {e.event_type === "cancellation" ? "İptal" : "Rezervasyon"}
                    </span>
                  </td>
                  <td className="px-2 py-2 text-xs font-medium text-stone-800">{e.source_channel}</td>
                  <td className="px-2 py-2 text-xs text-stone-600">{e.guest_name || "—"}</td>
                  <td className="px-2 py-2 text-xs text-stone-600">{e.check_in} → {e.check_out}</td>
                  <td className={`px-2 py-2 text-right text-xs font-bold ${e.tasks_succeeded === e.tasks_total ? "text-emerald-600" : "text-amber-600"}`}>
                    {e.tasks_succeeded}/{e.tasks_total}
                  </td>
                  <td className="px-4 py-2 text-xs text-stone-500">{(e.channels || []).join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
