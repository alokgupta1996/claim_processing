from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List

import pandas as pd


MASTER_CENSUS_COLUMNS: List[str] = [
    "master_member_id",
    "source_uw",
    "policy_number",
    "country",
    "insurer_name",
    "member_name",
    "gender",
    "relationship",
    "date_of_birth",
    "age",
    "age_group",
    "nationality_code",
    "benefit_class",
    "network_tier",
    "annual_premium_usd",
    "copay_pct",
    "deductible_usd",
    "member_status",
]

MASTER_CLAIMS_COLUMNS: List[str] = [
    "master_claim_id",
    "source_uw",
    "policy_number",
    "country",
    "master_member_id",
    "member_name",
    "gender",
    "relationship",
    "age",
    "age_group",
    "benefit_class",
    "network_tier",
    "claim_id",
    "claim_date",
    "service_date",
    "month",
    "quarter",
    "year",
    "icd10_code",
    "diagnosis_description",
    "illness_type",
    "pec_flag",
    "oncology_flag",
    "maternity_flag",
    "mental_health_flag",
    "benefit_type",
    "provider_name",
    "provider_city",
    "billed_amount_usd",
    "paid_amount_usd",
    "copay_usd",
    "episode_id",
]


def _clean_text(value: object) -> str:
    return " ".join(str(value).strip().split())


def _title_case(value: object) -> str:
    return _clean_text(value).title()


def _to_age_group(age: object) -> str:
    age_int = int(age)
    if age_int <= 10:
        return "0-10"
    lower = ((age_int - 1) // 10) * 10 + 1
    upper = lower + 9
    return f"{lower}-{upper}"


def _parse_ddmmyyyy(value: object) -> str:
    return pd.to_datetime(value, dayfirst=True).date().isoformat()


def _parse_yyyymmdd(value: object) -> str:
    return pd.to_datetime(str(int(value)), format="%Y%m%d").date().isoformat()


def _parse_excel_serial(value: object) -> str:
    serial = int(value)
    return (datetime(1899, 12, 30) + timedelta(days=serial)).date().isoformat()


def _derive_quarter(date_iso: str) -> str:
    month = pd.to_datetime(date_iso).month
    return f"Q{((month - 1) // 3) + 1}"


def _normalize_icd10(value: object) -> str:
    code = _clean_text(value).upper()
    if code == "E1165":
        return "E11.65"
    return code


def _normalize_illness_uw1(value: object) -> str:
    mapping = {
        "CHRONIC": "PEC/Chronic",
        "ACUTE": "Acute",
        "MATERNITY": "Maternity",
        "ONCOLOGY": "Oncology",
    }
    key = _clean_text(value).upper()
    return mapping.get(key, "Other")


def _normalize_illness_uw2(value: object) -> str:
    mapping = {
        "PEC_CHRONIC": "PEC/Chronic",
        "ACUTE": "Acute",
        "MENTAL": "Mental Health",
        "ONCOLOGY": "Oncology",
        "MATERNITY": "Maternity",
    }
    key = _clean_text(value).upper()
    return mapping.get(key, "Other")


def _normalize_illness_uw3(value: object) -> str:
    mapping = {
        "PEC CHRONIC": "PEC/Chronic",
        "CHRONIC": "PEC/Chronic",
        "ACUTE": "Acute",
        "MENTAL HEALTH": "Mental Health",
        "ONCOLOGY": "Oncology",
        "MATERNITY": "Maternity",
    }
    key = _clean_text(value).upper()
    return mapping.get(key, "Other")


def _normalize_benefit(base_value: object, emergency_hint: object | None = None) -> str:
    if emergency_hint is not None and _clean_text(emergency_hint).upper() == "EMERGENCY":
        return "Emergency"
    key = _clean_text(base_value).upper()
    mapping = {
        "OP": "Outpatient",
        "OUTPATIENT": "Outpatient",
        "IP": "Inpatient",
        "INPATIENT": "Inpatient",
        "EMERGENCY": "Emergency",
    }
    return mapping.get(key, "Other")


def _add_flags(claims_df: pd.DataFrame) -> pd.DataFrame:
    out = claims_df.copy()
    out["pec_flag"] = (out["illness_type"] == "PEC/Chronic").astype(int)
    out["oncology_flag"] = (out["illness_type"] == "Oncology").astype(int)
    out["maternity_flag"] = (out["illness_type"] == "Maternity").astype(int)
    out["mental_health_flag"] = (out["illness_type"] == "Mental Health").astype(int)
    return out


def _na_float_column(length: int) -> pd.Series:
    return pd.Series([pd.NA] * length, dtype="Float64")


def _transform_uw1_members(df: pd.DataFrame) -> pd.DataFrame:
    gender_map = {"M": "Male", "F": "Female"}
    relationship_map = {"EMP": "Employee", "SPO": "Spouse", "CHD": "Child"}
    network_map = {"GOLD": "Gold", "SILVER": "Silver", "BRONZE": "Bronze"}
    policy_number = "POL-OIC-2024-001"

    out = pd.DataFrame(
        {
            "master_member_id": "UW1_" + df["Card No"].astype(str).map(_clean_text),
            "source_uw": "UW1",
            "policy_number": policy_number,
            "country": "Oman",
            "insurer_name": "Oman Insurance",
            "member_name": df["Member Name"].map(_title_case),
            "gender": df["Sex"].map(lambda x: gender_map[_clean_text(x).upper()]),
            "relationship": df["Relation"].map(
                lambda x: relationship_map[_clean_text(x).upper()]
            ),
            "date_of_birth": df["Date of Birth"].map(_parse_ddmmyyyy),
            "age": df["Age"].astype(int),
            "age_group": df["Age"].map(_to_age_group),
            "nationality_code": df["Nationality"].map(_clean_text),
            "benefit_class": df["Class"].map(_clean_text),
            "network_tier": df["Network Tier"].map(
                lambda x: network_map[_clean_text(x).upper()]
            ),
            "annual_premium_usd": (
                pd.to_numeric(df["Annual Prem (Fils)"]) / 1000 * 2.59
            ).round(2),
            "copay_pct": _na_float_column(len(df)),
            "deductible_usd": _na_float_column(len(df)),
            "member_status": "Active",
            "_source_join_key": df["Card No"].map(_clean_text),
        }
    )
    return out


def _transform_uw2_members(df: pd.DataFrame) -> pd.DataFrame:
    gender_map = {"M": "Male", "F": "Female"}
    relationship_map = {"E": "Employee", "S": "Spouse", "C": "Child"}
    class_map = {"P1": "A", "P2": "B", "P3": "C"}
    network_map = {"ELITE": "Gold", "NETWORK_B": "Silver", "NETWORK_C": "Bronze"}

    out = pd.DataFrame(
        {
            "master_member_id": "UW2_" + df["MEMBER_ID"].astype(str).map(_clean_text),
            "source_uw": "UW2",
            "policy_number": df["POLICY_REF"].map(_clean_text),
            "country": "Saudi Arabia",
            "insurer_name": "National Life",
            "member_name": (
                df["FIRST_NAME"].map(_clean_text) + " " + df["LAST_NAME"].map(_clean_text)
            ).map(_title_case),
            "gender": df["GENDER_CD"].map(lambda x: gender_map[_clean_text(x).upper()]),
            "relationship": df["REL_CODE"].map(
                lambda x: relationship_map[_clean_text(x).upper()]
            ),
            "date_of_birth": df["DOB_YYYYMMDD"].map(_parse_yyyymmdd),
            "age": df["AGE_YRS"].astype(int),
            "age_group": df["AGE_YRS"].map(_to_age_group),
            "nationality_code": df["CTRY_CODE"].map(_clean_text),
            "benefit_class": df["GRADE"].map(lambda x: class_map[_clean_text(x).upper()]),
            "network_tier": df["NETWORK"].map(
                lambda x: network_map[_clean_text(x).upper()]
            ),
            "annual_premium_usd": pd.to_numeric(df["ANNUAL_PREM_USD"]).round(2),
            "copay_pct": _na_float_column(len(df)),
            "deductible_usd": _na_float_column(len(df)),
            "member_status": "Active",
            "_source_join_key": df["MEMBER_ID"].map(_clean_text),
        }
    )
    return out


def _transform_uw3_members(df: pd.DataFrame) -> pd.DataFrame:
    relationship_map = {"PRINCIPAL": "Employee", "SPOUSE": "Spouse", "CHILD": "Child"}
    class_map = {"PLATINUM": "A", "STANDARD": "B", "ECONOMY": "C"}
    network_map = {"NETWORK_1": "Gold", "NETWORK_2": "Silver", "NETWORK_3": "Bronze"}
    policy_number = "QGI-GRP-QAT-2024-001"

    english_name = (
        df["Employee Full Name (EN / AR)"]
        .astype(str)
        .map(lambda x: x.split("/")[0])
        .map(_title_case)
    )

    out = pd.DataFrame(
        {
            "master_member_id": "UW3_" + df["Certificate No"].astype(str).map(_clean_text),
            "source_uw": "UW3",
            "policy_number": policy_number,
            "country": "Qatar",
            "insurer_name": "Qatar General",
            "member_name": english_name,
            "gender": df["Gender"].map(_title_case),
            "relationship": df["Relationship"].map(
                lambda x: relationship_map[_clean_text(x).upper()]
            ),
            "date_of_birth": df["DOB (Excel Serial)"].map(_parse_excel_serial),
            "age": df["Age"].astype(int),
            "age_group": df["Age"].map(_to_age_group),
            "nationality_code": df["Nationality"].map(_clean_text),
            "benefit_class": df["Benefit Category"].map(
                lambda x: class_map[_clean_text(x).upper()]
            ),
            "network_tier": df["Sub-Network"].map(
                lambda x: network_map[_clean_text(x).upper()]
            ),
            "annual_premium_usd": (pd.to_numeric(df["Annual Premium (QAR)"]) / 3.64).round(2),
            "copay_pct": (pd.to_numeric(df["Co-pay %"]).astype("Float64") / 100).round(4),
            "deductible_usd": _na_float_column(len(df)),
            "member_status": "Active",
            "_source_join_key": df["Certificate No"].map(_clean_text),
        }
    )
    return out


def _enrich_claims_with_member_keys(
    claims_df: pd.DataFrame, members_df: pd.DataFrame, source_claim_key: str
) -> pd.DataFrame:
    member_lookup = members_df.set_index("_source_join_key")
    out = claims_df.copy()
    join_key = out[source_claim_key].map(_clean_text)
    out["_member_join_key"] = join_key
    out["master_member_id"] = join_key.map(member_lookup["master_member_id"])
    out["member_name"] = join_key.map(member_lookup["member_name"])
    out["gender"] = join_key.map(member_lookup["gender"])
    out["relationship"] = join_key.map(member_lookup["relationship"])
    out["age"] = join_key.map(member_lookup["age"])
    out["age_group"] = join_key.map(member_lookup["age_group"])
    out["benefit_class"] = join_key.map(member_lookup["benefit_class"])
    out["network_tier"] = join_key.map(member_lookup["network_tier"])
    out["policy_number"] = join_key.map(member_lookup["policy_number"])
    out["country"] = join_key.map(member_lookup["country"])
    return out


def _transform_uw1_claims(df: pd.DataFrame, members_df: pd.DataFrame) -> pd.DataFrame:
    out = _enrich_claims_with_member_keys(df, members_df, "Card No")
    service_date = out["Service Date"].map(_parse_ddmmyyyy)

    claims = pd.DataFrame(
        {
            "master_claim_id": "UW1_" + out["Claim Ref"].map(_clean_text),
            "source_uw": "UW1",
            "policy_number": out["policy_number"],
            "country": out["country"],
            "master_member_id": out["master_member_id"],
            "member_name": out["member_name"],
            "gender": out["gender"],
            "relationship": out["relationship"],
            "age": out["age"],
            "age_group": out["age_group"],
            "benefit_class": out["benefit_class"],
            "network_tier": out["network_tier"],
            "claim_id": out["Claim Ref"].map(_clean_text),
            "claim_date": service_date,
            "service_date": service_date,
            "month": pd.to_datetime(service_date).dt.month.astype(int),
            "quarter": service_date.map(_derive_quarter),
            "year": pd.to_datetime(service_date).dt.year.astype(int),
            "icd10_code": out["ICD Code"].map(_normalize_icd10),
            "diagnosis_description": out["Diagnosis"].map(_title_case),
            "illness_type": out["Claim Category"].map(_normalize_illness_uw1),
            "benefit_type": out["Service Type"].map(_normalize_benefit),
            "provider_name": out["Provider Name"].map(_title_case),
            "provider_city": None,
            "billed_amount_usd": (pd.to_numeric(out["Billed (Fils)"]) / 1000 * 2.59).round(2),
            "paid_amount_usd": (pd.to_numeric(out["Paid (Fils)"]) / 1000 * 2.59).round(2),
            "copay_usd": (pd.to_numeric(out["Deductible (Fils)"]) / 1000 * 2.59).round(2),
            "episode_id": out["Episode"].map(_clean_text),
        }
    )
    return _add_flags(claims)


def _transform_uw2_claims(df: pd.DataFrame, members_df: pd.DataFrame) -> pd.DataFrame:
    out = _enrich_claims_with_member_keys(df, members_df, "MEMBER_ID")
    claim_date = out["CLAIM_DT"].map(_parse_yyyymmdd)
    service_date = out["SVC_DT"].map(_parse_yyyymmdd)

    claims = pd.DataFrame(
        {
            "master_claim_id": "UW2_" + out["TRANS_ID"].map(_clean_text),
            "source_uw": "UW2",
            "policy_number": out["policy_number"],
            "country": out["country"],
            "master_member_id": out["master_member_id"],
            "member_name": out["member_name"],
            "gender": out["gender"],
            "relationship": out["relationship"],
            "age": out["age"],
            "age_group": out["age_group"],
            "benefit_class": out["benefit_class"],
            "network_tier": out["network_tier"],
            "claim_id": out["TRANS_ID"].map(_clean_text),
            "claim_date": claim_date,
            "service_date": service_date,
            "month": pd.to_datetime(service_date).dt.month.astype(int),
            "quarter": service_date.map(_derive_quarter),
            "year": pd.to_datetime(service_date).dt.year.astype(int),
            "icd10_code": out["DIAGNOSIS_CD"].map(_normalize_icd10),
            "diagnosis_description": out["DIAGNOSIS_TEXT"].map(_title_case),
            "illness_type": out["ILLNESS_CATG"].map(_normalize_illness_uw2),
            "benefit_type": out["BENEFIT_CD"].map(_normalize_benefit),
            "provider_name": out["PROV_NAME"].map(_title_case),
            "provider_city": None,
            "billed_amount_usd": pd.to_numeric(out["BILLED_USD"]).round(2),
            "paid_amount_usd": pd.to_numeric(out["PAID_USD"]).round(2),
            "copay_usd": pd.to_numeric(out["COPAY_USD"]).round(2),
            "episode_id": out["PREAUTH_NO"].map(
                lambda x: _clean_text(x) if pd.notna(x) else None
            ),
        }
    )
    return _add_flags(claims)


def _transform_uw3_claims(df: pd.DataFrame, members_df: pd.DataFrame) -> pd.DataFrame:
    out = _enrich_claims_with_member_keys(df, members_df, "Cert No")
    claim_date = out["Submission Date"].map(_parse_ddmmyyyy)
    service_date = out["Date of Service"].map(_parse_ddmmyyyy)

    claims = pd.DataFrame(
        {
            "master_claim_id": "UW3_" + out["Claim ID"].map(_clean_text),
            "source_uw": "UW3",
            "policy_number": out["policy_number"],
            "country": out["country"],
            "master_member_id": out["master_member_id"],
            "member_name": out["member_name"],
            "gender": out["gender"],
            "relationship": out["relationship"],
            "age": out["age"],
            "age_group": out["age_group"],
            "benefit_class": out["benefit_class"],
            "network_tier": out["network_tier"],
            "claim_id": out["Claim ID"].map(_clean_text),
            "claim_date": claim_date,
            "service_date": service_date,
            "month": pd.to_datetime(service_date).dt.month.astype(int),
            "quarter": service_date.map(_derive_quarter),
            "year": pd.to_datetime(service_date).dt.year.astype(int),
            "icd10_code": out["ICD-10 Code"].map(_normalize_icd10),
            "diagnosis_description": out["Disease Description"].map(_title_case),
            "illness_type": out["Disease Category"].map(_normalize_illness_uw3),
            "benefit_type": out.apply(
                lambda row: _normalize_benefit(
                    row["Service Category"], emergency_hint=row["Sub-Type"]
                ),
                axis=1,
            ),
            "provider_name": out["Provider Name"].map(_title_case),
            "provider_city": out["City"].map(_clean_text),
            "billed_amount_usd": (pd.to_numeric(out["Gross Billed (QAR)"]) / 3.64).round(2),
            "paid_amount_usd": (pd.to_numeric(out["Insurer Share (QAR)"]) / 3.64).round(2),
            "copay_usd": (pd.to_numeric(out["Member Copay (QAR)"]) / 3.64).round(2),
            "episode_id": out["Claim ID"].map(_clean_text),
        }
    )
    return _add_flags(claims)


def transform_sources(
    sources: Dict[str, Dict[str, pd.DataFrame]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    member_frames: list[pd.DataFrame] = []
    claims_frames: list[pd.DataFrame] = []
    transformed_members_by_uw: Dict[str, pd.DataFrame] = {}

    if "UW1" in sources:
        uw1_members = _transform_uw1_members(sources["UW1"]["members"])
        transformed_members_by_uw["UW1"] = uw1_members
        member_frames.append(uw1_members)
    if "UW2" in sources:
        uw2_members = _transform_uw2_members(sources["UW2"]["members"])
        transformed_members_by_uw["UW2"] = uw2_members
        member_frames.append(uw2_members)
    if "UW3" in sources:
        uw3_members = _transform_uw3_members(sources["UW3"]["members"])
        transformed_members_by_uw["UW3"] = uw3_members
        member_frames.append(uw3_members)

    if not member_frames:
        raise ValueError("No UW sources available for transformation.")

    if "UW1" in sources:
        claims_frames.append(
            _transform_uw1_claims(sources["UW1"]["claims"], transformed_members_by_uw["UW1"])
        )
    if "UW2" in sources:
        claims_frames.append(
            _transform_uw2_claims(sources["UW2"]["claims"], transformed_members_by_uw["UW2"])
        )
    if "UW3" in sources:
        claims_frames.append(
            _transform_uw3_claims(sources["UW3"]["claims"], transformed_members_by_uw["UW3"])
        )

    if not claims_frames:
        raise ValueError("No UW claim sources available for transformation.")

    master_census = pd.concat(member_frames, ignore_index=True)
    master_census = master_census[MASTER_CENSUS_COLUMNS + ["_source_join_key"]]

    master_claims = pd.concat(claims_frames, ignore_index=True)
    master_claims = master_claims[MASTER_CLAIMS_COLUMNS]

    master_census = master_census[MASTER_CENSUS_COLUMNS]
    return master_census, master_claims
