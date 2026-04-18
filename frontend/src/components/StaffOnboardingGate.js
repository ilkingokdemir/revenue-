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
  // HMRC form state (HMRC 09/22 Starter Checklist)
  const [hmrc, setHmrc] = useState({
    // Personal details
    last_name: "", first_names: "", sex: "", dob: "",
    home_address: "", postcode: "", country: "United Kingdom",
    ni_number: "", start_date: "",
    // Employee statement decision tree
    q8_another_job: false,
    q9_receives_pension: false,
    q10_recent_payments: false,
    statement: "",
    // Student loan
    has_loan: false, still_studying: false, student_loan_plans: [],
    // Declaration
    declaration_full_name: "", declaration_signature: "",
    declaration_date: new Date().toISOString().slice(0, 10),
    declaration_confirmed: false,
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

  // HMRC Statement A/B/C decision tree per HMRC guidance.
  // Declared BEFORE any early-return so React hook rules are honoured.
  const computedStatement = (() => {
    if (hmrc.q8_another_job) return "C";
    if (hmrc.q9_receives_pension) return "C";
    if (hmrc.q10_recent_payments) return "B";
    if (hmrc.dob) return "A";
    return "";
  })();

  // Keep hmrc.statement in sync with the decision tree
  useEffect(() => {
    if (computedStatement && hmrc.statement !== computedStatement) {
      setHmrc(h => ({ ...h, statement: computedStatement }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [computedStatement]);

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

  const togglePlan = (plan) => {
    setHmrc(h => ({
      ...h,
      student_loan_plans: h.student_loan_plans.includes(plan)
        ? h.student_loan_plans.filter(p => p !== plan)
        : [...h.student_loan_plans, plan],
    }));
  };

  const submitHMRC = async () => {
    const required = {
      last_name: "Last name",
      first_names: "First names",
      sex: "Sex",
      dob: "Date of birth",
      home_address: "Home address",
      postcode: "Postcode",
      start_date: "Employment start date",
      declaration_full_name: "Declaration full name",
      declaration_signature: "Signature",
    };
    for (const [k, label] of Object.entries(required)) {
      if (!(hmrc[k] || "").trim()) { toast.error(`Missing: ${label}`); return; }
    }
    if (!hmrc.statement) { toast.error("Please answer the employee-statement questions"); return; }
    if (!hmrc.declaration_confirmed) { toast.error("Please tick the declaration confirmation"); return; }
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

  const UploadedChip = ({ label }) => (
    <div className="mt-3 flex items-center gap-2 bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs rounded-lg p-2.5">
      <CheckCircle2 className="w-4 h-4" />
      <span>{label} received · <span className="font-semibold">locked</span></span>
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
                <>
                  <UploadedChip label="ID / Passport" />
                  <p className="text-[10px] text-stone-400 mt-2 leading-relaxed">
                    For your security this document is now sealed. You can't re-open, re-upload or delete it.
                    If you've made a mistake, please ask your admin to reset this step.
                  </p>
                </>
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
            </div>
          )}

          {/* ADDRESS */}
          {tab === "address" && (
            <div data-testid="tab-address">
              <h3 className="text-base font-black text-stone-800 mb-1">Upload proof of address</h3>
              <p className="text-[12px] text-stone-500 mb-4">Utility bill, bank statement or council tax letter dated within the last 3 months.</p>

              {status.address_proof_uploaded ? (
                <>
                  <UploadedChip label="Address proof" />
                  <p className="text-[10px] text-stone-400 mt-2 leading-relaxed">
                    For your security this document is now sealed. You can't re-open, re-upload or delete it.
                    If you've made a mistake, please ask your admin to reset this step.
                  </p>
                </>
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
            </div>
          )}

          {/* HMRC STARTER CHECKLIST — mirrors HMRC 09/22 form */}
          {tab === "hmrc" && status.hmrc_submitted && (
            <div data-testid="tab-hmrc-sealed" className="space-y-4">
              <div className="flex items-start gap-3 bg-gradient-to-br from-stone-50 to-stone-100 border border-stone-200 rounded-xl p-3">
                <div className="text-[10px] leading-tight">
                  <p className="font-black text-stone-800 uppercase tracking-wider">HM Revenue & Customs</p>
                  <p className="text-stone-500">Starter checklist · HMRC 09/22</p>
                </div>
                <div className="ml-auto text-right">
                  <Badge className="bg-emerald-100 text-emerald-700 border-emerald-200 text-[10px]">SUBMITTED & LOCKED</Badge>
                </div>
              </div>
              <div className="border-2 border-emerald-200 rounded-xl bg-emerald-50 p-6 text-center">
                <CheckCircle2 className="w-14 h-14 mx-auto text-emerald-500 mb-2" />
                <h3 className="text-base font-black text-stone-800">Checklist signed and submitted</h3>
                <p className="text-[12px] text-stone-600 mt-1 max-w-md mx-auto leading-relaxed">
                  Thank you. Your HMRC Starter Checklist has been recorded and digitally signed.
                  For your security and HMRC audit requirements, the form is now sealed and cannot be
                  re-opened or re-submitted from your account.
                </p>
                <p className="text-[11px] text-stone-500 mt-3">
                  If any detail is incorrect, please ask your admin to reset this step.
                </p>
              </div>
            </div>
          )}
          {tab === "hmrc" && !status.hmrc_submitted && (
            <div data-testid="tab-hmrc" className="space-y-5">
              <div className="flex items-start gap-3 bg-gradient-to-br from-stone-50 to-stone-100 border border-stone-200 rounded-xl p-3">
                <div className="text-[10px] leading-tight">
                  <p className="font-black text-stone-800 uppercase tracking-wider">HM Revenue & Customs</p>
                  <p className="text-stone-500">Starter checklist · HMRC 09/22</p>
                </div>
              </div>
              <p className="text-[12px] text-stone-600 leading-relaxed">
                <span className="font-semibold">Tell your employer of your circumstances</span> so that you do not pay too much or too little tax.
                Fill this form if you do not have a P45. Make sure you answer the questions correctly.
              </p>

              {/* ========== PERSONAL DETAILS ========== */}
              <section>
                <h4 className="text-xs font-black uppercase tracking-wider text-stone-800 border-b border-stone-200 pb-1 mb-3">Employee's personal details</h4>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label className="text-xs">1. Last name *</Label>
                    <Input value={hmrc.last_name} onChange={e => setHmrc({ ...hmrc, last_name: e.target.value })} data-testid="hmrc-last-name" />
                  </div>
                  <div>
                    <Label className="text-xs">2. First names *</Label>
                    <Input value={hmrc.first_names} onChange={e => setHmrc({ ...hmrc, first_names: e.target.value })} placeholder="Jim (not initials)" data-testid="hmrc-first-names" />
                    <p className="text-[9px] text-stone-400 mt-0.5">Do not enter initials or shortened names — e.g. Jim for James.</p>
                  </div>
                  <div className="col-span-2">
                    <Label className="text-xs">3. What is your sex? *</Label>
                    <p className="text-[9px] text-stone-400 mb-1">As shown on your birth certificate or gender recognition certificate.</p>
                    <div className="flex items-center gap-3">
                      {[{v:"male",l:"Male"},{v:"female",l:"Female"}].map(o => (
                        <label key={o.v} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border cursor-pointer text-xs font-semibold ${hmrc.sex === o.v ? "bg-emerald-50 border-emerald-300 text-emerald-700" : "bg-white border-stone-200 text-stone-600"}`} data-testid={`hmrc-sex-${o.v}`}>
                          <input type="radio" name="sex" className="hidden" checked={hmrc.sex === o.v} onChange={() => setHmrc({ ...hmrc, sex: o.v })} />
                          <div className={`w-3 h-3 rounded-full border ${hmrc.sex === o.v ? "bg-emerald-500 border-emerald-500" : "border-stone-300"}`} />
                          {o.l}
                        </label>
                      ))}
                    </div>
                  </div>
                  <div>
                    <Label className="text-xs">4. Date of birth *</Label>
                    <Input type="date" value={hmrc.dob} onChange={e => setHmrc({ ...hmrc, dob: e.target.value })} data-testid="hmrc-dob" />
                  </div>
                  <div>
                    <Label className="text-xs">7. Employment start date *</Label>
                    <Input type="date" value={hmrc.start_date} onChange={e => setHmrc({ ...hmrc, start_date: e.target.value })} data-testid="hmrc-start" />
                  </div>
                  <div className="col-span-2">
                    <Label className="text-xs">5. Home address *</Label>
                    <Textarea rows={2} value={hmrc.home_address} onChange={e => setHmrc({ ...hmrc, home_address: e.target.value })} placeholder="123 High Street, London" data-testid="hmrc-address" />
                  </div>
                  <div>
                    <Label className="text-xs">Postcode *</Label>
                    <Input value={hmrc.postcode} onChange={e => setHmrc({ ...hmrc, postcode: e.target.value })} placeholder="SW1A 1AA" className="uppercase" data-testid="hmrc-postcode" />
                  </div>
                  <div>
                    <Label className="text-xs">Country</Label>
                    <Input value={hmrc.country} onChange={e => setHmrc({ ...hmrc, country: e.target.value })} data-testid="hmrc-country" />
                  </div>
                  <div className="col-span-2">
                    <Label className="text-xs">6. National Insurance number <span className="text-stone-400 font-normal">(if known)</span></Label>
                    <Input value={hmrc.ni_number} onChange={e => setHmrc({ ...hmrc, ni_number: e.target.value.toUpperCase() })} placeholder="AB123456C" className="uppercase" data-testid="hmrc-ni" />
                  </div>
                </div>
              </section>

              {/* ========== EMPLOYEE STATEMENT ========== */}
              <section>
                <h4 className="text-xs font-black uppercase tracking-wider text-stone-800 border-b border-stone-200 pb-1 mb-3">Employee statement</h4>
                <p className="text-[11px] text-stone-500 mb-3">These questions help choose the statement that matches your circumstances so your employer applies the correct tax code.</p>
                <div className="space-y-3">
                  <YesNo label="8. Do you have another job?"
                         value={hmrc.q8_another_job}
                         onChange={v => setHmrc({ ...hmrc, q8_another_job: v })}
                         testId="hmrc-q8" />
                  {!hmrc.q8_another_job && (
                    <YesNo label="9. Do you receive payments from a State, workplace or private pension?"
                           value={hmrc.q9_receives_pension}
                           onChange={v => setHmrc({ ...hmrc, q9_receives_pension: v })}
                           testId="hmrc-q9" />
                  )}
                  {!hmrc.q8_another_job && !hmrc.q9_receives_pension && (
                    <YesNo label="10. Since 6 April have you received payments from another job which has ended, Jobseeker's Allowance (JSA), Employment and Support Allowance (ESA) or Incapacity Benefit?"
                           value={hmrc.q10_recent_payments}
                           onChange={v => setHmrc({ ...hmrc, q10_recent_payments: v })}
                           testId="hmrc-q10" />
                  )}
                </div>

                {/* Auto-computed statement */}
                {computedStatement && (
                  <div className="mt-3 bg-blue-50 border border-blue-200 rounded-xl p-3" data-testid="hmrc-statement-picked">
                    <p className="text-[10px] font-bold text-blue-900 uppercase tracking-wide mb-1">Based on your answers</p>
                    <p className="text-sm font-black text-blue-900 mb-1">Statement {computedStatement} applies</p>
                    <p className="text-[11px] text-blue-800 leading-snug">
                      {computedStatement === "A" && "Current personal allowance — This is your first job since 6 April with no other income."}
                      {computedStatement === "B" && "Current personal allowance on a Week 1/Month 1 basis — Since 6 April you've had another job or taxable benefits."}
                      {computedStatement === "C" && "Tax Code BR — You have another job or receive a State/workplace/private pension."}
                    </p>
                  </div>
                )}
              </section>

              {/* ========== STUDENT LOANS ========== */}
              <section>
                <h4 className="text-xs font-black uppercase tracking-wider text-stone-800 border-b border-stone-200 pb-1 mb-3">Student loans</h4>
                <div className="space-y-3">
                  <YesNo label="11. Do you have a student or postgraduate loan?"
                         value={hmrc.has_loan}
                         onChange={v => setHmrc({ ...hmrc, has_loan: v, still_studying: false, student_loan_plans: [] })}
                         testId="hmrc-q11" />

                  {hmrc.has_loan && (
                    <>
                      <YesNo
                        label="12. Are any of these true? You're still studying / you completed or left your course after 6 April / you've already repaid your loan in full / you're paying Student Loans Company by Direct Debit"
                        value={hmrc.still_studying}
                        onChange={v => setHmrc({ ...hmrc, still_studying: v, student_loan_plans: v ? [] : hmrc.student_loan_plans })}
                        testId="hmrc-q12" />

                      {!hmrc.still_studying && (
                        <div className="bg-stone-50 border border-stone-200 rounded-xl p-3">
                          <p className="text-[11px] font-bold text-stone-800 mb-2">13. Tick all loan plans that apply *</p>
                          <div className="space-y-2">
                            {[
                              { id: "plan_1", label: "Plan 1 — Northern Ireland or started England/Wales course before 1 Sep 2012" },
                              { id: "plan_2", label: "Plan 2 — England/Wales, started on or after 1 Sep 2012" },
                              { id: "plan_4", label: "Plan 4 — Scotland (SAAS)" },
                              { id: "postgraduate", label: "Postgraduate loan (England & Wales)" },
                            ].map(p => (
                              <label key={p.id} className="flex items-start gap-2 cursor-pointer" data-testid={`hmrc-plan-${p.id}`}>
                                <input type="checkbox" className="mt-0.5"
                                       checked={hmrc.student_loan_plans.includes(p.id)}
                                       onChange={() => togglePlan(p.id)} />
                                <span className="text-[11px] text-stone-700">{p.label}</span>
                              </label>
                            ))}
                          </div>
                        </div>
                      )}
                    </>
                  )}
                </div>
              </section>

              {/* ========== DECLARATION ========== */}
              <section>
                <h4 className="text-xs font-black uppercase tracking-wider text-stone-800 border-b border-stone-200 pb-1 mb-3">Declaration</h4>
                <p className="text-[11px] text-stone-600 mb-3">I confirm that the information I've given on this form is correct.</p>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label className="text-xs">Full name *</Label>
                    <Input value={hmrc.declaration_full_name}
                           onChange={e => setHmrc({ ...hmrc, declaration_full_name: e.target.value.toUpperCase() })}
                           placeholder="USE CAPITAL LETTERS" className="uppercase" data-testid="hmrc-decl-name" />
                  </div>
                  <div>
                    <Label className="text-xs">Date *</Label>
                    <Input type="date" value={hmrc.declaration_date}
                           onChange={e => setHmrc({ ...hmrc, declaration_date: e.target.value })}
                           data-testid="hmrc-decl-date" />
                  </div>
                  <div className="col-span-2">
                    <Label className="text-xs">Signature *</Label>
                    <Input value={hmrc.declaration_signature}
                           onChange={e => setHmrc({ ...hmrc, declaration_signature: e.target.value })}
                           placeholder="Type your full name as your signature"
                           className="text-xl"
                           style={{ fontFamily: "'Brush Script MT', 'Caveat', cursive" }}
                           data-testid="hmrc-decl-sig" />
                  </div>
                </div>
                <label className="flex items-start gap-2 mt-3 cursor-pointer" data-testid="hmrc-decl-confirm-wrap">
                  <input type="checkbox" className="mt-0.5"
                         checked={hmrc.declaration_confirmed}
                         onChange={e => setHmrc({ ...hmrc, declaration_confirmed: e.target.checked })}
                         data-testid="hmrc-decl-confirm" />
                  <span className="text-[11px] text-stone-700">
                    I confirm the information on this form is correct. I understand providing false information may result in a penalty and affect my tax code.
                  </span>
                </label>
              </section>

              <Button onClick={submitHMRC} disabled={submitting} className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold h-10" data-testid="hmrc-submit">
                {submitting ? "Submitting..." : "Submit HMRC starter checklist"}
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

// Helper: Yes/No pill selector for HMRC questions
const YesNo = ({ label, value, onChange, testId }) => (
  <div data-testid={testId}>
    <p className="text-[12px] text-stone-700 leading-snug mb-1.5">{label}</p>
    <div className="flex items-center gap-2">
      {[{v:true,l:"Yes"},{v:false,l:"No"}].map(o => (
        <button key={o.l} type="button" onClick={() => onChange(o.v)}
          className={`px-4 py-1 text-xs font-semibold rounded-lg border transition ${value === o.v ? "bg-emerald-50 border-emerald-300 text-emerald-700" : "bg-white border-stone-200 text-stone-500 hover:border-stone-300"}`}
          data-testid={`${testId}-${o.l.toLowerCase()}`}>
          {o.l}
        </button>
      ))}
    </div>
  </div>
);
