import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Download, FileText, TrendingUp, Users, Wrench, ShoppingCart, Heart, ClipboardList } from "lucide-react";
import { CurrencyDollar, CheckCircle, WarningCircle, Smiley } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export function ReportsCentrePanel({ properties, activePropertyId: propId }) {
  const activePropertyId = propId || "all";
  const [period, setPeriod] = useState("month");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const { data: d } = await axios.get(`${API}/reports/summary/${activePropertyId}?period=${period}`);
      setData(d);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [activePropertyId, period]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const exportCSV = (type) => {
    const url = `${API}/reports/export/${activePropertyId}/${type}?period=${period}`;
    window.open(url, "_blank");
    toast.success(`Downloading ${type} report...`);
  };

  if (loading || !data) return <div className="p-6"><div className="animate-pulse space-y-4"><div className="h-8 bg-stone-100 rounded w-48" /><div className="grid grid-cols-4 gap-4">{[1,2,3,4].map(i => <div key={i} className="h-24 bg-stone-100 rounded-xl" />)}</div></div></div>;

  return (
    <div className="p-6 space-y-6" data-testid="reports-centre">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-stone-800" data-testid="reports-title">Reports Centre</h1>
          <p className="text-sm text-stone-500 mt-0.5">Consolidated overview across all modules</p>
        </div>
        <Select value={period} onValueChange={setPeriod}>
          <SelectTrigger className="w-36" data-testid="period-select"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="week">Last 7 Days</SelectItem>
            <SelectItem value="month">Last 30 Days</SelectItem>
            <SelectItem value="quarter">Last 90 Days</SelectItem>
            <SelectItem value="year">Last Year</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-4" data-testid="summary-cards">
        <SummaryCard title="Bookings" value={data.bookings.total} sub={`${data.bookings.confirmed} confirmed`} extra={`Revenue: £${data.bookings.revenue.toLocaleString()}`} icon={<ClipboardList size={18} className="text-blue-500" />} bg="bg-blue-50" />
        <SummaryCard title="Maintenance" value={data.maintenance.total} sub={`${data.maintenance.resolved} resolved`} extra={data.maintenance.overdue > 0 ? `${data.maintenance.overdue} overdue!` : "No SLA breaches"} icon={<Wrench size={18} className="text-orange-500" />} bg="bg-orange-50" alert={data.maintenance.overdue > 0} />
        <SummaryCard title="Guest Registration" value={data.guest_journey.registrations} sub={`${data.guest_journey.completion_rate}% completed`} extra={`${data.guest_journey.completed} finished`} icon={<Users size={18} className="text-violet-500" />} bg="bg-violet-50" />
        <SummaryCard title="Satisfaction" value={data.satisfaction.total > 0 ? `${data.satisfaction.satisfaction_rate}%` : "—"} sub={`${data.satisfaction.happy} happy / ${data.satisfaction.need_help} need help`} extra={`${data.satisfaction.total} responses`} icon={<Smiley size={18} className="text-emerald-500" weight="fill" />} bg="bg-emerald-50" />
      </div>

      {/* Detail Sections */}
      <div className="grid grid-cols-2 gap-4">
        {/* Revenue */}
        <ReportSection title="Revenue Overview" icon={<CurrencyDollar size={16} className="text-blue-600" />}>
          <Row label="Booking Revenue" value={`£${data.bookings.revenue.toLocaleString()}`} bold />
          <Row label="POS Revenue" value={`£${data.pos.revenue.toLocaleString()}`} />
          <Row label="POS Orders" value={data.pos.orders} />
          <Row label="Maintenance Costs" value={`-£${data.maintenance.cost.toLocaleString()}`} red />
          <div className="border-t border-stone-100 pt-2 mt-2">
            <Row label="Net (Booking + POS - Maint)" value={`£${(data.bookings.revenue + data.pos.revenue - data.maintenance.cost).toLocaleString()}`} bold />
          </div>
        </ReportSection>

        {/* Operations */}
        <ReportSection title="Operations Summary" icon={<Wrench size={16} className="text-orange-600" />}>
          <Row label="Open Issues" value={data.maintenance.open} alert={data.maintenance.open > 5} />
          <Row label="Resolved Issues" value={data.maintenance.resolved} />
          <Row label="SLA Breaches" value={data.maintenance.overdue} alert={data.maintenance.overdue > 0} />
          <Row label="Maintenance Cost" value={`£${data.maintenance.cost.toLocaleString()}`} />
          <Row label="Loyalty Members" value={data.loyalty.members} />
        </ReportSection>
      </div>

      {/* Export Section */}
      <div className="bg-white rounded-xl border border-stone-200/60 p-5" data-testid="export-section">
        <h3 className="text-sm font-semibold text-stone-800 mb-3">Export Reports (CSV)</h3>
        <div className="grid grid-cols-5 gap-3">
          {[
            { type: "bookings", label: "Bookings", icon: <ClipboardList size={14} /> },
            { type: "maintenance", label: "Maintenance", icon: <Wrench size={14} /> },
            { type: "registrations", label: "Guest Registrations", icon: <Users size={14} /> },
            { type: "pos", label: "POS Orders", icon: <ShoppingCart size={14} /> },
            { type: "satisfaction", label: "Satisfaction", icon: <Heart size={14} /> },
          ].map(r => (
            <button key={r.type} onClick={() => exportCSV(r.type)} className="flex items-center justify-center gap-2 py-3 border border-stone-200 rounded-xl hover:bg-stone-50 text-sm font-medium text-stone-700 transition" data-testid={`export-${r.type}`}>
              <Download size={14} className="text-stone-400" /> {r.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function SummaryCard({ title, value, sub, extra, icon, bg, alert }) {
  return (
    <div className={`${bg} rounded-xl p-4`}>
      <div className="flex items-center gap-2 mb-2">{icon}<span className="text-xs font-semibold text-stone-600">{title}</span></div>
      <p className={`text-2xl font-bold ${alert ? "text-red-600" : "text-stone-800"}`}>{value}</p>
      <p className="text-xs text-stone-500 mt-0.5">{sub}</p>
      <p className={`text-[10px] mt-1 ${alert ? "text-red-500 font-medium" : "text-stone-400"}`}>{extra}</p>
    </div>
  );
}

function ReportSection({ title, icon, children }) {
  return (
    <div className="bg-white rounded-xl border border-stone-200/60 p-5">
      <div className="flex items-center gap-2 mb-3">{icon}<h3 className="text-sm font-semibold text-stone-800">{title}</h3></div>
      <div className="space-y-2 text-sm">{children}</div>
    </div>
  );
}

function Row({ label, value, bold, red, alert }) {
  return (
    <div className="flex justify-between">
      <span className="text-stone-500">{label}</span>
      <span className={`${bold ? "font-bold text-stone-800" : "font-medium text-stone-700"} ${red ? "text-red-600" : ""} ${alert ? "text-red-600 font-bold" : ""}`}>{value}</span>
    </div>
  );
}
