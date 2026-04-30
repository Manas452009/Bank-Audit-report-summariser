import { useState, useEffect } from 'react'
import { useLocation, useNavigate, Link } from 'react-router-dom'
import './SummaryPage.css'

const AI_BASE = '/ai'

function riskColor(risk: string) {
  const r = (risk || '').toUpperCase()
  if (r === 'HIGH') return '#ef4444'
  if (r === 'MODERATE') return '#fbbf24'
  if (r === 'LOW') return '#4ade80'
  return '#94a3b8'
}

function fmt(n: number | null | undefined, decimals = 2) {
  if (n == null || isNaN(n)) return '—'
  return n.toLocaleString('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
}

function SummaryPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [summary, setSummary] = useState<any>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isDownloading, setIsDownloading] = useState(false)
  const [error, setError] = useState<string>('')
  const [filename, setFilename] = useState<string>('report')

  useEffect(() => {
    const state = location.state as any
    const data = state?.originalData || (() => {
      try { return JSON.parse(localStorage.getItem('lastUploadResult') || '') } catch { return null }
    })()

    if (state?.filename) setFilename(state.filename)

    if (data) {
      generateSummary(data)
    } else {
      setError('No data available. Please upload a file first.')
      setIsLoading(false)
    }
  }, [location])

  const generateSummary = async (data: any) => {
    setIsLoading(true)
    setError('')
    try {
      const response = await fetch(`${AI_BASE}/generate-summary`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })

      if (!response.ok) {
        let msg = `Summary failed (HTTP ${response.status})`
        try { const j = await response.json(); if (j?.detail) msg = j.detail } catch { /* */ }
        throw new Error(msg)
      }

      const result = await response.json()
      setSummary(result)
    } catch (err) {
      if (err instanceof TypeError) {
        setError('Cannot reach the AI server. Make sure it is running on port 8000.')
      } else {
        setError(err instanceof Error ? err.message : 'Summary generation failed')
      }
    } finally {
      setIsLoading(false)
    }
  }

  const handleDownloadPdf = async () => {
    if (!summary) return
    setIsDownloading(true)
    try {
      const response = await fetch(`${AI_BASE}/generate-pdf`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: 'summary', data: summary, filename }),
      })

      if (!response.ok) {
        let msg = `Download failed (HTTP ${response.status})`
        try { const j = await response.json(); if (j?.detail) msg = j.detail } catch { /* */ }
        throw new Error(msg)
      }

      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `bank_audit_summary_${Date.now()}.pdf`
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      // fallback: download as plain text
      const text = summary?.summary || JSON.stringify(summary, null, 2)
      const blob = new Blob([text], { type: 'text/plain' })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `bank_audit_summary_${Date.now()}.txt`
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
    } finally {
      setIsDownloading(false)
    }
  }

  // ── Loading ────────────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="summary-page">
        <div className="loading-container">
          <div className="spinner" />
          <p>Generating AI audit summary…</p>
          <p style={{ fontSize: '0.85rem', opacity: 0.5, marginTop: '0.5rem' }}>
            Calling Gemini to write the professional report
          </p>
        </div>
      </div>
    )
  }

  // ── Error ──────────────────────────────────────────────────────────────────
  if (error) {
    return (
      <div className="summary-page">
        <div className="error-container">
          <h2>Error</h2>
          <p>{error}</p>
          <div className="error-actions">
            <Link to="/summarizer" className="btn btn-primary">Upload New File</Link>
            <button className="btn btn-secondary" onClick={() => navigate(-1)}>Back</button>
          </div>
        </div>
      </div>
    )
  }

  const summaryText: string = summary?.summary || ''
  const sections = parseSections(summaryText)

  return (
    <div className="summary-page">
      <header className="summary-header">
        <div className="logo">
          <Link to="/">
            <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
              <rect width="32" height="32" rx="8" fill="#1a5f4a"/>
              <path d="M8 12h16M8 16h12M8 20h8" stroke="white" strokeWidth="2" strokeLinecap="round"/>
            </svg>
          </Link>
          <span>BankReport AI</span>
        </div>
        <nav>
          <Link to="/" className="nav-link">Home</Link>
          <Link to="/summarizer" className="nav-link">New Upload</Link>
        </nav>
      </header>

      <main className="summary-content">
        {/* ── Title block ── */}
        <div className="summary-hero">
          <div className="ai-badge">🤖 AI-Generated Report</div>
          <h1>Bank Audit Summary</h1>
          {filename && <p className="summary-filename">📄 {filename}</p>}
          <p className="generated-at">Generated: {new Date().toLocaleString()}</p>
        </div>

        {/* ── Risk + KPI strip ── */}
        <div className="summary-kpi-strip">
          {summary?.risk_level && (
            <div className="kpi-pill" style={{ borderColor: riskColor(summary.risk_level) }}>
              <span className="kpi-pill-label">Overall Risk</span>
              <span className="kpi-pill-value" style={{ color: riskColor(summary.risk_level) }}>
                {summary.risk_level}
              </span>
            </div>
          )}
          {summary?.total_deposits != null && (
            <div className="kpi-pill">
              <span className="kpi-pill-label">Deposits</span>
              <span className="kpi-pill-value">₹ {fmt(summary.total_deposits)}</span>
            </div>
          )}
          {summary?.total_advances != null && (
            <div className="kpi-pill">
              <span className="kpi-pill-label">Advances</span>
              <span className="kpi-pill-value">₹ {fmt(summary.total_advances)}</span>
            </div>
          )}
          {summary?.overall_ldr != null && (
            <div className="kpi-pill">
              <span className="kpi-pill-label">LDR</span>
              <span className="kpi-pill-value">{(summary.overall_ldr * 100).toFixed(2)}%</span>
            </div>
          )}
          {summary?.high_risk_rows != null && (
            <div className="kpi-pill" style={{ borderColor: '#ef4444' }}>
              <span className="kpi-pill-label">High Risk Rows</span>
              <span className="kpi-pill-value" style={{ color: '#ef4444' }}>{summary.high_risk_rows}</span>
            </div>
          )}
        </div>

        {/* ── Full AI text rendered section-by-section ── */}
        <div className="ai-report-body">
          {sections.length > 0 ? (
            sections.map((sec, i) => (
              <div key={i} className="report-section">
                {sec.heading && <h2 className="section-heading">{sec.heading}</h2>}
                <div className="section-content">
                  {sec.lines.map((line, j) => {
                    if (line.startsWith('- ')) {
                      return <p key={j} className="bullet-line">• {line.slice(2)}</p>
                    }
                    return <p key={j} className="text-line">{line}</p>
                  })}
                </div>
              </div>
            ))
          ) : (
            <pre className="raw-summary">{summaryText}</pre>
          )}
        </div>

        {/* ── Actions ── */}
        <div className="summary-actions">
          <button className="btn btn-primary" onClick={handleDownloadPdf} disabled={isDownloading}>
            {isDownloading ? '⏳ Generating PDF…' : '⬇ Download Summary PDF'}
          </button>
          <button className="btn btn-secondary" onClick={() => navigate(-1)}>
            ← View Analysis
          </button>
          <button className="btn btn-outline" onClick={() => navigate('/summarizer')}>
            Upload Another File
          </button>
        </div>
      </main>
    </div>
  )
}

/** Split the Gemini plain-text output into heading+body sections */
function parseSections(text: string): { heading: string; lines: string[] }[] {
  if (!text.trim()) return []

  const sections: { heading: string; lines: string[] }[] = []
  let current: { heading: string; lines: string[] } = { heading: '', lines: [] }

  for (const rawLine of text.split('\n')) {
    const line = rawLine.trimEnd()

    // ALL-CAPS heading (e.g. "EXECUTIVE SUMMARY")
    if (/^[A-Z][A-Z\s\/]{4,}$/.test(line.trim()) && line.trim().length > 4) {
      if (current.heading || current.lines.length) {
        sections.push(current)
      }
      current = { heading: line.trim(), lines: [] }
    } else if (line.trim()) {
      current.lines.push(line)
    } else {
      // blank line = paragraph break inside same section
      if (current.lines.length && current.lines[current.lines.length - 1] !== '') {
        current.lines.push('')
      }
    }
  }

  if (current.heading || current.lines.length) sections.push(current)
  return sections
}

export default SummaryPage
