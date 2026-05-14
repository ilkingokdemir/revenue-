import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { ForkKnife, Plus, X, ArrowsClockwise, Plug, Trash, Receipt, CheckCircle } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/fnb-pos`;

const STATUS_META = {
  ok:       { color: "bg-emerald-100 text-emerald-700", label: "Bağlı" },
  error:    { color: "bg-rose-100 text-rose-700",       label: "Hata" },
  untested: { color: "bg-stone-100 text-stone-600",     label: "Test edilmedi" },
};

export default function FnbPosHubPanel({ propertyId = "all" }) {
  const [tab, setTab] = useState("connections");
  const [conns, setConns] = useState([]);
  const [providers, setProviders] = useState([]);
  const [receipts, setReceipts] = useState([]);
  const [recon, setRecon] = useState(null);
  const [reconDate, setReconDate] = useState(new Date().toISOString().slice(0, 10));
  const [loading, setLoading] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ provider: "mock", credentials: {} });
  const [postingReceipt, setPostingReceipt] = useState(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      if (tab === "connections") {
        const [c, p] = await Promise.all([
          axios.get(`${API}/connections?property_id=${propertyId}`, { withCredentials: true }),
          axios.get(`${API}/providers`, { withCredentials: true }),
        ]);
        setConns(c.data.connections || []);
        setProviders(p.data.providers || []);
      } else if (tab === "receipts") {
        const r = await axios.get(`${API}/receipts?property_id=${propertyId}&limit=100`, { withCredentials: true });
        setReceipts(r.data.receipts || []);
      } else if (tab === "reconciliation") {
        const pid = propertyId === "all" ? "default" : propertyId;
        const r = await axios.get(`${API}/reconciliation/${pid}?date=${reconDate}`, { withCredentials: true });
        setRecon(r.data);
      }
    } catch (e) { toast.error("Yüklenemedi"); }
    finally { setLoading(false); }
  }, [tab, propertyId, reconDate]);

  useEffect(() => { reload(); }, [reload]);

  const selectedProvider = providers.find(p => p.id === form.provider);

  async function createConn() {
    try {
      await axios.post(`${API}/connections`, {
        property_id: propertyId === "all" ? "default" : propertyId,
        provider: form.provider,
        name: form.name || `${form.provider}-${Date.now()}`,
        outlet_name: form.outlet_name || "Restaurant",
        credentials: form.credentials || {},
      }, { withCredentials: true });
      toast.success("Bağlantı oluşturuldu");
      setShowCreate(false); setForm({ provider: "mock", credentials: {} });
      reload();
    } catch (e) { toast.error(e?.response?.data?.detail || "Eklenemedi"); }
  }

  async function testConn(id) {
    try {
      const r = await axios.post(`${API}/connections/${id}/test`, {}, { withCredentials: true });
      toast[r.data.ok ? "success" : "error"](r.data.ok ? `Bağlantı OK · ${r.data.latency_ms}ms` : "Bağlantı başarısız");
      reload();
    } catch (e) { toast.error("Test başarısız"); }
  }

  async function syncConn(id) {
    try {
      const r = await axios.post(`${API}/connections/${id}/sync`, {}, { withCredentials: true });
      toast.success(`${r.data.inserted} yeni fiş senkronize edildi (${r.data.fetched} alındı)`);
      reload();
    } catch (e) { toast.error("Senkronize edilemedi"); }
  }

  async function deleteConn(id) {
    if (!window.confirm("Bağlantı silinsin mi?")) return;
    try {
      await axios.delete(`${API}/connections/${id}`, { withCredentials: true });
      reload();
    } catch (e) { toast.error("Silinemedi"); }
  }

  async function postToFolio() {
    if (!postingReceipt) return;
    const ref = window.prompt("Booking referansı veya oda numarası:", "");
    if (!ref) return;
    try {
      const body = ref.match(/^\d+$/) ? { room_number: ref } : { booking_ref: ref };
      const r = await axios.post(`${API}/receipts/${postingReceipt.id}/post-to-folio`, body, { withCredentials: true });
      toast.success(`Folio'ya £${r.data.amount.toFixed(2)} aktarıldı`);
      setPostingReceipt(null); reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Aktarım başarısız");
    }
  }

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="fnb-pos-hub-panel">
      <div className="mb-4 flex items-start justify-between gap-3 flex-wrap">
        <div>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
            <ForkKnife size={12} weight="fill" className="text-orange-500" />
            <span>F&B POS Integration</span>
          </div>
          <h1 className="text-2xl font-semibold text-stone-900">POS Entegrasyon Merkezi</h1>
          <p className="text-sm text-stone-500 mt-1 max-w-2xl">
            Simphony / Lightspeed / Square / Toast adaptörleri — fişleri otomatik çek, oda folio'suna aktar, günlük mutabakatı tek tıkla yap.
          </p>
        </div>
        {tab === "connections" && (
          <button onClick={() => setShowCreate(true)} data-testid="pos-new-conn-btn"
                  className="px-3 py-1.5 text-xs text-white bg-stone-900 rounded-lg inline-flex items-center gap-1.5">
            <Plus size={13} /> Yeni Bağlantı
          </button>
        )}
      </div>

      <div className="flex gap-1 mb-4 border-b border-stone-200">
        {[
          { id: "connections", label: "Bağlantılar", icon: Plug },
          { id: "receipts", label: "Fişler", icon: Receipt },
          { id: "reconciliation", label: "Mutabakat", icon: CheckCircle },
        ].map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} data-testid={`pos-tab-${t.id}`}
                  className={`px-4 py-2 text-xs font-medium border-b-2 inline-flex items-center gap-1.5 ${tab === t.id ? "border-stone-900 text-stone-900" : "border-transparent text-stone-500"}`}>
            <t.icon size={12} /> {t.label}
          </button>
        ))}
      </div>

      {loading && <div className="text-center py-12 text-stone-400 text-sm">Yükleniyor…</div>}

      {!loading && tab === "connections" && (
        conns.length === 0 ? (
          <div className="text-center py-12 text-stone-400 text-sm" data-testid="pos-empty-conns">
            Henüz POS bağlantısı yok. "Yeni Bağlantı" ile başlayın (test için <code className="bg-stone-100 px-1 rounded">mock</code> sağlayıcısını seçin).
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {conns.map(c => (
              <div key={c.id} className="bg-white border border-stone-200 rounded-xl p-4" data-testid={`pos-conn-${c.id}`}>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="text-sm font-semibold">{c.name || c.provider}</div>
                    <div className="text-[11px] text-stone-500 mt-0.5">{c.provider} · {c.outlet_name}</div>
                  </div>
                  <span className={`text-[10px] px-2 py-0.5 rounded ${STATUS_META[c.status]?.color || ""}`}>
                    {STATUS_META[c.status]?.label || c.status}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-1 mt-3 text-[11px] text-stone-500">
                  <div>Fişler: <span className="text-stone-700 font-medium">{c.receipts_count || 0}</span></div>
                  <div>Son sync: <span className="text-stone-700">{c.last_sync_at ? new Date(c.last_sync_at).toLocaleString("tr-TR") : "—"}</span></div>
                </div>
                <div className="flex gap-1 mt-3">
                  <button onClick={() => testConn(c.id)} className="flex-1 text-xs px-2 py-1.5 bg-white border border-stone-300 rounded inline-flex items-center justify-center gap-1" data-testid={`pos-test-${c.id}`}>
                    <Plug size={12} /> Test
                  </button>
                  <button onClick={() => syncConn(c.id)} className="flex-1 text-xs px-2 py-1.5 bg-stone-900 text-white rounded inline-flex items-center justify-center gap-1" data-testid={`pos-sync-${c.id}`}>
                    <ArrowsClockwise size={12} /> Sync
                  </button>
                  <button onClick={() => deleteConn(c.id)} className="text-xs px-2 py-1.5 text-stone-400 hover:text-rose-500" data-testid={`pos-del-${c.id}`}>
                    <Trash size={12} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )
      )}

      {!loading && tab === "receipts" && (
        receipts.length === 0 ? (
          <div className="text-center py-12 text-stone-400 text-sm" data-testid="pos-empty-receipts">
            Fiş yok. Bağlantı sayfasından "Sync" tuşuna basın.
          </div>
        ) : (
          <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-stone-50 text-[11px] uppercase tracking-wider text-stone-500">
                <tr>
                  <th className="px-4 py-2 text-left">Fiş</th>
                  <th className="px-4 py-2 text-left">Outlet</th>
                  <th className="px-4 py-2 text-left">Zaman</th>
                  <th className="px-4 py-2 text-left">Masa</th>
                  <th className="px-4 py-2 text-right">Tutar</th>
                  <th className="px-4 py-2 text-left">Ödeme</th>
                  <th className="px-4 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {receipts.map(r => (
                  <tr key={r.id} className="border-t border-stone-100" data-testid={`pos-receipt-${r.id}`}>
                    <td className="px-4 py-2 text-xs font-mono">{r.external_id}</td>
                    <td className="px-4 py-2 text-xs">{r.outlet_name}</td>
                    <td className="px-4 py-2 text-xs">{new Date(r.closed_at).toLocaleString("tr-TR")}</td>
                    <td className="px-4 py-2 text-xs">{r.table || "—"}</td>
                    <td className="px-4 py-2 text-right font-semibold">£{r.total?.toFixed(2)}</td>
                    <td className="px-4 py-2 text-xs">{r.payment_type}</td>
                    <td className="px-4 py-2 text-right">
                      {r.posted_to_folio ? (
                        <span className="text-[10px] text-emerald-600 inline-flex items-center gap-1">
                          <CheckCircle size={11} weight="fill" /> Folio
                        </span>
                      ) : r.payment_type === "room_charge" ? (
                        <button onClick={() => setPostingReceipt(r)} data-testid={`pos-post-${r.id}`}
                                className="text-[10px] px-2 py-1 bg-amber-50 text-amber-700 border border-amber-200 rounded hover:bg-amber-100">
                          Folio'ya at
                        </button>
                      ) : (
                        <span className="text-[10px] text-stone-400">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}

      {!loading && tab === "reconciliation" && (
        <>
          <div className="mb-3 flex items-center gap-2">
            <input type="date" value={reconDate} onChange={e => setReconDate(e.target.value)}
                   data-testid="pos-recon-date"
                   className="text-xs px-2 py-1 border border-stone-300 rounded" />
          </div>
          {!recon ? (
            <div className="text-center py-12 text-stone-400 text-sm">Yükleniyor…</div>
          ) : recon.receipts_count === 0 ? (
            <div className="text-center py-12 text-stone-400 text-sm" data-testid="pos-recon-empty">
              Bu tarihte fiş yok.
            </div>
          ) : (
            <div className="space-y-4" data-testid="pos-recon-data">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <KPI label="Fiş Sayısı" value={recon.receipts_count} />
                <KPI label="Brüt Toplam" value={`£${recon.gross_total?.toFixed(2)}`} color="text-stone-900" />
                <KPI label="Folio'ya Aktarılan" value={`£${recon.posted_to_folio_total?.toFixed(2)}`} color="text-emerald-600" />
                <KPI label="Nakit/Kart" value={`£${recon.cash_card_total?.toFixed(2)}`} color="text-sky-600" />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <Breakdown title="Outlet'e Göre" data={recon.by_outlet} />
                <Breakdown title="Ödeme Tipine Göre" data={recon.by_payment} />
              </div>
            </div>
          )}
        </>
      )}

      {showCreate && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={() => setShowCreate(false)}>
          <div className="bg-white rounded-xl w-full max-w-md p-5 max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()} data-testid="pos-create-modal">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-semibold">Yeni POS Bağlantısı</h3>
              <button onClick={() => setShowCreate(false)}><X size={16} /></button>
            </div>
            <div className="space-y-3">
              <select value={form.provider} onChange={e => setForm({ ...form, provider: e.target.value, credentials: {} })}
                      className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg" data-testid="pos-form-provider">
                {providers.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
              <input placeholder="Bağlantı adı" value={form.name || ""} onChange={e => setForm({ ...form, name: e.target.value })}
                     className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg" />
              <input placeholder="Outlet (restoran/bar)" value={form.outlet_name || ""} onChange={e => setForm({ ...form, outlet_name: e.target.value })}
                     className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg" />
              {(selectedProvider?.required_fields || []).map(f => (
                <input key={f} placeholder={f} value={form.credentials[f] || ""}
                       onChange={e => setForm({ ...form, credentials: { ...form.credentials, [f]: e.target.value } })}
                       className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg font-mono"
                       data-testid={`pos-cred-${f}`} />
              ))}
              {selectedProvider?.required_fields?.length === 0 && (
                <p className="text-[11px] text-stone-500">Mock provider kimlik gerektirmez — direkt kullanılabilir.</p>
              )}
              <button onClick={createConn} data-testid="pos-form-save"
                      className="w-full py-2 text-sm text-white bg-stone-900 rounded-lg">
                Oluştur
              </button>
            </div>
          </div>
        </div>
      )}

      {postingReceipt && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={() => setPostingReceipt(null)}>
          <div className="bg-white rounded-xl w-full max-w-md p-5" onClick={e => e.stopPropagation()}>
            <h3 className="text-base font-semibold mb-3">Folio'ya Aktar</h3>
            <div className="bg-stone-50 rounded p-3 text-xs mb-3">
              <div>Fiş: <span className="font-mono">{postingReceipt.external_id}</span></div>
              <div>Toplam: <b>£{postingReceipt.total?.toFixed(2)}</b></div>
            </div>
            <p className="text-xs text-stone-500 mb-3">Booking referansı veya oda numarası gireceksiniz.</p>
            <div className="flex gap-2">
              <button onClick={postToFolio} className="flex-1 py-2 text-xs text-white bg-stone-900 rounded-lg">Devam</button>
              <button onClick={() => setPostingReceipt(null)} className="flex-1 py-2 text-xs text-stone-700 bg-white border border-stone-300 rounded-lg">İptal</button>
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

function Breakdown({ title, data }) {
  const entries = Object.entries(data || {});
  const max = Math.max(1, ...entries.map(([, v]) => v));
  return (
    <div className="bg-white border border-stone-200 rounded-xl p-4">
      <div className="text-sm font-semibold mb-2">{title}</div>
      <div className="space-y-1.5">
        {entries.map(([k, v]) => (
          <div key={k} className="flex items-center gap-2 text-xs">
            <div className="w-24 truncate">{k}</div>
            <div className="flex-1 bg-stone-100 rounded h-3 overflow-hidden">
              <div className="h-full bg-orange-400" style={{ width: `${(v / max) * 100}%` }}></div>
            </div>
            <div className="w-16 text-right">£{v.toFixed(2)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
