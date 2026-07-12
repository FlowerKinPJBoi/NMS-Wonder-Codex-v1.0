using Avalonia.Controls;
using Avalonia.Interactivity;
using WonderCodex.Importer.Core.Models;
using WonderCodex.Importer.Core.Services;

namespace WonderCodex.Importer;

public sealed partial class MainWindow : Window
{
    private readonly ImporterCompositionRoot _services = new();
    private CancellationTokenSource? _operationCancellation;
    private SaveCharacter? _selectedCharacter;
    private AnalysisReport? _report;

    public MainWindow()
    {
        InitializeComponent();
        Opened += async (_, _) => await ScanAsync();
        Closed += (_, _) => _operationCancellation?.Cancel();
    }

    private async Task ScanAsync()
    {
        CancelCurrentOperation();
        _operationCancellation = new CancellationTokenSource();
        var cancellationToken = _operationCancellation.Token;

        SetBusy(true);
        ResetAnalysis();
        AccountList.ItemsSource = null;
        CharacterList.ItemsSource = null;
        StatusText.Text = "Scanning known Steam and Xbox / Game Pass PC locations locally…";

        try
        {
            var progress = new Progress<string>(message => StatusText.Text = message);
            var result = await _services.Discovery.ScanDefaultLocationsAsync(progress, cancellationToken);
            AccountList.ItemsSource = result.Accounts;

            if (result.Accounts.Count == 0)
            {
                StatusText.Text = "No readable No Man's Sky accounts were found in the standard locations. Nothing was changed.";
                return;
            }

            StatusText.Text = $"Found {result.Accounts.Count} account(s) and {result.CharacterCount} character(s). Select an account to continue.";
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
        _selectedCharacter = CharacterList.SelectedItem as SaveCharacter;
        ResetAnalysis();

        if (_selectedCharacter is null)
        {
            SelectedCharacterTitle.Text = "Select a character";
            SelectedCharacterDetail.Text = "No save has been selected.";
            AnalyzeButton.IsEnabled = false;
            return;
        }

        SelectedCharacterTitle.Text = _selectedCharacter.DisplayName;
        SelectedCharacterDetail.Text = $"{_selectedCharacter.PlatformLabel} • {_selectedCharacter.DetailLine}";
        AnalyzeButton.IsEnabled = true;
        StatusText.Text = "Character selected. Analysis reads the save again using FileAccess.Read only.";
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
            _report = _services.Analyzer.Analyze(document.RootElement, _selectedCharacter);

            UpdateAnalysisDisplay(_report);
            if (_report.DiscoveryCount == 0 && _report.MatchCount == 0)
            {
                StatusText.Text = "The save opened successfully, but no normalized Wonder records were found. Submission remains disabled.";
                SubmissionStatus.Text = "Nothing can be submitted from an empty analysis.";
                return;
            }

            StatusText.Text = $"Analysis complete: {_report.DiscoveryCount:N0} discoveries and {_report.MatchCount:N0} exact pet matches.";
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
            StatusText.Text = $"Analysis failed safely: {error.Message}";
            SubmissionStatus.Text = "No data was submitted and no save file was changed.";
        }
        finally
        {
            SetBusy(false);
            AnalyzeButton.IsEnabled = _selectedCharacter is not null;
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
    }

    private void ResetAnalysis()
    {
        _report = null;
        SubmitButton.IsEnabled = false;
        SubmissionStatus.Text = "Analyze a character before submitting.";
        PreviewList.ItemsSource = null;
        SetCount(DiscoveriesCount, 0);
        SetCount(AnimalsCount, 0);
        SetCount(FloraCount, 0);
        SetCount(MineralsCount, 0);
        SetCount(PetsCount, 0);
        SetCount(MatchesCount, 0);
        SetCount(GenerationsCount, 0);
        SetCount(IssuesCount, 0);
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
        AccountList.IsEnabled = !busy;
        CharacterList.IsEnabled = !busy;
    }

    private void CancelCurrentOperation()
    {
        _operationCancellation?.Cancel();
        _operationCancellation?.Dispose();
        _operationCancellation = null;
    }
}
