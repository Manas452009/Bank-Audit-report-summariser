import pdfplumber, re

def clean_text(text):
    if not text: return ""
    text = re.sub(r"(.)\1{2,}", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def check_annual_report(pdf_path):
    print(f"\n=== Checking {pdf_path} ===")
    with pdfplumber.open(pdf_path) as pdf:
        all_text = ""
        structured_hints = []
        for page_num, page in enumerate(pdf.pages[:20]):
            raw_text = page.extract_text()
            if raw_text:
                all_text += raw_text + "\n"
                paragraphs = re.split(r"\n\s*\n", raw_text)
                for para in paragraphs:
                    cleaned = clean_text(para)
                    # Check for financial patterns
                    has_deposits = re.search(r'deposits?\s*[:\s]\s*[\d,.]+', cleaned, re.IGNORECASE)
                    has_advances = re.search(r'advances?\s*[:\s]\s*[\d,.]+', cleaned, re.IGNORECASE)
                    has_investments = re.search(r'investments?\s*[:\s]\s*[\d,.]+', cleaned, re.IGNORECASE)
                    if has_deposits or has_advances or has_investments:
                        structured_hints.append({
                            'page': page_num+1,
                            'text': cleaned[:200],
                            'patterns': {'deposits': bool(has_deposits), 'advances': bool(has_advances), 'investments': bool(has_investments)}
                        })
        print(f"Total extracted text length: {len(all_text)} chars")
        print(f"Paragraphs with financial patterns: {len(structured_hints)}")
        for hint in structured_hints[:5]:
            print(f"  Page {hint['page']}: {hint['patterns']}")
            print(f"    Preview: {hint['text'][:150]}")

check_annual_report("annual_report_for_the_year_2023_2024.pdf")
check_annual_report("annual_report_for_the_year_2024_2025.pdf")
