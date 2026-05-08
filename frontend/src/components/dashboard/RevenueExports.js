import { useState } from "react";
import { Download, FileSpreadsheet, FileText, FileBarChart } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const ExportButton = ({ endpoint, label, formats = ["csv", "excel"] }) => {
  const [open, setOpen] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const download = async (format) => {
    setDownloading(true);
    setOpen(false);
    try {
      const token = localStorage.getItem("token") || sessionStorage.getItem("token");
      const sep = endpoint.includes("?") ? "&" : "?";
      const url = `${API}${endpoint}${sep}format=${format}`;
      const response = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
      if (!response.ok) throw new Error("Download failed");
      const blob = await response.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      const disposition = response.headers.get("Content-Disposition") || "";
      const match = disposition.match(/filename=(.+)/);
      a.download = match ? match[1] : `report.${format === "excel" ? "xlsx" : "csv"}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(a.href);
    } catch { /* silent */ }
    setDownloading(false);
  };

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        disabled={downloading}
        className="flex items-center gap-1.5 bg-stone-800 hover:bg-stone-900 text-white px-3 py-1.5 rounded-lg text-xs font-medium transition-all disabled:opacity-50"
        data-testid={`export-${label.toLowerCase().replace(/\s/g, "-")}`}
      >
        <Download className={`w-3.5 h-3.5 ${downloading ? "animate-bounce" : ""}`} />
        {downloading ? "Downloading..." : "Export"}
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full mt-1 bg-white border border-stone-200 rounded-xl shadow-lg z-50 py-1 min-w-[160px]">
            {formats.includes("csv") && (
              <button onClick={() => download("csv")} className="w-full flex items-center gap-2 px-3 py-2 text-sm text-stone-700 hover:bg-stone-50 transition-colors" data-testid={`export-csv-${label.toLowerCase().replace(/\s/g, "-")}`}>
                <FileText className="w-4 h-4 text-emerald-500" /> CSV
              </button>
            )}
            {formats.includes("excel") && (
              <button onClick={() => download("excel")} className="w-full flex items-center gap-2 px-3 py-2 text-sm text-stone-700 hover:bg-stone-50 transition-colors" data-testid={`export-excel-${label.toLowerCase().replace(/\s/g, "-")}`}>
                <FileSpreadsheet className="w-4 h-4 text-emerald-600" /> Excel (.xlsx)
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
};

export const ExportBar = ({ propertyId }) => {
  const reports = [
    { label: "Executive Summary", endpoint: `/revenue/export/executive-summary/${propertyId}`, icon: FileBarChart, desc: "KPIs, channel mix, overview" },
    { label: "Performance", endpoint: `/revenue/export/performance/${propertyId}`, icon: FileSpreadsheet, desc: "Daily occupancy, ADR, RevPAR" },
    { label: "Pickup Report", endpoint: `/revenue/export/pickup/${propertyId}`, icon: FileSpreadsheet, desc: "Booking pace & SDLY comparison" },
    { label: "Budget Variance", endpoint: `/revenue/export/budget/${propertyId}`, icon: FileSpreadsheet, desc: "Actual vs budget" },
    { label: "Forecasting", endpoint: `/revenue/export/forecasting/${propertyId}`, icon: FileSpreadsheet, desc: "30-day demand forecast" },
    { label: "Profit OS", endpoint: `/revenue/export/profit-os/${propertyId}`, icon: FileSpreadsheet, desc: "Channel profitability" },
    { label: "Distribution", endpoint: `/revenue/export/distribution/${propertyId}`, icon: FileSpreadsheet, desc: "Channel performance" },
  ];

  return (
    <div className="space-y-6" data-testid="rev-exports">
      <div>
        <h2 className="text-lg font-bold text-stone-800">Reports & Export</h2>
        <p className="text-sm text-stone-500">Download revenue reports in CSV or Excel format for board meetings and analysis.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {reports.map(r => (
          <div key={r.label} className="bg-white border border-stone-200 rounded-2xl p-5 hover:border-violet-200 hover:shadow-md transition-all group" data-testid={`export-card-${r.label.toLowerCase().replace(/\s/g, "-")}`}>
            <div className="flex items-start justify-between mb-3">
              <div className="w-10 h-10 rounded-xl bg-violet-50 flex items-center justify-center group-hover:bg-violet-100 transition-colors">
                <r.icon className="w-5 h-5 text-violet-600" />
              </div>
              <ExportButton endpoint={r.endpoint} label={r.label} />
            </div>
            <h3 className="font-bold text-stone-800 text-sm">{r.label}</h3>
            <p className="text-xs text-stone-400 mt-1">{r.desc}</p>
          </div>
        ))}
      </div>

      <div className="bg-blue-50 border border-blue-100 rounded-xl px-4 py-3 text-sm text-blue-800">
        <strong>Tip:</strong> Excel exports include branded headers and auto-sized columns. CSV exports are best for importing into other systems.
      </div>
    </div>
  );
};
