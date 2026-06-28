from __future__ import annotations

from data_pipeline.config import build_runtime_config
from data_pipeline.exporter import dashboard_exists, export_dashboard
from data_pipeline.summary import build_dashboard_payload
from data_pipeline.tushare_client import TusharePipelineClient


def main() -> None:
    config = build_runtime_config()
    client = TusharePipelineClient(config)
    latest_market_trade_date = client.get_latest_market_trade_date()
    result = client.build_adjustment_rows()
    valid_row_count = sum(len(rows) for rows in result.rows_by_adjustment.values())

    print(f"Latest trade date: {result.latest_trade_date or latest_market_trade_date or 'unavailable'}")
    print(f"Successful stocks: {result.successful_stocks}")
    print(f"Failed stocks: {result.failed_stocks}")

    if valid_row_count == 0:
        status = "Kept existing dashboard.json." if dashboard_exists(config.output_json_file) else "No dashboard.json written."
        print(status)
        print(f"Output file path: {config.output_json_file}")
        return

    payload = build_dashboard_payload(
        result.rows_by_adjustment,
        result.errors,
        watchlist_total=len(config.watchlist),
        updated_at=config.updated_at,
    )
    export_dashboard(config.output_json_file, payload)
    print(f"Output file path: {config.output_json_file}")


if __name__ == "__main__":
    main()
