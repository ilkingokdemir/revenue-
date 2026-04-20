import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import { QRCodeSVG } from "qrcode.react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger,
  DialogFooter, DialogDescription,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import {
  RefreshCw, Plus, Send, Package, FileText, Shirt, CheckCircle2,
  Trash2, ArrowDown, Building2, Inbox, DoorOpen, BarChart3, AlertCircle,
  Calendar, FileBarChart, ShieldCheck, RotateCcw, Download, Sparkles,
  TrendingUp, QrCode, Printer, Mail, FileSpreadsheet, Camera,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const TABS = [
  { id: "dispatch",  label: "Dispatch",  icon: Send,     color: "bg-orange-500",  subtitle: "Send to laundry" },
  { id: "deliveries",label: "Deliveries",icon: Inbox,    color: "bg-emerald-500", subtitle: "Receive from laundry" },
  { id: "forecast",  label: "Next Order", icon: Sparkles, color: "bg-fuchsia-500", subtitle: "Forecast & order" },
  { id: "usage",     label: "Daily Usage",icon: DoorOpen, color: "bg-blue-500",   subtitle: "Room collections" },
  { id: "stock",     label: "Stock",      icon: Package, color: "bg-violet-500",  subtitle: "Inventory levels" },
  { id: "contracts", label: "Contracts",  icon: FileText, color: "bg-stone-500",  subtitle: "Vendor agreements" },
];

const REPORTS = [
  { id: "daily-usage",   label: "Daily Usage Report",  desc: "Room-wise daily usage breakdown",     icon: FileText,     color: "bg-blue-100 text-blue-600" },
  { id: "count",         label: "Count Report",        desc: "Aggregated usage with anomalies",     icon: BarChart3,    color: "bg-emerald-100 text-emerald-600" },
  { id: "order",         label: "Order Report",        desc: "Order vs Received comparison",        icon: Package,      color: "bg-violet-100 text-violet-600" },
  { id: "dispatch",      label: "Dispatch Report",     desc: "Dirty send with date ranges",         icon: Send,         color: "bg-amber-100 text-amber-600" },
  { id: "monthly-audit", label: "Monthly Audit",       desc: "End of month audit report",           icon: ShieldCheck,  color: "bg-red-100 text-red-600" },
  { id: "group-update",  label: "Group Update",        desc: "Rolling cycle ledger",                icon: RotateCcw,    color: "bg-indigo-100 text-indigo-600" },
];

const DISPATCH_STATUS_STYLE = {
  pending:  "bg-stone-100 text-stone-600",
  sent:     "bg-amber-100 text-amber-700",
  received: "bg-emerald-100 text-emerald-700",
  invoiced: "bg-blue-100 text-blue-700",
  paid:     "bg-violet-100 text-violet-700",
};

// i18n — scoped to this module (housekeeper-facing copy). Persist choice in localStorage.
const LAUNDRY_I18N = {
  en: {
    label: "English", flag: "🇬🇧",
    // Shared
    date: "Date", room: "Room", vendor: "Vendor", notes: "Notes (optional)", notesPh: "Additional notes…",
    submit: "Submit & Confirm", cancel: "Cancel", totals: "Totals", item: "Item",
    used: "Used", collected: "Collected", unusable: "Broken (from factory)", damaged: "Damaged (from room)",
    // Usage
    title: "New Daily Laundry Usage",
    subtitle: "Pick the room, then enter numbers for each linen. You don't need to select items — all items are pre-listed.",
    selectRoom: "Select room", roomPlaceholder: "Room number (e.g. 204)",
    usedHint: "clean → room", collectedHint: "room → laundry", unusableHint: "returned bad from factory", damagedHint: "guest write-off",
    saved: "Saved", fillRoom: "Pick a room first", fillQty: "Enter at least one quantity > 0",
    newBtn: "New Daily Laundry Usage", loading: "Loading items…",
    // Dispatch
    dispTitle: "New Dispatch · Send to Factory", dispSubtitle: "Enter dirty pieces & unusable pieces being sent back. Factory will count them on arrival.",
    dispDirtySent: "Dirty Sent", dispUnusableSent: "Broken (from factory) Sent",
    dispDirtyHint: "to wash", dispUnusableHint: "write-off pieces returned",
    dispRate: "Rate £", dispLineTotal: "Line £", dispExpectedReturn: "Expected Return",
    dispAutofill: "Auto-fill from stock (dirty+damaged)", dispNewBtn: "New Dispatch",
    dispSaved: "Dispatch sent",
    // Delivery / Receive
    delvTitle: "Receive Delivery · Count on Arrival", delvSubtitle: "Count every piece delivered. Enter Received + any Shortage / Damaged on arrival.",
    delvSent: "Sent", delvReceived: "Received", delvShortage: "Shortage", delvDamagedArr: "Damaged",
    delvReceivedHint: "good pieces arrived", delvShortageHint: "missing pieces", delvDamagedHint: "bad pieces on arrival",
    delvReceived2: "Receive", delvSaved: "Delivery received",
    // Broken (from factory) vs Damaged (from room) — origin-aware labels
    factoryBroken: "Broken (from factory)", factoryBrokenShort: "Broken",
    factoryBrokenHint: "returned broken by factory",
    roomDamaged: "Damaged (from room)", roomDamagedShort: "Damaged",
    roomDamagedHint: "damaged in the room (guest)",
    // Stock
    stockTitle: "Current Stock Levels", stockClean: "Clean", stockDirty: "Dirty",
    stockInTransit: "In Transit", stockTotalCol: "Total",
    stockHistory: "Transaction History", stockNoTx: "No transactions yet — use the buttons above to record one.",
    stockMaint: "Maintenance", stockDisp: "Disposal", stockWO: "Write-Off",
    stockFound: "Found", stockIn: "Stock In", stockOut: "Stock Out",
    stockRecordPrefix: "Record", stockTxDate: "Transaction Date", stockTxQty: "Quantity",
    stockTxUnit: "Unit Cost £", stockTxReason: "Reason", stockTxNotes: "Notes",
    stockTxItem: "Item", stockTxImpact: "Total impact:", stockTxBy: "By",
    stockTxDelConfirm: "Delete this transaction?", stockTxType: "Type",
    stockDeleted: "Deleted", stockRecorded: "recorded", stockSelectItem: "Select item",
    // Module-level
    moduleTitle: "Laundry Management", moduleSubtitle: "Manage dispatches, deliveries and view reports",
    kpiItemsSentYTD: "Items Sent YTD", kpiAwaitingReturn: "Awaiting Return",
    kpiDeliveries: "Deliveries", kpiContracts: "Contracts", kpiTotalSpend: "Total Spend",
    // Tiles
    tileDispatch: "Dispatch", tileDispatchSub: "Send to laundry",
    tileDeliveries: "Deliveries", tileDeliveriesSub: "Receive from laundry",
    tileForecast: "Next Order", tileForecastSub: "Forecast & order",
    tileUsage: "Daily Usage", tileUsageSub: "Room collections",
    tileStock: "Stock", tileStockSub: "Inventory levels",
    tileContracts: "Contracts", tileContractsSub: "Vendor agreements",
    // Dispatch tab table
    dispAwaiting: "Awaiting Return", dispNoAwaiting: "No dispatches awaiting return.",
    dispColExpected: "Expected", dispColItems: "Items", dispColCost: "Cost",
    dispColStatus: "Status", dispColActions: "Actions", dispColVendor: "Vendor", dispColSent: "Sent",
    receiveBtn: "Receive", loadingMsg: "Loading...",
    // Reports section
    reportsTitle: "Reports",
    repDailyUsage: "Daily Usage Report", repDailyUsageDesc: "Room-wise daily usage breakdown",
    repCount: "Count Report", repCountDesc: "Aggregated usage with anomalies",
    repOrder: "Order Report", repOrderDesc: "Order vs Received comparison",
    repDispatch: "Dispatch Report", repDispatchDesc: "Dirty send with date ranges",
    repMonthly: "Monthly Audit", repMonthlyDesc: "End of month audit report",
    repGroup: "Group Update", repGroupDesc: "Rolling cycle ledger",
    // Photos
    photosTitle: "Photos (Broken / Damaged evidence)", photosHint: "Snap up to 3 photos of broken or damaged items",
    photoAdd: "Take / Add Photo", photoRemove: "Remove", photoTooLarge: "Image too large (max 5MB)",
    // Offline
    offlineN: "queued offline (will auto-sync)",
  },
  tr: {
    label: "Türkçe", flag: "🇹🇷",
    date: "Tarih", room: "Oda", vendor: "Tedarikçi", notes: "Notlar (opsiyonel)", notesPh: "Ek notlar…",
    submit: "Kaydet & Onayla", cancel: "İptal", totals: "Toplam", item: "Ürün",
    used: "Kullanılan", collected: "Toplanan", unusable: "Fabrikadan bozuk geldi", damaged: "Odadan hasarlı çıktı",
    title: "Yeni Günlük Çamaşır Kaydı",
    subtitle: "Odayı seçin ve her malzeme için sayı yazın. Menüden item seçmenize gerek yok — hepsi hazır.",
    selectRoom: "Oda seç", roomPlaceholder: "Oda numarası (örn. 204)",
    usedHint: "temiz → oda", collectedHint: "oda → çamaşırhane", unusableHint: "fabrikadan bozuk geldi", damagedHint: "müşteri zararı",
    saved: "Kaydedildi", fillRoom: "Önce oda seçin", fillQty: "En az bir alana 0'dan büyük sayı yazın",
    newBtn: "Yeni Günlük Kayıt", loading: "Ürünler yükleniyor…",
    dispTitle: "Yeni Sevkıyat · Fabrikaya Gönder", dispSubtitle: "Gönderilen kirli miktarını ve geri iade edilen kullanılamaz miktarı yazın. Fabrika da sayım yapacak.",
    dispDirtySent: "Gönderilen Kirli", dispUnusableSent: "Gönderilen (Fabrikadan bozuk)",
    dispDirtyHint: "yıkanacak", dispUnusableHint: "iade ediliyor",
    dispRate: "Birim £", dispLineTotal: "Toplam £", dispExpectedReturn: "Beklenen İade Tarihi",
    dispAutofill: "Stoktan otomatik doldur (kirli+hasarlı)", dispNewBtn: "Yeni Sevkıyat",
    dispSaved: "Sevkıyat gönderildi",
    delvTitle: "Teslim Al · Gelişte Say", delvSubtitle: "Gelen her parçayı sayın. Alınan + varsa Eksik / Gelişte Hasarlı miktarını yazın.",
    delvSent: "Gönderilen", delvReceived: "Gelen", delvShortage: "Eksik", delvDamagedArr: "Hasarlı",
    delvReceivedHint: "sağlam gelen", delvShortageHint: "eksik gelen", delvDamagedHint: "gelişte bozuk",
    delvReceived2: "Teslim Al", delvSaved: "Teslim alındı",
    // Köken bazlı etiketler
    factoryBroken: "Bozuk (fabrikadan)", factoryBrokenShort: "Bozuk",
    factoryBrokenHint: "fabrikadan bozuk geldi",
    roomDamaged: "Hasarlı (odadan)", roomDamagedShort: "Hasarlı",
    roomDamagedHint: "odada hasar gördü (misafir)",
    // Stok
    stockTitle: "Mevcut Stok Seviyeleri", stockClean: "Temiz", stockDirty: "Kirli",
    stockInTransit: "Yolda", stockTotalCol: "Toplam",
    stockHistory: "İşlem Geçmişi", stockNoTx: "Henüz işlem yok — yukarıdaki butonlarla kayıt ekleyin.",
    stockMaint: "Bakım", stockDisp: "İmha", stockWO: "Zayiat",
    stockFound: "Bulundu", stockIn: "Stok Girişi", stockOut: "Stok Çıkışı",
    stockRecordPrefix: "Kaydet:", stockTxDate: "İşlem Tarihi", stockTxQty: "Adet",
    stockTxUnit: "Birim Maliyet £", stockTxReason: "Sebep", stockTxNotes: "Notlar",
    stockTxItem: "Ürün", stockTxImpact: "Toplam etki:", stockTxBy: "Kaydeden",
    stockTxDelConfirm: "Bu işlem silinsin mi?", stockTxType: "Tür",
    stockDeleted: "Silindi", stockRecorded: "kaydedildi", stockSelectItem: "Ürün seç",
    // Modül seviyesi
    moduleTitle: "Çamaşırhane Yönetimi", moduleSubtitle: "Sevkıyat, teslim alma ve raporları yönet",
    kpiItemsSentYTD: "Yıl Başından Gönderilen", kpiAwaitingReturn: "İade Bekleyen",
    kpiDeliveries: "Teslim Alınan", kpiContracts: "Sözleşmeler", kpiTotalSpend: "Toplam Harcama",
    // Kareler
    tileDispatch: "Sevkıyat", tileDispatchSub: "Fabrikaya gönder",
    tileDeliveries: "Teslim Alma", tileDeliveriesSub: "Fabrikadan gelen",
    tileForecast: "Yeni Sipariş", tileForecastSub: "Tahmin ve sipariş",
    tileUsage: "Günlük Kullanım", tileUsageSub: "Oda toplamaları",
    tileStock: "Stok", tileStockSub: "Envanter seviyeleri",
    tileContracts: "Sözleşmeler", tileContractsSub: "Tedarikçi anlaşmaları",
    // Sevkıyat tablosu
    dispAwaiting: "İade Bekleyen", dispNoAwaiting: "İade bekleyen sevkıyat yok.",
    dispColExpected: "Beklenen", dispColItems: "Adet", dispColCost: "Maliyet",
    dispColStatus: "Durum", dispColActions: "İşlem", dispColVendor: "Tedarikçi", dispColSent: "Gönderildi",
    receiveBtn: "Teslim Al", loadingMsg: "Yükleniyor...",
    // Rapor bölümü
    reportsTitle: "Raporlar",
    repDailyUsage: "Günlük Kullanım Raporu", repDailyUsageDesc: "Oda bazlı günlük kullanım dökümü",
    repCount: "Sayım Raporu", repCountDesc: "Kullanım ve anomaliler özeti",
    repOrder: "Sipariş Raporu", repOrderDesc: "Sipariş vs Teslim karşılaştırması",
    repDispatch: "Sevkıyat Raporu", repDispatchDesc: "Tarih aralıklı kirli gönderimi",
    repMonthly: "Aylık Denetim", repMonthlyDesc: "Ay sonu denetim raporu",
    repGroup: "Grup Güncellemesi", repGroupDesc: "Döngü defteri",
    // Fotoğraflar
    photosTitle: "Fotoğraflar (Bozuk / Hasarlı kanıt)", photosHint: "Bozuk veya hasarlı ürünlerin en fazla 3 fotoğrafını çekin",
    photoAdd: "Foto Çek / Ekle", photoRemove: "Kaldır", photoTooLarge: "Resim çok büyük (max 5MB)",
    offlineN: "offline sırada (bağlantı gelince otomatik yollanır)",
  },
  bg: {
    label: "Български", flag: "🇧🇬",
    date: "Дата", room: "Стая", vendor: "Доставчик", notes: "Бележки (по избор)", notesPh: "Допълнителни бележки…",
    submit: "Запази и потвърди", cancel: "Отказ", totals: "Общо", item: "Артикул",
    used: "Използвани", collected: "Събрани", unusable: "Счупени (от фабрика)", damaged: "Повредени (от стая)",
    title: "Нов дневен запис на пране",
    subtitle: "Изберете стая и въведете брой за всеки артикул. Не е нужно да избирате от меню — всички артикули са предварително показани.",
    selectRoom: "Изберете стая", roomPlaceholder: "Номер на стая (напр. 204)",
    usedHint: "чисто → стая", collectedHint: "стая → пране", unusableHint: "върнати негодни от пералнята", damagedHint: "повредени от госта",
    saved: "Записано", fillRoom: "Изберете стая", fillQty: "Въведете поне едно число > 0",
    newBtn: "Нов дневен запис", loading: "Зареждане на артикули…",
    dispTitle: "Нова доставка · Към фабрика", dispSubtitle: "Въведете мръсни парчета и негодни за връщане. Фабриката ще ги преброи.",
    dispDirtySent: "Изпратени мръсни", dispUnusableSent: "Изпратени (от фабрика счупени)",
    dispDirtyHint: "за пране", dispUnusableHint: "връщаме",
    dispRate: "Цена £", dispLineTotal: "Общо £", dispExpectedReturn: "Очаквано връщане",
    dispAutofill: "Автоматично от склад (мръсно+повредено)", dispNewBtn: "Нова доставка",
    dispSaved: "Доставката е изпратена",
    delvTitle: "Получаване · Преброяване при пристигане", delvSubtitle: "Пребройте всяко парче. Въведете Получени + всякакви Липсващи / Повредени при пристигане.",
    delvSent: "Изпратени", delvReceived: "Получени", delvShortage: "Липсващи", delvDamagedArr: "Повредени",
    delvReceivedHint: "добри парчета", delvShortageHint: "липсват", delvDamagedHint: "лоши при пристигане",
    delvReceived2: "Получи", delvSaved: "Получаването е записано",
    // Произход
    factoryBroken: "Счупени (от фабрика)", factoryBrokenShort: "Счупени",
    factoryBrokenHint: "върнати счупени от фабриката",
    roomDamaged: "Повредени (от стая)", roomDamagedShort: "Повредени",
    roomDamagedHint: "повредени в стаята (гост)",
    // Склад
    stockTitle: "Текущи складови нива", stockClean: "Чисти", stockDirty: "Мръсни",
    stockInTransit: "В транзит", stockTotalCol: "Общо",
    stockHistory: "История на операциите", stockNoTx: "Няма операции — използвайте бутоните горе.",
    stockMaint: "Поддръжка", stockDisp: "Изхвърляне", stockWO: "Отписване",
    stockFound: "Намерени", stockIn: "Вход", stockOut: "Изход",
    stockRecordPrefix: "Запиши", stockTxDate: "Дата на операция", stockTxQty: "Количество",
    stockTxUnit: "Ед. цена £", stockTxReason: "Причина", stockTxNotes: "Бележки",
    stockTxItem: "Артикул", stockTxImpact: "Общо въздействие:", stockTxBy: "От",
    stockTxDelConfirm: "Да изтрия ли тази операция?", stockTxType: "Тип",
    stockDeleted: "Изтрито", stockRecorded: "записано", stockSelectItem: "Изберете артикул",
    // Модул
    moduleTitle: "Управление на пране", moduleSubtitle: "Управлявайте доставки, получавания и отчети",
    kpiItemsSentYTD: "Изпратени от началото на годината", kpiAwaitingReturn: "Чака се връщане",
    kpiDeliveries: "Получени", kpiContracts: "Договори", kpiTotalSpend: "Общ разход",
    // Плочки
    tileDispatch: "Доставка", tileDispatchSub: "Към фабрика",
    tileDeliveries: "Получаване", tileDeliveriesSub: "От фабрика",
    tileForecast: "Нова поръчка", tileForecastSub: "Прогноза и поръчка",
    tileUsage: "Дневна употреба", tileUsageSub: "Събиране от стая",
    tileStock: "Склад", tileStockSub: "Нива на запаси",
    tileContracts: "Договори", tileContractsSub: "Споразумения с доставчик",
    // Таблица доставки
    dispAwaiting: "Чака се връщане", dispNoAwaiting: "Няма доставки в очакване.",
    dispColExpected: "Очаквано", dispColItems: "Артикули", dispColCost: "Стойност",
    dispColStatus: "Статус", dispColActions: "Действия", dispColVendor: "Доставчик", dispColSent: "Изпратено",
    receiveBtn: "Получи", loadingMsg: "Зареждане...",
    // Отчети
    reportsTitle: "Отчети",
    repDailyUsage: "Дневен отчет", repDailyUsageDesc: "Употреба по стая",
    repCount: "Отчет за броене", repCountDesc: "Обобщение с аномалии",
    repOrder: "Отчет за поръчки", repOrderDesc: "Поръчано срещу получено",
    repDispatch: "Отчет за доставки", repDispatchDesc: "Изпращане на мръсно",
    repMonthly: "Месечен одит", repMonthlyDesc: "Отчет в края на месеца",
    repGroup: "Групова актуализация", repGroupDesc: "Ротационен дневник",
    // Снимки
    photosTitle: "Снимки (доказателство за счупени/повредени)", photosHint: "Направете до 3 снимки на счупените или повредените артикули",
    photoAdd: "Снимай / Добави", photoRemove: "Премахни", photoTooLarge: "Снимката е твърде голяма (макс. 5MB)",
    offlineN: "опашка офлайн (ще се синхронизира автоматично)",
  },
};

export const LaundryManagement = ({ propertyId, user, permissions }) => {
  // Language preference (scoped to this module, persisted)
  const [lang, setLang] = useState(() => {
    try { return localStorage.getItem("laundry_lang") || "en"; } catch { return "en"; }
  });
  useEffect(() => { try { localStorage.setItem("laundry_lang", lang); } catch { /* quota */ } }, [lang]);
  const L = LAUNDRY_I18N[lang] || LAUNDRY_I18N.en;

  const [tab, setTab] = useState("dispatch");
  const [dispatches, setDispatches] = useState({ dispatches: [], kpis: {} });
  const [usage, setUsage] = useState({ records: [], count: 0 });
  const [stock, setStock] = useState([]);
  const [contracts, setContracts] = useState([]);
  const [catalog, setCatalog] = useState([]);
  const [rooms, setRooms] = useState([]);
  const [loading, setLoading] = useState(true);

  const [dispOpen, setDispOpen] = useState(false);
  const [contractOpen, setContractOpen] = useState(false);
  const [usageOpen, setUsageOpen] = useState(false);
  const [reportOpen, setReportOpen] = useState(null);
  const [reportData, setReportData] = useState(null);
  const [reportLoading, setReportLoading] = useState(false);

  const [dispForm, setDispForm] = useState({ vendor: "", sent_date: new Date().toISOString().slice(0, 10), expected_return: "", items: [], notes: "" });
  const [contractForm, setContractForm] = useState({
    vendor: "", contact_name: "", contact_email: "", contact_phone: "",
    start_date: "", end_date: "", pickup_schedule: "weekly", terms: "", rates: [], active: true,
  });
  const [usageForm, setUsageForm] = useState({ date: new Date().toISOString().slice(0, 10), room_id: "", room_number: "", notes: "", items: [], photos: [] });

  // Pre-populate the usage form with ALL catalog items (housekeeper-friendly ready-table)
  const openUsageForm = () => {
    const prefilled = (catalog || []).map(c => ({
      item_id: c.id, item_name: c.name,
      clean_used: 0, dirty_collected: 0, factory_unusable: 0, guest_damaged: 0,
    }));
    setUsageForm(f => ({
      ...f,
      date: new Date().toISOString().slice(0, 10),
      room_id: "", room_number: "", notes: "",
      items: prefilled,
    }));
    setUsageOpen(true);
  };

  const pid = propertyId || "all";
  const isManager = user?.role === "admin" || user?.role === "manager";
  // Permission-gated cost visibility: configured by admin in Roles & Permissions.
  // Legacy admin always allowed; otherwise requires `view_laundry_costs` perm.
  const canSeeCosts = !!permissions?.is_legacy_admin
                   || !!permissions?.permissions?.has?.("view_laundry_costs");
  // Filter tabs: housekeeper + receptionist should NOT see contracts
  const visibleTabs = TABS.filter(t => t.id !== "contracts" || canSeeCosts);
  // If a restricted user somehow has 'contracts' selected, force them to dispatch
  useEffect(() => {
    if (!canSeeCosts && tab === "contracts") setTab("dispatch");
  }, [canSeeCosts, tab]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [d, u, s, c, cat, rm] = await Promise.all([
        axios.get(`${API}/laundry/dispatches/${pid}`),
        axios.get(`${API}/laundry/usage/${pid}`),
        axios.get(`${API}/laundry/stock/${pid}`),
        axios.get(`${API}/laundry/contracts/${pid}`).catch(() => ({ data: { contracts: [] } })),
        axios.get(`${API}/laundry/catalog`, { params: { property_id: pid } }),
        axios.get(`${API}/rooms`).catch(() => ({ data: [] })),
      ]);
      setDispatches(d.data);
      setUsage(u.data);
      setStock(s.data.stock || []);
      setContracts(c.data.contracts || []);
      setCatalog(cat.data.items || []);
      setRooms(Array.isArray(rm.data) ? rm.data : (rm.data.rooms || []));
    } catch { /* silent */ }
    setLoading(false);
  }, [pid]);

  useEffect(() => { load(); }, [load]);

  // ============ DISPATCH HELPERS ============
  const addDispItem = () => setDispForm(f => ({ ...f, items: [...f.items, { item_id: "", name: "", qty_sent: 0, qty_unusable_sent: 0, rate: 0 }] }));
  const updateDispItem = (idx, patch) => {
    setDispForm(f => {
      const items = [...f.items];
      items[idx] = { ...items[idx], ...patch };
      if (patch.item_id) {
        const c = catalog.find(x => x.id === patch.item_id);
        if (c) items[idx].name = c.name;
      }
      return { ...f, items };
    });
  };

  // Pre-populate dispatch with ALL active catalog items + auto-fill dirty/damaged from current stock
  const openDispForm = () => {
    const stockMap = Object.fromEntries((stock || []).map(s => [s.item_id, s]));
    const prefilled = (catalog || []).map(c => {
      const s = stockMap[c.id] || {};
      return {
        item_id: c.id, name: c.name,
        qty_sent: Number(s.dirty || 0),                 // all current dirty goes to factory
        qty_unusable_sent: Number(s.damaged || 0),      // all current damaged returned too
        rate: 0,
      };
    });
    setDispForm(f => ({
      ...f,
      vendor: f.vendor || "", sent_date: new Date().toISOString().slice(0, 10),
      expected_return: "", notes: "",
      items: prefilled,
    }));
    setDispOpen(true);
  };
  const removeDispItem = (idx) => setDispForm(f => ({ ...f, items: f.items.filter((_, i) => i !== idx) }));
  const submitDispatch = async () => {
    if (!dispForm.vendor.trim()) { toast.error(L.vendor + " ?"); return; }
    const validItems = (dispForm.items || []).filter(i => (i.qty_sent || 0) > 0 || (i.qty_unusable_sent || 0) > 0);
    if (validItems.length === 0) { toast.error(L.fillQty); return; }
    try {
      await axios.post(`${API}/laundry/dispatches/${pid}`, { ...dispForm, items: validItems });
      toast.success(L.dispSaved);
      setDispOpen(false);
      setDispForm({ vendor: "", sent_date: new Date().toISOString().slice(0, 10), expected_return: "", items: [], notes: "" });
      load();
    } catch { toast.error("Failed"); }
  };
  const receiveDispatch = async (d) => {
    if (!window.confirm(`Mark ${d.vendor} dispatch as received (full qty)?`)) return;
    try {
      await axios.post(`${API}/laundry/dispatches/${pid}/${d.id}/receive`, { items: d.items.map(i => ({ item_id: i.item_id, qty_received: i.qty_sent })) });
      toast.success("Received");
      load();
    } catch { toast.error("Failed"); }
  };

  // ============ USAGE HELPERS ============
  const addUsageItem = () => setUsageForm(f => ({ ...f, items: [...f.items, { item_id: "", item_name: "", clean_used: 0, dirty_collected: 0 }] }));
  const updateUsageItem = (idx, patch) => setUsageForm(f => {
    const items = [...f.items];
    items[idx] = { ...items[idx], ...patch };
    if (patch.item_id) {
      const c = catalog.find(x => x.id === patch.item_id);
      if (c) items[idx].item_name = c.name;
    }
    return { ...f, items };
  });
  const removeUsageItem = (idx) => setUsageForm(f => ({ ...f, items: f.items.filter((_, i) => i !== idx) }));
  const LAUNDRY_QUEUE_KEY = `laundry_usage_queue_${pid}`;

  // Flush any queued (offline) usage entries to the server
  const flushOfflineQueue = useCallback(async () => {
    try {
      const raw = localStorage.getItem(LAUNDRY_QUEUE_KEY);
      if (!raw) return;
      const queue = JSON.parse(raw) || [];
      if (queue.length === 0) return;
      const remaining = [];
      for (const payload of queue) {
        try { await axios.post(`${API}/laundry/usage/${pid}`, payload); }
        catch { remaining.push(payload); }
      }
      localStorage.setItem(LAUNDRY_QUEUE_KEY, JSON.stringify(remaining));
      const synced = queue.length - remaining.length;
      if (synced > 0) toast.success(`${synced} offline entr${synced === 1 ? "y" : "ies"} synced`);
    } catch { /* non-fatal */ }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pid]);

  // Auto-flush on online event + on mount
  useEffect(() => {
    flushOfflineQueue();
    const handler = () => flushOfflineQueue();
    window.addEventListener("online", handler);
    return () => window.removeEventListener("online", handler);
  }, [flushOfflineQueue]);

  // Count queued items for UI badge
  const [queueLen, setQueueLen] = useState(0);
  // Providers list (used for auto-email prefill + Forecast vendor dropdown)
  const [laundryProviders, setLaundryProviders] = useState([]);
  useEffect(() => {
    axios.get(`${API}/laundry/providers/${pid}`)
      .then(r => setLaundryProviders((r.data.providers || []).filter(p => p.status === "active")))
      .catch(() => setLaundryProviders([]));
  }, [pid]);
  // QR code preview modal for dispatches — future-ready, factory can scan on arrival
  const [qrDispatch, setQrDispatch] = useState(null);
  // Email-to-vendor modal state
  const [emailDispatch, setEmailDispatch] = useState(null);
  const [emailTo, setEmailTo] = useState("");
  const [emailSending, setEmailSending] = useState(false);

  const downloadDispatch = async (dispatchId, format) => {
    // format = "pdf" | "excel"
    try {
      const { data, headers } = await axios.get(
        `${API}/laundry/dispatches/${dispatchId}/${format}`,
        { responseType: "blob" }
      );
      const ext = format === "pdf" ? "pdf" : "xlsx";
      const blob = new Blob([data], { type: headers["content-type"] });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `dispatch_${dispatchId.slice(0, 8)}.${ext}`;
      document.body.appendChild(a); a.click();
      a.remove(); URL.revokeObjectURL(url);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Download failed");
    }
  };

  const openEmailDispatch = (d) => {
    setEmailDispatch(d);
    // Try to prefill from provider records
    const match = laundryProviders?.find?.(p => p.name === d.vendor);
    setEmailTo(match?.email || "");
  };

  const sendDispatchEmail = async () => {
    if (!emailDispatch) return;
    if (!emailTo || !emailTo.includes("@")) {
      toast.error("Valid recipient email required");
      return;
    }
    setEmailSending(true);
    try {
      await axios.post(`${API}/laundry/dispatches/${emailDispatch.id}/email`, {
        to: emailTo.split(",").map(x => x.trim()).filter(Boolean),
      });
      toast.success(`Dispatch emailed to ${emailTo}`);
      setEmailDispatch(null); setEmailTo("");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Email failed");
    }
    setEmailSending(false);
  };
  useEffect(() => {
    const tick = () => {
      try {
        const raw = localStorage.getItem(LAUNDRY_QUEUE_KEY);
        setQueueLen(raw ? (JSON.parse(raw) || []).length : 0);
      } catch { setQueueLen(0); }
    };
    tick();
    const iv = setInterval(tick, 3000);
    return () => clearInterval(iv);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pid, usageOpen]);

  const submitUsage = async () => {
    if (!usageForm.room_number.trim() || usageForm.items.length === 0) { toast.error(L.fillRoom); return; }
    const validItems = usageForm.items.filter(i =>
      (i.clean_used || 0) > 0 ||
      (i.dirty_collected || 0) > 0 ||
      (i.factory_unusable || 0) > 0 ||
      (i.guest_damaged || 0) > 0
    );
    if (validItems.length === 0) { toast.error(L.fillQty); return; }
    const payload = { ...usageForm, items: validItems };
    try {
      await axios.post(`${API}/laundry/usage/${pid}`, payload);
      toast.success(`${L.saved} · ${validItems.length} · ${L.room} ${usageForm.room_number}`);
      setUsageOpen(false);
      setUsageForm({ date: new Date().toISOString().slice(0, 10), room_id: "", room_number: "", notes: "", items: [], photos: [] });
      load();
    } catch {
      // Offline fallback — push to localStorage queue
      try {
        const raw = localStorage.getItem(LAUNDRY_QUEUE_KEY);
        const queue = raw ? (JSON.parse(raw) || []) : [];
        queue.push(payload);
        localStorage.setItem(LAUNDRY_QUEUE_KEY, JSON.stringify(queue));
        toast.success(`${validItems.length} ${L.offlineN}`);
        setUsageOpen(false);
        setUsageForm({ date: new Date().toISOString().slice(0, 10), room_id: "", room_number: "", notes: "", items: [], photos: [] });
      } catch {
        toast.error("Failed");
      }
    }
  };
  const deleteUsage = async (id) => {
    if (!window.confirm("Delete this usage record? Stock will be reversed.")) return;
    try { await axios.delete(`${API}/laundry/usage/${pid}/${id}`); toast.success("Deleted"); load(); } catch { toast.error("Failed"); }
  };

  // ============ STOCK ============
  const updateStockCell = async (item_id, field, value) => {
    const row = stock.find(s => s.item_id === item_id);
    try {
      await axios.put(`${API}/laundry/stock/${pid}/${item_id}`, { [field]: parseInt(value) || 0, name: row?.name || item_id });
      load();
    } catch { toast.error("Failed"); }
  };

  // ============ CONTRACTS ============
  const submitContract = async () => {
    if (!contractForm.vendor.trim()) { toast.error("Vendor required"); return; }
    try {
      await axios.post(`${API}/laundry/contracts/${pid}`, contractForm);
      toast.success("Contract added");
      setContractOpen(false);
      setContractForm({ vendor: "", contact_name: "", contact_email: "", contact_phone: "", start_date: "", end_date: "", pickup_schedule: "weekly", terms: "", rates: [], active: true });
      load();
    } catch { toast.error("Failed"); }
  };
  const deleteContract = async (id) => {
    if (!window.confirm("Delete this contract?")) return;
    try { await axios.delete(`${API}/laundry/contracts/${pid}/${id}`); toast.success("Deleted"); load(); } catch { toast.error("Failed"); }
  };
  const addRate = () => setContractForm(f => ({ ...f, rates: [...f.rates, { item_id: "", name: "", rate: 0 }] }));
  const updateRate = (i, patch) => setContractForm(f => {
    const rates = [...f.rates];
    rates[i] = { ...rates[i], ...patch };
    if (patch.item_id) {
      const c = catalog.find(x => x.id === patch.item_id);
      if (c) rates[i].name = c.name;
    }
    return { ...f, rates };
  });

  // ============ REPORTS ============
  const openReport = async (rep) => {
    setReportOpen(rep);
    setReportLoading(true);
    setReportData(null);
    try {
      const { data } = await axios.get(`${API}/laundry/reports/${pid}/${rep.id}`);
      setReportData(data);
    } catch { toast.error("Failed to load report"); }
    setReportLoading(false);
  };
  const exportCSV = () => {
    if (!reportData || !reportOpen) return;
    let csv = "";
    if (reportOpen.id === "daily-usage") {
      csv = "Date,Room,Item,Qty,Recorded By\n" + (reportData.rows || []).map(r => `${r.date},${r.room_number},${r.item_name},${r.qty},${r.recorded_by}`).join("\n");
    } else if (reportOpen.id === "count") {
      csv = "Item,Total,Days Active,Rooms Active,Daily Avg,Anomaly\n" + (reportData.items || []).map(i => `${i.item},${i.total},${i.days_active},${i.rooms_active},${i.daily_avg},${i.anomaly}`).join("\n");
    } else if (reportOpen.id === "order") {
      csv = "Item,Sent,Received,Variance\n" + (reportData.items || []).map(i => `${i.item},${i.sent},${i.received},${i.variance}`).join("\n");
    } else if (reportOpen.id === "monthly-audit") {
      csv = "Item,Clean,Dirty,In Transit,Damaged,Used,Dispatched,Total\n" + (reportData.audit || []).map(a => `${a.item},${a.clean},${a.dirty},${a.in_transit},${a.damaged},${a.used_in_period},${a.dispatched_in_period},${a.total_inventory}`).join("\n");
    } else if (reportOpen.id === "group-update") {
      csv = "Date,Type,Item,Qty,Ref\n" + (reportData.events || []).map(e => `${e.date},${e.type},${e.item},${e.qty},${e.ref}`).join("\n");
    }
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `laundry-${reportOpen.id}-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
  };

  const k = dispatches.kpis || {};
  const deliveries = (dispatches.dispatches || []).filter(d => d.status === "received");
  const sentDispatches = (dispatches.dispatches || []).filter(d => d.status !== "received");

  const fmt = (n) => `£${Number(n || 0).toLocaleString()}`;

  return (
    <div className="space-y-5" data-testid="laundry-management">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-3">
            <Shirt className="w-5 h-5 text-stone-700" />
            <h2 className="text-base font-bold text-stone-800" data-testid="laundry-title">{L.moduleTitle || "Laundry Management"}</h2>
          </div>
          <p className="text-[11px] text-stone-500 mt-0.5">{L.moduleSubtitle || "Manage dispatches, deliveries and view reports"}</p>
        </div>
        {/* Global language toggle */}
        <div className="flex gap-1 bg-stone-100 rounded-lg p-1" data-testid="laundry-lang-toggle">
          {Object.keys(LAUNDRY_I18N).map(code => (
            <button key={code} onClick={() => setLang(code)}
              className={`px-2.5 py-1 text-xs font-semibold rounded transition ${lang === code ? "bg-white text-stone-800 shadow" : "text-stone-500 hover:text-stone-700"}`}
              data-testid={`laundry-lang-${code}`}>
              {LAUNDRY_I18N[code].flag} {code.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {/* KPIs */}
      <div className={`grid gap-3 ${canSeeCosts ? "grid-cols-5" : "grid-cols-3"}`} data-testid="laundry-kpis">
        <div className="bg-stone-50 border border-stone-200 rounded-xl p-4 text-center"><p className="text-2xl font-black text-stone-700">{k.total_items || 0}</p><p className="text-[10px] text-stone-500">{L.kpiItemsSentYTD || "Items Sent YTD"}</p></div>
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-center"><Send className="w-4 h-4 mx-auto mb-1 text-amber-600" /><p className="text-2xl font-black text-amber-700">{k.sent || 0}</p><p className="text-[10px] text-amber-600">{L.kpiAwaitingReturn || "Awaiting Return"}</p></div>
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-center"><CheckCircle2 className="w-4 h-4 mx-auto mb-1 text-emerald-600" /><p className="text-2xl font-black text-emerald-700">{k.received || 0}</p><p className="text-[10px] text-emerald-600">{L.kpiDeliveries || "Deliveries"}</p></div>
        {canSeeCosts && (
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-center"><Building2 className="w-4 h-4 mx-auto mb-1 text-blue-600" /><p className="text-2xl font-black text-blue-700">{contracts.length}</p><p className="text-[10px] text-blue-600">{L.kpiContracts || "Contracts"}</p></div>
        )}
        {canSeeCosts && (
          <div className="bg-violet-50 border border-violet-200 rounded-xl p-4 text-center"><p className="text-2xl font-black text-violet-700">{fmt(k.total_cost)}</p><p className="text-[10px] text-violet-600">{L.kpiTotalSpend || "Total Spend"}</p></div>
        )}
      </div>

      {/* Big Colored Tiles (like the mobile screenshot) */}
      <div className={`grid grid-cols-2 gap-3 ${visibleTabs.length === 6 ? "md:grid-cols-6" : visibleTabs.length === 5 ? "md:grid-cols-5" : "md:grid-cols-4"}`} data-testid="laundry-tiles">
        {visibleTabs.map(t => {
          const Icon = t.icon;
          const active = tab === t.id;
          const tileLabel = { dispatch: L.tileDispatch, deliveries: L.tileDeliveries, forecast: L.tileForecast, usage: L.tileUsage, stock: L.tileStock, contracts: L.tileContracts }[t.id] || t.label;
          const tileSub   = { dispatch: L.tileDispatchSub, deliveries: L.tileDeliveriesSub, forecast: L.tileForecastSub, usage: L.tileUsageSub, stock: L.tileStockSub, contracts: L.tileContractsSub }[t.id] || t.subtitle;
          return (
            <button key={t.id} onClick={() => setTab(t.id)} data-testid={`tab-${t.id}`}
              className={`${t.color} text-white rounded-xl p-4 text-left transition-all ${active ? "ring-4 ring-offset-2 ring-stone-800 scale-[1.02]" : "hover:scale-[1.02] opacity-90 hover:opacity-100"}`}>
              <div className="w-10 h-10 bg-white/20 rounded-lg flex items-center justify-center mb-3">
                <Icon className="w-5 h-5" />
              </div>
              <h3 className="text-sm font-black">{tileLabel}</h3>
              <p className="text-[11px] opacity-90">{tileSub}</p>
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      {loading ? (
        <div className="flex items-center justify-center py-20 text-stone-400"><RefreshCw className="w-5 h-5 animate-spin mr-2" />{L.loadingMsg || "Loading..."}</div>
      ) : (
        <>
          {/* DISPATCH */}
          {tab === "dispatch" && (
            <div className="bg-white border border-stone-200 rounded-xl overflow-hidden" data-testid="dispatch-panel">
              <div className="p-3 border-b border-stone-200 flex items-center justify-between">
                <h3 className="text-sm font-bold text-stone-800">{L.dispAwaiting || "Awaiting Return"} ({sentDispatches.length})</h3>
                <Button size="sm" onClick={openDispForm} className="bg-stone-800 hover:bg-stone-700 text-white" data-testid="new-dispatch-btn">
                  <Plus className="w-4 h-4 mr-1.5" />{L.dispNewBtn}
                </Button>
              </div>
              {sentDispatches.length === 0 ? (
                <p className="text-center text-sm text-stone-400 py-12">{L.dispNoAwaiting || "No dispatches awaiting return."}</p>
              ) : (
                <table className="w-full text-xs">
                  <thead className="bg-stone-50 border-b border-stone-200">
                    <tr>
                      <th className="text-left py-2.5 px-3 font-semibold text-stone-600">{L.dispColVendor || "Vendor"}</th>
                      <th className="text-left py-2.5 px-3 font-semibold text-stone-600">{L.dispColSent || "Sent"}</th>
                      <th className="text-left py-2.5 px-3 font-semibold text-stone-600">{L.dispColExpected || "Expected"}</th>
                      <th className="text-center py-2.5 px-3 font-semibold text-stone-600">{L.dispColItems || "Items"}</th>
                      {canSeeCosts && <th className="text-right py-2.5 px-3 font-semibold text-stone-600">{L.dispColCost || "Cost"}</th>}
                      <th className="text-center py-2.5 px-3 font-semibold text-stone-600">{L.dispColStatus || "Status"}</th>
                      <th className="text-right py-2.5 px-3 font-semibold text-stone-600">{L.dispColActions || "Actions"}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sentDispatches.map(d => (
                      <tr key={d.id} className="border-b border-stone-100 hover:bg-stone-50/50" data-testid={`dispatch-row-${d.id}`}>
                        <td className="py-2.5 px-3 font-semibold text-stone-700">{d.vendor}</td>
                        <td className="py-2.5 px-3 text-stone-600">{d.sent_date}</td>
                        <td className="py-2.5 px-3 text-stone-600">{d.expected_return || "—"}</td>
                        <td className="py-2.5 px-3 text-center font-semibold text-stone-700">{d.items.reduce((s, i) => s + i.qty_sent, 0)}</td>
                        {canSeeCosts && <td className="py-2.5 px-3 text-right font-mono text-stone-700">£{d.total_cost?.toFixed(2)}</td>}
                        <td className="py-2.5 px-3 text-center"><Badge className={`${DISPATCH_STATUS_STYLE[d.status] || "bg-stone-100"} text-[9px] capitalize`}>{d.status}</Badge></td>
                        <td className="py-2.5 px-3 text-right">
                          <div className="inline-flex flex-wrap gap-1 justify-end">
                            <button onClick={() => downloadDispatch(d.id, "pdf")} className="text-[10px] px-2 py-1 bg-rose-50 text-rose-700 rounded hover:bg-rose-100 font-semibold" data-testid={`pdf-btn-${d.id}`} title="Download PDF">
                              <FileText className="w-3 h-3 inline mr-1" />PDF
                            </button>
                            <button onClick={() => downloadDispatch(d.id, "excel")} className="text-[10px] px-2 py-1 bg-emerald-50 text-emerald-700 rounded hover:bg-emerald-100 font-semibold" data-testid={`xlsx-btn-${d.id}`} title="Download Excel">
                              <FileSpreadsheet className="w-3 h-3 inline mr-1" />XLS
                            </button>
                            <button onClick={() => openEmailDispatch(d)} className="text-[10px] px-2 py-1 bg-violet-50 text-violet-700 rounded hover:bg-violet-100 font-semibold" data-testid={`email-btn-${d.id}`} title="Email to vendor">
                              <Mail className="w-3 h-3 inline mr-1" />Email
                            </button>
                            <button onClick={() => setQrDispatch(d)} className="text-[10px] px-2 py-1 bg-blue-50 text-blue-700 rounded hover:bg-blue-100 font-semibold" data-testid={`qr-btn-${d.id}`} title="Show QR code (future factory scan)">
                              <QrCode className="w-3 h-3 inline mr-1" />QR
                            </button>
                            <button onClick={() => receiveDispatch(d)} className="text-[10px] px-2 py-1 bg-amber-50 text-amber-700 rounded hover:bg-amber-100 font-semibold" data-testid={`receive-btn-${d.id}`}>
                              <ArrowDown className="w-3 h-3 inline mr-1" />{L.receiveBtn || "Receive"}
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {/* DELIVERIES */}
          {tab === "deliveries" && (
            <DeliveriesTab pid={pid} dispatches={sentDispatches} stock={stock} catalog={catalog} lang={lang} setLang={setLang} L={L} canSeeCosts={canSeeCosts} />
          )}

          {/* FORECAST */}
          {tab === "forecast" && (
            <ForecastTab pid={pid} onCreated={load} canSeeCosts={canSeeCosts} />
          )}

          {/* DAILY USAGE */}
          {tab === "usage" && (
            <div className="bg-white border border-stone-200 rounded-xl overflow-hidden" data-testid="usage-panel">
              <div className="p-3 border-b border-stone-200 flex items-center justify-between">
                <h3 className="text-sm font-bold text-stone-800">Room-by-Room Usage ({usage.count})</h3>
                <div className="flex items-center gap-2">
                  {queueLen > 0 && (
                    <Badge className="bg-amber-100 text-amber-800 border border-amber-300 font-mono" data-testid="offline-queue-badge">
                      ⏳ {queueLen} {L.offlineN}
                    </Badge>
                  )}
                  <Button size="sm" onClick={openUsageForm} className="bg-stone-800 hover:bg-stone-700 text-white" data-testid="new-usage-btn">
                    <Plus className="w-4 h-4 mr-1" />{L.newBtn}
                  </Button>
                </div>
              </div>
              {usage.records.length === 0 ? (
                <p className="text-center text-sm text-stone-400 py-12">No usage recorded. Record a room's daily linen collection to track circulation.</p>
              ) : (
                <table className="w-full text-xs">
                  <thead className="bg-stone-50 border-b border-stone-200">
                    <tr>
                      <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Date</th>
                      <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Room</th>
                      <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Item</th>
                      <th className="text-center py-2.5 px-3 font-semibold text-emerald-700">Used ↓</th>
                      <th className="text-center py-2.5 px-3 font-semibold text-amber-700">Collected ↑</th>
                      <th className="text-center py-2.5 px-3 font-semibold text-rose-700">Unusable</th>
                      <th className="text-center py-2.5 px-3 font-semibold text-fuchsia-700">Damaged</th>
                      <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Notes</th>
                      <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Recorded By</th>
                      <th className="text-right py-2.5 px-3 font-semibold text-stone-600"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {usage.records.map(r => {
                      const clean = r.clean_used ?? r.qty ?? 0;
                      const dirty = r.dirty_collected ?? r.qty ?? 0;
                      const unusable = r.factory_unusable ?? 0;
                      const damaged = r.guest_damaged ?? 0;
                      const mismatch = clean !== dirty;
                      return (
                      <tr key={r.id} className="border-b border-stone-100 hover:bg-stone-50/50" data-testid={`usage-row-${r.id}`}>
                        <td className="py-2 px-3 text-stone-600">{r.date}</td>
                        <td className="py-2 px-3 font-semibold text-stone-700">{r.room_number}</td>
                        <td className="py-2 px-3 text-stone-700">{r.item_name}</td>
                        <td className="py-2 px-3 text-center font-bold text-emerald-700">{clean}</td>
                        <td className="py-2 px-3 text-center">
                          <span className={`font-bold ${mismatch ? "text-rose-600" : "text-amber-700"}`}>{dirty}</span>
                          {mismatch && <span className="ml-1 text-[9px] text-rose-500" title="Differs from clean used">≠</span>}
                        </td>
                        <td className="py-2 px-3 text-center font-bold text-rose-700">{unusable || "—"}</td>
                        <td className="py-2 px-3 text-center font-bold text-fuchsia-700">{damaged || "—"}</td>
                        <td className="py-2 px-3 text-[10px] text-stone-500 italic">{r.notes || "—"}</td>
                        <td className="py-2 px-3 text-[10px] text-stone-500">{r.recorded_by}</td>
                        <td className="py-2 px-3 text-right">
                          {isManager && <button onClick={() => deleteUsage(r.id)} className="p-1 hover:bg-red-50 rounded"><Trash2 className="w-3 h-3 text-red-500" /></button>}
                        </td>
                      </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {/* STOCK */}
          {tab === "stock" && (
            <StockTab pid={pid} stock={stock} updateStockCell={updateStockCell} lang={lang} setLang={setLang} L={L} />
          )}

          {/* CONTRACTS */}
          {tab === "contracts" && (
            <div data-testid="contracts-panel">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-bold text-stone-800">Laundry Contracts ({contracts.length})</h3>
                {isManager && (
                  <Button size="sm" onClick={() => setContractOpen(true)} className="bg-stone-800 hover:bg-stone-700 text-white" data-testid="new-contract-btn">
                    <Plus className="w-4 h-4 mr-1.5" />New Contract
                  </Button>
                )}
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                {contracts.length === 0 ? (
                  <p className="text-center text-sm text-stone-400 py-12 col-span-2">No contracts yet.</p>
                ) : contracts.map(c => (
                  <div key={c.id} className="bg-white border border-stone-200 rounded-xl p-4" data-testid={`contract-card-${c.id}`}>
                    <div className="flex items-start justify-between">
                      <div>
                        <h4 className="text-sm font-bold text-stone-800">{c.vendor}</h4>
                        <p className="text-[10px] text-stone-400">{c.contact_name} · {c.contact_email}</p>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <Badge className={c.active ? "bg-emerald-100 text-emerald-700 text-[9px]" : "bg-stone-100 text-stone-500 text-[9px]"}>{c.active ? "Active" : "Inactive"}</Badge>
                        {isManager && <button onClick={() => deleteContract(c.id)} className="p-1 hover:bg-red-50 rounded"><Trash2 className="w-3 h-3 text-red-500" /></button>}
                      </div>
                    </div>
                    <div className="mt-2 flex items-center gap-3 text-[10px] text-stone-500">
                      <span>{c.start_date || "—"} → {c.end_date || "open"}</span>
                      <span>Pickup: {c.pickup_schedule}</span>
                    </div>
                    {c.rates?.length > 0 && (
                      <div className="mt-3 pt-2 border-t border-stone-100">
                        <p className="text-[10px] font-semibold text-stone-600 mb-1">Rates ({c.rates.length})</p>
                        <div className="grid grid-cols-2 gap-1 text-[10px]">
                          {c.rates.slice(0, 6).map((r, i) => (
                            <div key={i} className="flex justify-between text-stone-600"><span className="truncate">{r.name}</span><span className="font-mono">£{parseFloat(r.rate).toFixed(2)}</span></div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* REPORTS SECTION */}
      <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="laundry-reports">
        <h3 className="text-sm font-bold text-stone-800 mb-3 flex items-center gap-2">
          <FileBarChart className="w-4 h-4" />{L.reportsTitle || "Reports"}
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
          {REPORTS.map(r => {
            const Icon = r.icon;
            const label = { "daily-usage": L.repDailyUsage, count: L.repCount, order: L.repOrder, dispatch: L.repDispatch, "monthly-audit": L.repMonthly, "group-update": L.repGroup }[r.id] || r.label;
            const desc  = { "daily-usage": L.repDailyUsageDesc, count: L.repCountDesc, order: L.repOrderDesc, dispatch: L.repDispatchDesc, "monthly-audit": L.repMonthlyDesc, "group-update": L.repGroupDesc }[r.id] || r.desc;
            return (
              <button key={r.id} onClick={() => openReport(r)} data-testid={`report-${r.id}`}
                className="flex items-center gap-3 p-3 rounded-lg border border-stone-200 hover:border-stone-400 hover:bg-stone-50 text-left transition">
                <div className={`w-10 h-10 rounded-lg ${r.color} flex items-center justify-center flex-shrink-0`}>
                  <Icon className="w-5 h-5" />
                </div>
                <div className="min-w-0">
                  <h4 className="text-xs font-bold text-stone-800">{label}</h4>
                  <p className="text-[10px] text-stone-500 truncate">{desc}</p>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Report Viewer Dialog */}
      <Dialog open={!!reportOpen} onOpenChange={o => !o && setReportOpen(null)}>
        <DialogContent className="max-w-4xl max-h-[85vh] overflow-y-auto" data-testid="report-viewer">
          <DialogHeader>
            <DialogTitle className="flex items-center justify-between">
              <span>{reportOpen?.label}</span>
              {reportData && <Button size="sm" variant="outline" onClick={exportCSV}><Download className="w-3 h-3 mr-1" />Export CSV</Button>}
            </DialogTitle>
            <DialogDescription>{reportOpen?.desc} {reportData?.start && `· ${reportData.start} → ${reportData.end}`}</DialogDescription>
          </DialogHeader>
          {reportLoading ? (
            <div className="flex items-center justify-center py-10 text-stone-400"><RefreshCw className="w-5 h-5 animate-spin mr-2" />Loading report...</div>
          ) : !reportData ? null : (
            <div className="space-y-3">
              {reportOpen?.id === "daily-usage" && (
                <>
                  <div className="grid grid-cols-3 gap-2">
                    <div className="bg-stone-50 p-3 rounded-lg"><p className="text-[10px] text-stone-500">Total Items Used</p><p className="text-lg font-bold text-stone-800">{reportData.total_items}</p></div>
                    <div className="bg-stone-50 p-3 rounded-lg"><p className="text-[10px] text-stone-500">Unique Rooms</p><p className="text-lg font-bold text-stone-800">{Object.keys(reportData.by_room || {}).length}</p></div>
                    <div className="bg-stone-50 p-3 rounded-lg"><p className="text-[10px] text-stone-500">Active Days</p><p className="text-lg font-bold text-stone-800">{Object.keys(reportData.by_date || {}).length}</p></div>
                  </div>
                  <table className="w-full text-xs">
                    <thead className="bg-stone-50"><tr><th className="text-left p-2">Date</th><th className="text-left p-2">Room</th><th className="text-left p-2">Item</th><th className="text-center p-2">Qty</th></tr></thead>
                    <tbody>
                      {(reportData.rows || []).slice(0, 100).map((r, i) => (
                        <tr key={i} className="border-t border-stone-100"><td className="p-2">{r.date}</td><td className="p-2 font-semibold">{r.room_number}</td><td className="p-2">{r.item_name}</td><td className="p-2 text-center font-bold text-blue-700">{r.qty}</td></tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}
              {reportOpen?.id === "count" && (
                <table className="w-full text-xs">
                  <thead className="bg-stone-50"><tr><th className="text-left p-2">Item</th><th className="text-center p-2">Total</th><th className="text-center p-2">Days</th><th className="text-center p-2">Rooms</th><th className="text-center p-2">Daily Avg</th><th className="text-center p-2">Anomaly</th></tr></thead>
                  <tbody>
                    {(reportData.items || []).map((r, i) => (
                      <tr key={i} className="border-t border-stone-100"><td className="p-2 font-semibold">{r.item}</td><td className="p-2 text-center font-bold">{r.total}</td><td className="p-2 text-center">{r.days_active}</td><td className="p-2 text-center">{r.rooms_active}</td><td className="p-2 text-center">{r.daily_avg}</td><td className="p-2 text-center">{r.anomaly && <Badge className="bg-red-100 text-red-700 text-[9px]"><AlertCircle className="w-2 h-2 inline mr-0.5" />Anomaly</Badge>}</td></tr>
                    ))}
                  </tbody>
                </table>
              )}
              {reportOpen?.id === "order" && (
                <table className="w-full text-xs">
                  <thead className="bg-stone-50"><tr><th className="text-left p-2">Item</th><th className="text-center p-2">Sent</th><th className="text-center p-2">Received</th><th className="text-center p-2">Variance</th></tr></thead>
                  <tbody>
                    {(reportData.items || []).map((r, i) => (
                      <tr key={i} className="border-t border-stone-100"><td className="p-2 font-semibold">{r.item}</td><td className="p-2 text-center">{r.sent}</td><td className="p-2 text-center text-emerald-700">{r.received}</td><td className={`p-2 text-center font-bold ${r.variance > 0 ? "text-red-600" : "text-stone-400"}`}>{r.variance === 0 ? "—" : `-${r.variance}`}</td></tr>
                    ))}
                  </tbody>
                </table>
              )}
              {reportOpen?.id === "dispatch" && (
                <>
                  <div className="grid grid-cols-3 gap-2">
                    <div className="bg-stone-50 p-3 rounded-lg"><p className="text-[10px] text-stone-500">Total Dispatches</p><p className="text-lg font-bold">{reportData.dispatches?.length || 0}</p></div>
                    <div className="bg-stone-50 p-3 rounded-lg"><p className="text-[10px] text-stone-500">Items Sent</p><p className="text-lg font-bold">{reportData.total_items}</p></div>
                    <div className="bg-stone-50 p-3 rounded-lg"><p className="text-[10px] text-stone-500">Total Cost</p><p className="text-lg font-bold text-violet-700">£{reportData.total_cost?.toFixed(2)}</p></div>
                  </div>
                  <table className="w-full text-xs">
                    <thead className="bg-stone-50"><tr><th className="text-left p-2">Date</th><th className="text-left p-2">Vendor</th><th className="text-center p-2">Items</th><th className="text-right p-2">Cost</th><th className="text-center p-2">Status</th></tr></thead>
                    <tbody>
                      {(reportData.dispatches || []).map((d, i) => (
                        <tr key={i} className="border-t border-stone-100"><td className="p-2">{d.sent_date}</td><td className="p-2 font-semibold">{d.vendor}</td><td className="p-2 text-center">{d.items?.reduce((s, it) => s + it.qty_sent, 0)}</td><td className="p-2 text-right font-mono">£{d.total_cost?.toFixed(2)}</td><td className="p-2 text-center"><Badge className={`${DISPATCH_STATUS_STYLE[d.status]} text-[9px]`}>{d.status}</Badge></td></tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}
              {reportOpen?.id === "monthly-audit" && (
                <table className="w-full text-xs">
                  <thead className="bg-stone-50"><tr><th className="text-left p-2">Item</th><th className="text-center p-2">Clean</th><th className="text-center p-2">Dirty</th><th className="text-center p-2">In Transit</th><th className="text-center p-2">Damaged</th><th className="text-center p-2">Used</th><th className="text-center p-2">Dispatched</th><th className="text-center p-2">Total</th></tr></thead>
                  <tbody>
                    {(reportData.audit || []).map((a, i) => (
                      <tr key={i} className="border-t border-stone-100"><td className="p-2 font-semibold">{a.item}</td><td className="p-2 text-center text-emerald-700">{a.clean}</td><td className="p-2 text-center text-amber-700">{a.dirty}</td><td className="p-2 text-center text-blue-700">{a.in_transit}</td><td className="p-2 text-center text-red-600">{a.damaged}</td><td className="p-2 text-center">{a.used_in_period}</td><td className="p-2 text-center">{a.dispatched_in_period}</td><td className="p-2 text-center font-bold">{a.total_inventory}</td></tr>
                    ))}
                  </tbody>
                </table>
              )}
              {reportOpen?.id === "group-update" && (
                <table className="w-full text-xs">
                  <thead className="bg-stone-50"><tr><th className="text-left p-2">Date</th><th className="text-left p-2">Type</th><th className="text-left p-2">Item/Ref</th><th className="text-center p-2">Qty</th><th className="text-center p-2">Δ Clean</th><th className="text-center p-2">Δ Dirty</th></tr></thead>
                  <tbody>
                    {(reportData.events || []).slice(0, 100).map((e, i) => (
                      <tr key={i} className="border-t border-stone-100"><td className="p-2">{e.date}</td><td className="p-2"><Badge className="bg-stone-100 text-stone-600 text-[9px]">{e.type}</Badge></td><td className="p-2">{e.item} {e.ref ? `· ${e.ref}` : ""}</td><td className="p-2 text-center">{e.qty}</td><td className={`p-2 text-center font-mono ${e.delta_clean > 0 ? "text-emerald-700" : e.delta_clean < 0 ? "text-red-600" : "text-stone-400"}`}>{e.delta_clean > 0 ? "+" : ""}{e.delta_clean}</td><td className={`p-2 text-center font-mono ${e.delta_dirty > 0 ? "text-amber-700" : e.delta_dirty < 0 ? "text-emerald-700" : "text-stone-400"}`}>{e.delta_dirty > 0 ? "+" : ""}{e.delta_dirty}</td></tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Dispatch Dialog — Ready table (dirty + unusable) · mobile + i18n */}
      <Dialog open={dispOpen} onOpenChange={setDispOpen}>
        <DialogContent className="w-[95vw] max-w-4xl max-h-[95vh] overflow-y-auto p-4 sm:p-6">
          <DialogHeader className="space-y-2">
            <div className="flex items-start justify-between gap-2 flex-wrap">
              <DialogTitle className="text-base sm:text-lg">{L.dispTitle}</DialogTitle>
              <div className="flex gap-1 bg-stone-100 rounded-lg p-1" data-testid="disp-lang-switcher">
                {Object.keys(LAUNDRY_I18N).map(code => (
                  <button key={code} onClick={() => setLang(code)}
                    className={`px-2 py-1 text-xs font-semibold rounded transition ${lang === code ? "bg-white text-stone-800 shadow" : "text-stone-500"}`}>
                    {LAUNDRY_I18N[code].flag} {code.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>
            <DialogDescription className="text-xs sm:text-sm">{L.dispSubtitle}</DialogDescription>
          </DialogHeader>
          <div className="space-y-3 sm:space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div><label className="text-xs font-semibold text-stone-600">{L.vendor} *</label><Input value={dispForm.vendor} onChange={e => setDispForm({ ...dispForm, vendor: e.target.value })} className="h-10" data-testid="dispatch-vendor-input" /></div>
              <div><label className="text-xs font-semibold text-stone-600">{L.date}</label><Input type="date" value={dispForm.sent_date} onChange={e => setDispForm({ ...dispForm, sent_date: e.target.value })} className="h-10" /></div>
              <div><label className="text-xs font-semibold text-stone-600">{L.dispExpectedReturn}</label><Input type="date" value={dispForm.expected_return} onChange={e => setDispForm({ ...dispForm, expected_return: e.target.value })} className="h-10" /></div>
            </div>

            {/* Desktop table */}
            <div className="hidden sm:block border border-stone-200 rounded-xl overflow-hidden bg-white">
              <table className="w-full text-sm" data-testid="dispatch-readytable">
                <thead className="bg-stone-50 border-b border-stone-200">
                  <tr>
                    <th className="text-left py-2.5 px-3 font-semibold text-stone-700 w-[40%]">{L.item}</th>
                    <th className="text-center py-2.5 px-2 font-semibold text-amber-700">{L.dispDirtySent}</th>
                    <th className="text-center py-2.5 px-2 font-semibold text-rose-700">{L.dispUnusableSent}</th>
                    <th className="text-right py-2.5 px-2 font-semibold text-stone-600">{L.dispRate}</th>
                    <th className="text-right py-2.5 px-2 font-semibold text-stone-600">{L.dispLineTotal}</th>
                  </tr>
                </thead>
                <tbody>
                  {(dispForm.items || []).map((it, i) => {
                    const lineTotal = (it.qty_sent || 0) * (it.rate || 0);
                    return (
                    <tr key={it.item_id || i} className="border-b border-stone-100">
                      <td className="py-2 px-3"><div className="font-semibold text-stone-800">{it.name || "—"}</div><div className="text-[10px] text-stone-400">{it.item_id}</div></td>
                      <td className="py-1 px-2"><Input type="number" min="0" inputMode="numeric" value={it.qty_sent || 0} onChange={e => updateDispItem(i, { qty_sent: parseInt(e.target.value) || 0 })} className="h-9 text-center font-mono font-bold bg-amber-50 border-amber-200" data-testid={`disp-dirty-${it.item_id}`} /></td>
                      <td className="py-1 px-2"><Input type="number" min="0" inputMode="numeric" value={it.qty_unusable_sent || 0} onChange={e => updateDispItem(i, { qty_unusable_sent: parseInt(e.target.value) || 0 })} className="h-9 text-center font-mono font-bold bg-rose-50 border-rose-200" data-testid={`disp-unus-${it.item_id}`} /></td>
                      <td className="py-1 px-2"><Input type="number" step="0.01" min="0" value={it.rate || 0} onChange={e => updateDispItem(i, { rate: parseFloat(e.target.value) || 0 })} className="h-9 text-right font-mono bg-white" /></td>
                      <td className="py-2 px-2 text-right font-mono font-bold text-stone-800">£{lineTotal.toFixed(2)}</td>
                    </tr>
                    );
                  })}
                </tbody>
                <tfoot className="bg-stone-50 border-t-2 border-stone-200">
                  <tr>
                    <td className="py-2 px-3 text-right font-bold text-stone-700">{L.totals}</td>
                    <td className="py-2 px-2 text-center font-mono font-black text-amber-700">{dispForm.items?.reduce((s, i) => s + (i.qty_sent || 0), 0) || 0}</td>
                    <td className="py-2 px-2 text-center font-mono font-black text-rose-700">{dispForm.items?.reduce((s, i) => s + (i.qty_unusable_sent || 0), 0) || 0}</td>
                    <td></td>
                    <td className="py-2 px-2 text-right font-mono font-black text-stone-900">£{(dispForm.items?.reduce((s, i) => s + ((i.qty_sent || 0) * (i.rate || 0)), 0) || 0).toFixed(2)}</td>
                  </tr>
                </tfoot>
              </table>
            </div>

            {/* Mobile cards */}
            <div className="sm:hidden space-y-2">
              {(dispForm.items || []).map((it, i) => (
                <div key={it.item_id || i} className="bg-white border border-stone-200 rounded-xl p-3">
                  <div className="font-bold text-sm text-stone-800 mb-2">{it.name || "—"}</div>
                  <div className="grid grid-cols-2 gap-2">
                    <div><label className="text-[10px] font-bold uppercase text-amber-700">{L.dispDirtySent}</label><Input type="number" min="0" inputMode="numeric" value={it.qty_sent || 0} onChange={e => updateDispItem(i, { qty_sent: parseInt(e.target.value) || 0 })} className="h-11 text-center text-base font-mono font-bold bg-amber-50 border-amber-200" /></div>
                    <div><label className="text-[10px] font-bold uppercase text-rose-700">{L.dispUnusableSent}</label><Input type="number" min="0" inputMode="numeric" value={it.qty_unusable_sent || 0} onChange={e => updateDispItem(i, { qty_unusable_sent: parseInt(e.target.value) || 0 })} className="h-11 text-center text-base font-mono font-bold bg-rose-50 border-rose-200" /></div>
                    <div><label className="text-[10px] font-bold uppercase text-stone-500">{L.dispRate}</label><Input type="number" step="0.01" min="0" value={it.rate || 0} onChange={e => updateDispItem(i, { rate: parseFloat(e.target.value) || 0 })} className="h-11 text-right text-base font-mono" /></div>
                    <div className="flex flex-col justify-end"><label className="text-[10px] font-bold uppercase text-stone-500">{L.dispLineTotal}</label><div className="h-11 flex items-center justify-end pr-2 font-mono font-black text-stone-800">£{((it.qty_sent || 0) * (it.rate || 0)).toFixed(2)}</div></div>
                  </div>
                </div>
              ))}
            </div>

            <div className="grid grid-cols-2 gap-2 text-[10px] sm:text-[11px]">
              <div className="flex items-start gap-1.5 bg-amber-50 border border-amber-200 rounded-lg px-2 py-1.5"><span className="w-2 h-2 rounded-full bg-amber-500 mt-1 shrink-0"></span><div><b>{L.dispDirtySent}:</b> {L.dispDirtyHint}</div></div>
              <div className="flex items-start gap-1.5 bg-rose-50 border border-rose-200 rounded-lg px-2 py-1.5"><span className="w-2 h-2 rounded-full bg-rose-500 mt-1 shrink-0"></span><div><b>{L.dispUnusableSent}:</b> {L.dispUnusableHint}</div></div>
            </div>

            <div><label className="text-xs font-semibold text-stone-600">{L.notes}</label><Textarea value={dispForm.notes} onChange={e => setDispForm({ ...dispForm, notes: e.target.value })} rows={2} placeholder={L.notesPh} /></div>
          </div>
          <DialogFooter className="flex-col-reverse sm:flex-row gap-2">
            <Button variant="outline" size="sm" onClick={() => setDispOpen(false)} className="w-full sm:w-auto">{L.cancel}</Button>
            <Button size="sm" className="w-full sm:w-auto bg-emerald-600 hover:bg-emerald-700 text-white h-11 sm:h-9" onClick={submitDispatch} data-testid="dispatch-submit-btn">
              <CheckCircle2 className="w-4 h-4 mr-1" />{L.submit}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Usage Dialog — Mobile-friendly ready table + i18n (EN/TR/BG) */}
      <Dialog open={usageOpen} onOpenChange={setUsageOpen}>
        <DialogContent className="w-[95vw] max-w-4xl max-h-[95vh] overflow-y-auto p-4 sm:p-6">
          <DialogHeader className="space-y-2">
            <div className="flex items-start justify-between gap-2 flex-wrap">
              <DialogTitle className="text-base sm:text-lg">{L.title}</DialogTitle>
              {/* Language picker */}
              <div className="flex gap-1 bg-stone-100 rounded-lg p-1" data-testid="usage-lang-switcher">
                {Object.keys(LAUNDRY_I18N).map(code => (
                  <button key={code} onClick={() => setLang(code)}
                    className={`px-2 py-1 text-xs font-semibold rounded transition ${lang === code ? "bg-white text-stone-800 shadow" : "text-stone-500 hover:text-stone-700"}`}
                    data-testid={`lang-${code}`}>
                    {LAUNDRY_I18N[code].flag} {code.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>
            <DialogDescription className="text-xs sm:text-sm">{L.subtitle}</DialogDescription>
          </DialogHeader>
          <div className="space-y-3 sm:space-y-4">
            {/* Date + Room */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-semibold text-stone-600">{L.date} <span className="text-red-500">*</span></label>
                <Input type="date" value={usageForm.date} onChange={e => setUsageForm({ ...usageForm, date: e.target.value })} className="h-10" data-testid="usage-date-input" />
              </div>
              <div>
                <label className="text-xs font-semibold text-stone-600">{L.room} <span className="text-red-500">*</span></label>
                {rooms.length > 0 ? (
                  <Select value={usageForm.room_id} onValueChange={v => {
                    const r = rooms.find(x => (x.id || x.room_id) === v);
                    setUsageForm({ ...usageForm, room_id: v, room_number: r?.number || r?.room_number || v });
                  }}>
                    <SelectTrigger className="h-10" data-testid="usage-room-select"><SelectValue placeholder={L.selectRoom} /></SelectTrigger>
                    <SelectContent>{rooms.slice(0, 200).map(r => <SelectItem key={r.id || r.room_id} value={r.id || r.room_id}>{r.number || r.room_number || r.name}</SelectItem>)}</SelectContent>
                  </Select>
                ) : (
                  <Input value={usageForm.room_number} onChange={e => setUsageForm({ ...usageForm, room_number: e.target.value, room_id: e.target.value })} placeholder={L.roomPlaceholder} className="h-10" data-testid="usage-room-input" />
                )}
              </div>
            </div>

            {/* Pre-filled ready grid — desktop=table, mobile=cards */}
            {usageForm.items.length === 0 ? (
              <div className="py-8 text-center text-sm text-stone-400">{L.loading}</div>
            ) : (
              <>
                {/* Desktop table (sm+) */}
                <div className="hidden sm:block border border-stone-200 rounded-xl overflow-hidden bg-white">
                  <table className="w-full text-sm" data-testid="usage-readytable">
                    <thead className="bg-stone-50 border-b border-stone-200">
                      <tr>
                        <th className="text-left py-2.5 px-3 font-semibold text-stone-700 w-[35%]">{L.item}</th>
                        <th className="text-center py-2.5 px-2 font-semibold text-emerald-700">{L.used} ↓</th>
                        <th className="text-center py-2.5 px-2 font-semibold text-amber-700">{L.collected} ↑</th>
                        <th className="text-center py-2.5 px-2 font-semibold text-rose-700">{L.unusable}</th>
                        <th className="text-center py-2.5 px-2 font-semibold text-fuchsia-700">{L.damaged}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {usageForm.items.map((it, i) => (
                        <tr key={it.item_id} className="border-b border-stone-100 hover:bg-stone-50/50" data-testid={`usage-row-${it.item_id}`}>
                          <td className="py-2 px-3">
                            <div className="font-semibold text-stone-800">{it.item_name}</div>
                            <div className="text-[10px] text-stone-400">{it.item_id}</div>
                          </td>
                          <td className="py-1 px-2">
                            <Input type="number" min="0" inputMode="numeric" value={it.clean_used || 0}
                                   onChange={e => updateUsageItem(i, { clean_used: parseInt(e.target.value) || 0 })}
                                   className="h-9 text-center font-mono font-bold bg-emerald-50 border-emerald-200" data-testid={`usage-clean-${it.item_id}`} />
                          </td>
                          <td className="py-1 px-2">
                            <Input type="number" min="0" inputMode="numeric" value={it.dirty_collected || 0}
                                   onChange={e => updateUsageItem(i, { dirty_collected: parseInt(e.target.value) || 0 })}
                                   className="h-9 text-center font-mono font-bold bg-amber-50 border-amber-200" data-testid={`usage-dirty-${it.item_id}`} />
                          </td>
                          <td className="py-1 px-2">
                            <Input type="number" min="0" inputMode="numeric" value={it.factory_unusable || 0}
                                   onChange={e => updateUsageItem(i, { factory_unusable: parseInt(e.target.value) || 0 })}
                                   className="h-9 text-center font-mono font-bold bg-rose-50 border-rose-200" data-testid={`usage-unusable-${it.item_id}`} />
                          </td>
                          <td className="py-1 px-2">
                            <Input type="number" min="0" inputMode="numeric" value={it.guest_damaged || 0}
                                   onChange={e => updateUsageItem(i, { guest_damaged: parseInt(e.target.value) || 0 })}
                                   className="h-9 text-center font-mono font-bold bg-fuchsia-50 border-fuchsia-200" data-testid={`usage-damaged-${it.item_id}`} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot className="bg-stone-50 border-t-2 border-stone-200">
                      <tr>
                        <td className="py-2 px-3 text-right font-bold text-stone-700">{L.totals}</td>
                        <td className="py-2 px-2 text-center font-mono font-black text-emerald-700">{usageForm.items.reduce((s, i) => s + (i.clean_used || 0), 0)}</td>
                        <td className="py-2 px-2 text-center font-mono font-black text-amber-700">{usageForm.items.reduce((s, i) => s + (i.dirty_collected || 0), 0)}</td>
                        <td className="py-2 px-2 text-center font-mono font-black text-rose-700">{usageForm.items.reduce((s, i) => s + (i.factory_unusable || 0), 0)}</td>
                        <td className="py-2 px-2 text-center font-mono font-black text-fuchsia-700">{usageForm.items.reduce((s, i) => s + (i.guest_damaged || 0), 0)}</td>
                      </tr>
                    </tfoot>
                  </table>
                </div>

                {/* Mobile card layout (<sm) — one card per item, 2x2 qty grid */}
                <div className="sm:hidden space-y-2">
                  {usageForm.items.map((it, i) => (
                    <div key={it.item_id} className="bg-white border border-stone-200 rounded-xl p-3" data-testid={`usage-card-${it.item_id}`}>
                      <div className="font-bold text-sm text-stone-800 mb-2">{it.item_name}</div>
                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <label className="text-[10px] font-bold uppercase text-emerald-700">{L.used} ↓</label>
                          <Input type="number" min="0" inputMode="numeric" value={it.clean_used || 0}
                                 onChange={e => updateUsageItem(i, { clean_used: parseInt(e.target.value) || 0 })}
                                 className="h-11 text-center text-base font-mono font-bold bg-emerald-50 border-emerald-200 mt-0.5" data-testid={`usage-clean-${it.item_id}`} />
                        </div>
                        <div>
                          <label className="text-[10px] font-bold uppercase text-amber-700">{L.collected} ↑</label>
                          <Input type="number" min="0" inputMode="numeric" value={it.dirty_collected || 0}
                                 onChange={e => updateUsageItem(i, { dirty_collected: parseInt(e.target.value) || 0 })}
                                 className="h-11 text-center text-base font-mono font-bold bg-amber-50 border-amber-200 mt-0.5" data-testid={`usage-dirty-${it.item_id}`} />
                        </div>
                        <div>
                          <label className="text-[10px] font-bold uppercase text-rose-700">{L.unusable}</label>
                          <Input type="number" min="0" inputMode="numeric" value={it.factory_unusable || 0}
                                 onChange={e => updateUsageItem(i, { factory_unusable: parseInt(e.target.value) || 0 })}
                                 className="h-11 text-center text-base font-mono font-bold bg-rose-50 border-rose-200 mt-0.5" data-testid={`usage-unusable-${it.item_id}`} />
                        </div>
                        <div>
                          <label className="text-[10px] font-bold uppercase text-fuchsia-700">{L.damaged}</label>
                          <Input type="number" min="0" inputMode="numeric" value={it.guest_damaged || 0}
                                 onChange={e => updateUsageItem(i, { guest_damaged: parseInt(e.target.value) || 0 })}
                                 className="h-11 text-center text-base font-mono font-bold bg-fuchsia-50 border-fuchsia-200 mt-0.5" data-testid={`usage-damaged-${it.item_id}`} />
                        </div>
                      </div>
                    </div>
                  ))}
                  {/* Mobile totals row */}
                  <div className="bg-stone-50 border border-stone-300 rounded-xl p-3 flex items-center justify-between sticky bottom-0">
                    <span className="text-sm font-bold text-stone-700">{L.totals}</span>
                    <div className="flex gap-2 text-xs font-mono font-black">
                      <span className="text-emerald-700">↓{usageForm.items.reduce((s, i) => s + (i.clean_used || 0), 0)}</span>
                      <span className="text-amber-700">↑{usageForm.items.reduce((s, i) => s + (i.dirty_collected || 0), 0)}</span>
                      <span className="text-rose-700">✗{usageForm.items.reduce((s, i) => s + (i.factory_unusable || 0), 0)}</span>
                      <span className="text-fuchsia-700">!{usageForm.items.reduce((s, i) => s + (i.guest_damaged || 0), 0)}</span>
                    </div>
                  </div>
                </div>
              </>
            )}

            {/* Column legend */}
            <div className="grid grid-cols-2 gap-2 text-[10px] sm:text-[11px]">
              <div className="flex items-start gap-1.5 bg-emerald-50 border border-emerald-200 rounded-lg px-2 py-1.5"><span className="w-2 h-2 rounded-full bg-emerald-500 mt-1 shrink-0"></span><div><b>{L.used}:</b> {L.usedHint}</div></div>
              <div className="flex items-start gap-1.5 bg-amber-50 border border-amber-200 rounded-lg px-2 py-1.5"><span className="w-2 h-2 rounded-full bg-amber-500 mt-1 shrink-0"></span><div><b>{L.collected}:</b> {L.collectedHint}</div></div>
              <div className="flex items-start gap-1.5 bg-rose-50 border border-rose-200 rounded-lg px-2 py-1.5"><span className="w-2 h-2 rounded-full bg-rose-500 mt-1 shrink-0"></span><div><b>{L.unusable}:</b> {L.unusableHint}</div></div>
              <div className="flex items-start gap-1.5 bg-fuchsia-50 border border-fuchsia-200 rounded-lg px-2 py-1.5"><span className="w-2 h-2 rounded-full bg-fuchsia-500 mt-1 shrink-0"></span><div><b>{L.damaged}:</b> {L.damagedHint}</div></div>
            </div>

            {/* Photos */}
            <PhotoCapture photos={usageForm.photos || []} onChange={(ps) => setUsageForm(f => ({ ...f, photos: ps }))} L={L} />

            {/* Notes */}
            <div>
              <label className="text-xs font-semibold text-stone-600">{L.notes}</label>
              <Textarea value={usageForm.notes || ""} onChange={e => setUsageForm(f => ({ ...f, notes: e.target.value }))}
                     rows={2} placeholder={L.notesPh} className="text-xs sm:text-sm" data-testid="usage-notes-input" />
            </div>
          </div>
          <DialogFooter className="flex-col-reverse sm:flex-row gap-2">
            <Button variant="outline" size="sm" onClick={() => setUsageOpen(false)} className="w-full sm:w-auto">{L.cancel}</Button>
            <Button size="sm" className="w-full sm:w-auto bg-emerald-600 hover:bg-emerald-700 text-white h-11 sm:h-9" onClick={submitUsage} data-testid="usage-submit-btn">
              <CheckCircle2 className="w-4 h-4 mr-1" />{L.submit}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Contract Dialog */}
      <Dialog open={contractOpen} onOpenChange={setContractOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle>New Laundry Contract</DialogTitle><DialogDescription>Set up rate card and terms with a laundry vendor.</DialogDescription></DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <div><label className="text-xs font-semibold text-stone-600">Vendor</label><Input value={contractForm.vendor} onChange={e => setContractForm({ ...contractForm, vendor: e.target.value })} data-testid="contract-vendor-input" /></div>
              <div><label className="text-xs font-semibold text-stone-600">Pickup Schedule</label><Select value={contractForm.pickup_schedule} onValueChange={v => setContractForm({ ...contractForm, pickup_schedule: v })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="daily">Daily</SelectItem><SelectItem value="weekly">Weekly</SelectItem><SelectItem value="biweekly">Bi-Weekly</SelectItem><SelectItem value="monthly">Monthly</SelectItem><SelectItem value="on_demand">On Demand</SelectItem></SelectContent></Select></div>
            </div>
            <div className="grid grid-cols-3 gap-2">
              <Input placeholder="Contact Name" value={contractForm.contact_name} onChange={e => setContractForm({ ...contractForm, contact_name: e.target.value })} />
              <Input placeholder="Email" value={contractForm.contact_email} onChange={e => setContractForm({ ...contractForm, contact_email: e.target.value })} />
              <Input placeholder="Phone" value={contractForm.contact_phone} onChange={e => setContractForm({ ...contractForm, contact_phone: e.target.value })} />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div><label className="text-xs font-semibold text-stone-600">Start Date</label><Input type="date" value={contractForm.start_date} onChange={e => setContractForm({ ...contractForm, start_date: e.target.value })} /></div>
              <div><label className="text-xs font-semibold text-stone-600">End Date</label><Input type="date" value={contractForm.end_date} onChange={e => setContractForm({ ...contractForm, end_date: e.target.value })} /></div>
            </div>
            <div>
              <div className="flex items-center justify-between mb-1"><label className="text-xs font-semibold text-stone-600">Rate Card</label><Button size="sm" variant="outline" onClick={addRate}><Plus className="w-3 h-3 mr-1" />Add Rate</Button></div>
              {contractForm.rates.map((r, i) => (
                <div key={i} className="grid grid-cols-12 gap-1.5 mb-1.5">
                  <Select value={r.item_id} onValueChange={v => updateRate(i, { item_id: v })}><SelectTrigger className="col-span-8 h-8 text-xs"><SelectValue placeholder="Select item" /></SelectTrigger><SelectContent>{catalog.map(c => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}</SelectContent></Select>
                  <Input type="number" step="0.01" value={r.rate} onChange={e => updateRate(i, { rate: parseFloat(e.target.value) || 0 })} placeholder="£ per item" className="col-span-4 h-8 text-xs" />
                </div>
              ))}
            </div>
            <div><label className="text-xs font-semibold text-stone-600">Terms</label><Textarea value={contractForm.terms} onChange={e => setContractForm({ ...contractForm, terms: e.target.value })} rows={3} /></div>
          </div>
          <DialogFooter><Button variant="outline" size="sm" onClick={() => setContractOpen(false)}>Cancel</Button><Button size="sm" className="bg-stone-800 hover:bg-stone-700 text-white" onClick={submitContract} data-testid="contract-submit-btn">Create Contract</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Email Dispatch Dialog */}
      <Dialog open={!!emailDispatch} onOpenChange={o => !o && setEmailDispatch(null)}>
        <DialogContent className="w-[95vw] max-w-md p-4 sm:p-6">
          <DialogHeader>
            <DialogTitle className="text-base flex items-center gap-2">
              <Mail className="w-4 h-4" /> Email Dispatch to Vendor
            </DialogTitle>
            <DialogDescription className="text-xs">
              PDF will be attached automatically. Use commas for multiple recipients.
            </DialogDescription>
          </DialogHeader>
          {emailDispatch && (
            <div className="space-y-3">
              <div className="bg-stone-50 border border-stone-200 rounded-lg p-3 text-xs space-y-1">
                <div className="flex justify-between"><span className="text-stone-500">{L.vendor}:</span><span className="font-bold">{emailDispatch.vendor}</span></div>
                <div className="flex justify-between"><span className="text-stone-500">{L.date}:</span><span className="font-bold">{emailDispatch.sent_date}</span></div>
                <div className="flex justify-between"><span className="text-stone-500">Pieces:</span><span className="font-mono font-bold">{(emailDispatch.items || []).reduce((s, i) => s + (i.qty_sent || 0) + (i.qty_unusable_sent || 0), 0)}</span></div>
              </div>
              <div>
                <label className="text-xs font-semibold text-stone-600">Recipient email(s) *</label>
                <Input type="email" value={emailTo} onChange={e => setEmailTo(e.target.value)}
                       placeholder="vendor@example.com, second@example.com" className="h-10"
                       data-testid="email-dispatch-to-input" />
              </div>
              {emailDispatch.email_history?.length > 0 && (
                <div className="text-[11px] text-stone-500">
                  Previously sent: {emailDispatch.email_history.length}× —
                  last on {emailDispatch.email_history[emailDispatch.email_history.length - 1]?.at?.slice(0, 10)}
                </div>
              )}
            </div>
          )}
          <DialogFooter className="flex-col-reverse sm:flex-row gap-2">
            <Button variant="outline" size="sm" onClick={() => { setEmailDispatch(null); setEmailTo(""); }} className="w-full sm:w-auto">{L.cancel}</Button>
            <Button size="sm" className="w-full sm:w-auto bg-violet-600 hover:bg-violet-700 text-white" onClick={sendDispatchEmail} disabled={emailSending} data-testid="email-dispatch-send">
              {emailSending ? <RefreshCw className="w-4 h-4 mr-1 animate-spin" /> : <Mail className="w-4 h-4 mr-1" />}
              Send Email
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* QR Code Dialog — future-ready for factory scan */}
      <Dialog open={!!qrDispatch} onOpenChange={o => !o && setQrDispatch(null)}>
        <DialogContent className="w-[95vw] max-w-md p-4 sm:p-6">
          <DialogHeader>
            <DialogTitle className="text-base flex items-center gap-2">
              <QrCode className="w-4 h-4" /> Dispatch QR Code
            </DialogTitle>
            <DialogDescription className="text-xs">
              Print this QR and attach to the dispatch bag. In the future, when the factory or receiving staff scans it, the entire dispatch list opens instantly — no manual search.
            </DialogDescription>
          </DialogHeader>
          {qrDispatch && (
            <div className="space-y-3 print:p-4" id="qr-print-area">
              <div className="flex justify-center bg-white p-6 rounded-xl border-2 border-stone-200">
                <QRCodeSVG
                  value={JSON.stringify({
                    t: "laundry_dispatch",
                    id: qrDispatch.id,
                    pid: qrDispatch.property_id,
                    vendor: qrDispatch.vendor,
                    sent: qrDispatch.sent_date,
                    dirty: qrDispatch.total_dirty_sent || qrDispatch.items?.reduce((s, i) => s + (i.qty_sent || 0), 0) || 0,
                    unusable: qrDispatch.total_unusable_sent || qrDispatch.items?.reduce((s, i) => s + (i.qty_unusable_sent || 0), 0) || 0,
                  })}
                  size={220} level="M" includeMargin={true}
                  data-testid="dispatch-qr-svg"
                />
              </div>
              <div className="bg-stone-50 border border-stone-200 rounded-lg p-3 text-xs space-y-1">
                <div className="flex justify-between"><span className="text-stone-500">Dispatch ID:</span><span className="font-mono font-semibold">{qrDispatch.id.slice(0, 8)}…</span></div>
                <div className="flex justify-between"><span className="text-stone-500">{L.vendor}:</span><span className="font-semibold">{qrDispatch.vendor}</span></div>
                <div className="flex justify-between"><span className="text-stone-500">{L.date}:</span><span className="font-semibold">{qrDispatch.sent_date}</span></div>
                <div className="flex justify-between"><span className="text-stone-500">{L.dispDirtySent}:</span><span className="font-mono font-black text-amber-700">{qrDispatch.total_dirty_sent || qrDispatch.items?.reduce((s, i) => s + (i.qty_sent || 0), 0) || 0}</span></div>
                <div className="flex justify-between"><span className="text-stone-500">{L.dispUnusableSent}:</span><span className="font-mono font-black text-rose-700">{qrDispatch.total_unusable_sent || qrDispatch.items?.reduce((s, i) => s + (i.qty_unusable_sent || 0), 0) || 0}</span></div>
              </div>
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-2.5 text-[11px] text-blue-800">
                💡 QR payload: JSON containing dispatch ID + vendor + counts. Any QR-enabled scanner app can decode it. When factory adopts scanning, we'll add instant delivery auto-fill.
              </div>
            </div>
          )}
          <DialogFooter className="flex-col-reverse sm:flex-row gap-2 print:hidden">
            <Button variant="outline" size="sm" onClick={() => setQrDispatch(null)} className="w-full sm:w-auto">{L.cancel}</Button>
            <Button size="sm" className="w-full sm:w-auto bg-blue-600 hover:bg-blue-700 text-white" onClick={() => window.print()} data-testid="qr-print-btn">
              <Printer className="w-4 h-4 mr-1" />Print
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

/* ═══════════ STOCK TAB — with transactions (maintenance/disposal/write-off) ═══════════ */
const StockTab = ({ pid, stock, updateStockCell, lang, setLang, L }) => {
  const [txns, setTxns] = useState([]);
  const [stats, setStats] = useState({});
  const [filter, setFilter] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [txType, setTxType] = useState("maintenance");
  const today = new Date().toISOString().slice(0, 10);
  const [form, setForm] = useState({
    item_id: "", name: "", quantity: 1, unit_cost: 0,
    transaction_date: today, reason: "", notes: "",
  });

  const loadTxns = async () => {
    try {
      const qs = filter ? `?tx_type=${filter}` : "";
      const { data } = await axios.get(`${API}/laundry/stock-transactions/${pid}${qs}`);
      setTxns(data.rows || []); setStats(data.stats || {});
    } catch { /* */ }
  };
  useEffect(() => { loadTxns(); /* eslint-disable-next-line */ }, [pid, filter]);

  const save = async () => {
    if (!form.item_id) return toast.error(L?.stockSelectItem || "Select an item");
    try {
      await axios.post(`${API}/laundry/stock-transactions/${pid}`, { ...form, tx_type: txType, reason: form.reason || txType });
      toast.success(`${txType} ${L?.stockRecorded || "recorded"}`);
      setShowForm(false);
      setForm({ item_id: "", name: "", quantity: 1, unit_cost: 0, transaction_date: today, reason: "", notes: "" });
      loadTxns();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const del = async (id) => {
    if (!window.confirm(L?.stockTxDelConfirm || "Delete this transaction?")) return;
    await axios.delete(`${API}/laundry/stock-transactions/${id}`);
    toast.success(L?.stockDeleted || "Deleted"); loadTxns();
  };

  const openForm = (type) => { setTxType(type); setForm(f => ({ ...f, reason: type })); setShowForm(true); };

  const typeBadge = (t) => ({
    maintenance: "bg-amber-100 text-amber-700",
    disposal:    "bg-rose-100 text-rose-700",
    write_off:   "bg-stone-200 text-stone-700",
    found:       "bg-emerald-100 text-emerald-700",
    stock_in:    "bg-blue-100 text-blue-700",
    stock_out:   "bg-violet-100 text-violet-700",
  }[t] || "bg-stone-100 text-stone-600");

  return (
    <div className="space-y-3" data-testid="stock-panel">
      {/* Language toggle */}
      {setLang && (
        <div className="flex items-center justify-end">
          <div className="flex gap-1 bg-stone-100 rounded-lg p-1">
            {Object.keys(LAUNDRY_I18N).map(code => (
              <button key={code} onClick={() => setLang(code)}
                className={`px-2 py-1 text-xs font-semibold rounded transition ${lang === code ? "bg-white text-stone-800 shadow" : "text-stone-500 hover:text-stone-700"}`}
                data-testid={`stock-lang-${code}`}>
                {LAUNDRY_I18N[code].flag} {code.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Quick-action buttons */}
      <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
        {[
          { k: "maintenance", l: L?.stockMaint || "Maintenance",  c: "border-amber-300 text-amber-700 hover:bg-amber-50" },
          { k: "disposal",    l: L?.stockDisp  || "Disposal",     c: "border-rose-300 text-rose-700 hover:bg-rose-50" },
          { k: "write_off",   l: L?.stockWO    || "Write-Off",    c: "border-stone-300 text-stone-700 hover:bg-stone-100" },
          { k: "found",       l: L?.stockFound || "Found",        c: "border-emerald-300 text-emerald-700 hover:bg-emerald-50" },
          { k: "stock_in",    l: L?.stockIn    || "Stock In",     c: "border-blue-300 text-blue-700 hover:bg-blue-50" },
          { k: "stock_out",   l: L?.stockOut   || "Stock Out",    c: "border-violet-300 text-violet-700 hover:bg-violet-50" },
        ].map(b => (
          <button key={b.k} onClick={() => openForm(b.k)} className={`px-3 py-2.5 border rounded-xl text-xs font-semibold ${b.c}`} data-testid={`stock-tx-${b.k}-btn`}>
            + {b.l}
          </button>
        ))}
      </div>

      {/* Stat chips */}
      {Object.keys(stats).length > 0 && (
        <div className="flex gap-2 flex-wrap">
          {Object.entries(stats).map(([k, v]) => (
            <button key={k} onClick={() => setFilter(filter === k ? "" : k)} className={`px-3 py-1.5 rounded-lg text-xs border transition ${filter === k ? "bg-blue-50 border-blue-300" : "bg-white border-stone-200"}`}>
              <span className="font-semibold capitalize">{k.replace("_", " ")}</span>
              <span className="text-stone-500 ml-2">{v.count} · {v.qty} items · £{v.cost.toFixed(2)}</span>
            </button>
          ))}
          {filter && <button onClick={() => setFilter("")} className="px-2 py-1 text-xs text-stone-500 hover:text-stone-700">Clear filter ×</button>}
        </div>
      )}

      {/* Current Stock table */}
      <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
        <div className="px-3 py-2 bg-stone-50 border-b border-stone-200 text-xs font-bold text-stone-700">{L?.stockTitle || "Current Stock Levels"}</div>
        <table className="w-full text-xs">
          <thead className="bg-stone-50 border-b border-stone-200">
            <tr>
              <th className="text-left py-2 px-3 font-semibold text-stone-600">{L?.item || "Item"}</th>
              <th className="text-center py-2 px-3 font-semibold text-emerald-600">{L?.stockClean || "Clean"}</th>
              <th className="text-center py-2 px-3 font-semibold text-amber-600">{L?.stockDirty || "Dirty"}</th>
              <th className="text-center py-2 px-3 font-semibold text-blue-600">{L?.stockInTransit || "In Transit"}</th>
              <th className="text-center py-2 px-3 font-semibold text-amber-700" title={L?.roomDamagedHint}>{L?.roomDamaged || "Damaged (room)"}</th>
              <th className="text-center py-2 px-3 font-semibold text-stone-600">{L?.stockTotalCol || "Total"}</th>
            </tr>
          </thead>
          <tbody>
            {stock.map(s => (
              <tr key={s.item_id} className="border-b border-stone-100 hover:bg-stone-50/50" data-testid={`stock-row-${s.item_id}`}>
                <td className="py-2 px-3 font-semibold text-stone-700">{s.name}</td>
                <td className="py-2 px-3 text-center"><input type="number" value={s.on_hand_clean} onChange={e => updateStockCell(s.item_id, "on_hand_clean", e.target.value)} className="w-16 text-center border border-stone-200 rounded px-1 py-0.5 text-xs" /></td>
                <td className="py-2 px-3 text-center"><input type="number" value={s.dirty} onChange={e => updateStockCell(s.item_id, "dirty", e.target.value)} className="w-16 text-center border border-stone-200 rounded px-1 py-0.5 text-xs" /></td>
                <td className="py-2 px-3 text-center font-semibold text-blue-600">{s.in_transit}</td>
                <td className="py-2 px-3 text-center"><input type="number" value={s.damaged} onChange={e => updateStockCell(s.item_id, "damaged", e.target.value)} className="w-16 text-center border border-stone-200 rounded px-1 py-0.5 text-xs" /></td>
                <td className="py-2 px-3 text-center font-bold text-stone-800">{s.total}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Transaction history */}
      <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
        <div className="px-3 py-2 bg-stone-50 border-b border-stone-200 text-xs font-bold text-stone-700">{L?.stockHistory || "Transaction History"} ({txns.length})</div>
        {txns.length === 0 ? (
          <p className="text-center text-sm text-stone-400 py-8">{L?.stockNoTx || "No transactions yet — use the buttons above to record one."}</p>
        ) : (
          <table className="w-full text-xs">
            <thead className="bg-stone-50 border-b border-stone-200">
              <tr>
                <th className="text-left py-2 px-3 font-semibold text-stone-600">{L?.date || "Date"}</th>
                <th className="text-left py-2 px-3 font-semibold text-stone-600">{L?.stockTxType || "Type"}</th>
                <th className="text-left py-2 px-3 font-semibold text-stone-600">{L?.item || "Item"}</th>
                <th className="text-center py-2 px-3 font-semibold text-stone-600">{L?.stockTxQty || "Qty"}</th>
                <th className="text-right py-2 px-3 font-semibold text-stone-600">{L?.dispRate || "Unit £"}</th>
                <th className="text-right py-2 px-3 font-semibold text-stone-600">{L?.totals || "Total"}</th>
                <th className="text-left py-2 px-3 font-semibold text-stone-600">{L?.stockTxReason || "Reason"} / {L?.stockTxNotes || "Notes"}</th>
                <th className="text-left py-2 px-3 font-semibold text-stone-600">{L?.stockTxBy || "By"}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {txns.map(t => (
                <tr key={t.id} className="border-b border-stone-100 hover:bg-stone-50/50" data-testid={`stock-tx-row-${t.id.slice(0,6)}`}>
                  <td className="py-2 px-3 text-stone-600">{t.transaction_date}</td>
                  <td className="py-2 px-3"><Badge className={`${typeBadge(t.tx_type)} text-[10px]`}>{t.tx_type.replace("_", " ")}</Badge></td>
                  <td className="py-2 px-3 font-semibold text-stone-700">{t.name || t.item_id}</td>
                  <td className="py-2 px-3 text-center font-mono">{t.quantity}</td>
                  <td className="py-2 px-3 text-right font-mono">£{t.unit_cost?.toFixed(2)}</td>
                  <td className="py-2 px-3 text-right font-mono font-bold">£{t.total_cost?.toFixed(2)}</td>
                  <td className="py-2 px-3 text-stone-600 truncate max-w-xs">{t.notes || t.reason}</td>
                  <td className="py-2 px-3 text-stone-500 text-[10px]">{t.created_by}</td>
                  <td><button onClick={() => del(t.id)} className="text-rose-500 text-xs px-2">×</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Record Transaction Modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-6" onClick={() => setShowForm(false)}>
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full" onClick={e => e.stopPropagation()}>
            <div className="p-4 border-b border-stone-100 flex items-center justify-between">
              <h3 className="font-bold capitalize">{L?.stockRecordPrefix || "Record"} {txType.replace("_", " ")}</h3>
              <button onClick={() => setShowForm(false)} className="text-stone-400 hover:text-stone-600 text-2xl leading-none">×</button>
            </div>
            <div className="p-4 space-y-3">
              <div>
                <label className="text-xs text-stone-500">{L?.stockTxItem || "Item"} *</label>
                <select value={form.item_id} onChange={e => {
                  const match = stock.find(s => s.item_id === e.target.value);
                  setForm(f => ({ ...f, item_id: e.target.value, name: match?.name || "" }));
                }} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" data-testid="stock-tx-item">
                  <option value="">{L?.stockSelectItem || "Select item"}…</option>
                  {stock.map(s => <option key={s.item_id} value={s.item_id}>{s.name}</option>)}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-stone-500">{L?.stockTxQty || "Quantity"} *</label>
                  <input type="number" min="1" value={form.quantity} onChange={e => setForm(f => ({ ...f, quantity: parseInt(e.target.value) || 1 }))} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" data-testid="stock-tx-qty" />
                </div>
                <div>
                  <label className="text-xs text-stone-500">{L?.stockTxUnit || "Unit Cost £"}</label>
                  <input type="number" step="0.01" value={form.unit_cost} onChange={e => setForm(f => ({ ...f, unit_cost: parseFloat(e.target.value) || 0 }))} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" />
                </div>
              </div>
              <div>
                <label className="text-xs text-stone-500">{L?.stockTxDate || "Transaction Date"} *</label>
                <input type="date" value={form.transaction_date} onChange={e => setForm(f => ({ ...f, transaction_date: e.target.value }))} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" />
              </div>
              <div>
                <label className="text-xs text-stone-500">{L?.stockTxReason || "Reason"}</label>
                <input value={form.reason} onChange={e => setForm(f => ({ ...f, reason: e.target.value }))} placeholder={txType} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" />
              </div>
              <div>
                <label className="text-xs text-stone-500">{L?.stockTxNotes || "Notes"}</label>
                <textarea value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" rows={3} placeholder={L?.notesPh || "Any details…"} />
              </div>
              <div className="bg-stone-50 border border-stone-200 rounded-lg p-2 text-xs flex justify-between">
                <span className="text-stone-500">{L?.stockTxImpact || "Total impact:"}</span>
                <span className="font-mono font-bold">£{(form.quantity * form.unit_cost).toFixed(2)}</span>
              </div>
            </div>
            <div className="p-4 border-t border-stone-100 flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => setShowForm(false)}>{L?.cancel || "Cancel"}</Button>
              <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700 text-white" onClick={save} data-testid="stock-tx-submit">{L?.stockRecordPrefix || "Record"}</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
const DeliveriesTab = ({ pid, dispatches, stock, catalog = [], lang, setLang, L, canSeeCosts = true }) => {
  const [rows, setRows] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const emptyItem = { item_id: "", name: "", qty_sent: 0, qty_received: 0, qty_shortage: 0, qty_damage: 0, qty_rejected: 0, reason: "", unit_cost: 0 };
  const today = new Date().toISOString().slice(0, 10);
  const [form, setForm] = useState({
    dispatch_id: "", delivery_date: today,
    invoice_number: "", notes: "", items: [], photos: [],
  });

  // Open the modal with ALL catalog items pre-listed (like Daily Laundry Usage)
  const openForm = () => {
    const prefilled = (catalog && catalog.length ? catalog : stock).map(c => ({
      ...emptyItem,
      item_id: c.id || c.item_id,
      name: c.name,
    }));
    setForm({
      dispatch_id: "", delivery_date: today,
      invoice_number: "", notes: "",
      items: prefilled, photos: [],
    });
    setShowForm(true);
  };

  const load = async () => {
    try { const { data } = await axios.get(`${API}/laundry/deliveries/${pid}`); setRows(data.rows || []); }
    catch { /* */ }
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [pid]);

  const save = async () => {
    // Only submit items that have at least one non-zero quantity
    const validItems = form.items.filter(i => i.item_id && (
      (i.qty_received || 0) > 0 ||
      (i.qty_shortage || 0) > 0 ||
      (i.qty_damage || 0) > 0 ||
      (i.qty_rejected || 0) > 0
    ));
    if (validItems.length === 0) return toast.error(L?.fillQty || "Enter at least one quantity > 0");
    try {
      await axios.post(`${API}/laundry/deliveries/${pid}`, { ...form, items: validItems });
      toast.success(L?.delvSaved || "Delivery recorded");
      setShowForm(false);
      setForm({ dispatch_id: "", delivery_date: today, invoice_number: "", notes: "", items: [], photos: [] });
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const del = async (id) => {
    if (!window.confirm("Delete this delivery record?")) return;
    await axios.delete(`${API}/laundry/deliveries/${id}`);
    toast.success("Deleted"); load();
  };

  const addItem = () => setForm(f => ({ ...f, items: [...f.items, { ...emptyItem }] }));
  const updItem = (i, k, v) => setForm(f => { const arr = [...f.items]; arr[i] = { ...arr[i], [k]: v }; return { ...f, items: arr }; });
  const rmItem = (i) => setForm(f => { const arr = [...f.items]; arr.splice(i, 1); return { ...f, items: arr }; });

  const loadFromDispatch = (dispatch_id) => {
    if (!dispatch_id) {
      // Clear sent + received qty while keeping the pre-filled catalog
      setForm(f => ({ ...f, dispatch_id: "", items: f.items.map(it => ({ ...it, qty_sent: 0, qty_received: 0 })) }));
      return;
    }
    const d = dispatches.find(x => x.id === dispatch_id);
    if (!d) return;
    // Build sentMap: item_id → qty sent in dispatch
    const sentMap = Object.fromEntries((d.items || []).map(it => [it.item_id, it.qty_sent]));
    const rateMap = Object.fromEntries((d.items || []).map(it => [it.item_id, it.rate || it.unit_cost || 0]));
    setForm(f => ({
      ...f, dispatch_id,
      // Keep pre-filled full catalog; annotate sent + received from the dispatch
      items: f.items.map(it => ({
        ...it,
        qty_sent: sentMap[it.item_id] || 0,
        qty_received: sentMap[it.item_id] || 0,
        unit_cost: rateMap[it.item_id] || it.unit_cost || 0,
      })),
    }));
  };

  const gross = form.items.reduce((s, it) => s + Number(it.qty_received || 0) * Number(it.unit_cost || 0), 0);
  const deduction = form.items.reduce((s, it) => s + (Number(it.qty_shortage || 0) + Number(it.qty_damage || 0) + Number(it.qty_rejected || 0)) * Number(it.unit_cost || 0), 0);
  const net = gross - deduction;

  const statusBadge = (s) => s === "complete" ? "bg-emerald-100 text-emerald-700" : s === "short" ? "bg-rose-100 text-rose-700" : "bg-amber-100 text-amber-700";

  return (
    <div className="space-y-3" data-testid="deliveries-panel">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-bold text-stone-800">Laundry Deliveries ({rows.length})</h3>
          <p className="text-xs text-stone-500">Track items received from laundry company with discrepancy tracking.</p>
        </div>
        <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700 text-white" onClick={openForm} data-testid="delivery-new-btn">
          + {L?.delvReceived2 || "Record Delivery"}
        </Button>
      </div>

      <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
        {rows.length === 0 ? (
          <p className="text-center text-sm text-stone-400 py-12">No deliveries recorded yet.</p>
        ) : (
          <table className="w-full text-xs">
            <thead className="bg-stone-50 border-b border-stone-200">
              <tr>
                <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Date</th>
                <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Invoice #</th>
                <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Linked Dispatch</th>
                <th className="text-right py-2.5 px-3 font-semibold text-stone-600">Gross</th>
                <th className="text-right py-2.5 px-3 font-semibold text-stone-600">Deduction</th>
                <th className="text-right py-2.5 px-3 font-semibold text-stone-600">Net Payable</th>
                <th className="text-center py-2.5 px-3 font-semibold text-stone-600">Coverage</th>
                <th className="text-center py-2.5 px-3 font-semibold text-stone-600">Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map(r => (
                <tr key={r.id} className="border-b border-stone-100 hover:bg-stone-50/50" data-testid={`delivery-row-${r.id.slice(0,6)}`}>
                  <td className="py-2.5 px-3 text-stone-700">{r.delivery_date}</td>
                  <td className="py-2.5 px-3 font-mono text-stone-600">{r.invoice_number || "—"}</td>
                  <td className="py-2.5 px-3 text-stone-600">{r.dispatch_summary ? `${r.dispatch_summary.vendor} · ${r.dispatch_summary.dispatch_date}` : "—"}</td>
                  <td className="py-2.5 px-3 text-right font-mono text-stone-700">£{r.gross_amount?.toFixed(2)}</td>
                  <td className="py-2.5 px-3 text-right font-mono text-rose-600">£{r.deduction_amount?.toFixed(2)}</td>
                  <td className="py-2.5 px-3 text-right font-mono font-bold text-emerald-700">£{r.net_payable?.toFixed(2)}</td>
                  <td className="py-2.5 px-3 text-center text-stone-700">{r.coverage_pct != null ? `${r.coverage_pct}%` : "—"}</td>
                  <td className="py-2.5 px-3 text-center"><Badge className={statusBadge(r.status)}>{r.status}</Badge></td>
                  <td><button onClick={() => del(r.id)} className="text-rose-500 text-xs">Del</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Record Delivery Modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-3 sm:p-6" onClick={() => setShowForm(false)}>
          <div className="bg-white rounded-2xl shadow-2xl w-[98vw] sm:w-[95vw] max-w-4xl max-h-[95vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="p-4 border-b border-stone-100 flex items-center justify-between flex-wrap gap-2">
              <div>
                <h3 className="font-bold text-base sm:text-lg">{L?.delvTitle || "Record Delivery"}</h3>
                <p className="text-xs text-stone-500">{L?.delvSubtitle || "Record items received from laundry company."}</p>
              </div>
              <div className="flex items-center gap-2">
                {setLang && (
                  <div className="flex gap-1 bg-stone-100 rounded-lg p-1">
                    {Object.keys(LAUNDRY_I18N).map(code => (
                      <button key={code} onClick={() => setLang(code)}
                        className={`px-2 py-1 text-xs font-semibold rounded transition ${lang === code ? "bg-white text-stone-800 shadow" : "text-stone-500 hover:text-stone-700"}`}
                        data-testid={`delv-lang-${code}`}>
                        {LAUNDRY_I18N[code].flag} {code.toUpperCase()}
                      </button>
                    ))}
                  </div>
                )}
                <button onClick={() => setShowForm(false)} className="text-stone-400 hover:text-stone-600 text-2xl leading-none">×</button>
              </div>
            </div>
            <div className="p-4 space-y-4">
              {/* Link to Dispatch */}
              <div className="border border-stone-200 rounded-xl p-3 space-y-3">
                <div className="text-xs font-semibold text-stone-600 uppercase">Link to Dispatch</div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-stone-500">Select Dispatch</label>
                    <select value={form.dispatch_id} onChange={e => loadFromDispatch(e.target.value)} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" data-testid="delivery-dispatch-select">
                      <option value="">None (no comparison)</option>
                      {dispatches.map(d => <option key={d.id} value={d.id}>{d.vendor} · {d.sent_date} · {d.items?.length || 0} items</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-stone-500">Delivery Date *</label>
                    <input type="date" value={form.delivery_date} onChange={e => setForm(f => ({ ...f, delivery_date: e.target.value }))} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" data-testid="delivery-date" />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-stone-500">Delivery Note / Invoice Number</label>
                    <input value={form.invoice_number} onChange={e => setForm(f => ({ ...f, invoice_number: e.target.value }))} placeholder="e.g. INV-2026-001" className="w-full mt-1 px-3 py-2 border rounded-lg text-sm font-mono" data-testid="delivery-invoice" />
                  </div>
                  <div>
                    <label className="text-xs text-stone-500">Notes</label>
                    <input value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} placeholder="Any additional notes…" className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" />
                  </div>
                </div>
              </div>

              {/* Items — hazır tablo (pre-filled with full catalog like Daily Usage) */}
              <div className="border border-stone-200 rounded-xl p-3">
                <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
                  <div className="text-xs font-semibold text-stone-600 uppercase">{L?.item || "Items"}</div>
                  <div className="text-[10px] text-stone-500">
                    {L?.delvSubtitle || "Count every piece delivered. Shortage / Damaged on arrival are deducted."}
                  </div>
                </div>

                {/* Desktop table */}
                <div className="hidden sm:block overflow-x-auto">
                  <table className="w-full text-sm" data-testid="delivery-readytable">
                    <thead className="bg-stone-50 border-b border-stone-200">
                      <tr>
                        <th className="text-left py-2 px-2 font-semibold text-stone-700 w-[28%]">{L?.item || "Item"}</th>
                        <th className="text-center py-2 px-2 font-semibold text-stone-500">{L?.delvSent || "Sent"}</th>
                        <th className="text-center py-2 px-2 font-semibold text-emerald-700">{L?.delvReceived || "Received"} ↓</th>
                        <th className="text-center py-2 px-2 font-semibold text-rose-700">{L?.delvShortage || "Shortage"}</th>
                        <th className="text-center py-2 px-2 font-semibold text-fuchsia-700" title={L?.factoryBrokenHint}>{L?.factoryBroken || "Broken (factory)"}</th>
                        <th className="text-center py-2 px-2 font-semibold text-amber-700" title={L?.roomDamagedHint}>{L?.roomDamaged || "Damaged (room)"}</th>
                        {canSeeCosts && <th className="text-right py-2 px-2 font-semibold text-stone-600">{L?.dispRate || "£"}</th>}
                      </tr>
                    </thead>
                    <tbody>
                      {form.items.map((it, i) => {
                        const diff = (it.qty_sent || 0) - (it.qty_received || 0);
                        return (
                          <tr key={it.item_id || i} className="border-b border-stone-100 hover:bg-stone-50/50" data-testid={`delivery-row-${it.item_id}`}>
                            <td className="py-1.5 px-2">
                              <div className="font-semibold text-stone-800">{it.name}</div>
                              <div className="text-[10px] text-stone-400">{it.item_id}</div>
                            </td>
                            <td className="py-1 px-2 text-center">
                              {it.qty_sent > 0 ? (
                                <span className={`inline-block min-w-[36px] px-2 py-1 rounded font-mono text-xs bg-stone-100 text-stone-700`}>
                                  {it.qty_sent}
                                </span>
                              ) : <span className="text-stone-300">—</span>}
                            </td>
                            <td className="py-1 px-1"><input type="number" min="0" inputMode="numeric" value={it.qty_received} onChange={e => updItem(i, "qty_received", parseInt(e.target.value) || 0)} className="w-full h-9 text-center font-mono font-bold bg-emerald-50 border border-emerald-200 rounded" data-testid={`delv-received-${it.item_id}`} /></td>
                            <td className="py-1 px-1"><input type="number" min="0" inputMode="numeric" value={it.qty_shortage} onChange={e => updItem(i, "qty_shortage", parseInt(e.target.value) || 0)} className="w-full h-9 text-center font-mono font-bold bg-rose-50 border border-rose-200 rounded" data-testid={`delv-short-${it.item_id}`} /></td>
                            <td className="py-1 px-1"><input type="number" min="0" inputMode="numeric" value={it.qty_damage} onChange={e => updItem(i, "qty_damage", parseInt(e.target.value) || 0)} className="w-full h-9 text-center font-mono font-bold bg-fuchsia-50 border border-fuchsia-200 rounded" data-testid={`delv-dmg-${it.item_id}`} /></td>
                            <td className="py-1 px-1"><input type="number" min="0" inputMode="numeric" value={it.qty_rejected} onChange={e => updItem(i, "qty_rejected", parseInt(e.target.value) || 0)} className="w-full h-9 text-center font-mono font-bold bg-amber-50 border border-amber-200 rounded" /></td>
                            {canSeeCosts && <td className="py-1 px-1"><input type="number" step="0.01" min="0" value={it.unit_cost} onChange={e => updItem(i, "unit_cost", parseFloat(e.target.value) || 0)} className="w-full h-9 text-right font-mono border border-stone-200 rounded px-1" /></td>}
                          </tr>
                        );
                      })}
                    </tbody>
                    <tfoot className="bg-stone-50 border-t-2 border-stone-200">
                      <tr>
                        <td className="py-2 px-2 text-right font-bold text-stone-700">{L?.totals || "Totals"}</td>
                        <td className="py-2 px-2 text-center font-mono font-black text-stone-700">{form.items.reduce((s, i) => s + (i.qty_sent || 0), 0)}</td>
                        <td className="py-2 px-2 text-center font-mono font-black text-emerald-700">{form.items.reduce((s, i) => s + (i.qty_received || 0), 0)}</td>
                        <td className="py-2 px-2 text-center font-mono font-black text-rose-700">{form.items.reduce((s, i) => s + (i.qty_shortage || 0), 0)}</td>
                        <td className="py-2 px-2 text-center font-mono font-black text-fuchsia-700">{form.items.reduce((s, i) => s + (i.qty_damage || 0), 0)}</td>
                        <td className="py-2 px-2 text-center font-mono font-black text-amber-700">{form.items.reduce((s, i) => s + (i.qty_rejected || 0), 0)}</td>
                        {canSeeCosts && <td></td>}
                      </tr>
                    </tfoot>
                  </table>
                </div>

                {/* Mobile cards */}
                <div className="sm:hidden space-y-2">
                  {form.items.map((it, i) => (
                    <div key={it.item_id || i} className="bg-white border border-stone-200 rounded-xl p-3">
                      <div className="flex items-start justify-between mb-2">
                        <div>
                          <div className="font-bold text-sm text-stone-800">{it.name}</div>
                          {it.qty_sent > 0 && (
                            <div className="text-[11px] text-stone-500">{L?.delvSent || "Sent"}: <b className="font-mono">{it.qty_sent}</b></div>
                          )}
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        <div><label className="text-[10px] font-bold uppercase text-emerald-700">{L?.delvReceived || "Received"} ↓</label><input type="number" min="0" inputMode="numeric" value={it.qty_received} onChange={e => updItem(i, "qty_received", parseInt(e.target.value) || 0)} className="w-full h-11 text-center text-base font-mono font-bold bg-emerald-50 border-emerald-200 border rounded mt-0.5" /></div>
                        <div><label className="text-[10px] font-bold uppercase text-rose-700">{L?.delvShortage || "Shortage"}</label><input type="number" min="0" inputMode="numeric" value={it.qty_shortage} onChange={e => updItem(i, "qty_shortage", parseInt(e.target.value) || 0)} className="w-full h-11 text-center text-base font-mono font-bold bg-rose-50 border-rose-200 border rounded mt-0.5" /></div>
                        <div><label className="text-[10px] font-bold uppercase text-fuchsia-700" title={L?.factoryBrokenHint}>{L?.factoryBrokenShort || "Broken"}</label><input type="number" min="0" inputMode="numeric" value={it.qty_damage} onChange={e => updItem(i, "qty_damage", parseInt(e.target.value) || 0)} className="w-full h-11 text-center text-base font-mono font-bold bg-fuchsia-50 border-fuchsia-200 border rounded mt-0.5" /></div>
                        <div><label className="text-[10px] font-bold uppercase text-amber-700" title={L?.roomDamagedHint}>{L?.roomDamagedShort || "Damaged"}</label><input type="number" min="0" inputMode="numeric" value={it.qty_rejected} onChange={e => updItem(i, "qty_rejected", parseInt(e.target.value) || 0)} className="w-full h-11 text-center text-base font-mono font-bold bg-amber-50 border-amber-200 border rounded mt-0.5" /></div>
                        {canSeeCosts && <div className="col-span-2"><label className="text-[10px] font-bold uppercase text-stone-500">{L?.dispRate || "Unit Cost £"}</label><input type="number" step="0.01" min="0" value={it.unit_cost} onChange={e => updItem(i, "unit_cost", parseFloat(e.target.value) || 0)} className="w-full h-11 text-right text-base font-mono border rounded mt-0.5" /></div>}
                      </div>
                    </div>
                  ))}
                </div>

                {form.items.some(it => it.qty_shortage || it.qty_damage || it.qty_rejected) && (
                  <div className="mt-3 space-y-1">
                    <div className="text-[10px] font-bold uppercase text-stone-500">Discrepancy reasons:</div>
                    {form.items.map((it, i) => ((it.qty_shortage || it.qty_damage || it.qty_rejected) ? (
                      <input key={i} value={it.reason} onChange={e => updItem(i, "reason", e.target.value)} placeholder={`Reason for ${it.name} discrepancy…`} className="w-full px-2 py-2 border rounded text-xs bg-rose-50" />
                    ) : null))}
                  </div>
                )}
              </div>

              {/* Photos */}
              <PhotoCapture photos={form.photos || []} onChange={(ps) => setForm(f => ({ ...f, photos: ps }))} L={L} />

              {/* Totals */}
              <div className="border border-stone-200 rounded-xl p-3 text-sm">
                <div className="flex justify-between py-1"><span className="text-stone-600">Gross Amount:</span><span className="font-mono">£{gross.toFixed(2)}</span></div>
                <div className="flex justify-between py-1"><span className="text-stone-600">Deductions:</span><span className="font-mono text-rose-600">-£{deduction.toFixed(2)}</span></div>
                <div className="flex justify-between py-1 border-t border-stone-200 mt-1 pt-2"><span className="font-bold">Net Payable:</span><span className="font-mono font-bold text-emerald-700">£{net.toFixed(2)}</span></div>
              </div>
            </div>
            <div className="p-4 border-t border-stone-100 flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => setShowForm(false)}>Cancel</Button>
              <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700 text-white" onClick={save} data-testid="delivery-submit-btn">Record Delivery</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};


/* ═══════════════════ ORDER FORECAST TAB ═══════════════════ */
const ForecastTab = ({ pid, onCreated, canSeeCosts = true }) => {
  // Map day-name → JS weekday (0=Sun ... 6=Sat)
  const DAY_MAP = { sunday: 0, monday: 1, tuesday: 2, wednesday: 3, thursday: 4, friday: 5, saturday: 6 };
  const nextMondayISO = () => {
    const d = new Date();
    const diff = (8 - d.getDay()) % 7 || 7;
    d.setDate(d.getDate() + diff);
    return d.toISOString().slice(0, 10);
  };
  // Contract-aware: find the next date whose weekday is in the allowed set
  const nextAllowedDate = (allowedDays) => {
    if (!allowedDays || allowedDays.length === 0) return nextMondayISO();
    const wanted = new Set(allowedDays.map(x => DAY_MAP[String(x).toLowerCase()]).filter(v => v !== undefined));
    if (wanted.size === 0) return nextMondayISO();
    const d = new Date();
    for (let i = 1; i <= 14; i++) {
      const cand = new Date(d);
      cand.setDate(d.getDate() + i);
      if (wanted.has(cand.getDay())) return cand.toISOString().slice(0, 10);
    }
    return nextMondayISO();
  };
  const [delivery, setDelivery] = useState("");
  const [allowedDispatchDays, setAllowedDispatchDays] = useState([]);   // e.g. ["monday","thursday"]
  const [contractInfo, setContractInfo] = useState(null);               // { provider_name, vendor?, etc }
  const [horizon, setHorizon] = useState(7);
  const [everyN, setEveryN] = useState(2);
  const [providers, setProviders] = useState([]);
  const [vendor, setVendor] = useState("");
  const [forecast, setForecast] = useState(null);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [editableItems, setEditableItems] = useState([]);  // user can override order qty
  const [globalBuffer, setGlobalBuffer] = useState(0);     // safety stock % applied to all

  const applyBuffer = (shortfall, pct) => Math.ceil((shortfall || 0) * (1 + (pct || 0) / 100));

  const runForecast = useCallback(async () => {
    if (!delivery) { toast.error("Pick a delivery date"); return; }
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/laundry/forecast/${pid}`, {
        params: { delivery_date: delivery, horizon_days: horizon, in_house_cleaning_every: everyN },
      });
      setForecast(data);
      setEditableItems(data.items.map(i => ({
        ...i,
        buffer_pct: globalBuffer,
        order_qty: applyBuffer(i.shortfall, globalBuffer),
      })));
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed to compute forecast"); }
    setLoading(false);
  }, [pid, delivery, horizon, everyN, globalBuffer]);

  useEffect(() => {
    // Fetch active laundry contract to learn allowed dispatch days
    axios.get(`${API}/laundry/contracts/${pid}`).then(r => {
      const all = r.data.contracts || [];
      const act = all.find(c => c.active !== false) || all[0];
      const days = act?.dispatch_days || [];
      setAllowedDispatchDays(days);
      setContractInfo(act || null);
      setDelivery(nextAllowedDate(days));
    }).catch(() => { setAllowedDispatchDays([]); setDelivery(nextMondayISO()); });

    axios.get(`${API}/laundry/providers/${pid}`).then(r => {
      const active = (r.data.providers || []).filter(p => p.status === "active");
      setProviders(active);
      if (active.length && !vendor) setVendor(active[0].name);
    }).catch(() => setProviders([]));
    // runForecast() fires via its own useEffect (delivery change)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pid]);

  // When delivery is set by contract load, run the forecast once
  useEffect(() => {
    if (delivery) runForecast();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [delivery]);

  const updateQty = (item_id, v) => {
    setEditableItems(arr => arr.map(x => x.item_id === item_id ? { ...x, order_qty: Math.max(0, parseInt(v) || 0) } : x));
  };

  const updateBuffer = (item_id, pct) => {
    setEditableItems(arr => arr.map(x => {
      if (x.item_id !== item_id) return x;
      const p = parseInt(pct) || 0;
      return { ...x, buffer_pct: p, order_qty: applyBuffer(x.shortfall, p) };
    }));
  };

  const applyGlobalBuffer = (pct) => {
    const p = parseInt(pct) || 0;
    setGlobalBuffer(p);
    setEditableItems(arr => arr.map(x => ({
      ...x, buffer_pct: p, order_qty: applyBuffer(x.shortfall, p),
    })));
  };

  const totals = () => {
    const qty = editableItems.reduce((s, x) => s + (x.order_qty || 0), 0);
    const cost = editableItems.reduce((s, x) => s + (x.order_qty || 0) * (x.washing_cost || 0), 0);
    return { qty, cost };
  };

  const createOrder = async () => {
    const lines = editableItems.filter(i => (i.order_qty || 0) > 0);
    if (!lines.length) return toast.error("No items to order");
    if (!vendor) return toast.error("Select a provider/vendor");
    if (!window.confirm(`Create dispatch to ${vendor} for ${lines.length} items (${totals().qty} pieces, est. £${totals().cost.toFixed(2)})?`)) return;
    setCreating(true);
    try {
      await axios.post(`${API}/laundry/forecast/${pid}/create-dispatch`, {
        vendor, delivery_date: delivery, horizon_days: horizon, in_house_cleaning_every: everyN,
        items: lines.map(l => ({
          item_id: l.item_id, name: l.name,
          qty_sent: l.order_qty, rate: l.washing_cost || 0,
        })),
      });
      toast.success(`Dispatch created — ${totals().qty} pieces → ${vendor}`);
      onCreated && onCreated();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    setCreating(false);
  };

  const fmt = (n) => `£${Number(n || 0).toFixed(2)}`;
  const t = totals();
  const daily = forecast?.daily || [];
  const maxEvents = Math.max(1, ...daily.map(d => d.events));

  return (
    <div className="space-y-4" data-testid="forecast-panel">
      {/* Controls */}
      <div className="bg-gradient-to-br from-fuchsia-50 to-white border border-fuchsia-200 rounded-xl p-4">
        <div className="flex items-center gap-2 mb-3 flex-wrap">
          <Sparkles className="w-4 h-4 text-fuchsia-600" />
          <h3 className="text-sm font-bold text-stone-800">Smart Order Forecast</h3>
          <span className="text-xs text-stone-500">Computes next-week linen needs based on arrivals + in-house cleanings</span>
          {contractInfo && (
            <span className="ml-auto text-[11px] bg-emerald-50 border border-emerald-200 text-emerald-700 rounded px-2 py-0.5 font-semibold" data-testid="forecast-active-contract">
              Active contract · {contractInfo.provider_name || contractInfo.provider_id || "—"}
            </span>
          )}
        </div>
        <div className="grid grid-cols-2 md:grid-cols-7 gap-3">
          <div className="md:col-span-2">
            <label className="text-[11px] font-semibold text-stone-500 uppercase">Delivery Date</label>
            <input type="date" value={delivery} onChange={e => setDelivery(e.target.value)} className="w-full mt-1 px-3 py-2 border border-stone-200 rounded-lg text-sm" data-testid="forecast-delivery-date" />
            {allowedDispatchDays.length > 0 && (() => {
              const selWd = delivery ? new Date(delivery + "T00:00:00").getDay() : -1;
              const allowedSet = new Set(allowedDispatchDays.map(x => DAY_MAP[String(x).toLowerCase()]).filter(v => v !== undefined));
              const ok = allowedSet.has(selWd);
              return (
                <>
                  <div className="flex flex-wrap items-center gap-1 mt-1.5">
                    <span className="text-[10px] font-semibold text-stone-500 uppercase mr-1">Contract dispatch days:</span>
                    {allowedDispatchDays.map(d => (
                      <span key={d} className="text-[10px] px-1.5 py-0.5 bg-emerald-100 text-emerald-700 rounded font-bold">{String(d).slice(0, 3).toUpperCase()}</span>
                    ))}
                    <button type="button" onClick={() => setDelivery(nextAllowedDate(allowedDispatchDays))}
                            className="ml-1 text-[10px] px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded hover:bg-blue-200 font-semibold"
                            data-testid="forecast-next-allowed-btn">Next valid →</button>
                  </div>
                  {!ok && delivery && (
                    <p className="mt-1 text-[11px] text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1" data-testid="forecast-day-warn">
                      ⚠ {new Date(delivery + "T00:00:00").toLocaleDateString("en-GB", { weekday: "long" })} is not a contract dispatch day.
                    </p>
                  )}
                </>
              );
            })()}
          </div>
          <div>
            <label className="text-[11px] font-semibold text-stone-500 uppercase">Forecast Horizon</label>
            <select value={horizon} onChange={e => setHorizon(parseInt(e.target.value))} className="w-full mt-1 px-3 py-2 border border-stone-200 rounded-lg text-sm" data-testid="forecast-horizon">
              <option value={3}>3 days</option>
              <option value={7}>7 days (1 week)</option>
              <option value={14}>14 days (2 weeks)</option>
              <option value={30}>30 days</option>
            </select>
          </div>
          <div>
            <label className="text-[11px] font-semibold text-stone-500 uppercase">In-house Clean Every</label>
            <select value={everyN} onChange={e => setEveryN(parseInt(e.target.value))} className="w-full mt-1 px-3 py-2 border border-stone-200 rounded-lg text-sm" data-testid="forecast-every-n">
              <option value={1}>Daily</option>
              <option value={2}>Every 2 days</option>
              <option value={3}>Every 3 days</option>
              <option value={7}>Weekly</option>
            </select>
          </div>
          <div>
            <label className="text-[11px] font-semibold text-stone-500 uppercase">Provider / Vendor</label>
            {providers.length > 0 ? (
              <select value={vendor} onChange={e => setVendor(e.target.value)} className="w-full mt-1 px-3 py-2 border border-stone-200 rounded-lg text-sm" data-testid="forecast-vendor">
                {providers.map(p => <option key={p.id} value={p.name}>{p.name}</option>)}
              </select>
            ) : (
              <input value={vendor} onChange={e => setVendor(e.target.value)} placeholder="Vendor name" className="w-full mt-1 px-3 py-2 border border-stone-200 rounded-lg text-sm" />
            )}
          </div>
          <div className="md:col-span-2 flex items-end">
            <Button size="sm" className="w-full bg-fuchsia-600 hover:bg-fuchsia-700 text-white" onClick={runForecast} disabled={loading} data-testid="forecast-run">
              {loading ? <RefreshCw className="w-4 h-4 mr-1 animate-spin" /> : <TrendingUp className="w-4 h-4 mr-1" />}
              {loading ? "Computing..." : "Recompute Forecast"}
            </Button>
          </div>
        </div>
      </div>

      {forecast && (
        <>
          {/* Summary KPIs */}
          <div className={`grid gap-3 ${canSeeCosts ? "grid-cols-2 md:grid-cols-6" : "grid-cols-2 md:grid-cols-5"}`}>
            <div className="bg-white border border-stone-200 rounded-xl p-4 text-center">
              <p className="text-2xl font-black text-stone-700">{forecast.bookings_in_window}</p>
              <p className="text-[11px] text-stone-500">Bookings in window</p>
            </div>
            <div className="bg-rose-50 border border-rose-200 rounded-xl p-4 text-center" title={`Cleaning events between today and ${delivery}`}>
              <p className="text-2xl font-black text-rose-600">{forecast.pre_delivery_events || 0}</p>
              <p className="text-[11px] text-rose-600">Pre-delivery events ({forecast.pre_delivery_days || 0}d)</p>
            </div>
            <div className="bg-white border border-stone-200 rounded-xl p-4 text-center">
              <p className="text-2xl font-black text-blue-600">{forecast.total_cleaning_events}</p>
              <p className="text-[11px] text-stone-500">Horizon cleaning events</p>
            </div>
            <div className="bg-white border border-stone-200 rounded-xl p-4 text-center">
              <p className="text-2xl font-black text-fuchsia-600">{t.qty}</p>
              <p className="text-[11px] text-stone-500">Total pieces to order</p>
            </div>
            {canSeeCosts && (
              <div className="bg-white border border-stone-200 rounded-xl p-4 text-center">
                <p className="text-2xl font-black text-emerald-600">{fmt(t.cost)}</p>
                <p className="text-[11px] text-stone-500">Estimated cost</p>
              </div>
            )}
            <div className="bg-white border border-stone-200 rounded-xl p-4 text-center">
              <p className="text-2xl font-black text-amber-600">{editableItems.filter(i => i.order_qty > 0).length}</p>
              <p className="text-[11px] text-stone-500">Items to order</p>
            </div>
          </div>

          {/* Daily breakdown */}
          <div className="bg-white border border-stone-200 rounded-xl p-4">
            <h4 className="text-sm font-bold text-stone-800 mb-2">Daily Cleaning Events</h4>
            <div className="flex items-end gap-2 h-28" data-testid="forecast-daily">
              {daily.map(d => {
                const h = (d.events / maxEvents) * 100;
                const dd = new Date(d.date);
                const label = dd.toLocaleDateString("en-GB", { weekday: "short", day: "numeric" });
                return (
                  <div key={d.date} className="flex-1 flex flex-col items-center justify-end gap-1">
                    <div className="text-xs font-bold text-stone-700">{d.events || ""}</div>
                    <div className="w-full bg-stone-100 rounded-t relative overflow-hidden" style={{ height: "70%" }}>
                      {d.arrivals > 0 && (
                        <div className="absolute bottom-0 left-0 right-0 bg-emerald-500"
                             style={{ height: `${(d.arrivals / maxEvents) * 100}%` }}
                             title={`${d.arrivals} arrivals`} />
                      )}
                      {d.in_house_cleanings > 0 && (
                        <div className="absolute left-0 right-0 bg-blue-500"
                             style={{ bottom: `${(d.arrivals / maxEvents) * 100}%`,
                                      height: `${(d.in_house_cleanings / maxEvents) * 100}%` }}
                             title={`${d.in_house_cleanings} in-house cleanings`} />
                      )}
                    </div>
                    <div className="text-[10px] text-stone-500 text-center leading-tight">{label}</div>
                  </div>
                );
              })}
            </div>
            <div className="flex items-center gap-4 mt-2 text-xs text-stone-500">
              <span className="flex items-center gap-1"><span className="w-3 h-3 bg-emerald-500 rounded"></span>Arrivals (new guests)</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 bg-blue-500 rounded"></span>In-house cleanings (every {everyN}d)</span>
            </div>
          </div>

          {/* Order table */}
          <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
            <div className="p-3 border-b border-stone-200 flex items-center justify-between flex-wrap gap-2">
              <div className="flex items-center gap-3">
                <h4 className="text-sm font-bold text-stone-800">Suggested Order</h4>
                <div className="flex items-center gap-2 bg-amber-50 border border-amber-200 rounded-lg px-3 py-1.5">
                  <span className="text-xs font-semibold text-amber-800">Safety Buffer</span>
                  <select value={globalBuffer} onChange={e => applyGlobalBuffer(e.target.value)}
                          className="text-xs border border-amber-300 rounded bg-white px-2 py-0.5 font-mono font-bold text-amber-700"
                          data-testid="forecast-global-buffer">
                    <option value={0}>None</option>
                    <option value={5}>+5%</option>
                    <option value={10}>+10%</option>
                    <option value={15}>+15%</option>
                    <option value={20}>+20%</option>
                    <option value={25}>+25%</option>
                  </select>
                  <span className="text-[11px] text-amber-700">applies to all rows</span>
                </div>
              </div>
              <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700 text-white" onClick={createOrder} disabled={creating || t.qty === 0} data-testid="forecast-create-dispatch">
                {creating ? <RefreshCw className="w-4 h-4 mr-1 animate-spin" /> : <Send className="w-4 h-4 mr-1" />}
                Create Dispatch → {vendor || "vendor"}
              </Button>
            </div>
            <table className="w-full text-sm">
              <thead className="bg-stone-50 border-b border-stone-200">
                <tr>
                  <th className="text-left py-2 px-3 font-semibold text-stone-600">Item</th>
                  <th className="text-center py-2 px-3 font-semibold text-stone-600">Per Cleaning</th>
                  <th className="text-center py-2 px-3 font-semibold text-stone-600" title="Current clean stock on hand today">Stock Now</th>
                  <th className="text-center py-2 px-3 font-semibold text-stone-600" title={`Consumed between today and ${delivery} (pre-delivery)`}>Used Before Delivery</th>
                  <th className="text-center py-2 px-3 font-semibold text-stone-600" title="Stock Now minus Used Before Delivery">Remain @ Delivery</th>
                  <th className="text-center py-2 px-3 font-semibold text-stone-600" title={`Pieces needed during the ${horizon}-day horizon after delivery`}>Horizon Need</th>
                  <th className="text-center py-2 px-3 font-semibold text-stone-600">Shortfall</th>
                  <th className="text-center py-2 px-3 font-semibold text-stone-600">Safety +%</th>
                  <th className="text-center py-2 px-3 font-semibold text-stone-600">Order Qty</th>
                  {canSeeCosts && <th className="text-right py-2 px-3 font-semibold text-stone-600">Unit £</th>}
                  {canSeeCosts && <th className="text-right py-2 px-3 font-semibold text-stone-600">Line Total</th>}
                </tr>
              </thead>
              <tbody>
                {editableItems.map(i => {
                  const line = (i.order_qty || 0) * (i.washing_cost || 0);
                  const extraQty = (i.order_qty || 0) - (i.shortfall || 0);
                  return (
                    <tr key={i.item_id} className={`border-b border-stone-100 ${i.shortfall > 0 ? "" : "opacity-60"}`} data-testid={`forecast-row-${i.item_id}`}>
                      <td className="py-2 px-3 font-semibold text-stone-800">{i.name}</td>
                      <td className="py-2 px-3 text-center text-stone-600">× {i.per_cleaning_qty}</td>
                      <td className="py-2 px-3 text-center font-mono text-stone-700">{i.on_hand_clean}</td>
                      <td className="py-2 px-3 text-center font-mono text-rose-600">
                        {i.used_before_delivery > 0 ? `-${i.used_before_delivery}` : "0"}
                      </td>
                      <td className="py-2 px-3 text-center font-mono font-bold text-blue-700">{i.remaining_at_delivery}</td>
                      <td className="py-2 px-3 text-center font-mono text-stone-700">{i.needed}</td>
                      <td className="py-2 px-3 text-center">
                        {i.shortfall > 0
                          ? <Badge className="bg-rose-100 text-rose-700 font-mono">{i.shortfall}</Badge>
                          : <Badge className="bg-emerald-100 text-emerald-700 font-mono">OK</Badge>}
                      </td>
                      <td className="py-2 px-3 text-center">
                        <select value={i.buffer_pct || 0} onChange={e => updateBuffer(i.item_id, e.target.value)}
                                className="w-20 px-1 py-1 border border-stone-200 rounded text-xs font-mono font-bold text-amber-700 bg-amber-50"
                                data-testid={`forecast-buffer-${i.item_id}`}>
                          <option value={0}>0%</option>
                          <option value={5}>+5%</option>
                          <option value={10}>+10%</option>
                          <option value={15}>+15%</option>
                          <option value={20}>+20%</option>
                          <option value={25}>+25%</option>
                          <option value={30}>+30%</option>
                          <option value={50}>+50%</option>
                        </select>
                      </td>
                      <td className="py-2 px-3 text-center">
                        <div className="flex flex-col items-center">
                          <input type="number" min="0" value={i.order_qty || 0}
                                 onChange={e => updateQty(i.item_id, e.target.value)}
                                 className="w-20 px-2 py-1 border border-stone-200 rounded text-sm text-right font-mono"
                                 data-testid={`forecast-qty-${i.item_id}`} />
                          {extraQty > 0 && (
                            <span className="text-[10px] text-amber-600 font-mono mt-0.5">+{extraQty} safety</span>
                          )}
                        </div>
                      </td>
                      <td className="py-2 px-3 text-right font-mono text-stone-600">{canSeeCosts ? fmt(i.washing_cost) : null}</td>
                      <td className="py-2 px-3 text-right font-mono font-bold text-stone-800">{canSeeCosts ? fmt(line) : null}</td>
                    </tr>
                  );
                })}
              </tbody>
              <tfoot className="bg-stone-50 border-t-2 border-stone-200">
                <tr>
                  <td colSpan={8} className="py-2 px-3 text-right font-bold text-stone-700">Totals</td>
                  <td className="py-2 px-3 text-center font-mono font-black text-fuchsia-700">{t.qty}</td>
                  {canSeeCosts && <td></td>}
                  {canSeeCosts && <td className="py-2 px-3 text-right font-mono font-black text-stone-900">{fmt(t.cost)}</td>}
                </tr>
              </tfoot>
            </table>
          </div>
        </>
      )}
    </div>
  );
};


/* ═══════════ PhotoCapture — up to 3 photos, downsize to ~1280px jpeg base64 ═══════════ */
const PhotoCapture = ({ photos = [], onChange, L, max = 3 }) => {
  const inputRef = useRef(null);

  const downscale = (file) => new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (ev) => {
      const img = new Image();
      img.onload = () => {
        const maxDim = 1280;
        let w = img.width, h = img.height;
        if (w > maxDim || h > maxDim) {
          const r = Math.min(maxDim / w, maxDim / h);
          w = Math.round(w * r); h = Math.round(h * r);
        }
        const canvas = document.createElement("canvas");
        canvas.width = w; canvas.height = h;
        canvas.getContext("2d").drawImage(img, 0, 0, w, h);
        resolve(canvas.toDataURL("image/jpeg", 0.78));
      };
      img.onerror = reject;
      img.src = ev.target.result;
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });

  const handle = async (e) => {
    const files = Array.from(e.target.files || []);
    e.target.value = "";
    for (const f of files) {
      if (photos.length >= max) break;
      if (f.size > 5 * 1024 * 1024) { toast.error(L?.photoTooLarge || "Image too large"); continue; }
      try {
        const b64 = await downscale(f);
        onChange([...(photos || []), b64].slice(0, max));
      } catch { /* ignore */ }
    }
  };

  return (
    <div className="border border-stone-200 rounded-xl p-3 bg-stone-50/50" data-testid="photo-capture">
      <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
        <div>
          <div className="text-xs font-bold uppercase text-stone-700">{L?.photosTitle || "Photos"}</div>
          <div className="text-[10px] text-stone-500">{L?.photosHint || "Up to 3 photos"}</div>
        </div>
        {photos.length < max && (
          <button type="button" onClick={() => inputRef.current?.click()}
            className="flex items-center gap-1.5 px-3 py-2 bg-violet-600 hover:bg-violet-700 text-white text-xs font-semibold rounded-lg"
            data-testid="photo-add-btn">
            <Camera className="w-4 h-4" />{L?.photoAdd || "Add Photo"} ({photos.length}/{max})
          </button>
        )}
        <input ref={inputRef} type="file" accept="image/*" capture="environment" multiple onChange={handle} className="hidden" data-testid="photo-input" />
      </div>
      {photos.length > 0 && (
        <div className="grid grid-cols-3 gap-2">
          {photos.map((src, i) => (
            <div key={i} className="relative group aspect-square" data-testid={`photo-${i}`}>
              <img src={src} alt={`proof-${i}`} className="w-full h-full object-cover rounded-lg border border-stone-200" />
              <button type="button" onClick={() => onChange(photos.filter((_, idx) => idx !== i))}
                className="absolute -top-2 -right-2 bg-rose-500 hover:bg-rose-600 text-white text-xs font-bold w-6 h-6 rounded-full shadow"
                data-testid={`photo-remove-${i}`} title={L?.photoRemove || "Remove"}>×</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
