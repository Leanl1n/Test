"""
tests/test_converter.py
-----------------------
Unit tests for the Excel to TSV converter.
"""

import sys
import os
import pytest
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from excel_to_tsv.converter import clean_columns, build_dataframe, extract_headers


def make_raw() -> pd.DataFrame:
    """Build a mock raw DataFrame mimicking the Excel structure."""
    return pd.DataFrame([
        ["AGENT INFO", None, None, None],   # Row 0 - merged section header
        [None, None, None, None],           # Row 1 - empty
        ["Territory", "Region", None, "Agent Code"],  # Row 2 - real headers (one NaN)
        ["VisMin", "Visayas", None, "007598672"],      # Row 3 - data
        ["Others", "Other Units", None, "007767445"],  # Row 4 - data
    ])


def test_extract_headers():
    raw = make_raw()
    headers = extract_headers(raw, header_row=2)
    assert headers == ["Territory", "Region", None, "Agent Code"]


def test_build_dataframe():
    raw = make_raw()
    headers = extract_headers(raw, header_row=2)
    df = build_dataframe(raw, headers, data_start_row=3)
    assert len(df) == 2
    assert df.iloc[0]["Territory"] == "VisMin"


def test_clean_columns_drops_nan_header():
    raw = make_raw()
    headers = extract_headers(raw, header_row=2)
    df = build_dataframe(raw, headers, data_start_row=3)
    df = clean_columns(df)
    assert None not in df.columns
    assert "nan" not in [c.lower() for c in df.columns]


def test_clean_columns_uppercases():
    raw = make_raw()
    headers = extract_headers(raw, header_row=2)
    df = build_dataframe(raw, headers, data_start_row=3)
    df = clean_columns(df)
    for col in df.columns:
        assert col == col.upper()


def test_clean_columns_drops_all_empty():
    raw = make_raw()
    headers = extract_headers(raw, header_row=2)
    df = build_dataframe(raw, headers, data_start_row=3)
    df = clean_columns(df)
    # The None-header column (index 2) had all NaN data too — should be gone
    assert len(df.columns) == 2
