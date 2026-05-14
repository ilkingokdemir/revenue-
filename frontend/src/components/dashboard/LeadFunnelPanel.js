/**
 * LeadFunnelPanel — Web Concierge → CRM lead pipeline + Lighthouse refresh.
 */
import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Funnel, ArrowsClockwise, ChartLineUp } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function LeadFunnelPanel({ propertyId }) {
  const [leads, setLeads] = useState([]);
  const [counts, setCounts] = useState({});
  const [filter, setFilter] = useState("");
  const [lhStatus, setLhStatus] = useState(null);
  const [lhSnapshot, setLhSnapshot] = useState(null);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    if (!propertyId) return;
    try {
      const r = await axios.get(
        `${API}/lead-funnel/leads?property_id=${propertyId}${filter ? `&status=${filter}` : ""}`,
        { withCredentials: true });
      setLeads(r.data.items || []);
      setCounts(r.data.counts_by_status || {});
      const l = await axios.get(`${API}/lighthouse-adapter/status`, { withCredentials: true });
      setLhStatus(l.data);
    } catch (e) { toast.error("Yüklenemedi"); }
  }, [propertyId, filter]);

  useEffect(() => { reload(); }, [reload]);

  async function ingest() {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/lead-funnel/ingest-concierge-sessions/${propertyId}`,
        { limit: 100, cutoff_hours: 168 }, { withCredentials: true });
      toast.success(`${r.data.created} yeni lead, ${r.data.skipped_duplicates} duplicate atlandı`);
      reload();
    } catch (e) { toast.error("Hata"); }
    finally { setBusy(false); }
  }

  async function updateStatus(id, status) {
    try {
      await axios.patch(`${API}/lead-funnel/leads/${id}`, { status }, { withCredentials: true });
      reload();
    } catch (e) { toast.error("Hata"); }
  }

  async function refreshLighthouse() {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/lighthouse-adapter/refresh/${propertyId}`,
        {}, { withCredentials: true });
      setLhSnapshot(r.data);
      toast.success(`${r.data.competitors.length} rakip tarandı`);
    } catch (e) { toast.error("Hata"); }
    finally { setBusy(false); }
  }

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="lead-funnel-panel">
      <div className="mb-5">
        <div className="text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">Web Concierge → CRM Funnel</div>
        <h2 className="text-2xl font-semibold text-stone-900 inline-flex items-center gap-2">
          <Funnel size={22} weight="fill" className="text-cyan-600" /> Lead Funnel & Compset Hub
        </h2>
        <p className="text-sm text-stone-500 mt-1">
          AI Concierge'in topladığı niyetli misafir sorularını CRM lead'ine dönüştürür.
          Lighthouse adapter compset rate'leri hot-swap eder.
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-5">
        <KPI label="Yeni" value={counts.new || 0} color="text-amber-600" />
        <KPI label="İletişimde" value={counts.contacted || 0} />
        <KPI label="Kalifiye" value={counts.qualified || 0} color="text-indigo-600" />
        <KPI label="Kazanıldı" value={counts.won || 0} color="text-emerald-600" />
        <KPI label="Kaybedildi" value={counts.lost || 0} color="text-rose-600" />
      </div>

      <div className="grid lg:grid-cols-3 gap-4 mb-4">
        <div className="lg:col-span-2 bg-white border border-stone-200 rounded-xl p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold inline-flex items-center gap-1.5">
              <Funnel size={14} weight="fill" /> CRM Lead Pipeline
            </h3>
            <div className="flex gap-2">
              <select value={filter} onChange={e => setFilter(e.target.value)}
                      data-testid="lf-filter-select"
                      className="px-2 py-1 text-xs border border-stone-300 rounded">
                <option value="">Tümü</option>
                <option value="new">Yeni</option>
                <option value="contacted">İletişimde</option>
                <option value="qualified">Kalifiye</option>
                <option value="won">Kazanıldı</option>
                <option value="lost">Kaybedildi</option>
              </select>
              <button onClick={ingest} disabled={busy} data-testid="lf-ingest-btn"
                      className="text-xs px-3 py-1 bg-cyan-600 text-white rounded inline-flex items-center gap-1 hover:bg-cyan-700 disabled:opacity-50">
                <ArrowsClockwise size={11} /> {busy ? "..." : "Concierge'den İçeri Aktar"}
              </button>
            </div>
          </div>
          <div className="max-h-[500px] overflow-y-auto">
            {leads.map(l => (
              <div key={l.id} data-testid={`lf-lead-${l.id}`}
                   className="border-t border-stone-100 first:border-t-0 py-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium truncate">{l.intent_summary || "(intent yok)"}</div>
                    <div className="text-xs text-stone-500 mt-0.5">
                      {l.email && <span className="mr-2">✉ {l.email}</span>}
                      {l.phone && <span className="mr-2">☎ {l.phone}</span>}
                      <span>{l.message_count} msg · score {l.intent_score}</span>
                    </div>
                    <div className="text-[10px] text-stone-400 mt-0.5">{l.last_activity_at?.slice(0, 19).replace("T", " ")}</div>
                  </div>
                  <select value={l.status} onChange={e => updateStatus(l.id, e.target.value)}
                          data-testid={`lf-status-${l.id}`}
                          className="text-[10px] px-2 py-0.5 rounded border border-stone-300">
                    <option value="new">Yeni</option>
                    <option value="contacted">İletişimde</option>
                    <option value="qualified">Kalifiye</option>
                    <option value="won">Kazanıldı</option>
                    <option value="lost">Kaybedildi</option>
                  </select>
                </div>
              </div>
            ))}
            {leads.length === 0 && (
              <div className="text-center py-10 text-stone-400 text-xs">
                Henüz lead yok. "Concierge'den İçeri Aktar" butonuyla başlayın.
              </div>
            )}
          </div>
        </div>

        <div className="bg-white border border-stone-200 rounded-xl p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold inline-flex items-center gap-1.5">
              <ChartLineUp size={14} weight="fill" className="text-cyan-600" /> Lighthouse Compset
            </h3>
            <button onClick={refreshLighthouse} disabled={busy} data-testid="lh-refresh-btn"
                    className="text-xs px-2 py-1 bg-cyan-600 text-white rounded inline-flex items-center gap-1 hover:bg-cyan-700 disabled:opacity-50">
              <ArrowsClockwise size={11} /> Tara
            </button>
          </div>
          {lhStatus && (
            <div className={`text-xs p-2 rounded mb-3 ${
              lhStatus.real_data ? "bg-emerald-50 text-emerald-800" : "bg-amber-50 text-amber-800"
            }`} data-testid="lh-status">
              <div className="font-semibold mb-0.5">{lhStatus.provider}</div>
              <div className="text-[10px]">{lhStatus.note}</div>
            </div>
          )}
          {lhSnapshot && (
            <div data-testid="lh-snapshot">
              <div className="text-xs text-stone-500 mb-2">
                Veri noktası: {lhSnapshot.data_points_sampled?.toLocaleString()}<br/>
                Pazar ortalaması: <b>£{lhSnapshot.market_average}</b>
              </div>
              <div className="space-y-1.5">
                {lhSnapshot.competitors.map((c, i) => (
                  <div key={i} className="flex justify-between text-xs px-2 py-1 bg-stone-50 rounded">
                    <span>{c.name}</span>
                    <span className="font-semibold">£{c.rate_today}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function KPI({ label, value, color }) {
  return (
    <div className="bg-white border border-stone-200 rounded-xl p-3">
      <div className="text-[10px] uppercase tracking-wider text-stone-500">{label}</div>
      <div className={`text-xl font-semibold mt-1 ${color || "text-stone-900"}`}>{value}</div>
    </div>
  );
}
