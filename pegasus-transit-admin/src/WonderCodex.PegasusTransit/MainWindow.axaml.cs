using Avalonia.Controls;
using Avalonia.Interactivity;
using Avalonia.Platform.Storage;
using System.Text.Json;
using WonderCodex.Importer.Core.Models;
using WonderCodex.Importer.Core.Services;
using WonderCodex.PegasusTransit.Core.Models;
using WonderCodex.PegasusTransit.Core.Services;

namespace WonderCodex.PegasusTransit;

public sealed partial class MainWindow : Window
{
    private readonly ImporterCompositionRoot _importer = new();
    private readonly AdminSessionClient _adminSession = new();
    private readonly TransitCoordinator _transit;
    private CancellationTokenSource? _operation;
    private bool _authorized;
    private string _operatorName = string.Empty;
    private TransitPlan? _plan;

    public MainWindow()
    {
        InitializeComponent();
        var patcher = new UniverseAddressPatcher();
        var backups = new TransitBackupService();
        _transit = new TransitCoordinator(
            _importer.Decoder,
            patcher,
            new SteamTransitWriter(_importer.Decoder, patcher, backups),
            new XboxWgsTransitWriter(_importer.Decoder, patcher, backups));
    }

    private async void AuthorizeButton_OnClick(object? sender, RoutedEventArgs e)
    {
        CancelCurrentOperation();
        _operation = new CancellationTokenSource();
        SetBusy(true);
        try
        {
            var baseText = ApiBaseBox.Text?.Trim() ?? string.Empty;
            if (!baseText.EndsWith('/')) baseText += "/";
            if (!Uri.TryCreate(baseText, UriKind.Absolute, out var apiBase) || apiBase.Scheme != Uri.UriSchemeHttps)
                throw new InvalidOperationException("Enter the HTTPS Wonder Codex API base address.");

            var operatorName = OperatorNameBox.Text?.Trim() ?? string.Empty;
            await _adminSession.AuthorizeAsync(
                apiBase,
                operatorName,
                AdminKeyBox.Text ?? string.Empty,
                _operation.Token);
            _authorized = true;
            _operatorName = operatorName;
            AdminKeyBox.Text = string.Empty;
            AuthorizationStatus.Text = $"Authorized for this session as {_operatorName}. The key was cleared from the screen.";
            AuthorizationStatus.Classes.Add("success");
            ScanButton.IsEnabled = true;
        }
        catch (Exception error)
        {
            _authorized = false;
            _operatorName = string.Empty;
            ScanButton.IsEnabled = false;
            AuthorizationStatus.Text = $"Authorization failed: {error.Message}";
        }
        finally
        {
            SetBusy(false);
        }
    }

    private async void ScanButton_OnClick(object? sender, RoutedEventArgs e)
    {
        if (!_authorized) return;
        CancelCurrentOperation();
        _operation = new CancellationTokenSource();
        SetBusy(true);
        CharacterPicker.ItemsSource = null;
        CharacterStatus.Text = "Scanning known local save locations read-only…";
        try
        {
            var progress = new Progress<string>(message => CharacterStatus.Text = message);
            var result = await _importer.Discovery.ScanDefaultLocationsAsync(progress, _operation.Token);
            var options = result.Accounts
                .SelectMany(account => account.Characters.Select(character => new CharacterOption(account, character)))
                .Where(option => option.Character.IsPlayableCharacterState)
                .OrderBy(option => option.Character.Platform)
                .ThenBy(option => option.Character.DisplayName)
                .ToArray();
            CharacterPicker.ItemsSource = options;
            CharacterStatus.Text = options.Length == 0
                ? "No confirmed playable Steam or Xbox / Game Pass characters were found."
                : $"Found {options.Length:N0} playable character(s). Choose the exact departure save.";
        }
        catch (Exception error)
        {
            CharacterStatus.Text = $"Save scan failed safely: {error.Message}";
        }
        finally
        {
            SetBusy(false);
        }
    }

    private void CharacterPicker_OnSelectionChanged(object? sender, SelectionChangedEventArgs e)
    {
        _plan = null;
        var option = CharacterPicker.SelectedItem as CharacterOption;
        CharacterStatus.Text = option is null
            ? "No character selected."
            : $"{option.Character.PlatformLabel} • {option.Character.DetailLine} • {option.Character.RevisionSummary}";
        PcHydratedCheck.Content = option?.Character.Platform == SavePlatform.XboxGamePass
            ? "The PC main menu synced this Xbox console save once, then NMS was closed."
            : "This Steam save is local on this PC; the Xbox cloud-handoff step does not apply.";
        PcHydratedCheck.IsChecked = false;
        PreviewButton.IsEnabled = _authorized && option is not null;
        UpdateEngageButton();
    }

    private async void LoadTicketButton_OnClick(object? sender, RoutedEventArgs e)
    {
        var files = await StorageProvider.OpenFilePickerAsync(new FilePickerOpenOptions
        {
            Title = "Choose a Wonder Codex transit route",
            AllowMultiple = false,
            FileTypeFilter =
            [
                new FilePickerFileType("Wonder Codex transit route")
                {
                    Patterns = ["*.wctransit", "*.json"]
                }
            ]
        });
        if (files.Count == 0) return;

        try
        {
            await using var stream = await files[0].OpenReadAsync();
            var ticket = await JsonSerializer.DeserializeAsync<CatalogTransitTicket>(stream)
                ?? throw new InvalidDataException("The transit ticket is empty.");
            var destination = ticket.ValidateAndBuildDestination();
            GalaxyNumberBox.Text = destination.GalaxyNumber.ToString();
            GalaxyNameBox.Text = destination.GalaxyName;
            GlyphsBox.Text = destination.PortalGlyphs;
            WonderRecordBox.Text = ticket.WonderRecordId;
            OperationStatus.Text = $"Loaded {ticket.WonderRecordId}. Preview the route against the selected character.";
            _plan = null;
            UpdateEngageButton();
        }
        catch (Exception error)
        {
            OperationStatus.Text = $"Transit ticket rejected: {error.Message}";
        }
    }

    private async void PreviewButton_OnClick(object? sender, RoutedEventArgs e)
    {
        if (CharacterPicker.SelectedItem is not CharacterOption option) return;
        CancelCurrentOperation();
        _operation = new CancellationTokenSource();
        SetBusy(true);
        _plan = null;
        UpdateEngageButton();
        try
        {
            if (!int.TryParse(GalaxyNumberBox.Text?.Trim(), out var galaxyNumber))
                throw new InvalidOperationException("Enter the catalog galaxy number from 1 through 256.");
            var destination = TransitDestinationParser.Parse(
                galaxyNumber,
                GlyphsBox.Text ?? string.Empty,
                GalaxyNameBox.Text);
            _plan = await _transit.PrepareAsync(
                option.Character,
                destination,
                _operatorName,
                WonderRecordBox.Text,
                _operation.Token);

            RouteTitle.Text = string.IsNullOrWhiteSpace(_plan.WonderRecordId)
                ? destination.DisplayName
                : $"{_plan.WonderRecordId} → {destination.DisplayName}";
            CurrentLocationText.Text = "Current: " + _plan.CurrentLocation.CoordinateSummary;
            TargetLocationText.Text =
                $"Target: {destination.UniversalAddress} • X {destination.VoxelX}; Y {destination.VoxelY}; " +
                $"Z {destination.VoxelZ}; system {destination.SolarSystemIndex}; planet {destination.PlanetIndex}";
            PatchScopeText.Text = _plan.Character.Platform == SavePlatform.XboxGamePass
                ? $"{_plan.Character.SlotLabel}. Preflight passed. The paired save and WGS index are locked; " +
                  "if either revision changes before departure, Transit will refuse to write."
                : "Preflight passed. The Steam source hash is locked; if the save changes before departure, " +
                  "Transit will refuse to write.";
            OperationStatus.Text = "Route prepared. Complete the departure checklist.";
        }
        catch (Exception error)
        {
            RouteTitle.Text = "Route preview failed";
            OperationStatus.Text = error.Message;
        }
        finally
        {
            SetBusy(false);
            UpdateEngageButton();
        }
    }

    private void Checklist_OnClick(object? sender, RoutedEventArgs e) => UpdateEngageButton();

    private async void EngageButton_OnClick(object? sender, RoutedEventArgs e)
    {
        if (_plan is null || !ChecklistComplete()) return;
        CancelCurrentOperation();
        _operation = new CancellationTokenSource();
        SetBusy(true);
        EngageButton.IsEnabled = false;
        OperationStatus.Text = _plan.Character.Platform == SavePlatform.XboxGamePass
            ? "Creating the full backup, writing the paired local WGS transaction, and decoding Manual again…"
            : "Creating the full backup, writing the Steam save pair, and decoding it again…";
        try
        {
            var result = await _transit.ExecuteAsync(_plan, _operation.Token);
            OperationStatus.Text = result.Platform == "Xbox / Game Pass WGS"
                ? $"LOCAL WRITE VERIFIED — {result.Message}"
                : $"SUCCESS — {result.Message} Reopen the game and confirm the destination.";
            OperationStatus.Classes.Add("success");
            BackupPathText.Text = $"Before-write backup: {result.BackupPath}" +
                                  (string.IsNullOrWhiteSpace(result.PostWriteSnapshotPath)
                                      ? string.Empty
                                      : $"{Environment.NewLine}After-local-write snapshot: {result.PostWriteSnapshotPath}");
            TargetLocationText.Text = "Verified written location: " + result.VerifiedLocation.CoordinateSummary;
            _plan = null;
            PreviewButton.IsEnabled = false;
        }
        catch (Exception error)
        {
            OperationStatus.Text = $"Transit stopped safely: {error.Message}";
        }
        finally
        {
            SetBusy(false);
            UpdateEngageButton();
        }
    }

    private bool ChecklistComplete()
        => InSpaceCheck.IsChecked == true &&
           PcHydratedCheck.IsChecked == true &&
           GameClosedCheck.IsChecked == true &&
           BackupConsentCheck.IsChecked == true &&
           AlphaConsentCheck.IsChecked == true;

    private void UpdateEngageButton()
        => EngageButton.IsEnabled = _plan is not null && ChecklistComplete() && _authorized;

    private void SetBusy(bool busy)
    {
        AuthorizeButton.IsEnabled = !busy;
        ScanButton.IsEnabled = !busy && _authorized;
        CharacterPicker.IsEnabled = !busy;
        LoadTicketButton.IsEnabled = !busy;
        PreviewButton.IsEnabled = !busy && _authorized && CharacterPicker.SelectedItem is CharacterOption;
        if (busy) EngageButton.IsEnabled = false;
    }

    private void CancelCurrentOperation()
    {
        _operation?.Cancel();
        _operation?.Dispose();
        _operation = null;
    }

    private sealed record CharacterOption(SaveAccount Account, SaveCharacter Character)
    {
        public override string ToString()
            => $"{Character.DisplayName} — {Character.PlatformLabel} — {Account.DisplayName}";
    }
}
