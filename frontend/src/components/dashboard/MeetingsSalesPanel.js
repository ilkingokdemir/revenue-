import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Briefcase, Plus, X, Trash, Funnel } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/meetings`;

const STAGE_META = {
  inquiry:       { label: "Talep",        color: "bg-stone-100 text-stone-700 border-stone-300" },
  site_visit:    { label: "Site Ziyareti",color: "bg-sky-100 text-sky-700 border-sky-300" },
  proposal_sent: { label: "Teklif Gönd.", color: "bg-violet-100 text-violet-700 border-violet-300" },
  negotiating:   { label: "Pazarlık",     color: "bg-amber-100 text-amber-800 border-amber-300" },
  confirmed:     { label: "Onaylandı",    color: "bg-emerald-100 text-emerald-700 border-emerald-300" },
  invoiced:      { label: "Faturalandı",  color: "bg-teal-100 text-teal-700 border-teal-300" },
  completed:     { label: "Tamamlandı",   color: "bg-stone-100 text-stone-700 border-stone-300" },
  lost:          { label: "Kaybedildi",   color: "bg-rose-100 text-rose-700 border-rose-300" },
};
const ACTIVE_STAGES = ["inquiry", "site_visit", "proposal_sent", "negotiating", "confirmed"];
const EVENT_TYPES = [
  { v: "wedding", l: "Düğün" }, { v: "corporate_meeting", l: "Kurumsal" },
  { v: "conference", l: "Konferans" }, { v: "gala", l: "Gala" },
  { v: "birthday", l: "Doğum Günü" }, { v: "association", l: "Dernek" },
  { v: "training", l: "Eğitim" }, { v: "other", l: "Diğer" },
];
const ITEM_KINDS = [
  { v: "room_block", l: "Oda Bloğu" }, { v: "fnb", l: "Yiyecek-İçecek" },
  { v: "av_tech", l: "AV/Teknik" }, { v: "meeting_space", l: "Mekan" },
  { v: "decor", l: "Dekor" }, { v: "misc", l: "Diğer" },
];

export default function MeetingsSalesPanel({ propertyId = "all" }) {
  const [tab, setTab] = useState("pipeline");
  const [pipeline, setPipeline] = useState({ by_stage: {}, active_value: 0 });
  const [list, setList] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [detail, setDetail] = useState(null);
  const [form, setForm] = useState({ event_type: "wedding", guests_count: 0, rooms_required: 0, budget_estimate: 0 });
  const [itemForm, setItemForm] = useState({ kind: "fnb", qty: 1, unit_price: 0 });

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      if (tab === "pipeline") {
        const r = await axios.get(`${API}/pipeline?property_id=${propertyId}`, { withCredentials: true });
        setPipeline(r.data);
      } else if (tab === "list") {
        const r = await axios.get(`${API}?property_id=${propertyId}`, { withCredentials: true });
        setList(r.data.meetings || []);
      } else if (tab === "analytics") {
        const r = await axios.get(`${API}/analytics?property_id=${propertyId}&days=90`, { withCredentials: true });
        setAnalytics(r.data);
      }
    } catch (e) { toast.error("Yüklenemedi"); }
    finally { setLoading(false); }
  }, [tab, propertyId]);

  useEffect(() => { reload(); }, [reload]);

  async function loadDetail(id) {
    try {
      const r = await axios.get(`${API}/${id}`, { withCredentials: true });
      setDetail(r.data);
    } catch (e) { toast.error("Detay yüklenemedi"); }
  }

  async function create() {
    try {
      await axios.post(API, {
        name: form.name, event_type: form.event_type,
        property_id: propertyId === "all" ? "default" : propertyId,
        contact_name: form.contact_name || "",
        contact_email: form.contact_email || "",
        event_date: form.event_date,
        guests_count: Number(form.guests_count || 0),
        rooms_required: Number(form.rooms_required || 0),
        budget_estimate: Number(form.budget_estimate || 0),
        notes: form.notes || "",
      }, { withCredentials: true });
      toast.success("RFP oluşturuldu");
      setShowCreate(false); setForm({ event_type: "wedding", guests_count: 0, rooms_required: 0, budget_estimate: 0 });
      reload();
    } catch (e) { toast.error("Oluşturulamadı"); }
  }

  async function moveStage(id, newStage) {
    try {
      const body = { stage: newStage };
      if (newStage === "lost") {
        body.lost_reason = window.prompt("Kayıp sebebi:", "price") || "unspecified";
      }
      await axios.patch(`${API}/${id}`, body, { withCredentials: true });
      toast.success("Aşama güncellendi");
      if (detail?.id === id) loadDetail(id);
      reload();
    } catch (e) { toast.error("Güncellenemedi"); }
  }

  async function addItem() {
    if (!detail) return;
    try {
      await axios.post(`${API}/${detail.id}/items`, {
        kind: itemForm.kind, label: itemForm.label,
        qty: Number(itemForm.qty || 1), unit_price: Number(itemForm.unit_price || 0),
      }, { withCredentials: true });
      setItemForm({ kind: "fnb", qty: 1, unit_price: 0 });
      loadDetail(detail.id); reload();
    } catch (e) { toast.error("Satır eklenemedi"); }
  }

  async function removeItem(itemId) {
    try {
      await axios.delete(`${API}/${detail.id}/items/${itemId}`, { withCredentials: true });
      loadDetail(detail.id); reload();
    } catch (e) { toast.error("Silinemedi"); }
  }

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="meetings-sales-panel">
      <div className="mb-4 flex items-start justify-between gap-3 flex-wrap">
        <div>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
            <Briefcase size={12} weight="fill" className="text-indigo-500" />
            <span>MICE Sales</span>
          </div>
          <h1 className="text-2xl font-semibold text-stone-900">Toplantı & Etkinlik Satış Hattı</h1>
          <p className="text-sm text-stone-500 mt-1 max-w-2xl">
            Düğün, kurumsal toplantı, konferans satış pipeline'ı — RFP'den faturaya kadar.
          </p>
        </div>
        <button onClick={() => setShowCreate(true)} data-testid="meetings-create-btn"
                className="px-3 py-1.5 text-xs text-white bg-stone-900 rounded-lg inline-flex items-center gap-1.5">
          <Plus size={13} /> Yeni RFP
        </button>
      </div>

      <div className="flex gap-1 mb-4 border-b border-stone-200">
        {[
          { id: "pipeline", label: "Pipeline" },
          { id: "list", label: "Tüm Talepler" },
          { id: "analytics", label: "Analitik" },
        ].map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} data-testid={`meetings-tab-${t.id}`}
                  className={`px-4 py-2 text-xs font-medium border-b-2 ${tab === t.id ? "border-stone-900 text-stone-900" : "border-transparent text-stone-500"}`}>
            {t.label}
          </button>
        ))}
      </div>

      {loading && <div className="text-center py-12 text-stone-400 text-sm">Yükleniyor…</div>}

      {!loading && tab === "pipeline" && (
        <>
          <div className="mb-3 inline-flex items-center gap-2 px-3 py-1.5 bg-emerald-50 border border-emerald-200 rounded-lg">
            <Funnel size={13} className="text-emerald-600" />
            <span className="text-xs text-emerald-700">Aktif pipeline değeri:</span>
            <span className="text-sm font-semibold text-emerald-700" data-testid="meetings-active-value">
              £{pipeline.active_value?.toLocaleString("tr-TR") || 0}
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            {ACTIVE_STAGES.map(s => (
              <div key={s} className="bg-stone-50 border border-stone-200 rounded-xl p-2 min-h-[180px]" data-testid={`meetings-lane-${s}`}>
                <div className={`text-[10px] uppercase tracking-wider font-semibold px-2 py-1 mb-2 rounded ${STAGE_META[s].color}`}>
                  {STAGE_META[s].label} ({(pipeline.by_stage[s] || []).length})
                </div>
                <div className="space-y-1.5">
                  {(pipeline.by_stage[s] || []).map(m => (
                    <button key={m.id} onClick={() => loadDetail(m.id)}
                            data-testid={`meetings-card-${m.id}`}
                            className="w-full text-left bg-white border border-stone-200 rounded-lg p-2 hover:border-stone-400 transition-colors">
                      <div className="text-xs font-medium text-stone-800 truncate">{m.name}</div>
                      <div className="text-[10px] text-stone-500 mt-0.5">{m.event_date} · {m.guests_count} kişi</div>
                      <div className="text-[10px] font-semibold text-emerald-600 mt-0.5">£{(m.total_estimate || 0).toLocaleString("tr-TR")}</div>
                    </button>
                  ))}
                  {(pipeline.by_stage[s] || []).length === 0 && (
                    <div className="text-center text-[10px] text-stone-400 py-2">—</div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {!loading && tab === "list" && (
        list.length === 0 ? (
          <div className="text-center py-12 text-stone-400 text-sm" data-testid="meetings-empty">Henüz talep yok.</div>
        ) : (
          <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-stone-50 text-[11px] uppercase tracking-wider text-stone-500">
                <tr>
                  <th className="px-4 py-2 text-left">İsim</th>
                  <th className="px-4 py-2 text-left">Tür</th>
                  <th className="px-4 py-2 text-left">Tarih</th>
                  <th className="px-4 py-2 text-right">Kişi</th>
                  <th className="px-4 py-2 text-right">Tahmini</th>
                  <th className="px-4 py-2 text-left">Aşama</th>
                </tr>
              </thead>
              <tbody>
                {list.map(m => (
                  <tr key={m.id} onClick={() => loadDetail(m.id)}
                      className="border-t border-stone-100 cursor-pointer hover:bg-stone-50"
                      data-testid={`meetings-list-${m.id}`}>
                    <td className="px-4 py-2 font-medium">{m.name}</td>
                    <td className="px-4 py-2 text-xs">{EVENT_TYPES.find(e => e.v === m.event_type)?.l || m.event_type}</td>
                    <td className="px-4 py-2 text-xs">{m.event_date}</td>
                    <td className="px-4 py-2 text-right">{m.guests_count}</td>
                    <td className="px-4 py-2 text-right">£{(m.total_estimate || 0).toLocaleString("tr-TR")}</td>
                    <td className="px-4 py-2">
                      <span className={`text-[10px] px-1.5 py-0.5 rounded border ${STAGE_META[m.stage]?.color || ""}`}>
                        {STAGE_META[m.stage]?.label || m.stage}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}

      {!loading && tab === "analytics" && analytics && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            <KPI label="Toplam Talep (90g)" value={analytics.total_inquiries} />
            <KPI label="Kazanç Oranı" value={`${analytics.win_rate_pct}%`} color={analytics.win_rate_pct >= 30 ? "text-emerald-600" : "text-amber-600"} />
            <KPI label="Kazanılan Ciro" value={`£${(analytics.won_revenue_estimate || 0).toLocaleString("tr-TR")}`} color="text-emerald-600" />
            <KPI label="Ortalama Anlaşma" value={`£${(analytics.avg_deal_size || 0).toLocaleString("tr-TR")}`} />
          </div>
          <div className="bg-white border border-stone-200 rounded-xl p-4">
            <h3 className="text-sm font-semibold mb-3">Dönüşüm Hunisi</h3>
            <div className="space-y-1.5">
              {Object.keys(STAGE_META).map(s => {
                const count = analytics.funnel[s] || 0;
                const pct = analytics.total_inquiries ? Math.round(count / analytics.total_inquiries * 100) : 0;
                return (
                  <div key={s} className="flex items-center gap-2" data-testid={`meetings-funnel-${s}`}>
                    <div className="w-32 text-xs text-stone-700">{STAGE_META[s].label}</div>
                    <div className="flex-1 bg-stone-100 rounded h-5 relative overflow-hidden">
                      <div className={`h-full ${s === "lost" ? "bg-rose-400" : "bg-indigo-500"}`} style={{ width: `${pct}%` }}></div>
                    </div>
                    <div className="w-20 text-right text-xs">{count} ({pct}%)</div>
                  </div>
                );
              })}
            </div>
            {Object.keys(analytics.lost_reasons || {}).length > 0 && (
              <div className="mt-4 pt-3 border-t border-stone-200">
                <div className="text-xs font-semibold text-stone-600 mb-1.5">Kayıp Sebepleri</div>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(analytics.lost_reasons).map(([r, n]) => (
                    <span key={r} className="text-[10px] px-2 py-0.5 bg-rose-50 text-rose-700 rounded">
                      {r} ({n})
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </>
      )}

      {/* Detail drawer */}
      {detail && (
        <div className="fixed inset-0 bg-black/40 z-40 flex justify-end" onClick={() => setDetail(null)}>
          <div className="w-full max-w-xl bg-white h-full overflow-y-auto" onClick={e => e.stopPropagation()} data-testid="meetings-detail">
            <div className="px-5 py-3 border-b border-stone-200 flex items-center justify-between sticky top-0 bg-white">
              <div>
                <h3 className="text-base font-semibold">{detail.name}</h3>
                <div className="text-xs text-stone-500">{detail.event_date} · {detail.guests_count} kişi</div>
              </div>
              <button onClick={() => setDetail(null)}><X size={16} /></button>
            </div>
            <div className="p-5 space-y-4">
              <div>
                <div className="text-[11px] uppercase tracking-wider text-stone-500 mb-1">Aşama</div>
                <div className="flex flex-wrap gap-1">
                  {Object.keys(STAGE_META).map(s => (
                    <button key={s} onClick={() => moveStage(detail.id, s)}
                            data-testid={`meetings-stage-${s}`}
                            className={`text-[10px] px-2 py-0.5 rounded border ${detail.stage === s ? STAGE_META[s].color + " font-semibold" : "border-stone-200 text-stone-500 hover:bg-stone-50"}`}>
                      {STAGE_META[s].label}
                    </button>
                  ))}
                </div>
                {detail.stage === "lost" && detail.lost_reason && (
                  <div className="mt-1 text-[11px] text-rose-600">Sebep: {detail.lost_reason}</div>
                )}
              </div>

              <div className="grid grid-cols-2 gap-2 text-xs">
                <div><span className="text-stone-500">İletişim:</span> {detail.contact_name || "—"}</div>
                <div><span className="text-stone-500">E-posta:</span> {detail.contact_email || "—"}</div>
                <div><span className="text-stone-500">Şirket:</span> {detail.company || "—"}</div>
                <div><span className="text-stone-500">Bütçe Tahmini:</span> £{detail.budget_estimate?.toLocaleString("tr-TR") || 0}</div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-sm font-semibold">Kalemler ({detail.items?.length || 0})</h4>
                  <span className="text-sm font-semibold text-emerald-600">£{(detail.total_estimate || 0).toLocaleString("tr-TR")}</span>
                </div>
                <div className="space-y-1 mb-3">
                  {(detail.items || []).map(it => (
                    <div key={it.id} className="flex items-center gap-2 bg-stone-50 rounded px-2 py-1.5 text-xs" data-testid={`meetings-item-${it.id}`}>
                      <span className="text-[10px] px-1.5 py-0 bg-stone-200 rounded">{ITEM_KINDS.find(k => k.v === it.kind)?.l || it.kind}</span>
                      <span className="flex-1 truncate">{it.label}</span>
                      <span className="text-stone-500">{it.qty}×£{it.unit_price}</span>
                      <span className="font-semibold w-20 text-right">£{it.subtotal?.toFixed(2)}</span>
                      <button onClick={() => removeItem(it.id)} className="text-stone-400 hover:text-rose-500">
                        <Trash size={12} />
                      </button>
                    </div>
                  ))}
                </div>
                <div className="bg-stone-50 border border-stone-200 rounded p-2 space-y-2">
                  <div className="grid grid-cols-12 gap-1">
                    <select value={itemForm.kind} onChange={e => setItemForm({ ...itemForm, kind: e.target.value })}
                            className="col-span-4 text-xs px-1 py-1 border border-stone-300 rounded" data-testid="meetings-item-kind">
                      {ITEM_KINDS.map(k => <option key={k.v} value={k.v}>{k.l}</option>)}
                    </select>
                    <input placeholder="Açıklama" value={itemForm.label || ""}
                           onChange={e => setItemForm({ ...itemForm, label: e.target.value })}
                           className="col-span-4 text-xs px-2 py-1 border border-stone-300 rounded" data-testid="meetings-item-label" />
                    <input type="number" placeholder="Adet" value={itemForm.qty}
                           onChange={e => setItemForm({ ...itemForm, qty: e.target.value })}
                           className="col-span-2 text-xs px-1 py-1 border border-stone-300 rounded" />
                    <input type="number" placeholder="Birim £" value={itemForm.unit_price}
                           onChange={e => setItemForm({ ...itemForm, unit_price: e.target.value })}
                           className="col-span-2 text-xs px-1 py-1 border border-stone-300 rounded" />
                  </div>
                  <button onClick={addItem} disabled={!itemForm.label} data-testid="meetings-item-add"
                          className="w-full py-1.5 text-xs text-white bg-stone-900 rounded disabled:opacity-50">
                    Kalem Ekle
                  </button>
                </div>
              </div>

              {detail.notes && (
                <div className="bg-amber-50 border border-amber-200 rounded p-2 text-xs">
                  <div className="font-semibold mb-1">Notlar:</div>
                  <div>{detail.notes}</div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {showCreate && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={() => setShowCreate(false)}>
          <div className="bg-white rounded-xl w-full max-w-lg p-5 max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()} data-testid="meetings-create-modal">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-semibold">Yeni RFP / Talep</h3>
              <button onClick={() => setShowCreate(false)}><X size={16} /></button>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <input placeholder="Etkinlik adı" value={form.name || ""} onChange={e => setForm({ ...form, name: e.target.value })}
                     className="col-span-2 px-3 py-2 text-sm border border-stone-300 rounded-lg" data-testid="meetings-form-name" />
              <select value={form.event_type} onChange={e => setForm({ ...form, event_type: e.target.value })}
                      className="px-3 py-2 text-sm border border-stone-300 rounded-lg">
                {EVENT_TYPES.map(et => <option key={et.v} value={et.v}>{et.l}</option>)}
              </select>
              <input type="date" value={form.event_date || ""} onChange={e => setForm({ ...form, event_date: e.target.value })}
                     className="px-3 py-2 text-sm border border-stone-300 rounded-lg" data-testid="meetings-form-date" />
              <input placeholder="İletişim adı" value={form.contact_name || ""} onChange={e => setForm({ ...form, contact_name: e.target.value })}
                     className="px-3 py-2 text-sm border border-stone-300 rounded-lg" />
              <input placeholder="E-posta" type="email" value={form.contact_email || ""} onChange={e => setForm({ ...form, contact_email: e.target.value })}
                     className="px-3 py-2 text-sm border border-stone-300 rounded-lg" />
              <input type="number" placeholder="Kişi sayısı" value={form.guests_count || 0} onChange={e => setForm({ ...form, guests_count: e.target.value })}
                     className="px-3 py-2 text-sm border border-stone-300 rounded-lg" />
              <input type="number" placeholder="Oda sayısı" value={form.rooms_required || 0} onChange={e => setForm({ ...form, rooms_required: e.target.value })}
                     className="px-3 py-2 text-sm border border-stone-300 rounded-lg" />
              <input type="number" placeholder="Bütçe tahmini £" value={form.budget_estimate || 0} onChange={e => setForm({ ...form, budget_estimate: e.target.value })}
                     className="col-span-2 px-3 py-2 text-sm border border-stone-300 rounded-lg" />
              <textarea placeholder="Notlar" value={form.notes || ""} onChange={e => setForm({ ...form, notes: e.target.value })}
                        rows={2} className="col-span-2 px-3 py-2 text-sm border border-stone-300 rounded-lg" />
              <button onClick={create} disabled={!form.name || !form.event_date} data-testid="meetings-form-save"
                      className="col-span-2 py-2 text-sm text-white bg-stone-900 rounded-lg disabled:opacity-50">
                Oluştur
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function KPI({ label, value, color }) {
  return (
    <div className="bg-white border border-stone-200 rounded-xl p-3">
      <div className="text-[10px] uppercase tracking-wider text-stone-500">{label}</div>
      <div className={`text-lg font-semibold mt-0.5 ${color || "text-stone-900"}`}>{value}</div>
    </div>
  );
}
