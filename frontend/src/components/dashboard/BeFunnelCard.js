import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function BeFunnelCard({ propertyId }) {
  const [days, setDays] = useState(30);
  const [d, setD] = useState(null);
  const load = useCallback(async () => {
    if (!propertyId || propertyId === "all") return;
    try { const r = await axios.get(`${API}/booking/funnel/${propertyId}?days=${days}`, { withCredentials: true }); setD(r.data); } catch { toast.error("Huni verisi yüklenemedi"); }
  }, [propertyId, days]);
  useEffect(() => { load(); }, [load]);

  if (!propertyId || propertyId === "all") return <div className="text-sm text-stone-500 py-8 text-center" data-testid="funnel-select-property">Huni için üstten bir tesis seçin.</div>;
  if (!d) return <div className="text-sm text-stone-400 py-8 text-center">Yükleniyor…</div>;
  const max = Math.max(1, d.steps[0]?.sessions || 0);
  return (
    <div className="space-y-4" data-testid="be-funnel-card">
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="font-semibold text-stone-900">Rezervasyon Hunisi</h3>
        <select value={days} onChange={(e) => setDays(Number(e.target.value))} className="border border-stone-300 rounded-lg px-2 py-1 text-xs" data-testid="funnel-days">{[7, 14, 30, 90].map((n) => <option key={n} value={n}>{n} gün</option>)}</select>
        <div className="ml-auto flex gap-4 text-xs">
          <span data-testid="funnel-sessions"><b className="text-lg text-stone-900">{d.sessions}</b> oturum</span>
          <span data-testid="funnel-conversions"><b className="text-lg text-stone-900">{d.conversions}</b> rezervasyon</span>
          <span data-testid="funnel-cr"><b className={`text-lg ${d.conversion_rate >= 3 ? "text-emerald-600" : "text-amber-600"}`}>{d.conversion_rate}%</b> dönüşüm</span>
        </div>
      </div>
      {!d.sessions && <div className="text-sm text-stone-400 bg-stone-50 rounded-xl p-4" data-testid="funnel-empty">Henüz huni verisi yok — booking engine'de bir arama yapıldığında oturumlar burada görünür.</div>}
      <div className="space-y-1.5">
        {d.steps.map((s, i) => (
          <div key={s.step} className="flex items-center gap-3 text-xs" data-testid={`funnel-step-${s.step}`}>
            <span className="w-40 text-stone-600">{i + 1}. {s.label}</span>
            <div className="flex-1 h-6 bg-stone-100 rounded-md overflow-hidden relative">
              <div className="h-full rounded-md" style={{ width: `${(s.sessions / max) * 100}%`, background: s.step === "confirm" ? "#059669" : "#0f766e", opacity: 0.35 + 0.65 * (s.sessions / max) }} />
              <span className="absolute inset-y-0 left-2 flex items-center font-bold text-stone-800">{s.sessions} <span className="font-normal text-stone-500 ml-1">({s.pct_of_start}%)</span></span>
            </div>
            <span className={`w-24 text-right font-semibold ${s.drop_pct >= 50 ? "text-rose-600" : s.drop_pct >= 25 ? "text-amber-600" : "text-stone-400"}`} data-testid={`funnel-drop-${s.step}`}>{i ? `−${s.drop_pct}%` : ""}</span>
          </div>
        ))}
      </div>
      {d.biggest_drop && d.sessions > 0 && (
        <div className="text-xs bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 text-amber-900" data-testid="funnel-biggest-drop">
          En büyük kayıp: <b>{d.biggest_drop.label}</b> adımında −{d.biggest_drop.drop_pct}%. {d.biggest_drop.step === "details" ? "Form alanlarını azaltın, misafir hesabı / otomatik doldurma açın." : d.biggest_drop.step === "payment" ? "Ödeme yöntemlerini (Apple/Google Pay, otelde öde) ve depozito seçeneğini kontrol edin." : d.biggest_drop.step === "rate_select" ? "Fiyat planı farklarını ve kıtlık etiketlerini netleştirin." : "Fiyat takvimi ve esnek tarih önerilerini öne çıkarın."}
        </div>
      )}
      <div className="grid md:grid-cols-2 gap-3">
        <Breakdown title="Cihaz" rows={d.by_device} keyName="device" testid="funnel-device" />
        <Breakdown title="Kaynak" rows={d.by_source} keyName="source" testid="funnel-source" />
      </div>
    </div>
  );
}

function Breakdown({ title, rows, keyName, testid }) {
  return (
    <div className="border border-stone-100 rounded-xl p-3" data-testid={testid}>
      <div className="text-xs font-bold text-stone-700 mb-2">{title}</div>
      {!rows.length && <div className="text-[11px] text-stone-400">Veri yok</div>}
      {rows.slice(0, 6).map((r) => (
        <div key={r[keyName]} className="flex items-center justify-between text-[11px] py-1 border-t border-stone-50">
          <span className="text-stone-700 capitalize">{r[keyName]}</span>
          <span className="text-stone-500">{r.sessions} oturum · {r.confirm} rez. · <b className="text-stone-800">{r.cr}%</b></span>
        </div>
      ))}
    </div>
  );
}
