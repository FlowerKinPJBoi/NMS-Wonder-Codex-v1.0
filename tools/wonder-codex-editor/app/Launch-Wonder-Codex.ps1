$ErrorActionPreference = 'Stop'
try {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT -or ![Environment]::Is64BitOperatingSystem) { throw 'This build requires 64-bit Windows.' }
    . (Join-Path $PSScriptRoot 'Dependency-Tools.ps1')
    Test-EditorStartup -AppRoot $PSScriptRoot
    $reports = Join-Path $PSScriptRoot 'reports'
    $null = New-Item -ItemType Directory -Path $reports -Force
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
    $javaw = Join-Path $PSScriptRoot 'runtime\bin\javaw.exe'
    $process = Start-Process -FilePath $javaw -ArgumentList '-cp','WonderCodexEditor.jar;CosmosBridge.jar;engine\NMSSaveEditor.jar','nomanssave.WCEditorLauncher' -WorkingDirectory $PSScriptRoot -RedirectStandardOutput (Join-Path $reports ('startup-' + $stamp + '.log')) -RedirectStandardError (Join-Path $reports ('startup-' + $stamp + '-errors.log')) -PassThru
    Write-Host ('Wonder Codex Editor started. Process ' + $process.Id)
} catch {
    $message = $_.Exception.Message
    Write-Host $message -ForegroundColor Red
    try {
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.MessageBox]::Show($message,'Wonder Codex Editor could not start','OK','Error') | Out-Null
    } catch { }
    exit 1
}
