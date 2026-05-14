/**
 * TÜRSAB Agency Portal — public route `/agency`.
 *
 * Self-service portal for travel agencies (acentalar) to view their
 * contracted rates, get quotes, create bookings, and track commissions.
 * Uses `agency_access_token` localStorage (segregated from staff & owner tokens).
 */
import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast, Toaster } from "sonner";
import { Briefcase, SignIn, SignOut, ChartLineUp, House, Plus, Receipt, Calendar } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const STORAGE_KEY = "agency_access_token";
const MONTH_LABELS = ["Oca","Şub","Mar","Nis","May","Haz","Tem","Ağu","Eyl","Eki","Kas","Ara"];

export default function AgencyPortalApp() {
  const [token, setToken] = useState(() => localStorage.getItem(STORAGE_KEY) || "");
  const [me, setMe] = useState(null);
  const [tab, setTab] = useState("dashboard");

  const ax = useCallback(() => axios.create({
    baseURL: API,
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  }), [token]);

  useEffect(() => {
    if (!token) return;
    (async () => {
      try {
        const r = await ax().get("/agency-auth/me");
        setMe(r.data);
      } catch {
        localStorage.removeItem(STORAGE_KEY); setToken(""); setMe(null);
      }
    })();
  }, [token, ax]);

  function logout() {
    localStorage.removeItem(STORAGE_KEY); setToken(""); setMe(null);
  }

  if (!token || !me) {
    return <AgencyLoginScreen onLogin={(t) => { localStorage.setItem(STORAGE_KEY, t); setToken(t); }} />;
  }

  return (
    <div className="min-h-screen bg-stone-50" data-testid="agency-portal-app">
      <Toaster position="top-right" />
      <header className="bg-white border-b border-stone-200">
        <div className="max-w-6xl mx-auto px-5 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Briefcase size={24} weight="fill" className="text-sky-600" />
            <div>
              <h1 className="text-base font-semibold text-stone-900">Acenta Portalı</h1>
              <p className="text-[11px] text-stone-500">
                {me.name}{me.tursab_no ? ` · TÜRSAB ${me.tursab_no}` : ""}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-stone-500 hidden md:inline">{me.email}</span>
            <button onClick={logout} data-testid="agency-logout"
                    className="text-xs px-3 py-1.5 text-stone-700 bg-white border border-stone-300 rounded-lg inline-flex items-center gap-1 hover:bg-stone-100">
              <SignOut size={13} /> Çıkış
            </button>
          </div>
        </div>
        <nav className="max-w-6xl mx-auto px-5 flex gap-1 -mt-1 overflow-x-auto">
          {[
            {k:"dashboard", label:"Pano", icon:ChartLineUp, tid:"tab-dashboard"},
            {k:"contracts", label:"Kontratlarım", icon:Receipt, tid:"tab-contracts"},
            {k:"book",      label:"Rezervasyon Oluştur", icon:Plus, tid:"tab-book"},
            {k:"bookings",  label:"Rezervasyonlarım", icon:Calendar, tid:"tab-bookings"},
          ].map(t => (
            <button key={t.k} onClick={() => setTab(t.k)} data-testid={t.tid}
                    className={`px-3 py-2 text-xs font-medium border-b-2 inline-flex items-center gap-1.5 ${
                      tab===t.k ? "border-sky-600 text-sky-700"
                                : "border-transparent text-stone-500 hover:text-stone-800"
                    }`}>
              <t.icon size={13} weight="bold" /> {t.label}
            </button>
          ))}
        </nav>
      </header>

      <main className="max-w-6xl mx-auto px-5 py-6">
        {tab === "dashboard" && <DashboardTab ax={ax} me={me} />}
        {tab === "contracts" && <ContractsTab ax={ax} />}
        {tab === "book" && <BookTab ax={ax} />}
        {tab === "bookings" && <BookingsTab ax={ax} />}
      </main>
    </div>
  );
}

function DashboardTab({ ax, me }) {
  const [year, setYear] = useState(new Date().getFullYear().toString());
  const [data, setData] = useState(null);
  useEffect(() => {
    ax().get(`/agency-auth/dashboard?year=${year}`).then(r => setData(r.data))
        .catch(() => toast.error("Pano yüklenemedi"));
  }, [year, ax]);
  if (!data) return <div className="text-center py-12 text-stone-400 text-sm">Yükleniyor…</div>;
  return (
    <div>
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-2xl font-semibold text-stone-900">{year} Performansı</h2>
          <p className="text-sm text-stone-500 mt-0.5">
            Varsayılan komisyon %{me.default_commission_percent}
          </p>
        </div>
        <select value={year} onChange={e => setYear(e.target.value)} data-testid="agency-year-select"
                className="px-3 py-1.5 text-sm border border-stone-300 rounded-lg bg-white">
          {[0,-1,-2].map(d => {
            const y = (new Date().getFullYear()+d).toString();
            return <option key={y} value={y}>{y}</option>;
          })}
        </select>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
        <KPI label="Toplam Üretim" value={`${data.total.revenue.toLocaleString("tr-TR")} TL`} />
        <KPI label="Komisyon" value={`${data.total.commission.toLocaleString("tr-TR")} TL`} color="text-emerald-600" />
        <KPI label="Rezervasyon" value={data.total.bookings_count} />
        <KPI label="Toplam Gece" value={data.total.nights} />
      </div>
      <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
        <div className="px-4 py-2.5 border-b border-stone-200 text-sm font-semibold">Aylık Dağılım</div>
        <table className="w-full text-sm">
          <thead className="bg-stone-50 text-[11px] uppercase tracking-wider text-stone-500">
            <tr>
              <th className="px-4 py-2 text-left">Ay</th>
              <th className="px-4 py-2 text-right">Üretim</th>
              <th className="px-4 py-2 text-right">Rezervasyon</th>
              <th className="px-4 py-2 text-right">Gece</th>
              <th className="px-4 py-2 text-right">Komisyon</th>
            </tr>
          </thead>
          <tbody>
            {data.months.map((m,i) => (
              <tr key={m.month} className="border-t border-stone-100" data-testid={`agency-month-${m.month}`}>
                <td className="px-4 py-2 font-medium">{MONTH_LABELS[i]} {year}</td>
                <td className="px-4 py-2 text-right">{m.revenue.toFixed(2)} TL</td>
                <td className="px-4 py-2 text-right">{m.bookings}</td>
                <td className="px-4 py-2 text-right">{m.nights}</td>
                <td className="px-4 py-2 text-right font-semibold text-emerald-600">
                  {m.commission.toFixed(2)} TL
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ContractsTab({ ax }) {
  const [items, setItems] = useState([]);
  useEffect(() => {
    ax().get("/agency-auth/contracts").then(r => setItems(r.data.items || []))
        .catch(() => toast.error("Kontratlar yüklenemedi"));
  }, [ax]);
  if (!items.length) {
    return <div className="text-center py-16 text-stone-400 text-sm">
      Henüz aktif kontratınız yok. Lütfen otel yönetimi ile iletişime geçin.
    </div>;
  }
  return (
    <div>
      <h2 className="text-2xl font-semibold text-stone-900 mb-4">Kontrat Tarifelerim</h2>
      <div className="grid md:grid-cols-2 gap-3">
        {items.map(c => (
          <div key={c.id} data-testid={`contract-${c.id}`}
               className="bg-white border border-stone-200 rounded-xl p-4">
            <div className="flex items-start justify-between mb-2">
              <div>
                <div className="font-semibold text-stone-900">{c.property_name}</div>
                <div className="text-xs text-stone-500">{c.room_type_name}</div>
              </div>
              <span className={`text-[10px] px-2 py-0.5 rounded-full ${
                c.valid_now ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"
              }`}>{c.valid_now ? "AKTİF" : "GEÇERSİZ"}</span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <Field label="Fiyat" value={`${c.contract_rate} ${c.currency}/gece`} bold />
              <Field label="Komisyon" value={`%${c.commission_percent}`} />
              <Field label="Min/Maks" value={`${c.min_stay || 1}-${c.max_stay || 30} gece`} />
              <Field label="Geçerlilik" value={`${c.valid_from || "-"} → ${c.valid_to || "-"}`} />
            </div>
            {c.promotion && (
              <div className="mt-2 text-[11px] bg-amber-50 border border-amber-200 rounded px-2 py-1 text-amber-800">
                🎁 Promosyon: {c.promotion.type === "stay_pay"
                  ? `${c.promotion.stay} yat ${c.promotion.pay} öde`
                  : c.promotion.type === "early_bird"
                    ? `${c.promotion.days_ahead}+ gün önce: -%${c.promotion.discount_percent}`
                    : JSON.stringify(c.promotion)}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function BookTab({ ax }) {
  const [contracts, setContracts] = useState([]);
  const [form, setForm] = useState({
    property_id: "", room_type_id: "", check_in: "", check_out: "",
    guests: 2, guest_name: "", guest_email: "", guest_phone: "", notes: "",
  });
  const [quote, setQuote] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    ax().get("/agency-auth/contracts").then(r => setContracts(r.data.items || []));
  }, [ax]);

  const propOptions = Array.from(new Map(contracts.map(c => [c.property_id, c.property_name])).entries());
  const rtOptions = contracts
    .filter(c => c.property_id === form.property_id)
    .map(c => ({ id: c.room_type_id, name: c.room_type_name }));

  async function getQuote() {
    if (!form.property_id || !form.room_type_id || !form.check_in || !form.check_out) {
      toast.error("Tüm tarih/oda alanlarını doldurun"); return;
    }
    setLoading(true);
    try {
      const r = await ax().post("/agency-auth/quote", form);
      setQuote(r.data);
    } catch (e) { toast.error(e?.response?.data?.detail || "Fiyat alınamadı"); }
    finally { setLoading(false); }
  }

  async function book() {
    if (!form.guest_name) { toast.error("Misafir adı girin"); return; }
    setLoading(true);
    try {
      const r = await ax().post("/agency-auth/book", form);
      toast.success(`Rezervasyon oluşturuldu: ${r.data.booking_ref}`);
      setForm({...form, guest_name:"", guest_email:"", guest_phone:"", notes:""});
      setQuote(null);
    } catch (e) { toast.error(e?.response?.data?.detail || "Rezervasyon oluşturulamadı"); }
    finally { setLoading(false); }
  }

  return (
    <div className="max-w-3xl">
      <h2 className="text-2xl font-semibold text-stone-900 mb-4">Yeni Rezervasyon</h2>
      <div className="bg-white border border-stone-200 rounded-xl p-5 space-y-4">
        <div className="grid md:grid-cols-2 gap-3">
          <Input label="Mülk" data-testid="book-property">
            <select value={form.property_id} data-testid="book-property-select"
                    onChange={e => setForm({...form, property_id:e.target.value, room_type_id:""})}
                    className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg">
              <option value="">Seçin</option>
              {propOptions.map(([id,name]) => <option key={id} value={id}>{name}</option>)}
            </select>
          </Input>
          <Input label="Oda Tipi" data-testid="book-roomtype">
            <select value={form.room_type_id} data-testid="book-roomtype-select"
                    onChange={e => setForm({...form, room_type_id:e.target.value})}
                    className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg">
              <option value="">Seçin</option>
              {rtOptions.map(o => <option key={o.id||""} value={o.id||""}>{o.name}</option>)}
            </select>
          </Input>
          <Input label="Giriş Tarihi">
            <input type="date" value={form.check_in} data-testid="book-checkin"
                   onChange={e => setForm({...form, check_in:e.target.value})}
                   className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg" />
          </Input>
          <Input label="Çıkış Tarihi">
            <input type="date" value={form.check_out} data-testid="book-checkout"
                   onChange={e => setForm({...form, check_out:e.target.value})}
                   className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg" />
          </Input>
          <Input label="Misafir Sayısı">
            <input type="number" min="1" value={form.guests}
                   onChange={e => setForm({...form, guests:parseInt(e.target.value)||1})}
                   className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg" />
          </Input>
        </div>
        <button onClick={getQuote} disabled={loading} data-testid="book-getquote-btn"
                className="px-4 py-2 text-sm font-medium bg-stone-900 text-white rounded-lg hover:bg-stone-800 disabled:opacity-50">
          {loading ? "Hesaplanıyor…" : "Fiyat Al"}
        </button>

        {quote && (
          <div className="bg-sky-50 border border-sky-200 rounded-lg p-3 text-sm" data-testid="book-quote-box">
            <div className="font-semibold text-sky-900 mb-1">Teklif</div>
            <div className="grid grid-cols-2 gap-1.5 text-xs">
              <Field label="Gece" value={`${quote.nights} (öde: ${quote.pay_nights})`} />
              <Field label="Gece Tarifesi" value={`${quote.contract_rate_per_night} ${quote.currency}`} />
              <Field label="Toplam Brüt" value={`${quote.total_gross} ${quote.currency}`} bold />
              <Field label="Komisyon" value={`%${quote.commission_percent} = ${quote.commission_amount} ${quote.currency}`} />
              <Field label="Otel'e Net" value={`${quote.net_payable_to_hotel} ${quote.currency}`} />
              {quote.promotion && <Field label="Promosyon" value={quote.promotion} />}
            </div>
            <div className="border-t border-sky-200 mt-3 pt-3 space-y-2">
              <div className="grid md:grid-cols-2 gap-2">
                <input placeholder="Misafir Adı Soyadı" value={form.guest_name} data-testid="book-guestname"
                       onChange={e => setForm({...form, guest_name:e.target.value})}
                       className="px-3 py-1.5 text-xs border border-sky-300 rounded bg-white" />
                <input placeholder="E-posta" value={form.guest_email}
                       onChange={e => setForm({...form, guest_email:e.target.value})}
                       className="px-3 py-1.5 text-xs border border-sky-300 rounded bg-white" />
                <input placeholder="Telefon" value={form.guest_phone}
                       onChange={e => setForm({...form, guest_phone:e.target.value})}
                       className="px-3 py-1.5 text-xs border border-sky-300 rounded bg-white" />
                <input placeholder="Notlar" value={form.notes}
                       onChange={e => setForm({...form, notes:e.target.value})}
                       className="px-3 py-1.5 text-xs border border-sky-300 rounded bg-white" />
              </div>
              <button onClick={book} disabled={loading || !form.guest_name} data-testid="book-confirm-btn"
                      className="w-full py-2 text-sm font-medium bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 disabled:opacity-50">
                Rezervasyonu Onayla
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function BookingsTab({ ax }) {
  const [items, setItems] = useState([]);
  useEffect(() => {
    ax().get("/agency-auth/bookings?limit=200").then(r => setItems(r.data.items || []));
  }, [ax]);
  return (
    <div>
      <h2 className="text-2xl font-semibold text-stone-900 mb-4">Rezervasyonlarım</h2>
      {items.length === 0 ? (
        <div className="text-center py-16 text-stone-400 text-sm">Henüz rezervasyon yok.</div>
      ) : (
        <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-stone-50 text-[11px] uppercase tracking-wider text-stone-500">
              <tr>
                <th className="px-4 py-2 text-left">Ref</th>
                <th className="px-4 py-2 text-left">Misafir</th>
                <th className="px-4 py-2 text-left">Giriş→Çıkış</th>
                <th className="px-4 py-2 text-right">Tutar</th>
                <th className="px-4 py-2 text-right">Komisyon</th>
                <th className="px-4 py-2 text-center">Durum</th>
              </tr>
            </thead>
            <tbody>
              {items.map(b => (
                <tr key={b.id} className="border-t border-stone-100" data-testid={`agency-booking-${b.booking_ref}`}>
                  <td className="px-4 py-2 font-mono text-xs">{b.booking_ref}</td>
                  <td className="px-4 py-2">{b.guest_name}</td>
                  <td className="px-4 py-2 text-xs">{b.check_in?.slice(0,10)} → {b.check_out?.slice(0,10)}</td>
                  <td className="px-4 py-2 text-right">{b.total_price} {b.currency}</td>
                  <td className="px-4 py-2 text-right text-emerald-600">{b.commission_amount || 0}</td>
                  <td className="px-4 py-2 text-center">
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-stone-100 text-stone-700">{b.status}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function KPI({ label, value, color }) {
  return (
    <div className="bg-white border border-stone-200 rounded-xl p-4">
      <div className="text-[10px] uppercase tracking-wider text-stone-500">{label}</div>
      <div className={`text-xl font-semibold mt-1 ${color || "text-stone-900"}`}>{value}</div>
    </div>
  );
}

function Field({ label, value, bold }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-stone-500">{label}</div>
      <div className={`${bold ? "font-semibold text-stone-900" : "text-stone-700"}`}>{value}</div>
    </div>
  );
}

function Input({ label, children }) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-stone-700 block mb-1">{label}</span>
      {children}
    </label>
  );
}

function AgencyLoginScreen({ onLogin }) {
  const [email, setEmail] = useState("");
  const [pin, setPin] = useState("");
  const [loading, setLoading] = useState(false);
  async function submit(e) {
    e?.preventDefault();
    if (!email || !pin) return;
    setLoading(true);
    try {
      const r = await axios.post(`${API}/agency-auth/login`, { email, pin });
      toast.success(`Hoş geldiniz, ${r.data.agency.name}`);
      onLogin(r.data.access_token);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Giriş başarısız");
    } finally { setLoading(false); }
  }
  return (
    <div className="min-h-screen bg-gradient-to-br from-stone-100 via-sky-50/40 to-stone-100 flex items-center justify-center p-4"
         data-testid="agency-login-screen">
      <Toaster position="top-right" />
      <form onSubmit={submit} className="w-full max-w-md bg-white rounded-2xl shadow-xl border border-stone-200 p-7">
        <div className="flex items-center gap-3 mb-1">
          <div className="w-10 h-10 rounded-xl bg-sky-100 flex items-center justify-center">
            <Briefcase size={22} weight="fill" className="text-sky-600" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-stone-900">Acenta Portalı</h1>
            <p className="text-xs text-stone-500">TÜRSAB üye acentaları için</p>
          </div>
        </div>
        <div className="mt-6 space-y-3">
          <label className="block">
            <span className="text-xs font-medium text-stone-700">E-posta</span>
            <input value={email} onChange={e => setEmail(e.target.value)} type="email"
                   required data-testid="agency-login-email"
                   placeholder="acenta@ornek.com.tr"
                   className="mt-1 w-full px-3 py-2 text-sm border border-stone-300 rounded-lg focus:outline-none focus:border-stone-900" />
          </label>
          <label className="block">
            <span className="text-xs font-medium text-stone-700">PIN</span>
            <input value={pin} onChange={e => setPin(e.target.value)} type="password"
                   required data-testid="agency-login-pin"
                   placeholder="6 haneli PIN"
                   inputMode="numeric"
                   className="mt-1 w-full px-3 py-2 text-sm border border-stone-300 rounded-lg focus:outline-none focus:border-stone-900 font-mono tracking-widest" />
          </label>
          <button type="submit" disabled={loading || !email || !pin}
                  data-testid="agency-login-submit"
                  className="w-full py-2.5 text-sm font-medium text-white bg-stone-900 rounded-lg hover:bg-stone-800 disabled:opacity-50 inline-flex items-center justify-center gap-2">
            <SignIn size={14} /> {loading ? "Giriş yapılıyor…" : "Giriş Yap"}
          </button>
        </div>
        <p className="text-[11px] text-stone-400 mt-5 leading-relaxed">
          PIN'iniz yoksa veya unuttuysanız, anlaşmalı otel yönetimi ile iletişime geçin.
        </p>
      </form>
    </div>
  );
}
