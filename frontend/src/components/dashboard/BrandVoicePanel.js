/**
 * BrandVoicePanel — centralized tone-of-voice studio.
 *
 * Two columns:
 *  - Left: Brand voice profile editor (tone, traits, dos/donts, samples, sign-off)
 *  - Right: Live preview / generate panel — pick a purpose, paste context, preview
 *
 * On save, profile is persisted. Generate creates a record in history.
 */
import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Megaphone, Sparkle, FloppyDisk, Eye, X, ClockCounterClockwise } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/brand-voice`;

export default function BrandVoicePanel({ propertyId }) {
  const [profile, setProfile] = useState(null);
  const [purposes, setPurposes] = useState([]);
  const [purpose, setPurpose] = useState("email_pre_arrival");
  const [context, setContext] = useState(
    "Misafir: Ahmet Yılmaz · 3 Temmuz - 6 Temmuz, deluxe oda, ailesi ile · sürpriz balayı yıldönümü"
  );
  const [output, setOutput] = useState("");
  const [previewMode, setPreviewMode] = useState(false);
  const [busy, setBusy] = useState(false);
  const [history, setHistory] = useState([]);
  const [tagInput, setTagInput] = useState("");
  const [doInput, setDoInput] = useState("");
  const [dontInput, setDontInput] = useState("");
  const [sampleInput, setSampleInput] = useState("");

  const reload = useCallback(async () => {
    if (!propertyId) return;
    try {
      const p = await axios.get(`${API}/profile/${propertyId}`, { withCredentials: true });
      setProfile(p.data);
      const pp = await axios.get(`${API}/purposes`, { withCredentials: true });
      setPurposes(pp.data.items || []);
      const h = await axios.get(`${API}/history/${propertyId}?limit=20`, { withCredentials: true });
      setHistory(h.data.items || []);
    } catch (e) { toast.error("Yüklenemedi"); }
  }, [propertyId]);

  useEffect(() => { reload(); }, [reload]);

  async function saveProfile() {
    try {
      await axios.post(`${API}/profile/${propertyId}`, profile, { withCredentials: true });
      toast.success("Marka sesi kaydedildi");
    } catch (e) { toast.error("Kaydedilemedi"); }
  }

  async function doPreview() {
    setBusy(true); setOutput("");
    try {
      const r = await axios.post(`${API}/preview`,
        { profile, purpose, context }, { withCredentials: true });
      setOutput(r.data.preview);
      setPreviewMode(true);
    } catch (e) { toast.error("Önizleme başarısız"); }
    finally { setBusy(false); }
  }

  async function doGenerate() {
    setBusy(true); setOutput("");
    try {
      const r = await axios.post(`${API}/generate`,
        { property_id: propertyId, purpose, context }, { withCredentials: true });
      setOutput(r.data.output);
      setPreviewMode(false);
      toast.success("Üretildi ve geçmişe kaydedildi");
      reload();
    } catch (e) { toast.error("Üretim başarısız"); }
    finally { setBusy(false); }
  }

  if (!profile) {
    return <div className="p-10 text-center text-stone-400 text-sm">Yükleniyor…</div>;
  }

  function addToList(field, value, setter) {
    if (!value.trim()) return;
    setProfile({...profile, [field]: [...(profile[field]||[]), value.trim()]});
    setter("");
  }
  function removeFromList(field, idx) {
    setProfile({...profile, [field]: profile[field].filter((_, i) => i !== idx)});
  }

  return (
    <div className="p-5 max-w-[1600px] mx-auto" data-testid="brand-voice-panel">
      <div className="mb-5">
        <div className="text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">Brand Voice Studio</div>
        <h2 className="text-2xl font-semibold text-stone-900 inline-flex items-center gap-2">
          <Megaphone size={22} weight="fill" className="text-rose-600" /> Marka Sesi Stüdyosu
        </h2>
        <p className="text-sm text-stone-500 mt-1">
          Otelin ton-of-voice'unu tek noktadan yönet. Email, yorum yanıtı, sosyal caption ve video prompt — hepsi aynı sesle üretilir.
        </p>
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        {/* Profile editor */}
        <div className="bg-white border border-stone-200 rounded-xl p-4">
          <h3 className="text-sm font-semibold mb-3">Marka Sesi Profili</h3>

          <Inp label="Genel Ton" v={profile.tone}
               onChange={v => setProfile({...profile, tone: v})}
               testId="bv-tone-input"
               help="Örn: warm_luxury, formal_classic, playful_friendly, modern_minimal" />

          <ListField
            label="Kişilik Özellikleri"
            items={profile.personality_traits || []}
            input={tagInput} onChangeInput={setTagInput}
            onAdd={() => addToList("personality_traits", tagInput, setTagInput)}
            onRemove={idx => removeFromList("personality_traits", idx)}
            testIdPrefix="bv-trait"
            placeholder="örn. zarif, sıcak, detaycı..."
            tagColor="rose"
          />

          <ListField
            label="✓ YAPILMASI Gerekenler"
            items={profile.dos || []}
            input={doInput} onChangeInput={setDoInput}
            onAdd={() => addToList("dos", doInput, setDoInput)}
            onRemove={idx => removeFromList("dos", idx)}
            testIdPrefix="bv-do"
            placeholder="örn. Misafire ismiyle hitap et"
            tagColor="emerald"
          />

          <ListField
            label="✗ YAPILMAMASI Gerekenler"
            items={profile.donts || []}
            input={dontInput} onChangeInput={setDontInput}
            onAdd={() => addToList("donts", dontInput, setDontInput)}
            onRemove={idx => removeFromList("donts", idx)}
            testIdPrefix="bv-dont"
            placeholder="örn. Aşırı ünlem işareti kullanma"
            tagColor="rose"
          />

          <ListField
            label="Örnek Cümleler (ton referansı)"
            items={profile.sample_sentences || []}
            input={sampleInput} onChangeInput={setSampleInput}
            onAdd={() => addToList("sample_sentences", sampleInput, setSampleInput)}
            onRemove={idx => removeFromList("sample_sentences", idx)}
            testIdPrefix="bv-sample"
            placeholder="örn. Antalya'nın güneşli sabahı sizin için hazır..."
            tagColor="stone"
          />

          <label className="block mt-3">
            <span className="text-xs font-medium text-stone-700">İmza</span>
            <textarea value={profile.sign_off||""} rows={2}
                      onChange={e => setProfile({...profile, sign_off: e.target.value})}
                      data-testid="bv-signoff-input"
                      className="w-full px-3 py-1.5 text-sm border border-stone-300 rounded-lg mt-1" />
          </label>

          <button onClick={saveProfile} data-testid="bv-save-btn"
                  className="w-full mt-4 py-2 text-sm font-medium bg-stone-900 text-white rounded-lg hover:bg-stone-800 inline-flex items-center justify-center gap-1.5">
            <FloppyDisk size={13} weight="fill" /> Profili Kaydet
          </button>
        </div>

        {/* Live preview + generate */}
        <div className="bg-white border border-stone-200 rounded-xl p-4">
          <h3 className="text-sm font-semibold mb-3 inline-flex items-center gap-1.5">
            <Sparkle size={14} weight="fill" className="text-rose-600" /> Canlı Önizleme & Üretim
          </h3>

          <label className="block mb-2">
            <span className="text-xs font-medium text-stone-700">Amaç</span>
            <select value={purpose} onChange={e => setPurpose(e.target.value)}
                    data-testid="bv-purpose-select"
                    className="w-full px-3 py-1.5 text-sm border border-stone-300 rounded-lg mt-1">
              {purposes.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
            </select>
          </label>

          <label className="block mb-3">
            <span className="text-xs font-medium text-stone-700">Bağlam</span>
            <textarea value={context} rows={3}
                      onChange={e => setContext(e.target.value)}
                      data-testid="bv-context-input"
                      placeholder="Misafir adı, tarih, durum, özel notlar..."
                      className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg mt-1" />
          </label>

          <div className="flex gap-2 mb-3">
            <button onClick={doPreview} disabled={busy} data-testid="bv-preview-btn"
                    className="flex-1 py-2 text-xs font-medium bg-stone-100 text-stone-700 rounded-lg hover:bg-stone-200 disabled:opacity-50 inline-flex items-center justify-center gap-1.5">
              <Eye size={12} /> {busy && previewMode ? "..." : "Önizle (kaydetmeden)"}
            </button>
            <button onClick={doGenerate} disabled={busy} data-testid="bv-generate-btn"
                    className="flex-1 py-2 text-xs font-medium bg-rose-600 text-white rounded-lg hover:bg-rose-700 disabled:opacity-50 inline-flex items-center justify-center gap-1.5">
              <Sparkle size={12} weight="fill" /> {busy && !previewMode ? "..." : "Üret & Kaydet"}
            </button>
          </div>

          {output && (
            <div className={`p-3 rounded-lg border text-sm whitespace-pre-line ${
              previewMode ? "bg-stone-50 border-stone-200" : "bg-rose-50 border-rose-200"
            }`} data-testid="bv-output">
              {output}
            </div>
          )}

          {history.length > 0 && (
            <div className="mt-5">
              <h4 className="text-xs font-semibold text-stone-700 mb-2 inline-flex items-center gap-1">
                <ClockCounterClockwise size={12} /> Son Üretimler
              </h4>
              <div className="space-y-1 max-h-60 overflow-y-auto">
                {history.slice(0, 10).map(h => (
                  <button key={h.id}
                          onClick={() => { setOutput(h.output); setPreviewMode(false); setPurpose(h.purpose); setContext(h.context_input); }}
                          className="w-full text-left p-2 text-xs hover:bg-stone-50 rounded border border-stone-100">
                    <div className="font-medium text-stone-700">{h.purpose_label}</div>
                    <div className="text-stone-500 truncate">{h.output?.slice(0, 100)}…</div>
                    <div className="text-[10px] text-stone-400">{h.generated_at?.slice(0, 16).replace("T", " ")}</div>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Inp({ label, v, onChange, testId, help }) {
  return (
    <label className="block mb-3">
      <span className="text-xs font-medium text-stone-700">{label}</span>
      <input value={v||""} onChange={e => onChange(e.target.value)}
             data-testid={testId}
             className="w-full px-3 py-1.5 text-sm border border-stone-300 rounded-lg mt-1" />
      {help && <span className="text-[10px] text-stone-400">{help}</span>}
    </label>
  );
}

function ListField({ label, items, input, onChangeInput, onAdd, onRemove, testIdPrefix, placeholder, tagColor }) {
  const colorMap = {
    rose: "bg-rose-100 text-rose-700",
    emerald: "bg-emerald-100 text-emerald-700",
    stone: "bg-stone-100 text-stone-700",
  };
  return (
    <div className="mb-3">
      <span className="text-xs font-medium text-stone-700 block mb-1">{label}</span>
      <div className="flex flex-wrap gap-1 mb-1">
        {items.map((it, i) => (
          <span key={i} className={`text-[11px] px-2 py-0.5 rounded inline-flex items-center gap-1 ${colorMap[tagColor]}`}
                data-testid={`${testIdPrefix}-${i}`}>
            {it}
            <button onClick={() => onRemove(i)} className="opacity-60 hover:opacity-100">
              <X size={10} weight="bold" />
            </button>
          </span>
        ))}
      </div>
      <div className="flex gap-1">
        <input value={input} onChange={e => onChangeInput(e.target.value)}
               onKeyDown={e => e.key === "Enter" && (e.preventDefault(), onAdd())}
               placeholder={placeholder}
               data-testid={`${testIdPrefix}-input`}
               className="flex-1 px-2 py-1 text-xs border border-stone-300 rounded" />
        <button onClick={onAdd} data-testid={`${testIdPrefix}-add`}
                className="text-xs px-2 py-1 bg-stone-100 rounded hover:bg-stone-200">+</button>
      </div>
    </div>
  );
}
