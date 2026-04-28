import React, { useEffect, useState, useCallback, useRef } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Broom,
  Sparkle,
  Camera,
  CheckCircle,
  XCircle,
  Warning,
  ArrowsClockwise,
  ArrowRight,
  PlayCircle,
  ShieldCheck,
  Trash,
  House,
} from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

const COLUMNS = [
  { state: "vacant_dirty", label: "Kirli", color: "rose", Icon: Trash },
  { state: "cleaning_in_progress", label: "Temizleniyor", color: "amber", Icon: Broom },
  { state: "ai_inspection", label: "AI Denetiminde", color: "violet", Icon: Sparkle },
  { state: "needs_rework", label: "Tekrar Gerek", color: "orange", Icon: Warning },
  { state: "vacant_clean", label: "Temiz · Satılabilir", color: "emerald", Icon: CheckCircle },
];

const COLOR_BG = {
  rose: "bg-rose-50 border-rose-200",
  amber: "bg-amber-50 border-amber-200",
  violet: "bg-violet-50 border-violet-200",
  orange: "bg-orange-50 border-orange-200",
  emerald: "bg-emerald-50 border-emerald-200",
};
const COLOR_TEXT = {
  rose: "text-rose-700",
  amber: "text-amber-700",
  violet: "text-violet-700",
  orange: "text-orange-700",
  emerald: "text-emerald-700",
};

export default function HkTurnoverPanel({ propertyId }) {
  const [board, setBoard] = useState(null);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [selectedRoom, setSelectedRoom] = useState(null);

  const load = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const [b, d] = await Promise.all([
        axios.get(`${API}/api/hk-turnover/${propertyId}`, { withCredentials: true }),
        axios.get(`${API}/api/hk-turnover/dashboard/${propertyId}`, { withCredentials: true }),
      ]);
      setBoard(b.data);
      setStats(d.data);
    } catch (e) {
      toast.error("Kanban yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="p-5 max-w-[1600px] mx-auto" data-testid="hk-turnover-panel">
      <div className="mb-5">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          <Sparkle size={12} weight="fill" className="text-cyan-500" />
          <span>HK · AI Otomatik Onay</span>
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">Oda Devir Kanban</h1>
        <p className="text-sm text-stone-500 mt-1 max-w-2xl">
          Kirli → Temizleniyor → <b>Foto yükle → AI 5sn'de onaylar</b> → Satılabilir. Süpervizörü atla, oda devir hızını ↑.
        </p>
      </div>

      {/* Dashboard KPIs */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-5" data-testid="hk-stats">
          <Kpi label="Toplam Oda" value={stats.total_rooms} color="stone" />
          <Kpi label="Bugün Skorlama" value={stats.scores_today} color="violet" />
          <Kpi label="AI Otomatik Onay" value={stats.auto_approved_today} color="emerald" />
          <Kpi label="Onay Oranı" value={`%${stats.auto_approval_rate}`} color="cyan" />
          <Kpi label="Ort. Skor" value={stats.avg_score_today || "—"} color="sky" />
        </div>
      )}

      <div className="flex justify-between items-center mb-3">
        <div className="text-xs text-stone-500">
          {board?.total || 0} oda yönetimde · 5 durum kolonu
        </div>
        <button onClick={load} className="px-3 py-1 text-xs rounded-md border border-stone-200 text-stone-600 hover:bg-stone-50 inline-flex items-center gap-1.5">
          <ArrowsClockwise size={12} /> Yenile
        </button>
      </div>

      {loading && <div className="text-sm text-stone-400">Yükleniyor…</div>}

      {board && (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3" data-testid="hk-kanban-board">
          {COLUMNS.map((col) => {
            const cards = board.by_state[col.state] || [];
            return (
              <div
                key={col.state}
                className={`${COLOR_BG[col.color]} border-2 rounded-lg p-3`}
                data-testid={`hk-col-${col.state}`}
              >
                <div className={`flex items-center gap-2 ${COLOR_TEXT[col.color]} mb-3`}>
                  <col.Icon size={14} weight="fill" />
                  <div className="text-xs font-bold uppercase tracking-wider">{col.label}</div>
                  <span className="ml-auto text-xs font-mono">{cards.length}</span>
                </div>
                <div className="space-y-2 min-h-[80px]" data-testid={`hk-col-rows-${col.state}`}>
                  {cards.length === 0 ? (
                    <div className="text-[10px] text-stone-400 text-center py-4">—</div>
                  ) : (
                    cards.map((c) => (
                      <button
                        key={c.id}
                        onClick={() => setSelectedRoom(c)}
                        data-testid={`hk-card-${c.room_id}`}
                        className="w-full bg-white border border-stone-200 rounded-md p-2 text-left hover:border-cyan-400 hover:shadow-sm transition-all"
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <div className="text-sm font-bold text-stone-900">Oda {c.room_id}</div>
                            {c.room_type && <div className="text-[9px] text-stone-500">{c.room_type}</div>}
                          </div>
                          {c.last_score !== null && c.last_score !== undefined && (
                            <div className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                              c.last_score >= 90 ? "bg-emerald-100 text-emerald-700" :
                              c.last_score >= 75 ? "bg-cyan-100 text-cyan-700" :
                              c.last_score >= 50 ? "bg-amber-100 text-amber-700" :
                              "bg-rose-100 text-rose-700"
                            }`}>
                              {c.last_score}
                            </div>
                          )}
                        </div>
                        {c.assigned_to && (
                          <div className="text-[9px] text-stone-400 mt-0.5 truncate">
                            👤 {c.assigned_to}
                          </div>
                        )}
                      </button>
                    ))
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {selectedRoom && (
        <RoomActionModal
          card={selectedRoom}
          propertyId={propertyId}
          onClose={() => setSelectedRoom(null)}
          onChanged={() => { load(); }}
        />
      )}
    </div>
  );
}

function Kpi({ label, value, color }) {
  const bg = {
    stone: "bg-stone-100 text-stone-700",
    violet: "bg-violet-50 text-violet-700",
    emerald: "bg-emerald-50 text-emerald-700",
    cyan: "bg-cyan-50 text-cyan-700",
    sky: "bg-sky-50 text-sky-700",
  }[color];
  return (
    <div className={`${bg} border border-stone-100 rounded-lg p-3`}>
      <div className="text-[10px] uppercase tracking-wider opacity-70">{label}</div>
      <div className="text-xl font-semibold mt-1">{value}</div>
    </div>
  );
}

function RoomActionModal({ card, propertyId, onClose, onChanged }) {
  return (
    <div
      className="fixed inset-0 bg-stone-900/50 backdrop-blur-sm z-[9999] flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
        data-testid="hk-modal"
      >
        <div className="p-5 border-b border-stone-100 flex items-center justify-between">
          <div>
            <div className="text-2xl font-bold text-stone-900">Oda {card.room_id}</div>
            <div className="text-xs text-stone-500">{card.room_type || ""}</div>
          </div>
          <button onClick={onClose} data-testid="hk-modal-close" className="w-8 h-8 rounded-full bg-stone-100 hover:bg-stone-200 inline-flex items-center justify-center">
            <XCircle size={14} />
          </button>
        </div>

        <div className="p-5 space-y-4">
          <CurrentStateBlock card={card} />
          {card.state === "vacant_dirty" && <StartCleaningBlock card={card} propertyId={propertyId} onDone={() => { onChanged(); onClose(); }} />}
          {card.state === "needs_rework" && <StartCleaningBlock card={card} propertyId={propertyId} onDone={() => { onChanged(); onClose(); }} rework />}
          {(card.state === "cleaning_in_progress" || card.state === "needs_rework") && (
            <SubmitPhotosBlock card={card} propertyId={propertyId} onDone={() => { onChanged(); onClose(); }} />
          )}
          {card.state === "ai_inspection" && (
            <ManualReviewBlock card={card} propertyId={propertyId} onDone={() => { onChanged(); onClose(); }} />
          )}
          <HistoryBlock history={card.history} />
        </div>
      </div>
    </div>
  );
}

function CurrentStateBlock({ card }) {
  const cur = COLUMNS.find((c) => c.state === card.state);
  return (
    <div className={`${COLOR_BG[cur?.color || "stone"]} border rounded-lg p-3`}>
      <div className="text-[10px] uppercase tracking-wider text-stone-500 mb-1">Mevcut Durum</div>
      <div className={`flex items-center gap-2 ${COLOR_TEXT[cur?.color || "stone"]} font-semibold`}>
        {cur && <cur.Icon size={16} weight="fill" />}
        {cur?.label || card.state}
      </div>
      {card.assigned_to && <div className="text-xs text-stone-600 mt-1">Atanan: {card.assigned_to}</div>}
      {card.last_score !== null && card.last_score !== undefined && (
        <div className="text-xs text-stone-600 mt-1">Son AI Skoru: <b>{card.last_score}</b>/100</div>
      )}
    </div>
  );
}

function StartCleaningBlock({ card, propertyId, onDone, rework = false }) {
  const [busy, setBusy] = useState(false);
  const start = async () => {
    setBusy(true);
    try {
      await axios.post(`${API}/api/hk-turnover/${card.room_id}/start-cleaning?property_id=${propertyId}`, {
        note: rework ? "Yeniden temizlik" : null,
      }, { withCredentials: true });
      toast.success("Temizlik başlatıldı");
      onDone();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Hata");
    } finally {
      setBusy(false);
    }
  };
  return (
    <button
      onClick={start}
      disabled={busy}
      data-testid="hk-start-cleaning"
      className="w-full py-3 rounded-md bg-amber-500 text-white font-semibold hover:bg-amber-600 disabled:opacity-50 inline-flex items-center justify-center gap-2"
    >
      <PlayCircle size={16} weight="fill" />
      {busy ? "Başlatılıyor…" : (rework ? "Yeniden Temizliği Başlat" : "Temizliği Başlat")}
    </button>
  );
}

function SubmitPhotosBlock({ card, propertyId, onDone }) {
  const [photos, setPhotos] = useState([]);
  const [threshold, setThreshold] = useState(75);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const fileRef = useRef();

  const onFiles = (files) => {
    const slots = 3 - photos.length;
    const accepted = Array.from(files).slice(0, slots);
    const reads = accepted.map((f) => new Promise((res, rej) => {
      if (f.size > 4 * 1024 * 1024) { rej(); return; }
      const r = new FileReader();
      r.onload = () => res(r.result);
      r.onerror = () => rej();
      r.readAsDataURL(f);
    }));
    Promise.allSettled(reads).then((rs) => {
      setPhotos([...photos, ...rs.filter((x) => x.status === "fulfilled").map((x) => x.value)]);
    });
  };

  const submit = async () => {
    if (photos.length === 0) { toast.error("En az 1 foto"); return; }
    setBusy(true);
    setResult(null);
    try {
      const r = await axios.post(`${API}/api/hk-turnover/${card.room_id}/submit-photos?property_id=${propertyId}`, {
        photos_base64: photos,
        ai_pass_threshold: parseInt(threshold) || 75,
      }, { withCredentials: true });
      setResult(r.data);
      const decision = r.data.decision === "auto_approved" ? "✅ AI Otomatik Onayladı! Oda satışa açıldı." :
                       r.data.decision === "needs_supervisor_review" ? "⚠️ Süpervizör onayı bekleniyor" :
                       "❌ Yeniden temizlik gerekiyor";
      toast[r.data.decision === "auto_approved" ? "success" : "warning"](decision);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Hata");
    } finally {
      setBusy(false);
    }
  };

  if (result) {
    const isApproved = result.decision === "auto_approved";
    return (
      <div className={`border-2 rounded-lg p-4 ${isApproved ? "border-emerald-300 bg-emerald-50" : "border-amber-300 bg-amber-50"}`} data-testid="hk-submit-result">
        <div className="text-center mb-3">
          <div className={`text-5xl font-bold ${isApproved ? "text-emerald-600" : "text-amber-600"}`}>{result.score}</div>
          <div className="text-xs text-stone-500 mt-1">/ 100 · eşik {threshold}</div>
          <div className={`mt-2 text-sm font-semibold ${isApproved ? "text-emerald-700" : "text-amber-700"}`}>
            {isApproved ? "✅ AI Otomatik Onayladı" : result.decision === "needs_supervisor_review" ? "⚠️ Süpervizör Onayı Bekleniyor" : "❌ Yeniden Temizlik"}
          </div>
        </div>
        {result.issues?.length > 0 && (
          <div>
            <div className="text-[10px] uppercase tracking-wider text-stone-500 mb-1">Sorunlar</div>
            {result.issues.slice(0, 3).map((i, idx) => (
              <div key={idx} className="text-xs text-stone-700 mb-1">• {i}</div>
            ))}
          </div>
        )}
        {result.next_action && (
          <div className="mt-2 bg-white border border-stone-200 rounded-md p-2 text-xs text-stone-700">
            <b>Öneri:</b> {result.next_action}
          </div>
        )}
        <button onClick={onDone} className="w-full mt-3 py-2 rounded-md bg-stone-900 text-white text-sm hover:bg-stone-800">
          Tamam
        </button>
      </div>
    );
  }

  return (
    <div className="border-2 border-dashed border-stone-200 rounded-lg p-4 space-y-3" data-testid="hk-submit-block">
      <div className="flex items-center justify-between">
        <div className="text-sm font-semibold text-stone-800">Fotoğraf Yükle ve AI Skorla</div>
        <div className="text-xs">
          Eşik:
          <input
            type="number"
            min={0}
            max={100}
            value={threshold}
            onChange={(e) => setThreshold(e.target.value)}
            data-testid="hk-threshold"
            className="ml-2 w-14 px-1 py-0.5 text-xs border border-stone-200 rounded text-center"
          />
        </div>
      </div>
      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        multiple
        onChange={(e) => { onFiles(e.target.files); e.target.value = ""; }}
        data-testid="hk-photos-input"
        className="hidden"
      />
      <button
        onClick={() => fileRef.current?.click()}
        disabled={photos.length >= 3}
        data-testid="hk-photos-upload"
        className="w-full py-3 border-2 border-dashed border-stone-300 rounded-md text-sm text-stone-600 hover:border-cyan-400 hover:bg-cyan-50 disabled:opacity-50 inline-flex items-center justify-center gap-2"
      >
        <Camera size={16} />
        {photos.length >= 3 ? "Maksimum 3 foto" : `Foto Ekle (${photos.length}/3)`}
      </button>
      {photos.length > 0 && (
        <div className="grid grid-cols-3 gap-2">
          {photos.map((p, i) => (
            <div key={i} className="relative aspect-square rounded-md overflow-hidden border border-stone-200">
              <img src={p} alt="" className="w-full h-full object-cover" />
              <button
                onClick={() => setPhotos(photos.filter((_, idx) => idx !== i))}
                className="absolute top-1 right-1 w-5 h-5 rounded-full bg-rose-500 text-white text-[10px] inline-flex items-center justify-center"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}
      <button
        onClick={submit}
        disabled={busy || photos.length === 0}
        data-testid="hk-submit-photos"
        className="w-full py-2.5 rounded-md bg-cyan-500 text-white font-semibold hover:bg-cyan-600 disabled:opacity-50 inline-flex items-center justify-center gap-2"
      >
        <Sparkle size={14} weight="fill" />
        {busy ? "AI Düşünüyor…" : "AI ile Skorla & Onayla"}
      </button>
    </div>
  );
}

function ManualReviewBlock({ card, propertyId, onDone }) {
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const decide = async (decision) => {
    setBusy(true);
    try {
      await axios.post(`${API}/api/hk-turnover/${card.room_id}/manual-review?property_id=${propertyId}`, { decision, note }, { withCredentials: true });
      toast.success(decision === "approve" ? "Onaylandı" : "Reddedildi");
      onDone();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Hata");
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="bg-violet-50 border border-violet-200 rounded-lg p-3 space-y-2" data-testid="hk-manual-review">
      <div className="text-sm font-semibold text-violet-900">Süpervizör Kararı</div>
      <div className="text-xs text-violet-700">AI {card.last_score}/100 verdi. Onaylıyor musunuz?</div>
      <input
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="Not (opsiyonel)"
        data-testid="hk-review-note"
        className="w-full px-2 py-1 text-xs border border-violet-200 rounded bg-white"
      />
      <div className="grid grid-cols-2 gap-2">
        <button
          onClick={() => decide("approve")}
          disabled={busy}
          data-testid="hk-review-approve"
          className="py-2 rounded-md bg-emerald-500 text-white text-sm font-semibold hover:bg-emerald-600 disabled:opacity-50 inline-flex items-center justify-center gap-1"
        >
          <CheckCircle size={14} weight="bold" /> Onayla
        </button>
        <button
          onClick={() => decide("reject")}
          disabled={busy}
          data-testid="hk-review-reject"
          className="py-2 rounded-md bg-rose-500 text-white text-sm font-semibold hover:bg-rose-600 disabled:opacity-50 inline-flex items-center justify-center gap-1"
        >
          <XCircle size={14} weight="bold" /> Reddet
        </button>
      </div>
    </div>
  );
}

function HistoryBlock({ history }) {
  if (!history?.length) return null;
  return (
    <div data-testid="hk-history">
      <div className="text-[10px] uppercase tracking-wider text-stone-500 mb-2">Geçmiş</div>
      <div className="space-y-1">
        {history.slice().reverse().slice(0, 10).map((h, i) => (
          <div key={i} className="flex items-center gap-2 text-[11px] text-stone-600">
            <span className="font-mono text-[10px] text-stone-400">{h.at?.slice(11, 16)}</span>
            <span className="px-1 py-0 bg-stone-100 rounded">{h.state}</span>
            {h.score !== undefined && <span className="text-stone-500">skor {h.score}</span>}
            {h.decision && <span className="text-stone-500 italic">{h.decision}</span>}
            <span className="text-stone-400 truncate">{h.by}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
