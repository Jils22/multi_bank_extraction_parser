# Multi-Bank Statement PDF Parser

A robust Python parser for extracting transactions from bank statement PDFs with automatic bank detection and multiple parsing strategies.

## 🎯 Features

- **🏦 Multi-bank Support**: Detects and parses statements from 6+ banks automatically
- **🔍 Smart Detection**: Analyzes PDF content to identify bank type
- **📊 Multiple Strategies**: Combines table extraction, regex, and text-based parsing
- **📁 Fallback Parsing**: Gracefully handles edge cases with fallback parsers
- **📋 Clean JSON Output**: Structured transaction data ready for integration
- **⚙️ CLI Interface**: Simple command-line usage with optional mode override

## 🏦 Supported Banks

| Bank | Method | Detection |
|------|--------|-----------|
| **Axis Bank** | Table + Text | Keyword matching |
| **YesBank** | Table + Text | Keyword matching |
| **J&K Bank** | Regex-based | "Jammu" + "Kashmir" |
| **HDFC** | Coordinate-based | "HDFC Bank" keyword |
| **Kotak Mahindra** | Table-based | "Cust. Reln. No." |
| **SBI/Standard** | Table + Regex | Fallback parser |

## 📦 Installation

### Prerequisites
- Python 3.7 or higher
- pip (Python package manager)

### Setup

```bash
# Clone the repository
git clone https://github.com/Jils22/multi_bank_extraction_parser.git
cd multi_bank_extraction_parser

# Create virtual environment
python -m venv .venv

# Activate environment
# Windows:
.\.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## 🚀 Quick Start

### Auto-detect Bank Type (Recommended)

```bash
python main_parser.py "path/to/statement.pdf" "output/transactions.json"
```

### Specify Bank Type

```bash
python main_parser.py "statement.pdf" "output.json" --mode AXIS
python main_parser.py "statement.pdf" "output.json" --mode KOTAK
```

### Available Modes

```
auto          Auto-detect bank (default)
standard      SBI/generic table parser
AXIS          Force Axis Bank parser
YESBANK       Force YesBank parser
JK            Force J&K Bank parser
HDFC          Force HDFC Bank parser
KOTAK         Force Kotak Bank parser
```

## 📊 Output Format

The parser generates a JSON array of transactions:

```json
[
  {
    "Date": "01/04/2024",
    "Description": "NEFT Transfer - ABC Ltd",
    "Amount": "50000.00",
    "Balance": "150000.00",
    "Bank": "AXIS"
  },
  {
    "Date": "02/04/2024",
    "Description": "UPI Payment",
    "Debit": "500.00",
    "Credit": "0.00",
    "Balance": "149500.00",
    "Bank": "YESBANK"
  }
]
```

**Note**: Field names vary by bank. Common fields include `Date`, `Description`, `Amount`/`Debit`/`Credit`, `Balance`, and `Bank`.

## 📁 Project Structure

```
multi_bank_extraction_parser/
├── main_parser.py              # Main parser (all logic consolidated)
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── .gitignore                  # Git ignore rules
├── archive/                    # Legacy parser scripts (reference)
│   └── *.py                    # Individual bank parsers (archived)
└── .venv/                      # Virtual environment (git-ignored)
```

## 🛠️ How It Works

1. **Bank Detection**: Analyzes first page of PDF for bank-specific keywords
2. **Parser Selection**: Chooses appropriate parsing strategy based on detected bank
3. **Transaction Extraction**:
   - **Table-based**: Extracts structured tables (Axis, YesBank, Kotak)
   - **Regex-based**: Uses pattern matching for text-based PDFs (J&K Bank)
   - **Coordinate-based**: Maps column positions from PDF layout (HDFC)
4. **Fallback Strategy**: Tries alternative parser if primary method fails
5. **JSON Export**: Writes clean transaction data to output file

## 🐛 Troubleshooting

### Parser Returns 0 Transactions

**Solution 1: Try Standard Parser**
```bash
python main_parser.py "statement.pdf" "output.json" --mode standard
```

**Solution 2: Check PDF Format**
- Ensure PDF is text-based (not scanned image)
- Try opening PDF with a text reader to verify content

**Solution 3: Specify Bank Mode**
```bash
python main_parser.py "statement.pdf" "output.json" --mode AXIS
```

### Module Not Found Error

```bash
# Verify virtual environment is activated
.venv\Scripts\activate  # Windows

# Reinstall dependencies
pip install -r requirements.txt
```

## 📝 Example Usage

### Single PDF Parsing
```bash
python main_parser.py "axis_statement_jan2024.pdf" "output/axis_jan.json"
```

### Batch Processing
```bash
for file in pdfs/*.pdf; do
  python main_parser.py "$file" "outputs/$(basename "$file" .pdf).json"
done
```

## 📚 Technical Details

### Parser Strategies

- **pdfplumber Table Extraction**: Uses text-flow algorithms for structured data
- **Regex Patterns**: Matches transaction keywords and amount formats
- **Coordinate-Based**: Maps word positions to identify column boundaries
- **Multi-line Handling**: Captures descriptions spanning multiple lines

### Bank Detection Priority
1. Kotak (checks "Cust. Reln. No.")
2. J&K Bank (checks "Jammu" + "Kashmir")
3. Axis Bank (checks "AXIS BANK")
4. YesBank (checks "YES BANK")
5. HDFC (checks "HDFC BANK")
6. Standard/SBI (fallback)

## 🤝 Contributing

Contributions welcome! To add support for a new bank:

1. Add detection keyword in `detect_bank()`
2. Implement `parse_<bank>_statement()` function
3. Test with sample PDF
4. Submit pull request

## 📄 License

[Specify your license - MIT, Apache 2.0, etc.]

## 👤 Author

Jils22

## 🙏 Acknowledgments

- Built with [pdfplumber](https://github.com/jsvine/pdfplumber)
- Supports multiple Indian banks
