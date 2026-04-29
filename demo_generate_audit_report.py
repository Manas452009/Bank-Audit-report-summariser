from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
import io
import re
import pandas as pd
import pdfplumber

INPUT_PDF = "demo_bank_audit_input.pdf"
OUTPUT_PDF = "demo_bank_audit_report.pdf"

sample_paragraph = (
    "This sample bank audit report contains key balance sheet information for several branches. "
    "The table below shows deposits, advances, and investments for each business unit, "
    "which is used to compute loan-to-deposit ratios and liquidity review metrics."
)

sample_table_data = [
    ["Branch", "Deposits", "Advances", "Investments", "Assets"],
    ["North Region", "120000", "98000", "36000", "230000"],
    ["South Region", "85000", "76000", "28000", "170000"],
    ["East Region", "142000", "130000", "52000", "250000"],
    ["West Region", "96000", "89000", "45000", "190000"],
]


def create_demo_pdf(path: str):
    doc = SimpleDocTemplate(path, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("DEMO BANK AUDIT INPUT REPORT", styles["Title"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph(sample_paragraph, styles["BodyText"]))
    story.append(Spacer(1, 20))

    table = Table(sample_table_data, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4f81bd")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
    ]))

    story.append(table)
    doc.build(story)
    print(f"Created demo input PDF: {path}")


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"(.)\1{2,}", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_text_and_tables(pdf_path: str):
    text_data = []
    table_data = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            raw_text = page.extract_text()
            if raw_text:
                paragraphs = re.split(r"\n\s*\n", raw_text)
                for para in paragraphs:
                    para = clean_text(para)
                    if len(para) < 100:
                        continue
                    if para.count(".") < 1:
                        continue
                    text_data.append({"page": page_num + 1, "text": para})

            for table in page.extract_tables({"vertical_strategy": "lines", "horizontal_strategy": "lines"}):
                if not table:
                    continue
                cleaned_table = []
                for row in table:
                    if any(cell is not None and str(cell).strip() != "" for cell in row):
                        cleaned_table.append([str(cell).strip() if cell else "" for cell in row])
                if len(cleaned_table) < 2:
                    continue
                table_data.append({"page": page_num + 1, "table": cleaned_table})

    return text_data, table_data


def is_high_value_financial_table(table):
    text = " ".join([" ".join(row) for row in table]).lower()
    strong_headers = [
        "npa", "gross npa", "net npa", "provision", "write off",
        "advances", "liabilities", "assets", "borrowings", "exposure"
    ]
    reject_keywords = [
        "strategy", "strategic", "customer", "esg", "sustainability",
        "value creation", "stakeholder", "digital", "governance",
        "subsidiary", "market positioning", "progress", "target", "penetration"
    ]
    if any(k in text for k in reject_keywords):
        return False
    if not any(k in text for k in strong_headers):
        return False
    numbers = re.findall(r"\d+\.?\d*", text)
    if len(numbers) < 15:
        return False
    if text.count("%") > 0 and len(numbers) < 10:
        return False
    if len(table) < 3:
        return False
    if max(len(row) for row in table) < 2:
        return False
    return True


def clean_field_name(name: str) -> str:
    name = re.sub(r"\d+", "", name)
    name = re.sub(r"[^a-zA-Z\s]", "", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip()


def clean_value(value: str) -> str:
    return value.replace(",", "").strip()


def table_to_structured_text(table):
    headers = table[0]
    rows = table[1:]
    structured_data = []
    for row in rows:
        row_text = []
        for h, v in zip(headers, row):
            if v and v != "-":
                clean_h = clean_field_name(h)
                clean_v = clean_value(v)
                if clean_h:
                    row_text.append(f"{clean_h}: {clean_v}")
        if row_text:
            structured_data.append(", ".join(row_text)
            )
    return structured_data


def convert_all_tables(financial_tables):
    converted = []
    for item in financial_tables:
        page = item["page"]
        table = item["table"]
        for row in table_to_structured_text(table):
            converted.append({"page": page, "text": row})
    return converted


def risk_level(ldr):
    if pd.isna(ldr):
        return "Unknown"
    if ldr > 0.90:
        return "High"
    if ldr > 0.70:
        return "Moderate"
    return "Low"


def comments(row):
    notes = []
    if row["LDR"] > 1:
        notes.append("Advances exceed deposits")
    elif row["LDR"] > 0.85:
        notes.append("Aggressive lending")
    elif row["LDR"] < 0.60:
        notes.append("Conservative lending")
    if row["INV_RATIO"] > 2:
        notes.append("Very high investment concentration")
    elif row["INV_RATIO"] > 1:
        notes.append("High investments")
    if row["deposits"] < 10000:
        notes.append("Low deposit base")
    return "; ".join(notes)


def perform_audit_analysis(structured_rows):
    records = []
    for item in structured_rows:
        text = item["text"]
        d = re.search(r"Deposits:\s*([\d\.]+)", text)
        a = re.search(r"Advances:\s*([\d\.]+)", text)
        inv = re.search(r"Investments:\s*([\d\.]+)", text)
        records.append({
            "page": item["page"],
            "deposits": float(d.group(1)) if d else None,
            "advances": float(a.group(1)) if a else None,
            "investments": float(inv.group(1)) if inv else None,
        })

    df = pd.DataFrame(records)
    df = df.dropna(subset=["deposits", "advances", "investments"], how="all")
    df["LDR"] = df.apply(lambda row: row["advances"] / row["deposits"] if row["deposits"] and row["deposits"] > 0 else float('nan'), axis=1)
    df["INV_RATIO"] = df.apply(lambda row: row["investments"] / row["deposits"] if row["deposits"] and row["deposits"] > 0 else float('nan'), axis=1)
    df["risk_level"] = df["LDR"].apply(risk_level)
    df["observations"] = df.apply(comments, axis=1)

    total_deposits = df["deposits"].sum()
    total_advances = df["advances"].sum()
    total_investments = df["investments"].sum()
    overall_ldr = total_advances / total_deposits if total_deposits > 0 else 0
    overall_inv_ratio = total_investments / total_deposits if total_deposits > 0 else 0
    overall_risk = "High" if overall_ldr > 0.90 else "Moderate" if overall_ldr > 0.70 else "Low"

    summary = {
        "total_rows_analyzed": len(df),
        "total_deposits": round(float(total_deposits), 2),
        "total_advances": round(float(total_advances), 2),
        "total_investments": round(float(total_investments), 2),
        "overall_ldr": round(float(overall_ldr), 4),
        "overall_investment_ratio": round(float(overall_inv_ratio), 4),
        "overall_risk": overall_risk,
        "high_risk_rows": int((df["risk_level"] == "High").sum()),
        "moderate_risk_rows": int((df["risk_level"] == "Moderate").sum()),
        "low_risk_rows": int((df["risk_level"] == "Low").sum()),
    }
    return df, summary


def build_output_pdf(path: str, summary: dict, df: pd.DataFrame):
    doc = SimpleDocTemplate(path, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("BANK AUDIT REPORT SUMMARY", styles["Title"]))
    story.append(Spacer(1, 14))

    story.append(Paragraph("Executive Summary:", styles["Heading2"]))
    lines = [
        f"Total rows analyzed: {summary['total_rows_analyzed']}",
        f"Total deposits: {summary['total_deposits']:,}",
        f"Total advances: {summary['total_advances']:,}",
        f"Total investments: {summary['total_investments']:,}",
        f"Overall Loan-to-Deposit Ratio: {summary['overall_ldr']:.2%}",
        f"Overall Investment Ratio: {summary['overall_investment_ratio']:.2%}",
        f"Overall risk rating: {summary['overall_risk']}",
    ]
    for line in lines:
        story.append(Paragraph(line, styles["BodyText"]))
        story.append(Spacer(1, 6))
    story.append(Spacer(1, 16))

    story.append(Paragraph("Detailed Analysis Table", styles["Heading2"]))
    data = [df.columns.tolist()] + df.astype(str).values.tolist()
    table = Table(data, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4f81bd")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(table)

    doc.build(story)
    print(f"Created output audit report PDF: {path}")


if __name__ == "__main__":
    create_demo_pdf(INPUT_PDF)
    text_data, table_data = extract_text_and_tables(INPUT_PDF)
    financial_tables = [item for item in table_data if is_high_value_financial_table(item["table"])]
    if not financial_tables:
        raise RuntimeError("No high-value financial tables found in the input PDF.")

    structured_rows = convert_all_tables(financial_tables)
    df, summary = perform_audit_analysis(structured_rows)

    print("Extracted text paragraphs:", len(text_data))
    print("Extracted tables:", len(table_data))
    print("Financial tables:", len(financial_tables))
    print("Structured rows:", len(structured_rows))
    print("Audit summary:", summary)

    build_output_pdf(OUTPUT_PDF, summary, df)
