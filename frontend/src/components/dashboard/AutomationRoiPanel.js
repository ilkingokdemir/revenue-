import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Coins, ArrowsClockwise, EnvelopeSimple, ShoppingCartSimple, Lightning, Robot, Storefront, Crosshair, ArrowRight, Wrench, TrendUp, Funnel } from "@phosphor-icons/react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

const API = process.env.REACT_APP_BACKEND_URL;
const ICONS = { rebook: EnvelopeSimple, comeback: ShoppingCartSimple, direct_conversion: Storefront, upsell: Lightning, ai_pricing: Robot };
const fmt = (v) => `£${Number(v || 0).toLocaleString("en-GB", { maximumFractionDigits: 0 })}`;

function FunnelCard({ title, stages, color, testId }) {
  const max = Math.max(...stages.map((s) => s.value), 1);
  return (
    <div className="bg-white border border-stone-200 rounded-xl p-5" data-testid={testId}>
      <div className="flex items-center gap-2 mb-4">
        <Funnel size={16} weight="fill" className="text-stone-500" />
        <h3 className="text-sm font-semibold text-stone-900">{title}</h3>
      </div>
      <div className="space-y-3">
        {stages.map((s) => (
          <div key={s.label}>
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="text-stone-500">{s.label}</span>
              <span className="font-semibold text-stone-800">
                {s.value}{s.rate !== undefined && <span className="text-stone-400 font-normal ml-1.5">%{s.rate}</span>}
              </span>
            </div>
            <div className="h-2 bg-stone-100 rounded-full overflow-hidden">
              <div className={`h-full rounded-full ${color}`} style={{ width: `${Math.round((s.value / max) * 100)}%` }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function AutomationRoiPanel({ propertyId, onNavigate }) {
  const [data, setData] = useState(null);
  const [opps, setOpps] = useState(null);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [fixing, setFixing] = useState(false);
  const [trend, setTrend] = useState(null);
  const [funnel, setFunnel] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [r, o, t, f] = await Promise.all([
        axios.get(`${API}/api/automation/roi/${propertyId}?days=${days}`),
        axios.get(`${API}/api/automation/opportunities/${propertyId}`),
        axios.get(`${API}/api/automation/roi/${propertyId}/trend?weeks=8`),
        axios.get(`${API}/api/automation/funnel/${propertyId}?days=30`),
      ]);
      setData(r.data);
      setOpps(o.data);
      setTrend(t.data);
      setFunnel(f.data);
    } catch { toast.error("ROI verisi yüklenemedi"); }
    finally { setLoading(false); }
  }, [propertyId, days]);
  useEffect(() => { load(); }, [load]);

  const autoFix = async () => {
    setFixing(true);
    try {
      const r = await axios.post(`${API}/api/automation/opportunities/${propertyId}/auto-fix`, {});
      const res = r.data.results || {};
      const rb = res.rebook || {};
      const cb = res.comeback || {};
      const up = res.upsell || {};
      toast.success(`Otomatik düzeltme tamam: ${rb.queued ?? 0} rebook kuponu, ${cb.emails_sent ?? 0} sepet kurtarma, ${up.offers_sent ?? 0} upsell teklifi gönderildi`);
      load();
    } catch { toast.error("Otomatik düzeltme başarısız"); }
    finally { setFixing(false); }
  };

  if (loading) return <div className="p-8 text-stone-400 text-sm" data-testid="automation-roi-loading">Hesaplanıyor…</div>;
  if (!data) return <div className="p-8 text-stone-400 text-sm">Veri yok</div>;

  const maxRev = Math.max(...data.rows.map((r) => r.revenue), 1);

  return (
    <div className="space-y-6" data-testid="automation-roi-panel">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
            <Coins size={12} weight="fill" className="text-amber-500" />
            <span>Otomasyon ROI</span>
          </div>
          <h2 className="text-xl font-semibold text-stone-900">Otomasyonlar ne kazandırdı?</h2>
        </div>
        <div className="flex items-center gap-2">
          {[30, 90, 365].map((d) => (
            <button key={d} onClick={() => setDays(d)} data-testid={`roi-days-${d}`}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${days === d ? "bg-stone-900 text-white border-stone-900" : "bg-white text-stone-600 border-stone-200 hover:border-stone-300"}`}>
              {d === 365 ? "1 yıl" : `${d} gün`}
            </button>
          ))}
          <button onClick={load} data-testid="roi-refresh-btn"
            className="inline-flex items-center gap-1.5 text-xs text-stone-500 hover:text-stone-800 border border-stone-200 rounded-lg px-3 py-1.5 bg-white transition-colors">
            <ArrowsClockwise size={14} /> Yenile
          </button>
        </div>
      </div>

      <div className="bg-stone-900 text-white rounded-2xl p-6 flex flex-wrap items-center gap-8">
        <div>
          <div className="text-3xl font-semibold" data-testid="roi-total">{fmt(data.total_attributed)}</div>
          <div className="text-xs text-stone-400 mt-1">Doğrulanmış atfedilen gelir (son {data.days} gün)</div>
        </div>
        <div>
          <div className="text-xl font-semibold text-amber-400">+{fmt(data.total_estimated)}</div>
          <div className="text-xs text-stone-400 mt-1">AI fiyatlama tahmini katkı</div>
        </div>
        {data.commission_saved > 0 && (
          <div>
            <div className="text-xl font-semibold text-emerald-400">{fmt(data.commission_saved)}</div>
            <div className="text-xs text-stone-400 mt-1">OTA komisyon tasarrufu</div>
          </div>
        )}
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        {data.rows.map((r) => {
          const Icon = ICONS[r.key] || Lightning;
          return (
            <div key={r.key} className="bg-white border border-stone-200 rounded-xl p-5" data-testid={`roi-row-${r.key}`}>
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-stone-100 flex items-center justify-center">
                    <Icon size={20} className="text-stone-700" />
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-stone-900">
                      {r.name}
                      {r.estimated && <span className="ml-2 text-[10px] uppercase text-amber-600 font-medium">tahmini</span>}
                    </div>
                    <div className="text-xs text-stone-500 mt-0.5">{r.desc}</div>
                  </div>
                </div>
                <div className="text-right shrink-0">
                  <div className={`text-lg font-semibold ${r.estimated ? "text-amber-600" : "text-emerald-700"}`}>{fmt(r.revenue)}</div>
                  <div className="text-[11px] text-stone-400">{r.count} işlem{r.extra ? ` · ${fmt(r.extra)} komisyon` : ""}</div>
                </div>
              </div>
              <div className="h-1.5 bg-stone-100 rounded-full mt-4 overflow-hidden">
                <div className={`h-full rounded-full ${r.estimated ? "bg-amber-400" : "bg-emerald-500"}`}
                  style={{ width: `${Math.round((r.revenue / maxRev) * 100)}%` }} />
              </div>
            </div>
          );
        })}
      </div>

      {trend?.buckets?.length > 0 && (
        <div className="bg-white border border-stone-200 rounded-xl p-5" data-testid="roi-trend-chart">
          <div className="flex items-center gap-2 mb-4">
            <TrendUp size={16} weight="fill" className="text-emerald-600" />
            <h3 className="text-sm font-semibold text-stone-900">Haftalık trend — atfedilen gelir (8 hafta)</h3>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={trend.buckets} barCategoryGap="25%">
              <XAxis dataKey="week" tick={{ fontSize: 11, fill: "#78716c" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "#78716c" }} axisLine={false} tickLine={false} tickFormatter={(v) => `£${v}`} width={50} />
              <Tooltip formatter={(v, n) => [fmt(v), n === "coupon" ? "Kupon geliri" : "Upsell geliri"]}
                contentStyle={{ borderRadius: 12, border: "1px solid #e7e5e4", fontSize: 12 }} />
              <Bar dataKey="coupon" stackId="a" fill="#10b981" radius={[0, 0, 0, 0]} />
              <Bar dataKey="upsell" stackId="a" fill="#f59e0b" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
          <div className="flex items-center gap-4 mt-2 text-[11px] text-stone-500">
            <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-emerald-500 inline-block" /> Kupon (rebook · sepet · OTA→direkt)</span>
            <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-amber-500 inline-block" /> Upsell</span>
          </div>
        </div>
      )}

      {funnel && (
        <div className="grid md:grid-cols-2 gap-4" data-testid="roi-funnel">
          <FunnelCard title="Kupon hunisi (30 gün)" testId="funnel-coupon"
            stages={[
              { label: "Gönderilen", value: funnel.coupon.sent },
              { label: "Tıklanan", value: funnel.coupon.clicked, rate: funnel.coupon.click_rate },
              { label: "Kullanılan", value: funnel.coupon.redeemed, rate: funnel.coupon.redeem_rate },
            ]} color="bg-emerald-500" />
          <FunnelCard title="Upsell hunisi (30 gün)" testId="funnel-upsell"
            stages={[
              { label: "Gönderilen", value: funnel.upsell.sent },
              { label: "Görüntülenen", value: funnel.upsell.viewed, rate: funnel.upsell.view_rate },
              { label: "Kabul edilen", value: funnel.upsell.accepted, rate: funnel.upsell.accept_rate },
            ]} color="bg-amber-500" />
        </div>
      )}

      {opps && (
        <div className="space-y-3" data-testid="opportunity-radar">
          <div className="flex items-center justify-between pt-2">
            <div className="flex items-center gap-2">
              <Crosshair size={16} weight="fill" className="text-rose-500" />
              <h3 className="text-sm font-semibold text-stone-900">Fırsat Radarı — masada kalan para</h3>
            </div>
            <div className="flex items-center gap-3">
              <div className="text-sm font-semibold text-rose-600" data-testid="opportunity-total">
                ~{fmt(opps.total_potential)} potansiyel
              </div>
              <button onClick={autoFix} disabled={fixing} data-testid="auto-fix-btn"
                className="inline-flex items-center gap-1.5 text-xs font-semibold text-white bg-rose-600 hover:bg-rose-700 disabled:opacity-60 rounded-lg px-3 py-1.5 transition-colors">
                <Wrench size={14} weight="fill" />
                {fixing ? "Çalışıyor…" : "Hepsini Düzelt"}
              </button>
            </div>
          </div>
          <div className="grid md:grid-cols-2 gap-3">
            {opps.rows.map((r) => {
              const Icon = ICONS[r.key] || Lightning;
              return (
                <div key={r.key} className="bg-rose-50/50 border border-rose-100 rounded-xl p-4 flex items-start justify-between gap-3"
                  data-testid={`opportunity-${r.key}`}>
                  <div className="flex items-start gap-3 min-w-0">
                    <div className="w-9 h-9 rounded-lg bg-white border border-rose-100 flex items-center justify-center shrink-0">
                      <Icon size={18} className="text-rose-500" />
                    </div>
                    <div className="min-w-0">
                      <div className="text-sm font-semibold text-stone-900">{r.name}</div>
                      <div className="text-xs text-stone-500 mt-0.5">{r.desc}</div>
                      {onNavigate && r.count > 0 && (
                        <button onClick={() => onNavigate(r.view)} data-testid={`opportunity-action-${r.key}`}
                          className="inline-flex items-center gap-1 mt-2 text-xs font-medium text-rose-700 hover:text-rose-900 transition-colors">
                          {r.action} <ArrowRight size={12} />
                        </button>
                      )}
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <div className="text-base font-semibold text-rose-600">~{fmt(r.potential)}</div>
                    <div className="text-[11px] text-stone-400">{r.count} fırsat{r.extra ? ` · ${fmt(r.extra)} komisyon riski` : ""}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
