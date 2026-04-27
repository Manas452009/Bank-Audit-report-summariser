import pdfplumber
import re

def search_financial_patterns(pdf_path):
    print(f"\n=== {pdf_path} ===")
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages[:30]):
            text = page.extract_text()
            if not text:
                continue
            # Search for various deposit/advance/investment patterns
            patterns = [
                (r'Deposits\s*[=:]\s*[\d,.]+', 'deposits_eq'),
                (r'Deposits\s+[\d,.]+', 'deposits_space'),
                (r'Total\s+deposits?\s+[\d,.]+', 'total_deposits'),
                (r'Gross\s+advances?\s+[\d,.]+', 'gross_advances'),
                (r'Total\s+investments?\s+[\d,.]+', 'total_investments'),
                (r'loan.{0,20}deposit.{0,20}ratio', 'ldr_phrase'),
            ]
            for pattern, name in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    for m in matches[:3]:
                        print(f"  Page {page_num+1} [{name}]: {m.strip()}")

search_financial_patterns("annual_report_for_the_year_2023_2024.pdf")
search_financial_patterns("annual_report_for_the_year_2024_2025.pdf")
