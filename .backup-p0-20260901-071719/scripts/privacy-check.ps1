param()

$ErrorActionPreference = "Stop"

$patterns = @(
  'C:\\Users\\',
  '/Users/',
  '@gmail\.com',
  '@outlook\.com',
  '@yahoo\.com',
  'google-analytics',
  'googletagmanager',
  'facebook\.com/tr',
  'doubleclick',
  'hotjar',
  'segment\.com'
)

$extensions = @(
  ".html",
  ".css",
  ".js",
  ".json",
  ".md",
  ".txt",
  ".yml",
  ".yaml"
)

$files =
  Get-ChildItem . -Recurse -File |
  Where-Object {

    $_.FullName -notmatch '\\\.git\\' -and
    $_.FullName -notmatch '\\backup-' -and
    $extensions -contains $_.Extension

  }


$matches =
  $files |
  Select-String `
    -Pattern $patterns `
    -ErrorAction SilentlyContinue


Write-Host ""
Write-Host "=== PRIVACY CHECK ===" -ForegroundColor Cyan


if ($matches) {

  Write-Host "[WARN] Review required:" -ForegroundColor Yellow

  foreach ($match in $matches) {

    Write-Host `
      "$($match.Path):$($match.LineNumber): $($match.Line.Trim())" `
      -ForegroundColor Yellow
  }

  Write-Host ""
  Write-Host "RESULT: REVIEW REQUIRED" -ForegroundColor Yellow
}
else {

  Write-Host "[PASS] No obvious privacy-sensitive patterns found." `
    -ForegroundColor Green

  Write-Host ""
  Write-Host "RESULT: PASS" -ForegroundColor Green
}
