import { useEffect, useState } from "react";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import {
  FileSignature, CheckCircle2, AlertTriangle, PoundSterling,
  Calendar, Clock, Briefcase, User,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const fmt$ = (n) => `£${(Number(n) || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
const TYPE_LABEL = {
  full_time: "Full-time", part_time: "Part-time", fixed_term: "Fixed-term",
  casual: "Casual", zero_hours: "Zero-hours", freelance: "Freelance",
};

export const ContractSigningPage = ({ token }) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [contract, setContract] = useState(null);
  const [hotel, setHotel] = useState("");
  const [alreadySigned, setAlreadySigned] = useState(false);
  const [fullName, setFullName] = useState("");
  const [accept, setAccept] = useState(false);
  const [signature, setSignature] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [signed, setSigned] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await axios.get(`${API}/contracts/sign/${token}`);
        setContract(data.contract);
        setHotel(data.hotel_name);
        setAlreadySigned(data.already_signed);
        setFullName(data.contract.staff_name || "");
      } catch (e) {
        setError(e?.response?.data?.detail || "Invalid or expired signing link.");
      }
      setLoading(false);
    })();
  }, [token]);

  const submit = async () => {
    if (!fullName.trim() || !signature.trim()) { toast.error("Type your full name and signature"); return; }
    if (!accept) { toast.error("Please accept the terms"); return; }
    setSubmitting(true);
    try {
      await axios.post(`${API}/contracts/sign/${token}`, {
        full_name: fullName.trim(),
        signature: signature.trim(),
        accept_terms: true,
      });
      setSigned(true);
      toast.success("Contract signed");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to sign");
    }
    setSubmitting(false);
  };

  if (loading) {
    return <div className="min-h-screen flex items-center justify-center text-stone-500">Loading contract...</div>;
  }
  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6 bg-stone-50">
        <div className="bg-white rounded-2xl p-10 shadow-md text-center max-w-md">
          <AlertTriangle className="w-12 h-12 mx-auto text-rose-500 mb-3" />
          <h1 className="text-xl font-black text-stone-800 mb-1">Unable to load contract</h1>
          <p className="text-sm text-stone-600">{error}</p>
        </div>
      </div>
    );
  }
  if (signed || alreadySigned) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6 bg-emerald-50">
        <div className="bg-white rounded-2xl p-10 shadow-md text-center max-w-md" data-testid="signed-state">
          <CheckCircle2 className="w-14 h-14 mx-auto text-emerald-500 mb-3" />
          <h1 className="text-2xl font-black text-stone-800 mb-1">Contract signed</h1>
          <p className="text-sm text-stone-600 mb-4">
            Your employment contract with <span className="font-semibold">{hotel}</span> is now on file. A copy has been saved for your records.
          </p>
          {contract.signed_at && <p className="text-[11px] text-stone-400">Signed {String(contract.signed_at).slice(0, 16).replace("T", " ")}</p>}
        </div>
      </div>
    );
  }

  const pay = contract.salary_annual > 0
    ? `${fmt$(contract.salary_annual)}/year`
    : `${fmt$(contract.hourly_rate)}/hour`;

  return (
    <div className="min-h-screen bg-stone-100 py-10 px-4" data-testid="contract-sign-page">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="bg-gradient-to-br from-slate-900 to-slate-700 text-white rounded-t-2xl p-6 shadow-md">
          <div className="flex items-center gap-2 mb-1">
            <FileSignature className="w-5 h-5" />
            <span className="text-[10px] uppercase tracking-widest opacity-80">Employment Contract</span>
          </div>
          <h1 className="text-2xl font-black">{hotel}</h1>
          <p className="text-sm opacity-85 mt-0.5">Prepared for {contract.staff_name}</p>
        </div>

        {/* Body */}
        <div className="bg-white p-6 shadow-sm space-y-5">
          {/* Key terms grid */}
          <div>
            <h2 className="text-sm font-bold text-stone-800 mb-2">Key terms</h2>
            <div className="grid grid-cols-2 gap-3">
              <Row icon={User} label="Employee" value={contract.staff_name} />
              <Row icon={Briefcase} label="Role" value={contract.role || "—"} />
              <Row icon={FileSignature} label="Contract" value={TYPE_LABEL[contract.contract_type] || contract.contract_type} />
              <Row icon={Calendar} label="Start" value={contract.start_date || "—"} />
              <Row icon={Calendar} label="End" value={contract.end_date || "Permanent"} />
              <Row icon={Clock} label="Hours/week" value={`${contract.hours_per_week || 0}h`} />
              <Row icon={PoundSterling} label="Pay" value={pay} />
              <Row icon={Clock} label="Notice" value={`${contract.notice_period_days || 0} days`} />
              <Row icon={Calendar} label="Holiday" value={`${contract.holiday_entitlement_days || 0} days/yr`} />
              {contract.probation_end && <Row icon={AlertTriangle} label="Probation until" value={contract.probation_end} />}
            </div>
          </div>

          {/* Terms */}
          {contract.terms && (
            <div>
              <h2 className="text-sm font-bold text-stone-800 mb-2">Terms & conditions</h2>
              <div className="bg-stone-50 rounded-xl p-4 text-[13px] text-stone-700 leading-relaxed whitespace-pre-wrap max-h-64 overflow-y-auto border border-stone-200" data-testid="contract-terms">
                {contract.terms}
              </div>
            </div>
          )}

          {/* Signature */}
          <div className="border-t pt-5 space-y-3">
            <h2 className="text-sm font-bold text-stone-800">E-signature</h2>
            <div>
              <label className="text-xs text-stone-500 font-medium">Your full legal name</label>
              <Input value={fullName} onChange={e => setFullName(e.target.value)} data-testid="sign-name" />
            </div>
            <div>
              <label className="text-xs text-stone-500 font-medium">Type your signature</label>
              <Input value={signature} onChange={e => setSignature(e.target.value)} placeholder="Type your name as your signature" data-testid="sign-signature"
                className="font-['Caveat',_cursive] text-xl" style={{ fontFamily: "'Brush Script MT', 'Caveat', cursive" }} />
            </div>
            <label className="flex items-start gap-2 text-xs text-stone-600 cursor-pointer" data-testid="sign-accept-label">
              <input type="checkbox" className="mt-0.5" checked={accept} onChange={e => setAccept(e.target.checked)} data-testid="sign-accept" />
              <span>I have read and agree to the terms of this employment contract. I understand this signature is legally binding.</span>
            </label>
            <Button onClick={submit} disabled={submitting} className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold h-11" data-testid="sign-submit">
              {submitting ? "Signing..." : "Sign Contract"}
            </Button>
          </div>
        </div>

        <div className="text-center text-[10px] text-stone-400 mt-3">
          Signing link · powered by {hotel}
        </div>
      </div>
    </div>
  );
};

const Row = ({ icon: Icon, label, value }) => (
  <div className="flex items-start gap-2 bg-stone-50 rounded-lg p-2.5 border border-stone-200">
    <Icon className="w-3.5 h-3.5 text-stone-400 mt-0.5 flex-shrink-0" />
    <div className="min-w-0">
      <p className="text-[10px] text-stone-500 uppercase tracking-wider">{label}</p>
      <p className="text-sm font-semibold text-stone-800 truncate">{value}</p>
    </div>
  </div>
);
