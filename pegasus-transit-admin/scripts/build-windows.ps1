$ErrorActionPreference = 'Stop'
$root = Resolve-Path (Join-Path $PSScriptRoot '..')
$project = Join-Path $root 'src\WonderCodex.PegasusTransit\WonderCodex.PegasusTransit.csproj'
$selfTest = Join-Path $root 'tools\WonderCodex.PegasusTransit.SelfTest\WonderCodex.PegasusTransit.SelfTest.csproj'
$output = Join-Path $root 'artifacts\win-x64'

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

Copy-Item (Join-Path $root 'README.md') (Join-Path $output 'PEGASUS_TRANSIT_README.md')
Copy-Item (Join-Path $root '..\THIRD_PARTY_NOTICES.md') (Join-Path $output 'THIRD_PARTY_NOTICES.md')
Write-Host "Pegasus Transit Windows build created at $output" -ForegroundColor Cyan
