from __future__ import annotations

from pathlib import Path
from typing import Dict

import pandas as pd


def _ordered_quarter(value: str) -> tuple[int, int]:
    # Supports values such as Q1, Q2...
    q = str(value).strip().upper().replace("Q", "")
    return (0, int(q)) if q.isdigit() else (1, 99)


def _save(df: pd.DataFrame, out_dir: Path, file_name: str) -> str:
    path = out_dir / file_name
    df.to_csv(path, index=False)
    return str(path)


def build_powerbi_tables(
    master_census: pd.DataFrame,
    master_claims: pd.DataFrame,
) -> Dict[str, pd.DataFrame]:

    claims = master_claims.copy()
    census = master_census.copy()

    claims["service_date"] = pd.to_datetime(claims["service_date"])
    claims["month_label"] = claims["service_date"].dt.strftime("%Y-%m")

    monthly = (
        claims.groupby("month_label", as_index=False)
        .agg(
            total_claims=("master_claim_id", "count"),
            total_paid_usd=("paid_amount_usd", "sum"),
        )
        .sort_values("month_label")
    )

    quarterly = (
        claims.groupby("quarter", as_index=False)
        .agg(
            total_claims=("master_claim_id", "count"),
            total_paid_usd=("paid_amount_usd", "sum"),
            avg_cost_per_claim=("paid_amount_usd", "mean"),
        )
        .sort_values("quarter", key=lambda s: s.map(_ordered_quarter))
    )

    benefit_split = claims.groupby("benefit_type", as_index=False).agg(
        total_claims=("master_claim_id", "count"),
        total_paid_usd=("paid_amount_usd", "sum"),
    )
    benefit_split["claims_share_pct"] = (
        benefit_split["total_claims"] / benefit_split["total_claims"].sum() * 100
    ).round(2)

    relationship_age = (
        census.groupby("relationship", as_index=False)
        .agg(avg_age=("age", "mean"), total_members=("master_member_id", "count"))
        .sort_values("relationship")
    )
    relationship_age["avg_age"] = relationship_age["avg_age"].round(1)

    age_group_analysis = claims.groupby("age_group", as_index=False).agg(
        total_claims=("master_claim_id", "count"),
        total_paid_usd=("paid_amount_usd", "sum"),
        avg_cost_usd=("paid_amount_usd", "mean"),
    )
    age_group_analysis["avg_cost_usd"] = age_group_analysis["avg_cost_usd"].round(2)

    pec_diagnosis = (
        claims[claims["illness_type"] == "PEC/Chronic"]
        .groupby(["icd10_code", "diagnosis_description"], as_index=False)
        .agg(total_claims=("master_claim_id", "count"), total_paid_usd=("paid_amount_usd", "sum"))
        .sort_values(["total_claims", "total_paid_usd"], ascending=[False, False])
        .head(10)
    )

    provider_summary = (
        claims.groupby("provider_name", as_index=False)
        .agg(total_claims=("master_claim_id", "count"), total_paid_usd=("paid_amount_usd", "sum"))
        .sort_values("total_paid_usd", ascending=False)
        .head(5)
    )
    provider_summary["paid_share_pct"] = (
        provider_summary["total_paid_usd"] / provider_summary["total_paid_usd"].sum() * 100
    ).round(2)
    provider_summary["avg_cost_per_claim"] = (
        provider_summary["total_paid_usd"] / provider_summary["total_claims"]
    ).round(2)

    members_by_uw = census.groupby("source_uw", as_index=False).agg(
        total_members=("master_member_id", "count"),
        total_premium_usd=("annual_premium_usd", "sum"),
    )

    uw_claims = claims.groupby(["source_uw", "country"], as_index=False).agg(
        total_claims=("master_claim_id", "count"),
        total_paid_usd=("paid_amount_usd", "sum"),
        cost_per_claim=("paid_amount_usd", "mean"),
        pec_claims=("pec_flag", "sum"),
        oncology_cases=("oncology_flag", "sum"),
        maternity_cases=("maternity_flag", "sum"),
    )
    uw_comparison = uw_claims.merge(members_by_uw, on="source_uw", how="left")
    uw_comparison["loss_ratio_pct"] = (
        uw_comparison["total_paid_usd"] / uw_comparison["total_premium_usd"] * 100
    ).round(2)
    uw_comparison["pec_ratio_pct"] = (
        uw_comparison["pec_claims"] / uw_comparison["total_claims"] * 100
    ).round(2)
    uw_comparison["cost_per_claim"] = uw_comparison["cost_per_claim"].round(2)

    benchmarks = pd.DataFrame(
        [
            {"metric": "loss_ratio_pct", "benchmark_value": 88.0},
            {"metric": "cost_per_claim_usd", "benchmark_value": 200.0},
            {"metric": "pec_ratio_pct", "benchmark_value": 65.0},
            {"metric": "provider_concentration_pct", "benchmark_value": 25.0},
        ]
    )

    return {
        "monthly_trend": monthly,
        "quarterly_summary": quarterly,
        "benefit_split": benefit_split,
        "relationship_age": relationship_age,
        "age_group_analysis": age_group_analysis,
        "pec_diagnosis_top10": pec_diagnosis,
        "provider_top5": provider_summary,
        "uw_comparison": uw_comparison,
        "benchmarks": benchmarks,
    }


def write_powerbi_tables(powerbi_tables: Dict[str, pd.DataFrame], out_dir: Path) -> Dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    return {
        "monthly_trend": _save(powerbi_tables["monthly_trend"], out_dir, "monthly_trend.csv"),
        "quarterly_summary": _save(powerbi_tables["quarterly_summary"], out_dir, "quarterly_summary.csv"),
        "benefit_split": _save(powerbi_tables["benefit_split"], out_dir, "benefit_split.csv"),
        "relationship_age": _save(powerbi_tables["relationship_age"], out_dir, "relationship_age.csv"),
        "age_group_analysis": _save(powerbi_tables["age_group_analysis"], out_dir, "age_group_analysis.csv"),
        "pec_diagnosis_top10": _save(powerbi_tables["pec_diagnosis_top10"], out_dir, "pec_diagnosis_top10.csv"),
        "provider_top5": _save(powerbi_tables["provider_top5"], out_dir, "provider_top5.csv"),
        "uw_comparison": _save(powerbi_tables["uw_comparison"], out_dir, "uw_comparison.csv"),
        "benchmarks": _save(powerbi_tables["benchmarks"], out_dir, "benchmarks.csv"),
    }


def prepare_powerbi_tables(
    master_census: pd.DataFrame,
    master_claims: pd.DataFrame,
    out_dir: Path,
) -> Dict[str, str]:
    tables = build_powerbi_tables(master_census, master_claims)
    return write_powerbi_tables(tables, out_dir)


def load_powerbi_tables(table_paths: Dict[str, str]) -> Dict[str, pd.DataFrame]:
    return {name: pd.read_csv(path) for name, path in table_paths.items()}
