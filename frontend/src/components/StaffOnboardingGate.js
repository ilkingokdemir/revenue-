import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import {
  UserCheck, Camera, Upload, FileText, Home, CheckCircle2, Circle,
  Loader2, AlertCircle, Sparkles, ArrowRight, ArrowLeft, Receipt,
  FileSignature, RefreshCw,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const TABS = [
  { id: "passport",  label: "ID / Passport",     icon: UserCheck, key: "passport" },
  { id: "address",   label: "Address Proof",     icon: Home,      key: "address" },
  { id: "hmrc",      label: "HMRC Checklist",    icon: Receipt,   key: "hmrc" },
  { id: "contract",  label: "Employment Contract", icon: FileSignature, key: "contract" },
];

export const StaffOnboardingGate = ({ user, onActivated }) => {
  const [status, setStatus] = useState(null);
  const [tab, setTab] = useState("passport");
  const [submitting, setSubmitting] = useState(false);
  const [completing, setCompleting] = useState(false);
  const passportRef = useRef(null);
  const addressRef = useRef(null);
  // HMRC form state
  const [hmrc, setHmrc] = useState({
    first_name: "", last_name: "", dob: "", ni_number: "",
    address: "", postcode: "", start_date: "",
    statement: "A", student_loan: false, student_loan_plan: "", postgrad_loan: false, gender: "",
  });

  const load = useCallback(async () => {
    if (!user) return;
    try {
      const { data } = await axios.get(`${API}/staff-onboarding/me`);
      setStatus(data);
      if (data.hmrc_data && Object.keys(data.hmrc_data).length) {
        setHmrc(h => ({ ...h, ...data.hmrc_data }));
      }
      // Jump to first unfinished tab
      const unfinished = TABS.find(t => !data.progress.tasks[t.key]);
      if (unfinished) setTab(unfinished.id);
    } catch { /* silent */ }
  }, [user]);

  useEffect(() => { load(); }, [load]);

  // Gate is only shown when user is authenticated but NOT activated.
  if (!user) return null;
  if (user.is_activated !== false) return null;
  if (!status) {
    return (
      <div className="fixed inset-0 z-[90] bg-slate-950/85 backdrop-blur-sm flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-white" />
      </div>
    );
  }

  const uploadFile = async (kind, file) => {
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) { toast.error("File must be under 10MB"); return; }
    setSubmitting(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      await axios.post(`${API}/staff-onboarding/upload/${kind}`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success(`${kind === "passport" ? "ID" : "Address proof"} uploaded`);
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Upload failed");
    }
    setSubmitting(false);
  };

  const submitHMRC = async () => {
    const required = ["first_name", "last_name", "dob", "ni_number", "address", "postcode", "start_date"];
    for (const r of required) {
      if (!(hmrc[r] || "").trim()) { toast.error(`Missing: ${r.replace("_", " ")}`); return; }
    }
    setSubmitting(true);
    try {
      await axios.post(`${API}/staff-onboarding/hmrc`, hmrc);
      toast.success("HMRC starter checklist submitted");
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed");
    }
    setSubmitting(false);
  };

  const completeOnboarding = async () => {
    setCompleting(true);
    try {
      await axios.post(`${API}/staff-onboarding/complete`);
      toast.success("Welcome aboard! Your account is now active.");
      onActivated?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Complete failed");
    }
    setCompleting(false);
  };

  const tabIdx = TABS.findIndex(t => t.id === tab);
  const next = () => setTab(TABS[Math.min(tabIdx + 1, TABS.length - 1)].id);
  const prev = () => setTab(TABS[Math.max(tabIdx - 1, 0)].id);
  const p = status.progress;

  const TabButton = ({ t, idx }) => {
    const done = p.tasks[t.key];
    const active = tab === t.id;
    const Icon = t.icon;
    return (
      <button
        onClick={() => setTab(t.id)}
        className={`flex-1 flex items-center gap-2 px-3 py-2.5 text-xs font-semibold rounded-lg transition ${active ? "bg-white text-slate-900 shadow-sm" : "text-stone-500 hover:text-stone-700"}`}
        data-testid={`onboard-tab-${t.id}`}
      >
        {done ? <CheckCircle2 className="w-4 h-4 text-emerald-500" /> : <Icon className="w-4 h-4" />}
        <span className="hidden md:inline">{t.label}</span>
        <span className="md:hidden">{idx + 1}</span>
      </button>
    );
  };

  const UploadedChip = ({ filename }) => (
    <div className="mt-3 flex items-center gap-2 bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs rounded-lg p-2.5">
      <CheckCircle2 className="w-4 h-4" />
      <span>Uploaded: <span className="font-semibold">{filename}</span></span>
    </div>
  );

  return (
    <div className="fixed inset-0 z-[90] bg-slate-950/90 backdrop-blur-sm flex items-center justify-center p-4" data-testid="onboarding-gate">
      <div className="bg-white rounded-2xl shadow-2xl max-w-3xl w-full max-h-[95vh] flex flex-col">
        {/* Header */}
        <div className="bg-gradient-to-br from-emerald-700 via-teal-800 to-slate-900 text-white rounded-t-2xl p-5 flex-shrink-0">
          <div className="flex items-center gap-2 mb-1">
            <Sparkles className="w-5 h-5 text-amber-300" />
            <span className="text-[10px] font-bold uppercase tracking-widest opacity-80">Welcome to the team, {user.name.split(" ")[0]}</span>
          </div>
          <div className="flex items-end justify-between gap-3">
            <h2 className="text-xl md:text-2xl font-black leading-tight" data-testid="onboard-title">
              Let's finish setting you up — {p.done}/{p.total} complete
            </h2>
            <Badge className="bg-white/10 text-white border-white/20 text-[10px]">{p.pct}%</Badge>
          </div>
          {/* Progress bar */}
          <div className="mt-3 h-1.5 bg-white/10 rounded-full overflow-hidden">
            <div className="h-full bg-gradient-to-r from-emerald-400 to-teal-400 transition-all" style={{ width: `${p.pct}%` }} />
          </div>
          <p className="text-[11px] opacity-80 mt-2">
            Your account will activate automatically once all four steps are completed.
          </p>
        </div>

        {/* Tabs */}
        <div className="flex items-center gap-1 bg-stone-100 mx-4 mt-4 p-1 rounded-xl flex-shrink-0">
          {TABS.map((t, i) => <TabButton key={t.id} t={t} idx={i} />)}
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-5">
          {/* PASSPORT */}
          {tab === "passport" && (
            <div data-testid="tab-passport">
              <h3 className="text-base font-black text-stone-800 mb-1">Upload your passport or national ID</h3>
              <p className="text-[12px] text-stone-500 mb-4">We need a clear photo or scan. Accepted: JPG, PNG, PDF, HEIC (max 10MB).</p>

              {status.passport_uploaded ? (
                <UploadedChip filename={status.passport_filename} />
              ) : (
                <div className="border-2 border-dashed border-stone-200 rounded-xl p-8 text-center">
                  <Camera className="w-10 h-10 mx-auto text-stone-400 mb-2" />
                  <p className="text-sm text-stone-600 mb-4">Take a photo or upload from your device</p>
                  <div className="flex items-center justify-center gap-2 flex-wrap">
                    <Button onClick={() => passportRef.current?.click()} disabled={submitting} className="bg-emerald-600 hover:bg-emerald-700 text-white" data-testid="passport-upload-btn">
                      <Upload className="w-4 h-4 mr-1" />Choose file
                    </Button>
                    <input type="file" ref={passportRef} hidden accept="image/*,.pdf,.heic,.heif"
                           onChange={e => uploadFile("passport", e.target.files?.[0])} data-testid="passport-input" />
                    <Button variant="outline" onClick={() => {
                      const el = document.createElement("input");
                      el.type = "file"; el.accept = "image/*"; el.capture = "environment";
                      el.onchange = e => uploadFile("passport", e.target.files?.[0]);
                      el.click();
                    }} data-testid="passport-camera-btn">
                      <Camera className="w-4 h-4 mr-1" />Take photo
                    </Button>
                  </div>
                </div>
              )}

              {status.passport_url && (
                <div className="mt-3">
                  <a href={`${process.env.REACT_APP_BACKEND_URL}${status.passport_url}`} target="_blank" rel="noreferrer"
                     className="text-xs text-blue-600 hover:underline">View uploaded document ↗</a>
                </div>
              )}
            </div>
          )}

          {/* ADDRESS */}
          {tab === "address" && (
            <div data-testid="tab-address">
              <h3 className="text-base font-black text-stone-800 mb-1">Upload proof of address</h3>
              <p className="text-[12px] text-stone-500 mb-4">Utility bill, bank statement or council tax letter dated within the last 3 months.</p>

              {status.address_proof_uploaded ? (
                <UploadedChip filename={status.address_proof_filename} />
              ) : (
                <div className="border-2 border-dashed border-stone-200 rounded-xl p-8 text-center">
                  <FileText className="w-10 h-10 mx-auto text-stone-400 mb-2" />
                  <p className="text-sm text-stone-600 mb-4">Take a photo or upload from your device</p>
                  <div className="flex items-center justify-center gap-2 flex-wrap">
                    <Button onClick={() => addressRef.current?.click()} disabled={submitting} className="bg-emerald-600 hover:bg-emerald-700 text-white" data-testid="address-upload-btn">
                      <Upload className="w-4 h-4 mr-1" />Choose file
                    </Button>
                    <input type="file" ref={addressRef} hidden accept="image/*,.pdf,.heic,.heif"
                           onChange={e => uploadFile("address", e.target.files?.[0])} data-testid="address-input" />
                    <Button variant="outline" onClick={() => {
                      const el = document.createElement("input");
                      el.type = "file"; el.accept = "image/*"; el.capture = "environment";
                      el.onchange = e => uploadFile("address", e.target.files?.[0]);
                      el.click();
                    }} data-testid="address-camera-btn">
                      <Camera className="w-4 h-4 mr-1" />Take photo
                    </Button>
                  </div>
                </div>
              )}
              {status.address_proof_url && (
                <div className="mt-3">
                  <a href={`${process.env.REACT_APP_BACKEND_URL}${status.address_proof_url}`} target="_blank" rel="noreferrer"
                     className="text-xs text-blue-600 hover:underline">View uploaded document ↗</a>
                </div>
              )}
            </div>
          )}

          {/* HMRC STARTER CHECKLIST */}
          {tab === "hmrc" && (
            <div data-testid="tab-hmrc">
              <div className="flex items-center gap-2 mb-1">
                <h3 className="text-base font-black text-stone-800">HMRC Starter Checklist</h3>
                {status.hmrc_submitted && <Badge className="bg-emerald-100 text-emerald-700 border-emerald-200 text-[10px]">SUBMITTED</Badge>}
              </div>
              <p className="text-[12px] text-stone-500 mb-4">Required for HMRC to apply the correct tax code. Equivalent to a P46.</p>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="text-xs">First name *</Label>
                  <Input value={hmrc.first_name} onChange={e => setHmrc({ ...hmrc, first_name: e.target.value })} data-testid="hmrc-first-name" />
                </div>
                <div>
                  <Label className="text-xs">Last name *</Label>
                  <Input value={hmrc.last_name} onChange={e => setHmrc({ ...hmrc, last_name: e.target.value })} data-testid="hmrc-last-name" />
                </div>
                <div>
                  <Label className="text-xs">Date of birth *</Label>
                  <Input type="date" value={hmrc.dob} onChange={e => setHmrc({ ...hmrc, dob: e.target.value })} data-testid="hmrc-dob" />
                </div>
                <div>
                  <Label className="text-xs">Gender</Label>
                  <Select value={hmrc.gender || "prefer_not_say"} onValueChange={v => setHmrc({ ...hmrc, gender: v === "prefer_not_say" ? "" : v })}>
                    <SelectTrigger data-testid="hmrc-gender"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="male">Male</SelectItem>
                      <SelectItem value="female">Female</SelectItem>
                      <SelectItem value="other">Other</SelectItem>
                      <SelectItem value="prefer_not_say">Prefer not to say</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-xs">National Insurance number *</Label>
                  <Input value={hmrc.ni_number} onChange={e => setHmrc({ ...hmrc, ni_number: e.target.value })} placeholder="AB123456C" className="uppercase" data-testid="hmrc-ni" />
                </div>
                <div>
                  <Label className="text-xs">Start date *</Label>
                  <Input type="date" value={hmrc.start_date} onChange={e => setHmrc({ ...hmrc, start_date: e.target.value })} data-testid="hmrc-start" />
                </div>
                <div className="col-span-2">
                  <Label className="text-xs">Home address *</Label>
                  <Textarea rows={2} value={hmrc.address} onChange={e => setHmrc({ ...hmrc, address: e.target.value })} placeholder="123 High Street, London" data-testid="hmrc-address" />
                </div>
                <div>
                  <Label className="text-xs">Postcode *</Label>
                  <Input value={hmrc.postcode} onChange={e => setHmrc({ ...hmrc, postcode: e.target.value })} placeholder="SW1A 1AA" className="uppercase" data-testid="hmrc-postcode" />
                </div>
              </div>

              <div className="mt-5 bg-blue-50 border border-blue-200 rounded-xl p-3">
                <p className="text-[11px] font-bold text-blue-900 mb-2">Employee statement — choose ONE *</p>
                <div className="space-y-2">
                  {["A", "B", "C"].map(s => (
                    <label key={s} className={`flex items-start gap-2 p-2 rounded-lg cursor-pointer border ${hmrc.statement === s ? "bg-white border-blue-400" : "bg-white/50 border-transparent hover:border-blue-200"}`} data-testid={`hmrc-stmt-${s}`}>
                      <input type="radio" name="stmt" className="mt-0.5" checked={hmrc.statement === s} onChange={() => setHmrc({ ...hmrc, statement: s })} />
                      <span className="text-[11px] text-stone-700"><span className="font-bold text-blue-900">Statement {s}:</span> {status.hmrc_statements?.[s]}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div className="mt-4 space-y-2">
                <label className="flex items-center gap-2 text-sm text-stone-700 cursor-pointer">
                  <input type="checkbox" checked={hmrc.student_loan} onChange={e => setHmrc({ ...hmrc, student_loan: e.target.checked })} data-testid="hmrc-student" />
                  I have a student loan still being repaid
                </label>
                {hmrc.student_loan && (
                  <Select value={hmrc.student_loan_plan || "plan_1"} onValueChange={v => setHmrc({ ...hmrc, student_loan_plan: v })}>
                    <SelectTrigger className="ml-6 w-64" data-testid="hmrc-loan-plan"><SelectValue placeholder="Plan" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="plan_1">Plan 1</SelectItem>
                      <SelectItem value="plan_2">Plan 2</SelectItem>
                      <SelectItem value="plan_4">Plan 4 (Scotland)</SelectItem>
                      <SelectItem value="plan_5">Plan 5</SelectItem>
                    </SelectContent>
                  </Select>
                )}
                <label className="flex items-center gap-2 text-sm text-stone-700 cursor-pointer">
                  <input type="checkbox" checked={hmrc.postgrad_loan} onChange={e => setHmrc({ ...hmrc, postgrad_loan: e.target.checked })} data-testid="hmrc-postgrad" />
                  I have a postgraduate loan still being repaid
                </label>
              </div>

              <Button onClick={submitHMRC} disabled={submitting} className="mt-5 w-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold h-10" data-testid="hmrc-submit">
                {submitting ? "Submitting..." : status.hmrc_submitted ? "Update HMRC details" : "Submit HMRC checklist"}
              </Button>
            </div>
          )}

          {/* CONTRACT */}
          {tab === "contract" && (
            <div data-testid="tab-contract">
              <h3 className="text-base font-black text-stone-800 mb-1">Sign your employment contract</h3>
              <p className="text-[12px] text-stone-500 mb-4">Your manager has emailed you a secure signing link. Once signed, this step will tick automatically.</p>

              {status.contract_signed ? (
                <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-5 text-center">
                  <CheckCircle2 className="w-10 h-10 mx-auto text-emerald-500 mb-2" />
                  <p className="text-sm font-bold text-emerald-800">Contract signed</p>
                  <p className="text-[11px] text-emerald-700 mt-1">Your employment contract is on file.</p>
                </div>
              ) : (
                <div className="bg-amber-50 border border-amber-200 rounded-xl p-5">
                  <div className="flex items-start gap-2">
                    <AlertCircle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-sm font-bold text-amber-900">Awaiting signature</p>
                      <p className="text-[12px] text-amber-800 mt-1">
                        Ask your admin to send you the signing link. Once you sign from the link, this step will update automatically.
                        Click <span className="font-bold">Refresh</span> below if you've just signed.
                      </p>
                      <Button size="sm" onClick={load} variant="outline" className="mt-3 bg-white" data-testid="refresh-contract">
                        <RefreshCw className="w-3.5 h-3.5 mr-1" />Refresh status
                      </Button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer nav */}
        <div className="border-t p-4 flex items-center justify-between gap-3 flex-shrink-0 bg-stone-50 rounded-b-2xl">
          <Button variant="outline" onClick={prev} disabled={tabIdx === 0} data-testid="onboard-prev">
            <ArrowLeft className="w-3.5 h-3.5 mr-1" />Back
          </Button>
          {p.complete ? (
            <Button onClick={completeOnboarding} disabled={completing} className="bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-600 hover:to-teal-700 text-white font-bold px-6" data-testid="onboard-complete">
              {completing ? "Activating..." : <><Sparkles className="w-4 h-4 mr-1" />Activate my account</>}
            </Button>
          ) : (
            <Button onClick={next} disabled={tabIdx === TABS.length - 1} className="bg-slate-800 hover:bg-slate-700 text-white" data-testid="onboard-next">
              Next<ArrowRight className="w-3.5 h-3.5 ml-1" />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};
