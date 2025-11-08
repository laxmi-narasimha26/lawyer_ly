$ErrorActionPreference = 'Stop'

Write-Host '==> Starting Postgres + Redis + Backend + Frontend (Docker compose)' -ForegroundColor Cyan
if (-not (Test-Path Env:OPENAI_API_KEY)) {
  Write-Host 'ERROR: Please set OPENAI_API_KEY in your environment.' -ForegroundColor Red
  exit 1
}

docker compose -f docker-compose.local.app.yml up -d --build

Write-Host '==> Waiting for backend to become healthy at http://localhost:8000/health' -ForegroundColor Cyan
$max = 60
for ($i=0; $i -lt $max; $i++) {
  try {
    $resp = Invoke-WebRequest -UseBasicParsing http://localhost:8000/health -TimeoutSec 2
    if ($resp.StatusCode -eq 200) { break }
  } catch {}
  Start-Sleep -Seconds 2
}

try {
  $resp = Invoke-WebRequest -UseBasicParsing http://localhost:8000/health -TimeoutSec 2
  if ($resp.StatusCode -ne 200) { throw 'Backend not healthy' }
  Write-Host '==> Backend is up.' -ForegroundColor Green
} catch {
  Write-Host 'ERROR: Backend did not start. Check docker logs.' -ForegroundColor Red
  docker logs legal-ai-backend-local --tail=200
  exit 1
}

Write-Host '==> Frontend will serve on http://localhost:5173' -ForegroundColor Green
Write-Host '==> Run scripts/smoke_test_local.py to send a few queries.' -ForegroundColor Yellow
