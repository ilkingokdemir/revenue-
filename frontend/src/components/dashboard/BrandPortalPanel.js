import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Buildings,
  TrendUp,
  Star,
  Warning,
  Palette,
  ArrowsClockwise,
  CheckCircle,
} from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

export default function BrandPortalPanel({ hotelName }) {
  const [tab, setTab] = useState("overview");

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="brand-portal-panel">
      <div className="mb-5">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          <Buildings size={12} weight="fill" className="text-indigo-500" />
          <span>Chain HQ · Brand Portal</span>
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">
          Marka Genel Merkezi
        </h1>
        <p className="text-sm text-stone-500 mt-1 max-w-2xl">
          Tüm tesislerin konsolide görünümü + per-property white-label.
        </p>
      </div>

      <div className="flex gap-2 mb-5 border-b border-stone-200">
        <TabBtn active={tab === "overview"} onClick={() => setTab("overview")} testId="brand-tab-overview">
          <TrendUp size={14} className="inline mr-1.5" />
          Konsolide KPI
        </TabBtn>
        <TabBtn active={tab === "alerts"} onClick={() => setTab("alerts")} testId="brand-tab-alerts">
          <Warning size={14} className="inline mr-1.5" />
          Uyarılar
        </TabBtn>
        <TabBtn active={tab === "branding"} onClick={() => setTab("branding")} testId="brand-tab-branding">
          <Palette size={14} className="inline mr-1.5" />
          White-Label
        </TabBtn>
      </div>

      {tab === "overview" && <OverviewTab />}
      {tab === "alerts" && <AlertsTab />}
      {tab === "branding" && <BrandingTab />}
    </div>
  );
}

function TabBtn({ active, onClick, children, testId }) {
  return (
    <button
      onClick={onClick}
      data-testid={testId}
      className={`px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition ${
        active
          ? "border-indigo-500 text-indigo-600"
          : "border-transparent text-stone-500 hover:text-stone-700"
      }`}
    >
      {children}
    </button>
  );
}

function OverviewTab() {
  const [days, setDays] = useState(30);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/api/brand-portal/overview?days=${days}`);
      setData(data);
    } catch (_) { toast.error("Overview yüklenemedi"); }
    setLoading(false);
  }, [days]);

  useEffect(() => { load(); }, [load]);

  const t = data?.total || {};

  return (
    <div className="space-y-4" data-testid="overview-tab">
      {/* Window filter */}
      <div className="flex items-center gap-2">
        <select value={days} onChange={(e) => setDays(Number(e.target.value))}
          className="px-2 py-1.5 rounded border border-stone-300 text-sm">
          <option value={7}>7 gün</option>
          <option value={30}>30 gün</option>
          <option value={90}>90 gün</option>
        </select>
        <button onClick={load} className="ml-auto p-2 text-stone-500 hover:text-stone-800">
          <ArrowsClockwise size={14} className={loading ? "animate-spin" : ""} />
        </button>
      </div>

      {/* Consolidated KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2">
        <Tile label="Tesis" value={t.properties || 0} accent="indigo" />
        <Tile label="Oda" value={t.rooms || 0} />
        <Tile label="Rezervasyon" value={t.bookings || 0} />
        <Tile label="Gelir" value={`£${(t.revenue || 0).toLocaleString()}`} accent="emerald" />
        <Tile label="Doluluk" value={`${t.avg_occupancy || 0}%`} />
        <Tile label="ADR" value={`£${t.avg_adr || 0}`} />
        <Tile label="RevPAR" value={`£${t.avg_revpar || 0}`} />
        <Tile label="Ortalama ★" value={`${t.avg_rating || 0}`} accent="amber" />
      </div>

      {/* By Revenue */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="p-4 rounded-xl bg-white border border-stone-200">
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <TrendUp size={14} className="text-emerald-500" /> En Yüksek Gelir
          </h3>
          <div className="space-y-1.5">
            {(data?.by_revenue || []).slice(0, 6).map((p, i) => (
              <div key={p.property_id} className="flex items-center gap-2 text-sm" data-testid={`rank-rev-${i}`}>
                <span className="w-5 text-center text-xs font-mono text-stone-400">#{i + 1}</span>
                <span className="flex-1 truncate">{p.name}</span>
                <span className="font-bold text-emerald-700">£{p.revenue.toLocaleString()}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="p-4 rounded-xl bg-white border border-stone-200">
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <Star size={14} className="text-rose-500" /> En Düşük Puan (dikkat!)
          </h3>
          <div className="space-y-1.5">
            {(data?.lowest_rating || []).length === 0 && (
              <div className="text-xs text-stone-500">Tüm tesisler sağlıklı ✓</div>
            )}
            {(data?.lowest_rating || []).map((p) => (
              <div key={p.property_id} className="flex items-center gap-2 text-sm">
                <span className="flex-1 truncate">{p.name}</span>
                <span className="text-xs text-stone-400">({p.review_count})</span>
                <span className={`font-bold ${p.avg_rating < 4 ? "text-rose-600" : "text-stone-700"}`}>
                  ★ {p.avg_rating}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Full table */}
      <div className="p-4 rounded-xl bg-white border border-stone-200">
        <h3 className="text-sm font-semibold mb-3">Tüm Tesisler</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[10px] uppercase tracking-wider text-stone-500 border-b border-stone-200">
                <th className="text-left py-2">Tesis</th>
                <th className="text-right py-2">Oda</th>
                <th className="text-right py-2">Booking</th>
                <th className="text-right py-2">Gelir</th>
                <th className="text-right py-2">Doluluk</th>
                <th className="text-right py-2">ADR</th>
                <th className="text-right py-2">RevPAR</th>
                <th className="text-right py-2">★</th>
              </tr>
            </thead>
            <tbody>
              {(data?.properties || []).map((p) => (
                <tr key={p.property_id} className="border-b border-stone-100 hover:bg-stone-50"
                  data-testid={`prop-row-${p.property_id}`}>
                  <td className="py-2">
                    <div className="font-medium text-stone-900">{p.name}</div>
                    <div className="text-[10px] text-stone-500">{p.city}, {p.country}</div>
                  </td>
                  <td className="text-right py-2 font-mono">{p.rooms}</td>
                  <td className="text-right py-2 font-mono">{p.bookings}</td>
                  <td className="text-right py-2 font-mono font-bold text-emerald-700">£{p.revenue.toLocaleString()}</td>
                  <td className="text-right py-2 font-mono">{p.occupancy_pct}%</td>
                  <td className="text-right py-2 font-mono">£{p.adr}</td>
                  <td className="text-right py-2 font-mono">£{p.revpar}</td>
                  <td className="text-right py-2 font-mono text-amber-600">{p.avg_rating || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function AlertsTab() {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/api/brand-portal/alerts?days=7`);
      setAlerts(data.alerts || []);
    } catch (_) { toast.error("Uyarılar yüklenemedi"); }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-4" data-testid="alerts-tab">
      <div className="flex items-center justify-between">
        <div className="text-sm text-stone-600">{alerts.length} uyarı tüm tesislerde</div>
        <button onClick={load} className="p-2 text-stone-500 hover:text-stone-800">
          <ArrowsClockwise size={14} className={loading ? "animate-spin" : ""} />
        </button>
      </div>

      <div className="rounded-xl bg-white border border-stone-200 overflow-hidden">
        {alerts.length === 0 ? (
          <div className="py-10 text-center" data-testid="no-alerts">
            <CheckCircle size={32} className="text-emerald-500 mx-auto mb-2" weight="fill" />
            <div className="text-sm text-stone-600">Hiç uyarı yok · tüm tesisler sağlıklı</div>
          </div>
        ) : (
          <div className="divide-y divide-stone-100">
            {alerts.map((a, i) => (
              <div key={i} className="p-3 flex items-center gap-3 text-sm"
                data-testid={`alert-${a.type}-${i}`}>
                <div className={`w-2 h-2 rounded-full ${a.severity === "warn" ? "bg-amber-500" : "bg-sky-500"}`} />
                <div className="flex-1">
                  <div className="font-medium text-stone-900">{a.property_name}</div>
                  <div className="text-xs text-stone-500">{a.message}</div>
                </div>
                <span className={`text-[10px] px-2 py-0.5 rounded-full uppercase font-mono ${
                  a.severity === "warn" ? "bg-amber-100 text-amber-700" : "bg-sky-100 text-sky-700"
                }`}>
                  {a.type.replace(/_/g, " ")}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function BrandingTab() {
  const [propertyId, setPropertyId] = useState("");
  const [properties, setProperties] = useState([]);
  const [branding, setBranding] = useState({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    axios.get(`${API}/api/properties`).then(({ data }) => {
      const list = Array.isArray(data) ? data : (data.properties || []);
      setProperties(list);
      if (list[0]) setPropertyId(list[0].id);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!propertyId) return;
    axios.get(`${API}/api/brand-portal/branding/${propertyId}`)
      .then(({ data }) => setBranding(data))
      .catch(() => {});
  }, [propertyId]);

  const save = async () => {
    setBusy(true);
    try {
      await axios.put(`${API}/api/brand-portal/branding/${propertyId}`, {
        property_id: propertyId,
        ...branding,
      });
      toast.success("Branding kaydedildi");
    } catch (_) { toast.error("Kaydetme başarısız"); }
    setBusy(false);
  };

  const set = (k, v) => setBranding({ ...branding, [k]: v });

  return (
    <div className="space-y-4" data-testid="branding-tab">
      <div className="flex items-center gap-2">
        <label className="text-xs text-stone-500">Tesis</label>
        <select value={propertyId} onChange={(e) => setPropertyId(e.target.value)}
          className="px-3 py-2 rounded-lg border border-stone-300 text-sm bg-white"
          data-testid="branding-property-select">
          {properties.map((p) => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Form */}
        <div className="p-4 rounded-xl bg-white border border-stone-200 space-y-3">
          <Input label="Logo URL" val={branding.logo_url} onChange={(v) => set("logo_url", v)} testId="branding-logo" />
          <div className="grid grid-cols-2 gap-2">
            <Input label="Ana Renk" val={branding.primary_color} onChange={(v) => set("primary_color", v)} type="color" />
            <Input label="İkincil" val={branding.secondary_color} onChange={(v) => set("secondary_color", v)} type="color" />
          </div>
          <Input label="Özel Domain" val={branding.custom_domain} onChange={(v) => set("custom_domain", v)}
            placeholder="reservations.hotelname.com" />
          <Input label="Gönderen E-posta" val={branding.from_email} onChange={(v) => set("from_email", v)}
            placeholder="reservations@hotel.com" />
          <Input label="Booking Engine URL" val={branding.booking_engine_url} onChange={(v) => set("booking_engine_url", v)} />
          <div className="grid grid-cols-2 gap-2">
            <Input label="Instagram" val={branding.social_instagram} onChange={(v) => set("social_instagram", v)} />
            <Input label="Facebook" val={branding.social_facebook} onChange={(v) => set("social_facebook", v)} />
          </div>
          <label className="flex flex-col text-xs gap-1">
            <span className="text-stone-500">Yasal alt bilgi</span>
            <textarea value={branding.legal_footer || ""} onChange={(e) => set("legal_footer", e.target.value)}
              rows={3} className="px-3 py-2 rounded-lg border border-stone-300 text-sm" />
          </label>
          <button onClick={save} disabled={busy}
            className="w-full px-4 py-2.5 bg-indigo-600 text-white rounded-xl font-medium hover:bg-indigo-700 disabled:opacity-50"
            data-testid="branding-save">
            {busy ? "…" : "Kaydet"}
          </button>
        </div>

        {/* Preview */}
        <div className="p-4 rounded-xl bg-white border border-stone-200">
          <h3 className="text-xs uppercase tracking-wider text-stone-500 mb-3">Önizleme</h3>
          <div className="rounded-xl overflow-hidden border border-stone-200">
            <div className="p-5" style={{ background: branding.primary_color || "#0f172a" }}>
              <div className="flex items-center gap-3">
                {branding.logo_url ? (
                  <img src={branding.logo_url} alt="" className="w-10 h-10 rounded-lg object-cover bg-white" />
                ) : (
                  <div className="w-10 h-10 rounded-lg bg-white/20 text-white flex items-center justify-center font-bold">
                    {(properties.find((p) => p.id === propertyId)?.name || "H")[0]}
                  </div>
                )}
                <div className="text-white">
                  <div className="font-bold">{properties.find((p) => p.id === propertyId)?.name || "Hotel"}</div>
                  <div className="text-xs opacity-80">{branding.custom_domain || "example.com"}</div>
                </div>
              </div>
            </div>
            <div className="p-5 bg-white">
              <button className="px-4 py-2 rounded-lg text-white font-medium"
                style={{ background: branding.secondary_color || "#f59e0b" }}>
                Rezervasyon Yap
              </button>
              <p className="text-xs text-stone-500 mt-3">
                Gönderen: {branding.from_email || "reservations@example.com"}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Input({ label, val, onChange, type = "text", placeholder, testId }) {
  return (
    <label className="flex flex-col text-xs gap-1">
      <span className="text-stone-500">{label}</span>
      <input type={type} value={val || ""} onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={`px-3 py-2 rounded-lg border border-stone-300 text-sm ${type === "color" ? "h-10 p-1" : ""}`}
        data-testid={testId} />
    </label>
  );
}

function Tile({ label, value, accent }) {
  const m = {
    emerald: "text-emerald-700", amber: "text-amber-600", indigo: "text-indigo-700",
  };
  return (
    <div className="p-3 rounded-xl bg-white border border-stone-200">
      <div className="text-[10px] uppercase tracking-wider text-stone-500 mb-1">{label}</div>
      <div className={`text-lg font-bold ${accent ? m[accent] : "text-stone-900"}`}>{value}</div>
    </div>
  );
}
