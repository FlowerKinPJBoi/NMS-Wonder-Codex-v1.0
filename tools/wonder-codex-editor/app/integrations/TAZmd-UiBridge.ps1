<#
CREATOR-REVIEW ADAPTER. See release test results for Windows/app versions verified.
This original adapter invokes the unmodified TAZmd application through Windows UIA.
It contains no optimizer algorithm, binaries, copied assets, or private reflection.

Required caller: powershell.exe -NoProfile -STA -File <this script> ...
The Java coordinator must check versions/executable identity, supply a fresh private
JobDir, independently validate prefill.json against its immutable export, and only
then create JobDir\continue. Create JobDir\abort to cancel. It must validate any
optimized.json as an exact Objects permutation before staging it in the editor.

Controls grounded in supplied TAZmd 1.5.0 compiled AXAML:
  btnPaste = Paste All; btnCopy = Copy All; btnOp = Optimize Corvette;
  chkAutoOptimize; chkAutoDelete.
Its Avalonia 11.2.3 ControlAutomationPeer falls back to Name for AutomationId.
Unknown/new UI, missing IDs, startup modals, or inaccessible patterns fail closed.
No coordinate clicks, SendKeys, process injection, Save action, or game save writes.

Protocol: status.txt = working | prefill | done | error
prefill.json then prefill.ready appear before status=prefill.
Only direct mode writes optimized.json. Errors use error.txt. Files are atomic UTF-8
without BOM. The official app stays open in either mode, including errors.
Deadlines bound polling; caller must also impose a process timeout because a broken
third-party UIA provider can block a synchronous Windows accessibility call itself.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$OptimizerPath,
    [Parameter(Mandatory = $true)][string]$InputJson,
    [Parameter(Mandatory = $true)][string]$JobDir,
    [Parameter(Mandatory = $true)][ValidateSet('direct', 'handoff')][string]$Mode
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$script:jobPath = $null
$script:jobOwned = $false
$script:appProcess = $null
$script:appWindow = $null
$script:appId = 0
$script:lastClipboardText = $null
$script:lastClipboardSequence = [uint32]0
$script:clipboardTouched = $false
$script:clipboardSnapshot = $null
$script:clipboardWasEmpty = $false
$script:clipboardSnapshotReady = $false
$script:clock = [Diagnostics.Stopwatch]::StartNew()
$exitCode = 1

function Write-AtomicText([string]$Name, [string]$Text) {
    $target = Join-Path $script:jobPath $Name
    $temporary = Join-Path $script:jobPath ('.' + $Name + '.' + [Guid]::NewGuid().ToString('N') + '.tmp')
    try {
        [IO.File]::WriteAllText($temporary, $Text, (New-Object Text.UTF8Encoding($false)))
        if ([IO.File]::Exists($target)) {
            if (([IO.File]::GetAttributes($target) -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'A job output is a link; refusing to replace it.' }
            # Windows PowerShell 5.1 converts ordinary $null to an empty string for
            # this overload; NullString preserves the intended no-backup argument.
            [IO.File]::Replace($temporary, $target, [NullString]::Value)
        } else { [IO.File]::Move($temporary, $target) }
    } finally {
        if ([IO.File]::Exists($temporary)) { [IO.File]::Delete($temporary) }
    }
}

function New-Deadline([int]$Seconds) { return ($script:clock.ElapsedMilliseconds + [long]($Seconds * 1000)) }
function Assert-Active([long]$Deadline) {
    if ($script:clock.ElapsedMilliseconds -gt $Deadline) { throw 'The TAZmd control did not become ready in time. Use the manual export/open/import workflow.' }
    if ([IO.File]::Exists((Join-Path $script:jobPath 'abort'))) { throw 'The editor cancelled this optimizer session.' }
    if ($null -ne $script:appProcess) {
        $script:appProcess.Refresh()
        if ($script:appProcess.HasExited) { throw 'The new TAZmd process closed before this session completed.' }
    }
}

function Assert-WindowReady {
    if ($null -eq $script:appWindow -or $script:appWindow.Current.ProcessId -ne $script:appId) { throw 'The TAZmd window identity changed.' }
    if (-not $script:appWindow.Current.IsEnabled) { throw 'TAZmd has a disabled window or startup dialog. Complete it and retry, or use manual export/open/import.' }
    $windowPattern = $null
    if ($script:appWindow.TryGetCurrentPattern([Windows.Automation.WindowPattern]::Pattern, [ref]$windowPattern)) {
        if ($windowPattern.Current.WindowInteractionState -eq [Windows.Automation.WindowInteractionState]::BlockedByModalWindow) {
            throw 'TAZmd has a modal dialog open. Complete it and retry, or use manual export/open/import.'
        }
    }
}

function Find-ExactControl([string]$Id, $ControlType, [long]$Deadline) {
    while ($true) {
        Assert-Active $Deadline
        Assert-WindowReady
        $condition = New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::AutomationIdProperty, $Id)
        $foundControls = $script:appWindow.FindAll([Windows.Automation.TreeScope]::Descendants, $condition)
        if ($foundControls.Count -gt 1) { throw "TAZmd exposes more than one '$Id' control; refusing an ambiguous action." }
        if ($foundControls.Count -eq 1) {
            $control = $foundControls.Item(0)
            if ($control.Current.ProcessId -ne $script:appId -or $control.Current.ControlType -ne $ControlType) { throw "The '$Id' control did not belong to the expected TAZmd process or type." }
            if ($control.Current.IsEnabled -and -not $control.Current.IsOffscreen) { return $control }
        }
        Start-Sleep -Milliseconds 100
    }
}

function Get-Toggle([string]$Id, [long]$Deadline) {
    $control = Find-ExactControl $Id ([Windows.Automation.ControlType]::CheckBox) $Deadline
    $pattern = $null
    if (-not $control.TryGetCurrentPattern([Windows.Automation.TogglePattern]::Pattern, [ref]$pattern)) { throw "TAZmd '$Id' does not expose a safe checkbox action." }
    return $pattern
}

function Set-ToggleOff([string]$Id, [long]$Deadline) {
    for ($attempt = 0; $attempt -lt 3; $attempt++) {
        Assert-Active $Deadline
        $pattern = Get-Toggle $Id $Deadline
        if ($pattern.Current.ToggleState -eq [Windows.Automation.ToggleState]::Off) { return }
        $pattern.Toggle()
        Start-Sleep -Milliseconds 100
    }
    if ((Get-Toggle $Id $Deadline).Current.ToggleState -ne [Windows.Automation.ToggleState]::Off) { throw "Could not disable TAZmd '$Id'; no Corvette will be pasted." }
}

function Assert-AutomaticEditsOff([long]$Deadline) {
    foreach ($id in @('chkAutoOptimize', 'chkAutoDelete')) {
        if ((Get-Toggle $id $Deadline).Current.ToggleState -ne [Windows.Automation.ToggleState]::Off) { throw 'TAZmd automatic optimization/deletion changed during this session. Start a new session.' }
    }
}

function Invoke-ExactButton([string]$Id, [long]$Deadline) {
    Assert-Active $Deadline
    $control = Find-ExactControl $Id ([Windows.Automation.ControlType]::Button) $Deadline
    $pattern = $null
    if (-not $control.TryGetCurrentPattern([Windows.Automation.InvokePattern]::Pattern, [ref]$pattern)) { throw "TAZmd '$Id' does not expose a safe button action." }
    Assert-WindowReady
    $pattern.Invoke()
}

function Get-ClipboardText {
    if ([Windows.Forms.Clipboard]::ContainsText([Windows.Forms.TextDataFormat]::UnicodeText)) {
        return [Windows.Forms.Clipboard]::GetText([Windows.Forms.TextDataFormat]::UnicodeText)
    }
    return $null
}

function Snapshot-Clipboard {
    $sequenceBefore = [WonderCodexTazClipboard]::GetClipboardSequenceNumber()
    $original = [Windows.Forms.Clipboard]::GetDataObject()
    $script:clipboardWasEmpty = ($null -eq $original)
    $copy = New-Object Windows.Forms.DataObject
    $copied = 0
    if ($null -ne $original) {
        foreach ($format in $original.GetFormats($false)) {
            $value = $original.GetData($format, $false)
            if ($null -eq $value) { continue }
            if ($value -is [IO.MemoryStream]) { $value = New-Object IO.MemoryStream(,$value.ToArray()) }
            elseif ($value -is [ICloneable]) { $value = $value.Clone() }
            $copy.SetData($format, $false, $value)
            $copied++
        }
        if ($copied -eq 0) { $script:clipboardWasEmpty = $true }
    }
    if ($sequenceBefore -ne [WonderCodexTazClipboard]::GetClipboardSequenceNumber()) { throw 'The clipboard changed while preparing the session. Retry when other copying is finished.' }
    $script:clipboardSnapshot = $copy
    $script:clipboardSnapshotReady = $true
    $script:lastClipboardSequence = $sequenceBefore
}

function Assert-ClipboardUnchanged {
    if ([WonderCodexTazClipboard]::GetClipboardSequenceNumber() -ne $script:lastClipboardSequence) { throw 'The clipboard was changed outside this optimizer session. It has been left untouched; start a new session.' }
}

function Set-SourceClipboard([string]$Text) {
    Assert-ClipboardUnchanged
    [Windows.Forms.Clipboard]::SetText($Text, [Windows.Forms.TextDataFormat]::UnicodeText)
    $script:clipboardTouched = $true
    $script:lastClipboardText = $Text
    $script:lastClipboardSequence = [WonderCodexTazClipboard]::GetClipboardSequenceNumber()
    if ((Get-ClipboardText) -cne $Text) { throw 'The clipboard could not hold the selected Corvette.' }
}

function Copy-FromTaz([long]$Deadline) {
    Assert-ClipboardUnchanged
    $oldSequence = $script:lastClipboardSequence
    Invoke-ExactButton 'btnCopy' $Deadline
    while ($true) {
        Assert-Active $Deadline
        $sequence = [WonderCodexTazClipboard]::GetClipboardSequenceNumber()
        if ($sequence -ne $oldSequence) {
            $owner = [WonderCodexTazClipboard]::GetClipboardOwner()
            [uint32]$ownerId = 0
            [void][WonderCodexTazClipboard]::GetWindowThreadProcessId($owner, [ref]$ownerId)
            # Windows/OLE clipboard transfers can legitimately leave owner HWND/PID
            # zero. In that case producer identity is unavailable, not verified.
            # Continue only under the existing PID-scoped invocation, sequence checks,
            # Java's exact prefill gate, and final exact permutation validation.
            if ($ownerId -ne 0 -and $ownerId -ne $script:appId) { throw 'Another application changed the clipboard while TAZmd was copying. Its clipboard has been left untouched.' }
            $text = Get-ClipboardText
            if ($sequence -ne [WonderCodexTazClipboard]::GetClipboardSequenceNumber()) { throw 'The clipboard changed during TAZmd verification.' }
            if ([string]::IsNullOrWhiteSpace($text)) { throw 'TAZmd Copy All returned no JSON.' }
            if ($text.Length -gt 67108864) { throw 'TAZmd returned an unexpectedly large result.' }
            $script:lastClipboardText = $text
            $script:lastClipboardSequence = $sequence
            return $text
        }
        Start-Sleep -Milliseconds 100
    }
}

try {
    $script:jobPath = [IO.Path]::GetFullPath($JobDir)
    if (-not [IO.Directory]::Exists($script:jobPath)) { throw 'The editor must create a fresh private job folder first.' }
    if (([IO.File]::GetAttributes($script:jobPath) -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'The job folder cannot be a link.' }
    foreach ($name in @('continue', 'abort', 'prefill.json', 'prefill.ready', 'optimized.json', 'status.txt', 'error.txt')) {
        if ([IO.File]::Exists((Join-Path $script:jobPath $name))) { throw 'The optimizer job folder was already used. Start a fresh session.' }
    }
    $script:jobOwned = $true
    Write-AtomicText 'status.txt' 'working'
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw 'TAZmd integration requires Windows.' }
    if ([Threading.Thread]::CurrentThread.ApartmentState -ne [Threading.ApartmentState]::STA) { throw 'Launch the adapter with PowerShell -STA.' }
    $executable = [IO.Path]::GetFullPath($OptimizerPath)
    $sourcePath = [IO.Path]::GetFullPath($InputJson)
    if (-not [IO.File]::Exists($executable) -or [IO.Path]::GetExtension($executable) -ine '.exe') { throw 'Choose the official TAZmd Windows executable.' }
    if (-not [IO.File]::Exists($sourcePath) -or (Get-Item -LiteralPath $sourcePath).Length -gt 67108864) { throw 'The selected Corvette export is missing or too large.' }
    $sourceText = [IO.File]::ReadAllText($sourcePath, (New-Object Text.UTF8Encoding($false, $true)))
    if ([string]::IsNullOrWhiteSpace($sourceText)) { throw 'The selected Corvette export is empty.' }
    Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes, System.Windows.Forms
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class WonderCodexTazClipboard {
    [DllImport("user32.dll")] public static extern uint GetClipboardSequenceNumber();
    [DllImport("user32.dll")] public static extern IntPtr GetClipboardOwner();
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint processId);
}
'@
    # A new process only. No existing optimizer window or another player's save is reused.
    $script:appProcess = Start-Process -FilePath $executable -WorkingDirectory ([IO.Path]::GetDirectoryName($executable)) -PassThru
    $script:appId = $script:appProcess.Id
    Write-AtomicText 'optimizer-process.txt' ([string]$script:appId)
    $startupDeadline = New-Deadline 30
    while ($true) {
        Assert-Active $startupDeadline
        $script:appProcess.Refresh()
        $handle = $script:appProcess.MainWindowHandle
        if ($handle -ne [IntPtr]::Zero) {
            if (-not [string]::Equals([IO.Path]::GetFullPath($script:appProcess.MainModule.FileName), $executable, [StringComparison]::OrdinalIgnoreCase)) { throw 'The launched process did not match the selected optimizer executable.' }
            $script:appWindow = [Windows.Automation.AutomationElement]::FromHandle($handle)
            if ($null -ne $script:appWindow -and $script:appWindow.Current.ProcessId -eq $script:appId) { break }
        }
        Start-Sleep -Milliseconds 100
    }
    # A first-run language/update dialog requires the user's own interaction; never dismiss it blindly.
    Set-ToggleOff 'chkAutoOptimize' $startupDeadline
    Set-ToggleOff 'chkAutoDelete' $startupDeadline
    Assert-AutomaticEditsOff $startupDeadline
    Snapshot-Clipboard
    Set-SourceClipboard $sourceText
    $pasteDeadline = New-Deadline 15
    Invoke-ExactButton 'btnPaste' $pasteDeadline
    $prefillText = Copy-FromTaz $pasteDeadline
    Assert-AutomaticEditsOff $pasteDeadline
    Write-AtomicText 'prefill.json' $prefillText
    Write-AtomicText 'prefill.ready' 'ready'
    Write-AtomicText 'status.txt' 'prefill'
    # Java must independently compare every returned value before granting permission to continue.
    $approvalDeadline = New-Deadline 30
    while (-not [IO.File]::Exists((Join-Path $script:jobPath 'continue'))) {
        Assert-Active $approvalDeadline
        Start-Sleep -Milliseconds 100
    }
    Assert-Active $approvalDeadline
    Assert-WindowReady
    Assert-AutomaticEditsOff (New-Deadline 15)
    if ($Mode -eq 'direct') {
        Assert-ClipboardUnchanged
        $optimizeDeadline = New-Deadline 15
        Invoke-ExactButton 'btnOp' $optimizeDeadline
        $resultText = Copy-FromTaz $optimizeDeadline
        Write-AtomicText 'optimized.json' $resultText
    }
    Write-AtomicText 'status.txt' 'done'
    $exitCode = 0
} catch {
    $message = [string]$_.Exception.Message
    if ($message.Length -gt 1500) { $message = $message.Substring(0, 1500) }
    if ($script:jobOwned -and $null -ne $script:jobPath -and [IO.Directory]::Exists($script:jobPath)) {
        try { Write-AtomicText 'error.txt' $message; Write-AtomicText 'status.txt' 'error' } catch { }
    }
    [Console]::Error.WriteLine($message)
} finally {
    # Restore only while the clipboard is still exactly the content/sequence this job last observed.
    # If the user copied something else, that content wins and is never overwritten.
    if ($script:clipboardTouched -and $script:clipboardSnapshotReady) {
        try {
            if ([WonderCodexTazClipboard]::GetClipboardSequenceNumber() -eq $script:lastClipboardSequence -and (Get-ClipboardText) -ceq $script:lastClipboardText) {
                if ($script:clipboardWasEmpty) { [Windows.Forms.Clipboard]::Clear() }
                else { [Windows.Forms.Clipboard]::SetDataObject($script:clipboardSnapshot, $true) }
            }
        } catch { }
    }
}
exit $exitCode
