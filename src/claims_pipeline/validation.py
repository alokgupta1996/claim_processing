from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import pandas as pd


def _check(name: str, passed: bool, details: str) -> Dict[str, object]:
    return {"name": name, "passed": bool(passed), "details": details}


def validate_transformed_data(
    master_census: pd.DataFrame, master_claims: pd.DataFrame
) -> Dict[str, object]:
    checks: List[Dict[str, object]] = []

    checks.append(
        _check(
            "row_count_master_census",
            len(master_census) > 0,
            f"rows={len(master_census)}",
        )
    )
    checks.append(
        _check(
            "row_count_master_claims",
            len(master_claims) > 0,
            f"rows={len(master_claims)}",
        )
    )
    checks.append(
        _check(
            "unique_master_member_id",
            master_census["master_member_id"].is_unique,
            f"duplicates={master_census['master_member_id'].duplicated().sum()}",
        )
    )
    checks.append(
        _check(
            "unique_master_claim_id",
            master_claims["master_claim_id"].is_unique,
            f"duplicates={master_claims['master_claim_id'].duplicated().sum()}",
        )
    )

    missing_member_fk = master_claims["master_member_id"].isna().sum()
    unmatched_member_fk = (
        ~master_claims["master_member_id"].isin(master_census["master_member_id"])
    ).sum()
    checks.append(
        _check(
            "claims_member_fk_integrity",
            missing_member_fk == 0 and unmatched_member_fk == 0,
            f"missing={missing_member_fk}, unmatched={unmatched_member_fk}",
        )
    )

    date_cols = ["date_of_birth"]
    for col in date_cols:
        parsed = pd.to_datetime(master_census[col], errors="coerce")
        checks.append(
            _check(
                f"valid_date_{col}",
                parsed.notna().all(),
                f"invalid={(~parsed.notna()).sum()}",
            )
        )

    claim_date_cols = ["claim_date", "service_date"]
    for col in claim_date_cols:
        parsed = pd.to_datetime(master_claims[col], errors="coerce")
        checks.append(
            _check(
                f"valid_date_{col}",
                parsed.notna().all(),
                f"invalid={(~parsed.notna()).sum()}",
            )
        )

    numeric_non_negative_columns = [
        ("annual_premium_usd", master_census),
        ("billed_amount_usd", master_claims),
        ("paid_amount_usd", master_claims),
        ("copay_usd", master_claims),
    ]
    for column, frame in numeric_non_negative_columns:
        as_num = pd.to_numeric(frame[column], errors="coerce")
        checks.append(
            _check(
                f"non_negative_{column}",
                as_num.notna().all() and (as_num >= 0).all(),
                f"invalid={(~as_num.notna()).sum()}, negatives={(as_num < 0).sum()}",
            )
        )

    allowed_quarters = {"Q1", "Q2", "Q3", "Q4"}
    checks.append(
        _check(
            "quarter_domain",
            master_claims["quarter"].isin(allowed_quarters).all(),
            f"invalid={(~master_claims['quarter'].isin(allowed_quarters)).sum()}",
        )
    )

    passed = all(check["passed"] for check in checks)
    return {
        "passed": passed,
        "summary": {
            "master_census_rows": int(len(master_census)),
            "master_claims_rows": int(len(master_claims)),
            "total_checks": len(checks),
            "passed_checks": sum(int(c["passed"]) for c in checks),
        },
        "checks": checks,
    }


def write_validation_report(report: Dict[str, object], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

