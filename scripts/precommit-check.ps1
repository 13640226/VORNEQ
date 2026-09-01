param()

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=== PRE-COMMIT CHECK ===" -ForegroundColor Cyan

Write-Host ""
Write-Host "1. Integrity" -ForegroundColor Yellow

powershell -ExecutionPolicy Bypass `
    -File .\scripts\p0-integrity-check.ps1

if ($LASTEXITCODE -ne 0) {
    Write-Host "Integrity check failed." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "2. Privacy" -ForegroundColor Yellow

powershell -ExecutionPolicy Bypass `
    -File .\scripts\privacy-check.ps1

Write-Host ""
Write-Host "3. Git diff check" -ForegroundColor Yellow

git diff --check

if ($LASTEXITCODE -ne 0) {
    Write-Host "git diff --check failed." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "4. Git status" -ForegroundColor Yellow

git status --short

Write-Host ""
Write-Host "PRE-COMMIT CHECK COMPLETE" -ForegroundColor Green
