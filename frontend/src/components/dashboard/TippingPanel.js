import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  HandCoins,
  Trophy,
  ChatCircleDots,
  ArrowsClockwise,
  Users,
  QrCode,
  Copy,
} from "@phosphor-icons/react";
import CopilotButton from "../CopilotButton";

const API = process.env.REACT_APP_BACKEND_URL;

const ROLE_LABELS = {
  receptionist: "Resepsiyon",
  housekeeping: "Kat Hizmetleri",
  concierge: "Konsiyerj",
  bellhop: "Bellboy",
  restaurant: "Restoran",
  bar: "Bar",
  spa: "Spa",
  other: "Diğer",
};

export default function TippingPanel({ propertyId }) {
  const [tab, setTab] = useState("dashboard");

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="tipping-panel">
      <div className="mb-5">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          <HandCoins size={12} weight="fill" className="text-teal-500" />
          <span>Bahşiş · Dijital</span>
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">
          Digital Tipping
        </h1>
        <p className="text-sm text-stone-500 mt-1 max-w-2xl">
          QR ile ekipten doğrudan Stripe'a bahşiş. Sıfır ek vendor ücreti, native PMS entegrasyonu.
        </p>
      </div>

      <div className="flex gap-2 mb-5 border-b border-stone-200">
        <TabBtn active={tab === "dashboard"} onClick={() => setTab("dashboard")} testId="tip-tab-dashboard">
          <Trophy size={14} className="inline mr-1.5" />
          Lider Tablosu
        </TabBtn>
        <TabBtn active={tab === "qr"} onClick={() => setTab("qr")} testId="tip-tab-qr">
          <QrCode size={14} className="inline mr-1.5" />
          QR Linki
        </TabBtn>
      </div>

      {tab === "dashboard" && <DashboardTab propertyId={propertyId} />}
      {tab === "qr" && <QrTab propertyId={propertyId} />}
    </div>
  );
}

function TabBtn({ active, onClick, children, testId }) {
  return (
    <button
      onClick={onClick}
      data-testid={testId}
      className={`px-3.5 py-2 text-sm font-medium transition-all border-b-2 -mb-px ${
        active ? "border-teal-500 text-teal-700" : "border-transparent text-stone-500 hover:text-stone-800"
      }`}
    >
      {children}
    </button>
  );
}

function DashboardTab({ propertyId }) {
  const [data, setData] = useState(null);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const r = await axios.get(`${API}/api/tipping/leaderboard/${propertyId}?days=${days}`, { withCredentials: true });
      setData(r.data);
    } catch (e) {
      toast.error("Lider tablosu yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [propertyId, days]);

  useEffect(() => { load(); }, [load]);

  if (loading) return <div className="text-sm text-stone-400">Yükleniyor…</div>;
  if (!data) return null;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Kpi label="Toplam Bahşiş" value={`£${data.total_amount}`} color="teal" testId="tip-kpi-total" />
        <Kpi label="Adet" value={data.total_count} color="sky" testId="tip-kpi-count" />
        <Kpi label="Ortalama" value={`£${data.avg_tip}`} color="emerald" testId="tip-kpi-avg" />
        <Kpi label="Taranan Gün" value={`${data.days} gün`} color="amber" testId="tip-kpi-days" />
      </div>

      <div className="flex justify-end">
        <CopilotButton
          contextType="leaderboard"
          data={{ total_amount: data.total_amount, total_count: data.total_count, avg: data.avg_tip, top_staff: data.leaderboard.slice(0, 5), by_role: data.by_role }}
          label="AI Özet: Çalışan Performansı"
          testId="tip-copilot-btn"
        />
      </div>

      <div className="flex items-center gap-2">
        <label className="text-xs text-stone-600">Aralık:</label>
        {[7, 30, 90, 365].map((d) => (
          <button
            key={d}
            onClick={() => setDays(d)}
            data-testid={`tip-days-${d}`}
            className={`px-2.5 py-1 text-xs rounded-full border transition-all ${
              days === d ? "bg-teal-500 text-white border-teal-500" : "bg-white text-stone-600 border-stone-200 hover:border-stone-400"
            }`}
          >
            {d === 365 ? "Yıl" : `${d} gün`}
          </button>
        ))}
        <button onClick={load} className="ml-auto px-3 py-1 text-xs rounded-md border border-stone-200 text-stone-600 hover:bg-stone-50 inline-flex items-center gap-1.5">
          <ArrowsClockwise size={12} /> Yenile
        </button>
      </div>

      {/* Leaderboard */}
      <div className="bg-white border border-stone-200 rounded-lg overflow-hidden">
        <div className="p-3 bg-stone-50 border-b border-stone-200 flex items-center gap-2">
          <Trophy size={14} weight="fill" className="text-amber-500" />
          <div className="text-sm font-semibold text-stone-800">Çalışan Sıralaması</div>
        </div>
        {data.leaderboard.length === 0 ? (
          <div className="p-8 text-center text-stone-400 text-sm">Henüz bahşiş yok.</div>
        ) : (
          <div data-testid="tip-leaderboard">
            {data.leaderboard.map((r, i) => (
              <div key={r.staff_id} className="px-4 py-3 border-b border-stone-100 flex items-center gap-3 hover:bg-stone-50" data-testid={`tip-lb-row-${i}`}>
                <div className={`w-8 h-8 rounded-full inline-flex items-center justify-center font-semibold text-sm ${
                  i === 0 ? "bg-amber-100 text-amber-700" :
                  i === 1 ? "bg-stone-200 text-stone-700" :
                  i === 2 ? "bg-orange-100 text-orange-700" :
                  "bg-stone-100 text-stone-500"
                }`}>
                  {i + 1}
                </div>
                <div className="flex-1">
                  <div className="text-sm font-medium text-stone-900">{r.staff_name}</div>
                  <div className="text-[11px] text-stone-500">{r.count} bahşiş</div>
                </div>
                <div className="text-right">
                  <div className="text-base font-semibold text-stone-900">£{r.total}</div>
                  <div className="text-[11px] text-stone-400">ort £{(r.total / r.count).toFixed(2)}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Role distribution */}
      {data.by_role.length > 0 && (
        <div className="bg-white border border-stone-200 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-3">
            <Users size={14} className="text-teal-500" />
            <div className="text-sm font-semibold text-stone-800">Rol Dağılımı</div>
          </div>
          <div className="space-y-2" data-testid="tip-by-role">
            {data.by_role.map((r) => {
              const pct = data.total_amount > 0 ? (r.total / data.total_amount * 100).toFixed(1) : 0;
              return (
                <div key={r.role} className="flex items-center gap-2 text-sm">
                  <div className="w-28 text-stone-600">{ROLE_LABELS[r.role] || r.role}</div>
                  <div className="flex-1 bg-stone-100 rounded-full h-2">
                    <div className="bg-teal-500 h-2 rounded-full transition-all" style={{ width: `${pct}%` }} />
                  </div>
                  <div className="w-20 text-right font-medium text-stone-800">£{r.total}</div>
                  <div className="w-16 text-right text-stone-500 text-xs">{pct}%</div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Messages */}
      <div className="bg-white border border-stone-200 rounded-lg overflow-hidden">
        <div className="p-3 bg-stone-50 border-b border-stone-200 flex items-center gap-2">
          <ChatCircleDots size={14} weight="fill" className="text-sky-500" />
          <div className="text-sm font-semibold text-stone-800">Son Misafir Mesajları</div>
        </div>
        {data.recent_messages.length === 0 ? (
          <div className="p-8 text-center text-stone-400 text-sm">Mesajlı bahşiş yok.</div>
        ) : (
          <div data-testid="tip-messages">
            {data.recent_messages.map((m, i) => (
              <div key={i} className="px-4 py-3 border-b border-stone-100">
                <div className="flex items-center gap-2 mb-1">
                  <div className="text-sm font-medium text-stone-900">{m.guest_name}</div>
                  <div className="text-[11px] text-stone-400">→ {m.staff_name || ROLE_LABELS[m.staff_role]}</div>
                  <div className="ml-auto text-[11px] font-semibold text-teal-600">£{m.amount}</div>
                </div>
                <div className="text-xs text-stone-600 italic">"{m.message}"</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function Kpi({ label, value, color, testId }) {
  const bg = {
    teal: "bg-teal-50 text-teal-700",
    sky: "bg-sky-50 text-sky-700",
    emerald: "bg-emerald-50 text-emerald-700",
    amber: "bg-amber-50 text-amber-700",
  }[color];
  return (
    <div className={`${bg} border border-stone-100 rounded-lg p-3.5`} data-testid={testId}>
      <div className="text-[10px] uppercase tracking-wider opacity-70">{label}</div>
      <div className="text-2xl font-semibold mt-1">{value}</div>
    </div>
  );
}

function QrTab({ propertyId }) {
  const origin = window.location.origin;
  const propertyLink = `${origin}/tip/${propertyId}`;
  const copy = (text) => {
    navigator.clipboard.writeText(text);
    toast.success("Panoya kopyalandı");
  };

  const qrPng = (data) =>
    `https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=${encodeURIComponent(data)}`;

  return (
    <div className="space-y-4">
      <div className="bg-white border border-stone-200 rounded-lg p-6">
        <div className="flex items-start gap-6 flex-wrap">
          <div className="flex-shrink-0">
            <img src={qrPng(propertyLink)} alt="QR" width={220} height={220} className="border border-stone-200 rounded-md" data-testid="tip-qr-image" />
          </div>
          <div className="flex-1 min-w-[300px]">
            <div className="text-lg font-semibold text-stone-900 mb-2">Tesis Geneli Bahşiş Linki</div>
            <div className="text-sm text-stone-600 mb-4">
              QR kodu lobi, oda veya restoran masalarına yerleştirin. Misafirler kameralarıyla tarayıp
              doğrudan tesis veya bir ekip üyesine Stripe ile bahşiş bırakabilir.
            </div>
            <div className="bg-stone-50 border border-stone-200 rounded-md p-2 flex items-center gap-2 mb-3">
              <code className="text-xs text-stone-700 flex-1 truncate" data-testid="tip-qr-url">{propertyLink}</code>
              <button onClick={() => copy(propertyLink)} className="px-2 py-1 text-xs rounded border border-stone-200 text-stone-600 hover:bg-white inline-flex items-center gap-1">
                <Copy size={11} /> Kopyala
              </button>
            </div>
            <ul className="text-xs text-stone-500 space-y-1">
              <li>✓ 5 önerilen tutar: £2, £5, £10, £20, £50 (misafir istediğini girebilir)</li>
              <li>✓ Opsiyonel: Belirli çalışana bağlı link <code className="bg-stone-100 px-1 rounded">/tip/{propertyId}/{"{staff_id}"}</code></li>
              <li>✓ Ödeme Stripe Checkout, webhook ile otomatik kayıt</li>
              <li>✓ Misafir ad + teşekkür mesajı bırakabilir (isteğe bağlı)</li>
            </ul>
          </div>
        </div>
      </div>

      <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-xs text-amber-800">
        <b>İpucu:</b> Oda kartı arkasına QR bas. Hizmet sektöründe dijital bahşiş oranı fiziksel nakiti %400 geride bırakıyor.
      </div>
    </div>
  );
}
