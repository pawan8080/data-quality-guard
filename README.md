# data-quality-guard 🛡️

A lightweight CLI that profiles a dataset and catches the **silent killers of BI dashboards** — nulls, duplicates, outliers, and stale data — before they break trust in your reports.

> Most BI failures aren't bad visuals. They're silent data failures. This guard makes them loud.

## The problem

Dashboards rarely break loudly. A null sneaks into a revenue column, a duplicate row inflates a KPI, an outlier skews an average, a pipeline goes stale — and nobody notices until a stakeholder asks why the numbers look wrong. By then, trust is already damaged.

## What it does

Point it at a CSV or Parquet file and get a Markdown quality report with:

- **Health score (0–100)** + plain-English verdict
- **Null analysis** per column (count + %)
- **Duplicate row detection**
- **Outlier detection** on numeric columns (IQR rule, with examples)
- **Freshness check** — days since the newest timestamp (auto-detects date columns, or pass `--date-col`)

## Quickstart

```bash
pip install -r requirements.txt
python guard.py sample_data.csv --out report.md
```

With an explicit date column:

```bash
python guard.py sales.parquet --date-col order_date --out report.md
```

## Example output

Running on the included `sample_data.csv` (12 rows with planted issues):

```
report written to report.md — score 71/100
```

`report.md` contains:

```markdown
## Verdict: 71/100 — NEEDS ATTENTION — fix flagged issues before trusting dashboards
...
## Nulls
| column      | nulls | null % |
| amount      | 1     | 8.33%  |
| customer_id | 1     | 8.33%  |
## Duplicates
**1** exact-duplicate rows (8.33% of data).
## Outliers (IQR rule, numeric columns)
- **amount**: 1 outliers (8.33%) — e.g. 99999.99
## Freshness
✅ fresh — `order_date` freshest value: **2026-09-24** (1 days ago).
```

## CI idea

Run this as a gate before your BI refresh — fail the pipeline when the score drops below your bar:

```bash
python guard.py daily_export.csv --out dq_report.md
# parse the score, e.g.: grep -oP 'score \K\d+' ... or check exit artifacts
```

## Project structure

| File | Purpose |
|---|---|
| `guard.py` | The CLI — load, profile, report |
| `sample_data.csv` | Demo dataset with intentional issues |
| `requirements.txt` | `pandas` only — stays light |

## Roadmap ideas

- [ ] JSON output mode for programmatic CI gates
- [ ] Schema-drift detection vs. a baseline
- [ ] LLM-generated plain-English summary of findings

---

Built by [Pawan Patel](https://github.com/pawan8080) — Day 1 of a daily BI/AI/ML portfolio series.
