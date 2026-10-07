param(
    [string]$InstallRoot = '',
    [switch]$NoLaunch
)
$ErrorActionPreference = 'Stop'
$stage = $null
try {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT -or ![Environment]::Is64BitOperatingSystem) { throw 'This package requires 64-bit Windows 10 or later.' }
    if ([string]::IsNullOrWhiteSpace($InstallRoot)) { $InstallRoot = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'WonderCodexEditor\1.0.0-direct' }
    $InstallRoot = [IO.Path]::GetFullPath($InstallRoot)
    $setupRoot = [IO.Path]::GetFullPath($PSScriptRoot).TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
    if ($InstallRoot.StartsWith($setupRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Choose an install folder outside the extracted setup folder.' }
    if (Test-Path -LiteralPath $InstallRoot) { throw ('That install folder already exists: ' + $InstallRoot + '. Use its Start Wonder Codex.bat, or choose a new -InstallRoot folder. Existing files were preserved.') }
    $packageFiles = Join-Path $PSScriptRoot 'app'
    . (Join-Path $packageFiles 'Dependency-Tools.ps1')
    Write-Host 'Checking the complete Wonder Codex package...'
    Assert-PackageFiles -Root $packageFiles -Manifest (Join-Path $PSScriptRoot 'PACKAGE-CHECKSUMS.json')
    $parent = Split-Path -Parent $InstallRoot
    $null = New-Item -ItemType Directory -Path $parent -Force
    $stage = Join-Path $parent ('.wonder-codex-setup-' + [Guid]::NewGuid().ToString('N'))
    Copy-Item -LiteralPath $packageFiles -Destination $stage -Recurse
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'PACKAGE-CHECKSUMS.json') -Destination $stage
    $thirdParty = Join-Path $PSScriptRoot 'third-party'
    if (Test-Path -LiteralPath $thirdParty) { Copy-Item -LiteralPath $thirdParty -Destination $stage -Recurse }
    Assert-PackageFiles -Root $stage -Manifest (Join-Path $stage 'PACKAGE-CHECKSUMS.json')
    Get-VerifiedEngine -AppRoot $stage
    Test-EditorStartup -AppRoot $stage
    [IO.Directory]::Move($stage, $InstallRoot)
    $stage = $null
    $installInfo = @{ version='1.0.0-direct'; installed_at=[DateTime]::UtcNow.ToString('o'); location=$InstallRoot }
    $installInfo | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $InstallRoot 'install-info.json') -Encoding UTF8
    try {
        $desktopDir = [Environment]::GetFolderPath('DesktopDirectory')
        $shortcutPath = Join-Path $desktopDir 'Wonder Codex Editor 1.0.0 Direct UI.lnk'
        $shell = New-Object -ComObject WScript.Shell
        $shortcut = $shell.CreateShortcut($shortcutPath)
        $shortcut.TargetPath = Join-Path ([Environment]::GetFolderPath('System')) 'WindowsPowerShell\v1.0\powershell.exe'
        $shortcut.Arguments = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + (Join-Path $InstallRoot 'Launch-Wonder-Codex.ps1') + '"'
        $shortcut.WorkingDirectory = $InstallRoot
        $shortcut.Description = 'Wonder Codex Editor 1.0.0 Direct UI'
        $shortcut.IconLocation = (Join-Path $InstallRoot 'assets\WonderCodex.ico') + ',0'
        $shortcut.Save()
        Write-Host ('Desktop shortcut: ' + $shortcutPath)
    } catch { Write-Warning ('Installed, but could not create a Desktop shortcut. Use Start Wonder Codex.bat in ' + $InstallRoot) }
    Write-Host ('Installed successfully: ' + $InstallRoot)
    Write-Host 'No previous COSMOS folder or separately installed Java is needed.'
    if (!$NoLaunch) { & (Join-Path $InstallRoot 'Launch-Wonder-Codex.ps1') }
    exit 0
} catch {
    Write-Host ''
    Write-Host ('SETUP DID NOT COMPLETE: ' + $_.Exception.Message) -ForegroundColor Red
    if ($stage -and (Test-Path -LiteralPath $stage)) { Remove-Item -LiteralPath $stage -Recurse -Force }
    exit 1
}
