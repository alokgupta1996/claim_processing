from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict

import pandas as pd


def build_kpi_summary(master_claims: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        master_claims.groupby(["source_uw", "quarter"], as_index=False)
        .agg(
            total_claims=("master_claim_id", "count"),
            total_paid_usd=("paid_amount_usd", "sum"),
            avg_cost_per_claim=("paid_amount_usd", "mean"),
            pec_claims=("pec_flag", "sum"),
            oncology_claims=("oncology_flag", "sum"),
            maternity_claims=("maternity_flag", "sum"),
            mental_health_claims=("mental_health_flag", "sum"),
        )
        .sort_values(["source_uw", "quarter"])
    )
    grouped["pec_ratio"] = (grouped["pec_claims"] / grouped["total_claims"]).round(4)
    grouped["total_paid_usd"] = grouped["total_paid_usd"].round(2)
    grouped["avg_cost_per_claim"] = grouped["avg_cost_per_claim"].round(2)
    return grouped


def write_sqlite_database(
    master_census: pd.DataFrame,
    master_claims: pd.DataFrame,
    db_path: Path,
) -> Dict[str, int]:
    db_path.parent.mkdir(parents=True, exist_ok=True)

    kpi_summary = build_kpi_summary(master_claims)
    with sqlite3.connect(db_path) as conn:
        master_census.to_sql("members", conn, if_exists="replace", index=False)
        master_claims.to_sql("claims", conn, if_exists="replace", index=False)
        kpi_summary.to_sql("kpi_summary", conn, if_exists="replace", index=False)

    return {
        "members": int(len(master_census)),
        "claims": int(len(master_claims)),
        "kpi_summary": int(len(kpi_summary)),
    }

