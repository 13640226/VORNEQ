param()

$ErrorActionPreference = "Stop"

$projectRoot =
  Split-Path -Parent $PSScriptRoot

Set-Location $projectRoot

$requiredFiles = @(
  ".\assets\css\tokens.css",
  ".\assets\css\themes.css",
  ".\assets\css\base.css",
  ".\assets\css\components.css",
  ".\playground.html",
  ".\playground.js",
  ".\scripts\serve-playground.ps1",
  ".\scripts\privacy-check.ps1"
)

$failed = $false

Write-Host ""
Write-Host "=== P0 INTEGRITY CHECK ===" -ForegroundColor Cyan

foreach ($file in $requiredFiles) {

  if (-not (Test-Path $file)) {

    Write-Host `
      "[FAIL] $file -- NOT FOUND" `
      -ForegroundColor Red

    $failed = $true

    continue
  }


  $size =
    (Get-Item $file).Length


  if ($size -le 0) {

    Write-Host `
      "[FAIL] $file -- EMPTY" `
      -ForegroundColor Red

    $failed = $true
  }
  else {

    Write-Host `
      "[PASS] $file -- $size bytes" `
      -ForegroundColor Green
  }
}


Write-Host ""
Write-Host "=== HTML REFERENCES ===" -ForegroundColor Cyan

$html =
  Get-Content .\playground.html -Raw


$references = @(
  "./assets/css/tokens.css",
  "./assets/css/themes.css",
  "./assets/css/base.css",
  "./assets/css/components.css",
  "./playground.js"
)


foreach ($reference in $references) {

  if ($html.Contains($reference)) {

    Write-Host `
      "[PASS] $reference" `
      -ForegroundColor Green
  }
  else {

    Write-Host `
      "[FAIL] $reference" `
      -ForegroundColor Red

    $failed = $true
  }
}


Write-Host ""
Write-Host "=== REQUIRED COMPONENTS ===" -ForegroundColor Cyan

$requiredMarkers = @(
  "drawerTrigger",
  "pg-hero__grid",
  "pg-metadata",
  "pg-utility",
  "pg-gallery",
  "accordion-item",
  "editorial-grid",
  "method-list",
  "article-grid",
  "related-grid",
  "footer-accordion"
)


foreach ($marker in $requiredMarkers) {

  if ($html.Contains($marker)) {

    Write-Host `
      "[PASS] $marker" `
      -ForegroundColor Green
  }
  else {

    Write-Host `
      "[FAIL] $marker -- MISSING" `
      -ForegroundColor Red

    $failed = $true
  }
}


Write-Host ""

if ($failed) {

  Write-Host "RESULT: FAIL" -ForegroundColor Red

  exit 1
}

Write-Host "RESULT: PASS" -ForegroundColor Green
exit 0
