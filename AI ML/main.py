"""
FastAPI server for Bank Audit Report Summariser (BARS)
Exposes:
  POST /process-pdf       – accepts a PDF upload, extracts financial tables, returns JSON analysis
  POST /generate-summary  – accepts structured JSON data and produces an LLM-generated audit summary
  POST /generate-pdf      – accepts analysis/summary JSON and returns a formatted PDF for download
"""

import io
import os
import re
import json
import asyncio
import tempfile
import traceback
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import pdfplumber

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Any, AsyncGenerator

# Thread-pool for CPU-bound pdfplumber work (keeps async event loop free)
_PDF_WORKERS = int(os.getenv("PDF_WORKERS", "4"))
_executor = ThreadPoolExecutor(max_workers=_PDF_WORKERS)

# ── reportlab ────────────────────────────────────────────────────────────────
try:
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


# ── optional Gemini import ──────────────────────────────────────────────────
try:
    import google.generativeai as genai
    from google.generativeai.types import GenerationConfig
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        _gemini_model = genai.GenerativeModel(
            "models/gemini-2.5-flash-lite",
            generation_config=GenerationConfig(
                max_output_tokens=8000,   # stay well within the 64k limit
                temperature=0.3,
            ),
        )
    else:
        _gemini_model = None
except ImportError:
    _gemini_model = None

app = FastAPI(title="BARS AI Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# ── PDF helpers (ported from notebook) ─────────────────────────────────────

def _clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"(.)\1{2,}", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _is_high_value_financial_table(table: list) -> bool:
    text = " ".join([" ".join(row) for row in table]).lower()

    strong_headers = [
        "npa", "gross npa", "net npa",
        "provision", "write off",
        "advances", "liabilities",
        "assets", "borrowings",
        "exposure",
    ]
    reject_keywords = [
        "strategy", "strategic", "customer",
        "esg", "sustainability", "value creation",
        "stakeholder", "digital", "governance",
        "subsidiary", "market positioning",
        "progress", "target", "penetration",
    ]

    if any(k in text for k in reject_keywords):
        return False
    if not any(k in text for k in strong_headers):
        return False

    numbers = re.findall(r"\d+\.?\d*", text)
    if len(numbers) < 15:
        return False

    percent_count = text.count("%")
    if percent_count > 0 and len(numbers) < 10:
        return False

    if len(table) < 3:
        return False
    if max(len(row) for row in table) < 2:
        return False

    return True


# ── Parallel page processor ──────────────────────────────────────────────────

def _process_single_page(args: tuple) -> dict | None:
    """
    Process one PDF page (run in a thread). Returns a result dict or None.
    args = (page_num, page_bytes_or_index, pdf_bytes)
    We re-open only the target page via pdfplumber slice to stay thread-safe.
    """
    page_num, pdf_bytes = args
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            page = pdf.pages[page_num]
            # Fast pre-filter: skip pages with no ruled lines at all
            if not page.lines and not page.edges:
                return {"page": page_num + 1, "skipped": True, "tables": []}
            tables = page.extract_tables({
                "vertical_strategy": "lines",
                "horizontal_strategy": "lines",
            })
            found = []
            for table in (tables or []):
                if not table:
                    continue
                cleaned = [
                    [str(cell).strip() if cell else "" for cell in row]
                    for row in table
                    if any(cell is not None and str(cell).strip() != "" for cell in row)
                ]
                if len(cleaned) >= 2 and _is_high_value_financial_table(cleaned):
                    found.append(cleaned)
            return {"page": page_num + 1, "skipped": False, "tables": found}
    except Exception:
        return {"page": page_num + 1, "skipped": True, "tables": [], "error": True}


def _extract_financial_tables(pdf_bytes: bytes) -> list:
    """Return list of high-value financial tables (parallel page processing)."""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        total = len(pdf.pages)

    args_list = [(i, pdf_bytes) for i in range(total)]
    results = list(_executor.map(_process_single_page, args_list))

    # Re-assemble in page order
    table_data = []
    for res in results:
        if res and not res["skipped"]:
            for tbl in res["tables"]:
                table_data.append({"page": res["page"], "table": tbl})
    return table_data


async def _stream_pdf_processing(
    pdf_bytes: bytes, filename: str
) -> AsyncGenerator[str, None]:
    """
    SSE generator: processes pages in parallel then streams progress events
    so the client sees live updates without waiting for the full result.

    Event types emitted (JSON payloads inside 'data: ...' lines):
      { type: 'start',    total_pages: N }
      { type: 'page',     page: N, tables_found: K }
      { type: 'analysis', ...analysis_fields }
      { type: 'done',     ...full_result }
      { type: 'error',    message: '...' }
    """
    def _sse(payload: dict) -> str:
        return f"data: {json.dumps(payload)}\n\n"

    try:
        # --- discover page count ---
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            total_pages = len(pdf.pages)

        yield _sse({"type": "start", "total_pages": total_pages})

        # --- submit all pages to thread-pool ---
        loop = asyncio.get_event_loop()
        futures = [
            loop.run_in_executor(_executor, _process_single_page, (i, pdf_bytes))
            for i in range(total_pages)
        ]

        # --- stream results as each page finishes ---
        table_data = []
        for coro in asyncio.as_completed(futures):
            res = await coro
            if res:
                page_tables = res["tables"]
                yield _sse({
                    "type": "page",
                    "page": res["page"],
                    "tables_found": len(page_tables),
                    "skipped": res.get("skipped", False),
                })
                for tbl in page_tables:
                    table_data.append({"page": res["page"], "table": tbl})

        # --- build structured rows ---
        # Sort by page for deterministic analysis
        table_data.sort(key=lambda x: x["page"])
        structured_data = []
        for item in table_data:
            page = item["page"]
            for row in _table_to_structured_text(item["table"]):
                structured_data.append({"page": page, "text": row})

        # --- analyse ---
        analysis = _analyse_structured_data(structured_data)
        yield _sse({"type": "analysis", **analysis})

        # --- final complete payload ---
        yield _sse({
            "type": "done",
            "filename": filename,
            "financial_tables_found": len(table_data),
            "structured_rows": len(structured_data),
            "analysis": analysis,
        })

    except Exception as exc:
        traceback.print_exc()
        yield _sse({"type": "error", "message": str(exc)})


def _clean_field_name(name: str) -> str:
    name = re.sub(r"\d+", "", name)
    name = re.sub(r"[^a-zA-Z\s]", "", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip()


def _clean_value(value: str) -> str:
    return value.replace(",", "").strip()


def _table_to_structured_text(table: list) -> list:
    headers = table[0]
    rows = table[1:]
    structured = []
    for row in rows:
        row_text = []
        for h, v in zip(headers, row):
            if v and v != "-":
                clean_h = _clean_field_name(h)
                clean_v = _clean_value(v)
                if clean_h:
                    row_text.append(f"{clean_h}: {clean_v}")
        if row_text:
            structured.append(", ".join(row_text))
    return structured


def _analyse_structured_data(structured_data: list) -> dict:
    rows = []
    for item in structured_data:
        txt = item["text"]
        dep = re.search(r"Deposits:\s*([\d\.]+)", txt)
        adv = re.search(r"Advances:\s*([\d\.]+)", txt)
        inv = re.search(r"Investments:\s*([\d\.]+)", txt)
        deposits = float(dep.group(1)) if dep else np.nan
        advances = float(adv.group(1)) if adv else np.nan
        investments = float(inv.group(1)) if inv else np.nan
        rows.append({"page": item["page"], "deposits": deposits, "advances": advances, "investments": investments})

    df = pd.DataFrame(rows)
    df = df.dropna(subset=["deposits", "advances", "investments"], how="all")

    if df.empty:
        return {
            "total_deposits": 0,
            "total_advances": 0,
            "total_investments": 0,
            "overall_ldr": None,
            "overall_inv_ratio": None,
            "overall_risk": "UNKNOWN",
            "row_count": 0,
            "rows": [],
        }

    df["LDR"] = np.where(df["deposits"] > 0, df["advances"] / df["deposits"], np.nan)
    df["INV_RATIO"] = np.where(df["deposits"] > 0, df["investments"] / df["deposits"], np.nan)

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
        ldr = row["LDR"]
        inv = row["INV_RATIO"]
        dep = row["deposits"]
        if pd.isna(ldr):
            return ""
        if ldr > 1:
            notes.append("Advances exceed deposits")
        elif ldr > 0.85:
            notes.append("Aggressive lending")
        elif ldr < 0.60:
            notes.append("Conservative lending")
        if not pd.isna(inv):
            if inv > 2:
                notes.append("Very high investment concentration")
            elif inv > 1:
                notes.append("High investments")
        if not pd.isna(dep) and dep < 10000:
            notes.append("Low deposit base")
        return "; ".join(notes)

    df["risk_level"] = df["LDR"].apply(risk_level)
    df["observations"] = df.apply(comments, axis=1)

    total_dep = float(df["deposits"].sum())
    total_adv = float(df["advances"].sum())
    total_inv = float(df["investments"].sum())
    overall_ldr = float(total_adv / total_dep) if total_dep > 0 else None
    overall_inv = float(total_inv / total_dep) if total_dep > 0 else None

    if overall_ldr is None:
        overall_risk = "UNKNOWN"
    elif overall_ldr > 0.90:
        overall_risk = "HIGH"
    elif overall_ldr > 0.70:
        overall_risk = "MODERATE"
    else:
        overall_risk = "LOW"

    df = df.replace({np.nan: None})
    detail_rows = df.to_dict(orient="records")

    return {
        "total_deposits": total_dep,
        "total_advances": total_adv,
        "total_investments": total_inv,
        "overall_ldr": overall_ldr,
        "overall_inv_ratio": overall_inv,
        "overall_risk": overall_risk,
        "row_count": len(df),
        "rows": detail_rows,
    }


# ── endpoints ───────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/process-pdf")
async def process_pdf(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    try:
        pdf_bytes = await file.read()

        # Run blocking extraction in thread pool so async loop stays free
        loop = asyncio.get_event_loop()
        financial_tables = await loop.run_in_executor(
            _executor, _extract_financial_tables, pdf_bytes
        )

        structured_data = []
        for item in financial_tables:
            page = item["page"]
            for row in _table_to_structured_text(item["table"]):
                structured_data.append({"page": page, "text": row})

        analysis = _analyse_structured_data(structured_data)

        return {
            "filename": file.filename,
            "financial_tables_found": len(financial_tables),
            "structured_rows": len(structured_data),
            "analysis": analysis,
        }

    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"PDF processing failed: {str(exc)}")


@app.post("/process-pdf-stream")
async def process_pdf_stream(file: UploadFile = File(...)):
    """
    SSE endpoint — streams per-page progress then final analysis JSON.
    The client reads events of the form:  data: {...}\\n\\n

    Event shapes:
      { type: 'start',    total_pages: N }
      { type: 'page',     page: N, tables_found: K, skipped: bool }
      { type: 'analysis', total_deposits, total_advances, ... }
      { type: 'done',     filename, financial_tables_found, structured_rows, analysis }
      { type: 'error',    message }
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    pdf_bytes = await file.read()

    return StreamingResponse(
        _stream_pdf_processing(pdf_bytes, file.filename),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering
        },
    )


class SummaryRequest(BaseModel):
    data: Any = None


@app.post("/generate-summary")
async def generate_summary(payload: dict):
    """
    Accepts the analysis JSON (returned by /process-pdf) and produces
    a professional audit summary using Gemini (if configured) or a
    rule-based fallback.
    """
    try:
        analysis = payload.get("analysis") or payload

        total_dep = analysis.get("total_deposits", 0)
        total_adv = analysis.get("total_advances", 0)
        total_inv = analysis.get("total_investments", 0)
        overall_ldr = analysis.get("overall_ldr")
        overall_risk = analysis.get("overall_risk", "UNKNOWN")
        row_count = analysis.get("row_count", 0)
        rows = analysis.get("rows", [])

        high_risk = sum(1 for r in rows if r.get("risk_level") == "High")
        moderate_risk = sum(1 for r in rows if r.get("risk_level") == "Moderate")
        low_risk = sum(1 for r in rows if r.get("risk_level") == "Low")

        # ── Gemini path ──────────────────────────────────────────────────
        if _gemini_model:
            # Limit row detail in prompt to avoid token overflow (max 20 rows)
            MAX_ROWS_IN_PROMPT = 20
            row_sample = rows[:MAX_ROWS_IN_PROMPT]
            row_detail_lines = []
            for i, r in enumerate(row_sample, 1):
                ldr_v = r.get("LDR")
                obs   = r.get("observations", "")
                row_detail_lines.append(
                    f"  Row {i}: Risk={r.get('risk_level','?')}, "
                    f"LDR={f'{ldr_v:.2%}' if ldr_v is not None else 'N/A'}, "
                    f"Obs={obs}"
                )
            row_detail_str = "\n".join(row_detail_lines)
            if len(rows) > MAX_ROWS_IN_PROMPT:
                row_detail_str += f"\n  ... and {len(rows) - MAX_ROWS_IN_PROMPT} more rows (summarized above)."

            prompt = f"""You are a senior banking auditor from a Big 4 consulting firm preparing a professional audit note for senior management.

STRICT FORMATTING RULES:
1. Do NOT use any Markdown (no asterisks **, no hashes #, no bolding, no italics).
2. Use ALL CAPS for section headings to create structure.
3. Use simple dashes (-) for bullet points.
4. Ensure there is a blank line between each section.
5. Do not write prepared by.
6. Keep each section concise (3-5 sentences or bullet points maximum).

Use ONLY the data provided below. Do NOT invent numbers. Do NOT assume facts not present.
Use formal banking language.

Prepare a structured report with these sections:
1. Executive Summary
2. Liquidity Position
3. Credit Risk Review (analyze LDR, lending aggressiveness, concentration concerns)
4. Investment Portfolio Review
5. High Risk Accounts
6. Overall Risk Rating
7. Recommendations (5 points)
8. Final Management Note

==================================
FINANCIAL DATA
==================================
Total Rows Analyzed   : {row_count}
Total Deposits        : {total_dep:,.2f}
Total Advances        : {total_adv:,.2f}
Total Investments     : {total_inv:,.2f}
Overall LDR           : {f"{overall_ldr:.2%}" if overall_ldr is not None else "N/A"}
Overall Risk          : {overall_risk}
High Risk Rows        : {high_risk}
Moderate Risk Rows    : {moderate_risk}
Low Risk Rows         : {low_risk}

ROW DETAIL SAMPLE:
{row_detail_str}
"""
            response = _gemini_model.generate_content(prompt)
            summary_text = response.text

        # ── Rule-based fallback ──────────────────────────────────────────
        else:
            ldr_str = f"{overall_ldr:.2%}" if overall_ldr is not None else "N/A"
            summary_text = (
                f"EXECUTIVE SUMMARY\n\n"
                f"Analysis of {row_count} data rows reveals total deposits of {total_dep:,.2f}, "
                f"total advances of {total_adv:,.2f}, and total investments of {total_inv:,.2f}.\n\n"
                f"CREDIT RISK REVIEW\n\n"
                f"Overall Loan-to-Deposit Ratio (LDR): {ldr_str}. "
                f"Risk distribution: {high_risk} high-risk, {moderate_risk} moderate-risk, {low_risk} low-risk rows.\n\n"
                f"OVERALL RISK RATING\n\n"
                f"{overall_risk}\n\n"
                f"RECOMMENDATIONS\n\n"
                f"- Review high-risk rows for excessive lending aggressiveness.\n"
                f"- Monitor deposit-to-advance ratios monthly.\n"
                f"- Investigate rows where advances exceed deposits.\n"
                f"- Perform sensitivity analysis on the investment portfolio.\n"
                f"- Update lending policies to cap LDR within prudent limits."
            )

        return {
            "summary": summary_text,
            "risk_level": overall_risk,
            "total_deposits": total_dep,
            "total_advances": total_adv,
            "total_investments": total_inv,
            "overall_ldr": overall_ldr,
            "high_risk_rows": high_risk,
            "moderate_risk_rows": moderate_risk,
            "low_risk_rows": low_risk,
        }

    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Summary generation failed: {str(exc)}")




@app.post("/generate-pdf")
async def generate_pdf_endpoint(payload: dict):
    """
    Generate a formatted PDF from analysis data or summary data.
    payload keys:
      type     : "report" | "summary"
      data     : the analysis JSON or summary JSON
      filename : original uploaded filename (optional)
    """
    if not REPORTLAB_AVAILABLE:
        raise HTTPException(
            status_code=501,
            detail="reportlab is not installed. Run: pip install reportlab"
        )

    try:
        report_type = payload.get("type", "report")
        data = payload.get("data", {})
        source_filename = payload.get("filename", "bank_audit_report")
        generated_at = datetime.now().strftime("%d %B %Y, %H:%M")

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4,
                                leftMargin=2*cm, rightMargin=2*cm,
                                topMargin=2*cm, bottomMargin=2*cm)

        styles = getSampleStyleSheet()
        story = []

        # ── Custom styles ────────────────────────────────────────────────────
        title_style = ParagraphStyle(
            "BARSTitle",
            parent=styles["Title"],
            fontSize=22,
            textColor=colors.HexColor("#1a5f4a"),
            spaceAfter=6,
        )
        h1_style = ParagraphStyle(
            "BARSH1",
            parent=styles["Heading1"],
            fontSize=11,
            textColor=colors.HexColor("#1a5f4a"),
            spaceBefore=14,
            spaceAfter=4,
        )
        body_style = ParagraphStyle(
            "BARSBody",
            parent=styles["Normal"],
            fontSize=9,
            leading=14,
            spaceAfter=3,
        )
        bullet_style = ParagraphStyle(
            "BARSBullet",
            parent=styles["Normal"],
            fontSize=9,
            leading=14,
            leftIndent=12,
            spaceAfter=3,
        )
        meta_style = ParagraphStyle(
            "BARSMeta",
            parent=styles["Normal"],
            fontSize=8,
            textColor=colors.grey,
            spaceAfter=2,
        )

        # ── Title block ──────────────────────────────────────────────────────
        story.append(Paragraph("Bank Audit Report Summariser (BARS)", title_style))
        story.append(Paragraph(f"Source: {source_filename}", meta_style))
        story.append(Paragraph(f"Generated: {generated_at}", meta_style))
        story.append(HRFlowable(width="100%", thickness=1,
                                color=colors.HexColor("#1a5f4a"), spaceAfter=12))

        if report_type == "summary":
            # ── Summary PDF ──────────────────────────────────────────────────
            summary_text: str = data.get("summary", "")
            risk = data.get("risk_level", "")
            total_dep = data.get("total_deposits")
            total_adv = data.get("total_advances")
            total_inv = data.get("total_investments")
            overall_ldr = data.get("overall_ldr")
            high_rows = data.get("high_risk_rows", 0)

            # KPI table
            kpi_rows = [["Metric", "Value"]]
            if risk:
                kpi_rows.append(["Overall Risk", risk])
            if total_dep is not None:
                kpi_rows.append(["Total Deposits", f"{total_dep:,.2f}"])
            if total_adv is not None:
                kpi_rows.append(["Total Advances", f"{total_adv:,.2f}"])
            if total_inv is not None:
                kpi_rows.append(["Total Investments", f"{total_inv:,.2f}"])
            if overall_ldr is not None:
                kpi_rows.append(["Loan-to-Deposit Ratio", f"{overall_ldr:.2%}"])
            kpi_rows.append(["High Risk Rows", str(high_rows)])

            if len(kpi_rows) > 1:
                story.append(Paragraph("Key Metrics", h1_style))
                tbl = Table(kpi_rows, colWidths=[8*cm, 7*cm])
                tbl.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a5f4a")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                     [colors.white, colors.HexColor("#f0fdf4")]),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]))
                story.append(tbl)
                story.append(Spacer(1, 14))

            # Narrative
            story.append(Paragraph("AI-Generated Audit Narrative", h1_style))
            for raw_line in summary_text.split("\n"):
                line = raw_line.strip()
                if not line:
                    story.append(Spacer(1, 5))
                elif re.match(r"^[A-Z][A-Z\s\/]{4,}$", line):
                    story.append(Paragraph(line, h1_style))
                elif line.startswith("- "):
                    story.append(Paragraph("• " + line[2:], bullet_style))
                else:
                    story.append(Paragraph(line, body_style))

        else:
            # ── Analysis Report PDF ──────────────────────────────────────────
            analysis = data.get("analysis") or data
            rows: list = analysis.get("rows", [])

            # Summary KPI table
            kpi_rows = [["Metric", "Value"]]
            kpi_rows.append(["Overall Risk", analysis.get("overall_risk", "—")])
            kpi_rows.append(["Total Deposits", f"{analysis.get('total_deposits', 0):,.2f}"])
            kpi_rows.append(["Total Advances", f"{analysis.get('total_advances', 0):,.2f}"])
            kpi_rows.append(["Total Investments", f"{analysis.get('total_investments', 0):,.2f}"])
            ldr = analysis.get("overall_ldr")
            kpi_rows.append(["Loan-to-Deposit Ratio", f"{ldr:.2%}" if ldr is not None else "—"])
            kpi_rows.append(["Rows Analysed", str(analysis.get("row_count", 0))])

            story.append(Paragraph("Analysis Overview", h1_style))
            tbl = Table(kpi_rows, colWidths=[8*cm, 7*cm])
            tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a5f4a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                 [colors.white, colors.HexColor("#f0fdf4")]),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            story.append(tbl)
            story.append(Spacer(1, 16))

            # Row-level table
            if rows:
                story.append(Paragraph("Row-Level Financial Analysis", h1_style))
                headers = ["Page", "Deposits", "Advances", "Investments", "LDR", "Inv. Ratio", "Risk", "Observations"]
                table_data = [headers]
                for r in rows:
                    ldr_val = r.get("LDR")
                    inv_val = r.get("INV_RATIO")
                    table_data.append([
                        str(r.get("page", "")),
                        f"{r.get('deposits', 0):,.2f}" if r.get("deposits") is not None else "—",
                        f"{r.get('advances', 0):,.2f}" if r.get("advances") is not None else "—",
                        f"{r.get('investments', 0):,.2f}" if r.get("investments") is not None else "—",
                        f"{ldr_val:.1%}" if ldr_val is not None else "—",
                        f"{inv_val:.1%}" if inv_val is not None else "—",
                        str(r.get("risk_level", "")),
                        str(r.get("observations", "")),
                    ])

                col_widths = [1.2*cm, 2.8*cm, 2.8*cm, 2.8*cm, 1.8*cm, 2*cm, 1.8*cm, 4*cm]
                detail_tbl = Table(table_data, colWidths=col_widths, repeatRows=1)

                def _risk_bg(level: str):
                    l = level.lower()
                    if l == "high": return colors.HexColor("#fee2e2")
                    if l == "moderate": return colors.HexColor("#fef9c3")
                    if l == "low": return colors.HexColor("#dcfce7")
                    return colors.white

                row_styles = [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a5f4a")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("WORDWRAP", (7, 1), (7, -1), True),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
                for i, r in enumerate(rows, start=1):
                    bg = _risk_bg(r.get("risk_level", ""))
                    if bg != colors.white:
                        row_styles.append(("BACKGROUND", (6, i), (6, i), bg))

                detail_tbl.setStyle(TableStyle(row_styles))
                story.append(detail_tbl)

        doc.build(story)
        buf.seek(0)

        return StreamingResponse(
            buf,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=bank_audit_{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"},
        )

    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(exc)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
