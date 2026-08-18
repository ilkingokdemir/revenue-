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
  const [preview, setPreview] = useState(null); // {entries, source_kind, filename, expenses}
  const [rows, setRows] = useState([]); // editable income rows
  const [expenseRows, setExpenseRows] = useState([]); // editable expense rows
  const [saving, setSaving] = useState(false);
  const [existing, setExisting] = useState([]);
  const [existingExpenses, setExistingExpenses] = useState([]);
  const [loadingExisting, setLoadingExisting] = useState(true);
  const [categories, setCategories] = useState([
    "Kira", "Komisyon", "Vergi", "Personel", "Temizlik", "Bakım & Onarım",
    "Enerji & Su", "İnternet & İletişim", "Pazarlama", "Sigorta",
    "Belediye/Council", "Yiyecek & İçecek", "Yönetim & Ofis",
    "Yazılım & Abonelik", "Banka & Komisyon Ücretleri", "Diğer",
  ]);
  const [parseFailedFile, setParseFailedFile] = useState(null);
  const [saveSuccess, setSaveSuccess] = useState(null); // {rows, expenses} after save

  // Download a ready-to-use CSV template so users have a known-good format.
  const downloadTemplate = () => {
    const yr = new Date().getFullYear() - 1;
    const csv = [
      "month,revenue",
      ...Array.from({ length: 12 }, (_, i) => `${yr}-${String(i + 1).padStart(2, "0")},0`),
    ].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `yoy_template_${yr}.csv`; a.click();
    URL.revokeObjectURL(url);
  };

  // Fetch canonical category list from backend once
  useEffect(() => {
    let cancelled = false;
    axios.get(`${API}/revenue/market-robot/expense-categories`).then(r => {
      if (!cancelled && r.data?.categories?.length) setCategories(r.data.categories);
    }).catch(() => {});
    return () => { cancelled = true; };
  }, []);

  // Load any previously saved YoY rows + expenses on open
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await axios.get(`${API}/revenue/market-robot/${propertyId}/yoy-history`);
        if (!cancelled) {
          setExisting(r.data.rows || []);
          setExistingExpenses(r.data.expenses || []);
          // If user already has saved expenses, pre-populate the editor so
          // they're shown alongside any newly parsed file (and so the user
          // doesn't have to re-enter them when uploading a new revenue file).
          if (r.data.expenses && r.data.expenses.length > 0) {
            setExpenseRows(r.data.expenses.map(x => ({
              label: x.label, amount: x.amount, period: x.period || "annual",
              category: x.category || "Diğer",
            })));
          }
        }
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
      // Merge parsed expenses with any existing ones (parsed take priority by label)
      const parsedExp = r.data.expenses || [];
      if (parsedExp.length > 0) {
        setExpenseRows(prev => {
          const byLabel = new Map(prev.map(x => [x.label.toLowerCase(), x]));
          for (const x of parsedExp) {
            byLabel.set(x.label.toLowerCase(), {
              label: x.label, amount: x.amount,
              period: x.period || "annual",
              category: x.category || "Diğer",
            });
          }
          return Array.from(byLabel.values());
        });
      }
      const incCount = (r.data.entries || []).length;
      const expCount = parsedExp.length;
      if (incCount === 0 && expCount === 0) {
        setParseFailedFile(f.name);
        toast.warning(`'${f.name}' dosyasından satır okunamadı — format kontrol edin veya manuel ekleyin.`, { duration: 6000 });
      } else {
        setParseFailedFile(null);
        toast.success(`${incCount} ay + ${expCount} gider kalemi okundu — kontrol edip kaydedin.`);
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

  // Expense row management
  const updateExp = (idx, key, val) => {
    setExpenseRows(prev => prev.map((r, i) => i === idx ? { ...r, [key]: val } : r));
  };
  const removeExp = (idx) => {
    setExpenseRows(prev => prev.filter((_, i) => i !== idx));
  };
  const addExp = () => {
    setExpenseRows(prev => [...prev, { label: "", amount: 0, period: "annual", category: "Diğer" }]);
  };

  const handleSave = async () => {
    const validRows = rows.filter(r => {
      const y = parseInt(r.year, 10);
      const m = parseInt(r.month, 10);
      const rev = parseFloat(r.revenue);
      return Number.isFinite(y) && Number.isFinite(m) && Number.isFinite(rev) &&
             y >= 2000 && y <= 2100 && m >= 1 && m <= 12 && rev > 0;
    });
    const validExpenses = expenseRows.filter(x => {
      const amt = parseFloat(x.amount);
      return x.label && x.label.toString().trim().length > 0 &&
             Number.isFinite(amt) && amt > 0 &&
             ["annual", "monthly"].includes((x.period || "annual").toLowerCase());
    });
    if (validRows.length === 0 && validExpenses.length === 0) {
      toast.error("Kaydedilecek veri yok (gelir veya gider satırı ekleyin)");
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
        expenses: validExpenses.map(x => ({
          label: x.label.toString().trim(),
          amount: parseFloat(x.amount),
          period: (x.period || "annual").toLowerCase(),
          category: (x.category || "Diğer").toString(),
        })),
        source_kind: preview?.source_kind || "manual",
        replace_expenses: true,
      };
      const r = await axios.post(
        `${API}/revenue/market-robot/${propertyId}/yoy-upload/confirm`,
        payload,
      );
      toast.success(`✅ Kaydedildi · ${r.data.saved_count} ay gelir + ${r.data.saved_expenses} gider`, {
        description: "Performance Report'ta Yıllık Net Kâr ve Kategori Dağılımı güncellendi.",
        duration: 5000,
      });
      // Show full-screen success overlay for 1.8s before closing the modal so
      // the operator gets unmistakable confirmation (toasts get missed).
      setSaveSuccess({ rows: r.data.saved_count, expenses: r.data.saved_expenses });
      if (onSaved) onSaved();
      setTimeout(() => {
        if (onClose) onClose();
      }, 1800);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Kayıt başarısız");
    } finally {
      setSaving(false);
    }
  };

  const clearAll = async () => {
    if (!window.confirm("Tüm yüklenmiş geçmiş veriyi (gelir + gider) silmek istiyor musunuz?")) return;
    try {
      await Promise.all([
        axios.delete(`${API}/revenue/market-robot/${propertyId}/yoy-history`),
        axios.delete(`${API}/revenue/market-robot/${propertyId}/yoy-expenses`),
      ]);
      setExisting([]);
      setExistingExpenses([]);
      setExpenseRows([]);
      toast.success("Geçmiş veri silindi");
      if (onSaved) onSaved();
    } catch (e) {
      toast.error("Silme başarısız");
    }
  };

  const SourceIcon = SOURCE_ICON[preview?.source_kind] || FileText;

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4" data-testid="yoy-upload-modal">
      {/* Full-screen success overlay — shown for 1.8s after save before modal closes */}
      {saveSuccess && (
        <div
          className="absolute inset-0 z-10 bg-emerald-600/95 backdrop-blur-sm flex items-center justify-center animate-in fade-in duration-200"
          data-testid="yoy-save-success-overlay"
        >
          <div className="text-center text-white px-8">
            <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-white/20 mb-4 animate-in zoom-in duration-300">
              <Check className="w-12 h-12 text-white stroke-[3]" />
            </div>
            <h2 className="text-3xl font-black mb-2">Kaydedildi!</h2>
            <p className="text-lg font-bold text-emerald-50">
              {saveSuccess.rows} ay gelir + {saveSuccess.expenses} gider
            </p>
            <p className="text-sm text-emerald-100/90 mt-2">
              Performance Report otomatik güncellendi — YoY karşılaştırma ve Net Kâr şeridi görünecek.
            </p>
          </div>
        </div>
      )}
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
                  <span className="font-bold">{existing.length}</span> ay gelir +{" "}
                  <span className="font-bold">{existingExpenses.length}</span> gider kayıtlı
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

          {/* Upload zone — show smaller version after first interaction */}
          {!preview && rows.length === 0 && expenseRows.length === 0 && (
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              data-testid="yoy-upload-dropzone"
              className="w-full border-2 border-dashed border-stone-300 hover:border-indigo-400 rounded-xl py-8 px-4 text-center transition-colors disabled:opacity-50"
            >
              {uploading ? (
                <>
                  <Loader2 className="w-8 h-8 text-indigo-500 mx-auto animate-spin mb-3" />
                  <p className="text-stone-600 font-bold">Dosya işleniyor (OCR/parse)...</p>
                </>
              ) : (
                <>
                  <Upload className="w-8 h-8 text-stone-400 mx-auto mb-2" />
                  <p className="text-stone-700 font-bold text-sm">Dosya seç (PDF · JPG · Excel · CSV)</p>
                  <p className="text-[11px] text-stone-400 mt-1">veya aşağıdan manuel ekleyebilirsiniz</p>
                </>
              )}
            </button>
          )}
          {/* Parser failed → prominent guidance banner */}
          {parseFailedFile && (
            <div className="bg-amber-50 border-2 border-amber-300 rounded-lg p-4" data-testid="yoy-parse-failed-banner">
              <div className="flex items-start gap-3">
                <div className="text-2xl leading-none">⚠️</div>
                <div className="flex-1">
                  <p className="text-sm font-bold text-amber-900">
                    "{parseFailedFile}" dosyasından geçerli satır bulunamadı
                  </p>
                  <p className="text-xs text-amber-800 mt-1.5">
                    Parser şu formatları bekliyor:
                  </p>
                  <ul className="text-[11px] text-amber-800 mt-1 ml-4 list-disc space-y-0.5">
                    <li>Ay kolonu: <code className="bg-amber-100 px-1 rounded">2024-01</code>, <code className="bg-amber-100 px-1 rounded">Jan 2024</code>, <code className="bg-amber-100 px-1 rounded">Ocak 2024</code>, <code className="bg-amber-100 px-1 rounded">01/2024</code></li>
                    <li>Gelir kolonu: pozitif sayı (örn. <code className="bg-amber-100 px-1 rounded">12345.67</code>, <code className="bg-amber-100 px-1 rounded">£12.345,67</code>)</li>
                    <li>Excel/CSV → ilk sütun ay, ikinci sütun gelir önerilir</li>
                  </ul>
                  <div className="mt-3 flex items-center gap-2 flex-wrap">
                    <button
                      onClick={downloadTemplate}
                      data-testid="yoy-download-template"
                      className="text-xs px-2.5 py-1 bg-amber-600 hover:bg-amber-700 text-white rounded font-bold inline-flex items-center gap-1"
                    >
                      <Upload className="w-3 h-3 rotate-180" />
                      CSV Şablonu İndir
                    </button>
                    <button
                      onClick={() => { setParseFailedFile(null); fileInputRef.current?.click(); }}
                      data-testid="yoy-retry-upload"
                      className="text-xs px-2.5 py-1 bg-white hover:bg-amber-100 text-amber-900 rounded font-bold border border-amber-300 inline-flex items-center gap-1"
                    >
                      Tekrar Yükle
                    </button>
                    <span className="text-[11px] text-amber-700/80">veya aşağıdan manuel ekleyin →</span>
                  </div>
                </div>
                <button
                  onClick={() => setParseFailedFile(null)}
                  data-testid="yoy-parse-failed-dismiss"
                  className="p-1 rounded hover:bg-amber-100"
                  title="Kapat"
                >
                  <X className="w-4 h-4 text-amber-700" />
                </button>
              </div>
            </div>
          )}
          {/* Smaller add-file button when tables are already populated */}
          {!preview && (rows.length > 0 || expenseRows.length > 0) && (
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              data-testid="yoy-upload-add-file"
              className="w-full border border-dashed border-stone-300 hover:border-indigo-400 rounded-lg py-2.5 px-4 text-xs text-stone-600 font-bold transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {uploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
              {uploading ? "İşleniyor..." : "Dosyadan içe aktar (PDF / JPG / Excel / CSV)"}
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

          {/* Income table — always rendered so users can add monthly revenue
              rows manually without uploading a file. */}
          <div data-testid="yoy-preview-table">
            {preview && (
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <SourceIcon className="w-4 h-4 text-indigo-500" />
                  <span className="text-sm text-stone-700 font-bold">{preview.filename}</span>
                  <span className="text-[11px] px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700 font-bold">
                    {preview.source_kind.toUpperCase()}
                  </span>
                  <span className="text-xs text-stone-500">· {rows.length} ay · {expenseRows.length} gider</span>
                </div>
                <button
                  onClick={() => { setPreview(null); setRows([]); }}
                  data-testid="yoy-restart"
                  className="text-xs text-stone-500 hover:text-stone-700"
                >
                  Dosyayı kaldır
                </button>
              </div>
            )}
            <p className="text-xs font-bold text-stone-600 uppercase mb-2">💰 Aylık Gelirler</p>
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
                              <option key={i+1} value={i+1}>{`${mn} (${i+1})`}</option>
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
                    {rows.length === 0 && (
                      <tr>
                        <td colSpan={4} className="px-3 py-6 text-center text-xs text-stone-400">
                          Henüz aylık gelir satırı yok — alttan "Manuel satır ekle" ile başlayın veya dosya yükleyin.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
                <div className="bg-stone-50 px-3 py-2 border-t border-stone-100">
                  <button
                    onClick={addRow}
                    data-testid="yoy-add-row"
                    className="text-xs text-indigo-600 hover:text-indigo-800 font-bold flex items-center gap-1"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    Manuel gelir satırı ekle
                  </button>
                </div>
              </div>
              <p className="text-[11px] text-stone-400 mt-2 mb-4">
                💡 Yanlış okunan satırları düzeltebilir, fazladan satırları silebilir veya manuel ekleyebilirsiniz.
                Aynı ay için tekrar yükleme önceki değeri günceller.
              </p>
            </div>

          {/* Expense table — always editable */}
          <div data-testid="yoy-expense-table">
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs font-bold text-stone-600 uppercase">💸 Yıllık Gider Kalemleri</p>
                {(() => {
                  const totalAnnual = expenseRows.reduce((sum, x) => {
                    const a = parseFloat(x.amount) || 0;
                    return sum + (String(x.period).toLowerCase() === "monthly" ? a * 12 : a);
                  }, 0);
                  const totalRev = rows.reduce((sum, r) => sum + (parseFloat(r.revenue) || 0), 0);
                  const net = totalRev - totalAnnual;
                  if (totalAnnual === 0 && totalRev === 0) return null;
                  return (
                    <div className="text-[11px] text-stone-500 flex items-center gap-3" data-testid="yoy-net-summary">
                      <span>Gelir: <span className="font-bold text-emerald-600">{cur ? cur(totalRev) : totalRev.toFixed(0)}</span></span>
                      <span>Gider: <span className="font-bold text-rose-600">{cur ? cur(totalAnnual) : totalAnnual.toFixed(0)}</span></span>
                      <span>Net: <span className={`font-black ${net >= 0 ? "text-indigo-600" : "text-rose-600"}`}>{cur ? cur(net) : net.toFixed(0)}</span></span>
                    </div>
                  );
                })()}
              </div>
              <div className="border border-stone-200 rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-stone-50 text-stone-600 text-xs uppercase">
                    <tr>
                      <th className="px-3 py-2 text-left">Kalem</th>
                      <th className="px-3 py-2 text-left w-44">Kategori</th>
                      <th className="px-3 py-2 text-right">Tutar</th>
                      <th className="px-3 py-2 text-left w-24">Periyot</th>
                      <th className="px-3 py-2 w-10"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {expenseRows.map((x, idx) => (
                      <tr key={idx} className="border-t border-stone-100 hover:bg-stone-50/60" data-testid={`yoy-exp-row-${idx}`}>
                        <td className="px-3 py-2">
                          <input
                            type="text"
                            value={x.label}
                            onChange={(e) => updateExp(idx, "label", e.target.value)}
                            placeholder="Rent, Komisyon, Council, Temizlik..."
                            className="w-full px-2 py-1 border border-stone-200 rounded text-sm focus:outline-none focus:border-indigo-400"
                          />
                        </td>
                        <td className="px-3 py-2">
                          <select
                            value={x.category || "Diğer"}
                            onChange={(e) => updateExp(idx, "category", e.target.value)}
                            data-testid={`yoy-exp-category-${idx}`}
                            className="w-full px-2 py-1 border border-stone-200 rounded text-sm focus:outline-none focus:border-indigo-400"
                          >
                            {categories.map(c => <option key={c} value={c}>{c}</option>)}
                          </select>
                        </td>
                        <td className="px-3 py-2 text-right">
                          <input
                            type="number"
                            step="0.01"
                            value={x.amount}
                            onChange={(e) => updateExp(idx, "amount", e.target.value)}
                            className="w-32 px-2 py-1 border border-stone-200 rounded text-sm text-right focus:outline-none focus:border-indigo-400"
                          />
                          <span className="text-xs text-stone-400 ml-1">{cur ? cur(parseFloat(x.amount) || 0) : ""}</span>
                        </td>
                        <td className="px-3 py-2">
                          <select
                            value={x.period || "annual"}
                            onChange={(e) => updateExp(idx, "period", e.target.value)}
                            className="px-2 py-1 border border-stone-200 rounded text-sm focus:outline-none focus:border-indigo-400"
                          >
                            <option value="annual">Yıllık</option>
                            <option value="monthly">Aylık</option>
                          </select>
                        </td>
                        <td className="px-3 py-2">
                          <button
                            onClick={() => removeExp(idx)}
                            data-testid={`yoy-exp-remove-${idx}`}
                            className="p-1 rounded hover:bg-rose-100 text-rose-500"
                            title="Sil"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      </tr>
                    ))}
                    {expenseRows.length === 0 && (
                      <tr>
                        <td colSpan={5} className="px-3 py-6 text-center text-xs text-stone-400">
                          Henüz gider satırı yok — alttan "Manuel gider ekle" ile başlayın veya bir dosya yükleyin.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
                <div className="bg-stone-50 px-3 py-2 border-t border-stone-100">
                  <button
                    onClick={addExp}
                    data-testid="yoy-add-expense"
                    className="text-xs text-indigo-600 hover:text-indigo-800 font-bold flex items-center gap-1"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    Manuel gider ekle
                  </button>
                </div>
              </div>
              <p className="text-[11px] text-stone-400 mt-2">
                💡 "Yıllık" seçimi bu kalemin yılda toplam tutarı olduğunu söyler. "Aylık" seçilirse 12 ile çarpılıp yıllığa çevrilir.
              </p>
            </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-stone-200 flex justify-between items-center gap-3 bg-stone-50">
          <p className="text-xs text-stone-500">
            {(rows.length > 0 || expenseRows.length > 0)
              ? `${rows.length} gelir ay · ${expenseRows.length} gider kalemi`
              : "Aşağıdan manuel ekleyebilir veya dosya yükleyebilirsiniz"}
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
              disabled={saving || (rows.length === 0 && expenseRows.length === 0)}
              data-testid="yoy-modal-save"
              className="px-5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-bold flex items-center gap-2 disabled:opacity-50"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
              Kaydet
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
