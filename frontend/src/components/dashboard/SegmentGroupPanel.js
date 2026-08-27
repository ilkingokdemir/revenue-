import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Lightning } from "@phosphor-icons/react";

const B = process.env.REACT_APP_BACKEND_URL;

export default function SegmentGroupPanel({ propertyId = "default" }) {
  const pid = propertyId === "all" ? "default" : propertyId;
  const [seg, setSeg] = useState(null);
  const [quotes, setQuotes] = useState([]);
  const [events, setEvents] = useState([]);
  const [cfg, setCfg] = useState(null);
  const [busy, setBusy] = useState("");
  const day = new Date(Date.now() + 86400000).toISOString().slice(0, 10);

  const load = useCallback(async () => {
    try {
      const [s, g, e, c] = await Promise.all([
        axios.get(`${B}/api/segment-pricing/${pid}?date=${day}`),
        axios.get(`${B}/api/group-approval/${pid}`),
        axios.get(`${B}/api/reprice-bridge/${pid}/events`),
        axios.get(`${B}/api/group-approval/${pid}/config`),
      ]);
      setSeg(s.data); setQuotes(g.data.quotes || []); setEvents(e.data.events || []); setCfg(c.data);
    } catch { toast.error("Veri yüklenemedi"); }
  }, [pid, day]);
  useEffect(() => { load(); }, [load]);

  async function saveCfg(e) {
    e.preventDefault(); setBusy("cfg");
    try {
      await axios.put(`${B}/api/group-approval/${pid}/config`, {
        steps: {
          revenue: e.target.rev.value.split(",").map((x) => x.trim()).filter(Boolean),
          sales: e.target.sal.value.split(",").map((x) => x.trim()).filter(Boolean),
        },
      });
      toast.success("Onay yetkileri güncellendi"); load();
    } catch (err) { toast.error(err.response?.data?.detail || "Kaydedilemedi (sadece admin)"); }
    setBusy("");
  }

  async function saveSeg(e) {
    e.preventDefault(); setBusy("seg");
    const segments = seg.segments.map((s, i) => ({ ...s, offset_pct: parseFloat(e.target[`o_${i}`].value) }));
    try {
      await axios.put(`${B}/api/segment-pricing/${pid}`, { segments });
      toast.success("Segment offsetleri kaydedildi"); load();
    } catch { toast.error("Kaydedilemedi"); }
    setBusy("");
  }

  async function createQuote(e) {
    e.preventDefault(); setBusy("q");
    const f = e.target;
    try {
      await axios.post(`${B}/api/group-approval/${pid}/quotes`, {
        group_name: f.gname.value, rooms: parseInt(f.rooms.value, 10),
        nights: parseInt(f.nights.value, 10), check_in: f.ci.value,
        wish_price: parseFloat(f.wish.value), walk_price: parseFloat(f.walk.value),
      });
      toast.success("Grup teklifi oluşturuldu — Revenue onayı bekliyor"); f.reset(); load();
    } catch (err) { toast.error(err.response?.data?.detail || "Teklif oluşturulamadı"); }
    setBusy("");
  }

  async function act(qid, action, role) {
    try {
      if (action === "approve") await axios.post(`${B}/api/group-approval/${pid}/quotes/${qid}/approve`, { role });
      else await axios.post(`${B}/api/group-approval/${pid}/quotes/${qid}/reject`, {});
      toast.success(action === "approve" ? `${role} onayı verildi` : "Teklif reddedildi"); load();
    } catch (err) { toast.error(err.response?.data?.detail || "İşlem başarısız"); }
  }

  const statusTr = { pending_revenue: "Revenue onayı bekliyor", pending_sales: "Satış onayı bekliyor", approved: "✅ ONAYLANDI", rejected: "❌ Reddedildi" };

  return (
    <div className="p-5 max-w-[1100px] mx-auto space-y-4" data-testid="segment-group-panel">
      <div className="bg-gradient-to-br from-stone-900 via-indigo-950 to-purple-950 rounded-2xl p-6 text-white">
        <h1 className="text-2xl font-bold">Segment Fiyat Katmanı & Grup Onay Akışı</h1>
        <p className="text-sm text-stone-300 mt-1">Aynı gece için segment bazlı bağımsız fiyat offsetleri (Open Pricing) + grup tekliflerinde Wish/Walk metrikleri ve departman onay zinciri.</p>
      </div>

      {seg && (
        <form onSubmit={saveSeg} className="bg-white rounded-2xl border border-stone-200 p-5" data-testid="segment-card">
          <h2 className="text-lg font-semibold mb-1">Segment Offsetleri</h2>
          <p className="text-xs text-stone-400 mb-3">Baz fiyat ({day}): <b>£{seg.base_rate}</b> — offset uygulanmış segment fiyatları aşağıda</p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {seg.segments.map((s, i) => (
              <div key={s.code} className="bg-stone-50 rounded-xl p-3" data-testid={`segment-${s.code}`}>
                <div className="text-sm font-semibold">{s.name}</div>
                <input name={`o_${i}`} type="number" step="0.5" min="-50" max="50" defaultValue={s.offset_pct}
                  data-testid={`segment-offset-${s.code}`} className="mt-1 w-full border rounded-lg px-2 py-1 text-sm" />
                <div className="text-xs text-stone-500 mt-1">% offset → <b className="text-indigo-700">{s.rate != null ? `£${s.rate}` : "—"}</b></div>
              </div>
            ))}
          </div>
          <button type="submit" disabled={busy === "seg"} data-testid="segment-save-btn"
            className="mt-3 px-4 py-2 rounded-full bg-indigo-600 text-white text-sm font-semibold disabled:opacity-50">Offsetleri Kaydet</button>
        </form>
      )}

      <div className="bg-white rounded-2xl border border-stone-200 p-5" data-testid="group-approval-card">
        <h2 className="text-lg font-semibold mb-3">Grup Teklifleri (Wish & Walk + Onay Zinciri)</h2>
        {cfg && (
          <form onSubmit={saveCfg} className="flex flex-wrap items-end gap-3 mb-4 bg-stone-50 border border-stone-200 rounded-xl p-3" data-testid="approval-config-card">
            <span className="text-xs font-bold text-stone-600">Onay Yetkileri:</span>
            <label className="text-[11px] text-stone-500">Revenue adımı (departmanlar, virgülle)
              <input name="rev" defaultValue={(cfg.steps.revenue || []).join(", ")} data-testid="approval-rev-depts-input"
                className="block border rounded-lg px-2 py-1.5 text-xs w-56 mt-0.5" /></label>
            <label className="text-[11px] text-stone-500">Sales adımı
              <input name="sal" defaultValue={(cfg.steps.sales || []).join(", ")} data-testid="approval-sales-depts-input"
                className="block border rounded-lg px-2 py-1.5 text-xs w-56 mt-0.5" /></label>
            <button type="submit" disabled={busy === "cfg"} data-testid="approval-config-save-btn"
              className="px-3 py-1.5 rounded-full bg-stone-900 text-white text-[11px] font-bold disabled:opacity-50">Kaydet</button>
            <span className="text-[10px] text-stone-400">{cfg.note}</span>
          </form>
        )}
        <form onSubmit={createQuote} className="grid grid-cols-2 md:grid-cols-7 gap-2 items-end mb-4">
          <input name="gname" required placeholder="Grup adı" data-testid="quote-name-input" className="border rounded-lg px-2 py-1.5 text-sm md:col-span-2" />
          <input name="rooms" type="number" min="1" defaultValue="10" title="Oda" data-testid="quote-rooms-input" className="border rounded-lg px-2 py-1.5 text-sm" />
          <input name="nights" type="number" min="1" defaultValue="2" title="Gece" data-testid="quote-nights-input" className="border rounded-lg px-2 py-1.5 text-sm" />
          <input name="ci" type="date" required data-testid="quote-checkin-input" className="border rounded-lg px-2 py-1.5 text-sm" />
          <input name="wish" type="number" step="0.01" required placeholder="Wish £" data-testid="quote-wish-input" className="border rounded-lg px-2 py-1.5 text-sm" />
          <input name="walk" type="number" step="0.01" required placeholder="Walk £" data-testid="quote-walk-input" className="border rounded-lg px-2 py-1.5 text-sm" />
          <button type="submit" disabled={busy === "q"} data-testid="quote-create-btn" className="col-span-2 md:col-span-7 md:w-44 px-4 py-2 rounded-full bg-stone-900 text-white text-sm font-semibold disabled:opacity-50">Teklif Oluştur</button>
        </form>
        {quotes.length === 0 ? <p className="text-sm text-stone-400" data-testid="quotes-empty">Henüz teklif yok.</p> : (
          <table className="w-full text-sm" data-testid="quotes-table">
            <thead><tr className="text-left text-xs text-stone-500 border-b"><th className="py-2">Grup</th><th>Oda×Gece</th><th>Wish</th><th>Walk</th><th>Durum</th><th>Aksiyon</th></tr></thead>
            <tbody>{quotes.map((q) => (
              <tr key={q.id} className="border-b border-stone-100">
                <td className="py-2 font-medium">{q.group_name}<div className="text-[10px] text-stone-400">{q.check_in}</div></td>
                <td>{q.rooms}×{q.nights}</td>
                <td className="text-emerald-700 font-semibold">£{q.wish_price} <span className="text-[10px] text-stone-400">(£{q.wish_total})</span></td>
                <td className="text-rose-700 font-semibold">£{q.walk_price} <span className="text-[10px] text-stone-400">(£{q.walk_total})</span></td>
                <td className="text-xs font-semibold">{statusTr[q.status] || q.status}</td>
                <td>{q.status?.startsWith("pending") && (
                  <div className="flex gap-1">
                    <button onClick={() => act(q.id, "approve", q.status.replace("pending_", ""))} data-testid={`quote-approve-${q.id}`}
                      className="px-2 py-1 rounded-full bg-emerald-600 text-white text-[10px] font-semibold">Onayla ({q.status.replace("pending_", "")})</button>
                    <button onClick={() => act(q.id, "reject")} data-testid={`quote-reject-${q.id}`}
                      className="px-2 py-1 rounded-full border border-rose-300 text-rose-600 text-[10px] font-semibold">Reddet</button>
                  </div>)}</td>
              </tr>))}</tbody>
          </table>
        )}
      </div>

      <div className="bg-white rounded-2xl border border-stone-200 p-5" data-testid="reprice-events-card">
        <h2 className="text-lg font-semibold mb-1 flex items-center gap-2"><Lightning size={18} className="text-amber-500" /> Anlık Re-Price Olayları</h2>
        <p className="text-xs text-stone-400 mb-2">Her rezervasyon, iptal ve kayıp talep kaydı fiyat motorunu saniyeler içinde tetikler.</p>
        {events.length === 0 ? <p className="text-sm text-stone-400" data-testid="reprice-empty">Henüz olay yok — yeni rezervasyon/iptal geldiğinde burada görünür.</p> : (
          <div className="flex flex-wrap gap-2">{events.slice(0, 12).map((e) => (
            <span key={e.id} className="px-2.5 py-1 rounded-full bg-amber-50 border border-amber-200 text-[11px]">
              ⚡ {e.reason} · {e.actions} aksiyon · {e.latency_ms}ms · {e.created_at?.slice(11, 16)}
            </span>))}</div>
        )}
      </div>
    </div>
  );
}
