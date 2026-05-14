/**
 * Owner Self-Service Portal — public route `/owner`.
 *
 * Provides REIT / unit owners with their own login + dashboard,
 * separate from the main staff app. Uses `owner_access_token` localStorage
 * (segregated from staff `access_token`).
 */
import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast, Toaster } from "sonner";
import { Buildings, SignIn, SignOut, FilePdf, ChartLineUp, House } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const STORAGE_KEY = "owner_access_token";

const MONTH_LABELS = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];

export default function OwnerSelfServiceApp() {
  const [token, setToken] = useState(() => localStorage.getItem(STORAGE_KEY) || "");
  const [me, setMe] = useState(null);
  const [dashboard, setDashboard] = useState(null);
  const [year, setYear] = useState(new Date().getFullYear().toString());

  const ax = useCallback(() => axios.create({
    baseURL: API,
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  }), [token]);

  useEffect(() => {
    if (!token) return;
    (async () => {
      try {
        const r = await ax().get("/owner-auth/me");
        setMe(r.data);
      } catch (e) {
        localStorage.removeItem(STORAGE_KEY);
        setToken(""); setMe(null);
      }
    })();
  }, [token, ax]);

  const loadDashboard = useCallback(async () => {
    try {
      const r = await ax().get(`/owner-auth/dashboard?year=${year}`);
      setDashboard(r.data);
    } catch (e) { toast.error("Pano yüklenemedi"); }
  }, [year, ax]);

  useEffect(() => { if (me) loadDashboard(); }, [me, loadDashboard]);

  function logout() {
    localStorage.removeItem(STORAGE_KEY);
    setToken(""); setMe(null); setDashboard(null);
  }

  if (!token || !me) {
    return <OwnerLoginScreen onLogin={(t) => { localStorage.setItem(STORAGE_KEY, t); setToken(t); }} />;
  }

  return (
    <div className="min-h-screen bg-stone-50" data-testid="owner-self-service-app">
      <Toaster position="top-right" />
      <header className="bg-white border-b border-stone-200">
        <div className="max-w-6xl mx-auto px-5 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Buildings size={24} weight="fill" className="text-amber-600" />
            <div>
              <h1 className="text-base font-semibold text-stone-900">Sahip Portalı</h1>
              <p className="text-[11px] text-stone-500">Hoş geldiniz, {me.name}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-stone-500 hidden md:inline">{me.email}</span>
            <button onClick={logout} data-testid="owner-logout"
                    className="text-xs px-3 py-1.5 text-stone-700 bg-white border border-stone-300 rounded-lg inline-flex items-center gap-1 hover:bg-stone-100">
              <SignOut size={13} /> Çıkış
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-5 py-6">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h2 className="text-2xl font-semibold text-stone-900">{year} Performans Özeti</h2>
            <p className="text-sm text-stone-500 mt-0.5">
              {me.unit_count || 0} birim · Yönetim ücreti %{me.management_fee_percent}
            </p>
          </div>
          <select value={year} onChange={e => setYear(e.target.value)}
                  data-testid="owner-year-select"
                  className="px-3 py-1.5 text-sm border border-stone-300 rounded-lg bg-white">
            {[0, -1, -2].map(d => {
              const y = (new Date().getFullYear() + d).toString();
              return <option key={y} value={y}>{y}</option>;
            })}
          </select>
        </div>

        {!dashboard ? (
          <div className="text-center py-12 text-stone-400 text-sm">Yükleniyor…</div>
        ) : (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
              <KPI label="Brüt Gelir" value={`£${dashboard.total.revenue.toLocaleString("tr-TR")}`} icon={ChartLineUp} color="text-stone-900" />
              <KPI label="Net Dağıtım" value={`£${dashboard.total.net_distribution.toLocaleString("tr-TR")}`} icon={ChartLineUp} color="text-emerald-600" />
              <KPI label="Toplam Rezervasyon" value={dashboard.total.bookings_count} icon={House} color="text-stone-900" />
              <KPI label="Doluluk (gece)" value={dashboard.total.nights} icon={House} color="text-stone-900" />
            </div>

            <div className="bg-white border border-stone-200 rounded-xl overflow-hidden mb-5">
              <div className="px-4 py-2.5 border-b border-stone-200 text-sm font-semibold">Aylık Dağılım</div>
              <table className="w-full text-sm">
                <thead className="bg-stone-50 text-[11px] uppercase tracking-wider text-stone-500">
                  <tr>
                    <th className="px-4 py-2 text-left">Ay</th>
                    <th className="px-4 py-2 text-right">Gelir</th>
                    <th className="px-4 py-2 text-right">Yönetim Ücreti</th>
                    <th className="px-4 py-2 text-right">OpEx</th>
                    <th className="px-4 py-2 text-right">Net Dağıtım</th>
                    <th className="px-4 py-2 text-center">Ekstre</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.months.map((m, i) => (
                    <tr key={m.month} className="border-t border-stone-100" data-testid={`owner-month-${m.month}`}>
                      <td className="px-4 py-2 font-medium">{MONTH_LABELS[i]} {year}</td>
                      <td className="px-4 py-2 text-right">£{m.revenue.toFixed(2)}</td>
                      <td className="px-4 py-2 text-right text-rose-600">-£{m.mgmt_fee.toFixed(2)}</td>
                      <td className="px-4 py-2 text-right text-rose-600">-£{m.opex_est.toFixed(2)}</td>
                      <td className="px-4 py-2 text-right font-semibold text-emerald-600">£{m.net_distribution.toFixed(2)}</td>
                      <td className="px-4 py-2 text-center">
                        {m.revenue > 0 ? (
                          <a href={`${API}/owner-auth/statement.pdf?month=${m.month}`}
                             download
                             onClick={e => { e.preventDefault(); downloadPdf(token, m.month, me.id); }}
                             data-testid={`owner-pdf-${m.month}`}
                             className="text-xs px-2 py-0.5 bg-rose-50 text-rose-700 border border-rose-200 rounded inline-flex items-center gap-1 hover:bg-rose-100">
                            <FilePdf size={11} /> PDF
                          </a>
                        ) : (
                          <span className="text-xs text-stone-300">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="text-xs text-stone-400 mt-4 text-center">
              Sorularınız için yönetim ofisini arayın. PDF ekstreleri vergi belgesi olarak kullanılabilir.
            </div>
          </>
        )}
      </main>
    </div>
  );
}

// PDF needs auth header; we use blob fetch then trigger download
async function downloadPdf(token, month, ownerId) {
  try {
    const res = await fetch(`${API}/owner-auth/statement.pdf?month=${month}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) throw new Error("download_failed");
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `statement_${ownerId.slice(0, 8)}_${month}.pdf`;
    document.body.appendChild(a); a.click(); a.remove();
    window.URL.revokeObjectURL(url);
  } catch (e) {
    toast.error("PDF indirilemedi");
  }
}

function KPI({ label, value, icon: Icon, color }) {
  return (
    <div className="bg-white border border-stone-200 rounded-xl p-4">
      <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-stone-500">
        <Icon size={12} weight="fill" />{label}
      </div>
      <div className={`text-xl font-semibold mt-1 ${color || "text-stone-900"}`}>{value}</div>
    </div>
  );
}

function OwnerLoginScreen({ onLogin }) {
  const [email, setEmail] = useState("");
  const [pin, setPin] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e) {
    e?.preventDefault();
    if (!email || !pin) return;
    setLoading(true);
    try {
      const r = await axios.post(`${API}/owner-auth/login`, { email, pin });
      toast.success(`Hoş geldiniz, ${r.data.owner.name}`);
      onLogin(r.data.access_token);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Giriş başarısız");
    } finally { setLoading(false); }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-stone-100 via-amber-50/40 to-stone-100 flex items-center justify-center p-4" data-testid="owner-login-screen">
      <Toaster position="top-right" />
      <form onSubmit={submit} className="w-full max-w-md bg-white rounded-2xl shadow-xl border border-stone-200 p-7">
        <div className="flex items-center gap-3 mb-1">
          <div className="w-10 h-10 rounded-xl bg-amber-100 flex items-center justify-center">
            <Buildings size={22} weight="fill" className="text-amber-600" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-stone-900">Sahip Portalı</h1>
            <p className="text-xs text-stone-500">Birim performansınız ve aylık ekstreler</p>
          </div>
        </div>
        <div className="mt-6 space-y-3">
          <label className="block">
            <span className="text-xs font-medium text-stone-700">E-posta</span>
            <input value={email} onChange={e => setEmail(e.target.value)} type="email"
                   required data-testid="owner-login-email"
                   placeholder="ornek@firma.com"
                   className="mt-1 w-full px-3 py-2 text-sm border border-stone-300 rounded-lg focus:outline-none focus:border-stone-900" />
          </label>
          <label className="block">
            <span className="text-xs font-medium text-stone-700">PIN</span>
            <input value={pin} onChange={e => setPin(e.target.value)} type="password"
                   required data-testid="owner-login-pin"
                   placeholder="6 haneli PIN"
                   inputMode="numeric"
                   className="mt-1 w-full px-3 py-2 text-sm border border-stone-300 rounded-lg focus:outline-none focus:border-stone-900 font-mono tracking-widest" />
          </label>
          <button type="submit" disabled={loading || !email || !pin}
                  data-testid="owner-login-submit"
                  className="w-full py-2.5 text-sm font-medium text-white bg-stone-900 rounded-lg hover:bg-stone-800 disabled:opacity-50 inline-flex items-center justify-center gap-2">
            <SignIn size={14} /> {loading ? "Giriş yapılıyor…" : "Giriş Yap"}
          </button>
        </div>
        <p className="text-[11px] text-stone-400 mt-5 leading-relaxed">
          PIN'iniz yoksa veya unuttuysanız, lütfen yönetim ofisi ile iletişime geçin.
          Güvenliğiniz için PIN'inizi kimseyle paylaşmayın.
        </p>
      </form>
    </div>
  );
}
