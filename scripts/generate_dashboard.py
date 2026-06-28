from __future__ import annotations

from data_pipeline.config import build_runtime_config
from data_pipeline.exporter import export_dashboard
from data_pipeline.summary import build_dashboard_payload
from data_pipeline.tushare_client import TusharePipelineClient


def main() -> None:
    config = build_runtime_config()
    client = TusharePipelineClient(config)
    rows_by_adjustment, errors = client.build_adjustment_rows()
    payload = build_dashboard_payload(rows_by_adjustment, errors, updated_at=config.updated_at)
    export_dashboard(config.output_path, payload)

    print(f"Wrote {config.output_path}")
    if errors:
        print("Failed symbols:")
        for item in errors:
            print(f"- {item['code']}: {item['error']}")


if __name__ == "__main__":
    main()
