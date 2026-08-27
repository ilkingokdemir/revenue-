import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Lightning, TrendUp } from "@phosphor-icons/react";

const B = process.env.REACT_APP_BACKEND_URL;
const TIER_TR = { floor: "Taban (son dakika)", mid: "Orta", high: "Yüksek (uzak tarih)" };
const TIER_BG = { floor: "#e5484d", mid: "#c9a56a", high: "#2dd4bf" };

function Bar({ tiers }) {
  return (
    <div className="flex h-10 rounded-lg overflow-hidden" data-testid="rate-mix-bar">
      {tiers.map((t) => t.share_pct > 0 && (
        <div key={t.tier} title={`${TIER_TR[t.tier]} — %${t.share_pct} @ £${t.avg_rate}`}
          style={{ width: `${t.share_pct}%`, background: TIER_BG[t.tier] }}
          className="flex flex-col items-center justify-center text-[11px] font-bold text-stone-950 min-w-[46px]">
          <span>{t.share_pct}%</span>
          <span className="font-normal">£{t.avg_rate}</span>
        </div>
      ))}
    </div>
  );
}

function PropertyRow({ p, onApply, busy }) {
  const rec = p.recommendation;
  return (
    <div className="bg-stone-900 border border-stone-800 rounded-2xl p-4" data-testid={`rate-mix-row-${p.property_id}`}>
      <div className="flex items-baseline justify-between mb-2 flex-wrap gap-1">
        <div className="flex items-baseline gap-3">
          <h3 className="text-white font-bold">{p.name}</h3>
          <span className="text-xs text-stone-400 font-mono">
            {p.rooms || "?"} oda{p.occ_pct != null ? ` · %${p.occ_pct} doluluk` : ""} · LMF £{p.lmf}{p.lmf_lead != null ? ` / ${p.lmf_lead}g` : ""}
          </span>
        </div>
        <span className="text-sm text-stone-300 font-mono">ADR <b className="text-white">£{p.adr}</b></span>
      </div>
      <Bar tiers={p.tiers} />
      {rec && (
        <div className="mt-3 flex items-start justify-between gap-3 bg-stone-950 border border-amber-900/40 rounded-xl p-3" data-testid={`rate-mix-rec-${p.property_id}`}>
          <p className="text-xs text-amber-200/90 leading-relaxed">
            <TrendUp size={13} className="inline mr-1 text-amber-400" />{rec.message}
          </p>
          <button onClick={() => onApply(p.property_id, rec.sweet_spot)} disabled={busy === p.property_id}
            data-testid={`rate-mix-apply-${p.property_id}`}
            className="shrink-0 px-3 py-1.5 rounded-full bg-amber-500 text-stone-950 text-xs font-bold disabled:opacity-50">
            {busy === p.property_id ? "Uygulanıyor…" : `£${rec.sweet_spot} Uygula`}
          </button>
        </div>
      )}
      <p className="mt-2 text-[10px] text-stone-500">{p.sample.bookings} rezervasyon · {p.sample.room_nights} oda-gece · son {p.sample.days} gün (iptaller hariç)</p>
    </div>
  );
}

export default function RateMixPanel({ propertyId = "all" }) {
  const [data, setData] = useState(null);
  const [days, setDays] = useState(365);
  const [busy, setBusy] = useState("");
  const pid = propertyId === "default" ? "all" : propertyId;

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${B}/api/rate-mix/${pid}?days=${days}`);
      setData(r.data);
    } catch { toast.error("Rate mix verisi yüklenemedi"); }
  }, [pid, days]);
  useEffect(() => { load(); }, [load]);

  async function apply(propId, rate) {
    if (!window.confirm(`£${rate} fiyatı 14-90 gün sonrası tarihlere (mevcut override'lar korunarak) yazılacak. Onaylıyor musunuz?`)) return;
    setBusy(propId);
    try {
      const r = await axios.post(`${B}/api/rate-mix/${propId}/apply`, { rate, start_offset: 14, end_offset: 90 });
      toast.success(`£${rate} uygulandı — ${r.data.written} gün yazıldı, ${r.data.skipped} gün atlandı (mevcut override/kilit)`);
    } catch (err) { toast.error(err.response?.data?.detail || "Uygulanamadı"); }
    setBusy("");
  }

  return (
    <div className="p-5 max-w-[1200px] mx-auto space-y-4" data-testid="rate-mix-panel">
      <div className="bg-stone-950 rounded-2xl p-6 border border-stone-800">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2">
              <Lightning size={22} className="text-amber-400" /> Fiyat Karışımı Analizi (Rate Mix)
            </h1>
            <p className="text-sm text-stone-400 mt-1">
              Tüm rezervasyonlar (iptaller hariç) fiyat katmanlarına ayrıldı. <span className="text-red-400 font-semibold">Kırmızı</span> = son-dakika taban satışları, <span className="text-amber-300 font-semibold">bej</span> = orta bant, <span className="text-teal-300 font-semibold">yeşil</span> = indirilmesi gereken uzak tarih fiyatları.
            </p>
          </div>
          <select value={days} onChange={(e) => setDays(+e.target.value)} data-testid="rate-mix-days-select"
            className="bg-stone-900 border border-stone-700 text-stone-200 text-sm rounded-lg px-3 py-2">
            <option value={90}>Son 90 gün</option>
            <option value={180}>Son 180 gün</option>
            <option value={365}>Son 365 gün</option>
            <option value={730}>Son 730 gün</option>
          </select>
        </div>
        <div className="flex gap-4 mt-3 text-[11px] text-stone-500">
          {Object.entries(TIER_TR).map(([k, v]) => (
            <span key={k} className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-sm inline-block" style={{ background: TIER_BG[k] }} /> {v}
            </span>
          ))}
          <span className="ml-auto">LMF = son-dakika taban fiyatı / taban satışların medyan lead-time'ı</span>
        </div>
      </div>

      {!data ? <p className="text-sm text-stone-400 p-4" data-testid="rate-mix-loading">Analiz hesaplanıyor…</p> : (
        data.properties.length === 0
          ? <p className="text-sm text-stone-400 p-4" data-testid="rate-mix-empty">Yeterli rezervasyon verisi yok.</p>
          : <div className="space-y-3">{data.properties.map((p) => (
              <PropertyRow key={p.property_id} p={p} onApply={apply} busy={busy} />))}</div>
      )}
    </div>
  );
}
