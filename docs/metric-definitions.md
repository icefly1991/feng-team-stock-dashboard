# Metric Definitions

This document defines the stock metrics written into `dashboard.json` by `scripts/generate_dashboard.py`.

All metrics must be calculated independently for each adjustment mode:

- `qfq`: use only the `qfq` price series and derived values.
- `none`: use only the non-adjusted price series and derived values.

Do not mix rows, reference values, or rolling windows across adjustment modes.

## Today Return

- Display name: Today Return
- JSON field name: `today_return_pct`
- Financial definition: The percentage change from the previous trading day's close to the latest close.
- Formula: `(latest close / previous trading day's close - 1) * 100`
- Required input columns: `trade_date`, `close`, `pct_chg` if available
- Adjustment behavior: Calculate separately for `qfq` and `none` using that adjustment's own latest row and previous trading row.
- Edge cases:
  - If Tushare `pct_chg` is present and reliable for the latest row, it may be used directly.
  - Fallback: if `pct_chg` is missing, compute from the latest close and previous trading day's close.
  - If neither `pct_chg` nor a previous trading row is available, the metric cannot be computed.
  - Round to 2 decimals.

## Distance to MA250

- Display name: Distance to MA250
- JSON field name: `distance_ma250_pct`
- Financial definition: The percentage distance between the latest close and the 250-trading-day moving average.
- Formula: `(latest close / MA250 - 1) * 100`
- Required input columns: `trade_date`, `close`
- Adjustment behavior: Calculate separately for `qfq` and `none` using that adjustment's own trailing 250 trading rows.
- Edge cases:
  - `MA250` is the arithmetic average of `close` over the latest 250 trading rows.
  - If fewer than 250 trading rows are available, the metric cannot be computed.
  - If `MA250` is zero, the metric cannot be computed.
  - Round to 2 decimals.

## YTD Return

- Display name: YTD Return
- JSON field name: `ytd_return_pct`
- Financial definition: The percentage return from the first available trading close in the current calendar year to the latest close.
- Formula: `(latest close / first close of the current calendar year - 1) * 100`
- Required input columns: `trade_date`, `close`
- Adjustment behavior: Calculate separately for `qfq` and `none` using that adjustment's own current-year trading rows.
- Edge cases:
  - Use the first available trading day in the current year, not January 1 unless it is a trading day.
  - If there are no trading rows in the current calendar year, the metric cannot be computed.
  - If the year-start close is zero, the metric cannot be computed.
  - Round to 2 decimals.

## Distance to 52 Week High

- Display name: Distance to 52 Week High
- JSON field name: `distance_52w_high_pct`
- Financial definition: The percentage distance from the latest close to the highest intraday high reached during the latest 252 trading rows.
- Formula: `(latest close / max(high over latest 252 trading rows) - 1) * 100`
- Required input columns: `trade_date`, `close`, `high`
- Adjustment behavior: Calculate separately for `qfq` and `none` using that adjustment's own latest 252 trading rows.
- Edge cases:
  - Use the `high` column, not `close`.
  - Use the latest 252 trading rows, not full history.
  - This value should usually be `<= 0`.
  - If fewer than 252 trading rows are available, the metric cannot be computed.
  - If the 52-week high is zero, the metric cannot be computed.
  - Round to 2 decimals.

## Distance to 52 Week Low

- Display name: Distance to 52 Week Low
- JSON field name: `distance_52w_low_pct`
- Financial definition: The percentage distance from the latest close to the lowest intraday low reached during the latest 252 trading rows.
- Formula: `(latest close / min(low over latest 252 trading rows) - 1) * 100`
- Required input columns: `trade_date`, `close`, `low`
- Adjustment behavior: Calculate separately for `qfq` and `none` using that adjustment's own latest 252 trading rows.
- Edge cases:
  - Use the `low` column, not `close`.
  - Use the latest 252 trading rows, not full history.
  - This value should usually be `>= 0`.
  - If fewer than 252 trading rows are available, the metric cannot be computed.
  - If the 52-week low is zero, the metric cannot be computed.
  - Round to 2 decimals.

## Position Within 52 Week Range

- Display name: Position Within 52 Week Range
- JSON field name: `position_52w_pct`
- Financial definition: The latest close's linear price position between the lowest intraday low and highest intraday high over the latest 252 trading rows.
- Formula: `(latest close - 52-week low) / (52-week high - 52-week low) * 100`
- Required input columns: `trade_date`, `close`, `high`, `low`
- Adjustment behavior: Calculate separately for `qfq` and `none` using that adjustment's own latest 252 trading rows.
- Edge cases:
  - The 52-week high is `max(high)` and the 52-week low is `min(low)` over the same latest 252 rows.
  - `0%` represents the low end and `100%` represents the high end of the price range; this is not elapsed-time progress or historical path progress.
  - If fewer than 252 trading rows are available, the metric cannot be computed.
  - If the 52-week high equals the 52-week low, the metric cannot be computed.
  - Round to 2 decimals.
