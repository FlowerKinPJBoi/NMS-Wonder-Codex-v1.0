$ErrorActionPreference = "Stop"

$source = Join-Path $PSScriptRoot "..\src"
$forbidden = @(
  'File\.WriteAll',
  'File\.AppendAll',
  'File\.Create\(',
  'FileMode\.(Create|CreateNew|Append|Truncate)',
  'HttpClient',
  'HttpRequestMessage',
  'PostAsync\(',
  'PutAsync\(',
  'DeleteAsync\('
)

$matches = Get-ChildItem $source -Recurse -File -Include *.cs |
  Select-String -Pattern $forbidden

if ($matches) {
  $matches | ForEach-Object { Write-Error $_.Line }
  throw "Capture companion read-only contract failed."
}

Write-Host "Capture companion read-only contract passed: no file-write or network-upload APIs were found."
