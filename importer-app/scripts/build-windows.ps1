$ErrorActionPreference = 'Stop'
$root = Resolve-Path (Join-Path $PSScriptRoot '..')
$project = Join-Path $root 'src\WonderCodex.Importer\WonderCodex.Importer.csproj'
$selfTest = Join-Path $root 'tools\WonderCodex.Importer.SelfTest\WonderCodex.Importer.SelfTest.csproj'
$output = Join-Path $root 'artifacts\win-x64'

& (Join-Path $PSScriptRoot 'verify-read-only.ps1')
dotnet restore $project
dotnet run --project $selfTest -c Release
dotnet publish $project `
  -c Release `
  -r win-x64 `
  --self-contained true `
  -p:PublishSingleFile=true `
  -p:IncludeNativeLibrariesForSelfExtract=true `
  -p:PublishTrimmed=false `
  -o $output

Write-Host "Windows build created at $output" -ForegroundColor Cyan
