using Avalonia.Controls;
using Avalonia.Interactivity;
using Avalonia.Platform.Storage;
using Avalonia.Threading;
using WonderCodex.Capture.Core.Models;
using WonderCodex.Capture.Core.Services;
using WonderCodex.Importer.Core.Models;
using WonderCodex.Importer.Core.Services;

namespace WonderCodex.Capture;

public sealed partial class MainWindow : Window
{
    private readonly ImporterCompositionRoot _importer = new();
    private readonly DiscoverySnapshotService _snapshots = new();
    private readonly CapturePairingService _pairing = new();
    private readonly List<CaptureDiscovery> _newDiscoveries = [];
    private readonly List<ScreenshotCandidate> _screenshots = [];
    private readonly List<CapturePairCandidate> _pairs = [];
    private readonly NormalizedDiscoveryReader _reader;
    private ScreenshotFolderWatcher? _screenshotWatcher;
    private CancellationTokenSource? _monitorCancellation;
    private Task? _monitorTask;
    private DiscoverySnapshot? _snapshot;
    private CaptureCharacterSelection? _selection;
    private string _lastSourcePath = string.Empty;
    private DateTimeOffset _lastSaveWriteUtc;
    private long _lastSaveSize;

    public MainWindow()
    {
        InitializeComponent();
        _reader = new NormalizedDiscoveryReader(_importer);
        Opened += async (_, _) => await ScanAsync();
        Closed += async (_, _) => await StopMonitoringAsync();
    }

    private async Task ScanAsync()
    {
        ScanStatusText.Text = "Scanning supported save locations locally…";
        try
        {
            var result = await _importer.Discovery.ScanDefaultLocationsAsync();
            var options = result.Accounts
                .SelectMany(account => account.Characters.Select(character => new CharacterOption(
                    CaptureCharacterSelection.From(character),
                    character)))
                .OrderBy(option => option.Selection.Platform)
                .ThenBy(option => option.Selection.DisplayName, StringComparer.OrdinalIgnoreCase)
                .ToArray();
            CharacterBox.ItemsSource = options;
            CharacterBox.SelectedIndex = options.Length > 0 ? 0 : -1;
            ScanStatusText.Text = options.Length == 0
                ? "No supported playable character saves were found. Nothing was changed."
                : $"Found {options.Length} resolved character slot(s). Choose the one you are playing.";
            if (result.Warnings.Count > 0)
                ScanStatusText.Text += $" Notes: {string.Join(" ", result.Warnings)}";
        }
        catch (Exception error)
        {
            ScanStatusText.Text = $"Local scan stopped safely: {error.Message}";
        }
    }

    private async void ScanButton_OnClick(object? sender, RoutedEventArgs e)
        => await ScanAsync();

    private async void ChooseScreenshotFolder_OnClick(object? sender, RoutedEventArgs e)
    {
        var folders = await StorageProvider.OpenFolderPickerAsync(new FolderPickerOpenOptions
        {
            Title = "Choose the folder where new No Man's Sky screenshots appear",
            AllowMultiple = false
        });
        if (folders.Count == 0) return;

        ScreenshotFolderBox.Text = folders[0].Path.LocalPath;
        ScreenshotStatusText.Text = "The companion will observe new PNG, JPG, WEBP, or BMP files in this folder only.";
    }

    private async void StartButton_OnClick(object? sender, RoutedEventArgs e)
    {
        if (CharacterBox.SelectedItem is not CharacterOption option)
        {
            MonitorStatusText.Text = "Choose a local character first.";
            return;
        }

        var screenshotFolder = ScreenshotFolderBox.Text?.Trim() ?? string.Empty;
        if (!Directory.Exists(screenshotFolder))
        {
            MonitorStatusText.Text = "Choose an existing screenshot folder first.";
            return;
        }

        await StopMonitoringAsync();
        SetRunning(true);
        MonitorStatusText.Text = "Building the session baseline from the selected save…";

        try
        {
            _selection = option.Selection;
            var read = await _reader.ReadAsync(option.Character);
            _snapshot = _snapshots.Build(SessionCharacterId(_selection), read.Report);
            RememberRevision(read.Character);
            _newDiscoveries.Clear();
            _screenshots.Clear();
            _pairs.Clear();
            RefreshQueue();
            UpdateCounts();

            _screenshotWatcher = new ScreenshotFolderWatcher(screenshotFolder);
            _screenshotWatcher.ScreenshotObserved += ScreenshotWatcher_OnScreenshotObserved;
            _screenshotWatcher.Start();

            _monitorCancellation = new CancellationTokenSource();
            _monitorTask = MonitorLoopAsync(_monitorCancellation.Token);
            MonitorStatusText.Text =
                $"ARMED — baseline contains {_snapshot.Count:N0} discoveries. " +
                "Scan something in game, take its screenshot, then let the game save.";
        }
        catch (Exception error)
        {
            MonitorStatusText.Text = $"The monitor stopped safely before arming: {error.Message}";
            await StopMonitoringAsync();
        }
    }

    private async void StopButton_OnClick(object? sender, RoutedEventArgs e)
    {
        await StopMonitoringAsync();
        MonitorStatusText.Text = "Monitor stopped. The session queue remains visible until a new session begins.";
    }

    private async Task MonitorLoopAsync(CancellationToken cancellationToken)
    {
        using var timer = new PeriodicTimer(TimeSpan.FromSeconds(4));
        try
        {
            while (await timer.WaitForNextTickAsync(cancellationToken))
                await CheckForSaveChangeAsync(cancellationToken);
        }
        catch (OperationCanceledException)
        {
            // Expected when the operator stops the session.
        }
        catch (Exception error)
        {
            await Dispatcher.UIThread.InvokeAsync(() =>
            {
                MonitorStatusText.Text = $"Monitoring stopped safely: {error.Message}";
                SetRunning(false);
            });
        }
    }

    private async Task CheckForSaveChangeAsync(CancellationToken cancellationToken)
    {
        if (_selection is null || _snapshot is null) return;

        var scan = await _importer.Discovery.ScanDefaultLocationsAsync(cancellationToken: cancellationToken);
        var currentCharacter = CaptureCharacterResolver.Resolve(_selection, scan.Accounts);
        if (currentCharacter is null)
        {
            MonitorStatusText.Text = "Waiting for the selected character save to become readable again…";
            return;
        }

        if (!RevisionChanged(currentCharacter)) return;

        var read = await _reader.ReadAsync(currentCharacter, cancellationToken);
        var current = _snapshots.Build(_snapshot.CharacterId, read.Report);
        var added = _snapshots.FindAdded(_snapshot, current);
        _snapshot = current;
        RememberRevision(read.Character);

        if (added.Count == 0)
        {
            MonitorStatusText.Text = "Save update observed; no new normalized discovery appeared.";
            return;
        }

        _newDiscoveries.AddRange(added.Where(candidate =>
            _newDiscoveries.All(existing => existing.Fingerprint != candidate.Fingerprint)));
        MonitorStatusText.Text =
            $"Detected {added.Count} newly persisted discover{(added.Count == 1 ? "y" : "ies")}. " +
            "Checking the screenshot queue for a nearby image…";
        UpdateCounts();
        ProposePairs();
    }

    private void ScreenshotWatcher_OnScreenshotObserved(object? sender, ScreenshotCandidate candidate)
    {
        Dispatcher.UIThread.Post(() =>
        {
            if (_screenshots.Any(item => string.Equals(
                    item.FullPath,
                    candidate.FullPath,
                    StringComparison.OrdinalIgnoreCase)))
            {
                return;
            }

            _screenshots.Add(candidate);
            ScreenshotStatusText.Text = $"Observed new screenshot: {candidate.FileName}";
            UpdateCounts();
            ProposePairs();
        });
    }

    private void ProposePairs()
    {
        var proposed = _pairing.Propose(_newDiscoveries, _screenshots, _pairs);
        foreach (var pair in proposed)
        {
            if (_pairs.All(existing => existing.PairId != pair.PairId))
                _pairs.Add(pair);
        }
        RefreshQueue();
    }

    private void ConfirmPair_OnClick(object? sender, RoutedEventArgs e)
    {
        if (PairList.SelectedItem is not CapturePairCandidate selected)
        {
            QueueStatusText.Text = "Select a proposed pair first.";
            return;
        }

        var index = _pairs.FindIndex(pair => pair.PairId == selected.PairId);
        if (index < 0) return;
        _pairs[index] = selected with { Confirmed = true };
        QueueStatusText.Text = "Pair confirmed for this local session. Nothing was uploaded.";
        RefreshQueue();
        PairList.SelectedIndex = index;
    }

    private async Task StopMonitoringAsync()
    {
        _monitorCancellation?.Cancel();
        if (_monitorTask is not null)
        {
            try
            {
                await _monitorTask;
            }
            catch (OperationCanceledException)
            {
                // Expected during shutdown.
            }
        }

        _monitorTask = null;
        _monitorCancellation?.Dispose();
        _monitorCancellation = null;
        if (_screenshotWatcher is not null)
        {
            _screenshotWatcher.ScreenshotObserved -= ScreenshotWatcher_OnScreenshotObserved;
            _screenshotWatcher.Dispose();
            _screenshotWatcher = null;
        }
        SetRunning(false);
    }

    private bool RevisionChanged(SaveCharacter character)
        => !string.Equals(character.SourcePath, _lastSourcePath, StringComparison.OrdinalIgnoreCase) ||
           character.LastModifiedUtc > _lastSaveWriteUtc ||
           character.FileSize != _lastSaveSize;

    private void RememberRevision(SaveCharacter character)
    {
        _lastSourcePath = character.SourcePath;
        _lastSaveWriteUtc = character.LastModifiedUtc;
        _lastSaveSize = character.FileSize;
    }

    private void RefreshQueue()
    {
        PairList.ItemsSource = null;
        PairList.ItemsSource = _pairs.OrderByDescending(pair => pair.ProposedUtc).ToArray();
        if (_pairs.Count == 0)
            QueueStatusText.Text = "No candidate pairs yet.";
        else if (_pairs.All(pair => pair.Confirmed))
            QueueStatusText.Text = "All proposed pairs are confirmed locally.";
        else
            QueueStatusText.Text = $"{_pairs.Count(pair => !pair.Confirmed)} pair(s) need human review.";
    }

    private void UpdateCounts()
    {
        BaselineCountText.Text = (_snapshot?.Count ?? 0).ToString("N0");
        NewCountText.Text = _newDiscoveries.Count.ToString("N0");
        ScreenshotCountText.Text = _screenshots.Count.ToString("N0");
    }

    private void SetRunning(bool running)
    {
        StartButton.IsEnabled = !running;
        StopButton.IsEnabled = running;
        CharacterBox.IsEnabled = !running;
    }

    private static string SessionCharacterId(CaptureCharacterSelection selection)
        => string.Join('|',
            selection.Platform,
            selection.AccountId,
            selection.SlotKey ?? selection.CharacterId);

    private sealed record CharacterOption(
        CaptureCharacterSelection Selection,
        SaveCharacter Character)
    {
        public string Display => Selection.Display;
    }
}
