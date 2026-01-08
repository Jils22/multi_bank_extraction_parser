# pro1 — Bank Statement PDF Parser

A consolidated Python parser that automatically detects bank statement formats and extracts transactions from PDF files.

## Features

- **Multi-bank support**: Axis Bank, YesBank, J&K Bank, HDFC, Kotak, and standard table-based formats
- **Auto-detection**: Intelligently identifies bank type from PDF content
- **Fallback parsing**: Uses multiple strategies (table extraction, regex) for robust parsing
- **JSON output**: Exports parsed transactions in structured JSON format
- **Command-line interface**: Simple CLI with optional mode override

## Supported Banks

- **AXIS**: Table and text-based parser
- **YESBANK**: Table and text-based parser
- **JK**: J&K Bank (regex-based parsing)
- **HDFC**: Via original `sample.py` module
- **KOTAK**: Kotak Mahindra Bank (via original `sample.py`)
- **STANDARD**: SBI and other banks (simple table extraction with fallback regex)

## Installation

### Prerequisites
- Python 3.7+
- virtualenv

### Setup

```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows)
.\.venv\Scripts\activate

# Activate (macOS/Linux)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Basic Usage (Auto-detect)

```bash
python main_parser.py <pdf_path> <output_json>
```

Example:
```bash
python main_parser.py "unparsed_pdfs/statement.pdf" "outputs/statement.json"
```

### Specify Parser Mode

```bash
python main_parser.py <pdf_path> <output_json> --mode <mode>
```

Available modes:
- `auto` (default): Auto-detect bank type
- `standard`: SBI/generic table parser
- `AXIS`: Force Axis Bank parser
- `YESBANK`: Force YesBank parser
- `JK`: Force J&K Bank parser
- `HDFC`: Force HDFC Bank parser
- `KOTAK`: Force Kotak Bank parser

Examples:
```bash
python main_parser.py "statement.pdf" "output.json" --mode AXIS
python main_parser.py "statement.pdf" "output.json" --mode standard
```

## Project Structure

```
pro1/
├── main_parser.py           # Main consolidated parser (all logic)
├── requirements.txt         # Python dependencies
├── .gitignore              # Git ignore rules
├── README.md               # This file
├── archive_move.ps1        # PowerShell script to archive legacy files
├── archive/                # Legacy/archived parser scripts
│   ├── parse_one.py
│   ├── parse_one_enhanced.py
│   ├── parse_one_standard.py
│   ├── parse_remaining_*.py
│   ├── final_recovery.py
│   └── sample_enhanced.py
├── parsable_pdfs/          # Sample input PDFs (handled by .gitignore)
│   └── outputs/
├── unparsed_pdfs/          # Additional input PDFs (handled by .gitignore)
└── .venv/                  # Virtual environment (gitignored)
```

## Output Format

The parser generates a JSON file with transaction arrays:

```json
[
  {
    "Date": "01/04/2024",
    "Description": "Transfer to savings account",
    "Amount": "5000.00",
    "Balance": "15000.00",
    "Bank": "AXIS"
  },
  ...
]
```

Fields vary by bank. Check specific parser documentation for full schema.

## Legacy Scripts

Old parser scripts are available in the `archive/` folder for reference:
- `parse_one.py`, `parse_one_enhanced.py`, `parse_one_standard.py`: Single-file parsers
- `parse_remaining_*.py`: Batch recovery scripts
- `sample_enhanced.py`: Enhanced bank detector and parsers

To restore any legacy scripts, copy them back from `archive/` to the root.

## Dependencies

- **pdfplumber**: PDF text and table extraction

See `requirements.txt` for the full dependency list.

## Troubleshooting

### Parser returns 0 transactions

1. Ensure PDF is readable: check file path and format.
2. Try specifying a parser mode: `--mode standard`
3. Verify the bank is supported (see Features section).
4. Check stderr output for parsing errors.

### Module not found errors

Ensure virtual environment is activated and dependencies are installed:
```bash
pip install -r requirements.txt
```

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]
