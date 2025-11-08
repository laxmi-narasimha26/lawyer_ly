$ErrorActionPreference = 'Stop'

param(
  [string]$RepoName = "legal-ai-demo",
  [string]$Visibility = "private", # private|public
  [switch]$UseGitHubCLI
)

function Require-Cli($name) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: '$name' is not installed or not on PATH." -ForegroundColor Red
    exit 1
  }
}

Require-Cli git

# Safety: prevent committing secrets accidentally
Write-Host "Checking for embedded API keys in config files..." -ForegroundColor Yellow
$suspects = @(
  "backend/config/local_settings.py",
  ".env.local",
  "frontend/.env.local"
) | Where-Object { Test-Path $_ }

foreach ($file in $suspects) {
  $content = Get-Content $file -Raw
  if ($content -match "sk-" -or $content -match "OPENAI_API_KEY" -and $content -match "=") {
    Write-Host "WARNING: Secrets detected in '$file'. Remove or move to env vars before pushing." -ForegroundColor Red
  }
}

if (-not (Test-Path .git)) {
  git init
}

git add .
git commit -m "Initial push: local demo stack (backend+frontend+infra)" --allow-empty
git branch -M main

if ($UseGitHubCLI) {
  Require-Cli gh
  gh repo create $RepoName --$Visibility --source . --remote origin --push
} else {
  Write-Host "No GitHub CLI selected. To push manually run:" -ForegroundColor Cyan
  Write-Host "  git remote add origin https://github.com/<your-user>/$RepoName.git"
  Write-Host "  git push -u origin main"
}

Write-Host "Done. Review your repo on GitHub." -ForegroundColor Green

