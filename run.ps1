$tags = curl.exe -s http://127.0.0.1:11434/api/tags
if ($LASTEXITCODE -ne 0) {
  $ollamaExe = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
  if (Test-Path $ollamaExe) {
    & $ollamaExe serve | Out-Null
    Start-Sleep -Seconds 2
  }
}

ollama list | findstr /I "llama3.2:8b-instruct" | Out-Null; if ($LASTEXITCODE -ne 0) { ollama pull llama3.2:8b-instruct }
ollama list | findstr /I "llama3.2:3b-instruct" | Out-Null; if ($LASTEXITCODE -ne 0) { ollama pull llama3.2:3b-instruct }
ollama list | findstr /I "nomic-embed-text"     | Out-Null; if ($LASTEXITCODE -ne 0) { ollama pull nomic-embed-text }
ollama list | findstr /I "llava:7b"             | Out-Null; if ($LASTEXITCODE -ne 0) { ollama pull llava:7b }

& .\.venv\Scripts\Activate.ps1
py -3.12 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
