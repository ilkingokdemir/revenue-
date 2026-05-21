# Changelog — Hotel PMS & Revenue Management

## 2026-05-21

### Added — Performance Report YoY Comparison strip
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
