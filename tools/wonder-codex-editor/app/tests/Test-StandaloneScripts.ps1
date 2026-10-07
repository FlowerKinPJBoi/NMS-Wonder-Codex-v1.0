param([string]$PackageRoot = (Join-Path $PSScriptRoot '../standalone-package'))
$ErrorActionPreference = 'Stop'
$PackageRoot = [IO.Path]::GetFullPath($PackageRoot)
$results = [Collections.Generic.List[object]]::new()
function Check { param([bool]$Ok,[string]$Name) if(!$Ok){throw ('FAIL: '+$Name)}; $results.Add([pscustomobject]@{name=$Name;passed=$true});Write-Host ('PASS: '+$Name) }
function Expect-Throw { param([scriptblock]$Action,[string]$Like,[string]$Name)
    $caught=$null;try { & $Action } catch {$caught=$_.Exception.Message}
    Check ($null -ne $caught -and $caught -like $Like) $Name
}
function Sha([string]$Path){(Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()}
$cases=Join-Path $PSScriptRoot ('cases-'+[Guid]::NewGuid().ToString('N'))
$null=New-Item -ItemType Directory -Path $cases
try {
    foreach($p in Get-ChildItem -LiteralPath $PackageRoot -Filter '*.ps1' -Recurse) {
        $tokens=$null;$errors=$null
        $null=[Management.Automation.Language.Parser]::ParseFile($p.FullName,[ref]$tokens,[ref]$errors)
        Check ($errors.Count -eq 0) ('PowerShell parser: '+[IO.Path]::GetRelativePath($PackageRoot,$p.FullName))
    }
    . (Join-Path $PackageRoot 'app/Dependency-Tools.ps1')
    Assert-PackageFiles -Root (Join-Path $PackageRoot 'app') -Manifest (Join-Path $PackageRoot 'PACKAGE-CHECKSUMS.json')
    Check $true 'Complete package passes manifest verification'
    $packageFiles=Join-Path $cases 'valid package files with spaces'
    $null=New-Item -ItemType Directory -Path $packageFiles
    $entries=@();foreach($name in @('One.txt','sub dir/Two.txt',('sub dir/Unicode-'+[char]0x03A9+'.txt'))) {
        $path=Join-Path $packageFiles $name;$null=New-Item -ItemType Directory -Path (Split-Path $path -Parent) -Force
        [IO.File]::WriteAllText($path,('fixture: '+$name))
        $entries += [pscustomobject]@{path=$name;bytes=(Get-Item -LiteralPath $path).Length;sha256=(Sha $path)}
    }
    $manifest=Join-Path $cases 'manifest.json'
    ConvertTo-Json -InputObject @($entries) | Set-Content -LiteralPath $manifest -Encoding utf8
    Assert-PackageFiles -Root $packageFiles -Manifest $manifest;Check $true 'Manifest supports spaces, subdirectories and Unicode'
    $one=Join-Path $packageFiles 'One.txt';$original=[IO.File]::ReadAllBytes($one)
    [IO.File]::WriteAllText($one,'broken')
    Expect-Throw {Assert-PackageFiles -Root $packageFiles -Manifest $manifest} '*checksum failed*' 'Corrupt package files blocked'
    Check ([IO.File]::ReadAllText($one) -eq 'broken') 'Package file verifier does not modify corrupt files'
    [IO.File]::WriteAllBytes($one,$original)
    Remove-Item -LiteralPath $one
    Expect-Throw {Assert-PackageFiles -Root $packageFiles -Manifest $manifest} '*Missing package file*' 'Missing package files blocked'
    [IO.File]::WriteAllBytes($one,$original)
    $bad=@($entries | ForEach-Object {[pscustomobject]@{path=$_.path;bytes=$_.bytes;sha256=$_.sha256}})
    $bad[0].path='../outside.txt';$outside=Join-Path $cases 'outside.txt';[IO.File]::WriteAllText($outside,'sentinel')
    ConvertTo-Json -InputObject @($bad) | Set-Content -LiteralPath $manifest -Encoding utf8
    Expect-Throw {Assert-PackageFiles -Root $packageFiles -Manifest $manifest} '*Invalid package manifest path*' 'Manifest directory traversal blocked'
    Check ([IO.File]::ReadAllText($outside) -eq 'sentinel') 'Traversal test preserves outside sentinel'
    $bad[0].path=$outside;ConvertTo-Json -InputObject @($bad) | Set-Content -LiteralPath $manifest -Encoding utf8
    Expect-Throw {Assert-PackageFiles -Root $packageFiles -Manifest $manifest} '*Invalid package manifest path*' 'Absolute manifest path blocked'
    ConvertTo-Json -InputObject @($entries[0]) | Set-Content -LiteralPath $manifest -Encoding utf8
    Expect-Throw {Assert-PackageFiles -Root $packageFiles -Manifest $manifest} '*manifest is incomplete*' 'Incomplete manifest blocked'

    $script:DownloadCalls=0;$script:DownloadBehavior='forbidden'
    $script:FixtureEngine=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../lib/engine.jar'))
    function Invoke-WebRequest {
        param([string]$Uri,[string]$OutFile,[switch]$UseBasicParsing,[int]$TimeoutSec)
        $script:DownloadCalls++
        Check ($Uri -eq $script:EngineUrl) 'Downloader uses pinned official engine URL'
        if($script:DownloadBehavior -eq 'forbidden'){throw 'Network not allowed for this test case'}
        if($script:DownloadBehavior -eq 'valid'){Copy-Item -LiteralPath $script:FixtureEngine -Destination $OutFile;return}
        if($script:DownloadBehavior -eq 'corrupt'){[IO.File]::WriteAllText($OutFile,'invalid downloaded binary');return}
        if($script:DownloadBehavior -eq 'error'){[IO.File]::WriteAllText($OutFile,'partial');throw 'Simulated network failure'}
        if($script:DownloadBehavior -eq 'race'){
            Copy-Item -LiteralPath $script:FixtureEngine -Destination $OutFile
            [IO.File]::WriteAllText((Join-Path (Split-Path $OutFile -Parent) 'NMSSaveEditor.jar'),'existing sentinel')
            return
        }
        throw 'Unknown test download mode'
    }
    function EngineCase([string]$Name) {$p=Join-Path $cases $Name;$null=New-Item -ItemType Directory -Path (Join-Path $p 'engine');return $p}
    $valid=EngineCase 'valid-engine';$validFile=Join-Path $valid 'engine/NMSSaveEditor.jar'
    Copy-Item -LiteralPath $script:FixtureEngine -Destination $validFile
    $hash=Sha $validFile;Get-VerifiedEngine -AppRoot $valid
    Check ($script:DownloadCalls -eq 0 -and (Sha $validFile) -eq $hash) 'Valid existing engine reused without network or replacement'
    $corrupt=EngineCase 'corrupt-engine';$corruptFile=Join-Path $corrupt 'engine/NMSSaveEditor.jar';[IO.File]::WriteAllText($corruptFile,'sentinel')
    Expect-Throw {Get-VerifiedEngine -AppRoot $corrupt} '*existing engine checksum is incorrect*' 'Corrupt existing engine blocked'
    Check ($script:DownloadCalls -eq 0 -and [IO.File]::ReadAllText($corruptFile) -eq 'sentinel') 'Existing corrupt engine never overwritten and download not attempted'
    $download=EngineCase 'download-success';$script:DownloadBehavior='valid';Get-VerifiedEngine -AppRoot $download
    Check ((Sha (Join-Path $download 'engine/NMSSaveEditor.jar')) -eq $script:EngineSha) 'Verified engine download is installed exactly'
    Check (@(Get-ChildItem -LiteralPath (Join-Path $download 'engine') -Filter '*.partial').Count -eq 0) 'Successful engine download leaves no partial file'
    $badDownload=EngineCase 'download-corrupt';$script:DownloadBehavior='corrupt'
    Expect-Throw {Get-VerifiedEngine -AppRoot $badDownload} '*download failed its checksum*' 'Corrupt engine download rejected'
    Check (!(Test-Path -LiteralPath (Join-Path $badDownload 'engine/NMSSaveEditor.jar')) -and @(Get-ChildItem -LiteralPath (Join-Path $badDownload 'engine')).Count -eq 0) 'Corrupt download is removed without an installed engine'
    $failedDownload=EngineCase 'download-error';$script:DownloadBehavior='error'
    Expect-Throw {Get-VerifiedEngine -AppRoot $failedDownload} '*Simulated network failure*' 'Download error propagates'
    Check (@(Get-ChildItem -LiteralPath (Join-Path $failedDownload 'engine')).Count -eq 0) 'Network failure removes partial download'
    $raced=EngineCase 'download-race';$script:DownloadBehavior='race'
    Expect-Throw {Get-VerifiedEngine -AppRoot $raced} '*' 'Concurrent destination creation blocks replace'
    Check ([IO.File]::ReadAllText((Join-Path $raced 'engine/NMSSaveEditor.jar')) -eq 'existing sentinel') 'Concurrent existing engine is never overwritten'
    Check (@(Get-ChildItem -LiteralPath (Join-Path $raced 'engine') -Filter '*.partial').Count -eq 0) 'Concurrent destination race cleans up temporary download'
    [pscustomobject]@{passed=$results.Count;powerShell=$PSVersionTable.PSVersion.ToString();platform=$PSVersionTable.OS;checks=$results;limits=@('Parsed and executed helper functions under PowerShell 7.6.6 on Linux; Windows PowerShell 5.1 execution and Windows launcher execution remain untested.','Network downloads mocked with the exact verified engine fixture; production scripts never changed.')} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'standalone-script-results.json') -Encoding utf8
    Write-Host ('STANDALONE_SCRIPT_TEST passed='+$results.Count)
} finally {
    if(Test-Path -LiteralPath $cases){Remove-Item -LiteralPath $cases -Recurse -Force}
}
