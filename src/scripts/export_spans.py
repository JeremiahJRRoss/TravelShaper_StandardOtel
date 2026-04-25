"""Export Phoenix spans to CSV for the Step 5 deliverable.

Usage:
    python -m scripts.export_spans

Writes spans_export.csv to the project root (src/).
Run this AFTER generating traces with ./run_traces.sh.
"""

import sys
from pathlib import Path

import phoenix as px

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "spans_export.csv"


def export_spans(project_name: str = "travelshaper") -> None:
    """Fetch spans from Phoenix and write to CSV."""
    client = px.Client()

    try:
        spans_df = client.get_spans_dataframe(project_name=project_name)
    except Exception as exc:
        print(f"Could not connect to Phoenix: {exc}")
        print("Make sure Phoenix is running at http://localhost:6006")
        sys.exit(1)

    if spans_df is None or spans_df.empty:
        print("No spans found. Run ./run_traces.sh first to generate traces.")
        sys.exit(0)  # Not an error state — just no data yet

    spans_df.to_csv(OUTPUT_PATH, index=False)

    root_spans = spans_df[spans_df["parent_id"].isna()]

    llm_count = 0
    tool_count = 0
    if "span_kind" in spans_df.columns:
        kind_upper = spans_df["span_kind"].astype(str).str.upper()
        llm_count = int((kind_upper == "LLM").sum())
        tool_count = int((kind_upper == "TOOL").sum())

    print(f"Exported {len(spans_df)} total spans to {OUTPUT_PATH}")
    print(f"  Root (request) spans : {len(root_spans)}")
    print(f"  LLM spans            : {llm_count}")
    print(f"  Tool spans           : {tool_count}")


if __name__ == "__main__":
    export_spans()
