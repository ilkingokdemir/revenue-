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

# ─────────────────────────────────────────────────────────────────────────
# Expense category taxonomy — used both for auto-classification on upload
# and as the UI dropdown list. Each entry is (canonical_label, keywords).
# The classifier matches whichever category has the largest keyword overlap
# with the user's label text. Keywords are intentionally multilingual
# (English + Turkish) since operators often type a mix.
# ─────────────────────────────────────────────────────────────────────────
EXPENSE_CATEGORIES: List[Tuple[str, List[str]]] = [
    ("Kira",            ["rent", "kira", "leasing", "lease"]),
    ("Komisyon",        ["commission", "comissoin", "komisyon", "booking fee", "ota fee", "channel"]),
    ("Vergi",           ["tax", "vergi", "kdv", "vat", "stopaj", "withholding"]),
    ("Personel",        ["salary", "salaries", "personel", "maaş", "maas", "wages", "payroll", "staff", "tip", "bonus"]),
    ("Temizlik",        ["temizlik", "cleaning", "leaning", "housekeeping", "laundry", "çamaşır", "camasir", "linen"]),
    ("Bakım & Onarım",  ["bakım", "bakim", "onarım", "onarim", "maintenance", "repair", "tamir"]),
    ("Enerji & Su",     ["elektrik", "electricity", "energy", "enerji", "gas", "doğalgaz", "dogalgaz", "su", "water", "utility", "utilities"]),
    ("İnternet & İletişim", ["internet", "iletişim", "iletisim", "telecom", "phone", "telefon", "wifi"]),
    ("Pazarlama",       ["marketing", "pazarlama", "reklam", "advertising", "advert", "ads", "seo", "ppc"]),
    ("Sigorta",         ["sigorta", "insurance", "policy"]),
    ("Belediye/Council", ["council", "belediye", "municipal", "rates", "property tax"]),
    ("Yiyecek & İçecek", ["food", "beverage", "f&b", "fb", "yiyecek", "içecek", "icecek", "kahvaltı", "kahvalti", "breakfast"]),
    ("Yönetim & Ofis",  ["admin", "yönetim", "yonetim", "office", "ofis", "muhasebe", "accounting", "legal", "avukat"]),
    ("Yazılım & Abonelik", ["software", "yazılım", "yazilim", "subscription", "abonelik", "saas", "pms"]),
    ("Banka & Komisyon Ücretleri", ["bank", "banka", "fee", "ödeme", "odeme", "stripe", "iyzico", "payment"]),
]

# Convenience: ordered list of canonical names for FE dropdown
EXPENSE_CATEGORY_NAMES: List[str] = [c[0] for c in EXPENSE_CATEGORIES] + ["Diğer"]


def classify_expense(label: str) -> str:
    """Return the best-matching canonical category for an expense label,
    or 'Diğer' (Other) if nothing matches."""
    if not label:
        return "Diğer"
    t = label.strip().lower()
    if not t:
        return "Diğer"
    best = ("Diğer", 0)
    for canon, keywords in EXPENSE_CATEGORIES:
        score = 0
        for kw in keywords:
            if kw in t:
                # Longer keyword matches outweigh shorter ones (e.g. "council"
                # should beat "cou…" overlap).
                score = max(score, len(kw))
        if score > best[1]:
            best = (canon, score)
    return best[0]


# ─────────────────────────────────────────────────────────────────────────
# Month name → number lookup (English + Turkish, full + abbreviations)
# ─────────────────────────────────────────────────────────────────────────
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


def _is_expense_label(s: str) -> bool:
    """Heuristic: a non-empty string that is NOT a month name, NOT a year,
    NOT a pure number. Typical examples: 'rent', 'commission', 'temizlik'.
    """
    if not s:
        return False
    t = str(s).strip().lower()
    if not t or len(t) < 2 or len(t) > 40:
        return False
    if t in _MONTH_MAP:
        return False
    # Pure number or year
    if re.fullmatch(r"\d{2,4}([.,]\d{1,2})?", t):
        return False
    # Common revenue/header keywords to skip (these are not expenses)
    skip = {
        "date", "month", "year", "total", "subtotal", "revenue", "gelir",
        "ciro", "income", "gross", "net", "adr", "occupancy", "doluluk",
        "bookings", "nights", "room rates", "accommodations", "yıl",
    }
    if t in skip:
        return False
    # If contains a digit but also letters → maybe "room rates 2025" header
    has_letter = any(c.isalpha() for c in t)
    if not has_letter:
        return False
    return True


def extract_expenses_from_spreadsheet(df) -> List[Dict]:
    """Find rows that look like {label: text, amount: number} expense entries.
    Used after main month/revenue parsing to capture the cost-line items the
    operator typically lists below the monthly table (rent, cleaning, council,
    commission, etc.).
    """
    expenses: List[Dict] = []
    seen_labels = set()
    n_cols = df.shape[1]
    for i in range(len(df)):
        # Find a label cell and an amount cell on this row
        label_val: Optional[str] = None
        amount_val: Optional[float] = None
        for c in range(n_cols):
            cell = str(df.iat[i, c]).strip() if df.iat[i, c] is not None else ""
            if not cell:
                continue
            # Is this cell a month? Skip the whole row — it's an income row.
            if _detect_month(cell, 0) is not None:
                label_val = None
                break
            num = _normalise_number(cell)
            if num is not None and num >= 100:
                if amount_val is None or num > amount_val:
                    amount_val = num
            elif _is_expense_label(cell):
                if label_val is None or len(cell) > len(label_val):
                    label_val = cell
        if label_val and amount_val and amount_val >= 100:
            key = label_val.strip().lower()
            if key in seen_labels:
                continue
            seen_labels.add(key)
            expenses.append({
                "label": label_val.strip(),
                "amount": round(amount_val, 2),
                "period": "annual",  # default; user can edit in UI
                "category": classify_expense(label_val),
            })
    return expenses


# ─────────────────────────────────────────────────────────────────────────
# Spreadsheet (XLSX / XLS / CSV)
# ─────────────────────────────────────────────────────────────────────────
def parse_spreadsheet(content: bytes, filename: str, default_year: int) -> Tuple[List[Dict], List[Dict]]:
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
    income_entries = sorted(by_key.values(), key=lambda x: x["month_key"])
    expenses = extract_expenses_from_spreadsheet(df)
    return income_entries, expenses


# ─────────────────────────────────────────────────────────────────────────
# PDF — text extraction first, OCR fallback
# ─────────────────────────────────────────────────────────────────────────
def parse_pdf(content: bytes, default_year: int) -> Tuple[List[Dict], List[Dict]]:
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
def parse_image(content: bytes, default_year: int) -> Tuple[List[Dict], List[Dict]]:
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
def parse_text_block(text: str, default_year: int) -> Tuple[List[Dict], List[Dict]]:
    """Extract (month, revenue) pairs AND expense rows from free-text.
    Returns (income_entries, expenses).
    """
    if not text:
        return [], []
    by_key: Dict[str, Dict] = {}
    expenses: List[Dict] = []
    seen_exp_labels: set = set()
    # Match month tokens (full/abbrev English+Turkish OR YYYY-MM OR MM/YYYY)
    month_re = re.compile(
        r"(?:(\d{4})[-/.](\d{1,2})|(\d{1,2})[-/.](\d{4})|"
        r"([A-Za-zÇĞİÖŞÜçğıöşü]{3,12})\s*[-,/]?\s*(\d{2,4})?)",
        re.UNICODE,
    )
    num_re = re.compile(r"[£$€₺]?\s*\d[\d.,]*\d|\d")

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or len(line) < 4:
            continue
        ym = None
        match_span = None
        for m in month_re.finditer(line):
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
        if ym:
            # ── INCOME row ──
            line_for_nums = line
            if match_span:
                line_for_nums = line[:match_span[0]] + (" " * (match_span[1] - match_span[0])) + line[match_span[1]:]
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
        else:
            # ── Possible EXPENSE line ── extract a label + amount
            # Look for the largest number on the line and a labelish word
            nums: List[float] = []
            for nm in num_re.finditer(line):
                v = _normalise_number(nm.group(0))
                if v is not None and v >= 100:
                    nums.append(v)
            if not nums:
                continue
            amount = max(nums)
            # Strip currency and digit tokens to find the label words
            label_part = re.sub(r"[£$€₺]?\s*\d[\d.,]*", " ", line)
            label_part = re.sub(r"[^A-Za-zÇĞİÖŞÜçğıöşü\s]", " ", label_part)
            label_part = re.sub(r"\s+", " ", label_part).strip()
            if not _is_expense_label(label_part):
                continue
            key = label_part.lower()
            if key in seen_exp_labels:
                continue
            seen_exp_labels.add(key)
            expenses.append({
                "label": label_part,
                "amount": round(amount, 2),
                "period": "annual",
                "category": classify_expense(label_part),
            })
    return sorted(by_key.values(), key=lambda x: x["month_key"]), expenses


# ─────────────────────────────────────────────────────────────────────────
# Main dispatcher
# ─────────────────────────────────────────────────────────────────────────
def parse_upload(content: bytes, filename: str, default_year: int) -> Dict:
    """Returns {entries, expenses, source_kind, detected_count}.
    `entries` = monthly revenue rows · `expenses` = annual cost-line items.
    """
    name = (filename or "").lower()
    if name.endswith((".xlsx", ".xls")):
        entries, expenses = parse_spreadsheet(content, filename, default_year)
        kind = "excel"
    elif name.endswith(".csv"):
        entries, expenses = parse_spreadsheet(content, filename, default_year)
        kind = "csv"
    elif name.endswith(".pdf"):
        entries, expenses = parse_pdf(content, default_year)
        kind = "pdf"
    elif name.endswith((".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff")):
        entries, expenses = parse_image(content, default_year)
        kind = "image"
    else:
        raise ValueError(f"Unsupported file type: {filename}")
    return {
        "entries": entries,
        "expenses": expenses,
        "source_kind": kind,
        "detected_count": len(entries),
        "detected_expenses_count": len(expenses),
    }
