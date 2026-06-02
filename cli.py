"""
cli.py
------
Command-line interface for the Excel to TSV converter.

Usage:
    python cli.py --input data/test.xlsx
    python cli.py --input data/test.xlsx --output output/result.tsv
    python cli.py --input data/test.xlsx --header-row 2 --data-start-row 3
"""

import argparse
import sys
import time

sys.path.insert(0, "src")
from excel_to_tsv.converter import convert


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        prog="excel_to_tsv",
        description="Convert an Excel file with merged headers to a clean TSV.",
    )
    parser.add_argument(
        "--input",
        required=True,
        metavar="FILE",
        help="Path to the input .xlsx file (e.g. data/test.xlsx)",
    )
    parser.add_argument(
        "--output",
        default="output/output.tsv",
        metavar="FILE",
        help="Path for the output .tsv file (default: output/output.tsv)",
    )
    parser.add_argument(
        "--header-row",
        type=int,
        default=2,
        metavar="N",
        help="Zero-based row index of the real column headers (default: 2)",
    )
    parser.add_argument(
        "--data-start-row",
        type=int,
        default=3,
        metavar="N",
        help="Zero-based row index where data begins (default: 3)",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point for the CLI."""
    args = parse_args()

    print(f"Reading:      {args.input}")
    print(f"Header row:   {args.header_row}")
    print(f"Data from:    row {args.data_start_row}")
    print(f"Output:       {args.output}")
    print("-" * 40)

    start = time.time()

    try:
        df = convert(
            filepath=args.input,
            output_path=args.output,
            header_row=args.header_row,
            data_start_row=args.data_start_row,
        )
    except FileNotFoundError:
        print(f"ERROR: File not found — '{args.input}'")
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}")
        sys.exit(1)

    elapsed = time.time() - start

    print(f"Columns ({len(df.columns)}): {df.columns.tolist()}")
    print(f"Rows:         {len(df):,}")
    print(f"Done in:      {elapsed:.1f}s")
    print(f"Saved to:     {args.output}")


if __name__ == "__main__":
    main()
