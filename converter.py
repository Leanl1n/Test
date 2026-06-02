"""
converter.py
------------
Core logic for reading an Excel file with merged header rows,
dropping empty columns, and exporting to TSV.
"""

import pandas as pd


def load_raw(filepath: str) -> pd.DataFrame:
    """
    Read the Excel file without any header parsing.

    Args:
        filepath: Path to the .xlsx file.

    Returns:
        Raw DataFrame with no header applied.
    """
    return pd.read_excel(filepath, header=None, engine="calamine")


def extract_headers(raw: pd.DataFrame, header_row: int = 2) -> list[str]:
    """
    Extract column headers from a specific row index.

    Args:
        raw: Raw DataFrame loaded without headers.
        header_row: Zero-based row index where real headers live (default: 2).

    Returns:
        List of header strings.
    """
    return raw.iloc[header_row].tolist()


def build_dataframe(raw: pd.DataFrame, headers: list[str], data_start_row: int = 3) -> pd.DataFrame:
    """
    Slice the raw DataFrame from the data start row and assign headers.

    Args:
        raw: Raw DataFrame loaded without headers.
        headers: List of column header strings.
        data_start_row: Zero-based row index where data begins (default: 3).

    Returns:
        DataFrame with headers assigned and index reset.
    """
    df = raw.iloc[data_start_row:].copy()
    df.columns = headers
    return df.reset_index(drop=True)


def clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove columns with no valid header and columns with no data at all.

    Steps:
        1. Drop columns where the header is NaN.
        2. Drop columns where the header is an empty string.
        3. Drop columns where every single row value is NaN.
        4. Uppercase all remaining headers.

    Args:
        df: DataFrame with raw headers assigned.

    Returns:
        Cleaned DataFrame.
    """
    # Drop NaN headers
    df = df.loc[:, pd.notna(df.columns)]

    # Drop empty string headers
    df = df.loc[:, df.columns.astype(str).str.strip() != ""]

    # Drop columns where ALL rows are empty
    df = df.dropna(axis=1, how="all")

    # Uppercase and strip all headers
    df.columns = [str(col).strip().upper() for col in df.columns]

    return df


def export_tsv(df: pd.DataFrame, output_path: str) -> None:
    """
    Export DataFrame to a tab-separated values file.

    Args:
        df: Cleaned DataFrame to export.
        output_path: Destination file path for the .tsv file.
    """
    df.to_csv(output_path, sep="\t", index=False)


def convert(filepath: str, output_path: str, header_row: int = 2, data_start_row: int = 3) -> pd.DataFrame:
    """
    Full pipeline: load Excel -> extract headers -> clean -> export TSV.

    Args:
        filepath: Path to the input .xlsx file.
        output_path: Path for the output .tsv file.
        header_row: Zero-based row index of the real headers (default: 2).
        data_start_row: Zero-based row index where data begins (default: 3).

    Returns:
        The cleaned DataFrame.
    """
    raw = load_raw(filepath)
    headers = extract_headers(raw, header_row)
    df = build_dataframe(raw, headers, data_start_row)
    df = clean_columns(df)
    export_tsv(df, output_path)
    return df
