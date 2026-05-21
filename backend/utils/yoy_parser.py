"""
YoY (Year-over-Year) History File Parser
─────────────────────────────────────────
Parses uploaded historical revenue files (Excel / CSV / PDF / JPG / PNG) into
a normalised list of {year, month, month_key, revenue} rows that feed the
Performance Report's YoY comparison.

Strategy (no paid APIs):
    • .xlsx / .xls → openpyxl + pandas
    • .csv         → pandas
    • .pdf         → pdfplumber text extraction (fallback: pdf2image → Tesseract OCR)
    • .jpg / .png  → Tesseract OCR (PIL)

The parser is intentionally forgiving about formats. It looks for a month
column (Jan/Şub/01/2025-01) and a revenue column (numeric, large value) and
returns whatever it can find. The user reviews and edits the output in a
preview table before saving, so 100% accuracy is not required.
"""
from __future__ import annotations
import io
import re
import calendar
import logging
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Month name → number lookup (English + Turkish, full + abbreviations)
_MONTH_MAP: Dict[str, int] = {}
for i, names in enumerate([
    ["january", "jan", "ocak", "oca"],
    ["february", "feb", "şubat", "subat", "şub", "sub"],
    ["march", "mar", "mart", "mar"],
    ["april", "apr", "nisan", "nis"],
    ["may", "mayıs", "mayis", "may"],
    ["june", "jun", "haziran", "haz"],
    ["july", "jul", "temmuz", "tem"],
    ["august", "aug", "ağustos", "agustos", "ağu", "agu"],
    ["september", "sep", "sept", "eylül", "eylul", "eyl"],
    ["october", "oct", "ekim", "eki"],
    ["november", "nov", "kasım", "kasim", "kas"],
    ["december", "dec", "aralık", "aralik", "ara"],
], start=1):
    for n in names:
        _MONTH_MAP[n.lower()] = i


def _normalise_number(raw: str) -> Optional[float]:
    """Convert '£1,234.50' / '1.234,50' / '1234,50 TL' → 1234.50."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    # Strip currency symbols and letters
    s = re.sub(r"[£$€₺¥\s]|TL|GBP|USD|EUR|TRY|JPY", "", s, flags=re.I)
    if not s:
        return None
    # If both . and , present → assume European fmt (1.234,50) or US (1,234.50)
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        # Comma only — could be thousands or decimal. If 3 digits after comma → thousands.
        last = s.split(",")[-1]
        if len(last) == 3 and "." not in s:
            s = s.replace(",", "")
        else:
            s = s.replace(",", ".")
    try:
        v = float(s)
        return v if v > 0 else None
    except Exception:
        return None


def _detect_month(cell: str, default_year: int) -> Optional[Tuple[int, int]]:
    """Detect (year, month) from a free-text cell. Returns None if not a month."""
    if cell is None:
        return None
    s = str(cell).strip().lower()
    if not s:
        return None
    # YYYY-MM, YYYY/MM
    m = re.match(r"^(\d{4})[-/.](\d{1,2})$", s)
    if m:
        y, mm = int(m.group(1)), int(m.group(2))
        if 1 <= mm <= 12:
            return y, mm
    # MM/YYYY, MM-YYYY
    m = re.match(r"^(\d{1,2})[-/.](\d{4})$", s)
    if m:
        mm, y = int(m.group(1)), int(m.group(2))
        if 1 <= mm <= 12:
            return y, mm
    # "Jan 2025", "January 2025", "Ocak 2025", "Şub 25"
    m = re.match(r"^([A-Za-zÇĞİÖŞÜçğıöşü]+)\s+(\d{2,4})$", s)
    if m:
        name, yr = m.group(1).lower(), m.group(2)
        if name in _MONTH_MAP:
            y = int(yr) if len(yr) == 4 else 2000 + int(yr)
            return y, _MONTH_MAP[name]
    # Just a month name → assume default_year
    if s in _MONTH_MAP:
        return default_year, _MONTH_MAP[s]
    # "2025 Jan", "25 Şub"
    m = re.match(r"^(\d{2,4})\s+([A-Za-zÇĞİÖŞÜçğıöşü]+)$", s)
    if m:
        yr, name = m.group(1), m.group(2).lower()
        if name in _MONTH_MAP:
            y = int(yr) if len(yr) == 4 else 2000 + int(yr)
            return y, _MONTH_MAP[name]
    return None


def _row_to_entry(month_cell, revenue_cell, default_year: int) -> Optional[Dict]:
    ym = _detect_month(month_cell, default_year)
    if not ym:
        return None
    rev = _normalise_number(revenue_cell)
    if rev is None or rev < 1:  # ignore zeros and empties
        return None
    y, mm = ym
    return {
        "year": y,
        "month": mm,
        "month_key": f"{y:04d}-{mm:02d}",
        "month_label": f"{calendar.month_abbr[mm]} {y}",
        "revenue": round(rev, 2),
    }


# ─────────────────────────────────────────────────────────────────────────
# Spreadsheet (XLSX / XLS / CSV)
# ─────────────────────────────────────────────────────────────────────────
def parse_spreadsheet(content: bytes, filename: str, default_year: int) -> List[Dict]:
    import pandas as pd
    name = filename.lower()
    if name.endswith(".csv"):
        try:
            df = pd.read_csv(io.BytesIO(content), header=None, dtype=str, encoding="utf-8")
        except Exception:
            df = pd.read_csv(io.BytesIO(content), header=None, dtype=str, encoding="latin-1")
    else:
        df = pd.read_excel(io.BytesIO(content), header=None, dtype=str)
    df = df.fillna("")
    entries: List[Dict] = []
    seen_keys = set()

    # Try each pair of columns — find the (month_col, revenue_col) combo
    # that yields the most valid rows. When multiple (mc, rc) pairs produce
    # the SAME number of valid rows (e.g. an Excel with month-col + several
    # numeric cols like ADR / nights / revenue), pick the one with the
    # HIGHEST total — that's almost always the revenue column rather than
    # ADR or occupancy.
    n_cols = df.shape[1]
    best: Tuple[int, int, List[Dict], float] = (-1, -1, [], -1.0)
    for mc in range(n_cols):
        for rc in range(n_cols):
            if mc == rc:
                continue
            rows: List[Dict] = []
            local_seen = set()
            for i in range(len(df)):
                e = _row_to_entry(df.iat[i, mc], df.iat[i, rc], default_year)
                if e and e["month_key"] not in local_seen:
                    local_seen.add(e["month_key"])
                    rows.append(e)
            row_total = sum(r["revenue"] for r in rows)
            if (len(rows) > len(best[2])) or (len(rows) == len(best[2]) and row_total > best[3]):
                best = (mc, rc, rows, row_total)
    entries = best[2]
    # Deduplicate by month_key (keep the largest revenue if duplicates)
    by_key: Dict[str, Dict] = {}
    for e in entries:
        if e["month_key"] not in by_key or e["revenue"] > by_key[e["month_key"]]["revenue"]:
            by_key[e["month_key"]] = e
    return sorted(by_key.values(), key=lambda x: x["month_key"])


# ─────────────────────────────────────────────────────────────────────────
# PDF — text extraction first, OCR fallback
# ─────────────────────────────────────────────────────────────────────────
def parse_pdf(content: bytes, default_year: int) -> List[Dict]:
    text = ""
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            text = "\n".join((p.extract_text() or "") for p in pdf.pages)
    except Exception as e:
        logger.warning("pdfplumber failed: %s", e)

    if not text.strip() or len(text.strip()) < 30:
        # Image-only PDF → OCR each page
        try:
            from pdf2image import convert_from_bytes
            import pytesseract
            imgs = convert_from_bytes(content, dpi=180, first_page=1, last_page=10)
            ocr_chunks = []
            for img in imgs:
                ocr_chunks.append(pytesseract.image_to_string(img, lang="eng+tur"))
            text = "\n".join(ocr_chunks)
        except Exception as e:
            logger.warning("PDF OCR failed: %s", e)

    return parse_text_block(text, default_year)


# ─────────────────────────────────────────────────────────────────────────
# Image (JPG/PNG) — Tesseract OCR
# ─────────────────────────────────────────────────────────────────────────
def parse_image(content: bytes, default_year: int) -> List[Dict]:
    from PIL import Image
    import pytesseract
    img = Image.open(io.BytesIO(content))
    if img.mode != "RGB":
        img = img.convert("RGB")
    text = pytesseract.image_to_string(img, lang="eng+tur")
    return parse_text_block(text, default_year)


# ─────────────────────────────────────────────────────────────────────────
# Generic text-block parser (line-by-line)
# ─────────────────────────────────────────────────────────────────────────
def parse_text_block(text: str, default_year: int) -> List[Dict]:
    """Extract (month, revenue) pairs from free-text. Each line is scanned
    for a month token and a numeric token; if both are present we emit a row.
    """
    if not text:
        return []
    by_key: Dict[str, Dict] = {}
    # Match month tokens (full/abbrev English+Turkish OR YYYY-MM OR MM/YYYY)
    month_re = re.compile(
        r"(?:(\d{4})[-/.](\d{1,2})|(\d{1,2})[-/.](\d{4})|"
        r"([A-Za-zÇĞİÖŞÜçğıöşü]{3,12})\s*[-,/]?\s*(\d{2,4})?)",
        re.UNICODE,
    )
    # Match any numeric token (currency-prefixed) and let _normalise_number
    # parse the format. Using a single greedy bracket-class avoids the
    # subtle backtracking pitfalls of trying to encode all thousand-separator
    # rules into the regex itself.
    num_re = re.compile(r"[£$€₺]?\s*\d[\d.,]*\d|\d")

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or len(line) < 4:
            continue
        # Find first month-like token in the line
        ym = None
        match_span = None
        for m in month_re.finditer(line):
            # Year-Month numeric
            if m.group(1) and m.group(2):
                yr, mm = int(m.group(1)), int(m.group(2))
                if 1 <= mm <= 12 and 2000 <= yr <= 2100:
                    ym = (yr, mm); match_span = m.span(); break
            elif m.group(3) and m.group(4):
                mm, yr = int(m.group(3)), int(m.group(4))
                if 1 <= mm <= 12 and 2000 <= yr <= 2100:
                    ym = (yr, mm); match_span = m.span(); break
            elif m.group(5):
                name = m.group(5).lower()
                if name in _MONTH_MAP:
                    yr = int(m.group(6)) if m.group(6) else default_year
                    if yr < 100:
                        yr += 2000
                    ym = (yr, _MONTH_MAP[name]); match_span = m.span(); break
        if not ym:
            continue
        # Mask out the month-match region so the year inside it isn't picked
        # up as a revenue value (e.g. "Jan 2025: £450" must NOT yield 2025).
        line_for_nums = line
        if match_span:
            line_for_nums = line[:match_span[0]] + (" " * (match_span[1] - match_span[0])) + line[match_span[1]:]
        # Find the largest plausible number on the line (must be > 100)
        nums: List[float] = []
        for nm in num_re.finditer(line_for_nums):
            v = _normalise_number(nm.group(0))
            if v is not None and v > 100:
                nums.append(v)
        if not nums:
            continue
        rev = max(nums)
        y, mm = ym
        key = f"{y:04d}-{mm:02d}"
        if key not in by_key or rev > by_key[key]["revenue"]:
            by_key[key] = {
                "year": y, "month": mm, "month_key": key,
                "month_label": f"{calendar.month_abbr[mm]} {y}",
                "revenue": round(rev, 2),
            }
    return sorted(by_key.values(), key=lambda x: x["month_key"])


# ─────────────────────────────────────────────────────────────────────────
# Main dispatcher
# ─────────────────────────────────────────────────────────────────────────
def parse_upload(content: bytes, filename: str, default_year: int) -> Dict:
    """Returns {entries: [...], source_kind: 'excel|csv|pdf|image', detected_count: N}."""
    name = (filename or "").lower()
    if name.endswith((".xlsx", ".xls")):
        entries = parse_spreadsheet(content, filename, default_year)
        kind = "excel"
    elif name.endswith(".csv"):
        entries = parse_spreadsheet(content, filename, default_year)
        kind = "csv"
    elif name.endswith(".pdf"):
        entries = parse_pdf(content, default_year)
        kind = "pdf"
    elif name.endswith((".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff")):
        entries = parse_image(content, default_year)
        kind = "image"
    else:
        raise ValueError(f"Unsupported file type: {filename}")
    return {
        "entries": entries,
        "source_kind": kind,
        "detected_count": len(entries),
    }
