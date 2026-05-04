import pdfplumber
import re

def check_pdf(pdf_path):
    print(f"\n=== Checking {pdf_path} ===")
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages[:10]):
            tables = page.extract_tables({"vertical_strategy": "lines", "horizontal_strategy": "lines"})
            print(f"Page {page_num+1}: {len(tables)} tables")
            for idx, table in enumerate(tables):
                if not table:
                    continue
                print(f"  Table {idx+1}: {len(table)} rows x {len(table[0]) if table[0] else 0} cols")
                # Check numeric count
                all_text = " ".join([" ".join(str(cell) for cell in row if cell) for row in table])
                numbers = re.findall(r"\d+\.?\d*", all_text)
                print(f"    Numeric values: {len(numbers)}")
                # Show first 2 rows
                for row_idx, row in enumerate(table[:2]):
                    print(f"    Row {row_idx+1}: {[str(cell)[:40] for cell in row]}")

check_pdf("demo_bank_audit_input.pdf")
check_pdf("annual_report_for_the_year_2023_2024.pdf")
check_pdf("annual_report_for_the_year_2024_2025.pdf")
