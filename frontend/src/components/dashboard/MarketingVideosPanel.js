/**
 * MarketingVideosPanel — Sora 2 video generation hub.
 *
 * Generate IG/TikTok-ready promotional videos for events or ad-hoc prompts.
 * Polls job status every 8s until complete.
 */
import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import { toast } from "sonner";
import { FilmReel, Sparkle, Download, ArrowsClockwise, CheckCircle, XCircle } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/marketing-videos`;

export default function MarketingVideosPanel() {
  const [jobs, setJobs] = useState([]);
  const [config, setConfig] = useState(null);
  const [form, setForm] = useState({
    prompt: "", size: "1024x1792", duration: 8, model: "sora-2",
  });
  const [creating, setCreating] = useState(false);
  const pollRef = useRef(null);

  const reload = useCallback(async () => {
    try {
      const r = await axios.get(`${API}?limit=50`, { withCredentials: true });
      setJobs(r.data.items || []);
    } catch (e) { toast.error("Yüklenemedi"); }
  }, []);

  useEffect(() => {
    axios.get(`${API}/sizes`, { withCredentials: true })
         .then(r => setConfig(r.data));
    reload();
    // Poll every 10s while any job is queued/rendering
    pollRef.current = setInterval(() => {
      setJobs(curr => {
        if (curr.some(j => j.status === "queued" || j.status === "rendering")) {
          reload();
        }
        return curr;
      });
    }, 10000);
    return () => clearInterval(pollRef.current);
  }, [reload]);

  async function create() {
    if (!form.prompt) { toast.error("Prompt gerekli"); return; }
    setCreating(true);
    try {
      await axios.post(`${API}/generate`, form, { withCredentials: true });
      toast.success("Video kuyruğa alındı — 2-5 dk içinde hazır olacak");
      setForm({ ...form, prompt: "" });
      reload();
    } catch (e) { toast.error(e?.response?.data?.detail || "Hata"); }
    finally { setCreating(false); }
  }

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="marketing-videos-panel">
      <div className="mb-5">
        <div className="text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">Sora 2 · Social Marketing</div>
        <h2 className="text-2xl font-semibold text-stone-900 inline-flex items-center gap-2">
          <FilmReel size={22} weight="fill" className="text-fuchsia-600" /> Pazarlama Videosu Üretici
        </h2>
        <p className="text-sm text-stone-500 mt-1">
          AI ile Instagram/TikTok için 4-12 saniyelik tanıtım videoları üretin. Public events için tek-tıkla otomatik prompt.
        </p>
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        <div className="lg:col-span-1 bg-white border border-stone-200 rounded-xl p-4 sticky top-4 h-fit">
          <h3 className="text-sm font-semibold mb-3 inline-flex items-center gap-1.5">
            <Sparkle size={14} weight="fill" /> Yeni Video
          </h3>
          <div className="space-y-2.5">
            <label className="block">
              <span className="text-xs text-stone-700">Prompt</span>
              <textarea value={form.prompt} rows={4} data-testid="mv-prompt"
                        onChange={e => setForm({...form, prompt: e.target.value})}
                        placeholder="Örn: Akdeniz manzaralı butik otelin terasında günbatımında şefin canlı pişirme deneyimi, sinematik..."
                        className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg mt-1" />
            </label>
            <div className="grid grid-cols-2 gap-2">
              <label className="block">
                <span className="text-xs text-stone-700">Boyut</span>
                <select value={form.size} onChange={e => setForm({...form, size:e.target.value})}
                        data-testid="mv-size"
                        className="w-full px-2 py-1.5 text-xs border border-stone-300 rounded-lg mt-1">
                  {config?.sizes.map(s => <option key={s} value={s}>{`${s}${s==="1024x1792"?" (IG/TikTok)":""}`}</option>)}
                </select>
              </label>
              <label className="block">
                <span className="text-xs text-stone-700">Süre (sn)</span>
                <select value={form.duration} onChange={e => setForm({...form, duration:parseInt(e.target.value)})}
                        data-testid="mv-duration"
                        className="w-full px-2 py-1.5 text-xs border border-stone-300 rounded-lg mt-1">
                  {config?.durations.map(d => <option key={d} value={d}>{`${d} sn`}</option>)}
                </select>
              </label>
              <label className="block col-span-2">
                <span className="text-xs text-stone-700">Model</span>
                <select value={form.model} onChange={e => setForm({...form, model:e.target.value})}
                        className="w-full px-2 py-1.5 text-xs border border-stone-300 rounded-lg mt-1">
                  {config?.models.map(m => <option key={m} value={m}>{`${m}${m==="sora-2-pro"?" (yüksek kalite, yavaş)":""}`}</option>)}
                </select>
              </label>
            </div>
            <button onClick={create} disabled={creating || !form.prompt}
                    data-testid="mv-generate-btn"
                    className="w-full py-2 text-sm font-medium bg-fuchsia-600 text-white rounded-lg hover:bg-fuchsia-700 disabled:opacity-50 inline-flex items-center justify-center gap-1.5">
              <Sparkle size={13} weight="fill" /> {creating ? "Kuyruğa alınıyor..." : "Üret"}
            </button>
            <div className="text-[10px] text-stone-500 bg-stone-50 border border-stone-200 rounded p-2">
              💡 İpucu: Detaylı görsel açıklama, ışık, kamera hareketi belirtin. Üretim 2-5 dk sürer.
            </div>
          </div>
        </div>

        <div className="lg:col-span-2">
          <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
            <div className="px-4 py-2.5 border-b border-stone-200 flex items-center justify-between text-sm font-semibold">
              <span>Üretim Geçmişi ({jobs.length})</span>
              <button onClick={reload} className="text-stone-400 hover:text-stone-700">
                <ArrowsClockwise size={14} />
              </button>
            </div>
            <div className="max-h-[700px] overflow-y-auto">
              {jobs.length === 0 ? (
                <div className="px-4 py-12 text-center text-stone-400 text-sm">
                  Henüz video üretilmedi.
                </div>
              ) : jobs.map(j => (
                <div key={j.id} data-testid={`mv-job-${j.id}`}
                     className="border-t border-stone-100 first:border-t-0 p-4">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex-1 min-w-0 pr-3">
                      <div className="flex items-center gap-2 mb-1">
                        <StatusBadge status={j.status} />
                        <span className="text-[10px] text-stone-400">
                          {j.size} · {j.duration}sn · {j.model}
                        </span>
                        {j.source_type === "public_event" && (
                          <span className="text-[10px] bg-fuchsia-100 text-fuchsia-700 px-1.5 py-0.5 rounded">
                            Etkinlik: {j.event_title}
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-stone-700 line-clamp-2">{j.prompt}</p>
                      <div className="text-[10px] text-stone-400 mt-1">
                        {j.created_at?.slice(0, 19).replace("T", " ")} · {j.created_by}
                        {j.file_size_bytes && (
                          <span> · {(j.file_size_bytes/1024/1024).toFixed(1)} MB</span>
                        )}
                      </div>
                      {j.error && (
                        <div className="text-xs text-rose-600 mt-1 bg-rose-50 border border-rose-200 rounded p-1.5">
                          {j.error}
                        </div>
                      )}
                    </div>
                    {j.status === "completed" && j.public_url && (
                      <div className="flex flex-col gap-2">
                        <video src={j.public_url} controls
                               className="w-32 rounded-lg border border-stone-200"
                               data-testid={`mv-video-${j.id}`} />
                        <a href={j.public_url} target="_blank" rel="noopener noreferrer" download
                           className="text-[10px] inline-flex items-center justify-center gap-1 px-2 py-1 bg-fuchsia-600 text-white rounded">
                          <Download size={11} /> İndir
                        </a>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatusBadge({ status }) {
  const map = {
    queued: { l: "Kuyrukta", c: "bg-amber-100 text-amber-700", I: ArrowsClockwise },
    rendering: { l: "Üretiliyor", c: "bg-blue-100 text-blue-700", I: ArrowsClockwise },
    completed: { l: "Tamamlandı", c: "bg-emerald-100 text-emerald-700", I: CheckCircle },
    failed: { l: "Hata", c: "bg-rose-100 text-rose-700", I: XCircle },
  };
  const m = map[status] || map.queued;
  const I = m.I;
  return (
    <span className={`text-[10px] px-2 py-0.5 rounded-full inline-flex items-center gap-1 ${m.c}`}>
      <I size={10} weight={status==="completed"?"fill":"regular"} className={status==="rendering"?"animate-spin":""} />
      {m.l}
    </span>
  );
}
