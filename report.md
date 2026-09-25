# Data Quality Report: `sample_data.csv`

_Generated 2026-09-25 03:11 UTC by data-quality-guard_

## Verdict: 71/100 — NEEDS ATTENTION — fix flagged issues before trusting dashboards

## Shape

- Rows: **12** | Columns: **5**
- Memory: ~1.6 KB

## Schema

| column | dtype |
|---|---|
| order_id | int64 |
| order_date | datetime64[ns] |
| region | object |
| amount | float64 |
| customer_id | object |

## Nulls

| column | nulls | null % |
|---|---|---|
| amount | 1 | 8.33% |
| customer_id | 1 | 8.33% |

## Duplicates

**1** exact-duplicate rows (8.33% of data).

## Outliers (IQR rule, numeric columns)

- **amount**: 1 outliers (8.33%) — e.g. 99999.99

## Freshness

✅ fresh — `order_date` freshest value: **2026-09-24** (1 days ago).

---
_Tip: run this in CI before your BI refresh — fail the build when the score drops below your bar._
