# Power BI DAX Measures Pack

Create these in Power BI Desktop after loading:
- `master_claims`
- `master_census`
- `uw_comparison`
- `benchmarks`

## Core KPI Measures

```DAX
Total Claims = COUNTROWS(master_claims)
```

```DAX
Total Paid USD = SUM(master_claims[paid_amount_usd])
```

```DAX
Total Premium USD = SUM(master_census[annual_premium_usd])
```

```DAX
Loss Ratio % = DIVIDE([Total Paid USD], [Total Premium USD]) * 100
```

```DAX
Cost Per Claim USD = DIVIDE([Total Paid USD], [Total Claims])
```

```DAX
PEC Claims = SUM(master_claims[pec_flag])
```

```DAX
PEC Ratio % = DIVIDE([PEC Claims], [Total Claims]) * 100
```

```DAX
Oncology Cases = SUM(master_claims[oncology_flag])
```

```DAX
Maternity Cases = SUM(master_claims[maternity_flag])
```

```DAX
Mental Health Cases = SUM(master_claims[mental_health_flag])
```

## Provider Measures

```DAX
Provider Paid USD = SUM(master_claims[paid_amount_usd])
```

```DAX
Provider Claims = COUNTROWS(master_claims)
```

```DAX
Provider Avg Cost = DIVIDE([Provider Paid USD], [Provider Claims])
```

```DAX
Provider Share % =
DIVIDE(
    [Provider Paid USD],
    CALCULATE([Total Paid USD], ALL(master_claims[provider_name]))
) * 100
```

## UW Comparison Measures

```DAX
UW Total Claims = SUM(uw_comparison[total_claims])
```

```DAX
UW Total Paid USD = SUM(uw_comparison[total_paid_usd])
```

```DAX
UW Loss Ratio % = AVERAGE(uw_comparison[loss_ratio_pct])
```

```DAX
UW Cost Per Claim = AVERAGE(uw_comparison[cost_per_claim])
```

```DAX
UW PEC Ratio % = AVERAGE(uw_comparison[pec_ratio_pct])
```

## Benchmark Measures

```DAX
Benchmark Loss Ratio % =
CALCULATE(
    MAX(benchmarks[benchmark_value]),
    benchmarks[metric] = "loss_ratio_pct"
)
```

```DAX
Benchmark Cost Per Claim USD =
CALCULATE(
    MAX(benchmarks[benchmark_value]),
    benchmarks[metric] = "cost_per_claim_usd"
)
```

```DAX
Benchmark PEC Ratio % =
CALCULATE(
    MAX(benchmarks[benchmark_value]),
    benchmarks[metric] = "pec_ratio_pct"
)
```

```DAX
Benchmark Provider Concentration % =
CALCULATE(
    MAX(benchmarks[benchmark_value]),
    benchmarks[metric] = "provider_concentration_pct"
)
```

## Formatting Tips

- Format all percentage measures as `%` with `1` decimal place.
- Format currency as `$#,0` or `$#,0.00`.
- Keep page headings in navy `#1F3864`.
- Use primary red `#9B1942` for key bars/lines.

