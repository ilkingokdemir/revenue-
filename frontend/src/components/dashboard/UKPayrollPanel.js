import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Users, Calculator, History, RefreshCw, Download, Mail, AlertTriangle,
  CheckCircle, XCircle, UserMinus, UserPlus, Pencil, ShieldCheck, PoundSterling,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cfg = { withCredentials: true };

const MONTHS_TR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
  "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"];
const CONTRACT_TYPES = [
  { v: "full_time", l: "Tam zamanlı" }, { v: "part_time", l: "Yarı zamanlı" },
  { v: "zero_hours", l: "Zero-hours" }, { v: "apprentice", l: "Çırak (Apprentice)" },
];
const TAX_CODES = ["1257L", "1257L W1", "BR", "0T", "D0", "D1", "NT"];
const SL_PLANS = [
  { v: "plan_1", l: "Plan 1" }, { v: "plan_2", l: "Plan 2" },
  { v: "plan_4", l: "Plan 4" }, { v: "postgraduate", l: "Postgraduate" },
];

const gbp = (n) => `£${Number(n || 0).toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const Field = ({ label, children }) => (
  <label className="block text-xs">
    <span className="text-stone-500 font-medium">{label}</span>
    <div className="mt-1">{children}</div>
  </label>
);
const inputCls = "w-full border border-stone-300 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500";

function HrEditDialog({ emp, onClose, onSaved }) {
  const [f, setF] = useState({
    name: emp.name || "", email: emp.email || "", phone: emp.phone || "",
    role: emp.role || "receptionist", pay_type: emp.pay_type || "hourly",
    pay_rate: emp.pay_rate || 0, dob: emp.dob || "", ni_number: emp.ni_number || "",
    tax_code: emp.tax_code || "1257L", contract_type: emp.contract_type || "full_time",
    start_date: emp.start_date || "", bank_sort_code: emp.bank_sort_code || "",
    bank_account_no: emp.bank_account_no || "", student_loan_plans: emp.student_loan_plans || [],
    address: emp.address || "", postcode: emp.postcode || "",
  });
  const [saving, setSaving] = useState(false);
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));
  const save = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/uk-payroll/employees/${emp.id}/hr`, { ...f, pay_rate: parseFloat(f.pay_rate) || 0 }, cfg);
      toast.success("İK kaydı güncellendi");
      onSaved();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Kaydedilemedi");
    }
    setSaving(false);
  };
  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" data-testid="hr-edit-dialog">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-bold text-lg">İK Kaydı — {emp.name}</h3>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-700" data-testid="hr-edit-close"><XCircle size={22} /></button>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <Field label="Ad Soyad"><input className={inputCls} value={f.name} onChange={(e) => set("name", e.target.value)} data-testid="hr-name-input" /></Field>
          <Field label="E-posta"><input className={inputCls} value={f.email} onChange={(e) => set("email", e.target.value)} data-testid="hr-email-input" /></Field>
          <Field label="Telefon"><input className={inputCls} value={f.phone} onChange={(e) => set("phone", e.target.value)} /></Field>
          <Field label="Rol">
            <select className={inputCls} value={f.role} onChange={(e) => set("role", e.target.value)}>
              {["receptionist", "housekeeper", "maintenance", "manager", "chef", "waiter"].map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </Field>
          <Field label="Ücret tipi">
            <select className={inputCls} value={f.pay_type} onChange={(e) => set("pay_type", e.target.value)}>
              <option value="hourly">Saatlik</option><option value="daily">Günlük</option>
            </select>
          </Field>
          <Field label={`Ücret (£/${f.pay_type === "hourly" ? "saat" : "gün"})`}>
            <input type="number" step="0.01" className={inputCls} value={f.pay_rate} onChange={(e) => set("pay_rate", e.target.value)} data-testid="hr-payrate-input" />
          </Field>
          <Field label="Doğum tarihi"><input type="date" className={inputCls} value={f.dob} onChange={(e) => set("dob", e.target.value)} data-testid="hr-dob-input" /></Field>
          <Field label="NI numarası"><input className={inputCls} placeholder="AB123456C" value={f.ni_number} onChange={(e) => set("ni_number", e.target.value)} data-testid="hr-ni-input" /></Field>
          <Field label="Vergi kodu">
            <select className={inputCls} value={f.tax_code} onChange={(e) => set("tax_code", e.target.value)} data-testid="hr-taxcode-select">
              {TAX_CODES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </Field>
          <Field label="Sözleşme türü">
            <select className={inputCls} value={f.contract_type} onChange={(e) => set("contract_type", e.target.value)} data-testid="hr-contract-select">
              {CONTRACT_TYPES.map((c) => <option key={c.v} value={c.v}>{c.l}</option>)}
            </select>
          </Field>
          <Field label="İşe giriş tarihi"><input type="date" className={inputCls} value={f.start_date} onChange={(e) => set("start_date", e.target.value)} data-testid="hr-startdate-input" /></Field>
          <Field label="Öğrenci kredisi">
            <select className={inputCls} value={f.student_loan_plans[0] || ""} onChange={(e) => set("student_loan_plans", e.target.value ? [e.target.value] : [])}>
              <option value="">Yok</option>
              {SL_PLANS.map((p) => <option key={p.v} value={p.v}>{p.l}</option>)}
            </select>
          </Field>
          <Field label="Sort code"><input className={inputCls} placeholder="12-34-56" value={f.bank_sort_code} onChange={(e) => set("bank_sort_code", e.target.value)} /></Field>
          <Field label="Hesap no"><input className={inputCls} placeholder="12345678" value={f.bank_account_no} onChange={(e) => set("bank_account_no", e.target.value)} data-testid="hr-bank-input" /></Field>
          <Field label="Posta kodu"><input className={inputCls} value={f.postcode} onChange={(e) => set("postcode", e.target.value)} /></Field>
          <div className="col-span-2 md:col-span-3">
            <Field label="Adres"><input className={inputCls} value={f.address} onChange={(e) => set("address", e.target.value)} /></Field>
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-5">
          <button onClick={onClose} className="px-4 py-2 text-sm rounded-lg border border-stone-300 hover:bg-stone-50">İptal</button>
          <button onClick={save} disabled={saving} className="px-4 py-2 text-sm rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50" data-testid="hr-save-btn">
            {saving ? "Kaydediliyor..." : "Kaydet"}
          </button>
        </div>
      </div>
    </div>
  );
}

function OffboardDialog({ emp, onClose, onDone }) {
  const [leaverDate, setLeaverDate] = useState(new Date().toISOString().slice(0, 10));
  const [reason, setReason] = useState("");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setBusy(true);
    try {
      const { data } = await axios.post(`${API}/uk-payroll/employees/${emp.id}/offboard`, { leaver_date: leaverDate, reason }, cfg);
      setResult(data);
      toast.success("İşten çıkış kaydedildi");
    } catch (e) {
      toast.error(e.response?.data?.detail || "İşlem başarısız");
    }
    setBusy(false);
  };
  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" data-testid="offboard-dialog">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6">
        <h3 className="font-bold text-lg mb-1">İşten Çıkış — {emp.name}</h3>
        <p className="text-xs text-stone-500 mb-4">P45 düzenlenmeli ve son FPS'te leaver işaretlenmelidir.</p>
        {!result ? (
          <>
            <div className="space-y-3">
              <Field label="Ayrılış tarihi (leaver date)">
                <input type="date" className={inputCls} value={leaverDate} onChange={(e) => setLeaverDate(e.target.value)} data-testid="offboard-date-input" />
              </Field>
              <Field label="Ayrılış nedeni">
                <input className={inputCls} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="İstifa, sözleşme sonu..." />
              </Field>
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <button onClick={onClose} className="px-4 py-2 text-sm rounded-lg border border-stone-300">İptal</button>
              <button onClick={submit} disabled={busy} className="px-4 py-2 text-sm rounded-lg bg-red-600 text-white hover:bg-red-700 disabled:opacity-50" data-testid="offboard-confirm-btn">
                {busy ? "İşleniyor..." : "İşten Çıkar"}
              </button>
            </div>
          </>
        ) : (
          <div>
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm space-y-1" data-testid="offboard-finalpay">
              <div className="font-semibold text-amber-800 mb-2">Son Ödeme (Final Pay) Tahmini</div>
              <div className="flex justify-between"><span>Ödenmemiş vardiyalar</span><b>{gbp(result.final_pay.unpaid_shifts)}</b></div>
              <div className="flex justify-between"><span>Birikmiş tatil ({result.final_pay.holiday_hours_accrued} saat)</span><b>{gbp(result.final_pay.holiday_pay)}</b></div>
              <div className="flex justify-between border-t border-amber-200 pt-1 mt-1"><span>Toplam</span><b className="text-amber-900">{gbp(result.final_pay.total_estimate)}</b></div>
            </div>
            <p className="text-xs text-stone-500 mt-3">{result.note}</p>
            <div className="flex justify-end mt-4">
              <button onClick={onDone} className="px-4 py-2 text-sm rounded-lg bg-stone-900 text-white" data-testid="offboard-done-btn">Tamam</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export const UKPayrollPanel = ({ propertyId }) => {
  const pid = propertyId || "all";
  const [tab, setTab] = useState("employees");
  const [employees, setEmployees] = useState([]);
  const [rates, setRates] = useState(null);
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [preview, setPreview] = useState(null);
  const [runs, setRuns] = useState([]);
  const [slips, setSlips] = useState([]);
  const [activeRun, setActiveRun] = useState(null);
  const [editEmp, setEditEmp] = useState(null);
  const [offEmp, setOffEmp] = useState(null);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);

  const loadEmployees = useCallback(async () => {
    try {
      const [e, r] = await Promise.all([
        axios.get(`${API}/uk-payroll/employees/${pid}`, cfg),
        axios.get(`${API}/uk-payroll/rates`, cfg),
      ]);
      setEmployees(e.data);
      setRates(r.data);
    } catch { toast.error("Personel listesi yüklenemedi"); }
  }, [pid]);

  const loadPreview = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/uk-payroll/preview/${pid}?year=${year}&month=${month}`, cfg);
      setPreview(data);
    } catch { toast.error("Bordro önizlemesi yüklenemedi"); }
    setLoading(false);
  }, [pid, year, month]);

  const loadRuns = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/uk-payroll/runs/${pid}`, cfg);
      setRuns(data);
    } catch { /* ignore */ }
  }, [pid]);

  useEffect(() => { loadEmployees(); }, [loadEmployees]);
  useEffect(() => { if (tab === "payroll") loadPreview(); }, [tab, loadPreview]);
  useEffect(() => { if (tab === "history") loadRuns(); }, [tab, loadRuns]);

  const runPayroll = async (force = false) => {
    setRunning(true);
    try {
      const { data } = await axios.post(`${API}/uk-payroll/run/${pid}`, { year, month, force }, cfg);
      toast.success(`Bordro kaydedildi — ${data.payslips_created} payslip oluşturuldu`);
      loadRuns();
    } catch (e) {
      if (e.response?.status === 409) {
        if (window.confirm("Bu dönem zaten çalıştırılmış. Üzerine yazılsın mı?")) return runPayroll(true);
      } else toast.error(e.response?.data?.detail || "Bordro çalıştırılamadı");
    }
    setRunning(false);
  };

  const openRun = async (run) => {
    setActiveRun(run);
    try {
      const { data } = await axios.get(`${API}/uk-payroll/runs/${run.property_id}/${run.id}/payslips`, cfg);
      setSlips(data);
    } catch { toast.error("Payslip'ler yüklenemedi"); }
  };

  const downloadPdf = async (slip) => {
    try {
      const res = await axios.get(`${API}/uk-payroll/payslip/${slip.id}/pdf`, { ...cfg, responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `payslip_${slip.staff_name}_${slip.year}-${String(slip.month).padStart(2, "0")}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch { toast.error("PDF indirilemedi"); }
  };

  const emailSlip = async (slip) => {
    try {
      const { data } = await axios.post(`${API}/uk-payroll/payslip/${slip.id}/email`, {}, cfg);
      toast.success(data.status === "sent" ? "E-posta gönderildi" : "E-posta MOCK modda loglandı (Resend anahtarı yok)");
      if (activeRun) openRun(activeRun);
    } catch (e) { toast.error(e.response?.data?.detail || "Gönderilemedi"); }
  };

  const emailAll = async () => {
    if (!activeRun) return;
    try {
      const { data } = await axios.post(`${API}/uk-payroll/runs/${activeRun.id}/email-all`, {}, cfg);
      toast.success(`Gönderilen: ${data.sent} · Mock: ${data.mocked} · E-postasız: ${data.skipped_no_email}`);
      openRun(activeRun);
    } catch { toast.error("Toplu gönderim başarısız"); }
  };

  const reinstate = async (emp) => {
    await axios.post(`${API}/uk-payroll/employees/${emp.id}/reinstate`, {}, cfg);
    toast.success("Personel yeniden aktif edildi");
    loadEmployees();
  };

  const TabBtn = ({ id, icon: Icon, label, testid }) => (
    <button onClick={() => setTab(id)} data-testid={testid}
      className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-colors ${tab === id ? "bg-stone-900 text-white" : "bg-white text-stone-600 border border-stone-200 hover:bg-stone-50"}`}>
      <Icon size={16} /> {label}
    </button>
  );

  return (
    <div className="p-6 space-y-5" data-testid="uk-payroll-panel">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-stone-900 flex items-center gap-2">
            <PoundSterling className="text-emerald-600" size={26} /> İK & Bordro (UK)
          </h1>
          <p className="text-sm text-stone-500 mt-0.5">
            Vergi yılı {rates?.tax_year || "2026/27"} · NMW yaş bantları, PAYE, NI Class 1 otomatik hesap · Vardiyadan bordroya
          </p>
        </div>
        <div className="flex gap-2">
          <TabBtn id="employees" icon={Users} label="Personel & İK" testid="ukp-tab-employees" />
          <TabBtn id="payroll" icon={Calculator} label="Aylık Bordro" testid="ukp-tab-payroll" />
          <TabBtn id="history" icon={History} label="Bordro Geçmişi" testid="ukp-tab-history" />
        </div>
      </div>

      {rates && tab === "employees" && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[["NLW 21+", rates.nmw["21_plus"]], ["NMW 18-20", rates.nmw["18_20"]], ["NMW <18", rates.nmw.under_18], ["Çırak", rates.nmw.apprentice]].map(([l, v]) => (
            <div key={l} className="bg-white border border-stone-200 rounded-xl px-4 py-3">
              <div className="text-xs text-stone-500">{l}</div>
              <div className="text-lg font-bold text-stone-900">£{v}/saat</div>
            </div>
          ))}
        </div>
      )}

      {tab === "employees" && (
        <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="ukp-employees-table">
              <thead className="bg-stone-50 text-xs text-stone-500 uppercase">
                <tr>
                  {["Personel", "Rol", "Yaş", "Ücret", "NMW", "İK Dosyası", "Durum", ""].map((h) => (
                    <th key={h} className="text-left px-4 py-2.5 font-semibold">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-100">
                {employees.map((e) => (
                  <tr key={e.id} className={e.employment_status === "leaver" ? "opacity-50" : ""} data-testid={`ukp-emp-row-${e.id}`}>
                    <td className="px-4 py-2.5">
                      <div className="font-medium text-stone-900">{e.name}</div>
                      <div className="text-xs text-stone-400">{e.email || "e-posta yok"}</div>
                    </td>
                    <td className="px-4 py-2.5">{e.role}</td>
                    <td className="px-4 py-2.5">{e.age ?? <span className="text-amber-600 text-xs">DOB eksik</span>}</td>
                    <td className="px-4 py-2.5">£{e.pay_rate}/{e.pay_type === "hourly" ? "saat" : "gün"}</td>
                    <td className="px-4 py-2.5">
                      {e.nmw_compliant === false
                        ? <span className="inline-flex items-center gap-1 text-xs text-red-600 font-medium"><AlertTriangle size={13} /> £{e.nmw_rate} altında</span>
                        : <span className="inline-flex items-center gap-1 text-xs text-emerald-600"><ShieldCheck size={13} /> £{e.nmw_rate}</span>}
                    </td>
                    <td className="px-4 py-2.5">
                      {e.hr_complete
                        ? <span className="inline-flex items-center gap-1 text-xs text-emerald-600"><CheckCircle size={13} /> Tam</span>
                        : <span className="text-xs text-amber-600" title={e.hr_missing.join(", ")}>{e.hr_missing.length} eksik</span>}
                    </td>
                    <td className="px-4 py-2.5">
                      {e.employment_status === "leaver"
                        ? <span className="text-xs px-2 py-0.5 rounded-full bg-red-50 text-red-600">Ayrıldı · {e.leaver_date}</span>
                        : <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700">Aktif</span>}
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex gap-1.5 justify-end">
                        <button onClick={() => setEditEmp(e)} className="p-1.5 rounded-lg border border-stone-200 hover:bg-stone-50" title="İK kaydını düzenle" data-testid={`ukp-edit-${e.id}`}><Pencil size={14} /></button>
                        {e.employment_status === "leaver"
                          ? <button onClick={() => reinstate(e)} className="p-1.5 rounded-lg border border-stone-200 hover:bg-emerald-50 text-emerald-600" title="Geri al" data-testid={`ukp-reinstate-${e.id}`}><UserPlus size={14} /></button>
                          : <button onClick={() => setOffEmp(e)} className="p-1.5 rounded-lg border border-stone-200 hover:bg-red-50 text-red-500" title="İşten çıkar" data-testid={`ukp-offboard-${e.id}`}><UserMinus size={14} /></button>}
                      </div>
                    </td>
                  </tr>
                ))}
                {employees.length === 0 && (
                  <tr><td colSpan={8} className="px-4 py-8 text-center text-stone-400">Personel yok — Shift Scheduler'dan personel ekleyin.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "payroll" && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <select className={inputCls + " !w-auto"} value={month} onChange={(e) => setMonth(+e.target.value)} data-testid="ukp-month-select">
              {MONTHS_TR.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
            </select>
            <select className={inputCls + " !w-auto"} value={year} onChange={(e) => setYear(+e.target.value)} data-testid="ukp-year-select">
              {[year - 1, year, year + 1].filter((v, i, a) => a.indexOf(v) === i).map((y) => <option key={y} value={y}>{y}</option>)}
            </select>
            <button onClick={loadPreview} className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg border border-stone-300 hover:bg-stone-50" data-testid="ukp-refresh-btn">
              <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Yenile
            </button>
            <div className="flex-1" />
            <button onClick={() => runPayroll(false)} disabled={running || !preview?.rows?.length}
              className="flex items-center gap-2 px-4 py-2 text-sm rounded-xl bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50 font-medium" data-testid="ukp-run-btn">
              <Calculator size={16} /> {running ? "Çalıştırılıyor..." : "Bordroyu Çalıştır & Kaydet"}
            </button>
          </div>

          {preview?.warnings?.length > 0 && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4" data-testid="ukp-warnings">
              <div className="flex items-center gap-2 font-semibold text-amber-800 text-sm mb-2"><AlertTriangle size={16} /> Uyum Uyarıları ({preview.warnings.length})</div>
              <ul className="text-xs text-amber-700 space-y-1">
                {preview.warnings.map((w, i) => <li key={i}><b>{w.staff_name}:</b> {w.issues.join(" · ")}</li>)}
              </ul>
            </div>
          )}

          <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="ukp-payroll-table">
                <thead className="bg-stone-900 text-white text-xs uppercase">
                  <tr>
                    {["Personel", "Saat", "Vardiya Kazancı", "NMW Tamamlama", "Brüt", "PAYE", "NI (Çalışan)", "Öğr. Kredisi", "Net", "İşveren NI"].map((h) => (
                      <th key={h} className="text-left px-3 py-2.5 font-semibold whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100">
                  {(preview?.rows || []).map((r) => (
                    <tr key={r.staff_id} data-testid={`ukp-pay-row-${r.staff_id}`}>
                      <td className="px-3 py-2.5">
                        <div className="font-medium">{r.staff_name}</div>
                        <div className="text-xs text-stone-400">{r.tax_code} · {r.ni_number || "NI yok"}</div>
                      </td>
                      <td className="px-3 py-2.5">{r.hours}</td>
                      <td className="px-3 py-2.5">{gbp(r.base_earned)}</td>
                      <td className="px-3 py-2.5">{r.nmw_topup ? <span className="text-amber-600 font-medium">{gbp(r.nmw_topup)}</span> : "—"}</td>
                      <td className="px-3 py-2.5 font-semibold">{gbp(r.gross)}</td>
                      <td className="px-3 py-2.5 text-red-600">{gbp(r.paye)}</td>
                      <td className="px-3 py-2.5 text-red-600">{gbp(r.ni_employee)}</td>
                      <td className="px-3 py-2.5">{r.student_loan ? gbp(r.student_loan) : "—"}</td>
                      <td className="px-3 py-2.5 font-bold text-emerald-700">{gbp(r.net)}</td>
                      <td className="px-3 py-2.5 text-stone-500">{gbp(r.ni_employer)}</td>
                    </tr>
                  ))}
                  {!loading && !preview?.rows?.length && (
                    <tr><td colSpan={10} className="px-4 py-8 text-center text-stone-400">Bu dönemde onaylanmış/tamamlanmış vardiya yok.</td></tr>
                  )}
                </tbody>
                {preview?.rows?.length > 0 && (
                  <tfoot className="bg-stone-50 font-semibold">
                    <tr data-testid="ukp-totals-row">
                      <td className="px-3 py-2.5">TOPLAM ({preview.staff_count} personel)</td>
                      <td className="px-3 py-2.5">{preview.totals.hours}</td>
                      <td className="px-3 py-2.5" />
                      <td className="px-3 py-2.5">{preview.totals.nmw_topup ? gbp(preview.totals.nmw_topup) : "—"}</td>
                      <td className="px-3 py-2.5">{gbp(preview.totals.gross)}</td>
                      <td className="px-3 py-2.5 text-red-600">{gbp(preview.totals.paye)}</td>
                      <td className="px-3 py-2.5 text-red-600">{gbp(preview.totals.ni_employee)}</td>
                      <td className="px-3 py-2.5">{gbp(preview.totals.student_loan)}</td>
                      <td className="px-3 py-2.5 text-emerald-700">{gbp(preview.totals.net)}</td>
                      <td className="px-3 py-2.5">{gbp(preview.totals.ni_employer)}</td>
                    </tr>
                  </tfoot>
                )}
              </table>
            </div>
          </div>
          {preview?.totals && preview.rows.length > 0 && (
            <div className="text-sm text-stone-500">
              Toplam işveren maliyeti (brüt + işveren NI): <b className="text-stone-900">{gbp(preview.totals.employer_cost)}</b>
            </div>
          )}
        </div>
      )}

      {tab === "history" && (
        <div className="grid md:grid-cols-3 gap-4">
          <div className="space-y-2">
            {runs.map((r) => (
              <button key={r.id} onClick={() => openRun(r)} data-testid={`ukp-run-${r.id}`}
                className={`w-full text-left bg-white border rounded-xl px-4 py-3 hover:border-emerald-400 transition-colors ${activeRun?.id === r.id ? "border-emerald-500 ring-1 ring-emerald-200" : "border-stone-200"}`}>
                <div className="font-semibold text-sm">{MONTHS_TR[r.month - 1]} {r.year}</div>
                <div className="text-xs text-stone-500">{r.staff_count} personel · Net {gbp(r.totals?.net)} · {new Date(r.created_at).toLocaleDateString("tr-TR")}</div>
              </button>
            ))}
            {runs.length === 0 && <div className="text-sm text-stone-400 p-4">Henüz bordro çalıştırılmamış.</div>}
          </div>
          <div className="md:col-span-2">
            {activeRun ? (
              <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden">
                <div className="flex items-center justify-between px-4 py-3 border-b border-stone-100">
                  <div className="font-semibold text-sm">{MONTHS_TR[activeRun.month - 1]} {activeRun.year} — Payslip'ler</div>
                  <button onClick={emailAll} className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-stone-900 text-white hover:bg-stone-700" data-testid="ukp-email-all-btn">
                    <Mail size={13} /> Tümüne E-posta
                  </button>
                </div>
                <table className="w-full text-sm" data-testid="ukp-slips-table">
                  <tbody className="divide-y divide-stone-100">
                    {slips.map((s) => (
                      <tr key={s.id}>
                        <td className="px-4 py-2.5">
                          <div className="font-medium">{s.staff_name}</div>
                          <div className="text-xs text-stone-400">Brüt {gbp(s.gross)} · Net <b className="text-emerald-700">{gbp(s.net)}</b></div>
                        </td>
                        <td className="px-4 py-2.5 text-xs text-stone-500">
                          {s.email_status === "sent" && <span className="text-emerald-600">E-posta gönderildi</span>}
                          {s.email_status === "mocked" && <span className="text-amber-600">Mock loglandı</span>}
                        </td>
                        <td className="px-4 py-2.5">
                          <div className="flex gap-1.5 justify-end">
                            <button onClick={() => downloadPdf(s)} className="p-1.5 rounded-lg border border-stone-200 hover:bg-stone-50" title="PDF indir" data-testid={`ukp-pdf-${s.id}`}><Download size={14} /></button>
                            <button onClick={() => emailSlip(s)} className="p-1.5 rounded-lg border border-stone-200 hover:bg-stone-50" title="E-posta gönder" data-testid={`ukp-email-${s.id}`}><Mail size={14} /></button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-sm text-stone-400 p-6 border border-dashed border-stone-200 rounded-2xl">Soldan bir bordro dönemi seçin.</div>
            )}
          </div>
        </div>
      )}

      {editEmp && <HrEditDialog emp={editEmp} onClose={() => setEditEmp(null)} onSaved={() => { setEditEmp(null); loadEmployees(); }} />}
      {offEmp && <OffboardDialog emp={offEmp} onClose={() => setOffEmp(null)} onDone={() => { setOffEmp(null); loadEmployees(); }} />}
    </div>
  );
};

export default UKPayrollPanel;
