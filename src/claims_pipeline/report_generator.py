from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Dict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import FancyBboxPatch, Rectangle
from matplotlib.ticker import FuncFormatter
import pandas as pd
import seaborn as sns

from claims_pipeline.narrative import generate_report_narrative


BRAND_NAVY = "#1F3864"
BRAND_RED = "#9B1942"
BRAND_TEAL = "#2A9D8F"
BRAND_GOLD = "#D18F00"
TEXT_DARK = "#1E2A3B"
TEXT_MUTED = "#5B6778"
CARD_BG = "#F7F9FC"
CARD_BORDER = "#D6DEEA"


def _safe_top(series: pd.Series, idx: int = 0, default: str = "N/A") -> str:
    if series.empty:
        return default
    return str(series.iloc[idx])


def _to_number(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _fmt_int(value: object) -> str:
    return f"{int(round(_to_number(value))):,}"


def _fmt_currency(value: object) -> str:
    return f"${_to_number(value):,.0f}"


def _fmt_pct(value: object) -> str:
    return f"{_to_number(value):.1f}%"


def _compact_currency(value: float, _pos: int) -> str:
    abs_value = abs(value)
    if abs_value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if abs_value >= 1_000:
        return f"${value / 1_000:.0f}K"
    return f"${value:,.0f}"


def _wrap_lines(lines: list[str], width: int = 84) -> list[str]:
    wrapped: list[str] = []
    for raw in lines:
        text = str(raw).strip()
        if not text:
            continue
        wrapped_parts = textwrap.wrap(text, width=width)
        wrapped.extend(wrapped_parts or [text])
    return wrapped


def _build_context(master_census: pd.DataFrame, master_claims: pd.DataFrame) -> Dict[str, object]:
    total_claims = int(len(master_claims))
    total_paid = float(master_claims["paid_amount_usd"].sum())
    total_premium = float(master_census["annual_premium_usd"].sum())
    loss_ratio = (total_paid / total_premium * 100) if total_premium else 0.0

    provider = (
        master_claims.groupby("provider_name", as_index=False)
        .agg(total_paid_usd=("paid_amount_usd", "sum"))
        .sort_values("total_paid_usd", ascending=False)
    )
    top_provider = _safe_top(provider["provider_name"])
    top_provider_share = (
        float(provider["total_paid_usd"].iloc[0] / total_paid * 100) if (not provider.empty and total_paid) else 0.0
    )

    diagnosis = (
        master_claims[master_claims["illness_type"] == "PEC/Chronic"]
        .groupby("diagnosis_description", as_index=False)
        .agg(total_claims=("master_claim_id", "count"))
        .sort_values("total_claims", ascending=False)
    )
    top_diagnosis = _safe_top(diagnosis["diagnosis_description"])

    return {
        "total_claims": total_claims,
        "total_paid_usd": round(total_paid, 2),
        "total_premium_usd": round(total_premium, 2),
        "loss_ratio_pct": round(loss_ratio, 2),
        "top_provider_name": top_provider,
        "top_provider_share_pct": round(top_provider_share, 2),
        "top_diagnosis": top_diagnosis,
    }


def _add_page_chrome(fig: plt.Figure, title: str, subtitle: str, page_number: int, total_pages: int) -> None:
    fig.patch.set_facecolor("white")
    fig.add_artist(Rectangle((0.0, 0.92), 1.0, 0.08, transform=fig.transFigure, color=BRAND_NAVY, zorder=0))
    fig.add_artist(Rectangle((0.0, 0.92), 0.18, 0.08, transform=fig.transFigure, color=BRAND_RED, zorder=1))
    fig.add_artist(Rectangle((0.02, 0.055), 0.96, 0.0014, transform=fig.transFigure, color=CARD_BORDER, zorder=1))

    fig.text(0.03, 0.973, title, fontsize=12.2, color="white", weight="bold", va="center")
    fig.text(0.03, 0.943, subtitle, fontsize=9.8, color="#E5ECF4", va="center")
    fig.text(0.03, 0.03, "Confidential | Health Claims Analytics", fontsize=8.5, color=TEXT_MUTED)
    fig.text(0.97, 0.03, f"Page {page_number}/{total_pages}", fontsize=8.5, color=TEXT_MUTED, ha="right")


def _draw_kpi_card(fig: plt.Figure, bounds: list[float], label: str, value: str, accent: str) -> None:
    ax = fig.add_axes(bounds)
    ax.axis("off")
    card = FancyBboxPatch(
        (0, 0),
        1,
        1,
        boxstyle="round,pad=0.014,rounding_size=0.03",
        transform=ax.transAxes,
        facecolor=CARD_BG,
        edgecolor=CARD_BORDER,
        linewidth=1.2,
    )
    ax.add_patch(card)
    ax.add_patch(Rectangle((0, 0), 0.03, 1, transform=ax.transAxes, color=accent))
    ax.text(0.08, 0.68, label, fontsize=9.5, color=TEXT_MUTED, weight="semibold")
    ax.text(0.08, 0.30, value, fontsize=16, color=TEXT_DARK, weight="bold")


def _draw_text_card(
    fig: plt.Figure,
    bounds: list[float],
    title: str,
    lines: list[str],
    bullet: bool = True,
) -> None:
    ax = fig.add_axes(bounds)
    ax.axis("off")
    card = FancyBboxPatch(
        (0, 0),
        1,
        1,
        boxstyle="round,pad=0.014,rounding_size=0.03",
        transform=ax.transAxes,
        facecolor="white",
        edgecolor=CARD_BORDER,
        linewidth=1.0,
    )
    ax.add_patch(card)
    ax.text(0.04, 0.92, title, fontsize=11.5, color=BRAND_NAVY, weight="bold", va="top")

    cursor = 0.80
    for line in lines:
        wrapped = textwrap.wrap(str(line), width=92) or [str(line)]
        first = True
        for segment in wrapped:
            prefix = "- " if bullet and first else "  "
            ax.text(0.04, cursor, f"{prefix}{segment}", fontsize=9.8, color=TEXT_DARK, va="top")
            cursor -= 0.105
            first = False
            if cursor < 0.08:
                return


def _draw_panel_text(ax: plt.Axes, title: str, lines: list[str], bullet: bool = True) -> None:
    ax.axis("off")
    card = FancyBboxPatch(
        (0, 0),
        1,
        1,
        boxstyle="round,pad=0.014,rounding_size=0.03",
        transform=ax.transAxes,
        facecolor="white",
        edgecolor=CARD_BORDER,
        linewidth=1.0,
    )
    ax.add_patch(card)
    ax.text(0.05, 0.92, title, fontsize=11, color=BRAND_NAVY, weight="bold", va="top")

    cursor = 0.80
    for line in lines:
        wrapped = textwrap.wrap(str(line), width=54) or [str(line)]
        first = True
        for segment in wrapped:
            prefix = "- " if bullet and first else "  "
            ax.text(0.05, cursor, f"{prefix}{segment}", fontsize=9.5, color=TEXT_DARK, va="top")
            cursor -= 0.10
            first = False
            if cursor < 0.08:
                return


def _maybe_format_numeric(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().sum() >= max(1, int(0.6 * len(series))):
        return numeric
    return series


def _format_table(df: pd.DataFrame, max_rows: int = 8) -> pd.DataFrame:
    display = df.head(max_rows).copy()
    display.columns = [str(col).replace("_", " ").title() for col in display.columns]

    for column in display.columns:
        series = _maybe_format_numeric(display[column])
        if not pd.api.types.is_numeric_dtype(series):
            display[column] = series.astype(str)
            continue

        col_key = column.lower()
        if "pct" in col_key or "ratio" in col_key or "share" in col_key:
            display[column] = series.map(lambda v: f"{float(v):.1f}%" if pd.notna(v) else "-")
        elif "usd" in col_key or "premium" in col_key or "paid" in col_key or "cost" in col_key:
            display[column] = series.map(lambda v: f"{float(v):,.0f}" if pd.notna(v) else "-")
        else:
            display[column] = series.map(lambda v: f"{float(v):,.0f}" if pd.notna(v) else "-")

    return display


def _draw_table(ax: plt.Axes, title: str, df: pd.DataFrame, max_rows: int = 8) -> None:
    ax.axis("off")
    ax.set_title(title, loc="left", fontsize=11.5, color=BRAND_NAVY, fontweight="bold", pad=8)
    if df.empty:
        ax.text(0.5, 0.5, "No data available", ha="center", va="center", color=TEXT_MUTED, fontsize=10.5)
        return

    display = _format_table(df, max_rows=max_rows)
    table = ax.table(
        cellText=display.values,
        colLabels=display.columns,
        cellLoc="center",
        colLoc="center",
        bbox=[0.0, 0.0, 1.0, 0.88],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(8.8)
    table.scale(1.0, 1.45)

    for (row, _col), cell in table.get_celld().items():
        if row == 0:
            cell.set_facecolor(BRAND_NAVY)
            cell.set_text_props(color="white", weight="bold")
        else:
            cell.set_facecolor("#F8FAFD" if row % 2 == 0 else "white")
            cell.set_text_props(color=TEXT_DARK)
        cell.set_edgecolor(CARD_BORDER)
        cell.set_linewidth(0.8)


def _style_axis(ax: plt.Axes, title: str, xlabel: str = "", ylabel: str = "", rotate_x: int = 0) -> None:
    ax.set_title(title, fontsize=11.5, color=BRAND_NAVY, fontweight="bold", pad=8)
    ax.set_xlabel(xlabel, fontsize=9.5, color=TEXT_MUTED)
    ax.set_ylabel(ylabel, fontsize=9.5, color=TEXT_MUTED)
    ax.grid(axis="y", color="#DFE5EF", linewidth=0.8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#BFCBDD")
    ax.spines["bottom"].set_color("#BFCBDD")
    ax.tick_params(axis="both", labelsize=9, colors=TEXT_DARK)
    if rotate_x:
        ax.tick_params(axis="x", labelrotation=rotate_x)
        for tick in ax.get_xticklabels():
            tick.set_ha("right" if rotate_x >= 20 else "center")
    ax.margins(x=0.02)


def _wrap_tick_labels(ax: plt.Axes, axis: str = "x", width: int = 14) -> None:
    if width <= 0:
        return
    ticks = ax.get_xticklabels() if axis == "x" else ax.get_yticklabels()
    for tick in ticks:
        tick.set_text(textwrap.fill(str(tick.get_text()), width=width, break_long_words=False))
    ax.figure.canvas.draw()


def _draw_empty_state(ax: plt.Axes, title: str, message: str = "No data available for this section.") -> None:
    ax.axis("off")
    ax.text(0.5, 0.58, title, ha="center", va="center", fontsize=11, color=BRAND_NAVY, weight="bold")
    ax.text(0.5, 0.44, message, ha="center", va="center", fontsize=9.5, color=TEXT_MUTED)


def _period_label(monthly: pd.DataFrame) -> str:
    if monthly.empty or "month_label" not in monthly.columns:
        return "Period: Not available"
    labels = monthly["month_label"].astype(str).tolist()
    return f"Period: {labels[0]} to {labels[-1]}" if labels else "Period: Not available"


def _status_between(actual: float, low: float, high: float) -> str:
    if actual < low:
        return "Below range"
    if actual > high:
        return "Above range"
    return "Within range"


def _status_upper(actual: float, upper: float) -> str:
    return "Within range" if actual <= upper else "Above range"


def _build_advisory_recommendations(
    master_census: pd.DataFrame,
    master_claims: pd.DataFrame,
    context: Dict[str, object],
    provider: pd.DataFrame,
    uw_comp: pd.DataFrame,
) -> list[Dict[str, str]]:
    claims = master_claims.copy()
    census = master_census.copy()

    total_claims = max(1, len(claims))
    paid_series = pd.to_numeric(claims["paid_amount_usd"], errors="coerce").fillna(0.0) if "paid_amount_usd" in claims.columns else pd.Series(dtype=float)
    total_paid = float(paid_series.sum()) if len(paid_series) else 0.0

    chronic_mask = pd.Series([False] * len(claims), index=claims.index)
    if "illness_type" in claims.columns:
        illness_series = claims["illness_type"].astype(str).str.lower()
        chronic_mask = illness_series.eq("pec/chronic")
    chronic_claims = int(chronic_mask.sum()) if len(chronic_mask) else 0
    chronic_ratio = float(chronic_claims / total_claims * 100)
    chronic_paid = float(paid_series[chronic_mask].sum()) if len(paid_series) else 0.0

    diagnosis_series = claims["diagnosis_description"].astype(str).str.lower() if "diagnosis_description" in claims.columns else pd.Series([None] * len(claims))
    htn_count = int(diagnosis_series.str.contains("hypertension", na=False).sum()) if len(diagnosis_series) else 0
    dm_count = int(diagnosis_series.str.contains("diabetes", na=False).sum()) if len(diagnosis_series) else 0

    top_provider_share = _to_number(context.get("top_provider_share_pct", 0.0))
    top_provider_spend = 0.0
    if not provider.empty and "total_paid_usd" in provider.columns:
        top_provider_spend = float(pd.to_numeric(provider["total_paid_usd"], errors="coerce").fillna(0.0).iloc[0])
    elif total_paid:
        top_provider_spend = total_paid * (top_provider_share / 100.0)

    qatar_claims = pd.DataFrame()
    qatar_loss_ratio = 0.0
    if "country" in claims.columns:
        qatar_claims = claims[claims["country"].astype(str).str.contains("qatar", case=False, na=False)].copy()
    if not uw_comp.empty and {"country", "loss_ratio_pct"}.issubset(uw_comp.columns):
        qatar_rows = uw_comp[uw_comp["country"].astype(str).str.contains("qatar", case=False, na=False)]
        if not qatar_rows.empty:
            qatar_loss_ratio = float(pd.to_numeric(qatar_rows["loss_ratio_pct"], errors="coerce").fillna(0.0).max())

    qatar_paid = float(pd.to_numeric(qatar_claims["paid_amount_usd"], errors="coerce").fillna(0.0).sum()) if (not qatar_claims.empty and "paid_amount_usd" in qatar_claims.columns) else 0.0
    qatar_top2_share = 0.0
    if qatar_paid > 0:
        top2_paid = float(pd.to_numeric(qatar_claims["paid_amount_usd"], errors="coerce").fillna(0.0).nlargest(2).sum())
        qatar_top2_share = top2_paid / qatar_paid * 100

    bronze_mask = pd.Series([False] * len(census))
    if "benefit_class" in census.columns:
        bronze_mask = bronze_mask | census["benefit_class"].astype(str).str.upper().isin(["C", "CLASS C"])
    if "network_tier" in census.columns:
        bronze_mask = bronze_mask | census["network_tier"].astype(str).str.lower().str.contains("bronze", na=False)

    bronze_members = census[bronze_mask].copy()
    bronze_country_text = "key markets"
    if not bronze_members.empty and "country" in bronze_members.columns:
        bronze_countries = sorted(bronze_members["country"].dropna().astype(str).unique().tolist())
        if bronze_countries:
            bronze_country_text = ", ".join(bronze_countries[:4])

    bronze_claims_mask = pd.Series([False] * len(claims))
    if "benefit_class" in claims.columns:
        bronze_claims_mask = bronze_claims_mask | claims["benefit_class"].astype(str).str.upper().isin(["C", "CLASS C"])
    if "network_tier" in claims.columns:
        bronze_claims_mask = bronze_claims_mask | claims["network_tier"].astype(str).str.lower().str.contains("bronze", na=False)
    bronze_claims = claims[bronze_claims_mask].copy()

    bronze_avg_cost = 0.0
    if not bronze_claims.empty and "paid_amount_usd" in bronze_claims.columns:
        bronze_avg_cost = float(pd.to_numeric(bronze_claims["paid_amount_usd"], errors="coerce").fillna(0.0).mean())

    bronze_provider_names = "top contracted providers"
    if not bronze_claims.empty and {"provider_name", "paid_amount_usd"}.issubset(bronze_claims.columns):
        bronze_provider = (
            bronze_claims.groupby("provider_name", as_index=False)
            .agg(total_paid_usd=("paid_amount_usd", "sum"))
            .sort_values("total_paid_usd", ascending=False)
        )
        names = bronze_provider["provider_name"].head(2).astype(str).tolist()
        if names:
            bronze_provider_names = " + ".join(names)

    chronic_save_low = max(0.0, chronic_paid * 0.08)
    chronic_save_high = max(chronic_save_low, chronic_paid * 0.12)
    provider_save_low = max(0.0, top_provider_spend * 0.06)
    provider_save_high = max(provider_save_low, top_provider_spend * 0.09)
    bronze_pool_paid = float(pd.to_numeric(bronze_claims["paid_amount_usd"], errors="coerce").fillna(0.0).sum()) if (not bronze_claims.empty and "paid_amount_usd" in bronze_claims.columns) else 0.0
    bronze_save_low = max(0.0, bronze_pool_paid * 0.12)
    bronze_save_high = max(bronze_save_low, bronze_pool_paid * 0.18)

    return [
        {
            "title": "Chronic Disease Management Programme",
            "business_case": (
                f"PEC/Chronic conditions currently drive {chronic_ratio:.1f}% of portfolio claims. "
                f"Hypertension and diabetes contribute {htn_count + dm_count:,} diagnosed episodes."
            ),
            "action": (
                "Run annual HbA1c, blood pressure, and lipid screening with a regional wellness partner; "
                "use telemedicine follow-up for confirmed chronic members."
            ),
            "est_saving": f"USD {chronic_save_low:,.0f} to {chronic_save_high:,.0f} per year from a 10% episode reduction.",
        },
        {
            "title": "Provider Network Renegotiation",
            "business_case": (
                f"Top provider concentration is {top_provider_share:.1f}% of paid amount, creating renewal pricing risk "
                "and negotiation dependency."
            ),
            "action": (
                "Request itemized billing audits for top-spend providers and negotiate a portfolio-level volume discount "
                "across countries."
            ),
            "est_saving": f"USD {provider_save_low:,.0f} to {provider_save_high:,.0f} per year with a 6%-9% discount range.",
        },
        {
            "title": "Qatar Portfolio Pre-Authorization Tightening",
            "business_case": (
                f"Qatar loss ratio is currently {qatar_loss_ratio:.1f}% and top two high-cost claims contribute "
                f"{qatar_top2_share:.1f}% of Qatar paid value."
            ),
            "action": (
                "Mandate pre-authorization for inpatient admissions above USD 1,500 in Qatar and add second-opinion "
                "review for oncology treatment plans."
            ),
            "est_saving": (
                "Risk mitigation action to prevent loss-ratio drift above renewal tolerance bands, "
                "especially where case concentration is high."
            ),
        },
        {
            "title": "Class C / Bronze Network Consolidation",
            "business_case": (
                f"Class C/Bronze segment in {bronze_country_text} averages USD {bronze_avg_cost:,.0f} per claim and "
                "can be managed with tighter provider panels."
            ),
            "action": (
                f"Review Bronze networks and consolidate to fewer preferred providers (e.g., {bronze_provider_names}) "
                "after HR and employee communication sign-off."
            ),
            "est_saving": f"USD {bronze_save_low:,.0f} to {bronze_save_high:,.0f} per year via consolidation and admin efficiency.",
        },
    ]


def _build_kpi_summary_table(master_census: pd.DataFrame, master_claims: pd.DataFrame, context: Dict[str, object]) -> pd.DataFrame:
    total_claims = int(_to_number(context.get("total_claims", 0)))
    total_paid = _to_number(context.get("total_paid_usd", 0.0))
    loss_ratio = _to_number(context.get("loss_ratio_pct", 0.0))
    avg_cost = (total_paid / total_claims) if total_claims else 0.0

    pec_ratio = 0.0
    oncology_cases = 0
    maternity_cases = 0
    inpatient_pct = 0.0
    if len(master_claims):
        if "pec_flag" in master_claims.columns:
            pec_ratio = float(pd.to_numeric(master_claims["pec_flag"], errors="coerce").fillna(0).mean() * 100)
        if "oncology_flag" in master_claims.columns:
            oncology_cases = int(pd.to_numeric(master_claims["oncology_flag"], errors="coerce").fillna(0).sum())
        if "maternity_flag" in master_claims.columns:
            maternity_cases = int(pd.to_numeric(master_claims["maternity_flag"], errors="coerce").fillna(0).sum())
        if "benefit_type" in master_claims.columns:
            inpatient_count = master_claims["benefit_type"].astype(str).str.contains("inpatient", case=False, na=False).sum()
            inpatient_pct = float(inpatient_count / max(1, len(master_claims)) * 100)

    avg_employee_age = 0.0
    if len(master_census) and {"relationship", "age"}.issubset(master_census.columns):
        employee_rows = master_census[master_census["relationship"].astype(str).str.lower() == "employee"]
        if not employee_rows.empty:
            avg_employee_age = float(pd.to_numeric(employee_rows["age"], errors="coerce").dropna().mean())

    rows = [
        {"Metric": "Total Claims", "Value": f"{total_claims:,}", "Benchmark": "-", "Status": "-"},
        {"Metric": "Total Paid (USD)", "Value": f"USD {total_paid:,.0f}", "Benchmark": "-", "Status": "-"},
        {
            "Metric": "Loss Ratio",
            "Value": f"{loss_ratio:.1f}%",
            "Benchmark": "85-95%",
            "Status": _status_between(loss_ratio, 85.0, 95.0),
        },
        {
            "Metric": "Cost Per Claim (USD)",
            "Value": f"USD {avg_cost:,.0f}",
            "Benchmark": "USD 150-250",
            "Status": _status_between(avg_cost, 150.0, 250.0),
        },
        {
            "Metric": "PEC/Chronic Ratio",
            "Value": f"{pec_ratio:.1f}%",
            "Benchmark": "< 65%",
            "Status": _status_upper(pec_ratio, 65.0),
        },
        {
            "Metric": "Inpatient %",
            "Value": f"{inpatient_pct:.1f}%",
            "Benchmark": "25-35%",
            "Status": _status_between(inpatient_pct, 25.0, 35.0),
        },
        {
            "Metric": "Avg Age (Employee)",
            "Value": f"{avg_employee_age:.1f} yrs" if avg_employee_age else "N/A",
            "Benchmark": "30-42 yrs",
            "Status": _status_between(avg_employee_age, 30.0, 42.0) if avg_employee_age else "-",
        },
        {
            "Metric": "Oncology Cases",
            "Value": f"{oncology_cases} claims",
            "Benchmark": "< 5 per period",
            "Status": _status_upper(float(oncology_cases), 5.0),
        },
        {
            "Metric": "Maternity Cases",
            "Value": f"{maternity_cases} claims",
            "Benchmark": "-",
            "Status": "-",
        },
    ]
    return pd.DataFrame(rows)


def _draw_recommendation_card(ax: plt.Axes, index: int, item: Dict[str, str]) -> None:
    ax.axis("off")
    card = FancyBboxPatch(
        (0, 0),
        1,
        1,
        boxstyle="round,pad=0.014,rounding_size=0.03",
        transform=ax.transAxes,
        facecolor="white",
        edgecolor=CARD_BORDER,
        linewidth=1.1,
    )
    ax.add_patch(card)
    ax.text(0.04, 0.93, f"{index}. {item.get('title', '')}", fontsize=10.6, color=BRAND_NAVY, weight="bold", va="top")

    sections = [
        ("Business case", item.get("business_case", "")),
        ("Action", item.get("action", "")),
        ("Est. saving", item.get("est_saving", "")),
    ]
    cursor = 0.83
    for label, value in sections:
        ax.text(0.04, cursor, f"{label}:", fontsize=9.2, color=BRAND_RED, weight="bold", va="top")
        cursor -= 0.075
        for line in textwrap.wrap(str(value), width=58):
            ax.text(0.04, cursor, line, fontsize=9.0, color=TEXT_DARK, va="top")
            cursor -= 0.065
            if cursor < 0.07:
                return
        cursor -= 0.02


def _draw_string_table(ax: plt.Axes, title: str, df: pd.DataFrame) -> None:
    ax.axis("off")
    ax.set_title(title, loc="left", fontsize=11.5, color=BRAND_NAVY, fontweight="bold", pad=8)
    table = ax.table(
        cellText=df.values,
        colLabels=df.columns,
        cellLoc="left",
        colLoc="left",
        bbox=[0.0, 0.0, 1.0, 0.90],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9.0)
    table.scale(1.0, 1.35)

    for (row, _col), cell in table.get_celld().items():
        if row == 0:
            cell.set_facecolor(BRAND_NAVY)
            cell.set_text_props(color="white", weight="bold")
        else:
            cell.set_facecolor("#F8FAFD" if row % 2 == 0 else "white")
            cell.set_text_props(color=TEXT_DARK)
        cell.set_edgecolor(CARD_BORDER)
        cell.set_linewidth(0.8)


def generate_claims_pdf_report(
    master_census: pd.DataFrame,
    master_claims: pd.DataFrame,
    powerbi_tables: Dict[str, pd.DataFrame],
    output_path: Path,
    use_llm_narrative: bool = True,
) -> str:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid", context="notebook")

    context = _build_context(master_census, master_claims)
    narrative = generate_report_narrative(context, use_llm=use_llm_narrative)

    monthly = powerbi_tables.get("monthly_trend", pd.DataFrame()).copy()
    quarterly = powerbi_tables.get("quarterly_summary", pd.DataFrame()).copy()
    benefit = powerbi_tables.get("benefit_split", pd.DataFrame()).copy()
    relationship = powerbi_tables.get("relationship_age", pd.DataFrame()).copy()
    age_group = powerbi_tables.get("age_group_analysis", pd.DataFrame()).copy()
    pec_top = powerbi_tables.get("pec_diagnosis_top10", pd.DataFrame()).copy()
    provider = powerbi_tables.get("provider_top5", pd.DataFrame()).copy()
    uw_comp = powerbi_tables.get("uw_comparison", pd.DataFrame()).copy()
    benchmarks = powerbi_tables.get("benchmarks", pd.DataFrame()).copy()
    advisory_recommendations = _build_advisory_recommendations(
        master_census=master_census,
        master_claims=master_claims,
        context=context,
        provider=provider,
        uw_comp=uw_comp,
    )
    kpi_summary_table = _build_kpi_summary_table(
        master_census=master_census,
        master_claims=master_claims,
        context=context,
    )

    total_pages = 8
    with PdfPages(output_path) as pdf:
        # Page 1: Executive summary
        fig = plt.figure(figsize=(11.69, 8.27))
        _add_page_chrome(
            fig,
            "Health Insurance Claims Analysis",
            "Executive Summary",
            page_number=1,
            total_pages=total_pages,
        )
        fig.text(0.03, 0.895, _period_label(monthly), fontsize=10, color=TEXT_MUTED)
        fig.text(0.03, 0.872, "Scope: multi-country underwriter portfolio", fontsize=10, color=TEXT_MUTED)

        kpi_cards = [
            ("Total Claims", _fmt_int(context["total_claims"]), BRAND_RED),
            ("Total Paid (USD)", _fmt_currency(context["total_paid_usd"]), BRAND_NAVY),
            ("Total Premium (USD)", _fmt_currency(context["total_premium_usd"]), BRAND_TEAL),
            ("Loss Ratio", _fmt_pct(context["loss_ratio_pct"]), BRAND_GOLD),
        ]
        for index, (label, value, accent) in enumerate(kpi_cards):
            x = 0.03 + index * 0.238
            _draw_kpi_card(fig, [x, 0.71, 0.223, 0.14], label, value, accent)

        _draw_text_card(
            fig,
            [0.03, 0.40, 0.94, 0.27],
            "Executive Summary",
            _wrap_lines([str(narrative.get("executive_summary", ""))], width=120),
            bullet=False,
        )
        _draw_text_card(
            fig,
            [0.03, 0.10, 0.46, 0.25],
            "Key Findings",
            [str(item) for item in narrative.get("key_findings", [])],
            bullet=True,
        )
        _draw_text_card(
            fig,
            [0.51, 0.10, 0.46, 0.25],
            "Top Recommendations",
            [str(item) for item in narrative.get("recommendations", [])],
            bullet=True,
        )

        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        # Page 2: Claims overview
        fig, axes = plt.subplots(2, 2, figsize=(11.69, 8.27))
        _add_page_chrome(fig, "Health Insurance Claims Analysis", "Claims Overview", 2, total_pages)
        fig.subplots_adjust(top=0.855, bottom=0.11, left=0.06, right=0.98, hspace=0.56, wspace=0.25)

        if not monthly.empty and {"month_label", "total_claims", "total_paid_usd"}.issubset(monthly.columns):
            monthly_plot = monthly.copy()
            monthly_plot["month_label"] = monthly_plot["month_label"].astype(str)
            monthly_plot["total_claims"] = pd.to_numeric(monthly_plot["total_claims"], errors="coerce").fillna(0.0)
            monthly_plot["total_paid_usd"] = pd.to_numeric(monthly_plot["total_paid_usd"], errors="coerce").fillna(0.0)

            sns.barplot(
                data=monthly_plot,
                x="month_label",
                y="total_claims",
                hue="month_label",
                palette="Reds",
                legend=False,
                ax=axes[0, 0],
            )
            _style_axis(axes[0, 0], "Monthly Claim Volume", ylabel="Claim Count", rotate_x=35)

            paid_ax = axes[0, 0].twinx()
            sns.lineplot(
                data=monthly_plot,
                x="month_label",
                y="total_paid_usd",
                color=BRAND_NAVY,
                marker="o",
                linewidth=2.2,
                ax=paid_ax,
                sort=False,
            )
            paid_ax.yaxis.set_major_formatter(FuncFormatter(_compact_currency))
            paid_ax.tick_params(axis="y", labelsize=8.5, colors=BRAND_NAVY)
            paid_ax.set_ylabel("Paid USD", fontsize=9.5, color=BRAND_NAVY)
        else:
            _draw_empty_state(axes[0, 0], "Monthly Claim Volume")

        _draw_table(axes[0, 1], "Quarterly Summary", quarterly, max_rows=6)

        if not benefit.empty and {"benefit_type", "total_claims"}.issubset(benefit.columns):
            benefit_plot = benefit.copy().sort_values("total_claims", ascending=False)
            sns.barplot(
                data=benefit_plot,
                x="benefit_type",
                y="total_claims",
                hue="benefit_type",
                palette="Set2",
                legend=False,
                ax=axes[1, 0],
            )
            _wrap_tick_labels(axes[1, 0], axis="x", width=12)
            _style_axis(axes[1, 0], "Benefit Mix by Claim Count", ylabel="Claim Count", rotate_x=30)
        else:
            _draw_empty_state(axes[1, 0], "Benefit Mix by Claim Count")

        if not benefit.empty and {"benefit_type", "total_claims"}.issubset(benefit.columns):
            donut_labels = benefit["benefit_type"].astype(str)
            donut_values = pd.to_numeric(benefit["total_claims"], errors="coerce").fillna(0.0)
            axes[1, 1].pie(
                donut_values,
                labels=donut_labels,
                autopct="%1.1f%%",
                startangle=90,
                pctdistance=0.78,
                wedgeprops={"width": 0.42, "edgecolor": "white"},
                colors=sns.color_palette("crest", len(donut_values)),
                textprops={"fontsize": 8.5},
            )
            axes[1, 1].text(0, 0, "Benefit\nShare", ha="center", va="center", fontsize=10.5, color=TEXT_DARK, weight="bold")
            axes[1, 1].set_title("Benefit Distribution", fontsize=11.5, color=BRAND_NAVY, fontweight="bold")
        else:
            _draw_empty_state(axes[1, 1], "Benefit Distribution")

        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        # Page 3: Demographics
        fig, axes = plt.subplots(2, 2, figsize=(11.69, 8.27))
        _add_page_chrome(fig, "Health Insurance Claims Analysis", "Demographics and Cost Profile", 3, total_pages)
        fig.subplots_adjust(top=0.855, bottom=0.11, left=0.06, right=0.98, hspace=0.56, wspace=0.25)

        if not relationship.empty and {"relationship", "avg_age"}.issubset(relationship.columns):
            rel_plot = relationship.copy()
            rel_plot["avg_age"] = pd.to_numeric(rel_plot["avg_age"], errors="coerce").fillna(0.0)
            sns.barplot(
                data=rel_plot,
                x="relationship",
                y="avg_age",
                hue="relationship",
                palette="Blues",
                legend=False,
                ax=axes[0, 0],
            )
            _style_axis(axes[0, 0], "Average Age by Relationship", ylabel="Average Age")
        else:
            _draw_empty_state(axes[0, 0], "Average Age by Relationship")

        if not age_group.empty and {"age_group", "total_claims"}.issubset(age_group.columns):
            age_claims = age_group.copy()
            age_claims["total_claims"] = pd.to_numeric(age_claims["total_claims"], errors="coerce").fillna(0.0)
            sns.barplot(
                data=age_claims,
                x="age_group",
                y="total_claims",
                hue="age_group",
                palette="mako",
                legend=False,
                ax=axes[0, 1],
            )
            _wrap_tick_labels(axes[0, 1], axis="x", width=11)
            _style_axis(axes[0, 1], "Claims by Age Group", ylabel="Claim Count", rotate_x=35)
        else:
            _draw_empty_state(axes[0, 1], "Claims by Age Group")

        if not age_group.empty and {"age_group", "avg_cost_usd"}.issubset(age_group.columns):
            age_costs = age_group.copy()
            age_costs["avg_cost_usd"] = pd.to_numeric(age_costs["avg_cost_usd"], errors="coerce").fillna(0.0)
            sns.lineplot(
                data=age_costs,
                x="age_group",
                y="avg_cost_usd",
                marker="o",
                linewidth=2.3,
                color=BRAND_TEAL,
                ax=axes[1, 0],
                sort=False,
            )
            _wrap_tick_labels(axes[1, 0], axis="x", width=11)
            axes[1, 0].yaxis.set_major_formatter(FuncFormatter(_compact_currency))
            _style_axis(axes[1, 0], "Average Cost by Age Group", ylabel="Average Cost (USD)", rotate_x=35)
        else:
            _draw_empty_state(axes[1, 0], "Average Cost by Age Group")

        top_claim_age = "N/A"
        top_cost_age = "N/A"
        if not age_group.empty and "age_group" in age_group.columns:
            if "total_claims" in age_group.columns:
                sorted_claims = age_group.sort_values("total_claims", ascending=False)
                top_claim_age = _safe_top(sorted_claims["age_group"])
            if "avg_cost_usd" in age_group.columns:
                sorted_cost = age_group.sort_values("avg_cost_usd", ascending=False)
                top_cost_age = _safe_top(sorted_cost["age_group"])

        _draw_panel_text(
            axes[1, 1],
            "Demographic Insights",
            [
                f"Highest claim-volume age group: {top_claim_age}.",
                f"Highest average-cost age group: {top_cost_age}.",
                f"Top provider concentration currently sits at {_fmt_pct(context['top_provider_share_pct'])}.",
                f"Current portfolio loss ratio is {_fmt_pct(context['loss_ratio_pct'])}.",
            ],
            bullet=True,
        )

        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        # Page 4: PEC/Chronic drilldown
        fig = plt.figure(figsize=(11.69, 8.27))
        _add_page_chrome(fig, "Health Insurance Claims Analysis", "PEC and Chronic Conditions", 4, total_pages)
        grid = fig.add_gridspec(2, 2, left=0.08, right=0.98, top=0.855, bottom=0.10, hspace=0.42, wspace=0.24)
        ax_top = fig.add_subplot(grid[0, :])
        ax_table = fig.add_subplot(grid[1, 0])
        ax_notes = fig.add_subplot(grid[1, 1])

        if not pec_top.empty and {"diagnosis_description", "total_claims"}.issubset(pec_top.columns):
            pec_plot = pec_top.copy().sort_values("total_claims", ascending=True)
            sns.barplot(
                data=pec_plot,
                x="total_claims",
                y="diagnosis_description",
                hue="diagnosis_description",
                palette="rocket",
                legend=False,
                ax=ax_top,
            )
            _wrap_tick_labels(ax_top, axis="y", width=26)
            ax_top.tick_params(axis="y", labelsize=8.5)
            _style_axis(ax_top, "Top PEC Diagnoses by Claim Count", xlabel="Claim Count", ylabel="")
        else:
            _draw_empty_state(ax_top, "Top PEC Diagnoses by Claim Count")

        _draw_table(
            ax_table,
            "PEC Summary Table",
            pec_top[["icd10_code", "diagnosis_description", "total_claims", "total_paid_usd"]]
            if not pec_top.empty and {"icd10_code", "diagnosis_description", "total_claims", "total_paid_usd"}.issubset(pec_top.columns)
            else pd.DataFrame(),
            max_rows=8,
        )
        _draw_panel_text(
            ax_notes,
            "Clinical Insights",
            [str(item) for item in narrative.get("clinical_insights", [])],
            bullet=True,
        )

        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        # Page 5: Provider and country performance
        fig, axes = plt.subplots(2, 2, figsize=(11.69, 8.27))
        _add_page_chrome(fig, "Health Insurance Claims Analysis", "Provider and Country Performance", 5, total_pages)
        fig.subplots_adjust(top=0.855, bottom=0.11, left=0.06, right=0.98, hspace=0.56, wspace=0.25)

        if not provider.empty and {"provider_name", "total_paid_usd"}.issubset(provider.columns):
            provider_plot = provider.copy().sort_values("total_paid_usd", ascending=False)
            sns.barplot(
                data=provider_plot,
                x="total_paid_usd",
                y="provider_name",
                hue="provider_name",
                palette="flare",
                legend=False,
                ax=axes[0, 0],
            )
            _wrap_tick_labels(axes[0, 0], axis="y", width=22)
            axes[0, 0].xaxis.set_major_formatter(FuncFormatter(_compact_currency))
            _style_axis(axes[0, 0], "Top Providers by Paid Amount", xlabel="Paid USD", ylabel="")
        else:
            _draw_empty_state(axes[0, 0], "Top Providers by Paid Amount")

        _draw_table(
            axes[0, 1],
            "Provider Summary",
            provider[["provider_name", "total_claims", "total_paid_usd", "paid_share_pct", "avg_cost_per_claim"]]
            if not provider.empty and {"provider_name", "total_claims", "total_paid_usd", "paid_share_pct", "avg_cost_per_claim"}.issubset(provider.columns)
            else pd.DataFrame(),
            max_rows=6,
        )

        if not uw_comp.empty and {"source_uw", "country", "loss_ratio_pct"}.issubset(uw_comp.columns):
            uw_plot = uw_comp.copy().sort_values("loss_ratio_pct", ascending=False)
            uw_plot["loss_ratio_pct"] = pd.to_numeric(uw_plot["loss_ratio_pct"], errors="coerce").fillna(0.0)
            sns.barplot(
                data=uw_plot,
                x="source_uw",
                y="loss_ratio_pct",
                hue="country",
                palette="Set1",
                ax=axes[1, 0],
            )
            _wrap_tick_labels(axes[1, 0], axis="x", width=10)
            axes[1, 0].axhline(88.0, color=BRAND_NAVY, linestyle="--", linewidth=1.6, label="Benchmark 88%")
            _style_axis(axes[1, 0], "Underwriter Loss Ratio Comparison", ylabel="Loss Ratio (%)")
            axes[1, 0].legend(fontsize=8, frameon=False, loc="upper right")
        else:
            _draw_empty_state(axes[1, 0], "Underwriter Loss Ratio Comparison")

        if not uw_comp.empty and {"pec_ratio_pct", "cost_per_claim", "source_uw", "total_claims"}.issubset(uw_comp.columns):
            scatter_plot = uw_comp.copy()
            scatter_plot["pec_ratio_pct"] = pd.to_numeric(scatter_plot["pec_ratio_pct"], errors="coerce").fillna(0.0)
            scatter_plot["cost_per_claim"] = pd.to_numeric(scatter_plot["cost_per_claim"], errors="coerce").fillna(0.0)
            scatter_plot["total_claims"] = pd.to_numeric(scatter_plot["total_claims"], errors="coerce").fillna(1.0)
            sns.scatterplot(
                data=scatter_plot,
                x="pec_ratio_pct",
                y="cost_per_claim",
                hue="source_uw",
                size="total_claims",
                palette="Dark2",
                sizes=(70, 320),
                alpha=0.85,
                ax=axes[1, 1],
                legend=False,
            )
            axes[1, 1].yaxis.set_major_formatter(FuncFormatter(_compact_currency))
            _style_axis(axes[1, 1], "PEC Burden vs Cost per Claim", xlabel="PEC Ratio (%)", ylabel="Cost per Claim")
        else:
            _draw_panel_text(
                axes[1, 1],
                "Methodology Notes",
                [str(item) for item in narrative.get("methodology_notes", [])],
                bullet=True,
            )

        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        # Page 6: Benchmarks and handoff notes
        fig, axes = plt.subplots(1, 2, figsize=(11.69, 8.27))
        _add_page_chrome(fig, "Health Insurance Claims Analysis", "Benchmark Positioning and Handoff", 6, total_pages)
        fig.subplots_adjust(top=0.855, bottom=0.10, left=0.06, right=0.98, wspace=0.22)

        benchmark_map = {}
        if not benchmarks.empty and {"metric", "benchmark_value"}.issubset(benchmarks.columns):
            benchmark_map = dict(zip(benchmarks["metric"].astype(str), pd.to_numeric(benchmarks["benchmark_value"], errors="coerce")))

        avg_cost = (_to_number(context["total_paid_usd"]) / _to_number(context["total_claims"])) if _to_number(context["total_claims"]) else 0.0
        pec_ratio = 0.0
        if "pec_flag" in master_claims.columns and len(master_claims):
            pec_ratio = float(pd.to_numeric(master_claims["pec_flag"], errors="coerce").fillna(0).mean() * 100)

        benchmark_df = pd.DataFrame(
            [
                {
                    "Metric": "Loss Ratio (%)",
                    "Actual": _to_number(context["loss_ratio_pct"]),
                    "Benchmark": _to_number(benchmark_map.get("loss_ratio_pct", 88.0), 88.0),
                },
                {
                    "Metric": "Cost per Claim (USD)",
                    "Actual": avg_cost,
                    "Benchmark": _to_number(benchmark_map.get("cost_per_claim_usd", 200.0), 200.0),
                },
                {
                    "Metric": "PEC Ratio (%)",
                    "Actual": pec_ratio,
                    "Benchmark": _to_number(benchmark_map.get("pec_ratio_pct", 65.0), 65.0),
                },
                {
                    "Metric": "Provider Concentration (%)",
                    "Actual": _to_number(context["top_provider_share_pct"]),
                    "Benchmark": _to_number(benchmark_map.get("provider_concentration_pct", 25.0), 25.0),
                },
            ]
        )

        benchmark_long = benchmark_df.melt(id_vars="Metric", var_name="Type", value_name="Value")
        sns.barplot(
            data=benchmark_long,
            x="Value",
            y="Metric",
            hue="Type",
            palette=[BRAND_RED, BRAND_TEAL],
            ax=axes[0],
        )
        _wrap_tick_labels(axes[0], axis="y", width=24)
        _style_axis(axes[0], "Actual vs Benchmark", xlabel="Value", ylabel="")
        axes[0].legend(frameon=False, fontsize=9, title="")

        _draw_panel_text(
            axes[1],
            "Handoff Notes",
            [
                f"PDF pack includes {total_pages} pages with KPI, trend, demographic, and PEC analyses.",
                "Power BI-ready tables are generated in CSV format and can be connected directly.",
                "Narrative sections can run in fallback mode or use Azure OpenAI for richer wording.",
                "Use this report layout as a deterministic baseline for future underwriter uploads.",
            ],
            bullet=True,
        )

        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        # Page 7: Advisory recommendations
        fig = plt.figure(figsize=(11.69, 8.27))
        _add_page_chrome(fig, "Health Insurance Claims Analysis", "Advisory Recommendations", 7, total_pages)
        fig.text(
            0.03,
            0.89,
            "Action plan focused on chronic utilization, provider leverage, and country-specific controls.",
            fontsize=10,
            color=TEXT_MUTED,
        )
        grid = fig.add_gridspec(2, 2, left=0.04, right=0.98, top=0.86, bottom=0.08, hspace=0.20, wspace=0.12)
        for i, item in enumerate(advisory_recommendations[:4]):
            ax = fig.add_subplot(grid[i // 2, i % 2])
            _draw_recommendation_card(ax, i + 1, item)

        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        # Page 8: Appendix KPI summary, methodology, and disclaimer
        fig = plt.figure(figsize=(11.69, 8.27))
        _add_page_chrome(fig, "Health Insurance Claims Analysis", "Appendix - KPI Summary", 8, total_pages)

        ax_table = fig.add_axes([0.03, 0.38, 0.94, 0.50])
        _draw_string_table(ax_table, "Full KPI Summary", kpi_summary_table)

        methodology_lines = [
            "Loss Ratio = Total Paid Amount (USD) / Gross Written Premium (USD) x 100.",
            "UW1 (Oman): Amounts in Baisa/Fils are converted to OMR then to USD as per pipeline rules.",
            "UW2 (Saudi Arabia): Amounts are treated as USD where already normalized in source.",
            "UW3 (Qatar): Amounts in QAR are converted to USD using configured conversion factors.",
            "Market benchmarks are indicative GCC health insurance reference thresholds.",
        ]
        disclaimer_lines = [
            "Prepared from underwriter-provided claim records for the selected reporting period.",
            "Benchmarks are directional and should be validated during renewal discussions.",
            "CONFIDENTIAL - For Client Use Only.",
        ]

        ax_method = fig.add_axes([0.03, 0.10, 0.61, 0.23])
        _draw_panel_text(ax_method, "Methodology and Currency Conversion", methodology_lines, bullet=True)
        ax_disclaimer = fig.add_axes([0.66, 0.10, 0.31, 0.23])
        _draw_panel_text(ax_disclaimer, "Disclaimer", disclaimer_lines, bullet=True)

        fig.text(
            0.03,
            0.06,
            "ACE | Gallagher | Multi-Country Claims Analysis H1 2024 · CONFIDENTIAL",
            fontsize=8.5,
            color=TEXT_MUTED,
        )
        fig.text(
            0.97,
            0.06,
            "CONFIDENTIAL - For Client Use Only",
            fontsize=8.5,
            color=TEXT_MUTED,
            ha="right",
        )

        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

    return str(output_path)
