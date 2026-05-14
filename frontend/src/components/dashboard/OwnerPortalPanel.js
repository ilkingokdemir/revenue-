import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Buildings, Plus, X, ChartLine, FilePdf } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/owners`;

export default function OwnerPortalPanel() {
  const [owners, setOwners] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(null);
  const [statement, setStatement] = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ management_fee_percent: 25 });
  const [month, setMonth] = useState(new Date().toISOString().slice(0, 7));

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(API, { withCredentials: true });
      setOwners(r.data.owners || []);
    } catch (e) { toast.error("Yüklenemedi"); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { reload(); }, [reload]);

  async function create() {
    try {
      await axios.post(API, form, { withCredentials: true });
      toast.success("Sahip eklendi");
      setShowCreate(false); setForm({ management_fee_percent: 25 });
      reload();
    } catch (e) { toast.error("Eklenemedi"); }
  }

  async function loadStatement(ownerId) {
    setSelected(ownerId);
    try {
      const r = await axios.get(`${API}/${ownerId}/statement?month=${month}`, { withCredentials: true });
      setStatement(r.data);
    } catch (e) { toast.error("Ekstre yüklenemedi"); }
  }

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="owner-portal-panel">
      <div className="flex items-start justify-between gap-4 mb-5 flex-wrap">
        <div>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
            <Buildings size={12} weight="fill" className="text-amber-500" />
            <span>Investor Suite</span>
          </div>
          <h1 className="text-2xl font-semibold text-stone-900">Sahip / Yatırımcı Portalı</h1>
          <p className="text-sm text-stone-500 mt-1 max-w-2xl">
            REIT / kondotel sahiplerine birim performansı, yönetim ücreti kesintisi sonrası net dağıtım hesapları.
          </p>
        </div>
        <button onClick={() => setShowCreate(true)} data-testid="owner-add-btn"
                className="px-3 py-1.5 text-xs text-white bg-stone-900 rounded-lg inline-flex items-center gap-1.5">
          <Plus size={13} /> Sahip Ekle
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-1 bg-white border border-stone-200 rounded-xl p-3">
          <div className="text-[11px] uppercase tracking-wider text-stone-500 mb-2 px-1">Sahipler ({owners.length})</div>
          {loading && <div className="text-xs text-stone-400 p-2">Yükleniyor…</div>}
          {!loading && owners.length === 0 && (
            <div className="text-center py-6 text-stone-400 text-xs" data-testid="owner-empty">Henüz sahip yok.</div>
          )}
          <div className="space-y-1">
            {owners.map(o => (
              <button key={o.id} onClick={() => loadStatement(o.id)}
                      data-testid={`owner-row-${o.id}`}
                      className={`w-full text-left px-3 py-2 text-sm rounded-lg ${selected === o.id ? "bg-stone-900 text-white" : "hover:bg-stone-50"}`}>
                <div className="font-medium">{o.name}</div>
                <div className={`text-[11px] ${selected === o.id ? "text-stone-300" : "text-stone-500"}`}>
                  {o.unit_count || 0} birim · %{o.management_fee_percent || 25} mgmt
                </div>
              </button>
            ))}
          </div>
        </div>

        <div className="lg:col-span-2 bg-white border border-stone-200 rounded-xl p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold inline-flex items-center gap-1.5">
              <ChartLine size={14} /> Aylık Ekstre
            </h3>
            <div className="flex items-center gap-2">
              <input type="month" value={month} onChange={e => { setMonth(e.target.value); if (selected) loadStatement(selected); }}
                     className="text-xs px-2 py-1 border border-stone-300 rounded" data-testid="owner-month" />
              {selected && (
                <a href={`${API}/${selected}/statement.pdf?month=${month}`} target="_blank" rel="noreferrer"
                   data-testid="owner-pdf-btn"
                   className="text-xs px-2 py-1 bg-rose-50 text-rose-700 border border-rose-200 rounded inline-flex items-center gap-1 hover:bg-rose-100">
                  <FilePdf size={12} /> PDF
                </a>
              )}
            </div>
          </div>
          {!statement && <div className="text-center py-12 text-stone-400 text-sm">Sol taraftan bir sahip seçin.</div>}
          {statement && (
            <div className="space-y-3" data-testid="owner-statement">
              <div className="grid grid-cols-2 gap-3">
                <Metric label="Brüt Gelir" value={`£${statement.gross_revenue?.toFixed(2)}`} />
                <Metric label="Sahip Payı (Brüt)" value={`£${statement.owner_share_gross?.toFixed(2)}`} />
                <Metric label={`Yönetim Ücreti (%${statement.management_fee_percent})`} value={`-£${statement.management_fee?.toFixed(2)}`} negative />
                <Metric label="Tahmini OpEx" value={`-£${statement.operating_costs_est?.toFixed(2)}`} negative />
              </div>
              <div className="border-t border-stone-200 pt-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-stone-600">Net Dağıtım</span>
                  <span className="text-xl font-semibold text-emerald-600">£{statement.net_distribution?.toFixed(2)}</span>
                </div>
                <div className="text-[11px] text-stone-400 mt-1">{statement.bookings_count} rezervasyon · {statement.nights_sold} gece</div>
              </div>
            </div>
          )}
        </div>
      </div>

      {showCreate && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={() => setShowCreate(false)}>
          <div className="bg-white rounded-xl w-full max-w-md p-5" onClick={e => e.stopPropagation()} data-testid="owner-create-modal">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-semibold">Yeni Sahip</h3>
              <button onClick={() => setShowCreate(false)}><X size={16} /></button>
            </div>
            <div className="space-y-3">
              <input placeholder="Ad Soyad" value={form.name || ""} onChange={e => setForm({ ...form, name: e.target.value })}
                     className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg" data-testid="owner-form-name" />
              <input placeholder="E-posta" type="email" value={form.email || ""} onChange={e => setForm({ ...form, email: e.target.value })}
                     className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg" data-testid="owner-form-email" />
              <input placeholder="Telefon" value={form.phone || ""} onChange={e => setForm({ ...form, phone: e.target.value })}
                     className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg" />
              <input placeholder="Şirket" value={form.company || ""} onChange={e => setForm({ ...form, company: e.target.value })}
                     className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg" />
              <label className="block text-xs text-stone-600">
                Yönetim Ücreti (%)
                <input type="number" value={form.management_fee_percent || 25}
                       onChange={e => setForm({ ...form, management_fee_percent: Number(e.target.value) })}
                       className="w-full mt-1 px-3 py-2 text-sm border border-stone-300 rounded-lg" />
              </label>
              <button onClick={create} disabled={!form.name || !form.email} data-testid="owner-form-save"
                      className="w-full py-2 text-sm text-white bg-stone-900 rounded-lg disabled:opacity-50">
                Kaydet
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Metric({ label, value, negative }) {
  return (
    <div className="bg-stone-50 rounded-lg p-3">
      <div className="text-[10px] uppercase tracking-wider text-stone-500">{label}</div>
      <div className={`text-base font-semibold mt-0.5 ${negative ? "text-rose-600" : "text-stone-900"}`}>{value}</div>
    </div>
  );
}
