import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ChartPieSlice, Bed, House, ArrowRight, CalendarBlank, MoonStars, Monitor,
  CursorClick, UsersThree, ChartLineUp, Percent, Tag, ArrowsClockwise, DownloadSimple,
} from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;
const fmt = (v) => `£${Number(v || 0).toLocaleString("en-GB", { maximumFractionDigits: 2 })}`;
const fmt0 = (v) => `£${Number(v || 0).toLocaleString("en-GB", { maximumFractionDigits: 0 })}`;

const iso = (d) => d.toISOString().slice(0, 10);
const QUICK = [
  { key: "this_month", label: "Bu ay", range: () => { const n = new Date(); return [iso(new Date(n.getFullYear(), n.getMonth(), 1)), iso(new Date(n.getFullYear(), n.getMonth() + 1, 0))]; } },
  { key: "last_30", label: "Son 30 gün", range: () => { const n = new Date(); const s = new Date(n); s.setDate(n.getDate() - 30); return [iso(s), iso(n)]; } },
  { key: "last_12m", label: "Son 12 ay", range: () => { const n = new Date(); const s = new Date(n); s.setFullYear(n.getFullYear() - 1); return [iso(s), iso(n)]; } },
  { key: "next_12m", label: "Gelecek 12 ay", range: () => { const n = new Date(); const e = new Date(n); e.setFullYear(n.getFullYear() + 1); return [iso(n), iso(e)]; } },
];

function Tile({ icon: Icon, value, label, testId, delta, invert }) {
  let deltaEl = null;
  if (delta && delta.pct !== null && delta.pct !== undefined) {
    const up = delta.pct >= 0;
    const good = invert ? !up : up;
    deltaEl = (
      <span className={`text-[10px] font-semibold ${good ? "text-emerald-600" : "text-rose-600"}`}>
        {up ? "▲" : "▼"} %{Math.abs(delta.pct)}
      </span>
    );
  }
  return (
    <div className="flex items-center gap-3 bg-white border border-stone-200 rounded-xl p-3.5" data-testid={testId}>
      <div className="h-11 w-11 rounded-lg bg-amber-100 border border-amber-200 flex items-center justify-center shrink-0">
        <Icon size={20} weight="fill" className="text-amber-700" />
      </div>
      <div className="min-w-0">
        <div className="text-lg font-bold text-stone-900 truncate flex items-center gap-2">{value} {deltaEl}</div>
        <div className="text-[11px] text-stone-500">{label}</div>
      </div>
    </div>
  );
}

function BRow({ label, value, bold, muted }) {
  return (
    <div className={`flex items-center justify-between px-4 py-2.5 border-b border-stone-100 last:border-0 ${muted ? "bg-stone-50" : ""}`}>
      <span className={`text-xs ${bold ? "font-semibold text-stone-900" : "text-stone-600"}`}>{label}</span>
      <span className={`text-xs ${bold ? "font-bold text-stone-900" : "font-medium text-stone-800"}`}>{value}</span>
    </div>
  );
}

export default function KeyFiguresPanel({ propertyId }) {
  const [[start, end], setRange] = useState(QUICK[0].range());
  const [basis, setBasis] = useState("staying");
  const [compare, setCompare] = useState("none");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/api/key-figures/${propertyId}?start=${start}&end=${end}&basis=${basis}&compare=${compare}`);
      setData(r.data);
    } catch { toast.error("Anahtar göstergeler yüklenemedi"); }
    finally { setLoading(false); }
  }, [propertyId, start, end, basis, compare]);
  useEffect(() => { load(); }, [load]);

  const t = data?.tiles;
  const b = data?.breakdown;
  const dl = data?.comparison?.deltas || {};

  return (
    <div className="space-y-5" data-testid="key-figures-panel">
      <div>
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          <ChartPieSlice size={12} weight="fill" className="text-amber-600" />
          <span>Anahtar Göstergeler</span>
        </div>
        <h2 className="text-xl font-semibold text-stone-900">Dönem özeti — tüm kritik rakamlar tek ekranda</h2>
      </div>

      <div className="flex flex-wrap items-center gap-2 bg-white border border-stone-200 rounded-xl p-3">
        <select value={basis} onChange={(e) => setBasis(e.target.value)} data-testid="kf-basis-select"
          className="text-xs border border-stone-200 rounded-lg px-2.5 py-2 bg-white font-medium">
          <option value="staying">Konaklama tarihine göre</option>
          <option value="booked">Rezervasyon tarihine göre</option>
        </select>
        <input type="date" value={start} onChange={(e) => setRange([e.target.value, end])}
          data-testid="kf-start-date"
          className="text-xs border border-stone-200 rounded-lg px-2.5 py-2 bg-white" />
        <span className="text-xs text-stone-400">—</span>
        <input type="date" value={end} onChange={(e) => setRange([start, e.target.value])}
          data-testid="kf-end-date"
          className="text-xs border border-stone-200 rounded-lg px-2.5 py-2 bg-white" />
        <select value={compare} onChange={(e) => setCompare(e.target.value)} data-testid="kf-compare-select"
          className="text-xs border border-stone-200 rounded-lg px-2.5 py-2 bg-white font-medium">
          <option value="none">Karşılaştırma yok</option>
          <option value="previous">Önceki döneme göre</option>
          <option value="last_year">Geçen yıl aynı döneme göre</option>
        </select>
        <div className="flex items-center gap-1.5 ml-auto">
          {QUICK.map((q) => (
            <button key={q.key} onClick={() => setRange(q.range())} data-testid={`kf-quick-${q.key}`}
              className="text-[11px] font-medium text-stone-600 border border-stone-200 rounded-lg px-2.5 py-1.5 bg-white hover:border-stone-400 transition-colors">
              {q.label}
            </button>
          ))}
          <button onClick={async () => {
            try {
              const r = await axios.get(`${API}/api/key-figures/${propertyId}/export?start=${start}&end=${end}&basis=${basis}`, { responseType: "blob" });
              const url = URL.createObjectURL(r.data);
              const a = document.createElement("a");
              a.href = url; a.download = `anahtar-gostergeler_${start}_${end}.csv`; a.click();
              URL.revokeObjectURL(url);
            } catch { toast.error("Dışa aktarma başarısız"); }
          }} data-testid="kf-export-csv"
            className="inline-flex items-center gap-1 text-[11px] font-medium text-stone-600 border border-stone-200 rounded-lg px-2.5 py-1.5 bg-white hover:border-stone-400 transition-colors">
            <DownloadSimple size={13} /> CSV
          </button>
          <button onClick={load} data-testid="kf-refresh"
            className="text-stone-500 hover:text-stone-800 border border-stone-200 rounded-lg p-1.5 bg-white">
            <ArrowsClockwise size={14} />
          </button>
        </div>
      </div>

      {loading ? (
        <div className="p-8 text-stone-400 text-sm" data-testid="kf-loading">Hesaplanıyor…</div>
      ) : !t ? (
        <div className="p-8 text-stone-400 text-sm">Veri yok</div>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
          <div className="xl:col-span-2 space-y-3">
            {data.comparison && (
              <p className="text-[11px] text-stone-500" data-testid="kf-compare-info">
                Karşılaştırma dönemi: <span className="font-medium text-stone-700">{data.comparison.start} — {data.comparison.end}</span> (▲▼ değişim yüzdeleri bu döneme göredir)
              </p>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Tile icon={Bed} value={`${t.nights_sold.toLocaleString()} gece`} label="Satılan" testId="kf-nights-sold" delta={dl.nights_sold} />
            <Tile icon={House} value={`%${t.avg_occupancy_pct}`} label="Ortalama doluluk" testId="kf-occupancy" delta={dl.avg_occupancy_pct} />
            <Tile icon={Bed} value={`${t.nights_unsold.toLocaleString()} gece`} label="Satılmayan" testId="kf-nights-unsold" delta={dl.nights_unsold} invert />
            <Tile icon={MoonStars} value={fmt(t.avg_price_per_night)} label="Gecelik ortalama fiyat (ADR)" testId="kf-adr" delta={dl.avg_price_per_night} />
            <Tile icon={ArrowRight} value={`${t.avg_booking_window_days} gün`} label="Ortalama rezervasyon penceresi" testId="kf-window" delta={dl.avg_booking_window_days} />
            <Tile icon={CalendarBlank} value={`${t.avg_stay_nights} gece`} label="Ortalama konaklama" testId="kf-stay" delta={dl.avg_stay_nights} />
            <Tile icon={Monitor} value={`%${t.total_online_pct}`} label="Toplam online" testId="kf-online" delta={dl.total_online_pct} />
            <Tile icon={CursorClick} value={`%${t.my_website_pct}`} label="Kendi web sitem / direkt" testId="kf-website" delta={dl.my_website_pct} />
            <Tile icon={UsersThree} value={t.guest_count.toLocaleString()} label="Misafir sayısı" testId="kf-guests" delta={dl.guest_count} />
            <Tile icon={ChartLineUp} value={fmt0(t.total_revenue)} label="Toplam gelir" testId="kf-revenue" delta={dl.total_revenue} />
            <Tile icon={Percent} value={`%${t.cancellation_pct}`} label="İptal / no-show oranı" testId="kf-cancel" delta={dl.cancellation_pct} invert />
            <Tile icon={Tag} value={fmt0(t.commission_costs)} label="Komisyon maliyeti" testId="kf-commission" delta={dl.commission_costs} invert />
            </div>
          </div>

          <div className="bg-white border border-stone-200 rounded-xl overflow-hidden h-fit" data-testid="kf-breakdown">
            <div className="px-4 py-3 border-b border-stone-100">
              <h3 className="text-sm font-semibold text-stone-900">Rezervasyon geliri dökümü</h3>
              <p className="text-[10px] text-stone-400 mt-0.5">{data.booking_count} rezervasyon · {data.days} gün · {data.rooms} oda</p>
            </div>
            <BRow label="Oda geliri" value={fmt(b.room_revenue)} />
            <BRow label="Oda dışı gelir (ekstralar)" value={fmt(b.non_room_revenue)} />
            <BRow label="Alan geliri (Spaces)" value={fmt(b.spaces_revenue)} />
            <BRow label="No-show ücretleri" value={fmt(b.no_show_fees)} />
            <BRow label="Şehir & turizm vergileri" value={fmt(b.taxes_collected)} />
            <BRow label="Toplam gelir" value={fmt(b.total_revenue)} bold />
            <div className="px-4 py-2 bg-stone-50 border-y border-stone-100">
              <span className="text-[10px] uppercase tracking-wide text-stone-400 font-medium">Bu rezervasyonların maliyeti</span>
            </div>
            <BRow label="Komisyonlar" value={fmt(b.costs.commissions)} />
            <BRow label="Tahsil edilen depozitolar" value={fmt(b.costs.advanced_deposits)} bold />
          </div>
        </div>
      )}
    </div>
  );
}
