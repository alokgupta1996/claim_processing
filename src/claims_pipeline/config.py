from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


@dataclass(frozen=True)
class UnderwriterSpec:
    source_uw: str
    country: str
    file_name: str
    members_sheet: str
    claims_sheet: str
    members_skiprows: int
    claims_skiprows: int
    expected_member_rows: int
    expected_claim_rows: int
    expected_member_columns: List[str]
    expected_claim_columns: List[str]


def _default_specs() -> Dict[str, UnderwriterSpec]:
    return {
        "UW1": UnderwriterSpec(
            source_uw="UW1",
            country="Oman",
            file_name="UW1_OmanInsurance_RawData.xlsx",
            members_sheet="Members_List",
            claims_sheet="Claims_Register",
            members_skiprows=1,
            claims_skiprows=1,
            expected_member_rows=10,
            expected_claim_rows=12,
            expected_member_columns=[
                "Card No",
                "Cert No",
                "Date of Birth",
                "Member Name",
                "Sex",
                "Relation",
                "Nationality",
                "Class",
                "Network Tier",
                "Eff Date",
                "Exp Date",
                "Age",
                "Plan",
                "Annual Prem (Fils)",
            ],
            expected_claim_columns=[
                "Claim Ref",
                "Card No",
                "Member Name",
                "Service Date",
                "ICD Code",
                "Diagnosis",
                "Claim Category",
                "Service Type",
                "Provider Name",
                "Billed (Fils)",
                "Deductible (Fils)",
                "Approved (Fils)",
                "Paid (Fils)",
                "Status",
                "PA Ref",
                "Episode",
                "Quarter",
            ],
        ),
        "UW2": UnderwriterSpec(
            source_uw="UW2",
            country="Saudi Arabia",
            file_name="UW2_NationalLife_RawData.xlsx",
            members_sheet="POLICY_MEMBERS",
            claims_sheet="CLAIM_TRANSACTIONS",
            members_skiprows=0,
            claims_skiprows=0,
            expected_member_rows=10,
            expected_claim_rows=12,
            expected_member_columns=[
                "MEMBER_ID",
                "POLICY_REF",
                "EMP_NO",
                "FIRST_NAME",
                "LAST_NAME",
                "GENDER_CD",
                "REL_CODE",
                "DOB_YYYYMMDD",
                "AGE_YRS",
                "CTRY_CODE",
                "GRADE",
                "COVER_TYPE",
                "NETWORK",
                "EFF_DT",
                "TERM_DT",
                "ANNUAL_PREM_USD",
            ],
            expected_claim_columns=[
                "TRANS_ID",
                "MEMBER_ID",
                "CLAIM_DT",
                "SVC_DT",
                "DIAGNOSIS_CD",
                "DIAGNOSIS_TEXT",
                "ILLNESS_CATG",
                "BENEFIT_CD",
                "PROV_NAME",
                "BILLED_USD",
                "APPROVED_USD",
                "PAID_USD",
                "COPAY_USD",
                "CLAIM_STATUS",
                "PREAUTH_NO",
                "MONTH_NO",
                "YEAR",
            ],
        ),
        "UW3": UnderwriterSpec(
            source_uw="UW3",
            country="Qatar",
            file_name="UW3_QatarGeneral_RawData.xlsx",
            members_sheet="Insured_Members",
            claims_sheet="Claims_Detail",
            members_skiprows=4,
            claims_skiprows=4,
            expected_member_rows=12,
            expected_claim_rows=12,
            expected_member_columns=[
                "Seq",
                "Certificate No",
                "Sponsor ID",
                "Employee Full Name (EN / AR)",
                "Gender",
                "Relationship",
                "DOB (Excel Serial)",
                "Age",
                "Nationality",
                "Benefit Category",
                "Sub-Network",
                "Annual Premium (QAR)",
                "Co-pay %",
            ],
            expected_claim_columns=[
                "Claim ID",
                "Cert No",
                "Member Name",
                "Submission Date",
                "Date of Service",
                "ICD-10 Code",
                "Disease Description",
                "Disease Category",
                "Service Category",
                "Sub-Type",
                "Provider Name",
                "City",
                "Gross Billed (QAR)",
                "Discount (QAR)",
                "Net Billed (QAR)",
                "Insurer Share (QAR)",
                "Member Copay (QAR)",
                "Deductible (QAR)",
                "Settlement Status",
            ],
        ),
    }


def _spec_from_dict(payload: dict) -> UnderwriterSpec:
    required = [
        "source_uw",
        "country",
        "file_name",
        "members_sheet",
        "claims_sheet",
        "members_skiprows",
        "claims_skiprows",
        "expected_member_rows",
        "expected_claim_rows",
        "expected_member_columns",
        "expected_claim_columns",
    ]
    missing = [k for k in required if k not in payload]
    if missing:
        raise ValueError(f"Missing required keys in template spec: {missing}")

    return UnderwriterSpec(
        source_uw=str(payload["source_uw"]),
        country=str(payload["country"]),
        file_name=str(payload["file_name"]),
        members_sheet=str(payload["members_sheet"]),
        claims_sheet=str(payload["claims_sheet"]),
        members_skiprows=int(payload["members_skiprows"]),
        claims_skiprows=int(payload["claims_skiprows"]),
        expected_member_rows=int(payload["expected_member_rows"]),
        expected_claim_rows=int(payload["expected_claim_rows"]),
        expected_member_columns=[str(x) for x in payload["expected_member_columns"]],
        expected_claim_columns=[str(x) for x in payload["expected_claim_columns"]],
    )


def _load_specs_from_templates_dir(templates_dir: Path) -> Dict[str, UnderwriterSpec]:
    if not templates_dir.exists():
        return {}
    specs: Dict[str, UnderwriterSpec] = {}
    for path in sorted(templates_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        spec = _spec_from_dict(payload)
        specs[spec.source_uw] = spec
    return specs


def get_underwriter_specs(base_dir: Path | None = None) -> Dict[str, UnderwriterSpec]:
    base = base_dir or Path.cwd()
    templates_dir = base / "configs" / "templates"
    loaded = _load_specs_from_templates_dir(templates_dir)
    if loaded:
        return loaded
    return _default_specs()
