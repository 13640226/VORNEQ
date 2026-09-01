param()

$ErrorActionPreference = "Stop"

$requiredFiles = @(
  ".\assets\css\tokens.css",
  ".\assets\css\themes.css",
  ".\assets\css\base.css",
  ".\assets\css\components.css",
  ".\playground.html",
  ".\playground.js",
  ".\scripts\serve-playground.ps1"
)

$failed = $false

Write-Host ""
Write-Host "=== P0 RED VISUAL BUILD CHECK ===" -ForegroundColor Cyan

foreach ($file in $requiredFiles) {

  if (-not (Test-Path $file)) {

    Write-Host "[FAIL] $file -- NOT FOUND" -ForegroundColor Red

    $failed = $true

    continue
  }

  $length =
    (Get-Item $file).Length


  if ($length -le 0) {

    Write-Host "[FAIL] $file -- EMPTY" -ForegroundColor Red

    $failed = $true
  }
  else {

    Write-Host "[PASS] $file -- $length bytes" -ForegroundColor Green
  }
}


Write-Host ""
Write-Host "=== REFERENCES ===" -ForegroundColor Cyan


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

    Write-Host "[PASS] $reference" -ForegroundColor Green
  }
  else {

    Write-Host "[FAIL] $reference -- MISSING" -ForegroundColor Red

    $failed = $true
  }
}


Write-Host ""
Write-Host "=== RED PALETTE ===" -ForegroundColor Cyan


$paletteChecks = @(
  @{ Path=".\assets\css\tokens.css"; Pattern="#7a2a2a" },
  @{ Path=".\assets\css\themes.css"; Pattern="#792c2c" },
  @{ Path=".\assets\css\themes.css"; Pattern="#b84a4a" }
)


foreach ($check in $paletteChecks) {

  $match =
    Select-String `
      -Path $check.Path `
      -Pattern $check.Pattern `
      -Quiet


  if ($match) {

    Write-Host "[PASS] $($check.Pattern)" -ForegroundColor Green
  }
  else {

    Write-Host "[FAIL] $($check.Pattern)" -ForegroundColor Red

    $failed = $true
  }
}


Write-Host ""

if ($failed) {

  Write-Host "RESULT: FAIL" -ForegroundColor Red

  exit 1
}
else {

  Write-Host "RESULT: PASS" -ForegroundColor Green
}
