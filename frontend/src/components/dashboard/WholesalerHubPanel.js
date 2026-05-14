/**
 * WholesalerHubPanel — Cloudbeds Hotel Trader parity.
 *
 * Manages wholesaler (HotelBeds/TBO/Travelgate/GTA) connections,
 * inbound bookings, sync queue.
 */
import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Globe, Plus, ArrowsClockwise, CheckCircle, X, Trash } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/wholesaler`;

export default function WholesalerHubPanel({ propertyId }) {
  const [tab, setTab] = useState("connections");
  const [providers, setProviders] = useState([]);
  const [conns, setConns] = useState([]);
  const [inbound, setInbound] = useState([]);
  const [queue, setQueue] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ provider: "mock", commission_percent: 10 });
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    try {
      const p = await axios.get(`${API}/providers`, { withCredentials: true });
      setProviders(p.data.items || []);
      const c = await axios.get(`${API}/connections${propertyId ? `?property_id=${propertyId}` : ""}`, { withCredentials: true });
      setConns(c.data.items || []);
      const i = await axios.get(`${API}/inbound-bookings${propertyId ? `?property_id=${propertyId}` : ""}`, { withCredentials: true });
      setInbound(i.data.items || []);
      const q = await axios.get(`${API}/queue`, { withCredentials: true });
      setQueue(q.data.items || []);
    } catch (e) { toast.error("Yüklenemedi"); }
  }, [propertyId]);

  useEffect(() => { reload(); }, [reload]);

  async function connect() {
    try {
      await axios.post(`${API}/connections`,
        { ...form, property_id: propertyId },
        { withCredentials: true });
      toast.success("Bağlantı eklendi");
      setShowAdd(false);
      setForm({ provider: "mock", commission_percent: 10 });
      reload();
    } catch (e) { toast.error(e?.response?.data?.detail || "Hata"); }
  }

  async function test(id) {
    try {
      const r = await axios.post(`${API}/connections/${id}/test`, {}, { withCredentials: true });
      toast.success(r.data.ok ? "Online" : "Hata");
      reload();
    } catch (e) { toast.error("Hata"); }
  }

  async function del(id) {
    if (!window.confirm("Sil?")) return;
    try {
      await axios.delete(`${API}/connections/${id}`, { withCredentials: true });
      reload();
    } catch (e) { toast.error("Hata"); }
  }

  async function dispatch() {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/dispatch`, {}, { withCredentials: true });
      toast.success(`${r.data.total_new} yeni rezervasyon çekildi`);
      reload();
    } catch (e) { toast.error("Hata"); }
    finally { setBusy(false); }
  }

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="wholesaler-hub-panel">
      <div className="flex items-start justify-between gap-4 mb-5 flex-wrap">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">Cloudbeds Hotel Trader parity</div>
          <h2 className="text-2xl font-semibold text-stone-900 inline-flex items-center gap-2">
            <Globe size={22} weight="fill" className="text-blue-600" /> Wholesaler / Net Rate Ağı
          </h2>
          <p className="text-sm text-stone-500 mt-1">
            HotelBeds (60k acenta) + TBO (22k) + Travelgate (140 partner) + GTA + Mock. Hot-swap mimari.
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={dispatch} disabled={busy} data-testid="ws-dispatch-btn"
                  className="text-sm px-3 py-1.5 bg-blue-600 text-white rounded-lg inline-flex items-center gap-1.5 hover:bg-blue-700 disabled:opacity-50">
            <ArrowsClockwise size={13} weight="bold" /> {busy ? "Çekiliyor..." : "Tüm Bağlantıları Tara"}
          </button>
          <button onClick={() => setShowAdd(true)} data-testid="ws-add-btn"
                  className="text-sm px-3 py-1.5 bg-stone-900 text-white rounded-lg inline-flex items-center gap-1.5">
            <Plus size={13} /> Bağlan
          </button>
        </div>
      </div>

      <div className="flex gap-1 border-b border-stone-200 mb-4">
        {[{k:"connections",l:`Bağlantılar (${conns.length})`},{k:"inbound",l:`Gelen Rezervasyonlar (${inbound.length})`},{k:"queue",l:`Kuyruk (${queue.length})`}].map(t => (
          <button key={t.k} onClick={() => setTab(t.k)} data-testid={`ws-tab-${t.k}`}
                  className={`px-3 py-2 text-xs font-medium border-b-2 ${tab===t.k ? "border-blue-600 text-blue-700":"border-transparent text-stone-500"}`}>
            {t.l}
          </button>
        ))}
      </div>

      {tab === "connections" && (
        <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-stone-50 text-[11px] uppercase tracking-wider text-stone-500">
              <tr>
                <th className="px-4 py-2 text-left">Sağlayıcı</th>
                <th className="px-4 py-2 text-left">Mülk</th>
                <th className="px-4 py-2 text-right">Komisyon</th>
                <th className="px-4 py-2 text-right">Gelen</th>
                <th className="px-4 py-2 text-right">Push</th>
                <th className="px-4 py-2 text-center">Durum</th>
                <th className="px-4 py-2 text-right">İşlem</th>
              </tr>
            </thead>
            <tbody>
              {conns.map(c => {
                const prov = providers.find(p => p.id === c.provider);
                return (
                  <tr key={c.id} className="border-t border-stone-100" data-testid={`ws-conn-${c.id}`}>
                    <td className="px-4 py-2">
                      <div className="font-medium">{prov?.label || c.provider}</div>
                      {prov && <div className="text-[10px] text-stone-400">{prov.partner_count_global.toLocaleString()} global partner</div>}
                    </td>
                    <td className="px-4 py-2 text-xs">{c.property_id}</td>
                    <td className="px-4 py-2 text-right">%{c.commission_percent}</td>
                    <td className="px-4 py-2 text-right">{c.inbound_count || 0}</td>
                    <td className="px-4 py-2 text-right">{c.push_count || 0}</td>
                    <td className="px-4 py-2 text-center">
                      <span className={`text-[10px] px-2 py-0.5 rounded-full ${
                        c.status==="online" ? "bg-emerald-100 text-emerald-700":
                        c.status==="error" ? "bg-rose-100 text-rose-700":
                        "bg-amber-100 text-amber-700"
                      }`}>{c.status}</span>
                    </td>
                    <td className="px-4 py-2 text-right">
                      <div className="flex gap-1 justify-end">
                        <button onClick={() => test(c.id)} data-testid={`ws-test-${c.id}`}
                                className="text-[10px] px-2 py-0.5 bg-stone-100 rounded hover:bg-stone-200">
                          Test
                        </button>
                        <button onClick={() => del(c.id)} className="text-rose-600 hover:bg-rose-50 p-1 rounded">
                          <Trash size={12} />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
              {conns.length === 0 && (
                <tr><td colSpan={7} className="px-4 py-10 text-center text-stone-400 text-xs">Bağlantı yok. "Bağlan" butonuyla başlayın.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {tab === "inbound" && (
        <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-stone-50 text-[11px] uppercase tracking-wider text-stone-500">
              <tr>
                <th className="px-4 py-2 text-left">Tarih</th>
                <th className="px-4 py-2 text-left">Sağlayıcı</th>
                <th className="px-4 py-2 text-left">Misafir</th>
                <th className="px-4 py-2 text-left">Konaklama</th>
                <th className="px-4 py-2 text-right">Net Fiyat</th>
                <th className="px-4 py-2 text-right">Komisyon %</th>
                <th className="px-4 py-2 text-left">External ID</th>
              </tr>
            </thead>
            <tbody>
              {inbound.map(b => (
                <tr key={b.id} className="border-t border-stone-100" data-testid={`ws-inbound-${b.id}`}>
                  <td className="px-4 py-2 text-xs">{b.received_at?.slice(0, 19)?.replace("T", " ")}</td>
                  <td className="px-4 py-2 text-xs"><span className="bg-blue-100 text-blue-800 px-1.5 py-0.5 rounded">{b.provider}</span></td>
                  <td className="px-4 py-2">{b.guest_name}</td>
                  <td className="px-4 py-2 text-xs">{b.check_in} → {b.check_out}</td>
                  <td className="px-4 py-2 text-right font-semibold">{b.net_rate} {b.currency}</td>
                  <td className="px-4 py-2 text-right">%{b.commission_percent}</td>
                  <td className="px-4 py-2 text-[10px] font-mono">{b.external_id}</td>
                </tr>
              ))}
              {inbound.length === 0 && (
                <tr><td colSpan={7} className="px-4 py-10 text-center text-stone-400 text-xs">Gelen rezervasyon yok. "Tüm Bağlantıları Tara" butonuna basın.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {tab === "queue" && (
        <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-stone-50 text-[11px] uppercase tracking-wider text-stone-500">
              <tr>
                <th className="px-4 py-2 text-left">Zaman</th>
                <th className="px-4 py-2 text-left">Sağlayıcı</th>
                <th className="px-4 py-2 text-left">Aksiyon</th>
                <th className="px-4 py-2 text-center">Durum</th>
                <th className="px-4 py-2 text-left">Referans</th>
              </tr>
            </thead>
            <tbody>
              {queue.map(j => (
                <tr key={j.id} className="border-t border-stone-100">
                  <td className="px-4 py-2 text-xs">{j.created_at?.slice(0,19)?.replace("T"," ")}</td>
                  <td className="px-4 py-2 text-xs">{j.provider}</td>
                  <td className="px-4 py-2 text-xs">{j.action}</td>
                  <td className="px-4 py-2 text-center">
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700">{j.status}</span>
                  </td>
                  <td className="px-4 py-2 text-[10px] font-mono">{j.result?.reference}</td>
                </tr>
              ))}
              {queue.length === 0 && <tr><td colSpan={5} className="px-4 py-10 text-center text-stone-400 text-xs">Kuyruk boş.</td></tr>}
            </tbody>
          </table>
        </div>
      )}

      {showAdd && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl w-full max-w-md shadow-xl">
            <div className="flex items-center justify-between p-4 border-b border-stone-200">
              <h3 className="text-base font-semibold">Yeni Wholesaler Bağlantısı</h3>
              <button onClick={() => setShowAdd(false)} className="text-stone-400">✕</button>
            </div>
            <div className="p-4 space-y-2">
              <label className="block">
                <span className="text-xs text-stone-700">Sağlayıcı</span>
                <select value={form.provider} onChange={e => setForm({...form, provider:e.target.value})}
                        data-testid="ws-form-provider"
                        className="w-full px-3 py-1.5 text-sm border border-stone-300 rounded-lg mt-1">
                  {providers.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
                </select>
              </label>
              <label className="block">
                <span className="text-xs text-stone-700">Komisyon %</span>
                <input value={form.commission_percent} type="number"
                       onChange={e => setForm({...form, commission_percent:parseFloat(e.target.value)||10})}
                       className="w-full px-3 py-1.5 text-sm border border-stone-300 rounded-lg mt-1" />
              </label>
              <label className="block">
                <span className="text-xs text-stone-700">Etiket</span>
                <input value={form.label||""}
                       onChange={e => setForm({...form, label:e.target.value})}
                       placeholder="örn. Antalya - HotelBeds prod"
                       className="w-full px-3 py-1.5 text-sm border border-stone-300 rounded-lg mt-1" />
              </label>
              <div className="text-[10px] text-stone-500 bg-amber-50 border border-amber-200 rounded p-2">
                ℹ Gerçek API anahtarları geldiğinde, <code>credentials</code> alanını sağlayıcıya göre PATCH ile güncelleyin.
                Şimdilik tüm adapter'lar mock modunda çalışır.
              </div>
            </div>
            <div className="p-4 border-t border-stone-200 flex justify-end gap-2">
              <button onClick={() => setShowAdd(false)} className="text-xs px-3 py-1.5 border border-stone-300 rounded-lg">İptal</button>
              <button onClick={connect} data-testid="ws-form-save" className="text-xs px-3 py-1.5 bg-stone-900 text-white rounded-lg">Bağlan</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
