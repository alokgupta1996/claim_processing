from __future__ import annotations

import pandas as pd

from claims_pipeline.transform import transform_sources


def test_transform_sources_supports_uwx_canonical_path() -> None:
    members = pd.DataFrame(
        [
            {
                "Policy Ref": "FC-OM-2024-001",
                "Member UID": "M1001",
                "Dependent UID": "D000",
                "Full Name": "Ahmed Rashid",
                "Sex": "M",
                "Relation Type": "EMP",
                "DOB": "1985-02-12",
                "Age Years": 39,
                "Nationality ISO": "OM",
                "Plan Level": "A",
                "Network Plan": "GOLD_PLUS",
                "Annual Premium Local": 980.0,
                "Currency": "OMR",
                "Join Date": "2024-01-01",
                "Expiry Date": "2024-12-31",
            }
        ]
    )
    claims = pd.DataFrame(
        [
            {
                "Txn ID": "TXN-90001",
                "Member UID": "M1001",
                "Service Dt": "2024-01-05",
                "Submission Dt": "2024-01-07",
                "Diagnosis Code": "E11.9",
                "Diagnosis Narrative": "Type 2 diabetes follow-up",
                "Chronicity": "PEC_CHRONIC",
                "Service Bucket": "OP",
                "Provider Group": "NMC Specialty",
                "Provider City": "Muscat",
                "Gross Amt": 85.0,
                "Insurer Paid": 70.0,
                "Member Copay": 15.0,
                "Currency": "OMR",
                "PreAuth Ref": "PA-001",
                "Case Ref": "EPI-5001",
                "Country": "Oman",
                "Status": "Paid",
            }
        ]
    )
    sources = {"UWX": {"members": members, "claims": claims}}

    master_census, master_claims = transform_sources(sources)

    assert len(master_census) == 1
    assert len(master_claims) == 1
    assert master_census.loc[0, "source_uw"] == "UWX"
    assert master_claims.loc[0, "source_uw"] == "UWX"
    assert float(master_census.loc[0, "annual_premium_usd"]) == 2538.2
    assert master_claims.loc[0, "illness_type"] == "PEC/Chronic"
