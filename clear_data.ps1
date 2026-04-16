# clear_data.ps1 — Wipes old data directories and creates fresh structure
# Run this once after changing base_dir, then restart the backend server.
#
# Usage: .\clear_data.ps1

$ErrorActionPreference = "Stop"

$oldPaths = @(
    "C:\LocalAI\db",
    "C:\LocalAI\data\chroma",
    "C:\LocalAI\data\uploads",
    "C:\LocalAI\data\processed"
)

$newBase = "C:\Users\ze9167523\IdeaProjects\doctel\localai"
$newDirs = @(
    "$newBase\db",
    "$newBase\data\uploads",
    "$newBase\data\chroma",
    "$newBase\data\processed",
    "$newBase\logs"
)

Write-Host "=== Clearing old data ===" -ForegroundColor Yellow

foreach ($path in $oldPaths) {
    if (Test-Path $path) {
        try {
            Remove-Item $path -Recurse -Force
            Write-Host "  Removed: $path" -ForegroundColor Red
        } catch {
            Write-Host "  Could not remove $path (network/permission issue) — skipping" -ForegroundColor DarkYellow
        }
    } else {
        Write-Host "  Skipped (not found): $path"
    }
}

Write-Host ""
Write-Host "=== Creating new data directories ===" -ForegroundColor Yellow

foreach ($dir in $newDirs) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
    Write-Host "  Created: $dir" -ForegroundColor Green
}

Write-Host ""
Write-Host "=== Done ===" -ForegroundColor Cyan
Write-Host "Now restart the backend server:"
Write-Host "  cd C:\Users\ze9167523\IdeaProjects\doctel" -ForegroundColor White
Write-Host "  .\.venv\Scripts\activate" -ForegroundColor White
Write-Host "  python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload" -ForegroundColor White
Write-Host ""
Write-Host "A fresh database will be created automatically on first startup." -ForegroundColor DarkGray
