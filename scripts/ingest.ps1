# ingest.ps1

param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectName,
    [Parameter(Mandatory=$true)]
    [string]$Path
)

Write-Host "Ingesting documents from $Path for project '$ProjectName'..." -ForegroundColor Cyan

# Logic here to walk $Path and call /api/upload for each file
# For now, let's just use curl/httpx as a demonstration

# Get project_id
$project = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/projects?name=$ProjectName" -Method Post
$projectId = $project.id

Get-ChildItem -Path $Path -File | ForEach-Object {
    Write-Host "Uploading $($_.Name)..." -ForegroundColor Gray
    curl.exe -X POST "http://127.0.0.1:8000/api/upload?project_id=$projectId" -F "files=@$($_.FullName)"
}

Write-Host "Bulk ingestion complete!" -ForegroundColor Green
