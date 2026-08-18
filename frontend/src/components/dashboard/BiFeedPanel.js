import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ChartBar,
  Plus,
  Copy,
  Trash,
  Download,
  ArrowsClockwise,
  Key,
  Code,
  FileCsv,
  ArrowSquareOut,
} from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

const ENTITY_LABELS = {
  Bookings: "Rezervasyonlar",
  Tips: "Bahşişler",
  FnbTabs: "F&B Tab'lar",
  Inquiries: "MICE Talepleri",
  CleanlinessScores: "Temizlik Skorları",
  WorkOrders: "İş Emirleri",
};

export default function BiFeedPanel({ propertyId }) {
  const [tab, setTab] = useState("tokens");

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="bi-feed-panel">
      <div className="mb-5">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          <ChartBar size={12} weight="fill" className="text-indigo-500" />
          <span>Enterprise BI Feed</span>
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">
          Power BI · Tableau · Excel
        </h1>
        <p className="text-sm text-stone-500 mt-1 max-w-2xl">
          OData v4 feed + Tableau Web Data Connector + CSV indirme. Token oluştur, BI aracında bağlan.
        </p>
      </div>

      <div className="flex gap-2 mb-5 border-b border-stone-200">
        <TabBtn active={tab === "tokens"} onClick={() => setTab("tokens")} testId="bi-tab-tokens">
          <Key size={14} className="inline mr-1.5" />
          Token'lar
        </TabBtn>
        <TabBtn active={tab === "connect"} onClick={() => setTab("connect")} testId="bi-tab-connect">
          <Code size={14} className="inline mr-1.5" />
          Bağlanma Talimatları
        </TabBtn>
        <TabBtn active={tab === "csv"} onClick={() => setTab("csv")} testId="bi-tab-csv">
          <FileCsv size={14} className="inline mr-1.5" />
          CSV İndir
        </TabBtn>
      </div>

      {tab === "tokens" && <TokensTab propertyId={propertyId} />}
      {tab === "connect" && <ConnectTab propertyId={propertyId} />}
      {tab === "csv" && <CsvTab propertyId={propertyId} />}
    </div>
  );
}

function TabBtn({ active, onClick, children, testId }) {
  return (
    <button onClick={onClick} data-testid={testId}
      className={`px-3.5 py-2 text-sm font-medium transition-all border-b-2 -mb-px ${
        active ? "border-indigo-500 text-indigo-700" : "border-transparent text-stone-500 hover:text-stone-800"
      }`}>
      {children}
    </button>
  );
}

function TokensTab({ propertyId }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [justCreated, setJustCreated] = useState(null);

  const load = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const r = await axios.get(`${API}/api/bi/tokens/${propertyId}`, { withCredentials: true });
      setRows(r.data.rows || []);
    } catch (e) {
      toast.error("Token'lar yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);

  const revoke = async (id) => {
    if (!window.confirm("Bu token iptal edilsin mi? Bu BI bağlantılarını kıracak.")) return;
    try {
      await axios.delete(`${API}/api/bi/tokens/${id}`, { withCredentials: true });
      toast.success("İptal edildi");
      load();
    } catch (e) {
      toast.error("Hata");
    }
  };

  const copy = (text) => {
    navigator.clipboard.writeText(text);
    toast.success("Kopyalandı");
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <div className="text-xs text-stone-500">Her token bir BI aracına özel oluşturun. Süre sonu girip ihtiyaç olduğunda iptal edin.</div>
        <button onClick={() => setShowNew(true)} data-testid="bi-new-token-btn" className="px-3 py-1.5 text-xs rounded-md bg-indigo-500 text-white hover:bg-indigo-600 inline-flex items-center gap-1.5">
          <Plus size={12} weight="bold" />
          Yeni Token
        </button>
      </div>

      {showNew && <NewTokenForm propertyId={propertyId} onCreated={(t) => { setShowNew(false); setJustCreated(t); load(); }} onCancel={() => setShowNew(false)} />}

      {justCreated && (
        <div className="bg-emerald-50 border-2 border-emerald-200 rounded-lg p-4" data-testid="bi-just-created">
          <div className="text-xs font-semibold text-emerald-800 uppercase tracking-wider mb-2">⚠️ Token sadece şimdi gösterilir — kopyalayın</div>
          <div className="bg-white border border-stone-200 rounded p-2 flex items-center gap-2">
            <code className="text-xs font-mono flex-1 truncate text-stone-800">{justCreated.token}</code>
            <button onClick={() => copy(justCreated.token)} data-testid="bi-copy-fresh-token" className="px-2 py-1 text-xs rounded border border-stone-200 inline-flex items-center gap-1">
              <Copy size={11} /> Kopyala
            </button>
          </div>
          <button onClick={() => setJustCreated(null)} className="mt-2 text-xs text-emerald-700 hover:text-emerald-900">Tamam, kapatabilirim</button>
        </div>
      )}

      {loading && <div className="text-sm text-stone-400">Yükleniyor…</div>}

      {rows.length === 0 && !loading && (
        <div className="text-center py-12 text-stone-400 text-sm border border-dashed border-stone-200 rounded-lg">
          Henüz token yok. "Yeni Token" ile başlayın.
        </div>
      )}

      <div className="space-y-2" data-testid="bi-tokens-list">
        {rows.map((t) => (
          <div key={t.id} className="bg-white border border-stone-200 rounded-lg p-3.5" data-testid={`bi-token-row-${t.id}`}>
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-sm font-semibold text-stone-900">{t.name}</span>
                  {t.revoked ? (
                    <span className="px-1.5 py-0.5 text-[10px] rounded bg-rose-100 text-rose-700">İPTAL EDİLDİ</span>
                  ) : (
                    <span className="px-1.5 py-0.5 text-[10px] rounded bg-emerald-100 text-emerald-700">AKTİF</span>
                  )}
                </div>
                <div className="font-mono text-[10px] text-stone-500">{t.token_masked}</div>
                <div className="text-[11px] text-stone-500 mt-1">
                  Oluşturma: {t.created_at?.slice(0, 10)} · Sona erme: {t.expires_at?.slice(0, 10)}
                  {t.use_count > 0 && ` · ${t.use_count} kez kullanıldı`}
                  {t.last_used_at && ` · Son: ${t.last_used_at?.slice(0, 16).replace("T", " ")}`}
                </div>
              </div>
              {!t.revoked && (
                <button onClick={() => revoke(t.id)} data-testid={`bi-revoke-${t.id}`} className="px-2 py-1 text-xs rounded-md text-rose-600 hover:bg-rose-50 inline-flex items-center gap-1">
                  <Trash size={12} />
                  İptal
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function NewTokenForm({ propertyId, onCreated, onCancel }) {
  const [name, setName] = useState("");
  const [days, setDays] = useState(365);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!name.trim()) { toast.error("İsim girin"); return; }
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/bi/tokens`, {
        property_id: propertyId,
        name: name.trim(),
        expires_days: parseInt(days) || 365,
      }, { withCredentials: true });
      toast.success("Token oluşturuldu");
      onCreated(r.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Hata");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="bg-stone-50 border border-stone-200 rounded-lg p-4 space-y-3" data-testid="bi-new-form">
      <div className="text-sm font-semibold text-stone-800">Yeni BI Feed Token</div>
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="block text-[11px] uppercase tracking-wider text-stone-500 mb-1">İsim</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Örn: Power BI - Finans"
            data-testid="bi-form-name"
            className="w-full px-3 py-2 text-sm border border-stone-200 rounded-md focus:outline-none focus:border-indigo-400"
          />
        </div>
        <div>
          <label className="block text-[11px] uppercase tracking-wider text-stone-500 mb-1">Süre (gün)</label>
          <input
            type="number"
            value={days}
            onChange={(e) => setDays(e.target.value)}
            min={1}
            max={3650}
            data-testid="bi-form-days"
            className="w-full px-3 py-2 text-sm border border-stone-200 rounded-md focus:outline-none focus:border-indigo-400"
          />
        </div>
      </div>
      <div className="flex gap-2 justify-end">
        <button onClick={onCancel} className="px-3 py-1.5 text-xs rounded-md border border-stone-200 text-stone-600">Vazgeç</button>
        <button onClick={submit} disabled={busy} data-testid="bi-form-submit" className="px-3 py-1.5 text-xs rounded-md bg-indigo-500 text-white hover:bg-indigo-600 disabled:opacity-50">
          {busy ? "Oluşturuluyor…" : "Oluştur"}
        </button>
      </div>
    </div>
  );
}

function ConnectTab({ propertyId }) {
  const [tokens, setTokens] = useState([]);
  const [selectedTokenId, setSelectedTokenId] = useState("");
  const [samples, setSamples] = useState(null);

  const loadTokens = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/api/bi/tokens/${propertyId}`, { withCredentials: true });
      const active = (r.data.rows || []).filter((t) => !t.revoked);
      setTokens(active);
      if (active.length > 0 && !selectedTokenId) {
        setSelectedTokenId(active[0].id);
      }
    } catch (e) {}
  }, [propertyId, selectedTokenId]);

  useEffect(() => { loadTokens(); }, [loadTokens]);

  const loadSamples = useCallback(async () => {
    if (!selectedTokenId) return;
    try {
      const r = await axios.get(`${API}/api/bi/sample-urls/${selectedTokenId}`, { withCredentials: true });
      setSamples(r.data);
    } catch (e) {
      toast.error("Örnek URL'ler yüklenemedi");
    }
  }, [selectedTokenId]);

  useEffect(() => { loadSamples(); }, [loadSamples]);

  const copy = (text) => {
    navigator.clipboard.writeText(text);
    toast.success("Kopyalandı");
  };

  if (tokens.length === 0) {
    return (
      <div className="text-center py-12 text-stone-400 text-sm border border-dashed border-stone-200 rounded-lg">
        Önce "Token'lar" sekmesinden bir token oluşturun.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-[11px] uppercase tracking-wider text-stone-500 mb-1">Aktif Token Seçin</label>
        <select
          value={selectedTokenId}
          onChange={(e) => setSelectedTokenId(e.target.value)}
          data-testid="bi-token-select"
          className="px-3 py-2 text-sm border border-stone-200 rounded-md bg-white focus:outline-none focus:border-indigo-400"
        >
          {tokens.map((t) => (
            <option key={t.id} value={t.id}>{`${t.name} (${t.token_masked})`}</option>
          ))}
        </select>
      </div>

      {samples && (
        <div className="grid md:grid-cols-2 gap-4">
          <ConnectionCard
            title="Power BI Desktop"
            color="amber"
            steps={samples.powerbi_instructions}
            url={samples.odata_root}
            onCopy={copy}
            testId="bi-connect-powerbi"
          />
          <ConnectionCard
            title="Microsoft Excel"
            color="emerald"
            steps={samples.excel_instructions}
            url={samples.odata_root}
            onCopy={copy}
            testId="bi-connect-excel"
          />
          <ConnectionCard
            title="Tableau Desktop"
            color="indigo"
            steps={[
              "Tableau Desktop → Connect → To a Server → Web Data Connector",
              "URL aşağıdaki:",
            ]}
            url={samples.tableau_wdc}
            externalLabel="WDC sayfasını aç"
            onCopy={copy}
            testId="bi-connect-tableau"
          />
          <ConnectionCard
            title="OData (Genel)"
            color="violet"
            steps={["Diğer BI araçları için OData v4 kök URL:", "Auth: Anonymous"]}
            url={samples.odata_root}
            onCopy={copy}
            testId="bi-connect-odata"
          />
        </div>
      )}
    </div>
  );
}

function ConnectionCard({ title, color, steps, url, externalLabel, onCopy, testId }) {
  const bg = {
    amber: "from-amber-50 to-amber-100/30 border-amber-200",
    emerald: "from-emerald-50 to-emerald-100/30 border-emerald-200",
    indigo: "from-indigo-50 to-indigo-100/30 border-indigo-200",
    violet: "from-violet-50 to-violet-100/30 border-violet-200",
  }[color];
  const text = {
    amber: "text-amber-700",
    emerald: "text-emerald-700",
    indigo: "text-indigo-700",
    violet: "text-violet-700",
  }[color];
  return (
    <div className={`bg-gradient-to-br ${bg} border-2 rounded-lg p-4`} data-testid={testId}>
      <div className={`text-base font-semibold ${text} mb-2`}>{title}</div>
      <ol className="text-xs text-stone-700 space-y-1 mb-3 list-decimal list-inside">
        {steps.map((s, i) => <li key={i}>{s}</li>)}
      </ol>
      <div className="bg-white border border-stone-200 rounded-md p-2 flex items-center gap-2">
        <code className="text-[10px] font-mono flex-1 truncate text-stone-700">{url}</code>
        <button onClick={() => onCopy(url)} className="px-2 py-1 text-[10px] rounded border border-stone-200 hover:bg-stone-50 inline-flex items-center gap-1">
          <Copy size={10} /> Kopyala
        </button>
        {externalLabel && (
          <a href={url} target="_blank" rel="noreferrer" className="px-2 py-1 text-[10px] rounded bg-stone-900 text-white hover:bg-stone-800 inline-flex items-center gap-1">
            <ArrowSquareOut size={10} /> {externalLabel}
          </a>
        )}
      </div>
    </div>
  );
}

function CsvTab({ propertyId }) {
  const [tokens, setTokens] = useState([]);
  const [selectedToken, setSelectedToken] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const r = await axios.get(`${API}/api/bi/tokens/${propertyId}`, { withCredentials: true });
        setTokens((r.data.rows || []).filter((t) => !t.revoked));
      } catch (e) {}
    })();
  }, [propertyId]);

  // Need actual full token to construct URL, but we don't expose it after creation.
  // Workaround: ask user to paste their token.
  const [manualToken, setManualToken] = useState("");

  const downloadCsv = (entity) => {
    const t = manualToken.trim();
    if (!t) { toast.error("Token yapıştırın"); return; }
    window.open(`${API}/api/bi/csv/${entity}?token=${encodeURIComponent(t)}`, "_blank");
  };

  return (
    <div className="space-y-4">
      <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-800">
        💡 Token'lar oluşturulduktan sonra güvenlik için tam değer gösterilmiyor. CSV indirmek için Token'lar sekmesinden token'ı kopyalayıp aşağıya yapıştırın (sadece oluşturulduğu anda kopyalayabilirsiniz).
      </div>

      <div>
        <label className="block text-[11px] uppercase tracking-wider text-stone-500 mb-1">Token Yapıştır</label>
        <input
          type="password"
          value={manualToken}
          onChange={(e) => setManualToken(e.target.value)}
          placeholder="hbk_..."
          data-testid="bi-csv-token-input"
          className="w-full px-3 py-2 text-sm border border-stone-200 rounded-md font-mono focus:outline-none focus:border-indigo-400"
        />
        <div className="text-[10px] text-stone-400 mt-1">
          Aktif token sayısı: {tokens.length}
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-3" data-testid="bi-csv-grid">
        {Object.entries(ENTITY_LABELS).map(([k, l]) => (
          <button
            key={k}
            onClick={() => downloadCsv(k)}
            disabled={!manualToken.trim()}
            data-testid={`bi-csv-${k}`}
            className="p-4 bg-white border-2 border-stone-200 rounded-lg hover:border-indigo-400 hover:shadow-sm transition-all text-left disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <div className="flex items-center gap-2">
              <Download size={16} className="text-indigo-500" />
              <div>
                <div className="text-sm font-semibold text-stone-900">{l}</div>
                <div className="text-[10px] text-stone-400">{k}.csv</div>
              </div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
