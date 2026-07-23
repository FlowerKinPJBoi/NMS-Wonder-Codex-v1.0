$ErrorActionPreference = 'Stop'
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
Push-Location $repoRoot
try {
  $tracked = @(git ls-files)
  $forbiddenPatterns = @(
    '(?i)(^|/)containers\.index$',
    '(?i)\.hg$',
    '(?i)(^|/)slot[^/]*\.json$',
    '(?i)(^|/)save[^/]*\.json$',
    '(?i)(^|/)wgs/',
    '(?i)(^|/)private-fixtures/',
    '(?i)(^|/)research/raw/'
  )

  $violations = @()
  foreach ($file in $tracked) {
    foreach ($pattern in $forbiddenPatterns) {
      if ($file -match $pattern) {
        $violations += $file
        break
      }
    }
  }

  if ($violations.Count -gt 0) {
    Write-Error ("Private save-data policy failed:`n" + (($violations | Sort-Object -Unique) -join "`n"))
  }

  Write-Host 'No private save fixtures are tracked.' -ForegroundColor Green
}
finally {
  Pop-Location
}
