import { useState, useRef, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Upload, X, Check, Loader2, Trash2, FileSpreadsheet, FileText, FileImage, Plus } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const SOURCE_ICON = {
  excel: FileSpreadsheet,
  csv: FileSpreadsheet,
  pdf: FileText,
  image: FileImage,
};

/**
 * YoYUploadModal — uploads a historical revenue file (PDF/JPG/PNG/XLSX/CSV),
 * lets the operator review/edit the parsed rows in a table, then saves them
 * to feed the Performance Report's YoY comparison.
 */
export const YoYUploadModal = ({ propertyId, onClose, onSaved, cur }) => {
  const fileInputRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [preview, setPreview] = useState(null); // {entries, source_kind, filename}
  const [rows, setRows] = useState([]); // editable copy of entries
  const [saving, setSaving] = useState(false);
  const [existing, setExisting] = useState([]);
  const [loadingExisting, setLoadingExisting] = useState(true);

  // Load any previously saved YoY rows on open
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await axios.get(`${API}/revenue/market-robot/${propertyId}/yoy-history`);
        if (!cancelled) setExisting(r.data.rows || []);
      } catch (e) {
        // non-fatal
      } finally {
        if (!cancelled) setLoadingExisting(false);
      }
    })();
    return () => { cancelled = true; };
  }, [propertyId]);

  const handleFile = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", f);
      const r = await axios.post(
        `${API}/revenue/market-robot/${propertyId}/yoy-upload/preview`,
        form,
        { headers: { "Content-Type": "multipart/form-data" } }
      );
      setPreview(r.data);
      setRows(r.data.entries || []);
      if ((r.data.entries || []).length === 0) {
        toast.warning("Dosyada satır bulunamadı. Lütfen ayları manuel olarak girebilirsiniz.");
      } else {
        toast.success(`${r.data.entries.length} ay verisi okundu — kontrol edip kaydedin.`);
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || "Dosya okunamadı");
    } finally {
      setUploading(false);
      // reset input so the same file can be re-selected
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const updateRow = (idx, key, val) => {
    setRows(prev => prev.map((r, i) => i === idx ? { ...r, [key]: val } : r));
  };

  const removeRow = (idx) => {
    setRows(prev => prev.filter((_, i) => i !== idx));
  };

  const addRow = () => {
    const lastYear = rows.length ? rows[rows.length - 1].year : new Date().getFullYear() - 1;
    setRows(prev => [...prev, { year: lastYear, month: 1, month_key: `${lastYear}-01`, month_label: `Jan ${lastYear}`, revenue: 0 }]);
  };

  const handleSave = async () => {
    const validRows = rows.filter(r => {
      const y = parseInt(r.year, 10);
      const m = parseInt(r.month, 10);
      const rev = parseFloat(r.revenue);
      return Number.isFinite(y) && Number.isFinite(m) && Number.isFinite(rev) &&
             y >= 2000 && y <= 2100 && m >= 1 && m <= 12 && rev > 0;
    });
    if (validRows.length === 0) {
      toast.error("Kaydedilecek geçerli satır yok");
      return;
    }
    setSaving(true);
    try {
      const payload = {
        entries: validRows.map(r => ({
          year: parseInt(r.year, 10),
          month: parseInt(r.month, 10),
          revenue: parseFloat(r.revenue),
        })),
        source_kind: preview?.source_kind || "manual",
      };
      const r = await axios.post(
        `${API}/revenue/market-robot/${propertyId}/yoy-upload/confirm`,
        payload,
      );
      toast.success(`${r.data.saved_count} ay verisi kaydedildi — YoY karşılaştırma güncellendi`);
      if (onSaved) onSaved();
      if (onClose) onClose();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Kayıt başarısız");
    } finally {
      setSaving(false);
    }
  };

  const clearAll = async () => {
    if (!window.confirm("Tüm yüklenmiş geçmiş veriyi silmek istiyor musunuz?")) return;
    try {
      await axios.delete(`${API}/revenue/market-robot/${propertyId}/yoy-history`);
      setExisting([]);
      toast.success("Geçmiş veri silindi");
      if (onSaved) onSaved();
    } catch (e) {
      toast.error("Silme başarısız");
    }
  };

  const SourceIcon = SOURCE_ICON[preview?.source_kind] || FileText;

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4" data-testid="yoy-upload-modal">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-stone-200 flex items-center justify-between bg-gradient-to-r from-indigo-50 to-violet-50">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-indigo-100 rounded-lg flex items-center justify-center">
              <Upload className="w-5 h-5 text-indigo-600" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-stone-900">Geçmiş Yıl Verisi Yükle</h3>
              <p className="text-xs text-stone-500">PDF · JPG · PNG · Excel · CSV — YoY karşılaştırmaya beslenir</p>
            </div>
          </div>
          <button
            onClick={onClose}
            data-testid="yoy-modal-close"
            className="p-2 rounded-lg hover:bg-stone-100 transition-colors"
          >
            <X className="w-5 h-5 text-stone-500" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {/* Existing data summary */}
          {!loadingExisting && existing.length > 0 && (
            <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3 flex items-center justify-between" data-testid="yoy-existing-summary">
              <div className="flex items-center gap-2">
                <Check className="w-4 h-4 text-emerald-600" />
                <span className="text-sm text-emerald-800">
                  <span className="font-bold">{existing.length}</span> ay verisi kayıtlı
                  <span className="text-emerald-600/70 ml-1">(yeni yükleme aynı ayları günceller)</span>
                </span>
              </div>
              <button
                onClick={clearAll}
                data-testid="yoy-clear-all"
                className="text-xs text-rose-600 hover:text-rose-800 flex items-center gap-1 font-bold"
              >
                <Trash2 className="w-3.5 h-3.5" />
                Hepsini sil
              </button>
            </div>
          )}

          {/* Upload zone */}
          {!preview && (
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              data-testid="yoy-upload-dropzone"
              className="w-full border-2 border-dashed border-stone-300 hover:border-indigo-400 rounded-xl py-12 px-4 text-center transition-colors disabled:opacity-50"
            >
              {uploading ? (
                <>
                  <Loader2 className="w-8 h-8 text-indigo-500 mx-auto animate-spin mb-3" />
                  <p className="text-stone-600 font-bold">Dosya işleniyor (OCR/parse)...</p>
                  <p className="text-xs text-stone-400 mt-1">PDF/JPG için OCR birkaç saniye sürer</p>
                </>
              ) : (
                <>
                  <Upload className="w-10 h-10 text-stone-400 mx-auto mb-3" />
                  <p className="text-stone-700 font-bold">Dosya seçin veya buraya tıklayın</p>
                  <p className="text-xs text-stone-500 mt-2">
                    Desteklenen formatlar: <span className="font-mono">.pdf · .jpg · .jpeg · .png · .xlsx · .xls · .csv</span>
                  </p>
                  <p className="text-[11px] text-stone-400 mt-1">Aylık ciro içermeli (Ocak 2025 → 12,450 gibi)</p>
                </>
              )}
            </button>
          )}
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.jpg,.jpeg,.png,.webp,.bmp,.tiff,.xlsx,.xls,.csv"
            className="hidden"
            onChange={handleFile}
            data-testid="yoy-file-input"
          />

          {/* Preview / Edit table */}
          {preview && (
            <div data-testid="yoy-preview-table">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <SourceIcon className="w-4 h-4 text-indigo-500" />
                  <span className="text-sm text-stone-700 font-bold">{preview.filename}</span>
                  <span className="text-[11px] px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700 font-bold">
                    {preview.source_kind.toUpperCase()}
                  </span>
                  <span className="text-xs text-stone-500">· {rows.length} satır</span>
                </div>
                <button
                  onClick={() => { setPreview(null); setRows([]); }}
                  data-testid="yoy-restart"
                  className="text-xs text-stone-500 hover:text-stone-700"
                >
                  Başka dosya seç
                </button>
              </div>
              <div className="border border-stone-200 rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-stone-50 text-stone-600 text-xs uppercase">
                    <tr>
                      <th className="px-3 py-2 text-left">Yıl</th>
                      <th className="px-3 py-2 text-left">Ay</th>
                      <th className="px-3 py-2 text-right">Ciro</th>
                      <th className="px-3 py-2 w-10"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r, idx) => (
                      <tr key={idx} className="border-t border-stone-100 hover:bg-stone-50/60" data-testid={`yoy-row-${idx}`}>
                        <td className="px-3 py-2">
                          <input
                            type="number"
                            value={r.year}
                            onChange={(e) => updateRow(idx, "year", e.target.value)}
                            className="w-20 px-2 py-1 border border-stone-200 rounded text-sm focus:outline-none focus:border-indigo-400"
                          />
                        </td>
                        <td className="px-3 py-2">
                          <select
                            value={r.month}
                            onChange={(e) => updateRow(idx, "month", e.target.value)}
                            className="px-2 py-1 border border-stone-200 rounded text-sm focus:outline-none focus:border-indigo-400"
                          >
                            {["Oca","Şub","Mar","Nis","May","Haz","Tem","Ağu","Eyl","Eki","Kas","Ara"].map((mn, i) => (
                              <option key={i+1} value={i+1}>{mn} ({i+1})</option>
                            ))}
                          </select>
                        </td>
                        <td className="px-3 py-2 text-right">
                          <input
                            type="number"
                            step="0.01"
                            value={r.revenue}
                            onChange={(e) => updateRow(idx, "revenue", e.target.value)}
                            className="w-32 px-2 py-1 border border-stone-200 rounded text-sm text-right focus:outline-none focus:border-indigo-400"
                          />
                          <span className="text-xs text-stone-400 ml-1">{cur ? cur(parseFloat(r.revenue) || 0) : ""}</span>
                        </td>
                        <td className="px-3 py-2">
                          <button
                            onClick={() => removeRow(idx)}
                            data-testid={`yoy-row-remove-${idx}`}
                            className="p-1 rounded hover:bg-rose-100 text-rose-500"
                            title="Sil"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="bg-stone-50 px-3 py-2 border-t border-stone-100">
                  <button
                    onClick={addRow}
                    data-testid="yoy-add-row"
                    className="text-xs text-indigo-600 hover:text-indigo-800 font-bold flex items-center gap-1"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    Manuel satır ekle
                  </button>
                </div>
              </div>
              <p className="text-[11px] text-stone-400 mt-2">
                💡 Yanlış okunan satırları düzeltebilir, fazladan satırları silebilir veya manuel ekleyebilirsiniz.
                Aynı ay için tekrar yükleme önceki değeri günceller.
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-stone-200 flex justify-between items-center gap-3 bg-stone-50">
          <p className="text-xs text-stone-500">
            {preview ? `${rows.length} ay · Kaydetmeden çıkarsanız değişiklikler iptal olur` : "Dosya seçtikten sonra düzenleyebilirsiniz"}
          </p>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              data-testid="yoy-modal-cancel"
              className="px-4 py-2 rounded-lg border border-stone-300 text-stone-700 hover:bg-stone-100 text-sm font-bold"
            >
              İptal
            </button>
            <button
              onClick={handleSave}
              disabled={saving || rows.length === 0}
              data-testid="yoy-modal-save"
              className="px-5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-bold flex items-center gap-2 disabled:opacity-50"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
              {rows.length > 0 ? `${rows.length} satırı kaydet` : "Kaydet"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
