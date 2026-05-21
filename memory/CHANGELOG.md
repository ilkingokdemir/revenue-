# Changelog — Hotel PMS & Revenue Management

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
