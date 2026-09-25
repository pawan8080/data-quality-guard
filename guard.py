#!/usr/bin/env python3
"""data-quality-guard: a lightweight data-quality profiler for BI pipelines.

Profiles a CSV (or Parquet) file and reports the silent killers of dashboards:
nulls, duplicates, outliers, schema surprises, and stale data.

Usage:
    python guard.py sample.csv --out report.md
    python guard.py data.parquet --date-col order_date --out report.md
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def load_frame(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in (".parquet", ".pq"):
        return pd.read_parquet(path)
    raise ValueError(f"unsupported file type: {suffix} (use .csv or .parquet)")


def null_report(df: pd.DataFrame) -> pd.DataFrame:
    nulls = df.isna().sum()
    pct = (nulls / len(df) * 100).round(2)
    out = pd.DataFrame({"nulls": nulls, "null_pct": pct})
    return out[out["nulls"] > 0].sort_values("null_pct", ascending=False)


def duplicate_count(df: pd.DataFrame) -> int:
    return int(df.duplicated().sum())


def iqr_outliers(series: pd.Series) -> pd.Series:
    """Boolean mask of outliers via the IQR rule."""
    s = series.dropna()
    if s.empty:
        return pd.Series(False, index=series.index)
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    if iqr == 0:
        return pd.Series(False, index=series.index)
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    return (series < lower) | (series > upper)


def outlier_report(df: pd.DataFrame, max_examples: int = 5) -> dict:
    report: dict[str, dict] = {}
    for col in df.select_dtypes(include="number").columns:
        mask = iqr_outliers(df[col])
        n = int(mask.sum())
        if n:
            examples = df.loc[mask, col].head(max_examples).tolist()
            report[col] = {"count": n, "pct": round(n / len(df) * 100, 2), "examples": examples}
    return report


def stale_report(df: pd.DataFrame, date_col: str | None) -> dict | None:
    """Days since the freshest timestamp in a date column (auto-detected if not given)."""
    col = date_col
    if col is None:
        datetime_cols = df.select_dtypes(include=["datetime64"]).columns.tolist()
        if not datetime_cols:
            # try to coerce likely date columns
            for c in df.columns:
                if any(k in c.lower() for k in ("date", "time", "created", "updated")):
                    coerced = pd.to_datetime(df[c], errors="coerce")
                    if coerced.notna().sum() > len(df) * 0.5:
                        df[c] = coerced
                        datetime_cols.append(c)
                        break
        if not datetime_cols:
            return None
        col = datetime_cols[0]
    else:
        if col not in df.columns:
            return {"error": f"date column '{col}' not found"}
        df[col] = pd.to_datetime(df[col], errors="coerce")
    freshest = df[col].max()
    if pd.isna(freshest):
        return {"column": col, "error": "no parseable dates"}
    now = datetime.now(timezone.utc)
    if freshest.tzinfo is None:
        freshest = freshest.tz_localize("UTC")
    days = (now - freshest).days
    return {
        "column": col,
        "freshest": str(freshest.date()),
        "days_since_freshest": days,
        "stale": days > 1,
    }


def health_score(n_rows: int, null_pct_max: float, dupes: int, outlier_cols: int, stale: bool) -> int:
    score = 100
    score -= min(30, int(null_pct_max))            # nulls hurt most
    score -= min(20, int(dupes / max(n_rows, 1) * 100 * 2))
    score -= min(15, outlier_cols * 5)
    if stale:
        score -= 15
    return max(0, score)


def build_report(df: pd.DataFrame, source: str, date_col: str | None) -> tuple[str, int]:
    n_rows, n_cols = df.shape
    nulls = null_report(df)
    dupes = duplicate_count(df)
    outliers = outlier_report(df)
    stale = stale_report(df, date_col)

    null_pct_max = float(nulls["null_pct"].max()) if not nulls.empty else 0.0
    stale_flag = bool(stale and stale.get("stale"))
    score = health_score(n_rows, null_pct_max, dupes, len(outliers), stale_flag)

    verdict = (
        "HEALTHY — safe to build on" if score >= 85
        else "NEEDS ATTENTION — fix flagged issues before trusting dashboards" if score >= 60
        else "AT RISK — do not ship dashboards on this data without fixes"
    )

    lines = [
        f"# Data Quality Report: `{source}`",
        "",
        f"_Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} by data-quality-guard_",
        "",
        f"## Verdict: {score}/100 — {verdict}",
        "",
        "## Shape",
        "",
        f"- Rows: **{n_rows:,}** | Columns: **{n_cols}**",
        f"- Memory: ~{df.memory_usage(deep=True).sum() / 1024:.1f} KB",
        "",
        "## Schema",
        "",
        "| column | dtype |",
        "|---|---|",
    ]
    for col, dtype in df.dtypes.items():
        lines.append(f"| {col} | {dtype} |")

    lines += ["", "## Nulls", ""]
    if nulls.empty:
        lines.append("No nulls found. 🎉")
    else:
        lines += ["| column | nulls | null % |", "|---|---|---|"]
        for col, row in nulls.iterrows():
            lines.append(f"| {col} | {int(row['nulls'])} | {row['null_pct']}% |")

    lines += ["", "## Duplicates", ""]
    lines.append(
        f"**{dupes:,}** exact-duplicate rows ({dupes / n_rows * 100:.2f}% of data)."
        if dupes else "No exact-duplicate rows found. 🎉"
    )

    lines += ["", "## Outliers (IQR rule, numeric columns)", ""]
    if not outliers:
        lines.append("No outliers detected. 🎉")
    else:
        for col, info in outliers.items():
            ex = ", ".join(str(x) for x in info["examples"])
            lines.append(f"- **{col}**: {info['count']} outliers ({info['pct']}%) — e.g. {ex}")

    lines += ["", "## Freshness", ""]
    if stale is None:
        lines.append("No date column found — pass `--date-col` or add one to enable staleness checks.")
    elif "error" in stale:
        lines.append(f"⚠️ {stale['error']}")
    else:
        flag = "⚠️ STALE" if stale["stale"] else "✅ fresh"
        lines.append(
            f"{flag} — `{stale['column']}` freshest value: **{stale['freshest']}** "
            f"({stale['days_since_freshest']} days ago)."
        )

    lines += [
        "",
        "---",
        "_Tip: run this in CI before your BI refresh — fail the build when the score drops below your bar._",
        "",
    ]
    return "\n".join(lines), score


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Profile a dataset and flag data-quality issues.")
    parser.add_argument("input", type=Path, help="CSV or Parquet file to profile")
    parser.add_argument("--out", type=Path, default=Path("report.md"), help="output markdown report path")
    parser.add_argument("--date-col", default=None, help="date column for the staleness check")
    args = parser.parse_args(argv)

    if not args.input.exists():
        print(f"error: file not found: {args.input}", file=sys.stderr)
        return 1
    try:
        df = load_frame(args.input)
    except Exception as exc:  # noqa: BLE001 - surface any load failure cleanly
        print(f"error: could not load {args.input}: {exc}", file=sys.stderr)
        return 1
    if df.empty:
        print("error: dataset is empty", file=sys.stderr)
        return 1

    report, score = build_report(df, args.input.name, args.date_col)
    args.out.write_text(report, encoding="utf-8")
    print(f"report written to {args.out} — score {score}/100")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
