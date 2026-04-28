@echo off
echo ============================================
echo  BARS - AI Python Server Startup
echo ============================================
echo.

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found in PATH.
    pause
    exit /b 1
)

cd /d "%~dp0"

echo Installing / verifying Python dependencies...
pip install -r requirements.txt --quiet

echo.
echo Starting FastAPI AI server on http://localhost:8000
echo.
echo  Endpoints:
echo   POST /process-pdf       -- Upload PDF for AI analysis
echo   POST /generate-summary  -- Generate Gemini audit narrative
echo   POST /generate-pdf      -- Download formatted PDF report
echo   GET  /health            -- Health check
echo.
echo  To enable Gemini summaries, set your API key first:
echo    set GEMINI_API_KEY=your_api_key_here
echo.
echo Press Ctrl+C to stop.
echo.

python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
