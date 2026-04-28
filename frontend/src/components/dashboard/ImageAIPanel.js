import React, { useEffect, useState, useCallback, useRef } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Camera,
  CheckCircle,
  XCircle,
  Warning,
  Sparkle,
  ArrowsClockwise,
  Trash,
  ImageSquare,
} from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

const SEVERITY_CFG = {
  pass: { label: "Geçti", bg: "bg-emerald-50 text-emerald-700 border-emerald-200", dot: "bg-emerald-500", Icon: CheckCircle },
  warning: { label: "Uyarı", bg: "bg-amber-50 text-amber-700 border-amber-200", dot: "bg-amber-500", Icon: Warning },
  fail: { label: "Başarısız", bg: "bg-rose-50 text-rose-700 border-rose-200", dot: "bg-rose-500", Icon: XCircle },
};

export default function ImageAIPanel({ propertyId }) {
  const [tab, setTab] = useState("score");

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="image-ai-panel">
      <div className="mb-5">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          <Camera size={12} weight="fill" className="text-cyan-500" />
          <span>HK · AI Görsel Denetim</span>
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">
          AI Temizlik Skorlaması
        </h1>
        <p className="text-sm text-stone-500 mt-1 max-w-2xl">
          Oda fotoğrafı yükle → GPT-5.2 görsel analiz → 0-100 skor + sorunlar + aksiyon önerisi.
          Süpervizörün sübjektif kararını ortadan kaldırır, oda devir hızını artırır.
        </p>
      </div>

      <div className="flex gap-2 mb-5 border-b border-stone-200">
        <TabBtn active={tab === "score"} onClick={() => setTab("score")} testId="img-tab-score">
          <Sparkle size={14} className="inline mr-1.5" />
          Skorla
        </TabBtn>
        <TabBtn active={tab === "history"} onClick={() => setTab("history")} testId="img-tab-history">
          <ImageSquare size={14} className="inline mr-1.5" />
          Geçmiş
        </TabBtn>
      </div>

      {tab === "score" && <ScoreTab propertyId={propertyId} />}
      {tab === "history" && <HistoryTab propertyId={propertyId} />}
    </div>
  );
}

function TabBtn({ active, onClick, children, testId }) {
  return (
    <button onClick={onClick} data-testid={testId}
      className={`px-3.5 py-2 text-sm font-medium transition-all border-b-2 -mb-px ${
        active ? "border-cyan-500 text-cyan-700" : "border-transparent text-stone-500 hover:text-stone-800"
      }`}>
      {children}
    </button>
  );
}

function ScoreTab({ propertyId }) {
  const [roomId, setRoomId] = useState("");
  const [notes, setNotes] = useState("");
  const [photos, setPhotos] = useState([]); // base64 strings
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const fileRef = useRef(null);

  const onFiles = (files) => {
    const slots = 3 - photos.length;
    const accepted = Array.from(files).slice(0, slots);
    const reads = accepted.map((f) => new Promise((res, rej) => {
      if (f.size > 4 * 1024 * 1024) { rej(new Error("4MB üstü")); return; }
      const r = new FileReader();
      r.onload = () => res(r.result);
      r.onerror = () => rej(r.error);
      r.readAsDataURL(f);
    }));
    Promise.allSettled(reads).then((rs) => {
      const ok = rs.filter((x) => x.status === "fulfilled").map((x) => x.value);
      if (ok.length < rs.length) toast.error("Bazı dosyalar atlandı (>4MB)");
      setPhotos([...photos, ...ok]);
    });
  };

  const submit = async () => {
    if (!roomId.trim()) { toast.error("Oda no girin"); return; }
    if (photos.length === 0) { toast.error("En az 1 fotoğraf"); return; }
    setBusy(true);
    setResult(null);
    try {
      const r = await axios.post(`${API}/api/image-ai/cleanliness-score`, {
        property_id: propertyId,
        room_id: roomId,
        photos_base64: photos,
        notes: notes || null,
      }, { withCredentials: true });
      setResult(r.data);
      toast.success(`Skor: ${r.data.score}/100 · ${SEVERITY_CFG[r.data.severity]?.label}`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Skorlama başarısız");
    } finally {
      setBusy(false);
    }
  };

  const reset = () => { setRoomId(""); setNotes(""); setPhotos([]); setResult(null); };

  return (
    <div className="grid md:grid-cols-2 gap-4">
      <div className="space-y-3">
        <div>
          <label className="block text-[11px] uppercase tracking-wider text-stone-500 mb-1">Oda No / ID</label>
          <input
            value={roomId}
            onChange={(e) => setRoomId(e.target.value)}
            data-testid="img-room-id"
            placeholder="Örn: 204"
            className="w-full px-3 py-2 text-sm border border-stone-200 rounded-md focus:outline-none focus:border-cyan-400"
          />
        </div>

        <div>
          <label className="block text-[11px] uppercase tracking-wider text-stone-500 mb-1">Fotoğraflar (max 3, ≤4MB)</label>
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            multiple
            onChange={(e) => { onFiles(e.target.files); e.target.value = ""; }}
            data-testid="img-file-input"
            className="hidden"
          />
          <button
            onClick={() => fileRef.current?.click()}
            disabled={photos.length >= 3}
            data-testid="img-upload-btn"
            className="w-full py-3 border-2 border-dashed border-stone-300 rounded-md text-sm text-stone-600 hover:border-cyan-400 hover:bg-cyan-50 transition-all disabled:opacity-50 inline-flex items-center justify-center gap-2"
          >
            <Camera size={16} />
            {photos.length >= 3 ? "Maksimum 3 fotoğraf" : `Fotoğraf yükle (${photos.length}/3)`}
          </button>
          {photos.length > 0 && (
            <div className="grid grid-cols-3 gap-2 mt-2" data-testid="img-photos-grid">
              {photos.map((p, i) => (
                <div key={i} className="relative aspect-square bg-stone-100 rounded-md overflow-hidden border border-stone-200">
                  <img src={p} alt="" className="w-full h-full object-cover" />
                  <button
                    onClick={() => setPhotos(photos.filter((_, idx) => idx !== i))}
                    data-testid={`img-remove-${i}`}
                    className="absolute top-1 right-1 w-5 h-5 rounded-full bg-rose-500 text-white text-[10px] inline-flex items-center justify-center hover:bg-rose-600"
                  >
                    <Trash size={10} weight="bold" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        <div>
          <label className="block text-[11px] uppercase tracking-wider text-stone-500 mb-1">Notlar (opsiyonel)</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={2}
            data-testid="img-notes"
            placeholder="Örn: Banyo tadilatı sonrası ilk temizlik"
            className="w-full px-3 py-2 text-sm border border-stone-200 rounded-md focus:outline-none focus:border-cyan-400"
          />
        </div>

        <div className="flex gap-2">
          <button
            onClick={submit}
            disabled={busy || photos.length === 0}
            data-testid="img-submit"
            className="flex-1 py-2.5 rounded-md bg-cyan-500 text-white text-sm font-semibold hover:bg-cyan-600 disabled:opacity-50 inline-flex items-center justify-center gap-2"
          >
            <Sparkle size={14} weight="fill" />
            {busy ? "AI Analiz Ediyor…" : "AI ile Skorla"}
          </button>
          {result && (
            <button onClick={reset} className="px-4 py-2.5 rounded-md border border-stone-200 text-stone-600 hover:bg-stone-50 text-sm">
              Sıfırla
            </button>
          )}
        </div>
      </div>

      {/* Result */}
      <div className="bg-white border border-stone-200 rounded-lg p-5" data-testid="img-result">
        {!result && !busy && (
          <div className="text-center py-12 text-stone-400 text-sm">
            <Camera size={48} className="mx-auto mb-3 opacity-30" />
            Fotoğrafları yükleyip "AI ile Skorla" butonuna basın.
          </div>
        )}

        {busy && (
          <div className="text-center py-12">
            <div className="w-12 h-12 border-4 border-cyan-200 border-t-cyan-500 rounded-full animate-spin mx-auto mb-3" />
            <div className="text-sm text-stone-600">AI fotoğrafları analiz ediyor…</div>
          </div>
        )}

        {result && (
          <ScoreResultCard result={result} />
        )}
      </div>
    </div>
  );
}

function ScoreResultCard({ result }) {
  const cfg = SEVERITY_CFG[result.severity] || SEVERITY_CFG.warning;
  const Icon = cfg.Icon;
  const scoreColor = result.score >= 90 ? "text-emerald-600" : result.score >= 70 ? "text-amber-600" : "text-rose-600";

  return (
    <div className="space-y-4">
      <div className="text-center">
        <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full border text-xs font-medium ${cfg.bg}`}>
          <Icon size={14} weight="fill" />
          {cfg.label}
        </div>
        <div className={`text-6xl font-bold mt-3 ${scoreColor}`}>{result.score}</div>
        <div className="text-xs text-stone-400 mt-1">/ 100 puan · Oda {result.room_id}</div>
      </div>

      {result.issues?.length > 0 && (
        <div>
          <div className="text-[10px] uppercase tracking-wider text-stone-500 mb-2 flex items-center gap-1">
            <Warning size={11} weight="fill" />
            Tespit Edilen Sorunlar ({result.issues.length})
          </div>
          <div className="space-y-1.5" data-testid="img-issues">
            {result.issues.map((iss, i) => (
              <div key={i} className="bg-rose-50 border border-rose-100 rounded-md px-2.5 py-1.5 text-xs text-rose-800 flex items-start gap-2">
                <span className="text-rose-500 font-semibold">•</span>
                <span>{iss}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {result.observations?.length > 0 && (
        <div>
          <div className="text-[10px] uppercase tracking-wider text-stone-500 mb-2">Görsel Gözlemler</div>
          <div className="space-y-1" data-testid="img-observations">
            {result.observations.map((o, i) => (
              <div key={i} className="text-xs text-stone-600 px-2.5 py-1 bg-stone-50 rounded">
                {o}
              </div>
            ))}
          </div>
        </div>
      )}

      {result.next_action && (
        <div className="bg-cyan-50 border border-cyan-100 rounded-md p-3">
          <div className="text-[10px] uppercase tracking-wider text-cyan-700 mb-1 flex items-center gap-1">
            <Sparkle size={10} weight="fill" />
            Önerilen Eylem
          </div>
          <div className="text-xs text-cyan-900">{result.next_action}</div>
        </div>
      )}
    </div>
  );
}

function HistoryTab({ propertyId }) {
  const [rows, setRows] = useState([]);
  const [stats, setStats] = useState({ pass_rate: 0, avg_score: 0, count: 0 });
  const [loading, setLoading] = useState(false);
  const [filterRoom, setFilterRoom] = useState("");

  const load = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const url = filterRoom
        ? `${API}/api/image-ai/cleanliness-history/${propertyId}?room_id=${filterRoom}&limit=100`
        : `${API}/api/image-ai/cleanliness-history/${propertyId}?limit=100`;
      const r = await axios.get(url, { withCredentials: true });
      setRows(r.data.rows || []);
      setStats({ pass_rate: r.data.pass_rate, avg_score: r.data.avg_score, count: r.data.count });
    } catch (e) {
      toast.error("Geçmiş yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [propertyId, filterRoom]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        <Kpi label="Toplam Skor" value={stats.count} color="cyan" />
        <Kpi label="Geçme Oranı" value={`%${stats.pass_rate}`} color="emerald" />
        <Kpi label="Ort. Skor" value={stats.avg_score} color="sky" />
      </div>

      <div className="flex items-center gap-2">
        <input
          value={filterRoom}
          onChange={(e) => setFilterRoom(e.target.value)}
          placeholder="Oda no filtresi"
          data-testid="img-filter-room"
          className="px-2.5 py-1 text-xs border border-stone-200 rounded-md focus:outline-none focus:border-cyan-400"
        />
        <button onClick={load} className="ml-auto px-3 py-1 text-xs rounded-md border border-stone-200 text-stone-600 hover:bg-stone-50 inline-flex items-center gap-1.5">
          <ArrowsClockwise size={12} /> Yenile
        </button>
      </div>

      {loading && <div className="text-sm text-stone-400">Yükleniyor…</div>}

      {rows.length === 0 && !loading && (
        <div className="text-center py-12 text-stone-400 text-sm border border-dashed border-stone-200 rounded-lg">
          Henüz skorlama yok.
        </div>
      )}

      <div className="space-y-2" data-testid="img-history-list">
        {rows.map((r) => {
          const cfg = SEVERITY_CFG[r.severity] || SEVERITY_CFG.warning;
          const Icon = cfg.Icon;
          return (
            <div key={r.id} className="bg-white border border-stone-200 rounded-lg p-3 flex items-center gap-3">
              <div className={`w-10 h-10 rounded-md inline-flex items-center justify-center flex-shrink-0 ${cfg.bg.split(" ").slice(0, 2).join(" ")}`}>
                <Icon size={18} weight="fill" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-stone-900">Oda {r.room_id}</span>
                  <span className={`px-1.5 py-0.5 text-[10px] rounded font-medium ${cfg.bg}`}>{cfg.label}</span>
                  <span className="text-[10px] text-stone-400">{r.photo_count} foto</span>
                </div>
                {r.issues?.length > 0 && (
                  <div className="text-[11px] text-stone-500 mt-0.5 truncate">{r.issues.slice(0, 2).join(" · ")}</div>
                )}
                <div className="text-[10px] text-stone-400 mt-0.5">{r.scored_at?.slice(0, 16).replace("T", " ")} · {r.scored_by}</div>
              </div>
              <div className={`text-2xl font-bold ${r.score >= 90 ? "text-emerald-600" : r.score >= 70 ? "text-amber-600" : "text-rose-600"}`}>
                {r.score}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Kpi({ label, value, color }) {
  const bg = {
    cyan: "bg-cyan-50 text-cyan-700",
    emerald: "bg-emerald-50 text-emerald-700",
    sky: "bg-sky-50 text-sky-700",
  }[color];
  return (
    <div className={`${bg} border border-stone-100 rounded-lg p-3.5`}>
      <div className="text-[10px] uppercase tracking-wider opacity-70">{label}</div>
      <div className="text-2xl font-semibold mt-1">{value}</div>
    </div>
  );
}
