# setup.ps1

$BaseDir = "C:\LocalAI"
$Folders = @(
    "data\projects",
    "data\uploads",
    "data\ocr",
    "data\chroma",
    "db",
    "logs",
    "app"
)

Write-Host "Creating directory structure at $BaseDir..." -ForegroundColor Cyan
foreach ($folder in $Folders) {
    $path = Join-Path $BaseDir $folder
    if (-not (Test-Path $path)) {
        New-Item -Path $path -ItemType Directory -Force
    }
}

Write-Host "Setting up Python environment..." -ForegroundColor Cyan
python -m venv .venv
& .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

Write-Host "Verifying Tesseract installation..." -ForegroundColor Cyan
if (-not (Get-Command tesseract -ErrorAction SilentlyContinue)) {
    Write-Warning "Tesseract not found in PATH. Please install it for OCR support."
}

Write-Host "Verifying Ollama installation..." -ForegroundColor Cyan
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Warning "Ollama not found in PATH. Please install it from ollama.com."
} else {
    Write-Host "Pulling models..." -ForegroundColor Cyan
    ollama pull llama3.2:8b-instruct
    ollama pull llama3.2:3b-instruct
    ollama pull llava:7b
    ollama pull nomic-embed-text
}

Write-Host "Setup complete!" -ForegroundColor Green
