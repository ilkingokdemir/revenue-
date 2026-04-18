import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import {
  Upload, FileSpreadsheet, Users, Bed, Calendar, TrendingUp,
  ArrowRight, ArrowLeft, X, RefreshCw, CheckCircle2, AlertTriangle,
  Download, Eye, Play, Sparkles, Zap, Clock, Trash2, ChevronRight,
  FileText, Check as CheckIcon, AlertCircle,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const ICON_MAP = { calendar: Calendar, users: Users, bed: Bed, "chart-line": TrendingUp };

const TINT_BY_ENTITY = {
  bookings:   "from-sky-500 to-indigo-600",
  guests:     "from-emerald-500 to-teal-600",
  rooms:      "from-amber-500 to-orange-600",
  rate_plans: "from-violet-500 to-fuchsia-600",
};

const STATUS_META = {
  draft:   { label: "Draft",      cls: "bg-stone-100 text-stone-700 border-stone-200" },
  dry_run: { label: "Validated",  cls: "bg-sky-100 text-sky-800 border-sky-200" },
  running: { label: "Running",    cls: "bg-amber-100 text-amber-800 border-amber-200" },
  done:    { label: "Completed",  cls: "bg-emerald-100 text-emerald-800 border-emerald-200" },
  failed:  { label: "Failed",     cls: "bg-rose-100 text-rose-800 border-rose-200" },
};

export const ImportModulePanel = ({ user }) => {
  const [schemas, setSchemas] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [step, setStep] = useState("list"); // list | pick-entity | upload | map | review
  const [wizard, setWizard] = useState({
    entity: null, file: null, parsed: null, mapping: {}, job: null, dryRun: null, running: false, skipDupBy: "",
  });

  const reload = useCallback(async () => {
    try {
      const [schemasR, jobsR] = await Promise.all([
        axios.get(`${API}/imports/schemas`),
        axios.get(`${API}/imports`),
      ]);
      setSchemas(schemasR.data.entities);
      setJobs(jobsR.data.jobs || []);
    } catch (e) { /* silent */ }
    setLoading(false);
  }, []);
  useEffect(() => { reload(); }, [reload]);

  const reset = () => {
    setWizard({ entity: null, file: null, parsed: null, mapping: {}, job: null, dryRun: null, running: false, skipDupBy: "" });
    setStep("list");
  };

  return (
    <div className="space-y-5" data-testid="import-module">
      {/* Hero */}
      <div className="relative rounded-2xl overflow-hidden shadow-2xl">
        <div className="absolute inset-0 bg-gradient-to-br from-teal-700 via-emerald-700 to-slate-900" />
        <div className="absolute inset-0 opacity-25"
             style={{ backgroundImage: "radial-gradient(circle at 20% 30%, rgba(52,211,153,0.5), transparent 50%), radial-gradient(circle at 85% 70%, rgba(14,165,233,0.3), transparent 50%)" }} />
        <div className="relative p-7 text-white">
          <div className="flex items-start justify-between gap-6 flex-wrap">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <div className="w-8 h-8 rounded-lg bg-white/10 backdrop-blur-md border border-white/20 flex items-center justify-center">
                  <Upload className="w-4 h-4" />
                </div>
                <span className="text-[10px] font-bold uppercase tracking-[0.2em] opacity-80">Import Module</span>
                <Badge className="text-[9px] bg-emerald-400/20 text-emerald-100 border-emerald-300/30">
                  <Sparkles className="w-2.5 h-2.5 mr-0.5" />Competitor says "Missing" — we built it
                </Badge>
              </div>
              <h2 className="text-4xl font-black mb-2 leading-tight" data-testid="import-title">
                Import anything.<br/>
                <span className="bg-gradient-to-r from-emerald-200 to-teal-100 bg-clip-text text-transparent">From any system.</span>
              </h2>
              <p className="text-sm opacity-80 max-w-xl">
                CSV or XLSX in. Bookings, guests, rooms, or rate plans out. Auto-map columns, preview errors, dry-run before commit.
              </p>
            </div>
            <div className="flex flex-col items-end gap-3">
              <div className="flex items-center gap-5">
                <Stat label="Jobs" value={jobs.length} />
                <div className="h-10 w-px bg-white/20" />
                <Stat label="Imported" value={jobs.reduce((a, j) => a + (j.summary?.inserted || 0), 0)} />
              </div>
              <Button size="sm" onClick={() => setStep("pick-entity")}
                      className="bg-white text-emerald-900 hover:bg-white/90 font-bold h-10 px-5 shadow-lg" data-testid="start-import-btn">
                <Upload className="w-4 h-4 mr-1.5" />New Import
              </Button>
            </div>
          </div>
        </div>
      </div>

      {step === "list" && (
        <JobsList jobs={jobs} loading={loading} onReload={reload} user={user} onResume={(j) => {
          // Re-enter wizard for a draft/dry_run job
          setWizard(w => ({ ...w, job: j, entity: j.entity, mapping: j.mapping || {} }));
          setStep("review");
        }} />
      )}
      {step === "pick-entity" && <PickEntity schemas={schemas} onPick={(k) => { setWizard(w => ({ ...w, entity: k })); setStep("upload"); }} onCancel={reset} />}
      {step === "upload" && <UploadStep wizard={wizard} setWizard={setWizard} onNext={() => setStep("map")} onBack={() => setStep("pick-entity")} />}
      {step === "map" && <MapStep wizard={wizard} setWizard={setWizard} schemas={schemas} onNext={async () => {
        // create job + dry run in one shot
        try {
          const { data: job } = await axios.post(`${API}/imports`, {
            entity: wizard.entity,
            file_token: wizard.parsed.file_token,
            mapping: wizard.mapping,
            skip_duplicates_by: wizard.skipDupBy || null,
          });
          const { data: dry } = await axios.post(`${API}/imports/${job.id}/dry-run`);
          setWizard(w => ({ ...w, job, dryRun: dry }));
          setStep("review");
          toast.success(`Validated ${dry.valid}/${dry.total} rows`);
        } catch (e) {
          toast.error(e?.response?.data?.detail || "Validation failed");
        }
      }} onBack={() => setStep("upload")} />}
      {step === "review" && <ReviewStep wizard={wizard} setWizard={setWizard} onBack={() => setStep("map")}
        onImport={async () => {
          setWizard(w => ({ ...w, running: true }));
          try {
            const { data } = await axios.post(`${API}/imports/${wizard.job.id}/run`);
            toast.success(`Imported ${data.inserted} · skipped ${data.skipped} · failed ${data.failed}`);
            reload();
            reset();
          } catch (e) {
            toast.error(e?.response?.data?.detail || "Import failed");
            setWizard(w => ({ ...w, running: false }));
          }
        }} />}
    </div>
  );
};

const Stat = ({ label, value }) => (
  <div><p className="text-3xl font-black tabular-nums">{value}</p><p className="text-[10px] opacity-70 uppercase tracking-wider font-semibold">{label}</p></div>
);

// ====================== Jobs List ======================

const JobsList = ({ jobs, loading, onReload, user, onResume }) => {
  const deleteJob = async (j) => {
    if (!window.confirm(`Delete import record '${j.entity}' from ${new Date(j.created_at).toLocaleString()}?`)) return;
    try {
      await axios.delete(`${API}/imports/${j.id}`);
      toast.success("Deleted");
      onReload();
    } catch (e) { toast.error("Failed"); }
  };

  return (
    <div className="bg-white rounded-2xl border border-stone-200 overflow-hidden" data-testid="jobs-list">
      <div className="px-5 py-3 border-b border-stone-100 flex items-center justify-between">
        <h3 className="text-sm font-bold text-stone-700">Import history</h3>
        <Button size="sm" variant="ghost" onClick={onReload}><RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} /></Button>
      </div>
      {!jobs.length && !loading && (
        <div className="py-20 text-center" data-testid="jobs-empty">
          <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-teal-100 to-emerald-100 flex items-center justify-center">
            <Upload className="w-8 h-8 text-teal-600" />
          </div>
          <p className="font-bold text-stone-700 mb-1 text-lg">No imports yet</p>
          <p className="text-sm text-stone-500">Upload a CSV or XLSX to get started.</p>
        </div>
      )}
      <ul className="divide-y divide-stone-100">
        {jobs.map(j => {
          const s = STATUS_META[j.status] || STATUS_META.draft;
          return (
            <li key={j.id} className="px-5 py-3 hover:bg-stone-50 flex items-center gap-3 group" data-testid={`job-${j.id}`}>
              <div className={`w-10 h-10 rounded-lg flex items-center justify-center text-white bg-gradient-to-br ${TINT_BY_ENTITY[j.entity] || "from-stone-500 to-stone-700"}`}>
                {(() => { const Ic = ICON_MAP[{bookings:"calendar",guests:"users",rooms:"bed",rate_plans:"chart-line"}[j.entity]] || FileText; return <Ic className="w-4 h-4" />; })()}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="font-semibold text-stone-900 text-sm capitalize">{j.entity.replace("_", " ")}</p>
                  <Badge className={`text-[9px] font-bold ${s.cls}`}>{s.label}</Badge>
                  {j.summary && (j.status === "done" || j.status === "dry_run") && (
                    <span className="text-[11px] text-stone-500">
                      {j.summary.inserted !== undefined ? `${j.summary.inserted} inserted · ${j.summary.skipped || 0} skipped · ${j.summary.failed || 0} failed` : `${j.summary.valid}/${j.summary.total} valid`}
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-stone-500 mt-0.5 flex items-center gap-1">
                  <Clock className="w-3 h-3" />{new Date(j.created_at).toLocaleString()} · {j.created_by_name}
                </p>
              </div>
              <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition">
                {(j.status === "draft" || j.status === "dry_run") && (
                  <Button size="sm" variant="ghost" onClick={() => onResume(j)} data-testid={`resume-${j.id}`}>Resume</Button>
                )}
                {user?.role === "admin" && (
                  <Button size="sm" variant="ghost" onClick={() => deleteJob(j)} className="text-red-600 hover:bg-red-50" data-testid={`delete-${j.id}`}>
                    <Trash2 className="w-3.5 h-3.5" />
                  </Button>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
};

// ====================== Step 1: Pick Entity ======================

const PickEntity = ({ schemas, onPick, onCancel }) => (
  <div className="bg-white border border-stone-200 rounded-2xl p-6" data-testid="pick-entity">
    <div className="flex items-center gap-3 mb-5">
      <Button size="sm" variant="ghost" onClick={onCancel}><ArrowLeft className="w-4 h-4 mr-1" />Cancel</Button>
      <h3 className="text-xl font-black text-stone-900">What are you importing?</h3>
    </div>
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      {schemas && Object.entries(schemas).map(([k, v]) => {
        const Ic = ICON_MAP[v.icon] || FileText;
        return (
          <button key={k} onClick={() => onPick(k)}
                  className={`p-5 rounded-xl border-2 border-stone-200 hover:border-stone-300 transition text-left bg-gradient-to-br from-white to-stone-50 hover:shadow-lg hover:-translate-y-0.5 group`}
                  data-testid={`entity-${k}`}>
            <div className={`w-12 h-12 rounded-xl flex items-center justify-center text-white bg-gradient-to-br ${TINT_BY_ENTITY[k] || "from-stone-500 to-stone-700"} mb-3 group-hover:scale-110 transition`}>
              <Ic className="w-6 h-6" />
            </div>
            <p className="font-black text-lg text-stone-900">{v.label}</p>
            <p className="text-xs text-stone-600 mt-0.5">{v.description}</p>
            <p className="text-[10px] text-stone-400 mt-2">{v.required.length} required · {v.optional.length} optional fields</p>
          </button>
        );
      })}
    </div>
  </div>
);

// ====================== Step 2: Upload ======================

const UploadStep = ({ wizard, setWizard, onNext, onBack }) => {
  const fileRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [drag, setDrag] = useState(false);

  const doUpload = async (file) => {
    if (!file) return;
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("entity", wizard.entity);
      const { data } = await axios.post(`${API}/imports/parse`, form, { headers: { "Content-Type": "multipart/form-data" } });
      setWizard(w => ({ ...w, file, parsed: data, mapping: data.auto_mapping || {} }));
      toast.success(`Parsed ${data.rows_count} rows · ${Object.keys(data.auto_mapping).length} fields auto-mapped`);
      onNext();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Upload failed");
    }
    setUploading(false);
  };

  return (
    <div className="bg-white border border-stone-200 rounded-2xl p-6 space-y-4" data-testid="upload-step">
      <div className="flex items-center gap-3">
        <Button size="sm" variant="ghost" onClick={onBack}><ArrowLeft className="w-4 h-4 mr-1" />Back</Button>
        <h3 className="text-xl font-black text-stone-900">Upload your file</h3>
        <Badge className="ml-auto capitalize bg-stone-100 text-stone-700">Importing: {wizard.entity?.replace("_"," ")}</Badge>
      </div>
      <div onDragOver={e => { e.preventDefault(); setDrag(true); }}
           onDragLeave={() => setDrag(false)}
           onDrop={e => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files[0]; if (f) doUpload(f); }}
           onClick={() => fileRef.current?.click()}
           className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition ${drag ? "border-emerald-500 bg-emerald-50" : "border-stone-300 hover:border-stone-400 hover:bg-stone-50"}`}
           data-testid="dropzone">
        <input ref={fileRef} type="file" accept=".csv,.xlsx,.xls,.txt" className="hidden"
               onChange={e => doUpload(e.target.files[0])} data-testid="file-input" />
        <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 mx-auto mb-3 flex items-center justify-center">
          {uploading ? <RefreshCw className="w-6 h-6 text-white animate-spin" /> : <Upload className="w-6 h-6 text-white" />}
        </div>
        <p className="font-bold text-stone-800">Drop your file here or click to browse</p>
        <p className="text-xs text-stone-500 mt-1">CSV, XLSX or XLS · Max 20MB · Max 10,000 rows</p>
      </div>
    </div>
  );
};

// ====================== Step 3: Mapping ======================

const MapStep = ({ wizard, setWizard, schemas, onNext, onBack }) => {
  const schema = schemas[wizard.entity];
  const parsed = wizard.parsed;
  const setMapping = (field, header) => setWizard(w => ({ ...w, mapping: { ...w.mapping, [field]: header === "none" ? "" : header } }));
  const mappedCount = Object.values(wizard.mapping).filter(Boolean).length;
  const reqMissing = schema.required.filter(r => !wizard.mapping[r]);

  return (
    <div className="bg-white border border-stone-200 rounded-2xl p-6 space-y-4" data-testid="map-step">
      <div className="flex items-center gap-3">
        <Button size="sm" variant="ghost" onClick={onBack}><ArrowLeft className="w-4 h-4 mr-1" />Back</Button>
        <h3 className="text-xl font-black text-stone-900">Map columns → fields</h3>
        <Badge className="ml-auto bg-stone-100 text-stone-700">{parsed.rows_count} rows · {mappedCount} mapped</Badge>
      </div>

      {Object.keys(parsed.auto_mapping || {}).length > 0 && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-3 text-xs text-emerald-900 flex items-center gap-2">
          <Sparkles className="w-4 h-4 flex-shrink-0" />
          We auto-mapped {Object.keys(parsed.auto_mapping).length} fields. Double-check below.
        </div>
      )}

      {reqMissing.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-xs text-amber-900 flex items-center gap-2" data-testid="req-missing">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          Required field{reqMissing.length > 1 ? "s" : ""} not mapped: <b>{reqMissing.join(", ")}</b>
        </div>
      )}

      <div className="space-y-3">
        {[...schema.required, ...schema.optional].map(field => {
          const isReq = schema.required.includes(field);
          return (
            <div key={field} className="flex items-center gap-3 py-2 border-b border-stone-100 last:border-0">
              <div className="min-w-[180px] flex items-center gap-1.5">
                <span className="font-mono text-sm text-stone-800">{field}</span>
                {isReq && <Badge className="text-[9px] bg-rose-100 text-rose-700 border-rose-200">REQUIRED</Badge>}
              </div>
              <ArrowRight className="w-4 h-4 text-stone-400" />
              <Select value={wizard.mapping[field] || "none"} onValueChange={v => setMapping(field, v)}>
                <SelectTrigger className="flex-1 h-9" data-testid={`map-${field}`}><SelectValue placeholder="— not mapped —" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">— not mapped —</SelectItem>
                  {parsed.headers.map(h => <SelectItem key={h} value={h}>{h}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          );
        })}
      </div>

      {/* Skip duplicates option */}
      <div className="pt-3 border-t border-stone-100">
        <p className="text-xs font-semibold text-stone-600 mb-2">Skip duplicates based on:</p>
        <Select value={wizard.skipDupBy || "none"} onValueChange={v => setWizard(w => ({ ...w, skipDupBy: v === "none" ? "" : v }))}>
          <SelectTrigger className="h-9 max-w-xs" data-testid="dup-key"><SelectValue placeholder="Don't skip" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="none">Don't skip any</SelectItem>
            {schema.all_fields.filter(f => wizard.mapping[f]).map(f => <SelectItem key={f} value={f}>{f}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      <div className="flex items-center justify-between pt-3">
        <p className="text-xs text-stone-500">{reqMissing.length ? `Map ${reqMissing.length} more required field${reqMissing.length > 1 ? "s" : ""}` : "All required fields mapped ✓"}</p>
        <Button onClick={onNext} disabled={reqMissing.length > 0} className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold" data-testid="validate-btn">
          <Eye className="w-4 h-4 mr-1.5" />Validate & preview
        </Button>
      </div>
    </div>
  );
};

// ====================== Step 4: Review & Commit ======================

const ReviewStep = ({ wizard, setWizard, onBack, onImport }) => {
  const dry = wizard.dryRun || wizard.job?.summary || {};
  const errors = wizard.job?.errors || [];

  return (
    <div className="space-y-4" data-testid="review-step">
      <div className="flex items-center gap-3">
        <Button size="sm" variant="ghost" onClick={onBack}><ArrowLeft className="w-4 h-4 mr-1" />Back</Button>
        <h3 className="text-xl font-black text-stone-900">Review & commit</h3>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <KPI label="Total rows" value={dry.total || 0} tint="stone" />
        <KPI label="Valid" value={dry.valid ?? dry.inserted ?? 0} tint="emerald" />
        <KPI label="Errors" value={(dry.errors ?? dry.failed ?? 0)} tint="rose" />
      </div>

      {dry.preview && dry.preview.length > 0 && (
        <div className="bg-white border border-stone-200 rounded-xl p-4">
          <p className="text-[10px] font-bold uppercase tracking-wider text-stone-500 mb-2">Preview of first 3 rows</p>
          <div className="overflow-x-auto">
            <pre className="text-[10px] text-stone-700 bg-stone-50 p-3 rounded font-mono">{JSON.stringify(dry.preview, null, 2)}</pre>
          </div>
        </div>
      )}

      {errors.length > 0 && (
        <div className="bg-rose-50 border border-rose-200 rounded-xl p-4" data-testid="error-list">
          <p className="text-sm font-bold text-rose-900 mb-2 flex items-center gap-1.5">
            <AlertCircle className="w-4 h-4" />{errors.length} row{errors.length > 1 ? "s" : ""} with errors (first 10 shown)
          </p>
          <ul className="space-y-1 max-h-60 overflow-y-auto">
            {errors.slice(0, 10).map((e, i) => (
              <li key={i} className="text-xs bg-white rounded p-2 border border-rose-100">
                <span className="font-mono text-rose-700">Row {e.row}</span>: <span className="text-stone-700">{e.error}</span>
              </li>
            ))}
          </ul>
          <p className="text-[10px] text-rose-700 mt-2">These rows will be skipped during import.</p>
        </div>
      )}

      <div className="flex items-center justify-between pt-2">
        <p className="text-xs text-stone-500">Ready to import {dry.valid ?? 0} valid rows into your database.</p>
        <Button onClick={onImport} disabled={wizard.running || !dry.valid} className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold h-11 px-5" data-testid="commit-btn">
          {wizard.running ? <><RefreshCw className="w-4 h-4 mr-1.5 animate-spin" />Importing...</> : <><Zap className="w-4 h-4 mr-1.5" />Commit import</>}
        </Button>
      </div>
    </div>
  );
};

const KPI = ({ label, value, tint }) => {
  const tm = {
    stone: "from-stone-100 to-white text-stone-900 border-stone-200",
    emerald: "from-emerald-100 to-white text-emerald-900 border-emerald-200",
    rose: "from-rose-100 to-white text-rose-900 border-rose-200",
  }[tint] || "from-stone-100 to-white text-stone-900 border-stone-200";
  return (
    <div className={`bg-gradient-to-br ${tm} border rounded-xl p-4`}>
      <p className="text-[10px] font-bold uppercase tracking-wider opacity-70">{label}</p>
      <p className="text-3xl font-black tabular-nums mt-1">{value}</p>
    </div>
  );
};
