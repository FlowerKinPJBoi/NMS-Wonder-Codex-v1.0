using System.Text.Json;
using Avalonia.Controls;
using Avalonia.Input.Platform;
using Avalonia.Interactivity;
using Avalonia.Platform.Storage;
using WonderCodex.Importer.Core.Models;
using WonderCodex.Importer.Core.Services;

namespace WonderCodex.Importer;

public sealed partial class MainWindow : Window
{
    private readonly ImporterCompositionRoot _services = new();
    private CancellationTokenSource? _operationCancellation;
    private SaveCharacter? _groupedCharacter;
    private SaveCharacter? _selectedCharacter;
    private AnalysisReport? _report;
    private PegasusCollectionReport? _pegasusReport;
    private MatchedPairProfile? _mappingProfile;

    public MainWindow()
    {
        InitializeComponent();
        ContributionSourcePlatformBox.SelectedIndex = 0;
        Opened += async (_, _) => await ScanAsync();
        Closed += (_, _) => _operationCancellation?.Cancel();
    }

    private async Task ScanAsync()
    {
        CancelCurrentOperation();
        _operationCancellation = new CancellationTokenSource();
        var cancellationToken = _operationCancellation.Token;

        SetBusy(true);
        _groupedCharacter = null;
        _selectedCharacter = null;
        ResetAnalysis();
        AccountList.ItemsSource = null;
        CharacterList.ItemsSource = null;
        RevisionList.ItemsSource = null;
        RevisionExpander.IsVisible = false;
        SelectedCharacterTitle.Text = "Resolving characters…";
        SelectedCharacterDetail.Text = "Supported compact saves are translated locally during this scan.";
        StatusText.Text = "Scanning known Steam and Xbox / Game Pass PC locations locally…";

        try
        {
            var progress = new Progress<string>(message => StatusText.Text = message);
            var result = await _services.Discovery.ScanDefaultLocationsAsync(progress, cancellationToken);
            AccountList.ItemsSource = result.Accounts;

            if (result.Accounts.Count == 0)
            {
                SelectedCharacterTitle.Text = "No accounts found";
                SelectedCharacterDetail.Text = "No save was changed.";
                StatusText.Text = "No readable No Man's Sky accounts were found in the standard locations. Nothing was changed.";
                return;
            }

            StatusText.Text =
                $"Found {result.Accounts.Count} account(s) and {result.CharacterCount} resolved character(s). " +
                "Duplicate save revisions were grouped automatically.";
            AccountList.SelectedIndex = 0;

            if (result.Warnings.Count > 0)
                StatusText.Text += $" Scan notes: {string.Join(" ", result.Warnings)}";
        }
        catch (OperationCanceledException)
        {
            StatusText.Text = "Scan cancelled.";
        }
        catch (Exception error)
        {
            StatusText.Text = $"Save scan failed safely: {error.Message}";
        }
        finally
        {
            SetBusy(false);
        }
    }

    private async void RescanButton_OnClick(object? sender, RoutedEventArgs e)
        => await ScanAsync();

    private void ResearchModeToggle_OnClick(object? sender, RoutedEventArgs e)
    {
        var enabled = ResearchModeToggle.IsChecked == true;
        ResearchPanel.IsVisible = enabled;
        PairButton.IsEnabled = enabled && _selectedCharacter is not null && BusyProgress.IsVisible == false;

        if (!enabled)
        {
            CopyMappingButton.IsEnabled = false;
            MappingPreviewList.ItemsSource = null;
            _mappingProfile = null;
        }
    }

    private void AccountList_OnSelectionChanged(object? sender, SelectionChangedEventArgs e)
    {
        if (AccountList.SelectedItem is not SaveAccount account)
        {
            CharacterList.ItemsSource = null;
            return;
        }

        CharacterList.ItemsSource = account.Characters;
        CharacterList.SelectedIndex = account.Characters.Count > 0 ? 0 : -1;
    }

    private void CharacterList_OnSelectionChanged(object? sender, SelectionChangedEventArgs e)
    {
        _groupedCharacter = CharacterList.SelectedItem as SaveCharacter;
        RevisionList.ItemsSource = null;
        RevisionExpander.IsVisible = false;

        if (_groupedCharacter is null)
        {
            _selectedCharacter = null;
            ResetAnalysis();
            SelectedCharacterTitle.Text = "Select a character";
            SelectedCharacterDetail.Text = "No save has been selected.";
            AnalyzeButton.IsEnabled = false;
            return;
        }

        if (_groupedCharacter.ReadOnlyRevisions.Count > 0)
        {
            RevisionList.ItemsSource = _groupedCharacter.ReadOnlyRevisions;
            RevisionExpander.IsVisible = _groupedCharacter.RevisionCount > 1;
            RevisionList.SelectedIndex = 0;
            return;
        }

        SelectCharacter(_groupedCharacter);
    }

    private void RevisionList_OnSelectionChanged(object? sender, SelectionChangedEventArgs e)
    {
        if (_groupedCharacter is null || RevisionList.SelectedItem is not SaveRevision revision) return;

        var selectedRevision = _groupedCharacter with
        {
            SourcePath = revision.SourcePath,
            LastModifiedUtc = revision.LastModifiedUtc,
            FileSize = revision.FileSize,
            SlotLabel = $"{_groupedCharacter.SlotLabel} • {revision.Label}"
        };
        SelectCharacter(selectedRevision);
    }

    private void SelectCharacter(SaveCharacter character)
    {
        _selectedCharacter = character;
        ResetAnalysis();
        SelectedCharacterTitle.Text = character.DisplayName;
        SelectedCharacterDetail.Text =
            $"{character.PlatformLabel} • {character.DetailLine} • {character.CatalogSummary}";
        AnalyzeButton.IsEnabled = true;
        PairButton.IsEnabled = ResearchModeToggle.IsChecked == true;
        StatusText.Text = "Character selected. Analysis reads the chosen revision again using FileAccess.Read only.";
    }

    private async void AnalyzeButton_OnClick(object? sender, RoutedEventArgs e)
    {
        if (_selectedCharacter is null) return;

        CancelCurrentOperation();
        _operationCancellation = new CancellationTokenSource();
        var cancellationToken = _operationCancellation.Token;

        SetBusy(true);
        AnalyzeButton.IsEnabled = false;
        SubmitButton.IsEnabled = false;
        StatusText.Text = $"Reading {_selectedCharacter.DisplayName} locally…";

        try
        {
            using var document = await _services.Loader.LoadAsync(_selectedCharacter, cancellationToken);
            StatusText.Text = "Finding pets, discoveries, and Wonder records…";
            await Task.Yield();

            var analyzedCharacter = _selectedCharacter;
            _report = _services.Analyzer.Analyze(document.RootElement, analyzedCharacter);
            _pegasusReport = _services.PegasusAssetAnalyzer.Analyze(
                document.RootElement,
                analyzedCharacter.DisplayName,
                analyzedCharacter.PlatformLabel,
                BuildPegasusOptions());

            var usedProductionTranslator = false;
            if (_report.DiscoveryCount == 0 &&
                _report.MatchCount == 0 &&
                _services.ProductionKeyMap.TryGetSchema(document.RootElement, out var productionSchema))
            {
                StatusText.Text =
                    $"Applying proprietary clean-room translator {productionSchema.SchemaId} in memory…";
                await Task.Yield();

                using var translatedDocument = _services.KeyTranslator.Translate(
                    document.RootElement,
                    _services.ProductionKeyMap.Mapping);

                var translatedName = SaveMetadataParser.GetSaveName(
                    translatedDocument.RootElement,
                    _selectedCharacter.DisplayName);

                analyzedCharacter = _selectedCharacter with
                {
                    DisplayName = translatedName,
                    SlotLabel = $"{_selectedCharacter.SlotLabel} • automatic clean-room translation"
                };

                _report = _services.Analyzer.Analyze(translatedDocument.RootElement, analyzedCharacter);
                _pegasusReport = _services.PegasusAssetAnalyzer.Analyze(
                    translatedDocument.RootElement,
                    translatedName,
                    analyzedCharacter.PlatformLabel,
                    BuildPegasusOptions());
                usedProductionTranslator = true;

                SelectedCharacterTitle.Text = translatedName;
                SelectedCharacterDetail.Text =
                    $"{analyzedCharacter.PlatformLabel} • {analyzedCharacter.DetailLine}";
                PairStatusText.Text =
                    $"Automatic translator {productionSchema.SchemaId} applied " +
                    $"({ProductionKeyMapProvider.PersistedTranslations:N0} shared translations; " +
                    $"{productionSchema.CorroboratingPairs} corroborating matched pairs; " +
                    $"{productionSchema.AcceptedEvidenceMappings:N0} accepted mappings in this schema).";
            }

            UpdateAnalysisDisplay(_report);
            UpdatePegasusDisplay(_pegasusReport);
            if (_report.DiscoveryCount == 0 && _report.MatchCount == 0)
            {
                if (_services.ProductionKeyMap.LooksCompact(document.RootElement) &&
                    !_services.ProductionKeyMap.Supports(document.RootElement))
                {
                    StatusText.Text =
                        "This compact-key save version is not yet covered by the production clean-room translator. " +
                        "Enable Research mode to pair it with a decoded JSON export.";
                }
                else
                {
                    StatusText.Text =
                        "Analysis ran successfully, but no normalized Wonder records were found. " +
                        "Enable Research mode for redacted diagnostics.";
                }

                SubmissionStatus.Text =
                    "Submission remains disabled while this revision is being identified.";
                return;
            }

            StatusText.Text = usedProductionTranslator
                ? $"Automatic clean-room analysis complete: {_report.DiscoveryCount:N0} discoveries and " +
                  $"{_report.MatchCount:N0} exact pet matches."
                : $"Analysis complete: {_report.DiscoveryCount:N0} discoveries and " +
                  $"{_report.MatchCount:N0} exact pet matches.";

            SubmissionStatus.Text = "Review the counts and preview, then enter a contributor name.";
            SubmitButton.IsEnabled = true;
        }
        catch (OperationCanceledException)
        {
            StatusText.Text = "Analysis cancelled.";
        }
        catch (Exception error)
        {
            _report = null;
            _pegasusReport = null;
            ResetPegasusDisplay();
            StatusText.Text = $"Analysis failed safely: {error.Message}";
            SubmissionStatus.Text = "No data was submitted and no save file was changed.";
        }
        finally
        {
            SetBusy(false);
            AnalyzeButton.IsEnabled = _selectedCharacter is not null;
        }
    }

    private async void PairButton_OnClick(object? sender, RoutedEventArgs e)
    {
        if (_selectedCharacter is null || ResearchModeToggle.IsChecked != true) return;

        var files = await StorageProvider.OpenFilePickerAsync(new FilePickerOpenOptions
        {
            Title = "Choose decoded JSON for the same account and slot",
            AllowMultiple = false,
            FileTypeFilter =
            [
                new FilePickerFileType("No Man's Sky decoded JSON")
                {
                    Patterns = ["*.json"]
                }
            ]
        });

        if (files.Count == 0) return;

        CancelCurrentOperation();
        _operationCancellation = new CancellationTokenSource();
        var cancellationToken = _operationCancellation.Token;

        SetBusy(true);
        PairButton.IsEnabled = false;
        SubmitButton.IsEnabled = false;
        PairStatusText.Text = "Comparing the compact save JSON with the decoded reference locally…";
        MappingPreviewList.ItemsSource = null;

        try
        {
            using var compactDocument = await _services.Loader.LoadAsync(_selectedCharacter, cancellationToken);
            await using var decodedStream = await files[0].OpenReadAsync();
            using var readableDocument = await _services.DecodedJsonLoader.LoadAsync(decodedStream, cancellationToken);

            _mappingProfile = _services.PairProfiler.Profile(
                compactDocument.RootElement,
                readableDocument.RootElement);

            MappingPreviewList.ItemsSource = _mappingProfile.PreviewLines;
            CopyMappingButton.IsEnabled = _mappingProfile.AcceptedMappings > 0;

            using var translatedDocument = _services.KeyTranslator.Translate(
                compactDocument.RootElement,
                _mappingProfile.Mapping);

            var pairedName = SaveMetadataParser.GetSaveName(
                readableDocument.RootElement,
                _selectedCharacter.DisplayName);
            var pairedCharacter = _selectedCharacter with
            {
                DisplayName = pairedName,
                SlotLabel = $"{_selectedCharacter.SlotLabel} • clean-room paired"
            };

            _report = _services.Analyzer.Analyze(translatedDocument.RootElement, pairedCharacter);
            _pegasusReport = _services.PegasusAssetAnalyzer.Analyze(
                translatedDocument.RootElement,
                pairedName,
                pairedCharacter.PlatformLabel,
                BuildPegasusOptions());
            UpdateAnalysisDisplay(_report);
            UpdatePegasusDisplay(_pegasusReport);
            SelectedCharacterTitle.Text = pairedName;

            PairStatusText.Text =
                $"Derived {_mappingProfile.AcceptedMappings:N0} key mappings from " +
                $"{_mappingProfile.ComparedNodes:N0} compared nodes; " +
                $"{_mappingProfile.ConflictingKeys:N0} compact keys remain ambiguous.";

            if (_report.DiscoveryCount == 0 && _report.MatchCount == 0)
            {
                StatusText.Text =
                    "Pairing completed, but the provisional mapping did not yet expose normalized Wonder records. " +
                    "Copy the redacted evidence report for the next clean-room refinement.";
                SubmissionStatus.Text = "Submission remains disabled during mapping research.";
                return;
            }

            StatusText.Text =
                $"Clean-room paired analysis complete: {_report.DiscoveryCount:N0} discoveries and " +
                $"{_report.MatchCount:N0} exact pet matches.";
            SubmissionStatus.Text = "Review the normalized counts before submitting.";
            SubmitButton.IsEnabled = true;
        }
        catch (OperationCanceledException)
        {
            PairStatusText.Text = "Matched-pair comparison cancelled.";
        }
        catch (Exception error)
        {
            _report = null;
            _pegasusReport = null;
            ResetPegasusDisplay();
            PairStatusText.Text = $"Matched-pair comparison failed safely: {error.Message}";
            SubmissionStatus.Text = "No data was submitted and no save file was changed.";
        }
        finally
        {
            SetBusy(false);
            PairButton.IsEnabled = ResearchModeToggle.IsChecked == true && _selectedCharacter is not null;
        }
    }

    private async void CopyMappingButton_OnClick(object? sender, RoutedEventArgs e)
    {
        if (_mappingProfile is null) return;
        var clipboard = TopLevel.GetTopLevel(this)?.Clipboard;
        if (clipboard is null)
        {
            PairStatusText.Text = "Clipboard access is unavailable on this system.";
            return;
        }

        await clipboard.SetTextAsync(_mappingProfile.ToRedactedJson());
        PairStatusText.Text =
            "Redacted mapping evidence copied. It contains key names, counts, and contexts only—no save values or file paths.";
    }

    private void CollectionOption_OnClick(object? sender, RoutedEventArgs e)
    {
        _pegasusReport = null;
        ResetPegasusDisplay();
        PegasusStatusText.Text =
            "Collection options changed. Analyze the selected character again to rebuild the local normalized manifest.";
    }

    private PegasusCollectionOptions BuildPegasusOptions()
        => new(
            IncludeCompanionPets: CollectPetsBox.IsChecked == true,
            IncludeCreatureEggSignals: CollectEggsBox.IsChecked == true,
            IncludeStarships: CollectShipsBox.IsChecked == true,
            IncludeFreighter: CollectFreighterBox.IsChecked == true,
            IncludeFrigates: CollectFrigatesBox.IsChecked == true,
            IncludeMultitools: CollectMultitoolsBox.IsChecked == true,
            IncludeInventoryCatalog: CollectInventoryBox.IsChecked == true,
            IncludeInventoryAmounts: IncludeInventoryAmountsBox.IsChecked == true,
            IncludeCustomNames: IncludeCustomNamesBox.IsChecked == true);

    private void ContributorBox_OnTextChanged(object? sender, TextChangedEventArgs e)
        => UpdateContributionPreview();

    private void PrivateAttributionBox_OnClick(object? sender, RoutedEventArgs e)
        => UpdateContributionPreview();

    private void ContributionSourcePlatformBox_OnSelectionChanged(
        object? sender,
        SelectionChangedEventArgs e)
    {
        var requiresCrossSave = ContributionSourceRequiresCrossSave();
        ContributionCrossSaveBox.IsEnabled = requiresCrossSave;
        if (!requiresCrossSave) ContributionCrossSaveBox.IsChecked = false;
        UpdateContributionPreview();
    }

    private void ContributionCrossSaveBox_OnClick(object? sender, RoutedEventArgs e)
        => UpdateContributionPreview();

    private void UpdateContributionPreview()
    {
        if (_report is null || _report.ContributionRecords.Count == 0)
        {
            ContributionPreviewText.Text = "Analyze a character to prepare the WCCP v0.1 export preview.";
            ExportContributionButton.IsEnabled = false;
            return;
        }

        var preview = _services.ContributionBuilder.Preview(_report);
        var attribution = PrivateAttributionBox.IsChecked == true
            ? "Anonymous attribution; no contributor name will be embedded."
            : string.IsNullOrWhiteSpace(ContributorBox.Text)
                ? "Enter a contributor display name or select anonymous attribution."
                : $"Credited to {ContributorBox.Text.Trim()}.";
        var requiresCrossSave = ContributionSourceRequiresCrossSave();
        var crossSaveConfirmed = ContributionCrossSaveBox.IsChecked == true;
        var platform = SelectedContributionSourcePlatform();
        var source = requiresCrossSave
            ? crossSaveConfirmed
                ? $"Original platform: {ContributionSourcePlatformLabel(platform)}; official cross-save to this PC confirmed."
                : $"Original platform: {ContributionSourcePlatformLabel(platform)}. Confirm official cross-save to this PC before exporting."
            : platform == "unknown"
                ? "Original platform: unknown."
                : "Original platform: PC; read from a local PC save.";
        var attributionReady = PrivateAttributionBox.IsChecked == true ||
                               !string.IsNullOrWhiteSpace(ContributorBox.Text);
        var sourceReady = !requiresCrossSave || crossSaveConfirmed;

        ContributionPreviewText.Text = $"{preview.Summary} {attribution} {source}";
        ExportContributionButton.IsEnabled = preview.RecordCount > 0 && attributionReady && sourceReady;
    }

    private async void ExportContributionButton_OnClick(object? sender, RoutedEventArgs e)
    {
        if (_report is null) return;

        var anonymous = PrivateAttributionBox.IsChecked == true;
        ContributionPackageDraft draft;
        try
        {
            draft = _services.ContributionBuilder.Build(
                _report,
                ContributorBox.Text,
                anonymous,
                sourcePlatformFamily: SelectedContributionSourcePlatform(),
                officialCrossSaveToPc: ContributionCrossSaveBox.IsChecked == true);
        }
        catch (Exception error)
        {
            ContributionExportStatus.Text = $"WCCP preview needs attention: {error.Message}";
            return;
        }

        var contributorLabel = anonymous
            ? "Anonymous"
            : SanitizeFileName(draft.Manifest.Attribution.DisplayName ?? "Contributor");
        var file = await StorageProvider.SaveFilePickerAsync(new FilePickerSaveOptions
        {
            Title = "Export Wonder Codex contribution package",
            SuggestedFileName = $"WC-Contribution-{DateTime.UtcNow:yyyyMMdd}-{contributorLabel}.zip",
            FileTypeChoices =
            [
                new FilePickerFileType("Wonder Codex contribution package")
                {
                    Patterns = ["*.zip"]
                }
            ]
        });

        if (file is null) return;

        ExportContributionButton.IsEnabled = false;
        ContributionExportStatus.Text = "Creating and self-validating the data-only WCCP package…";
        try
        {
            await using var stream = await file.OpenWriteAsync();
            var result = await _services.ContributionExporter.ExportAsync(stream, draft);
            ContributionExportStatus.Text =
                $"WCCP v0.1 ready: {result.RecordCount:N0} records, " +
                $"{result.PackageBytes / 1024d:N1} KiB. Reference: {result.SubmissionId}.";
        }
        catch (Exception error)
        {
            ContributionExportStatus.Text = $"WCCP export failed safely: {error.Message}";
        }
        finally
        {
            UpdateContributionPreview();
        }
    }

    private string SelectedContributionSourcePlatform()
        => ContributionSourcePlatformBox.SelectedIndex switch
        {
            0 => "pc",
            1 => "playstation",
            2 => "xbox",
            3 => "nintendo",
            4 => "mac",
            _ => "unknown"
        };

    private bool ContributionSourceRequiresCrossSave()
        => SelectedContributionSourcePlatform() is "playstation" or "xbox" or "nintendo" or "mac";

    private static string ContributionSourcePlatformLabel(string platform)
        => platform switch
        {
            "playstation" => "PlayStation",
            "xbox" => "Xbox",
            "nintendo" => "Nintendo Switch",
            "mac" => "Mac",
            "pc" => "PC",
            _ => "Unknown"
        };

    private async void ExportPegasusButton_OnClick(object? sender, RoutedEventArgs e)
    {
        var report = _pegasusReport;
        if (report is null) return;

        var suggestedName = SanitizeFileName(report.SaveName);
        var file = await StorageProvider.SaveFilePickerAsync(new FilePickerSaveOptions
        {
            Title = "Export normalized Pegasus beta manifest",
            SuggestedFileName = $"WonderCodex-Pegasus-{suggestedName}-beta.json",
            FileTypeChoices =
            [
                new FilePickerFileType("Normalized Pegasus JSON")
                {
                    Patterns = ["*.json"]
                }
            ]
        });

        if (file is null) return;

        try
        {
            await using var stream = await file.OpenWriteAsync();
            stream.SetLength(0);
            await JsonSerializer.SerializeAsync(
                stream,
                report,
                new JsonSerializerOptions(JsonSerializerDefaults.Web)
                {
                    WriteIndented = true
                });
            await stream.FlushAsync();
            PegasusStatusText.Text =
                $"Exported {report.AssetCount:N0} normalized beta assets. No raw save data or local save path was included.";
        }
        catch (Exception error)
        {
            PegasusStatusText.Text = $"Normalized export failed safely: {error.Message}";
        }
    }

    private async void SubmitButton_OnClick(object? sender, RoutedEventArgs e)
    {
        if (_report is null) return;
        var contributor = ContributorBox.Text?.Trim() ?? string.Empty;
        if (string.IsNullOrWhiteSpace(contributor))
        {
            SubmissionStatus.Text = "Enter a contributor name. Use private attribution to hide it from public pages.";
            return;
        }

        CancelCurrentOperation();
        _operationCancellation = new CancellationTokenSource();
        var cancellationToken = _operationCancellation.Token;

        _report.Contributor = contributor;
        _report.PublicAttribution = PrivateAttributionBox.IsChecked != true;
        _report.CreatedUtc = DateTimeOffset.UtcNow.ToString("O");

        SetBusy(true);
        SubmitButton.IsEnabled = false;
        SubmissionStatus.Text = $"Sending {_report.DiscoveryCount:N0} normalized discoveries to the review queue…";

        try
        {
            var result = await _services.SubmissionClient.SubmitAsync(_report, cancellationToken);
            SubmissionStatus.Text =
                $"Submission received. {result.QueuedRecords.Discoveries:N0} discoveries and " +
                $"{result.QueuedRecords.PetMatches:N0} pet matches queued. Reference: {result.SubmissionId}";
        }
        catch (OperationCanceledException)
        {
            SubmissionStatus.Text = "Submission cancelled before completion.";
            SubmitButton.IsEnabled = true;
        }
        catch (Exception error)
        {
            SubmissionStatus.Text = $"Submission failed: {error.Message}";
            SubmitButton.IsEnabled = true;
        }
        finally
        {
            SetBusy(false);
        }
    }

    private void UpdatePegasusDisplay(PegasusCollectionReport? report)
    {
        if (report is null)
        {
            ResetPegasusDisplay();
            return;
        }

        SetCount(PegasusPetsCount, report.Count("CompanionPet"));
        SetCount(PegasusEggsCount, report.Count("CreatureEggSignal"));
        SetCount(PegasusShipsCount, report.Count("Starship"));
        SetCount(PegasusFreightersCount, report.Count("Freighter"));
        SetCount(PegasusFrigatesCount, report.Count("Frigate"));
        SetCount(PegasusMultitoolsCount, report.Count("Multitool"));
        SetCount(PegasusItemsCount, report.Count("InventoryItem"));
        PegasusPreviewList.ItemsSource = report.PreviewLines;
        ExportPegasusButton.IsEnabled = report.AssetCount > 0;
        PegasusStatusText.Text =
            $"Local beta manifest ready: {report.AssetCount:N0} normalized assets. Pegasus categories remain local-only in this build.";
    }

    private void ResetPegasusDisplay()
    {
        ExportPegasusButton.IsEnabled = false;
        PegasusPreviewList.ItemsSource = null;
        SetCount(PegasusPetsCount, 0);
        SetCount(PegasusEggsCount, 0);
        SetCount(PegasusShipsCount, 0);
        SetCount(PegasusFreightersCount, 0);
        SetCount(PegasusFrigatesCount, 0);
        SetCount(PegasusMultitoolsCount, 0);
        SetCount(PegasusItemsCount, 0);
    }

    private static string SanitizeFileName(string value)
    {
        var invalid = Path.GetInvalidFileNameChars();
        var cleaned = new string(value.Select(character => invalid.Contains(character) ? '-' : character).ToArray());
        return string.IsNullOrWhiteSpace(cleaned) ? "Character" : cleaned.Trim();
    }

    private void UpdateAnalysisDisplay(AnalysisReport report)
    {
        SetCount(DiscoveriesCount, report.DiscoveryCount);
        SetCount(AnimalsCount, SummaryInt(report, "Animal"));
        SetCount(FloraCount, SummaryInt(report, "Flora"));
        SetCount(MineralsCount, SummaryInt(report, "Mineral"));
        SetCount(PetsCount, SummaryInt(report, "pets"));
        SetCount(MatchesCount, report.MatchCount);
        SetCount(GenerationsCount, SummaryInt(report, "generations"));
        SetCount(IssuesCount, report.IssueCount);
        PreviewList.ItemsSource = report.PreviewLines;
        UpdateContributionPreview();
    }

    private void ResetAnalysis()
    {
        _report = null;
        _pegasusReport = null;
        _mappingProfile = null;
        SubmitButton.IsEnabled = false;
        ExportContributionButton.IsEnabled = false;
        PairButton.IsEnabled = ResearchModeToggle.IsChecked == true && _selectedCharacter is not null;
        CopyMappingButton.IsEnabled = false;
        PairStatusText.Text =
            "Select a Game Pass revision, then pair it with a decoded JSON export from the same slot.";
        MappingPreviewList.ItemsSource = null;
        SubmissionStatus.Text = "Analyze a character before submitting.";
        ContributionPreviewText.Text = "Analyze a character to prepare the WCCP v0.1 export preview.";
        ContributionExportStatus.Text = "No contribution package has been created.";
        PreviewList.ItemsSource = null;
        SetCount(DiscoveriesCount, 0);
        SetCount(AnimalsCount, 0);
        SetCount(FloraCount, 0);
        SetCount(MineralsCount, 0);
        SetCount(PetsCount, 0);
        SetCount(MatchesCount, 0);
        SetCount(GenerationsCount, 0);
        SetCount(IssuesCount, 0);
        ResetPegasusDisplay();
        PegasusStatusText.Text = "Analyze a character to build the local Pegasus beta manifest.";
    }

    private static int SummaryInt(AnalysisReport report, string key)
    {
        if (!report.Summary.TryGetValue(key, out var value) || value is null) return 0;
        return Convert.ToInt32(value);
    }

    private static void SetCount(TextBlock control, int value)
        => control.Text = value.ToString("N0");

    private void SetBusy(bool busy)
    {
        BusyProgress.IsVisible = busy;
        RescanButton.IsEnabled = !busy;
        ResearchModeToggle.IsEnabled = !busy;
        CollectPetsBox.IsEnabled = !busy;
        CollectEggsBox.IsEnabled = !busy;
        CollectShipsBox.IsEnabled = !busy;
        CollectFreighterBox.IsEnabled = !busy;
        CollectFrigatesBox.IsEnabled = !busy;
        CollectMultitoolsBox.IsEnabled = !busy;
        CollectInventoryBox.IsEnabled = !busy;
        IncludeInventoryAmountsBox.IsEnabled = !busy;
        IncludeCustomNamesBox.IsEnabled = !busy;
        ContributorBox.IsEnabled = !busy;
        PrivateAttributionBox.IsEnabled = !busy;
        ContributionSourcePlatformBox.IsEnabled = !busy;
        ContributionCrossSaveBox.IsEnabled = !busy && ContributionSourceRequiresCrossSave();
        ExportPegasusButton.IsEnabled = !busy && _pegasusReport?.AssetCount > 0;
        ExportContributionButton.IsEnabled =
            !busy && _report?.ContributionRecords.Count > 0;
        AccountList.IsEnabled = !busy;
        CharacterList.IsEnabled = !busy;
        RevisionList.IsEnabled = !busy;
        PairButton.IsEnabled =
            !busy && ResearchModeToggle.IsChecked == true && _selectedCharacter is not null;
    }

    private void CancelCurrentOperation()
    {
        _operationCancellation?.Cancel();
        _operationCancellation?.Dispose();
        _operationCancellation = null;
    }
}
