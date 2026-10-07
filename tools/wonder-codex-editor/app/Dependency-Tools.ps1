$ErrorActionPreference = 'Stop'
$script:EngineUrl = 'https://raw.githubusercontent.com/goatfungus/NMSSaveEditor/6047315f47321e2a8400d38bf8d904bcca88bb8d/NMSSaveEditor.jar'
$script:EngineSha = 'ef898af4e1c4c0c25a6c6529dfea52520cda243383544d8d358ad10aae3a178c'
$script:EngineSize = 70523384

function Assert-PackageFiles {
    param([Parameter(Mandatory=$true)][string]$Root, [Parameter(Mandatory=$true)][string]$Manifest)
    $rootFull = [IO.Path]::GetFullPath($Root).TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
    $entries = Get-Content -LiteralPath $Manifest -Raw | ConvertFrom-Json
    if ($null -eq $entries -or @($entries).Count -lt 3) { throw 'The setup manifest is incomplete. Extract the complete setup ZIP again.' }
    foreach ($entry in $entries) {
        $relative = ([string]$entry.path).Replace('/', [IO.Path]::DirectorySeparatorChar)
        if ([IO.Path]::IsPathRooted($relative)) { throw 'Invalid package manifest path.' }
        $file = [IO.Path]::GetFullPath((Join-Path $rootFull $relative))
        if (!$file.StartsWith($rootFull, [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid package manifest path.' }
        if (!(Test-Path -LiteralPath $file -PathType Leaf)) { throw ('Missing package file: ' + $entry.path + '. Extract the complete setup ZIP again.') }
        if ((Get-Item -LiteralPath $file).Length -ne [long]$entry.bytes -or (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash -ne [string]$entry.sha256) {
            throw ('Package checksum failed: ' + $entry.path + '. Download and extract a fresh setup ZIP.')
        }
    }
}

function Get-VerifiedEngine {
    param([Parameter(Mandatory=$true)][string]$AppRoot)
    $engineDir = Join-Path $AppRoot 'engine'
    $engineFile = Join-Path $engineDir 'NMSSaveEditor.jar'
    if (Test-Path -LiteralPath $engineFile) {
        if ((Get-Item -LiteralPath $engineFile).Length -eq $script:EngineSize -and (Get-FileHash -LiteralPath $engineFile -Algorithm SHA256).Hash -eq $script:EngineSha) { return }
        throw 'The existing engine checksum is incorrect. Install into a fresh folder; no existing files were replaced.'
    }
    $null = New-Item -ItemType Directory -Path $engineDir -Force
    $partial = Join-Path $engineDir ('download-' + [Guid]::NewGuid().ToString('N') + '.partial')
    try {
        Write-Host 'Downloading the matching GoatFungus engine (about 67 MB)...'
        [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
        $previousProgress = $ProgressPreference
        try {
            $ProgressPreference = 'SilentlyContinue'
            Invoke-WebRequest -Uri $script:EngineUrl -OutFile $partial -UseBasicParsing -TimeoutSec 300
        } finally { $ProgressPreference = $previousProgress }
        if ((Get-Item -LiteralPath $partial).Length -ne $script:EngineSize -or (Get-FileHash -LiteralPath $partial -Algorithm SHA256).Hash -ne $script:EngineSha) {
            throw 'The engine download failed its checksum. Nothing was installed. Check your connection and run SETUP.bat again.'
        }
        Move-Item -LiteralPath $partial -Destination $engineFile
        Write-Host 'Engine checksum verified.'
    } finally {
        if (Test-Path -LiteralPath $partial) { Remove-Item -LiteralPath $partial -Force }
    }
}

function Test-EditorStartup {
    param([Parameter(Mandatory=$true)][string]$AppRoot)
    $java = Join-Path $AppRoot 'runtime\bin\java.exe'
    if (!(Test-Path -LiteralPath $java)) { throw 'Bundled Java is missing. Run SETUP.bat from a freshly extracted setup package.' }
    Push-Location -LiteralPath $AppRoot
    try {
        $output = & $java -cp 'WonderCodexEditor.jar;CosmosBridge.jar;engine\NMSSaveEditor.jar' nomanssave.WCEditorLauncher --verify 2>&1
        $javaExitCode = $LASTEXITCODE
        if ($javaExitCode -ne 0) { throw ('Startup verification failed: ' + ($output -join [Environment]::NewLine)) }
        Write-Host ($output -join [Environment]::NewLine)
    } finally { Pop-Location }
}
