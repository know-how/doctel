$BaseDir = "C:\LocalAI"
$Folders = @(
  "data\projects",
  "data\uploads",
  "data\ocr",
  "data\chroma",
  "db",
  "logs"
)

foreach ($folder in $Folders) {
  $path = Join-Path $BaseDir $folder
  if (-not (Test-Path $path)) { New-Item -Path $path -ItemType Directory -Force | Out-Null }
}

py -3.12 -m venv .venv
& .\.venv\Scripts\Activate.ps1
py -3.12 -m pip install -r requirements.txt

if (-not (Get-Command tesseract -ErrorAction SilentlyContinue)) { Write-Host "Tesseract not found in PATH" -ForegroundColor Yellow }
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) { Write-Host "Ollama not found in PATH" -ForegroundColor Yellow }
