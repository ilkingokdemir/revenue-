/** Owner Reports Hub — kategorili rapor kataloğu + dinamik tablo görüntüleyici */
import { useState } from "react";
import { ChartBar, CalendarBlank, Receipt, Broadcast, ArrowLeft, DownloadSimple } from "@phosphor-icons/react";
import { toast } from "sonner";

const CATALOG = [
  { cat: "TEMEL ANALİTİK", items: [
    { key: "performance", title: "Performans Metrikleri", desc: "Doluluk, ADR, RevPAR ve gelir — son 30 gün", Icon: ChartBar },
    { key: "yoy", title: "Yıllık Karşılaştırma (YoY)", desc: "Ay bazında iki yıl yan yana varyans analizi", Icon: CalendarBlank },
  ]},
  { cat: "REZERVASYON", items: [
    { key: "bookings", title: "Rezervasyon Raporu", desc: "Son 30 günün misafir detaylı rezervasyon dökümü", Icon: Receipt },
    { key: "source", title: "Kaynak / Kanal Raporu", desc: "Kanal bazlı hacim, gece ve gelir payı", Icon: Broadcast },
  ]},
];

export default function OwnerReportsHub({ ax }) {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState("");

  const open = async (key) => {
    setLoading(key);
    try {
      const r = await ax().get(`/owner-pulse/portal/reports/${key}`);
      setReport(r.data);
    } catch (e) { toast.error(e?.response?.data?.detail || "Rapor yüklenemedi"); }
    setLoading("");
  };

  const exportCsv = () => {
    if (!report) return;
    const head = report.columns.map((col) => col.label).join(",");
    const lines = report.rows.map((row) => report.columns.map((col) => `"${row[col.key] ?? ""}"`).join(","));
    const blob = new Blob(["\uFEFF" + [head, ...lines].join("\n")], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = `${report.title}.csv`; a.click();
    URL.revokeObjectURL(a.href);
  };

  if (report) {
    return (
      <div className="space-y-4" data-testid="op-report-view">
        <div className="flex items-center justify-between">
          <button onClick={() => setReport(null)} data-testid="op-report-back" className="text-xs px-3 py-1.5 bg-white border border-stone-300 rounded-lg inline-flex items-center gap-1 text-stone-700 hover:bg-stone-100"><ArrowLeft size={12} /> Rapor Kataloğu</button>
          <button onClick={exportCsv} data-testid="op-report-csv" className="text-xs px-3 py-1.5 bg-stone-900 text-white rounded-lg inline-flex items-center gap-1"><DownloadSimple size={12} /> CSV İndir</button>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-stone-200 text-sm font-semibold text-stone-800">{report.title}</div>
          <div className="max-h-[520px] overflow-auto">
            <table className="w-full text-xs">
              <thead className="text-[9px] uppercase text-stone-400 bg-stone-50 sticky top-0">
                <tr>{report.columns.map((col) => <th key={col.key} className="text-left px-4 py-2">{col.label}</th>)}</tr>
              </thead>
              <tbody>
                {report.rows.map((row, i) => (
                  <tr key={i} className="border-t border-stone-100">
                    {report.columns.map((col) => <td key={col.key} className="px-4 py-1.5 text-stone-600">{String(row[col.key] ?? "—")}</td>)}
                  </tr>
                ))}
                {report.rows.length === 0 && <tr><td colSpan={report.columns.length} className="px-4 py-8 text-center text-stone-400">Veri yok</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div data-testid="owner-reports-hub">
      <h2 className="text-2xl font-semibold text-stone-900">Rapor Merkezi</h2>
      <p className="text-sm text-stone-500 mt-0.5 mb-5">Özel analiz oluşturmak için bir rapor türü seçin</p>
      {CATALOG.map((group) => (
        <div key={group.cat} className="mb-6">
          <div className="text-[10px] uppercase tracking-wider text-stone-400 font-semibold mb-2">{group.cat}</div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {group.items.map(({ key, title, desc, Icon }) => (
              <button key={key} onClick={() => open(key)} data-testid={`op-report-${key}`}
                className="text-left bg-white border border-stone-200 rounded-xl p-4 hover:border-stone-400 hover:shadow-sm transition-all">
                <div className="flex items-center gap-2 text-sm font-semibold text-stone-800"><Icon size={16} className="text-teal-600" /> {title}{loading === key && <span className="text-[10px] text-stone-400">yükleniyor…</span>}</div>
                <div className="text-[11px] text-stone-500 mt-1.5">{desc}</div>
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
