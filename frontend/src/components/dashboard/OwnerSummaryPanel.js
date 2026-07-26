import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { FileText, Mail, TrendingUp, TrendingDown } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const money = (n) => `£${Number(n || 0).toLocaleString("en-GB", { maximumFractionDigits: 0 })}`;

const Delta = ({ v, money: isMoney }) => {
  if (v === 0 || v == null) return null;
  const up = v > 0;
  return (
    <span className={`inline-flex items-center gap-0.5 text-[10px] font-semibold ${up ? "text-emerald-600" : "text-rose-500"}`}>
      {up ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
      {up ? "+" : ""}{isMoney ? money(v) : v}
    </span>
  );
};

export default function OwnerSummaryPanel({ propertyId }) {
  const now = new Date();
  const defMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  const [month, setMonth] = useState(defMonth);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState("");
  const [sending, setSending] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/owner-summary/${propertyId || "all"}?month=${month}`);
      setData(r.data);
    } catch { toast.error("Özet yüklenemedi"); }
    finally { setLoading(false); }
  }, [propertyId, month]);
  useEffect(() => { load(); }, [load]);

  const downloadPdf = () => {
    window.open(`${API}/owner-summary/${propertyId || "all"}/pdf?month=${month}`, "_blank");
  };

  const send = async () => {
    if (!email.trim()) { toast.error("E-posta girin"); return; }
    setSending(true);
    try {
      const r = await axios.post(`${API}/owner-summary/send`, { property_id: propertyId || "all", month, email });
      toast.success(`Özet gönderildi (${r.data.email_status === "mock" ? "mock e-posta" : r.data.email_status})`);
    } catch { toast.error("Gönderilemedi"); }
    finally { setSending(false); }
  };

  const c = data?.current || {};
  const d = data?.deltas || {};
  const KPIS = [
    { label: "Toplam gelir", value: money(c.total_revenue), delta: d.total_revenue, money: true, hero: true },
    { label: "Doluluk", value: `%${c.occupancy_pct ?? 0}`, delta: d.occupancy_pct },
    { label: "ADR (ortalama gecelik)", value: money(c.adr), delta: d.adr, money: true },
    { label: "Oda geliri", value: money(c.room_revenue) },
    { label: "Alan geliri (Spaces)", value: money(c.spaces_revenue), delta: d.spaces_revenue, money: true },
    { label: "VCC tahsilatı", value: money(c.vcc_collected) },
    { label: "Kurumsal fatura tahsilatı", value: money(c.invoices_collected) },
    { label: "Satılan gece", value: c.nights_sold ?? 0, delta: d.nights_sold },
    { label: "Misafir sayısı", value: c.guest_count ?? 0 },
    { label: "İptal oranı", value: `%${c.cancellation_pct ?? 0}` },
    { label: "Online pay", value: `%${c.online_share_pct ?? 0}` },
    { label: "Komisyon maliyeti", value: money(c.commission_costs) },
  ];

  return (
    <div className="space-y-5" data-testid="owner-summary-panel">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-2xl font-semibold text-stone-900">Aylık Sahip Özeti</h2>
          <p className="text-sm text-stone-500 mt-1">{data?.property_name} — otel sahibi/yatırımcı için tek sayfalık yönetim raporu. Her ayın 1'inde otomatik hazırlanır.</p>
        </div>
        <div className="flex items-center gap-2">
          <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} data-testid="owner-month-input"
            className="border border-stone-300 rounded-lg px-3 py-2 text-sm" />
          <button onClick={downloadPdf} data-testid="owner-pdf-btn"
            className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-stone-900 hover:bg-stone-700 text-white text-sm font-medium">
            <FileText className="w-4 h-4" /> PDF indir
          </button>
        </div>
      </div>

      {loading ? (
        <div className="p-10 text-sm text-stone-400" data-testid="owner-loading">Yükleniyor…</div>
      ) : (
        <>
          <div className="grid grid-cols-4 gap-3">
            {KPIS.map((k) => (
              <div key={k.label} className={`rounded-xl p-4 border ${k.hero ? "bg-stone-900 border-stone-900 text-white col-span-1" : "bg-white border-stone-200"}`}
                data-testid={`owner-kpi-${k.label.split(" ")[0].toLowerCase()}`}>
                <div className={`text-xl font-bold ${k.hero ? "text-white" : "text-stone-900"}`}>{k.value}</div>
                <div className={`text-[11px] mt-1 flex items-center gap-2 ${k.hero ? "text-stone-300" : "text-stone-500"}`}>
                  {k.label} <Delta v={k.delta} money={k.money} />
                </div>
              </div>
            ))}
          </div>

          <div className="bg-white border border-stone-200 rounded-xl p-4 flex items-center gap-3 flex-wrap" data-testid="owner-send-box">
            <Mail className="w-4 h-4 text-stone-400" />
            <span className="text-sm font-medium text-stone-700">Sahibe e-postala:</span>
            <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="sahip@ornek.com"
              data-testid="owner-email-input"
              className="border border-stone-300 rounded-lg px-3 py-2 text-sm flex-1 min-w-[220px]" />
            <button onClick={send} disabled={sending} data-testid="owner-send-btn"
              className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-semibold disabled:opacity-50">
              {sending ? "Gönderiliyor…" : "Özeti gönder"}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
