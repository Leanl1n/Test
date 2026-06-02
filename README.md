# Excel to TSV Converter

Converts an Excel file with merged header rows into a clean, flat TSV file.

## Project Structure

```
excel_to_tsv/
├── src/
│   └── excel_to_tsv/
│       ├── __init__.py
│       └── converter.py    # Core conversion logic
├── tests/
│   └── test_converter.py   # Unit tests
├── data/
│   └── test.xlsx           # Put your Excel file here
├── output/                 # TSV output saved here
├── cli.py                  # Command-line interface
├── requirements.txt
├── .gitignore
└── README.md
```

## What it does

- Reads `.xlsx` files that have merged/multi-row section headers
- Uses row 3 (index 2) as the real column headers by default
- Drops columns with no header (NaN or empty string)
- Drops columns where every single row is empty
- Uppercases all column headers for consistency
- Exports a clean `.tsv` file to the `output/` folder

## Installation

```bash
pip install -r requirements.txt
```

## Usage

Place your Excel file in the `data/` folder and run:

```bash
python cli.py --input data/test.xlsx
```

Output is saved to `output/output.tsv` by default.

### Custom output path
```bash
python cli.py --input data/test.xlsx --output output/result.tsv
```

### Custom header/data rows
```bash
python cli.py --input data/test.xlsx --header-row 2 --data-start-row 3
```

### All options

| Argument           | Default               | Description                                     |
|--------------------|-----------------------|-------------------------------------------------|
| `--input`          | *(required)*          | Path to the input `.xlsx` file                  |
| `--output`         | `output/output.tsv`   | Path for the output `.tsv` file                 |
| `--header-row`     | `2`                   | Zero-based row index of real column headers     |
| `--data-start-row` | `3`                   | Zero-based row index where data begins          |

## Running Tests

```bash
pytest tests/
```

## Excel File Structure Expected

```
Row 0:  [ AGENT INFO (merged A:J) ]  [ other section ]
Row 1:  [ NaN                     ]  [ NaN            ]
Row 2:  TERRITORY | REGION | ...      COL_K | COL_L ...   ← real headers
Row 3:  data      | data   | ...      ...                  ← data starts here
```

## Opening TSV in Excel

1. Open Excel
2. **File > Open** → change file filter to **All Files (`*.*`)**
3. Select your `.tsv` file
4. Text Import Wizard: choose **Delimited** → check **Tab** → Finish
