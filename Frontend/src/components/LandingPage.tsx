import { Link } from 'react-router-dom'
import './LandingPage.css'

function LandingPage() {
  return (
    <div className="landing">
      <header className="header">
        <div className="logo">
          <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
            <rect width="32" height="32" rx="8" fill="#1a5f4a"/>
            <path d="M8 12h16M8 16h12M8 20h8" stroke="white" strokeWidth="2" strokeLinecap="round"/>
          </svg>
          <span>BankReport AI</span>
        </div>
        <nav>
          <Link to="/login" className="nav-link">Sign In</Link>
        </nav>
      </header>

      <main className="hero">
        <div className="hero-content">
          <h1>Smart Bank Report Summarization</h1>
          <p>Instantly analyze and summarize your bank statements, transaction history, and financial reports with AI-powered insights.</p>
          <div className="cta-group">
            <Link to="/signup" className="btn-primary">Start For Free</Link>
            <Link to="/login" className="btn-secondary">Sign In</Link>
          </div>
        </div>
        <div className="hero-visual">
          <div className="document-preview">
            <div className="preview-header">
              <span className="dot red"></span>
              <span className="dot yellow"></span>
              <span className="dot green"></span>
            </div>
            <div className="preview-content">
              <div className="line short"></div>
              <div className="line"></div>
              <div className="line medium"></div>
              <div className="line"></div>
              <div className="line short"></div>
              <div className="arrow">→</div>
              <div className="summary-box">
                <div className="summary-title">Summary</div>
                <div className="summary-line"></div>
                <div className="summary-line short"></div>
              </div>
            </div>
          </div>
        </div>
      </main>

      <section className="features">
        <div className="feature">
          <div className="feature-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
              <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            </svg>
          </div>
          <h3>Quick Analysis</h3>
          <p>Upload your bank statements and get instant summaries in seconds</p>
        </div>
        <div className="feature">
          <div className="feature-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
              <path d="M13 10V3L4 14h7v7l9-11h-7z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <h3>AI-Powered</h3>
          <p>Advanced AI extracts key insights from complex financial documents</p>
        </div>
        <div className="feature">
          <div className="feature-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
              <path d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            </svg>
          </div>
          <h3>Secure & Private</h3>
          <p>Your financial data is encrypted and never shared</p>
        </div>
      </section>

      <footer className="footer">
        <p>© 2026 BankReport AI. All rights reserved.</p>
      </footer>
    </div>
  )
}

export default LandingPage