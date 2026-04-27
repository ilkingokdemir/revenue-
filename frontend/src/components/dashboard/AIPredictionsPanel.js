import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Warning,
  TrendUp,
  Sparkle,
  ArrowsClockwise,
  PaperPlaneTilt,
  Lightning,
  Bed,
  Clock,
  Coffee,
  Heart,
  Car,
} from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

const UPSELL_CATS = [
  { id: "room_upgrade", label: "Oda Upgrade", icon: Bed, color: "violet" },
  { id: "late_checkout", label: "Geç Çıkış", icon: Clock, color: "amber" },
  { id: "breakfast", label: "Kahvaltı", icon: Coffee, color: "emerald" },
  { id: "spa", label: "SPA", icon: Heart, color: "rose" },
  { id: "transport", label: "Transfer", icon: Car, color: "sky" },
];

export default function AIPredictionsPanel({ propertyId, hotelName }) {
  const [tab, setTab] = useState("cancel");

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="ai-predictions-panel">
      <div className="mb-5">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          <Sparkle size={12} weight="fill" className="text-violet-500" />
          <span>AI Tahminler</span>
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">
          Öngörü Motoru · {hotelName || "Property"}
        </h1>
        <p className="text-sm text-stone-500 mt-1 max-w-2xl">
          Riskli rezervasyonları ve upsell fırsatlarını gelmeden önce görün. Save-offer ve upsell kampanyaları tek tıkla tetiklenir.
        </p>
      </div>

      <div className="flex gap-2 mb-5 border-b border-stone-200">
        <TabBtn active={tab === "cancel"} onClick={() => setTab("cancel")} testId="ai-tab-cancel">
          <Warning size={14} className="inline mr-1.5" />
          İptal Riski
        </TabBtn>
        <TabBtn active={tab === "upsell"} onClick={() => setTab("upsell")} testId="ai-tab-upsell">
          <TrendUp size={14} className="inline mr-1.5" />
          Upsell Fırsatı
        </TabBtn>
      </div>

      {tab === "cancel" && <CancelRiskTab propertyId={propertyId} />}
      {tab === "upsell" && <UpsellTab propertyId={propertyId} />}
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
          ? "border-violet-500 text-violet-600"
          : "border-transparent text-stone-500 hover:text-stone-700"
      }`}
    >
      {children}
    </button>
  );
}

function CancelRiskTab({ propertyId }) {
  const [days, setDays] = useState(60);
  const [minScore, setMinScore] = useState(40);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(
        `${API}/api/ai-predictions/cancel-risk/${propertyId}?days_ahead=${days}&min_score=${minScore}`
      );
      setData(data);
    } catch (e) {
      toast.error("Risk skorları yüklenemedi");
    }
    setLoading(false);
  }, [propertyId, days, minScore]);

  useEffect(() => { load(); }, [load]);

  const sendSave = async (bookingId) => {
    try {
      const { data: r } = await axios.post(
        `${API}/api/ai-predictions/cancel-risk/${bookingId}/save-offer`
      );
      toast.success(`Save-offer sıraya alındı: ${r.voucher_code} (%${r.discount_pct})`);
      load();
    } catch (_) {
      toast.error("Save-offer gönderilemedi");
    }
  };

  const rows = data?.rows || [];

  return (
    <div className="space-y-5" data-testid="cancel-risk-tab">
      {/* KPI */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Stat label="Yüksek risk" value={data?.by_band?.high || 0} accent="rose" />
        <Stat label="Orta risk" value={data?.by_band?.medium || 0} accent="amber" />
        <Stat label="Düşük risk" value={data?.by_band?.low || 0} accent="emerald" />
        <Stat
          label="Risk altındaki gelir"
          value={`£${(data?.at_risk_revenue || 0).toLocaleString("en-GB")}`}
          accent="rose"
        />
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3 p-3 rounded-xl bg-white border border-stone-200">
        <div className="flex items-center gap-2 text-xs">
          <span className="text-stone-500">Sonraki</span>
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="px-2 py-1 rounded border border-stone-300 text-xs"
            data-testid="cancel-risk-days"
          >
            <option value={14}>14 gün</option>
            <option value={30}>30 gün</option>
            <option value={60}>60 gün</option>
            <option value={90}>90 gün</option>
          </select>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="text-stone-500">Min skor</span>
          <select
            value={minScore}
            onChange={(e) => setMinScore(Number(e.target.value))}
            className="px-2 py-1 rounded border border-stone-300 text-xs"
          >
            <option value={30}>30</option>
            <option value={40}>40</option>
            <option value={55}>55</option>
            <option value={70}>70</option>
          </select>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="ml-auto px-3 py-1.5 text-xs bg-violet-600 text-white rounded-lg hover:bg-violet-700 flex items-center gap-1.5"
          data-testid="cancel-risk-reload"
        >
          <ArrowsClockwise size={12} />
          Yenile
        </button>
      </div>

      {/* Rows */}
      <div className="rounded-xl bg-white border border-stone-200 overflow-hidden">
        {rows.length === 0 && (
          <div className="text-xs text-stone-500 py-8 text-center">
            {loading ? "Yükleniyor…" : "Eşiğin üzerinde risk yok — tüm rezervasyonlar güvenli."}
          </div>
        )}
        <div className="divide-y divide-stone-100">
          {rows.map((r) => (
            <div
              key={r.booking_id}
              className="p-3 hover:bg-stone-50 cursor-pointer"
              onClick={() => setSelected(r)}
              data-testid={`cancel-risk-row-${r.booking_id}`}
            >
              <div className="flex items-center gap-3 text-sm">
                <div
                  className={`w-1 h-12 rounded-full ${
                    r.band === "high"
                      ? "bg-rose-500"
                      : r.band === "medium"
                      ? "bg-amber-500"
                      : "bg-emerald-500"
                  }`}
                />
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-stone-900 truncate">
                    {r.guest_name || "—"}
                  </div>
                  <div className="text-xs text-stone-500 mt-0.5">
                    {r.check_in} → {r.check_out} · {r.channel || "—"} · £{r.total_price}
                  </div>
                </div>
                <div className="flex flex-col items-end">
                  <div
                    className={`text-lg font-bold ${
                      r.band === "high"
                        ? "text-rose-600"
                        : r.band === "medium"
                        ? "text-amber-600"
                        : "text-emerald-600"
                    }`}
                  >
                    {r.score}
                  </div>
                  <div className="text-[10px] uppercase tracking-wider text-stone-500">
                    {r.band === "high" ? "Yüksek" : r.band === "medium" ? "Orta" : "Düşük"} risk
                  </div>
                </div>
                {r.band === "high" && !r.save_offer_sent_at && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      sendSave(r.booking_id);
                    }}
                    className="ml-3 px-2.5 py-1.5 text-xs bg-violet-600 text-white rounded-md hover:bg-violet-700 flex items-center gap-1.5"
                    data-testid={`cancel-risk-save-${r.booking_id}`}
                  >
                    <Lightning size={12} /> Save-Offer
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Detail drawer */}
      {selected && (
        <div
          className="fixed inset-0 bg-black/30 z-40 flex items-end sm:items-center justify-center p-4"
          onClick={() => setSelected(null)}
          data-testid="cancel-risk-detail"
        >
          <div
            className="bg-white rounded-2xl max-w-md w-full p-5"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between mb-3">
              <div>
                <div className="text-xs text-stone-500">İptal riski</div>
                <h3 className="text-xl font-bold text-stone-900">{selected.guest_name}</h3>
                <div className="text-xs text-stone-500 mt-0.5">
                  {selected.check_in} → {selected.check_out}
                </div>
              </div>
              <div
                className={`px-3 py-2 rounded-xl text-center ${
                  selected.band === "high"
                    ? "bg-rose-100 text-rose-700"
                    : selected.band === "medium"
                    ? "bg-amber-100 text-amber-700"
                    : "bg-emerald-100 text-emerald-700"
                }`}
              >
                <div className="text-2xl font-bold">{selected.score}</div>
                <div className="text-[9px] uppercase">risk</div>
              </div>
            </div>
            <div className="text-xs text-stone-500 font-medium mb-2">Sinyaller</div>
            <div className="space-y-1">
              {selected.signals?.map((s, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between text-xs p-2 rounded-lg bg-stone-50"
                >
                  <span className="text-stone-700">{s.name}</span>
                  <span
                    className={`font-mono font-bold ${
                      s.impact > 0 ? "text-rose-600" : "text-emerald-600"
                    }`}
                  >
                    {s.impact > 0 ? "+" : ""}
                    {s.impact}
                  </span>
                </div>
              ))}
            </div>
            <div className="mt-4 flex gap-2">
              {selected.band === "high" && (
                <button
                  onClick={() => {
                    sendSave(selected.booking_id);
                    setSelected(null);
                  }}
                  className="flex-1 px-3 py-2 text-sm bg-violet-600 text-white rounded-lg hover:bg-violet-700"
                >
                  Save-Offer Gönder
                </button>
              )}
              <button
                onClick={() => setSelected(null)}
                className="px-3 py-2 text-sm bg-stone-100 text-stone-700 rounded-lg hover:bg-stone-200"
              >
                Kapat
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function UpsellTab({ propertyId }) {
  const [days, setDays] = useState(14);
  const [category, setCategory] = useState("");
  const [minScore, setMinScore] = useState(50);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        days_ahead: String(days),
        min_score: String(minScore),
      });
      if (category) params.set("category", category);
      const { data } = await axios.get(
        `${API}/api/ai-predictions/upsell/${propertyId}?${params}`
      );
      setData(data);
    } catch (e) {
      toast.error("Upsell skorları yüklenemedi");
    }
    setLoading(false);
  }, [propertyId, days, category, minScore]);

  useEffect(() => { load(); }, [load]);

  const send = async (bookingId, cat) => {
    try {
      const { data: r } = await axios.post(
        `${API}/api/ai-predictions/upsell/${bookingId}/send-offer?category=${cat}`
      );
      toast.success(`Upsell teklifi kuyruğa: ${r.offer_id}`);
    } catch (_) {
      toast.error("Teklif gönderilemedi");
    }
  };

  const rows = data?.rows || [];

  return (
    <div className="space-y-5" data-testid="upsell-tab">
      {/* Top rec KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        {UPSELL_CATS.map((c) => (
          <Stat
            key={c.id}
            label={c.label}
            value={data?.by_top_recommendation?.[c.id] || 0}
            subtitle="ana öneri"
            accent={c.color}
            icon={c.icon}
          />
        ))}
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3 p-3 rounded-xl bg-white border border-stone-200">
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="px-2 py-1 rounded border border-stone-300 text-xs"
        >
          <option value={7}>7 gün</option>
          <option value={14}>14 gün</option>
          <option value={30}>30 gün</option>
        </select>
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="px-2 py-1 rounded border border-stone-300 text-xs"
          data-testid="upsell-category-filter"
        >
          <option value="">Tüm kategoriler</option>
          {UPSELL_CATS.map((c) => (
            <option key={c.id} value={c.id}>
              {c.label}
            </option>
          ))}
        </select>
        <select
          value={minScore}
          onChange={(e) => setMinScore(Number(e.target.value))}
          className="px-2 py-1 rounded border border-stone-300 text-xs"
        >
          <option value={40}>Min 40</option>
          <option value={50}>Min 50</option>
          <option value={65}>Min 65</option>
          <option value={80}>Min 80</option>
        </select>
        <button
          onClick={load}
          disabled={loading}
          className="ml-auto px-3 py-1.5 text-xs bg-violet-600 text-white rounded-lg hover:bg-violet-700"
          data-testid="upsell-reload"
        >
          Yenile
        </button>
      </div>

      {/* Rows */}
      <div className="rounded-xl bg-white border border-stone-200 overflow-hidden">
        {rows.length === 0 && (
          <div className="text-xs text-stone-500 py-8 text-center">
            {loading ? "Yükleniyor…" : "Eşiğin üzerinde upsell fırsatı yok."}
          </div>
        )}
        <div className="divide-y divide-stone-100">
          {rows.map((r) => {
            const topCat = UPSELL_CATS.find((c) => c.id === r.top_recommendation) || UPSELL_CATS[0];
            const Icon = topCat.icon;
            return (
              <div
                key={r.booking_id}
                className="p-3 hover:bg-stone-50"
                data-testid={`upsell-row-${r.booking_id}`}
              >
                <div className="flex items-center gap-3 text-sm">
                  <div
                    className={`w-10 h-10 rounded-xl flex items-center justify-center bg-${topCat.color}-100 text-${topCat.color}-700`}
                  >
                    <Icon size={18} weight="bold" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-stone-900 truncate">
                      {r.guest_name || "—"}
                    </div>
                    <div className="text-xs text-stone-500 mt-0.5">
                      {r.check_in} → {r.check_out} · {r.room_type || "—"} ·{" "}
                      <span className="capitalize">{r.loyalty_tier}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {UPSELL_CATS.map((c) => (
                      <div
                        key={c.id}
                        className={`w-10 text-center text-[11px] font-mono ${
                          r.scores?.[c.id] >= 70
                            ? "text-emerald-600 font-bold"
                            : r.scores?.[c.id] >= 50
                            ? "text-stone-700"
                            : "text-stone-400"
                        }`}
                        title={c.label}
                      >
                        {r.scores?.[c.id] ?? "—"}
                      </div>
                    ))}
                  </div>
                  <button
                    onClick={() => send(r.booking_id, r.top_recommendation)}
                    className="ml-3 px-2.5 py-1.5 text-xs bg-violet-600 text-white rounded-md hover:bg-violet-700 flex items-center gap-1.5"
                    data-testid={`upsell-send-${r.booking_id}`}
                  >
                    <PaperPlaneTilt size={12} />
                    Gönder
                  </button>
                </div>
              </div>
            );
          })}
        </div>
        {rows.length > 0 && (
          <div className="px-3 py-2 bg-stone-50 border-t border-stone-200 flex gap-2 text-[10px] text-stone-500 justify-end">
            {UPSELL_CATS.map((c) => (
              <div key={c.id} className="w-10 text-center truncate" title={c.label}>
                {c.label.slice(0, 6)}
              </div>
            ))}
            <div className="w-20" />
          </div>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value, subtitle, icon: Icon, accent }) {
  const map = {
    emerald: "text-emerald-700",
    rose: "text-rose-600",
    sky: "text-sky-700",
    amber: "text-amber-600",
    violet: "text-violet-700",
  };
  return (
    <div className="p-3 rounded-xl bg-white border border-stone-200">
      <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-stone-500 mb-1">
        {Icon && <Icon size={11} />}
        <span className="truncate">{label}</span>
      </div>
      <div className={`text-xl font-bold ${accent ? map[accent] : "text-stone-900"}`}>
        {value}
      </div>
      {subtitle && <div className="text-[10px] text-stone-500 mt-0.5">{subtitle}</div>}
    </div>
  );
}
