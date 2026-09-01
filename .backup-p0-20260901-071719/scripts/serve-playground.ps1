param(
  [int]$Port = 8081
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================" -ForegroundColor DarkGray
Write-Host " SAMAN KHERAD — COMPONENT PLAYGROUND" -ForegroundColor Cyan
Write-Host " Red Editorial Visual Direction" -ForegroundColor DarkRed
Write-Host "========================================" -ForegroundColor DarkGray
Write-Host ""

Write-Host "Local:" -ForegroundColor Yellow
Write-Host "http://127.0.0.1:$Port/playground.html" -ForegroundColor Green

Write-Host ""
Write-Host "Press Ctrl+C to stop." -ForegroundColor Yellow
Write-Host ""

python -m http.server $Port --bind 0.0.0.0
