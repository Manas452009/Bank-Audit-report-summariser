import pdfplumber
import re

def find_financial_sections(pdf_path):
    print(f"\n=== {pdf_path} ===")
    keywords = ['balance sheet', 'profit and loss', 'statement of profit', 'financial position', 
                'assets', 'liabilities', 'equity', 'deposits', 'advances', 'income', 'expenditure']
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                continue
            lower = text.lower()
            for kw in keywords:
                if kw in lower:
                    # Find the line containing keyword
                    for line in text.split('\n'):
                        if kw in line.lower():
                            print(f"  Page {page_num+1} [{kw}]: {line.strip()[:150]}")

find_financial_sections("annual_report_for_the_year_2023_2024.pdf")
find_financial_sections("annual_report_for_the_year_2024_2025.pdf")
