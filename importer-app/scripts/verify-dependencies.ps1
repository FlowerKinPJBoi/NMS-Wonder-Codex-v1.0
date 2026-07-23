$ErrorActionPreference = 'Stop'

$project = Join-Path $PSScriptRoot '..\src\WonderCodex.Importer\WonderCodex.Importer.csproj'
[xml]$xml = Get-Content $project -Raw

$allowed = @(
  'Avalonia',
  'Avalonia.Desktop',
  'Avalonia.Themes.Fluent',
  'Avalonia.Fonts.Inter'
)

$packages = @($xml.Project.ItemGroup.PackageReference | ForEach-Object { $_.Include })
$unexpected = @($packages | Where-Object { $_ -and ($_ -notin $allowed) })

if ($unexpected.Count -gt 0) {
  Write-Error ("Dependency policy failed. Unreviewed direct package(s): " + ($unexpected -join ', '))
}

$forbiddenText = @('GPL', 'AGPL', 'libNOM.map')
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$sourceFiles = Get-ChildItem $repoRoot -Recurse -File -Include *.cs,*.csproj,*.props,*.targets

foreach ($file in $sourceFiles) {
  $text = Get-Content $file.FullName -Raw
  foreach ($marker in $forbiddenText) {
    if ($text.Contains($marker, [System.StringComparison]::OrdinalIgnoreCase)) {
      Write-Error "Dependency policy failed: '$marker' found in $($file.FullName)"
    }
  }
}

Write-Host 'Dependency allowlist passed.' -ForegroundColor Green
