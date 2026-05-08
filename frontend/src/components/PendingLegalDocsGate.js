import { useEffect, useState } from "react";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { Scale, ShieldAlert, CheckCircle2, Feather } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const PendingLegalDocsGate = ({ user }) => {
  const [pending, setPending] = useState([]);
  const [idx, setIdx] = useState(0);
  const [loaded, setLoaded] = useState(false);
  const [responses, setResponses] = useState({});
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!user) return;
    // Only fetch pending legal docs for activated users (during onboarding, the Onboarding Gate
    // takes priority — legal acceptance happens after the user is fully activated).
    if (user.is_activated === false) { setLoaded(true); return; }
    (async () => {
      try {
        const { data } = await axios.get(`${API}/legal-documents/pending/me`);
        setPending(data || []);
      } catch { /* silent */ }
      setLoaded(true);
    })();
  }, [user]);

  // Reset responses when advancing to a new doc
  useEffect(() => { setResponses({}); }, [idx]);

  if (!loaded || pending.length === 0 || idx >= pending.length) return null;

  const doc = pending[idx];
  const updateResp = (fid, val) => setResponses(r => ({ ...r, [fid]: val }));

  const submit = async () => {
    // Client-side required validation
    for (const f of doc.fields || []) {
      if (f.required && f.type !== "heading") {
        const v = responses[f.id];
        if (f.type === "checkbox" && !v) {
          toast.error(`Required: ${f.label}`); return;
        }
        if (f.type !== "checkbox" && (!v || (typeof v === "string" && !v.trim()))) {
          toast.error(`Required: ${f.label}`); return;
        }
      }
    }
    setSubmitting(true);
    try {
      await axios.post(`${API}/legal-documents/${doc.id}/accept`, { responses });
      toast.success(`Accepted: ${doc.title}`);
      if (idx + 1 >= pending.length) {
        setIdx(idx + 1);
      } else {
        setIdx(idx + 1);
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to accept");
    }
    setSubmitting(false);
  };

  const renderField = (f) => {
    if (f.type === "heading") {
      return (
        <div key={f.id} className="border-l-4 border-indigo-500 pl-4 py-1 bg-indigo-50/50" data-testid={`gate-field-${f.id}`}>
          <h3 className="text-sm font-black text-stone-800 uppercase tracking-wide">{f.label}</h3>
          {f.content && <p className="text-[13px] text-stone-600 leading-relaxed mt-1 whitespace-pre-wrap">{f.content}</p>}
        </div>
      );
    }
    if (f.type === "checkbox") {
      return (
        <label key={f.id} className="flex items-start gap-2 cursor-pointer" data-testid={`gate-field-${f.id}`}>
          <input type="checkbox" className="mt-0.5" checked={!!responses[f.id]} onChange={e => updateResp(f.id, e.target.checked)} />
          <span className="text-sm text-stone-700">
            {f.label} {f.required && <span className="text-red-500">*</span>}
          </span>
        </label>
      );
    }
    if (f.type === "text") {
      return (
        <div key={f.id} data-testid={`gate-field-${f.id}`}>
          <Label className="text-xs">{f.label} {f.required && <span className="text-red-500">*</span>}</Label>
          <Input value={responses[f.id] || ""} onChange={e => updateResp(f.id, e.target.value)} placeholder={f.placeholder || ""} />
        </div>
      );
    }
    if (f.type === "textarea") {
      return (
        <div key={f.id} data-testid={`gate-field-${f.id}`}>
          <Label className="text-xs">{f.label} {f.required && <span className="text-red-500">*</span>}</Label>
          <Textarea rows={3} value={responses[f.id] || ""} onChange={e => updateResp(f.id, e.target.value)} placeholder={f.placeholder || ""} />
        </div>
      );
    }
    if (f.type === "select") {
      return (
        <div key={f.id} data-testid={`gate-field-${f.id}`}>
          <Label className="text-xs">{f.label} {f.required && <span className="text-red-500">*</span>}</Label>
          <Select value={responses[f.id] || ""} onValueChange={v => updateResp(f.id, v)}>
            <SelectTrigger><SelectValue placeholder="Select..." /></SelectTrigger>
            <SelectContent>
              {(f.options || []).map(o => <SelectItem key={o} value={o}>{o}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      );
    }
    if (f.type === "date") {
      return (
        <div key={f.id} data-testid={`gate-field-${f.id}`}>
          <Label className="text-xs">{f.label} {f.required && <span className="text-red-500">*</span>}</Label>
          <Input type="date" value={responses[f.id] || ""} onChange={e => updateResp(f.id, e.target.value)} />
        </div>
      );
    }
    if (f.type === "signature") {
      return (
        <div key={f.id} data-testid={`gate-field-${f.id}`}>
          <Label className="text-xs flex items-center gap-1"><Feather className="w-3 h-3" />{f.label} {f.required && <span className="text-red-500">*</span>}</Label>
          <Input value={responses[f.id] || ""} onChange={e => updateResp(f.id, e.target.value)} placeholder="Type your full name as signature"
            className="text-xl" style={{ fontFamily: "'Brush Script MT', 'Caveat', cursive" }} />
        </div>
      );
    }
    return null;
  };

  return (
    <div className="fixed inset-0 z-[100] bg-slate-950/85 backdrop-blur-sm flex items-center justify-center p-4" data-testid="legal-gate">
      <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[92vh] flex flex-col">
        {/* Header */}
        <div className="bg-gradient-to-br from-indigo-900 to-slate-900 text-white rounded-t-2xl p-5 flex-shrink-0">
          <div className="flex items-center gap-2 mb-1">
            <ShieldAlert className="w-5 h-5 text-amber-300" />
            <span className="text-[10px] font-bold uppercase tracking-widest opacity-80">Action Required · {idx + 1} of {pending.length}</span>
          </div>
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-xl font-black" data-testid="gate-title">{doc.title}</h2>
              <p className="text-[11px] opacity-75 mt-0.5">
                <Badge className="bg-white/10 text-white border-white/20 text-[9px] mr-1">v{doc.version}</Badge>
                <code className="opacity-70">{doc.code}</code>
              </p>
            </div>
            <Scale className="w-6 h-6 opacity-50 flex-shrink-0" />
          </div>
          {doc.description && <p className="text-[12px] opacity-80 mt-2">{doc.description}</p>}
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {(doc.fields || []).map(renderField)}
          {(!doc.fields || doc.fields.length === 0) && (
            <p className="text-center text-stone-400 py-6 text-sm">No additional fields — click Accept to confirm.</p>
          )}
        </div>

        {/* Footer */}
        <div className="border-t p-4 flex items-center justify-between gap-3 flex-shrink-0 bg-stone-50 rounded-b-2xl">
          <p className="text-[11px] text-stone-500">
            Signed as <span className="font-semibold text-stone-700">{user?.name}</span> · your IP will be recorded for audit.
          </p>
          <Button size="sm" onClick={submit} disabled={submitting} className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold px-6" data-testid="gate-accept">
            {submitting ? "Recording..." : <><CheckCircle2 className="w-4 h-4 mr-1" />Accept & Continue</>}
          </Button>
        </div>

        {/* Progress */}
        <div className="absolute top-0 left-0 right-0 h-1 bg-stone-200 rounded-t-2xl overflow-hidden">
          <div className="h-full bg-gradient-to-r from-emerald-400 to-teal-500 transition-all" style={{ width: `${(idx / pending.length) * 100}%` }} />
        </div>
      </div>
    </div>
  );
};
