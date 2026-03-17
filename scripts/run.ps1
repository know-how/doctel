# run.ps1

Write-Host "Starting Ollama service if not already running..." -ForegroundColor Cyan
if (-not (Get-Process "ollama" -ErrorAction SilentlyContinue)) {
    Start-Process "ollama" -WindowStyle Hidden
    Start-Sleep -Seconds 5
}

Write-Host "Activating venv and launching FastAPI server..." -ForegroundColor Cyan
& .\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
