import { useEffect, useState } from "react";
import axios from "axios";
import { CheckCircle2, Clock, MessageSquareText, Wrench } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STATUS_TR = {
  open: "Alındı", in_progress: "İlgileniliyor",
  resolved: "Çözüldü", closed: "Kapatıldı",
};

export default function ComplaintTrackPage({ token }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    axios.get(`${API}/public/complaint-track/${token}`)
      .then((r) => setData(r.data))
      .catch(() => setError("Takip kaydı bulunamadı. Lütfen linki kontrol edin."));
  }, [token]);

  if (error) return (
    <div className="min-h-screen bg-stone-50 flex items-center justify-center p-4">
      <p className="text-stone-600">{error}</p>
    </div>
  );
  if (!data) return (
    <div className="min-h-screen bg-stone-50 flex items-center justify-center">
      <div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );

  const steps = [
    { key: "open", label: "Talebiniz alındı", done: true, icon: Clock, at: data.created_at },
    { key: "routed", label: data.routed_department ? `${data.routed_department} ekibine iletildi` : "İlgili ekibe iletildi", done: !!data.routed_department, icon: Wrench },
    { key: "responded", label: "Size yanıt verildi", done: !!data.response_text, icon: MessageSquareText, at: data.response_at },
    { key: "resolved", label: "Çözüldü", done: data.status === "resolved" || data.status === "closed", icon: CheckCircle2, at: data.resolved_at },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-b from-stone-50 to-white p-4" data-testid="complaint-track-page">
      <div className="max-w-lg mx-auto pt-10 space-y-6">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-stone-900">Geri Bildirim Takibi</h1>
          <p className="text-sm text-stone-500 mt-1">
            Sayın {data.guest_name || "Misafirimiz"} — durum:{" "}
            <span className={`font-semibold ${data.status === "resolved" ? "text-emerald-600" : "text-amber-600"}`} data-testid="track-status">
              {STATUS_TR[data.status] || data.status}
            </span>
          </p>
        </div>
        <div className="bg-white rounded-2xl border border-stone-200 shadow-sm p-5 space-y-4">
          {steps.map((s) => (
            <div key={s.key} className="flex items-start gap-3">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${s.done ? "bg-emerald-100 text-emerald-600" : "bg-stone-100 text-stone-400"}`}>
                <s.icon className="w-4 h-4" />
              </div>
              <div>
                <p className={`text-sm ${s.done ? "text-stone-900 font-medium" : "text-stone-400"}`}>{s.label}</p>
                {s.at && <p className="text-[11px] text-stone-400">{s.at.slice(0, 16).replace("T", " ")}</p>}
              </div>
            </div>
          ))}
        </div>
        {data.response_text && (
          <div className="bg-emerald-50 border border-emerald-200 rounded-2xl p-5" data-testid="track-response">
            <p className="text-xs font-medium text-emerald-700 mb-2">Otel Yönetiminin Yanıtı</p>
            <p className="text-sm text-stone-700 whitespace-pre-wrap">{data.response_text}</p>
          </div>
        )}
        <p className="text-center text-[11px] text-stone-400">Bu sayfa otomatik güncellenir — linki saklayabilirsiniz.</p>
      </div>
    </div>
  );
}
