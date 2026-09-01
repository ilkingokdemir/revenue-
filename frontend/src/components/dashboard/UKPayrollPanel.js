import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Users, Calculator, History, RefreshCw, Download, Mail, AlertTriangle,
  CheckCircle, XCircle, UserMinus, UserPlus, Pencil, ShieldCheck, PoundSterling,
  UserCircle, FileText, Bot, Paperclip, GitCompareArrows,
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
    pension_status: emp.pension_status || "auto",
    annual_leave_days: emp.annual_leave_days || 28,
    address: emp.address || "", postcode: emp.postcode || "",
  });
  const [saving, setSaving] = useState(false);
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));
  const save = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/uk-payroll/employees/${emp.id}/hr`, { ...f, pay_rate: parseFloat(f.pay_rate) || 0, annual_leave_days: parseInt(f.annual_leave_days) || 28 }, cfg);
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
          <Field label="Emeklilik (auto-enrolment)">
            <select className={inputCls} value={f.pension_status} onChange={(e) => set("pension_status", e.target.value)} data-testid="hr-pension-select">
              <option value="auto">Otomatik (uygunsa kayıt)</option>
              <option value="opted_in">Katıldı (opt-in)</option>
              <option value="opted_out">Vazgeçti (opt-out)</option>
            </select>
          </Field>
          <Field label="Yıllık izin hakkı (gün)">
            <input type="number" min="0" max="60" className={inputCls} value={f.annual_leave_days} onChange={(e) => set("annual_leave_days", e.target.value)} data-testid="hr-leave-days-input" />
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

const DOC_TYPE_TR = { contract: "Sözleşme", passport: "Pasaport/Kimlik", visa: "Vize/Çalışma izni", address_proof: "Adres belgesi", certificate: "Sertifika", other: "Diğer" };

function DocsDialog({ emp, onClose }) {
  const [docs, setDocs] = useState([]);
  const [docType, setDocType] = useState("contract");
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/uk-payroll/employees/${emp.id}/documents`, cfg);
      setDocs(data);
    } catch { toast.error("Belgeler yüklenemedi"); }
  }, [emp.id]);
  useEffect(() => { load(); }, [load]);
  const upload = async (file) => {
    if (!file) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("doc_type", docType);
      fd.append("file", file);
      await axios.post(`${API}/uk-payroll/employees/${emp.id}/documents`, fd, cfg);
      toast.success("Belge yüklendi");
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Yükleme başarısız"); }
    setBusy(false);
  };
  const download = async (doc) => {
    try {
      const res = await axios.get(`${API}/uk-payroll/documents/${doc.id}/download`, { ...cfg, responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url; a.download = doc.orig_name || `belge.${doc.ext}`; a.click();
      URL.revokeObjectURL(url);
    } catch { toast.error("İndirilemedi"); }
  };
  const remove = async (doc) => {
    try {
      await axios.delete(`${API}/uk-payroll/documents/${doc.id}`, cfg);
      toast.success("Belge silindi");
      load();
    } catch { toast.error("Silinemedi"); }
  };
  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" data-testid="docs-dialog">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg max-h-[85vh] overflow-y-auto p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-bold text-lg">İK Belgeleri — {emp.name}</h3>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-700" data-testid="docs-close"><XCircle size={22} /></button>
        </div>
        <div className="flex gap-2 items-end mb-4">
          <Field label="Belge türü">
            <select className={inputCls} value={docType} onChange={(e) => setDocType(e.target.value)} data-testid="docs-type-select">
              {Object.entries(DOC_TYPE_TR).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </Field>
          <label className={`px-4 py-2 text-sm rounded-lg bg-stone-900 text-white hover:bg-stone-700 cursor-pointer ${busy ? "opacity-50 pointer-events-none" : ""}`} data-testid="docs-upload-btn">
            {busy ? "Yükleniyor..." : "Dosya Yükle"}
            <input type="file" className="hidden" accept=".pdf,.jpg,.jpeg,.png,.webp,.heic,.docx" onChange={(e) => upload(e.target.files?.[0])} data-testid="docs-file-input" />
          </label>
        </div>
        <div className="space-y-2" data-testid="docs-list">
          {docs.map((d) => (
            <div key={d.id} className="flex items-center justify-between gap-2 border border-stone-100 rounded-xl px-3 py-2 text-sm">
              <div>
                <div className="font-medium">{DOC_TYPE_TR[d.doc_type] || d.doc_type} · {d.orig_name}</div>
                <div className="text-xs text-stone-400">{(d.size / 1024).toFixed(0)} KB · {new Date(d.uploaded_at).toLocaleDateString("tr-TR")} · {d.uploaded_by}</div>
              </div>
              <div className="flex gap-1.5">
                <button onClick={() => download(d)} className="p-1.5 rounded-lg border border-stone-200 hover:bg-stone-50" title="İndir" data-testid={`docs-dl-${d.id}`}><Download size={14} /></button>
                <button onClick={() => remove(d)} className="p-1.5 rounded-lg border border-stone-200 hover:bg-red-50 text-red-500" title="Sil" data-testid={`docs-del-${d.id}`}><XCircle size={14} /></button>
              </div>
            </div>
          ))}
          {docs.length === 0 && <div className="text-sm text-stone-400 py-3">Henüz belge yüklenmemiş.</div>}
        </div>
      </div>
    </div>
  );
}

export const UKPayrollPanel = ({ propertyId, user }) => {
  const pid = propertyId || "all";
  const isManager = ["admin", "manager"].includes(user?.role);
  const [tab, setTab] = useState(isManager ? "employees" : "portal");
  const [employees, setEmployees] = useState([]);
  const [rates, setRates] = useState(null);
  const [portal, setPortal] = useState(null);
  const [mySlips, setMySlips] = useState([]);
  const [myShifts, setMyShifts] = useState([]);
  const [myLeaves, setMyLeaves] = useState([]);
  const [pendingLeaves, setPendingLeaves] = useState([]);
  const [leaveForm, setLeaveForm] = useState({ leave_type: "annual", start_date: "", end_date: "", reason: "" });
  const [leaveOpen, setLeaveOpen] = useState(false);
  const [leaveBalance, setLeaveBalance] = useState(null);
  const [docsEmp, setDocsEmp] = useState(null);
  const [cmpA, setCmpA] = useState("");
  const [cmpB, setCmpB] = useState("");
  const [cmpResult, setCmpResult] = useState(null);
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

  const loadPortal = useCallback(async () => {
    try {
      const [s, p, sh, lv] = await Promise.all([
        axios.get(`${API}/uk-payroll/me/summary`, cfg),
        axios.get(`${API}/uk-payroll/me/payslips`, cfg),
        axios.get(`${API}/uk-payroll/me/shifts?weeks=8`, cfg),
        axios.get(`${API}/uk-payroll/me/leaves`, cfg),
      ]);
      setPortal(s.data);
      setMySlips(p.data);
      setMyShifts(sh.data);
      setMyLeaves(lv.data);
      if (s.data?.linked) {
        try {
          const bal = await axios.get(`${API}/uk-payroll/me/leave-balance`, cfg);
          setLeaveBalance(bal.data);
        } catch { /* ignore */ }
      }
    } catch { toast.error("Portal verileri yüklenemedi"); }
  }, []);

  const loadPendingLeaves = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/shifts/leaves/${pid}?status=pending`, cfg);
      setPendingLeaves(data);
    } catch { /* ignore */ }
  }, [pid]);

  useEffect(() => { if (isManager) { loadEmployees(); loadPendingLeaves(); } }, [isManager, loadEmployees, loadPendingLeaves]);
  useEffect(() => { if (tab === "payroll") loadPreview(); }, [tab, loadPreview]);
  useEffect(() => { if (tab === "history") loadRuns(); }, [tab, loadRuns]);
  useEffect(() => { if (tab === "portal") loadPortal(); }, [tab, loadPortal]);

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

  const blobDownload = (data, filename) => {
    const url = URL.createObjectURL(data);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const downloadP60 = async (emp) => {
    try {
      const path = emp ? `${API}/uk-payroll/employees/${emp.id}/p60` : `${API}/uk-payroll/me/p60`;
      const res = await axios.get(path, { ...cfg, responseType: "blob" });
      const who = (emp?.name || "benim").replace(/\s+/g, "_");
      blobDownload(res.data, `P60_${who}_${new Date().getFullYear()}.pdf`);
      toast.success("P60 belgesi indirildi");
    } catch { toast.error("P60 oluşturulamadı"); }
  };

  const downloadBacs = async (run) => {
    try {
      const res = await axios.get(`${API}/uk-payroll/runs/${run.id}/bacs`, { ...cfg, responseType: "blob" });
      blobDownload(res.data, `BACS_${run.year}-${String(run.month).padStart(2, "0")}.txt`);
      const inc = res.headers["x-bacs-included"], skip = res.headers["x-bacs-skipped"];
      toast.success(`BACS dosyası indirildi — ${inc} ödeme satırı${skip > 0 ? `, ${skip} personel banka bilgisi eksik` : ""}`);
    } catch (e) {
      if (e.response?.status === 400) toast.error("Hiçbir personelde geçerli banka bilgisi yok (sort code + hesap no gerekli)");
      else toast.error("BACS dosyası oluşturulamadı");
    }
  };

  const decideLeave = async (leaveId, status) => {
    try {
      await axios.put(`${API}/shifts/leaves/${leaveId}`, { status }, cfg);
      toast.success(status === "approved" ? "İzin onaylandı" : "İzin reddedildi");
      loadPendingLeaves();
    } catch { toast.error("İşlem başarısız"); }
  };

  const runCompare = async () => {
    if (!cmpA || !cmpB) { toast.error("İki dönem seçin"); return; }
    const [y1, m1] = cmpA.split("-").map(Number);
    const [y2, m2] = cmpB.split("-").map(Number);
    try {
      const { data } = await axios.get(`${API}/uk-payroll/compare/${pid}?y1=${y1}&m1=${m1}&y2=${y2}&m2=${m2}`, cfg);
      setCmpResult(data);
    } catch (e) { toast.error(e.response?.data?.detail || "Karşılaştırma yapılamadı"); }
  };

  const submitLeave = async () => {
    if (!leaveForm.start_date || !leaveForm.end_date) { toast.error("Başlangıç ve bitiş tarihi zorunlu"); return; }
    if (leaveForm.leave_type === "annual" && leaveBalance) {
      const days = Math.round((new Date(leaveForm.end_date) - new Date(leaveForm.start_date)) / 86400000) + 1;
      if (days > leaveBalance.remaining) {
        toast.error(`Yetersiz izin bakiyesi: kalan ${leaveBalance.remaining} gün, talep ${days} gün`);
        return;
      }
    }
    try {
      await axios.post(`${API}/uk-payroll/me/leave-request`, leaveForm, cfg);
      toast.success("İzin talebiniz gönderildi — yönetici onayı bekleniyor");
      setLeaveForm({ leave_type: "annual", start_date: "", end_date: "", reason: "" });
      setLeaveOpen(false);
      loadPortal();
    } catch (e) { toast.error(e.response?.data?.detail || "Talep gönderilemedi"); }
  };

  const downloadP45 = async (emp) => {
    try {
      const res = await axios.get(`${API}/uk-payroll/employees/${emp.id}/p45`, { ...cfg, responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `P45_${emp.name}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("P45 belgesi indirildi");
    } catch { toast.error("P45 oluşturulamadı"); }
  };

  const runRobot = async () => {
    try {
      const { data } = await axios.post(`${API}/uk-payroll/robot/run`, { property_id: pid, force: true }, cfg);
      if (data.skipped === "already_run") toast.info("Bu ayın bordrosu zaten çalıştırılmış");
      else if (data.skipped === "no_shifts") toast.info("Bu ay onaylanmış vardiya yok");
      else toast.success(`Robot bordroyu çalıştırdı — ${data.payslips_created} payslip, ${data.emails?.mocked || 0} özet e-postası (mock)`);
      loadRuns();
    } catch { toast.error("Robot çalıştırılamadı"); }
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
        <div className="flex flex-wrap gap-2">
          {isManager && <TabBtn id="employees" icon={Users} label="Personel & İK" testid="ukp-tab-employees" />}
          {isManager && <TabBtn id="payroll" icon={Calculator} label="Aylık Bordro" testid="ukp-tab-payroll" />}
          {isManager && <TabBtn id="history" icon={History} label="Bordro Geçmişi" testid="ukp-tab-history" />}
          <TabBtn id="portal" icon={UserCircle} label="Portalım" testid="ukp-tab-portal" />
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
        <div className="space-y-4">
          {pendingLeaves.length > 0 && (
            <div className="bg-white border border-indigo-200 rounded-2xl p-4" data-testid="ukp-pending-leaves">
              <div className="font-semibold text-sm text-indigo-800 mb-3">Bekleyen İzin Talepleri ({pendingLeaves.length})</div>
              <div className="space-y-2">
                {pendingLeaves.map((lv) => (
                  <div key={lv.id} className="flex flex-wrap items-center justify-between gap-2 bg-indigo-50/50 rounded-xl px-3 py-2 text-sm">
                    <div>
                      <b>{lv.staff_name}</b> · {lv.leave_type === "annual" ? "Yıllık izin" : lv.leave_type === "sick" ? "Hastalık" : lv.leave_type} · {lv.start_date} → {lv.end_date} ({lv.days} gün)
                      {lv.reason && <span className="text-stone-500"> — {lv.reason}</span>}
                    </div>
                    <div className="flex gap-1.5">
                      <button onClick={() => decideLeave(lv.id, "approved")} className="px-3 py-1 text-xs rounded-lg bg-emerald-600 text-white hover:bg-emerald-700" data-testid={`ukp-leave-approve-${lv.id}`}>Onayla</button>
                      <button onClick={() => decideLeave(lv.id, "rejected")} className="px-3 py-1 text-xs rounded-lg bg-red-100 text-red-600 hover:bg-red-200" data-testid={`ukp-leave-reject-${lv.id}`}>Reddet</button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
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
                        <button onClick={() => downloadP60(e)} className="p-1.5 rounded-lg border border-stone-200 hover:bg-blue-50 text-blue-600" title="P60 indir (vergi yılı özeti)" data-testid={`ukp-p60-${e.id}`}><FileText size={14} /></button>
                        <button onClick={() => setDocsEmp(e)} className="p-1.5 rounded-lg border border-stone-200 hover:bg-stone-50" title="İK belgeleri" data-testid={`ukp-docs-${e.id}`}><Paperclip size={14} /></button>
                        {e.employment_status === "leaver" ? (
                          <>
                            <button onClick={() => downloadP45(e)} className="p-1.5 rounded-lg border border-stone-200 hover:bg-amber-50 text-amber-600" title="P45 indir" data-testid={`ukp-p45-${e.id}`}><FileText size={14} /></button>
                            <button onClick={() => reinstate(e)} className="p-1.5 rounded-lg border border-stone-200 hover:bg-emerald-50 text-emerald-600" title="Geri al" data-testid={`ukp-reinstate-${e.id}`}><UserPlus size={14} /></button>
                          </>
                        ) : (
                          <button onClick={() => setOffEmp(e)} className="p-1.5 rounded-lg border border-stone-200 hover:bg-red-50 text-red-500" title="İşten çıkar" data-testid={`ukp-offboard-${e.id}`}><UserMinus size={14} /></button>
                        )}
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
                    {["Personel", "Saat", "Vardiya Kazancı", "NMW Tamamlama", "Brüt", "PAYE", "NI (Çalışan)", "Öğr. Kredisi", "Emeklilik", "Net", "İşveren NI"].map((h) => (
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
                      <td className="px-3 py-2.5">{r.pension_ee ? <span className="text-indigo-600">{gbp(r.pension_ee)}</span> : "—"}</td>
                      <td className="px-3 py-2.5 font-bold text-emerald-700">{gbp(r.net)}</td>
                      <td className="px-3 py-2.5 text-stone-500">{gbp(r.ni_employer)}</td>
                    </tr>
                  ))}
                  {!loading && !preview?.rows?.length && (
                    <tr><td colSpan={11} className="px-4 py-8 text-center text-stone-400">Bu dönemde onaylanmış/tamamlanmış vardiya yok.</td></tr>
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
                      <td className="px-3 py-2.5 text-indigo-600">{preview.totals.pension_ee ? gbp(preview.totals.pension_ee) : "—"}</td>
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
              Toplam işveren maliyeti (brüt + işveren NI + işveren emeklilik %3): <b className="text-stone-900">{gbp(preview.totals.employer_cost)}</b>
              {preview.totals.pension_er > 0 && <span className="ml-3">İşveren emeklilik katkısı: <b>{gbp(preview.totals.pension_er)}</b></span>}
            </div>
          )}
        </div>
      )}

      {tab === "history" && (
        <div className="space-y-4">
          <div className="bg-stone-900 text-white rounded-2xl px-5 py-4 flex flex-wrap items-center justify-between gap-3" data-testid="ukp-robot-card">
            <div className="flex items-center gap-3">
              <Bot size={22} className="text-emerald-400" />
              <div>
                <div className="font-semibold text-sm">Bordro Robotu</div>
                <div className="text-xs text-stone-400">Her ayın son günü 18:00'de bordroyu otomatik çalıştırır ve yöneticilere özet e-postası gönderir (Otomasyon Merkezi'nden yönetilir).</div>
              </div>
            </div>
            <button onClick={runRobot} className="px-4 py-2 text-sm rounded-xl bg-emerald-600 hover:bg-emerald-500 font-medium" data-testid="ukp-robot-run-btn">
              Şimdi Çalıştır
            </button>
          </div>
          <div className="bg-white border border-stone-200 rounded-2xl p-4" data-testid="ukp-compare-card">
            <div className="flex flex-wrap items-end gap-3">
              <div className="flex items-center gap-2 font-semibold text-sm mr-2"><GitCompareArrows size={16} className="text-violet-600" /> Bordro Karşılaştırma</div>
              <Field label="Dönem A">
                <select className={inputCls + " !w-auto"} value={cmpA} onChange={(e) => setCmpA(e.target.value)} data-testid="ukp-cmp-a">
                  <option value="">Seçin</option>
                  {runs.map((r) => <option key={r.id} value={`${r.year}-${r.month}`}>{MONTHS_TR[r.month - 1]} {r.year}</option>)}
                </select>
              </Field>
              <Field label="Dönem B">
                <select className={inputCls + " !w-auto"} value={cmpB} onChange={(e) => setCmpB(e.target.value)} data-testid="ukp-cmp-b">
                  <option value="">Seçin</option>
                  {runs.map((r) => <option key={r.id} value={`${r.year}-${r.month}`}>{MONTHS_TR[r.month - 1]} {r.year}</option>)}
                </select>
              </Field>
              <button onClick={runCompare} className="px-4 py-2 text-sm rounded-lg bg-violet-600 text-white hover:bg-violet-700" data-testid="ukp-cmp-btn">Karşılaştır</button>
            </div>
            {cmpResult && (
              <div className="mt-4 grid md:grid-cols-2 gap-4" data-testid="ukp-cmp-result">
                <table className="w-full text-sm">
                  <thead className="text-xs text-stone-500 uppercase">
                    <tr><th className="text-left py-1.5">Metrik</th><th className="text-right">A</th><th className="text-right">B</th><th className="text-right">Fark</th></tr>
                  </thead>
                  <tbody className="divide-y divide-stone-100">
                    {[["hours", "Saat"], ["gross", "Brüt"], ["paye", "PAYE"], ["ni_employee", "NI"], ["pension_ee", "Emeklilik"], ["net", "Net"], ["employer_cost", "İşveren maliyeti"]].map(([k, l]) => {
                      const t = cmpResult.totals[k];
                      return (
                        <tr key={k}>
                          <td className="py-1.5 font-medium">{l}</td>
                          <td className="text-right">{k === "hours" ? t.a : gbp(t.a)}</td>
                          <td className="text-right">{k === "hours" ? t.b : gbp(t.b)}</td>
                          <td className={`text-right font-semibold ${t.delta > 0 ? "text-emerald-600" : t.delta < 0 ? "text-red-600" : "text-stone-400"}`}>
                            {t.delta > 0 ? "▲" : t.delta < 0 ? "▼" : ""} {k === "hours" ? Math.abs(t.delta) : gbp(Math.abs(t.delta))}{t.pct !== null ? ` (%${Math.abs(t.pct)})` : ""}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                <div className="space-y-1.5 max-h-64 overflow-y-auto">
                  <div className="text-xs text-stone-500 uppercase font-semibold">Personel bazında net fark</div>
                  {cmpResult.rows.map((r) => (
                    <div key={r.staff_id} className="flex items-center justify-between text-sm border border-stone-100 rounded-lg px-3 py-1.5">
                      <div>{r.staff_name} <span className="text-xs text-stone-400">({r.status})</span></div>
                      <div className={`font-semibold ${r.delta > 0 ? "text-emerald-600" : r.delta < 0 ? "text-red-600" : "text-stone-400"}`}>
                        {r.delta > 0 ? "▲" : r.delta < 0 ? "▼" : "—"} {gbp(Math.abs(r.delta))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
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
                  <div className="flex gap-1.5">
                    <button onClick={() => downloadBacs(activeRun)} className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-stone-300 hover:bg-stone-50" data-testid="ukp-bacs-btn">
                      <Download size={13} /> BACS Dosyası
                    </button>
                    <button onClick={emailAll} className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-stone-900 text-white hover:bg-stone-700" data-testid="ukp-email-all-btn">
                      <Mail size={13} /> Tümüne E-posta
                    </button>
                  </div>
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
        </div>
      )}

      {tab === "portal" && (
        <div className="space-y-4" data-testid="ukp-portal">
          {portal && !portal.linked ? (
            <div className="bg-amber-50 border border-amber-200 rounded-2xl p-6 text-sm text-amber-800" data-testid="ukp-portal-unlinked">
              {portal.message}
            </div>
          ) : portal ? (
            <>
              <div className="grid md:grid-cols-2 gap-4">
                <div className="bg-white border border-stone-200 rounded-2xl p-5" data-testid="ukp-portal-summary">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="text-xs text-stone-500 uppercase font-semibold mb-2">Kayıt Bilgilerim</div>
                      <div className="font-bold text-lg text-stone-900">{portal.staff?.name}</div>
                    </div>
                    <button onClick={() => downloadP60(null)} className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-blue-200 text-blue-600 hover:bg-blue-50" data-testid="ukp-my-p60-btn">
                      <FileText size={13} /> P60 İndir
                    </button>
                  </div>
                  <div className="text-sm text-stone-500 mt-1">
                    {portal.staff?.role} · £{portal.staff?.pay_rate}/{portal.staff?.pay_type === "hourly" ? "saat" : "gün"} · Vergi kodu {portal.staff?.tax_code || "1257L"}
                  </div>
                  <div className="text-xs text-stone-400 mt-1">NI: {portal.staff?.ni_number || "—"} · İşe giriş: {portal.staff?.start_date || "—"}</div>
                </div>
                <div className="bg-stone-900 text-white rounded-2xl p-5" data-testid="ukp-portal-ytd">
                  <div className="text-xs text-stone-400 uppercase font-semibold mb-2">Vergi Yılı Toplamlarım ({portal.tax_year})</div>
                  <div className="grid grid-cols-4 gap-3 text-center">
                    {[["Brüt", portal.ytd?.gross], ["PAYE", portal.ytd?.paye], ["NI", portal.ytd?.ni], ["Net", portal.ytd?.net]].map(([l, v]) => (
                      <div key={l}><div className="text-xs text-stone-400">{l}</div><div className="font-bold text-sm">{gbp(v)}</div></div>
                    ))}
                  </div>
                </div>
              </div>
              <div className="grid md:grid-cols-2 gap-4">
                <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden">
                  <div className="px-4 py-3 border-b border-stone-100 font-semibold text-sm">Bordrolarım</div>
                  <table className="w-full text-sm" data-testid="ukp-my-payslips">
                    <tbody className="divide-y divide-stone-100">
                      {mySlips.map((s) => (
                        <tr key={s.id}>
                          <td className="px-4 py-2.5">
                            <div className="font-medium">{MONTHS_TR[s.month - 1]} {s.year}</div>
                            <div className="text-xs text-stone-400">{s.hours} saat · Brüt {gbp(s.gross)}</div>
                          </td>
                          <td className="px-4 py-2.5 font-bold text-emerald-700">{gbp(s.net)}</td>
                          <td className="px-4 py-2.5 text-right">
                            <button onClick={() => downloadPdf({ ...s, staff_name: portal.staff?.name })} className="p-1.5 rounded-lg border border-stone-200 hover:bg-stone-50" title="PDF indir" data-testid={`ukp-my-pdf-${s.id}`}><Download size={14} /></button>
                          </td>
                        </tr>
                      ))}
                      {mySlips.length === 0 && <tr><td className="px-4 py-6 text-center text-stone-400 text-sm">Henüz bordronuz oluşturulmamış.</td></tr>}
                    </tbody>
                  </table>
                </div>
                <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden">
                  <div className="px-4 py-3 border-b border-stone-100 font-semibold text-sm">Vardiyalarım (son 8 hafta)</div>
                  <div className="max-h-96 overflow-y-auto">
                    <table className="w-full text-sm" data-testid="ukp-my-shifts">
                      <tbody className="divide-y divide-stone-100">
                        {myShifts.map((s, i) => (
                          <tr key={i}>
                            <td className="px-4 py-2">{s.date}</td>
                            <td className="px-4 py-2 text-stone-500">{s.start_time}–{s.end_time}</td>
                            <td className="px-4 py-2">{s.hours_worked} saat</td>
                            <td className="px-4 py-2">
                              <span className={`text-xs px-2 py-0.5 rounded-full ${["completed", "approved"].includes(s.status) ? "bg-emerald-50 text-emerald-700" : "bg-stone-100 text-stone-500"}`}>{s.status}</span>
                            </td>
                          </tr>
                        ))}
                        {myShifts.length === 0 && <tr><td className="px-4 py-6 text-center text-stone-400 text-sm">Son 8 haftada vardiya kaydınız yok.</td></tr>}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
              <div className="bg-white border border-stone-200 rounded-2xl p-5" data-testid="ukp-my-leaves">
                <div className="flex items-center justify-between mb-3">
                  <div className="font-semibold text-sm">İzin Taleplerim</div>
                  <div className="flex items-center gap-3">
                    {leaveBalance && (
                      <div className="text-xs bg-indigo-50 border border-indigo-100 rounded-lg px-3 py-1.5" data-testid="ukp-leave-balance">
                        <b className="text-indigo-700">{leaveBalance.remaining} gün</b> kalan yıllık izin
                        <span className="text-stone-500"> · hak {leaveBalance.entitled} · kullanılan {leaveBalance.used} · bekleyen {leaveBalance.pending}</span>
                      </div>
                    )}
                    <button onClick={() => setLeaveOpen(!leaveOpen)} className="text-xs px-3 py-1.5 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700" data-testid="ukp-leave-request-btn">
                      {leaveOpen ? "Vazgeç" : "+ İzin Talep Et"}
                    </button>
                  </div>
                </div>
                {leaveOpen && (
                  <div className="bg-indigo-50/50 border border-indigo-100 rounded-xl p-4 mb-4 grid grid-cols-2 md:grid-cols-5 gap-3 items-end" data-testid="ukp-leave-form">
                    <Field label="İzin türü">
                      <select className={inputCls} value={leaveForm.leave_type} onChange={(e) => setLeaveForm({ ...leaveForm, leave_type: e.target.value })} data-testid="ukp-leave-type">
                        <option value="annual">Yıllık izin</option>
                        <option value="sick">Hastalık</option>
                        <option value="unpaid">Ücretsiz izin</option>
                        <option value="toil">TOIL (fazla mesai)</option>
                      </select>
                    </Field>
                    <Field label="Başlangıç"><input type="date" className={inputCls} value={leaveForm.start_date} onChange={(e) => setLeaveForm({ ...leaveForm, start_date: e.target.value })} data-testid="ukp-leave-start" /></Field>
                    <Field label="Bitiş"><input type="date" className={inputCls} value={leaveForm.end_date} onChange={(e) => setLeaveForm({ ...leaveForm, end_date: e.target.value })} data-testid="ukp-leave-end" /></Field>
                    <Field label="Açıklama"><input className={inputCls} value={leaveForm.reason} onChange={(e) => setLeaveForm({ ...leaveForm, reason: e.target.value })} placeholder="Opsiyonel" /></Field>
                    <button onClick={submitLeave} className="px-4 py-2 text-sm rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 h-fit" data-testid="ukp-leave-submit">Gönder</button>
                  </div>
                )}
                <div className="space-y-2">
                  {myLeaves.map((lv) => (
                    <div key={lv.id} className="flex flex-wrap items-center justify-between gap-2 text-sm border border-stone-100 rounded-xl px-3 py-2">
                      <div>{lv.leave_type === "annual" ? "Yıllık izin" : lv.leave_type === "sick" ? "Hastalık" : lv.leave_type} · {lv.start_date} → {lv.end_date} ({lv.days} gün)</div>
                      <span className={`text-xs px-2 py-0.5 rounded-full ${lv.status === "approved" ? "bg-emerald-50 text-emerald-700" : lv.status === "rejected" ? "bg-red-50 text-red-600" : "bg-amber-50 text-amber-700"}`}>
                        {lv.status === "approved" ? "Onaylandı" : lv.status === "rejected" ? "Reddedildi" : "Onay bekliyor"}
                      </span>
                    </div>
                  ))}
                  {myLeaves.length === 0 && <div className="text-sm text-stone-400 py-2">Henüz izin talebiniz yok.</div>}
                </div>
              </div>
            </>
          ) : (
            <div className="text-sm text-stone-400 p-6">Yükleniyor...</div>
          )}
        </div>
      )}

      {editEmp && <HrEditDialog emp={editEmp} onClose={() => setEditEmp(null)} onSaved={() => { setEditEmp(null); loadEmployees(); }} />}
      {docsEmp && <DocsDialog emp={docsEmp} onClose={() => setDocsEmp(null)} />}
      {offEmp && <OffboardDialog emp={offEmp} onClose={() => setOffEmp(null)} onDone={() => { setOffEmp(null); loadEmployees(); }} />}
    </div>
  );
};

export default UKPayrollPanel;
