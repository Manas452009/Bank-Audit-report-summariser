import { useState, useEffect } from 'react'
import { useLocation, useNavigate, Link } from 'react-router-dom'
import './ResultPage.css'

const AI_BASE = '/ai'

// ── helpers ──────────────────────────────────────────────────────────────────
function fmt(n: number | null | undefined, decimals = 2) {
  if (n == null || isNaN(n)) return '—'
  return n.toLocaleString('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
}

function riskColor(risk: string) {
  const r = (risk || '').toUpperCase()
  if (r === 'HIGH') return '#ef4444'
  if (r === 'MODERATE') return '#fbbf24'
  if (r === 'LOW') return '#4ade80'
  return '#94a3b8'
}

function rowRiskColor(level: string) {
  const l = (level || '').toLowerCase()
  if (l === 'high') return 'risk-high'
  if (l === 'moderate') return 'risk-moderate'
  if (l === 'low') return 'risk-low'
  return ''
}

// ── main component ────────────────────────────────────────────────────────────
function ResultPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [result, setResult] = useState<any>(null)
  const [filename, setFilename] = useState<string>('report')
  const [isDownloading, setIsDownloading] = useState(false)
  const [error, setError] = useState<string>('')

  useEffect(() => {
    const state = location.state as any
    if (state?.result) {
      setResult(state.result)
      setFilename(state.filename || 'report')
      localStorage.setItem('lastUploadResult', JSON.stringify(state.result))
    } else {
      const saved = localStorage.getItem('lastUploadResult')
      if (saved) {
        setResult(JSON.parse(saved))
      } else {
        setError('No upload result found. Please upload a file first.')
      }
    }
  }, [location])

  const handleGetSummary = () => {
    navigate('/summary', { state: { originalData: result, filename } })
  }

  /** Download the full analysis as a PDF via the AI server */
  const handleDownloadReport = async () => {
    if (!result) return
    setIsDownloading(true)
    setError('')

    try {
      const response = await fetch(`${AI_BASE}/generate-pdf`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: 'report', data: result, filename }),
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
      a.download = `bank_audit_report_${Date.now()}.pdf`
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Download failed')
    } finally {
      setIsDownloading(false)
    }
  }

  if (error && !result) {
    return (
      <div className="result-page">
        <div className="error-container">
          <h2>Error</h2>
          <p>{error}</p>
          <Link to="/summarizer" className="btn btn-primary">Go Back to Upload</Link>
        </div>
      </div>
    )
  }

  const analysis = result?.analysis || {}
  const rows: any[] = analysis?.rows || []

  return (
    <div className="result-page">
      <header className="result-header">
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

      <main className="result-content">
        <div className="result-hero">
          <h1>Analysis Complete</h1>
          {filename && <p className="result-filename">📄 {filename}</p>}
          <p className="result-sub">
            Found <strong>{result?.financial_tables_found ?? 0}</strong> financial tables ·{' '}
            <strong>{result?.structured_rows ?? 0}</strong> structured rows extracted
          </p>
        </div>

        {/* ── Risk Banner ── */}
        {analysis?.overall_risk && (
          <div className="risk-banner" style={{ '--risk-color': riskColor(analysis.overall_risk) } as any}>
            <span className="risk-label">Overall Risk</span>
            <span className="risk-value" style={{ color: riskColor(analysis.overall_risk) }}>
              {analysis.overall_risk}
            </span>
          </div>
        )}

        {/* ── KPI Cards ── */}
        <div className="kpi-grid">
          <KpiCard label="Total Deposits" value={`₹ ${fmt(analysis?.total_deposits)}`} />
          <KpiCard label="Total Advances" value={`₹ ${fmt(analysis?.total_advances)}`} />
          <KpiCard label="Total Investments" value={`₹ ${fmt(analysis?.total_investments)}`} />
          <KpiCard
            label="Loan-to-Deposit Ratio"
            value={analysis?.overall_ldr != null ? `${(analysis.overall_ldr * 100).toFixed(2)}%` : '—'}
            highlight={analysis?.overall_ldr > 0.9}
          />
          <KpiCard
            label="Investment Ratio"
            value={analysis?.overall_inv_ratio != null ? `${(analysis.overall_inv_ratio * 100).toFixed(2)}%` : '—'}
          />
          <KpiCard label="Rows Analysed" value={String(analysis?.row_count ?? 0)} />
        </div>

        {/* ── Action Buttons ── */}
        <div className="result-actions">
          <button className="btn btn-primary" onClick={handleGetSummary} disabled={!result}>
            🤖 Generate AI Summary
          </button>
          <button className="btn btn-secondary" onClick={handleDownloadReport} disabled={isDownloading || !result}>
            {isDownloading ? '⏳ Generating PDF…' : '⬇ Download Report PDF'}
          </button>
        </div>

        {error && <p className="inline-error">{error}</p>}

        {/* ── Detailed Rows Table ── */}
        {rows.length > 0 && (
          <div className="result-data">
            <h2>Row-level Analysis</h2>
            <div className="table-wrapper">
              <table className="result-table">
                <thead>
                  <tr>
                    <th>Page</th>
                    <th>Deposits</th>
                    <th>Advances</th>
                    <th>Investments</th>
                    <th>LDR</th>
                    <th>Inv. Ratio</th>
                    <th>Risk</th>
                    <th>Observations</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row: any, i: number) => (
                    <tr key={i}>
                      <td>{row.page}</td>
                      <td>{fmt(row.deposits)}</td>
                      <td>{fmt(row.advances)}</td>
                      <td>{fmt(row.investments)}</td>
                      <td>{row.LDR != null ? `${(row.LDR * 100).toFixed(1)}%` : '—'}</td>
                      <td>{row.INV_RATIO != null ? `${(row.INV_RATIO * 100).toFixed(1)}%` : '—'}</td>
                      <td>
                        <span className={`risk-badge ${rowRiskColor(row.risk_level)}`}>
                          {row.risk_level || '—'}
                        </span>
                      </td>
                      <td className="obs-cell">{row.observations || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {rows.length === 0 && result && (
          <div className="no-data">
            <p>No high-value financial tables were detected in this PDF.</p>
            <p style={{ fontSize: '0.875rem', marginTop: '0.5rem', opacity: 0.6 }}>
              The AI looks for tables containing keywords like Deposits, Advances, NPA, Investments with at least 15 numeric values.
            </p>
          </div>
        )}

        <div className="result-footer">
          <button className="btn btn-outline" onClick={() => navigate('/summarizer')}>
            Upload Another File
          </button>
        </div>
      </main>
    </div>
  )
}

function KpiCard({ label, value, highlight = false }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className={`kpi-card ${highlight ? 'kpi-highlight' : ''}`}>
      <span className="kpi-label">{label}</span>
      <span className="kpi-value">{value}</span>
    </div>
  )
}

export default ResultPage
