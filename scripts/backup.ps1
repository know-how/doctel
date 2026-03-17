# backup.ps1

$BaseDir = "C:\LocalAI"
$BackupDir = "C:\LocalAI_Backups"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupPath = Join-Path $BackupDir "DocIntel_Backup_$Timestamp.zip"

Write-Host "Backing up data/ and db/ to $BackupPath..." -ForegroundColor Cyan

if (-not (Test-Path $BackupDir)) {
    New-Item -Path $BackupDir -ItemType Directory -Force
}

Compress-Archive -Path (Join-Path $BaseDir "data"), (Join-Path $BaseDir "db") -DestinationPath $BackupPath

Write-Host "Backup complete!" -ForegroundColor Green
