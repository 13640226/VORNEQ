param()

$files = @(
  ".\assets\css\tokens.css",
  ".\assets\css\themes.css",
  ".\assets\css\base.css",
  ".\assets\css\components.css",
  ".\playground.html",
  ".\playground.js",
  ".\scripts\serve-playground.ps1"
)

Write-Host ""
Write-Host "=== FILE CHECK ===" -ForegroundColor Cyan

foreach ($file in $files) {
  if (Test-Path $file) {
    $size = (Get-Item $file).Length
    Write-Host "[PASS] $file -- $size bytes" -ForegroundColor Green
  }
  else {
    Write-Host "[FAIL] $file -- NOT FOUND" -ForegroundColor Red
  }
}

Write-Host ""
Write-Host "=== REFERENCES ===" -ForegroundColor Cyan

Select-String -Path .\playground.html -Pattern `
"tokens.css","themes.css","base.css","components.css","playground.js"

Write-Host ""
Write-Host "=== DONE ===" -ForegroundColor Green
