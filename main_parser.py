import sys
import os
import json
import re
import argparse
import importlib.util
import pdfplumber

# --- Detection & Parsers (consolidated from previous modules) ---

JK_START_KEYWORDS = [
    "mTFR", "NEFT", "RTGS", "UPI", "By Cash", "To Transfer",
    "IMPS", "ACH", "BPAY", "MB:", "Dr Card", "eTFR", "REJECT",
    "By Inst", "Cheque", "To Clg", "Int. Pd", "Pos", "CMS", "TRF"
]

AXIS_DATE_PATTERN = re.compile(r'(\d{2}/\d{2}/\d{4}|\d{1,2}-\w+-\d{2})')
AXIS_AMOUNT_PATTERN = re.compile(r'[\d,]+\.?\d*')
YESBANK_DATE_PATTERN = re.compile(r'(\d{2}/\d{2}/\d{4}|\d{1,2}-\w+-\d{2})')
YESBANK_AMOUNT_PATTERN = re.compile(r'[\d,]+\.?\d*')


def detect_bank(pdf_path):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if not pdf.pages:
                return "STANDARD"
            first_page_text = pdf.pages[0].extract_text() or ""
            text_lower = first_page_text.lower()
            text_nospace = text_lower.replace(" ", "").replace("\n", "")

            if "cust. reln. no." in text_lower or "kotak mahindra bank" in text_lower or "kkbk" in text_nospace:
                return "KOTAK"
            if "jammu" in text_lower and "kashmir" in text_lower:
                return "JK"
            if "axis bank" in text_lower or "axisbank" in text_nospace:
                return "AXIS"
            if "yes bank" in text_lower or "yesbank" in text_nospace:
                return "YESBANK"
            if "hdfc bank" in text_lower or "proc-dl-statement" in text_lower or "hdfcbank" in text_nospace:
                return "HDFC"
            return "STANDARD"
    except Exception:
        return "STANDARD"


def parse_axis_statement(pdf_path):
    transactions = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables(table_settings={
                    "vertical_strategy": "text",
                    "horizontal_strategy": "text",
                    "snap_tolerance": 3
                })

                if not tables:
                    text = page.extract_text()
                    if text:
                        transactions.extend(_parse_axis_text(text))
                    continue

                for table in tables:
                    if not table:
                        continue
                    header_idx = -1
                    for i, row in enumerate(table):
                        row_text = " ".join([str(c) for c in row if c]).lower()
                        if ("date" in row_text or "transaction" in row_text) and "amount" in row_text:
                            header_idx = i
                            break
                    if header_idx == -1 and len(table) > 0:
                        header_idx = 0
                    start_row = header_idx + 1 if header_idx != -1 else 0
                    for row in table[start_row:]:
                        row = [str(c).strip() if c else "" for c in row]
                        if not any(row) or len(row) < 2:
                            continue
                        txn = {"Date": "", "Description": "", "Amount": "0.00", "Balance": "0.00", "Bank": "AXIS"}
                        for i, cell in enumerate(row):
                            if i == 0 and AXIS_DATE_PATTERN.match(cell):
                                txn["Date"] = cell
                            elif i == len(row) - 1 and AXIS_AMOUNT_PATTERN.match(cell):
                                txn["Balance"] = cell
                            elif i == len(row) - 2 and AXIS_AMOUNT_PATTERN.match(cell):
                                txn["Amount"] = cell
                            else:
                                txn["Description"] = (txn["Description"] + " " + cell).strip() if cell else txn["Description"]
                        if txn["Date"]:
                            transactions.append(txn)
    except Exception as e:
        print(f"Axis parser error: {e}", file=sys.stderr)
    return transactions


def _parse_axis_text(text):
    transactions = []
    lines = text.split('\n')
    date_pattern = re.compile(r'^(\d{2}/\d{2}/\d{4})')
    current_txn = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if date_pattern.match(line):
            if current_txn:
                transactions.append(current_txn)
            parts = line.split()
            current_txn = {"Date": parts[0] if parts else "", "Description": " ".join(parts[1:]) if len(parts) > 1 else "", "Amount": "0.00", "Balance": "0.00", "Bank": "AXIS"}
        elif current_txn:
            current_txn["Description"] += " " + line
    if current_txn:
        transactions.append(current_txn)
    return transactions


def parse_yesbank_statement(pdf_path):
    transactions = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables(table_settings={
                    "vertical_strategy": "text",
                    "horizontal_strategy": "text",
                    "snap_tolerance": 3
                })
                if not tables:
                    text = page.extract_text()
                    if text:
                        transactions.extend(_parse_yesbank_text(text))
                    continue
                for table in tables:
                    if not table:
                        continue
                    header_idx = -1
                    for i, row in enumerate(table):
                        row_text = " ".join([str(c) for c in row if c]).lower()
                        if ("date" in row_text or "transaction" in row_text) and ("amount" in row_text or "balance" in row_text):
                            header_idx = i
                            break
                    if header_idx == -1 and len(table) > 0:
                        header_idx = 0
                    start_row = header_idx + 1 if header_idx != -1 else 0
                    for row in table[start_row:]:
                        row = [str(c).strip() if c else "" for c in row]
                        if not any(row) or len(row) < 2:
                            continue
                        txn = {"Date": "", "Description": "", "Debit": "0.00", "Credit": "0.00", "Balance": "0.00", "Bank": "YESBANK"}
                        for i, cell in enumerate(row):
                            if i == 0 and YESBANK_DATE_PATTERN.match(cell):
                                txn["Date"] = cell
                            elif i == len(row) - 1 and YESBANK_AMOUNT_PATTERN.match(cell):
                                txn["Balance"] = cell
                            else:
                                txn["Description"] = (txn["Description"] + " " + cell).strip() if cell else txn["Description"]
                        if txn["Date"]:
                            transactions.append(txn)
    except Exception as e:
        print(f"YesBank parser error: {e}", file=sys.stderr)
    return transactions


def _parse_yesbank_text(text):
    transactions = []
    lines = text.split('\n')
    date_pattern = re.compile(r'^(\d{2}/\d{2}/\d{4})')
    current_txn = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if date_pattern.match(line):
            if current_txn:
                transactions.append(current_txn)
            parts = line.split()
            current_txn = {"Date": parts[0] if parts else "", "Description": " ".join(parts[1:]) if len(parts) > 1 else "", "Debit": "0.00", "Credit": "0.00", "Balance": "0.00", "Bank": "YESBANK"}
        elif current_txn:
            current_txn["Description"] += " " + line
    if current_txn:
        transactions.append(current_txn)
    return transactions


def parse_with_simple_table(pdf):
    transactions = []
    for page in pdf.pages:
        table = page.extract_table()
        if not table:
            continue
        headers = table[0]
        for row in table[1:]:
            if not any(row):
                continue
            txn = {}
            for i, header in enumerate(headers):
                header_text = header.strip().replace(" ", "_") if header else f"col_{i}"
                value = row[i].strip() if (i < len(row) and row[i]) else ""
                txn[header_text] = value
            txn["Bank"] = "Standard/SBI"
            transactions.append(txn)
    return transactions


def parse_with_regex_jk(pdf):
    transactions = []
    date_pattern = re.compile(r'^(\d{2}/\d{2}/\d{4})')
    amount_pattern = re.compile(r'^-?[\d,]+(\.\d+)?$')
    cheque_pattern = re.compile(r'^\d{6}$')
    pending_next_description = ""
    for page in pdf.pages:
        text = page.extract_text(x_tolerance=2, y_tolerance=5)
        if not text:
            continue
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if any(x in line for x in ["Value Date", "Account Balance", "Page", "Balance Carried"]):
                continue
            if date_pattern.match(line):
                parts = line.split()
                if len(parts) < 3:
                    continue
                val_date = parts[0]
                txn_date = parts[1] if re.match(r'\d{2}/\d{2}/\d{4}', parts[1]) else ""
                remaining = line.replace(val_date, "", 1).replace(txn_date, "", 1).strip()
                rem_parts = remaining.split()
                cheque_no, ref_no = "", ""
                balance, deposit, withdrawal = "0.0", "0.0", "0.0"
                if rem_parts:
                    if cheque_pattern.match(rem_parts[0]):
                        cheque_no = rem_parts.pop(0)
                    elif rem_parts[0] == "-":
                        rem_parts.pop(0)
                if rem_parts:
                    ref_no = rem_parts.pop()
                if rem_parts and amount_pattern.match(rem_parts[-1]):
                    balance = rem_parts.pop()
                if rem_parts and amount_pattern.match(rem_parts[-1]):
                    deposit = rem_parts.pop()
                if rem_parts and amount_pattern.match(rem_parts[-1]):
                    withdrawal = rem_parts.pop()
                current_desc = " ".join(rem_parts)
                if pending_next_description:
                    current_desc = pending_next_description + " " + current_desc
                    pending_next_description = ""
                txn = {"Date": val_date, "Description": current_desc, "Ref_No": ref_no, "Debit": withdrawal, "Credit": deposit, "Balance": balance, "Cheque": cheque_no, "Bank": "J&K"}
                transactions.append(txn)
            else:
                is_start_keyword = any(line.upper().startswith(kw.upper()) for kw in JK_START_KEYWORDS)
                if is_start_keyword:
                    pending_next_description = (pending_next_description + " " + line).strip()
                else:
                    if transactions:
                        transactions[-1]["Description"] += " " + line
    return transactions


def parse_pdf(pdf_path, out_json, mode='auto'):
    data = []
    try:
        if mode == 'standard':
            with pdfplumber.open(pdf_path) as pdf:
                data = parse_with_simple_table(pdf)
                if not data:
                    data = parse_with_regex_jk(pdf)
        else:
            bank = detect_bank(pdf_path) if mode == 'auto' else mode.upper()
            if bank == 'AXIS':
                data = parse_axis_statement(pdf_path)
            elif bank == 'YESBANK':
                data = parse_yesbank_statement(pdf_path)
            elif bank == 'HDFC' or bank == 'KOTAK':
                sample_path = os.path.join(os.getcwd(), '.venv', 'sample.py')
                if os.path.exists(sample_path):
                    spec = importlib.util.spec_from_file_location('sample', sample_path)
                    sample = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(sample)
                    if bank == 'HDFC':
                        data = sample.parse_hdfc_statement(pdf_path)
                    else:
                        data = sample.parse_kotak_statement(pdf_path)
                else:
                    with pdfplumber.open(pdf_path) as pdf:
                        data = parse_with_simple_table(pdf)
            elif bank == 'JK':
                with pdfplumber.open(pdf_path) as pdf:
                    data = parse_with_regex_jk(pdf)
            else:
                with pdfplumber.open(pdf_path) as pdf:
                    data = parse_with_simple_table(pdf)
                    if not data:
                        data = parse_with_regex_jk(pdf)
    except Exception as e:
        print(f"parse_error:{e}", file=sys.stderr)
        data = []

    if data:
        with open(out_json, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"transactions:{len(data)}")
        return 0
    else:
        print("transactions:0")
        return 1


def main():
    parser = argparse.ArgumentParser(description='Main parser: auto-selects or uses a mode')
    parser.add_argument('pdf_path')
    parser.add_argument('out_json')
    parser.add_argument('--mode', choices=['auto', 'standard', 'enhanced', 'AXIS', 'YESBANK', 'HDFC', 'KOTAK', 'JK'], default='auto')
    args = parser.parse_args()
    rc = parse_pdf(args.pdf_path, args.out_json, mode=args.mode)
    sys.exit(rc)


if __name__ == '__main__':
    main()
