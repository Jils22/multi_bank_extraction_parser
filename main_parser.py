import sys
import os
import json
import re
import argparse
import logging
import pdfplumber

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==========================================
# CONSTANTS & PATTERNS
# ==========================================

# --- J&K Bank Constants ---
JK_START_KEYWORDS = [
    "mTFR", "NEFT", "RTGS", "UPI", "By Cash", "To Transfer",
    "IMPS", "ACH", "BPAY", "MB:", "Dr Card", "eTFR", "REJECT",
    "By Inst", "Cheque", "To Clg", "Int. Pd", "Pos", "CMS", "TRF"
]

# --- HDFC Bank Constants ---
HDFC_JUNK_PHRASES = [
    r"nomination\s*[:\-]?\s*not\s*registered",
    r"not\s*registered",
    r"from\s*:\s*\d{2}/\d{2}/\d{4}",
    r"to\s*:\s*\d{2}/\d{2}/\d{4}",
    r"statement\s*of\s*account",
    r"statement\s*summary",
    r"generated\s*on",
    r"generated\s*by",
    r"page\s*no",
    r"hdfc\s*bank",
    r"registered\s*office",
    r"end\s*of\s*statement"
]

HDFC_REF_BLOCKLIST = [
    "account", "branch", "address", "city", "state", "phone", "od", "limit",
    "currency", "email", "cust", "id", "open", "date", "status", "type",
    "ifsc", "micr", "regular", "trade", "current", "holder", "joint", "mr", "ms",
    "m/s", "rtgs", "neft"
]

# --- Kotak Bank Regex ---
KOTAK_RE_MERGED_SL_DATE = re.compile(r"^(\d+)\s+(\d{2}/\d{2}/\d{4})")
KOTAK_RE_DATE = re.compile(r'\d{2}/\d{2}/\d{4}')
KOTAK_RE_AMOUNT = re.compile(r'^-?[\d,]+\.\d{2}$')
KOTAK_RE_DR_CR = re.compile(r'^(DR|CR)$', re.IGNORECASE)

# --- Axis & YesBank Patterns ---
AXIS_DATE_PATTERN = re.compile(r'(\d{2}/\d{2}/\d{4}|\d{1,2}-\w+-\d{2})')
AXIS_AMOUNT_PATTERN = re.compile(r'[\d,]+\.?\d*')
YESBANK_DATE_PATTERN = re.compile(r'(\d{2}/\d{2}/\d{4}|\d{1,2}-\w+-\d{2})')
YESBANK_AMOUNT_PATTERN = re.compile(r'[\d,]+\.?\d*')



# ==========================================
# BANK DETECTION LOGIC
# ==========================================

def detect_bank(pdf_path):
    """
    Detects the bank type based on specific keywords and headers in the first page.
    Follows a strict priority order to avoid false positives.
    
    Args:
        pdf_path (str): Path to the PDF file
        
    Returns:
        str: Bank identifier (KOTAK, JK, HDFC, AXIS, YESBANK, or STANDARD)
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if not pdf.pages:
                logger.warning("PDF has no pages, using STANDARD parser")
                return "STANDARD"
            first_page_text = pdf.pages[0].extract_text() or ""
            text_lower = first_page_text.lower()
            text_nospace = text_lower.replace(" ", "").replace("\n", "")

            # --- PRIORITY 1: UNIQUE KOTAK IDENTIFIERS ---
            if "cust. reln. no." in text_lower or "kotak mahindra bank" in text_lower or "kkbk" in text_nospace:
                logger.info("Detected bank: KOTAK")
                return "KOTAK"
            
            # --- PRIORITY 2: J&K BANK ---
            if "jammu" in text_lower and "kashmir" in text_lower:
                logger.info("Detected bank: J&K")
                return "JK"
            
            # --- PRIORITY 3: HDFC BANK (Strict Mode) ---
            if "hdfc bank" in text_lower or "proc-dl-statement" in text_lower or "hdfcbank" in text_nospace:
                logger.info("Detected bank: HDFC")
                return "HDFC"
            
            # --- PRIORITY 4: AXIS BANK ---
            if "axis bank" in text_lower or "axisbank" in text_nospace:
                logger.info("Detected bank: AXIS")
                return "AXIS"
            
            # --- PRIORITY 5: YES BANK ---
            if "yes bank" in text_lower or "yesbank" in text_nospace:
                logger.info("Detected bank: YESBANK")
                return "YESBANK"
            
            logger.info("No specific bank detected, using STANDARD parser")
            return "STANDARD"
    except Exception as e:
        logger.error(f"Error in bank detection: {e}")
        return "STANDARD"


# ==========================================
# AXIS BANK PARSER (Table + Text)
# ==========================================

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


# ==========================================
# YESBANK PARSER (Table + Text)
# ==========================================

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


# ==========================================
# J&K BANK PARSER (Regex Based)
# ==========================================

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

            # Skip header lines
            if any(x in line for x in ["Value Date", "Account Balance", "Page", "Balance Carried"]):
                continue

            # Check if line starts with a date (New Transaction)
            if date_pattern.match(line):
                parts = line.split()
                if len(parts) < 3:
                    continue

                val_date = parts[0]
                txn_date = parts[1] if re.match(r'\d{2}/\d{2}/\d{4}', parts[1]) else ""

                # Remove dates to process remaining text
                remaining = line.replace(val_date, "", 1).replace(txn_date, "", 1).strip()
                rem_parts = remaining.split()

                cheque_no, ref_no = "", ""
                balance, deposit, withdrawal = "0.0", "0.0", "0.0"

                # Extract Cheque Number if present
                if rem_parts:
                    if cheque_pattern.match(rem_parts[0]):
                        cheque_no = rem_parts.pop(0)
                    elif rem_parts[0] == "-":
                        rem_parts.pop(0)

                # Extract numeric values from the end of the line
                if rem_parts: ref_no = rem_parts.pop()
                if rem_parts and amount_pattern.match(rem_parts[-1]): balance = rem_parts.pop()
                if rem_parts and amount_pattern.match(rem_parts[-1]): deposit = rem_parts.pop()
                if rem_parts and amount_pattern.match(rem_parts[-1]): withdrawal = rem_parts.pop()

                current_desc = " ".join(rem_parts)
                
                # Append any pending description from previous lines
                if pending_next_description:
                    current_desc = pending_next_description + " " + current_desc
                    pending_next_description = ""

                txn = {
                    "Date": val_date,
                    "Description": current_desc,
                    "Ref_No": ref_no,
                    "Debit": withdrawal,
                    "Credit": deposit,
                    "Balance": balance,
                    "Cheque": cheque_no,
                    "Bank": "J&K"
                }
                transactions.append(txn)

            else:
                # Handle multi-line descriptions
                is_start_keyword = any(line.upper().startswith(kw.upper()) for kw in JK_START_KEYWORDS)
                if is_start_keyword:
                    pending_next_description = (pending_next_description + " " + line).strip()
                else:
                    if transactions:
                        transactions[-1]["Description"] += " " + line

    return transactions


# ==========================================
# STANDARD PARSER (Simple Table)
# ==========================================

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


# ==========================================
# HDFC BANK PARSER (Coordinate Based)
# ==========================================

# --- HDFC Helper Functions ---
def hdfc_is_date(t): 
    return bool(re.fullmatch(r"\d{2}/\d{2}/\d{2}", t))

def hdfc_is_amount(t): 
    return bool(re.search(r"\d{1,3}(?:,\d{3})*\.\d{2}", t))

def hdfc_clean_amount(t):
    t = t.replace(",", "")
    m = re.search(r"\d+\.\d{2}", t)
    return float(m.group()) if m else None

def hdfc_is_ref(t): 
    return bool(re.fullmatch(r"\d{10,}", t)) or bool(re.match(r"(MIR|IMPS|UTR|RRN|IBKL|UPI|POS|HDFCN|UBIN)", t))

def hdfc_is_junk_text(text):
    t_lower = text.lower()
    for pattern in HDFC_JUNK_PHRASES:
        if re.search(pattern, t_lower): return True
    return False

def hdfc_is_valid_ref_part(text):
    t_lower = text.lower()
    for bad_word in HDFC_REF_BLOCKLIST:
        if bad_word in t_lower: return False
    if text.isalpha() and not text.isupper(): return False
    return True

def hdfc_get_column_boundaries(page):
    """
    Dynamically determines column boundaries for HDFC statements based on text coordinates.
    """
    words = page.extract_words()
    date_end_xs = [w['x1'] for w in words if hdfc_is_date(w['text']) and w['x0'] < 100]
    narration_min_x = max(date_end_xs) + 2 if date_end_xs else 80

    ref_start_xs = []
    for w in words:
        if w['x0'] > 250:
            if hdfc_is_ref(w['text']): ref_start_xs.append(w['x0'])
    ref_min_x = min(ref_start_xs) - 2 if ref_start_xs else 330
    narration_max_x = ref_min_x

    ref_end_xs = []
    for w in words:
        if w['x0'] > ref_min_x + 20:
            if (hdfc_is_date(w['text']) and w['x0'] > 300) or hdfc_is_amount(w['text']):
                ref_end_xs.append(w['x0'])
    ref_max_x = min(ref_end_xs) - 2 if ref_end_xs else 420
    
    return narration_min_x, narration_max_x, ref_min_x, ref_max_x

def parse_hdfc_statement(path):
    txns = []
    opening_balance = 0.0
    opening_balance_found = False

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            narration_min, narration_max, ref_min, ref_max = hdfc_get_column_boundaries(page)
            words = page.extract_words(use_text_flow=True)
            
            # Group words by Y-coordinate (rows)
            lines = {}
            for w in words: 
                lines.setdefault(round(w["top"]), []).append(w)

            sorted_lines = sorted(lines.items())

            for y, row in sorted_lines:
                row = sorted(row, key=lambda w: w["x0"])
                if not row: continue
                first = row[0]
                line_text = " ".join(w["text"] for w in row)

                # Capture opening balance
                if not opening_balance_found and "opening balance" in line_text.lower():
                    m = re.search(r"opening\s*balance.*?([\d,]+\.\d{2})", line_text, re.IGNORECASE)
                    if m:
                        opening_balance = hdfc_clean_amount(m.group(1))
                        opening_balance_found = True

                if hdfc_is_junk_text(line_text): continue

                # New Transaction Detection
                if hdfc_is_date(first["text"]) and first['x0'] < 100:
                    tx = {
                        "Date": first["text"], "Narration": "", "Value_Date": "", "Ref_No": "",
                        "Withdrawal": 0.0, "Deposit": 0.0, "Closing_Balance": 0.0, "Bank": "HDFC"
                    }
                    narration_words = []
                    ref_words = []

                    for w in row:
                        t = w["text"]; x = w["x0"]
                        if narration_min <= x <= narration_max:
                            narration_words.append(t)
                        elif ref_min <= x <= ref_max:
                            if not hdfc_is_date(t) and not hdfc_is_amount(t):
                                if hdfc_is_valid_ref_part(t): ref_words.append(t)
                        elif x > ref_max:
                            if hdfc_is_date(t) and not tx["Value_Date"]: tx["Value_Date"] = t

                    tx["Narration"] = " ".join(narration_words)
                    tx["Ref_No"] = "".join(ref_words)

                    # Determine Amounts (Withdrawal vs Deposit) based on balance logic
                    amt_objs = [(hdfc_clean_amount(w["text"]), w["x0"]) for w in row if hdfc_is_amount(w["text"]) and w['x0'] > ref_max]

                    if amt_objs:
                        tx["Closing_Balance"] = amt_objs[-1][0]
                        balance_x = amt_objs[-1][1]

                        if len(amt_objs) >= 2:
                            txn_amt = amt_objs[0][0]
                            txn_x = amt_objs[0][1]

                            prev_bal = txns[-1]["Closing_Balance"] if txns else opening_balance

                            if txns or opening_balance_found:
                                if tx["Closing_Balance"] < prev_bal:
                                    tx["Withdrawal"] = txn_amt
                                elif tx["Closing_Balance"] > prev_bal:
                                    tx["Deposit"] = txn_amt
                                else:
                                    # Fallback to coordinate distance if math doesn't help
                                    if (balance_x - txn_x) > 100: tx["Withdrawal"] = txn_amt
                                    else: tx["Deposit"] = txn_amt
                            else:
                                dist = balance_x - txn_x
                                if dist > 110:
                                    tx["Withdrawal"] = txn_amt
                                else:
                                    tx["Deposit"] = txn_amt

                        elif len(amt_objs) == 3:
                            tx["Withdrawal"] = amt_objs[0][0]
                            tx["Deposit"] = amt_objs[1][0]

                    txns.append(tx)

                # Append to previous transaction (Multi-line)
                elif txns:
                    if hdfc_is_junk_text(line_text): continue
                    extra_narr = []
                    extra_ref = []
                    for w in row:
                        if narration_min <= w["x0"] <= narration_max:
                            if not hdfc_is_amount(w["text"]) and not hdfc_is_date(w["text"]):
                                extra_narr.append(w["text"])
                        elif ref_min <= w["x0"] <= ref_max:
                            if not hdfc_is_amount(w["text"]) and not hdfc_is_date(w["text"]):
                                if hdfc_is_valid_ref_part(w["text"]):
                                    extra_ref.append(w["text"])
                    if extra_narr:
                        line_content = " ".join(extra_narr)
                        if not hdfc_is_junk_text(line_content):
                            txns[-1]["Narration"] += " " + line_content
                    if extra_ref: txns[-1]["Ref_No"] += "".join(extra_ref)

    # Final Cleanup
    for t in txns:
        t["Narration"] = t["Narration"].strip()
        t["Narration"] = re.sub(r"(?i)statement\s*summary.*", "", t["Narration"])
        t["Narration"] = re.sub(r"(?i)generated\s*on.*", "", t["Narration"])
        t["Ref_No"] = t["Ref_No"].replace(" ", "").strip()
    return txns


# ==========================================
# KOTAK BANK PARSER (Table Based)
# ==========================================

# --- Kotak Helper Functions ---
def kotak_is_date(text): 
    return bool(KOTAK_RE_DATE.search(str(text)))

def kotak_is_amount(text):
    clean_text = str(text).replace(" ", "").replace(",", "")
    return bool(KOTAK_RE_AMOUNT.match(clean_text))

def kotak_is_dr_cr(text): 
    return bool(KOTAK_RE_DR_CR.match(str(text).strip()))

def kotak_repair_merged_columns(row):
    """
    Repairs rows where the Serial Number and Date are merged into one cell.
    """
    if not row or not row[0]: return row
    match = KOTAK_RE_MERGED_SL_DATE.match(str(row[0]).strip())
    if match:
        sl_no, date_str = match.groups()
        remaining = str(row[0])[match.end():].strip()
        new_row = [sl_no, date_str]
        if remaining: new_row.append(remaining)
        new_row.extend(row[1:])
        return new_row
    return row

def parse_kotak_statement(pdf_path):
    transactions = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables(table_settings={"vertical_strategy": "text", "horizontal_strategy": "text", "snap_tolerance": 3})
            for table in tables:
                if not table: continue
                
                # Identify Header Row
                header_idx = -1
                for i, row in enumerate(table):
                    row_text = " ".join([str(c) for c in row if c]).lower()
                    if "date" in row_text and "balance" in row_text:
                        header_idx = i
                        break
                start_row = header_idx + 1 if header_idx != -1 else 0

                for raw_row in table[start_row:]:
                    cleaned_row = [str(c).strip().replace('\n', ' ') if c else "" for c in raw_row]
                    row = kotak_repair_merged_columns(cleaned_row)
                    
                    # Find Date Column Index
                    date_idx = -1
                    for idx, cell in enumerate(row):
                        if kotak_is_date(cell):
                            date_idx = idx
                            break
                    
                    if date_idx != -1:
                        sl_no = row[date_idx-1] if date_idx > 0 else ""
                        date_val = row[date_idx]
                        tx = {
                            "Sl. No.": sl_no, "Date": date_val, "Description": "", "Chq/Ref number": "",
                            "Amount": "0.00", "Dr/Cr": "", "Balance": "0.00", "Balance_Dr/Cr": "", "Bank": "KOTAK"
                        }
                        
                        remaining = [c for c in row[date_idx+1:] if c.strip()]
                        if remaining and kotak_is_dr_cr(remaining[-1]): tx["Balance_Dr/Cr"] = remaining.pop()
                        if remaining and kotak_is_amount(remaining[-1]): tx["Balance"] = remaining.pop()
                        if remaining and kotak_is_dr_cr(remaining[-1]): tx["Dr/Cr"] = remaining.pop()
                        if remaining and kotak_is_amount(remaining[-1]): tx["Amount"] = remaining.pop()
                        
                        ref_candidates = []
                        desc_parts = []
                        for item in remaining:
                            if re.match(r'^(UPI|IMPS|NEFT|RTGS|MB)-', item) or (item.isdigit() and len(item)>6):
                                ref_candidates.append(item)
                            else: 
                                desc_parts.append(item)
                        
                        tx["Description"] = " ".join(desc_parts)
                        tx["Chq/Ref number"] = " ".join(ref_candidates)
                        transactions.append(tx)

                    elif transactions and len(row) > 0:
                        # Append multiline description
                        extra_text = " ".join([c for c in row if c.strip()])
                        is_garbage = re.search(r"(Page\s+\d+|Account\s+Statement|Opening\s+Balance)", extra_text, re.IGNORECASE)
                        if extra_text and not is_garbage: 
                            transactions[-1]["Description"] += " " + extra_text

    # Final Cleanup
    for t in transactions:
        t["Description"] = t["Description"].strip()
        t["Amount"] = t["Amount"].replace(',', '')
        t["Balance"] = t["Balance"].replace(',', '')
    logger.info(f"Kotak parser: Extracted {len(transactions)} transactions")
    return transactions




# ==========================================
# MAIN EXECUTION BLOCK
# ==========================================

def parse_pdf(pdf_path, out_json, mode='auto'):
    """
    Main parser function that routes to appropriate parser based on bank type or mode.
    
    Args:
        pdf_path (str): Path to the PDF file
        out_json (str): Output JSON file path
        mode (str): Parser mode ('auto', 'standard', 'AXIS', 'YESBANK', 'HDFC', 'KOTAK', 'JK')
        
    Returns:
        int: 0 on success, 1 on failure
    """
    data = []
    try:
        if mode == 'standard':
            logger.info("Using STANDARD parser")
            with pdfplumber.open(pdf_path) as pdf:
                data = parse_with_simple_table(pdf)
                if not data:
                    logger.info("Standard parser found no transactions, trying J&K regex parser")
                    data = parse_with_regex_jk(pdf)
        else:
            bank = detect_bank(pdf_path) if mode == 'auto' else mode.upper()
            logger.info(f"Using {bank} parser")
            
            if bank == 'AXIS':
                data = parse_axis_statement(pdf_path)
            elif bank == 'YESBANK':
                data = parse_yesbank_statement(pdf_path)
            elif bank == 'HDFC':
                data = parse_hdfc_statement(pdf_path)
            elif bank == 'KOTAK':
                data = parse_kotak_statement(pdf_path)
            elif bank == 'JK':
                with pdfplumber.open(pdf_path) as pdf:
                    data = parse_with_regex_jk(pdf)
            else:
                logger.info("Using fallback STANDARD parser")
                with pdfplumber.open(pdf_path) as pdf:
                    data = parse_with_simple_table(pdf)
                    if not data:
                        logger.info("Standard parser found no transactions, trying J&K regex parser")
                        data = parse_with_regex_jk(pdf)
    except Exception as e:
        logger.error(f"Parse error: {e}", exc_info=True)
        data = []

    if data:
        try:
            with open(out_json, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"Successfully written {len(data)} transactions to {out_json}")
            print(f"transactions:{len(data)}")
            return 0
        except Exception as e:
            logger.error(f"Error writing output file: {e}", exc_info=True)
            print(f"transactions:0")
            return 1
    else:
        logger.warning("No transactions extracted from PDF")
        print("transactions:0")
        return 1


def main():
    """Main entry point for the PDF parser."""
    parser = argparse.ArgumentParser(
        description='Multi-Bank PDF Statement Parser - Automatic bank detection and transaction extraction',
        epilog='Examples:\n  python main_parser.py statement.pdf output.json\n  python main_parser.py statement.pdf output.json --mode AXIS',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('pdf_path', help='Path to the PDF file to parse')
    parser.add_argument('out_json', help='Output JSON file path')
    parser.add_argument(
        '--mode', 
        choices=['auto', 'standard', 'AXIS', 'YESBANK', 'HDFC', 'KOTAK', 'JK'], 
        default='auto',
        help='Parsing mode (default: auto detection)'
    )
    parser.add_argument(
        '--verbose', 
        action='store_true',
        help='Enable verbose logging'
    )
    args = parser.parse_args()
    
    # Set logging level based on verbose flag
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    logger.info(f"Starting PDF parser - Mode: {args.mode}")
    
    if not os.path.exists(args.pdf_path):
        logger.error(f"PDF file not found: {args.pdf_path}")
        print(f"Error: PDF file not found: {args.pdf_path}", file=sys.stderr)
        sys.exit(1)
    
    if not args.pdf_path.lower().endswith('.pdf'):
        logger.warning(f"Input file does not have .pdf extension: {args.pdf_path}")
    
    rc = parse_pdf(args.pdf_path, args.out_json, mode=args.mode)
    logger.info(f"Parser finished with return code: {rc}")
    sys.exit(rc)


if __name__ == '__main__':
    main()
