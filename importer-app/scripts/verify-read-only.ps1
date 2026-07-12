$ErrorActionPreference = 'Stop'
$sourceRoot = Join-Path $PSScriptRoot '..\src'
$forbidden = @(
  'File.WriteAll',
  'File.OpenWrite',
  'File.Create(',
  'File.Delete(',
  'File.Move(',
  'Directory.Delete(',
  'FileAccess.Write',
  'FileMode.Create',
  'FileMode.Truncate',
  'FileMode.Append'
)

$violations = @()
Get-ChildItem $sourceRoot -Recurse -Filter *.cs | ForEach-Object {
  $text = Get-Content $_.FullName -Raw
  foreach ($marker in $forbidden) {
    if ($text.Contains($marker)) {
      $violations += "$marker in $($_.FullName)"
    }
  }
}

if ($violations.Count -gt 0) {
  Write-Error ("Read-only contract failed:`n" + ($violations -join "`n"))
}

Write-Host 'Read-only source contract passed.' -ForegroundColor Green
