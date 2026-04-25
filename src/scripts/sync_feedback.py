"""Batch-sync locally stored feedback to Phoenix annotations.

Usage:
    python -m scripts.sync_feedback

Reads feedback.jsonl, finds matching spans in Phoenix, logs User Feedback
annotations, and marks entries as synced. Safe to run repeatedly — already-
synced entries are skipped.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

FEEDBACK_FILE = Path(__file__).resolve().parent.parent / "feedback.jsonl"


def sync() -> None:
    """Read unsynced feedback entries and push to Phoenix."""
    if not FEEDBACK_FILE.exists():
        print("No feedback.jsonl found. Nothing to sync.")
        return

    # Read all entries
    entries = []
    with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    unsynced = [e for e in entries if not e.get("synced", False)]
    if not unsynced:
        print("All feedback entries already synced.")
        return

    print(f"Found {len(unsynced)} unsynced entries out of {len(entries)} total.")

    try:
        import phoenix as px
        from phoenix.trace import SpanEvaluations
        import pandas as pd
    except ImportError:
        print("Phoenix packages not installed. Cannot sync.")
        sys.exit(1)

    client = px.Client()
    try:
        spans_df = client.get_spans_dataframe()
    except Exception as exc:
        print(f"Could not connect to Phoenix: {exc}")
        sys.exit(1)

    if spans_df is None or spans_df.empty:
        print("No spans in Phoenix. Run queries first.")
        return

    synced_count = 0
    for entry in unsynced:
        run_id = entry.get("run_id", "")
        score = entry.get("score", 0)
        comment = entry.get("comment", "")

        # Try to find the span
        match = pd.DataFrame()
        if "context.span_id" in spans_df.columns:
            match = spans_df[spans_df["context.span_id"].astype(str) == run_id]
        if match.empty:
            idx_match = spans_df.index.astype(str) == run_id
            if idx_match.any():
                match = spans_df[idx_match]

        if match.empty:
            continue

        try:
            eval_df = pd.DataFrame(
                {
                    "label": ["positive" if score >= 1 else "negative"],
                    "score": [float(score)],
                    "explanation": [comment or ""],
                },
                index=match.index[:1],
            )
            client.log_evaluations(
                SpanEvaluations(eval_name="User Feedback", dataframe=eval_df)
            )
            entry["synced"] = True
            synced_count += 1
        except Exception as exc:
            print(f"  Failed to sync run_id={run_id}: {exc}")

    # Rewrite the file with updated sync status
    tmp_fd, tmp_path = tempfile.mkstemp(dir=FEEDBACK_FILE.parent, suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
        os.replace(tmp_path, FEEDBACK_FILE)
    except Exception:
        os.unlink(tmp_path)
        raise

    print(f"Synced {synced_count}/{len(unsynced)} entries to Phoenix.")


if __name__ == "__main__":
    sync()
