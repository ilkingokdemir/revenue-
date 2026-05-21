# Changelog — Hotel PMS & Revenue Management

## 2026-05-21 — Net Kâr (Gelir − Gider) Performance Report'a eklendi
- **Goal**: Operatör yıllık/aylık net kârını aynı sayfada görsün.
- **Backend** (`market_robot.py` + `utils/yoy_parser.py`):
  - Parser artık Excel/PDF/JPG/CSV'lerden hem **aylık gelir** hem **gider kalemleri** (rent / commission / temizlik / council / cleaning vb.) çıkartıyor — annual veya monthly periyod.
  - `POST /yoy-upload/confirm` artık `entries` yanında `expenses` listesini de saklıyor (yeni koleksiyon `property_yoy_expenses`).
  - `GET /yoy-history` artık `{rows, expenses}` döndürüyor.
  - Yeni `DELETE /yoy-expenses` endpoint'i.
  - `GET /performance` response'ında yeni `annual_forecast.expenses` blok: `items`, `annual_total`, `monthly_avg`, `annual_net_revenue`, `net_margin_pct`. Her aylık forecast row'una `expense` ve `net_revenue` decorate edildi.
- **Frontend**:
  - `YoYUploadModal` artık iki tablolu: Gelir + Gider. Her tablo düzenlenebilir; "Yıllık/Aylık" periyod seçimi destekleniyor. Canlı **Net = Gelir − Gider** özeti.
  - `PerformanceReport`: Annual forecast card'ında yeni **"Yıllık Net Kâr" strip** — Gelir / Gider / Yıllık Net / Aylık Ort. Net + gider kalemleri detay grid + "Düzenle" butonu.
  - Henüz gider yoksa CTA strip "Net kâr için gider kalemlerini ekle".
  - Aylık bar tooltip'ine `Aylık gider` ve `Net` eklendi.
- **Test**: Pytest **8/8 PASS** (`test_yoy_expenses_net_profit.py` 3 case + `test_yoy_parser_multi_column.py` 2 case + `test_iteration331_perf_kpi_dedup.py` 3 case).
- **Camden örneği doğrulandı**: 12 ay £198,037 gelir → 5 gider kalemi £180,200 → **Yıllık Net £17,837 (9% margin)** veya cari yıl forecast £437,298 → Net £257,098 (58.8% margin).

## 2026-05-21 — Fix: Camden çoklu-sütun Excel parser bug
- Çoklu sütun Excel (Date | ADR | Bookings | Room Rates) ay sütunu doğru, ama yanlış değer sütunu seçiliyordu (ADR yerine Revenue). Tie-breaker: aynı satır sayısında **toplam değer en yüksek** sütun seçildi.

## 2026-05-21 — Fix: Performance Report KPI'leri abartılı/duplicate sayım
- 90 gün horizon + (date, room_type) dedup + per-date averaging. 491→91 days, çok daha gerçekçi numbers.

## 2026-05-21 — YoY Historical-Revenue Upload (PDF/JPG/Excel/CSV)
- Tesseract OCR + pdfplumber + openpyxl ile $0 maliyet upload pipeline. Inline editable preview table. iter 330 ile doğrulandı.

## 2026-05-21 — Performance Report YoY Comparison strip
- annual_forecast.yoy_comparison (prev_year vs forecast) + per-month yoy_delta_pct.
- **Şikayet**: "Estimated Revenue Uplift +£95,554 / Days Optimized 491 (421 up / 70 down) — bu sacma rakamlar".
- **Kök neden**: `get_performance_report` her `rate_override` satırını ham toplam ediyordu. Robot her tarama için aynı (tarih, oda tipi) için yeni override yazıyor + her gün için N oda tipi → aynı uplift 4-5x sayılıyordu. Ayrıca 13 ay forward / 30 gün backward bütün geçmiş yazıma dahildi.
- **Düzeltme** (`/app/backend/routes/revenue_ext/market_robot.py:3312`):
  1. Sorgu **aktif horizon**'a bağlandı: `today ≤ date ≤ today+90d` (robotun gerçek aktif penceresi).
  2. `(date, room_type)` başına **en son** override seçildi (eski yazımlar yutuldu).
  3. Tarih başına oda tipi rate'leri **ortalama** alındı → multi-room-type properties artık N-kat sayılmıyor.
- **Etki**: aldgate-flats 491 gün → **91 gün**; £95,554 → gerçekçi seviye. Pytest 3/3 PASS (`tests/test_iteration331_perf_kpi_dedup.py`).

## 2026-05-21 — YoY Historical-Revenue Upload (PDF/JPG/Excel/CSV)
- **Goal**: Operatör Booking history yoksa bile geçen yılın ciro verisini yükleyebilsin → YoY karşılaştırma anında dolsun.
- **Cost**: $0 — Tesseract OCR (lokal) + pdfplumber + pandas/openpyxl. Hiçbir paid API yok.
- **Backend**:
  - `POST /api/revenue/market-robot/{pid}/yoy-upload/preview` (multipart) → parse → `{entries[], source_kind, detected_count}`.
  - `POST /api/revenue/market-robot/{pid}/yoy-upload/confirm` → kaydet (collection `property_yoy_history`).
  - `GET /api/revenue/market-robot/{pid}/yoy-history` · `DELETE /api/revenue/market-robot/{pid}/yoy-history?month_key=YYYY-MM`.
  - `get_performance_report` artık YoY hesaplamasında upload'ları bookings'in üzerine yazıyor.
  - Yeni modül: `utils/yoy_parser.py` (excel/csv/pdf/image dispatch + text-block parsing).
- **Frontend**:
  - Yeni `YoYUploadModal.js` — file dropzone, OCR sırasında loading, düzenlenebilir önizleme tablosu (yıl/ay/ciro), manuel satır ekleme, satır silme, kayıtlı verileri görüntüleme/temizleme.
  - `PerformanceReport.js` YoY tile (`yoy-upload-open-tile`, `yoy-upload-open-empty`) ve strip header'a (`yoy-upload-open-strip`) Upload butonları eklendi.
- **Test**: iter 330 — Backend 10/10, Frontend 100%, regression OK, action_item yok.
- **Dependency**: `tesseract-ocr`, `poppler-utils` (apt) + `pytesseract`, `pdfplumber`, `pdf2image` (pip).

## 2026-05-21 — Performance Report YoY Comparison strip
- Backend `/api/revenue/market-robot/{property_id}/performance` now returns:
  - `annual_forecast.yoy_comparison` with `prev_year_total_revenue`, `this_year_forecast_revenue`, `delta_revenue`, `delta_pct`, `months_with_history`, `horizon_months`.
  - Each `annual_forecast.monthly[]` item now includes `prev_year_revenue`, `prev_year_month_key`, `yoy_delta_pct`.
- Frontend `PerformanceReport.js`:
  - New `yoy-tile` KPI (4-col grid) showing YoY Δ% with TrendingUp/Down icon next to RevPAR & Avg Occupancy.
  - New `yoy-strip` below the bar chart showing prev-year total → this-year forecast → growth Δ.
  - Bar tooltips now include prev-year revenue & delta % when available.
- Verified via testing agent iter 329 — 5/5 backend tests passed, frontend regression OK.

### Fixed
- `_build_annual_revenue_forecast` default `horizon_months` reverted from 24 → 12 to match the rest of the UI/scrape stack (frontend grid-cols-12, yearly price scrape range(12)).
