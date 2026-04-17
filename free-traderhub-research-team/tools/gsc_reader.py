"""gsc_reader.py — Read and analyse Google Search Console CSV exports."""

import json
import os
import pandas as pd
from crewai.tools import tool

_GSC_PATH = os.path.join("inputs", "gsc_export.csv")
_MIN_IMPRESSIONS_FOR_CTR = 50


def _find_column(df: pd.DataFrame, *candidates: str) -> str | None:
    """Find the first column whose normalised name contains any candidate substring."""
    normalised = {col: col.lower().replace(" ", "_").replace("-", "_") for col in df.columns}
    for col, norm in normalised.items():
        for candidate in candidates:
            if candidate in norm:
                return col
    return None


@tool("Read GSC CSV")
def read_gsc_csv(placeholder: str = "") -> str:
    """
    Read the Google Search Console export at inputs/gsc_export.csv and return
    a structured performance summary.

    Returns:
        JSON string with:
        - top_10_by_clicks: queries ranked by click volume
        - top_5_by_ctr: queries with >=50 impressions ranked by CTR
        - top_5_by_impressions: queries ranked by impression volume
        - total_queries: total number of unique queries in the export
        - instructions: present only if the file is missing
    """
    if not os.path.exists(_GSC_PATH):
        return json.dumps(
            {
                "instructions": (
                    "GSC data file not found. To add it:\n"
                    "1. Open Google Search Console → Performance → Search results.\n"
                    "2. Set your desired date range (last 28 days recommended).\n"
                    "3. Click 'Export' → 'Download CSV'.\n"
                    "4. Rename the downloaded file to 'gsc_export.csv'.\n"
                    "5. Drop it in the 'inputs/' folder.\n"
                    "6. Re-run the crew.\n\n"
                    "The crew will continue without GSC data this run."
                )
            },
            ensure_ascii=False,
            indent=2,
        )

    try:
        df = pd.read_csv(_GSC_PATH)
    except Exception as exc:
        return json.dumps({"error": f"Could not read CSV: {exc}"}, indent=2)

    # Normalise column names for partial matching
    query_col = _find_column(df, "query", "keyword", "search_term")
    clicks_col = _find_column(df, "click")
    impressions_col = _find_column(df, "impression")
    ctr_col = _find_column(df, "ctr", "click_through")
    position_col = _find_column(df, "position", "rank", "avg_pos")

    if not query_col:
        return json.dumps(
            {"error": "Could not identify a 'query' column in the CSV. Check your export format."},
            indent=2,
        )

    # Coerce numeric columns
    for col in [clicks_col, impressions_col, ctr_col, position_col]:
        if col:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace("%", ""), errors="coerce")

    def row_to_dict(row):
        d = {"query": row[query_col]}
        if clicks_col:
            d["clicks"] = int(row[clicks_col]) if pd.notna(row[clicks_col]) else 0
        if impressions_col:
            d["impressions"] = int(row[impressions_col]) if pd.notna(row[impressions_col]) else 0
        if ctr_col:
            d["ctr"] = round(float(row[ctr_col]), 4) if pd.notna(row[ctr_col]) else 0.0
        if position_col:
            d["avg_position"] = round(float(row[position_col]), 1) if pd.notna(row[position_col]) else None
        return d

    # Top 10 by clicks
    top_clicks = []
    if clicks_col:
        top_clicks = [
            row_to_dict(row)
            for _, row in df.nlargest(10, clicks_col).iterrows()
        ]

    # Top 5 by CTR (minimum 50 impressions)
    top_ctr = []
    if ctr_col and impressions_col:
        filtered = df[df[impressions_col] >= _MIN_IMPRESSIONS_FOR_CTR]
        top_ctr = [
            row_to_dict(row)
            for _, row in filtered.nlargest(5, ctr_col).iterrows()
        ]

    # Top 5 by impressions
    top_impressions = []
    if impressions_col:
        top_impressions = [
            row_to_dict(row)
            for _, row in df.nlargest(5, impressions_col).iterrows()
        ]

    result = {
        "total_queries": len(df),
        "top_10_by_clicks": top_clicks,
        "top_5_by_ctr": top_ctr,
        "top_5_by_impressions": top_impressions,
    }
    return json.dumps(result, ensure_ascii=False, indent=2)
