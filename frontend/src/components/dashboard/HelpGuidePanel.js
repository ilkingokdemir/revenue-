import React, { useEffect, useState, useMemo } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  BookOpen,
  MagnifyingGlass,
  Play,
  ListBullets,
  ArrowsClockwise,
  Download,
  X,
} from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

/**
 * In-app Help & User Guide.
 * Loads /api/help/manual and renders it with a sticky table-of-contents on the left.
 * Manager+ users also see a "Video script" tab to download/play.
 */
export default function HelpGuidePanel() {
  const [tab, setTab] = useState("manual"); // manual | video
  const [manual, setManual] = useState("");
  const [script, setScript] = useState("");
  const [index, setIndex] = useState([]);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState("");
  const [activeSection, setActiveSection] = useState(null);

  useEffect(() => {
    let dead = false;
    setLoading(true);
    Promise.all([
      axios.get(`${API}/api/help/manual`, { withCredentials: true }).catch(() => ({ data: { content: "" } })),
      axios.get(`${API}/api/help/index`, { withCredentials: true }).catch(() => ({ data: { sections: [] } })),
      axios.get(`${API}/api/help/video-script`, { withCredentials: true }).catch(() => ({ data: { content: "" } })),
    ]).then(([m, i, v]) => {
      if (dead) return;
      setManual(m.data.content || "");
      setIndex(i.data.sections || []);
      setScript(v.data.content || "");
      setLoading(false);
    });
    return () => { dead = true; };
  }, []);

  const filteredIndex = useMemo(() => {
    if (!query) return index;
    const q = query.toLowerCase();
    return index.filter((s) => s.title.toLowerCase().includes(q));
  }, [index, query]);

  const downloadMd = (content, name) => {
    const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    a.click();
    URL.revokeObjectURL(url);
    toast.success("İndirildi");
  };

  const printIt = () => {
    window.print();
  };

  return (
    <div className="p-5 max-w-[1500px] mx-auto" data-testid="help-panel">
      <div className="mb-5 flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
            <BookOpen size={12} weight="fill" /> Help & user guide
          </div>
          <h1 className="text-2xl font-semibold text-stone-900">Yardım & Kullanıcı Kılavuzu</h1>
          <p className="text-sm text-stone-500 mt-1 max-w-2xl">
            Yazılımı baştan sona anlatan tam el kitabı. Soldaki içerik tablosundan istediğiniz bölüme atlayın veya yukarıdan arayın.
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button onClick={() => downloadMd(manual, "MyHotelBox-Kullanim-Kilavuzu.md")} data-testid="help-download-manual" className="px-3 py-1.5 text-xs rounded-md border border-stone-200 hover:bg-stone-50 inline-flex items-center gap-1.5">
            <Download size={12} /> .md indir
          </button>
          <button onClick={printIt} data-testid="help-print" className="px-3 py-1.5 text-xs rounded-md border border-stone-200 hover:bg-stone-50">
            Yazdır
          </button>
        </div>
      </div>

      <div className="flex items-center gap-2 mb-4">
        <TabBtn active={tab === "manual"} onClick={() => setTab("manual")} testId="help-tab-manual">
          <BookOpen size={12} weight="fill" /> Kullanıcı Kılavuzu
        </TabBtn>
        {script && (
          <TabBtn active={tab === "video"} onClick={() => setTab("video")} testId="help-tab-video">
            <Play size={12} weight="fill" /> Video Script
          </TabBtn>
        )}
      </div>

      {loading && <div className="text-sm text-stone-400">Yükleniyor…</div>}

      {!loading && tab === "manual" && (
        <div className="grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-6">
          <aside className="lg:sticky lg:top-4 lg:self-start lg:max-h-[80vh] lg:overflow-y-auto" data-testid="help-toc">
            <div className="bg-stone-50 border border-stone-200 rounded-lg p-3">
              <div className="flex items-center gap-2 mb-2">
                <ListBullets size={14} className="text-stone-500" />
                <span className="text-xs font-semibold text-stone-700">İçindekiler</span>
              </div>
              <div className="relative mb-2">
                <MagnifyingGlass size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-stone-400" />
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Ara…"
                  data-testid="help-search"
                  className="w-full pl-7 pr-2 py-1 text-xs border border-stone-200 rounded focus:outline-none focus:border-stone-400"
                />
              </div>
              <ul className="space-y-0.5">
                {filteredIndex.map((s, i) => (
                  <li key={i}>
                    <a
                      href={`#${s.anchor}`}
                      onClick={(e) => {
                        e.preventDefault();
                        const el = document.getElementById(s.anchor);
                        if (el) {
                          el.scrollIntoView({ behavior: "smooth", block: "start" });
                          setActiveSection(s.anchor);
                        }
                      }}
                      className={`block text-xs py-1 ${s.level === 3 ? "pl-4 text-stone-500" : "font-semibold text-stone-700"} hover:text-stone-900 ${activeSection === s.anchor ? "text-stone-900" : ""}`}
                    >
                      {s.title}
                    </a>
                  </li>
                ))}
                {filteredIndex.length === 0 && <li className="text-xs text-stone-400 py-2">Sonuç yok.</li>}
              </ul>
            </div>
          </aside>
          <article className="prose prose-stone max-w-none" data-testid="help-manual-body">
            <Markdown text={manual} />
          </article>
        </div>
      )}

      {!loading && tab === "video" && script && (
        <div className="space-y-3">
          <div className="bg-violet-50 border border-violet-200 rounded-lg p-3 text-xs text-violet-900">
            Bu Türkçe **video tanıtım scripti**. 12-14 dakikalık ekran kaydı + voice-over için sahne sahne hazır. Loom, Tella veya OBS ile kaydedin. ElevenLabs Türkçe AI sesi ile %80 daha hızlı tamamlanır.
          </div>
          <div className="flex gap-2">
            <button onClick={() => downloadMd(script, "MyHotelBox-Video-Script.md")} data-testid="help-download-script" className="px-3 py-1.5 text-xs rounded-md bg-violet-600 text-white hover:bg-violet-700 inline-flex items-center gap-1.5">
              <Download size={12} /> Script .md indir
            </button>
          </div>
          <article className="prose prose-stone max-w-none bg-white border border-stone-200 rounded-lg p-4">
            <Markdown text={script} />
          </article>
        </div>
      )}
    </div>
  );
}

function TabBtn({ active, onClick, testId, children }) {
  return (
    <button
      onClick={onClick}
      data-testid={testId}
      className={`px-3 py-1.5 text-xs rounded-md inline-flex items-center gap-1.5 ${active ? "bg-stone-900 text-white" : "bg-stone-100 text-stone-600 hover:bg-stone-200"}`}
    >
      {children}
    </button>
  );
}

/**
 * Tiny markdown renderer — supports H1/H2/H3, **bold**, *italic*, `code`,
 * unordered lists, ordered lists, blockquotes, tables (basic), horizontal rules.
 * Avoids react-markdown to keep bundle small.
 */
function Markdown({ text }) {
  const blocks = useMemo(() => parseBlocks(text || ""), [text]);
  return <>{blocks.map((b, i) => renderBlock(b, i))}</>;
}

function parseBlocks(text) {
  const lines = text.split("\n");
  const blocks = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (/^---\s*$/.test(line)) {
      blocks.push({ type: "hr" });
      i++;
      continue;
    }
    const h = line.match(/^(#{1,3})\s+(.*)$/);
    if (h) {
      blocks.push({ type: "h", level: h[1].length, text: h[2] });
      i++;
      continue;
    }
    if (/^\|.+\|/.test(line) && i + 1 < lines.length && /^\|[\s:|-]+\|$/.test(lines[i + 1])) {
      const rows = [];
      while (i < lines.length && /^\|.+\|/.test(lines[i])) {
        rows.push(lines[i]);
        i++;
      }
      blocks.push({ type: "table", rows });
      continue;
    }
    if (/^[*-]\s+/.test(line)) {
      const items = [];
      while (i < lines.length && /^[*-]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^[*-]\s+/, ""));
        i++;
      }
      blocks.push({ type: "ul", items });
      continue;
    }
    if (/^\d+\.\s+/.test(line)) {
      const items = [];
      while (i < lines.length && /^\d+\.\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\d+\.\s+/, ""));
        i++;
      }
      blocks.push({ type: "ol", items });
      continue;
    }
    if (/^>\s+/.test(line)) {
      const buf = [];
      while (i < lines.length && /^>\s+/.test(lines[i])) {
        buf.push(lines[i].replace(/^>\s+/, ""));
        i++;
      }
      blocks.push({ type: "quote", text: buf.join(" ") });
      continue;
    }
    if (line.trim() === "") {
      i++;
      continue;
    }
    const buf = [line];
    i++;
    while (i < lines.length && lines[i].trim() !== "" && !/^(#{1,3}\s|---\s*$|[*-]\s|>\s|\d+\.\s|\|.+\|)/.test(lines[i])) {
      buf.push(lines[i]);
      i++;
    }
    blocks.push({ type: "p", text: buf.join(" ") });
  }
  return blocks;
}

function renderInline(text) {
  // bold **x** → <strong>, italic *x* → <em>, code `x` → <code>
  const parts = [];
  let cursor = 0;
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g;
  let m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > cursor) parts.push(text.slice(cursor, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) parts.push(<strong key={m.index} className="font-semibold text-stone-900">{tok.slice(2, -2)}</strong>);
    else if (tok.startsWith("`")) parts.push(<code key={m.index} className="bg-stone-100 px-1 py-0.5 rounded text-[12px] font-mono">{tok.slice(1, -1)}</code>);
    else parts.push(<em key={m.index} className="italic">{tok.slice(1, -1)}</em>);
    cursor = m.index + tok.length;
  }
  if (cursor < text.length) parts.push(text.slice(cursor));
  return parts;
}

function renderBlock(b, i) {
  if (b.type === "hr") return <hr key={i} className="my-6 border-stone-200" />;
  if (b.type === "h") {
    const id = (b.text || "").toLowerCase().replace(/[^\w\s-]/g, "").replace(/\s+/g, "-");
    if (b.level === 1) return <h1 key={i} id={id} className="text-3xl font-bold text-stone-900 mt-8 mb-3 scroll-mt-4">{renderInline(b.text)}</h1>;
    if (b.level === 2) return <h2 key={i} id={id} className="text-2xl font-bold text-stone-900 mt-7 mb-3 scroll-mt-4 border-b border-stone-200 pb-2">{renderInline(b.text)}</h2>;
    return <h3 key={i} id={id} className="text-lg font-semibold text-stone-800 mt-5 mb-2 scroll-mt-4">{renderInline(b.text)}</h3>;
  }
  if (b.type === "p") return <p key={i} className="text-sm text-stone-700 leading-relaxed mb-3">{renderInline(b.text)}</p>;
  if (b.type === "ul") return <ul key={i} className="list-disc pl-6 text-sm text-stone-700 leading-relaxed mb-3 space-y-1">{b.items.map((it, j) => <li key={j}>{renderInline(it)}</li>)}</ul>;
  if (b.type === "ol") return <ol key={i} className="list-decimal pl-6 text-sm text-stone-700 leading-relaxed mb-3 space-y-1">{b.items.map((it, j) => <li key={j}>{renderInline(it)}</li>)}</ol>;
  if (b.type === "quote") return <blockquote key={i} className="border-l-4 border-stone-900 pl-4 my-4 italic text-stone-700 bg-stone-50 py-2">{renderInline(b.text)}</blockquote>;
  if (b.type === "table") {
    const cells = b.rows.map((r) => r.replace(/^\|/, "").replace(/\|\s*$/, "").split("|").map((c) => c.trim()));
    const header = cells[0];
    // skip the divider row at index 1
    const body = cells.slice(2);
    return (
      <div key={i} className="my-4 overflow-x-auto">
        <table className="text-sm border-collapse w-full">
          <thead>
            <tr className="bg-stone-100">
              {header.map((h, j) => <th key={j} className="border border-stone-200 px-3 py-2 text-left font-semibold text-stone-700">{renderInline(h)}</th>)}
            </tr>
          </thead>
          <tbody>
            {body.map((row, ri) => (
              <tr key={ri} className="hover:bg-stone-50">
                {row.map((c, ci) => <td key={ci} className="border border-stone-200 px-3 py-1.5 text-stone-700 align-top">{renderInline(c)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }
  return null;
}

// Re-export icons used to keep tree clean
export { X };
