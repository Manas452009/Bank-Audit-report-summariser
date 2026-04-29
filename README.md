# Bank Audit Report Summarizer - FastAPI Service

A FastAPI REST API for the Bank Audit Report Summarizer AI model.

## Installation
`ash
pip install -r requirements.txt
`

## Start Server
`ash
python main.py
`

## API Endpoints

### POST /process-pdf
Upload a bank audit PDF. Returns extracted data and analysis summary.

### POST /analyze-text
Submit structured text rows for financial analysis.

### POST /query
Query cached results with filters (page, deposits, advances, risk_level).

### GET /summary
Get cached summary for a processed file.

### GET /health
Health check endpoint.

## Usage Example

`python
import requests

# Process PDF
with open(report.pdf, rb) as f:
    r = requests.post(http://localhost:8000/process-pdf, files={file: f})
    print(r.json())
`

## Interactive Docs
http://localhost:8000/docs

