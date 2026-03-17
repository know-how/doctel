param(
  [string]$BaseUrl = "http://localhost:8000",
  [string]$Token = "",
  [switch]$DropUsers
)

$confirm = Read-Host "Type RESET_DOCTEL to confirm a HARD reset (DB + Chroma will be cleared)"
if ($confirm -ne "RESET_DOCTEL") {
  Write-Host "Cancelled."
  exit 1
}

if (-not $Token) {
  $Token = Read-Host "Paste admin Bearer token (docintel_auth_token)"
}

$body = @{
  confirm_token = "RESET_DOCTEL"
  drop_users = [bool]$DropUsers
} | ConvertTo-Json

$headers = @{
  Authorization = "Bearer $Token"
  "Content-Type" = "application/json"
}

Write-Host "Calling $BaseUrl/admin/reset/hard ..."
try {
  $res = Invoke-RestMethod -Method Post -Uri "$BaseUrl/admin/reset/hard" -Headers $headers -Body $body
  $res | ConvertTo-Json -Depth 6
} catch {
  Write-Host $_.Exception.Message
  if ($_.ErrorDetails -and $_.ErrorDetails.Message) {
    Write-Host $_.ErrorDetails.Message
  }
  exit 1
}
