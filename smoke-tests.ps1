$base = "http://127.0.0.1:8000"
curl.exe -s "$base/api/health/app"
curl.exe -s "$base/api/health/ollama"

$login = Invoke-RestMethod -Method Post -Uri "$base/auth/login" -ContentType "application/json" -Body (@{
  ec_number = "smoke"
  password  = "smoke"
} | ConvertTo-Json)
$token = $login.access_token
$headers = @{ Authorization = "Bearer $token" }

$models = Invoke-RestMethod -Method Get -Uri "$base/api/models/available" -Headers $headers
$model = $models.default_model

$samplePath = Join-Path $PSScriptRoot "app\data\documents\doc_2_requirements.txt"
if (-not (Test-Path $samplePath)) { throw "Missing sample file: $samplePath" }

$upload = Invoke-WebRequest -Method Post -Uri "$base/documents" -Headers $headers -Form @{
  project_name  = "Smoke Project"
  document_type = "txt"
  document_date = "2026-03-11"
  file          = Get-Item $samplePath
}
$uploaded = $upload.Content | ConvertFrom-Json
$docId = $uploaded.id

for ($i = 0; $i -lt 60; $i++) {
  $status = Invoke-RestMethod -Method Get -Uri "$base/api/ingest/$docId/status" -Headers $headers
  "$($status.status) $($status.percent)% $($status.step) $($status.message)" | Write-Host
  if ($status.status -eq "completed") { break }
  if ($status.status -eq "failed") { throw "Ingestion failed: $($status.error_message)" }
  Start-Sleep -Seconds 2
}

$session = Invoke-RestMethod -Method Post -Uri "$base/api/chat/sessions" -Headers $headers -ContentType "application/json" -Body (@{
  document_id = $docId
} | ConvertTo-Json)

$ask = Invoke-RestMethod -Method Post -Uri "$base/api/ask/$docId" -Headers $headers -ContentType "application/json" -Body (@{
  question   = "List the requirements mentioned in this document."
  session_id = $session.session_id
  model      = $model
} | ConvertTo-Json)

$messages = Invoke-RestMethod -Method Get -Uri "$base/api/chat/sessions/$($session.session_id)/messages?limit=100" -Headers $headers
$messages.messages | Select-Object role, status, content | Format-Table -AutoSize
